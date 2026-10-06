# Spec: Edit Expense Feature In UI

## Overview
Step 8 lets a logged-in user correct an existing expense from the browser.
Step 7 added expense creation, but a typo in an amount, category, date or
description currently cannot be fixed. This step replaces the `/expenses/<id>/edit`
stub with a real page: a form pre-filled with the expense's current values that
validates input with the same rules as the add form, updates the row, and
redirects to `/profile` where the transactions list, stats and category
breakdown reflect the change. An "Edit" link is added to each transaction row on
the profile page so the feature is reachable from the UI. A user can only edit
their own expenses.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4/5: Profile page wired to live data (`database/queries.py`)
- Step 6: Date filter (`_today()` helper in `app.py`, `Asia/Kolkata`)
- Step 7: Add expense (`_validate_expense_form()`, `EXPENSE_CATEGORIES`, `add_expense.html`, `add_expense.css`)

## Routes
- `GET /expenses/<int:id>/edit` — render the form pre-filled with the expense's current values — logged-in (redirect to `login` if not); `abort(404)` if the expense does not exist or belongs to another user
- `POST /expenses/<int:id>/edit` — validate and update the expense, then redirect to `profile` — logged-in
  - Unauthenticated: redirect to `login`, write nothing
  - Expense missing or owned by another user: `abort(404)`, write nothing
  - On validation error: re-render the form with the error and the user's entered values, status 400
  - On success: `flash("Expense updated.", "success")` and `redirect(url_for("profile"))`

The route changes from a stub to `methods=["GET", "POST"]`. The delete stub is untouched.

## Database changes
No schema changes. Add two helpers to `database/queries.py`:
- `get_expense(expense_id, user_id)` — parameterised `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`; returns the row or `None`; closes the connection in `finally`
- `update_expense(expense_id, user_id, amount, category, date, description)` — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`, committed via `with conn:`, returns `cursor.rowcount` (0 means not found / not owned), closes the connection in `finally`

Also update `get_recent_transactions()` in `database/queries.py` to include `id` in the selected columns so each row can link to its edit page. Existing callers/tests must keep working.

## Templates
- **Create:** none. Reuse `templates/add_expense.html` for both add and edit to avoid duplicating the form (see Modify).
- **Modify:**
  - `templates/add_expense.html` — make the page title, heading, subtitle, form `action` and submit-button label depend on a `form_action` / `is_edit` context variable passed by the route (add: current behaviour, `url_for('add_expense')`, "Add expense"; edit: `url_for('edit_expense', id=expense_id)`, "Edit expense", "Save changes"). Pre-filled values still come from `form`. Still extends `base.html`.
  - `templates/profile.html` — add an "Edit" link (`url_for('edit_expense', id=t.id)`) in each transaction row (new, unlabelled or "Actions" column header); `<td>` colspans/empty state unaffected.

## Files to change
- `app.py` — implement `edit_expense(id)` (GET + POST) replacing the stub; import `get_expense` and `update_expense`; include `id` in `_build_transactions_ctx`; update `add_expense()` to pass the new template context variables if required
- `database/queries.py` — add `get_expense()`, `update_expense()`; add `id` to `get_recent_transactions()` select
- `templates/add_expense.html` — shared add/edit form as described above
- `templates/profile.html` — Edit link per transaction row
- `static/css/profile.css` — style the Edit link/actions column (CSS variables only)
- `CLAUDE.md` — update the routes table: `/expenses/<id>/edit` becomes Implemented (Step 8)

## Files to create
- `tests/test_edit_expense.py` — route and helper tests (see Definition of done)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/queries.py`; the route only fetches, validates, calls `update_expense`, redirects (or re-renders on error)
- Reuse `_validate_expense_form()` from Step 7 — do not duplicate validation rules
- `user_id` always comes from `session["user_id"]`, never from the form; ownership is enforced in the SQL (`AND user_id = ?`) for both the read and the update
- A missing expense and another user's expense both return 404 (do not reveal existence)
- Unauthenticated GET or POST redirects to `login` and writes nothing
- Use `abort()` for HTTP errors, not raw string returns; validation errors re-render the form with status 400
- Jinja autoescaping stays on; never mark user input `|safe`
- All internal links and form actions via `url_for()`; currency displays as ₹
- Follow the Post/Redirect/Get pattern on success
- Pre-fill the amount with a plain 2-decimal value (e.g. `12.50`), and a `NULL` description as an empty string
- Do not implement the delete stub route (Step 9)
- Vanilla JS only, and none is required for this step

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Posting to `/expenses/<id>/edit` while logged out redirects to `/login` and changes no row
- [ ] Each transaction row on `/profile` shows an "Edit" link that navigates to that expense's edit page
- [ ] Logged in, `GET /expenses/<id>/edit` for your own expense returns 200 with amount, category, date and description pre-filled with the stored values, and the page is clearly labelled as editing (not adding)
- [ ] `GET` or `POST` on `/expenses/<id>/edit` for another user's expense returns 404 and the row is unchanged
- [ ] `GET` or `POST` on `/expenses/99999/edit` (non-existent) returns 404
- [ ] Submitting valid changes redirects to `/profile`, shows an "Expense updated." message, and the Transactions list shows the new date, description, category and ₹ amount for that row (no duplicate row created)
- [ ] Profile total spent and category breakdown reflect the edited amount/category
- [ ] The updated `expenses` row keeps its original `id` and `user_id`, and the amount is stored to 2 decimals
- [ ] Clearing the description is accepted and stored as NULL
- [ ] Amount of `0`, a negative number, `abc`, `nan`, or empty is rejected with an error message, status 400, and the row is unchanged
- [ ] A category not in the list (tampered POST) is rejected with 400
- [ ] A malformed or future date is rejected with 400
- [ ] A description over 200 characters is rejected with 400
- [ ] On any validation error the form re-renders with the user's submitted values preserved and still posts to the same edit URL
- [ ] A submitted `user_id` form field is ignored
- [ ] A description containing `<script>` renders escaped on the edit form and on the profile page
- [ ] The Add expense page still works exactly as before (title, heading, submit label, redirect, flash)
- [ ] `/expenses/<id>/delete` still returns its stub response
- [ ] `pytest tests/test_edit_expense.py` passes and the existing test suite still passes
