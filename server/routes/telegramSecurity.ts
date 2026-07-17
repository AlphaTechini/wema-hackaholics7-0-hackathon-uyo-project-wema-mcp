import { FastifyInstance } from 'fastify';
import { getTelegramSecurityStatus } from '../controllers/getTelegramSecurityStatus.js';

export default async function telegramSecurityRoutes(fastify: FastifyInstance) {
  fastify.get('/:user_id/status', {
    schema: {
      params: {
        type: 'object',
        required: ['user_id'],
        properties: {
          user_id: { type: 'string', minLength: 1, maxLength: 64 }
        }
      }
    }
  }, getTelegramSecurityStatus);
}
