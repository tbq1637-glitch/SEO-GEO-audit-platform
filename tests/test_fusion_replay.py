"""Offline STEP5 archive replay, request budget and diagnostics tests."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fusion_api as api
import fusion_report as report
import validate_fusion_replay as replay


def fake_evidence(root):
    root.mkdir(exist_ok=True)
    target = "https://example.org/webinar/"
    files = {
        "business_profile.json": {"source_url": target, "brand": "Demo"},
        "search_intents.json": {"target": target},
        "google_serp.json": {"target_url": target,
                             "groups": [{"id": "Q" + str(i), "error": None,
                                         "results": []} for i in range(1, 6)]},
        "competitor_evidence.json": {
            "source_snapshot": "google_serp.json",
            "pages": [{"status": "captured", "url": "https://source.org/p",
                       "markdown_file": "competitor_1.md", "query_id": "Q1"}],
            "per_query": [{"id": "Q1", "successes": 1}]},
        "seo.json": {"qualityScores": {"overall": {"score": 9.6}}},
        "geo.json": {"score": 25},
        "step4/siteone_ai_seo.json": {"tables": {}},
    }
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    (root / "siteone_page.md").write_text("# Demo Webinar\nContent.")
    (root / "competitor_1.md").write_text("# Competitor webinar\nDetails.")
    return target


def test_valid_archived_evidence_and_provenance(tmp_path, monkeypatch):
    target = fake_evidence(tmp_path)
    monkeypatch.setenv("EXPECTED_TARGET_URL", target)
    result = replay.verify_local(tmp_path)
    assert result["query_count"] == 5
    assert result["captured_query_samples"] == 1
    assert result["unique_captured_urls"] == 1
    monkeypatch.setenv("EXPECTED_TARGET_URL", "https://other.org/")
    with pytest.raises(RuntimeError, match="differs"):
        replay.verify_local(tmp_path)


def test_missing_archive_input_never_triggers_api(tmp_path):
    fake_evidence(tmp_path)
    (tmp_path / "competitor_1.md").unlink()
    with pytest.raises(RuntimeError, match="Missing archived competitor"):
        replay.verify_local(tmp_path)


def test_siteone_compaction_removes_duplicate_resource_tables_but_keeps_ai():
    source = {"qualityScores": {"overall": {"score": 9.6}},
              "summary": {"items": [{"text": "verified signal"}]},
              "tables": {"seo": {"rows": ["a"]}, "ai-seo": {"rows": ["AI"]},
                         "caching-per-domain": {"rows": list(range(3000))}}}
    a = report.compact_siteone_scan(source)
    b = report.compact_siteone_scan(source, include_ai=True)
    assert "seo" in a["selected_native_tables"]
    assert "ai-seo" not in a["selected_native_tables"]
    assert "ai-seo" in b["selected_native_tables"]
    assert "caching-per-domain" not in b["selected_native_tables"]
    assert a["summary"]["items"][0]["text"] == "verified signal"


def good_reply(body="Evidence-grounded report"):
    return SimpleNamespace(status="completed", incomplete_details=None,
                           output_text=body, usage=SimpleNamespace(
                               input_tokens=4500, output_tokens=2600, total_tokens=7100))


def timeout_error():
    return APITimeoutError(request=httpx.Request("POST",
                                                 "https://api.openai.com/v1/responses"))


class MockClient:
    def __init__(self, responses):
        self.results = iter(responses)
        self.count = 0
        self.responses = self

    def create(self, **kwargs):
        assert kwargs["reasoning"]["effort"] == "high"
        assert 90 <= kwargs["timeout"] <= 420
        self.count += 1
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


def test_fusion_first_timeout_then_success_no_extra_calls(tmp_path):
    client = MockClient([timeout_error(), good_reply()])
    diagnostics = tmp_path / "step5_fusion_diagnostics.json"
    report_text = api.call_fusion(client, "model-for-test", "source-based",
                                  '{"evidence":"test"}', {"x": {"count": 1}},
                                  diagnostics, sleep_fn=lambda _: None)
    assert report_text == "Evidence-grounded report"
    assert client.count == 2
    record = json.loads(diagnostics.read_text())
    assert record["outcome"] == "completed"
    assert record["attempts"][0]["failure_type"] == "APITimeoutError"
    assert record["attempts"][1]["usage"]["input_tokens"] == 4500
    assert "source-based" not in diagnostics.read_text()
    assert '"evidence":"test"' not in diagnostics.read_text()


def test_fusion_two_timeouts_only_two_attempts(tmp_path):
    client = MockClient([timeout_error(), timeout_error(), good_reply()])
    diagnostics = tmp_path / "step5_fusion_diagnostics.json"
    with pytest.raises(APITimeoutError):
        api.call_fusion(client, "test", "prompt", "evidence", {"x": "n"},
                        diagnostics, max_attempts=5, sleep_fn=lambda _: None)
    assert client.count == 2
    record = json.loads(diagnostics.read_text())
    assert record["outcome"] == "failed"
    assert record["attempt_limit"] == 2
    assert len(record["attempts"]) == 2


def test_fusion_incomplete_api_result_is_not_published(tmp_path):
    incomplete = SimpleNamespace(status="incomplete",
                                 incomplete_details=SimpleNamespace(
                                     reason="max_output_tokens"),
                                 output_text="PARTIAL")
    client = MockClient([incomplete, good_reply()])
    diagnostics = tmp_path / "step5_fusion_diagnostics.json"
    with pytest.raises(RuntimeError, match="incomplete"):
        api.call_fusion(client, "test", "system", "body", {}, diagnostics)
    assert client.count == 1
    record = json.loads(diagnostics.read_text())
    assert record["outcome"] == "incomplete"


def test_remote_verification_rejects_wrong_branch(monkeypatch):
    from io import BytesIO
    def fake_urlopen(req, timeout):
        if "/artifacts" in req.full_url:
            return BytesIO(json.dumps({"artifacts": [{
                "name": "seo-geo-audit-26", "size_in_bytes": 10000,
                "expired": False, "id": 100}]}).encode())
        return BytesIO(json.dumps({
            "repository": {"full_name": "owner/repo"},
            "head_branch": "main", "path": ".github/workflows/audit.yml",
            "status": "completed", "conclusion": "failure", "run_number": 26,
        }).encode())
    monkeypatch.setattr(replay, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="V2"):
        replay.verify_remote(42764278546, "owner/repo", "testtoken")
