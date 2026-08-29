FROM python:3.10-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for health checks and ML wheels
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 300 -r requirements.txt

# CPU-only PyTorch first (smaller, faster mirror) then sentence-transformers
RUN pip install --no-cache-dir --retries 5 --timeout 300 \
    torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --retries 5 --timeout 300 sentence-transformers

COPY . .

RUN mkdir -p /app/data/chroma

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${AI_SERVICE_PORT:-10000}"]
