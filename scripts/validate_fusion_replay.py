"""Safely replay a completed SEO/GEO audit without re-running earlier steps.

Remote phase checks GitHub workflow/artifact provenance with Actions read-only
API. Local phase validates downloaded JSON evidence before paid STEP 5.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path("reports")
REQUIRED = (
    "business_profile.json", "search_intents.json", "google_serp.json",
    "competitor_evidence.json", "seo.json", "geo.json",
    "siteone_page.md", "step4/siteone_ai_seo.json"
)


def verify_remote(run_id, repo, token):
    if not re.fullmatch(r"[1-9][0-9]{5,15}", str(run_id)):
        raise RuntimeError("Source run ID must be a positive GitHub Actions run number ID")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo or ""):
        raise RuntimeError("Invalid repository")
    if not token:
        raise RuntimeError("GitHub Actions read token unavailable")

    def github_json(path):
        req = Request(
            "https://api.github.com/repos/" + repo + path,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "User-Agent": "seo-geo-step5-replay"},
        )
        try:
            with urlopen(req, timeout=20) as response:
                return json.load(response)
        except (HTTPError, URLError, ValueError) as exc:
            raise RuntimeError("Could not verify source run metadata: " +
                               type(exc).__name__) from exc

    run = github_json("/actions/runs/" + str(run_id))
    if run.get("repository", {}).get("full_name", "").casefold() != repo.casefold():
        raise RuntimeError("Source run does not belong to this repository")
    if run.get("head_branch") != "v2-search-competitiveness":
        raise RuntimeError("Source run is not from the approved V2 development branch")
    if (str(run.get("path", "")).split("@")[0]
            .removeprefix(".github/workflows/") != "audit.yml"):
        raise RuntimeError("Source is not the complete SEO and GEO Audit workflow")
    if run.get("status") != "completed" or run.get("conclusion") not in ("failure", "success"):
        raise RuntimeError("Source audit must be completed, success or partial failure")

    expected = "seo-geo-audit-" + str(run.get("run_number"))
    artifacts = github_json("/actions/runs/" + str(run_id) + "/artifacts").get("artifacts", [])
    matches = [item for item in artifacts
               if item.get("name") == expected and not item.get("expired")
               and item.get("size_in_bytes", 0) > 1000]
    if len(matches) != 1:
        raise RuntimeError("Expected source audit artifact is missing, expired or ambiguous")
    return {"source_run_id": int(run_id), "source_run_number": run["run_number"],
            "source_commit": run.get("head_sha"), "source_artifact_id": matches[0]["id"],
            "source_artifact_name": expected,
            "source_created_at": run.get("created_at"),
            "source_conclusion": run.get("conclusion"),
            "repository": repo}


def verify_local(root=ROOT):
    root = Path(root)
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise RuntimeError("Missing saved audit evidence: " + ", ".join(missing))
    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8"))
    profile = read("business_profile.json")
    snapshot = read("google_serp.json")
    competitors = read("competitor_evidence.json")
    url = profile.get("source_url", "")
    if not url.startswith("https://") or snapshot.get("target_url") != url:
        raise RuntimeError("Source business profile and Google snapshot target mismatch")
    expected_url = os.environ.get("EXPECTED_TARGET_URL", "").strip()
    if expected_url and url.rstrip("/") != expected_url.rstrip("/"):
        raise RuntimeError("Saved audit target differs from the explicitly requested URL")
    if len(snapshot.get("groups", [])) != 5 or any(g.get("error") for g in snapshot["groups"]):
        raise RuntimeError("Expected five completed source Google query groups")
    if (competitors.get("source_snapshot") != "google_serp.json"
            or not competitors.get("pages") or not competitors.get("per_query")):
        raise RuntimeError("Saved competitor capture manifest is incomplete")
    if not any(r.get("status") == "captured" for r in competitors["pages"]):
        raise RuntimeError("No previously captured competitor body evidence")
    # Check referenced source files, never attempt a new network crawl.
    valid = 0
    for row in competitors["pages"]:
        if row.get("status") != "captured":
            continue
        file_name = row.get("markdown_file", "")
        if not re.fullmatch(r"competitor_[0-9]+\.md", file_name):
            raise RuntimeError("Unexpected archived competitor filename")
        if not (root / file_name).is_file():
            raise RuntimeError("Missing archived competitor Markdown: " + file_name)
        valid += 1
    if not valid:
        raise RuntimeError("No validated captured competitor Markdown")
    return {"target_url": url, "query_count": 5,
            "captured_query_samples": sum(r.get("status") == "captured"
                                          for r in competitors["pages"]),
            "unique_captured_urls": len({r.get("url") for r in competitors["pages"]
                                         if r.get("status") == "captured"}),
            "all_sources_from_existing_artifact": True}


def main():
    phase = sys.argv[1] if len(sys.argv) == 2 else None
    if phase == "remote":
        record = verify_remote(os.environ.get("SOURCE_RUN_ID", ""),
                               os.environ.get("GITHUB_REPOSITORY", ""),
                               os.environ.get("GH_TOKEN", ""))
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as stream:
                stream.write("run_number=" + str(record["source_run_number"]) + "\n")
        Path("replay_source_remote.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("Verified source run", record["source_run_id"],
              "artifact", record["source_artifact_name"])
    elif phase == "local":
        record = verify_local()
        remote = Path("replay_source_remote.json")
        if remote.is_file():
            record.update(json.loads(remote.read_text(encoding="utf-8")))
        (ROOT / "STEP5_REPLAY_PROVENANCE.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("Saved evidence validated for five query groups and",
              record["captured_query_samples"], "previous competitor samples")
    else:
        raise SystemExit("Usage: validate_fusion_replay.py remote|local")


if __name__ == "__main__":
    main()
