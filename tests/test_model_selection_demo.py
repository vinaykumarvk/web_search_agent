"""Demonstration of model selection across different query types with expected outputs."""
from __future__ import annotations

import json
from typing import Dict, List

from app.agents.profile_router import classify_web_profile
from app.strategy import select_strategy


# Test queries covering different scenarios with expected classifications
TEST_QUERIES = [
    {
        "id": 1,
        "query": "What is artificial intelligence?",
        "description": "Simple definition query - quick answer",
        "expected": {
            "purpose": "market_query",
            "depth": "quick",
            "profile": "MARKET_OR_TREND_QUERY",
            "research_model": "gpt-5.1",
            "max_searches": 2,
        },
    },
    {
        "id": 2,
        "query": "Write a comprehensive Business Requirements Document for a mobile banking application",
        "description": "BRD request - deep research needed",
        "expected": {
            "purpose": "brd",
            "depth": "deep",
            "profile": "BRD_MODELING",
            "research_model": "o3-deep-research",
            "max_searches": 8,
        },
    },
    {
        "id": 3,
        "query": "Research Apple Inc. company overview and recent financial performance",
        "description": "Company research - standard depth",
        "expected": {
            "purpose": "company_research",
            "depth": "standard",
            "profile": "COMPANY_RESEARCH",
            "research_model": "gpt-5.1",
            "max_searches": 4,
        },
    },
    {
        "id": 4,
        "query": "Compare TAM vs SAM vs SOM in market sizing",
        "description": "Market query - quick comparison",
        "expected": {
            "purpose": "market_query",
            "depth": "quick",
            "profile": "MARKET_OR_TREND_QUERY",
            "research_model": "gpt-5.1",
            "max_searches": 2,
        },
    },
    {
        "id": 5,
        "query": "Elaborate requirements for a user authentication feature into epics and user stories",
        "description": "Requirement elaboration - standard depth",
        "expected": {
            "purpose": "req_elaboration",
            "depth": "standard",
            "profile": "REQUIREMENT_ELABORATION",
            "research_model": "gpt-5.1",
            "max_searches": 3,
        },
    },
    {
        "id": 6,
        "query": "Deep dive analysis of Tesla's autonomous driving strategy and competitive positioning",
        "description": "Company research - deep analysis",
        "expected": {
            "purpose": "company_research",
            "depth": "deep",
            "profile": "COMPANY_RESEARCH",
            "research_model": "o3-deep-research",
            "max_searches": 8,
        },
    },
    {
        "id": 7,
        "query": "Create a BRD for implementing two-factor authentication",
        "description": "BRD request - standard depth",
        "expected": {
            "purpose": "brd",
            "depth": "standard",
            "profile": "BRD_MODELING",
            "research_model": "gpt-5.1",
            "max_searches": 4,
        },
    },
    {
        "id": 8,
        "query": "What are the latest trends in cloud computing?",
        "description": "Market trend query - standard depth",
        "expected": {
            "purpose": "market_query",
            "depth": "standard",
            "profile": "MARKET_OR_TREND_QUERY",
            "research_model": "gpt-5.1",
            "max_searches": 4,
        },
    },
    {
        "id": 9,
        "query": "Break down the requirement for a payment gateway integration",
        "description": "Requirement elaboration - quick breakdown",
        "expected": {
            "purpose": "req_elaboration",
            "depth": "quick",
            "profile": "REQUIREMENT_ELABORATION",
            "research_model": "gpt-5.1",
            "max_searches": 2,
        },
    },
    {
        "id": 10,
        "query": "I need a comprehensive document outlining what we should build for a customer portal",
        "description": "Ambiguous query - should detect BRD intent",
        "expected": {
            "purpose": "brd",
            "depth": "deep",
            "profile": "BRD_MODELING",
            "research_model": "o3-deep-research",
            "max_searches": 8,
        },
    },
]


def simulate_model_selection_flow(query: Dict) -> Dict:
    """Simulate the model selection flow using expected classifications."""
    
    expected = query["expected"]
    purpose = expected["purpose"]
    depth = expected["depth"]
    
    # Stage 1: Router (GPT-5-mini) - classification
    router_decision = {
        "purpose": purpose,
        "depth": depth,
        "needs_clarification": False,
    }
    
    # Stage 2: Profile determination
    profile_decision = classify_web_profile(
        query["query"],
        purpose_hint=purpose,
        depth_hint=depth,
    )
    profile = profile_decision.profile
    
    # Stage 3: Strategy selection
    strategy = select_strategy(profile, depth)
    
    # Stage 4: Determine all models used
    models_used = {
        "router": "gpt-5-mini",
        "clarifier": None,  # Only if needs_clarification is True
        "research": strategy.model,
        "writer": "gpt-5.1",
        "fact_checker": "gpt-5.1",
    }
    
    return {
        "query_id": query["id"],
        "query": query["query"],
        "description": query["description"],
        "router_decision": {
            **router_decision,
            "profile": profile,
        },
        "strategy": {
            "model": strategy.model,
            "effort": strategy.effort,
            "max_searches": strategy.max_searches,
            "recency_bias": strategy.recency_bias,
        },
        "models_used": models_used,
        "expected": expected,
        "matches_expected": strategy.model == expected["research_model"],
    }


def print_detailed_table(results: List[Dict]) -> None:
    """Print a detailed formatted table showing model selection."""
    
    print("\n" + "=" * 140)
    print("MODEL SELECTION DEMONSTRATION - 10 Test Queries")
    print("=" * 140)
    
    for result in results:
        print(f"\n{'─' * 140}")
        print(f"Query #{result['query_id']}: {result['query']}")
        print(f"Description: {result['description']}")
        
        print(f"\n{'Stage 1: Router (GPT-5-mini)':<50} {'Stage 2: Profile Router':<50}")
        print(f"{'─' * 50} {'─' * 50}")
        print(f"Purpose: {result['router_decision']['purpose']:<45} Profile: {result['router_decision']['profile']}")
        print(f"Depth: {result['router_decision']['depth']:<46} Need Deep Research: {result['strategy']['model'] == 'o3-deep-research'}")
        print(f"Needs Clarification: {result['router_decision']['needs_clarification']}")
        
        print(f"\n{'Stage 3: Strategy Matrix Lookup':<70} {'Stage 4: Models Used':<70}")
        print(f"{'─' * 70} {'─' * 70}")
        print(f"Lookup Key: ({result['router_decision']['profile']}, {result['router_decision']['depth']})")
        print(f"Research Model: {result['strategy']['model']:<60} Router: {result['models_used']['router']}")
        print(f"Max Searches: {result['strategy']['max_searches']:<63} Research: {result['models_used']['research']}")
        print(f"Effort: {result['strategy']['effort']:<66} Writer: {result['models_used']['writer']}")
        print(f"Recency Bias: {result['strategy']['recency_bias']:<63} Fact Checker: {result['models_used']['fact_checker']}")
        
        if result['matches_expected']:
            print(f"\n✓ Matches Expected Model: {result['expected']['research_model']}")
        else:
            print(f"\n⚠ Expected: {result['expected']['research_model']}, Got: {result['strategy']['model']}")
    
    print("\n" + "=" * 140)
    print("SUMMARY STATISTICS")
    print("=" * 140)
    
    # Count model usage
    research_models = {}
    depths = {}
    purposes = {}
    profiles = {}
    
    for result in results:
        research_model = result['models_used']['research']
        research_models[research_model] = research_models.get(research_model, 0) + 1
        
        depth = result['router_decision']['depth']
        depths[depth] = depths.get(depth, 0) + 1
        
        purpose = result['router_decision']['purpose']
        purposes[purpose] = purposes.get(purpose, 0) + 1
        
        profile = result['router_decision']['profile']
        profiles[profile] = profiles.get(profile, 0) + 1
    
    print(f"\nResearch Model Distribution:")
    for model, count in sorted(research_models.items()):
        percentage = (count / len(results)) * 100
        print(f"  {model:<25} {count:>2} queries ({percentage:>5.1f}%)")
    
    print(f"\nDepth Distribution:")
    for depth, count in sorted(depths.items()):
        percentage = (count / len(results)) * 100
        print(f"  {depth:<25} {count:>2} queries ({percentage:>5.1f}%)")
    
    print(f"\nPurpose Distribution:")
    for purpose, count in sorted(purposes.items()):
        percentage = (count / len(results)) * 100
        print(f"  {purpose:<25} {count:>2} queries ({percentage:>5.1f}%)")
    
    print(f"\nProfile Distribution:")
    for profile, count in sorted(profiles.items()):
        percentage = (count / len(results)) * 100
        print(f"  {profile:<35} {count:>2} queries ({percentage:>5.1f}%)")
    
    print("\n" + "=" * 140)
    print("MODEL USAGE BY STAGE")
    print("=" * 140)
    print("\nAll queries use the following models:")
    print("  Router:        gpt-5-mini  (fast classification)")
    print("  Clarifier:     gpt-5-mini  (only if clarification needed)")
    print("  Research:      gpt-5.1 or o3-deep-research  (selected by strategy matrix)")
    print("  Writer:        gpt-5.1     (structured generation)")
    print("  Fact Checker:  gpt-5.1     (quality analysis)")


def run_demonstration() -> None:
    """Run the model selection demonstration."""
    
    print("=" * 140)
    print("MODEL SELECTION FLOW DEMONSTRATION")
    print("=" * 140)
    print("\nThis demonstration shows how different queries route through the system")
    print("and which models are selected at each stage.\n")
    
    results = []
    
    for query_data in TEST_QUERIES:
        result = simulate_model_selection_flow(query_data)
        results.append(result)
    
    print_detailed_table(results)
    
    # Save results to JSON
    output_file = "tests/model_selection_demo_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Detailed results saved to {output_file}")


if __name__ == "__main__":
    run_demonstration()

