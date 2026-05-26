/**
 * Ticket classifier — calls Claude with a tight JSON-only prompt.
 *
 * Pure function from text (+ optional image) to category + priority.
 * Mockable: if ANTHROPIC_API_KEY is missing, returns a deterministic
 * heuristic so dev environments still work end-to-end.
 */

import { getAnthropic, DEFAULT_MODEL } from './client';
import { TICKET_CLASSIFIER_PROMPT } from './prompts';

export type TicketCategory =
  | 'plumbing'
  | 'electrical'
  | 'elevator'
  | 'cleaning'
  | 'security'
  | 'hvac'
  | 'common_area'
  | 'access'
  | 'billing'
  | 'other';

export type TicketPriority = 'low' | 'med' | 'high' | 'urgent';

export interface ClassifyResult {
  category: TicketCategory;
  priority: TicketPriority;
  confidence: number;
  source: 'ai' | 'heuristic';
}

export async function classifyTicket(
  text: string,
  photoUrls: string[] = [],
): Promise<ClassifyResult> {
  if (!process.env.ANTHROPIC_API_KEY) {
    return heuristicClassify(text);
  }

  try {
    const result = await getAnthropic().messages.create({
      model: process.env.ANTHROPIC_MODEL ?? DEFAULT_MODEL,
      system: TICKET_CLASSIFIER_PROMPT,
      max_tokens: 200,
      temperature: 0,
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text },
            ...photoUrls.slice(0, 4).map(
              (url) =>
                ({
                  type: 'image',
                  source: { type: 'url', url },
                }) as const,
            ),
          ],
        },
      ],
    });
    const block = result.content.find((c) => c.type === 'text');
    const json = block && 'text' in block ? JSON.parse(block.text) : null;
    if (!json) return heuristicClassify(text);
    return {
      category: json.category as TicketCategory,
      priority: json.priority as TicketPriority,
      confidence: Number(json.confidence) || 0.5,
      source: 'ai',
    };
  } catch {
    return heuristicClassify(text);
  }
}

const HEURISTIC: Record<string, { category: TicketCategory; priority: TicketPriority }> = {
  נזיל: { category: 'plumbing', priority: 'high' },
  צינור: { category: 'plumbing', priority: 'med' },
  ביוב: { category: 'plumbing', priority: 'high' },
  כיור: { category: 'plumbing', priority: 'med' },
  אסלה: { category: 'plumbing', priority: 'med' },
  חשמל: { category: 'electrical', priority: 'high' },
  נורה: { category: 'electrical', priority: 'low' },
  מעלית: { category: 'elevator', priority: 'high' },
  ניקיון: { category: 'cleaning', priority: 'low' },
  זבל: { category: 'cleaning', priority: 'low' },
  אשפה: { category: 'cleaning', priority: 'low' },
  גינה: { category: 'common_area', priority: 'low' },
  שער: { category: 'access', priority: 'med' },
  חניה: { category: 'access', priority: 'med' },
  מצלמ: { category: 'security', priority: 'med' },
  פריצה: { category: 'security', priority: 'urgent' },
  מזגן: { category: 'hvac', priority: 'med' },
  חיוב: { category: 'billing', priority: 'med' },
};

function heuristicClassify(text: string): ClassifyResult {
  const lower = text.toLowerCase();
  for (const [keyword, hit] of Object.entries(HEURISTIC)) {
    if (lower.includes(keyword)) {
      return { ...hit, confidence: 0.6, source: 'heuristic' };
    }
  }
  return { category: 'other', priority: 'med', confidence: 0.3, source: 'heuristic' };
}
