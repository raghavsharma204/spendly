# Spec: Backend Routes for Profile Page

## Overview
Step 04 turned `GET /profile` into a real logged-in page showing account info, an
all-time spend total, and a category bar breakdown — all sourced from one aggregate
helper, `get_expense_summary(user_id)`. That page is a thin snapshot. This step expands
the **same single route** into three read-only, server-rendered data sections, each
backed by its own single-responsibility helper in `database/db.py`:

1. **Transaction history** — the user's most recent expenses as a table
2. **Summary stats** — headline numbers: all-time total, transaction count, average
   transaction, current calendar-month total
3. **Category breakdown** — per-category totals as bars, which supersedes the breakdown
   half of `get_expense_summary` (that helper is removed)

There are no new routes, no JSON endpoints, no JavaScript, and no profile editing —
`/profile` simply becomes a proper spending dashboard while staying inside the existing
Flask + Jinja2 + single-stylesheet conventions. Implementation is split across three
subagents (one per section) run sequentially, coordinated by anchor comments in the
shared files.

## Depends on
- **Step 01 (database setup)** — `get_db()`, the `expenses` table, the module-level
  `CATEGORIES` list in `database/db.py`.
- **Step 03 (login/logout)** — session-based auth via `session["user_id"]`.
- **Step 04 (profile page)** — the `GET /profile` route and its inline auth guard,
  `get_user_by_id()`, the `.profile-*` CSS section, the `.mock-*` bar markup/styles, the
  `member_since` computation, and the `currency` Jinja filter.

## Routes
No new routes. `GET /profile` (logged-in only) is refactored: the same inline
`session.get("user_id")` guard and `get_user_by_id` null-check, but it now fetches three
datasets (recent transactions, summary stats, category breakdown) and passes them to
`profile.html`.

## Database changes
No schema changes. New helpers in `database/db.py`, all using parameterised (`?`) queries
and the existing `conn = get_db(); try: … finally: conn.close()` shape:

- `get_recent_transactions(user_id, limit=10)` — `SELECT id, amount, category, date,
  description FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?`.
  Returns a list of dicts (`id, amount, category, date, display_date, description`);
  `display_date` formatted `"%b %d, %Y"`. Returns `[]` for a user with no expenses.
- `get_summary_stats(user_id)` — one query returning `COUNT(*)`, `COALESCE(SUM(amount),0)`,
  `COALESCE(AVG(amount),0)`, and a `COALESCE(SUM(CASE WHEN strftime('%Y-%m', date) =
  strftime('%Y-%m','now') THEN amount END),0)` current-month total. Returns
  `{"total", "txn_count", "avg_amount", "month_total"}`; all zeros for a user with no
  expenses (no division by zero — `AVG` is computed by SQLite).
- `get_category_breakdown(user_id)` — the breakdown logic currently inside
  `get_expense_summary`, unchanged: `SELECT category, SUM(amount) AS total … GROUP BY
  category`, iterate `CATEGORIES` in order, skip categories with no spend, `pct` relative
  to the largest category (guarded against divide-by-zero), `variant =
  CATEGORIES.index(category) + 1`. Returns a **bare list** of `{category, total, pct,
  variant}`. Returns `[]` for a user with no expenses.

`get_expense_summary(user_id)` is **removed** — its total is now provided by
`get_summary_stats` and its breakdown by `get_category_breakdown`.

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html` — add three sections, each delimited by
  `{# Step 05: <feature> start #}` / `{# … end #}` anchor comments:
  - **Summary stats** — full-width row of four `.profile-stat` tiles, inserted between the
    `.profile-header` and `.profile-grid`.
  - **Category breakdown** — replaces the existing `.mock-card.profile-summary-card`
    block inside `.profile-grid`; a `.mock-card.profile-breakdown-card` with header label
    "Spending by category" and the existing `.mock-bars` loop over `category_breakdown`,
    with a `.profile-empty` empty state.
  - **Transaction history** — full-width `.profile-history` block below `.profile-grid`:
    an `<h2 class="profile-card-title">` plus a `.profile-txn-table` `<table>`
    (Date / Category / Description / Amount), with a `.profile-empty` empty state.
- `templates/base.html` is unchanged.

## Files to change
- `app.py` — refactor the `profile()` route (three fetch blocks + updated
  `render_template` kwargs); update the `from database.db import (...)` block
  (`-get_expense_summary`, `+get_category_breakdown`, `+get_recent_transactions`,
  `+get_summary_stats`).
- `database/db.py` — add the three helpers above; add `from datetime import datetime`;
  remove `get_expense_summary`.
- `templates/profile.html` — the three sections above.
- `static/css/style.css` — three labeled banner blocks in the Profile section
  (transaction-history table styles; summary-stats tile grid + one line in the existing
  `@media (max-width: 900px)` block; `.profile-breakdown-card`), and delete the now-dead
  `.profile-summary-card { max-width: none; }` rule.
- `CLAUDE.md` — *(optional, separable)* correct the stale "Implemented vs stub routes"
  rows for `GET /logout` and `GET /profile`.

## Files to create
None. (`.claude/specs/05-backend-routes-for-profile-page.md`, this file, is the spec
itself.)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only (`?` placeholders) — never f-strings or `%`-formatting in SQL.
- No DB logic in route functions — all queries live in `database/db.py`; the route only
  fetches and renders.
- Route functions have one responsibility: fetch data, render the template.
- Use `abort()` / framework errors for HTTP errors, not bare string returns.
- All templates extend `base.html`.
- Use the `:root` CSS custom properties — never hardcode hex values. Reuse the existing
  `.mock-*` bar classes for the category breakdown.
- New CSS goes only in `static/css/style.css`, in the Profile section, under labeled
  comment banners matching the file's existing style. Use the `.profile-*` prefix for new
  page classes.
- Only the existing responsive breakpoints (900px, 600px) — do not add new ones.
- Money is rendered with the `currency` Jinja filter (₹).
- No new pip packages. The app runs on port 5001.
- Do **not** modify the `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete`
  stub routes.
- A user with zero expenses must not crash or divide by zero — every helper returns a
  sensible empty value and every section renders an empty state.
- No JavaScript — `static/js/main.js` stays empty and `profile.html` adds no
  `{% block scripts %}`.

## Definition of done
Run `source venv/bin/activate && python3 app.py`, open http://127.0.0.1:5001, sign in as
`demo@spendly.com` / `demo123`, and visit `/profile`.

- [ ] App boots on port 5001 with no import error (confirms `get_expense_summary` is fully
      removed and the three new helpers import cleanly).
- [ ] Visiting `/profile` while logged out redirects to `/login`.
- [ ] The **summary stats** row shows four tiles: All-time spend **₹6,120.25**,
      Transactions **8**, Average transaction **₹765.03**, This month **₹6,120.25**.
- [ ] The **category breakdown** card ("Spending by category") shows bars for Food
      ₹1,050.00, Transport ₹120.50, Bills ₹1,500.00, Health ₹800.00, Entertainment
      ₹350.75, Shopping ₹2,200.00 (widest at 100%), Other ₹99.00; each row uses its
      `mock-bar-{variant}` colour; zero-spend categories are omitted.
- [ ] The **transaction history** table shows 8 rows, newest first (Food "Dinner with
      friends" on day 21 at the top → Food "Groceries at local market" on day 2 at the
      bottom); dates render like `Aug 21, 2026`; amounts in ₹; an empty description shows
      "—".
- [ ] **Zero-expense edge case:** register a second user (or use the `seed-user` skill),
      sign in, visit `/profile` → HTTP 200 with no traceback; stats tiles read
      `₹0.00 / 0 / ₹0.00 / ₹0.00`; the breakdown card and the transaction table each show
      "No expenses recorded yet."
- [ ] **Responsive:** at ≤900px the stats grid collapses to two columns and
      `.profile-grid` to one; `grep -nE '@media' static/css/style.css` shows only 900px
      and 600px.
- [ ] `grep -rn "get_expense_summary" app.py database/ templates/` returns nothing.
- [ ] No f-string SQL in `database/db.py`; every new query uses `?` placeholders.
- [ ] `git diff main -- app.py` shows no change to `add_expense` / `edit_expense` /
      `delete_expense`.
- [ ] `git diff main -- static/js/main.js` and `git diff main -- templates/base.html` are
      empty; `profile.html` has no `{% block scripts %}`.
- [ ] `git diff main -- static/css/style.css | grep -E '#[0-9a-fA-F]{3,6}'` shows no
      added hex literals.
