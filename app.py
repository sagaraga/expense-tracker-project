import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_db,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
# Development-only fallback; set SPENDLY_SECRET_KEY in any real deployment.
app.secret_key = os.environ.get("SPENDLY_SECRET_KEY") or "dev-only-insecure-spendly-key"

with app.app_context():
    init_db()
    seed_db()


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    return {"current_user": get_user_by_id(user_id) if user_id else None}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    error = None
    local, _, domain = email.partition("@")
    if not name or not email or not password:
        error = "All fields are required."
    elif not local or "." not in domain:
        error = "Enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    else:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "An account with this email already exists."

    if error:
        return render_template("register.html", error=error, name=name, email=email), 400
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login.html", error="All fields are required.", email=email), 400

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.", email=email), 401

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded placeholder data — Step 5 replaces this with DB queries.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "January 2026",
    }
    stats = {
        "total_spent": "₹5,000",
        "txn_count": 5,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "05 Oct 2026", "description": "Lunch at cafe",
         "category": "food", "category_label": "Food", "amount": "₹450"},
        {"date": "04 Oct 2026", "description": "Metro card top-up",
         "category": "transport", "category_label": "Transport", "amount": "₹500"},
        {"date": "03 Oct 2026", "description": "Electricity bill",
         "category": "bills", "category_label": "Bills", "amount": "₹1,750"},
        {"date": "02 Oct 2026", "description": "T-shirt",
         "category": "shopping", "category_label": "Shopping", "amount": "₹1,250"},
        {"date": "01 Oct 2026", "description": "Groceries",
         "category": "food", "category_label": "Food", "amount": "₹1,050"},
    ]
    # percent must be a multiple of 5 (0-100): profile.css only defines
    # width classes in steps of 5 (.pct-0 ... .pct-100).
    categories = [
        {"name": "Bills", "amount": "₹1,750", "percent": 35},
        {"name": "Food", "amount": "₹1,500", "percent": 30},
        {"name": "Shopping", "amount": "₹1,250", "percent": 25},
        {"name": "Transport", "amount": "₹500", "percent": 10},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
