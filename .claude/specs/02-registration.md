# Spec: Registration

## Overview

Turn the existing `GET /register` page into a working sign-up flow. A visitor submits name, email and password; the app validates the input, stores the user with a werkzeug-hashed password, and redirects to the login page. This is Step 2 of the Spendly roadmap: it builds on the data layer from Step 1 and is the prerequisite for login/logout (Step 3) and everything behind authentication.

## Depends on

- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes

- `GET /register` — render the registration form (already exists, unchanged) — public
- `POST /register` — validate the form, create the user, redirect to `/login` on success; re-render the form with an error message on failure — public

Both methods are served by the existing `register` view in `app.py` (`methods=["GET", "POST"]`). No other routes are added or changed. Stub routes (`/logout`, `/profile`, `/expenses/...`) stay untouched.

## Database changes

No database changes. The existing `users` table already has everything needed (`name`, `email UNIQUE`, `password_hash`, `created_at`).

New helpers go in `database/db.py` (DB logic must not live in routes):

- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, returns the new user id. Raises `sqlite3.IntegrityError` if the email already exists.

## Templates

- **Create:** none
- **Modify:** `templates/register.html`
  - Replace the hardcoded `action="/register"` with `action="{{ url_for('register') }}"`
  - Repopulate `name` and `email` inputs with the submitted values on error (never the password)
  - Add `minlength="8"` to the password input
  - Existing `{% if error %}` block is reused for validation errors

## Files to change

- `app.py` — accept POST on `/register`, validation, call db helpers, redirect; import `request`, `redirect`, `url_for`
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — see Templates above

## Files to create

- `tests/test_registration.py` — pytest coverage for the registration flow

## New dependencies

No new dependencies. `werkzeug.security` and `sqlite3` are already in use.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect — no hardcoded URLs
- Route function stays thin: read form, call db helpers, render or redirect
- Use `abort()` for HTTP errors, not bare string returns
- Validation (server-side, in this order), re-rendering `register.html` with `error` and status 400:
  - name, email and password are all present after stripping whitespace
  - email contains `@` and a domain part
  - password is at least 8 characters
  - email is not already registered (catch `sqlite3.IntegrityError` from `create_user` as the source of truth, so a race cannot create duplicates)
- Normalise email with `.strip().lower()` before lookup and insert
- Do not auto-login; there is no session until Step 3. Redirect to `login` on success
- Do not implement `/logout`, `/profile` or any other stub route
- Do not modify `login.html` beyond what is strictly required (nothing expected)

## Definition of done

- [ ] `GET /register` still renders the form with status 200
- [ ] Submitting valid name, email and password creates a row in `users` and redirects (302) to `/login`
- [ ] The stored `password_hash` is not the plaintext password and verifies with `check_password_hash`
- [ ] Registering an email that already exists (e.g. `demo@spendly.com`) re-renders the form with an error and does not create a second row
- [ ] Email matching is case-insensitive: `Demo@Spendly.com` is rejected as a duplicate
- [ ] A password shorter than 8 characters is rejected with an error message
- [ ] Empty or whitespace-only name, email or password is rejected with an error message
- [ ] On error, the name and email fields keep their submitted values and the password field is empty
- [ ] The form posts via `url_for('register')`; no hardcoded `/register` remains in `register.html`
- [ ] The app starts on port 5001 without errors
- [ ] `pytest tests/test_registration.py` passes
