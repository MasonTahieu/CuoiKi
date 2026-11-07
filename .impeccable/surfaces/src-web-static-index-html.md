---
version: 1
slug: "src-web-static-index-html"
primary_target: "src/web/static/index.html"
related_targets: ["src/web/static/app.css","src/web/static/app.js"]
---

# Surface brief — Screener main screen

Scope: the single working screen of the web UI (`src/web/static/`), served by `src/web/server.py`. Mode: **Operate**.

Audience and job: brokers and retail investors keeping it open beside the price board for the whole session; the lecturer evaluating via demo/video and report screenshots. Job: see which stocks lead VN30 at a stated moment, which factor drives each, and whether the data can be trusted. Success: top names and their drivers readable in one glance; every unranked stock has one short reason; no warning boxes covering the result.

Constraints: Vietnamese copy; offline (no CDN, system font stack); read-only; synthetic data always labelled; course brief §6 elements all present; demo, replay and live modes; Streamlit app kept as fallback.

## Direction contract

THESIS: The category standard played straight: a dark Vietnamese stock dashboard at the finish of SSI iBoard and FireAnt/Simplize. It refuses the default Streamlit arrangement (sidebar of form controls, stacked info boxes, one generic bar chart) and any novelty world.

OWN-WORLD: Near-black blue ground #0B0E14, raised surfaces #131823 with 1px #232A36 seams, text #E7EAF0, secondary #A3ACBA. One blue accent #3B82F6 for selection and percentile scales. Market convention only where price moves: green #16C784 up, red #FF5C66 down, amber #F0B90B reference/stale. System UI sans (Segoe UI) with tabular figures; drawn 16px line icons.

STORY: The visitor reads group, moment and connection in the top bar, sees the leaders in the ranking table with four factor bars per row, clicks a row to read why it ranks there, and switches group, weights, foreign basis or moment without leaving the screen.

FIRST VIEWPORT: Top bar (product name and audience, VN30 badge, mode/source chips, connection pill and moment). Market-pulse band (VN30 index, breadth, basket value, foreign net). Status strip of four compact metrics. Toolbar of standard controls (weights, foreign basis, search, minimum score, replay run/moment, CSV). Left about 62%: sortable ranking table, rank and symbol at left, total score with stacked contribution bar, four factor cells with inline percentile bars, one status word. Right about 38%: selected-stock panel (score, factor breakdown, raw indicators, single-line reason) above a total-score chart.

FORM: Category standard (canon), chosen by the user in the direction round; reference products SSI iBoard, FireAnt/Simplize. seed:661706d535d8c3a5

Signature move: every factor cell is a percentile bar inside the table row, and the total-score bar is stacked by weighted contribution, so "why this rank" is visible without opening anything.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Real SSI data not yet available; live-mode freshness thresholds pending calibration.
