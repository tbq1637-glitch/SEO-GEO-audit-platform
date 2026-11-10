"""Bounded video context and optional published text-track evidence.

This is NOT video decoding, speech recognition or a YouTube transcript scraper.
Only supplied SERP metadata, already-captured HTML, native video markup, and
public publisher-supplied .vtt/.srt/.txt tracks are used. Video evidence never
fills an HTML competitor slot. No AI or paid search API calls.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from competitor_evidence import eligible, fetch_html

ROOT = Path("reports")
OUT = ROOT / "step3_video"
MAX_TRANSCRIPTS = 3
MAX_TRANSCRIPT_PER_QUERY = 1
MAX_TRANSCRIPT_BYTES = 120_000
MAX_TRANSCRIPT_CHARS_FOR_FUSION = 5000
VIDEO_HOSTS = {"youtube.com", "youtu.be", "vimeo.com", "player.vimeo.com",
               "dailymotion.com", "www.dailymotion.com", "wistia.com"}
TRACK_EXTENSIONS = (".vtt", ".srt", ".txt")


def is_video_host(url):
    hostname = (urlsplit(url).hostname or "").lower()
    return any(hostname == host or hostname.endswith("." + host) for host in VIDEO_HOSTS)


def is_video_result(result):
    url = str(result.get("url", ""))
    return (is_video_host(url) or
            str(result.get("type", "")).lower() == "video" or
            str(result.get("result_type", "")).lower() == "video")


def text(value, max_chars=1000):
    return " ".join(str(value or "").split())[:max_chars]


def links_from_html(html, source_url):
    """Extract on-page multimedia evidence without claiming video understanding."""
    soup = BeautifulSoup(html, "html.parser")
    titles = []
    for node in soup.select("video, iframe[src], embed[src], object[data]")[:40]:
        url = node.get("src") or node.get("data") or ""
        if node.name == "video":
            url = url or (node.select_one("source[src]") or {}).get("src", "")
        if not url:
            continue
        absolute = urljoin(source_url, url)
        if node.name != "video" and not is_video_host(absolute):
            continue
        titles.append({
            "kind": node.name, "url": absolute[:1000],
            "title": text(node.get("title") or node.get("aria-label"), 300),
            "poster": str(node.get("poster", ""))[:600],
        })
    tracks = []
    for track in soup.select("track[src]")[:20]:
        url = urljoin(source_url, track.get("src", ""))
        tracks.append({"url": url, "kind": str(track.get("kind", ""))[:50],
                       "language": str(track.get("srclang", ""))[:40],
                       "label": text(track.get("label"), 120),
                       "source": "HTML track element"})
    for a in soup.select("a[href]")[:400]:
        href = urljoin(source_url, a.get("href", ""))
        path = urlsplit(href).path.lower()
        label = text(a.get_text(" ", strip=True), 180)
        if path.endswith(TRACK_EXTENSIONS) and (
                "transcript" in label.lower() or "caption" in label.lower()
                or "subtitle" in label.lower()):
            tracks.append({"url": href, "kind": "publisher_link",
                           "language": "", "label": label,
                           "source": "explicit publisher transcript link"})
    schemas = []
    for script in soup.select('script[type="application/ld+json"]')[:20]:
        try:
            value = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        def find_video(obj, depth=0):
            if depth > 8 or len(schemas) >= 12:
                return
            if isinstance(obj, list):
                for item in obj[:30]:
                    find_video(item, depth + 1)
            elif isinstance(obj, dict):
                types = obj.get("@type", "")
                typelist = types if isinstance(types, list) else [types]
                if "VideoObject" in typelist:
                    schemas.append({key: text(obj.get(key), 900)
                                    for key in ("name", "description", "uploadDate",
                                                "duration", "thumbnailUrl", "embedUrl",
                                                "contentUrl", "transcript")
                                    if obj.get(key)})
                for key, nested in list(obj.items())[:35]:
                    if isinstance(nested, (dict, list)):
                        find_video(nested, depth + 1)
        find_video(value)
    metadata = {}
    for key in ("og:title", "og:description", "og:video", "video:duration"):
        meta = soup.find("meta", attrs={"property": key})
        if meta and meta.get("content"):
            metadata[key] = text(meta["content"], 900)
    return {"embed_count": len(titles), "embeds": titles,
            "caption_links": tracks, "video_schema": schemas,
            "metadata": metadata,
            "limitations": "HTML metadata and video embeds do not establish playback, transcript contents, or whether a viewer watched the media."}


def _fetch_published_text(url):
    """Only a verified public HTTPS direct text resource, with strict bounds."""
    from urllib.parse import urlsplit
    import requests
    from competitor_evidence import public_dns
    parsed = urlsplit(url)
    if not parsed.path.lower().endswith(TRACK_EXTENSIONS):
        return None, "not_a_direct_published_text_track"
    valid, reason = eligible(url)
    if not valid or not public_dns(url):
        return None, reason or "unsafe_or_nonpublic_url"
    try:
        response = requests.get(url, timeout=15, allow_redirects=False,
                                stream=True, headers={"User-Agent": "SEO-GEO-Audit/2.0"})
        with response:
            if response.status_code != 200:
                return None, "http_" + str(response.status_code)
            mime = response.headers.get("Content-Type", "").split(";")[0].lower()
            if not (mime.startswith("text/") or mime in (
                    "application/x-subrip", "application/octet-stream")):
                return None, "non_text_media_type"
            chunks, length = [], 0
            for chunk in response.iter_content(chunk_size=8192):
                length += len(chunk)
                if length > MAX_TRANSCRIPT_BYTES:
                    return None, "text_exceeds_limit"
                chunks.append(chunk)
        body = b"".join(chunks).decode("utf-8-sig", errors="replace")
        if len(body.strip()) < 80:
            return None, "insufficient_published_text"
        return body, None
    except requests.RequestException as exc:
        return None, type(exc).__name__


def _clean_transcript(raw):
    # Keeps timestamp/location cues and speaker labels if publisher included.
    # Only normalize unsafe HTML, do not pretend partial excerpts are complete.
    plain = BeautifulSoup(raw, "html.parser").get_text("\n")
    lines = [line.strip() for line in plain.splitlines()]
    return "\n".join(x for x in lines if x).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot = json.loads((ROOT / "google_serp.json").read_text(encoding="utf-8"))
    captured = json.loads((ROOT / "competitor_evidence.json").read_text(encoding="utf-8"))
    results = {"version": 1, "sources": [], "query_video_results": {},
               "transcripts_attempted": 0, "transcripts_captured": 0,
               "max_transcripts_total": MAX_TRANSCRIPTS,
               "max_transcripts_per_query": MAX_TRANSCRIPT_PER_QUERY,
               "no_download_or_media_decoding": True,
               "no_youtube_caption_scraping": True}
    for group in snapshot.get("groups", []):
        qid = group.get("id", "")
        hits = [{
            "query_id": qid, "url": str(item.get("url", "")),
            "position": item.get("position"),
            "title": text(item.get("title"), 260),
            "snippet": text(item.get("snippet"), 650),
            "evidence_type": "SERP_VIDEO_METADATA_ONLY",
            "content_reviewed": False,
        } for item in group.get("results", []) if is_video_result(item)]
        results["query_video_results"][qid] = hits
    unique_stems = set()
    sources = []
    for row in captured.get("pages", []):
        stem = row.get("capture_stem", "")
        if not re.fullmatch(r"competitor_\d+", stem) or stem in unique_stems:
            continue
        raw_path = ROOT / (stem + "_source.html")
        if not raw_path.is_file():
            continue
        unique_stems.add(stem)
        sources.append({"stem": stem, "url": row.get("final_url") or row["url"],
                        "query_id": row.get("query_id"), "page_status": row.get("status"),
                        "html_file": raw_path.name})
    if (ROOT / "target_source.html").is_file():
        sources.append({"stem": "target", "url": snapshot.get("target_url"),
                        "query_id": "TARGET", "page_status": "target",
                        "html_file": "target_source.html"})

    attempted_urls, transcripts_per_query = set(), {}
    for source in sources:
        html = (ROOT / source["html_file"]).read_text(
            encoding="utf-8", errors="replace")
        details = links_from_html(html, source["url"])
        entry = {**source, **details, "transcript_status": "not_requested"}
        # A publisher's directly-linked transcript/track can add information
        # missing from thin page content, but no full-video downloads are made.
        needs_context = (source["page_status"] in ("insufficient_html",
                                                     "conversion_failed")
                         or (source["page_status"] == "captured" and
                             details["embed_count"] and len(BeautifulSoup(
                                 html, "html.parser").get_text(" ", strip=True)) < 1000))
        for link in details["caption_links"]:
            qid = source["query_id"]
            if not needs_context:
                entry["transcript_status"] = "page_text_sufficient"
                break
            if qid == "TARGET":
                # Target video transcripts require a separate content-owner
                # decision; no unsolicited retrieval of linked media assets.
                entry["transcript_status"] = "target_not_automatically_retrieved"
                break
            if (results["transcripts_attempted"] >= MAX_TRANSCRIPTS
                    or transcripts_per_query.get(qid, 0) >= MAX_TRANSCRIPT_PER_QUERY):
                entry["transcript_status"] = "budget_exhausted"
                break
            url = link["url"]
            if url in attempted_urls:
                entry["transcript_status"] = "duplicate_link_skipped"
                continue
            attempted_urls.add(url)
            transcripts_per_query[qid] = transcripts_per_query.get(qid, 0) + 1
            results["transcripts_attempted"] += 1
            value, error = _fetch_published_text(url)
            if error:
                entry["transcript_status"] = "failed"
                entry["transcript_error"] = error
            else:
                body = _clean_transcript(value)
                path = OUT / (source["stem"] + "_publisher_transcript.txt")
                path.write_text(body, encoding="utf-8")
                entry["transcript_status"] = "captured"
                entry["transcript_file"] = str(path)
                entry["transcript_chars"] = len(body)
                entry["transcript_source_url"] = url
                results["transcripts_captured"] += 1
                break
        results["sources"].append(entry)
    (OUT / "video_manifest.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    lines = ["# Multimedia / Video Evidence", "",
             "Video metadata is not proof of understood or viewed media.",
             "Only directly published accessible text tracks may be read.",
             "Video signals do not count toward the 5×3 HTML page quota.", "",
             "| Query | Video SERP results (metadata only) |",
             "|---|---:|"]
    for qid, items in results["query_video_results"].items():
        lines.append(f"| {qid} | {len(items)} |")
    lines.extend(["", "## Publisher-linked video metadata and text", ""])
    for item in results["sources"]:
        lines.append("- " + str(item["stem"]) + ": " +
                     str(item["embed_count"]) + " embeds; " +
                     str(len(item["video_schema"])) + " VideoObject records; " +
                     "transcript: " + str(item["transcript_status"]))
    (OUT / "VIDEO_EVIDENCE.md").write_text("\n".join(lines) + "\n",
                                            encoding="utf-8")
    print("Video evidence: no video downloads, no AI calls, no extra Google searches")


if __name__ == "__main__":
    main()
