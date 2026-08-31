FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PostgreSQL & build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose Render's default port
EXPOSE 10000

# Run Alembic migrations then start the server.
# PORT env var is automatically set by Render; fallback to 10000.
CMD ["sh", "-c", "alembic upgrade head && python seeds/seed_appointments.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
