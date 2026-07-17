import { FastifyRequest, FastifyReply } from 'fastify';
import { isTelegramUserBanned } from '../services/verifyAccountPin.js';

export async function getTelegramSecurityStatus(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { user_id } = request.params as { user_id: string };
    const banned = await isTelegramUserBanned(user_id);
    return reply.status(200).send({ data: { banned } });
  } catch (error: any) {
    request.log.error(error);
    return reply.status(500).send({ error: 'Internal Server Error' });
  }
}
