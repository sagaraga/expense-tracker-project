"""Read-only query helpers for the profile page.

Each helper opens its own connection via get_db() and closes it before
returning. No Flask imports here.
"""
from datetime import datetime

from database.db import get_db


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) limiting expenses to an inclusive range."""
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


def get_user_by_id(user_id):
    """Return {"name", "email", "member_since"} for the user, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
    }


# ==== SECTION: transactions (owned by subagent 1) ==== #

def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return the user's newest expenses as a list of dicts."""
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


# ==== END SECTION: transactions ==== #


# ==== SECTION: stats (owned by subagent 2) ==== #

def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {"total_spent", "transaction_count", "top_category"}."""
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) "
            "FROM expenses WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY SUM(amount) DESC, category LIMIT 1",
            (user_id, *params),
        ).fetchone()
    finally:
        conn.close()

    if totals[1] == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
    return {
        "total_spent": round(totals[0], 2),
        "transaction_count": totals[1],
        "top_category": top[0] if top else "—",
    }


# ==== END SECTION: stats ==== #


# ==== SECTION: categories (owned by subagent 3) ==== #

def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return [{"name", "amount", "pct"}] sorted by amount desc.

    pct values are ints that sum to exactly 100 (remainder goes to the
    largest category). Returns [] when the user has no expenses.
    """
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category "
            "ORDER BY SUM(amount) DESC, category",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total <= 0:
        return []

    breakdown = [
        {
            "name": row["category"],
            "amount": row["total"],
            "pct": round(100 * row["total"] / grand_total),
        }
        for row in rows
    ]
    breakdown[0]["pct"] += 100 - sum(item["pct"] for item in breakdown)
    return breakdown


# ==== END SECTION: categories ==== #
