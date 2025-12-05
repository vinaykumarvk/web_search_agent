Functional Specification — Multi‑Layered Web Research Agent (Python + OpenAI Agents SDK)
Document version: v1.0 (Dec 4, 2025)
 Purpose: Specify an agent system that can answer quick questions fast, or run deep, citation-rich research (BRDs, company research, requirement elaboration), producing consistent response structure while swapping template-specific bodies.

1) Goals & Non‑Goals
Goals
Multi-faceted web agent that supports multiple deliverable types:


Company research report


Product/Market research


Create BRD (Business Requirements Document)
Compare BRD


Requirement elaboration (epics/stories/AC)


Definitions / quick market queries


Quick → Deep capability:


“Quick answer” mode: minimal tool use, fast turnaround.


“Deep research” mode: tool-heavy web search + synthesis + citations, optionally long-running async.


Consistent response envelope across all templates (same outer structure), with template-specific sections inside.


High quality formatting similar to the ChatGPT “Pro” experience:


Clean Markdown sections


Tables where helpful


Citations/bibliography


Explicit assumptions & gaps


Operational robustness: caching, observability, retries, source-quality controls.


Non‑Goals
No autonomous “real-world actions” (purchases, sending emails, etc.).


No guaranteed correctness beyond cited evidence; must surface uncertainty.



2) User Experience (What the user can ask)
User inputs
Natural language query: “Write a BRD for…”, “Research company X…”, “Define TAM vs SAM vs SOM…”


Optional controls:


purpose: brd | company_research | req_elaboration | market_query | custom


depth: quick | standard | deep


audience: exec | product | engineering | mixed


region/timeframe: e.g., “APAC”, “last 24 months”


output_format: markdown (default) + optional structured JSON


User outcomes
Returns a response with the same top-level structure every time:


Title + metadata


Executive summary


Main deliverable (template-specific)


Citations / sources


Assumptions, gaps, open questions


Next steps / options



3) System Architecture (High level)
Recommended pattern: “Orchestrator + specialist agents” using the OpenAI Agents SDK, with delegation/handoffs represented as tool calls. (OpenAI GitHub)
Client (UI/API)
  |
  v
API Server (FastAPI)
  |
  v
Orchestrator (Agents SDK)
  |-- Router Agent (classify purpose/depth)
  |-- Clarifier Agent (2–3 questions only if required)
  |-- Research Agent(s) (web search heavy; deep mode)
  |-- Synthesizer/Writer Agent (template + narrative)
  |-- Fact-Checker Agent (citation enforcement + QA)
  |
  v
Renderer (Markdown + optional JSON)
  |
  v
Store (DB/Redis) + Artifact store (S3/GCS) + Optional vector store/MCP

Why this works
The SDK supports multi-agent orchestration patterns (including “agents as tools” and handoffs), enabling specialized sub-agents while keeping global coherence. (OpenAI Platform)



4) Core Functional Requirements
FR‑1: Intent & depth routing
System must infer:


purpose (template selection)


depth (quick/standard/deep)


need_web (whether web search is required)


Routing rules:


Quick: definitions, simple comparisons, short answers → minimal tool calls.


Standard: moderate research, a few searches, decent citations.


Deep: BRD/company research with multiple sections → deep research workflow.


FR‑2: Web research with citations
In “standard/deep”, the agent must use hosted web search tools and cite sources in the final output. Deep research is designed for planning + web searches + synthesis into a citation-rich report. (OpenAI Cookbook)


Citations must be grounded:


Any numerical claim should have a citation or be labeled as an estimate.


FR‑3: Optional long-running (async) deep runs
Deep research can take minutes; system must support background execution and later retrieval. (OpenAI Cookbook)


System must support:


Job creation → returns task_id


Polling status


Retrieve final report later (no need to hold connection)


FR‑4: Output consistency with template variance
Must keep a stable outer envelope.


Must allow different template bodies for BRD vs company research vs requirement elaboration.


FR‑5: Quality gates
Must include a final QA pass:


“Does every key claim cite something?”


“Are sections complete for this template?”


“Did we include assumptions and open questions?”


“No contradictory statements.”



5) Model & Tooling Strategy (Configurable)
5.1 Model roles
Router/Clarifier/Synthesizer: GPT‑5/5.1 class model tuned for steerability and formatting.


Deep Research agent: deep-research model for tool-heavy research + long synthesis. The Deep Research API explicitly supports this style and returns citation-backed outputs. (OpenAI Cookbook)


Implementation note: keep model names in config; don’t hardcode.
5.2 Reasoning & verbosity knobs
Use Responses API/SDK settings to control thinking and length:


reasoning: {"effort": "none|low|medium|high|minimal"} (varies by model family)


text: {"verbosity": "low|medium|high"} for GPT‑5 series behaviors shown in cookbook guidance. (OpenAI Cookbook)


Suggested mapping:


quick: reasoning low/none + verbosity low


standard: reasoning medium + verbosity medium


deep: reasoning high + verbosity high (but still structured)


5.3 Stateful runs and continuation
Use previous_response_id (Responses API) or SDK sessions to enable coherent multi-turn continuity; Responses API stores reasoning items and supports multi-turn state. (OpenAI Cookbook)



6) Templates (Stable envelope + variable body)
6.1 Output envelope (always present)
Envelope headings (always in this order):
# Title


## Metadata (purpose, depth, date, scope, audience)


## Executive Summary (3–7 bullets)


## Deliverable (template-specific body)


## Sources (bibliography; grouped by type)


## Assumptions & Gaps


## Open Questions


## Next Steps


6.2 Template bodies
A) BRD body
Problem statement


Goals / non-goals


Stakeholders + personas


User journeys


Functional requirements (MoSCoW)


Non-functional requirements


Data & analytics requirements


Dependencies/integrations


Risks & mitigations


Acceptance criteria outline


Rollout plan + success metrics


B) Company research body
Company overview (what they do, segments)


Products/services


Customers & positioning


Market sizing (bounded; cite assumptions)


Competitive landscape


Business model & unit economics (if available)


Financial snapshot (public filings if applicable)


Strategy signals (partnerships, M&A, hiring)


Risks (regulatory, tech, competition)


“What to watch” (leading indicators)


C) Requirement elaboration body
Restated requirement + intent


Ambiguities & clarifications (assumptions if unanswered)


Decomposition: epics → stories


Acceptance criteria (Given/When/Then)


Edge cases & failure modes


Test scenarios


Telemetry/metrics


D) Market query / definitions body
Definition (tight)


Why it matters (context)


Examples


Common confusions


Short source list



7) Agent Design (Agents SDK)
7.1 Agents (logical responsibilities)
Router Agent


Classifies purpose/depth


Decides if web search is needed


Clarifier Agent


Asks up to 2–3 targeted questions only if required (deep research API itself won’t do this, so you add it). (OpenAI Cookbook)


Research Agent


Runs web searches


Builds evidence notes (bullet facts with URLs)


Produces a “source map” (claim → citation)


Writer Agent


Fills the chosen template body inside the stable envelope


Enforces tone and formatting rules


Fact‑Checker Agent


Verifies: citations exist, contradictions flagged, missing sections detected


7.2 Orchestration pattern
Prefer “agent-as-tool” orchestration for complex reports (central orchestrator calling specialists). (OpenAI Platform)


Use handoffs where appropriate for clean delegation boundaries. (OpenAI GitHub)



8) Async Deep Research Workflow (If depth = deep)
Flow
Create task in DB: status=queued


Kick off deep research with background=True


Store returned response_id and mark status=running


Poll responses.retrieve(response_id) until complete (or use webhook pattern if implemented)


Run final “Writer + Fact‑Checker” pass (shorter, deterministic)


Persist final artifact and mark status=completed


Deep research guidance explicitly calls out background mode for long runs. (OpenAI Cookbook)
 Responses are retrievable later (stateful API). (OpenAI Cookbook)

9) API Surface (for Codex to implement)
9.1 REST endpoints (FastAPI)
POST /v1/agent/run


body: { query, purpose?, depth?, audience?, region?, timeframe?, output_format? }


returns: { task_id, status, estimated_mode: "sync|async" }


GET /v1/agent/tasks/{task_id}


returns: { status, progress?, result?, error? }


GET /v1/agent/tasks/{task_id}/stream (SSE/WebSocket)


streams progress events + partial notes (optional)


9.2 Task states
queued → running → writing → validating → completed


failure states:


failed_retriable (tool timeouts, transient)


failed_final (schema/constraints impossible)



10) Data Models (Pydantic)
Request
query: str


purpose: Enum


depth: Enum


constraints: dict (region/timeframe/industry/etc.)


output_format: Enum(markdown|json|both)


Internal artifacts
ResearchPlan (list of sub-questions + search queries)


EvidenceItem (claim, supporting excerpt, url, source_type, confidence)


DraftReport (templated sections)


FinalReport (envelope + bibliography + QA notes)


Implementation recommendation: keep a structured internal representation (Pydantic) even if you render Markdown at the end. This is how you keep the envelope stable while swapping templates.

11) Prompt & Template Management
11.1 Prompt layers
System (global): non-negotiables (honesty, citations, no fabrication)


Developer (per-purpose): template contract + quality gates


User: the user’s request


11.2 “Template library” structure
templates/base_envelope.md


templates/brd.md


templates/company_research.md


templates/req_elaboration.md


templates/market_query.md


Rule: Writer agent always renders:
base_envelope + {template_body} inserted at ## Deliverable



12) Source Quality & Citation Policy
Source preference order
Official / primary sources: regulator, standards body, filings, investor relations


Reputable reporting and analyst summaries


Blogs/community sources only for triangulation


Citation rules
Every key claim should cite at least one source.


Any number should cite, or be labeled “estimate”.


Deep research responses expose citation metadata and annotations suitable for building a bibliography. (OpenAI Cookbook)

13) Observability & Evaluation
Log:


search queries used


sources selected


token usage per stage


template completeness score


citation coverage score (claims with citations / total claims)


Tracing:


enable Agents SDK tracing in non‑ZDR environments; cookbook shows turning off tracing for ZDR setups. (OpenAI Cookbook)



14) Testing (Definition of Done)
Unit tests
Routing decisions (purpose/depth)


Template rendering correctness (envelope stable)


Citation parser (bibliography generation)


Integration tests
Deep research run creates task, retrieves later, renders output


Web search returns sources and citations appear in final output


Acceptance criteria
For each template, output includes:


correct envelope


all mandatory sections


sources list


assumptions + open questions



Appendix A — Key Implementation References
Deep Research API overview + models + citation metadata + clarification gap (you must add your own clarifier) (OpenAI Cookbook)


Deep Research with Agents SDK and multi-agent prompt enrichment example (OpenAI Cookbook)


Responses API statefulness + retrieve pattern (OpenAI Cookbook)


Agents SDK: multi-agent/handoffs concept (OpenAI GitHub)


GPT‑5 controls: verbosity + reasoning effort patterns (cookbook examples) (OpenAI Cookbook)


If you want, I can also include a “starter prompt pack” (system + developer prompts for each template) and a concrete folder layout that Codex can generate directly.

