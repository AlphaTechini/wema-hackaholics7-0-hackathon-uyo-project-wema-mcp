import { FastifyInstance } from 'fastify';
import { createAccount } from '../controllers/createAccount.js';
import { updateAccount } from '../controllers/updateAccount.js';
import { getBalance } from '../controllers/getBalance.js';
import { verifyAccountPin } from '../controllers/verifyAccountPin.js';
import { getStatement } from '../controllers/getStatement.js';

export default async function accountsRoutes(fastify: FastifyInstance) {
  fastify.post('/', {
    schema: {
      body: {
        type: 'object',
        required: ['first_name', 'last_name', 'email', 'pin'],
        properties: {
          first_name: { type: 'string', minLength: 1, maxLength: 20 },
          last_name: { type: 'string', minLength: 1, maxLength: 20 },
          email: { type: 'string', format: 'email', maxLength: 55 },
          phone_no: { type: 'integer' },
          pin: { type: 'string', minLength: 4, maxLength: 20 }
        }
      }
    }
  }, createAccount);

  fastify.patch('/:id', {
    schema: {
      params: {
        type: 'object',
        required: ['id'],
        properties: {
          id: { type: 'string' }
        }
      },
      body: {
        type: 'object',
        properties: {
          email: { type: 'string', format: 'email', maxLength: 55 },
          phone_no: { type: 'integer' }
        },
        additionalProperties: false
      }
    }
  }, updateAccount);

  fastify.get('/:id/balance', {
    schema: {
      params: {
        type: 'object',
        required: ['id'],
        properties: {
          id: { type: 'string' }
        }
      }
    }
  }, getBalance);

  fastify.post('/:id/verify-pin', {
    schema: {
      params: {
        type: 'object',
        required: ['id'],
        properties: {
          id: { type: 'string' }
        }
      },
      body: {
        type: 'object',
        required: ['telegram_user_id', 'pin'],
        additionalProperties: false,
        properties: {
          telegram_user_id: { type: 'string', minLength: 1, maxLength: 64 },
          pin: { type: 'string', minLength: 1, maxLength: 100 }
        }
      }
    }
  }, verifyAccountPin);

  fastify.get('/:id/statement', {
    schema: {
      params: {
        type: 'object',
        required: ['id'],
        properties: {
          id: { type: 'string' }
        }
      },
      querystring: {
        type: 'object',
        properties: {
          limit: { type: 'string', pattern: '^[0-9]+$' },
          role: { type: 'string', enum: ['sender', 'receiver'] }
        }
      }
    }
  }, getStatement);
}
