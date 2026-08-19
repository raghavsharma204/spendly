# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Spendly is a Flask-based personal expense tracker built incrementally as a step-by-step learning project. `app.py` contains explicit comments marking which routes are implemented and which are placeholders for future steps (e.g. `"Add expense — coming in Step 7"`). When extending functionality, follow the existing step numbering/ordering implied by those placeholder comments rather than jumping ahead or restructuring.

## Commands

Activate the virtualenv before running anything (dependencies are installed there, not system-wide):

```bash
source venv/bin/activate
```

Run the dev server (Flask debug mode, auto-reloads on file changes):

```bash
python3 app.py
```

The app serves on `http://127.0.0.1:5001` (port 5001, not Flask's default 5000).

Install/update dependencies:

```bash
pip install -r requirements.txt
```

There is no test suite, lint config, or build step yet — `pytest` and `pytest-flask` are listed in `requirements.txt` for future use but no tests exist.

## Architecture

- **`app.py`** — single-file Flask app; all routes are defined here directly (no blueprints).
- **`database/db.py`** — not yet implemented. Intended to hold `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (creates tables with `CREATE TABLE IF NOT EXISTS`), and `seed_db()` (sample data). The SQLite file (`expense_tracker.db`) is gitignored.
- **`templates/`** — Jinja2 templates. `base.html` is the shared layout (navbar, `<footer>`, `{% block title %}`, `{% block head %}`, `{% block content %}`, `{% block scripts %}`); page templates extend it. A template can define its own `head`/`scripts` blocks to add page-scoped `<style>`/`<script>` without touching `base.html` or `static/js/main.js` — see `landing.html`'s "How it works" modal for the pattern (prefix custom classes/ids, e.g. `hiw-`, to avoid colliding with global styles).
- **`static/css/style.css`** — single global stylesheet, organized in commented sections (Variables, Reset, Navbar, Hero, Buttons, Footer, Legal pages, Responsive, etc.). Uses CSS custom properties defined in `:root` (`--ink`, `--paper`, `--accent`, `--font-display`, `--font-body`, spacing/radius tokens) — reuse these rather than hardcoding colors/fonts. Two typefaces: `DM Serif Display` for headings/display text, `DM Sans` for body text (loaded via Google Fonts in `base.html`).
- **`static/js/main.js`** — currently an empty placeholder for future shared JS.

## Conventions

- Routes return `render_template(...)`; unimplemented features return a plain placeholder string naming the step they belong to (see the "Placeholder routes" section of `app.py`) — keep this pattern when adding new not-yet-built routes.
- Currency is displayed in ₹ (rupees).

## Code style
- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with url_for() for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (? placeholders) — never f-strings in SQL
- Error handling: use abort() for HTTP errors, not bare return "error string"

## Tech constraints
- Flask only — no FastAPI, no Django, no other web frameworks
- SQLite only — no PostgreSQL, no SQLAlchemy ORM, no external DB
- Vanilla JS only — no React, no jQuery, no npm packages
- No new pip packages — work within requirements.txt as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and match statements are fine

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration before implementing any new feature
- Always use a subagent to verify test results after any implementation
- When asked to plan, delegate codebase research to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

## Implemented vs stub routes
| Route	| Status |
|---|---|
|'GET/' |	Implemented — renders landing.html |
'GET /register' |	Implemented — renders register.html |
'GET /login'	| Implemented — renders login.html |
|'GET /logout' | Stub — Step 3 |
|'GET /profile'	| Stub — Step 4   |
|'GET /expenses/add'	| Stub — Step 7   |
|'GET /expenses/<id>/edit' |	Stub — Step 8|
|'GET /expenses/<id>/delete'	| Stub — Step 9|

**Do not implement a stub route unless the active task explicitly targets that step.**


## Warnings and things to avoid
- Never use raw string returns for stub routes once a step is implemented — always render a template
- Never hardcode URLs in templates — always use url_for()
- Never put DB logic in route functions — it belongs in database/db.py
- Never install new packages mid-feature without flagging it — keep requirements.txt in sync
- Never use JS frameworks — the frontend is intentionally vanilla
- database/db.py is currently empty — do not assume helpers exist until the step that implements them
- FK enforcement is manual — SQLite foreign keys are off by default; get_db() must run PRAGMA foreign_keys = ON on every connection
- The app runs on port 5001, not the Flask default 5000 — don't change this
