"""Optional upstream GEO diagnostics; no new SEO/GEO scoring rules or API calls.

GEO access is useful for any audited URL. Coherence, authority and sitemap
audit only run for website scope when a verifiable sitemap exists.
"""
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import requests

ROOT = Path("reports/step4")
ROOT.mkdir(parents=True, exist_ok=True)


def run(name, args, timeout=150):
    output = ROOT / (name + ".txt")
    log = ROOT / (name + ".log")
    try:
        with output.open("w", encoding="utf-8") as stream:
            p = subprocess.run(args, stdout=stream, stderr=subprocess.PIPE,
                               text=True, timeout=timeout, check=False)
        log.write_text(p.stderr[-5000:], encoding="utf-8")
        return {"status": "completed" if p.returncode == 0 else "failed",
                "exit_code": p.returncode, "file": str(output), "log": str(log)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__}


def discover_sitemap(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname:
        return None
    root = "https://" + p.netloc
    for path in ("/sitemap.xml", "/sitemap_index.xml"):
        candidate = root + path
        try:
            response = requests.get(candidate, timeout=12, allow_redirects=False,
                                    headers={"User-Agent": "SEO-GEO-Audit/2.0"})
            if response.status_code != 200 or len(response.content) > 1000000:
                continue
            xml = ElementTree.fromstring(response.content)
            if xml.tag.split("}")[-1] in ("urlset", "sitemapindex"):
                return candidate
        except (requests.RequestException, ElementTree.ParseError, ValueError):
            continue
    return None


def main():
    target = os.environ["AUDIT_URL"]
    scope = os.environ.get("AUDIT_SCOPE", "landing_page")
    checks = {"geo_access": run("geo_access", ["geo", "access", "--url", target], timeout=90)}
    sitemap = None
    if scope == "website":
        sitemap = discover_sitemap(target)
        if sitemap:
            checks["geo_coherence"] = run(
                "geo_coherence", ["geo", "coherence", "--sitemap", sitemap])
            checks["geo_authority"] = run(
                "geo_authority", ["geo", "authority", "--sitemap", sitemap])
            checks["geo_sitemap_audit"] = run(
                "geo_sitemap_audit", ["geo", "audit", "--sitemap", sitemap,
                                      "--max-urls", "25", "--format", "json"], timeout=200)
        else:
            for name in ("geo_coherence", "geo_authority", "geo_sitemap_audit"):
                checks[name] = {"status": "skipped", "reason": "No verified sitemap available"}
    else:
        for name in ("geo_coherence", "geo_authority", "geo_sitemap_audit"):
            checks[name] = {"status": "not_applicable", "reason": "Landing page scope"}
    manifest = {"target": target, "scope": scope, "sitemap": sitemap,
                "source": "geo-optimizer-skill", "checks": checks,
                "no_live_ai_citation_test": True}
    (ROOT / "geo_extended_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# GEO Additional Upstream Diagnostics", "",
             "Native GEO Optimizer diagnostics only; no new model API calls.", ""]
    for name, result in checks.items():
        lines.append(f"- {name}: {result['status']}"
                     + (f" ({result['reason']})" if result.get("reason") else ""))
    (ROOT / "GEO_EXTENDED_DIAGNOSTICS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print("GEO extended diagnostics saved; unavailable checks labelled explicitly.")


if __name__ == "__main__":
    main()
