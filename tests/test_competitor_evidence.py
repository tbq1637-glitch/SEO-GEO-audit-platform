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
        "groups": [{"query": "test query", "results": [
            {"url": f"https://site{i}.example.org/page", "position": i, "title": str(i)}
            for i in range(1, 6)
        ]}],
    }
    (tmp_path / "google_serp.json").write_text(json.dumps(snapshot))
    calls = []
    def fetch(url):
        calls.append(url)
        if len(calls) == 1:
            return None, {"status": "access_blocked", "http_status": 403}
        return "<html><body>" + ("Good page content " * 30) + "</body></html>", {"http_status": 200}
    monkeypatch.setattr(m, "fetch_html", fetch)
    monkeypatch.setattr(m, "convert_html", lambda html, index: ("Content " * 100, 0, "log.txt"))
    m.main()
    data = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert data["successful_pages"] == 3
    assert data["attempted_pages"] == 4
    assert data["google_api_requests_by_this_step"] == 0
    assert data["openai_requests_by_this_step"] == 0
