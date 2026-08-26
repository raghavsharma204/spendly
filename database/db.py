import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

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
