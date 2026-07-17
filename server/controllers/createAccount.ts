import { FastifyRequest, FastifyReply } from 'fastify';
import { createAccount as createAccountRecord } from '../services/createAccount.js';

export async function createAccount(request: FastifyRequest, reply: FastifyReply) {
  try {
    const { first_name, last_name, email, phone_no, pin } = request.body as any;

    const newUser = await createAccountRecord({
      first_name,
      last_name,
      email,
      phone_no,
      pin,
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
