"""Test suite demonstrating model selection across different query types."""
from __future__ import annotations

import json
from typing import Dict, List

from app.agents.llm_router import LLMRouterAgent
from app.agents.profile_router import classify_web_profile
from app.orchestrator import NormalizedRequest
from app.schemas import ResearchControls, Purpose, Depth
from app.strategy import select_strategy
from app.observability import MetricsEmitter


# Test queries covering different scenarios
TEST_QUERIES = [
    {
        "id": 1,
        "query": "What is artificial intelligence?",
        "description": "Simple definition query - quick answer",
        "expected_purpose": "market_query",
        "expected_depth": "quick",
    },
    {
        "id": 2,
        "query": "Write a comprehensive Business Requirements Document for a mobile banking application",
        "description": "BRD request - deep research needed",
        "expected_purpose": "brd",
        "expected_depth": "deep",
    },
    {
        "id": 3,
        "query": "Research Apple Inc. company overview and recent financial performance",
        "description": "Company research - standard depth",
        "expected_purpose": "company_research",
        "expected_depth": "standard",
    },
    {
        "id": 4,
        "query": "Compare TAM vs SAM vs SOM in market sizing",
        "description": "Market query - quick comparison",
        "expected_purpose": "market_query",
        "expected_depth": "quick",
    },
    {
        "id": 5,
        "query": "Elaborate requirements for a user authentication feature into epics and user stories",
        "description": "Requirement elaboration - standard depth",
        "expected_purpose": "req_elaboration",
        "expected_depth": "standard",
    },
    {
        "id": 6,
        "query": "Deep dive analysis of Tesla's autonomous driving strategy and competitive positioning",
        "description": "Company research - deep analysis",
        "expected_purpose": "company_research",
        "expected_depth": "deep",
    },
    {
        "id": 7,
        "query": "Create a BRD for implementing two-factor authentication",
        "description": "BRD request - standard depth",
        "expected_purpose": "brd",
        "expected_depth": "standard",
    },
    {
        "id": 8,
        "query": "What are the latest trends in cloud computing?",
        "description": "Market trend query - standard depth",
        "expected_purpose": "market_query",
        "expected_depth": "standard",
    },
    {
        "id": 9,
        "query": "Break down the requirement for a payment gateway integration",
        "description": "Requirement elaboration - quick breakdown",
        "expected_purpose": "req_elaboration",
        "expected_depth": "quick",
    },
    {
        "id": 10,
        "query": "I need a comprehensive document outlining what we should build for a customer portal",
        "description": "Ambiguous query - should detect BRD intent",
        "expected_purpose": "brd",
        "expected_depth": "deep",
    },
]


def get_model_selection_flow(query: Dict) -> Dict:
    """Trace model selection through the entire pipeline."""
    
    # Initialize router
    router = LLMRouterAgent(metrics_emitter=MetricsEmitter())
    
    # Create request
    request = NormalizedRequest(
        query=query["query"],
        metadata={"controls": ResearchControls(purpose=Purpose.CUSTOM, depth=Depth.QUICK)}
    )
    
    # Stage 1: Router classification
    try:
        router_decision = router.classify(request)
    except Exception as e:
        # Fallback to heuristic if LLM unavailable
        from app.runtime import HeuristicRouter
        heuristic_router = HeuristicRouter()
        router_decision = heuristic_router.classify(request)
    
    # Stage 2: Profile determination (if not already set)
    if not router_decision.profile:
        profile_decision = classify_web_profile(
            query["query"],
            purpose_hint=router_decision.purpose,
            depth_hint=router_decision.depth,
        )
        profile = profile_decision.profile
    else:
        profile = router_decision.profile
    
    # Stage 3: Strategy selection
    strategy = select_strategy(profile or "DEFINITION_OR_SIMPLE_QUERY", router_decision.depth)
    
    # Stage 4: Determine all models used
    models_used = {
        "router": "gpt-5-mini",  # Router model
        "clarifier": "gpt-5-mini" if router_decision.needs_clarification else None,
        "research": strategy.model,
        "writer": "gpt-5.1",  # Writer always uses GPT-5.1
        "fact_checker": "gpt-5.1",  # Fact checker always uses GPT-5.1
    }
    
    return {
        "query": query["query"],
        "description": query["description"],
        "router_decision": {
            "purpose": router_decision.purpose,
            "depth": router_decision.depth,
            "profile": profile,
            "needs_clarification": router_decision.needs_clarification,
        },
        "strategy": {
            "model": strategy.model,
            "effort": strategy.effort,
            "max_searches": strategy.max_searches,
            "recency_bias": strategy.recency_bias,
        },
        "models_used": models_used,
    }


def print_model_selection_table(results: List[Dict]) -> None:
    """Print a formatted table showing model selection."""
    
    print("\n" + "=" * 120)
    print("MODEL SELECTION TEST RESULTS")
    print("=" * 120)
    
    for result in results:
        print(f"\n{'─' * 120}")
        print(f"Query #{result['query_id']}: {result['query']}")
        print(f"Description: {result['description']}")
        print(f"\nRouter Decision (GPT-5-mini):")
        print(f"  Purpose: {result['router_decision']['purpose']}")
        print(f"  Depth: {result['router_decision']['depth']}")
        print(f"  Profile: {result['router_decision']['profile']}")
        print(f"  Needs Clarification: {result['router_decision']['needs_clarification']}")
        
        print(f"\nStrategy Selection:")
        print(f"  Research Model: {result['strategy']['model']}")
        print(f"  Effort: {result['strategy']['effort']}")
        print(f"  Max Searches: {result['strategy']['max_searches']}")
        print(f"  Recency Bias: {result['strategy']['recency_bias']}")
        
        print(f"\nModels Used at Each Stage:")
        print(f"  Router: {result['models_used']['router']}")
        if result['models_used']['clarifier']:
            print(f"  Clarifier: {result['models_used']['clarifier']}")
        print(f"  Research: {result['models_used']['research']}")
        print(f"  Writer: {result['models_used']['writer']}")
        print(f"  Fact Checker: {result['models_used']['fact_checker']}")
    
    print("\n" + "=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)
    
    # Count model usage
    research_models = {}
    depths = {}
    purposes = {}
    
    for result in results:
        research_model = result['models_used']['research']
        research_models[research_model] = research_models.get(research_model, 0) + 1
        
        depth = result['router_decision']['depth']
        depths[depth] = depths.get(depth, 0) + 1
        
        purpose = result['router_decision']['purpose']
        purposes[purpose] = purposes.get(purpose, 0) + 1
    
    print(f"\nResearch Model Distribution:")
    for model, count in sorted(research_models.items()):
        print(f"  {model}: {count} queries")
    
    print(f"\nDepth Distribution:")
    for depth, count in sorted(depths.items()):
        print(f"  {depth}: {count} queries")
    
    print(f"\nPurpose Distribution:")
    for purpose, count in sorted(purposes.items()):
        print(f"  {purpose}: {count} queries")


def run_model_selection_tests() -> None:
    """Run all test queries and display results."""
    
    print("Running Model Selection Tests...")
    print(f"Testing {len(TEST_QUERIES)} queries\n")
    
    results = []
    
    for query_data in TEST_QUERIES:
        print(f"Processing Query #{query_data['id']}: {query_data['query'][:60]}...")
        
        try:
            result = get_model_selection_flow(query_data)
            result['query_id'] = query_data['id']
            results.append(result)
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    print_model_selection_table(results)
    
    # Save results to JSON
    output_file = "tests/model_selection_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to {output_file}")


if __name__ == "__main__":
    run_model_selection_tests()

