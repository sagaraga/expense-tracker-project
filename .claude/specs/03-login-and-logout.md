# Spec: Login and Logout

## Overview

Make sign-in and sign-out work. A visitor submits their email and password on the existing login page; the app checks them against the stored werkzeug hash, starts a Flask session, and redirects to the landing page. `GET /logout` clears the session. The navbar reflects whether the user is signed in. This is Step 3 of the Spendly roadmap: Step 2 created accounts, and every later step (profile, expenses) needs a way to know who the current user is.

## Depends on

- Step 1 — Database setup (`users` table, `get_db()`)
- Step 2 — Registration (users can be created; `get_user_by_email()` and `create_user()` exist in `database/db.py`)

## Routes

- `GET /login` — render the login form (already exists); if the user is already signed in, redirect to `landing` — public
- `POST /login` — validate credentials; on success store the user id in the session and redirect to `landing`; on failure re-render the form with an error and status 401 — public
- `GET /logout` — clear the session and redirect to `landing` — public (harmless if not signed in)
- `GET /register` — existing route; add one behaviour: if the user is already signed in, redirect to `landing` — public

`/logout` keeps its existing `GET` method and endpoint name. No other routes are added or changed. Stub routes for `/profile` and `/expenses/...` stay untouched.

## Database changes

No database changes. `users` already has `email`, `password_hash` and `id`. `get_user_by_email()` from Step 2 is reused to look the user up, so no new db helper is needed.

## Templates

- **Create:** none
- **Modify:**
  - `templates/login.html` — change the hardcoded `action="/login"` to `action="{{ url_for('login') }}"`; repopulate the `email` input with the submitted value on error (never the password)
  - `templates/base.html` — navbar shows **Sign out** (`url_for('logout')`) when `session.user_id` is set, and the existing **Sign in** / **Get started** links otherwise

## Files to change

- `app.py` — set `app.secret_key`; implement `POST /login`; implement `/logout`; redirect signed-in users away from `/login` and `/register`; import `session`, `check_password_hash`, `get_user_by_email`, `os`
- `templates/login.html` — see Templates above
- `templates/base.html` — see Templates above
- `.gitignore` — only if needed to keep any local secret file out of git (expected: no change)

## Files to create

- `tests/test_login_logout.py` — pytest coverage for login, logout and the navbar state

## New dependencies

No new dependencies. Flask's built-in `session` and `werkzeug.security.check_password_hash` are already available.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with werkzeug; verify with `check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect — no hardcoded URLs
- Route functions stay thin: read form, call db helper, render or redirect. DB access goes through `get_user_by_email()` in `database/db.py`
- Read the secret key from the `SPENDLY_SECRET_KEY` environment variable. If it is unset, fall back to a clearly named development-only value so the app still starts locally. Do not commit a real secret
- Store only the user id in the session (`session["user_id"]`); do not store the password hash or email
- Normalise the email with `.strip().lower()` before lookup, matching registration
- Use one generic error message for both an unknown email and a wrong password ("Invalid email or password."), so the form does not reveal which emails are registered
- Failed login re-renders `login.html` with status 401 and the submitted email; blank fields get a 400 and "All fields are required."
- Call `session.clear()` on logout, and before setting `user_id` on login
- Do not add a `next` or other redirect parameter, so there is no open-redirect surface
- Do not implement `/profile` or any other stub route. After login, redirect to `landing`
- Do not add flash messages or any new pip package

## Definition of done

- [ ] `GET /login` renders the form with status 200 for a signed-out visitor
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) to `/` and the session holds that user's id
- [ ] A wrong password re-renders the form with "Invalid email or password." and status 401, with no session set
- [ ] An unknown email shows the same "Invalid email or password." message as a wrong password
- [ ] Email matching is case-insensitive: `Demo@Spendly.com` logs in successfully
- [ ] Blank email or password shows "All fields are required." and status 400
- [ ] On a failed login, the email field keeps its value and the password field is empty
- [ ] A user registered through `/register` can immediately log in with the same credentials
- [ ] While signed in, the navbar shows **Sign out** and hides **Sign in** and **Get started**
- [ ] While signed out, the navbar shows **Sign in** and **Get started** and hides **Sign out**
- [ ] `GET /logout` clears the session, redirects (302) to `/`, and the navbar returns to the signed-out state
- [ ] `GET /logout` when not signed in still redirects to `/` without an error
- [ ] A signed-in user visiting `/login` or `/register` is redirected to `/`
- [ ] The login form posts via `url_for('login')`; no hardcoded `/login` remains in `login.html`
- [ ] The app starts on port 5001 without errors, with and without `SPENDLY_SECRET_KEY` set
- [ ] `pytest` passes, including the existing database and registration tests
