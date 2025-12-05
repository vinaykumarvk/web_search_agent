from web_search_agent.router import route_request


def test_routes_by_keyword(sample_queries):
    decision = route_request(sample_queries["brd"])
    assert decision.purpose == "brd"
    assert decision.depth == "standard"

    decision = route_request(sample_queries["company"])
    assert decision.purpose == "company_research"

    decision = route_request(sample_queries["market"], depth_hint="deep")
    assert decision.purpose == "market_query"
    assert decision.depth == "deep"


def test_respects_hints_override():
    decision = route_request("random text", purpose_hint="custom", depth_hint="quick")
    assert decision.purpose == "custom"
    assert decision.depth == "quick"
