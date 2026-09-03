"""Tests for Step 07 — Add Expense.

Spec: .claude/specs/07-add-expense.md

Behaviour is derived from the spec's "Routes", "Rules for implementation" and
"Definition of done" sections, not from the implementation. The route, the
template (`add_expense.html`) and the db helpers are treated as a black box —
this file only references their public surface (route path, form field names,
redirect targets, helper signatures).
"""

from datetime import date

import pytest

from conftest import ALL_TIME_COUNT, ALL_TIME_TOTAL, USER_ID

# `<input type="date">` and the route's `today` default both use ISO YYYY-MM-DD.
TODAY = date.today().strftime("%Y-%m-%d")

# Spec "Routes" / DoD #2: the Category <select> lists exactly these 7 entries
# (the CATEGORIES list defined back in Step 05).
EXPECTED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]

# Seed baseline from conftest.
SEED_COUNT = ALL_TIME_COUNT


def rupees(value):
    """Match app.py's `currency` filter: 1234.5 -> '₹1,234.50'."""
    return f"₹{value:,.2f}"


def stat_value(value):
    """The exact markup a summary-stat tile renders for a raw (non-currency) value."""
    return f'<span class="profile-stat-value">{value}</span>'


# --------------------------------------------------------------------------- #
# Direct-DB helpers (parameterised SQL, own connection each call)             #
# --------------------------------------------------------------------------- #

def _count_expenses(db):
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


def _latest_expense(db):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()


def _valid_payload(**overrides):
    """A form body that passes every validation rule; override per-test."""
    payload = {
        "amount": "150.00",
        "category": "Food",
        "date": TODAY,
        "description": "Test expense",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# 1. Auth guards — DoD #1                                                     #
# --------------------------------------------------------------------------- #

def test_get_add_expense_requires_login(client):
    """DoD #1: logged-out GET /expenses/add redirects to /login."""
    resp = client.get("/expenses/add")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_add_expense_requires_login(client):
    """DoD #1: logged-out POST /expenses/add redirects to /login (guard covers POST)."""
    resp = client.post("/expenses/add", data=_valid_payload())

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_add_expense_logged_out_inserts_no_row(client, seeded_db):
    """DoD #1: a logged-out POST must not write to the expenses table."""
    before = _count_expenses(seeded_db)

    client.post("/expenses/add", data=_valid_payload())

    assert _count_expenses(seeded_db) == before


# --------------------------------------------------------------------------- #
# 2. GET /expenses/add — the form — DoD #2                                    #
# --------------------------------------------------------------------------- #

def test_get_add_expense_renders_form(auth_client):
    """DoD #2: logged-in GET renders a POST form for the add-expense route."""
    resp = auth_client.get("/expenses/add")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'method="POST"' in html
    assert "<form" in html


def test_get_form_has_amount_field(auth_client):
    """DoD #2: the form exposes a numeric amount field."""
    html = auth_client.get("/expenses/add").get_data(as_text=True)

    assert 'name="amount"' in html
    assert 'type="number"' in html


def test_get_form_has_category_select_with_exactly_seven_categories(auth_client, seeded_db):
    """DoD #2: Category is a <select> listing exactly the 7 CATEGORIES."""
    html = auth_client.get("/expenses/add").get_data(as_text=True)

    assert "<select" in html
    assert 'name="category"' in html
    for category in EXPECTED_CATEGORIES:
        assert f'<option value="{category}"' in html
    # One <option> per category, plus the single disabled placeholder option.
    assert html.count('<option value="') == len(EXPECTED_CATEGORIES) + 1
    assert "Bogus" not in html


def test_get_form_date_defaults_to_today(auth_client):
    """DoD #2: the date input is pre-filled with today's ISO date."""
    html = auth_client.get("/expenses/add").get_data(as_text=True)

    assert 'type="date"' in html
    assert 'name="date"' in html
    assert f'value="{TODAY}"' in html


def test_get_form_has_optional_description_field(auth_client):
    """DoD #2: there is a description field, and it is not marked required."""
    html = auth_client.get("/expenses/add").get_data(as_text=True)

    assert 'name="description"' in html
    # Isolate the description <input> and confirm it carries no `required` attr.
    start = html.index('name="description"')
    tag = html[html.rindex("<input", 0, start):html.index(">", start)]
    assert "required" not in tag


def test_get_form_action_targets_add_expense_route(auth_client):
    """DoD #2 / #11: the form action resolves via url_for('add_expense')."""
    html = auth_client.get("/expenses/add").get_data(as_text=True)

    assert 'action="/expenses/add"' in html


def test_categories_constant_matches_spec(seeded_db):
    """DoD #2: the CATEGORIES list the route feeds the <select> is exactly the 7."""
    assert list(seeded_db.CATEGORIES) == EXPECTED_CATEGORIES


# --------------------------------------------------------------------------- #
# 3. Happy path — DoD #3, #5                                                  #
# --------------------------------------------------------------------------- #

def test_valid_post_redirects_to_profile(auth_client):
    """DoD #3: a valid submission 302-redirects to /profile."""
    resp = auth_client.post(
        "/expenses/add",
        data=_valid_payload(amount="250.50", category="Food", description="Lunch"),
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_valid_post_inserts_exactly_one_row(auth_client, seeded_db):
    """DoD #3: exactly one new expenses row is created."""
    before = _count_expenses(seeded_db)

    auth_client.post(
        "/expenses/add",
        data=_valid_payload(amount="250.50", category="Food", description="Lunch"),
    )

    assert _count_expenses(seeded_db) == before + 1


def test_valid_post_row_has_correct_values(auth_client, seeded_db):
    """DoD #5: the stored row has the submitted user_id, amount, category, date, description."""
    auth_client.post(
        "/expenses/add",
        data=_valid_payload(amount="250.50", category="Food", date=TODAY,
                            description="Lunch"),
    )

    row = _latest_expense(seeded_db)
    assert row["user_id"] == USER_ID
    assert row["amount"] == pytest.approx(250.5)
    assert row["category"] == "Food"
    assert row["date"] == TODAY
    assert row["description"] == "Lunch"


def test_valid_post_amount_rounded_to_two_decimals(auth_client, seeded_db):
    """Spec Rules: amount is rounded to 2 decimals before insert."""
    auth_client.post("/expenses/add", data=_valid_payload(amount="123.456"))

    assert _latest_expense(seeded_db)["amount"] == pytest.approx(123.46)


# --------------------------------------------------------------------------- #
# 4. Optional description -> SQL NULL — DoD #6                                #
# --------------------------------------------------------------------------- #

def test_blank_description_stored_as_null(auth_client, seeded_db):
    """DoD #6: an empty description string is stored as SQL NULL."""
    auth_client.post("/expenses/add", data=_valid_payload(description="   "))

    assert _latest_expense(seeded_db)["description"] is None


def test_omitted_description_stored_as_null(auth_client, seeded_db):
    """DoD #6: an omitted description field is stored as SQL NULL."""
    payload = _valid_payload()
    del payload["description"]

    auth_client.post("/expenses/add", data=payload)

    assert _latest_expense(seeded_db)["description"] is None


# --------------------------------------------------------------------------- #
# 5. Success flash consumed once — DoD #3                                     #
# --------------------------------------------------------------------------- #

def test_success_flash_shown_once_on_profile(auth_client):
    """DoD #3: 'Expense added.' shows on the post-redirect /profile, then not again."""
    resp = auth_client.post(
        "/expenses/add", data=_valid_payload(), follow_redirects=True
    )

    assert resp.status_code == 200
    first = resp.get_data(as_text=True)
    assert "Expense added." in first
    assert "auth-success" in first

    second = auth_client.get("/profile").get_data(as_text=True)
    assert "Expense added." not in second


# --------------------------------------------------------------------------- #
# 6. New expense flows through the Step 05 helpers / profile page — DoD #4    #
# --------------------------------------------------------------------------- #

def test_new_expense_reflected_in_summary_stats(auth_client, seeded_db):
    """DoD #4: all-time total and transaction count pick up the new expense."""
    auth_client.post(
        "/expenses/add",
        data=_valid_payload(amount="250.50", category="Food", description="Lunch"),
    )

    stats = seeded_db.get_summary_stats(USER_ID)
    assert stats["txn_count"] == SEED_COUNT + 1
    assert stats["total"] == pytest.approx(ALL_TIME_TOTAL + 250.50)


def test_new_expense_reflected_in_category_breakdown(auth_client, seeded_db):
    """DoD #4: the chosen category's bar total increases by the new amount."""
    auth_client.post(
        "/expenses/add",
        data=_valid_payload(amount="250.50", category="Food", description="Lunch"),
    )

    breakdown = {r["category"]: r["total"] for r in seeded_db.get_category_breakdown(USER_ID)}
    # Seed Food total is 100 + 400 + 700 = 1200.
    assert breakdown["Food"] == pytest.approx(1200.00 + 250.50)


def test_new_expense_reflected_on_profile_page(auth_client):
    """DoD #4: /profile shows the incremented count, higher total, and the new row."""
    auth_client.post(
        "/expenses/add",
        data=_valid_payload(amount="250.50", category="Food", description="Lunch"),
    )

    html = auth_client.get("/profile").get_data(as_text=True)
    assert stat_value(SEED_COUNT + 1) in html
    assert rupees(ALL_TIME_TOTAL + 250.50) in html
    assert "Lunch" in html


# --------------------------------------------------------------------------- #
# 7. Validation-failure matrix — DoD #7, #8, #9, #10                         #
# --------------------------------------------------------------------------- #

_OMIT = object()

VALIDATION_CASES = [
    ("amount_zero", {"amount": "0"}),
    ("amount_negative", {"amount": "-5.00"}),
    ("amount_non_numeric", {"amount": "notanumber"}),
    ("amount_omitted", {"amount": _OMIT}),
    ("amount_empty", {"amount": ""}),
    ("amount_ten_million", {"amount": "10000000"}),
    ("amount_absurdly_large", {"amount": "99999999.99"}),
    ("category_not_in_list", {"category": "Bogus"}),
    ("category_omitted", {"category": _OMIT}),
    ("category_empty", {"category": ""}),
    ("date_omitted", {"date": _OMIT}),
    ("date_empty", {"date": ""}),
    ("date_malformed", {"date": "notadate"}),
    ("date_impossible", {"date": "2026-13-45"}),
    ("description_over_200_chars", {"description": "x" * 201}),
]


@pytest.mark.parametrize(
    "override", [c[1] for c in VALIDATION_CASES], ids=[c[0] for c in VALIDATION_CASES]
)
def test_validation_failure_rerenders_without_inserting(auth_client, seeded_db, override):
    """DoD #7-10: each invalid field re-renders the form (HTTP 200, inline error) and
    inserts no row."""
    payload = _valid_payload()
    for key, value in override.items():
        if value is _OMIT:
            payload.pop(key, None)
        else:
            payload[key] = value

    before = _count_expenses(seeded_db)
    resp = auth_client.post("/expenses/add", data=payload)

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    assert _count_expenses(seeded_db) == before


# --------------------------------------------------------------------------- #
# 8. Sticky field values on a validation re-render — DoD #7                   #
# --------------------------------------------------------------------------- #

def test_sticky_values_on_validation_rerender(auth_client):
    """DoD #7: on a re-render the submitted amount, category and description persist."""
    resp = auth_client.post(
        "/expenses/add",
        data={
            "amount": "abc",                 # invalid -> triggers the re-render
            "category": "Transport",
            "date": "2026-01-02",
            "description": "Sticky note",
        },
    )

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'value="abc"' in html                        # amount re-populated
    assert 'value="Transport" selected' in html         # chosen category re-selected
    assert 'value="2026-01-02"' in html                 # date re-populated
    assert 'value="Sticky note"' in html                # description re-populated


# --------------------------------------------------------------------------- #
# 9. Still-stubbed edit / delete routes — DoD #12                             #
# --------------------------------------------------------------------------- #

def test_edit_expense_stub_unchanged(client):
    """DoD #12: GET /expenses/<id>/edit still returns its Step 8 placeholder."""
    resp = client.get("/expenses/1/edit")

    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "Edit expense — coming in Step 8"


def test_delete_expense_stub_unchanged(client):
    """DoD #12: GET /expenses/<id>/delete still returns its Step 9 placeholder."""
    resp = client.get("/expenses/1/delete")

    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "Delete expense — coming in Step 9"


# --------------------------------------------------------------------------- #
# 10. create_expense(...) helper — Spec "Database changes"                    #
# --------------------------------------------------------------------------- #

def test_create_expense_inserts_row_and_returns_id(seeded_db):
    """Spec DB changes: create_expense inserts one row and returns its new id."""
    before = _count_expenses(seeded_db)

    new_id = seeded_db.create_expense(USER_ID, 42.50, "Bills", "2026-05-05", "unit test")

    assert isinstance(new_id, int)
    assert _count_expenses(seeded_db) == before + 1
    row = _latest_expense(seeded_db)
    assert row["id"] == new_id
    assert row["user_id"] == USER_ID
    assert row["amount"] == pytest.approx(42.50)
    assert row["category"] == "Bills"
    assert row["date"] == "2026-05-05"
    assert row["description"] == "unit test"


def test_create_expense_accepts_none_description(seeded_db):
    """Spec DB changes: description=None is stored as SQL NULL."""
    seeded_db.create_expense(USER_ID, 10.0, "Other", "2026-05-05", None)

    assert _latest_expense(seeded_db)["description"] is None
