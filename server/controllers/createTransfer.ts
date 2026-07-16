import { eq } from 'drizzle-orm';
import { db } from '../db/index.js';
import { Users, Transfers } from '../db/schema.js';
import argon2 from 'argon2';
import { FastifyRequest, FastifyReply } from 'fastify';

export async function createTransfer(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { sender_acc, receiver_acc, amount, pin, comment } = request.body as any;

    if (sender_acc === receiver_acc) {
      return reply.status(400).send({ error: 'Cannot transfer to the same account' });
    }
    if (amount <= 0) {
      return reply.status(400).send({ error: 'Transfer amount must be greater than zero' });
    }

    const result = await db.transaction(async (tx: any) => {
      const [sender] = await tx.select().from(Users).where(eq(Users.acc_no, sender_acc)).limit(1);
      if (!sender) throw new Error('SENDER_NOT_FOUND');

      const isPinValid = await argon2.verify(sender.pin, pin);
      if (!isPinValid) throw new Error('INVALID_PIN');

      if (sender.acc_balance < amount) throw new Error('INSUFFICIENT_FUNDS');

      const [receiver] = await tx.select().from(Users).where(eq(Users.acc_no, receiver_acc)).limit(1);
      if (!receiver) throw new Error('RECEIVER_NOT_FOUND');

      await tx.update(Users).set({ acc_balance: sender.acc_balance - amount }).where(eq(Users.acc_no, sender_acc));
      await tx.update(Users).set({ acc_balance: receiver.acc_balance + amount }).where(eq(Users.acc_no, receiver_acc));

      const [transfer] = await tx.insert(Transfers).values({
        sender_acc,
        receiver_acc,
        amount,
        comment,
      }).returning();

      return transfer;
    });

    return reply.status(201).send({ message: 'Transfer successful', data: result });
  } catch (error: any) {
    request.log.error(error);
    switch (error.message) {
      case 'SENDER_NOT_FOUND': return reply.status(404).send({ error: 'Sender account not found' });
      case 'RECEIVER_NOT_FOUND': return reply.status(404).send({ error: 'Receiver account not found' });
      case 'INVALID_PIN': return reply.status(401).send({ error: 'Invalid PIN' });
      case 'INSUFFICIENT_FUNDS': return reply.status(400).send({ error: 'Insufficient funds' });
      default: return reply.status(500).send({ error: 'Internal Server Error' });
    }
  }
}
