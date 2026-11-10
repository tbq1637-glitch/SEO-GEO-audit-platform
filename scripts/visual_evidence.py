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
import time
from pathlib import Path

from competitor_evidence import eligible, public_dns

ROOT = Path("reports")
OUT = ROOT / "step4" / "visual"
OUT.mkdir(parents=True, exist_ok=True)
MAX_COMPETITORS = 2
MAX_COMPETITOR_ATTEMPTS = 4
MAX_SCREENSHOTS = 2 * (1 + MAX_COMPETITOR_ATTEMPTS)


def select_pages(snapshot):
    """Target, then at most four distinct captured-text competitors.

    Prefer diversity of query, then fill with other candidates. Do not
    confuse a candidate queue with four required screenshot analyses.
    """
    selected = [{"kind": "target", "id": "target",
                 "url": os.environ["AUDIT_URL"], "query": None, "position": None}]
    rows = [r for r in snapshot.get("pages", []) if r.get("status") == "captured"]
    seen_urls, seen_queries = set(), set()

    def add(row):
        url = row.get("final_url") or row.get("url") or ""
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        selected.append({
            "kind": "competitor", "id": "competitor_" + str(len(selected)),
            "url": url, "query": row.get("query"),
            "position": row.get("position"),
        })

    for row in rows:
        if len(selected) >= MAX_COMPETITOR_ATTEMPTS + 1:
            break
        query = row.get("query", "")
        if query in seen_queries:
            continue
        seen_queries.add(query)
        add(row)
    for row in rows:
        if len(selected) >= MAX_COMPETITOR_ATTEMPTS + 1:
            break
        add(row)
    return selected


def _text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _inspect_screenshot(path, viewport):
    """Validate a fresh JPG after the screenshot process has stopped."""
    from PIL import Image, UnidentifiedImageError
    expected_width = {"desktop": 1440, "mobile": 390}[viewport]
    info = {"path": str(path), "valid": False}
    try:
        first = path.stat()
        time.sleep(0.15)
        second = path.stat()
        info["bytes"] = second.st_size
        if first.st_size != second.st_size or second.st_size < 4096:
            info["reason"] = "empty_or_unstable_file"
            return info
        with Image.open(path) as img:
            info["format"] = img.format
            info["width"], info["height"] = img.size
            img.verify()
        with Image.open(path) as img:
            img.load()
        if info["format"] != "JPEG":
            info["reason"] = "unexpected_format"
        elif not 0.9 * expected_width <= info["width"] <= 1.1 * expected_width:
            info["reason"] = "viewport_width_mismatch"
        elif info["height"] < 200:
            info["reason"] = "image_too_short"
        else:
            info["valid"] = True
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        info["reason"] = "invalid_image_" + type(exc).__name__
    return info


def run_screenshot(item, viewport):
    folder = OUT / item["id"] / viewport
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "siteone.log"
    # Do not count old files as evidence of the current attempt.
    for stale in folder.rglob("*.jpg"):
        stale.unlink()
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
    started = time.monotonic()
    diagnostic = {
        "url": item["url"], "viewport": viewport,
        "browser_timeout_seconds": 35, "process_timeout_seconds": 100,
        "command": cmd, "stage": "unknown_without_siteone_internal_trace"
    }
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=100, check=False)
        diagnostic["exit_code"] = proc.returncode
        diagnostic["stderr_tail"] = _text(getattr(proc, "stderr", None))[-6000:]
        diagnostic["stdout_tail"] = _text(getattr(proc, "stdout", None))[-3000:]
    except subprocess.TimeoutExpired as exc:
        diagnostic["timed_out"] = True
        diagnostic["exception"] = "TimeoutExpired"
        diagnostic["stderr_tail"] = _text(exc.stderr)[-6000:]
        diagnostic["stdout_tail"] = _text(exc.stdout)[-3000:]
    except OSError as exc:
        diagnostic["exception"] = type(exc).__name__
        diagnostic["error"] = str(exc)[:1000]
    diagnostic["elapsed_seconds"] = round(time.monotonic() - started, 2)

    images = [_inspect_screenshot(p, viewport) for p in sorted(folder.rglob("*.jpg"))]
    valid = [x for x in images if x["valid"]]
    diagnostic["image_checks"] = images
    diagnostic["valid_image_count"] = len(valid)
    log.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    outcome = {
        "viewport": viewport, "log": str(log),
        "elapsed_seconds": diagnostic["elapsed_seconds"],
        "process_timeout": diagnostic.get("timed_out", False),
        "exit_code": diagnostic.get("exit_code"),
        "image_checks": images
    }
    if valid:
        outcome.update(status="captured", image=valid[0]["path"],
                       capture_origin=("recovered_after_timeout" if diagnostic.get("timed_out")
                                       else "completed_process" if diagnostic.get("exit_code") == 0
                                       else "recovered_after_failed_process"))
    else:
        outcome.update(status="unavailable" if diagnostic.get("timed_out") else "failed",
                       reason=diagnostic.get("exception") or
                       ("siteone_exit_" + str(diagnostic.get("exit_code"))
                        if diagnostic.get("exit_code") is not None
                        else "no_verified_screenshot"))
    return outcome


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
    OUT.mkdir(parents=True, exist_ok=True)
    data_path = ROOT / "competitor_evidence.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    candidates = select_pages(data)
    log = {
        "source": "SiteOne browser screenshots + OpenAI image review",
        "policy": "target + up to four competitor attempts seeking two completed visual reviews",
        "not_a_ranking_measurement": True,
        "target_competitor_visual_samples": MAX_COMPETITORS,
        "max_competitor_attempts": MAX_COMPETITOR_ATTEMPTS,
        "max_screenshot_attempts": MAX_SCREENSHOTS,
        "competitor_attempts": 0, "completed_competitor_visual_samples": 0,
        "pages": []
    }
    if not shutil.which("siteone-crawler"):
        log["reason"] = "SiteOne unavailable"
        candidates = []

    for item in candidates:
        if item["kind"] == "competitor":
            if log["completed_competitor_visual_samples"] >= MAX_COMPETITORS:
                break
            if log["competitor_attempts"] >= MAX_COMPETITOR_ATTEMPTS:
                break
            log["competitor_attempts"] += 1
            safe, why = eligible(item["url"])
            if not safe or not public_dns(item["url"]):
                item["visual"] = {"status": "skipped",
                                  "reason": why or "Non-public DNS"}
                log["pages"].append(item)
                continue
        item["screenshots"] = {
            view: run_screenshot(item, view) for view in ("desktop", "mobile")
        }
        item["valid_viewports"] = [
            view for view, record in item["screenshots"].items()
            if record.get("status") == "captured"
        ]
        # One valid viewport is enough for an explicitly limited analysis.
        item["visual"] = visual_analysis(item)
        if item["kind"] == "competitor" and item["visual"].get("status") == "analysed":
            log["completed_competitor_visual_samples"] += 1
        log["pages"].append(item)

    (OUT / "visual_manifest.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Selective Layout Review", "",
        "Screenshots and AI observations are qualitative evidence, not ranking metrics.",
        f"Completed competitor visual samples: {log['completed_competitor_visual_samples']}"
        f" / {MAX_COMPETITORS} from {log['competitor_attempts']} attempted competitors.", ""
    ]
    for item in log["pages"]:
        lines.extend(["## " + item["id"], "Source URL: " + item["url"]])
        if item.get("valid_viewports"):
            lines.append("Verified viewports: " + ", ".join(item["valid_viewports"]))
        visual = item["visual"]
        if visual.get("status") == "analysed":
            lines.append(Path(visual["file"]).read_text(encoding="utf-8"))
        else:
            lines.append("Review status: " + visual.get("status", "not_tested"))
            if visual.get("reason"):
                lines.append("Reason: " + visual["reason"])
        lines.append("")
    (OUT / "VISUAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Visual evidence recorded with bounded fallback; no automatic OpenAI retries.")


if __name__ == "__main__":
    main()
