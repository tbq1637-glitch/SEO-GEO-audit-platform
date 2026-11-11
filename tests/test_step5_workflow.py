"""Offline contract checks for the public URL + scope full audit entry."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/audit.yml"


def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_public_workflow_only_url_and_scope():
    config = workflow()
    dispatch = (config.get("on") or config.get(True))["workflow_dispatch"]
    inputs = dispatch["inputs"]
    assert set(inputs) == {"url", "scope"}
    assert inputs["url"]["required"] is True
    assert set(inputs["scope"]["options"]) == {"landing_page", "website"}
    assert set(config["jobs"]) == {"audit"}
    assert "if" not in config["jobs"]["audit"]
    assert config["permissions"]["contents"] == "read"


def test_full_pipeline_is_preserved_in_order():
    config = workflow()
    steps = config["jobs"]["audit"]["steps"]
    script = "\n".join(str(step.get("run", "")) for step in steps)
    expected = [
        "scripts/business_identification.py",
        "geo audit",
        "scripts/auto_four_searches.py",
        "scripts/competitor_evidence.py",
        "scripts/structured_capture.py assess",
        "scripts/video_evidence.py",
        "scripts/geo_extended_diagnostics.py",
        "scripts/visual_evidence.py",
        "scripts/fusion_report.py",
        "scripts/render_combined_report.py",
    ]
    for item in expected:
        assert item in script
    assert "siteone-crawler" in script
    positions = [script.index(item) for item in expected]
    assert positions == sorted(positions)
    assert any("upload-artifact" in str(step.get("uses", "")) for step in steps)
    assert "validate_fusion_replay.py" not in script
    assert "source_run_id" not in WORKFLOW.read_text(encoding="utf-8")
    assert "step5_only" not in WORKFLOW.read_text(encoding="utf-8")
