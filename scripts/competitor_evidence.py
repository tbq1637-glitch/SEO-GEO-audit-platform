"""STEP 3: collect bounded, source-traceable competitor page evidence with SiteOne.

This step makes no SerpApi or OpenAI calls. It does not infer ranking causes.
"""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path("reports")
MAX_PAGES = 3
MAX_CHARS = 16000


def eligible(url):
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not host or host == "localhost":
        return False, "Only public HTTPS URLs are eligible"
    if host == "google.com" or host.endswith(".google.com"):
        return False, "Opaque Google redirect; destination not verified"
    if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host:
        return False, "Invalid hostname"
    if p.username or p.password or any(part.isdigit() for part in host.split(".")):
        return False, "Credentialed or IP-like URL rejected"
    if host.endswith((".local", ".internal", ".test", ".invalid")):
        return False, "Non-public hostname"
    return True, ""


def main():
    source = OUT / "google_serp.json"
    if not source.exists():
        print("Competitor evidence skipped: no Google snapshot available")
        return
    data = json.loads(source.read_text(encoding="utf-8"))
    records, selected = [], 0
    seen = set()
    target_host = urlsplit(data.get("target_url", "")).hostname
    target_host = (target_host or "").lower()
    for group in data.get("groups", []):
        for result in group.get("results", []):
            url = result.get("url", "")
            valid, reason = eligible(url)
            host = (urlsplit(url).hostname or "").lower()
            row = {
                "query": group.get("query", ""),
                "position": result.get("position"),
                "title": result.get("title", ""),
                "url": url,
                "domain": host,
                "status": "not_attempted",
                "reason": "",
                "source": "SerpApi Google organic snapshot + SiteOne page capture",
            }
            if not valid:
                row.update(status="unresolved_url", reason=reason)
            elif host == target_host:
                row.update(status="target_site", reason="Not a competitor")
            elif host in seen:
                row.update(status="duplicate_domain", reason="One page per domain in pilot")
            elif selected >= MAX_PAGES:
                row.update(status="not_selected", reason="Pilot cap: three pages")
            else:
                seen.add(host)
                selected += 1
                md = OUT / f"competitor_{selected}.md"
                export_dir = OUT / f"competitor_{selected}_export"
                export_dir.mkdir(parents=True, exist_ok=True)
                log_path = OUT / f"competitor_{selected}_siteone.log"
                row["log_file"] = log_path.name
                try:
                    run = subprocess.run(
                        ["siteone-crawler", f"--url={url}", "--single-page",
                         "--workers=1", "--max-reqs-per-sec=1",
                         f"--markdown-export-dir={export_dir}",
                         f"--markdown-export-single-file={md}"],
                        capture_output=True, text=True, timeout=100, check=False,
                    )
                    log_path.write_text(
                        f"SiteOne exit code: {run.returncode}\n"
                        f"Markdown file exists: {md.exists()}\n"
                        f"STDOUT:\n{run.stdout[-6000:]}\n"
                        f"STDERR:\n{run.stderr[-6000:]}\n",
                        encoding="utf-8",
                    )
                    row["siteone_exit_code"] = run.returncode
                    content = md.read_text(encoding="utf-8", errors="replace") if md.exists() else ""
                    if run.returncode == 0 and len(content.strip()) >= 200:
                        row.update(status="captured", markdown_file=md.name,
                                   excerpt=content[:MAX_CHARS],
                                   extracted_characters=len(content))
                    else:
                        row.update(status="capture_failed",
                                   reason=("SiteOne exit code " + str(run.returncode)
                                           + "; extracted characters: " + str(len(content))
                                           + "; see " + log_path.name))
                except (OSError, subprocess.TimeoutExpired) as exc:
                    row.update(status="capture_failed", reason=type(exc).__name__)
                    log_path.write_text(
                        f"SiteOne failed: {type(exc).__name__}\n",
                        encoding="utf-8",
                    )
            records.append(row)
    output = {
        "source_snapshot": "google_serp.json",
        "searched_at_utc": data.get("searched_at_utc"),
        "limit": MAX_PAGES,
        "google_queries_charged_by_this_step": 0,
        "ai_search_tested": False,
        "warning": "Search presence is observed; ranking causes are not established.",
        "pages": records,
    }
    (OUT / "competitor_evidence.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = ["# STEP 3 - Competitor Content Evidence", "",
               "Source: SerpApi organic results, followed by SiteOne capture.",
               "Rank observations do not establish why pages rank.", "",
               "| Google position | Domain | Capture status |",
               "|---|---|---|"]
    for row in records:
        summary.append(f"| {row['position']} | {row['domain']} | {row['status']} |")
    summary += ["", "No search ranking causality or ChatGPT citations are claimed."]
    (OUT / "COMPETITOR_EVIDENCE.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"Competitor evidence collected: {sum(x['status']=='captured' for x in records)} / {selected} attempted")


if __name__ == "__main__":
    main()
