# CHANGELOG — SEO + GEO Audit Platform

## 2026-11-11 — Source-first semantic capture verification (V2 only)

### Scope
- The user's only comparison source is the public Google Sites activity page; the event poster is excluded from this acceptance and from all field reconciliation.
- Prioritize content, semantic structure, links, source relevance and truncation checks before allowing downstream SEO/GEO recommendations. This does not imply pixel-exact live rendering or search-engine indexability.

### Change and tests
- Enhanced the conditional `scripts/embedded_page_evidence.py` sidecar to capture ordered section IDs/classes/headings/text, speaker article cards, FAQ question-answer/open states, timeline time elements, link references, image hashes/alt labels, native style/script counts, and per-source integrity metadata. Preserve raw HTML separately.
- Strengthened `scripts/crawl_completeness_audit.py` to reject truncated supplementary content; strengthened STEP 1 business identification evidence to pass a bounded structural overview. The STEP 5 evidence loader already receives the full supplementary JSON sidecar.
- Fixed whitespace normalization in section/FAQ/timetable extraction. No changes were made to SiteOne Crawler/GEO Optimizer sources, the search provider, the final model, or the STEP 5 high-reasoning prompt.
- Independently inspected Run #33 archived HTML: one Google Sites custom embed, 7 sections, 19 headings, 3 speaker cards, 3 image elements, 3 FAQ items, 6 timeline `time` elements, and 12 links; 7,967 extracted candidate-text characters with no configured truncation.
- GitHub Offline Structure Integration Tests **Run #69 succeeded: 62 tests passed**, including semantic structure retention and rejecting over-limit content. No paid end-to-end testing was launched.
- Details and accepted evidence boundaries are documented in `docs/GOOGLE_SITES_EVENT_CAPTURE_ACCEPTANCE.md`.

### Remaining gates
- Full layout (CSS rendering, desktop/mobile, card/FAQ interactions, image display) requires an actual rendered-page inspection; semantic parsing and saved source are not equivalent to screenshot validation.
- The next real V2 audit must verify that STEP 1, search planning and final STEP 5 report correctly use the captured event content. Do not claim completed end-to-end analysis or promote to `main` until this is verified.
- `main` is unchanged.

## 2026-11-11 — Real archived Webinar content verification (offline)

- Independently examined original `target_source.html` from GitHub Actions Run #33 (not a synthetic page). Source HTML contained one 647,197-character Google Sites `data-code` custom embed with 7,967 extracted candidate text characters and 19 H1–H4 headings, including the page's actual H1.
- Confirmed **16/16 targeted fact-presence checks** in the archived publisher source: topic, date, AEDT time, Zoom delivery, free status, all three presenter names, event/clinic address, email, webpage telephone, 45-minute talk plus 15-minute Q&A, recording note, shopping-centre voucher, certificate condition, and exact Zoom registration URL from a source anchor. The extracted text is under the 40,000-character bound and is not truncated.
- Recorded source facts, evidence boundaries, source-versus-poster telephone discrepancy, and next acceptance checks in `docs/GOOGLE_SITES_EVENT_CAPTURE_ACCEPTANCE.md` (commit `0ae377f`). The poster lists `1300 935 523` while the archived page lists `(02) 4733 0222`; do not silently reconcile them.
- This confirms archived **source content extraction**, not independent truth of the event, link functionality, live rendering, search-engine visibility, or field-level propagation into a fresh end-to-end report. Do not present the 16/16 checks as full-site completeness.
- No SiteOne/GEO source changes, no paid API audit, and no main-branch update were performed.

## 2026-11-11 — Google Sites embedded content supplemental recovery (V2 only)

### Confirmed diagnosis
- Real event landing page `https://sites.google.com/view/careformeglenmoreparkwebinar` failed the full audit at STEP 2–3 in GitHub Actions Run #33, before any new Google SERP requests; content completeness had verdict `NEEDS REVIEW - DO NOT USE FOR AI YET`.
- Native SiteOne completed an HTTP 200 crawl but recorded no H1, extracted only 809 Markdown characters; its existing browser recovery yielded approximately 575 characters. GEO Optimizer's native text extraction was likewise sparse. These native results are preserved rather than rewritten.
- The archived original target HTML contains an explicit Google Sites `data-code` custom HTML embed (roughly 647 KB), with a real embedded H1 and approximately 8K characters of candidate text. This is page-source evidence, **not proof that ordinary search crawlers can extract, index, or render that content**.

### Implementation (no upstream source changes)
- Added `scripts/embedded_page_evidence.py` to inspect up to five bounded Google Sites custom embeds, extract separately sourced H1/headings, candidate textual content, supported links and source hashes, with an explicit non-native-content warning. It is not used for other hosts.
- In `scripts/business_identification.py`, attempt this supplemental capture only for `sites.google.com` when the ordinary HTML has no H1 or unusually little visible text. Preserve raw `target_source.html` and SiteOne browser output, and pass separately labelled embed content to business identification.
- In `scripts/crawl_completeness_audit.py`, when a valid HTTP-200, non-blocked Google Sites page has sufficiently substantive embedded candidate HTML with a real H1, permit further analysis with the explicit verdict `CONTENT CAPTURED - GOOGLE SITES EMBED; NATIVE SEO DATA INCOMPLETE`. Keep the original native H1, crawl status, and source caveat unchanged.
- In `scripts/fusion_report.py`, make the saved `target_embedded_evidence.json` available to the final model separately from original SEO/GEO scanner findings. No changes to third-party SiteOne Crawler or GEO Optimizer, STEP 5 request model/transport, competitive sampling rules, or external search APIs.
- Added `tests/test_embedded_page_evidence.py` and wired it into `ci-structure.yml`. Offline Structure Integration Tests **#62: Success, 60 tests passed**. No paid tests were triggered for this patch.

### Risks / next acceptance
- These tests confirm the intended parser/guard behavior on local synthetic fixtures, but do not constitute a new end-to-end test on Google Sites. Check the next audit's captured text, title, event details, H1, and publisher-embedded evidence against the displayed page before trusting its final SEO/GEO conclusions.
- This is a controlled, conditional supplementary extraction stage; it does not prove website-wide completeness or search-engine indexing. Missing or blocked native captures remain visible in the report.
- The user-facing workflow remains only URL + scope. `main` remains unchanged until V2's new behavior is accepted.
- Other named Google Sites layouts, nested runtime-injected frames, or embedded scripts may need separate handling; do not broaden this recovery without evidence.

## 2026-11-11 — Release candidate promotion from V2 to main

### Release decision and evidence
- V3 comparison branch completed full five-step audit in GitHub Actions Run #30 (success): five Google query groups, 15/15 query samples from 14 distinct captured competitor URLs, SiteOne browser recovery, video metadata processing, visual analysis and a completed high-reasoning STEP 5 report using OpenAI background polling.
- V3 STEP 5-only replay Run #29 independently succeeded on preserved Run #26 evidence. Previous synchronous failures are retained in Runs #26 and #27 for provenance.
- Subsequent workflow cleanup removed temporary `mode`, `source_run_id` and the STEP 5-only job, leaving the normal URL + scope interface. Offline Structure Integration Tests Run #54 passed (56 tests) after this cleanup.
- No further paid end-to-end audit was run after the entrypoint cleanup. This is an explicit release validation limitation, not a claimed additional live test.
- Existing SiteOne model-input compaction remains exactly as tested in V3; full source JSON remains archived. Its necessity and complete fidelity are not separately established, and no further trimming is part of this release.
- The V2 development branch was aligned to the V3 accepted code at commit `9c8876b`. The pre-promotion main head was `1daac3b`; GitHub comparison showed the V2 head was ahead and not behind. This release is intended as a fast-forward of main, preserving the existing commit history.

### Follow-up and deferred work
- Keep the free CI workflow, the canonical full audit workflow and historical test evidence. Do not delete GitHub workflow histories just because experimental entrypoints were removed.
- Publisher caption retrieval did not trigger in Run #30; real caption validation remains outstanding.
- SiteOne repeated Facebook resource paths and complete losslessness of the model-facing SiteOne table selection remain separate review items, not release blockers.
- Redundant V3 experiment branch refs may be removed after confirming they have no independent commits; leave a recoverable V2 development branch. Do not treat branch deletion as deletion of historical run artifacts.

## 2026-11-11 — V3 full-run acceptance and temporary dispatch cleanup

### Acceptance evidence
- Full public-page audit Run #30 completed STEP 1–5 on `v3-step5-comparison`: five query groups, 15/15 successful query-page placements (14 unique URLs), SiteOne browser recovery, bounded video metadata, visual evidence, and a completed high-reasoning STEP 5 with an HTML report.
- STEP 5 ran one background create request and 17 retrieval polls, with zero recorded poll connection errors; actual usage was 114030 input tokens and 12969 output tokens. This validates the tested public-page path, not all possible website or transcript cases.
- Compared Run #30 to V2 Run #28: the new report includes per-query/cross-query comparisons, video provenance, 11 implementation backlog items, and clear launch approval checks. Source limitations remain explicitly disclosed. Length alone is not treated as evidence of quality.
- Original SiteOne JSON remains complete in the artifact; model-facing SiteOne native tables remain selected/compacted as in the successfully tested V3. This compaction has NOT received an independent necessity or exhaustive-losslessness demonstration. No further compaction or extraction changes are made in this cleanup.
- Run #30 recorded no attempted publisher transcript downloads; real-world caption retrieval is still unverified.

### Workflow cleanup
- Removed temporary `mode` and `source_run_id` dispatch controls and the `step5_only` GitHub Actions job. The public full audit has only required URL and scope inputs again.
- Restored unconditional full audit job while preserving its existing STEP 1–5 steps, background STEP 5 transport, Google research cache and report artifact upload.
- Updated offline workflow contract tests to cover the restored public input contract and five-step execution order, without calling SerpApi/OpenAI.
- Offline Structure Integration Tests #54: Success (56 tests passed). Earlier #52/#53 failed on obsolete/over-broad workflow test assertions during this cleanup; no paid calls were made.

### Remaining limitations
- Do not claim a new paid end-to-end run after dispatch cleanup; the same STEP 1–5 commands remain, but the cleaned entry point was verified offline only.
- Keep `main` untouched until explicit release acceptance. Do not delete branch history before safe integration; legacy diagnostic source files are not public workflow entrypoints.
- SiteOne Facebook export path proliferation and real-world text-track acquisition remain separate investigations; they did not prevent Run #30 completion.

## 2026-11-11 — V3 STEP 5 background transport isolation (development)

### Confirmed comparison
- V2 Run #28 succeeded end-to-end on the historical Run #23 commit (39354e1), including the STEP 5 integrated report. V3 Run #27 failed twice after about 269 seconds with APIConnectionError, despite valid archived inputs.
- This establishes a reproducible version-level difference, but does not yet prove that request size, a fixed network idle limit, or any specific upstream component caused the disconnect.
- Preserve the existing V3 evidence collection, model, high reasoning effort, report instructions and SiteOne JSON compaction unchanged during this isolated transport experiment. No content extraction or scoring changes were made.

### Changed
- Added `call_fusion_background` in `scripts/fusion_api.py`: one short-lived OpenAI Responses background creation request and polling of the same response ID, rather than keeping a single synchronous HTTP request open for the entire high-reasoning task.
- Save the response ID and status in `step5_fusion_diagnostics.json`. Polling connection errors retry only retrieval of the same response; uncertain creation errors never trigger a second paid submission automatically.
- Require completed, nonempty output before publishing. Preserve the existing synchronous `call_fusion` implementation for comparison.
- Route V3 STEP 5 through the new transport in `scripts/fusion_report.py`; leave STEP 1–4, all evidence content, the model, reasoning effort, and prompts unchanged.
- Added mocked offline tests for successful polling, intermittent poll disconnect, uncertain creation, incomplete response and polling deadline. Enabled V3 branch in the offline CI workflow.

### Validation and limits
- Offline CI and a live V3 STEP 5 replay are pending; do not claim this change has repaired the real API failure.
- No SerpApi or OpenAI request was initiated for this code change. The old working V2 branch and `main` remain unchanged.
- `mode` and `source_run_id` are temporary testing controls and must be removed after experimental acceptance; the production workflow should return to URL + scope.
- Background processing retains response data for retrieval; verify organizational data retention policy before using it on private customer data. This audit is limited to public-page evidence.

This file is the canonical record of functional changes. Entries distinguish implementation from validation.

## 2026-11-10 — STEP 5 Only recovery for failed Run #26 (V2 development)

### Failure confirmed
- GitHub SEO and GEO Audit **Run #26** completed STEP 1–4, five Google searches, 15/15 query competitor samples, DOM recovery, bounded video evidence and completed visual analysis, but `Integrated evidence-based fusion report` failed with `openai.APITimeoutError` after the old 240-second request timeout.
- Original Run #26 Artifact `seo-geo-audit-26` was preserved and includes the full pre-fusion evidence; rebuilding those steps or re-spending Google search credits is unnecessary.
- A timeout does **not** prove an API quota problem or that the failed request was unbilled.

### Added / changed
- `scripts/fusion_api.py`: bound individual STEP 5 requests to 300 seconds by default (allowed 90–420), at most **two attempts total** with zero SDK retries, and an eight-second pause only for selected transient failures (timeout, connection error, server error, rate limit). Reject incomplete/empty model output instead of publishing partial results.
- Record `reports/step5_fusion_diagnostics.json`: request-input digest, per-source serialized character counts, rough non-billing token estimate, model, attempt durations, error types, response status and actual API token usage when returned. Do not log raw page text or API keys.
- Retain all original SiteOne JSON files in artifacts while passing native SEO/AI SEO essential sections and selected original scan tables to STEP 5, eliminating redundant crawler tables from the high-reasoning prompt. Keep all query and competitor text/structure sampling and GEO evidence limits visible; no new SEO/GEO score is invented.
- `scripts/validate_fusion_replay.py`: verify source Actions run ID, repository, V2 branch, audit workflow, completed run and exact unexpired Artifact via read-only GitHub REST; then verify target URL, five completed search groups and archived competitor Markdown before spending OpenAI API tokens.
- Existing `.github/workflows/audit.yml` now supports two selectable modes: `full` (the existing complete audit, unchanged steps) and `step5_only` (read Run #26's archived evidence using GitHub Actions download-artifact, run only fusion and HTML rendering, then upload an output-only replay Artifact). `source_run_id` defaults to `42764278546`; user must enter the archived target URL for consistency. No SiteOne/GEO scanner installation, SerpApi, website crawling, video extraction or visual AI runs in this mode.
- Add offline tests for transient timeout followed by successful retry, twice-failed cap, incomplete-output rejection, diagnostics redaction, input de-duplication, replay evidence validation, source branch checks, valid YAML and no-upstream-paid-steps in STEP5-only mode.
- Fail closed on missing or mismatched dispatch mode: the full audit job only runs if `mode=full` is explicitly selected; `step5_only` only runs if explicitly selected, protecting against accidental paid full runs when UI inputs are not available.

### Status / limitations
- **Offline Structure Integration Tests #50: Success**, including the new replay/API tests, YAML syntax/operation safety checks, and Python validation. Real STEP 5 replay has **not yet been executed or compared against Run #23**.
- If the GitHub Workflow UI does not expose the new V2 mode after branch selection, do **not** run the default full audit. Investigate dispatch UI availability without silently modifying `main`.
- Only V2 was updated. Do not merge to `main` until a successful archived-input replay and report comparison.
- A timeout can still recur; no guarantee that a second attempt is free or successful. Output quality is not judged until the actual report is available.

## 2026-11-10 — Run #25 video test fixture compatibility repair

### Diagnosis
- Run #25 stopped in the **STEP 2-3 Offline safety tests** step: 37 tests passed and two video tests failed, before any of the five SerpApi Google searches or STEP 5 final report.
- Both failures traced to a synthetic `<video><track ...></video>` tag without a `src` or nested media `<source>`. The original metadata reader skipped the whole video node, so the linked publisher caption was not treated as video-context evidence even though the track URL was present.
- This is a real extraction-coverage corner case, not proof that the public caption endpoint is unavailable.

### Changed
- Retain `<video>` context when its media source URL is absent, including the explicit `has_media_url=false` marker and any caption tracks. Preserve the distinction between a video element, a playable video, and a transcript actually read.
- Do not increase text-track budgets, enable video/audio downloads, or count media metadata as an HTML comparator.

### Validation
- Offline Structure Integration Tests **#44 succeeded** on the patched V2 commit; syntax and existing regression tests pass.
- Run #25 did **not** reach the full audit or produce a new integrated comparison report. A fresh workflow dispatch on the new commit is required; rerunning jobs from #25 would use the old failed revision.
- Only `v2-search-competitiveness` was changed; `main` remains unchanged.

## 2026-11-10 — Conditional video metadata and publisher transcript evidence (development)

### Added
- `scripts/video_evidence.py` collects Google organic **video result metadata** (title, snippet, URL, query and position) without downloading video media or pretending to know its content.
- From the original, already-collected HTML, preserve video/iframe embeds, available poster/accessible labels, published `VideoObject` fields, basic social-video metadata, and explicitly linked captions/transcript files. Recognize linked video URLs found in SiteOne's optionally rendered Markdown after conditional browser recovery.
- If a relevant publisher page contains a video and lacks substantial main-page explanation, optionally retrieve **only publicly and directly linked** .vtt/.srt/.txt content (bounded 120 KB, HTTPS/public DNS, no redirects). Save source URLs, language/kind where supplied, capture time, source HTML SHA-256, transcript status, and full text if obtained.
- Cap direct text-track attempts at **one per query and three per audit**. No YouTube caption scraping, complete video/audio download, speech-to-text, frame decoding, or additional OpenAI/SerpApi call.
- Prioritize eligible text tracks from pages associated with predicted video/mixed search intents, then other pages; this is only an evidence-budget ordering heuristic, not an asserted real search ranking or a video relevancy score.
- STEP 5 now receives bounded, source-labelled video evidence, distinct from completed HTML competitor samples, and may mention what a verified publisher transcript actually says without claiming video playback.
- Add offline tests for video metadata, native schema/track extraction, transcript limits, unsafe or non-text URLs, no model/search calls, video host separation from HTML quota and SiteOne-rendered video links.

### Changed
- Distinct video-platform SERP URLs (YouTube, Vimeo etc.) remain separate results, but are tagged `video_reference` and do **not** count toward three successfully captured HTML pages per query. Subsequent eligible HTML URLs are considered normally.
- Ensure the video module runs after optional SiteOne DOM recovery so recovered Markdown links can be recorded.
- Refine automatic 7→5 search question selection: business-relevance order from AI remains primary, choose diverse customer-journey stages, and prefer ordinary/mixed webpage evidence to video-only predictions **within the same stage** rather than excluding video-only topics categorically.
- This run records video evidence source/capture dates and hashes but does **not** create an uncontrolled cross-workflow cache. Existing Google snapshot caching and exact-URL reuse remain intact.

### Validation / limitations
- **Offline Structure Integration Tests #43: Success** (2026-11-10), including the new video safety and provenance tests.
- Live mixed-content website and a valid published-caption test are still required before claiming real-world transcript extraction works.
- YouTube and other platform search results may offer only titles/snippets; missing subtitle links, restricted APIs and publisher access controls remain genuine coverage limitations.
- `main` is unchanged; modifications are confined to `v2-search-competitiveness`. The real Google and AI citation workflows, comprehensive video understanding and automatic video-to-text conversion are not introduced.

## 2026-11-10 — Competitor evidence fidelity, customer-journey planning and browser export recovery

### Confirmed source and findings
- The "one competitor URL per domain per query" rule was self-authored in `scripts/competitor_evidence.py`, **not** imposed by upstream SiteOne or GEO Optimizer. Run #23 Q5 erroneously discarded seven distinct YouTube URLs as duplicate domains; video content still requires a distinct evidence strategy and is **not** presented as captured HTML.
- All seven Run #23 generated candidate queries had `informational` as their generic search intent, so the previous automatic diversity selector could not distinguish registration/service discovery from general learning.
- Run #23 archived six native SiteOne browser JSONs reporting `MarkdownExporter error: Export error: Markdown export directory not set` despite subprocess return code 0. This identifies a missing CLI export directory argument, **not evidence that all six websites failed to render**.
- The prior Run #20 report included stronger ready-to-edit copy, hosting-specific SEO implementation guidance, verification criteria and launch preconditions. Run #23 improved competition coverage but weakened parts of these practical deliverables.

### Changed
- Permit distinct URLs from the same host within one query. Deduplicate exact URLs and reuse previously fetched text across queries. Do not mistake host similarity for duplicate content; keep status and source provenance.
- STEP 2 now distinguishes **customer journey stage** (`understand`, `discover`, `evaluate`, `participate`, `practical`) from generic SEO query intent, and records AI-predicted `expected_result_type` (`webpage`, `mixed`, `video`). Five-query selection prefers coverage across these stages and generally prioritizes webpage-oriented evidence. Such predictions are **not actual SERP evidence**.
- Increment plan/cache versions so old intent classifications cannot be silently reused as valid new research.
- Correct `--markdown-export-dir` plus `--markdown-export-single-file` for both the target-page SiteOne preflight and conditional competitor browser recovery.
- Check SiteOne's native JSON `summary.items` for `MarkdownExporter` errors in addition to process exit code and substantive output. Keep error diagnostics and prevent login/browser compatibility pages from silently becoming confirmed page evidence.
- When a browser successfully recovers competitor text, promote it only to a query with a remaining 3-page quota. Archive the rendered source, reconcile `competitor_evidence.json` and its human-readable summary, and keep excess successful renders as supplemental rather than increasing query sample counts past three.
- Strengthen STEP 5 instructions to restore **source-grounded implementation detail**: concrete suggested English copy (title/intro/FAQ where supported), page-specific changes, explicit verification/acceptance checks, platform-specific robots/canonical/redirect guidance when applicable, and real-launch approval prerequisites. Do not invent unknowns to meet formatting goals.

### Validation and remaining limitations
- Focused no-API tests **passed** in GitHub Actions Offline Structure Integration Tests #33 (2026-11-10): customer-journey diversity, video-priority handling, multiple URLs on one domain, SiteOne MarkdownExporter failure recognition, correct CLI flags in target/competitor browser recovery, and post-browser quota/report consistency.
- Browser export recovery and the improved report instructions **still require a new live end-to-end acceptance run**. We have not claimed that previously blocked Facebook/YouTube pages are now accessible or that actual AI citations were checked.
- Q5/video SERP result suitability and direct-competitor role scoring are deferred for separate design discussion. The existing text/visual analysis limits remain otherwise intact.
- Changes are on `v2-search-competitiveness` only; do not merge into `main` before the user accepts the new results.

## 2026-11-10 — STEP 2/3 seven candidates to five searches and 5×3 captures (development)

### Added and changed
- STEP 2 automatically proposes **seven safe, relevant, ranked search-intent candidates**, then selects **five** with intent diversity; preserves selection decisions and unused candidate records. Staff review/approval is a **future optional mode**, not yet implemented.
- STEP 3 runs **exactly five** Google organic searches at most once each per matching cached snapshot, with up to **ten ranked organic results per query** (SerpApi AU/en).
- Each query independently seeks **three successfully captured competitor pages**, skipping inaccessible/invalid pages and advancing to the next-ranked result. Results are capped by available top-ten candidates and per-query attempt limits: fifteen are a target, not guaranteed.
- Deduplicate domains **within each query** for diversity. An identical URL appearing under multiple queries is fetched and converted only once; the Google position and query membership are still retained separately. Track both unique URLs and per-query samples.
- Preserve all captured HTML, SiteOne Markdown, metadata, structure and visual samples in run artifacts. STEP 5 uses a **bounded, provenance-labelled** cross-page sample plus a full section heading outline and clearly records any truncation rather than assuming unseen content is absent.
- Expand the GitHub audit job timeout from 25 to 50 minutes to accommodate bounded extra page attempts. Screenshot scope and timeout settings are unchanged.
- Version the research cache for the new five-query workflow so an old four-query snapshot cannot be silently accepted.
- Add offline regression tests for seven-to-five planning, five searches/cache reuse, per-query 3-page ranked fallback, duplicate URL reuse, honest shortfalls and bounded STEP 5 evidence.

### Not changed
- No live AI search citation verification, no new local business competitor ranking metric, and no automatic website modification.
- SiteOne/GEO Optimizer remain authoritative third-party scanners. Dynamic browser capture remains conditional, and screenshot/vision reviews remain representative, not 15×2 per run.
- `main` is unchanged pending offline and live validation.

### Acceptance pending
- Offline GitHub Actions CI **passed**: Offline Structure Integration Tests #21 on 2026-11-10 (Python syntax validation + all enabled regression tests). Live five-query/15-sample audit **not yet performed**.
- After successful 5×3 rollout, conduct the separately requested **three-generation quality comparison** against the pre-structure baseline (~Run #20), Run #22 and the new report, including improvements **and regressions**, source evidence, omissions and responsible code changes. Do not begin this comparison before the user supplies/confirms all three applicable reports.

## Planned acceptance — Three-generation report comparison (after 5×3)

**Deferred by user request; do not perform this comparison until the 5-query × 3-successful-pages update is implemented and tested.**

Comparison baselines:
- **Baseline A:** pre-structural/visual audit, approximately Run #20 (confirm exact report and audited URL before comparing).
- **Baseline B:** post-structural extraction, conditional rendering, and screenshot-based visual analysis, Run #22; user-supplied `SEO_GEO_COMBINED_REPORT.html` is available in this conversation.
- **Baseline C:** future complete 5×3 audit report, not generated yet.

Acceptance should compare source evidence, not just report length or scores: target URL, snapshot date, query count/intent, per-query captured pages, HTML/Markdown completeness, headings/table/FAQ relationships, dynamic evidence, SEO/GEO coverage, visual evidence, factual precision, relevant competitor selection, source attribution, actionable recommendations, contradictions, omissions, false positives, costs and report clarity.

**Required conclusions:** identify actual improvements, regressions and unchanged issues, connect each to specific pipeline/code changes where evidence supports causality, and distinguish changed search snapshots/targets from implementation effects. Do not infer quality improvement merely from more samples or more text.

## 2026-11-10 — Run #22 screenshot performance investigation (no runtime changes)

### Investigated
- Archived the evidence-based analysis in `docs/SITEONE_SCREENSHOT_PERFORMANCE_AUDIT.md`.
- Four competitor viewport tasks exceeded the 100-second subprocess limit while producing valid images; the last logged resource progress was Kirana desktop 67/135, mobile 83/134, COPMI desktop/mobile 95/109.
- Identified the existing screenshot-only limits `--workers=1` and `--max-reqs-per-sec=1` as a plausible bottleneck for pages with many assets. This is a hypothesis strongly supported by the resource-progress logs, not a confirmed root cause.

### Deferred pending verification
- No screenshot timeouts, crawler request rates, API calls, or screenshot selection logic have changed.
- Proposed an isolated, no-API diagnostic comparing the current parameters with `--workers=2 --max-reqs-per-sec=3` on one previously observed competitor page; preserve the 35/100-second limits and validate screenshots and evidence before adopting any changes.
- No end-to-end re-run is required to inspect this hypothesis.

## 2026-11-10 — Screenshot timeout diagnosis and bounded fallback

### Changed
- Keep the existing SiteOne per-page browser timeout (35 seconds) and Python process timeout (100 seconds) unchanged. Desktop and Mobile remain separately evaluated.
- After each SiteOne process exits or times out, inspect current-attempt screenshot JPEGs for stable size, full decoding, expected viewport width and reasonable dimensions. A validated image may be reused even if the SiteOne process timed out; neither a stale nor a corrupt image can be counted.
- Save JSON diagnostics to each viewport's existing `siteone.log`: elapsed time, process exit/timeout, stderr/stdout tails where available, screenshot checks and image provenance. Exact internal SiteOne stall phase remains unknown without upstream traces.
- Prefer competitor pages from distinct search queries. If no *complete* visual AI review was obtained, continue with the next already text-captured competitor URL, up to four competitor attempts to obtain two completed visual reviews.
- Permit an explicitly single-viewport review if one screenshot is verified while the other fails, without pretending that both viewports were inspected.
- Preserve all previously captured text/structure evidence regardless of visual screenshot outcome; no new Google searches or OpenAI retries are triggered by this fallback.

### Explicit limitations and verification
- Visual fallback uses existing competitor candidates only and does not expand STEP 3's current Google search budget or three-page text capture limit.
- Up to five screenshot page attempts (one target + four competitors) can occur, each with up to two independent 100-second processes; budget and overall GitHub Actions timeout may still restrict execution.
- Diagnostic data does not by itself establish the upstream SiteOne internal cause of a timeout.
- Offline regression tests for timeout-recovered JPEG, corrupt/stale image rejection, candidate limits and fallback conditions **passed** in GitHub Actions Offline Structure Integration Tests #15 (2026-11-10). Actual screenshot timeout recovery in a live workflow remains unverified.
- The earlier 3,000 output-token cap and OpenAI completion-state check remain in effect.

## 2026-11-10 — Visual AI output completeness fix

### Changed
- Raise the per-page image-based visual review output cap from 1,100 to 3,000 tokens. This is an API output ceiling, not a monetary quota or guaranteed consumption.
- Inspect the Responses API `status` and `incomplete_details` before recording a review as `analysed`.
- Preserve partial model text in a separate `*_PARTIAL.md` diagnostic file if the response is incomplete; do **not** pass it to STEP 5 as a completed visual analysis.
- Store model response status, incomplete reason and input/output token usage in the existing visual manifest.

### Explicitly unchanged
- Keep SiteOne `--browser-timeout=35` and Python `subprocess.run(timeout=100)` exactly as before, pending investigation of screenshot timeouts.
- Screenshot capture and retry logic have **not** been repaired or altered.

### Verification
- Implementation committed to V2; real API execution and the full audit are **not yet validated**.

## 2026-11-10 — Selective screenshot evidence and visual AI analysis (development)

### Added
- SiteOne native browser-based desktop and mobile full-page screenshots, for **the target URL plus up to two captured comparison pages** (six screenshots maximum per run).
- AI image review of the actual screenshots, explicitly considering first-screen clarity, hierarchy, mobile overflow, calls to action, and visibly supported usability observations.
- A source-labelled visual evidence manifest, independent per-page screenshot analysis, and bounded image inputs; the report records image-model usage tokens where available.
- Integrate completed visual observations into STEP 5 alongside original SiteOne/GEO scan evidence; incomplete screenshot/AI results remain `not_tested`, `failed` or `unavailable`.
- Offline tests for sample count, query diversity, screenshot capture failure, and absence of model calls when there is no image.

### Limits / design decisions
- This is **representative-sample visual analysis**, not screenshot/vision analysis of all candidate pages. Competitor selection prefers different search queries; no unverified claim that every chosen site is a direct competitor.
- The full-page image may be downscaled for vision input; original screenshot files are retained. Pixel analysis is qualitative and never presented as evidence of ranking causes.
- A failure to obtain screenshots or an API exception cannot be counted as a successful layout audit.
- Existing STEP 3 Google-search and competitor-sample counts remain unchanged.
- No branch merges beyond the explicit `main` baseline synchronization; this new visual component remains on V2 until tested.

### Validation status
- Code and offline test cases committed; no confirmed passing GitHub Actions result or real SiteOne screenshot/model demonstration yet.
- End-to-end acceptance requires checking archived desktop/mobile images, per-page reports and final fused report in one run.

## 2026-11-10 — Structural evidence and conditional rendering (development integration)

### Added
- Preserve bounded source HTML for the audited URL and captured competitor pages.
- Extract section headings, paragraph/list membership, table rows/cells, links, metadata and JSON-LD evidence into `reports/step3_structure/`.
- Detect likely client-rendered or incomplete page bodies; run SiteOne Chromium DOM recovery only when evidence warrants it; keep screenshots disabled for this phase.
- Use SiteOne-rendered DOM evidence in STEP 1 business identification before search planning when the target HTML is JS-dependent.
- Record static-versus-rendered extraction outcomes and mark unavailable browser recovery explicitly.
- GEO Optimizer native `geo access` checks for each target; site-scope `geo coherence`, `geo authority` and sitemap audit where a sitemap is verified.
- Hand evidence manifests, selected section-level evidence and successful rendered content to STEP 5 with bounded prompt input and clear provenance.
- Offline regression tests for static/dynamic detection and section/table preservation, plus a separate no-API CI workflow.

### Changed
- Keep original HTML snapshots previously deleted after SiteOne Markdown conversion.
- Avoid re-running target browser recovery when STEP 1 already captured rendered Markdown.
- Treat missing competitor content as missing, not negative evidence of the website's content.
- Apply public HTTPS and DNS validation before optional competitor browser recovery.
- Preserve site-specific rather than one-size-fits-all GEO diagnostics.
- Continue to keep the previous four-search, three-successful-competitor workflow limits: increasing to five queries / fifteen samples is **not yet implemented**.

### Validation
- GitHub code committed and inspected.
- Offline CI workflow authored; passing execution has **not yet been independently verified**.
- Chromium execution, DOM completeness, GEO command compatibility, screenshot/visual AI analysis, and full end-to-end paid workflow remain **unverified**.
- No live ChatGPT Search citation verification.

### Branch policy
- `main`: requested synchronization baseline.
- `v2-search-competitiveness`: single continuing development branch.
- `v3-upstream-coverage`: former temporary branch; all of its commits are already an ancestor of V2, not a separate alternative implementation.
- On every future update, add a dated entry listing additions, changes, removed functionality, test evidence, known limitations and commit/branch state before merging.

## 2026-11-03 — Integrated full-pilot and report presentation
- STEP 1 business identity; automated AI search planning and four SerpApi Google organic searches; competitor HTML-to-Markdown evidence; upstream SiteOne SEO/GEO Optimizer analysis; high-reasoning evidence fusion.
- Replaced legacy user-facing plan/live_2 and manual query inputs with URL and Scope.
- Added source-keyed research cache, combined report markdown and human-readable HTML layout with navigation/tables.
- Run #18/#19 verified end-to-end for landing-page scenarios; sitewide AI coverage and real AI citations remain incomplete.
