"""Shared fixtures for the Spendly test suite.

The application (`app.py`) and `database/db.py` are treated as a black box:
fixtures here only wire up an isolated temp SQLite database, seed a known set
of expenses, and hand back a Flask test client (optionally logged in).
"""

import os
import sys
from datetime import date

import pytest

# pytest puts the `tests/` directory on sys.path (prepend import mode); make the
# project root importable so `import app` / `import database.db` resolve.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# The seeded user is the first (and only) row inserted, so its id is 1.
USER_ID = 1

# (amount, category, date, description). Fixed ISO dates so date-range
# assertions stay stable regardless of when the suite runs.
SEED_EXPENSES = [
    (100.00, "Food", "2026-06-10", "June food"),
    (200.00, "Transport", "2026-07-15", "July transport"),
    (300.00, "Bills", "2026-08-01", "August bills"),
    (400.00, "Food", "2026-08-15", "August food"),
    (500.00, "Shopping", "2026-08-31", "August shopping"),
    (600.00, "Health", "2026-09-05", "September health"),
    (700.00, "Food", "2026-09-20", "September food"),
]

# All-time figures derived from SEED_EXPENSES (range-independent).
ALL_TIME_TOTAL = 2800.00
ALL_TIME_COUNT = 7
ALL_TIME_AVG = 400.00


def current_year_month():
    return date.today().strftime("%Y-%m")


def expected_month_total(start=None, end=None):
    """Sum of seed amounts in the current calendar month AND the given range.

    Mirrors the spec: `month_total` is never range-adjusted, so when a filter is
    active it means "current calendar month AND within the selected range".
    """
    year_month = current_year_month()
    total = 0.0
    for amount, _category, iso_date, _description in SEED_EXPENSES:
        if start is not None and iso_date < start:
            continue
        if end is not None and iso_date > end:
            continue
        if iso_date[:7] == year_month:
            total += amount
    return total


def _seed(db):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("Test User", "test@example.com", "pbkdf2:sha256$fake$hash",
             "2026-01-15 09:00:00"),
        )
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (USER_ID, amount, category, iso_date, description)
                for amount, category, iso_date, description in SEED_EXPENSES
            ],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Isolated temp DB with schema + known seed rows. Yields the db module."""
    import database.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_expense_tracker.db"))
    db.init_db()
    _seed(db)
    return db


@pytest.fixture
def app(seeded_db):
    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as session:
        session["user_id"] = USER_ID
    return client
