# Spec: Add Expense

## Overview
`GET /expenses/add` is currently a placeholder route that returns the string
`"Add expense — coming in Step 7"`. This step turns it into a real feature: a
logged-in user gets a form to record a new expense (amount, category, date,
optional description), the server validates the input and inserts one row into
the existing `expenses` table for that user, then redirects to `/profile` where
the new expense immediately shows up in the summary stats, the category
breakdown, and the recent-transactions table (all built in Steps 05–06). This is
the first route that writes to the `expenses` table and the first of the
create/edit/delete trio (Steps 7–9). Edit (Step 8) and delete (Step 9) stay
stubbed and are out of scope here.

## Depends on
- **Step 01 — Database Setup**: the `expenses` table (`user_id`, `amount`,
  `category`, `date`, `description`, `created_at`) and `get_db()` with FK
  enforcement. Already implemented.
- **Step 03 — Login/Logout**: the session (`session["user_id"]`) and the
  logged-in redirect pattern used by `/profile`.
- **Step 05 — Backend Routes for Profile Page**: `get_summary_stats`,
  `get_category_breakdown`, `get_recent_transactions`, and the `CATEGORIES`
  list in `database/db.py` — the new expense must be picked up by all three
  with no further change.

## Routes
- `GET /expenses/add` — render the add-expense form (blank, with the date field
  defaulting to today) — logged-in
- `POST /expenses/add` — validate the submitted form; on success insert one
  `expenses` row for the current user, `flash("Expense added.")`, and
  `redirect(url_for("profile"))`; on failure re-render `add_expense.html` with
  an inline error and sticky field values, inserting nothing — logged-in

Both verbs share one route function: `@app.route("/expenses/add", methods=["GET", "POST"])`.

Access guard (identical to `/profile`, applied for **both** GET and POST):
`if not session.get("user_id"): return redirect(url_for("login"))`.

The stub `edit_expense` / `delete_expense` routes are **not** touched — they keep
returning their Step 8 / Step 9 placeholder strings.

## Database changes
No schema changes. The `expenses` table already has every column needed
(`user_id`, `amount REAL`, `category TEXT`, `date TEXT`, `description TEXT`
nullable, `created_at` default). `CATEGORIES` is already defined in
`database/db.py`.

Add one helper to `database/db.py`:

- `create_expense(user_id, amount, category, date, description)` — insert a
  single row with a parameterised `INSERT INTO expenses (user_id, amount,
  category, date, description) VALUES (?, ?, ?, ?, ?)` and return
  `cursor.lastrowid`. `description` may be `None` (stored as SQL NULL). Opens
  and closes its own connection via `get_db()` in a `try/finally`, matching the
  other helpers in the file. No validation logic here — the route is
  responsible for validating before calling.

## Templates
- **Create:** `templates/add_expense.html`
  - `{% extends "base.html" %}`; `{% block title %}Add expense — Spendly{% endblock %}`.
  - Reuse the auth-form shell: `<section class="auth-section">` →
    `<div class="auth-container">` → `.auth-header` (title "Add an expense",
    short subtitle) → `.auth-card` holding the form.
  - `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` at the
    top of the card (same pattern as `register.html`).
  - `<form method="POST" action="{{ url_for('add_expense') }}">` with four
    `.form-group` blocks:
    - **Amount** — `<input type="number" name="amount" class="form-input"
      step="0.01" min="0.01" required>`, `value="{{ amount or '' }}"`.
    - **Category** — `<select name="category" class="form-input" required>` with
      a disabled placeholder option and one `<option>` per entry in
      `categories` (passed from the route); mark the previously chosen one
      `selected` on re-render.
    - **Date** — `<input type="date" name="date" class="form-input" required>`,
      `value="{{ date or today }}"` (route passes `today` as an ISO string).
    - **Description** — `<input type="text" name="description"
      class="form-input" maxlength="200">` (no `required`),
      `value="{{ description or '' }}"`. Label it "Description (optional)".
    - `<button type="submit" class="btn-submit">Add expense</button>`.
  - A `.auth-switch`-style line below the card linking back to
    `{{ url_for('profile') }}` ("Back to your profile").
  - No `{% block scripts %}` — no JavaScript.
- **Modify:** `templates/profile.html`
  - In `.profile-header`, add an "Add expense" link next to the existing
    "View analytics" button: `<a href="{{ url_for('add_expense') }}"
    class="btn-primary">Add expense</a>` (wrap the two links in a small
    container if needed for spacing).
  - Directly inside `.profile-inner`, above `.profile-header`, add a flashed
    message block (mirroring `login.html`):
    `{% with messages = get_flashed_messages() %}{% if messages %}
    <div class="auth-success">{{ messages[0] }}</div>{% endif %}{% endwith %}`.
    This is what surfaces the "Expense added." confirmation after the redirect.
- **Modify:** `templates/base.html`
  - In the logged-in branch of `.nav-links` (the `{% if session.user_id %}`
    block), add `<a href="{{ url_for('add_expense') }}">Add expense</a>` before
    the "Profile" link.

## Files to change
- `app.py`
  - Replace the placeholder `add_expense()` function. Add `methods=["GET",
    "POST"]` to the decorator. Guard on `session.get("user_id")` → redirect to
    login. On `GET`, render `add_expense.html` with `categories=CATEGORIES` and
    `today=date.today().strftime(ISO_DATE)`. On `POST`, read `amount`,
    `category`, `date`, `description` from `request.form`; validate (see rules);
    on failure re-render `add_expense.html` with `error=...`, `categories`,
    `today`, and the submitted values so the form is sticky; on success call
    `create_expense(...)`, `flash("Expense added.")`,
    `redirect(url_for("profile"))`.
  - Update the import from `database.db` to add `create_expense` and
    `CATEGORIES`. `date` and the `_parse_iso_date` / `ISO_DATE` helpers are
    already present.
- `database/db.py` — add the `create_expense(...)` helper described above.
- `templates/add_expense.html` — new (listed under Files to create).
- `templates/profile.html` — header "Add expense" link + flashed-message block.
- `templates/base.html` — "Add expense" nav link for logged-in users.
- `static/css/style.css` — add a `/* Add expense (Step 07) */` section. Reuse
  `.auth-section`, `.auth-card`, `.form-group`, `.form-input`, `.btn-submit`,
  `.auth-error`, `.auth-success`, `.btn-primary` as-is. Add only: styling for
  `select.form-input` (consistent height/appearance with text inputs) and, if
  the two `.profile-header` links need it, a flex gap wrapper. Put any
  responsive tweaks inside the existing `@media (max-width: 900px)` /
  `@media (max-width: 600px)` blocks — no new breakpoints.
- `CLAUDE.md` — in the "Implemented vs stub routes" table, change the
  `GET /expenses/add` row from `Stub — Step 7` to
  `Implemented — GET renders add_expense.html; POST validates and inserts an
  expense for the logged-in user, then redirects to /profile`. Leave the
  Step 8 / Step 9 rows unchanged.

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only — `?` placeholders in the new `INSERT`, never
  f-strings or `%` formatting in SQL.
- Passwords hashed with werkzeug (unchanged; no auth code is modified here).
- Use CSS variables — never hardcode hex values. New rules reuse `--border`,
  `--radius-sm`, `--ink`, `--paper`, `--accent`, `--font-body`, etc.
- All templates extend `base.html` (`add_expense.html` must).
- Flask only; SQLite only; vanilla JS only — this step adds **no** JavaScript
  (native `<input type="date">` and `<select>` are enough).
- Route stays single-responsibility: read form → validate → call
  `create_expense` → redirect (or re-render on error). The `INSERT` lives in
  `database/db.py`, not in `app.py`.
- Server-side validation is mandatory even though inputs carry HTML5
  `required` / `type` / `min` — never trust the client. Validate:
  - `amount`: present; parses via `float()` (catch `ValueError`); strictly
    `> 0`; reject absurd values (`>= 10_000_000`); round to 2 decimals before
    insert.
  - `category`: present and exactly one of `CATEGORIES` — reject anything else.
  - `date`: present and a valid `YYYY-MM-DD` — validate with the existing
    `_parse_iso_date` helper; `None` result → error. (No past/future
    restriction — any valid calendar date is accepted, consistent with the
    seed data.)
  - `description`: optional; `.strip()`; store `None` when empty; truncate/limit
    to 200 chars (reject longer with an error, or slice — pick one and be
    consistent).
- On **any** validation failure: re-render `add_expense.html` with a single
  `error` string and the submitted values re-populated (amount, category, date,
  description); do **not** insert a row; return HTTP 200 (not a redirect, not
  an `abort()`).
- Do not use `abort()` here — form errors re-render the template. `abort()` is
  only for genuine HTTP error conditions, of which this route has none beyond
  the not-logged-in redirect.
- Preserve the placeholder pattern for the still-stubbed `edit_expense` /
  `delete_expense` routes — do not implement or restructure them.
- The success flash must be consumed on `/profile` via `get_flashed_messages()`
  so it shows once and does not reappear on refresh.

## Definition of done
Run the app (`python3 app.py`, port 5001) and verify:

1. Logged out, `GET /expenses/add` redirects to `/login`; `POST /expenses/add`
   (e.g. via curl) also redirects to `/login` and inserts no row.
2. Logged in as the seeded demo user (`demo@spendly.com` / `demo123`),
   `GET /expenses/add` renders a form inside `.auth-card` with Amount
   (number), Category (a `<select>` listing exactly the 7 `CATEGORIES`), Date
   (`<input type="date">` pre-filled with today), and an optional Description
   field. Page source shows `<form method="POST" action="/expenses/add">` (or
   the `url_for` equivalent).
3. Submitting Amount `250.50`, Category `Food`, today's date, Description
   `Lunch` redirects to `/profile`, which shows an "Expense added." message
   once; refreshing `/profile` does not show it again.
4. After that submission, the new expense appears at the top of "Recent
   transactions", the "Transactions" count goes up by 1, "All-time spend"
   increases by ₹250.50, and the "Food" category bar reflects the new total.
5. In the DB, the new `expenses` row has `user_id` = the demo user's id,
   `amount` = `250.5`, `category` = `Food`, `date` = today (ISO), and
   `description` = `Lunch`.
6. Submitting with Description left blank inserts a row whose `description` is
   SQL NULL (and `/profile` renders it as "—").
7. Submitting Amount `0`, a negative amount, or a non-numeric amount
   re-renders the form with an inline `.auth-error` and inserts no row; the
   other entered values are still populated.
8. Submitting (via curl, bypassing the `<select>`) a `category` not in the 7
   re-renders with an error and inserts no row.
9. Submitting (via curl) with a missing or malformed `date` (e.g. `date=foo`)
   re-renders with an error and inserts no row.
10. Submitting (via curl) with `amount`, `category`, or `date` entirely absent
    shows a validation error — no traceback, no 500, no row inserted.
11. An "Add expense" link appears in the top nav while logged in and as a
    button in the `/profile` header; both resolve via `url_for('add_expense')`
    (no hardcoded `/expenses/add` in the templates).
12. `/expenses/1/edit` and `/expenses/1/delete` still return their
    "coming in Step 8" / "coming in Step 9" placeholder strings.
13. `git grep` in `database/db.py` shows the new `INSERT` uses `?`
    placeholders only — no f-string or `%`-formatted SQL.
14. `requirements.txt` is unchanged; the app starts on port 5001 with no
    errors.
