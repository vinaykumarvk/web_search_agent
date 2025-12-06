"""Runtime wiring for the orchestrator with lightweight heuristic agents."""
from __future__ import annotations

import logging
import os
from dataclasses import asdict
from typing import Any, Dict, List

from web_search_agent.citations import Citation as SimpleCitation
from web_search_agent.citations import render_bibliography, render_citations
from web_search_agent.post_processing import evaluate_report_sections, summarize_coverage_by_section
from web_search_agent.router import route_request

from app.agents.gpt_writer import GPT5WriterAgent
from app.agents.llm_clarifier import LLMClarifierAgent
from app.agents.llm_fact_checker import LLMFactCheckerAgent
from app.agents.llm_router import LLMRouterAgent
from app.agents.profile_router import ProfileDecision, classify_web_profile
from app.agents.research import ResearchAgent
from app.orchestrator import NormalizedRequest, Orchestrator, ResearchPlan, RouterDecision
from app.schemas import (
    Citation,
    QualityReport,
    ResearchControls,
    ResponseEnvelope,
    ResponseMetadata,
    TaskStatus,
)
from app.search_models import Evidence, Finding
from app.templates import render as template_renderer
from app.observability import MetricsEmitter
from app.strategy import select_strategy
from app.tools.deep_research import DeepResearchClient, MockDeepResearchClient
from app.tools.openai_search import openai_web_search_transport
from app.tools.web_search import WebSearchTool
from app.utils.cache import TTLCache

logger = logging.getLogger(__name__)
metrics = MetricsEmitter()


def _controls_from_metadata(metadata: Dict[str, Any]) -> ResearchControls:
    raw_controls = metadata.get("controls") or {}
    if isinstance(raw_controls, ResearchControls):
        return raw_controls
    return ResearchControls.parse_obj(raw_controls)


class HeuristicRouter:
    """Adapter around the simple router heuristics."""

    def classify(self, request: NormalizedRequest) -> RouterDecision:
        controls = _controls_from_metadata(request.metadata)
        purpose_hint = controls.purpose.value if hasattr(controls.purpose, "value") else controls.purpose
        depth_hint = controls.depth.value if hasattr(controls.depth, "value") else controls.depth
        decision = route_request(request.query, purpose_hint=purpose_hint, depth_hint=depth_hint)
        profile_decision: ProfileDecision = classify_web_profile(
            request.query,
            purpose_hint=decision.purpose,
            depth_hint=decision.depth,
        )
        return RouterDecision(
            purpose=decision.purpose,
            depth=decision.depth,
            needs_clarification=False,
            profile=profile_decision.profile,
            need_deep_research=profile_decision.need_deep_research,
        )


class NoOpClarifier:
    """Clarifier stub that can be extended to ask targeted questions."""

    def clarify(self, request: NormalizedRequest, _decision: RouterDecision) -> Dict[str, str]:
        return {"query": request.query}


def _openai_search_safe(query: str) -> List[Dict[str, str]]:
    """Wrap OpenAI search transport with safety/telemetry."""

    try:
        return openai_web_search_transport(query, max_results=5)
    except Exception as exc:  # pragma: no cover - depends on external SDK
        logger.exception("OpenAI search transport failed; falling back to empty results: %s", exc)
        return []


def _build_search_tool() -> WebSearchTool:
    """Construct a search tool backed by OpenAI Responses web search."""

    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY is required for OpenAI-backed search; returning no-op search tool for tests")
        return WebSearchTool()
    
    try:
        from app.tools.openai_search import openai_web_search_transport
        
        def _openai_search_safe(q: str) -> List[Dict[str, str]]:
            """Wrapper around OpenAI search transport."""
            return openai_web_search_transport(q, max_results=5)
        
        return WebSearchTool(transport=_openai_search_safe)
    except Exception as exc:
        logger.warning("OpenAI search transport not available; using no-op transport: %s", exc)
        return WebSearchTool()


class ResearcherAdapter:
    """Wraps the research agent to match the orchestrator's expected signature."""

    def __init__(self, search_tool: WebSearchTool | None = None, deep_client: DeepResearchClient | None = None) -> None:
        self.agent = ResearchAgent(search_tool or _build_search_tool(), cache=TTLCache())
        self.deep_client = deep_client or DeepResearchClient(metrics_emitter=metrics)

    def research(
        self,
        request: NormalizedRequest,
        decision: RouterDecision,
        plan: ResearchPlan,
        pass_index: int,
        _persisted_task: Any,
    ) -> Dict[str, Any]:
        logger.info(
            "research.pass",
            extra={
                "query": request.query,
                "depth": decision.depth,
                "pass_index": pass_index,
                "profile": plan.search_profile,
            },
        )
        strategy = select_strategy(decision.profile or "DEFINITION_OR_SIMPLE_QUERY", decision.depth)
        
        # Initialize notes and overall_confidence before branching
        notes: List[str] = []
        overall_confidence: str = "medium"
        
        # Deep research path - use background mode for o3-deep-research
        metadata_deep_results = request.metadata.get("deep_results") if isinstance(request.metadata, dict) else None
        if metadata_deep_results:
            aggregated_results = {"preferred": metadata_deep_results, "all": metadata_deep_results}
            search_queries = [request.query]
            # Generate notes from deep results
            notes = [f"{item.title}: {item.snippet}" if hasattr(item, 'title') else str(item) for item in aggregated_results.get("preferred", [])[:5]]
            overall_confidence = "high"  # Deep research typically has high confidence
        elif "deep-research" in strategy.model and decision.depth == "deep":
            metrics.emit_search_query(request.query, decision.depth)
            # Use background mode for long-running deep research
            deep_results = self.deep_client.run_sync(request.query, max_results=strategy.max_searches, use_background=True)
            aggregated_results = {"preferred": deep_results, "all": deep_results}
            search_queries = [request.query]
            # Generate notes from deep results
            notes = [f"{item.title}: {item.snippet}" if hasattr(item, 'title') else str(item) for item in aggregated_results.get("preferred", [])[:5]]
            overall_confidence = "high"  # Deep research typically has high confidence
        else:
            search_queries = self._build_search_queries(request.query, strategy.max_searches, decision.depth)
            aggregated_results: Dict[str, List[Any]] = {"preferred": [], "all": []}
            aggregated_notes: List[str] = []
            aggregated_confidence: List[str] = []
            
            for idx, query in enumerate(search_queries):
                metrics.emit_search_query(query, decision.depth)
                # Use research_with_response to get structured WebSearchResponse
                results, web_response = self.agent.research_with_response(
                    query, 
                    depth=decision.depth, 
                    max_calls=strategy.max_searches,
                    model=strategy.model
                )
                aggregated_results["preferred"].extend(results.get("preferred", []))
                aggregated_results["all"].extend(results.get("all", []))
                
                # Collect notes and confidence from WebSearchResponse
                if web_response and web_response.notes_for_downstream_agents:
                    aggregated_notes.extend(web_response.notes_for_downstream_agents)
                if web_response and web_response.overall_confidence:
                    aggregated_confidence.append(web_response.overall_confidence)
                
                if len(aggregated_results["preferred"]) >= strategy.max_searches:
                    aggregated_results["preferred"] = aggregated_results["preferred"][: strategy.max_searches]
                    break
            
            # Combine notes: result summaries + downstream agent notes
            notes = [f"{item.title}: {item.snippet}" for item in aggregated_results.get("preferred", [])]
            notes.extend(aggregated_notes)
            
            # Determine overall confidence
            if aggregated_confidence:
                if all(c == "high" for c in aggregated_confidence):
                    overall_confidence = "high"
                elif any(c == "low" for c in aggregated_confidence):
                    overall_confidence = "low"
        
        return {
            "pass_index": pass_index,
            "profile": plan.search_profile,
            "model": strategy.model,
            "effort": strategy.effort,
            "results": aggregated_results,
            "search_queries": search_queries,
            "notes": notes,
            "overall_confidence": overall_confidence,
        }

    @staticmethod
    def _build_search_queries(query: str, max_searches: int, depth: str) -> List[str]:
        """Generate search queries based on depth and limit."""

        if depth == "quick":
            return [query]
        if depth == "standard":
            variations = [query, f"latest news {query}"]
        else:  # deep
            variations = [query, f"recent developments {query}", f"risks and outlook {query}"]
        return variations[:max_searches]


def _build_deliverable_fields(purpose: str, query: str) -> Dict[str, str]:
    """Create minimal placeholder fields for the given purpose template."""

    deliverable_fields: Dict[str, str] = {}
    required_keys = template_renderer.MANDATORY_DELIVERABLE_FIELDS.get(purpose)
    if not required_keys:
        return {"notes": f"Notes for '{query}'."}

    for key in required_keys:
        human_label = key.replace("_", " ").title()
        deliverable_fields[key] = f"{human_label} for '{query}'."
    return deliverable_fields


def _select_citations(research_results: List[Dict[str, Any]]) -> List[Citation]:
    """Convert preferred research results into Citation models."""

    citations: List[Citation] = []
    for result in research_results:
        preferred = result.get("results", {}).get("preferred", [])
        for item in preferred:
            if len(citations) >= 5:
                break
            citations.append(
                Citation(
                    source=item.title or "Source",
                    url=item.url,
                    note=item.snippet,
                )
            )
        if len(citations) >= 5:
            break
    return citations


def _build_findings(research_results: List[Dict[str, Any]]) -> List[Finding]:
    """Normalize search results into structured findings."""

    findings: List[Finding] = []
    counter = 1
    for result in research_results:
        preferred = result.get("results", {}).get("preferred", [])
        for item in preferred:
            findings.append(
                Finding(
                    id=f"F{counter}",
                    title=item.title or "Finding",
                    type="web",
                    relevance="medium",
                    source_url=item.url,
                    source_name=item.title or "",
                    snippet=item.snippet,
                    key_points=[item.snippet] if item.snippet else [],
                )
            )
            counter += 1
    return findings


def _build_evidence(findings: List[Finding]) -> List[Evidence]:
    """Create evidence items referencing findings."""

    evidence: List[Evidence] = []
    for finding in findings:
        claim_text = finding.key_points[0] if finding.key_points else (finding.snippet or finding.title)
        evidence.append(
            Evidence(
                id=f"E{finding.id}",
                claim=claim_text,
                excerpt=finding.snippet or "",
                source_id=finding.id,
                source_url=finding.source_url,
                confidence="medium",
            )
        )
    return evidence


class TemplateWriter:
    """Compose the final envelope and rendered Markdown document.
    
    Always uses GPT-5.1 writer for structured reporting (all purposes and depths).
    """

    def __init__(self, gpt_writer: Optional[GPT5WriterAgent] = None) -> None:
        self.gpt_writer = gpt_writer or GPT5WriterAgent()

    def write(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        router: RouterDecision = payload["router"]
        plan: ResearchPlan = payload["plan"]
        research_results: List[Dict[str, Any]] = payload["research"]
        request: NormalizedRequest = payload["request"]

        controls = _controls_from_metadata(request.metadata)
        region_timeframe = controls.region or controls.timeframe or "n/a"

        citations = _select_citations(research_results)
        source_block = render_citations(
            [SimpleCitation(title=c.source, url=c.url or "", snippet=c.note or "") for c in citations]
        ) or "- (pending web search integration)"
        bibliography_entries = [
            {
                "id": f"S{i+1}",
                "title": citation.source,
                "url": citation.url or "",
                "annotation": citation.note or "",
            }
            for i, citation in enumerate(citations)
        ]
        source_map = {entry["id"]: entry["url"] for entry in bibliography_entries}

        # Always use GPT-5.1 writer for structured reporting (all purposes and depths)
        logger.info("Using GPT-5.1 writer for structured deliverable", extra={"purpose": router.purpose, "depth": router.depth})
        
        # Get strategy to determine effort level
        from app.strategy import select_strategy
        strategy = select_strategy(router.profile or "DEFINITION_OR_SIMPLE_QUERY", router.depth)
        
        # Extract notes_for_downstream_agents from research results
        research_notes = []
        for result in research_results:
            if isinstance(result, dict):
                notes = result.get("notes", [])
                if notes:
                    research_notes.extend(notes if isinstance(notes, list) else [notes])
        
        citation_dicts = [
            {"title": c.source, "url": c.url or "", "snippet": c.note or ""} for c in citations
        ]
        gpt_output = self.gpt_writer.write_deliverable(
            purpose=router.purpose,
            research_findings=research_results,
            query=request.query,
            citations=citation_dicts,
            context={
                "audience": controls.audience.value,
                "region": controls.region,
                "timeframe": controls.timeframe,
                "research_notes": research_notes,  # Pass notes from WebSearchResponse
            },
            effort=strategy.effort,  # Pass effort from strategy
            depth=router.depth,  # Pass depth for verbosity
        )
        rendered_deliverable = gpt_output.get("deliverable", "")
        executive_summary = gpt_output.get("executive_summary", "")

        base_fields = {
            "title": f"Research: {request.query}",
            "purpose": router.purpose,
            "depth": router.depth,
            "audience": controls.audience.value,
            "region_timeframe": region_timeframe,
            "executive_summary": executive_summary,
            "sources": source_block,
            "assumptions_gaps": "Research findings synthesized. Key assumptions and gaps identified in deliverable.",
            "open_questions": ["Validate key claims with additional sources", "Confirm numerical estimates"],
            "next_steps": ["Review deliverable for completeness", "Validate citations"],
        }

        # Render full document with envelope
        deliverable_fields_for_envelope = _build_deliverable_fields(router.purpose, request.query)
        rendered_document = template_renderer.render_document(router.purpose, base_fields, deliverable_fields_for_envelope)

        findings = _build_findings(research_results)
        evidence_items = _build_evidence(findings)
        envelope = ResponseEnvelope(
            title=base_fields["title"],
            metadata=ResponseMetadata(
                purpose=controls.purpose,
                depth=controls.depth,
                audience=controls.audience,
                region=controls.region,
                timeframe=controls.timeframe,
                status=TaskStatus.COMPLETED,
            ),
            executive_summary=executive_summary,
            deliverable=rendered_deliverable,
            citations=citations,
            assumptions_and_gaps=base_fields["assumptions_gaps"],
            open_questions=base_fields["open_questions"],
            next_steps=base_fields["next_steps"],
        )

        sections = {
            "Executive Summary": envelope.executive_summary,
            "Deliverable": envelope.deliverable,
            "Assumptions & Gaps": envelope.assumptions_and_gaps,
            "Open Questions": "\n".join(envelope.open_questions),
        }
        evaluation = evaluate_report_sections(sections, required_sections=list(sections.keys()))

        # Determine output format from controls
        output_format = controls.output_format if hasattr(controls, "output_format") else "markdown"
        
        # Build structured JSON output if requested
        structured_output = None
        if output_format == "json":
            structured_output = {
                "title": envelope.title,
                "metadata": {
                    "purpose": envelope.metadata.purpose.value,
                    "depth": envelope.metadata.depth.value,
                    "audience": envelope.metadata.audience.value,
                    "region": envelope.metadata.region,
                    "timeframe": envelope.metadata.timeframe,
                    "status": envelope.metadata.status.value,
                    "created_at": envelope.metadata.created_at.isoformat() if hasattr(envelope.metadata, "created_at") else None,
                },
                "executive_summary": envelope.executive_summary,
                "deliverable": {
                    "content": envelope.deliverable,
                    "format": "markdown",
                },
                "citations": [
                    {
                        "source": c.source,
                        "url": c.url,
                        "note": c.note,
                    }
                    for c in envelope.citations
                ],
                "assumptions_and_gaps": envelope.assumptions_and_gaps,
                "open_questions": envelope.open_questions,
                "next_steps": envelope.next_steps,
                "quality": {
                    "citation_coverage_score": evaluation.citation_coverage_score,
                    "template_completeness_score": evaluation.template_completeness_score,
                    "missing_sections": evaluation.missing_sections,
                    "section_coverage": summarize_coverage_by_section(evaluation.section_evaluations),
                    "uncited_numbers": evaluation.has_uncited_numbers,
                    "contradictions": evaluation.has_contradictions,
                },
                "bibliography": bibliography_entries,
                "source_map": source_map,
                "findings": [finding.dict() for finding in findings],
                "evidence": [ev.dict() for ev in evidence_items],
                "overall_confidence": "medium",
            }
        
        result = {
            "envelope": envelope,
            "rendered_markdown": rendered_document if output_format == "markdown" else None,
            "structured_json": structured_output if output_format == "json" else None,
            "output_format": output_format,
            "plan": asdict(plan),
            "quality": QualityReport(
                citation_coverage_score=evaluation.citation_coverage_score,
                template_completeness_score=evaluation.template_completeness_score,
                missing_sections=evaluation.missing_sections,
                section_coverage=summarize_coverage_by_section(evaluation.section_evaluations),
                uncited_numbers=evaluation.has_uncited_numbers,
                contradictions=evaluation.has_contradictions,
            ),
            "bibliography": render_bibliography(bibliography_entries),
            "source_map": source_map,
            "notes": [note for result in research_results for note in result.get("notes", [])],
            "findings": [finding.dict() for finding in findings],
            "evidence": [ev.dict() for ev in evidence_items],
            "overall_confidence": "medium",
        }
        return result


class FactCheckerAgent:
    """LLM-powered fact-checker using GPT-5.1 for contradiction and citation analysis.
    
    This is a thin wrapper around LLMFactCheckerAgent that delegates all checking logic.
    """

    def __init__(self, llm_checker: Optional[LLMFactCheckerAgent] = None) -> None:
        self.llm_checker = llm_checker or LLMFactCheckerAgent(metrics_emitter=metrics)

    def check(self, written_output: Dict[str, Any], effort: str = "high", depth: str = "standard") -> QualityReport:
        """Delegate to LLM fact checker for comprehensive analysis."""
        return self.llm_checker.check(written_output, effort=effort, depth=depth)


def build_orchestrator() -> Orchestrator:
    """Construct an orchestrator wired with LLM agents (GPT-5.1-mini router/clarifier, GPT-5.1 writer/fact-checker)."""
    
    from app.orchestrator import RetryConfig
    
    # Initialize agents
    router_agent = LLMRouterAgent(metrics_emitter=metrics)
    clarifier_agent = LLMClarifierAgent(metrics_emitter=metrics)
    researcher_agent = ResearcherAdapter()
    writer_agent = TemplateWriter(gpt_writer=GPT5WriterAgent(metrics=metrics))
    fact_checker_agent = FactCheckerAgent(llm_checker=LLMFactCheckerAgent(metrics_emitter=metrics))
    
    # Timeout for synchronous requests (quick/standard depth)
    # Note: Deep research uses async mode with background polling (15 min timeout in _process_task)
    # Minimum 5 minutes for synchronous requests to allow for longer responses
    retry_config = RetryConfig(max_attempts=3, backoff_factor=0.5, timeout_seconds=300.0)
    
    # Register agents as tools for dynamic orchestration
    from app.utils.agent_tools import register_agent_tool
    from app.orchestrator import NormalizedRequest, RouterDecision, ResearchPlan
    
    # Register router as a tool (for clarification handoffs)
    register_agent_tool(
        name="classify_query_intent",
        description="Classify user query to determine purpose, depth, and routing decisions",
        agent_func=lambda request: router_agent.classify(request),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "User query to classify"},
            },
            "required": ["query"],
        },
    )
    
    # Register clarifier as a tool (for research handoffs)
    register_agent_tool(
        name="clarify_ambiguous_query",
        description="Generate targeted clarification questions for ambiguous queries",
        agent_func=lambda request, decision: clarifier_agent.clarify(request, decision),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Ambiguous query to clarify"},
                "needs_clarification": {"type": "boolean", "description": "Whether clarification is needed"},
            },
            "required": ["query"],
        },
    )
    
    # Register researcher as a tool (for writer handoffs)
    register_agent_tool(
        name="perform_web_research",
        description="Perform web research on a query with specified depth and strategy",
        agent_func=lambda request, decision, plan, pass_index: researcher_agent.research(request, decision, plan, pass_index, None),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research query"},
                "depth": {"type": "string", "enum": ["quick", "standard", "deep"], "description": "Research depth"},
            },
            "required": ["query", "depth"],
        },
    )
    
    logger.info("Registered agents as tools for dynamic orchestration")

    return Orchestrator(
        router_agent=router_agent,
        clarifier_agent=clarifier_agent,
        researcher_agent=researcher_agent,
        writer_agent=writer_agent,
        fact_checker_agent=fact_checker_agent,
        retry_config=retry_config,
    )
