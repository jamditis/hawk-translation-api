# Hawk docs site — editorial redesign

**Date:** 2026-02-20
**Scope:** All 6 HTML pages in `docs/` and `docs/mockups/`
**Approach:** Full clean rewrite — existing files are content reference only, not structural foundation

---

## Design direction

"The Atlantic meets a product page." Modern editorial light — crisp, literary, authoritative. Built for journalists and translation professionals, not developers.

---

## Visual system

### Color palette

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#f8f8f6` | Page background |
| `--surface` | `#ffffff` | Cards, panels, mockup frames |
| `--text` | `#0e1a12` | Body text (near-black with green undertone) |
| `--text-muted` | `#4a6b55` | Secondary text, captions |
| `--text-faint` | `#8aaa95` | Placeholders, disabled |
| `--accent` | `#1a6b4a` | Primary accent (deep forest teal) — used sparingly |
| `--accent-light` | `#e8f5ee` | Teal tint for highlights, hover states |
| `--accent-dark` | `#0e3d2a` | Deep teal for SVG backgrounds, mockup top bars |
| `--border` | `#d8e0da` | Subtle cool green-gray borders |
| `--red` | `#8b2020` | Error/flagged states |
| `--red-bg` | `#fdf0f0` | Error backgrounds |
| `--navy` | `#0e1a12` | Nav wordmark — same as text |

### Typography

**Cormorant Garamond** — editorial content at every level:
- Hero `h1`: `clamp(2.5rem, 6vw, 4rem)`, weight 600, italic variant for emphasis
- Section `h2`: `2rem`, weight 600
- Body text: `18px`, weight 400, line-height 1.8
- Pull quotes / section numbers: `4rem`, weight 300, color `#d8e0da`

**DM Sans** — UI chrome only:
- Nav links: `13px`, letter-spacing `0.04em`
- Labels/eyebrows: `11px`, weight 600, all-caps, letter-spacing `0.1em`
- Badge text: `11px`, weight 600, all-caps
- Table data: `13px`, weight 400
- Button text: `13px`, weight 500

### Spacing

- Max-width content: `780px` (editorial), `1080px` (full-width sections/mockups)
- Section gap: `6rem`
- Paragraph spacing: `1.4rem`
- Page padding: `0 2rem` horizontal

---

## Navigation

**Structure:** White bg (`#ffffff`), `1px` bottom border (`#d8e0da`), height `52px`, max-width container.

- **Left**: `Hawk` wordmark — Cormorant Garamond italic, `1.1rem`, color `#1a6b4a`
- **Center**: DM Sans links, `13px`, `rgba(0,0,0,0.55)` default, `#0e1a12` on hover. Active page: `#1a6b4a` color + `2px` teal underline offset `4px`
- **Right**: `mockup` badge on mockup pages — `#e8f5ee` bg, `#1a6b4a` text, DM Sans 11px caps

No separator between brand and links — the wordmark italic style creates enough visual separation from the roman-weight nav links.

---

## Page templates

### Explainer (`how it works`)

1. **Hero section**: Full-width, `#1a6b4a` background. Cormorant `h1` in white. Subtitle in Cormorant italic, `rgba(255,255,255,0.8)`. Language badge pills in `rgba(255,255,255,0.15)`.
2. **Pipeline SVG**: Full column width, teal-palette animation (see SVG system below).
3. **Seven steps**: Each step has a large decorative number (`4rem`, Cormorant, `#d8e0da`) + `h3` heading + body paragraph. Left-border accent (`2px`, `#1a6b4a`) on hover. No card boxes.
4. **Supporting sections**: Quality tiers, glossary, languages — clean typographic treatment, tables with horizontal rules only.

### Mockup hub (`index.html`)

1. **Editorial header**: Teal bg, Cormorant h1, DM Sans subtitle.
2. **Card grid**: 2-col, white cards, thin border. Cormorant card title, DM Sans body, teal `→` link. CSS art previews retain teal palette.

### Mockup pages (review, dashboard, glossary, wp-plugin)

1. **Page header**: White bg, teal eyebrow label (DM Sans, caps), Cormorant `h1`, DM Sans description.
2. **Flow SVG animation**: Full column width.
3. **Mockup frame**: `border-radius: 8px`, subtle shadow. Top bar: `#1a6b4a` (all mockup top bars, replacing the old navy). Inner interface uses teal status colors throughout — not trying to authentically simulate WP or other tools, showing an idealized version.
4. **Setup/features section**: Feature cards with numbered indicators in teal.

---

## SVG animation system

**SVG background**: `#0e1a12` (near-black with green undertone)
**Node default**: `fill: rgba(255,255,255,0.04)`, `stroke: rgba(255,255,255,0.1)`
**Node active peak**:
- `fill: rgba(26,107,74,0.45)`
- `stroke: #1a6b4a`, `stroke-width: 2`
- `filter: drop-shadow(0 0 10px rgba(26,107,74,0.85)) drop-shadow(0 0 22px rgba(26,107,74,0.4))`

**Connector lines**: `rgba(255,255,255,0.15)`, `stroke-width: 2`
**Primary dots**: `#ffffff`, `r=5`
**Echo dots**: `rgba(255,255,255,0.4)`, `r=3`, `+0.35s` delay behind primary
**Label text default**: `rgba(255,255,255,0.55)`
**Label text active**: `#ffffff`
**Sub-label default**: `rgba(255,255,255,0.28)`
**Sub-label active**: `rgba(255,255,255,0.7)`

---

## Page load animation

CSS only, no JS. Each major element gets `animation: fadeSlideIn 0.5s ease both`:

```css
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

Stagger: nav `0s`, header `0.1s`, first section `0.25s`, subsequent sections `+0.1s` each.

---

## Component patterns

### Status badges
- DM Sans, `11px`, all-caps, `0.1em` letter-spacing
- `3px` border-radius (boxy, not pill)
- Complete/approved: `#e8f5ee` bg, `#1a6b4a` text
- Flagged/error: `#fdf0f0` bg, `#8b2020` text
- Pending/queued: `#f0f0f0` bg, `#777` text
- In-progress: `#e8f5ee` bg, `#1a6b4a` text with spinner

### Tables
- Horizontal rules only (`1px`, `#d8e0da`), no cell backgrounds
- Header: DM Sans `11px` caps, `#8aaa95`
- Data: DM Sans `13px`
- Score/quality numbers: Cormorant Garamond (editorial numbers)
- Row hover: `#f0f8f3` (very pale teal)

### Mockup inner frame
- Top bar: `#1a6b4a` (all pages)
- Sidebar panels: `#f0f8f3` background
- Input focus ring: `2px` teal
- Active/selected rows: `#e8f5ee` background

---

## Implementation

6 HTML files — full clean rewrite of each. Content and data preserved, all markup and CSS written fresh.

Files:
1. `docs/explainer.html`
2. `docs/mockups/index.html`
3. `docs/mockups/review.html`
4. `docs/mockups/dashboard.html`
5. `docs/mockups/glossary.html`
6. `docs/mockups/wp-plugin.html`
