"""Offline tests for opt-in Google Sites custom embed evidence.

No network, OpenAI, SerpApi, or upstream scanner calls.
"""
import json
import sys
from pathlib import Path
from html import escape
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import embedded_page_evidence as emb
import crawl_completeness_audit as crawl
import search_research as search


def wrapper(host="sites.google.com", hidden=True):
    internal = ('<!doctype html><html><body><h1>Care for Me Webinar</h1>'
                '<main><p>' + ('Online free mental health webinar. ' * 20)
                + '</p><a href="https://example.org/register">Register</a>'
                '</main></body></html>')
    return '<html><head><title>Webinar</title></head><body><div data-code="' + escape(internal, quote=True) + '"></div></body></html>'


def test_google_sites_embedded_html_is_labelled_and_available(tmp_path):
    evidence = emb.capture(wrapper(), "https://sites.google.com/view/webinar", tmp_path)
    assert evidence["source_method"] == "google_sites_custom_html_attribute"
    assert evidence["native_scanner_results_unchanged"] is True
    item = evidence["items"][0]
    assert item["h1"] == "Care for Me Webinar"
    assert item["candidate_text_characters"] >= 400
    assert item["links"][0]["href"] == "https://example.org/register"
    assert (tmp_path / "target_embedded_evidence.json").exists()
    assert "not proof" in item["limitations"]


def test_other_sites_never_use_this_recovery(tmp_path):
    assert emb.capture(wrapper(), "https://other.example.org/webinar", tmp_path) is None
    assert not (tmp_path / "target_embedded_evidence.json").exists()


def test_missing_or_short_embeds_are_not_promoted(tmp_path):
    raw = '<html><body><div data-code="&lt;h1&gt;Short&lt;/h1&gt;"></div></body></html>'
    assert emb.capture(raw, "https://sites.google.com/view/test", tmp_path) is None


def test_completeness_accepts_only_separately_labelled_embedded_source(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl, "OUT", tmp_path)
    monkeypatch.setattr(crawl, "URL", "https://sites.google.com/view/webinar")
    (tmp_path / "seo.json").write_text(json.dumps({
        "results": [{"type": 1, "url": crawl.URL, "status": 200, "size": 900}],
        "tables": {"seo": {"rows": [{
            "urlPathAndQuery": "/view/webinar", "title": "Webinar", "h1": ""
        }]}}
    }))
    (tmp_path / "siteone_page.md").write_text("Outer wrapper only " * 30)
    evidence = emb.capture(wrapper(), crawl.URL, tmp_path)
    assert evidence
    crawl.main()
    verdict = json.loads((tmp_path / "crawl_completeness.json").read_text())
    assert verdict["embedded_source_valid"] is True
    assert verdict["embedded_is_not_native_crawler_content"] is True
    assert "GOOGLE SITES EMBED" in verdict["verdict"]
    assert verdict["h1"] == ""
    search.validate_evidence({"brand": "Demo", "page_type": "landing_page"}, verdict)
