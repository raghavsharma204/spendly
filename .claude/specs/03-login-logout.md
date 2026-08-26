# Spec: Login and Logout

## Overview
Turns the existing static `GET /login` page and the `GET /logout` stub into a working session-based authentication flow. Users submit their email and password on the login form; the server verifies the credentials against the hashed password stored in the `users` table and, on success, starts a Flask session so the app can recognize the user on later requests. Logging out clears that session. This is the step that makes "being logged in" a real, checkable state in the app — the navbar reflects it, and it lays the groundwork for the profile and expense routes (Steps 4+), which will depend on `session["user_id"]` to know who is making the request.

## Depends on
- Step 1 (database setup) — `database/db.py` `get_db()` and the `users` table. Already implemented.
- Step 2 (registration) — users must be able to register before they can log in; `create_user()` and password hashing via `werkzeug.security.generate_password_hash`. Already implemented.

## Routes
- `POST /login` — validate submitted email/password against `users`, start a session on success and redirect to `/profile`, or re-render `login.html` with an error on failure — public
- `GET /logout` — clear the session and redirect to `/login` with a flashed confirmation message — logged-in (safe no-op if called while logged out)

## Database changes
No database changes. The `users` table already has `email` and `password_hash` columns — verified in `database/db.py`.

## Templates
- **Create:** none
- **Modify:** `templates/login.html`
  - Change `<form method="POST" action="/login">` to `action="{{ url_for('login') }}"` (currently hardcoded)
  - Re-populate the `email` field value (`value="{{ email or '' }}"`) after a failed submission; never re-populate the password field
  - Existing `{% if error %}` block is reused as-is for "invalid email or password" messages
- **Modify:** `templates/base.html`
  - Navbar `.nav-links` conditionally renders based on `session.user_id` (Flask exposes `session` to Jinja automatically, no route changes needed elsewhere):
    - Logged out (current behavior): "Sign in" (`url_for('login')`) and "Get started" (`url_for('register')`)
    - Logged in: "Sign out" (`url_for('logout')`) in place of "Sign in" / "Get started"

## Files to change
- `app.py` — implement `POST` handling on `/login` (validate, create session, redirect), implement `GET /logout` (clear session, flash message, redirect)
- `database/db.py` — add an `authenticate_user(email, password)` helper
- `templates/login.html` — `url_for()` fix and sticky email field
- `templates/base.html` — session-aware navbar links

## Files to create
None

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is available alongside the already-used `generate_password_hash`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — no f-strings in SQL
- Passwords hashed with `werkzeug.security` — verify with `check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `/login` must accept both `GET` and `POST` on the same route (`methods=["GET", "POST"]`); `GET` keeps rendering `login.html` exactly as it does today
- Server-side validation is required: reject empty email/password before querying the database
- Use Flask's built-in `session` (already possible — `app.secret_key` is set in `app.py`) to store `session["user_id"]` on successful login; do not build a custom cookie/token scheme
- On invalid credentials, re-render `login.html` with a single generic `error="Invalid email or password"` — never reveal whether the email exists or the password was wrong
- `GET /logout` clears the session (`session.clear()`), flashes a confirmation message, and redirects to `url_for('login')`
- DB logic (the email lookup and password check) belongs in `database/db.py`, not in the route function in `app.py` — add `authenticate_user(email, password)` there rather than writing raw SQL or calling `check_password_hash` inline in `app.py`
- Do not implement `/profile` (Step 4) beyond its existing placeholder string — `POST /login` redirects there on success, but the route itself stays a stub
- Do not add a `login_required` decorator or guard other stub routes in this step — that belongs to whichever step actually builds the protected pages

## Definition of done
- [ ] `GET /login` still renders the empty form correctly
- [ ] Submitting a registered user's correct email/password redirects to `/profile` and the app.py's Placeholder stub response ("Profile page — coming in Step 4") is shown
- [ ] Submitting a correct email with the wrong password re-renders `login.html` with a generic invalid-credentials error and does not start a session
- [ ] Submitting an email that doesn't exist in `users` re-renders `login.html` with the same generic invalid-credentials error (no hint that the email is unregistered)
- [ ] Submitting with an empty email or password (bypassing the browser's `required` check, e.g. via curl) shows a validation error instead of crashing
- [ ] After a failed submission, the email field is pre-filled with what the user typed; the password field is empty
- [ ] The login form's `action` uses `url_for('login')`, not a hardcoded path
- [ ] While logged in, the navbar shows "Sign out" instead of "Sign in" / "Get started"
- [ ] Visiting `GET /logout` while logged in clears the session, flashes a confirmation message, and redirects to `/login`; the navbar reverts to the logged-out state
- [ ] Visiting `GET /logout` while already logged out does not crash — it just redirects to `/login`
- [ ] App starts and runs on port 5001 without errors after the change
