"""Run four Google searches from an existing or newly generated AI plan.
Uses the upstream search research module and its provider interface.
"""
import json, os
from pathlib import Path
import search_research as s
R=Path("reports")
def load(n): return json.loads((R/n).read_text(encoding="utf-8"))
def save(n,v): (R/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def main():
    profile,crawl,seo=load("business_profile.json"),load("crawl_completeness.json"),load("seo.json")
    s.validate_evidence(profile,crawl)
    plan_path=R/"search_intents.json"
    plan=load("search_intents.json") if plan_path.exists() else {}
    if plan.get("target")!=profile["source_url"] or len(plan.get("queries",[]))<4:
        if not os.getenv("OPENAI_API_KEY"): raise RuntimeError("Missing planning API key")
        plan={"target":profile["source_url"],"queries":s.create_plan(profile,s.create_client())}
        save("search_intents.json",plan)
    queries=[]
    for item in plan["queries"]:
        q=s.validate_query(item["query"],profile)
        if q.casefold() not in [x.casefold() for x in queries]: queries.append(q)
        if len(queries)==4:break
    if len(queries)!=4:raise RuntimeError("Four distinct queries required")
    batch=os.getenv("SEARCH_BATCH_ID","landing-pilot-v1")
    path=R/"google_serp.json"
    snapshot=load("google_serp.json") if path.exists() else {}
    if snapshot.get("target_url")==profile["source_url"] and snapshot.get("queries")==queries and snapshot.get("batch_id")==batch and len(snapshot.get("groups",[]))==4:
        print("Reusing Google snapshot; no new SerpApi requests");return
    key=os.getenv("SERPAPI_API_KEY")
    if not key:raise RuntimeError("Missing SERPAPI_API_KEY")
    groups=[]
    for i,q in enumerate(queries):
        hits,error=s.search_once(q,key)
        groups.append({"id":f"Q{i+1}","query":q,"results":hits,"error":error})
        save("google_serp.json",{"provider":"SerpApi - Google organic","target_url":profile["source_url"],"queries":queries,"batch_id":batch,"searched_at_utc":s.utcnow(),"chatgpt_tested":False,"groups":groups})
        if error:break
    save("SERPAPI_REQUEST_USAGE.json",{"attempted_requests":len(groups),"hard_limit":4})
    if any(g["error"] for g in groups):raise RuntimeError("Search provider failure; partial results saved; no retries")
if __name__=="__main__":main()
