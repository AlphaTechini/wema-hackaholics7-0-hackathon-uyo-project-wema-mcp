The Telegram service polls Telegram and forwards banking tool calls to the Wema MCP endpoint.

## Runtime Configuration

Set these values in Cloud Run or Secret Manager:

- `TELEGRAM_BOT_TOKEN`: token issued by BotFather.
- `NEAR_AI_API_KEY`: primary NEAR AI Cloud inference key.
- `GEMINI_API_KEY`: Gemini API key used by the assistant.
- `GEMINI_MODEL`: fallback model, defaulting to `gemini-2.5-flash-lite`.
- `AI_TIMEOUT_SECONDS`: per-provider request timeout, defaulting to `15`.
- `MCP_SERVER_URL`: deployed API endpoint ending in `/mcp`.
- `DEFAULT_ACCOUNT_ID`: fallback account identifier for demo operations.

The application uses Telegram long polling. Configure Cloud Run with one minimum instance, one maximum instance, and always-allocated CPU. Account opening uses a native flow rather than model context: the account PIN message is deleted immediately, submitted once, and never stored in conversation history. Chat requests use NEAR AI Cloud's direct `dsv4-flash.completions.near.ai` endpoint with `deepseek-ai/DeepSeek-V4-Flash`, avoiding the gateway routing hop, and retry with Gemini when NEAR AI fails. Voice transcription remains on Gemini because the configured transcription models are Gemini models.

To find the Telegram polling startup and update handling logic visit [bot.py](bot.py).

The Telegram connection can be found in [bot.py](bot.py), and the MCP connection can be found in [mcp_client.py](mcp_client.py).

The container entrypoint can be found in [Dockerfile](Dockerfile).
