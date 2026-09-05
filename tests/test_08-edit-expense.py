"""Tests for Step 08 — Edit Expense.

Spec: .claude/specs/08-edit-expense.md

Behaviour is derived from the spec's "Routes", "Rules for implementation" and
"Definition of done" sections, not from the implementation. The route, the
template (`edit_expense.html`) and the db helpers are treated as a black box —
this file only references their public surface (route path, form field names,
redirect targets, helper signatures).
"""

import pytest

from conftest import ALL_TIME_COUNT, ALL_TIME_TOTAL, SEED_EXPENSES, USER_ID

# Spec "Routes" / DoD #2: the Category <select> lists exactly these 7 entries
# (the CATEGORIES list defined back in Step 05).
EXPECTED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]

# conftest seeds expenses with ids 1..7 in SEED_EXPENSES order; id 1 is the row
# most tests edit: (100.00, "Food", "2026-06-10", "June food").
TARGET_ID = 1
TARGET_SEED = SEED_EXPENSES[TARGET_ID - 1]

VALID_DATE = "2026-05-05"


def rupees(value):
    """Match app.py's `currency` filter: 1234.5 -> '₹1,234.50'."""
    return f"₹{value:,.2f}"


def stat_value(value):
    """The exact markup a summary-stat tile renders for a raw (non-currency) value."""
    return f'<span class="profile-stat-value">{value}</span>'


# --------------------------------------------------------------------------- #
# Direct-DB helpers (parameterised SQL, own connection each call)             #
# --------------------------------------------------------------------------- #

def _get_expense(db, expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _snapshot(db, expense_id):
    """Full comparable tuple of a row's mutable + immutable columns."""
    row = _get_expense(db, expense_id)
    if row is None:
        return None
    return (
        row["user_id"],
        row["amount"],
        row["category"],
        row["date"],
        row["description"],
        row["created_at"],
    )


def _count_expenses(db):
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


def _set_description(db, expense_id, value):
    conn = db.get_db()
    try:
        conn.execute(
            "UPDATE expenses SET description = ? WHERE id = ?", (value, expense_id)
        )
        conn.commit()
    finally:
        conn.close()


def _seed_other_user(db):
    """Insert a second user + one expense they own. Returns (user_id, expense_id)."""
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("Other User", "other@example.com", "pbkdf2:sha256$fake$hash",
             "2026-02-01 09:00:00"),
        )
        other_user_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (other_user_id, 4321.00, "Entertainment", "2026-03-03", "not yours"),
        )
        other_expense_id = cur.lastrowid
        conn.commit()
        return other_user_id, other_expense_id
    finally:
        conn.close()


_OMIT = object()


def _valid_payload(**overrides):
    """A form body that passes every validation rule; override per-test."""
    payload = {
        "amount": "150.00",
        "category": "Food",
        "date": VALID_DATE,
        "description": "Edited expense",
    }
    payload.update(overrides)
    return payload


def _apply(payload, override):
    for key, value in override.items():
        if value is _OMIT:
            payload.pop(key, None)
        else:
            payload[key] = value
    return payload


# --------------------------------------------------------------------------- #
# 1. Auth guards (GET + POST) — DoD #1                                        #
# --------------------------------------------------------------------------- #

def test_get_edit_requires_login(client):
    """DoD #1: logged-out GET /expenses/1/edit redirects to /login."""
    resp = client.get("/expenses/1/edit")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_edit_requires_login(client):
    """DoD #1: logged-out POST /expenses/1/edit redirects to /login (guard covers POST)."""
    resp = client.post("/expenses/1/edit", data=_valid_payload())

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_edit_logged_out_updates_no_row(client, seeded_db):
    """DoD #1: a logged-out POST must not modify the target row."""
    before = _snapshot(seeded_db, TARGET_ID)

    client.post("/expenses/1/edit", data=_valid_payload(amount="999.99"))

    assert _snapshot(seeded_db, TARGET_ID) == before


# --------------------------------------------------------------------------- #
# 2. Ownership + 404 handling (GET + POST) — DoD #9, #10, #11                 #
# --------------------------------------------------------------------------- #

def test_get_nonexistent_id_returns_404(auth_client):
    """DoD #9: logged-in GET of a nonexistent expense id returns HTTP 404."""
    resp = auth_client.get("/expenses/9999/edit")

    assert resp.status_code == 404


def test_post_nonexistent_id_returns_404(auth_client):
    """DoD #9: logged-in POST to a nonexistent expense id returns HTTP 404."""
    resp = auth_client.post("/expenses/9999/edit", data=_valid_payload())

    assert resp.status_code == 404


def test_non_integer_id_returns_404(auth_client):
    """DoD #11: /expenses/abc/edit (non-integer id) 404s via the route converter."""
    assert auth_client.get("/expenses/abc/edit").status_code == 404


def test_get_other_users_expense_returns_404(auth_client, seeded_db):
    """DoD #10: GET of another user's expense id returns 404 (no data disclosed)."""
    _other_uid, other_eid = _seed_other_user(seeded_db)

    resp = auth_client.get(f"/expenses/{other_eid}/edit")

    assert resp.status_code == 404


def test_post_other_users_expense_404_and_row_unchanged(auth_client, seeded_db):
    """DoD #10: POST to another user's expense id 404s and leaves that row unchanged."""
    _other_uid, other_eid = _seed_other_user(seeded_db)
    before = _snapshot(seeded_db, other_eid)

    resp = auth_client.post(
        f"/expenses/{other_eid}/edit", data=_valid_payload(amount="999.99")
    )

    assert resp.status_code == 404
    assert _snapshot(seeded_db, other_eid) == before


# --------------------------------------------------------------------------- #
# 3. GET (owner) — pre-filled form — DoD #2                                   #
# --------------------------------------------------------------------------- #

def test_get_edit_renders_form(auth_client):
    """DoD #2: logged-in owner GET renders a POST form."""
    resp = auth_client.get("/expenses/1/edit")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<form" in html
    assert 'method="POST"' in html


def test_get_form_prefilled_from_stored_row(auth_client, seeded_db):
    """DoD #2: amount, date and description are populated from the stored expense."""
    row = seeded_db.get_expense_by_id(TARGET_ID, USER_ID)
    html = auth_client.get("/expenses/1/edit").get_data(as_text=True)

    assert f'value="{row["amount"]:.2f}"' in html  # rendered to 2 decimals
    assert f'value="{row["date"]}"' in html
    assert f'value="{row["description"]}"' in html


def test_get_form_marks_stored_category_selected(auth_client):
    """DoD #2: the stored category's <option> is the one marked selected."""
    html = auth_client.get("/expenses/1/edit").get_data(as_text=True)

    assert '<option value="Food" selected>' in html
    assert '<option value="Transport" selected>' not in html


def test_get_form_lists_exactly_seven_categories(auth_client):
    """DoD #2: the Category <select> offers exactly the 7 CATEGORIES (+ placeholder)."""
    html = auth_client.get("/expenses/1/edit").get_data(as_text=True)

    for category in EXPECTED_CATEGORIES:
        assert f'<option value="{category}"' in html
    assert html.count('<option value="') == len(EXPECTED_CATEGORIES) + 1


def test_get_form_action_targets_edit_route(auth_client):
    """DoD #2: the form action resolves to /expenses/<id>/edit."""
    html = auth_client.get("/expenses/1/edit").get_data(as_text=True)

    assert 'action="/expenses/1/edit"' in html


def test_get_form_submit_button_label(auth_client):
    """DoD #2: the submit button reads 'Save changes'."""
    html = auth_client.get("/expenses/1/edit").get_data(as_text=True)

    assert "Save changes" in html


# --------------------------------------------------------------------------- #
# 4. Happy-path POST (owner) — DoD #3, #5                                     #
# --------------------------------------------------------------------------- #

def test_valid_post_redirects_to_profile(auth_client):
    """DoD #3: a valid edit 302-redirects to /profile."""
    resp = auth_client.post("/expenses/1/edit", data=_valid_payload(amount="999.99"))

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_valid_post_updates_only_target_row(auth_client, seeded_db):
    """DoD #4/#5: exactly the target row changes; every other row is untouched."""
    others_before = {i: _snapshot(seeded_db, i) for i in range(2, ALL_TIME_COUNT + 1)}

    auth_client.post(
        "/expenses/1/edit",
        data=_valid_payload(amount="999.99", category="Bills", date="2026-04-04",
                            description="new text"),
    )

    row = _get_expense(seeded_db, TARGET_ID)
    assert row["amount"] == pytest.approx(999.99)
    assert row["category"] == "Bills"
    assert row["date"] == "2026-04-04"
    assert row["description"] == "new text"
    assert _count_expenses(seeded_db) == ALL_TIME_COUNT
    for i, snap in others_before.items():
        assert _snapshot(seeded_db, i) == snap


def test_valid_post_preserves_id_user_id_and_created_at(auth_client, seeded_db):
    """DoD #5: id, user_id and created_at are unchanged by an edit."""
    before = _get_expense(seeded_db, TARGET_ID)

    auth_client.post("/expenses/1/edit", data=_valid_payload(amount="999.99"))

    after = _get_expense(seeded_db, TARGET_ID)
    assert after["id"] == before["id"] == TARGET_ID
    assert after["user_id"] == before["user_id"]
    assert after["created_at"] == before["created_at"]
    assert after["amount"] == pytest.approx(999.99)


def test_valid_post_amount_rounded_to_two_decimals(auth_client, seeded_db):
    """Spec Rules: amount is rounded to 2 decimals before the update."""
    auth_client.post("/expenses/1/edit", data=_valid_payload(amount="123.456"))

    assert _get_expense(seeded_db, TARGET_ID)["amount"] == pytest.approx(123.46)


# --------------------------------------------------------------------------- #
# 5. Success flash consumed once — DoD #3                                     #
# --------------------------------------------------------------------------- #

def test_success_flash_shown_once_on_profile(auth_client):
    """DoD #3: 'Expense updated.' shows on the post-redirect /profile, then not again."""
    resp = auth_client.post(
        "/expenses/1/edit", data=_valid_payload(amount="999.99"),
        follow_redirects=True,
    )

    assert resp.status_code == 200
    first = resp.get_data(as_text=True)
    assert "Expense updated." in first
    assert "auth-success" in first

    second = auth_client.get("/profile").get_data(as_text=True)
    assert "Expense updated." not in second


# --------------------------------------------------------------------------- #
# 6. Edit flows through the Step 05 helpers / profile page — DoD #4          #
# --------------------------------------------------------------------------- #

def test_edit_reflected_in_summary_stats(auth_client, seeded_db):
    """DoD #4: all-time total tracks the new amount; transaction count is unchanged."""
    auth_client.post("/expenses/1/edit", data=_valid_payload(amount="999.99",
                                                             category="Food"))

    stats = seeded_db.get_summary_stats(USER_ID)
    assert stats["txn_count"] == ALL_TIME_COUNT
    assert stats["total"] == pytest.approx(ALL_TIME_TOTAL - TARGET_SEED[0] + 999.99)


def test_edit_reflected_in_category_breakdown(auth_client, seeded_db):
    """DoD #4: the category breakdown picks up the edited amount."""
    auth_client.post("/expenses/1/edit", data=_valid_payload(amount="999.99",
                                                             category="Food"))

    breakdown = {r["category"]: r["total"]
                 for r in seeded_db.get_category_breakdown(USER_ID)}
    # Seed Food total is 100 + 400 + 700 = 1200; row 1 (100) becomes 999.99.
    assert breakdown["Food"] == pytest.approx(1200.00 - 100.00 + 999.99)


def test_edit_reflected_on_profile_page(auth_client):
    """DoD #4: /profile renders the new total, the new amount, and the same count."""
    auth_client.post("/expenses/1/edit", data=_valid_payload(amount="999.99",
                                                             category="Food"))

    html = auth_client.get("/profile").get_data(as_text=True)
    assert stat_value(ALL_TIME_COUNT) in html
    assert rupees(ALL_TIME_TOTAL - TARGET_SEED[0] + 999.99) in html
    assert rupees(999.99) in html


# --------------------------------------------------------------------------- #
# 7. Description handling — DoD #6                                            #
# --------------------------------------------------------------------------- #

def test_clearing_description_stores_sql_null(auth_client, seeded_db):
    """DoD #6: submitting an empty description stores SQL NULL."""
    auth_client.post("/expenses/1/edit", data=_valid_payload(description="   "))

    assert _get_expense(seeded_db, TARGET_ID)["description"] is None


def test_cleared_description_renders_emdash_on_profile(auth_client, seeded_db):
    """DoD #6: a NULL description renders as '—' in the transactions table."""
    auth_client.post("/expenses/1/edit", data=_valid_payload(description=""))

    html = auth_client.get("/profile").get_data(as_text=True)
    assert TARGET_SEED[3] not in html  # old description text is gone
    assert "—" in html


def test_editing_null_description_row_stores_new_text(auth_client, seeded_db):
    """DoD #6: editing a NULL-description row to add text stores the text."""
    _set_description(seeded_db, TARGET_ID, None)

    auth_client.post(
        "/expenses/1/edit", data=_valid_payload(description="Now it has a note")
    )

    assert _get_expense(seeded_db, TARGET_ID)["description"] == "Now it has a note"


# --------------------------------------------------------------------------- #
# 8. Validation-failure matrix — DoD #7, #8                                   #
# --------------------------------------------------------------------------- #

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
    ("date_malformed", {"date": "foo"}),
    ("date_impossible", {"date": "2026-13-45"}),
    ("description_over_200_chars", {"description": "x" * 201}),
]


@pytest.mark.parametrize(
    "override", [c[1] for c in VALIDATION_CASES], ids=[c[0] for c in VALIDATION_CASES]
)
def test_validation_failure_rerenders_without_updating(auth_client, seeded_db, override):
    """DoD #7/#8: each invalid field re-renders the form (HTTP 200, inline error) and
    updates no row."""
    before = _snapshot(seeded_db, TARGET_ID)
    payload = _apply(_valid_payload(), override)

    resp = auth_client.post("/expenses/1/edit", data=payload)

    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    assert _snapshot(seeded_db, TARGET_ID) == before


# --------------------------------------------------------------------------- #
# 9. Sticky field values on a validation re-render — spec Rules / DoD #7      #
# --------------------------------------------------------------------------- #

def test_sticky_values_on_validation_rerender(auth_client):
    """Spec: on a re-render the submitted amount, category, date and description
    are re-populated (not the stored row's values)."""
    resp = auth_client.post(
        "/expenses/1/edit",
        data={
            "amount": "abc",                 # invalid -> triggers the re-render
            "category": "Transport",
            "date": "2026-01-02",
            "description": "Sticky note",
        },
    )

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'value="abc"' in html
    assert '<option value="Transport" selected>' in html
    assert '<option value="Food" selected>' not in html
    assert 'value="2026-01-02"' in html
    assert 'value="Sticky note"' in html


# --------------------------------------------------------------------------- #
# 10. Profile "Edit" links — DoD #12                                         #
# --------------------------------------------------------------------------- #

def test_every_profile_txn_row_has_edit_link(auth_client):
    """DoD #12: each transactions row links to its expense's edit form via url_for."""
    html = auth_client.get("/profile").get_data(as_text=True)

    for expense_id in range(1, ALL_TIME_COUNT + 1):
        assert f'href="/expenses/{expense_id}/edit"' in html
    assert html.count('class="profile-txn-edit"') == ALL_TIME_COUNT


# --------------------------------------------------------------------------- #
# 11. Still-stubbed delete route — DoD #13                                    #
# --------------------------------------------------------------------------- #

def test_delete_expense_stub_unchanged(client):
    """DoD #13: GET /expenses/1/delete still returns its Step 9 placeholder string."""
    resp = client.get("/expenses/1/delete")

    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "Delete expense — coming in Step 9"


# --------------------------------------------------------------------------- #
# 12. DB helper: get_expense_by_id(expense_id, user_id) — spec "DB changes"   #
# --------------------------------------------------------------------------- #

def test_get_expense_by_id_returns_row_for_owner(seeded_db):
    """Spec DB changes: get_expense_by_id returns the row for its owner."""
    row = seeded_db.get_expense_by_id(TARGET_ID, USER_ID)

    assert row is not None
    assert row["id"] == TARGET_ID
    assert row["user_id"] == USER_ID
    assert row["amount"] == pytest.approx(TARGET_SEED[0])
    assert row["category"] == TARGET_SEED[1]
    assert row["date"] == TARGET_SEED[2]
    assert row["description"] == TARGET_SEED[3]


def test_get_expense_by_id_wrong_user_returns_none(seeded_db):
    """Spec DB changes: a mismatched user_id yields None (ownership boundary)."""
    assert seeded_db.get_expense_by_id(TARGET_ID, 999) is None


def test_get_expense_by_id_missing_id_returns_none(seeded_db):
    """Spec DB changes: an id with no matching row yields None."""
    assert seeded_db.get_expense_by_id(9999, USER_ID) is None


def test_get_expense_by_id_scopes_to_owner_across_users(seeded_db):
    """Spec DB changes: another user's expense is invisible to the wrong user_id."""
    other_uid, other_eid = _seed_other_user(seeded_db)

    assert seeded_db.get_expense_by_id(other_eid, USER_ID) is None
    assert seeded_db.get_expense_by_id(other_eid, other_uid) is not None


# --------------------------------------------------------------------------- #
# 13. DB helper: update_expense(...) — spec "DB changes"                      #
# --------------------------------------------------------------------------- #

def test_update_expense_updates_row_and_returns_rowcount(seeded_db):
    """Spec DB changes: update_expense writes the four fields and returns rowcount 1."""
    rc = seeded_db.update_expense(TARGET_ID, USER_ID, 55.55, "Bills",
                                  "2026-02-02", "changed")

    assert rc == 1
    row = _get_expense(seeded_db, TARGET_ID)
    assert row["amount"] == pytest.approx(55.55)
    assert row["category"] == "Bills"
    assert row["date"] == "2026-02-02"
    assert row["description"] == "changed"


def test_update_expense_accepts_none_description(seeded_db):
    """Spec DB changes: description=None is stored as SQL NULL."""
    seeded_db.update_expense(TARGET_ID, USER_ID, 55.55, "Bills", "2026-02-02", None)

    assert _get_expense(seeded_db, TARGET_ID)["description"] is None


def test_update_expense_does_not_touch_user_id_or_created_at(seeded_db):
    """Spec DB changes: update_expense never modifies user_id or created_at."""
    before = _get_expense(seeded_db, TARGET_ID)

    seeded_db.update_expense(TARGET_ID, USER_ID, 55.55, "Bills", "2026-02-02", "x")

    after = _get_expense(seeded_db, TARGET_ID)
    assert after["user_id"] == before["user_id"]
    assert after["created_at"] == before["created_at"]


def test_update_expense_wrong_user_changes_nothing_and_returns_zero(seeded_db):
    """Spec DB changes: a mismatched user_id updates no row and returns rowcount 0."""
    before = _snapshot(seeded_db, TARGET_ID)

    rc = seeded_db.update_expense(TARGET_ID, 999, 55.55, "Bills", "2026-02-02", "x")

    assert rc == 0
    assert _snapshot(seeded_db, TARGET_ID) == before


def test_update_expense_updates_only_the_target_row(seeded_db):
    """Spec DB changes: the WHERE id = ? clause confines the write to one row."""
    others_before = {i: _snapshot(seeded_db, i) for i in range(2, ALL_TIME_COUNT + 1)}

    seeded_db.update_expense(TARGET_ID, USER_ID, 55.55, "Bills", "2026-02-02", "x")

    for i, snap in others_before.items():
        assert _snapshot(seeded_db, i) == snap
