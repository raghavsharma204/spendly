# Spec: Registration

## Overview
Turns the existing `GET /register` page from a static form into a working signup flow. Users submit their name, email, and password; the server validates the input, checks for a duplicate email, hashes the password, and inserts a new row into the `users` table. This is the first step that writes to the database from a route, and it lays the groundwork for the login/session step that follows — registration itself does not log the user in or create a session; on success it displays the message and redirects to the login page.

## Depends on
- Step 1 (database setup) — `database/db.py` must provide a working `get_db()` and a `users` table with a `UNIQUE` email constraint. Already implemented.

## Routes
- `POST /register` — validate submitted signup form, create the user, redirect to `/login` on success or re-render the form with an error on failure — public

## Database changes
No database changes. The `users` table already has the required columns (`name`, `email` UNIQUE, `password_hash`) — verified in `database/db.py`.

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Change `<form method="POST" action="/register">` to use `action="{{ url_for('register') }}"`
  - Re-populate `name` and `email` field values (`value="{{ name or '' }}"`, `value="{{ email or '' }}"`) after a failed submission so the user isn't forced to retype them; never re-populate the password field
  - Existing `{% if error %}` block is reused as-is for validation/duplicate-email messages
- **Modify:** `templates/login.html`
  - Add a `{% with messages = get_flashed_messages() %}` block rendering the first message in a new `.auth-success` div, alongside the existing `{% if error %}` block

## Files to change
- `app.py` — implement `POST` handling on the `/register` route, set `app.secret_key`, `flash()` on success
- `templates/register.html` — `url_for()` fix and sticky form values
- `templates/login.html` — display flashed success message
- `static/css/style.css` — add `.auth-success` style

## Files to create
None

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already used in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — no f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` (`pbkdf2:sha256`), never stored in plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `/register` must accept both `GET` and `POST` on the same route (`methods=["GET", "POST"]`)
- Server-side validation is required even though the inputs have HTML5 `required`/`type` attributes — never trust client-side validation alone
- Validate: name, email, and password are all non-empty; password is at least 8 characters (matches the placeholder text already in the form)
- Check for an existing email before inserting; on conflict, re-render `register.html` with `error="Email already registered"` (do not rely on catching the SQLite `UNIQUE` constraint as the primary path — check first, but the constraint remains as a safety net)
- On success, use `flash("Registration successful — please sign in.")` then `redirect(url_for('login'))` — this requires `app.secret_key` to be set; do not create a user-authentication session or log the user in, that belongs to the login/session step
- `templates/login.html` must display the flashed message (via `get_flashed_messages()`) in a new `.auth-success` style, alongside its existing `.auth-error` block
- DB logic (the insert, the duplicate-email check) belongs in `database/db.py`, not in the route function in `app.py` — add a small `create_user(name, email, password)` -style helper there rather than writing raw SQL inline in `app.py`

## Definition of done
- [ ] `GET /register` still renders the empty form correctly
- [ ] Submitting valid name/email/password redirects to `/login` and adds exactly one new row to `users` with a hashed (not plaintext) password
- [ ] Submitting an email that already exists in `users` re-renders `register.html` with an inline error and does not create a second row
- [ ] Submitting with an empty name, email, or password (bypassing the browser's `required` check, e.g. via curl) shows a validation error instead of crashing or inserting a row
- [ ] Submitting a password shorter than 8 characters shows a validation error and does not insert a row
- [ ] After a failed submission, the name and email fields are pre-filled with what the user typed; the password field is empty
- [ ] The register form's `action` uses `url_for('register')`, not a hardcoded path
- [ ] After a successful registration, `/login` displays a "Registration successful" flash message once, then it does not reappear on refresh
- [ ] App starts and runs on port 5001 without errors after the change
