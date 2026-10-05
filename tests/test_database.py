import sqlite3
from datetime import date

import pytest
from werkzeug.security import check_password_hash

from database import db

CATEGORIES = {"Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"}


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def count(table):
    conn = db.get_db()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_init_creates_tables(temp_db):
    conn = db.get_db()
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"users", "expenses"} <= names


def test_init_idempotent(temp_db):
    db.init_db()
    db.init_db()


def test_seed_counts_and_categories(temp_db):
    db.seed_db()
    assert count("users") == 1
    assert count("expenses") == 8
    conn = db.get_db()
    cats = {r["category"] for r in conn.execute("SELECT category FROM expenses")}
    conn.close()
    assert cats == CATEGORIES


def test_seed_idempotent(temp_db):
    db.seed_db()
    db.seed_db()
    assert count("users") == 1
    assert count("expenses") == 8


def test_password_hashed(temp_db):
    db.seed_db()
    conn = db.get_db()
    row = conn.execute("SELECT password_hash FROM users").fetchone()
    conn.close()
    assert row["password_hash"] != "demo123"
    assert check_password_hash(row["password_hash"], "demo123")


def test_row_factory(temp_db):
    db.seed_db()
    conn = db.get_db()
    row = conn.execute("SELECT email FROM users").fetchone()
    conn.close()
    assert row["email"] == "demo@spendly.com"


def test_foreign_keys_enforced(temp_db):
    conn = db.get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (999, 1.0, "Food", "2026-01-01"),
        )
    conn.close()


def test_unique_email(temp_db):
    conn = db.get_db()
    insert = "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)"
    conn.execute(insert, ("A", "a@x.com", "h"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("B", "a@x.com", "h"))
    conn.close()


def test_dates_valid_current_month(temp_db):
    db.seed_db()
    today = date.today()
    conn = db.get_db()
    dates = [r["date"] for r in conn.execute("SELECT date FROM expenses")]
    conn.close()
    for d in dates:
        parsed = date.fromisoformat(d)
        assert (parsed.year, parsed.month) == (today.year, today.month)
