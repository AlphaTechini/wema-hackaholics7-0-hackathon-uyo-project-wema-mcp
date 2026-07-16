# Wema Banking Assistant

An AI-powered banking assistant that brings Wema account operations into a Telegram conversation. The system combines a Fastify and PostgreSQL banking API, an official MCP Streamable HTTP server, and a Telegram bot that uses Gemini tool calling.

## Team Members

- Rehoboth Okoibu
- Emmanuel Fidelis

## Live Demo

- Telegram bot: `@bankin_with_alat_bot`
- Backend MCP endpoint: `https://YOUR_GCP_SERVICE_URL/mcp`
- Recorded demo: To be added after publication.

## The Problem

Financial exclusion is not only caused by a lack of banking infrastructure. Many people are underserved because financial products do not match how they earn, save, trade, contribute, or get paid.

Freelancers often have irregular income and no traditional payslip. Market traders may operate through cash-heavy workflows with limited formal financial history. Cooperatives may manage contributions and payouts manually. Gig workers can receive fragmented income from several platforms.

Developers and community-focused organisations could build specialized financial agents for these groups, but each team would need to independently solve banking integrations, permissions, transaction security, and compliance.

## The Solution

Financial Inclusion MCP is a reusable infrastructure layer that allows specialized AI agents to connect underserved users to formal financial services through channels they already use, such as Telegram, WhatsApp, voice, or local-language interfaces.

A freelancer agent can understand irregular income and support adaptive savings. A trader agent can turn daily activity into a usable financial history. A cooperative agent can manage member contributions and transparent payouts. A corporate or platform agent can maintain contributor lists, reconcile monthly payments, and execute approved payouts. The corporate entity is not necessarily financially excluded, but its payout infrastructure can determine whether contributors participate effectively in formal finance.

The agent focuses on the community and its context. Financial Inclusion MCP provides the reusable banking, validation, permission, and transaction layer underneath. This is the Stripe-like infrastructure layer for specialized financial agents, not another generic banking chatbot.

Account creation is conversational and state-aware. The agent extracts fields in any order, maps first and last names correctly, recognizes email addresses, asks for only one missing field at a time, and collects the PIN only after every other required field is complete. The final API request is submitted once with all required values together.

The MCP server exposes these tools:

- `create_account`
- `update_account`
- `get_statement`
- `create_transfer`

## Architecture

- `server/` contains the Fastify REST API, database layer, controllers, routes, and MCP server.
- `tgbot/` contains the Telegram conversation flow, Gemini integration, MCP client, and deployment files.
- `server/mcp/telegram-agent-instructions.md` contains the conversational rules used by the agent.
- The MCP endpoint is mounted at `/mcp` on the API service.
- The API container listens on port `3870` by default and honors the platform `PORT` environment variable.

See [structure.md](structure.md) for the complete directory map.

## Tech Stack

- Backend: Node.js, TypeScript, Fastify 5
- MCP: Official Model Context Protocol TypeScript SDK with Streamable HTTP
- Database: PostgreSQL with Drizzle ORM
- Security: Argon2 PIN hashing and schema validation with Zod and Fastify JSON Schema
- Telegram bot: Python, `python-telegram-bot`, HTTPX
- AI: Gemini through its OpenAI-compatible API
- Deployment: Docker and Google Cloud Run

## Setup

### API and MCP service

```bash
cd server
pnpm install
```

Create `server/.env` from [server/.env.example](server/.env.example) and set `DATABASE_URL`.

```bash
pnpm db:migrate
pnpm dev
```

The local API and MCP service starts on `http://localhost:3870`. The MCP endpoint is `http://localhost:3870/mcp`.

### Telegram bot

```bash
cd tgbot
python -m venv .venv
```

Activate the virtual environment, install dependencies, and create `tgbot/.env` from [tgbot/.env.example](tgbot/.env.example).

```bash
pip install -r requirements.txt
python bot.py
```

Set `MCP_SERVER_URL` to the deployed API MCP endpoint before starting the bot.

## Docker Deployment

Build the API image using `server/Dockerfile`:

```bash
docker build -f server/Dockerfile -t wema-mcp-api .
```

Build the Telegram bot image using `tgbot/Dockerfile`:

```bash
docker build -f tgbot/Dockerfile -t wema-telegram-bot .
```

Deploy the two images as separate Cloud Run services. Configure `DATABASE_URL` on the API service. Configure `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `MCP_SERVER_URL`, and `DEFAULT_ACCOUNT_ID` on the Telegram bot service. Secrets should be supplied through Google Cloud Secret Manager or the Cloud Run environment configuration, not committed to the repository.

## Security Notes

- PINs are hashed by the API and are not returned in account responses.
- The Telegram bot collects transfer PINs through a confirmation gate before calling `create_transfer`.
- Account-creation PINs are collected last and are not included in long-lived conversation history.
- The current MCP endpoint has no application-level authentication. Protect the Cloud Run service with an appropriate GCP ingress or authentication policy before exposing it publicly.

## Project Documentation

- [Project structure](structure.md)
- [API documentation](server/README.md)
- [MCP documentation](server/mcp/README.md)
- [Telegram bot documentation](tgbot/README.md)
- [Agent instructions](server/mcp/telegram-agent-instructions.md)
