"""Tests for Step 6: date-range filter on the profile page."""
import html as html_lib
import re
from datetime import date

import pytest

import app as app_module
from database import db
from database import queries

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
OTHER_EMAIL = "other@spendly.com"
OTHER_PASSWORD = "other123"
ERROR_TEXT = "Start date must be before end date."

# Total of the 8 seed rows (all in the current month), see database/db.py.
SEED_TOTAL = 12.50 + 35.00 + 89.99 + 45.00 + 18.00 + 64.75 + 10.00 + 27.30
SEED_COUNT = 8

# Fixed-date rows inserted for the demo user (all far from the seed month).
FIXED_ROWS = [
    (100.00, "Food", "2020-01-31", "Jan-end"),
    (200.00, "Transport", "2020-02-01", "Feb-start"),
    (300.00, "Food", "2020-02-15", "Feb-mid"),
    (50.00, "Bills", "2020-03-01", "Mar-start"),
]
FIXED_TOTAL = sum(r[0] for r in FIXED_ROWS)  # 650.00


def money(amount):
    return f"₹{amount:,.2f}"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


def add_expense(user_id, amount, category, date_str, description):
    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date_str, description),
            )
    finally:
        conn.close()


@pytest.fixture
def demo_id(client):
    return db.get_user_by_email(DEMO_EMAIL)["id"]


@pytest.fixture
def fixed_rows(client, demo_id):
    for amount, category, date_str, description in FIXED_ROWS:
        add_expense(demo_id, amount, category, date_str, description)
    return demo_id


@pytest.fixture
def other_user(client):
    user_id = db.create_user("Other Person", OTHER_EMAIL, OTHER_PASSWORD)
    add_expense(user_id, 999.00, "Shopping", "2020-02-10", "OtherUserTxn")
    return user_id


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def get_profile(client, query="", email=DEMO_EMAIL, password=DEMO_PASSWORD):
    login(client, email, password)
    response = client.get("/profile" + query)
    assert response.status_code == 200, "Expected /profile to return 200"
    return response.get_data(as_text=True)


def stat_value(page, label):
    match = re.search(
        r'profile-stat-label">' + re.escape(label) + r'</span>\s*'
        r'<span class="profile-stat-value">(.*?)</span>',
        page,
        re.S,
    )
    assert match, f"Stat '{label}' not found"
    return match.group(1).strip()


def preset_tag(page, label):
    for tag in re.findall(r"<a\s[^>]*>.*?</a>", page, re.S):
        if re.sub(r"<[^>]+>", "", tag).strip() == label:
            return tag
    raise AssertionError(f"Preset link '{label}' not found")


def href_of(tag):
    return html_lib.unescape(re.search(r'href="([^"]*)"', tag).group(1))


# ------------------------------------------------------------------ #
# Query helpers                                                       #
# ------------------------------------------------------------------ #

class TestQueryHelpers:
    def test_summary_stats_inclusive_bounds(self, fixed_rows):
        stats = queries.get_summary_stats(
            fixed_rows, date_from="2020-02-01", date_to="2020-02-15"
        )
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == pytest.approx(500.00)
        assert stats["top_category"] == "Food"

    def test_summary_stats_single_day_range(self, fixed_rows):
        stats = queries.get_summary_stats(
            fixed_rows, date_from="2020-02-01", date_to="2020-02-01"
        )
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == pytest.approx(200.00)
        assert stats["top_category"] == "Transport"

    def test_summary_stats_excludes_rows_outside_range(self, fixed_rows):
        stats = queries.get_summary_stats(
            fixed_rows, date_from="2020-02-02", date_to="2020-02-28"
        )
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == pytest.approx(300.00)

    def test_summary_stats_empty_range(self, fixed_rows):
        stats = queries.get_summary_stats(
            fixed_rows, date_from="1999-01-01", date_to="1999-12-31"
        )
        assert stats["transaction_count"] == 0
        assert stats["total_spent"] == 0

    def test_summary_stats_no_dates_matches_unfiltered(self, fixed_rows):
        stats = queries.get_summary_stats(fixed_rows)
        assert stats["transaction_count"] == SEED_COUNT + len(FIXED_ROWS)
        assert stats["total_spent"] == pytest.approx(SEED_TOTAL + FIXED_TOTAL)
        assert stats == queries.get_summary_stats(
            fixed_rows, date_from=None, date_to=None
        )

    def test_summary_stats_ignores_other_users(self, fixed_rows, other_user):
        stats = queries.get_summary_stats(
            fixed_rows, date_from="2020-02-01", date_to="2020-02-28"
        )
        assert stats["total_spent"] == pytest.approx(500.00)
        other = queries.get_summary_stats(
            other_user, date_from="2020-02-01", date_to="2020-02-28"
        )
        assert other["total_spent"] == pytest.approx(999.00)
        assert other["transaction_count"] == 1

    def test_recent_transactions_inclusive_bounds(self, fixed_rows):
        rows = queries.get_recent_transactions(
            fixed_rows, date_from="2020-02-01", date_to="2020-02-15"
        )
        assert [r["description"] for r in rows] == ["Feb-mid", "Feb-start"], (
            "Expected inclusive range, newest first"
        )

    def test_recent_transactions_empty_range(self, fixed_rows):
        rows = queries.get_recent_transactions(
            fixed_rows, date_from="1999-01-01", date_to="1999-12-31"
        )
        assert rows == []

    def test_recent_transactions_no_dates_unfiltered(self, fixed_rows):
        rows = queries.get_recent_transactions(fixed_rows, limit=100)
        assert len(rows) == SEED_COUNT + len(FIXED_ROWS)

    def test_recent_transactions_isolated_per_user(self, fixed_rows, other_user):
        rows = queries.get_recent_transactions(
            fixed_rows, date_from="2020-02-01", date_to="2020-02-28"
        )
        assert "OtherUserTxn" not in [r["description"] for r in rows]

    def test_recent_transactions_limit_still_applies_with_filter(self, client, demo_id):
        for day in range(1, 13):
            add_expense(demo_id, 1.00, "Food", f"2018-05-{day:02d}", f"Bulk{day}")
        rows = queries.get_recent_transactions(
            demo_id, date_from="2018-05-01", date_to="2018-05-31"
        )
        assert len(rows) == 10, "Default limit of 10 must still apply"
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True), "Expected newest first"
        stats = queries.get_summary_stats(
            demo_id, date_from="2018-05-01", date_to="2018-05-31"
        )
        assert stats["transaction_count"] == 12

    def test_category_breakdown_filtered(self, fixed_rows):
        breakdown = queries.get_category_breakdown(
            fixed_rows, date_from="2020-02-01", date_to="2020-03-01"
        )
        by_name = {b["name"]: b for b in breakdown}
        assert set(by_name) == {"Food", "Transport", "Bills"}
        assert by_name["Food"]["amount"] == pytest.approx(300.00)
        assert by_name["Transport"]["amount"] == pytest.approx(200.00)
        assert by_name["Bills"]["amount"] == pytest.approx(50.00)
        assert breakdown[0]["name"] == "Food", "Expected sorted by amount desc"

    def test_category_breakdown_percentages_sum_to_100(self, fixed_rows):
        breakdown = queries.get_category_breakdown(
            fixed_rows, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert sum(b["pct"] for b in breakdown) == 100

    def test_category_breakdown_empty_range(self, fixed_rows):
        assert queries.get_category_breakdown(
            fixed_rows, date_from="1999-01-01", date_to="1999-12-31"
        ) == []

    def test_category_breakdown_no_dates_unfiltered(self, fixed_rows):
        breakdown = queries.get_category_breakdown(fixed_rows)
        total = sum(b["amount"] for b in breakdown)
        assert total == pytest.approx(SEED_TOTAL + FIXED_TOTAL)
        assert sum(b["pct"] for b in breakdown) == 100

    def test_category_breakdown_isolated_per_user(self, fixed_rows, other_user):
        breakdown = queries.get_category_breakdown(
            fixed_rows, date_from="2020-02-01", date_to="2020-02-28"
        )
        assert "Shopping" not in {b["name"] for b in breakdown}

    def test_helpers_treat_sql_injection_as_data(self, fixed_rows):
        evil = "2020-01-01' OR '1'='1"
        stats = queries.get_summary_stats(
            fixed_rows, date_from=evil, date_to="2020-12-31"
        )
        # The bound is compared as plain text, so only the fixed 2020 rows
        # match; an OR bypass would also return the seed rows.
        plain = queries.get_summary_stats(
            fixed_rows, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert stats["transaction_count"] == plain["transaction_count"]
        # expenses table must still exist
        assert queries.get_summary_stats(fixed_rows)["transaction_count"] > 0


# ------------------------------------------------------------------ #
# Route: no params / custom range                                     #
# ------------------------------------------------------------------ #

class TestProfileRoute:
    def test_unauthenticated_with_filter_redirects_to_login(self, client):
        response = client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    def test_no_params_shows_unfiltered_data(self, client, fixed_rows):
        page = get_profile(client)
        assert stat_value(page, "Total spent") == money(SEED_TOTAL + FIXED_TOTAL)
        assert stat_value(page, "Transactions") == str(SEED_COUNT + len(FIXED_ROWS))
        assert "Electricity bill" in page
        assert ERROR_TEXT not in page

    def test_custom_range_filters_all_three_sections(self, client, fixed_rows):
        page = get_profile(client, "?date_from=2020-02-01&date_to=2020-02-15")
        assert stat_value(page, "Total spent") == money(500.00)
        assert stat_value(page, "Transactions") == "2"
        assert stat_value(page, "Top category") == "Food"
        assert "Feb-mid" in page and "Feb-start" in page
        for hidden in ("Jan-end", "Mar-start", "Electricity bill"):
            assert hidden not in page, f"{hidden} should be filtered out"
        # category breakdown: only Food and Transport rows
        breakdown = page.split("Category breakdown")[1]
        assert "Food" in breakdown and "Transport" in breakdown
        assert "Bills" not in breakdown
        assert len(re.findall(r'class="cat-bar pct-\d+"', page)) == 2
        assert ERROR_TEXT not in page

    def test_custom_range_equal_dates_is_valid(self, client, fixed_rows):
        page = get_profile(client, "?date_from=2020-02-15&date_to=2020-02-15")
        assert ERROR_TEXT not in page
        assert stat_value(page, "Total spent") == money(300.00)
        assert "Feb-mid" in page and "Feb-start" not in page

    def test_filtered_view_keeps_rupee_symbol(self, client, fixed_rows):
        page = get_profile(client, "?date_from=2020-02-01&date_to=2020-02-15")
        assert stat_value(page, "Total spent").startswith("₹")
        body = page.split("<tbody>")[1].split("</tbody>")[0]
        assert body.count("₹") == 2

    def test_custom_range_prefills_date_inputs(self, client, fixed_rows):
        page = get_profile(client, "?date_from=2020-02-01&date_to=2020-02-15")
        assert re.search(r'name="date_from"[^>]*value="2020-02-01"', page)
        assert re.search(r'name="date_to"[^>]*value="2020-02-15"', page)

    def test_date_inputs_are_html_date_type(self, client):
        page = get_profile(client)
        assert re.search(r'<input type="date" name="date_from"', page)
        assert re.search(r'<input type="date" name="date_to"', page)
        assert "Apply" in page

    def test_normalises_unpadded_dates(self, client, fixed_rows):
        page = get_profile(client, "?date_from=2020-2-1&date_to=2020-2-15")
        assert stat_value(page, "Total spent") == money(500.00)

    def test_user_isolation_in_filtered_view(self, client, fixed_rows, other_user):
        page = get_profile(client, "?date_from=2020-02-01&date_to=2020-02-28")
        assert "OtherUserTxn" not in page
        assert stat_value(page, "Total spent") == money(500.00)

    def test_other_user_sees_only_own_rows(self, client, fixed_rows, other_user):
        page = get_profile(
            client,
            "?date_from=2020-02-01&date_to=2020-02-28",
            email=OTHER_EMAIL,
            password=OTHER_PASSWORD,
        )
        assert "OtherUserTxn" in page
        assert "Feb-mid" not in page
        assert stat_value(page, "Total spent") == money(999.00)

    def test_empty_range_shows_zero_state(self, client, fixed_rows):
        page = get_profile(client, "?date_from=1999-01-01&date_to=1999-12-31")
        assert stat_value(page, "Total spent") == "₹0.00"
        assert stat_value(page, "Transactions") == "0"
        assert "No transactions in this period." in page
        assert "No spending in this period." in page
        assert not re.findall(r'class="cat-bar pct-\d+"', page)
        assert ERROR_TEXT not in page


# ------------------------------------------------------------------ #
# Route: invalid input                                                #
# ------------------------------------------------------------------ #

class TestInvalidInput:
    def test_from_after_to_flashes_error_and_is_unfiltered(self, client, fixed_rows):
        page = get_profile(client, "?date_from=2020-03-01&date_to=2020-02-01")
        assert ERROR_TEXT in page
        assert stat_value(page, "Total spent") == money(SEED_TOTAL + FIXED_TOTAL)
        assert stat_value(page, "Transactions") == str(SEED_COUNT + len(FIXED_ROWS))

    def test_flash_error_not_repeated_on_reload(self, client, fixed_rows):
        get_profile(client, "?date_from=2020-03-01&date_to=2020-02-01")
        response = client.get("/profile")
        assert response.status_code == 200
        assert ERROR_TEXT not in response.get_data(as_text=True)

    @pytest.mark.parametrize(
        "query",
        [
            "?date_from=not-a-date&date_to=2020-02-15",
            "?date_from=2020-02-01&date_to=not-a-date",
            "?date_from=garbage&date_to=garbage",
            "?date_from=2020-02-30&date_to=2020-03-01",
            "?date_from=&date_to=",
            "?date_from=2020-02-01",
            "?date_to=2020-02-15",
            "?date_from=2020-02-01&date_to=",
            "?date_from=2020-01-01%27%20OR%20%271%27%3D%271&date_to=2020-12-31",
            "?date_from=%27%3B%20DROP%20TABLE%20expenses%3B--&date_to=2020-12-31",
            "?date_from=" + "9" * 500 + "&date_to=2020-12-31",
        ],
    )
    def test_malformed_or_one_sided_params_fall_back_unfiltered(
        self, client, fixed_rows, query
    ):
        page = get_profile(client, query)  # asserts 200
        assert stat_value(page, "Total spent") == money(SEED_TOTAL + FIXED_TOTAL)
        assert stat_value(page, "Transactions") == str(SEED_COUNT + len(FIXED_ROWS))
        assert ERROR_TEXT not in page, "Malformed input must fall back silently"

    def test_after_injection_attempt_data_still_intact(self, client, fixed_rows):
        get_profile(client, "?date_from=%27%3B%20DROP%20TABLE%20expenses%3B--&date_to=x")
        assert queries.get_summary_stats(fixed_rows)["transaction_count"] > 0


# ------------------------------------------------------------------ #
# Presets                                                             #
# ------------------------------------------------------------------ #

PRESET_TODAY = date(2015, 6, 15)

PRESET_ROWS = [
    (10.00, "Food", "2015-06-16", "P-Jun16-future"),
    (20.00, "Food", "2015-06-15", "P-Jun15-today"),
    (30.00, "Food", "2015-06-01", "P-Jun01"),
    (40.00, "Food", "2015-05-31", "P-May31"),
    (50.00, "Food", "2015-03-15", "P-Mar15"),
    (60.00, "Food", "2015-03-14", "P-Mar14"),
    (70.00, "Food", "2014-12-15", "P-Dec15"),
    (80.00, "Food", "2014-12-14", "P-Dec14"),
]


@pytest.fixture
def preset_env(client, demo_id, monkeypatch):
    monkeypatch.setattr(app_module, "_today", lambda: PRESET_TODAY)
    for amount, category, date_str, description in PRESET_ROWS:
        add_expense(demo_id, amount, category, date_str, description)
    return client


def present(page):
    return {desc for _, _, _, desc in PRESET_ROWS if desc in page}


class TestPresets:
    def test_all_four_presets_rendered(self, preset_env):
        page = get_profile(preset_env)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            preset_tag(page, label)

    def test_this_month_link_params(self, preset_env):
        page = get_profile(preset_env)
        href = href_of(preset_tag(page, "This Month"))
        assert href.startswith("/profile?")
        assert "date_from=2015-06-01" in href
        assert "date_to=2015-06-15" in href

    def test_last_3_months_link_params(self, preset_env):
        page = get_profile(preset_env)
        href = href_of(preset_tag(page, "Last 3 Months"))
        assert "date_from=2015-03-15" in href
        assert "date_to=2015-06-15" in href

    def test_last_6_months_link_params(self, preset_env):
        page = get_profile(preset_env)
        href = href_of(preset_tag(page, "Last 6 Months"))
        assert "date_from=2014-12-15" in href
        assert "date_to=2015-06-15" in href

    def test_all_time_link_is_exactly_profile(self, preset_env):
        page = get_profile(preset_env)
        assert href_of(preset_tag(page, "All Time")) == "/profile"

    def test_this_month_preset_filters_data(self, preset_env):
        page = get_profile(preset_env)
        href = href_of(preset_tag(page, "This Month"))
        page = preset_env.get(href).get_data(as_text=True)
        assert present(page) == {"P-Jun15-today", "P-Jun01"}
        assert stat_value(page, "Total spent") == money(50.00)
        assert stat_value(page, "Transactions") == "2"

    def test_last_3_months_preset_filters_data(self, preset_env):
        page = get_profile(preset_env)
        href = href_of(preset_tag(page, "Last 3 Months"))
        page = preset_env.get(href).get_data(as_text=True)
        assert present(page) == {"P-Jun15-today", "P-Jun01", "P-May31", "P-Mar15"}
        assert stat_value(page, "Total spent") == money(140.00)

    def test_last_6_months_preset_filters_data(self, preset_env):
        page = get_profile(preset_env)
        href = href_of(preset_tag(page, "Last 6 Months"))
        page = preset_env.get(href).get_data(as_text=True)
        assert present(page) == {
            "P-Jun15-today", "P-Jun01", "P-May31", "P-Mar15", "P-Mar14", "P-Dec15",
        }
        assert stat_value(page, "Total spent") == money(270.00)

    def test_all_time_preset_removes_filter(self, preset_env):
        login(preset_env)
        filtered = preset_env.get(
            "/profile?date_from=2015-06-01&date_to=2015-06-15"
        ).get_data(as_text=True)
        all_href = href_of(preset_tag(filtered, "All Time"))
        page = preset_env.get(all_href).get_data(as_text=True)
        assert stat_value(page, "Total spent") == money(SEED_TOTAL + 360.00)

    def test_no_params_marks_all_time_active(self, preset_env):
        page = get_profile(preset_env)
        assert 'aria-current' in preset_tag(page, "All Time")
        assert 'aria-current' not in preset_tag(page, "This Month")
        assert "btn-primary" in preset_tag(page, "All Time")

    def test_preset_url_marks_that_preset_active(self, preset_env):
        page = get_profile(preset_env, "?date_from=2015-03-15&date_to=2015-06-15")
        assert "aria-current" in preset_tag(page, "Last 3 Months")
        for label in ("This Month", "Last 6 Months", "All Time"):
            assert "aria-current" not in preset_tag(page, label), label

    def test_custom_range_marks_custom_form_active_not_presets(self, preset_env):
        page = get_profile(preset_env, "?date_from=2015-01-02&date_to=2015-02-03")
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            assert "aria-current" not in preset_tag(page, label), label
        assert re.search(r'class="filter-custom is-active"', page)

    def test_custom_form_not_active_for_presets(self, preset_env):
        page = get_profile(preset_env)
        assert "is-active" not in page


# ------------------------------------------------------------------ #
# Unit tests for date helpers in app.py                               #
# ------------------------------------------------------------------ #

class TestDateHelpers:
    @pytest.mark.parametrize(
        "start, n, expected",
        [
            (date(2026, 5, 31), 3, date(2026, 2, 28)),   # month-end clamp
            (date(2024, 5, 31), 3, date(2024, 2, 29)),   # leap-year clamp
            (date(2026, 1, 15), 3, date(2025, 10, 15)),  # year rollover
            (date(2026, 3, 10), 6, date(2025, 9, 10)),
            (date(2026, 8, 31), 6, date(2026, 2, 28)),
            (date(2026, 6, 15), 0, date(2026, 6, 15)),
        ],
    )
    def test_months_back(self, start, n, expected):
        assert app_module._months_back(start, n) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2020-02-15", "2020-02-15"),
            ("2020-2-5", "2020-02-05"),
            (" 2020-02-15 ", "2020-02-15"),
            ("2020-02-30", None),
            ("not-a-date", None),
            ("", None),
            (None, None),
            ("15/02/2020", None),
        ],
    )
    def test_parse_date_param(self, raw, expected):
        assert app_module._parse_date_param(raw) == expected
