---
name: TradingAgents Paper Desk
description: A linked trading workstation for broker exposure, agent evidence, and explicit paper orders.
colors:
  accent: "#79ce9e"
  accent-hover: "#94ddB3"
  accent-wash: "#203b30"
  ink: "#e1e8ee"
  muted: "#a5b3c0"
  paper: "#1b252f"
  ground: "#111920"
  line: "#34414d"
  navy: "#101a23"
  nav-text: "#b9c7d1"
  positive: "#7bd5a2"
  negative: "#f29199"
  warning: "#e6c17d"
  instrument-header: "#23313c"
  table-header: "#202c36"
  table-hover: "#253b48"
  selected-row: "#233f35"
  control: "#253440"
  control-hover: "#324552"
  field: "#14202a"
  primary-text: "#10271b"
  focus: "#86d6ab"
typography:
  display:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "23px"
    fontWeight: 550
    lineHeight: 1.3
    letterSpacing: "-.025em"
  headline:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-.015em"
  title:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "12px"
    fontWeight: 620
    lineHeight: 1.5
    letterSpacing: "0"
  body:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  report:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "11px"
    fontWeight: 550
    lineHeight: 1.5
  action:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.5
rounded:
  control: "3px"
  badge: "2px"
  dialog: "5px"
spacing:
  chip-gap: "5px"
  control-block: "8px"
  panel-block: "11px"
  grid: "12px"
  panel-inline: "13px"
  section: "16px"
  workspace-top: "20px"
  workspace-inline: "21px"
  workspace-bottom: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.primary-text}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.primary-text}"
  button-default:
    backgroundColor: "{colors.control}"
    textColor: "{colors.ink}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  button-danger:
    backgroundColor: "#36272b"
    textColor: "{colors.negative}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  panel-header:
    backgroundColor: "{colors.instrument-header}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    padding: "11px 13px"
  navigation-active:
    backgroundColor: "#203329"
    textColor: "#a5e7bd"
    rounded: "0"
    padding: "0 17px"
  symbol-chip:
    backgroundColor: "#293a47"
    textColor: "#c1d0db"
    rounded: "{rounded.badge}"
    padding: "3px 5px"
  status-verified:
    backgroundColor: "#203a2d"
    textColor: "#a4dfba"
    rounded: "{rounded.badge}"
    padding: "3px 6px"
---

# Design System: TradingAgents Paper Desk

## Overview

**Creative North Star: "The Linked Trading Desk"**

A compact workstation places portfolio exposure, instrument data, and agent evidence within one continuous reading surface. Its charcoal navy layers, cool rules, and green controls follow the user's pinned Active Trader Pro direction. The interface supports sustained inspection through modest headings, tabular numbers, and explicit selection.

The visual system keeps research, proposals, and broker execution legible as separate states. Selection links the watchlist, chart, and evidence inspector; it does not imply an order. Paper identity, source timestamps, unavailable data, and broker acknowledgements are part of the interface's information hierarchy.

**Key Characteristics:**

- Dense horizontal navigation and linked instrument panels.
- Charcoal surfaces separated by fine rules and lighter headers.
- Green actions and selections with labeled status semantics.
- System typography with aligned, tabular financial figures.
- Responsive stacking that preserves instrument context.

Extracted from the current cascade in `tradingagents/web/static/app.css`, the shell in `tradingagents/web/static/index.html`, and the rendered component templates in `tradingagents/web/static/app.js`. The final dark `:root` and subsequent workstation rules supersede earlier light definitions. This document records the implemented system; it is not a complete application QA verdict. The surface brief is `.impeccable/surface-brief-paper-desk.md`.

## Colors

The palette uses cool charcoal layers for long reading sessions, with a pale green accent for action and selection. Sidecar tonal strips are derived previews for the documentation panel; they do not introduce new application tokens.

### Primary

- **Desk Green** (`accent`): primary buttons, active chart tabs, links, the brand mark, and active navigation underline.
- **Green Hover** (`accent-hover`): primary button hover fill and border.
- **Green Wash** (`accent-wash`): retained root wash token; the current status badges use their explicit component variants.
- **Positive Green** (`positive`): gains, positive quote changes, completed research stages, and upward candles.

### Secondary

- **Loss Rose** (`negative`): negative changes, sell-side labels, and destructive controls.
- **Review Amber** (`warning`): caution and review semantics.
- Status badges use separate muted green, blue, amber, and rose fills with matching borders and light text. Their words carry the meaning alongside color.

### Neutral

- **Workspace Charcoal** (`ground`): the application canvas.
- **Navigation Navy** (`navy`): the global navigation rail.
- **Instrument Charcoal** (`paper`): panels, tables, the account ledger, and settings surfaces.
- **Header Slate** (`instrument-header`, `table-header`): instrument and column headers.
- **Cool Rule** (`line`): panel boundaries, separators, and table structure.
- **Reading White** (`ink`), **Quiet Slate** (`muted`), and **Navigation Silver** (`nav-text`): content, supporting detail, and navigation text.
- **Control Slate** (`control`, `control-hover`): ordinary actions; **Field Recess** (`field`): editable values.
- **Linked Selection** (`selected-row`) and **Row Hover** (`table-hover`): distinguish the selected instrument from transient pointer location.

**The Labeled State Rule.** Pair semantic color with readable status, numeric signs, or a selected-state attribute; color alone does not establish meaning.

## Typography

**Typeface:** Segoe UI Variable Text, Segoe UI, then the platform sans-serif fallbacks recorded in the frontmatter. There is no separate display or monospace family.

The typography resembles a native trading workstation. Compact labels remain subordinate to instrument symbols and account values; reports gain breathing room through line height rather than a new font.

- **Display:** account ledger values use the `display` role. This is a financial metric style, not a promotional heading.
- **Headline:** page headings use the `headline` role; the narrow layout reduces them to 20px.
- **Title:** instrument headers use the `title` role. General section headings and settings titles retain their observed 14–16px hierarchy.
- **Body:** general UI text uses `body`; table values and research summaries commonly use 11px.
- **Report:** analyst text uses `report`, preserves whitespace, wraps long tokens, and limits width to 88ch. At the narrow breakpoint it becomes 11px.
- **Label:** table headings use `label`. Supporting captions retain an 11px minimum.
- **Action:** standard buttons use `action`; small controls retain the same 11px text size.

**The Numeric Alignment Rule.** Keep table cells and account values in tabular numerals. Right-align numeric columns and left-align instrument identity.

## Layout

The desktop shell is full width. A sticky horizontal navigation bar (61px) sits over a compact context bar (39px). The default workspace padding is 20px 21px 24px. Navigation stays horizontal as the page narrows, moving below the brand into its own row.

The account ledger is one bordered row of four equal cells. The primary instrument grid uses `minmax(280px,.97fr) minmax(410px,1.65fr) minmax(250px,.85fr)` with a 12px gap. The chart is the largest instrument. A lower grid uses a 1.25:1 ratio for positions and the order blotter. These are current desk compositions, not requirements for every future screen.

Responsive behavior follows the actual cascade:

| Condition | Implemented behavior |
| --- | --- |
| At least 1600px | Wider instrument minima, 25px horizontal workspace padding, 275px chart region. |
| At most 1250px | Tighter navigation and 10px panel gaps; compact header and table padding. |
| At most 1060px | Watchlist and chart remain side by side; evidence spans the following row; the lower grid becomes one column. |
| At most 980px | The inherited research-detail sidebar narrows to 175px. |
| At most 790px | Navigation wraps below the brand; settings and research details become one column; research symbols become a scrolling horizontal list. |
| At most 760px | The inherited account ledger becomes two columns; the footer stacks; the research toolbar may wrap. |
| At most 600px | Instruments stack in chart, watchlist, evidence order; the page action expands; fields use one column. |
| At most 540px | Supplemental inherited compact rules reduce event-list gutters and let the research-run label occupy a full row. |

Tables retain horizontal scrolling rather than compressing financial columns into unreadable text. Watchlist rows use 5px vertical cell padding on desktop and 7px at 600px and below. Panel content permits shrinking with `min-width:0`. The chart region is 242px high by default; breakpoint-specific heights range from 220px to 275px.

Chart SVGs render as block elements and match their viewBox to the measured content width and height through ResizeObserver. Plot geometry uses the available panel space while axis labels retain their 11px CSS size on narrow screens.

## Elevation & Depth

Normal workspace surfaces are flat. Layering comes from the dark canvas, lighter panel bodies and headers, and one-pixel boundaries. Shadows are reserved for transient feedback and the order dialog.

- **Toast:** `0 8px 28px #0005`.
- **Order dialog:** `0 20px 70px #0008`, with backdrop `#060d14ad`.

**The Flat Instrument Rule.** Use rules and tonal layers to separate persistent instruments. Reserve shadows for temporary overlays.

## Shapes

Controls, panels, and account containers use the compact control radius. Status badges and symbol chips use the smaller badge radius; the dialog uses the dialog radius. These are restrained corner treatments on rectangular tools. Navigation tabs remain square, with a two-pixel active underline. Circular marks identify status or research stages.

One-pixel borders carry structural separation. Avoid turning the ledger or instrument grid into detached rounded tiles.

## Components

### Buttons

Compact, explicit actions with a minimum height of 32px; the small variant uses 27px. Primary actions use Desk Green and dark text. Ordinary actions use Control Slate. Quiet actions remove the resting fill and border. Destructive actions use a rose border, dark rose fill, and Loss Rose text.

Hover changes fill and border. All buttons inherit 160ms ease transitions for background, text, and border color. Keyboard focus uses a three-pixel focus outline with a three-pixel offset. Disabled buttons retain their label, use half opacity, and show a not-allowed cursor. The mobile page-heading action has a more specific 9px 11px padding rule.

### Status badges and symbol chips

Status badges are compact labeled rectangles. Green represents completion, accepted/verified states, or positive ratings; blue covers running and pending states; amber covers review, blocked, hold, and stopping states; rose covers failures, rejected states, or negative ratings. Neutral covers other named states.

Symbol chips are buttons. Hover uses a green-toned surface; selection uses a brighter border, green fill, and `aria-pressed`. The selected symbol remains consistent across the linked instruments.

### Panels and ledger

Each panel has a ruled outer boundary, a lighter header, and a flush body. Standard headers have a minimum height of 49px. Tables meet the panel edges. Empty panels preserve their title and show an explanation of what is absent and the relevant next action.

The ledger uses large tabular values with smaller labels and context lines. Missing broker values remain visibly unavailable.

### Inputs and fields

Fields use a recessed dark surface, a cool border, and a minimum height of 36px. Hover shifts the border toward green; keyboard focus uses the shared outline. Labels sit above fields and concise help sits below. Disabled fields use a distinct filled surface and muted text. Validation messages appear beside the relevant form or dialog action.

### Navigation

Global navigation combines small line icons with text. The active page has a green-toned fill, lighter green text, and a bottom accent rule; hover uses a cooler slate fill. The pause/resume control remains at the right of the global bar. Narrow layouts place the navigation links below the brand and keep their labels; at 600px and below the icons are hidden.

### Linked instruments

Selecting a ticker updates the daily OHLC chart, quote strip, and research inspector. The selected table row uses a green-toned fill, while pointer hover uses a cooler surface. Chart tabs switch between instrument history and account equity; period controls are compact text buttons. Up/down candles use separate fills and strokes; volume bars have reduced opacity.

Reports use disclosure sections with a visible expansion marker. The research-stage line uses five equal grid columns, 11px labels that can wrap, and colored completion markers. Empty charts show a plain panel surface and an explicit absence message, with no decorative price series.

### Order preview and feedback

The order dialog is a focused review surface with paper identity, side and ticker, a ruled quantity/price/notional specification, and a full-width submit action. Toasts provide short feedback; persistent warnings use a full-width notice. Labels distinguish research launch, proposal building, review, and order submission.

The only repeating motion is the existing 1.5s loading pulse. The reduced-motion media query removes animation and transitions and disables smooth scrolling.

## Do's and Don'ts

### Do:

- **Do** preserve the charcoal workspace, compact rectangular instruments, and green action language.
- **Do** keep selected-symbol context consistent across the watchlist, chart, and evidence.
- **Do** pair status colors with text and financial changes with signed values.
- **Do** preserve tabular numerals and right-aligned financial columns.
- **Do** retain visible unavailable, loading, failed, and paused states.
- **Do** keep broker timestamps and paper identity readable alongside the data they qualify.
- **Do** preserve keyboard focus, native form controls, and reduced-motion behavior.

### Don't:

- **Don't** revive the superseded light palette or vertical desktop sidebar.
- **Don't** add decorative shadows to persistent instrument panels.
- **Don't** replace missing market data with illustrative prices or chart points.
- **Don't** imply that selecting a symbol or launching research submits an order.
- **Don't** hide financial columns by shrinking their text to fit a narrow viewport.

