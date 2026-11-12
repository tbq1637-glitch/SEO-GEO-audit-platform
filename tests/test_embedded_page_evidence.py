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
    assert evidence["source_method"] == "publisher_inline_embedded_html"
    assert evidence["native_scanner_results_unchanged"] is True
    item = evidence["items"][0]
    assert item["h1"] == "Care for Me Webinar"
    assert item["candidate_text_characters"] >= 400
    assert item["links"][0]["href"] == "https://example.org/register"
    assert (tmp_path / "target_embedded_evidence.json").exists()
    assert "not proof" in item["limitations"]


def test_other_host_with_same_real_embedded_html_is_supported(tmp_path):
    result = emb.capture(wrapper(), "https://other.example.org/webinar", tmp_path)
    assert result is not None
    assert result["items"][0]["h1"] == "Care for Me Webinar"


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
    assert "INLINE EMBED" in verdict["verdict"]
    assert verdict["h1"] == ""
    search.validate_evidence({"brand": "Demo", "page_type": "landing_page", "source_url": crawl.URL}, verdict)


def test_semantic_structure_images_faq_speakers_and_schedule(tmp_path):
    internal = """<html><head><style>.section{color:teal}</style></head><body>
    <section id="top" class="hero"><h1>Webinar Topic</h1><p>Free online webinar on Zoom.</p>
    <img alt="Clinic logo" src="data:image/png;base64,AAABBB"></section>
    <section id="speakers"><h2>Speakers</h2><article class="speaker">
      <h3>Dr Example</h3><p>Registered speaker for an event.</p></article></section>
    <section id="programme"><h2>Programme</h2><time>6.00 pm</time>
      <time>7.00 pm</time><p>Talk and Q&amp;A.</p></section>
    <section id="faqs"><h2>FAQ</h2><details open>
    <summary>How can I register?</summary><p>Use the Zoom form.</p></details></section>
    <section id="register"><h2>Register</h2>
    <a href="https://example.org/registration">Register free</a>
    <p>"""+("Additional educational overview content. "*16)+"""</p></section>
    </body></html>"""
    page = '<html><body><div data-code="' + escape(internal, quote=True) + '"></div></body></html>'
    result = emb.capture(page, "https://sites.google.com/view/event", tmp_path)
    assert result is not None
    item = result["items"][0]
    assert [x["id"] for x in item["sections"]] == ["top", "speakers", "programme", "faqs", "register"]
    assert item["sections"][0]["classes"] == ["hero"]
    assert item["faqs"][0]["question"] == "How can I register?"
    assert item["faqs"][0]["initially_open"] is True
    assert item["faqs"][0]["answer"].endswith("Use the Zoom form.")
    assert item["times"] == ["6.00 pm", "7.00 pm"]
    assert item["presenter_cards"][0]["headings"] == ["Dr Example"]
    assert item["images"][0]["alt"] == "Clinic logo"
    assert item["images"][0]["src_kind"] == "inline_data"
    assert item["images"][0]["src_reference"] is None
    assert item["links"][0]["href"] == "https://example.org/registration"
    assert item["source_structure_counts"]["style_blocks"] == 1
    assert item["source_capture_integrity"]["complete_without_configured_truncation"] is True
    assert len(item["visible_candidate_text"]) == item["candidate_text_characters"]


def test_truncated_or_overlimit_page_must_not_claim_complete(tmp_path):
    internal = "<html><body><h1>Long page</h1><p>" + ("Lorem ipsum content. " * 2200) + "</p></body></html>"
    page = '<div data-code="' + escape(internal, quote=True) + '"></div>'
    result = emb.capture(page, "https://sites.google.com/view/overlong", tmp_path)
    assert result is None
    assert not (tmp_path / "target_embedded_evidence.json").exists()


def test_srcdoc_embedded_html_without_following_external_iframe(tmp_path):
    internal = "<html><body><h1>Independent webinar</h1><p>" + ("Event details and timetable. " * 28) + "</p></body></html>"
    page = ('<html><body><iframe srcdoc="' + escape(internal, quote=True) +
            '"></iframe><iframe src="https://other-site.example/private"></iframe></body></html>')
    result = emb.capture(page, "https://events.example.org/current", tmp_path)
    assert result is not None
    assert result["items"][0]["embed_kind"] == "iframe_srcdoc"
    assert result["external_iframes_not_fetched"] is True
    assert "other-site.example" not in str(result)


def test_arbitrary_data_code_not_treated_as_html(tmp_path):
    value = "just a plain analytics blob; " * 35
    page = '<html><body><div data-code="' + value + '"></div></body></html>'
    assert emb.capture(page, "https://events.example.org/current", tmp_path) is None


def test_no_double_count_of_inherited_parent_source(tmp_path):
    page = '<html><body><h1>Native page</h1><p>' + ('Complete details ' * 30) + '</p></body></html>'
    assert emb.capture(page, "https://events.example.org/current", tmp_path) is None
