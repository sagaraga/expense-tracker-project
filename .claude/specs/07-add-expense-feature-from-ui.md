# Spec: Add Expense Feature From UI

## Overview
Step 7 lets a logged-in user record a new expense from the browser. Until now
expenses only exist via `seed_db()`, and `/expenses/add` is a stub returning a
raw string. This step turns it into a real page: a form (amount, category,
date, description) that validates input, inserts a row into `expenses` for the
current user, and redirects to `/profile` where the new expense appears in the
transactions list, stats, and category breakdown. An "Add expense" entry point
is added to the profile page so the feature is reachable from the UI.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4/5: Profile page wired to live data (`database/queries.py`)
- Step 6: Date filter (profile re-renders with the new expense; `_today()` helper in `app.py` uses `Asia/Kolkata`)

## Routes
- `GET /expenses/add` — render the empty add-expense form (date pre-filled with today in `Asia/Kolkata`) — logged-in (redirect to `login` if not)
- `POST /expenses/add` — validate and insert the expense, then redirect to `profile` — logged-in
  - On validation error: re-render the form with the error and the user's entered values, status 400
  - On success: `flash("Expense added.", "success")` and `redirect(url_for("profile"))`

The route changes from a stub to `methods=["GET", "POST"]`. Edit and delete stubs are untouched.

## Database changes
No schema changes. `expenses` already has `user_id`, `amount`, `category`, `date`
(`YYYY-MM-DD` text), `description`. Add one helper to `database/queries.py`:
- `create_expense(user_id, amount, category, date, description)` — parameterised `INSERT`, committed via `with conn:`, returns `lastrowid`, closes the connection in `finally`

Also expose the allowed category list as a single constant in `database/queries.py`
(`EXPENSE_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]`),
matching the categories used by `seed_db()`, so the form and validation share one source.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with
  - Amount (`type="number"`, `step="0.01"`, `min="0.01"`, required)
  - Category (`<select>` over `categories`, required)
  - Date (`type="date"`, required, default today)
  - Description (`type="text"`, optional, `maxlength="200"`)
  - Submit button and a Cancel link (`url_for('profile')`)
  - Error block (same pattern as `auth-error` in `login.html`)
- **Modify:** `templates/profile.html` — add an "Add expense" link/button
  (`url_for('add_expense')`) near the transactions panel header; render
  flashed "success" messages if profile does not already display them
  (it already renders flashed "error" messages for the date filter — reuse that markup/category handling).

## Files to change
- `app.py` — implement `add_expense()` (GET + POST) replacing the stub; import `create_expense` and `EXPENSE_CATEGORIES` from `database.queries`; add a small `_validate_expense_form(form)` helper returning `(clean_values, error)`
- `database/queries.py` — add `create_expense()` and `EXPENSE_CATEGORIES`
- `templates/profile.html` — add entry point link and success flash rendering
- `static/css/profile.css` — style the add button and success flash (CSS variables only)
- `CLAUDE.md` — update the routes table: `/expenses/add` becomes Implemented

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — form-page styles, loaded via `{% block head %}` (no inline `<style>`); reuse `form-group`, `form-input`, `btn-submit` from `style.css` where possible
- `tests/test_add_expense.py` — route and helper tests (see Definition of done)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/queries.py`; the route only validates, calls `create_expense`, redirects (or re-renders on error)
- `user_id` always comes from `session["user_id"]`, never from the form
- Unauthenticated GET or POST redirects to `login` and writes nothing
- Server-side validation (never rely on HTML attributes alone):
  - `amount`: parse with `Decimal`/`float` in try/except; must be finite and `> 0`; reject `nan`/`inf`; round to 2 decimals; sensible upper bound (e.g. `<= 10_000_000`)
  - `category`: must be in `EXPENSE_CATEGORIES`
  - `date`: `datetime.strptime(value, "%Y-%m-%d")` in try/except; must not be in the future (compare with `_today()`)
  - `description`: strip, optional, max 200 characters, stored as `None` if empty
- Use `abort()` for HTTP errors, not raw string returns; validation errors re-render the form with status 400
- Jinja autoescaping stays on; never mark user input `|safe`
- All internal links and form actions via `url_for()`; currency displays as ₹
- Follow the Post/Redirect/Get pattern on success
- Do not implement the edit or delete stub routes (Steps 8 and 9)
- Vanilla JS only, and none is required for this step

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Posting to `/expenses/add` while logged out redirects to `/login` and inserts no row
- [ ] Logged in, `GET /expenses/add` returns 200 with amount, category, date, and description fields; date defaults to today (IST); category dropdown lists all seven categories
- [ ] The profile page shows an "Add expense" link that navigates to `/expenses/add`
- [ ] Submitting a valid expense redirects to `/profile`, shows an "Expense added." message, and the expense appears in Transactions with the correct date, description, category, and ₹ amount
- [ ] Profile total spent, transaction count, and category breakdown reflect the new expense
- [ ] The new row in `expenses` has the logged-in user's `user_id` and the amount stored to 2 decimals
- [ ] Empty description is accepted and stored as NULL
- [ ] Amount of `0`, a negative number, `abc`, `nan`, or empty is rejected with an error message, status 400, and no row inserted
- [ ] A category not in the list (e.g. via a tampered POST) is rejected with 400
- [ ] A malformed date or a future date is rejected with 400
- [ ] A description over 200 characters is rejected with 400
- [ ] On any validation error the form re-renders with the user's previously entered values preserved
- [ ] A submitted `user_id` form field is ignored (row is created for the session user)
- [ ] A description containing `<script>` renders escaped on the profile page
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` still return their stub responses
- [ ] `pytest tests/test_add_expense.py` passes
