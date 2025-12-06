from app.strategy import Strategy, select_strategy


def test_selects_strategy_for_profile_and_depth():
    strategy: Strategy = select_strategy("COMPANY_RESEARCH", "standard")
    assert strategy.model == "gpt-5.1"
    assert strategy.max_searches == 4
    assert "web_search" in strategy.tools


def test_falls_back_to_standard_when_missing_combo():
    strategy = select_strategy("COMPANY_RESEARCH", "nonexistent")  # type: ignore[arg-type]
    assert strategy.max_searches == 4
