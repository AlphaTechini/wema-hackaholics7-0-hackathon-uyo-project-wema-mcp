import fastify from 'fastify';
import accountsRoutes from './routes/accounts.js';
import transfersRoutes from './routes/transfers.js';
import telegramSecurityRoutes from './routes/telegramSecurity.js';
import { registerMcp } from './mcp/register.js';
import 'dotenv/config';

const server = fastify({
  logger: true
});

server.register(accountsRoutes, { prefix: '/accounts' });
server.register(transfersRoutes, { prefix: '/transfers' });
server.register(telegramSecurityRoutes, { prefix: '/telegram-security' });
registerMcp(server);

const start = async () => {
  try {
    const port = Number(process.env.PORT ?? 3870);
    await server.listen({ port, host: '0.0.0.0' });
    console.log(`Server listening on http://localhost:${port}`);
  } catch (err) {
    server.log.error(err);
    process.exit(1);
  }
};

start();
