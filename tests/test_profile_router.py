from app.agents.profile_router import ProfileDecision, classify_web_profile


def test_classifies_brd_and_respects_depth_hint():
    decision: ProfileDecision = classify_web_profile(
        "Write a BRD for a new payments API",
        purpose_hint="brd",
        depth_hint="standard",
    )
    assert decision.profile == "BRD_MODELING"
    assert decision.depth == "standard"
    assert decision.need_deep_research is False


def test_classifies_company_research_and_deep_request():
    decision = classify_web_profile("Do a deep company research note on ACME Corp", purpose_hint=None, depth_hint=None)
    assert decision.profile == "COMPANY_RESEARCH"
    assert decision.depth == "deep"
    assert decision.need_deep_research is True


def test_classifies_definition_as_quick():
    decision = classify_web_profile("What is XIRR?")
    assert decision.profile == "DEFINITION_OR_SIMPLE_QUERY"
    assert decision.depth == "quick"
    assert decision.need_deep_research is False


def test_classifies_market_trend():
    decision = classify_web_profile("Market trend analysis for digital advisory in India", depth_hint="standard")
    assert decision.profile == "MARKET_OR_TREND_QUERY"
    assert decision.depth == "standard"
    assert decision.need_deep_research is False
