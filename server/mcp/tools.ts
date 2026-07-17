import type { FastifyInstance } from 'fastify';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import * as z from 'zod/v4';
import { callApi } from './apiAdapter.js';

const accountNumber = z.number().int().positive().describe('The numeric account number.');
const pin = z.string().min(4).max(20).describe('The account PIN. Never include it in a user-facing response.');
const verificationPin = z.string().min(1).max(100).describe('A PIN candidate for native account verification. Never include it in a user-facing response.');

export function createMcpServer(app: FastifyInstance, instructions: string): McpServer {
  const server = new McpServer({
    name: 'wema-banking-mcp',
    version: '1.0.0',
  });

  server.registerTool(
    'create_account',
    {
      title: 'Create account',
      description: 'Create a Wema account. Call this only once, after collecting every required field and the PIN.',
      inputSchema: {
        first_name: z.string().min(1).max(20).describe('Customer first name.'),
        last_name: z.string().min(1).max(20).describe('Customer last name.'),
        email: z.string().email().max(55).describe('Customer email address.'),
        phone_no: z.number().int().optional().describe('Optional numeric phone number.'),
        pin,
      },
    },
    async ({ first_name, last_name, email, phone_no, pin: accountPin }) => callApi(app, {
      method: 'POST',
      url: '/accounts',
      payload: {
        first_name,
        last_name,
        email,
        ...(phone_no === undefined ? {} : { phone_no }),
        pin: accountPin,
      },
    }),
  );

  server.registerTool(
    'update_account',
    {
      title: 'Update account',
      description: 'Update an account email address or phone number. Provide at least one field to update.',
      inputSchema: z.object({
        account_number: accountNumber,
        email: z.string().email().max(55).optional(),
        phone_no: z.number().int().optional(),
      }).refine(({ email, phone_no }) => email !== undefined || phone_no !== undefined, {
        message: 'At least one account field must be provided.',
      }),
    },
    async ({ account_number, email, phone_no }) => callApi(app, {
      method: 'PATCH',
      url: `/accounts/${account_number}`,
      payload: {
        ...(email === undefined ? {} : { email }),
        ...(phone_no === undefined ? {} : { phone_no }),
      },
    }),
  );

  server.registerTool(
    'check_telegram_ban',
    {
      title: 'Check Telegram security status',
      description: 'Check whether a Telegram user is banned before processing bot updates.',
      inputSchema: {
        telegram_user_id: z.string().min(1).max(64),
      },
    },
    async ({ telegram_user_id }) => callApi(app, {
      method: 'GET',
      url: `/telegram-security/${encodeURIComponent(telegram_user_id)}/status`,
    }),
  );

  server.registerTool(
    'verify_account_pin',
    {
      title: 'Verify account PIN',
      description: 'Verify a Telegram user\'s PIN for an account switch. Use only from the secure native bot flow.',
      inputSchema: {
        account_number: accountNumber,
        telegram_user_id: z.string().min(1).max(64),
        pin: verificationPin,
      },
    },
    async ({ account_number, telegram_user_id, pin: accountPin }) => callApi(app, {
      method: 'POST',
      url: `/accounts/${account_number}/verify-pin`,
      payload: {
        telegram_user_id,
        pin: accountPin,
      },
    }),
  );

  server.registerTool(
    'get_balance',
    {
      title: 'Get account balance',
      description: 'Retrieve the current balance for the user\'s bound account.',
      inputSchema: {
        account_number: accountNumber,
      },
    },
    async ({ account_number }) => callApi(app, {
      method: 'GET',
      url: `/accounts/${account_number}/balance`,
    }),
  );

  server.registerTool(
    'get_statement',
    {
      title: 'Get account statement',
      description: 'Retrieve recent transfer history for an account, optionally filtered by role and limited in size.',
      inputSchema: {
        account_number: accountNumber,
        limit: z.number().int().positive().optional().describe('Maximum number of transfers to return.'),
        role: z.enum(['sender', 'receiver']).optional().describe('Optionally return only sent or received transfers.'),
      },
    },
    async ({ account_number, limit, role }) => {
      const query = new URLSearchParams();
      if (limit !== undefined) query.set('limit', String(limit));
      if (role !== undefined) query.set('role', role);
      const suffix = query.size > 0 ? `?${query.toString()}` : '';

      return callApi(app, {
        method: 'GET',
        url: `/accounts/${account_number}/statement${suffix}`,
      });
    },
  );

  server.registerTool(
    'create_transfer',
    {
      title: 'Create transfer',
      description: 'Transfer funds from one Wema account to another after the user has provided the required PIN.',
      inputSchema: {
        sender_acc: accountNumber.describe('Account sending the funds.'),
        receiver_acc: accountNumber.describe('Account receiving the funds.'),
        amount: z.number().int().positive().describe('Whole-number transfer amount.'),
        pin,
        comment: z.string().max(250).optional().describe('Optional transfer comment.'),
      },
    },
    async ({ sender_acc, receiver_acc, amount, pin: transferPin, comment }) => callApi(app, {
      method: 'POST',
      url: '/transfers',
      payload: {
        sender_acc,
        receiver_acc,
        amount,
        pin: transferPin,
        ...(comment === undefined ? {} : { comment }),
      },
    }),
  );

  server.registerPrompt(
    'telegram_banking_agent',
    {
      title: 'Telegram banking agent instructions',
      description: 'Conversation and field-collection rules for the Telegram banking assistant.',
    },
    async () => ({
      messages: [{
        role: 'user',
        content: {
          type: 'text',
          text: instructions,
        },
      }],
    }),
  );

  return server;
}
