import re
from pathlib import Path

import pytest

from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
PROFILE_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "profile.html"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


def login(client):
    return client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})


def get_profile_html(client):
    login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_profile_requires_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_profile_returns_200_when_logged_in(client):
    login(client)
    assert client.get("/profile").status_code == 200


def test_profile_shows_user_card(client):
    html = get_profile_html(client)
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "DU" in html
    assert "Member since" in html


def test_profile_shows_summary_stats(client):
    html = get_profile_html(client)
    assert "Total spent" in html
    assert "Transactions" in html
    assert "Top category" in html


def test_profile_transaction_table_has_rows(client):
    html = get_profile_html(client)
    body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert body.count("<tr>") >= 3
    assert "badge badge-" in body


def test_profile_category_breakdown_has_categories(client):
    html = get_profile_html(client)
    assert len(re.findall(r'class="cat-bar pct-\d+"', html)) >= 3


def test_profile_navbar_shows_username_and_logout(client):
    html = get_profile_html(client)
    nav = html.split("</nav>")[0]
    assert "nav-user" in nav
    assert "Demo User" in nav
    assert "Sign out" in nav
    assert "Sign in" not in nav


def test_profile_with_stale_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_template_has_no_inline_styles_or_hex():
    source = PROFILE_TEMPLATE.read_text()
    assert "style=" not in source
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", source)
