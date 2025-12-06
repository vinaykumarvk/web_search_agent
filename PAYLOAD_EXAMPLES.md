# API Payload Examples

## Correct Request Format

### Quick Research (Synchronous - Returns immediately)
```json
{
  "query": "What is artificial intelligence?",
  "controls": {
    "depth": "quick",
    "purpose": "market_query",
    "audience": "mixed"
  }
}
```

### Standard Research (Synchronous - Returns immediately)
```json
{
  "query": "What are the latest advancements in AI?",
  "controls": {
    "depth": "standard",
    "purpose": "market_query",
    "audience": "technical"
  }
}
```

### Deep Research (Asynchronous - Returns task_id immediately)
```json
{
  "query": "What are the latest advancements in AI?",
  "controls": {
    "depth": "deep",
    "purpose": "company_research",
    "audience": "exec"
  }
}
```

**Response (immediate):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "estimated_mode": "async"
}
```

Then poll for results:
```bash
GET /v1/agent/tasks/550e8400-e29b-41d4-a716-446655440000
```

## Common Mistakes

### ❌ Wrong: Using "mode" instead of "depth"
```json
{
  "query": "What are the latest advancements in AI?",
  "mode": "balanced"  // ❌ Invalid field
}
```

### ✅ Correct: Using "depth" in "controls"
```json
{
  "query": "What are the latest advancements in AI?",
  "controls": {
    "depth": "deep"  // ✅ Valid: "quick" | "standard" | "deep"
  }
}
```

## Valid Values

### `depth` (required in controls)
- `"quick"` - Fast research, returns immediately
- `"standard"` - Standard research, returns immediately  
- `"deep"` - Deep research, returns task_id immediately, poll for results

### `purpose` (optional, default: "custom")
- `"brd"` - Business Requirements Document
- `"company_research"` - Company research
- `"req_elaboration"` - Requirement elaboration
- `"market_query"` - Market query
- `"custom"` - Custom purpose

### `audience` (optional, default: "mixed")
- `"exec"` - Executive audience
- `"product"` - Product team
- `"engineering"` - Engineering team
- `"mixed"` - Mixed audience

### `async_mode` (optional, default: false)
- `true` - Force async mode (returns task_id)
- `false` - Use depth to determine sync/async

## Why Deep Research is Always Async

Deep research uses O3-deep-research which can take 5-15 minutes. To avoid gateway timeouts:

1. **POST /v1/agent/run** with `"depth": "deep"` → Returns task_id immediately (< 1 second)
2. **GET /v1/agent/tasks/{task_id}** → Poll for status and results
3. **GET /v1/agent/tasks/{task_id}/stream** → Stream real-time progress via SSE

This ensures no 504 Gateway Timeout errors!

