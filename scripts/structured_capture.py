"""Preserve on-page structure and selectively recover JS-rendered content with SiteOne.

Modes:
  assess: write structured HTML evidence and browser-need decision (no browser/AI)
  recover: run SiteOne in Chromium only on pages flagged by assess (no screenshots/AI)
"""
import json
import os
import re
import subprocess
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag

ROOT = Path("reports")
EVIDENCE = ROOT / "step3_structure"
EVIDENCE.mkdir(parents=True, exist_ok=True)
LIMIT = 30
EXCERPT = 1800


def normalize(x):
    return re.sub(r"\s+", " ", x or "").strip()


def structure(html):
    soup = BeautifulSoup(html, "html.parser")
    title = normalize(soup.title.get_text(" ", strip=True)) if soup.title else ""
    metas = {str(t.get("name", "")).lower(): str(t.get("content", ""))
             for t in soup.select("meta[name][content]")[:50]}
    schemas = [normalize(t.string or t.get_text())[:6000]
               for t in soup.select('script[type="application/ld+json"]')[:12]]
    # Preserve document order, section ownership and table row/column positions.
    for tag in soup.select("script,style,noscript,svg"):
        tag.decompose()
    container = soup.select_one("main") or soup.body or soup
    sections = []
    current = {"heading": "Page introduction", "level": 0, "blocks": []}
    sections.append(current)
    for node in container.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading = normalize(node.get_text(" ", strip=True))
            if heading:
                current = {"heading": heading, "level": int(node.name[1]), "blocks": []}
                sections.append(current)
            continue
        if node.name not in ("p", "li", "table", "a", "button"):
            continue
        if node.find_parent(["p", "li", "table", "a", "button"]):
            continue
        if node.name == "table":
            rows = [[normalize(cell.get_text(" ", strip=True))
                     for cell in row.find_all(["th", "td"], recursive=False)]
                    for row in node.find_all("tr")[:60]]
            if rows:
                current["blocks"].append({"type": "table", "rows": rows})
        else:
            txt = normalize(node.get_text(" ", strip=True))
            if txt:
                item = {"type": node.name, "text": txt[:EXCERPT]}
                if node.name == "a":
                    item["href"] = str(node.get("href", ""))[:500]
                current["blocks"].append(item)
    # Never claim complete just because extraction returned non-empty text.
    raw_visible = normalize(container.get_text(" ", strip=True))
    framework = bool(re.search(r"(__NEXT_DATA__|__NUXT__|ng-version|data-reactroot|id=[\"'](?:root|app)[\"']|vite|webpack)", html, re.I))
    script_count = len(BeautifulSoup(html, "html.parser").select("script[src]"))
    meaningful = len(raw_visible)
    placeholders = bool(re.search(r"enable javascript to run|please enable javascript|loading\.{2,}|just a moment", raw_visible[:1000], re.I))
    needs_browser = placeholders or (framework and meaningful < 1600) or (script_count >= 5 and meaningful < 450)
    return {
        "title": title, "meta": metas, "schema_excerpts": schemas,
        "sections": sections[:250], "section_count": len(sections),
        "visible_text_characters": meaningful, "framework_signals": framework,
        "external_script_count": script_count, "javascript_placeholder": placeholders,
        "browser_recommended": needs_browser,
        "browser_reason": "js_placeholder" if placeholders else "sparse_framework_content" if framework and meaningful < 1600 else "sparse_script_heavy_content" if needs_browser else "static_content_available",
        "limitations": ["HTML section ownership is approximated by document-order headings; complex nested cards may need human review",
                        "Screenshots and visual hierarchy are not inferred from Markdown"]
    }


def pages():
    p = ROOT / "competitor_evidence.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    seen_stems = set()
    for row in data.get("pages", []):
        if row.get("status") not in ("captured", "insufficient_html", "conversion_failed"):
            continue
        stem = row.get("capture_stem", "")
        if re.fullmatch(r"competitor_[0-9]+", stem) and stem not in seen_stems:
            seen_stems.add(stem)
            yield row, stem


def assess():
    manifest = {"version": 1, "pages": [], "browser_needed": False, "mode": "conditional"}
    for row, stem in pages():
        raw = ROOT / (stem + "_source.html")
        if not raw.is_file():
            manifest["pages"].append({"stem": stem, "status": "missing_html"})
            continue
        extracted = structure(raw.read_text(encoding="utf-8", errors="replace"))
        evidence_file = EVIDENCE / (stem + "_structure.json")
        evidence_file.write_text(json.dumps(extracted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        browser_needed = extracted["browser_recommended"] or row.get("status") != "captured"
        rec = {"stem": stem, "url": row.get("final_url", row["url"]), "source": str(evidence_file),
               "static_status": row["status"], "browser_needed": browser_needed,
               "reason": extracted["browser_reason"] if extracted["browser_recommended"] else
                         ("static_conversion_incomplete" if browser_needed else "static_content_available"),
               "status": "static_extracted"}
        manifest["pages"].append(rec)
        manifest["browser_needed"] = manifest["browser_needed"] or rec["browser_needed"]
    # Target page: existing SiteOne content extraction remains the authority.
    raw_target = ROOT / "target_source.html"
    target_source = ROOT / "siteone_page.md"
    if raw_target.exists():
        target_structure = structure(raw_target.read_text(encoding="utf-8", errors="replace"))
        (EVIDENCE / "target_structure.json").write_text(
            json.dumps(target_structure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest["target_browser_needed"] = target_structure["browser_recommended"]
    else:
        manifest["target_browser_needed"] = not target_source.exists()
    if target_source.exists() and len(target_source.read_text(encoding="utf-8", errors="replace").strip()) < 600:
        manifest["target_browser_needed"] = True
    # A successful STEP 1 SiteOne preflight already rendered this target.
    # Do not fetch it a second time merely because the original HTML was sparse.
    prior_rendered = EVIDENCE / "target_rendered.md"
    if prior_rendered.is_file() and len(prior_rendered.read_text(
            encoding="utf-8", errors="replace").strip()) >= 400:
        manifest["target_preferred_for_analysis"] = str(prior_rendered)
        manifest["target_browser_reused"] = True
        manifest["target_browser_needed"] = False
    manifest["browser_needed"] = manifest["browser_needed"] or manifest["target_browser_needed"]
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("browser_needed=" + str(manifest["browser_needed"]).lower() + "\n")
    print(f"Structured evidence: {len(manifest['pages'])} captured pages; browser needed: {manifest['browser_needed']}")


def inspect_siteone_export(out, report_file, exit_code):
    """An exit code of zero is not proof that MarkdownExporter succeeded."""
    problems = []
    if report_file.is_file():
        try:
            details = json.loads(report_file.read_text(encoding="utf-8"))
            for record in details.get("summary", {}).get("items", []):
                if str(record.get("aplCode", "")).lower() == "markdownexporter":
                    problems.append(str(record.get("text", ""))[:1000])
        except (ValueError, OSError, TypeError) as exc:
            problems.append("Invalid SiteOne JSON: " + type(exc).__name__)
    else:
        problems.append("SiteOne JSON missing")
    body = out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""
    lowered = body[:1600].lower()
    if any(flag in lowered for flag in (
        "please log in to continue", "login to facebook",
        "this browser is no longer supported", "please update your browser",
    )):
        problems.append("Possible access or browser compatibility page")
    if exit_code != 0:
        problems.append("SiteOne exited with code " + str(exit_code))
    if len(body.strip()) < 200:
        problems.append("No substantive rendered Markdown produced")
    return body, problems


def recover():
    path = EVIDENCE / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    chrome = os.getenv("CHROME_PATH", "") or next(
        (shutil.which(name) for name in ("google-chrome", "chromium", "chromium-browser")
         if shutil.which(name)), "")
    if not chrome:
        manifest["browser_unavailable"] = "No Chromium executable in runner"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print("Dynamic recovery unavailable: no Chromium installed")
        return
    candidates = [rec for rec in manifest["pages"] if rec.get("browser_needed")]
    if manifest.get("target_browser_needed"):
        candidates.append({"stem": "target", "url": os.environ["AUDIT_URL"]})
    # Revalidate URLs before handing them to a browser-capable crawler.
    # Do not browser-fetch unsafe or non-public competitor hosts.
    from competitor_evidence import eligible, public_dns
    for rec in candidates[:6]:
        if rec["stem"] != "target":
            ok, why = eligible(rec["url"])
            if not ok or not public_dns(rec["url"]):
                rec["browser_status"] = "skipped_unsafe_url"
                rec["browser_error"] = why or "Non-public DNS resolution"
                continue
        stem = rec["stem"]
        out = EVIDENCE / (stem + "_rendered.md")
        report_file = EVIDENCE / (stem + "_browser.json")
        export_dir = EVIDENCE / (stem + "_export")
        export_dir.mkdir(parents=True, exist_ok=True)
        log = EVIDENCE / (stem + "_browser.log")
        out.unlink(missing_ok=True)
        cmd = ["siteone-crawler", "--url=" + rec["url"], "--single-page",
               "--browser", "--browser-path=" + chrome,
               "--browser-wait=networkidle", "--browser-timeout=35",
               "--browser-workers=1", "--workers=1", "--max-reqs-per-sec=1",
               "--markdown-export-dir=" + str(export_dir),
               "--markdown-export-single-file=" + str(out),
               "--output-json-file=" + str(report_file)]
        started = time.monotonic()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=110, check=False)
            body, problems = inspect_siteone_export(out, report_file, p.returncode)
            rec["browser_status"] = "captured" if not problems else "failed"
            rec["browser_elapsed_seconds"] = round(time.monotonic() - started, 2)
            rec["rendered_characters"] = len(body)
            rec["browser_export_errors"] = problems
            rec["rendered_markdown"] = str(out) if not problems else None
            log.write_text(
                "returncode=" + str(p.returncode) + "\n"
                + "export_errors=" + json.dumps(problems) + "\n"
                + p.stderr[-6000:] + "\n", encoding="utf-8")
            base_file = ROOT / (stem + ".md") if stem != "target" else ROOT / "siteone_page.md"
            static_size = len(base_file.read_text(
                encoding="utf-8", errors="replace")) if base_file.exists() else 0
            rec["static_markdown_characters"] = static_size
            rec["content_gain_chars"] = len(body) - static_size if not problems else None
            rec["preferred_for_analysis"] = (str(out) if not problems and len(body) > static_size
                                              else str(base_file))
            if stem == "target":
                manifest["target_preferred_for_analysis"] = rec["preferred_for_analysis"]
        except (OSError, subprocess.TimeoutExpired) as exc:
            rec["browser_status"] = "failed"
            rec["browser_error"] = type(exc).__name__
            rec["browser_elapsed_seconds"] = round(time.monotonic() - started, 2)
            log.write_text(type(exc).__name__ + "\n", encoding="utf-8")
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Conditional rendering complete; screenshots remain disabled.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in ("assess", "recover"):
        raise SystemExit("Usage: structured_capture.py assess|recover")
    {"assess": assess, "recover": recover}[sys.argv[1]]()
