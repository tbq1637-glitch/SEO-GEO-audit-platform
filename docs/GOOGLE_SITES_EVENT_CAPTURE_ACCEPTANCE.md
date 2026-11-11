# Google Sites embedded-page evidence acceptance — Run #33 snapshot

Date: 2026-11-11 (Australia/Sydney)
Target: https://sites.google.com/view/careformeglenmoreparkwebinar
Archived source: SEO and GEO Audit Run #33, artifact `seo-geo-audit-33`, `target_source.html`.

## Purpose and provenance

This is an offline examination of the **real archived publisher HTML**, performed after the V2 Google Sites supplementary acquisition change. It is NOT another paid live audit, not an assertion that search engines can index the embedded text, and not yet confirmation that the entire V2 workflow forwarded every fact to its final report.

- Archived source HTML: 756,768 characters (decoded).
- `data-code` custom HTML embed: 647,197 characters.
- Visible candidate text after excluding scripts/styles/templates/noscript/SVG and collapsing whitespace: 7,967 characters.
- Text is below the supplemental parser's 40,000-character cap, so no candidate-text truncation occurs.
- Heading extraction: 19 H1–H4 headings, including the H1 `Care for Me. It’s Okay to Feel. Anxiety & Depression.`
- Recognized relevant links: 12 anchor entries, including repeated registrations, three speaker profiles, page anchors.
- Native SiteOne and GEO outputs remain incomplete, and were not rewritten.

## Event fact coverage against archived publisher source

All 16 checks were found in the archived HTML's extracted text or original links. Each is source presence, **not independent event/credential verification**.

| Check | Extracted evidence | Result |
| --- | --- | --- |
| Topic | Care for Me / Anxiety & Depression | Present |
| Date | Tuesday 24 November 2026 | Present |
| Time | 6.00–7.00 pm AEDT | Present |
| Delivery | Online via Zoom | Present |
| Price | Free to attend | Present |
| Speaker | Dr Hani Bittar | Present |
| Speaker | Arshia Razavizadeh | Present |
| Speaker | Dr Zhen Zhang | Present |
| Address | Level 2, 33 Town Terrace, Glenmore Park | Present |
| Contact email | wellbeing@amcgrp.co | Present |
| Webpage phone | (02) 4733 0222 | Present |
| Session structure | 45-minute talk + 15-minute Q&A | Present |
| Recording statement | A recording will be emailed afterwards | Present |
| Reward statement | Shopping centre voucher | Present |
| Certificate | Certificate of Participation, conditional on answering the webinar question | Present |
| Registration destination | https://us06web.zoom.us/webinar/register/WN_ouvTC_dNTSOqHrHz0UEPxQ | Present in HTML links; destination functionality not tested |

## Important cross-source discrepancy

The supplied event poster shows contact number `1300 935 523`. The archived webpage text instead shows `(02) 4733 0222` and does not contain the `1300` number. Do not silently reconcile these; the organizer should confirm whether both are intentional.

The webpage also includes details not stated on the poster (recording, Q&A allocation, voucher, certificate). They should be represented accurately if the final report discusses conversion and participation policies.

## Acceptance boundary and next action

- **PASS:** All checked key facts exist in the archived custom HTML and can be extracted as labelled supplementary evidence; no extracted candidate text was truncated.
- **NOT YET PROVEN:** Whether all details render visibly at runtime; whether Google or AI search crawlers can see/index embedded HTML; whether the Zoom link presently accepts registrations; whether the live page changed after Run #33; whether new V2 end-to-end AI search planning and final report actually reflect all the facts.
- **Next acceptance:** Use V2 only, check `target_embedded_evidence.json`, `business_profile.json`, `crawl_completeness.json`, and the final report in sequence. Stop if material facts are absent rather than accepting H1 + 400 characters alone. Do not alter SiteOne/GEO source code and do not merge to `main` until acceptance.


## 2026-11-11 — Semantic structure and relevance acceptance (archived source only)

**Source of truth:** the archived event webpage HTML from Run #33, not the separate event poster. Extraction is scoped to one Google Sites `data-code` custom HTML embed.

### Actual archived page structure

| Evidence dimension | Observed source | Preservation in V2 supplemental capture |
| --- | --- | --- |
| H1–H4 headings | 19 | Ordered headings with tag level |
| `section[id]` content blocks | 7: `top`, `conversation`, `speakers`, `programme`, `thank-you`, `faqs`, `register` | Per-section ID, CSS classes, heading outline and bounded text |
| Presenter cards | 3 `article` elements | Per-card headings, text and classes |
| FAQ | 3 `details > summary` elements | Question, answer and original open state |
| Timetable | 6 `time` elements: 6.00, 6.05, 6.20, 6.35, 6.45, 7.00 pm | Ordered time text |
| Links | 12 (includes four links to the same Zoom registration endpoint and three presenter profiles) | Label and actual href, not just link count |
| Images | 3 inline image assets: two organizational logos and a hero illustration | Source kind/hash and alt text; image bytes remain in original HTML, not duplicated into AI JSON |
| Inline style sheets | 3 | Source count and classes preserved; original CSS remains in archived HTML |
| Source text | 7,967 normalized characters | Full candidate text (below the 40,000-character cap), source SHA-256 |
| Source topic | Anxiety & Depression community wellbeing webinar | H1, section headings, title and body are thematically consistent; no unrelated secondary embed was identified in this snapshot |

The original source contains **one** `data-code` embed. No `iframe`, `form` or `button` elements were found inside this archived embedded document; registration is linked to the external Zoom webinar URL rather than being a native HTML form on this embedded page.

### Quality assurance logic added to V2

- The supplementary parser now retains page sections, speaker cards, FAQ question-answer pairs, ordered times, link labels/URLs, image metadata, section classes and structural counts, with original raw HTML preserved separately.
- A candidate is not accepted as fully captured by this extraction path if it exceeds configured text/structure limits or shows a truncated section.
- STEP 1 receives a provenance-labelled overview of sections and supporting structures; STEP 5 receives the original full supplementary evidence file.
- The existing SiteOne and GEO Optimizer scan results are left untouched, and cannot be represented as having directly seen the embedded H1 or body.

### Validation and limits

- Free GitHub Offline Structure Integration Tests **#69: Success, 62 tests passed**, including structural preservation and overflow rejection. No new API consumption was initiated.
- The archived source was independently examined for the counts and exact source constructs listed above. This does **not** demonstrate that Google renders/indexes those constructs, that current live text has not changed, or that styling and interactive functionality are identical in the live Google Sites frame.
- Preserve a separate visual audit for desktop/mobile layout, image rendering, FAQ toggles, Zoom registration accessibility and source-to-render parity. No screenshot-based live visual acceptance is claimed here.
- A new V2 end-to-end audit remains needed to verify propagation into STEP 1 business profile, search queries, competitive evidence and STEP 5 report. Stop and investigate if any material page facts/sections are absent. Do not update main before this acceptance.

