# Design

Visual system for the Growthvine Content Automation dashboard. Shares the **GrowthVine Brandbook** tokens with the Fund Analyser (Vine Indigo, Poppins, Foundation Grey) — one visual identity, two tools in the same suite. Light-first with optional dark mode.

## Theme

Internal editorial ops dashboard, light-first. Scene: a content analyst at a desk during working hours, reviewing AI-generated ideas and drafts in batches. Light mode is the default working surface — dense, calm, readable. Dark mode is a low-light option.

The current frontend (`globals.css`) is bare Tailwind defaults — no brand tokens, no Poppins, no Vine Indigo. This DESIGN.md is the target state to build toward.

## Colors

### Brand palette (GrowthVine Brandbook — identical to Fund Analyser)

| Token | Name | Hex | Use |
|---|---|---|---|
| `--brand` | Vine Indigo | `#9B81F5` | Primary actions, active states, focus rings |
| `--ink` | Foundation Grey | `#1D1D1B` | Headings/body on light; dark-mode background |
| `--base` | Clarity White | `#FFFFFF` | Light-mode card surfaces; text on dark |
| `--mint` | Mint | `#B1F0DB` | Approved status, success tints |
| `--peach` | Peach | `#FFBB90` | Warning, pending-review tints |

### UI token mapping

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#F4F4F2` | `#1D1D1B` |
| `--surface` | `#FFFFFF` | `#262624` |
| `--surface-2` | `#F7F7F5` | `#2D2D2B` |
| `--border` | `#E3E3DF` | `#3B3B38` |
| `--text-primary` | `#1D1D1B` | `#F7F7F5` |
| `--text-secondary` | `#3D3D3A` | `#C9C9C5` |
| `--text-muted` | `#5C5C57` | `#B0B0AA` |
| `--brand` | `#9B81F5` | `#9B81F5` |
| `--brand-text` | `#5436C8` | `#BCA9F8` |
| `--brand-soft` | `rgba(155,129,245,0.12)` | `rgba(155,129,245,0.18)` |

### Status / approval tokens

| State | Text | Background | Border |
|---|---|---|---|
| Pending | `#7A440D` | `rgba(255,187,144,0.30)` | `rgba(122,68,13,0.35)` |
| Approved | `#11604A` | `rgba(177,240,219,0.35)` | `rgba(17,96,74,0.35)` |
| Rejected | `#A02128` | `rgba(160,33,40,0.10)` | `rgba(160,33,40,0.35)` |

**Contrast rules:** Vine Indigo is not a body-text color (≈2.9:1 on white). Use `--brand-text` (#5436C8, 7.6:1) for any indigo text. Body text must hit ≥4.5:1.

## Typography

**Poppins** is the only brand family — matches Fund Analyser exactly.

| Role | Family | Weight | Size |
|---|---|---|---|
| Page headings (h1–h2) | Poppins | 600 | 1.5–2rem |
| Section labels (h3) | Poppins | 500–600 | 1.125rem |
| Body / labels / controls | Poppins | 400 | 0.875–1rem |
| Idea/draft angle text | Poppins | 500 | 0.9375rem |
| Scores, counts, tabular | Poppins | 400 | `font-variant-numeric: tabular-nums` |
| Agent reasoning / logs | JetBrains Mono | 400 | 0.8125rem |

Load: `Poppins:wght@400;500;600` + `JetBrains+Mono:wght@400` via Google Fonts.

## Spacing & Layout

- App shell: fixed sidebar (224px) + main content area, fluid right
- Sidebar: section groups with muted uppercase labels, link items with hover/active states
- Content area: max-width 1200px; padding 2rem 2.5rem
- Card radius: 8px (idea/draft cards); 12px (modals, panels)
- Gap between cards: 12px
- Z-index scale: dropdown 10 → sticky 20 → modal-backdrop 30 → modal 40 → toast 50

## Components (current codebase — Next.js 14 + Tailwind 4)

### Approval cards (Gate 1 — Ideas, Gate 2 — Drafts)
- White surface, 1px `--border` border, 8px radius, 16px padding
- Top row: platform badge + persona badge + score chip + source name + date (all inline, wrapping)
- Content: angle text (full wrap, Poppins 500)
- Actions: secondary links (Show reasoning, View scraped article) + Approve (green) / Reject (red outline) buttons
- Approve enters edit mode: textarea + Confirm / Cancel

### Platform badges
- Color-coded by platform: LinkedIn blue, Twitter sky, blog purple, email amber, WhatsApp green, carousel pink, advisor slate
- `text-xs font-medium px-2 py-0.5 rounded`

### Persona badges
- Indigo family: `bg-indigo-50 text-indigo-700 border border-indigo-200`
- `text-[10px] uppercase font-semibold px-2 py-0.5 rounded`

### Buttons
- Primary (approve): `bg-green-600 text-white hover:bg-green-700`
- Destructive outline (reject): `border border-red-200 text-red-700 bg-red-50 hover:bg-red-100`
- Neutral (secondary): `border border-gray-300 text-gray-700 hover:bg-gray-50`
- All: `px-3 py-1.5 text-xs rounded disabled:opacity-50`

### Status tabs
- Underline style: `border-b-2`, active = `border-blue-600 text-blue-700`
- Target: replace blue with `--brand` (Vine Indigo) to align with brand system

### Job status badges
- Queued: neutral gray; In Progress: brand-soft bg; Complete: mint; Failed: peach/error

### Sticky creation bar
- Fixed bottom, left offset = sidebar width (224px)
- `bg-white border-t shadow-lg px-6 py-3`

### Sidebar navigation
- Fixed left, `w-56`, white surface, section labels as muted uppercase `text-[10px]`
- Active link: brand-text color + soft brand bg tint
- Target: replace current gray with Vine Indigo active states

### Orchestrator chat
- Full-height message list + fixed input bar at bottom
- User messages: brand-soft bg; agent messages: neutral surface

## Current State vs. Target

The frontend currently uses bare Tailwind with no brand tokens. Key gaps:

| Gap | Current | Target |
|---|---|---|
| Font | Arial/system | Poppins + JetBrains Mono |
| Brand color | Blue-600 (Tailwind) | Vine Indigo #9B81F5 |
| Background | White / gray-50 | #F4F4F2 warm off-white |
| Active states | blue-600/blue-700 | brand-text #5436C8 |
| Status colors | green/red Tailwind | Mint/Peach brand tokens |
| Sidebar | Ad-hoc gray | Brand-aligned Vine Indigo actives |

## Motion

- 150–250ms ease-out for state changes (hover, focus, tab switch)
- No orchestrated page-load sequences
- `@media (prefers-reduced-motion: reduce)`: instant transitions

## Brand Alignment

This tool is in the same suite as the Growthvine Fund Analyser. They share:
- Vine Indigo as the primary brand/action color
- Poppins as the sole type family
- Foundation Grey neutral ramp
- Mint/Peach status encoding

They differ in surface purpose: the Fund Analyser is data-heavy (rankings tables, charts); this tool is editorial-ops-heavy (content cards, approval queues). Layout and density differ accordingly.
