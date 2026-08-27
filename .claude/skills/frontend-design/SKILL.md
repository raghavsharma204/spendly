---
name: spendly-frontend-ui
description: Design system and markup conventions for Spendly's frontend (Flask + Jinja2 + plain CSS). Use whenever building or editing ANY page, template, form, button, card, or UI element in Spendly — even small tweaks — to keep visual style consistent with the existing app. Trigger this even if the user just says "add a page", "make a form", "style this", or mentions templates/, static/css, login, register, dashboard, etc.
---

# Spendly Frontend UI

Spendly's frontend is server-rendered Flask + Jinja2 with **one shared stylesheet** — no CSS framework, no JS framework. Never introduce Tailwind, Bootstrap, React, or a new CSS file without being asked. All new pages should extend `base.html` and reuse existing classes/tokens below before inventing new ones.

## Stack

- Templates: `templates/*.html`, all extend `templates/base.html` (blocks: `title`, `head`, `content`, `scripts`)
- Styles: single file `static/css/style.css` — add new rules here, grouped under a labeled comment banner matching the existing style (see file for section format, e.g. `/* --- Buttons --- */`)
- JS: `static/js/main.js`, vanilla JS only
- Fonts: DM Serif Display (headings/display text) + DM Sans (body), loaded via Google Fonts in `base.html`

## Design tokens (CSS variables in `:root`)

Always use these variables — never hardcode hex values.

**Color**
- `--ink` #0f0f0f — primary text
- `--ink-soft` #2d2d2d — secondary text/headings
- `--ink-muted` #6b6b6b — body copy, subtitles
- `--ink-faint` #a0a0a0 — placeholders, timestamps
- `--paper` #f7f6f3 — page background
- `--paper-warm` #f0ede6 — section background (alternating sections)
- `--paper-card` #ffffff — card/panel background
- `--accent` #1a472a (deep green) — primary brand accent, links, CTAs on hover
- `--accent-light` #e8f0eb — badges, success states
- `--accent-2` #c17f24 (amber) — secondary accent, chart series 2
- `--accent-2-light` #fdf3e3
- `--danger` #c0392b / `--danger-light` #fdecea — errors
- `--border` #e4e1da / `--border-soft` #eeebe4

**Type**
- `--font-display`: 'DM Serif Display' — used for h1/hero titles/card totals only, never body text
- `--font-body`: 'DM Sans' — everything else

**Layout/shape**
- `--max-width` 1200px (page container), `--auth-width` 440px (login/register)
- `--radius-sm` 6px (buttons, inputs), `--radius-md` 12px (cards), `--radius-lg` 20px (hero/feature cards)

## Component patterns — reuse these classes

- **Buttons**: `.btn-primary` (dark, fills accent green on hover), `.btn-ghost` (outlined), `.btn-submit` (full-width, for forms)
- **Cards**: `.auth-card` / `.feature-card` / `.mock-card` — white bg, `1px solid var(--border)`, radius-md, padding 2rem
- **Forms**: wrap each field in `.form-group` > `<label>` + `.form-input`. Show errors via `.auth-error`, success via `.auth-success`. Follow the exact markup in `templates/register.html` for new forms (label→input pairing, `required`, `value="{{ field or '' }}"` to repopulate on error)
- **Nav**: fixed `.navbar` > `.nav-inner` (max-width, flex, space-between) — don't restructure, just add links inside `.nav-links`
- **Section pattern**: any new content section = `<section class="X-section">` > `<div class="X-inner">` (max-width wrapper), matching `.hero`/`.features`/`.legal-section` naming

## Conventions to follow

- New page = new file in `templates/`, `{% extends "base.html" %}`, fill `content` block
- Section/component class names are prefixed by context (`hero-*`, `auth-*`, `legal-*`, `mock-*`) — follow this prefixing when adding new sections (e.g. a dashboard page would use `dashboard-*`)
- Currency/amount displays use `--font-display` for the number (see `.mock-total`), muted small text for labels
- Mobile breakpoints: 900px (stack hero/features to 1 column), 600px (hide nav links except CTA) — extend these same breakpoints, don't add new arbitrary ones
- `main-content` min-height accounts for navbar (60px) + footer (~100px) — keep this pattern for new pages so footer doesn't jump

## Before making changes

Read `static/css/style.css` in full first — it's ~600 lines and already has most patterns you'll need (buttons, forms, cards, responsive rules). Extend it; don't duplicate a rule that already exists under a different name.