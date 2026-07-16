import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createMcpServer } from './tools.js';

const instructionsPath = fileURLToPath(new URL('./telegram-agent-instructions.md', import.meta.url));
const instructions = readFileSync(instructionsPath, 'utf8');

function writeInternalError(reply: FastifyReply): void {
  if (reply.raw.headersSent) {
    reply.raw.end();
    return;
  }

  reply.raw.writeHead(500, { 'content-type': 'application/json' });
  reply.raw.end(JSON.stringify({ error: 'MCP request failed.' }));
}

export async function handleMcpRequest(
  app: FastifyInstance,
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<void> {
  reply.hijack();

  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  const mcpServer = createMcpServer(app, instructions);

  try {
    await mcpServer.connect(transport);
    await transport.handleRequest(request.raw, reply.raw, request.body);
  } catch {
    writeInternalError(reply);
  } finally {
    await mcpServer.close().catch(() => undefined);
  }
}
