import pytest

from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_login_success_sets_session(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert session_user_id(client) == db.get_user_by_email(DEMO_EMAIL)["id"]


def test_wrong_password_rejected(client):
    response = login(client, password="wrongpass")
    assert response.status_code == 401
    assert b"Invalid email or password." in response.data
    assert session_user_id(client) is None


def test_unknown_email_gives_same_message(client):
    response = login(client, email="nobody@example.com")
    assert response.status_code == 401
    assert b"Invalid email or password." in response.data
    assert session_user_id(client) is None


def test_email_is_case_insensitive(client):
    response = login(client, email="Demo@Spendly.com")
    assert response.status_code == 302
    assert session_user_id(client) is not None


@pytest.mark.parametrize(
    "email,password",
    [("", DEMO_PASSWORD), (DEMO_EMAIL, ""), ("", ""), (DEMO_EMAIL, "   ")],
)
def test_blank_fields_rejected(client, email, password):
    response = login(client, email=email, password=password)
    assert response.status_code == 400
    assert b"All fields are required." in response.data
    assert session_user_id(client) is None


def test_failed_login_keeps_email_not_password(client):
    response = login(client, password="wrongpass")
    html = response.get_data(as_text=True)
    assert f'value="{DEMO_EMAIL}"' in html
    assert "wrongpass" not in html


def test_register_then_login(client):
    client.post(
        "/register",
        data={"name": "Asha Nair", "email": "asha@example.com", "password": "  secret123  "},
    )
    response = login(client, email="asha@example.com", password="  secret123  ")
    assert response.status_code == 302
    assert session_user_id(client) == db.get_user_by_email("asha@example.com")["id"]


def test_navbar_signed_out(client):
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Get started" in html
    assert "Sign out" not in html


def test_navbar_signed_in(client):
    login(client)
    html = client.get("/").get_data(as_text=True)
    assert "Sign out" in html
    assert "Sign in" not in html
    assert "Get started" not in html


def test_logout_clears_session(client):
    login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert session_user_id(client) is None
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Sign out" not in html


def test_logout_when_anonymous(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_signed_in_user_redirected_away(client, path):
    login(client)
    assert client.get(path).headers["Location"] == "/"
    assert client.post(path, data={}).headers["Location"] == "/"


def test_login_replaces_existing_session_data(client):
    with client.session_transaction() as sess:
        sess["junk"] = "leftover"
    login(client)
    with client.session_transaction() as sess:
        assert "junk" not in sess
        assert set(sess.keys()) == {"user_id"}


def test_login_form_uses_url_for(client):
    html = client.get("/login").get_data(as_text=True)
    assert 'action="/login"' in html
