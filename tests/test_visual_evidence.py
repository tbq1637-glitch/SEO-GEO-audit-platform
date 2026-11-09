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
    assert len(pages) == 3
    assert pages[0]["kind"] == "target"
    assert set(p["query"] for p in pages[1:]) == {"Q1", "Q3"}


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
