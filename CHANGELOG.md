# CHANGELOG — SEO + GEO Audit Platform

This file is the canonical record of functional changes. Entries distinguish implementation from validation.

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
