# Wema MCP-API

This is the Wema MCP-API backend, built to support account, statement, transfer, and MCP operations.

I have structured this project following strict architectural guidelines to ensure scalability, security, and maintainability. This root directory houses the overarching server structure and environments.

Please refer to [structure.md](file:///c:/Hackathons/Wema%20MCP-API/structure.md) for a comprehensive overview of the project directory and logic mapping.

The official MCP endpoint is mounted at `/mcp` on the Fastify service. The Telegram agent instructions are available in [server/mcp/telegram-agent-instructions.md](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/telegram-agent-instructions.md).
