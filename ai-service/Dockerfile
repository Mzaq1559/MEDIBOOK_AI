FROM python:3.10-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render assigns port 10000 by default
EXPOSE 10000

# AI_SERVICE_PORT env var is set to 10000 via render.yaml
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${AI_SERVICE_PORT:-10000}"]
