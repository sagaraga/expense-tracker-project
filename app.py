import os
import sqlite3
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database import queries
from database.db import (
    create_user,
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


# ------------------------------------------------------------------ #
# Profile page                                                        #
# ------------------------------------------------------------------ #

def _fmt_money(amount):
    return f"₹{amount:,.2f}"


def _build_user_ctx(user):
    parts = user["name"].split()
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"
    return {**user, "initials": initials}


# ==== SECTION: transactions ctx (owned by subagent 1) ==== #

def _build_transactions_ctx(user_id):
    return [
        {
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": row["description"],
            "category": row["category"].lower(),
            "category_label": row["category"],
            "amount": _fmt_money(row["amount"]),
        }
        for row in queries.get_recent_transactions(user_id)
    ]


# ==== END SECTION: transactions ctx ==== #


# ==== SECTION: stats ctx (owned by subagent 2) ==== #

def _build_stats_ctx(user_id):
    stats = queries.get_summary_stats(user_id)
    return {
        "total_spent": _fmt_money(stats["total_spent"]),
        "txn_count": stats["transaction_count"],
        "top_category": stats["top_category"],
    }


# ==== END SECTION: stats ctx ==== #


# ==== SECTION: categories ctx (owned by subagent 3) ==== #

def _build_categories_ctx(user_id):
    return [
        {
            "name": item["name"],
            "amount": _fmt_money(item["amount"]),
            "percent": item["pct"],
        }
        for item in queries.get_category_breakdown(user_id)
    ]


# ==== END SECTION: categories ctx ==== #


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = queries.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=_build_user_ctx(user),
        stats=_build_stats_ctx(user_id),
        transactions=_build_transactions_ctx(user_id),
        categories=_build_categories_ctx(user_id),
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
