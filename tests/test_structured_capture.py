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
