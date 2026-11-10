"""Selective, evidence-grounded screenshot review using native SiteOne browser mode.

Default sample: the target page and up to two captured competitor URLs from
different queries. Two viewports per selected URL; never crawl entire sites.
Screenshots go to the artifact; a vision-capable AI examines them, separately
from SiteOne and GEO technical scores. Failures are recorded, not concealed.
"""
import base64
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from competitor_evidence import eligible, public_dns

ROOT = Path("reports")
OUT = ROOT / "step4" / "visual"
OUT.mkdir(parents=True, exist_ok=True)
MAX_COMPETITORS = 2
MAX_SCREENSHOTS = 6


def select_pages(snapshot):
    """Choose distinct query samples, not necessarily direct competitors."""
    selected = [{"kind": "target", "id": "target", "url": os.environ["AUDIT_URL"],
                 "query": None, "position": None}]
    rows = [r for r in snapshot.get("pages", []) if r.get("status") == "captured"]
    # First prioritize different search intents; then fill from remaining rows.
    seen_queries, seen_urls = set(), set()
    for row in rows:
        q = row.get("query", "")
        url = row.get("final_url") or row.get("url", "")
        if q in seen_queries or url in seen_urls:
            continue
        if len(selected) > MAX_COMPETITORS:
            break
        seen_queries.add(q)
        seen_urls.add(url)
        selected.append({"kind": "competitor", "id": "competitor_" + str(len(selected)),
                         "url": url, "query": q, "position": row.get("position")})
    if len(selected) <= MAX_COMPETITORS:
        for row in rows:
            url = row.get("final_url") or row.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            selected.append({"kind": "competitor", "id": "competitor_" + str(len(selected)),
                             "url": url, "query": row.get("query"),
                             "position": row.get("position")})
            if len(selected) > MAX_COMPETITORS:
                break
    return selected


def run_screenshot(item, viewport):
    folder = OUT / item["id"] / viewport
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "siteone.log"
    # Fixed viewport dimensions work with pinned SiteOne 2.5.1.
    dimensions = {"desktop": "1440x900", "mobile": "390x844"}[viewport]
    cmd = ["siteone-crawler", "--url=" + item["url"], "--single-page",
           "--workers=1", "--max-reqs-per-sec=1", "--browser",
           "--browser-wait=networkidle", "--browser-timeout=35",
           "--browser-workers=1", "--screenshots",
           "--screenshots-dir=" + str(folder),
           "--screenshot-viewport=" + dimensions,
           "--screenshot-mode=full-page", "--screenshot-format=jpg",
           "--screenshot-quality=65",
           "--output-json-file=" + str(folder / "browser.json")]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=100, check=False)
        log.write_text("exit_code=" + str(proc.returncode) + "\n"
                       + proc.stderr[-6000:] + "\n", encoding="utf-8")
        matches = sorted(p for p in folder.rglob("*.jpg") if p.is_file())
        if proc.returncode != 0 or not matches:
            return {"status": "failed", "exit_code": proc.returncode, "log": str(log)}
        return {"status": "captured", "image": str(matches[0]),
                "viewport": viewport, "log": str(log)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write_text(type(exc).__name__ + "\n", encoding="utf-8")
        return {"status": "unavailable", "reason": type(exc).__name__, "log": str(log)}


def visual_analysis(item):
    files = [r["image"] for r in item["screenshots"].values()
             if r["status"] == "captured"]
    if not files:
        return {"status": "not_tested", "reason": "No screenshots captured"}
    api = os.getenv("OPENAI_API_KEY")
    if not api:
        return {"status": "not_tested", "reason": "Missing OpenAI API key"}

    # Resize very tall pages before the AI call; preserve raw screenshot.
    from PIL import Image
    from io import BytesIO
    inputs = [{"type": "input_text", "text": (
        "Evaluate only visually observable layout and mobile usability for "
        "this actual page. Distinguish observations from speculative impact. "
        "Discuss above-the-fold clarity, heading hierarchy, reading flow, "
        "navigation, content sections, prominent calls-to-action, mobile "
        "overflow and accessibility concerns visible in these screenshots. "
        "Do not infer ranking or real AI citation. A screenshot does not prove "
        "interactive controls work. The page may be truncated/downscaled. "
        "Return concise English observations, strengths, weaknesses, and "
        "specific improvements, each with the applicable viewport."
    )}]
    for name, record in item["screenshots"].items():
        if record.get("status") != "captured":
            continue
        with Image.open(record["image"]) as picture:
            picture = picture.convert("RGB")
            picture.thumbnail((1500, 4200))
            buffer = BytesIO()
            picture.save(buffer, format="JPEG", quality=67, optimize=True)
            raw = buffer.getvalue()
        if len(raw) > 3_000_000:
            continue
        inputs.append({"type": "input_text", "text": "Viewport: " + name})
        inputs.append({"type": "input_image", "image_url":
                       "data:image/jpeg;base64," + base64.b64encode(raw).decode()})
    if not any(i["type"] == "input_image" for i in inputs):
        return {"status": "not_tested", "reason": "Images too large for bounded analysis"}
    try:
        from openai import OpenAI
        res = OpenAI(timeout=150, max_retries=0).responses.create(
            model=os.getenv("VISUAL_AUDIT_MODEL", "gpt-5-mini"),
            input=[{"role": "user", "content": inputs}],
            max_output_tokens=3000,
        )
        report = (res.output_text or "").strip()
        usage = getattr(res, "usage", None)
        usage_data = {"input_tokens": getattr(usage, "input_tokens", None),
                      "output_tokens": getattr(usage, "output_tokens", None)}
        response_status = getattr(res, "status", None)
        incomplete_details = getattr(res, "incomplete_details", None)
        reason = getattr(incomplete_details, "reason", None)
        details = {"response_status": response_status,
                   "incomplete_reason": reason, "usage": usage_data,
                   "model": os.getenv("VISUAL_AUDIT_MODEL", "gpt-5-mini")}
        if response_status != "completed" or incomplete_details is not None:
            # Keep partial evidence for diagnosis, but do not send it to STEP 5
            # as if the visual review were complete.
            if report:
                partial = OUT / (item["id"] + "_visual_review_PARTIAL.md")
                partial.write_text(report + "\n", encoding="utf-8")
                details["partial_file"] = str(partial)
            return {"status": "incomplete", **details}
        if not report:
            return {"status": "failed", "reason": "empty_model_output", **details}
        name = item["id"] + "_visual_review.md"
        (OUT / name).write_text(report + "\n", encoding="utf-8")
        return {"status": "analysed", "file": str(OUT / name), **details}
    except Exception as exc:
        return {"status": "failed", "reason": type(exc).__name__}


def main():
    data_path = ROOT / "competitor_evidence.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    selected = select_pages(data)
    log = {"source": "SiteOne full-page screenshots and optional OpenAI vision",
           "policy": "target plus two observed competitor pages; query diversity preferred",
           "not_a_ranking_measurement": True, "max_pages": 3,
           "max_screenshots": MAX_SCREENSHOTS, "pages": []}
    if not shutil.which("siteone-crawler"):
        log["reason"] = "SiteOne unavailable"
        selected = []
    for item in selected:
        if item["kind"] != "target":
            safe, why = eligible(item["url"])
            if not safe or not public_dns(item["url"]):
                item["visual"] = {"status": "skipped", "reason": why or "Non-public DNS"}
                log["pages"].append(item)
                continue
        item["screenshots"] = {
            view: run_screenshot(item, view) for view in ("desktop", "mobile")
        }
        item["visual"] = visual_analysis(item)
        log["pages"].append(item)
    (OUT / "visual_manifest.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "VISUAL_REPORT.md").write_text(
        "# Selective Layout Review\n\n"
        + "Screenshots and AI observations are evidence, not measured SEO ranking factors.\n\n"
        + "\n".join("## " + row["id"] + "\n\n"
                    + (Path(row["visual"]["file"]).read_text(encoding="utf-8")
                       if row["visual"].get("status") == "analysed"
                       else "Status: " + row["visual"]["status"])
                    for row in log["pages"]) + "\n", encoding="utf-8")
    print("Selective SiteOne screenshots and vision review recorded.")


if __name__ == "__main__":
    main()
