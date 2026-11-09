# CHANGELOG — SEO + GEO Audit Platform

This file is the canonical record of functional changes. Entries distinguish implementation from validation.

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
