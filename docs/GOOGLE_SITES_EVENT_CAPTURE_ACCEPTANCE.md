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
