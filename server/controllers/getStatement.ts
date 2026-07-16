import { eq, or, desc } from 'drizzle-orm';
import { db } from '../db/index.js';
import { Users, Transfers } from '../db/schema.js';
import { FastifyRequest, FastifyReply } from 'fastify';

export async function getStatement(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { id } = request.params as { id: string };
    const { limit, role } = request.query as { limit?: string; role?: 'sender' | 'receiver' };

    const accNo = parseInt(id, 10);
    if (isNaN(accNo)) {
      return reply.status(400).send({ error: 'Invalid account number' });
    }

    // Verify account exists before attempting any transfer query
    const [account] = await db.select({ acc_no: Users.acc_no }).from(Users).where(eq(Users.acc_no, accNo)).limit(1);
    if (!account) return reply.status(404).send({ error: 'Account not found' });

    const maxLimit = limit ? parseInt(limit, 10) : undefined;

    let whereClause;
    if (role === 'sender') {
      whereClause = eq(Transfers.sender_acc, accNo);
    } else if (role === 'receiver') {
      whereClause = eq(Transfers.receiver_acc, accNo);
    } else {
      // No role — include all transfers this account was part of
      whereClause = or(eq(Transfers.sender_acc, accNo), eq(Transfers.receiver_acc, accNo));
    }

    const baseQuery = db
      .select()
      .from(Transfers)
      .where(whereClause)
      .orderBy(desc(Transfers.created_at));

    const transfers = await (maxLimit !== undefined ? baseQuery.limit(maxLimit) : baseQuery);
    return reply.status(200).send({ data: transfers });
  } catch (error: any) {
    request.log.error(error);
    return reply.status(500).send({ error: 'Internal Server Error' });
  }
}
