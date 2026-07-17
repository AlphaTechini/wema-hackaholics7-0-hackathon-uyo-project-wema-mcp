The Telegram service receives updates through a Cloud Run webhook and forwards banking tool calls to the Wema MCP endpoint.

## Runtime Configuration

Set these values in Cloud Run or Secret Manager:

- `TELEGRAM_BOT_TOKEN`: token issued by BotFather.
- `GROQ_API_KEY`: primary Groq inference key.
- `GEMINI_API_KEY`: Gemini API key used by the assistant.
- `GROQ_MODEL`: primary model, defaulting to `qwen/qwen3-32b`.
- `GROQ_REASONING_EFFORT`: Groq reasoning mode, defaulting to `none` for responsive chat.
- `GEMINI_MODEL`: fallback model, defaulting to `gemini-2.5-flash-lite`.
- `MCP_SERVER_URL`: deployed API endpoint ending in `/mcp`.
- `DEFAULT_ACCOUNT_ID`: fallback account identifier for demo operations.
- `WEBHOOK_BASE_URL`: public Cloud Run URL for this service, without a trailing slash.
- `TELEGRAM_WEBHOOK_PATH`: non-sensitive path segment, normally `telegram`.
- `TELEGRAM_WEBHOOK_SECRET`: random Telegram webhook header secret.

The application registers the webhook with Telegram during startup. No manual `setWebhook` request is required, and the bot token is never included in the webhook URL. Chat requests use Groq first and retry with Gemini when Groq fails. Voice transcription remains on Gemini because the configured transcription models are Gemini models.

To find the Telegram webhook startup and update handling logic visit [bot.py](bot.py).

The Telegram connection can be found in [bot.py](bot.py), and the MCP connection can be found in [mcp_client.py](mcp_client.py).

The container entrypoint can be found in [Dockerfile](Dockerfile).
