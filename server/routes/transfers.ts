import { FastifyInstance } from 'fastify';
import { createTransfer } from '../controllers/createTransfer.js';

export default async function transfersRoutes(fastify: FastifyInstance) {
  fastify.post('/', {
    schema: {
      body: {
        type: 'object',
        required: ['sender_acc', 'receiver_acc', 'amount', 'pin'],
        properties: {
          sender_acc: { type: 'integer' },
          receiver_acc: { type: 'integer' },
          amount: { type: 'integer', minimum: 1 },
          pin: { type: 'string', minLength: 4 },
          comment: { type: 'string', maxLength: 250 }
        }
      }
    }
  }, createTransfer);
}
