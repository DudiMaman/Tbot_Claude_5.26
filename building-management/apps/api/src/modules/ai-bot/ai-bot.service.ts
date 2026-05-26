/**
 * AiBotService — customer-service AI bot powered by Claude.
 * Implements the tool registry from packages/ai/src/tools.ts and routes
 * tool calls to NestJS services.
 *
 * See SPEC §14.
 */
import { Injectable, Logger } from '@nestjs/common';
import { complete, CUSTOMER_SERVICE_PROMPT_V1, ALL_BOT_TOOLS, type PromptContext } from '@bm/ai';
import { DbService } from '../../db/db.service';
import { AssignmentService } from '../apartments/assignment.service';
import { TicketsService } from '../tickets/tickets.service';
import type { Message } from '@bm/db';

@Injectable()
export class AiBotService {
  private readonly logger = new Logger(AiBotService.name);

  constructor(
    private readonly db: DbService,
    private readonly assignments: AssignmentService,
    private readonly tickets: TicketsService,
  ) {}

  /**
   * Send a user turn into the conversation. The bot processes it, possibly
   * calls tools, and returns its reply. Returns escalation signal if needed.
   */
  async respond(
    tenantId: string,
    conversationId: string,
    userText: string,
  ): Promise<{ reply: string; escalated: boolean; tools_used: string[] }> {
    // Load context: conversation + person info
    const ctx = await this.loadContext(tenantId, conversationId);
    const systemPrompt = CUSTOMER_SERVICE_PROMPT_V1(ctx.promptCtx);
    const recentMessages = await this.loadRecentMessages(conversationId);

    // First call
    if (!process.env.ANTHROPIC_API_KEY) {
      // Mock: simple keyword routing
      return this.mockRespond(userText, ctx.promptCtx);
    }

    const result = await complete({
      systemPrompt,
      messages: [
        ...recentMessages.map((m) => ({
          role: (m.direction === 'in' ? 'user' : 'assistant') as 'user' | 'assistant',
          content: m.body ?? '',
        })),
        { role: 'user', content: userText },
      ],
      tools: ALL_BOT_TOOLS,
    });

    // Walk tool calls (simplified: not looping for brevity in skeleton)
    const toolsUsed: string[] = [];
    let escalated = false;
    let replyText = '';
    for (const block of result.content) {
      if (block.type === 'text') {
        replyText += block.text;
      } else if (block.type === 'tool_use') {
        toolsUsed.push(block.name);
        if (block.name === 'escalate_to_human') escalated = true;
        await this.executeTool(tenantId, ctx, block.name, block.input as any);
      }
    }
    if (!replyText) replyText = 'אני אשמח לעזור — תוכלו לפרט יותר?';

    return { reply: replyText, escalated, tools_used: toolsUsed };
  }

  private async executeTool(
    tenantId: string,
    ctx: { promptCtx: PromptContext; personId?: string },
    name: string,
    input: Record<string, any>,
  ) {
    switch (name) {
      case 'lookup_balance':
        return this.lookupBalance(tenantId, input.person_id ?? ctx.personId);
      case 'create_ticket':
        return this.tickets.create(tenantId, input.person_id ?? ctx.personId ?? null, {
          building_id: input.building_id ?? '',
          apartment_id: input.apartment_id,
          title: input.title,
          description: input.description,
          category: input.category,
          priority: input.priority,
          photos: input.photos ?? [],
        });
      case 'who_is_my_bill_payer':
        return this.assignments.listCurrent(tenantId, input.apartment_id);
      // Other tools: noop in skeleton
      default:
        return { ok: true };
    }
  }

  private async lookupBalance(tenantId: string, personId?: string) {
    if (!personId) return [];
    const { rows } = await this.db.query(
      `select id, description, amount, due_date, status
       from charges
       where tenant_id = $1 and billed_to_person_id = $2
         and status in ('pending', 'partial', 'overdue')
       order by due_date`,
      [tenantId, personId],
    );
    return rows;
  }

  private async loadContext(tenantId: string, conversationId: string): Promise<{
    promptCtx: PromptContext;
    personId?: string;
  }> {
    const { rows } = await this.db.query<{
      tenant_name: string;
      person_id: string | null;
      full_name: string | null;
      building_id: string | null;
      building_name: string | null;
      apartment_unit: string | null;
    }>(
      `select t.name as tenant_name, c.person_id, p.full_name,
              c.building_id, b.name as building_name, a.unit_number as apartment_unit
       from conversations c
       join tenants t on t.id = c.tenant_id
       left join people p on p.id = c.person_id
       left join buildings b on b.id = c.building_id
       left join apartments a on a.id = c.apartment_id
       where c.id = $1`,
      [conversationId],
    );
    const r = rows[0];
    return {
      personId: r?.person_id ?? undefined,
      promptCtx: {
        tenant_name: r?.tenant_name ?? '',
        building_name: r?.building_name ?? undefined,
        person_name: r?.full_name ?? undefined,
        apartment_unit: r?.apartment_unit ?? undefined,
        language: 'he',
        business_hours_open: this.isBusinessHours(),
      },
    };
  }

  private async loadRecentMessages(conversationId: string): Promise<Message[]> {
    const { rows } = await this.db.query<Message>(
      `select * from messages where conversation_id = $1 order by created_at desc limit 20`,
      [conversationId],
    );
    return rows.reverse();
  }

  private isBusinessHours(): boolean {
    const d = new Date();
    const h = (d.getUTCHours() + 3) % 24; // Israel offset
    const dow = d.getDay();
    return dow >= 0 && dow <= 4 && h >= 9 && h < 18;
  }

  private mockRespond(text: string, ctx: PromptContext) {
    const lower = text.toLowerCase();
    if (/בן.?אדם|נציג|אנושי/.test(text)) {
      return {
        reply: 'אני מעביר אתכם לנציג אנושי. צוות השירות יחזור אליכם בקרוב.',
        escalated: true,
        tools_used: ['escalate_to_human'],
      };
    }
    if (/חיוב|יתרה|לשלם/.test(text)) {
      return {
        reply: `שלום ${ctx.person_name ?? ''}. אבדוק את החיובים הפתוחים שלכם. ${ctx.outstanding_balance ?? ''}`,
        escalated: false,
        tools_used: ['lookup_balance'],
      };
    }
    if (/תקלה|בעיה|נזיל|לא עובד/.test(text)) {
      return {
        reply: 'אצור עבורכם פנייה. נא תיאור קצר של המיקום והתקלה.',
        escalated: false,
        tools_used: [],
      };
    }
    return { reply: 'תוכלו לפרט יותר במה אוכל לעזור?', escalated: false, tools_used: [] };
  }
}
