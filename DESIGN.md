---
name: Bộ lọc cổ phiếu đa yếu tố (VN30 Screener)
description: A dark Vietnamese stock dashboard that ranks a group at one moment and shows why each stock ranks there.
colors:
  ground: "#0B0E14"
  surface: "#131823"
  surface-2: "#182030"
  raised: "#1D2535"
  seam: "#232A36"
  seam-2: "#2E3746"
  seam-hover: "#3A4556"
  text: "#E7EAF0"
  text-2: "#A3ACBA"
  text-3: "#8892A2"
  accent: "#3B82F6"
  accent-soft: "rgba(59, 130, 246, 0.16)"
  accent-ink: "#CFE0FF"
  accent-pressed: "#2563EB"
  on-accent: "#FFFFFF"
  change-up: "#7FB0FF"
  up: "#16C784"
  down: "#FF5C66"
  reference: "#F0B90B"
  warn-ink: "#F6D365"
  bad-ink: "#FFB4B9"
  factor-momentum: "#4C8DFF"
  factor-liquidity: "#31C2D6"
  factor-foreign: "#A48BFF"
  factor-imbalance: "#E58BC8"
typography:
  display:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, -apple-system, Roboto, \"Helvetica Neue\", Arial, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.2
    fontFeature: "tnum"
  headline:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  title:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.45
  display-sm:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.01em"
  clock:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 650
    lineHeight: 1.2
    fontFeature: "tnum"
  headline-sm:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.2
    fontFeature: "tnum"
  body-lg:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.45
    fontFeature: "tnum"
  body-sm:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  chart-label:
    fontFamily: "\"Segoe UI Variable Text\", \"Segoe UI\", system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    fontFeature: "tnum"
rounded:
  pill: "999px"
  panel: "10px"
  tabs-outer: "9px"
  tabs-inner: "7px"
  control: "6px"
  bar: "4px"
  bar-sm: "3px"
  swatch: "2px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  gap: "16px"
  page-x: "24px"
  row-height: "46px"
  control-height: "34px"
  panel-head: "48px"
  topbar: "60px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "34px"
  button-hover:
    backgroundColor: "{colors.surface-2}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "34px"
  button-icon-only:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    size: "34px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "34px"
  segmented-option-selected:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-ink}"
    rounded: "4px"
    padding: "0 12px"
    height: "28px"
  group-tab-selected:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.tabs-inner}"
    padding: "6px 18px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.text-2}"
    rounded: "{rounded.pill}"
    padding: "0 10px"
    height: "26px"
  chip-synthetic:
    backgroundColor: "rgba(240, 185, 11, 0.08)"
    textColor: "{colors.warn-ink}"
    rounded: "{rounded.pill}"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
  table-row:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    height: "46px"
    padding: "0 12px"
  table-row-selected:
    backgroundColor: "{colors.accent-soft}"
  stacked-total-bar:
    backgroundColor: "{colors.raised}"
    rounded: "{rounded.bar}"
    height: "8px"
    width: "140px"
  factor-percentile-bar:
    backgroundColor: "{colors.raised}"
    rounded: "{rounded.bar-sm}"
    height: "6px"
  rank-change:
    textColor: "{colors.change-up}"
    typography: "{typography.label}"
---

# Design System: Bộ lọc cổ phiếu đa yếu tố

## Overview

**Creative North Star: "The Session Desk"**

The category standard played straight: a dark Vietnamese stock dashboard at the finish of SSI iBoard and FireAnt/Simplize, built to sit open beside the price board for a whole trading session. The user chose this world over any novelty direction; its job is to look exactly as trustworthy as the tools brokers already use, then do one thing those tools do not: show why each stock ranks where it does, inside the row.

Density is a working-desk density: 46px table rows, 34px controls, 12–14px text, tabular figures everywhere. Depth comes from tonal steps of a near-black blue ground and 1px seams, not from shadows. Colour is spent with discipline in three separate jobs that never borrow from each other: one blue accent for selection and focus, four factor hues that encode the score split, and market green/red/amber only where price moves or data is stale.

Everything is offline: system UI sans, drawn 16px line icons from an inline SVG sprite, inline SVG charts, no web fonts, no CDN, and a CSP that forbids inline style attributes.

**Key Characteristics:**
- Near-black blue ground with tonal surfaces and 1px seams; flat, no decorative shadow.
- Three colour vocabularies with fixed jobs: accent (selection), factor palette (score composition), market colours (price and staleness).
- Every ranking row carries a contribution-stacked total bar plus four factor percentile bars.
- Exceptions speak, valid states stay silent; run-wide notes appear once.
- Segoe UI system stack with tabular figures; Vietnamese copy throughout.

## Colors

A cool near-black ground, one restrained blue for interaction, a four-hue factor palette for data, and the market's own green/red/amber held back for prices and freshness.

### Primary
- **Selection Blue** (accent): the only interactive accent. Primary button fill, focus outline (2px, offset 2px), active view-tab underline (inset 2px), sort-arrow colour, text caret and selection. At 16% alpha (accent-soft) it fills the selected table row and the pressed segmented option, whose label turns to Pale Selection Ink (accent-ink).

### Secondary: the Factor Palette
Four hues that mean one factor each, everywhere the factor appears: segments of the contribution-stacked total bar, the per-factor percentile bars in the table, the legend swatches, the detail-panel factor rows, the score chart's stacked bars, and the brand mark.
- **Momentum Blue** (factor-momentum): momentum from the open (Động lượng).
- **Liquidity Cyan** (factor-liquidity): matched value, book depth and spread (Thanh khoản).
- **Foreign Violet** (factor-foreign): relative foreign net flow (Dòng tiền ngoại).
- **Imbalance Orchid** (factor-imbalance): 3-level order-book imbalance (Cung–cầu).

### Tertiary: Market Colours
- **Session Green** (up): price above reference in the price chart and changes; also the "connected" status dot (with a 3px 18%-alpha halo).
- **Session Red** (down): price below reference; "bad" status dot and unranked-reason tag tone (text in Soft Red Ink, bad-ink).
- **Reference Amber** (reference): the dashed open/reference line in the price chart, stale data ages, the "warn" status dot, and the synthetic-data chip (text Warm Amber Ink, warn-ink; 8% fill, 45% border).

### Neutral
- **Session Night** (ground): page background and sticky top bar (at 94% opacity).
- **Panel Slate** (surface): panels, metrics strip, inputs, sticky table header, tab track.
- **Lifted Slate** (surface-2): button hover, notice banner, reasons box.
- **Track Slate** (raised): empty track behind every bar, selected group tab.
- **Seam** (seam) and **Strong Seam** (seam-2): 1px panel borders and row dividers; control borders and scrollbar thumb. Controls brighten to seam-hover on hover.
- **Pale Change Blue** (change-up): rank-rise deltas beside the rank and the "mới" tag; a lighter tint of the accent so it reads as information, not as a control.
- **Primary Ink** (text), **Secondary Ink** (text-2), **Tertiary Ink** (text-3): values; labels and notes; counts and icon tint.

### Named Rules
**The Three Vocabularies Rule.** Blue accent means "selected or focused", factor hues mean "this factor's share", green/red/amber mean "price moved or data is stale". A colour never crosses into another vocabulary's job.

**The Market Colour Is Earned Rule.** Green and red appear only where a price moves or a connection/status is stated. Scores are never coloured green or red; a high score is shown by bar length and the factor palette.

**The Change Is Not a Market Move Rule.** Rank and score changes against an earlier moment are not price moves: a rise uses Pale Change Blue (change-up) with an up chevron, a fall uses Tertiary Ink with a down chevron, "mới" marks a stock newly ranked. Never green or red.

**The Factor Constancy Rule.** A factor's hue is identical in the table, detail panel, chart, legend and brand mark. Factor colour is applied by class (c-momentum, c-liquidity, c-foreign, c-imbalance) or the matching hex in SVG, never improvised.

## Typography

**Display Font:** Segoe UI Variable Text (with Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial)
**Body Font:** the same system stack
**Label/Mono Font:** none; tabular figures (`font-variant-numeric: tabular-nums`) on the body make every number column align.

**Character:** The operating system's own sans, as the category does it: neutral, legible at 12px, and exactly what investors see in their trading software. Weight carries hierarchy (400/500/600/650/700), not family changes.

### Hierarchy
- **Display** (700, 26–30px): the selected stock's symbol (26px, +0.01em) and score (30px) in the detail panel; nowhere else.
- **Headline** (650, 22px, -0.01em): metric values in the status strip; 17px at ≤560px. The live clock sits at 18px/650.
- **Title** (650, 14–16px): product name (16px) and panel headings (14px).
- **Body** (400, 14px/1.45): default text, explanation line; method prose at line-height 1.6 capped at 75ch. Table cells 13–15px (symbol 700 +0.02em, total 15px).
- **Label** (600 or 400, 12px): field labels, table headers, chips, legend, metric captions, chart titles.
- **Chart label** (400, 11px): SVG axis and bar labels, fixed at 11px because charts are drawn at container pixel width rather than scaled.

### Named Rules
**The Tabular Figures Rule.** Every number is set in tabular figures and right-aligned in numeric columns, so scores, ranks and times never jitter as data updates.

## Layout

A sticky 60px top bar (brand left, VN30 badge centred, mode chips, connection and clock right) above a page with 16px vertical gap and 24px side padding. Below it: a four-cell metrics strip in one panel, a wrapping toolbar of labelled controls (aligned to their bottoms, gaps 12px by 18px), then the workspace.

The workspace is two columns, ranking panel left (1.7fr, about 62%) and a side column (min 340px) with the "why" panel above the total-score chart. The side column is sticky below the top bar.

Responsive behaviour:
- **>1180px:** two columns as above; every row shows the stacked total bar (140px) and four factor columns.
- **901–1180px:** two columns with a fixed 340px side panel; the four factor columns are hidden and the stacked total bar widens to 200px to carry the split; the top bar wraps status onto its own row.
- **≤900px:** single column; side panel flows below the table; metrics become 2x2; page padding 12px/16px. The table scrolls horizontally inside its panel.
- **≤560px:** the toolbar collapses into a "Bộ lọc và thời điểm" disclosure whose summary shows the current moment and weights; controls stack full-width; group tabs span the width; the CSV button goes icon-only; legend and legend note hide.

Spacing rhythm is 4/8/12/16 with 24px page gutters; component heights are fixed (rows 46px, quality rows 40px, controls 34px, panel heads 48px).

### Named Rules
**The Split Survives Rule.** When width forces columns out, the factor columns go first and the contribution-stacked bar grows to carry the factor split. "Why this rank" is never dropped from the row.

## Elevation & Depth

Flat by default. Depth is tonal: ground, surface, surface-2, raised, separated by 1px seams. Shadows appear only as functional state cues.

### Shadow Vocabulary
- **Selected tab lift** (`box-shadow: 0 1px 2px rgba(0,0,0,.35)`): the VN30 badge in the top bar.
- **Tab underline** (`box-shadow: inset 0 -2px 0 #3B82F6`): the active view tab.
- **Live halo** (`box-shadow: 0 0 0 3px rgba(22, 199, 132, .18)`): the connected status dot only.

### Named Rules
**The Seam Not Shadow Rule.** Panels separate from the ground by a tone step and a 1px seam. No drop shadows on panels, cards or menus.

## Shapes

Gently rounded and consistent: panels 10px, controls and buttons 6px, segmented options 4px, bars 3–4px with clipped overflow, legend and factor swatches 2px, chips and status dots fully round. Borders are always 1px. The group-tab track nests 7px buttons in a 9px track with 3px padding so the radii stay concentric.

## Components

### Buttons
Quiet and solid; the accent is reserved.
- **Shape:** 6px radius, 34px tall (30px in panel heads), 1px strong seam border.
- **Default:** panel-slate fill, 13px/600 label, optional 16px line icon at 8px gap.
- **Primary:** Selection Blue fill and border with white text (on-accent); pressed/hover steps down to accent-pressed. Used for the error state's retry action only.
- **Hover / Focus:** fill steps to surface-2 and border brightens; focus is the global 2px blue outline at 2px offset. Disabled at 45% opacity.
- **Icon-only:** 34px square for replay prev/next, reload, and the CSV button at ≤560px.

### Chips
- **Style:** 26px pills, 12px/600, strong-seam border, secondary ink. Show the mode (Demo/Replay/Live).
- **State:** synthetic data is an amber-tinted chip ("Dữ liệu giả lập"); an unverified source is a red-tinted chip. Chips are statements of provenance, never filters.

### Cards / Containers
- **Corner Style:** 10px.
- **Background:** Panel Slate with a 1px seam.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Internal Padding:** 14–16px; panel heads are 48px rows with a bottom seam.

### Inputs / Fields
- **Style:** 34px selects, search and number inputs on Panel Slate, 1px strong seam, 6px radius; labels 12px secondary ink above the control. Search carries an inset 16px magnifier icon.
- **Segmented control:** 2px-padded track; pressed option takes accent-soft fill with Pale Selection Ink at 600.
- **Focus:** global 2px blue outline.

### Navigation
- **Group badge:** a single raised VN30 chip at the top bar's centre with a muted ranked/members count (the HNX30 tab was removed when scope narrowed to VN30).
- **View tabs:** Xếp hạng / Chất lượng dữ liệu / Phương pháp as full-height text tabs in the panel head; active tab in Primary Ink with a 2px blue underline.

### Ranking Row (signature)
Each row: rank (secondary ink), symbol (700), total score (15px) beside a **contribution-stacked total bar** (8px tall on a raised track, segments in factor hues sized by weighted contribution), then four **factor percentile bars** (6px, 0–100 width in the factor hue, value right-aligned). Row hover is a 2.5% white wash; selected row takes accent-soft. Bar widths animate 240ms on `cubic-bezier(.16, 1, .3, 1)`, off under reduced motion.

### Rank Change
Beside each rank: a 12px chevron plus the number of places moved since the comparison moment (default the previous recorded moment; 30 s, 1, 5, 15 min selectable; "Không so sánh" turns it off). The comparison moment is always strictly earlier and named in the legend note; when none exists the note says so instead of guessing. The detail panel adds one line "So với HH:MM:SS: hạng a → b (…), điểm x → y (±d)", the leader metric notes "từ hạng n", and the total-score chart marks each stock's previous total with a 2px white tick.

### Status Column
Valid rows are silent. Only exceptions carry a dot plus a short label (warn amber or bad red ink); details live in the tooltip. Run-wide reasons and warnings appear once, in the notice banner under the panel head or the legend note, never repeated per row.

### Detail Panel
Symbol and score at display size, a full-width 10px stacked bar, a one-line "strongest/weakest factor" sentence, then four factor rows (swatch, name, bar, value, raw indicator line beneath), a reasons box on surface-2, and a recorded-price line chart with an amber dashed reference line.

### Charts
Inline SVG drawn at the container's pixel width so 11px labels stay 11px. Gridlines in seam; labels in secondary ink. The total-score chart stacks factor contributions per symbol; non-selected bars sit at 45% opacity and the selected symbol's labels go Primary Ink 700. Clicking a bar selects the stock.

## Do's and Don'ts

### Do:
- **Do** keep the three colour vocabularies separate: accent #3B82F6 for selection/focus/primary, the factor palette for score composition, #16C784/#FF5C66/#F0B90B only for price movement, connection and staleness.
- **Do** show every ranked row with its contribution-stacked total bar and, where width allows, four factor percentile bars.
- **Do** keep valid rows silent in the status column; give an exception a dot plus a short Vietnamese label.
- **Do** state run-wide reasons and warnings once, in the notice banner or legend note.
- **Do** label synthetic data with the amber chip whenever it is shown.
- **Do** set every number in tabular figures and draw icons as 16px line icons (1.6 stroke) from the inline sprite.
- **Do** apply factor colours and bar widths through classes and the CSSOM; the CSP forbids inline style attributes.
- **Do** draw charts at container pixel width so chart labels stay 11px.

### Don't:
- **Don't** colour scores green or red; score strength is bar length in factor hues.
- **Don't** stack warning boxes over the ranking or repeat a run-wide note on every row.
- **Don't** add drop shadows to panels; separate with tone and a 1px seam.
- **Don't** load web fonts, icon fonts or CDN assets; the build runs offline.
- **Don't** fall back to the Streamlit arrangement of a form-control sidebar, stacked info boxes and one generic bar chart.
- **Don't** drop the factor split at narrow widths; hide factor columns and widen the stacked bar instead.
