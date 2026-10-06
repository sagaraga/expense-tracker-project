# Spec: Date Filter For Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page so a logged-in user can
narrow the summary stats, transaction list, and category breakdown to a chosen
period. Step 5 wired the profile page to live data, but every section always
covers the user's entire history (and the transaction list is capped at the 10
newest rows). This step lets the user pick a preset range (This month, Last 30
days, Last 3 months, All time) or a custom from/to date, and all three data
sections re-render for that range. The filter is driven by query-string
parameters on `GET /profile`, so filtered views are bookmarkable and need no JS.

## Depends on
- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4: Profile page static UI
- Step 5: Backend connection (`database/queries.py` helpers and `_build_*_ctx` functions in `app.py`)

## Routes
No new routes. The existing `GET /profile` — logged-in — now accepts optional
query parameters:
- `preset` — one of `this_month`, `last_30_days`, `last_3_months`, `all` (default `all`)
- `start` — `YYYY-MM-DD`, custom range start (inclusive)
- `end` — `YYYY-MM-DD`, custom range end (inclusive)

Precedence: if `start` and/or `end` is present and valid, it is used as a
custom range and `preset` is ignored. Invalid or unparseable dates are ignored
(treated as not supplied) — never a 500. If both are valid and `start > end`,
flash-free fallback: show an inline error message on the page and fall back to
the unfiltered ("all") view.

## Database changes
No database changes. `expenses.date` is already `TEXT` in ISO format, so range
filtering works with `date >= ? AND date <= ?`. (Optional, not required: an
index on `expenses(user_id, date)` — only add it if flagged and kept inside
`init_db()` with `CREATE INDEX IF NOT EXISTS`.)

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats row: preset links/buttons (using
    `url_for('profile', preset=...)`) and a `GET` form with two
    `<input type="date">` fields (`start`, `end`) plus Apply and Clear controls.
  - Highlight the active preset; pre-fill `start`/`end` when a custom range is active.
  - Show the active range label (e.g. "01 Oct 2026 – 06 Oct 2026") near the section titles.
  - Panel title "Recent transactions" becomes "Transactions" when a filter is active.
  - Show an inline error message when the custom range is invalid (`start > end`).
  - Empty state: when the filtered range has no expenses, show "No expenses in this period." in the transaction panel and category panel; stats show ₹0.00 / 0 / —.

## Files to change
- `app.py` — parse/validate filter params, resolve presets to a (start, end) pair using `Asia/Kolkata` "today", pass range to the `_build_*_ctx` helpers, pass filter state (active preset, start, end, label, error) to the template
- `database/queries.py` — add optional `start_date=None, end_date=None` params to `get_recent_transactions`, `get_summary_stats`, `get_category_breakdown`; append `AND date >= ?` / `AND date <= ?` with parameterised values only when provided
- `templates/profile.html` — filter bar and states described above
- `static/css/profile.css` — styles for the filter bar, active preset, and error message (CSS variables only)

## Files to create
- `tests/test_date_filter.py` — unit and route tests (see Definition of done)

## New dependencies
No new dependencies. Use stdlib `datetime` / `zoneinfo` (`Asia/Kolkata`) for "today"; compute month/day offsets with `timedelta` and `date.replace`, no `dateutil`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — build the optional date clauses by appending fixed SQL fragments, never by interpolating user input
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles or `<style>` tags; no JS required (vanilla JS only if added at all)
- DB logic stays in `database/queries.py`; the `profile()` route only parses params, calls helpers, renders
- Date validation uses `datetime.strptime(value, "%Y-%m-%d")` wrapped in try/except; never trust raw query params
- Range bounds are inclusive on both ends
- Preset definitions (relative to today in Asia/Kolkata):
  - `this_month`: first day of the current month → today
  - `last_30_days`: today − 29 days → today
  - `last_3_months`: same day-of-month 3 months ago (clamped to month end) → today
  - `all`: no bounds
- Stats, transactions, and category breakdown must all use the same range so figures stay consistent
- The 10-row transaction cap remains
- All internal links via `url_for()`; currency displays as ₹
- Do not touch the stub routes (`/expenses/add`, edit, delete)
- Keep existing no-filter behaviour of Step 5 unchanged (existing tests must still pass)

## Definition of done
- [ ] Visiting `/profile` with no params behaves exactly as in Step 5 (8 transactions, ₹302.54 total for the seed user)
- [ ] The profile page shows a filter bar with presets (This month, Last 30 days, Last 3 months, All time) and custom From/To date inputs
- [ ] Clicking "This month" updates the URL to `/profile?preset=this_month` and stats, transactions, and categories reflect only this month's expenses
- [ ] The active preset is visually highlighted
- [ ] `/profile?start=2026-10-02&end=2026-10-04` shows only expenses dated 2–4 Oct 2026 inclusive, and the date inputs are pre-filled with those values
- [ ] Total spent, transaction count, top category, and category percentages (still summing to 100) all match the filtered range
- [ ] A range with no expenses shows ₹0.00, 0 transactions, "—" top category, and "No expenses in this period." with no errors
- [ ] `/profile?start=garbage&end=2026-13-45` does not error (200) and falls back to unfiltered data
- [ ] `/profile?start=2026-10-10&end=2026-10-01` shows an inline error message and unfiltered data
- [ ] Clear returns to `/profile` with no params
- [ ] Unauthenticated `GET /profile?preset=this_month` still redirects to `/login`
- [ ] A user never sees another user's expenses under any filter
- [ ] No hardcoded hex colours or inline styles were added; `pytest` passes
