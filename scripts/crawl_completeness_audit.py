
"""Check SiteOne extraction before AI analysis."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path("reports")
URL = os.environ.get("AUDIT_URL", "")


def url_key(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    return host, parsed.path.rstrip("/") or "/"


def main():
    OUT.mkdir(exist_ok=True)
    issues = []

    try:
        data = json.loads(
            (OUT / "seo.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        data = {}
        issues.append(
            f"SEO JSON unavailable: {type(error).__name__}"
        )

    matches = [
        row for row in data.get("results", [])
        if isinstance(row, dict)
        and row.get("type") == 1
        and url_key(row.get("url", "")) == url_key(URL)
    ]

    row = matches[0] if matches else {}
    status = str(row.get("status", "not recorded"))
    size = row.get("size", "not recorded")

    path = OUT / "siteone_page.md"
    markdown = (
        path.read_text(encoding="utf-8", errors="replace")
        if path.exists() else ""
    )
    text = re.sub(r"\s+", " ", markdown).strip()

    blocked = bool(re.search(
        r"403 forbidden|access denied|just a moment|"
        r"checking your browser|verify you are human|"
        r"you have been blocked|captcha",
        text[:2000],
        re.IGNORECASE
    ))

    seo_rows = (
        data.get("tables", {}).get("seo", {}) or {}
    ).get("rows", [])

    target_path = urlsplit(URL).path.rstrip("/") or "/"
    meta = next(
        (
            item for item in seo_rows
            if (
                str(item.get("urlPathAndQuery", ""))
                .split("?")[0].rstrip("/") or "/"
            ) == target_path
        ),
        {},
    )

    title = meta.get("title", "")
    h1 = meta.get("h1", "")

    if not matches:
        issues.append("Target HTML URL was not recorded.")
    if status != "200":
        issues.append(f"HTTP status is {status}, not 200.")
    if not text:
        issues.append("Markdown export missing or empty.")
    if blocked:
        issues.append("Possible access-blocking page detected.")
    if len(text) < 400:
        issues.append("Extracted content is unusually short.")
    if not title or not h1:
        issues.append("Title or H1 needs verification.")

    if status != "200" or not text or blocked:
        verdict = "INCOMPLETE - DO NOT USE FOR AI"
    elif len(text) < 400 or not title or not h1:
        verdict = "NEEDS REVIEW - DO NOT USE FOR AI YET"
    else:
        verdict = (
            "CONTENT CAPTURED - FULL COMPLETENESS NOT PROVEN"
        )

    result = {
        "url": URL,
        "http_status": status,
        "response_bytes": size,
        "markdown_characters": len(text),
        "title": title,
        "h1": h1,
        "challenge_suspected": blocked,
        "verdict": verdict,
        "findings": issues,
    }

    (OUT / "crawl_completeness.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Crawl Completeness Audit",
        "",
        f"**Target:** `{URL}`",
        f"**Verdict:** **{verdict}**",
        "",
        "## Evidence",
        f"- HTTP status: {status}",
        f"- HTML size: {size} bytes",
        f"- Markdown characters: {len(text)}",
        f"- Extracted title: {title or 'Not found'}",
        f"- Extracted H1: {h1 or 'Not found'}",
        f"- Access-block page suspected: {blocked}",
        "",
        "## Findings",
    ]

    lines.extend(
        [f"- {issue}" for issue in issues]
        if issues else ["- No obvious extraction problem found."]
    )

    lines.extend([
        "",
        "## Body Preview",
        "",
        "```text",
        text[:500].replace("```", "'''"),
        "```",
        "",
        "## Limitations",
        "",
        "This check cannot prove that all dynamic content, "
        "images, forms, or metadata were captured.",
        "",
        "Manual verification is required before AI analysis.",
    ])

    report = "\n".join(lines) + "\n"

    (OUT / "CRAWL_COMPLETENESS_AUDIT.md").write_text(
        report, encoding="utf-8"
    )

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write(report + "\n")

    print(verdict)


if __name__ == "__main__":
    main()
