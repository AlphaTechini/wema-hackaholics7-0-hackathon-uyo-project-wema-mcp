import type { FastifyInstance } from 'fastify';
import { handleMcpRequest } from './transport.js';

export function registerMcp(fastify: FastifyInstance): void {
  fastify.route({
    method: ['GET', 'POST', 'DELETE'],
    url: '/mcp',
    handler: (request, reply) => handleMcpRequest(fastify, request, reply),
  });
}
