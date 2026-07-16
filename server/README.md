# Server

This directory contains the Fastify application, database integration, and mounted MCP service.

I decided to use Fastify for its high performance and built-in schema validation capabilities. The entry point leverages modern ESM syntax.

To find the main server initialization logic, visit [server.ts](server.ts).

The MCP endpoint is available at `/mcp` on the same host and port as the REST API. It uses the official Streamable HTTP protocol and exposes account creation, account updates, statements, transfers, and the Telegram agent prompt. The default port is `3870`; deployments can override it with the `PORT` environment variable.

- To find MCP integration logic visit [mcp/README.md](mcp/README.md).
- To find container packaging visit [Dockerfile](Dockerfile).
- To find runtime configuration fields visit [.env.example](.env.example).
