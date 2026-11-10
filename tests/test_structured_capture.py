"""Offline regression tests for structured SiteOne evidence and conditional recovery."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import structured_capture as c


STATIC = """
<html lang="en"><head><title>Mortgage Services</title>
<meta name="description" content="Home lending and refinance"></head>
<body><main><h1>Mortgage Services</h1>
<h2>Eligibility</h2><p>Applicants should disclose income and existing liabilities.</p>
<h2>Loan Comparison</h2><table><tr><th>Loan type</th><th>Rate</th></tr>
<tr><td>Fixed</td><td>Quoted on request</td></tr></table>
<h2>Questions</h2><h3>How do I apply?</h3>
<p>Contact the broker to discuss the application process.</p>
<a href="/contact">Contact us</a></main></body></html>
"""


def test_preserves_heading_membership_table_and_link():
    got = c.structure(STATIC)
    assert got["browser_recommended"] is False
    sections = {s["heading"]: s for s in got["sections"]}
    assert sections["Eligibility"]["blocks"][0]["text"].startswith("Applicants")
    tab = sections["Loan Comparison"]["blocks"][0]
    assert tab["type"] == "table"
    assert tab["rows"][0] == ["Loan type", "Rate"]
    assert tab["rows"][1] == ["Fixed", "Quoted on request"]
    assert sections["How do I apply?"]["blocks"][0]["text"].startswith("Contact")
    assert any(b.get("href") == "/contact" for b in sections["How do I apply?"]["blocks"])


def test_detects_sparse_javascript_app():
    html = '<html><head><title>App</title></head><body><div id="root"></div>' + (
        '<script src="/bundle.js"></script>') + '</body></html>'
    got = c.structure(html)
    assert got["browser_recommended"] is True
    assert got["browser_reason"] == "sparse_framework_content"


def test_does_not_browser_render_rich_static_page_even_with_scripts():
    html = STATIC.replace("</body>", '<script src="/a.js"></script><script src="/b.js"></script></body>')
    assert not c.structure(html)["browser_recommended"]


def test_captures_target_structure_without_browser(tmp_path, monkeypatch):
    root = tmp_path / "reports"
    root.mkdir()
    target = STATIC
    (root / "target_source.html").write_text(target)
    (root / "siteone_page.md").write_text("# Mortgage Services\n" + "Text " * 200)
    evidence = root / "step3_structure"
    evidence.mkdir()
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "EVIDENCE", evidence)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    c.assess()
    manifest = json.loads((evidence / "manifest.json").read_text())
    assert manifest["target_browser_needed"] is False
    assert manifest["browser_needed"] is False
    assert (evidence / "target_structure.json").is_file()


def test_recover_records_missing_chrome_without_crashing(tmp_path, monkeypatch):
    root = tmp_path / "reports"
    evidence = root / "step3_structure"
    evidence.mkdir(parents=True)
    (evidence / "manifest.json").write_text(json.dumps({
        "pages": [], "target_browser_needed": True, "browser_needed": True
    }))
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "EVIDENCE", evidence)
    monkeypatch.setattr(c.shutil, "which", lambda _: None)
    monkeypatch.delenv("CHROME_PATH", raising=False)
    c.recover()
    data = json.loads((evidence / "manifest.json").read_text())
    assert data["browser_unavailable"]


def test_upstream_markdown_export_error_is_not_mistaken_for_success(tmp_path):
    rendered = tmp_path / "page.md"
    report = tmp_path / "browser.json"
    report.write_text(json.dumps({"summary": {"items": [
        {"aplCode": "MarkdownExporter", "status": "CRITICAL",
         "text": "Markdown export directory not set"}
    ]}}))
    text, errors = c.inspect_siteone_export(rendered, report, 0)
    assert errors and any("directory not set" in e for e in errors)
    assert text == ""


def test_rendered_dom_uses_siteone_export_directory_and_checks_status(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import competitor_evidence
    root = tmp_path / "reports"
    out = root / "step3_structure"
    out.mkdir(parents=True)
    (out / "manifest.json").write_text(json.dumps({
        "pages": [{"stem": "competitor_1", "url": "https://example.org/webinar",
                   "browser_needed": True}],
        "target_browser_needed": False
    }))
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "EVIDENCE", out)
    monkeypatch.setenv("CHROME_PATH", "/fake/chromium")
    monkeypatch.setattr(competitor_evidence, "public_dns", lambda _: True)
    seen = []
    def fake_run(cmd, **kwargs):
        seen.extend(cmd)
        assert any(arg.startswith("--markdown-export-dir=") for arg in cmd)
        assert any(arg.startswith("--markdown-export-single-file=") for arg in cmd)
        (out / "competitor_1_rendered.md").write_text(
            "# Webinar schedule\n" + "Accessible rendered content " * 30)
        (out / "competitor_1_browser.json").write_text(
            json.dumps({"summary": {"items": []}}))
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr(c.subprocess, "run", fake_run)
    c.recover()
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["pages"][0]["browser_status"] == "captured"
    assert manifest["pages"][0]["browser_export_errors"] == []
    assert manifest["pages"][0]["rendered_characters"] > 200



def test_browser_recovery_updates_only_unfilled_query_quota(tmp_path, monkeypatch):
    root = tmp_path / "reports"
    structure_dir = root / "step3_structure"
    structure_dir.mkdir(parents=True)
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "EVIDENCE", structure_dir)
    recovered_text = "# Webinar joining guide\n" + "Confirmed section content " * 30
    (structure_dir / "competitor_4_rendered.md").write_text(recovered_text)
    (structure_dir / "competitor_8_rendered.md").write_text(recovered_text)
    per_query = [
        {"id": "Q1", "query": "one", "successes": 3},
        {"id": "Q2", "query": "two", "successes": 0},
    ]
    pages = [
        {"status": "captured", "query_id": "Q1",
         "url": f"https://one.org/{i}", "markdown_file": f"competitor_{i}.md"}
        for i in range(1, 4)
    ] + [
        {"status": "insufficient_html", "query_id": "Q1",
         "url": "https://one.org/extra", "capture_stem": "competitor_4"},
        {"status": "conversion_failed", "query_id": "Q2",
         "url": "https://two.org/page", "capture_stem": "competitor_8"},
    ]
    (root / "competitor_evidence.json").write_text(json.dumps({
        "pages": pages, "per_query": per_query,
        "max_successful_pages_per_query": 3,
    }))
    manifest = {"pages": [
        {"stem": "competitor_4", "browser_status": "captured",
         "rendered_markdown": str(structure_dir / "competitor_4_rendered.md")},
        {"stem": "competitor_8", "browser_status": "captured",
         "rendered_markdown": str(structure_dir / "competitor_8_rendered.md")},
    ]}
    c.reconcile_rendered_captures(manifest)
    record = json.loads((root / "competitor_evidence.json").read_text())
    assert record["per_query"][0]["successes"] == 3
    assert record["per_query"][1]["successes"] == 1
    assert record["query_sample_count"] == 4
    assert record["pages"][-2]["supplemental_not_in_quota"]
    assert record["pages"][-1]["browser_recovered"]
    assert (root / "competitor_8.md").read_text() == recovered_text
    assert record["pages"][-1]["status"] == "captured"
