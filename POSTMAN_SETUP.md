# Postman Setup Guide

## Quick Setup

1. **Configure OpenAI API Key** (REQUIRED for Real API Calls)

   **Option A: Using .env file (Recommended)**
   ```bash
   cp .env.example .env
   # Edit .env and add: OPENAI_API_KEY=your-openai-api-key-here
   ```

   **Option B: Using Environment Variable**
   ```bash
   export OPENAI_API_KEY="your-openai-api-key-here"
   ```

   ⚠️ **Without this, the API will use fallbacks/mocks instead of real OpenAI calls!**

2. **Start the API Server**
   ```bash
   python run_server.py
   ```
   Server will start at: `http://localhost:8000`
   - The startup script will warn you if API key is missing

3. **Import Postman Collection**
   - Open Postman
   - Click **Import** button (top left)
   - Select `Web_Research_Agent_API.postman_collection.json`
   - Collection will be imported with all requests pre-configured

4. **Set Environment Variables** (Optional)
   - Create a new environment in Postman
   - Add variable: `base_url` = `http://localhost:8000`
   - Add variable: `task_id` = (leave empty, will be set after async requests)

5. **Verify API Readiness**
   - **FIRST**: Run **Readiness Check** request
   - Verify `openai_api_key_configured: true`
   - Check that all endpoints show "LLM-based" or "OpenAI Responses API"

6. **Test the API**
   - Start with **Health Check** request
   - Run **Readiness Check** to verify OpenAI integration
   - Try **Quick Research** for immediate results
   - Use **Deep Research** to test async flow

## Collection Requests

### 1. Health Check
- **Method**: GET
- **URL**: `{{base_url}}/health`
- **Purpose**: Verify API is running

### 2. Quick Research (Synchronous)
- **Method**: POST
- **URL**: `{{base_url}}/v1/agent/run`
- **Returns**: Immediate response with research results
- **Use Case**: Fast testing, simple queries

### 3. Standard Research (Synchronous)
- **Method**: POST
- **URL**: `{{base_url}}/v1/agent/run`
- **Returns**: Immediate response with detailed research
- **Use Case**: Moderate depth research

### 4. Deep Research (Asynchronous)
- **Method**: POST
- **URL**: `{{base_url}}/v1/agent/run`
- **Returns**: Task ID for polling
- **Use Case**: Long-running comprehensive research

### 5. BRD Research
- **Method**: POST
- **URL**: `{{base_url}}/v1/agent/run`
- **Purpose**: Business Requirements Document generation

### 6. JSON Output Format
- **Method**: POST
- **URL**: `{{base_url}}/v1/agent/run`
- **Purpose**: Request structured JSON instead of markdown

### 7. Get Task Status
- **Method**: GET
- **URL**: `{{base_url}}/v1/agent/tasks/{{task_id}}`
- **Purpose**: Poll for async task results
- **Note**: Set `task_id` variable from async response

### 8. Stream Task Updates
- **Method**: GET
- **URL**: `{{base_url}}/v1/agent/tasks/{{task_id}}/stream`
- **Purpose**: Real-time SSE stream of task progress
- **Note**: Postman supports SSE in newer versions

## Testing Workflow

### Synchronous Testing
1. Run **Health Check** → Should return `{"status": "ok"}`
2. Run **Quick Research** → Should return immediate results
3. Run **Standard Research** → Should return detailed results

### Asynchronous Testing
1. Run **Deep Research** → Copy `task_id` from response
2. Set `task_id` variable in Postman environment
3. Run **Get Task Status** → Poll until status is `completed`
4. (Optional) Use **Stream Task Updates** for real-time progress

## Tips

- **Start Simple**: Use quick research first to verify setup
- **Check Logs**: Server console shows detailed request/response logs
- **Use Swagger**: Visit `http://localhost:8000/docs` for interactive API docs
- **Environment Variables**: Set `base_url` to easily switch between dev/prod
- **Task ID**: After async requests, copy task_id to environment variable for easy polling

## Troubleshooting

**Server won't start**
- Check if port 8000 is available
- Verify `OPENAI_API_KEY` is set (if using real API)
- Check Python dependencies: `pip install -r requirements.txt`

**Requests fail**
- Verify server is running: Check `/health` endpoint
- Check server logs for error messages
- Verify request body format matches examples

**Async tasks not completing**
- Check server logs for background task errors
- Verify OpenAI API key has credits
- Check database files for persistence issues

