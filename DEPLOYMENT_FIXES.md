# Deployment Fixes Applied

## Issues Fixed

### 1. ✅ Port Configuration
**Issue:** Cloud Run sets PORT env var dynamically, but Dockerfile wasn't handling it correctly.

**Fix:**
- Changed CMD to use `sh -c` to properly expand PORT env var at runtime
- Health check uses fixed port 8080 (Cloud Run handles PORT automatically for health checks)
- Removed duplicate gunicorn installation (already in requirements.txt)

### 2. ✅ Missing Import
**Issue:** `app/main.py` used `os.getenv()` without importing `os`.

**Fix:** Added `import os` to `app/main.py`.

### 3. ✅ Dependency Versions
**Issue:** Potential version incompatibilities, especially httpx with OpenAI SDK.

**Fix:**
- Added explicit httpx version constraint: `httpx>=0.27.0,<1.0.0`
- Added comments explaining version requirements
- Upgraded pip/setuptools/wheel in Dockerfile for better dependency resolution

### 4. ✅ Dockerfile Optimization
**Issue:** Multiple issues with Dockerfile structure.

**Fixes:**
- Removed duplicate gunicorn installation (was in both requirements.txt and Dockerfile)
- Added curl for health checks (more reliable than Python requests)
- Improved layer caching by copying requirements.txt first
- Added `--preload` flag to gunicorn for better performance
- Proper PORT env var handling in CMD

### 5. ✅ Path Handling
**Issue:** Paths using `__file__` might break in Docker.

**Status:** All paths are relative to WORKDIR (/app) and should work correctly:
- `app/templates/render.py` uses `Path(__file__).resolve().parents[2]` - works if templates are copied
- `app/agents/gpt_writer.py` uses `Path(templates_dir)` with default "app/templates" - works
- Database paths use `/tmp` which is writable in Cloud Run

### 6. ✅ No Asset Files
**Status:** No .png, .jpg, or other asset files found. Application is API-only, no static assets needed.

### 7. ✅ Duplicate Configurations
**Status:** No duplicate configurations found. All settings are properly centralized.

## Updated Files

1. **Dockerfile**
   - Fixed PORT env var handling
   - Removed duplicate gunicorn install
   - Added curl for health checks
   - Improved build optimization

2. **requirements.txt**
   - Added httpx version constraint
   - Added comments for clarity
   - Organized dependencies by category

3. **app/main.py**
   - Added missing `import os`

## Testing Checklist

Before deploying, verify:

- [ ] Docker build succeeds: `docker build -t web-research-agent .`
- [ ] Container starts: `docker run -p 8080:8080 -e PORT=8080 -e OPENAI_API_KEY=test web-research-agent`
- [ ] Health check works: `curl http://localhost:8080/health`
- [ ] Port is configurable: `docker run -p 9000:9000 -e PORT=9000 ...`
- [ ] All dependencies install correctly
- [ ] No import errors on startup

## Cloud Run Deployment

The fixed Dockerfile should now work correctly with Cloud Run:

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/web-research-agent
gcloud run deploy web-research-agent \
  --image gcr.io/YOUR_PROJECT_ID/web-research-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --port 8080
```

Note: Cloud Run automatically sets PORT env var, so the `--port 8080` flag ensures consistency.

