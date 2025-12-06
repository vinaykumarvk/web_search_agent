# Web Research Agent - Product Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Complete Workflow](#complete-workflow)
4. [API Endpoints](#api-endpoints)
5. [Agent Components](#agent-components)
6. [Model Selection Strategy](#model-selection-strategy)
7. [Storage & Persistence](#storage--persistence)
8. [Configuration](#configuration)
9. [Error Handling](#error-handling)
10. [Observability](#observability)

---

## Overview

The Web Research Agent is a multi-layered AI-powered research system that produces structured, citation-rich research reports. It supports multiple deliverable types (BRDs, company research, requirement elaboration, market queries) with configurable depth levels (quick, standard, deep).

### Key Features

- **Multi-Agent Orchestration**: Router, Clarifier, Researcher, Writer, and Fact-Checker agents work together
- **Intelligent Routing**: LLM-based intent classification determines purpose, depth, and research strategy
- **Deep Research Support**: Background processing for long-running research tasks
- **Structured Output**: Consistent response envelope with template-specific content
- **Quality Assurance**: LLM-based fact-checking with semantic citation validation
- **Persistent Storage**: Task persistence and metrics logging
- **Multiple Output Formats**: Markdown (default) and JSON support

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Client/API    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      FastAPI Server                 │
│  (app/main.py)                      │
│  - /v1/agent/run                    │
│  - /v1/agent/tasks/{task_id}       │
│  - /v1/agent/tasks/{task_id}/stream│
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      Orchestrator                   │
│  (app/orchestrator.py)              │
│  Coordinates all agents             │
└────────┬────────────────────────────┘
         │
         ├──► Router Agent (GPT-5-mini)
         ├──► Clarifier Agent (GPT-5-mini)
         ├──► Research Agent
         ├──► Writer Agent (GPT-5.1)
         └──► Fact Checker Agent (GPT-5.1)
         │
         ▼
┌─────────────────────────────────────┐
│      Storage Layer                  │
│  - Task Storage (SQLite)            │
│  - Metrics Storage (SQLite)         │
└─────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Model | Responsibility |
|-------|-------|----------------|
| **Router** | GPT-5-mini | Classifies query intent, determines purpose/depth |
| **Clarifier** | GPT-5-mini | Asks targeted questions when query is ambiguous |
| **Researcher** | GPT-5.1 / O3-deep-research | Performs web search and deep research |
| **Writer** | GPT-5.1 | Generates structured deliverables |
| **Fact Checker** | GPT-5.1 | Validates citations, checks contradictions |

---

## Complete Workflow

### Step-by-Step Process

#### 1. **Request Reception** (`app/main.py`)

**Endpoint:** `POST /v1/agent/run`

**Input:**
```json
{
  "query": "Research Tesla's business strategy",
  "controls": {
    "purpose": "company_research",
    "depth": "deep",
    "audience": "exec",
    "region": "Global",
    "timeframe": "last 2 years",
    "output_format": "markdown",
    "async_mode": false
  }
}
```

**Decision Logic:**
- If `depth == "deep"` OR `async_mode == true` → Async mode (background task)
- Otherwise → Synchronous mode (immediate response)

---

#### 2. **Request Normalization** (`app/main.py`)

**Function:** `_run_sync_research()`

Converts API request to `NormalizedRequest`:
```python
NormalizedRequest(
    query="Research Tesla's business strategy",
    metadata={
        "controls": {
            "purpose": "company_research",
            "depth": "deep",
            ...
        }
    }
)
```

---

#### 3. **Router Agent - Intent Classification** (`app/agents/llm_router.py`)

**Model:** GPT-5-mini

**Process:**
1. Receives normalized request
2. Analyzes query with LLM
3. Returns `RouterDecision`:
   ```python
   RouterDecision(
       purpose="company_research",      # Template type
       depth="deep",                    # Research intensity
       needs_clarification=False,       # Ambiguity flag
       profile="COMPANY_RESEARCH",      # Research profile
       need_deep_research=True          # Deep research flag
   )
   ```

**LLM Prompt:**
- System message: Router classification instructions
- User message: Query + any user-specified hints
- Response format: JSON object

**Fallback:** If LLM unavailable → Heuristic router (keyword-based)

---

#### 4. **Clarifier Agent - Query Refinement** (`app/agents/llm_clarifier.py`)

**Model:** GPT-5-mini

**Trigger:** Only if `router_decision.needs_clarification == true`

**Process:**
1. Analyzes ambiguous query
2. Generates 2-3 targeted questions
3. Returns clarification:
   ```python
   {
       "query": "Clarified query text",
       "questions": ["Question 1?", "Question 2?"],
       "clarification_skipped": False
   }
   ```

**Fallback:** If LLM unavailable → Returns original query with `clarification_skipped: true`

---

#### 5. **Research Plan Creation** (`app/orchestrator.py`)

**Function:** `DepthPolicy.build_plan()`

Based on depth, creates research plan:

| Depth | Passes | Persistent Task | Search Profile |
|-------|--------|----------------|----------------|
| `quick` | 1 | No | `minimal_search` |
| `standard` | 2 | No | `iterative_search` |
| `deep` | 3 | Yes | `multi_pass_search_with_synthesis` |

---

#### 6. **Research Agent - Web Search & Deep Research** (`app/runtime.py`)

**Location:** `ResearcherAdapter.research()`

**Process:**

**A. Strategy Selection** (`app/strategy.py`)
```python
strategy = select_strategy(profile="COMPANY_RESEARCH", depth="deep")
# Returns:
Strategy(
    model="o3-deep-research",
    effort="high",
    max_searches=8,
    tools=["web_search"],
    recency_bias=True
)
```

**B. Deep Research Path** (if `depth == "deep"` and `model == "o3-deep-research"`)
- Uses `DeepResearchClient.run_sync()` with `use_background=True`
- O3-deep-research performs autonomous multi-hop web search
- Returns citations with source URLs

**C. Standard Research Path** (if not deep)
- Uses `WebSearchTool` with OpenAI Responses API
- Performs multiple search queries based on depth
- Aggregates results from all searches

**D. Result Aggregation**
- Combines results from all passes
- Ranks by source preference (official > analyst > community)
- Returns structured results with citations

---

#### 7. **Writer Agent - Deliverable Generation** (`app/runtime.py`)

**Model:** GPT-5.1

**Location:** `TemplateWriter.write()`

**Process:**

**A. Template Selection**
- Based on `router.purpose` (brd, company_research, req_elaboration, market_query, custom)
- Loads template from `app/templates/`

**B. GPT-5.1 Writer** (`app/agents/gpt_writer.py`)
- Always uses GPT-5.1 for structured reporting
- Builds comprehensive prompt with:
  - System message (purpose-specific instructions)
  - Developer message (template structure)
  - User message (query, research findings, citations, context)
- Applies reasoning/verbosity parameters:
  - `reasoning: {"effort": strategy.effort}` (low/medium/high)
  - `text: {"verbosity": depth}` (low/medium/high)
- Generates deliverable and executive summary

**C. Template Rendering**
- Renders base envelope with template-specific sections
- Combines GPT-5.1 output with template structure
- Produces final Markdown document

**Output Format:**
- **Markdown** (default): Full rendered document
- **JSON** (if `output_format="json"`): Structured JSON with all fields

---

#### 8. **Fact Checker Agent - Quality Validation** (`app/agents/llm_fact_checker.py`)

**Model:** GPT-5.1

**Process:**

**A. LLM-Based Analysis**
- Extracts document text and citations
- Analyzes for:
  - Logical contradictions
  - Citation coverage
  - Uncited numerical claims
  - Missing sections

**B. Semantic Citation Validation** (`app/utils/semantic_citation.py`)
- Validates claims semantically match citations
- Checks URL accessibility (HTTP HEAD requests)
- Scores citation relevance (0.0-1.0)
- Identifies broken URLs and low-relevance citations

**C. Quality Report**
```python
QualityReport(
    citation_coverage_score=0.85,
    template_completeness_score=0.90,
    missing_sections=[],
    uncited_numbers=False,
    contradictions=False,
    semantic_citation_score=0.82,
    broken_urls=[],
    low_relevance_citations=[],
    citation_relevance_map={"url1": 0.9, "url2": 0.8}
)
```

---

#### 9. **Response Assembly** (`app/runtime.py`)

**Function:** `TemplateWriter.write()`

Assembles final response:
```python
{
    "envelope": ResponseEnvelope(...),
    "rendered_markdown": "...",
    "structured_json": {...},  # If output_format="json"
    "quality": QualityReport(...),
    "bibliography": "...",
    "source_map": {...},
    "notes": [...],
    "findings": [...],
    "evidence": [...],
    "overall_confidence": "medium"
}
```

---

#### 10. **Task Persistence** (`app/utils/task_storage.py`)

**Storage:** SQLite database (`tasks.db`)

**Process:**
- All task status changes saved to database
- In-memory cache for quick access
- Tasks survive server restarts
- Supports task recovery

---

### Async Workflow (Deep Research)

For deep research tasks:

1. **Task Creation** (`POST /v1/agent/run`)
   - Returns `task_id` immediately
   - Status: `QUEUED`

2. **Background Processing** (`app/main.py:_process_task()`)
   - Status: `RUNNING`
   - Starts O3 deep research in background mode
   - Polls for completion (every 2 seconds)
   - Extracts intermediate notes during polling
   - Updates task status in real-time

3. **Status Updates**
   - `QUEUED` → `RUNNING` → `WRITING` → `VALIDATING` → `COMPLETED`
   - Or `FAILED` if error occurs

4. **Task Retrieval** (`GET /v1/agent/tasks/{task_id}`)
   - Returns current status and results when complete

5. **Streaming** (`GET /v1/agent/tasks/{task_id}/stream`)
   - Server-Sent Events (SSE)
   - Streams status updates and intermediate notes
   - Real-time progress updates

---

## API Endpoints

### 1. Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{"status": "ok"}
```

---

### 2. Create Research Job

**Endpoint:** `POST /v1/agent/run`

**Request:**
```json
{
  "query": "Research Tesla's business strategy",
  "controls": {
    "purpose": "company_research",
    "depth": "deep",
    "audience": "exec",
    "region": "Global",
    "timeframe": "last 2 years",
    "output_format": "markdown",
    "async_mode": false
  }
}
```

**Response (Synchronous):**
```json
{
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

**Endpoint:** `GET /v1/agent/tasks/{task_id}`

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

**Endpoint:** `GET /v1/agent/tasks/{task_id}/stream`

**Response:** Server-Sent Events (SSE)

**Event Types:**
- `status` - Status updates
- `running` - Research in progress
- `writing` - Writing deliverable
- `validating` - Fact-checking
- `findings` - Partial findings available
- `evidence` - Partial evidence available
- `completed` - Task completed
- `failed` - Task failed

**Example:**
```
event: status
data: {"status": "running", "task_id": "..."}

event: findings
data: [{"id": "F1", "title": "...", ...}]

event: completed
data: {"status": "completed", "envelope": {...}}
```

---

## Agent Components

### 1. Router Agent (`app/agents/llm_router.py`)

**Purpose:** Classify user intent and determine research strategy

**Model:** GPT-5-mini

**Input:** `NormalizedRequest`

**Output:** `RouterDecision`
```python
RouterDecision(
    purpose="company_research",      # brd, company_research, req_elaboration, market_query, custom
    depth="deep",                    # quick, standard, deep
    needs_clarification=False,       # boolean
    profile="COMPANY_RESEARCH",      # Research profile for strategy selection
    need_deep_research=True          # boolean
)
```

**Process:**
1. Builds prompt with query and user hints
2. Calls GPT-5-mini with JSON response format
3. Parses classification result
4. Maps to research profile using `classify_web_profile()`
5. Returns router decision

**Fallback:** If LLM unavailable → `HeuristicRouter` (keyword-based)

---

### 2. Clarifier Agent (`app/agents/llm_clarifier.py`)

**Purpose:** Generate targeted clarification questions

**Model:** GPT-5-mini

**Trigger:** Only when `router_decision.needs_clarification == true`

**Output:**
```python
{
    "query": "Clarified/refined query",
    "questions": ["Question 1?", "Question 2?", "Question 3?"],
    "clarification_skipped": False
}
```

**Process:**
1. Analyzes ambiguous query
2. Identifies missing context (audience, region, timeframe, purpose)
3. Generates 2-3 targeted questions
4. Provides clarified query incorporating inferred context

**Fallback:** If LLM unavailable → Returns original query with `clarification_skipped: true`

---

### 3. Research Agent (`app/runtime.py`)

**Purpose:** Perform web search and deep research

**Components:**
- `ResearchAgent` - Web search with caching and ranking
- `DeepResearchClient` - O3-deep-research integration
- `ResearcherAdapter` - Wraps both for orchestrator

**Web Search Flow:**
1. Builds search queries based on depth
2. Calls `WebSearchTool.search()` → `openai_web_search_transport()`
3. Uses OpenAI Responses API with `web_search` tool
4. Filters and ranks results by source preference
5. Returns aggregated results

**Deep Research Flow:**
1. Checks if `depth == "deep"` and `model == "o3-deep-research"`
2. Calls `DeepResearchClient.run_sync()` with `use_background=True`
3. O3-deep-research performs autonomous multi-hop search
4. Extracts citations from response
5. Returns structured citations

**Result Format:**
```python
{
    "pass_index": 0,
    "profile": "COMPANY_RESEARCH",
    "model": "o3-deep-research",
    "effort": "high",
    "results": {
        "preferred": [SearchResult(...)],
        "all": [SearchResult(...)]
    },
    "search_queries": ["query1", "query2"],
    "notes": ["Note 1", "Note 2"]
}
```

---

### 4. Writer Agent (`app/runtime.py`, `app/agents/gpt_writer.py`)

**Purpose:** Generate structured deliverables

**Model:** GPT-5.1

**Components:**
- `GPT5WriterAgent` - LLM-based content generation
- `TemplateWriter` - Template rendering and envelope assembly

**Process:**

**A. Template Selection**
- Loads template based on `router.purpose`
- Templates: `brd.md`, `company_research.md`, `req_elaboration.md`, `market_query.md`, `custom.md`

**B. GPT-5.1 Generation**
- Builds comprehensive prompt:
  - System message: Purpose-specific instructions
  - Developer message: Template structure and requirements
  - User message: Query, research findings, citations, context
- Applies reasoning/verbosity parameters:
  - `reasoning: {"effort": "high"}` - Controls reasoning depth
  - `text: {"verbosity": "high"}` - Controls output detail
- Generates deliverable and executive summary

**C. Template Rendering**
- Renders base envelope (`base_envelope.md`)
- Inserts deliverable at `## Deliverable` section
- Adds citations, assumptions, open questions, next steps

**Output:**
- **Markdown:** Full rendered document
- **JSON:** Structured JSON (if `output_format="json"`)

---

### 5. Fact Checker Agent (`app/agents/llm_fact_checker.py`)

**Purpose:** Validate quality and citations

**Model:** GPT-5.1

**Process:**

**A. LLM-Based Analysis**
- Extracts document text and citations
- Analyzes for:
  - Logical contradictions
  - Citation coverage
  - Uncited numerical claims
  - Missing sections

**B. Semantic Citation Validation** (`app/utils/semantic_citation.py`)
- Extracts claim-citation pairs from document
- Uses LLM to score semantic relevance (0.0-1.0)
- Checks URL accessibility (HTTP HEAD requests)
- Identifies broken URLs and low-relevance citations

**C. Quality Report Generation**
- Combines LLM analysis and semantic validation
- Returns comprehensive quality report

**Output:**
```python
QualityReport(
    citation_coverage_score=0.85,        # 0.0-1.0
    template_completeness_score=0.90,   # 0.0-1.0
    missing_sections=[],                # List of missing sections
    section_coverage={...},             # Per-section coverage
    uncited_numbers=False,              # Boolean
    contradictions=False,               # Boolean
    semantic_citation_score=0.82,       # Average semantic match
    broken_urls=[],                     # Inaccessible URLs
    low_relevance_citations=[],         # Low relevance citations
    citation_relevance_map={...}        # Per-citation scores
)
```

---

## Model Selection Strategy

### Strategy Matrix (`app/strategy.py`)

The strategy matrix selects research models and parameters based on profile and depth:

| Profile | Depth | Model | Effort | Max Searches |
|---------|-------|-------|--------|--------------|
| COMPANY_RESEARCH | deep | o3-deep-research | high | 8 |
| BRD_MODELING | deep | o3-deep-research | high | 8 |
| MARKET_OR_TREND_QUERY | deep | o3-deep-research | high | 8 |
| COMPANY_RESEARCH | standard | gpt-5.1 | high | 4 |
| BRD_MODELING | standard | gpt-5.1 | high | 4 |
| MARKET_OR_TREND_QUERY | standard | gpt-5.1 | high | 4 |
| DEFINITION_OR_SIMPLE_QUERY | quick | gpt-5.1 | low | 2 |

### Model Roles

| Model | Used For | Why |
|-------|----------|-----|
| **GPT-5-mini** | Router, Clarifier | Fast, cheap, perfect for classification |
| **GPT-5.1** | Writer, Fact Checker, Web Search | Best formatting, structured output, quality |
| **O3-deep-research** | Deep Research | Autonomous multi-hop search, citations |

### Reasoning/Verbosity Parameters

**Reasoning Effort** (from strategy):
- `low` → `reasoning: {"effort": "low"}`
- `medium` → `reasoning: {"effort": "medium"}`
- `high` → `reasoning: {"effort": "high"}`

**Text Verbosity** (from depth):
- `quick` → `text: {"verbosity": "low"}`
- `standard` → `text: {"verbosity": "medium"}`
- `deep` → `text: {"verbosity": "high"}`

Applied to all GPT-5.1 API calls (Writer, Fact Checker).

---

## Storage & Persistence

### Task Storage (`app/utils/task_storage.py`)

**Backend:** SQLite (`tasks.db`)

**Schema:**
```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    envelope TEXT,          -- JSON string
    quality TEXT,           -- JSON string
    bibliography TEXT,
    source_map TEXT,        -- JSON string
    notes TEXT,            -- JSON string (array)
    findings TEXT,         -- JSON string (array)
    evidence TEXT,         -- JSON string (array)
    overall_confidence TEXT,
    error TEXT,
    created_at DATETIME,
    updated_at DATETIME
)
```

**Operations:**
- `save_task()` - Save or update task
- `get_task()` - Retrieve task by ID
- `list_tasks()` - List tasks (optionally filtered by status)
- `delete_task()` - Delete task

**Features:**
- In-memory cache for quick access
- Automatic file creation
- Task recovery on restart
- No credentials required

---

### Metrics Storage (`app/utils/persistent_logging.py`)

**Backend:** SQLite (`metrics.db`)

**Tables:**
- `metrics` - Generic metrics
- `token_usage` - Token usage by stage/model
- `search_queries` - Search query history
- `task_status` - Task status changes

**Operations:**
- `log_metric()` - Log generic metric
- `log_token_usage()` - Log token usage
- `log_search_query()` - Log search query
- `log_task_status()` - Log task status
- `get_token_usage_summary()` - Get usage summary
- `get_search_query_history()` - Get query history

**Integration:** Automatically integrated with `MetricsEmitter`

---

## Configuration

### Environment Variables (`app/config.py`)

**Required:**
- `OPENAI_API_KEY` - OpenAI API key for all LLM calls

**Optional:**
- `OPENAI_ROUTER_MODEL` - Router model (default: `gpt-5-mini`)
- `OPENAI_CLARIFIER_MODEL` - Clarifier model (default: `gpt-5-mini`)
- `OPENAI_WRITER_MODEL` - Writer model (default: `gpt-5.1`)
- `OPENAI_FACT_CHECK_MODEL` - Fact checker model (default: `gpt-5.1`)
- `OPENAI_SEARCH_MODEL` - Web search model (default: `gpt-5.1`)
- `OPENAI_DEEP_MODEL` - Deep research model (default: `o3-deep-research`)
- `STRICT_MODE` - Error handling mode (default: `false`)
- `CACHE_TTL_SECONDS` - Cache TTL (default: `300`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `TRACING_ENABLED` - Enable tracing (default: `false`)

### Settings Structure

```python
AppSettings(
    openai_api_key: str,
    search_api_key: Optional[str],
    cache: CacheSettings(ttl_seconds=300),
    observability: ObservabilitySettings(
        tracing_enabled=False,
        log_level="INFO"
    ),
    strict_mode: bool = False
)
```

---

## Error Handling

### Strict Mode vs. Graceful Mode

**Strict Mode** (`STRICT_MODE=true`):
- Raises custom exceptions on failures
- No fallbacks
- Better for testing/debugging

**Graceful Mode** (`STRICT_MODE=false`, default):
- Uses fallbacks when LLM unavailable
- Returns degraded output instead of failing
- Better for production resilience

### Custom Exceptions (`app/exceptions.py`)

- `RouterError` - Router agent failures
- `ClarifierError` - Clarifier agent failures
- `ResearchError` - Research agent failures
- `WriterError` - Writer agent failures
- `FactCheckerError` - Fact checker failures
- `DeepResearchError` - Deep research failures

### Fallback Behavior

| Agent | Fallback |
|-------|----------|
| Router | Heuristic router (keyword-based) |
| Clarifier | Returns original query with `clarification_skipped: true` |
| Writer | Returns placeholder deliverable |
| Fact Checker | Returns neutral quality report |
| Deep Research | Falls back to standard web search |

---

## Observability

### Logging (`app/observability.py`)

**Structured Logging:**
- All operations logged with context
- Log level configurable via `LOG_LEVEL`
- Includes task IDs, query text, agent names

### Metrics (`app/observability.py`)

**MetricsEmitter** emits:
- Token usage (by stage, model, tokens)
- Search queries (query, depth, results count)
- Task status (task_id, status)
- Agent availability (fallback metrics)
- Custom metrics

**Persistence:**
- Automatically persisted to `metrics.db`
- Historical analysis available
- Token usage tracking for cost analysis

### Tracing

**OpenAI Tracing:**
- Configurable via `TRACING_ENABLED`
- Sample rate configurable
- Endpoint configurable

---

## Data Flow Example

### Example: "Research Tesla's business strategy"

**1. Request:**
```json
POST /v1/agent/run
{
  "query": "Research Tesla's business strategy",
  "controls": {"depth": "deep", "purpose": "company_research"}
}
```

**2. Router Decision:**
```python
RouterDecision(
    purpose="company_research",
    depth="deep",
    profile="COMPANY_RESEARCH",
    need_deep_research=True
)
```

**3. Strategy Selection:**
```python
Strategy(
    model="o3-deep-research",
    effort="high",
    max_searches=8
)
```

**4. Research:**
- O3-deep-research performs autonomous search
- Returns citations with source URLs
- Multiple research passes

**5. Writing:**
- GPT-5.1 generates structured report
- Uses `company_research.md` template
- Applies high effort + high verbosity

**6. Fact Checking:**
- GPT-5.1 validates citations
- Semantic citation validation
- URL accessibility checks

**7. Response:**
```json
{
  "envelope": {
    "title": "Research: Tesla's business strategy",
    "executive_summary": "...",
    "deliverable": "# Company Research\n\n...",
    "citations": [...],
    ...
  },
  "quality": {
    "citation_coverage_score": 0.85,
    "semantic_citation_score": 0.82,
    ...
  }
}
```

---

## Key Design Decisions

### 1. **Always Use GPT-5.1 for Writing**
- Consistent quality across all depths
- Better formatting and structure
- Template-based output

### 2. **O3 for Deep Research Only**
- O3-deep-research for deep depth
- GPT-5.1 for quick/standard research
- Optimal model selection per use case

### 3. **LLM-Based Router/Clarifier**
- GPT-5-mini for fast, cheap classification
- Better intent understanding than heuristics
- Fallback to heuristics if LLM unavailable

### 4. **Semantic Citation Validation**
- LLM-based semantic matching
- URL accessibility checks
- Relevance scoring

### 5. **Persistent Storage**
- SQLite for simplicity (no credentials)
- Can upgrade to Redis/PostgreSQL for multi-instance
- In-memory cache for performance

---

## File Structure

```
web_search_agent/
├── app/
│   ├── main.py                 # FastAPI server, endpoints
│   ├── config.py               # Configuration management
│   ├── schemas.py              # Pydantic models
│   ├── orchestrator.py         # Orchestrator coordination
│   ├── runtime.py              # Agent implementations
│   ├── strategy.py             # Strategy matrix
│   ├── exceptions.py           # Custom exceptions
│   ├── observability.py        # Logging, metrics, tracing
│   ├── agents/
│   │   ├── llm_router.py       # Router agent (GPT-5-mini)
│   │   ├── llm_clarifier.py    # Clarifier agent (GPT-5-mini)
│   │   ├── research.py         # Research agent
│   │   ├── gpt_writer.py       # Writer agent (GPT-5.1)
│   │   └── llm_fact_checker.py # Fact checker (GPT-5.1)
│   ├── tools/
│   │   ├── web_search.py      # Web search tool
│   │   ├── openai_search.py   # OpenAI search transport
│   │   └── deep_research.py   # Deep research client
│   ├── utils/
│   │   ├── task_storage.py     # Task persistence
│   │   ├── persistent_logging.py # Metrics persistence
│   │   ├── reasoning_verbosity.py # Reasoning/verbosity params
│   │   └── semantic_citation.py  # Citation validation
│   └── templates/
│       ├── base_envelope.md    # Base template
│       ├── brd.md             # BRD template
│       ├── company_research.md # Company research template
│       ├── req_elaboration.md  # Requirement elaboration
│       └── market_query.md    # Market query template
└── README.md                   # Original spec
```

---

## Summary

The Web Research Agent is a production-ready, multi-agent research system that:

1. **Intelligently routes** queries using LLM-based classification
2. **Performs research** using optimal models (GPT-5.1 for standard, O3 for deep)
3. **Generates structured deliverables** using GPT-5.1 with templates
4. **Validates quality** using LLM-based fact-checking and semantic citation validation
5. **Persists tasks** using SQLite (upgradeable to Redis/PostgreSQL)
6. **Tracks metrics** for observability and cost analysis
7. **Handles errors** gracefully with fallbacks or strict mode

The system is designed for production use with comprehensive error handling, observability, and persistent storage.

