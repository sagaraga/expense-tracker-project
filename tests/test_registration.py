import pytest
from werkzeug.security import check_password_hash

from database import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


def user_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def register(client, name="Asha Nair", email="asha@example.com", password="password123"):
    return client.post("/register", data={"name": name, "email": email, "password": password})


def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_valid_registration_redirects_to_login(client):
    before = user_count()
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert user_count() == before + 1


def test_password_is_hashed(client):
    register(client)
    user = db.get_user_by_email("asha@example.com")
    assert user["password_hash"] != "password123"
    assert check_password_hash(user["password_hash"], "password123")


def test_duplicate_email_rejected(client):
    before = user_count()
    response = register(client, email="demo@spendly.com")
    assert response.status_code == 400
    assert b"already exists" in response.data
    assert user_count() == before


def test_duplicate_email_is_case_insensitive(client):
    before = user_count()
    response = register(client, email="Demo@Spendly.com")
    assert response.status_code == 400
    assert user_count() == before


def test_short_password_rejected(client):
    before = user_count()
    response = register(client, password="short")
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data
    assert user_count() == before


@pytest.mark.parametrize("field", ["name", "email", "password"])
def test_blank_fields_rejected(client, field):
    before = user_count()
    response = register(client, **{field: "   "})
    assert response.status_code == 400
    assert user_count() == before


@pytest.mark.parametrize("email", ["no-at-sign", "user@nodot", "@example.com"])
def test_invalid_email_rejected(client, email):
    before = user_count()
    response = register(client, email=email)
    assert response.status_code == 400
    assert user_count() == before


def test_error_keeps_name_and_email_but_not_password(client):
    response = register(client, name="Asha Nair", email="asha@example.com", password="short")
    html = response.get_data(as_text=True)
    assert 'value="Asha Nair"' in html
    assert 'value="asha@example.com"' in html
    assert "short" not in html.replace("Min. 8 characters", "")


def test_form_uses_url_for(client):
    html = client.get("/register").get_data(as_text=True)
    assert 'action="/register"' in html  # url_for resolves to the same path
