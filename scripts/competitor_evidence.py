"""STEP 3 free competitor-page evidence collection.

Uses the cached Google snapshot. Never invokes OpenAI or SerpApi.
Only public HTTPS HTML is converted; blocked pages remain search evidence.
"""
import ipaddress
import json
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

OUT = Path("reports")
MAX_PER_QUERY = 3
MAX_ATTEMPTS_PER_QUERY = 10
MAX_QUERIES = 5
MAX_CHARS = 16000
MAX_HTML_BYTES = 1_500_000
TIMEOUT = 25


def eligible(url):
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or not host or p.username or p.password:
            return False, "Requires a public HTTPS URL without credentials"
        if host == "google.com" or host.endswith(".google.com"):
            return False, "Opaque Google redirect; destination not verified"
        if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host:
            return False, "Invalid hostname"
        if host.endswith((".local", ".internal", ".test", ".invalid", ".localhost")):
            return False, "Non-public hostname"
        try:
            ipaddress.ip_address(host)
            return False, "Direct IP addresses are not permitted"
        except ValueError:
            pass
        return True, ""
    except ValueError:
        return False, "Malformed URL"


def is_video_platform_url(url):
    """Recognize hosting media pages without claiming to understand video."""
    host = (urlsplit(url).hostname or "").lower()
    hosts = ("youtube.com", "youtu.be", "vimeo.com",
             "dailymotion.com", "wistia.com")
    return any(host == h or host.endswith("." + h) for h in hosts)


def public_dns(url):
    host = urlsplit(url).hostname
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_global for item in addresses
        )
    except (OSError, ValueError):
        return False


def fetch_html(url):
    """No automatic redirects, to avoid fetching an unvalidated target."""
    current = url
    for redirects in range(4):
        valid, reason = eligible(current)
        if not valid or not public_dns(current):
            return None, {"status": "unsafe_url", "reason": reason or "DNS is not public"}
        try:
            response = requests.get(
                current, headers={"User-Agent": "SEO-GEO-Audit/2.0"},
                timeout=TIMEOUT, allow_redirects=False, stream=True,
            )
            status = response.status_code
            if status in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                location = response.headers.get("Location")
                response.close()
                if not location:
                    return None, {"status": "redirect_error", "http_status": status}
                current = urljoin(current, location)
                continue
            info = {"http_status": status, "final_url": current,
                    "content_type": response.headers.get("Content-Type", "")}
            if status in (401, 403, 429):
                response.close()
                return None, {**info, "status": "access_blocked"}
            if status != 200:
                response.close()
                return None, {**info, "status": "http_error"}
            if "text/html" not in info["content_type"].lower():
                response.close()
                return None, {**info, "status": "non_html"}
            data = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                data.extend(chunk)
                if len(data) > MAX_HTML_BYTES:
                    response.close()
                    return None, {**info, "status": "too_large"}
            encoding = response.encoding or "utf-8"
            response.close()
            return bytes(data).decode(encoding, errors="replace"), info
        except requests.RequestException as exc:
            return None, {"status": "network_error", "reason": type(exc).__name__}
    return None, {"status": "redirect_error", "reason": "Too many redirects"}


def convert_html(html, index):
    html_path = OUT / f"competitor_{index}_source.html"
    md_path = OUT / f"competitor_{index}.md"
    log_path = OUT / f"competitor_{index}_conversion.log"
    html_path.write_text(html, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["siteone-crawler", f"--html-to-markdown={html_path}",
             f"--html-to-markdown-output={md_path}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        log_path.write_text(
            f"exit_code={proc.returncode}\nstdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}\n",
            encoding="utf-8",
        )
        markdown = md_path.read_text(encoding="utf-8", errors="replace") if md_path.exists() else ""
        return markdown, proc.returncode, log_path.name
    except (OSError, subprocess.TimeoutExpired) as exc:
        log_path.write_text(type(exc).__name__ + "\n", encoding="utf-8")
        return "", -1, log_path.name
    finally:
        # Preserve bounded source HTML for structure and dynamic-content audit.
        # It is already capped at MAX_HTML_BYTES by fetch_html().
        pass


def main():
    source = OUT / "google_serp.json"
    if not source.exists():
        print("Competitor capture skipped: cached Google snapshot unavailable")
        return
    data = json.loads(source.read_text(encoding="utf-8"))
    groups = data.get("groups", [])
    if len(groups) != MAX_QUERIES or any(g.get("error") for g in groups):
        raise RuntimeError("Five completed Google query groups required")
    target_host = (urlsplit(data.get("target_url", "")).hostname or "").lower()
    records, per_query = [], []
    # URL cache includes both successful and failed attempts to avoid
    # repeatedly downloading the same content across search intents.
    fetched = {}
    attempts = 0
    successes = 0

    for group_index, group in enumerate(groups, 1):
        query_id = group.get("id") or f"Q{group_index}"
        query = group.get("query", "")
        group_successes = group_attempts = 0
        seen_urls_in_query = set()
        for result in group.get("results", [])[:MAX_ATTEMPTS_PER_QUERY]:
            url = str(result.get("url", ""))
            host = (urlsplit(url).hostname or "").lower()
            row = {
                "query_id": query_id, "query": query,
                "position": result.get("position"),
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "url": url, "domain": host,
                "status": "not_selected",
                "source": "SerpApi Google organic snapshot",
            }
            valid, reason = eligible(url)
            if group_successes >= MAX_PER_QUERY:
                row["reason"] = "Per-query three-success target reached"
            elif not valid:
                row.update(status="unresolved_url", reason=reason)
            elif host == target_host:
                row["status"] = "target_site"
            elif is_video_platform_url(url):
                row.update(status="video_reference",
                           reason="Video platform SERP result: metadata evidence only; not counted as HTML content")
            elif url in seen_urls_in_query:
                row["status"] = "duplicate_url_in_query"
            else:
                # Exact same URL is deduplicated, but distinct pages on the same
                # host remain eligible: domain equality is NOT content equality.
                seen_urls_in_query.add(url)
                cached = fetched.get(url)
                if cached is not None:
                    row.update({
                        k: value for k, value in cached.items()
                        if k not in ("query_id", "query", "position", "title",
                                     "snippet", "url", "domain", "source")
                    })
                    row["reused"] = True
                    row["reuse_source_url"] = url
                    # No repeated large excerpt: the source markdown filename
                    # provides the full retained text.
                    row.pop("excerpt", None)
                    if row.get("status") == "captured":
                        group_successes += 1
                elif group_attempts >= MAX_ATTEMPTS_PER_QUERY:
                    row["reason"] = "Per-query request attempt limit reached"
                else:
                    group_attempts += 1
                    attempts += 1
                    html, info = fetch_html(url)
                    row.update(info)
                    if html is not None:
                        soup = BeautifulSoup(html, "html.parser")
                        for node in soup(["script", "style", "noscript"]):
                            node.decompose()
                        visible = soup.get_text(" ", strip=True)
                        row["visible_text_characters"] = len(visible)
                        stem = f"competitor_{attempts}"
                        row["capture_stem"] = stem
                        row["html_file"] = stem + "_source.html"
                        if len(visible) < 200:
                            (OUT / row["html_file"]).write_text(
                                html, encoding="utf-8")
                            row["status"] = "insufficient_html"
                        else:
                            markdown, exit_code, log = convert_html(html, attempts)
                            row.update(conversion_exit_code=exit_code,
                                       log_file=log)
                            if exit_code == 0 and len(markdown.strip()) >= 200:
                                group_successes += 1
                                successes += 1
                                row.update(
                                    status="captured",
                                    source="SerpApi + validated HTML + SiteOne local conversion",
                                    markdown_file=stem + ".md",
                                    extracted_characters=len(markdown),
                                    excerpt=markdown[:MAX_CHARS],
                                )
                            else:
                                row.update(status="conversion_failed",
                                           reason="No usable Markdown; see conversion log")
                    # Cache failed outcomes as well to avoid repeats.
                    fetched[url] = dict(row)
            records.append(row)
        per_query.append({
            "id": query_id, "query": query, "successes": group_successes,
            "target_successes": MAX_PER_QUERY,
            "new_requests": group_attempts,
            "met_target": group_successes >= MAX_PER_QUERY,
            "shortfall": max(0, MAX_PER_QUERY - group_successes),
        })

    result = {
        "source_snapshot": "google_serp.json",
        "searched_at_utc": data.get("searched_at_utc"),
        "successful_pages": successes,
        "unique_captured_urls": successes,
        "query_sample_count": sum(x["successes"] for x in per_query),
        "attempted_pages": attempts,
        "max_successful_pages_per_query": MAX_PER_QUERY,
        "max_attempts_per_query": MAX_ATTEMPTS_PER_QUERY,
        "max_query_samples": MAX_QUERIES * MAX_PER_QUERY,
        "per_query": per_query,
        "google_api_requests_by_this_step": 0,
        "openai_requests_by_this_step": 0,
        "ai_search_tested": False,
        "warning": "Google positions do not establish ranking causes; capture shortfalls are disclosed.",
        "pages": records,
    }
    (OUT / "competitor_evidence.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = ["# STEP 3 - Five-query Competitor Content Evidence", "",
             "Query-specific samples. Same URL across different queries is reused.",
             "No additional paid API calls for direct HTTPS capture.", "",
             "| Query | Captured / target | New URL attempts | Coverage |",
             "|---|---:|---:|---|"]
    for q in per_query:
        lines.append(
            f"| {q['id']} | {q['successes']}/{MAX_PER_QUERY} "
            f"| {q['new_requests']} "
            f"| {'complete' if q['met_target'] else 'partial'} |")
    lines.extend(["", "## Source pages", "",
                  "| Query | Google position | Domain | Status |",
                  "|---|---:|---|---|"])
    for row in records:
        lines.append(
            f"| {row['query_id']} | {row['position']} | "
            f"{row['domain']} | {row['status']}"
            f"{' (reused)' if row.get('reused') else ''} |")
    lines.extend(["", "Blocked/unavailable pages are retained as search evidence, "
                  "not represented as full-text competitors.",
                  "Three captures per question are targets, not guaranteed results."])
    (OUT / "COMPETITOR_EVIDENCE.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Competitor evidence: {result['query_sample_count']}/15 query samples, "
        f"{successes} distinct captured URLs, {attempts} new URL requests")


if __name__ == "__main__":
    main()
