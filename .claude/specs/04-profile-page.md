# Spec: Profile Page

## Overview
Turns the existing `GET /profile` stub into a real, logged-in-only page. It is the first protected route in Spendly, so this step introduces the "must be signed in" guard pattern that later expense routes (Steps 7-9) will reuse. The page shows the signed-in user's account info (name, email, member since date) and a read-only snapshot of their spending — total spent and a per-category breakdown — pulled from the `expenses` rows already sitting in the database via `seed_db()`. It does not add any way to create, edit, or delete expenses; that's Steps 7-9. This step is about identity and visibility, not data entry.

## Depends on
- Step 1 (database setup) — `database/db.py` `get_db()`, `init_db()`, and the `users`/`expenses` tables. Already implemented.
- Step 3 (login/logout) — session-based auth via `session["user_id"]`, set on successful login. Already implemented.

## Routes
- `GET /profile` — render the signed-in user's account info and expense summary; if no `session["user_id"]`, redirect to `GET /login` — logged-in only

## Database changes
No schema changes. The `users` table already has `name`, `email`, `created_at`; the `expenses` table already has `user_id`, `amount`, `category`, `date` — verified in `database/db.py`.

New query helpers needed in `database/db.py` (no DB logic in `app.py`):
- `get_user_by_id(user_id)` — `SELECT * FROM users WHERE id = ?`, returns the row or `None`
- `get_expense_summary(user_id)` — returns the total amount spent and a per-category breakdown, e.g. `SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? GROUP BY category` plus an overall `SUM(amount)` total; parameterized, no f-strings

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; shows name/email/member-since in an account card, and total spend + category breakdown (reuse the `.mock-bar-row` / `.mock-bar-track` style pattern from `landing.html`'s hero mock card, adapted with real data instead of hardcoded percentages)
- **Modify:** `templates/base.html` — navbar `.nav-links`, logged-in branch: add a "Profile" link (`url_for('profile')`) alongside "Sign out"

## Files to change
- `app.py` — implement `GET /profile`: redirect to `/login` if not signed in, otherwise fetch user + summary and render `profile.html`
- `database/db.py` — add `get_user_by_id(user_id)` and `get_expense_summary(user_id)`
- `templates/base.html` — add "Profile" nav link for logged-in users

## Files to create
- `templates/profile.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — no f-strings in SQL
- Passwords hashed with `werkzeug.security` (unchanged by this step — no password handling here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `GET /profile` must check `session.get("user_id")` and redirect to `url_for('login')` when absent — do not render any part of the page for anonymous visitors
- Do not add a general-purpose `login_required` decorator unless it's trivial to scope to just this route — a simple inline check is acceptable and matches the codebase's current style (no decorators used elsewhere yet)
- DB logic (fetching the user, computing totals) belongs in `database/db.py` via `get_user_by_id` and `get_expense_summary` — not written inline in the route
- Do not implement `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete` beyond their existing placeholder strings — this step is read-only
- If a user has zero expenses (edge case, not the seeded demo user), the summary section should show a sensible empty state, not a crash or a division-by-zero

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as the seeded demo user (`demo@spendly.com` / `demo123`) and visiting `/profile` shows their name and email
- [ ] The page shows a total spend figure that matches the sum of the seeded demo expenses, formatted in ₹
- [ ] The page shows a per-category breakdown (Food, Transport, Bills, Health, Entertainment, Shopping, Other) matching the seeded demo data, with categories that have no spend simply omitted or shown as ₹0 — not crashing
- [ ] The navbar shows a "Profile" link next to "Sign out" while logged in, and clicking it loads `/profile`
- [ ] The navbar does not show "Profile" while logged out
- [ ] `app.py`'s `/profile` route renders `profile.html` via `render_template`, not a raw string
- [ ] App starts and runs on port 5001 without errors after the change
