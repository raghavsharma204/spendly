# Spec: Date Filter for Profile Page

## Overview
The profile page currently shows all-time figures only: summary stats, the
category breakdown, and the recent-transactions table are each computed over
every expense the user has ever recorded. This step adds an optional date-range
filter to `GET /profile` so a user can scope those three sections to a window
(e.g. "August 2026" or "the last pay period"). It is a read-only, server-side
filter driven entirely by query-string params on the existing route — no new
routes, no JavaScript, no expense editing. It is the natural next step after
Step 05 (which built the three profile data helpers) and sets up the reporting
mindset needed before expense create/edit/delete in Steps 7–9.

## Depends on
- **Step 04 — Profile Page**: the logged-in-only `GET /profile` route, its auth
  guard, and `templates/profile.html`.
- **Step 05 — Backend Routes for Profile Page**: the three helpers this step
  extends — `get_summary_stats`, `get_category_breakdown`,
  `get_recent_transactions` in `database/db.py` — and the three template
  sections that render them.

## Routes
No new routes.

`GET /profile` is extended to read two **optional** query-string params:

- `start` — inclusive lower bound, `YYYY-MM-DD`
- `end` — inclusive upper bound, `YYYY-MM-DD`

Behaviour:
- Neither param present → page renders exactly as it does today (unfiltered).
- Either or both present and valid → summary stats, category breakdown, and
  recent transactions are all scoped to expenses whose `date` falls in the
  given range (open-ended if only one bound is supplied).
- A param that is not a valid `YYYY-MM-DD` date is ignored (that bound is
  treated as absent); the page still renders, never a 500.
- `start` later than `end` is passed through as-is and simply yields an empty
  result set (the existing empty-state messages handle this) — no error.

Access level: logged-in (unchanged — same auth guard as today).

## Database changes
No schema changes. `expenses.date` is already `TEXT` in ISO `YYYY-MM-DD` form,
so lexical `>=` / `<=` comparison is also chronological.

Three existing helpers in `database/db.py` gain two optional keyword params,
`start=None` and `end=None` (ISO date strings):

- `get_summary_stats(user_id, start=None, end=None)`
- `get_category_breakdown(user_id, start=None, end=None)`
- `get_recent_transactions(user_id, limit=10, start=None, end=None)`

Each appends parameterised clauses to its existing `WHERE user_id = ?`:
- when `start` is not `None`: `AND date >= ?`
- when `end` is not `None`: `AND date <= ?`

Rules:
- Build the SQL and the params list conditionally; keep `?` placeholders —
  never interpolate the dates into the query string.
- Do not change the existing `ORDER BY` / `LIMIT` / `GROUP BY` clauses.
- `get_summary_stats` keeps its `month_total` CASE expression as-is. With a
  date filter active it therefore means "spend in the current calendar month
  **and** within the selected range"; a filter that excludes the current month
  will show ₹0.00 for the "This month" tile. This is acceptable — do not add
  special handling.
- All three helpers already return sensible empty values (`0` / `0.0` via
  `COALESCE`, or `[]`); no new empty-guards needed.

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html`
  - Add a filter form directly below `.profile-header` and above the Step 05
    summary-stats block.
    - `<form method="GET" action="{{ url_for('profile') }}">` (GET, not POST).
    - Two `<input type="date" class="form-input">` fields named `start` and
      `end`, each with a `<label>`, wrapped so they sit inline.
    - Values re-populated from context (`value="{{ start_date }}"` /
      `value="{{ end_date }}"`) so the selection persists after submit.
    - A submit button ("Apply").
    - A "Clear" link to `{{ url_for('profile') }}`, shown only when
      `filter_active` is true.
  - When `filter_active`, show a caption line (e.g. `.profile-filter-caption`)
    with the human-readable range from `filter_label`.
  - Do not change the three Step 05 section blocks themselves — they already
    render whatever the helpers return, including empty states. Reuse the
    existing `.profile-empty` message.
  - Keep all links as `url_for()`.

## Files to change
- `app.py` — extend the `profile()` view: read `request.args.get("start")` /
  `request.args.get("end")`, validate each with `datetime.strptime(..., "%Y-%m-%d")`
  (invalid → `None`), pass the clean ISO strings into the three helpers, and add
  `start_date`, `end_date`, `filter_active`, `filter_label` to the
  `render_template` context. `datetime` is already imported.
- `database/db.py` — add `start` / `end` params and conditional parameterised
  date clauses to `get_summary_stats`, `get_category_breakdown`,
  `get_recent_transactions`.
- `templates/profile.html` — add the filter form + active-range caption.
- `static/css/style.css` — add a `/* Profile — date filter (Step 06) */`
  section (form layout, field spacing, compact button). Reuse `.form-input`,
  `.form-group`/`.form-group label`, and existing button styling where
  possible. Add any responsive tweaks inside the existing
  `@media (max-width: 900px)` / `@media (max-width: 600px)` blocks — do not
  introduce new breakpoints.
- `CLAUDE.md` — update the `GET /profile` row of the "Implemented vs stub
  routes" table to note the optional `?start` / `?end` date filter.

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only — `?` placeholders, never f-strings/`%` in SQL,
  including the new date clauses.
- Passwords hashed with werkzeug (unchanged; no auth code touched here).
- Use CSS variables — never hardcode hex values. New styles reuse `--border`,
  `--radius-sm`, `--ink`, `--accent`, `--font-body`, etc.
- All templates extend `base.html` (`profile.html` already does).
- Flask only; SQLite only; vanilla JS only (this step adds **no** JS — the
  native `<input type="date">` picker is enough).
- Query-arg parsing / validation lives in the route; the date-range SQL lives
  in `database/db.py`. Keep the route single-responsibility: read args →
  validate → call helpers → render.
- Use `datetime.strptime` for validation; on `ValueError` treat that bound as
  absent. Do not `abort()` for a malformed filter param — a bad filter should
  degrade to "no filter", not an HTTP error.
- Preserve current unfiltered behaviour exactly when no params are supplied.

## Definition of done
Run the app (`python3 app.py`, port 5001), log in as the seeded demo user, and
verify:

1. `GET /profile` with no query string renders as before — All-time spend
   **₹6,120.25**, Transactions **8**, Average transaction **₹765.03** — and the
   category breakdown and recent-transactions table are unchanged.
2. A date-filter form is visible between the page header and the summary stats,
   with `start` and `end` date inputs and an "Apply" button; viewing source
   shows `<form method="GET" action="/profile">` (or the `url_for` equivalent).
3. Submitting the form navigates to `/profile?start=YYYY-MM-DD&end=YYYY-MM-DD`
   and the four stat tiles, the category bars, and the transactions table all
   reflect only expenses with `date` between `start` and `end` inclusive.
4. After submitting, the two date inputs still show the chosen dates (values
   re-populated from the query string).
5. When a filter is active, a caption shows the human-readable range and a
   "Clear" link is present; clicking it returns to an unfiltered `/profile`
   (no query string) with the original all-time figures.
6. `GET /profile?start=2026-08-01` (no `end`) filters as an open-ended range
   from that date; `GET /profile?end=2026-08-15` (no `start`) does the reverse.
7. `GET /profile?start=banana` (or any non-date value) renders the page
   unfiltered with no server error (HTTP 200, no 500).
8. `GET /profile?start=2026-12-01&end=2026-01-01` (start after end) renders
   with empty sections showing the existing "No expenses recorded yet."
   message and no error.
9. `git grep` shows the new date conditions in `database/db.py` use `?`
   placeholders; no f-string or `%`-formatted SQL was added.
10. `requirements.txt` is unchanged; no new imports beyond what already exists.
