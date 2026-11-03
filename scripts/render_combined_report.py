"""Render the finished Markdown audit as a human-readable HTML report.

Presentation only. Never changes the AI findings, citations or source data.
"""
import html
import re
from pathlib import Path
import markdown

ROOT = Path("reports")
CSS = """
:root{--bg:#f5f7fa;--ink:#16263a;--muted:#586b7e;--line:#dfe7ef;--blue:#235c9b}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.75 system-ui,-apple-system,'Segoe UI',Arial,sans-serif}
header{background:#102740;color:white;padding:32px clamp(20px,5vw,76px)}
header h1{font-size:clamp(26px,3vw,40px);margin:5px 0;color:white}
header p{color:#c8d8e7;margin:0}
.wrap{max-width:1480px;margin:auto;display:grid;grid-template-columns:235px minmax(0,1fr);gap:24px;padding:26px 30px}
aside{position:sticky;top:15px;height:fit-content;background:#fff;border:1px solid var(--line);border-radius:13px;padding:18px 12px}
aside strong{font-size:12px;color:var(--muted);padding:0 12px}
aside a{display:block;padding:8px 12px;color:#334961;text-decoration:none;font-size:13px;border-radius:8px}
aside a:hover{background:#edf4fa}
main{min-width:0}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:20px}
.stat{background:#fff;border:1px solid var(--line);border-radius:12px;padding:17px}
.stat b{font-size:25px;display:block}.stat span{font-size:12px;color:var(--muted)}
.content{background:#fff;border:1px solid var(--line);border-radius:15px;padding:clamp(20px,4vw,42px)}
h1{font-size:28px}h2{font-size:23px;color:#193f68;margin:40px 0 15px;border-bottom:1px solid var(--line);padding-bottom:12px;scroll-margin-top:20px}
h3{font-size:18px;color:#1b4a75;margin:25px 0 10px;scroll-margin-top:20px}
p{margin:10px 0 15px}a{color:#155c9a}ul,ol{padding-left:25px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0 24px}
th,td{padding:12px 14px;border:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#eaf1f8}tr:nth-child(even){background:#fafcff}
blockquote{border-left:4px solid #4b91c9;background:#f2f7fc;margin:18px 0;padding:14px 18px}
code{background:#edf2f6;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}
.note{background:#edf4fb;border:1px solid #d6e4f1;border-radius:10px;padding:14px 18px;margin-bottom:20px}
.priority{display:inline-block;font-size:12px;padding:2px 7px;border-radius:12px;font-weight:700}
.p0{background:#fde8e8;color:#a62a29}.p1{background:#fff1d7;color:#92580f}.p2{background:#e8f1f8;color:#41668a}
@media(max-width:1000px){.wrap{grid-template-columns:1fr;padding:18px}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}aside{position:static}}
@media(max-width:620px){header{padding:22px 18px}.content{padding:18px}table{display:block;overflow-x:auto}}
"""

def render(src: Path, dest: Path) -> None:
    text = src.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(body, "html.parser")
    headings = soup.find_all("h2")
    links = "".join(
        "<a href='#" + html.escape(h.get("id", ""), quote=True) + "'>" + html.escape(h.get_text(" ", strip=True)) + "</a>"
        for h in headings if h.get("id")
    )
    for h in soup.find_all(["h2", "h3"]):
        for match in re.findall(r"\bP[012]\b", h.get_text()):
            cls = match.lower()
            label = soup.new_tag("span", attrs={"class": f"priority {cls}"})
            label.string = match
            h.insert(0, label)
    # These summary values describe the audited Run 18 baseline only when
    # matching data is available, not assumed from future targets.
    import json
    def data(path):
        try: return json.loads((ROOT/path).read_text(encoding="utf-8"))
        except (OSError, ValueError): return {}
    technical = data("seo.json").get("qualityScores",{}).get("overall",{}).get("score","N/A")
    geo = data("geo.json").get("score","N/A")
    queries = len(data("google_serp.json").get("groups",[]))
    stats = [("SiteOne technical", str(technical)+"/10"), ("GEO readiness", str(geo)+"/100"),
             ("Google queries", str(queries)), ("AI SEO", "See native SiteOne report")]
    cards = "".join(f"<div class='stat'><b>{html.escape(v)}</b><span>{html.escape(k)}</span></div>" for k,v in stats)
    title = "SEO + GEO Competitive Audit"
    note = ("Google positions are search snapshots, not proven ranking causes. "
            "Actual ChatGPT Search citation measurement is not claimed.")
    dest.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>"+title+"</title><style>"+CSS+"</style></head><body>"
        "<header><h1>"+title+"</h1><p>Evidence-based SEO / GEO search competitiveness report</p></header>"
        "<div class='wrap'><aside><strong>REPORT SECTIONS</strong><nav>"+links+"</nav></aside>"
        "<main><div class='stats'>"+cards+"</div><div class='note'>"+note+"</div>"
        "<div class='content'>"+str(soup)+"</div></main></div></body></html>",
        encoding="utf-8"
    )

if __name__ == "__main__":
    render(ROOT/"SEO_GEO_COMBINED_REPORT.md", ROOT/"SEO_GEO_COMBINED_REPORT.html")
