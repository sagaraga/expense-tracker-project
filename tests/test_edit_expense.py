"""Tests for Step 8: edit an expense from the UI (/expenses/<id>/edit)."""
import html as html_lib
from datetime import timedelta

import pytest

import app as app_module
from database import db, queries

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
OTHER_EMAIL = "other@spendly.com"
OTHER_PASSWORD = "other123"


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


def get_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def count_rows():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    finally:
        conn.close()


def make_expense(user_id, amount=20.0, category="Food", date=None, description="Original"):
    date = date or app_module._today().isoformat()
    return queries.create_expense(user_id, amount, category, date, description)


def form_data(**overrides):
    data = {
        "amount": "42.50",
        "category": "Transport",
        "date": app_module._today().isoformat(),
        "description": "Updated",
    }
    data.update(overrides)
    return data


def edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def snapshot(expense_id):
    return dict(get_row(expense_id))


class TestAuth:
    def test_get_logged_out_redirects_to_login(self, client, demo_id):
        eid = make_expense(demo_id)
        response = client.get(edit_url(eid))
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_logged_out_redirects_and_changes_nothing(self, client, demo_id):
        eid = make_expense(demo_id)
        before = snapshot(eid)
        response = client.post(edit_url(eid), data=form_data())
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert snapshot(eid) == before


class TestProfileLink:
    def test_each_row_has_edit_link(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        page = client.get("/profile").get_data(as_text=True)
        assert f'href="{edit_url(eid)}"' in page
        assert page.count('class="txn-edit"') >= 8

    def test_add_link_still_present(self, client):
        login(client)
        page = client.get("/profile").get_data(as_text=True)
        assert 'href="/expenses/add"' in page


class TestGetForm:
    def test_prefills_current_values(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id, amount=12.5, category="Health", date="2026-01-15",
                           description="Checkup")
        response = client.get(edit_url(eid))
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert 'value="12.50"' in page
        assert 'value="2026-01-15"' in page
        assert 'value="Checkup"' in page
        assert '<option value="Health" selected>' in page

    def test_labelled_as_edit_with_edit_action(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        page = client.get(edit_url(eid)).get_data(as_text=True)
        assert "Edit expense" in page
        assert "Save changes" in page
        assert f'action="{edit_url(eid)}"' in page

    def test_null_description_prefills_empty(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id, description=None)
        page = client.get(edit_url(eid)).get_data(as_text=True)
        assert 'name="description"' in page
        assert 'value="None"' not in page


class TestNotFound:
    def test_other_users_expense_get_and_post_404(self, client, demo_id, other_user):
        login(client)
        eid = make_expense(other_user)
        before = snapshot(eid)
        assert client.get(edit_url(eid)).status_code == 404
        assert client.post(edit_url(eid), data=form_data()).status_code == 404
        assert snapshot(eid) == before

    def test_missing_expense_404(self, client):
        login(client)
        assert client.get(edit_url(99999)).status_code == 404
        assert client.post(edit_url(99999), data=form_data()).status_code == 404


class TestSuccessfulEdit:
    def test_valid_edit_updates_row_and_redirects(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        total_before = count_rows()
        response = client.post(edit_url(eid), data=form_data())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

        row = get_row(eid)
        assert row["id"] == eid
        assert row["user_id"] == demo_id
        assert row["amount"] == 42.5
        assert row["category"] == "Transport"
        assert row["description"] == "Updated"
        assert count_rows() == total_before

    def test_flash_and_profile_reflect_change(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id, amount=20.0, category="Food", description="Original")
        page = client.post(edit_url(eid), data=form_data(), follow_redirects=True).get_data(
            as_text=True
        )
        assert "Expense updated." in page
        assert "Updated" in page
        assert "₹42.50" in page
        assert "Original" not in page

    def test_amount_rounded_to_two_decimals(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        client.post(edit_url(eid), data=form_data(amount="10.005"))
        assert get_row(eid)["amount"] == 10.01

    def test_empty_description_stored_as_null(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        client.post(edit_url(eid), data=form_data(description="   "))
        assert get_row(eid)["description"] is None

    def test_user_id_form_field_ignored(self, client, demo_id, other_user):
        login(client)
        eid = make_expense(demo_id)
        client.post(edit_url(eid), data=form_data(user_id=str(other_user)))
        assert get_row(eid)["user_id"] == demo_id


class TestValidation:
    @pytest.mark.parametrize("amount", ["0", "-5", "abc", "nan", ""])
    def test_bad_amount_rejected(self, client, demo_id, amount):
        login(client)
        eid = make_expense(demo_id)
        before = snapshot(eid)
        response = client.post(edit_url(eid), data=form_data(amount=amount))
        assert response.status_code == 400
        assert 'role="alert"' in response.get_data(as_text=True)
        assert snapshot(eid) == before

    def test_bad_category_rejected(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        before = snapshot(eid)
        response = client.post(edit_url(eid), data=form_data(category="Gambling"))
        assert response.status_code == 400
        assert snapshot(eid) == before

    @pytest.mark.parametrize("bad_date", ["not-a-date", "2026-13-45", ""])
    def test_malformed_date_rejected(self, client, demo_id, bad_date):
        login(client)
        eid = make_expense(demo_id)
        before = snapshot(eid)
        response = client.post(edit_url(eid), data=form_data(date=bad_date))
        assert response.status_code == 400
        assert snapshot(eid) == before

    def test_future_date_rejected(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        before = snapshot(eid)
        future = (app_module._today() + timedelta(days=1)).isoformat()
        response = client.post(edit_url(eid), data=form_data(date=future))
        assert response.status_code == 400
        assert snapshot(eid) == before

    def test_long_description_rejected(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        before = snapshot(eid)
        response = client.post(edit_url(eid), data=form_data(description="x" * 201))
        assert response.status_code == 400
        assert snapshot(eid) == before

    def test_error_rerender_preserves_values_and_edit_action(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id)
        response = client.post(
            edit_url(eid), data=form_data(amount="-1", description="Keep me")
        )
        page = response.get_data(as_text=True)
        assert response.status_code == 400
        assert 'value="-1"' in page
        assert 'value="Keep me"' in page
        assert f'action="{edit_url(eid)}"' in page
        assert "Save changes" in page


class TestEscaping:
    def test_script_description_escaped(self, client, demo_id):
        login(client)
        eid = make_expense(demo_id, description="<script>alert(1)</script>")
        raw = "<script>alert(1)</script>"
        edit_page = client.get(edit_url(eid)).get_data(as_text=True)
        profile_page = client.get("/profile").get_data(as_text=True)
        for page in (edit_page, profile_page):
            assert raw not in page
            assert html_lib.escape(raw) in page


class TestRegressions:
    def test_add_page_unchanged(self, client):
        login(client)
        page = client.get("/expenses/add").get_data(as_text=True)
        assert "Add expense" in page
        assert 'action="/expenses/add"' in page
        assert "Save changes" not in page

    def test_add_still_redirects_with_flash(self, client):
        login(client)
        page = client.post(
            "/expenses/add", data=form_data(), follow_redirects=True
        ).get_data(as_text=True)
        assert "Expense added." in page

    def test_delete_stub_unchanged(self, client):
        response = client.get("/expenses/1/delete")
        assert response.status_code == 200
        assert "Step 9" in response.get_data(as_text=True)


class TestQueryHelpers:
    def test_get_expense_scoped_to_owner(self, client, demo_id, other_user):
        eid = make_expense(demo_id)
        assert queries.get_expense(eid, demo_id)["id"] == eid
        assert queries.get_expense(eid, other_user) is None

    def test_update_expense_rowcount(self, client, demo_id, other_user):
        eid = make_expense(demo_id)
        args = (10.0, "Food", "2026-01-01", "x")
        assert queries.update_expense(eid, demo_id, *args) == 1
        assert queries.update_expense(eid, other_user, *args) == 0
        assert queries.update_expense(99999, demo_id, *args) == 0

    def test_recent_transactions_include_id(self, client, demo_id):
        rows = queries.get_recent_transactions(demo_id)
        assert rows and all("id" in r for r in rows)
