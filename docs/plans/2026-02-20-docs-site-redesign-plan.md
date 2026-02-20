# Hawk docs site — editorial redesign implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Completely rewrite all 6 docs HTML pages with a modern editorial aesthetic (Cormorant Garamond + DM Sans, deep forest teal accent, clean near-white background).

**Architecture:** Full clean rewrite — each file written from scratch. Existing files are content reference only. No shared CSS file; each page is self-contained with identical CSS token definitions copy-pasted for reliability. Design doc at `docs/plans/2026-02-20-docs-site-redesign.md` is the authoritative spec.

**Tech Stack:** Static HTML5, inline CSS, inline SVG animations (CSS keyframes), Google Fonts (Cormorant Garamond + DM Sans). No build step, no framework, no JS libraries.

---

## CSS token block (copy into every page)

Every page starts with these exact CSS custom properties. Do not deviate.

```css
:root {
  --bg: #f8f8f6;
  --surface: #ffffff;
  --text: #0e1a12;
  --text-muted: #4a6b55;
  --text-faint: #8aaa95;
  --accent: #1a6b4a;
  --accent-light: #e8f5ee;
  --accent-dark: #0e3d2a;
  --border: #d8e0da;
  --red: #8b2020;
  --red-bg: #fdf0f0;
  --shadow: 0 2px 12px rgba(14,26,18,.07);
  --shadow-lg: 0 6px 28px rgba(14,26,18,.11);
  --radius: 8px;
}
```

## Google Fonts import (copy into every page)

```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400;1,600&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300;1,9..40,400&display=swap" rel="stylesheet">
```

## Standard nav HTML (copy into every page, mark active page with class="active")

```html
<nav class="site-nav" role="navigation" aria-label="Hawk site navigation">
  <div class="nav-inner">
    <a href="[path-to-explainer]" class="nav-wordmark">Hawk</a>
    <div class="nav-links">
      <a href="[path-to-explainer]" [class="active" if this page]>How it works</a>
      <span class="nav-sep">·</span>
      <span class="nav-label">Mockups:</span>
      <a href="[path]index.html" [class="active" if this page]>Overview</a>
      <a href="[path]review.html" [class="active" if this page]>Review</a>
      <a href="[path]dashboard.html" [class="active" if this page]>Dashboard</a>
      <a href="[path]glossary.html" [class="active" if this page]>Glossary</a>
      <a href="[path]wp-plugin.html" [class="active" if this page]>WP plugin</a>
    </div>
    <span class="nav-badge">mockup</span><!-- omit on explainer.html -->
  </div>
</nav>
```

## Standard nav CSS (copy into every page)

```css
/* Nav */
.site-nav { background: #fff; border-bottom: 1px solid var(--border); }
.nav-inner { max-width: 1080px; margin: 0 auto; padding: 0 2rem; height: 52px; display: flex; align-items: center; gap: 0; }
.nav-wordmark { font-family: 'Cormorant Garamond', Georgia, serif; font-style: italic; font-size: 1.15rem; font-weight: 600; color: var(--accent); text-decoration: none; flex-shrink: 0; padding-right: 1.5rem; border-right: 1px solid var(--border); margin-right: 0; }
.nav-links { flex: 1; display: flex; align-items: center; justify-content: center; gap: .7rem; font-family: 'DM Sans', system-ui, sans-serif; font-size: .8rem; letter-spacing: .02em; flex-wrap: wrap; }
.nav-links a { color: rgba(14,26,18,.5); text-decoration: none; transition: color .15s; padding-bottom: 2px; border-bottom: 2px solid transparent; white-space: nowrap; }
.nav-links a:hover { color: var(--text); }
.nav-links a.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 500; }
.nav-sep { color: var(--border); }
.nav-label { color: var(--text-faint); font-size: .73rem; }
.nav-badge { flex-shrink: 0; background: var(--accent-light); color: var(--accent); font-family: 'DM Sans', system-ui, sans-serif; font-size: .62rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; padding: .22rem .6rem; border-radius: 3px; }
```

## Standard SVG animation CSS (copy into any page with pipeline SVGs)

```css
/* SVG pipeline animations */
@keyframes nodeGlow {
  0%, 2%   { fill: rgba(255,255,255,0.04); stroke: rgba(255,255,255,0.1); stroke-width: 1; }
  9%       { fill: rgba(26,107,74,0.45); stroke: #1a6b4a; stroke-width: 2; }
  18%      { fill: rgba(26,107,74,0.08); stroke: rgba(255,255,255,0.12); stroke-width: 1; }
  100%     { fill: rgba(255,255,255,0.04); stroke: rgba(255,255,255,0.1); stroke-width: 1; }
}
@keyframes labelGlow {
  0%, 2%, 18%, 100% { fill: rgba(255,255,255,0.55); }
  9% { fill: #fff; }
}
@keyframes subGlow {
  0%, 2%, 18%, 100% { fill: rgba(255,255,255,0.28); }
  9% { fill: rgba(255,255,255,0.7); }
}
@keyframes numGlow {
  0%, 2%, 18%, 100% { fill: rgba(255,255,255,0.18); }
  9% { fill: #4ade80; }
}
@keyframes nodeGroupShadow {
  0%, 4%   { filter: none; }
  9%       { filter: drop-shadow(0 0 10px rgba(26,107,74,0.85)) drop-shadow(0 0 22px rgba(26,107,74,0.4)); }
  18%      { filter: none; }
  100%     { filter: none; }
}
@keyframes dotTravel {
  0%, 7%, 100% { opacity: 0; transform: translateX(0); }
  9%   { opacity: 1; transform: translateX(0); }
  12%  { opacity: 1; transform: translateX(24px); }
  14%  { opacity: 0; transform: translateX(24px); }
}
@keyframes dotEcho {
  0%, 8%, 100% { opacity: 0; transform: translateX(0); }
  10%  { opacity: 0.45; transform: translateX(4px); }
  14%  { opacity: 0; transform: translateX(24px); }
}
/* Apply per-node with animation-delay: 0s, 1s, 2s ... for 7-node pipeline */
/* Apply per-dot with animation-delay: 0.5s, 1.5s ... for connectors */
/* Apply per-echo with animation-delay: 0.85s, 1.85s ... */
```

**SVG geometry for 7-node pipeline (900×140 viewBox):**
- Background: `<rect width="900" height="140" rx="10" fill="#0e1a12"/>`
- 7 nodes × 108px + 6 connectors × 24px = 900px
- Node positions: x = 0, 132, 264, 396, 528, 660, 792 (each width 108, with 2px inset padding)
- Connector line cx pairs: 108→132, 240→264, 372→396, 504→528, 636→660, 768→792
- Primary dots (white, r=5): cx = 108, 240, 372, 504, 636, 768
- Echo dots (rgba(255,255,255,0.4), r=3): same cx values

---

## Task 1: Rewrite `docs/explainer.html`

This is the pattern-setter. Get it right and the rest follow.

**Files:**
- Rewrite: `docs/explainer.html` (preserve all existing section content, pipeline step text, language list, quality tier descriptions, glossary examples)

**Reference:** Current file at same path for content. Design doc for visual spec.

### Step 1: Read the current file for content inventory

Read `docs/explainer.html` in full. Note:
- The 7 pipeline step titles and descriptions
- The languages section (10 languages)
- The quality tiers section (Instant / Reviewed / Certified)
- The glossary section examples
- The intro text

Do NOT preserve any CSS or structural HTML.

### Step 2: Write the new file

The page structure (top to bottom):
1. `<head>` — meta tags, OG tags, favicon, Google Fonts import, inline `<style>`
2. `<nav class="site-nav">` — wordmark left, links center, NO badge (explainer is not a mockup)
3. `<header>` — full-width teal bg (`#1a6b4a`), Cormorant h1 in white, italic subtitle, language badge pills
4. `<main>` — max-width 780px, centered
   - Intro paragraph (Cormorant Garamond 18px)
   - Pipeline SVG animation (full column width, 900×140, teal glow system)
   - 7-step breakdown (decorative number + h3 + paragraph per step)
   - Quality tiers section
   - Languages section
   - Glossary section
5. `<footer>` — minimal, DM Sans, teal link back to mockups

**Header CSS:**
```css
header {
  background: var(--accent);
  padding: 5rem 2rem 4rem;
  text-align: center;
}
header h1 {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: clamp(2.5rem, 6vw, 4rem);
  font-weight: 600;
  color: #fff;
  line-height: 1.15;
  margin-bottom: .75rem;
}
header h1 em { font-style: italic; color: rgba(255,255,255,.85); }
.header-sub {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.25rem;
  font-style: italic;
  color: rgba(255,255,255,.75);
  font-weight: 300;
  max-width: 540px;
  margin: 0 auto 2rem;
}
.lang-badges { display: flex; flex-wrap: wrap; gap: .4rem; justify-content: center; }
.lang-badge {
  background: rgba(255,255,255,.15);
  color: rgba(255,255,255,.9);
  border: 1px solid rgba(255,255,255,.2);
  border-radius: 20px;
  padding: .2rem .75rem;
  font-family: 'DM Sans', sans-serif;
  font-size: .78rem;
}
```

**Pipeline step CSS:**
```css
.step {
  display: grid;
  grid-template-columns: 4rem 1fr;
  gap: 0 1.5rem;
  margin-bottom: 3.5rem;
  padding-bottom: 3.5rem;
  border-bottom: 1px solid var(--border);
}
.step:last-child { border-bottom: none; }
.step-num {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 4rem;
  font-weight: 300;
  color: var(--border);
  line-height: 1;
  padding-top: .15rem;
}
.step-content h3 {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: .5rem;
}
.step-content p {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.05rem;
  color: var(--text-muted);
  line-height: 1.75;
}
```

**Page load animation — add to every element:**
```css
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
nav { animation: fadeSlideIn .4s ease both; }
header { animation: fadeSlideIn .4s ease .1s both; }
main > * { animation: fadeSlideIn .5s ease both; }
/* Use nth-child or specific classes to stagger: .25s, .35s, .45s, .55s */
```

### Step 3: Verify the file

Open `docs/explainer.html` in a browser (or use `python3 -m http.server 8877` from the docs dir). Check:
- [ ] Nav wordmark is italic teal Cormorant
- [ ] Nav links are centered in the bar
- [ ] Header is full-width teal
- [ ] Pipeline SVG shows teal glow animation
- [ ] Steps use large decorative numbers
- [ ] Body text is Cormorant Garamond
- [ ] Page load animation fires

### Step 4: Commit

```bash
git add docs/explainer.html
git commit -m "redesign: rewrite explainer.html with editorial teal theme"
```

---

## Task 2: Rewrite `docs/mockups/index.html`

Hub page introducing all 4 mockups.

**Files:**
- Rewrite: `docs/mockups/index.html`

**Reference:** Current file for the 4 card titles/descriptions. Design doc for visual spec.

### Step 1: Write the new file

Structure:
1. `<head>` — standard setup, paths to fonts
2. `<nav>` — active: Overview, badge shown
3. `<header>` — teal bg, Cormorant h1 "Interface mockups", DM Sans subtitle
4. `<main>` — max-width 1080px
   - Brief editorial intro paragraph (Cormorant)
   - 2-column card grid: Review, Dashboard, Glossary, WP plugin
   - Each card: white surface, thin border, teal eyebrow label (DM Sans caps), Cormorant card title, DM Sans description, teal "View mockup →" link
   - Keep the CSS art mini-previews but use the teal color system

**Card CSS:**
```css
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.75rem;
  display: flex;
  flex-direction: column;
  transition: box-shadow .2s, border-color .2s;
}
.card:hover { box-shadow: var(--shadow); border-color: rgba(26,107,74,.3); }
.card-eyebrow { font-family: 'DM Sans', sans-serif; font-size: .7rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); margin-bottom: .4rem; }
.card-title { font-family: 'Cormorant Garamond', serif; font-size: 1.4rem; font-weight: 600; color: var(--text); margin-bottom: .5rem; }
.card-desc { font-family: 'DM Sans', sans-serif; font-size: .88rem; color: var(--text-muted); line-height: 1.55; flex: 1; margin-bottom: 1rem; }
.card-link { font-family: 'DM Sans', sans-serif; font-size: .85rem; font-weight: 500; color: var(--accent); text-decoration: none; }
.card-link:hover { text-decoration: underline; }
```

### Step 2: Verify

- [ ] Nav centered, active on Overview
- [ ] 2-column card grid
- [ ] Cormorant card titles
- [ ] CSS mini-previews use teal not amber/navy

### Step 3: Commit

```bash
git add docs/mockups/index.html
git commit -m "redesign: rewrite mockups/index.html with editorial teal theme"
```

---

## Task 3: Rewrite `docs/mockups/review.html`

Most visually complex mockup — side-by-side review interface.

**Files:**
- Rewrite: `docs/mockups/review.html`

**Reference:** Current file for the 5-paragraph article data, scores, job metadata. Design doc for visual spec.

### Step 1: Read current file for data

Note:
- Job ID: `a3f892b1`, newsroom: Newark Ledger, language: Spanish, tier: Reviewed
- 5 paragraphs with their scores (P1: 4.4 approved, P2: 2.1 flagged/editing, P3: 3.7 amber, P4: 4.8 pending, P5: 4.2 pending)
- The P2 flag reasons and edit textarea content
- Article: "Newark school board approves $2.1B budget"

### Step 2: Write the new file

Structure:
1. `<head>` + `<nav>` (active: Review, badge shown)
2. **Page context header** (white bg): teal eyebrow "Review interface — mockup", Cormorant h1 "STNS editor review", DM Sans description
3. **No flow SVG on this page** — the review interface IS the animation
4. **Interface frame** — `border-radius: 8px`, shadow, overflow hidden:
   - **Top bar** (`#1a6b4a` bg): job ID pill, newsroom → language, tier badge, progress indicator
   - **Column headers row**: `#` / Status / English / Spanish / Score (DM Sans, all-caps, 11px)
   - **5 paragraph rows** with correct states from current file
   - **Footer bar**: "Approve and deliver" button (disabled until all resolved)

**Interface color scheme (inside the frame):**
- Approved rows: `#f0f8f3` left border `3px solid var(--accent)`
- Flagged rows: `#fdf0f0` left border `3px solid var(--red)`
- Pending rows: white background
- Score numbers: Cormorant Garamond (they are editorial numbers)

**Top bar CSS:**
```css
.job-bar { background: var(--accent); padding: .9rem 1.25rem; color: #fff; font-family: 'DM Sans', sans-serif; }
.job-id-pill { background: rgba(255,255,255,.2); font-size: .72rem; padding: .15rem .5rem; border-radius: 3px; font-family: 'Courier New', monospace; }
```

### Step 3: Verify

- [ ] Top bar is teal (not navy)
- [ ] Approved rows have teal left border
- [ ] Flagged row has red left border and edit textarea
- [ ] Score numbers are Cormorant

### Step 4: Commit

```bash
git add docs/mockups/review.html
git commit -m "redesign: rewrite mockups/review.html with editorial teal theme"
```

---

## Task 4: Rewrite `docs/mockups/dashboard.html`

Partner dashboard with job lifecycle SVG and job table.

**Files:**
- Rewrite: `docs/mockups/dashboard.html`

**Reference:** Current file for job data (8 rows, stats bar values, API key). Design doc for visual spec.

### Step 1: Read current file for data

Note:
- Stats: 47 jobs, 153/200 quota, 2 active, 44 complete
- 8 job table rows with their statuses, job IDs, languages, scores
- API key: `hawk_live_••••••••••••••••••••ab3c`
- 6-node lifecycle SVG structure (Queued→Translating→Scoring→Tier?→Complete/InReview)

### Step 2: Write the new file

Structure:
1. `<head>` + `<nav>` (active: Dashboard, badge shown)
2. **Page context header**: teal eyebrow, Cormorant h1 "Partner dashboard"
3. **Job lifecycle SVG** — reuse 6-node structure from current file but replace all amber with teal glow system from the standard SVG CSS block above
4. **Interface frame**:
   - **Stats bar** (`#1a6b4a` bg): 4 stat tiles (jobs/quota/active/complete)
   - **Top bar** (white, border-bottom): search field, filter tabs, "New translation" button in teal
   - **Job table**: horizontal rules only, hover teal, score values in Cormorant
   - **API key row** at bottom: monospace display

**Job lifecycle SVG changes from current:**
- Background: `#0e1a12` (was `#1a2e4a`)
- Node glow: teal (`#1a6b4a`) not amber
- Dots: white not amber
- All other geometry unchanged from current file

### Step 3: Verify

- [ ] Stats bar is teal
- [ ] SVG glows teal on activation
- [ ] Table has no cell backgrounds, just horizontal rules
- [ ] Score values are Cormorant

### Step 4: Commit

```bash
git add docs/mockups/dashboard.html
git commit -m "redesign: rewrite mockups/dashboard.html with editorial teal theme"
```

---

## Task 5: Rewrite `docs/mockups/glossary.html`

Glossary editor with term substitution SVG animation.

**Files:**
- Rewrite: `docs/mockups/glossary.html`

**Reference:** Current file for the 10 glossary terms, SVG animation structure. Design doc for visual spec.

### Step 1: Read current file for data

Note:
- 10 glossary terms with English and Spanish equivalents
- SVG animation: 3-panel (English source | Glossary table | Protected output), cycling through 3 terms
- The 3 cycling terms: Board of Education, Governor, Superintendent

### Step 2: Write the new file

Structure:
1. `<head>` + `<nav>` (active: Glossary, badge shown)
2. **Page context header**: Cormorant h1 "Glossary editor"
3. **Term substitution SVG** — update colors to teal system:
   - Background: `#0e1a12`
   - Highlight rects: teal (`rgba(26,107,74,0.35)`) not amber
   - Spanish text appears in white
   - Row pulse in teal
4. **Interface frame**:
   - **Header bar** (`#1a6b4a`): language selector, title
   - **Toolbar** (white, border-bottom): search, add button in teal
   - **Term table**: horizontal rules only, teal "protected" badge, term rows
   - **Add term row** at bottom: inline form inputs

### Step 3: Verify

- [ ] SVG animation uses teal glow not amber
- [ ] Table has clean rules-only styling
- [ ] "Protected" badges are teal

### Step 4: Commit

```bash
git add docs/mockups/glossary.html
git commit -m "redesign: rewrite mockups/glossary.html with editorial teal theme"
```

---

## Task 6: Rewrite `docs/mockups/wp-plugin.html`

WordPress Gutenberg plugin mockup.

**Files:**
- Rewrite: `docs/mockups/wp-plugin.html`

**Reference:** Current file for article content, sidebar panel data, recent translations, setup steps. Design doc for visual spec.

### Step 1: Read current file for data

Note:
- Article: "Newark school board approves $2.1B budget"
- Job state: Spanish delivered (es-draft #8492), Portuguese scoring, French queued
- Recent translations: 2 previous jobs
- 4 setup steps (install, API key, webhook, publish)
- 4-node flow SVG: Your post → Hawk API → Translate + Score → Draft posts

### Step 2: Write the new file

Structure:
1. `<head>` + `<nav>` (active: WP plugin, badge shown)
2. **Page context header**: Cormorant h1 "WordPress plugin"
3. **4-node flow SVG** — update to teal system (background `#0e1a12`, teal glow, white dots). Keep 32px connector width and matching `wpDotTravel` keyframe.
4. **Gutenberg editor frame** — redesigned (NOT authentic WP chrome):
   - **Admin bar** (`#0e1a12` near-black, not WP's `#1d2327`): "Hawk CMS" branding, not WordPress
   - **Editor toolbar** (white): standard editing controls
   - **Writing area**: article content in Cormorant Garamond body text
   - **Hawk translation block** inside content: teal header bar, job status rows
   - **Sidebar**: teal panel header, language checkboxes, tier radios, translate button (disabled/spinning), recent jobs
5. **Setup grid**: 4 feature cards, Cormorant card titles, teal numbered indicators

**Note on WP chrome:** We're not simulating authentic WordPress anymore — we're showing a "Hawk CMS plugin" concept. Admin bar is `#0e1a12`, buttons are teal. This is intentional per the design decision to apply the editorial theme everywhere.

### Step 3: Verify

- [ ] Admin bar is `#0e1a12` (NOT `#1d2327`)
- [ ] Flow SVG uses teal glow
- [ ] Sidebar Hawk panel has teal header
- [ ] Setup cards use Cormorant titles

### Step 4: Commit

```bash
git add docs/mockups/wp-plugin.html
git commit -m "redesign: rewrite mockups/wp-plugin.html with editorial teal theme"
```

---

## Task 7: Final consistency pass + push

### Step 1: Cross-check all 6 pages

Open each file and verify these shared elements are identical:
- [ ] Google Fonts import URL matches the standard block above
- [ ] CSS token values match exactly
- [ ] Nav structure and link paths are correct for each page's location
- [ ] Active nav item is correct for each page
- [ ] No residual amber (`#b07020`) or old navy (`#1a2e4a`) color values anywhere

### Step 2: Search for old color values

```bash
grep -rn "b07020\|1a2e4a\|fefcf8\|d09030\|Source Serif" docs/
```

Expected output: nothing (or only in the plans/ directory and CLAUDE.md).

### Step 3: Push

```bash
git pull --rebase origin master
git push origin master
```

### Step 4: Verify on GitHub Pages

Check `https://jamditis.github.io/hawk-translation-api/` — Pages deploys within ~1 minute of push. Verify:
- [ ] Explainer page loads with teal header
- [ ] Nav links center correctly at 1080px+ viewport
- [ ] SVG animations show teal glow (not amber)
- [ ] All 5 mockup pages reachable from nav
