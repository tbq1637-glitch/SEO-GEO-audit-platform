"""Offline tests: video metadata, published subtitles and strict media budget."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import video_evidence as v
import competitor_evidence as c


def test_distinct_video_urls_same_host_are_separate_serp_evidence():
    assert v.is_video_result({"url": "https://www.youtube.com/watch?v=AAAA"})
    assert v.is_video_result({"url": "https://www.youtube.com/watch?v=BBBB"})
    assert c.is_video_platform_url("https://youtu.be/aaaa")
    assert not c.is_video_platform_url("https://clinic.example.org/event")


def test_html_video_markup_and_schema_retain_source_links():
    html = """<html><head><meta property="og:video"
     content="https://player.vimeo.com/video/55">
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"VideoObject",
     "name":"Webinar","description":"Explaining wellbeing",
     "uploadDate":"2026-11-01"}</script></head><body>
    <video controls poster="/cover.jpg"><source src="/intro.mp4">
    <track src="/subtitles/en.vtt" kind="captions" srclang="en"></video>
    <iframe src="https://www.youtube.com/embed/Qqq" title="Workshop"></iframe>
    <a href="/subtitles/transcript.txt">Download webinar transcript</a>
    </body></html>"""
    record = v.links_from_html(html, "https://clinic.example.org/event")
    assert record["embed_count"] == 2
    assert record["video_schema"][0]["name"] == "Webinar"
    assert record["metadata"]["og:video"].startswith("https://player.vimeo")
    links = {x["url"] for x in record["caption_links"]}
    assert "https://clinic.example.org/subtitles/en.vtt" in links
    assert "https://clinic.example.org/subtitles/transcript.txt" in links


def prepare_sources(tmp_path, count=5, enough=False):
    html = """<html><head><title>Webinar</title></head><body>
    <main><h1>Webinar</h1>
    <video controls><track kind="subtitles" src="/caption.vtt"></video>
    %s</main></body></html>""" % ("Detailed webinar content. " * 100 if enough else "Short page")
    groups = [{"id": f"Q{i}", "results": [
        {"url": f"https://www.youtube.com/watch?v={i}a",
         "position": 1, "title": f"Recorded webinar {i}",
         "snippet": "Publisher-described educational event"},
        {"url": f"https://www.youtube.com/watch?v={i}b",
         "position": 2, "title": f"Recorded webinar {i} part two",
         "snippet": "Different video"},
    ]} for i in range(1, 6)]
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://target.example.org/event", "groups": groups
    }))
    rows = []
    for i in range(1, count + 1):
        stem = f"competitor_{i}"
        (tmp_path / (stem + "_source.html")).write_text(html)
        rows.append({"query_id": f"Q{i}", "url": f"https://site{i}.org/webinar",
                     "status": "captured", "capture_stem": stem,
                     "final_url": f"https://site{i}.org/webinar"})
    (tmp_path / "competitor_evidence.json").write_text(json.dumps({"pages": rows}))


def test_video_manifest_serp_references_and_transcript_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "ROOT", tmp_path)
    monkeypatch.setattr(v, "OUT", tmp_path / "step3_video")
    prepare_sources(tmp_path)
    urls = []
    def fake_fetch(url):
        urls.append(url)
        return "WEBVTT\n00:00:00.100 --> 00:00:05.000\nA webinar about education.\n" * 5, None
    monkeypatch.setattr(v, "_fetch_published_text", fake_fetch)
    v.main()
    data = json.loads((tmp_path / "step3_video" / "video_manifest.json").read_text())
    assert data["transcripts_attempted"] == 3
    assert data["transcripts_captured"] == 3
    assert len(urls) == 3
    assert all(len(items) == 2 for items in data["query_video_results"].values())
    assert all(not item["content_reviewed"] for items in
               data["query_video_results"].values() for item in items)
    assert len([r for r in data["sources"] if r["transcript_status"] == "captured"]) == 3
    assert (tmp_path / "step3_video" / "VIDEO_EVIDENCE.md").exists()


def test_page_with_substantive_content_does_not_trigger_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "ROOT", tmp_path)
    monkeypatch.setattr(v, "OUT", tmp_path / "step3_video")
    prepare_sources(tmp_path, count=1, enough=True)
    monkeypatch.setattr(v, "_fetch_published_text", lambda _: (_ for _ in ()).throw(
        AssertionError("No transcript download expected")))
    v.main()
    manifest = json.loads((tmp_path / "step3_video" / "video_manifest.json").read_text())
    assert manifest["transcripts_attempted"] == 0
    assert manifest["sources"][0]["transcript_status"] == "page_text_sufficient"


def test_public_text_must_be_safe_url_without_following_redirects(monkeypatch):
    import competitor_evidence as collector
    monkeypatch.setattr(collector, "public_dns", lambda _: False)
    text, error = v._fetch_published_text("https://publisher.example.org/caption.vtt")
    assert text is None and error
    text, error = v._fetch_published_text("https://publisher.example.org/video.mp4")
    assert text is None and error == "not_a_direct_published_text_track"


def test_video_platform_results_do_not_consume_html_capture_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "OUT", tmp_path)
    groups = [{"id": f"Q{i}", "query": f"question {i}", "error": None,
               "results": [
                   {"url": f"https://www.youtube.com/watch?v={i}a", "position": 1},
                   {"url": f"https://www.youtube.com/watch?v={i}b", "position": 2},
                   {"url": f"https://site{i}.org/event1", "position": 3},
                   {"url": f"https://site{i}.org/event2", "position": 4},
                   {"url": f"https://site{i}.org/event3", "position": 5},
               ]} for i in range(1, 6)]
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://target.example.org", "groups": groups
    }))
    called = []
    def fake_get(url):
        called.append(url)
        return "<html><body>" + "Page evidence " * 40 + "</body></html>", {
            "http_status": 200
        }
    monkeypatch.setattr(c, "fetch_html", fake_get)
    monkeypatch.setattr(c, "convert_html", lambda *_: ("Text " * 100, 0, "test.log"))
    c.main()
    result = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert result["query_sample_count"] == 15
    assert result["attempted_pages"] == 15
    assert not any("youtube" in url for url in called)
    assert sum(x["status"] == "video_reference" for x in result["pages"]) == 10
