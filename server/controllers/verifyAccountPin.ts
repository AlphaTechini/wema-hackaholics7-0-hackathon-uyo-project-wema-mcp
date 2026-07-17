import { FastifyRequest, FastifyReply } from 'fastify';
import { verifyAccountPin as verifyAccountPinService } from '../services/verifyAccountPin.js';

export async function verifyAccountPin(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { id } = request.params as { id: string };
    const { telegram_user_id, pin } = request.body as {
      telegram_user_id: string;
      pin: string;
    };
    const accountNumber = parseInt(id, 10);

    if (isNaN(accountNumber)) {
      return reply.status(400).send({ error: 'Invalid account number' });
    }

    const result = await verifyAccountPinService({
      telegram_user_id,
      account_number: accountNumber,
      pin,
    });

    if (result.status === 'banned') {
      return reply.status(403).send({ error: 'User is banned' });
    }

    if (result.status === 'failed') {
      return reply.status(401).send({
        error: 'Account verification failed',
        attempts_remaining: result.attempts_remaining,
      });
    }

    return reply.status(200).send({ data: result });
  } catch (error: any) {
    request.log.error(error);
    return reply.status(500).send({ error: 'Internal Server Error' });
  }
}
