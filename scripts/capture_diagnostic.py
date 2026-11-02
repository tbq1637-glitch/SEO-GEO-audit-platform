"""Free STEP 3 capture diagnostic: no OpenAI, SerpApi, or SEO scores."""
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup

OUT=Path("reports/capture_diagnostic")
OUT.mkdir(parents=True,exist_ok=True)
# URLs observed in the already-paid Run 12 Google snapshot.
URLS=[
 "https://convergeinternational.com.au/webinars/",
 "https://www.mhfa.org.au/webinars",
 "https://services.unimelb.edu.au/counsel/workshops-and-webinars",
]
results=[]
for i,url in enumerate(URLS,1):
    row={"url":url,"id":i}
    try:
        r=requests.get(url,timeout=25,allow_redirects=True,headers={"User-Agent":"Mozilla/5.0 (compatible; SEO-GEO-Research/1.0)"},stream=True)
        data=b""
        for chunk in r.iter_content(chunk_size=8192):
            data+=chunk
            if len(data)>1500000:break
        content_type=r.headers.get("content-type","")
        row.update(http_status=r.status_code, final_url=r.url, content_type=content_type,
                   response_bytes=len(data), redirects=len(r.history))
        if r.status_code==200 and "text/html" in content_type.lower():
            raw=data.decode(r.encoding or "utf-8",errors="replace")
            soup=BeautifulSoup(raw,"html.parser")
            row["title"]=soup.title.get_text(" ",strip=True)[:200] if soup.title else ""
            for x in soup(["script","style","noscript"]):x.decompose()
            row["visible_text_chars"]=len(soup.get_text(" ",strip=True))
            html_file=OUT/f"page_{i}.html"
            html_file.write_bytes(data)
            md=OUT/f"page_{i}_converted.md"
            p=subprocess.run(["siteone-crawler",f"--html-to-markdown={html_file}",
                              f"--html-to-markdown-output={md}"],
                              capture_output=True,text=True,timeout=40,check=False)
            row["conversion_exit_code"]=p.returncode
            row["converted_characters"]=md.stat().st_size if md.exists() else 0
            row["conversion_error_tail"]=p.stderr[-1200:]
            # Avoid publishing the complete HTML; only report structural facts and
            # a short text sample from public pages.
            row["visible_text_sample"]=soup.get_text(" ",strip=True)[:350]
            html_file.unlink(missing_ok=True)
        else:
            row["status"]="non_html_or_unsuccessful_response"
    except (requests.RequestException, OSError, subprocess.TimeoutExpired) as e:
        row["error"]=type(e).__name__
    results.append(row)
(OUT/"CAPTURE_DIAGNOSTIC.json").write_text(json.dumps(results,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
for r in results:print(f"{r['id']}: HTTP={r.get('http_status')} HTML={r.get('visible_text_chars',0)} converted={r.get('converted_characters',0)}")
