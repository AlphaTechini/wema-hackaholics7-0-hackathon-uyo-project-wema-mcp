# Project Structure

This file provides a high-level mapping of where related logic resides within the Wema MCP-API.

## Directory Map

- `server/` - Core backend application code.
  - `server/controllers/` - Business logic and request handlers.
  - `server/routes/` - API route definitions and schema validation.
  - `server/db/` - Database schemas, models, and migrations.
  - `server/mcp/` - Official MCP tools, prompt, and Streamable HTTP transport.
  - `server/Dockerfile` - Multi-stage backend container image for GCP deployment.

## Relevant Links

- [Root README](file:///c:/Hackathons/Wema%20MCP-API/README.md)
- [Server README](file:///c:/Hackathons/Wema%20MCP-API/server/README.md)
- [Controllers README](file:///c:/Hackathons/Wema%20MCP-API/server/controllers/README.md)
- [Routes README](file:///c:/Hackathons/Wema%20MCP-API/server/routes/README.md)
- [Database README](file:///c:/Hackathons/Wema%20MCP-API/server/db/README.md)
- [MCP README](file:///c:/Hackathons/Wema%20MCP-API/server/mcp/README.md)
