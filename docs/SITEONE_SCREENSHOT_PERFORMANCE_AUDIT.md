# SiteOne Screenshot Runtime Diagnostic — Run #22

**Date:** 2026-11-10  
**Scope:** Evidence review only; no runtime changes or paid API calls.  
**Source:** GitHub Actions run #22, artifact `seo-geo-audit-22`, per-viewport `step4/visual/**/siteone.log`.

## Findings

| Page and viewport | Runtime | Screenshot | SiteOne final reported progress at termination |
| --- | ---: | --- | --- |
| Target demo desktop | 12.67 s | Valid | Exit code 0 |
| Target demo mobile | 3.50 s | Valid | Exit code 0 |
| Kirana desktop | 100.00 s | Valid, recovered after timeout | 67 / 135 resources |
| Kirana mobile | 100.01 s | Valid, recovered after timeout | 83 / 134 resources |
| COPMI desktop | 100.00 s | Valid, recovered after timeout | 95 / 109 resources |
| COPMI mobile | 100.00 s | Valid, recovered after timeout | 95 / 109 resources |

All four timed-out processes had created valid JPEGs before the hard process timeout.

Screenshot subprocess arguments currently include:

```text
--single-page
--workers=1
--max-reqs-per-sec=1
--browser
--browser-wait=networkidle
--browser-timeout=35
--screenshots
--screenshot-mode=full-page
```

The official SiteOne documentation explicitly says `--single-page` still crawls the page **and its assets** (it stops following other page links). `--workers` and `--max-reqs-per-sec` constrain the crawler's ordinary resource work. The last captured progress in three-digit resource lists plus identical 100-second termination across four attempts is consistent with resource enumeration/request throttling remaining after successful image generation.

## Diagnosis and limits

**Likely bottleneck:** whole SiteOne resource-audit process under one-worker, one-request-per-second limits, not necessarily an inability to render or screenshot the target page. The log does not prove an exact internal blocking stage, and progress timestamps are not available. The browser timeout is 35 seconds but does not cap total SiteOne process work.

**Not established:** whether resource processing would complete with increased concurrency or whether some pages have additional asynchronous blocking. No live SiteOne performance A/B test has been run.

## Proposed narrow experiment (not implemented)

Run a **standalone screenshot-only diagnostic**, with no OpenAI or SerpApi, using one previously observed competitor URL, comparing the existing parameters against a conservative SiteOne-only screenshot setting:

- Baseline: `--workers=1 --max-reqs-per-sec=1`
- Candidate: `--workers=2 --max-reqs-per-sec=3`
- Retain `--browser-timeout=35` and 100-second subprocess timeout.
- Preserve `--single-page`, browser rendering, image quality and output dimensions.
- Observe elapsed seconds, screenshot verification, total/processed resource count, and process exit.
- Limit load to the sampled page and 3 requests/sec; stop testing when conclusive.
- Do not skip resource types or weaken page completeness evidence solely to improve runtime.

If the candidate consistently finishes faster and screenshots remain valid, consider only then changing the screenshot-specific parameters in `scripts/visual_evidence.py`. Keep the base SiteOne and GEO audit limits unchanged.

## References

- SiteOne CLI options: https://crawler.siteone.io/configuration/command-line-options/
- GitHub Run #22: https://github.com/tbq1637-glitch/SEO-GEO-audit-platform/actions/runs/42734857462
