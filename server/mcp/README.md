# MCP

This directory contains the official MCP Streamable HTTP adapter for the Wema banking API.

The MCP server is mounted at `/mcp` by the Fastify application. It uses stateless transport so requests can be handled by different GCP service instances without in-memory session affinity.

- To find MCP route registration visit [register.ts](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/register.ts).
- To find Streamable HTTP handling visit [transport.ts](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/transport.ts).
- To find the exposed banking tools and MCP prompt visit [tools.ts](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/tools.ts).
- To find the in-process API connection visit [apiAdapter.ts](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/apiAdapter.ts).
- To find the Telegram conversation rules visit [telegram-agent-instructions.md](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/telegram-agent-instructions.md).

The MCP tools call the existing Fastify routes through `fastify.inject`. This keeps API validation and business logic in the existing route and controller modules instead of creating a second database implementation.

The prompt is discoverable as `telegram_banking_agent`. MCP clients must request that prompt or load the Markdown file as their system instructions; MCP does not automatically inject prompts into every model conversation.
