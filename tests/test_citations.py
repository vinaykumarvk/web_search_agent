from web_search_agent.citations import has_complete_citations, render_citations


def test_render_citations_formats_links(fake_citations):
    rendered = render_citations(fake_citations)
    assert "[Source One](http://example.com/1)" in rendered
    assert rendered.count("-") == len(fake_citations)


def test_has_complete_citations_true_for_valid_render(fake_citations):
    rendered = render_citations(fake_citations)
    assert has_complete_citations(rendered)


def test_has_complete_citations_false_for_missing_link(fake_citations):
    broken = "- Source without link"\
        "\n- [Source Two](http://example.com/2) — Second result"
    assert not has_complete_citations(broken)
