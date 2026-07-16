FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY mcp_client.py .
COPY tools.json .
COPY prompts/ prompts/

# GCP Cloud Run expects the application to listen on $PORT (default 8080)
ENV PORT=8080
EXPOSE $PORT

# Start a simple HTTP server in the background to satisfy Cloud Run's port health check,
# then start the Telegram bot (which runs via long-polling) in the foreground.
CMD python -m http.server $PORT & python bot.py
