"""STEP 3: evidence-first comparison preparation, no API or ranking-cause claims."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path("reports")
STOP = {"the","and","for","with","what","where","can","find","online","in","a","of","to","is","how","i","my","on","at"}
NAV = re.compile(r"^(?:[-*] \[|\[|Get in touch|Home|Menu|Donate|Contact Us|Privacy|Cookie|Subscribe|Follow us)", re.I)
HEADING = re.compile(r"^#{1,4}\s+(.+)")
SPACE = re.compile(r"\s+")


def clean(value):
    return SPACE.sub(" ", re.sub(r"!?\[([^]]+)\]\([^)]+\)", r"\1", value)).strip()


def terms(query):
    return {x for x in re.findall(r"[a-z]{3,}", query.lower()) if x not in STOP}


def extract_sections(markdown):
    """Capture topical heading/paragraph samples; do not claim full boilerplate removal."""
    sections = []
    heading = "(unheaded)"
    for raw in markdown.splitlines():
        s = clean(raw)
        if not s or NAV.match(s) or s.startswith(("|", "<", "![", "---")):
            continue
        h = HEADING.match(s)
        if h:
            heading = clean(h.group(1))[:160]
            continue
        if len(s) < 45 or s.count("http") > 1:
            continue
        sections.append({"heading": heading, "text": s[:700]})
    return sections


def classify(heading, sections):
    text = " ".join([heading] + [s["text"] for s in sections[:12]]).lower()
    if "webinar" in text:
        return "webinar_or_event_content"
    if "course" in text or "training" in text:
        return "course_or_training_content"
    return "related_search_result_unverified"


def analyze():
    source = OUT / "competitor_evidence.json"
    if not source.exists():
        raise RuntimeError("Missing competitor evidence: do not fabricate comparisons")
    evidence = json.loads(source.read_text(encoding="utf-8"))
    results = []
    for page in evidence.get("pages", []):
        row = {"query": page.get("query", ""), "position": page.get("position"),
               "url": page.get("url"), "title": page.get("title"),
               "capture_status": page.get("status"), "classification": "not_reviewable",
               "classification_basis": "No captured body evidence",
               "query_relevant_excerpts": []}
        if page.get("status") == "captured":
            filename = page.get("markdown_file", "")
            path = OUT / filename
            if not filename.startswith("competitor_") or "/" in filename or not path.is_file():
                row["classification_basis"] = "Captured markdown file is unavailable"
            else:
                content = path.read_text(encoding="utf-8", errors="replace")
                sections = extract_sections(content)
                row["classification"] = classify(page.get("title", ""), sections)
                row["classification_basis"] = "Provisional topic-based classification, not an AI judgment"
                ts = terms(page.get("query", ""))
                ranked = sorted(sections, key=lambda s: len(terms(s["heading"]+" "+s["text"]) & ts), reverse=True)
                row["query_relevant_excerpts"] = [
                    {"heading": s["heading"], "quote": s["text"],
                     "matched_terms": sorted(terms(s["heading"]+" "+s["text"]) & ts)}
                    for s in ranked[:5]
                ]
                row["body_sections_considered"] = len(sections)
        results.append(row)
    report = {"source": "competitor_evidence.json and captured Markdown",
              "method": "Deterministic evidence extraction; no paid APIs or AI model",
              "warning": "Excerpts and labels do not establish ranking causes, recommendation reasons or content quality.",
              "competitors": results}
    (OUT / "competitor_content_review.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    lines = ["# STEP 3 - Competitor Content Review (Evidence Only)", "",
             "Provisional categories and direct page excerpts; **not** ranking-cause analysis.", ""]
    for r in results:
        lines += [f"## {r['title'] or r['url']}", "",
                  f"- Query: {r['query']}",
                  f"- Google position: {r['position']}",
                  f"- Capture: {r['capture_status']}",
                  f"- Provisional type: {r['classification']}", ""]
        for s in r["query_relevant_excerpts"]:
            lines.append(f"- [{s['heading']}] {s['quote']}")
        lines.append("")
    (OUT / "COMPETITOR_CONTENT_REVIEW.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"STEP 3 evidence reviewed: {sum(bool(r['query_relevant_excerpts']) for r in results)} pages with excerpts; 0 paid API calls")


if __name__ == "__main__":
    analyze()
