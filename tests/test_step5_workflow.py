"""Offline contract checks: replay mode cannot inadvertently run full paid audit."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/audit.yml"


def test_workflow_yaml_and_input_modes_are_valid():
    config = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    dispatch = (config.get("on") or config.get(True))["workflow_dispatch"]
    inputs = dispatch["inputs"]
    assert inputs["mode"]["default"] == "full"
    assert set(inputs["mode"]["options"]) == {"full", "step5_only"}
    assert inputs["source_run_id"]["default"] == "42764278546"
    assert config["permissions"]["actions"] == "read"


def test_step5_only_skips_all_paid_upstream_scanners():
    config = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = config["jobs"]
    assert "inputs.mode == 'full'" in jobs["audit"]["if"]
    replay = jobs["step5_only"]
    assert "inputs.mode == 'step5_only'" in replay["if"]
    script = "\n".join(step.get("run", "") for step in replay["steps"])
    assert "scripts/validate_fusion_replay.py remote" in script
    assert "scripts/validate_fusion_replay.py local" in script
    assert "scripts/fusion_report.py" in script
    assert "scripts/render_combined_report.py" in script
    assert "scripts/business_identification.py" not in script
    assert "scripts/auto_four_searches.py" not in script
    assert "scripts/visual_evidence.py" not in script
    assert "siteone-crawler" not in script
    assert "geo audit" not in script
    assert "serpapi" not in script.lower()
    assert any("download-artifact" in step.get("uses", "")
               for step in replay["steps"])


def test_replay_requires_target_validation_before_model_call():
    config = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = config["jobs"]["step5_only"]["steps"]
    names = [step["name"] for step in steps if step.get("name")]
    assert names.index("Validate downloaded evidence and record provenance") < (
        names.index("Re-run STEP 5 fusion only with bounded diagnostics"))
    assert any("STEP5_REPLAY_PROVENANCE.json" in str(step)
               for step in steps)
