"""Offline tests for bounded selection and visual evidence outcomes."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import visual_evidence as m


def test_selection_prefers_distinct_queries(monkeypatch):
    monkeypatch.setenv("AUDIT_URL", "https://audit.example.org/")
    data = {"pages": [
        {"status": "captured", "url": "https://a.org/x", "query": "Q1", "position": 1},
        {"status": "captured", "url": "https://b.org/x", "query": "Q1", "position": 2},
        {"status": "captured", "url": "https://c.org/x", "query": "Q3", "position": 1},
        {"status": "captured", "url": "https://d.org/x", "query": "Q4", "position": 1},
    ]}
    pages = m.select_pages(data)
    assert len(pages) == 5
    assert pages[0]["kind"] == "target"
    assert set(p["query"] for p in pages[1:]) == {"Q1", "Q3", "Q4"}


def test_selection_does_not_fabricate_uncaptured_competitors(monkeypatch):
    monkeypatch.setenv("AUDIT_URL", "https://audit.example.org/")
    pages = m.select_pages({"pages": [{"status": "access_blocked", "url": "https://a.org"}]})
    assert len(pages) == 1


def test_no_screenshots_means_no_model_call():
    assert m.visual_analysis({"screenshots": {
        "desktop": {"status": "failed"}, "mobile": {"status": "unavailable"}}}) == {
        "status": "not_tested", "reason": "No screenshots captured"
    }


def test_siteone_failure_does_not_fabricate_image(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "OUT", tmp_path)
    def fail(*_args, **_kwargs):
        class P:
            returncode = 1
            stderr = "no browser"
        return P()
    monkeypatch.setattr(m.subprocess, "run", fail)
    item = {"url": "https://example.org", "id": "target"}
    result = m.run_screenshot(item, "desktop")
    assert result["status"] == "failed"
    assert "image" not in result


def test_select_pages_can_provide_four_fallback_candidates(monkeypatch):
    monkeypatch.setenv("AUDIT_URL", "https://audit.example.org/")
    data = {"pages": [
        {"status": "captured", "url": f"https://site{i}.org/p",
         "query": f"Q{i}", "position": i} for i in range(1, 7)
    ]}
    pages = m.select_pages(data)
    assert len(pages) == 5
    assert len({p["url"] for p in pages}) == 5


def test_timeout_with_complete_current_jpg_is_recovered(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(m, "OUT", tmp_path)
    def timed_out(command, **kwargs):
        target_folder = tmp_path / "target" / "desktop"
        target_folder.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1440, 900), "white").save(
            target_folder / "fresh.jpg", quality=95)
        raise m.subprocess.TimeoutExpired(cmd=command, timeout=100,
                                          stderr=b"browser exited late")
    monkeypatch.setattr(m.subprocess, "run", timed_out)
    result = m.run_screenshot({"url": "https://example.org", "id": "target"},
                              "desktop")
    assert result["status"] == "captured"
    assert result["capture_origin"] == "recovered_after_timeout"
    assert result["process_timeout"]
    assert result["image_checks"][0]["valid"]
    assert "browser exited late" in (
        tmp_path / "target" / "desktop" / "siteone.log").read_text()


def test_corrupt_timeout_image_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "OUT", tmp_path)
    def timed_out(command, **kwargs):
        folder = tmp_path / "target" / "mobile"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "broken.jpg").write_bytes(b"garbage" * 1000)
        raise m.subprocess.TimeoutExpired(cmd=command, timeout=100)
    monkeypatch.setattr(m.subprocess, "run", timed_out)
    result = m.run_screenshot({"url": "https://example.org", "id": "target"},
                              "mobile")
    assert result["status"] == "unavailable"
    assert "image" not in result
    assert not result["image_checks"][0]["valid"]


def test_stale_image_cannot_pass_as_new_attempt(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(m, "OUT", tmp_path)
    folder = tmp_path / "target" / "desktop"
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1440, 900), "white").save(folder / "old.jpg", quality=95)
    def fail(*args, **kwargs):
        class P:
            returncode = 1
            stderr = "failure"
            stdout = ""
        return P()
    monkeypatch.setattr(m.subprocess, "run", fail)
    result = m.run_screenshot({"url": "https://example.org", "id": "target"},
                              "desktop")
    assert result["status"] == "failed"
    assert not (folder / "old.jpg").exists()


def test_main_stops_after_two_successful_visual_competitors(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "OUT", tmp_path / "visual")
    monkeypatch.setenv("AUDIT_URL", "https://target.example.org")
    rows = [{"status": "captured", "url": f"https://site{i}.org",
             "query": f"Q{i}"} for i in range(1, 5)]
    (tmp_path / "competitor_evidence.json").write_text(json.dumps({"pages": rows}))
    monkeypatch.setattr(m.shutil, "which", lambda _: "/usr/bin/siteone-crawler")
    monkeypatch.setattr(m, "public_dns", lambda _: True)
    monkeypatch.setattr(m, "run_screenshot",
                        lambda item, viewport: {"status": "captured",
                                                 "image": "/valid/test.jpg"})
    calls = []
    def fake_analysis(item):
        calls.append(item["url"])
        return {"status": "analysed", "file": str(tmp_path / "test.md")}
    (tmp_path / "test.md").write_text("Test observations.")
    monkeypatch.setattr(m, "visual_analysis", fake_analysis)
    m.main()
    info = json.loads((tmp_path / "visual" / "visual_manifest.json").read_text())
    assert info["completed_competitor_visual_samples"] == 2
    assert info["competitor_attempts"] == 2
    assert len(info["pages"]) == 3
    assert len(calls) == 3


def test_main_falls_back_after_failed_visual_review(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "OUT", tmp_path / "visual")
    monkeypatch.setenv("AUDIT_URL", "https://target.example.org")
    rows = [{"status": "captured", "url": f"https://site{i}.org",
             "query": f"Q{i}"} for i in range(1, 6)]
    (tmp_path / "competitor_evidence.json").write_text(json.dumps({"pages": rows}))
    monkeypatch.setattr(m.shutil, "which", lambda _: "/usr/bin/siteone-crawler")
    monkeypatch.setattr(m, "public_dns", lambda _: True)
    monkeypatch.setattr(m, "run_screenshot",
                        lambda item, viewport: {"status": "failed"})
    calls = []
    def not_tested(item):
        calls.append(item["url"])
        return {"status": "not_tested", "reason": "No screenshots captured"}
    monkeypatch.setattr(m, "visual_analysis", not_tested)
    m.main()
    info = json.loads((tmp_path / "visual" / "visual_manifest.json").read_text())
    assert info["competitor_attempts"] == 4
    assert info["completed_competitor_visual_samples"] == 0
    assert len(calls) == 5
