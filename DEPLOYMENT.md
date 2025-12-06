# Production Deployment Guide - Google Cloud Platform

## Pre-Deployment Checklist

### ✅ Production-Ready Features
- [x] Health check endpoints (`/health`, `/health/ready`)
- [x] Environment variable configuration
- [x] Error handling and logging
- [x] CORS middleware (configurable)
- [x] Port configuration via `PORT` environment variable
- [x] Timeout configuration (5 min sync, 15 min async)
- [x] Responses API integration for GPT-5.1

### ⚠️ Production Considerations

#### 1. Database Storage
**Current:** SQLite (`tasks.db`, `metrics.db`)
**Issue:** SQLite files are stored in the working directory, which is ephemeral in Cloud Run.

**Options:**
- **Option A (Recommended for Cloud Run):** Use Cloud SQL (PostgreSQL) or Cloud Firestore
- **Option B (Quick fix):** Mount a Cloud Storage bucket for SQLite files
- **Option C:** Use Cloud Run's `/tmp` directory (ephemeral, data lost on restart)

**For initial deployment:** SQLite in `/tmp` works but data is ephemeral. Consider migrating to Cloud SQL for production.

#### 2. Environment Variables & Secrets
**Current:** Loads from `.env` file or environment variables
**Production:** Use GCP Secret Manager for sensitive values:
- `OPENAI_API_KEY` - Store in Secret Manager
- `SEARCH_API_KEY` - Store in Secret Manager (if used)

#### 3. CORS Configuration
**Current:** Allows all origins (`allow_origins=["*"]`)
**Production:** Restrict to your frontend domain(s)

#### 4. Logging
**Current:** Standard Python logging
**Production:** Logs automatically captured by Cloud Logging in GCP

## Deployment Options

### Option 1: Cloud Run (Recommended)

#### Prerequisites
```bash
# Install gcloud CLI
# Authenticate: gcloud auth login
# Set project: gcloud config set project YOUR_PROJECT_ID
```

#### Steps

1. **Create a Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Cloud Run uses PORT env var)
EXPOSE 8080

# Use gunicorn for production
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 900 --access-logfile - --error-logfile - app.main:app
```

2. **Build and deploy:**
```bash
# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/web-research-agent

# Deploy to Cloud Run
gcloud run deploy web-research-agent \
  --image gcr.io/YOUR_PROJECT_ID/web-research-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars PORT=8080 \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10 \
  --min-instances 0
```

3. **Set up Secret Manager:**
```bash
# Create secret
echo -n "your-openai-api-key" | gcloud secrets create openai-api-key --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Option 2: App Engine (Flexible)

1. **Create `app.yaml`:**
```yaml
runtime: python
env: flex

runtime_config:
  python_version: 3.11

resources:
  cpu: 2
  memory_gb: 2
  disk_size_gb: 10

env_variables:
  PORT: 8080

automatic_scaling:
  min_num_instances: 1
  max_num_instances: 10
```

2. **Deploy:**
```bash
gcloud app deploy
```

### Option 3: Compute Engine VM

1. **Create VM:**
```bash
gcloud compute instances create web-research-agent \
  --image-family ubuntu-2204-lts \
  --image-project ubuntu-os-cloud \
  --machine-type e2-standard-4 \
  --boot-disk-size 20GB
```

2. **SSH and setup:**
```bash
gcloud compute ssh web-research-agent

# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv -y

# Clone repo and setup
git clone YOUR_REPO
cd web-research-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# Set environment variables
export OPENAI_API_KEY="your-key"
export PORT=8080

# Run with systemd service
sudo nano /etc/systemd/system/web-research-agent.service
```

## Environment Variables

### Required
- `OPENAI_API_KEY` - OpenAI API key (use Secret Manager in production)

### Optional
- `PORT` - Server port (default: 8000, Cloud Run uses 8080)
- `LOG_LEVEL` - Logging level (default: INFO)
- `STRICT_MODE` - Fail fast on errors (default: false)
- `CACHE_TTL_SECONDS` - Cache TTL (default: 300)
- `TRACING_ENABLED` - Enable tracing (default: false)
- `TRACING_SAMPLE_RATE` - Tracing sample rate (default: 1.0)
- `TRACING_ENDPOINT` - Tracing endpoint URL

### Model Overrides
- `OPENAI_ROUTER_MODEL` - Router model (default: gpt-5-mini)
- `OPENAI_CLARIFIER_MODEL` - Clarifier model (default: gpt-5-mini)
- `OPENAI_WRITER_MODEL` - Writer model (default: gpt-5.1)
- `OPENAI_FACT_CHECK_MODEL` - Fact checker model (default: gpt-5.1)
- `OPENAI_SEARCH_MODEL` - Search model (default: gpt-5.1)
- `OPENAI_DEEP_MODEL` - Deep research model (default: o3-deep-research)

## Production Configuration Changes Needed

### 1. Update CORS (if needed)
Edit `app/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),  # Comma-separated list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Database Path for Cloud Run
SQLite files will be stored in `/tmp` (ephemeral). For persistent storage, migrate to Cloud SQL.

### 3. Add gunicorn to requirements.txt
```bash
echo "gunicorn>=21.2.0" >> requirements.txt
```

## Health Checks

- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check (verifies OpenAI API key)

Cloud Run will automatically use `/health` for health checks.

## Monitoring

- **Logs:** Available in Cloud Logging
- **Metrics:** Application metrics via `MetricsEmitter`
- **Errors:** Captured in Cloud Error Reporting

## Scaling Considerations

- **Cloud Run:** Auto-scales based on requests (0-10 instances default)
- **Memory:** 2GB recommended for deep research tasks
- **CPU:** 2 vCPU recommended
- **Timeout:** 900 seconds (15 minutes) for long-running tasks

## Security Best Practices

1. **Use Secret Manager** for API keys
2. **Restrict CORS** to known domains
3. **Enable authentication** if needed (Cloud Run IAM)
4. **Use HTTPS** (automatic with Cloud Run)
5. **Set resource limits** to prevent abuse

## Troubleshooting

### Database Issues
If SQLite fails, check:
- Write permissions in `/tmp`
- Disk space available
- File system type (must support SQLite)

### Timeout Issues
- Increase Cloud Run timeout: `--timeout 900`
- Check orchestrator timeout settings

### Memory Issues
- Increase memory: `--memory 4Gi`
- Monitor memory usage in Cloud Logging

## Next Steps

1. **Choose deployment option** (Cloud Run recommended)
2. **Set up Secret Manager** for API keys
3. **Configure CORS** if needed
4. **Deploy and test**
5. **Monitor logs** for issues
6. **Consider migrating to Cloud SQL** for persistent storage

