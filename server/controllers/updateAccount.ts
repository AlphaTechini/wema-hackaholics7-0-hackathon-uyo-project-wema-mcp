import { eq } from 'drizzle-orm';
import { db } from '../db/index.js';
import { Users } from '../db/schema.js';
import { FastifyRequest, FastifyReply } from 'fastify';

export async function updateAccount(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { id } = request.params as { id: string };
    const { email, phone_no } = request.body as any;
    const accNo = parseInt(id, 10);

    if (isNaN(accNo)) {
      return reply.status(400).send({ error: 'Invalid account number' });
    }

    const [updatedUser] = await db.update(Users)
      .set({ email, phone_no })
      .where(eq(Users.acc_no, accNo))
      .returning({
        acc_no: Users.acc_no,
        first_name: Users.first_name,
        last_name: Users.last_name,
        email: Users.email,
        phone_no: Users.phone_no,
        updated_at: Users.updated_at,
      });

    if (!updatedUser) {
      return reply.status(404).send({ error: 'Account not found' });
    }

    return reply.status(200).send({ message: 'Account updated successfully', data: updatedUser });
  } catch (error: any) {
    request.log.error(error);
    if (error.code === '23505') {
      return reply.status(409).send({ error: 'Email already exists' });
    }
    return reply.status(500).send({ error: 'Internal Server Error' });
  }
}
