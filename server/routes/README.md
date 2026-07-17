# Routes

This directory defines the Fastify route endpoints and their associated validation schemas.

I opted to use Fastify's native JSON Schema validation for inputs instead of external libraries like Typebox. This keeps dependencies minimal while ensuring robust runtime validation.

- To find the account and balance routes visit [accounts.ts](accounts.ts).
- To find Telegram ban status routes visit [telegramSecurity.ts](telegramSecurity.ts).
- To find the transfers routes visit [transfers.ts](transfers.ts).
