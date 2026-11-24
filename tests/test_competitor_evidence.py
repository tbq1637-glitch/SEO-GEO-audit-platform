"""Offline STEP 3 competitor evidence safety tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from competitor_evidence import eligible


def test_google_redirect_is_not_a_competitor():
    ok, reason = eligible("https://www.google.com/goto?url=opaque")
    assert not ok and "redirect" in reason.lower()


def test_normal_competitor_url_is_eligible():
    assert eligible("https://www.mhfa.org.au/webinars")[0]


def test_non_public_or_unsafe_urls_rejected():
    for url in ("http://example.org", "https://127.0.0.1/x",
                "https://localhost/x", "https://example.test/x",
                "https://user:pass@example.org/"):
        assert not eligible(url)[0]

import json
from types import SimpleNamespace
import competitor_evidence as m


def test_blocked_site_does_not_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(m, "public_dns", lambda _: True)
    def blocked(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(status_code=403, headers={"Content-Type": "text/html"},
                               url="https://example.org", close=lambda: None)
    monkeypatch.setattr(m.requests, "get", blocked)
    html, info = m.fetch_html("https://example.org/page")
    assert html is None and info["status"] == "access_blocked"
    assert len(calls) == 1


def test_failed_competitors_do_not_consume_success_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "OUT", tmp_path)
    snapshot = {
        "target_url": "https://target.example.org",
        "groups": [{"id": f"Q{q}", "query": f"test query {q}", "error": None,
                    "results": [
            {"url": f"https://q{q}-site{i}.example.org/page", "position": i,
             "title": str(i)} for i in range(1, 6)
        ]} for q in range(1, 6)],
    }
    (tmp_path / "google_serp.json").write_text(json.dumps(snapshot))
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        if "-site1." in url:
            return None, {"status": "access_blocked", "http_status": 403}
        return "<html><body>" + ("Good page content " * 30) + "</body></html>", {
            "http_status": 200
        }
    monkeypatch.setattr(m, "fetch_html", fetch)
    monkeypatch.setattr(m, "convert_html",
                        lambda html, index: ("Content " * 100, 0, "log.txt"))
    m.main()
    data = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert data["query_sample_count"] == 15
    assert data["successful_pages"] == 15
    assert data["attempted_pages"] == 20
    assert all(q["successes"] == 3 for q in data["per_query"])
    assert data["google_api_requests_by_this_step"] == 0
    assert data["openai_requests_by_this_step"] == 0



def test_same_domain_different_urls_are_not_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "OUT", tmp_path)
    urls = [f"https://learning.example.org/webinar/{x}" for x in (1, 2, 3)]
    groups = [{"id": f"Q{i}", "query": f"question {i}",
               "results": [{"url": url, "position": j}
                           for j, url in enumerate(urls, 1)],
               "error": None} for i in range(1, 6)]
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://target.example.org", "groups": groups
    }))
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return "<html><body>" + ("Useful event details. " * 35) + "</body></html>", {
            "http_status": 200
        }
    monkeypatch.setattr(m, "fetch_html", fetch)
    monkeypatch.setattr(m, "convert_html",
                        lambda html, index: ("Readable text " * 60, 0, "log.txt"))
    m.main()
    audit = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert audit["query_sample_count"] == 3
    assert audit["unique_captured_urls"] == 3
    assert calls == urls
    assert not any(p.get("status") == "duplicate_domain_in_query"
                   for p in audit["pages"])


def test_target_alias_and_redirect_and_global_failure_skip(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "OUT", tmp_path)
    monkeypatch.setenv("AUDIT_URL", "https://www.target.org/event")
    common = "https://competitor.org/article?utm_source=search"
    fail = "https://blocked.org/page"
    redirected = "https://redirect.org/to-target"
    aliases = ["https://target.org/other", "https://news.target.org/page", redirected]
    groups = []
    for q in range(1, 6):
        urls = aliases + [common if q == 1 else "https://www.competitor.org/article/#section", fail]
        urls += [f"https://q{q}-p{i}.org/page" for i in range(1, 5)]
        groups.append({"id": f"Q{q}", "query": str(q), "results": [
            {"url": url, "position": j} for j, url in enumerate(urls, 1)]})
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://www.target.org/event", "groups": groups}))
    calls = []
    def fetch(url, redirect_guard=None):
        calls.append(url)
        if url == redirected:
            dest = "https://target.org/private"
            status = redirect_guard(dest)
            assert status == "target_site_redirect"
            return None, {"status": status, "final_url": dest}
        if url == fail:
            return None, {"status": "access_blocked"}
        return "<html><body>" + "Text " * 100 + "</body></html>", {"http_status": 200}
    monkeypatch.setattr(m, "fetch_html", fetch)
    monkeypatch.setattr(m, "convert_html", lambda *_: ("Text " * 100, 0, "log"))
    m.main()
    data = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert data["query_sample_count"] == data["unique_captured_urls"] == 15
    assert all(q["successes"] == 3 for q in data["per_query"])
    assert calls.count(common) == calls.count(fail) == calls.count(redirected) == 1
    assert not any("target.org" in url for url in calls)
    assert not any("www.competitor.org" in url for url in calls)
    assert any(r["status"] == "target_site_redirect" for r in data["pages"])


def test_redirect_to_attempted_destination_not_fetched(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(m, "public_dns", lambda _: True)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=302, headers={"Location": "https://already.org/page"},
                               close=lambda: None)
    monkeypatch.setattr(m.requests, "get", get)
    html, info = m.fetch_html("https://alias.org/page", redirect_guard=lambda _: "duplicate_url_global")
    assert html is None and info["status"] == "duplicate_url_global"
    assert calls == ["https://alias.org/page"]


def test_page_identity_preserves_content_parameters():
    assert m.page_key("https://www.example.org/a/?utm_medium=x&id=1#section") == m.page_key("https://example.org/a?id=1")
    assert m.page_key("https://example.org/a?id=1") != m.page_key("https://example.org/a?id=2")
    assert m.own_site("https://sites.google.com/view/myevent/about", ["https://sites.google.com/view/myevent"])
    assert not m.own_site("https://sites.google.com/view/other", ["https://sites.google.com/view/myevent"])
