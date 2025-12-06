"""Semantic citation validation utilities."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.schemas import Citation

logger = logging.getLogger(__name__)

DEFAULT_VALIDATION_MODEL = "gpt-5.1"


class SemanticCitationValidator:
    """Validates citations semantically and checks URL accessibility."""
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        strict_mode: bool = False,
    ) -> None:
        self.model = model or DEFAULT_VALIDATION_MODEL
        self.api_key = api_key
        self.strict_mode = strict_mode
        if OpenAI is None:
            logger.warning("OpenAI package not available; semantic citation validation will not function")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None
    
    def validate_citations(
        self,
        document_text: str,
        citations: List[Citation],
        effort: str = "high",
    ) -> Dict[str, Any]:
        """Validate citations semantically and check URL accessibility.
        
        Returns:
            Dictionary with validation results:
            - semantic_scores: Dict[str, float] - Per-citation semantic relevance scores
            - url_accessibility: Dict[str, bool] - URL accessibility status
            - broken_urls: List[str] - List of inaccessible URLs
            - low_relevance_citations: List[str] - Citations with low relevance scores
            - overall_semantic_score: float - Average semantic score
        """
        results = {
            "semantic_scores": {},
            "url_accessibility": {},
            "broken_urls": [],
            "low_relevance_citations": [],
            "overall_semantic_score": 0.0,
        }
        
        if not citations:
            return results
        
        # Extract claims with citations from document
        claim_citation_pairs = self._extract_claim_citation_pairs(document_text, citations)
        
        # Validate semantic relevance
        semantic_scores = {}
        for claim, citation in claim_citation_pairs:
            score = self._score_citation_relevance(claim, citation, effort)
            citation_key = citation.url or citation.source
            semantic_scores[citation_key] = score
        
        results["semantic_scores"] = semantic_scores
        
        # Check URL accessibility
        url_accessibility = {}
        broken_urls = []
        for citation in citations:
            if citation.url:
                is_accessible = self._check_url_accessibility(citation.url)
                url_accessibility[citation.url] = is_accessible
                if not is_accessible:
                    broken_urls.append(citation.url)
        
        results["url_accessibility"] = url_accessibility
        results["broken_urls"] = broken_urls
        
        # Calculate overall semantic score
        if semantic_scores:
            results["overall_semantic_score"] = sum(semantic_scores.values()) / len(semantic_scores)
        else:
            results["overall_semantic_score"] = 0.5  # Default neutral score
        
        # Identify low relevance citations
        threshold = 0.5
        for citation_key, score in semantic_scores.items():
            if score < threshold:
                results["low_relevance_citations"].append(citation_key)
        
        return results
    
    def _extract_claim_citation_pairs(self, document_text: str, citations: List[Citation]) -> List[tuple[str, Citation]]:
        """Extract claims that reference citations."""
        pairs = []
        
        # Find citation references in text (e.g., [S1], [S2], etc.)
        import re
        citation_pattern = r'\[S(\d+)\]'
        
        # Map citation indices to Citation objects
        citation_map = {str(i + 1): citations[i] for i in range(len(citations))}
        
        # Find all citation references
        matches = list(re.finditer(citation_pattern, document_text))
        
        for match in matches:
            citation_idx = match.group(1)
            citation = citation_map.get(citation_idx)
            if citation:
                # Extract claim context (sentence or paragraph containing citation)
                start = max(0, match.start() - 200)
                end = min(len(document_text), match.end() + 200)
                claim = document_text[start:end].strip()
                pairs.append((claim, citation))
        
        return pairs
    
    def _score_citation_relevance(self, claim: str, citation: Citation, effort: str = "high") -> float:
        """Score how relevant a citation is to a claim using LLM."""
        if not self.client:
            raise RuntimeError("OpenAI client not available for semantic citation validation")
        
        try:
            # Build prompt for semantic validation
            prompt = f"""Evaluate how well the following citation supports the given claim.

Claim: {claim}

Citation:
- Title: {citation.source}
- URL: {citation.url or 'N/A'}
- Snippet: {citation.note or 'N/A'}

Rate the semantic relevance on a scale of 0.0 to 1.0, where:
- 1.0 = Citation directly supports the claim
- 0.5 = Citation is somewhat related but not directly supporting
- 0.0 = Citation is irrelevant or contradicts the claim

Return only a JSON object with a single field "relevance_score" (float between 0.0 and 1.0)."""
            
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are an expert at evaluating citation relevance. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_output_tokens=100,
            )
            content = getattr(response, "output_text", "") or "{}"
            
            import json
            result = json.loads(content)
            score = float(result.get("relevance_score", 0.5))
            
            # Clamp score to [0.0, 1.0]
            return max(0.0, min(1.0, score))
            
        except Exception as exc:
            logger.warning("Failed to score citation relevance: %s", exc)
            raise
    
    def _check_url_accessibility(self, url: str, timeout: int = 5) -> bool:
        """Check if a URL is accessible."""
        if not httpx:
            logger.warning("httpx not available; skipping URL accessibility check")
            return True  # Assume accessible if we can't check
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Use HEAD request to check accessibility
            response = httpx.head(url, timeout=timeout, follow_redirects=True)
            return response.status_code < 400
        except Exception as exc:
            logger.debug("URL accessibility check failed for %s: %s", url, exc)
            return False
