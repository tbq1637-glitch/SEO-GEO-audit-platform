"""Automatic seven-candidate planning and five distinct Google queries.

Five is a hard SerpApi request limit for this job. Cached snapshots are
reused only when URL, query order, batch and five successful groups agree.
No automatic retries or extra searches when the provider reports an error.
"""
import json
import os
from pathlib import Path

import search_research as search

ROOT = Path("reports")
CANDIDATES = 7
SELECTED = 5
BATCH = "auto-five-v1"


def load(name):
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save(name, value):
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")


def choose_queries(plan, profile):
    """Prioritize AI-ranked candidates, with distinct search intent coverage."""
    unique, selected, seen_queries, seen_intents = [], [], set(), set()
    for candidate in plan["queries"]:
        query = search.validate_query(candidate["query"], profile)
        if query.casefold() not in seen_queries:
            seen_queries.add(query.casefold())
            unique.append({**candidate, "query": query})
    if len(unique) < CANDIDATES:
        raise RuntimeError("Seven distinct, safe candidate queries required")
    # Preserve the model's ranked order, first covering unique intent labels.
    for candidate in unique:
        intent = candidate.get("intent", "")
        if intent and intent not in seen_intents:
            selected.append(candidate)
            seen_intents.add(intent)
        if len(selected) == SELECTED:
            break
    for candidate in unique:
        if len(selected) == SELECTED:
            break
        if candidate not in selected:
            selected.append(candidate)
    if len(selected) != SELECTED:
        raise RuntimeError("Exactly five approved automatic queries required")
    return selected


def main():
    profile = load("business_profile.json")
    search.validate_evidence(profile, load("crawl_completeness.json"))
    plan = load("search_intents.json")
    if (plan.get("target") != profile["source_url"]
            or len(plan.get("queries", [])) < CANDIDATES
            or plan.get("planning_version") != 2):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY missing for seven-query planning")
        plan = {"target": profile["source_url"], "planning_version": 2,
                "selection_method": "AI relevance rank, diversify intents, pick five",
                "queries": search.create_plan(
                    profile, search.create_client(), candidate_count=CANDIDATES)}
    chosen = choose_queries(plan, profile)
    selected_queries = [entry["query"] for entry in chosen]
    chosen_set = set(selected_queries)
    for item in plan["queries"]:
        item["status"] = ("Selected for Google search"
                          if item["query"] in chosen_set else "Unselected candidate")
        item["selected_for_google"] = item["query"] in chosen_set
    plan["selected_queries"] = selected_queries
    save("search_intents.json", plan)

    batch = os.getenv("SEARCH_BATCH_ID", BATCH)
    snapshot = load("google_serp.json")
    if (snapshot.get("target_url") == profile["source_url"]
            and snapshot.get("batch_id") == batch
            and snapshot.get("queries") == selected_queries
            and len(snapshot.get("groups", [])) == SELECTED
            and all(not g.get("error") for g in snapshot.get("groups", []))):
        save("SERPAPI_REQUEST_USAGE.json", {
            "attempted_requests": 0, "hard_limit": SELECTED,
            "cache_reused": True,
        })
        print("Five-query Google snapshot reused; no new SerpApi requests")
        return

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SERPAPI_API_KEY")
    groups = []
    for i, query in enumerate(selected_queries):
        hits, error = search.search_once(query, api_key)
        groups.append({"id": f"Q{i+1}", "query": query,
                       "intent": chosen[i].get("intent"),
                       "results": hits, "error": error})
        save("google_serp.json", {
            "provider": "SerpApi - Google organic",
            "target_url": profile["source_url"],
            "queries": selected_queries, "batch_id": batch,
            "searched_at_utc": search.utcnow(),
            "chatgpt_tested": False, "groups": groups,
            "candidate_count": CANDIDATES, "selected_query_count": SELECTED,
        })
        save("SERPAPI_REQUEST_USAGE.json", {
            "attempted_requests": len(groups), "hard_limit": SELECTED,
            "cache_reused": False,
        })
        if error:
            raise RuntimeError("Google search provider failed; partial evidence kept; no retry")
    print(f"Five Google searches completed; {sum(len(x['results']) for x in groups)} organic records")


if __name__ == "__main__":
    main()
