import { db } from '../db/index.js';
import { Users } from '../db/schema.js';
import argon2 from 'argon2';
import crypto from 'crypto';
import { FastifyRequest, FastifyReply } from 'fastify';

function generateAccNo(email: string): number {
  const hash = crypto.createHash('sha256').update(email).digest('hex');
  const numbersOnly = BigInt('0x' + hash.substring(0, 15)).toString(10);
  return parseInt(numbersOnly.substring(0, 10).padEnd(10, '1'), 10);
}

export async function createAccount(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { first_name, last_name, email, phone_no, pin } = request.body as any;

    const hashedPin = await argon2.hash(pin);
    const accNo = generateAccNo(email);

    const [newUser] = await db.insert(Users).values({
      acc_no: accNo,
      first_name,
      last_name,
      email,
      phone_no,
      pin: hashedPin,
    }).returning({
      acc_no: Users.acc_no,
      first_name: Users.first_name,
      last_name: Users.last_name,
      email: Users.email,
      phone_no: Users.phone_no,
      acc_balance: Users.acc_balance,
      created_at: Users.created_at,
    });

    return reply.status(201).send({ message: 'Account created successfully', data: newUser });
  } catch (error: any) {
    request.log.error(error);
    if (error.code === '23505') {
      return reply.status(409).send({ error: 'Email already exists' });
    }
    return reply.status(500).send({ error: 'Internal Server Error' });
  }
}
