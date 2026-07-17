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
ENV PYTHONUNBUFFERED=1
EXPOSE $PORT

# bot.py owns both the health listener and the Telegram polling process.
CMD ["python", "-u", "bot.py"]
