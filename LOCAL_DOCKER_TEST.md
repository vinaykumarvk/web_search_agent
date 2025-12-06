# Local Docker Testing Guide

## Issue Found and Fixed

**Problem:** FastAPI is an ASGI application, but gunicorn was configured to run it as WSGI, causing:
```
TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'
```

**Solution:** Use uvicorn workers with gunicorn for ASGI support:
```dockerfile
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 900 --access-logfile - --error-logfile - --log-level info --preload app.main:app"]
```

## Testing Locally

### Build Docker Image
```bash
docker build -t web-research-agent:local .
```

### Run Container
```bash
docker run -d \
  --name web-research-test \
  -p 8081:8080 \
  -e PORT=8080 \
  -e OPENAI_API_KEY="your-key-here" \
  web-research-agent:local
```

### Test Endpoints
```bash
# Health check
curl http://localhost:8081/health

# Readiness check
curl http://localhost:8081/health/ready

# Test API endpoint
curl -X POST http://localhost:8081/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?", "controls": {"depth": "quick"}}'
```

### Check Logs
```bash
docker logs web-research-test
docker logs -f web-research-test  # Follow logs
```

### Stop Container
```bash
docker rm -f web-research-test
```

## Verification Checklist

- ✅ Docker image builds successfully
- ✅ Container starts without errors
- ✅ `/health` endpoint returns `{"status":"ok"}`
- ✅ `/health/ready` endpoint returns readiness status
- ✅ API endpoints respond correctly
- ✅ Port configuration works (PORT env var)
- ✅ Environment variables load correctly

## Production Readiness

After local testing passes:
1. ✅ Fix committed to git
2. ✅ Ready for Cloud Build deployment
3. ✅ Same Dockerfile will work in Cloud Run

