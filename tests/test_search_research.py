
"""Offline tests: MUST NEVER use live OpenAI or SerpApi tokens."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import search_research as m  # noqa: E402


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "REPORTS", tmp_path)
    profile = {
        "brand": "Sample Community Wellness Clinic (fictional demo)",
        "industry": "Community mental health and wellbeing education",
        "business_type": "fictional clinic; no services scheduled",
        "page_type": "Demonstration webinar landing page",
        "page_goal": "Demonstrate a virtual education event; no registrations",
        "source_url": "https://example.test/webinar/",
        "candidate_search_topics": ["UNVERIFIED: online wellbeing webinar"],
    }
    crawl = {
        "url": profile["source_url"], "http_status": "200",
        "markdown_characters": 3100,
        "verdict": "CONTENT CAPTURED - FULL COMPLETENESS NOT PROVEN",
    }
    seo = {"summary": {"items": [{"aplCode": "seo-noindex"}]}}
    for name, data in (("business_profile.json", profile),
                       ("crawl_completeness.json", crawl), ("seo.json", seo)):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    for key in ("OPENAI_API_KEY", "SERPAPI_API_KEY", "GITHUB_STEP_SUMMARY",
                "GOOGLE_QUERY_1", "GOOGLE_QUERY_2", "SEARCH_MODE", "SEARCH_BATCH_ID"):
        monkeypatch.delenv(key, raising=False)
    return tmp_path, monkeypatch


def fake_plan(*_args, **_kwargs):
    return SimpleNamespace(output_parsed=m.SearchPlan(queries=[
        m.QueryCandidate(query="community wellbeing webinar Australia", intent="informational", reason="Related topic"),
        m.QueryCandidate(query="online mental health education webinars", intent="informational", reason="Alternative informational demand"),
        m.QueryCandidate(query="mental health education webinar registration", intent="commercial", reason="Participation intent"),
        m.QueryCandidate(query="community wellness events near Sydney", intent="local", reason="Local relevance"),
        m.QueryCandidate(query="free community wellbeing online session", intent="comparison", reason="Compare options"),
    ]))


def test_plan_never_calls_serpapi(sandbox, monkeypatch):
    out, env = sandbox
    env.setenv("SEARCH_MODE", "plan")
    env.setenv("OPENAI_API_KEY", "dummy-openai-key")
    env.setattr(m, "create_client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=fake_plan)))
    env.setattr(m.requests, "get", lambda *args, **kwargs: pytest.fail("Search API MUST NOT be called in plan mode"))
    m.main()
    plan = json.loads((out / "search_intents.json").read_text())
    assert len(plan["queries"]) == 5
    assert json.loads((out / "SERPAPI_REQUEST_USAGE.json").read_text())["attempted_requests"] == 0
    assert "SerpApi requests made:** 0" in (out / "SEARCH_DISCOVERY.md").read_text()


def test_live_never_more_than_two_calls_and_caches(sandbox, monkeypatch):
    out, env = sandbox
    env.setenv("SEARCH_MODE", "live_2")
    env.setenv("SERPAPI_API_KEY", "secret-key")
    env.setenv("GOOGLE_QUERY_1", "community wellbeing webinar Australia")
    env.setenv("GOOGLE_QUERY_2", "online mental health education webinars")
    count = []

    def one_search(q, key):
        count.append(q)
        assert key == "secret-key"
        return ([{"position": 1, "url": "https://example.org/article", "domain": "example.org",
                 "title": "Sample research", "snippet": "Example content", "role": "unclassified",
                 "role_source": "not examined"}], None)

    env.setattr(m, "search_once", one_search)
    m.main()
    assert len(count) == 2
    data = json.loads((out / "google_serp.json").read_text())
    assert len(data["groups"]) == 2 and data["demo"] is True
    assert data["chatgpt_tested"] is False
    assert json.loads((out / "SERPAPI_REQUEST_USAGE.json").read_text())["attempted_requests"] == 2
    m.main()
    assert len(count) == 2, "Repeat with same batch should read stored snapshot, not call provider"
    usage = json.loads((out / "SERPAPI_REQUEST_USAGE.json").read_text())
    assert usage["cache_reused"] is True and usage["attempted_requests"] == 0


def test_duplicate_query_rejected_before_network(sandbox, monkeypatch):
    out, env = sandbox
    env.setenv("SEARCH_MODE", "live_2")
    env.setenv("SERPAPI_API_KEY", "key")
    env.setenv("GOOGLE_QUERY_1", "community wellbeing webinars")
    env.setenv("GOOGLE_QUERY_2", "COMMUNITY WELLBEING WEBINARS")
    env.setattr(m, "search_once", lambda *_: pytest.fail("No searches allowed"))
    with pytest.raises(RuntimeError, match="Duplicate"):
        m.main()


def test_fictional_location_rejected_before_network(sandbox, monkeypatch):
    _out, env = sandbox
    env.setenv("SEARCH_MODE", "live_2")
    env.setenv("GOOGLE_QUERY_1", "wellbeing webinar in Sampletown")
    env.setenv("SERPAPI_API_KEY", "key")
    env.setattr(m, "search_once", lambda *_: pytest.fail("No searches allowed"))
    with pytest.raises(ValueError, match="fictional"):
        m.main()


def test_crawl_mismatch_fails_closed(sandbox, monkeypatch):
    out, env = sandbox
    crawl = json.loads((out / "crawl_completeness.json").read_text())
    crawl["url"] = "https://wrong.test/"
    (out / "crawl_completeness.json").write_text(json.dumps(crawl))
    env.setenv("SEARCH_MODE", "live_2")
    env.setenv("SERPAPI_API_KEY", "key")
    env.setenv("GOOGLE_QUERY_1", "online community wellbeing events")
    env.setattr(m, "search_once", lambda *_: pytest.fail("No searches allowed"))
    with pytest.raises(RuntimeError, match="different URLs"):
        m.main()


def test_failed_api_does_not_retry(sandbox, monkeypatch):
    out, env = sandbox
    env.setenv("SEARCH_MODE", "live_2")
    env.setenv("SERPAPI_API_KEY", "key")
    env.setenv("GOOGLE_QUERY_1", "online wellbeing lectures")
    env.setenv("GOOGLE_QUERY_2", "mental health community information webinar")
    count = []

    def fail_one(q, key):
        count.append(q)
        return [], "SerpApi HTTP 503"

    env.setattr(m, "search_once", fail_one)
    m.main()
    assert len(count) == 1, "Provider failure should prevent second search"
    assert json.loads((out / "SERPAPI_REQUEST_USAGE.json").read_text())["attempted_requests"] == 1
    assert "SerpApi HTTP 503" in (out / "SEARCH_DISCOVERY.md").read_text()


def test_off_mode_makes_zero_requests(sandbox, monkeypatch):
    _out, env = sandbox
    env.setattr(m.requests, "get", lambda *_a, **_kw: pytest.fail("No network"))
    env.setattr(m, "create_client", lambda: pytest.fail("No model"))
    m.main()


def test_same_batch_different_queries_refused(sandbox, monkeypatch):
    out, env = sandbox
    env.setenv("SEARCH_MODE", "live_2")
    env.setenv("SERPAPI_API_KEY", "key")
    env.setenv("GOOGLE_QUERY_1", "community wellbeing webinar Australia")
    env.setattr(m, "search_once", lambda *_: ([{"position": 1, "url": "https://example.org",
        "domain": "example.org", "title": "Example", "snippet": "Example"}], None))
    m.main()
    env.setenv("GOOGLE_QUERY_1", "different online community wellbeing webinar")
    env.setattr(m, "search_once", lambda *_: pytest.fail("Same batch must not spend another credit"))
    with pytest.raises(RuntimeError, match="already been used"):
        m.main()
