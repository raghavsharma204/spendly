import os
import sqlite3
from datetime import date, datetime

from werkzeug.security import check_password_hash, generate_password_hash

# database/db.py -> database/ -> repo root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "expense_tracker.db")

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    """Open a new SQLite connection with row access by column name and FK enforcement on."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist yet. Safe to call on every startup."""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert demo user + sample expenses once. No-op if users already exist."""
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        if row["count"] > 0:
            return

        password_hash = generate_password_hash("demo123", method="pbkdf2:sha256")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", password_hash),
        )
        user_id = cursor.lastrowid

        today = date.today()
        sample_expenses = [
            (450.00, "Food", _day_in_current_month(today, 2), "Groceries at local market"),
            (120.50, "Transport", _day_in_current_month(today, 4), "Auto rickshaw fare"),
            (1500.00, "Bills", _day_in_current_month(today, 5), "Electricity bill"),
            (800.00, "Health", _day_in_current_month(today, 9), "Pharmacy purchase"),
            (350.75, "Entertainment", _day_in_current_month(today, 12), "Movie tickets"),
            (2200.00, "Shopping", _day_in_current_month(today, 15), "New shoes"),
            (99.00, "Other", _day_in_current_month(today, 18), "Miscellaneous purchase"),
            (600.00, "Food", _day_in_current_month(today, 21), "Dinner with friends"),
        ]
        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(user_id, amount, category, exp_date, desc) for amount, category, exp_date, desc in sample_expenses],
        )
        conn.commit()
    finally:
        conn.close()


def _day_in_current_month(base_date, day):
    """Return an ISO date string (YYYY-MM-DD) for `day` in the same month/year as base_date."""
    return base_date.replace(day=day).isoformat()


def create_user(name, email, password):
    """Insert a new user with a hashed password. Returns the new user id, or None if the email is already taken."""
    name = name.strip()
    email = email.strip().lower()

    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return None

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, password_hash),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    finally:
        conn.close()


def create_expense(user_id, amount, category, date, description):
    """Insert one expense row for a user. Returns the new expense id.

    `description` may be None (stored as SQL NULL). Callers must validate
    amount / category / date before calling — this helper only writes.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id, user_id):
    """Fetch a single expense scoped to its owner.

    Returns the row, or None if no expense with that id belongs to that user.
    Scoping by user_id in the SQL *is* the ownership check — callers must pass
    the session's user id, never a client-supplied one.
    """
    conn = get_db()
    try:
        return conn.execute(
            """
            SELECT id, user_id, amount, category, date, description
            FROM expenses
            WHERE id = ? AND user_id = ?
            """,
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, date, description):
    """Update one expense's editable fields, scoped to its owner.

    Returns cursor.rowcount (1 on success, 0 if no such row for that user).
    `description` may be None (stored as SQL NULL). Callers must validate
    amount / category / date before calling — this helper only writes, and
    never touches user_id or created_at.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            UPDATE expenses
            SET amount = ?, category = ?, date = ?, description = ?
            WHERE id = ? AND user_id = ?
            """,
            (amount, category, date, description, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def authenticate_user(email, password):
    """Verify email/password against the users table. Returns the user row on success, None otherwise."""
    email = email.strip().lower()

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None:
            return None

        if not check_password_hash(user["password_hash"], password):
            return None

        return user
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Fetch a single user by id. Returns the row, or None if not found."""
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()


def _date_range_clause(start, end):
    """Return (sql_fragment, params) for an optional inclusive date range.

    Fragment is "" when both bounds are None. Values are bound with ?
    placeholders — the fragment never contains a literal date.
    """
    fragment = ""
    params = []
    if start is not None:
        fragment += " AND date >= ?"
        params.append(start)
    if end is not None:
        fragment += " AND date <= ?"
        params.append(end)
    return fragment, tuple(params)


def get_recent_transactions(user_id, limit=10, start=None, end=None):
    """Return the user's most recent expenses (newest first), at most `limit` rows.
    Optionally restrict to expenses whose date falls in [start, end] (inclusive,
    ISO YYYY-MM-DD strings; either bound may be None)."""
    date_clause, date_params = _date_range_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT id, amount, category, date, description
            FROM expenses
            WHERE user_id = ?
            """
            + date_clause
            + """
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()

    transactions = []
    for row in rows:
        transactions.append({
            "id": row["id"],
            "amount": row["amount"],
            "category": row["category"],
            "date": row["date"],
            "display_date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%b %d, %Y"),
            "description": row["description"],
        })
    return transactions


def get_summary_stats(user_id, start=None, end=None):
    """Return headline spend figures for a user: all-time total, transaction count,
    average transaction amount, and current calendar-month total. When start/end
    (inclusive ISO YYYY-MM-DD bounds, either may be None) are given, total, count
    and average are scoped to that range; month_total always means the current
    calendar month (and so reads 0 when the range excludes it)."""
    date_clause, date_params = _date_range_clause(start, end)
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS txn_count,
                COALESCE(SUM(amount), 0) AS total,
                COALESCE(AVG(amount), 0) AS avg_amount,
                COALESCE(SUM(
                    CASE WHEN strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
                         THEN amount END
                ), 0) AS month_total
            FROM expenses
            WHERE user_id = ?
            """
            + date_clause,
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total": row["total"],
        "txn_count": row["txn_count"],
        "avg_amount": row["avg_amount"],
        "month_total": row["month_total"],
    }


def get_category_breakdown(user_id, start=None, end=None):
    """Return per-category spend totals for a user as bar rows, ordered by CATEGORIES.
    Each row: {category, total, pct, variant}. pct is relative to the largest category.
    Categories with no spend are omitted. Optionally restrict to expenses whose date
    falls in [start, end] (inclusive ISO YYYY-MM-DD bounds, either may be None).
    Returns [] if the user has no expenses in range."""
    date_clause, date_params = _date_range_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total
            FROM expenses
            WHERE user_id = ?
            """
            + date_clause
            + """
            GROUP BY category
            """,
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()

    by_category = {row["category"]: row["total"] for row in rows}
    max_category_total = max(by_category.values()) if by_category else 0

    breakdown = []
    for category in CATEGORIES:
        if category not in by_category:
            continue
        cat_total = by_category[category]
        pct = round((cat_total / max_category_total) * 100) if max_category_total else 0
        breakdown.append({
            "category": category,
            "total": cat_total,
            "pct": pct,
            "variant": CATEGORIES.index(category) + 1,
        })
    return breakdown
