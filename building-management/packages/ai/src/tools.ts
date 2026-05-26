/**
 * Tool definitions for the AI bot.
 * Each tool has a JSON schema and a runtime handler signature.
 * The actual execution lives in `apps/api/src/modules/ai-bot/tool-registry.ts`
 * which wires Claude tool calls to NestJS services.
 */

import type Anthropic from '@anthropic-ai/sdk';

export const lookupBalanceTool: Anthropic.Messages.Tool = {
  name: 'lookup_balance',
  description:
    "Look up a person's outstanding charges for their apartment. " +
    'For renters returns only charges billed to them; for owners returns all charges for the apartment.',
  input_schema: {
    type: 'object',
    properties: {
      person_id: { type: 'string', format: 'uuid' },
      apartment_id: { type: 'string', format: 'uuid' },
    },
    required: ['person_id'],
  },
};

export const lookupTicketTool: Anthropic.Messages.Tool = {
  name: 'lookup_ticket',
  description: 'Get the status and history of a service ticket.',
  input_schema: {
    type: 'object',
    properties: { ticket_id: { type: 'string', format: 'uuid' } },
    required: ['ticket_id'],
  },
};

export const createTicketTool: Anthropic.Messages.Tool = {
  name: 'create_ticket',
  description:
    'Open a new service ticket on behalf of the resident. Use when the user describes a maintenance issue.',
  input_schema: {
    type: 'object',
    properties: {
      person_id: { type: 'string', format: 'uuid' },
      apartment_id: { type: 'string', format: 'uuid' },
      category: {
        type: 'string',
        enum: [
          'plumbing',
          'electrical',
          'elevator',
          'cleaning',
          'security',
          'hvac',
          'common_area',
          'access',
          'billing',
          'other',
        ],
      },
      priority: { type: 'string', enum: ['low', 'med', 'high', 'urgent'] },
      title: { type: 'string' },
      description: { type: 'string' },
      photos: { type: 'array', items: { type: 'string' } },
    },
    required: ['person_id', 'apartment_id', 'category', 'title'],
  },
};

export const scheduleCallbackTool: Anthropic.Messages.Tool = {
  name: 'schedule_callback',
  description: 'Schedule a callback from the management team.',
  input_schema: {
    type: 'object',
    properties: {
      person_id: { type: 'string', format: 'uuid' },
      when: { type: 'string', description: 'ISO 8601 datetime' },
      reason: { type: 'string' },
    },
    required: ['person_id', 'when'],
  },
};

export const buildingInfoTool: Anthropic.Messages.Tool = {
  name: 'building_info',
  description: 'Get information about a building from the FAQ knowledge base.',
  input_schema: {
    type: 'object',
    properties: {
      building_id: { type: 'string', format: 'uuid' },
      key: { type: 'string', description: 'Topic key e.g. "garbage_schedule", "elevator_service"' },
    },
    required: ['building_id', 'key'],
  },
};

export const searchKbTool: Anthropic.Messages.Tool = {
  name: 'search_kb',
  description:
    'Search the management company knowledge base for relevant information. ' +
    'Use this whenever the user asks something specific to the building.',
  input_schema: {
    type: 'object',
    properties: {
      query: { type: 'string' },
      building_id: { type: 'string', format: 'uuid' },
    },
    required: ['query'],
  },
};

export const whoIsMyBillPayerTool: Anthropic.Messages.Tool = {
  name: 'who_is_my_bill_payer',
  description: 'Find who is currently responsible for paying va\'ad fees for an apartment.',
  input_schema: {
    type: 'object',
    properties: {
      apartment_id: { type: 'string', format: 'uuid' },
    },
    required: ['apartment_id'],
  },
};

export const escalateToHumanTool: Anthropic.Messages.Tool = {
  name: 'escalate_to_human',
  description: 'Hand the conversation off to a human agent. Use sparingly.',
  input_schema: {
    type: 'object',
    properties: {
      reason: { type: 'string' },
      urgency: { type: 'string', enum: ['low', 'med', 'high'] },
    },
    required: ['reason'],
  },
};

export const ALL_BOT_TOOLS: Anthropic.Messages.Tool[] = [
  lookupBalanceTool,
  lookupTicketTool,
  createTicketTool,
  scheduleCallbackTool,
  buildingInfoTool,
  searchKbTool,
  whoIsMyBillPayerTool,
  escalateToHumanTool,
];
