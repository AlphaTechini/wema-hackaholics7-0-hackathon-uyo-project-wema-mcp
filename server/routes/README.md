# Routes

This directory defines the Fastify route endpoints and their associated validation schemas.

I opted to use Fastify's native JSON Schema validation for inputs instead of external libraries like Typebox. This keeps dependencies minimal while ensuring robust runtime validation.

- To find the accounts routes visit [accounts.ts](accounts.ts).
- To find the transfers routes visit [transfers.ts](transfers.ts).
