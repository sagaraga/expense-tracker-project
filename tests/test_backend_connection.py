import os
import re

import pytest

from database import db, queries

SEED_EMAIL = "demo@spendly.com"
SEED_PASSWORD = "demo123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def seed_user_id(client):
    return db.get_user_by_email(SEED_EMAIL)["id"]


@pytest.fixture
def empty_user_id(client):
    db.create_user("Empty User", "empty@example.com", "password123")
    return db.get_user_by_email("empty@example.com")["id"]


def login(client, email=SEED_EMAIL, password=SEED_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


# ==== SECTION: tests transactions (owned by subagent 1) ==== #

class TestTransactions:
    def test_seed_user_returns_eight_with_keys(self, seed_user_id):
        rows = queries.get_recent_transactions(seed_user_id)
        assert len(rows) == 8
        for row in rows:
            assert set(row) == {"id", "date", "description", "category", "amount"}

    def test_newest_first(self, seed_user_id):
        dates = [r["date"] for r in queries.get_recent_transactions(seed_user_id)]
        assert dates == sorted(dates, reverse=True)

    def test_id_tie_break(self, empty_user_id):
        conn = db.get_db()
        try:
            for desc in ("first", "second"):
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, date, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (empty_user_id, 10.0, "Food", "2026-01-01", desc),
                )
            conn.commit()
        finally:
            conn.close()
        rows = queries.get_recent_transactions(empty_user_id)
        assert [r["description"] for r in rows] == ["second", "first"]

    def test_limit(self, seed_user_id):
        assert len(queries.get_recent_transactions(seed_user_id, limit=3)) == 3

    def test_no_expenses_returns_empty(self, empty_user_id):
        assert queries.get_recent_transactions(empty_user_id) == []

    def test_profile_route_lists_rows(self, client):
        login(client)
        html = client.get("/profile").get_data(as_text=True)
        assert "₹" in html
        body = html.split("<tbody", 1)[1].split("</tbody>", 1)[0]
        assert body.count("<tr") == 8
        from datetime import datetime

        dates = [
            datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b %Y")
            for r in queries.get_recent_transactions(
                db.get_user_by_email(SEED_EMAIL)["id"]
            )
        ]
        positions = [body.index(d) for d in dates]
        assert positions == sorted(positions)


# ==== SECTION: tests stats (owned by subagent 2) ==== #

class TestStats:
    def test_seed_user_stats(self, seed_user_id):
        stats = queries.get_summary_stats(seed_user_id)
        assert stats["total_spent"] == 302.54
        assert stats["transaction_count"] == 8
        assert stats["top_category"] == "Bills"

    def test_empty_user_stats(self, empty_user_id):
        assert queries.get_summary_stats(empty_user_id) == {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—",
        }

    def test_profile_route_seed_user(self, client):
        login(client)
        resp = client.get("/profile")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "₹302.54" in html
        assert "Bills" in html

    def test_profile_route_new_user(self, client, empty_user_id):
        login(client, "empty@example.com", "password123")
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert "₹0.00" in resp.get_data(as_text=True)


# ==== SECTION: tests categories (owned by subagent 3) ==== #

class TestCategories:
    def test_seed_user_breakdown(self, client, seed_user_id):
        result = queries.get_category_breakdown(seed_user_id)
        assert len(result) == 7
        assert result[0]["name"] == "Bills"
        amounts = [r["amount"] for r in result]
        assert amounts == sorted(amounts, reverse=True)
        assert all(isinstance(r["pct"], int) for r in result)
        assert sum(r["pct"] for r in result) == 100

    def test_remainder_goes_to_largest(self, client):
        db.create_user("Third User", "third@example.com", "password123")
        uid = db.get_user_by_email("third@example.com")["id"]
        conn = db.get_db()
        try:
            for cat in ("Food", "Bills", "Health"):
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, date, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (uid, 10.0, cat, "2026-01-01", "x"),
                )
            conn.commit()
        finally:
            conn.close()
        result = queries.get_category_breakdown(uid)
        assert [r["pct"] for r in result] == [34, 33, 33]
        assert [r["name"] for r in result] == ["Bills", "Food", "Health"]

    def test_no_expenses(self, client, empty_user_id):
        assert queries.get_category_breakdown(empty_user_id) == []

    def test_route_renders_bars(self, client, seed_user_id):
        login(client)
        html = client.get("/profile").get_data(as_text=True)
        assert len(re.findall(r'class="cat-bar pct-\d+"', html)) == 7

    def test_route_empty_user(self, client, empty_user_id):
        login(client, "empty@example.com", "password123")
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert "cat-bar pct-" not in resp.get_data(as_text=True)

    def test_css_has_all_classes(self):
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "css", "profile.css"
        )
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        for n in range(101):
            assert f".pct-{n} " in css
        assert ".badge-health" in css
        assert ".badge-entertainment" in css
