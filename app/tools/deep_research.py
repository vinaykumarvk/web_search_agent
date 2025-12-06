"""Deep research client abstraction (OpenAI Responses background-ready)."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.tools.web_search import SearchResult
from app.observability import MetricsEmitter

logger = logging.getLogger(__name__)

try:
    from typing import Any
except ImportError:
    from typing import Any  # type: ignore


class DeepResearchClient:
    """Simple wrapper to call OpenAI deep research-capable models with background mode support."""

    def __init__(self, model: Optional[str] = None, metrics_emitter: Optional[Any] = None) -> None:
        self.model = model or os.environ.get("OPENAI_DEEP_MODEL", "o3-deep-research")
        self.metrics = metrics_emitter or MetricsEmitter()
        self._client = None
        if OpenAI is not None and os.environ.get("OPENAI_API_KEY"):
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def run_background(self, query: str) -> str:
        """Start a deep research request in background mode and return response_id.

        Returns the response_id that can be used to poll for results later.
        """
        if self._client is None:
            raise RuntimeError("OpenAI client unavailable; cannot start background research")

        try:
            response = self._client.responses.create(
                model=self.model,
                input=query,
                tools=[{"type": "web_search"}],
                response_mode="background",
            )
            response_id = getattr(response, "id", None) or getattr(response, "response_id", None)
            if not response_id:
                raise ValueError("Background response did not return a response_id")
            logger.info("Started background deep research", extra={"response_id": response_id, "query": query})
            return response_id
        except Exception as exc:
            logger.exception("Failed to start background deep research: %s", exc)
            if settings.strict_mode:
                raise DeepResearchError(f"Failed to start background deep research: {exc}") from exc
            raise

    def retrieve_response(self, response_id: str, max_wait_seconds: int = 900) -> Dict:  # 15 minutes default timeout
        """Retrieve a background response by ID, polling until complete.

        Returns the full response object when ready.
        """
        if self._client is None:
            raise RuntimeError("OpenAI client unavailable; cannot retrieve response")

        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            try:
                response = self._client.responses.retrieve(response_id)
                status = getattr(response, "status", None) or getattr(response, "response_status", None)
                
                if status in ("completed", "succeeded"):
                    logger.info("Background deep research completed", extra={"response_id": response_id})
                    usage = getattr(response, "usage", None)
                    if usage and self.metrics:
                        self.metrics.emit_token_usage(
                            stage="deep_research_background",
                            prompt_tokens=getattr(usage, "prompt_tokens", 0),
                            completion_tokens=getattr(usage, "completion_tokens", 0),
                            model=self.model,
                        )
                    return response
                elif status in ("failed", "error"):
                    error_msg = getattr(response, "error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Deep research failed: {error_msg}")
                
                # Still processing, wait and retry
                time.sleep(2)
            except Exception as exc:
                if "not found" in str(exc).lower():
                    raise ValueError(f"Response ID {response_id} not found")
                logger.warning("Error retrieving response, retrying...", exc_info=exc)
                time.sleep(2)
        
        raise TimeoutError(f"Deep research did not complete within {max_wait_seconds} seconds")

    def _extract_intermediate_notes(self, response: object) -> List[str]:
        """Extract intermediate notes from O3 deep research response.
        
        O3 deep research may include intermediate notes/thoughts during the research process.
        These can be extracted from response.output or response.output_text.
        """
        notes = []
        
        # Try to extract from output_text
        output_text = getattr(response, "output_text", None)
        if output_text:
            # Look for note-like patterns or intermediate thoughts
            lines = output_text.split("\n")
            for line in lines:
                line = line.strip()
                if line and (
                    line.startswith("Note:") or
                    line.startswith("Thinking:") or
                    line.startswith("Researching:") or
                    len(line) > 50  # Likely a note if it's a longer line
                ):
                    notes.append(line)
        
        # Try to extract from output structure
        output = getattr(response, "output", None)
        if output and isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    # Look for note fields
                    note_text = item.get("note") or item.get("notes") or item.get("thought")
                    if note_text:
                        notes.append(str(note_text))
        
        return notes[:10]  # Limit to 10 notes to avoid overwhelming
    
    def _extract_citations_from_response(self, response: object) -> List[SearchResult]:
        """Extract structured citations from O3 deep research response.
        
        O3 deep research returns citations in various formats:
        1. response.citations (list of citation objects)
        2. response.output with citation metadata
        3. response.output_text with embedded citations
        """
        results: List[SearchResult] = []
        
        # Method 1: Extract from response.citations attribute
        citations = getattr(response, "citations", None)
        if citations:
            if isinstance(citations, list):
                for citation in citations:
                    if isinstance(citation, dict):
                        results.append(
                            SearchResult(
                                title=citation.get("title", citation.get("name", "")),
                                url=citation.get("url", citation.get("link", "")),
                                snippet=citation.get("snippet", citation.get("excerpt", "")),
                                source_type=citation.get("source_type", citation.get("type", "unknown")),
                            )
                        )
            elif isinstance(citations, dict):
                # Single citation dict
                results.append(
                    SearchResult(
                        title=citations.get("title", citations.get("name", "")),
                        url=citations.get("url", citations.get("link", "")),
                        snippet=citations.get("snippet", citations.get("excerpt", "")),
                        source_type=citations.get("source_type", citations.get("type", "unknown")),
                    )
                )
        
        # Method 2: Extract from response.output (structured output)
        output = getattr(response, "output", None)
        if output and not results:
            try:
                if isinstance(output, list):
                    for item in output:
                        if isinstance(item, dict):
                            # Check for citation-like structure
                            if "url" in item or "link" in item or "citation" in item:
                                results.append(
                                    SearchResult(
                                        title=item.get("title", item.get("name", "")),
                                        url=item.get("url", item.get("link", "")),
                                        snippet=item.get("snippet", item.get("excerpt", item.get("text", ""))),
                                        source_type=item.get("source_type", item.get("type", "unknown")),
                                    )
                                )
            except Exception as exc:
                logger.debug("Error extracting citations from output: %s", exc)
        
        # Method 3: Extract from output_text (text with embedded citations)
        text = getattr(response, "output_text", "") or ""
        if text and not results:
            # Try to parse JSON if present
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and (item.get("url") or item.get("title")):
                            results.append(
                                SearchResult(
                                    title=item.get("title", ""),
                                    url=item.get("url", ""),
                                    snippet=item.get("snippet", item.get("text", "")),
                                    source_type=item.get("source_type", "unknown"),
                                )
                            )
                elif isinstance(parsed, dict):
                    # Single citation object
                    if parsed.get("url") or parsed.get("title"):
                        results.append(
                            SearchResult(
                                title=parsed.get("title", ""),
                                url=parsed.get("url", ""),
                                snippet=parsed.get("snippet", parsed.get("text", "")),
                                source_type=parsed.get("source_type", "unknown"),
                            )
                        )
            except json.JSONDecodeError:
                # Try to extract URLs from text (fallback)
                import re
                url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                urls = re.findall(url_pattern, text)
                if urls:
                    for url in urls[:10]:  # Limit to 10 URLs
                        results.append(
                            SearchResult(
                                title=f"Source from {url[:50]}",
                                url=url,
                                snippet="",
                                source_type="unknown",
                            )
                        )
                else:
                    # Last resort: treat lines as findings
                    for line in text.splitlines():
                        if line.strip() and len(results) < 20:
                            results.append(
                                SearchResult(
                                    title=line.strip()[:80],
                                    url="",
                                    snippet=line.strip(),
                                    source_type="unknown",
                                )
                            )
        
        return results

    def run_sync(self, query: str, max_results: int = 10, use_background: bool = False) -> List[SearchResult]:
        """Run a deep research request.

        If use_background=True, starts in background mode and polls until complete.
        Otherwise, uses create_and_wait for synchronous execution.
        """
        if OpenAI is None or not os.environ.get("OPENAI_API_KEY"):
            logger.warning("OpenAI client unavailable; deep research returns no results")
            return []

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        if use_background:
            try:
                response_id = self.run_background(query)
                response = self.retrieve_response(response_id)
                results = self._extract_citations_from_response(response)
                # Token usage already emitted in retrieve_response()
                return results[:max_results]
            except Exception as exc:
                logger.exception("Background deep research failed: %s", exc)
                return []
        
        # Synchronous mode (for quick tests or when background not needed)
        try:
            response = client.responses.create(
                model=self.model,
                input=query,
                tools=[{"type": "web_search"}],
            )
            
            # Extract and emit token usage metrics
            usage = getattr(response, "usage", None)
            if usage and self.metrics:
                self.metrics.emit_token_usage(
                    stage="deep_research_sync",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                    model=self.model,
                )
            
            results = self._extract_citations_from_response(response)
            return results[:max_results]
        except Exception as exc:
            logger.exception("Deep research failed: %s", exc)
            return []


class MockDeepResearchClient(DeepResearchClient):
    """Deterministic client for tests."""

    def __init__(self, results: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(model="mock")
        self._results = results or [
            {"title": "Deep Finding 1", "url": "https://example.com/df1", "snippet": "Snippet 1"},
            {"title": "Deep Finding 2", "url": "https://example.com/df2", "snippet": "Snippet 2"},
        ]
        self.calls: List[str] = []
        self._background_runs: Dict[str, List[SearchResult]] = {}

    def run_sync(self, query: str, max_results: int = 10, use_background: bool = False) -> List[SearchResult]:
        self.calls.append(query)
        return [SearchResult.from_raw(item) for item in self._results[:max_results]]

    def run_background(self, query: str) -> str:
        self.calls.append(query)
        response_id = f"resp_{len(self.calls)}"
        self._background_runs[response_id] = [SearchResult.from_raw(item) for item in self._results]
        return response_id

    def retrieve_response(self, response_id: str, max_wait_seconds: int = 900) -> Dict:  # 15 minutes default timeout
        class Resp:
            def __init__(self, results: List[SearchResult]) -> None:
                self.status = "completed"
                self.output = []
                self.citations = [r.__dict__ for r in results]
                self.usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 20})

        results = self._background_runs.get(response_id, [])
        return Resp(results)
