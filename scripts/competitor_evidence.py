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
MAX_PAGES = 3
MAX_ATTEMPTS = 7
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
    target_host = (urlsplit(data.get("target_url", "")).hostname or "").lower()
    records, seen = [], set()
    attempts = successes = 0
    for group in data.get("groups", []):
        for result in group.get("results", []):
            url = str(result.get("url", ""))
            host = (urlsplit(url).hostname or "").lower()
            row = {
                "query": group.get("query", ""),
                "position": result.get("position"),
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "url": url, "domain": host, "status": "not_selected",
                "source": "SerpApi Google organic snapshot",
            }
            valid, reason = eligible(url)
            if not valid:
                row.update(status="unresolved_url", reason=reason)
            elif host == target_host:
                row.update(status="target_site")
            elif host in seen:
                row.update(status="duplicate_domain")
            elif successes >= MAX_PAGES or attempts >= MAX_ATTEMPTS:
                row.update(reason="Capture budget exhausted")
            else:
                seen.add(host)
                attempts += 1
                html, info = fetch_html(url)
                row.update(info)
                if html is not None:
                    soup = BeautifulSoup(html, "html.parser")
                    for node in soup(["script", "style", "noscript"]):
                        node.decompose()
                    visible = soup.get_text(" ", strip=True)
                    row["visible_text_characters"] = len(visible)
                    if len(visible) < 200:
                        raw_path = OUT / f"competitor_{attempts}_source.html"
                        raw_path.write_text(html, encoding="utf-8")
                        row.update(status="insufficient_html",
                                   html_file=raw_path.name,
                                   capture_stem=f"competitor_{attempts}")
                    else:
                        markdown, exit_code, log = convert_html(html, attempts)
                        row["html_file"] = f"competitor_{attempts}_source.html"
                        row["capture_stem"] = f"competitor_{attempts}"
                        row.update(conversion_exit_code=exit_code, log_file=log)
                        if exit_code == 0 and len(markdown.strip()) >= 200:
                            successes += 1
                            row.update(status="captured",
                                       source="SerpApi + validated HTML + SiteOne local conversion",
                                       markdown_file=f"competitor_{attempts}.md",
                                       excerpt=markdown[:MAX_CHARS],
                                       extracted_characters=len(markdown))
                        else:
                            row.update(status="conversion_failed",
                                       reason="No usable Markdown; see conversion log")
                # Do not retry blocked or failed URLs.
            records.append(row)
    output = {
        "source_snapshot": "google_serp.json",
        "searched_at_utc": data.get("searched_at_utc"),
        "successful_pages": successes, "attempted_pages": attempts,
        "max_successful_pages": MAX_PAGES, "max_attempts": MAX_ATTEMPTS,
        "google_api_requests_by_this_step": 0, "openai_requests_by_this_step": 0,
        "ai_search_tested": False,
        "warning": "Observed Google positions do not prove ranking causes.",
        "pages": records,
    }
    (OUT / "competitor_evidence.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = ["# STEP 3 - Competitor Content Evidence", "",
             "Google SERP snapshot and validated public-HTML capture; no paid APIs.", "",
             "| Position | Domain | Status |", "|---|---|---|"]
    for row in records:
        lines.append(f"| {row['position']} | {row['domain']} | {row['status']} |")
    lines.extend(["", "Blocked/unavailable pages retain SERP evidence but are not content-reviewed.",
                  "Google rank alone does not establish the reason for ranking."])
    (OUT / "COMPETITOR_EVIDENCE.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"Competitor capture: {successes} successful of {attempts} attempts; no paid API calls")


if __name__ == "__main__":
    main()
