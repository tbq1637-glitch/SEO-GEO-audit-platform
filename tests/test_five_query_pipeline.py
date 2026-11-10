"""No-API regression tests for the automatic seven-to-five-to-fifteen workflow."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auto_four_searches as automated
import competitor_evidence as collector
import fusion_report as fusion


def plan_candidates():
    intents = ["informational", "informational", "comparison", "local",
               "commercial", "navigational", "commercial"]
    return [{"id": "Q" + str(i), "query": f"How does topic {i} work?",
             "intent": intent, "reason": "Potential audience research",
             "status": "AI proposed"} for i, intent in enumerate(intents, 1)]


def test_seven_candidates_choose_five_diverse_questions():
    candidates = automated.choose_queries({"queries": plan_candidates()}, {})
    assert len(candidates) == 5
    assert len(set(x["intent"] for x in candidates)) == 5
    assert len(set(x["query"] for x in candidates)) == 5


def test_journey_stage_diversity_when_all_searches_are_informational():
    stages = ["understand", "discover", "evaluate", "participate",
              "practical", "understand", "discover"]
    candidates = plan_candidates()
    for candidate, stage in zip(candidates, stages):
        candidate["intent"] = "informational"
        candidate["journey_stage"] = stage
        candidate["expected_result_type"] = "webpage"
    selected = automated.choose_queries({"queries": candidates}, {})
    assert len(selected) == 5
    assert {x["journey_stage"] for x in selected} == set(stages[:5])


def test_video_only_candidate_is_lower_priority_for_html_competitor_audit():
    candidates = plan_candidates()
    stages = ["understand", "discover", "evaluate", "participate",
              "practical", "understand", "practical"]
    for candidate, stage in zip(candidates, stages):
        candidate["journey_stage"] = stage
        candidate["expected_result_type"] = "webpage"
    candidates[0]["expected_result_type"] = "video"
    selected = automated.choose_queries({"queries": candidates}, {})
    assert len(selected) == 5
    assert candidates[0]["query"] not in [x["query"] for x in selected]


def test_five_queries_execute_once_and_reuse_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(automated, "ROOT", tmp_path)
    monkeypatch.setenv("SERPAPI_API_KEY", "fake")
    monkeypatch.setenv("SEARCH_BATCH_ID", "auto-five-v2")
    profile = {"source_url": "https://target.example.org"}
    (tmp_path / "business_profile.json").write_text(json.dumps(profile))
    (tmp_path / "crawl_completeness.json").write_text(json.dumps({"status": "ok"}))
    (tmp_path / "search_intents.json").write_text(json.dumps({
        "target": profile["source_url"], "planning_version": 3,
        "queries": plan_candidates()
    }))
    monkeypatch.setattr(automated.search, "validate_evidence", lambda *_: None)
    monkeypatch.setattr(automated.search, "validate_query", lambda q, *_: q)
    calls = []
    def fake_search(query, key):
        calls.append(query)
        return ([{"url": f"https://example.org/{len(calls)}", "position": 1}], None)
    monkeypatch.setattr(automated.search, "search_once", fake_search)
    automated.main()
    snapshot = json.loads((tmp_path / "google_serp.json").read_text())
    assert len(snapshot["groups"]) == 5
    assert snapshot["selected_query_count"] == 5
    assert len(calls) == 5
    monkeypatch.setattr(automated.search, "search_once",
                        lambda *_: (_ for _ in ()).throw(
                            AssertionError("unexpected paid API call")))
    automated.main()
    assert json.loads((tmp_path / "SERPAPI_REQUEST_USAGE.json").read_text())[
        "cache_reused"] is True


def test_five_groups_three_successes_each_with_rank_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "OUT", tmp_path)
    groups = []
    for q in range(1, 6):
        rows = [{"url": f"https://q{q}-site{p}.org/page", "position": p,
                 "title": "Example"} for p in range(1, 7)]
        groups.append({"id": "Q" + str(q), "query": "question " + str(q),
                       "results": rows, "error": None})
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://target.example.org", "groups": groups
    }))
    calls = []
    def fetch(url):
        calls.append(url)
        # First rank blocked in every query, remaining three captures succeed.
        if "-site1." in url:
            return None, {"status": "access_blocked", "http_status": 403}
        return "<html><body>" + "Informative content " * 30 + "</body></html>", {
            "status": "ok", "http_status": 200
        }
    monkeypatch.setattr(collector, "fetch_html", fetch)
    monkeypatch.setattr(collector, "convert_html",
                        lambda html, i: ("Markdown content " * 50, 0, "local.log"))
    collector.main()
    result = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert len(result["per_query"]) == 5
    assert all(r["successes"] == 3 and r["new_requests"] == 4
               for r in result["per_query"])
    assert result["query_sample_count"] == 15
    assert result["unique_captured_urls"] == 15
    assert result["attempted_pages"] == 20
    assert all(r["max_successful_pages_per_query"] == 3
               for r in [result])


def test_cross_query_exact_url_reused_without_extra_http(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "OUT", tmp_path)
    common = "https://shared.example.org/research"
    groups = []
    for q in range(1, 6):
        urls = [common] + [f"https://q{q}-site{p}.org/page" for p in (2, 3)]
        groups.append({"id": f"Q{q}", "query": f"query {q}",
                       "results": [{"url": u, "position": i + 1}
                                   for i, u in enumerate(urls)],
                       "error": None})
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://target.example.org", "groups": groups
    }))
    calls = []
    monkeypatch.setattr(collector, "fetch_html",
                        lambda url: (calls.append(url) or
                                     "<html><body>" + "Text " * 100 + "</body></html>",
                                     {"http_status": 200}))
    monkeypatch.setattr(collector, "convert_html",
                        lambda html, i: ("Content " * 100, 0, "success.log"))
    collector.main()
    result = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert result["query_sample_count"] == 15
    assert result["unique_captured_urls"] == 11
    assert calls.count(common) == 1
    reused = [r for r in result["pages"] if r.get("reused")]
    assert len(reused) == 4
    assert all(r["status"] == "captured" and r.get("markdown_file") for r in reused)
    assert not any("excerpt" in row for row in reused)


def test_query_shortfall_is_truthful(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "OUT", tmp_path)
    groups = [{"id": f"Q{i}", "query": f"question {i}",
               "results": [{"url": f"https://q{i}.org/a", "position": 1}],
               "error": None} for i in range(1, 6)]
    (tmp_path / "google_serp.json").write_text(json.dumps({
        "target_url": "https://target.example.org", "groups": groups
    }))
    monkeypatch.setattr(collector, "fetch_html",
                        lambda *_: (None, {"status": "access_blocked"}))
    collector.main()
    result = json.loads((tmp_path / "competitor_evidence.json").read_text())
    assert result["query_sample_count"] == 0
    assert all(q["shortfall"] == 3 and not q["met_target"]
               for q in result["per_query"])


def test_fusion_sampling_retains_end_headings_and_discloses_omissions():
    sections = [{"heading": "Section " + str(i), "level": 2,
                 "blocks": [{"type": "p", "text": "Content " * 40}]}
                for i in range(80)]
    out = fusion.summarize_sections(sections, budget=4000)
    assert out["total_sections"] == 80
    assert out["outline"][-1]["heading"] == "Section 79"
    assert out["sampled"] is True
    assert out["limitation"]


def test_markdown_bound_keeps_beginning_middle_and_end():
    sample = "START" + ("a" * 6000) + "MIDDLE" + ("b" * 6000) + "END"
    out = fusion.spaced_markdown(sample, budget=1200)
    assert out["sampled"] and out["total_chars"] == len(sample)
    assert "START" in out["text"] and "END" in out["text"]
    assert "OMITTED SOURCE PORTION" in out["text"]
