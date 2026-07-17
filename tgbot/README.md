The Telegram service polls Telegram and forwards banking tool calls to the Wema MCP endpoint.

## Runtime Configuration

Set these values in Cloud Run or Secret Manager:

- `TELEGRAM_BOT_TOKEN`: token issued by BotFather.
- `ELECTRONHUB_API_KEY`: primary Electron Hub inference key.
- `GEMINI_API_KEY`: Gemini API key used by the assistant.
- `ELECTRONHUB_MODEL`: primary model, defaulting to `deepseek-v4-flash`.
- `GEMINI_MODEL`: fallback model, defaulting to `gemini-2.5-flash-lite`.
- `MCP_SERVER_URL`: deployed API endpoint ending in `/mcp`.
- `DEFAULT_ACCOUNT_ID`: fallback account identifier for demo operations.

The application uses Telegram long polling. Configure Cloud Run with one minimum instance, one maximum instance, and always-allocated CPU. Chat requests use Electron Hub first and retry with Gemini when Electron Hub fails. Voice transcription remains on Gemini because the configured transcription models are Gemini models.

To find the Telegram polling startup and update handling logic visit [bot.py](bot.py).

The Telegram connection can be found in [bot.py](bot.py), and the MCP connection can be found in [mcp_client.py](mcp_client.py).

The container entrypoint can be found in [Dockerfile](Dockerfile).
