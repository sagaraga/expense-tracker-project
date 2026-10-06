"""Tests for Step 7: add an expense from the UI (/expenses/add)."""
import html as html_lib
from datetime import timedelta

import pytest

import app as app_module
from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
OTHER_EMAIL = "other@spendly.com"
OTHER_PASSWORD = "other123"

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
SEED_COUNT = 8
SEED_TOTAL = 12.50 + 35.00 + 89.99 + 45.00 + 18.00 + 64.75 + 10.00 + 27.30


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


@pytest.fixture
def demo_id(client):
    return db.get_user_by_email(DEMO_EMAIL)["id"]


@pytest.fixture
def other_user(client):
    return db.create_user("Other Person", OTHER_EMAIL, OTHER_PASSWORD)


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def count_rows(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            row = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row["n"]
    finally:
        conn.close()


def last_row():
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()


def valid_data(**overrides):
    data = {
        "amount": "42.50",
        "category": "Food",
        "date": app_module._today().isoformat(),
        "description": "Lunch at cafe",
    }
    data.update(overrides)
    return data


def post_expense(client, **overrides):
    return client.post("/expenses/add", data=valid_data(**overrides))


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_logged_out_redirects_and_inserts_nothing(self, client):
        before = count_rows()
        response = post_expense(client)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert count_rows() == before, "Logged-out POST must not insert a row"


class TestGetForm:
    def test_get_returns_form_fields(self, client):
        login(client)
        response = client.get("/expenses/add")
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        for name in ("amount", "category", "date", "description"):
            assert f'name="{name}"' in page, f"Missing field {name}"

    def test_get_date_defaults_to_today_ist(self, client):
        login(client)
        page = client.get("/expenses/add").get_data(as_text=True)
        assert app_module._today().isoformat() in page

    def test_get_lists_all_categories(self, client):
        login(client)
        page = client.get("/expenses/add").get_data(as_text=True)
        for category in CATEGORIES:
            assert category in page, f"Category {category} missing from dropdown"

    def test_profile_has_add_expense_link(self, client):
        login(client)
        page = client.get("/profile").get_data(as_text=True)
        assert 'href="/expenses/add"' in page
        assert "Add expense" in page


class TestValidPost:
    def test_valid_post_redirects_to_profile(self, client):
        login(client)
        response = post_expense(client)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_shows_message_and_transaction(self, client):
        login(client)
        today = app_module._today().isoformat()
        response = post_expense(
            client, amount="1234.56", category="Shopping",
            description="UniqueDescXYZ", date=today,
        )
        assert response.status_code == 302
        page = client.get("/profile").get_data(as_text=True)
        # Flash is consumed on the first profile render after the redirect.
        # Re-do with follow_redirects to check the message itself.
        assert "UniqueDescXYZ" in page
        assert "Shopping" in page
        assert money(1234.56) in page

    def test_valid_post_follow_redirect_shows_flash(self, client):
        login(client)
        response = client.post(
            "/expenses/add", data=valid_data(description="FlashCheck"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Expense added." in response.get_data(as_text=True)

    def test_valid_post_updates_total_and_count(self, client, demo_id):
        login(client)
        post_expense(client, amount="1000.00", category="Other")
        assert count_rows(demo_id) == SEED_COUNT + 1
        page = client.get("/profile").get_data(as_text=True)
        assert money(SEED_TOTAL + 1000.00) in page, "Total spent should include new expense"
        assert str(SEED_COUNT + 1) in page

    def test_row_has_session_user_and_two_decimals(self, client, demo_id):
        login(client)
        post_expense(client, amount="12.345")
        row = last_row()
        assert row["user_id"] == demo_id
        assert row["amount"] == pytest.approx(12.35)
        assert row["category"] == "Food"
        assert row["date"] == app_module._today().isoformat()
        assert row["description"] == "Lunch at cafe"

    def test_empty_description_stored_as_null(self, client):
        login(client)
        before = count_rows()
        response = post_expense(client, description="")
        assert response.status_code == 302
        assert count_rows() == before + 1
        assert last_row()["description"] is None

    def test_boundary_values_accepted(self, client):
        login(client)
        before = count_rows()
        response = post_expense(
            client, amount="10000000", description="x" * 200,
            date=app_module._today().isoformat(),
        )
        assert response.status_code == 302
        assert count_rows() == before + 1

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_category_accepted(self, client, category):
        login(client)
        before = count_rows()
        assert post_expense(client, category=category).status_code == 302
        assert count_rows() == before + 1


class TestInvalidPost:
    @pytest.mark.parametrize(
        "amount", ["0", "-5", "abc", "nan", "inf", "", "1e999999", "10000001", "0.001"]
    )
    def test_bad_amount_rejected(self, client, amount):
        login(client)
        before = count_rows()
        response = post_expense(client, amount=amount)
        assert response.status_code == 400, f"amount={amount!r} should be 400"
        assert count_rows() == before
        page = response.get_data(as_text=True)
        assert "form-error" in page, "Expected an error message block"

    def test_bad_category_rejected(self, client):
        login(client)
        before = count_rows()
        response = post_expense(client, category="Gambling")
        assert response.status_code == 400
        assert count_rows() == before

    def test_missing_category_rejected(self, client):
        login(client)
        before = count_rows()
        data = valid_data()
        del data["category"]
        response = client.post("/expenses/add", data=data)
        assert response.status_code == 400
        assert count_rows() == before

    def test_future_date_rejected(self, client):
        login(client)
        before = count_rows()
        tomorrow = (app_module._today() + timedelta(days=1)).isoformat()
        response = post_expense(client, date=tomorrow)
        assert response.status_code == 400
        assert count_rows() == before

    @pytest.mark.parametrize("bad_date", ["2024-13-01", "abc", "", "2024/01/01"])
    def test_malformed_date_rejected(self, client, bad_date):
        login(client)
        before = count_rows()
        response = post_expense(client, date=bad_date)
        assert response.status_code == 400, f"date={bad_date!r} should be 400"
        assert count_rows() == before

    def test_long_description_rejected(self, client):
        login(client)
        before = count_rows()
        response = post_expense(client, description="x" * 201)
        assert response.status_code == 400
        assert count_rows() == before

    def test_error_rerender_preserves_values(self, client):
        login(client)
        response = post_expense(
            client, amount="-7", category="Health",
            description="KeepMeDesc", date="2023-05-04",
        )
        assert response.status_code == 400
        page = response.get_data(as_text=True)
        assert "-7" in page
        assert "KeepMeDesc" in page
        assert "2023-05-04" in page
        assert "Health" in page

    def test_sql_injection_description_stored_literally(self, client):
        login(client)
        payload = "'); DROP TABLE expenses;--"
        before = count_rows()
        assert post_expense(client, description=payload).status_code == 302
        assert count_rows() == before + 1
        assert last_row()["description"] == payload


class TestSecurity:
    def test_tampered_user_id_ignored(self, client, demo_id, other_user):
        login(client)
        other_before = count_rows(other_user)
        post_expense(client, user_id=str(other_user))
        assert count_rows(other_user) == other_before, "Other user must get no row"
        assert last_row()["user_id"] == demo_id

    def test_script_description_rendered_escaped(self, client):
        login(client)
        post_expense(client, description="<script>alert(1)</script>")
        page = client.get("/profile").get_data(as_text=True)
        assert "<script>alert(1)</script>" not in page, "Description must be escaped"
        assert html_lib.escape("<script>alert(1)</script>") in page


class TestStubsUntouched:
    def test_edit_stub_unchanged(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 200
        assert "Step 8" in response.get_data(as_text=True)

    def test_delete_stub_unchanged(self, client):
        response = client.get("/expenses/1/delete")
        assert response.status_code == 200
        assert "Step 9" in response.get_data(as_text=True)


class TestValidateExpenseForm:
    def test_valid_form_returns_clean_values(self, client):
        clean, error = app_module._validate_expense_form(valid_data(amount="5.005"))
        assert error is None
        assert clean["amount"] == pytest.approx(5.01)
        assert clean["category"] == "Food"
        assert clean["date"] == app_module._today().isoformat()

    def test_empty_description_becomes_none(self, client):
        clean, error = app_module._validate_expense_form(valid_data(description="   "))
        assert error is None
        assert clean["description"] is None

    def test_description_is_stripped(self, client):
        clean, _ = app_module._validate_expense_form(valid_data(description="  hi  "))
        assert clean["description"] == "hi"

    def test_user_id_not_in_clean_values(self, client):
        clean, error = app_module._validate_expense_form(valid_data(user_id="99"))
        assert error is None
        assert "user_id" not in clean

    @pytest.mark.parametrize(
        "overrides",
        [
            {"amount": "0"}, {"amount": "-1"}, {"amount": "nan"}, {"amount": "inf"},
            {"amount": "abc"}, {"amount": ""}, {"amount": "10000001"},
            {"amount": "1e999999"}, {"amount": "0.001"},
            {"category": "Nope"}, {"date": "bad"}, {"date": "2024-13-01"},
            {"description": "x" * 201},
        ],
    )
    def test_invalid_form_returns_error(self, client, overrides):
        clean, error = app_module._validate_expense_form(valid_data(**overrides))
        assert clean is None
        assert error, f"Expected an error for {overrides}"

    def test_missing_keys_return_error_not_exception(self, client):
        clean, error = app_module._validate_expense_form({})
        assert clean is None
        assert error
