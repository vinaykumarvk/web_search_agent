FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for production
RUN pip install --no-cache-dir gunicorn>=21.2.0

# Copy application code
COPY . .

# Create directory for SQLite databases (ephemeral in Cloud Run)
RUN mkdir -p /tmp/db && chmod 777 /tmp/db

# Expose port (Cloud Run uses PORT env var)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:${PORT:-8080}/health')" || exit 1

# Use gunicorn for production with appropriate workers
# Cloud Run handles load balancing, so 1 worker is sufficient
CMD exec gunicorn \
  --bind 0.0.0.0:${PORT:-8080} \
  --workers 1 \
  --threads 8 \
  --timeout 900 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  app.main:app

