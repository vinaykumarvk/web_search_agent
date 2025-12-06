FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip to latest version for better dependency resolution
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for SQLite databases (ephemeral in Cloud Run)
RUN mkdir -p /tmp/db && chmod 777 /tmp/db

# Expose port (Cloud Run sets PORT env var dynamically)
# Use 8080 as default, but Cloud Run will override via PORT env var
EXPOSE 8080

# Health check using curl (more reliable than Python requests)
# Note: HEALTHCHECK doesn't expand env vars, so use fixed port 8080
# Cloud Run health checks will use the PORT env var automatically
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Use gunicorn with uvicorn workers for FastAPI (ASGI)
# Cloud Run sets PORT env var - must read it at runtime
# Use JSON format for CMD to prevent signal handling issues
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 900 --access-logfile - --error-logfile - --log-level info --preload app.main:app"]

