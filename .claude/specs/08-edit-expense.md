# Spec: Edit Expense

## Overview
`GET /expenses/<int:id>/edit` is currently a placeholder route that returns the
string `"Edit expense — coming in Step 8"`. This step turns it into a real
feature: a logged-in user opens the edit form for one of *their own* expenses,
the form is pre-filled with the current values (amount, category, date, optional
description), the server re-validates the input on submit and updates that single
`expenses` row, then redirects to `/profile` where the change is immediately
reflected in the summary stats, category breakdown, and recent-transactions
table (Steps 05–06). This is the second of the create/edit/delete trio
(Steps 7–9): Step 07 (add) is done, and Step 09 (delete) stays stubbed and out
of scope here. The defining concern of this step is **ownership enforcement** —
a user must never be able to view or modify another user's expense by guessing
an id.

## Depends on
- **Step 01 — Database Setup**: the `expenses` table (`id`, `user_id`, `amount`,
  `category`, `date`, `description`, `created_at`) and `get_db()` with FK
  enforcement. Already implemented.
- **Step 03 — Login/Logout**: the session (`session["user_id"]`) and the
  logged-in redirect pattern used by `/profile` and `/expenses/add`.
- **Step 05 — Backend Routes for Profile Page**: `get_summary_stats`,
  `get_category_breakdown`, `get_recent_transactions`, and the `CATEGORIES`
  list in `database/db.py` — an edited expense must be picked up by all three
  with no further change. `get_recent_transactions` already returns each row's
  `id`, which is what the profile "Edit" links are built from.
- **Step 07 — Add Expense**: the validation rules, the `add_expense.html`
  auth-form shell, and the `MAX_EXPENSE_AMOUNT` / `MAX_DESCRIPTION_LEN`
  constants and `_parse_iso_date` / `ISO_DATE` helpers in `app.py`. The edit
  route reuses all of the same field validation.

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the named
  expense's current values — **logged-in, owner only**
- `POST /expenses/<int:id>/edit` — re-validate the submitted form; on success
  update that one `expenses` row, `flash("Expense updated.")`, and
  `redirect(url_for("profile"))`; on failure re-render `edit_expense.html` with
  an inline error and sticky field values, updating nothing — **logged-in,
  owner only**

Both verbs share one route function:
`@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])`.

Access guard (identical to `/profile` and `/expenses/add`, applied for **both**
GET and POST): `if not session.get("user_id"): return redirect(url_for("login"))`.

Ownership guard (applied for **both** GET and POST, *after* the login guard):
fetch the expense scoped to the current user via
`get_expense_by_id(id, user_id)`. If it returns `None` — the id does not exist
**or** belongs to another user — `abort(404)`. Use 404 (not 403) so the route
does not leak whether an id exists. The `<int:id>` converter already returns 404
for a non-numeric id.

The `delete_expense` route is **not** touched — it keeps returning its Step 9
placeholder string and stays in the "Placeholder routes" section of `app.py`.
Move only `edit_expense` up out of that section, next to `add_expense`.

## Database changes
No schema changes. The `expenses` table already has every column needed. `created_at`
is **never** modified by an edit.

Add two helpers to `database/db.py` (both open/close their own connection via
`get_db()` in a `try/finally`, matching the existing helpers; both use `?`
placeholders only — no f-strings or `%` formatting in SQL):

- `get_expense_by_id(expense_id, user_id)` — `SELECT id, user_id, amount,
  category, date, description FROM expenses WHERE id = ? AND user_id = ?`.
  Returns the `sqlite3.Row`, or `None` if no such row for that user. Scoping by
  `user_id` in the SQL *is* the ownership check — callers must pass the
  session's user id, never trust a client-supplied one.
- `update_expense(expense_id, user_id, amount, category, date, description)` —
  `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
  WHERE id = ? AND user_id = ?`. `description` may be `None` (stored as SQL
  NULL). Commits and returns `cursor.rowcount` (1 on success, 0 if nothing
  matched). No validation logic here — the route validates before calling. Does
  not touch `user_id` or `created_at`.

## Templates
- **Create:** `templates/edit_expense.html`
  - `{% extends "base.html" %}`; `{% block title %}Edit expense — Spendly{% endblock %}`.
  - Structurally a near-clone of `add_expense.html`: `<section class="auth-section">`
    → `<div class="auth-container">` → `.auth-header` (title "Edit an expense",
    subtitle "Update this transaction") → `.auth-card` holding the form.
  - `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` at the
    top of the card.
  - `<form method="POST" action="{{ url_for('edit_expense', id=expense.id) }}">`
    with the same four `.form-group` blocks as the add form:
    - **Amount** — `<input type="number" name="amount" class="form-input"
      step="0.01" min="0.01" required autofocus>`,
      `value="{{ amount if amount is not none else expense.amount }}"`.
    - **Category** — `<select name="category" class="form-input" required>` with
      the disabled placeholder option and one `<option>` per entry in
      `categories`; mark `selected` on the option equal to
      `category or expense.category`.
    - **Date** — `<input type="date" name="date" class="form-input" required>`,
      `value="{{ date or expense.date }}"` (stored dates are already ISO
      `YYYY-MM-DD`).
    - **Description** — `<input type="text" name="description" class="form-input"
      maxlength="{{ max_description_len }}">`, no `required`, label
      "Description (optional)",
      `value="{{ description if description is not none else (expense.description or '') }}"`.
    - `<button type="submit" class="btn-submit">Save changes</button>`.
  - A `.auth-switch`-style line below the card linking back to
    `{{ url_for('profile') }}` ("Back to your profile").
  - No `{% block scripts %}` — no JavaScript.
  - The route passes the freshly-fetched `expense` row on every render (GET and
    the error re-render) so the form always has a fallback for any field the
    user did not re-supply.
- **Modify:** `templates/profile.html`
  - In the "Recent transactions" table (`.profile-txn-table`), add a trailing
    column for row actions:
    - `<thead>`: add `<th class="profile-txn-actions"><span class="sr-only">Actions</span></th>`
      after the Amount header (or a plain `<th>Actions</th>` if no `.sr-only`
      helper exists — check `style.css` first and match what's there).
    - `<tbody>` each row: add
      `<td class="profile-txn-actions"><a href="{{ url_for('edit_expense', id=txn.id) }}" class="profile-txn-edit">Edit</a></td>`
      after the amount cell.
  - No change to the flashed-message block — it already renders
    `get_flashed_messages()[0]`, so `"Expense updated."` surfaces automatically
    after the redirect.
- **base.html** — no change. The nav already has the logged-in "Add expense"
  link; edit is reached from the profile table, not the nav.

## Files to change
- `app.py`
  - Replace the placeholder `edit_expense(id)` function. Add
    `methods=["GET", "POST"]` to the decorator. Move the function up next to
    `add_expense()` (out of the "Placeholder routes" section — leave
    `delete_expense` behind in that section).
  - Login guard → redirect to login (both verbs). Then
    `expense = get_expense_by_id(id, user_id)`; `if expense is None: abort(404)`
    (both verbs). Also re-check `get_user_by_id(user_id)` and clear a stale
    session exactly as `add_expense` does.
  - On `GET`: render `edit_expense.html` with `expense=expense`,
    `categories=CATEGORIES`, `max_description_len=MAX_DESCRIPTION_LEN` (no
    `today` — the date defaults to the expense's own stored date).
  - On `POST`: read `amount`, `category`, `date`, `description` from
    `request.form`; validate with the **same rules as `add_expense`** (see
    "Rules for implementation"); on failure re-render `edit_expense.html` with
    `error=...`, `expense=expense`, `categories`, `max_description_len`, and the
    submitted values so the form is sticky (update nothing, HTTP 200); on
    success call `update_expense(id, user_id, amount, category, date,
    description or None)`, `flash("Expense updated.")`,
    `redirect(url_for("profile"))`.
  - **Shared validation.** The four-field validation block is now needed by two
    routes. Extract it into one module-level helper in `app.py`, e.g.
    `_parse_expense_form(form)` returning `(fields_dict, error_str)` where
    `error_str` is `None` on success and `fields_dict` holds the cleaned
    `amount` (float, 2dp), `category`, `date` (ISO string), and `description`
    (`str` or `None`). Refactor `add_expense`'s POST branch to call the same
    helper so the logic lives in exactly one place. The helper does no
    rendering and no DB work — it only parses and validates.
  - Update the `database.db` import to add `get_expense_by_id` and
    `update_expense`. `abort` must be imported from `flask` (add it to the
    existing `from flask import ...` line — it is not currently imported).
- `database/db.py` — add `get_expense_by_id(...)` and `update_expense(...)` as
  described under "Database changes".
- `templates/profile.html` — add the Actions column (header + per-row Edit
  link) to the transactions table.
- `static/css/style.css` — add an `/* Edit expense (Step 08) */` section. Reuse
  `.auth-section`, `.auth-card`, `.form-group`, `.form-input`, `select.form-input`,
  `.btn-submit`, `.auth-error`, `.auth-switch` as-is (the edit form needs no new
  form styling). Add only: styling for `.profile-txn-edit` (a small text link —
  use `--accent` / `--ink-soft` tokens, no hardcoded hex) and
  `.profile-txn-actions` (right-ish alignment, tight width), plus a `.sr-only`
  utility if one does not already exist. Put any responsive tweaks inside the
  existing `@media (max-width: 900px)` / `@media (max-width: 600px)` blocks — no
  new breakpoints.
- `CLAUDE.md` — in the "Implemented vs stub routes" table, change the
  `'GET /expenses/<id>/edit'` row from `Stub — Step 8` to
  `Implemented — GET renders edit_expense.html pre-filled for the owner; POST
  re-validates and updates the expense, then redirects to /profile; 404s if the
  id is missing or owned by another user`. Leave the `'GET /expenses/<id>/delete'`
  (Step 9) row unchanged.

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only — `?` placeholders in the new `SELECT` and
  `UPDATE`, never f-strings or `%` formatting in SQL. The `WHERE id = ? AND
  user_id = ?` clause is the ownership boundary; it must appear on **both** the
  fetch and the update.
- Passwords hashed with werkzeug (unchanged; no auth code is modified here).
- Use CSS variables — never hardcode hex values. New rules reuse `--accent`,
  `--ink`, `--ink-soft`, `--ink-muted`, `--border`, `--radius-sm`, etc.
- All templates extend `base.html` (`edit_expense.html` must).
- Flask only; SQLite only; vanilla JS only — this step adds **no** JavaScript.
- Routes stay single-responsibility: guard → fetch/authorize → (validate →
  update) → redirect, or re-render on error. The `SELECT` and `UPDATE` live in
  `database/db.py`, not in `app.py`. Validation lives in the shared
  `_parse_expense_form` helper, not inline in either route.
- Ownership: never compare a client-supplied user id. Always scope by
  `session["user_id"]` inside the SQL. A logged-in user requesting another
  user's expense id (GET or POST) gets `abort(404)` — no data disclosed, no row
  updated.
- Server-side validation is mandatory and identical to Step 07 — never trust the
  client. Validate:
  - `amount`: present; parses via `float()` (catch `ValueError`); finite and
    strictly `> 0`; reject `>= MAX_EXPENSE_AMOUNT` (10,000,000); round to 2
    decimals before update.
  - `category`: present and exactly one of `CATEGORIES` — reject anything else.
  - `date`: present and a valid `YYYY-MM-DD` — validate with `_parse_iso_date`;
    `None` result → error. No past/future restriction.
  - `description`: optional; `.strip()`; store `None` when empty; reject longer
    than `MAX_DESCRIPTION_LEN` (200) with an error.
- On **any** validation failure: re-render `edit_expense.html` with a single
  `error` string, the freshly-fetched `expense`, and the submitted values
  re-populated; do **not** update the row; return HTTP 200 (not a redirect, not
  an `abort()`).
- `abort(404)` is used **only** for the missing/not-owned expense. Form
  validation errors re-render the template; they never `abort()`.
- Do not modify `user_id` or `created_at` on update.
- Preserve the placeholder pattern for the still-stubbed `delete_expense` route
  — do not implement or restructure it.
- The success flash (`"Expense updated."`) is consumed on `/profile` via the
  existing `get_flashed_messages()` block so it shows once and does not reappear
  on refresh.

## Definition of done
Run the app (`python3 app.py`, port 5001) and verify:

1. Logged out, `GET /expenses/1/edit` redirects to `/login`; `POST
   /expenses/1/edit` (via curl) also redirects to `/login` and updates no row.
2. Logged in as the seeded demo user (`demo@spendly.com` / `demo123`),
   `GET /expenses/1/edit` renders a form inside `.auth-card` pre-filled with
   expense 1's current amount, category (correct `<option selected>`), date
   (`<input type="date">` set to the stored date), and description. Page source
   shows `<form method="POST" action="/expenses/1/edit">` (or the `url_for`
   equivalent).
3. Changing the amount to `999.99` and submitting redirects to `/profile`,
   which shows an "Expense updated." message once; refreshing `/profile` does
   not show it again.
4. After that edit, the transactions table, "All-time spend", "Average
   transaction", and the category breakdown all reflect the new amount; the
   "Transactions" count is unchanged.
5. In the DB, expense 1's row now has `amount` = `999.99` with the same `id`,
   `user_id`, and `created_at` as before the edit.
6. Editing an expense and clearing the Description field stores SQL NULL for
   `description` (and `/profile` renders it as "—"). Editing one that was NULL
   to add text stores the text.
7. Submitting Amount `0`, a negative amount, or a non-numeric amount re-renders
   the form with an inline `.auth-error` and updates no row; the other entered
   values stay populated.
8. Submitting (via curl) a `category` not in the 7, or a missing/malformed
   `date` (e.g. `date=foo`), or an entirely absent `amount`/`category`/`date`,
   re-renders with a validation error — no traceback, no 500 — and updates no
   row.
9. Logged in as the demo user, `GET /expenses/9999/edit` (nonexistent id)
   returns HTTP 404, not a 500 and not a redirect.
10. Create a second user with an expense, note its id, then as the demo user
    `GET` and `POST` that id at `/expenses/<id>/edit` — both return 404 and the
    other user's row is unchanged.
11. `GET /expenses/abc/edit` (non-integer id) returns 404 (route converter).
12. Every transaction row on `/profile` shows an "Edit" link resolving via
    `url_for('edit_expense', id=txn.id)` — no hardcoded `/expenses/<n>/edit` in
    the template — and each links to that expense's edit form.
13. `/expenses/1/delete` still returns its "coming in Step 9" placeholder
    string; the `delete_expense` route is untouched.
14. `git grep` in `database/db.py` shows the new `SELECT` and `UPDATE` use `?`
    placeholders only — no f-string or `%`-formatted SQL — and both carry
    `user_id = ?` in the `WHERE` clause.
15. `add_expense` still works end-to-end (its POST branch now calls the shared
    `_parse_expense_form` helper): adding a valid expense still redirects to
    `/profile` with "Expense added." and inserts the row.
16. `requirements.txt` is unchanged; the app starts on port 5001 with no errors.
