The Telegram service receives updates through a Cloud Run webhook and forwards banking tool calls to the Wema MCP endpoint.

## Runtime Configuration

Set these values in Cloud Run or Secret Manager:

- `TELEGRAM_BOT_TOKEN`: token issued by BotFather.
- `GEMINI_API_KEY`: Gemini API key used by the assistant.
- `MCP_SERVER_URL`: deployed API endpoint ending in `/mcp`.
- `DEFAULT_ACCOUNT_ID`: fallback account identifier for demo operations.
- `WEBHOOK_BASE_URL`: public Cloud Run URL for this service, without a trailing slash.
- `TELEGRAM_WEBHOOK_PATH`: non-sensitive path segment, normally `telegram`.
- `TELEGRAM_WEBHOOK_SECRET`: random Telegram webhook header secret.

The application registers the webhook with Telegram during startup. No manual `setWebhook` request is required, and the bot token is never included in the webhook URL.

To find the Telegram webhook startup and update handling logic visit [bot.py](bot.py).

The Telegram connection can be found in [bot.py](bot.py), and the MCP connection can be found in [mcp_client.py](mcp_client.py).

The container entrypoint can be found in [Dockerfile](Dockerfile).
