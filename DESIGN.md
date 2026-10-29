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
  error-surface: "#3a252b"
  error-border: "#6a414b"
  error-text: "#f2b0b8"
  universe-focus: "#99d4ef"
  # Shadow ink is specific to the narrow universe detail overlay.
  universe-detail-shadow-ink: "#000b"
  # The following values describe observed component-specific states.
  nav-active-surface: "#203329"
  quiet-hover-surface: "#2c3c48"
  symbol-hover-surface: "#345342"
  notice-warning-surface: "#353024"
  danger-button-surface: "#36272b"
  nav-count-surface: "#365c46"
  status-success-border: "#365c47"
  badge-warning-surface: "#393426"
  badge-error-surface: "#3d282e"
  nav-rail-border: "#3d5e4c"
  badge-info-border: "#426881"
  universe-border: "#435361"
  symbol-border: "#435462"
  button-border: "#475561"
  danger-hover-surface: "#4b3138"
  badge-neutral-border: "#4b5a67"
  field-border: "#4b5d6a"
  sidebar-control-border: "#547061"
  toast-border: "#547c64"
  notice-warning-border: "#5a5039"
  dialog-border: "#5a7060"
  research-selected-border: "#5c826b"
  universe-control-border: "#607484"
  symbol-selected-border: "#629674"
  button-hover-border: "#667a89"
  badge-warning-border: "#6b5c38"
  allocation-fill: "#78ae90"
  field-hover-border: "#7a9386"
  badge-error-border: "#81505a"
  danger-button-border: "#89585e"
  paper-identity-text: "#a3d3b7"
  status-success-text: "#a4dfba"
  nav-active-text: "#a5e7bd"
  badge-info-text: "#aad2ef"
  chart-control-text: "#acbac6"
  universe-muted-text: "#aebfcc"
  danger-hover-border: "#b27b83"
  symbol-selected-text: "#b8e9c9"
  nav-count-text: "#c5f3d4"
  report-text: "#cfdae2"
  asset-mark-text: "#d3e0e9"
  skip-link-text: "#d4efde"
  down-candle: "#dc8c96"
  chart-control-hover-text: "#e1eee5"
  toast-text: "#e2f2e8"
  badge-warning-text: "#e4cb97"
  notice-warning-text: "#e5cf9c"
  badge-error-text: "#f0a9b0"
  snapshot-warning-text: "#f1d49b"
  universe-error-text: "#ffc3a5"
  universe-selected-surface: "#2b5140"
typography:
  display:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-.02em"
  headline:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-.012em"
  title:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "0"
  body:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  report:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.45
  action:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  code:
    fontFamily: 'ui-monospace, Consolas, monospace'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  control: "3px"
  badge: "2px"
  compact: "4px"
  dialog: "5px"
spacing:
  chip-gap: "5px"
  control-block: "8px"
  panel-block: "16px"
  grid: "12px"
  panel-inline: "16px"
  section: "16px"
  workspace-top: "20px"
  workspace-inline: "16px"
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
    backgroundColor: "{colors.danger-button-surface}"
    textColor: "{colors.negative}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  panel-header:
    backgroundColor: "{colors.instrument-header}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    padding: "16px"
  navigation-active:
    backgroundColor: "{colors.nav-active-surface}"
    textColor: "{colors.nav-active-text}"
    rounded: "0"
    padding: "8px 12px"
  status-verified:
    backgroundColor: "#203a2d"
    textColor: "{colors.status-success-text}"
    rounded: "{rounded.badge}"
    padding: "4px 8px"
---

# Design System: TradingAgents Paper Desk

## Overview

**Creative North Star: "The Linked Trading Desk"**

A compact workstation places portfolio exposure, instrument data, and agent evidence within one continuous reading surface. Its charcoal navy layers, cool rules, and green controls follow the user's pinned Active Trader Pro direction. The interface supports sustained inspection through modest headings, tabular numbers, and explicit selection.

The visual system keeps research, proposals, and broker execution legible as separate states. Selection links the watchlist, chart, and evidence inspector; it does not imply an order. Paper identity, source timestamps, unavailable data, and broker acknowledgements are part of the interface's information hierarchy.

**Key Characteristics:**

- Desktop sidebar navigation and linked instrument panels.
- Charcoal surfaces separated by fine rules and lighter headers.
- Green actions and selections with labeled status semantics.
- System typography with aligned, tabular financial figures.
- Responsive stacking that preserves instrument context.

Extracted from the current cascade in `tradingagents/web/static/app.css` and the workspace stylesheets `ui-workflows.css`, `ui-markets.css`, `ui-instrument.css`, `ui-orders.css` and `ui-research-journal.css`, the shell in `tradingagents/web/static/index.html`, and the rendered component templates in `tradingagents/web/static/app.js`. The final dark `:root` and subsequent workstation rules supersede earlier light definitions. This document records the implemented system; it is not a complete application QA verdict. The surface brief is `.impeccable/surface-brief-paper-desk.md`.

## Colors

The palette uses cool charcoal layers for long reading sessions, with a pale green accent for action and selection. The named component-state colors in the frontmatter record observed control, badge, notice, chart and universe variants; they describe those specific uses, not a requirement to reuse each value globally. Sidecar tonal strips are derived previews; they do not introduce application tokens.

### Primary

- **Desk Green** (`accent`): primary buttons, active tabs, links, the brand mark, and active navigation treatment.
- **Green Hover** (`accent-hover`): primary button hover fill and border.
- **Green Wash** (`accent-wash`): retained root wash token; the current status badges use their explicit component variants.
- **Positive Green** (`positive`): gains, positive quote changes, completed research stages, and upward candles.

### Secondary

- **Loss Rose** (`negative`): negative changes, sell-side labels, and destructive controls.
- **Review Amber** (`warning`): caution and review semantics.
- **Error surface, border, and text** (`error-surface`, `error-border`, `error-text`): shared error notices and details.
- **Universe focus** (`universe-focus`): keyboard focus in the configured-universe workspace.
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

## Color palettes

Success, error, warning and information states use distinct foreground, border and surface tones across the workstation. These component-specific tones intentionally extend the base semantic colors while preserving the same status meaning. Desk fields and panels use the 3px control radius (`rounded.control`); the 4px `rounded.compact` value applies only to the configured-universe workspace, which overrides `--radius`.

## Typography

**Typeface:** Segoe UI Variable Text, Segoe UI, then the platform sans-serif fallbacks recorded in the frontmatter. There is no separate display family. Code and raw evidence use the CSS `--font-mono` token.

The typography resembles a native trading workstation. Compact labels remain subordinate to instrument symbols and account values; reports gain breathing room through line height rather than a new font.

- **Headline:** page headings use the 26px display token; section headings are 22px and Dashboard account values use the 22px heading token.
- **Title:** panel and section headings use the 18px section token.
- **Body:** general UI text uses 16px with 1.45 leading; paragraphs and reports use 1.65; data cells use 14px.
- **Report:** analyst text uses the body role, preserves whitespace, and wraps long tokens.
- **Label:** table headings (600 weight) and supporting captions use the 13px metadata token.
- **Action:** standard buttons and navigation controls use the 14px UI token at regular weight; compact metadata variants can use 13px.

**The Numeric Alignment Rule.** Keep table cells and account values in tabular numerals and left-align instrument identity. Right-align numeric columns where the workspace defines them (for example the watchlist); right alignment is not applied to every table.

## Layout

The blueprint Foundation uses a 36px app bar and 40px workspace heading, with
8px 12px 12px main padding and no workspace footer. Errors and recovery notices
retain natural height. The symbol search, labeled account flags, local-draft
counts, Alerts link, order-pause management and engine/stream/Laya observations
use existing source state; unverified exposure displays UNKNOWN.

Shared tabs use roving focus and Left/Right/Home/End keys. Single-key trader
shortcuts yield to form controls, editable regions, CodeMirror, composition and
open dialogs. Selection for inspection, research and deletion remains separate.
Edited or loaded legacy tickets keep their instrument identity until explicit
new/discard/reset; the docked drawer is a later implementation stage.

At 1100px width or 800px height the Dashboard keeps its single-panel tabs;
at 790px width the navigation becomes a scrolling horizontal row. The app bar
wraps when controls need more space. These are CSS viewport rules; browser
resizing does not establish actual Windows DPI acceptance.

The desktop shell places a vertical navigation sidebar (172px, widening to 208px from 1100px) beside the workspace and its context bar. The workspace pages are Dashboard, Portfolio, Markets, Research, Orders, Strategy lab, Journal, Alerts, Workflows and Settings. At narrow widths the navigation becomes a horizontal scrolling row above the workspace.

The Dashboard ledger presents five account measures in content-sized columns and scrolls horizontally when needed. At desktop sizes the Dashboard uses linked watchlist, chart, research, positions and orders panels. Its wider grid gives the watchlist and chart the first row; shorter or narrower views use panel tabs. The watchlist and its table remain scrollable when their controls need more space.

| Condition | Implemented behavior |
| --- | --- |
| At least 1101px wide and 801px high | Dashboard uses the wider two-row composition. |
| At most 1100px wide or 800px high | Dashboard switches to a single visible panel with tabs. |
| At most 790px wide | The sidebar becomes a horizontal scrolling navigation row and the footer is hidden. |

Tables retain horizontal scrolling when financial columns need more space. Chart sizing follows the available panel area.

## Elevation & Depth

Normal workspace surfaces are flat. Layering comes from the dark canvas, lighter panel bodies and headers, and one-pixel boundaries. Shadows are reserved for transient feedback and the order dialog.

- **Toast:** `0 8px 28px #0005`.
- **Order dialog:** `0 20px 70px #0008`, with backdrop `#060d14ad`.
- **Narrow universe detail:** `0 10px 70px #000b`.

**The Flat Instrument Rule.** Use rules and tonal layers to separate persistent instruments. Reserve shadows for temporary overlays.

## Shapes

Controls, panels, and account containers use the compact control radius. Status badges use the smaller badge radius; the dialog uses the dialog radius. These are restrained corner treatments on rectangular tools. Navigation controls retain a visible active state. Circular marks identify status or research stages.

One-pixel borders carry structural separation. Avoid turning the ledger or instrument grid into detached rounded tiles.

## Components

### Buttons

Compact, explicit actions with a minimum height of 36px. Primary actions use Desk Green and dark text. Ordinary actions use Control Slate. Quiet actions remove the resting fill and border. Destructive actions use a rose border, dark rose fill, and Loss Rose text.

Hover changes fill and border. All buttons inherit 160ms ease transitions for background, text, and border color. Keyboard focus uses a two-pixel accent outline with a two-pixel offset. Disabled buttons retain their label, use half opacity, and show a not-allowed cursor.

### Status badges

Status badges are compact labeled rectangles (4px 8px padding). Green represents completion, accepted/verified states, or positive ratings; blue covers running and pending states; amber covers review, blocked, hold, and stopping states; rose covers failures, rejected states, or negative ratings. Neutral covers other named states. The selected symbol remains consistent across the linked instruments through selection state, not a chip component.

### Panels and ledger

Each panel has a ruled outer boundary, a lighter header, and a flush body. Panel headers use 16px padding; Dashboard headers have a 40px minimum height and watchlist headers use 12px padding. Tables meet the panel edges. Empty panels preserve their title and show an explanation of what is absent and the relevant next action.

The ledger uses large tabular values with smaller labels and context lines. Missing broker values remain visibly unavailable.

### Inputs and fields

Fields use a recessed dark surface, a cool border, and a minimum height of 36px. Hover shifts the border toward green; keyboard focus uses the shared outline. Labels sit above fields and concise help sits below. Disabled fields use a distinct filled surface and muted text. Validation messages appear beside the relevant form or dialog action.

### Navigation

Global navigation combines small line icons with text in the desktop sidebar. The current page has a green-toned fill and accent border. At narrow widths the navigation becomes a horizontally scrolling row, with labels retained and icons hidden.

### Linked instruments

Selecting a ticker updates the daily OHLC chart, quote strip, and research inspector. The selected table row uses a green-toned fill, while pointer hover uses a cooler surface. The chart is the SVG renderer in `app.js` (`stockChart()`); there is no chart-tab control. Up/down candles use separate fills and strokes; volume bars have reduced opacity.

Reports use disclosure sections with a visible expansion marker. Research is organized in Summary, Reports, Debate, Sources, Activity and Setup tabs; stage markers use colored completion indicators. Empty charts show a plain panel surface and an explicit absence message, with no decorative price series.

### Workflows studio and other workspaces

The Workflows workspace is a studio grid (editor, generated diagram, inspector) styled in `ui-workflows.css`; its CodeMirror theme and Mermaid diagram are bundled from `desktop/workflow-ui`. Workspace stylesheets `ui-markets.css`, `ui-instrument.css` (quote strip and instrument tabs), `ui-orders.css` and `ui-research-journal.css` extend the shared tokens, and the Orders detail pane collapses at 1500px. Connected status uses `#268567`, distinct from the accent, and the browser theme color is `#182b3b`.

### Order preview and feedback

The order dialog is a focused review surface with paper identity, side and ticker, a ruled quantity/price/notional specification, and a full-width submit action. Toasts provide short feedback; persistent warnings use a full-width notice. Labels distinguish research launch, proposal building, review, and order submission.

The only repeating motion is the existing 1.5s loading pulse. The reduced-motion media query removes animation and transitions and disables smooth scrolling.

## Do's and Don'ts

### Do:

- **Do** preserve the charcoal workspace, compact rectangular instruments, and green action language.
- **Do** keep selected-symbol context consistent across the watchlist, chart, and evidence.
- **Do** pair status colors with text and financial changes with signed values.
- **Do** preserve tabular numerals and the right-aligned financial columns where defined.
- **Do** retain visible unavailable, loading, failed, and paused states.
- **Do** keep broker timestamps and paper identity readable alongside the data they qualify.
- **Do** preserve keyboard focus, native form controls, and reduced-motion behavior.

### Don't:

- **Don't** revive the superseded light palette.
- **Don't** add decorative shadows to persistent instrument panels.
- **Don't** replace missing market data with illustrative prices or chart points.
- **Don't** imply that selecting a symbol or launching research submits an order.
- **Don't** hide financial columns by shrinking their text to fit a narrow viewport.



## Shared desktop tokens

The shared CSS tokens are defined in the `:root` block in `tradingagents/web/static/app.css`; the configured-universe workspace (`#universe-review`) overrides several of them (accent, muted, line, radius, surface).
Workspace styles consume these properties; do not add local copies of the type or spacing scale.

| Role | Token | Value |
| --- | --- | --- |
| Body and research prose | `--text-body` | 16px |
| Controls and labels | `--text-ui` | 14px |
| Dense tabular data and chart axes | `--text-data` | 14px |
| Secondary metadata | `--text-meta` | 13px |
| Section, workspace and page headings | `--text-section / --text-heading / --text-display` | 18 / 22 / 26px |
| Account values | `--text-metric` / `--text-heading` | 28px / 22px on Dashboard |
| UI and prose leading | `--leading-ui / --leading-body` | 1.45 / 1.65 |
| Shared spacing scale | `--space-1` through `--space-6` | 4 / 8 / 12 / 16 / 20 / 24px |
| Standard control height | `--control-height` | 36px |

Keep the established system-font stack, dark palette and semantic colors.
The chart and its drawing annotations read type from the shared CSS font; chart surfaces, text, grid and candle colors use the corresponding CSS properties.
Use tight spacing for related controls and larger spacing between sections.
Prose fills its available panel or cell width, as requested; do not reintroduce narrow paragraph caps.
Desktop workspaces retain bounded scrolling within data, reading and form panes.
