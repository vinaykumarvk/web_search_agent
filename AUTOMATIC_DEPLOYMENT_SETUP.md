# Automatic Deployment Setup Guide

## Overview

Your repository is now configured for automatic deployment to Google Cloud Run via Cloud Build. When you push code to the `main` branch, it will automatically build and deploy.

## Setup Steps

### 1. Connect GitHub Repository to Cloud Build

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **Cloud Build** → **Triggers**
3. Click **Create Trigger**
4. Select **GitHub (Cloud Build GitHub App)** or **GitHub (Manually Connected)**
5. Authenticate and select repository: `vinaykumarvk/web_search_agent`
6. Configure trigger:
   - **Name:** `deploy-web-research-agent`
   - **Event:** Push to a branch
   - **Branch:** `^main$`
   - **Configuration:** Cloud Build configuration file
   - **Location:** `cloudbuild.yaml`
   - **Substitution variables:** (leave default)

### 2. Set Up Secret Manager

Before the first deployment, create the OpenAI API key secret:

```bash
# Create secret
echo -n "your-openai-api-key-here" | gcloud secrets create openai-api-key --data-file=-

# Grant Cloud Run service account access
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Update cloudbuild.yaml (if needed)

If your secret name is different, update the Cloud Run deployment step in `cloudbuild.yaml`:

```yaml
- '--set-secrets'
- 'OPENAI_API_KEY=openai-api-key:latest'
```

### 4. Enable Required APIs

Ensure these APIs are enabled:

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 5. Test Automatic Deployment

1. Make a small change (e.g., update a comment)
2. Commit and push:
   ```bash
   git add .
   git commit -m "Test automatic deployment"
   git push origin main
   ```
3. Check Cloud Build console for build status
4. Once build completes, check Cloud Run for deployment

## How It Works

1. **Push to GitHub** → Triggers Cloud Build
2. **Cloud Build** → Builds Docker image using Dockerfile
3. **Container Registry** → Stores image with commit SHA tag
4. **Cloud Run** → Deploys new revision automatically
5. **Service URL** → Available immediately after deployment

## Manual Deployment (Alternative)

If you prefer manual deployment or want to test first:

```bash
# Build and deploy manually
gcloud builds submit --config cloudbuild.yaml
```

## Monitoring

- **Build Logs:** Cloud Build → Build History
- **Deployment Logs:** Cloud Run → Revisions → Logs
- **Service URL:** Cloud Run → Service Details → URL

## Troubleshooting

### Build Fails
- Check Cloud Build logs for errors
- Verify `cloudbuild.yaml` syntax
- Ensure Dockerfile builds successfully locally

### Deployment Fails
- Check Cloud Run logs
- Verify secret exists in Secret Manager
- Check IAM permissions for service account

### Port Issues
- Verify PORT env var is set correctly (Cloud Run sets it automatically)
- Check Dockerfile CMD uses `${PORT:-8080}` correctly

## Files Added

- `cloudbuild.yaml` - Cloud Build configuration
- `.gcloudignore` - Files excluded from builds
- `AUTOMATIC_DEPLOYMENT_SETUP.md` - This guide

## Next Steps

1. ✅ Code pushed to GitHub
2. ⏳ Connect repository to Cloud Build (follow steps above)
3. ⏳ Set up Secret Manager
4. ⏳ Test deployment with a push

Once set up, every push to `main` will automatically deploy to Cloud Run!

