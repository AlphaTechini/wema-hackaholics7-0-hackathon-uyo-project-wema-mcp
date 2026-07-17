# Project Structure

This file provides a high-level mapping of where related logic resides within the Wema MCP-API.

## Directory Map

- `server/` - Core backend application code.
  - `server/controllers/` - Business logic and request handlers.
  - `server/services/` - Reusable application operations shared by entry points.
  - `server/scripts/` - Explicit operational and database seeding scripts.
  - `server/routes/` - API route definitions and schema validation.
  - `server/db/` - Database schemas, models, and migrations.
  - `server/mcp/` - Official MCP tools, prompt, and Streamable HTTP transport.
  - `server/Dockerfile` - Multi-stage backend container image for GCP deployment.
  - `tgbot/` - Telegram bot, MCP client, and bot deployment files.

## Relevant Links

- [Root README](README.md)
- [Server README](server/README.md)
- [Controllers README](server/controllers/README.md)
- [Services README](server/services/README.md)
- [Scripts README](server/scripts/README.md)
- [Routes README](server/routes/README.md)
- [Database README](server/db/README.md)
- [MCP README](server/mcp/README.md)
- [Telegram bot README](tgbot/README.md)
