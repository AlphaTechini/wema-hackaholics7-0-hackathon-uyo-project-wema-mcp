import type { FastifyInstance } from 'fastify';
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';

type ApiRequest = {
  method: 'GET' | 'POST' | 'PATCH';
  url: string;
  payload?: Record<string, unknown>;
};

function parseResponseBody(body: string): unknown {
  if (!body) return {};

  try {
    return JSON.parse(body);
  } catch {
    return { message: body };
  }
}

function formatResultBody(body: unknown): string {
  return typeof body === 'string' ? body : JSON.stringify(body);
}

export async function callApi(app: FastifyInstance, request: ApiRequest): Promise<CallToolResult> {
  try {
    const response = await app.inject({
      method: request.method,
      url: request.url,
      payload: request.payload,
    });
    const body = parseResponseBody(response.body);

    if (response.statusCode >= 400) {
      const message = typeof body === 'object' && body !== null && 'error' in body
        ? String(body.error)
        : `API request failed with status ${response.statusCode}`;

      return {
        content: [{ type: 'text', text: JSON.stringify({ error: message, status: response.statusCode }) }],
        isError: true,
      };
    }

    return {
      content: [{ type: 'text', text: formatResultBody(body) }],
    };
  } catch {
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: 'The banking API is unavailable.' }) }],
      isError: true,
    };
  }
}
