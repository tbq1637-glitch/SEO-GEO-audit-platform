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
BATCH = "auto-five-v2"


def load(name):
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save(name, value):
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")


def choose_queries(plan, profile):
    """Preserve AI relevance order, with journey coverage and media context.

    Input ordering is the model's relevance ranking. A webpage is preferred
    over a video-only result prediction *within the same journey stage*;
    media type cannot override the relevance ordering of every other stage.
    """
    unique, seen = [], set()
    for candidate in plan["queries"]:
        query = search.validate_query(candidate["query"], profile)
        if query.casefold() not in seen:
            seen.add(query.casefold())
            unique.append({**candidate, "query": query})
    if len(unique) < CANDIDATES:
        raise RuntimeError("Seven distinct safe candidate queries required")

    # Group by customer-journey stage while preserving the rank of its
    # first appearance in the AI's ordered proposal.
    grouped = {}
    for candidate in unique:
        stage = candidate.get("journey_stage") or candidate.get("intent") or "unknown"
        grouped.setdefault(stage, []).append(candidate)

    selected = []
    for options in grouped.values():
        # For the SAME user goal, prefer useful HTML or mixed evidence if
        # available; do not discard an otherwise unique video-only goal.
        choice = next(
            (x for x in options if x.get("expected_result_type") != "video"),
            options[0])
        selected.append(choice)
        if len(selected) >= SELECTED:
            break

    # Fill remaining slots by their original AI relevance order.
    for candidate in unique:
        if len(selected) >= SELECTED:
            break
        if candidate not in selected:
            selected.append(candidate)
    if len(selected) != SELECTED:
        raise RuntimeError("Exactly five search queries required")
    return selected


def main():
    profile = load("business_profile.json")
    search.validate_evidence(profile, load("crawl_completeness.json"))
    plan = load("search_intents.json")
    if (plan.get("target") != profile["source_url"]
            or len(plan.get("queries", [])) < CANDIDATES
            or plan.get("planning_version") != 3):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY missing for seven-query planning")
        plan = {"target": profile["source_url"], "planning_version": 3,
                "selection_method": "AI relevance ranked, diverse journey stages; media preference within same stage",
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
                       "journey_stage": chosen[i].get("journey_stage"),
                       "expected_result_type": chosen[i].get("expected_result_type"),
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
