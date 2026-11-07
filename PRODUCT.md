# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python is required by the course brief. Decided 06/11/2026 with the user: the UI moves from Streamlit to a dedicated web front end (hand-written HTML/CSS/JS, no build step, no CDN) served by a Python standard-library HTTP server that exposes the existing pipeline as JSON. No new Python packages; must run offline on Windows x64, CPython 3.13, from `RUN_APP.ps1`. The Streamlit app stays available as a fallback until the new UI is verified.

## Users

Two audiences, weighted equally (confirmed 06/11/2026):

- **Retail investors and brokers in Vietnam** using it during the trading session to narrow a watch list inside VN30 before deeper research, and to explain to themselves or a client why a stock stands out.
- **The course lecturer grading the final project** through a live demo or recorded video, who must understand quickly what data comes in, how it is processed, and why a stock ranks where it does.

All UI copy is Vietnamese.

## Product Purpose

An intraday multi-factor screener: four factors (momentum from the open, liquidity from matched value + 3-level book depth + spread, relative foreign net flow, 3-level order-book imbalance) are percentile-ranked within the VN30 basket at one moment of the continuous LO session, then weighted into a total score. Success: the user sees which stocks lead the group and which factor drives each one, and can trust (or see why not to trust) the data behind it.

## Positioning

Not a price board. It ranks within a group at a stated moment and refuses to rank when data is missing, stale, outside the LO session, or from an unverified source, and it says why per stock. Every result is traceable to a source, run, moment, configuration and cohort, and can be replayed.

## Operating Context

- Modes: `demo` (synthetic fictional tickers), `replay` (choose a recorded run and a moment), `live` (reads the local store on a 10/30 s refresh while a separate collector writes it).
- Data source: SSI FastConnect API V3 (stream + REST); FCData v2 and VPBankS NEO kept as fallbacks/history. Real keys not yet issued; synthetic data must always be labelled as such.
- Time zone: Asia/Ho_Chi_Minh (UTC+7) everywhere.
- Evaluated alongside a PDF report (8–12 pages with screenshots) and a short demo video.

## Capabilities and Constraints

- Scope is VN30 only (HNX30 dropped 07/11/2026: thin liquidity, 43% missing foreign data); weights 25/25/25/25 or momentum-tilted 40/20/20/20; foreign factor by value (default) or volume.
- Filters by symbol and minimum score apply after ranking and never change the cohort.
- Minimum 10 eligible stocks per group; ties share a rank; no silent reweighting when a factor is missing.
- Per-stock quality reasons and warnings (missing, stale, invalid, lagging, session not LO, no baseline after reconnect, V3-specific warnings).
- CSV export carries source, run, moment, method, config and cohort IDs.
- Read-only: no orders, no account data.
- Must show: product name, purpose and audience, last data update and connection state, ≥3 summary metrics, ≥2 visualizations, filters, an analysis/ranking area, brief method and limitations, clear empty/disconnected/error states (course brief §6).

## Brand Commitments

- Name in use: "Bộ lọc cổ phiếu đa yếu tố" / "VN30 Screener".
- Must state it is an academic analysis tool, not investment advice, and that scores are not probabilities of price increase.
- Visual standard (user choice, 06/11/2026): the category standard played straight — a dark stock-dashboard in the convention Vietnamese investors already use, at the craft level of **SSI iBoard** and **FireAnt / Simplize**. No novelty world, no smuggled quirks.
- Avoid: long text blocks and stacked warning boxes covering the main result (user's stated failure mode).

## Evidence on Hand

- Synthetic datasets only: 24-ticker demo, 22-ticker V3 sample journal (`runtime/v3-synthetic.sqlite`), sample SSI journals. No real SSI data yet; never present synthetic results as market results.
- Existing screenshots in `runtime/task7-build/` and the submitted PDF/video show the current Streamlit UI.

## Product Principles

1. Explain the rank: a score is always shown with the factors that make it.
2. Honesty over completeness: an unranked stock with a stated reason beats a guessed score.
3. One moment, one cohort: every view names the group, moment and configuration it reflects.
4. Replayable: any result can be traced and reproduced from the stored record.
