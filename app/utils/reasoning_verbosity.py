"""Utilities for mapping strategy effort and depth to reasoning/verbosity parameters."""
from __future__ import annotations

from typing import Dict, Literal

Effort = Literal["low", "medium", "high"]
Depth = Literal["quick", "standard", "deep"]
Verbosity = Literal["low", "medium", "high"]


def map_effort_to_reasoning(effort: Effort) -> Dict[str, str]:
    """Map strategy effort to reasoning parameter for GPT-5 models.
    
    Args:
        effort: Strategy effort level (low, medium, high)
        
    Returns:
        Dictionary with reasoning parameter for API calls
    """
    reasoning_map = {
        "low": "low",
        "medium": "medium",
        "high": "high",
    }
    return {"reasoning": {"effort": reasoning_map.get(effort, "medium")}}


def map_depth_to_verbosity(depth: Depth) -> Dict[str, str]:
    """Map depth to verbosity parameter for GPT-5 models.
    
    Args:
        depth: Research depth (quick, standard, deep)
        
    Returns:
        Dictionary with text verbosity parameter for API calls
    """
    verbosity_map = {
        "quick": "low",      # Quick queries → concise output
        "standard": "medium",  # Standard queries → balanced output
        "deep": "high",      # Deep queries → detailed output
    }
    return {"text": {"verbosity": verbosity_map.get(depth, "medium")}}


def build_reasoning_verbosity_params(effort: Effort, depth: Depth) -> Dict[str, Dict[str, str]]:
    """Build combined reasoning and verbosity parameters for GPT-5 API calls.
    
    Args:
        effort: Strategy effort level
        depth: Research depth
        
    Returns:
        Dictionary with both reasoning and text parameters
    """
    params = {}
    params.update(map_effort_to_reasoning(effort))
    params.update(map_depth_to_verbosity(depth))
    return params

