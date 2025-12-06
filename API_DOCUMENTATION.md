# Web Research Agent API Documentation

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure OpenAI API Key

**Option A: Using .env file (Recommended)**

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key:
   ```bash
   OPENAI_API_KEY=your-openai-api-key-here
   ```

The `.env` file is automatically loaded when the server starts.

**Option B: Using Environment Variable**

```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

⚠️ **IMPORTANT**: Without `OPENAI_API_KEY`, the API will use fallbacks/mocks:
- Router uses heuristic fallback (not LLM-based)
- Researcher returns empty results
- Writer generates placeholder content
- Deep research uses mock data

**Verify API is ready for real calls:**
```bash
curl http://localhost:8000/health/ready
```

**Optional Configuration (add to .env file):**
```bash
STRICT_MODE=false
LOG_LEVEL=INFO
CACHE_TTL_SECONDS=300
```

### 3. Start the Server

**Option A: Using the startup script**
```bash
python run_server.py
```

**Option B: Using uvicorn directly**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`

### 4. Access API Documentation

FastAPI automatically provides interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

---

## API Endpoints

### 1. Health Check

**GET** `/health`

Check if the API is running.

**Response:**
```json
{
  "status": "ok"
}
```

---

### 1b. Readiness Check

**GET** `/health/ready`

Verify OpenAI API key is configured and check which endpoints will use real API calls.

**Response (API Key Configured):**
```json
{
  "status": "ready",
  "openai_api_key_configured": true,
  "message": "API will make real OpenAI calls",
  "endpoints_available": {
    "router": "LLM-based",
    "clarifier": "LLM-based",
    "researcher": "OpenAI Responses API",
    "writer": "GPT-5.1",
    "fact_checker": "GPT-5.1 + Heuristics",
    "deep_research": "O3-deep-research"
  }
}
```

**Response (No API Key):**
```json
{
  "status": "degraded",
  "openai_api_key_configured": false,
  "message": "WARNING: OPENAI_API_KEY not set - API will use fallbacks/mocks",
  "endpoints_available": {
    "router": "Heuristic fallback",
    "clarifier": "Skipped",
    "researcher": "No-op (empty results)",
    "writer": "Placeholder content",
    "fact_checker": "Heuristics only",
    "deep_research": "Mock (test data)"
  }
}
```

---

---

### 2. Create Research Job

**POST** `/v1/agent/run`

Start a research run. Returns immediately for quick/standard depth, or returns a task ID for deep/async requests.

**Request Body:**
```json
{
  "query": "Research Tesla's business strategy",
  "controls": {
    "purpose": "company_research",
    "depth": "standard",
    "audience": "exec",
    "region": "Global",
    "timeframe": "last 2 years",
    "output_format": "markdown",
    "async_mode": false
  }
}
```

**Controls Options:**
- `purpose`: `"brd"` | `"company_research"` | `"req_elaboration"` | `"market_query"` | `"custom"`
- `depth`: `"quick"` | `"standard"` | `"deep"`
- `audience`: `"exec"` | `"product"` | `"engineering"` | `"mixed"`
- `region`: Optional string (e.g., `"Global"`, `"US"`, `"APAC"`)
- `timeframe`: Optional string (e.g., `"last 2 years"`, `"last 6 months"`)
- `output_format`: `"markdown"` | `"json"` (default: `"markdown"`)
- `async_mode`: `true` | `false` (default: `false`)

**Response (Synchronous):**
```json
{
  "envelope": {
    "title": "Research: Tesla's business strategy",
    "metadata": {...},
    "executive_summary": "...",
    "deliverable": "...",
    "citations": [...],
    "assumptions_and_gaps": "...",
    "open_questions": [...],
    "next_steps": [...]
  },
  "quality": {
    "citation_coverage_score": 0.85,
    "template_completeness_score": 0.90,
    "uncited_numbers": false,
    "contradictions": false,
    ...
  },
  "bibliography": "...",
  "source_map": {...},
  "notes": [...],
  "findings": [...],
  "evidence": [...],
  "overall_confidence": "medium"
}
```

**Response (Asynchronous):**
```json
{
  "task_id": "uuid-here",
  "status": "queued",
  "estimated_mode": "async",
  "message": "Research task created. Poll the task endpoint for updates."
}
```

---

### 3. Get Task Status

**GET** `/v1/agent/tasks/{task_id}`

Retrieve the status and results for an async research task.

**Response:**
```json
{
  "task_id": "uuid-here",
  "status": "completed",
  "envelope": {...},
  "quality": {...},
  "bibliography": "...",
  "source_map": {...},
  "notes": [...],
  "findings": [...],
  "evidence": [...],
  "overall_confidence": "medium"
}
```

**Status Values:**
- `queued` - Task created, waiting to start
- `running` - Research in progress
- `writing` - Generating deliverable
- `validating` - Fact-checking in progress
- `completed` - Task finished successfully
- `failed` - Task failed with error

---

### 4. Stream Task Updates

**GET** `/v1/agent/tasks/{task_id}/stream`

Server-Sent Events (SSE) stream that emits progress and partial artifacts until completion.

**Event Types:**
- `status` - Status updates
- `running` - Research in progress
- `writing` - Writing deliverable
- `validating` - Fact-checking
- `findings` - Partial findings available
- `evidence` - Partial evidence available
- `notes` - Intermediate notes from deep research
- `completed` - Task completed
- `failed` - Task failed

**Example Event:**
```
event: running
data: {"status": "running", "task_id": "...", ...}

event: findings
data: [{"id": "F1", "title": "...", ...}]

event: completed
data: {"status": "completed", "envelope": {...}}
```

---

## Postman Collection

Import the `Web_Research_Agent_API.postman_collection.json` file into Postman to get pre-configured requests.

### Postman Setup

1. **Import Collection**: File → Import → Select `Web_Research_Agent_API.postman_collection.json`
2. **Set Environment Variables**:
   - `base_url`: `http://localhost:8000`
   - `openai_api_key`: Your OpenAI API key (if needed for testing)
3. **Run Requests**: Use the collection requests to test the API

---

## Example Requests

### Quick Research (Synchronous)

```json
POST /v1/agent/run
{
  "query": "What is artificial intelligence?",
  "controls": {
    "depth": "quick",
    "purpose": "market_query"
  }
}
```

### Standard Research (Synchronous)

```json
POST /v1/agent/run
{
  "query": "Compare cloud providers AWS vs Azure",
  "controls": {
    "depth": "standard",
    "purpose": "company_research",
    "audience": "exec"
  }
}
```

### Deep Research (Asynchronous)

```json
POST /v1/agent/run
{
  "query": "Comprehensive analysis of Tesla's business strategy",
  "controls": {
    "depth": "deep",
    "purpose": "company_research",
    "audience": "exec",
    "region": "Global",
    "timeframe": "last 2 years"
  }
}
```

Then poll for results:
```
GET /v1/agent/tasks/{task_id}
```

Or stream updates:
```
GET /v1/agent/tasks/{task_id}/stream
```

### JSON Output Format

```json
POST /v1/agent/run
{
  "query": "Research OpenAI's GPT models",
  "controls": {
    "depth": "standard",
    "output_format": "json"
  }
}
```

---

## Error Responses

### 404 Not Found
```json
{
  "error": "Task not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

---

## Testing Tips

1. **Start with Quick Depth**: Use `"depth": "quick"` for fast testing
2. **Use Health Check**: Always verify `/health` before testing other endpoints
3. **Check Logs**: Server logs show detailed request/response information
4. **Use Swagger UI**: Interactive docs at `/docs` for easy testing
5. **Test Async Flow**: Use deep research to test async task polling/streaming

---

## Troubleshooting

### Server Won't Start
- Check if port 8000 is available: `lsof -i :8000`
- Verify dependencies: `pip install -r requirements.txt`
- Check Python version: Requires Python 3.9+

### API Returns Errors
- Verify `OPENAI_API_KEY` is set
- Check server logs for detailed error messages
- Use `/health` endpoint to verify server is running

### Tasks Not Completing
- Check server logs for background task errors
- Verify OpenAI API key has sufficient credits
- Check database files (`tasks.db`, `metrics.db`) for persistence issues

---

## API Version

Current API version: **v1**

Base path: `/v1/agent/`

