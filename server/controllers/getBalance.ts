import { eq } from 'drizzle-orm';
import { FastifyRequest, FastifyReply } from 'fastify';
import { db } from '../db/index.js';
import { Users } from '../db/schema.js';

export async function getBalance(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { id } = request.params as { id: string };
    const accNo = parseInt(id, 10);

    if (isNaN(accNo)) {
      return reply.status(400).send({ error: 'Invalid account number' });
    }

    const [account] = await db
      .select({ acc_no: Users.acc_no, acc_balance: Users.acc_balance })
      .from(Users)
      .where(eq(Users.acc_no, accNo))
      .limit(1);

    if (!account) {
      return reply.status(404).send({ error: 'Account not found' });
    }

    return reply.status(200).send({ data: account });
  } catch (error: any) {
    request.log.error(error);
    return reply.status(500).send({ error: 'Internal Server Error' });
  }
}
