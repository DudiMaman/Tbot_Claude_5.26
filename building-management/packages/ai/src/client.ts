import Anthropic from '@anthropic-ai/sdk';

export const DEFAULT_MODEL = 'claude-sonnet-4-6';

let client: Anthropic | undefined;

export function getAnthropic(): Anthropic {
  if (client) return client;
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY is not set');
  }
  client = new Anthropic({ apiKey });
  return client;
}

export interface CompletionOptions {
  model?: string;
  systemPrompt: string;
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
  tools?: Anthropic.Messages.Tool[];
  maxTokens?: number;
  temperature?: number;
}

export async function complete(options: CompletionOptions): Promise<Anthropic.Messages.Message> {
  return getAnthropic().messages.create({
    model: options.model ?? DEFAULT_MODEL,
    system: options.systemPrompt,
    messages: options.messages,
    tools: options.tools,
    max_tokens: options.maxTokens ?? 1024,
    temperature: options.temperature ?? 0.3,
  });
}
