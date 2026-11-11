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
        body = embedded.body or embedded
        heading = [re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()
                   for x in body.select("h1, h2, h3, h4")[:70]]
        text = re.sub(r"\s+", " ", body.get_text(" ", strip=True)).strip()
        if not text or not heading:
            continue
        links = []
        for anchor in body.select("a[href]")[:80]:
            href = anchor.get("href") or ""
            if href.startswith(("https://", "http://", "mailto:", "tel:", "#")):
                links.append({"label": anchor.get_text(" ", strip=True)[:160],
                              "href": href[:800]})
        # Preserve page-specific structure and visual asset references without
        # including huge inline image bytes in the AI-facing JSON.
        sections = []
        for section in body.select("section[id]")[:80]:
            section_text = re.sub(r"\s+", " ", section.get_text(" ", strip=True)).strip()
            sections.append({
                "id": str(section.get("id", ""))[:120],
                "headings": [{"level": h.name, "text": re.sub(r"\s+", " ", h.get_text(" ", strip=True)).strip()}
                             for h in section.select("h1,h2,h3,h4")[:30]],
                "text": section_text[:20_000],
                "text_truncated": len(section_text) > 20_000,
            })
        faqs = [
            {"question": re.sub(r"\s+", " ", q.get_text(" ", strip=True)).strip(),
             "answer": re.sub(r"\s+", " ", q.parent.get_text(" ", strip=True)).strip(),
             "initially_open": q.parent.has_attr("open")}
            for q in body.select("details > summary")[:60]
        ]
        images = []
        for picture in body.select("img")[:80]:
            src = str(picture.get("src", ""))
            images.append({
                "src_kind": "inline_data" if src.startswith("data:") else
                            ("external" if src.startswith(("https://", "http://")) else "relative"),
                "src_sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
                "src_reference": src[:600] if not src.startswith("data:") else None,
                "alt": str(picture.get("alt", ""))[:500],
                "width": str(picture.get("width", ""))[:30],
                "height": str(picture.get("height", ""))[:30],
            })
        times = [re.sub(r"\s+", " ", v.get_text(" ", strip=True)).strip()
                 for v in body.select("time")[:100]]
        counts = {
            "headings": len(body.select("h1,h2,h3,h4")),
            "sections": len(body.select("section[id]")),
            "links": len(body.select("a[href]")),
            "images": len(body.select("img")),
            "faqs": len(body.select("details > summary")),
            "time_elements": len(body.select("time")),
            "presenter_articles": len(body.select("article")),
            "style_blocks": len(embedded.select("style")),
            "scripts": len(embedded.select("script")),
        }
        structural_complete = (counts["headings"] <= 70
                               and counts["sections"] <= 80
                               and counts["links"] <= 80
                               and counts["images"] <= 80
                               and counts["faqs"] <= 60
                               and counts["time_elements"] <= 100
                               and len(text) <= 40_000
                               and all(not s["text_truncated"] for s in sections))
        items.append({
            "source": "Google Sites HTML data-code custom embed",
            "sections": sections,
            "faqs": faqs,
            "images": images,
            "times": times,
            "source_structure_counts": counts,
            "source_capture_integrity": {
                "complete_without_configured_truncation": structural_complete,
                "candidate_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "source_url_host": host,
                "limits_are_documented": True,
            },
            "source_html_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "embedded_html_characters": len(raw),
            "headings": heading,
            "h1": next((re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip() for x in body.select("h1")), ""),
            "visible_candidate_text": text[:40_000],
            "candidate_text_characters": len(text),
            "content_truncated": len(text) > 40_000,
            "links": links,
            "link_count_captured": len(links),
            "limitations": (
                "Attribute-embedded source text, not proof of search-engine indexing, "
                "frame rendering, CSS visibility, or availability to third-party crawlers. "
                "Check against the live page before treating details as approved."
            ),
        })
    valid = [x for x in items if x["h1"] and x["candidate_text_characters"] >= 400
             and x["source_capture_integrity"]["complete_without_configured_truncation"]]
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
