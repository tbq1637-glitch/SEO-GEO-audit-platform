"""Extract publisher-embedded Google Sites HTML without changing upstream scanners.

A Google Sites data-code attribute can contain an entire custom HTML widget while
the ordinary page body and SiteOne/GEO outputs expose only its wrapper.
Never report this as native crawler-visible content; preserve source provenance.
"""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


def capture(html, url, output_dir):
    host = (urlsplit(url).hostname or "").lower()
    if host != "sites.google.com":
        return None
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select("[data-code]")
    items = []
    for node in candidates[:5]:
        raw = node.get("data-code") or ""
        if not isinstance(raw, str) or not (100 <= len(raw) <= 900_000):
            continue
        embedded = BeautifulSoup(raw, "html.parser")
        for unwanted in embedded.select("script, style, template, noscript, svg"):
            unwanted.decompose()
        body = embedded.select_one("main") or embedded.body or embedded
        heading = [re.sub(r"\\s+", " ", x.get_text(" ", strip=True)).strip()
                   for x in body.select("h1, h2, h3, h4")[:70]]
        text = re.sub(r"\\s+", " ", body.get_text(" ", strip=True)).strip()
        if not text or not heading:
            continue
        links = []
        for anchor in body.select("a[href]")[:80]:
            href = anchor.get("href") or ""
            if href.startswith(("https://", "http://", "mailto:", "tel:", "#")):
                links.append({"label": anchor.get_text(" ", strip=True)[:160],
                              "href": href[:800]})
        items.append({
            "source": "Google Sites HTML data-code custom embed",
            "source_html_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "embedded_html_characters": len(raw),
            "headings": heading,
            "h1": next((x.get_text(" ", strip=True) for x in body.select("h1")), ""),
            "visible_candidate_text": text[:40_000],
            "candidate_text_characters": len(text),
            "links": links,
            "limitations": (
                "Attribute-embedded source text, not proof of search-engine indexing, "
                "frame rendering, CSS visibility, or availability to third-party crawlers. "
                "Check against the live page before treating details as approved."
            ),
        })
    valid = [x for x in items if x["h1"] and x["candidate_text_characters"] >= 400]
    if not valid:
        return None
    result = {
        "source_url": url,
        "source_method": "google_sites_custom_html_attribute",
        "http_wrapper_is_not_embedded_body": True,
        "full_page_completeness_not_proven": True,
        "items": valid,
        "total_candidate_text_characters": sum(x["candidate_text_characters"] for x in valid),
        "native_scanner_results_unchanged": True,
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "target_embedded_evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
