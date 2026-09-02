"""Tests for Step 06 — Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile-page.md

Behaviour is derived from the spec's "Routes", "Database changes" and
"Definition of done" sections, not from the implementation. The route, the
templates and the db helpers are treated as a black box.
"""

import pytest

from conftest import (
    ALL_TIME_AVG,
    ALL_TIME_COUNT,
    ALL_TIME_TOTAL,
    USER_ID,
    expected_month_total,
)


def rupees(value):
    """Match app.py's `currency` filter: 1234.5 -> '₹1,234.50'."""
    return f"₹{value:,.2f}"


def stat_value(value):
    """The exact markup a summary-stat tile renders for a raw (non-currency) value."""
    return f'<span class="profile-stat-value">{value}</span>'


def cat_row(name):
    return f'<span class="mock-cat">{name}</span>'


AUG = {"start": "2026-08-01", "end": "2026-08-31"}


# --------------------------------------------------------------------------- #
# Route: GET /profile — happy path / unfiltered                               #
# --------------------------------------------------------------------------- #

def test_profile_no_query_string_renders_unfiltered(auth_client):
    """DoD #1: GET /profile with no query string shows the all-time figures."""
    resp = auth_client.get("/profile")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert rupees(ALL_TIME_TOTAL) in html          # All-time spend ₹2,800.00
    assert stat_value(ALL_TIME_COUNT) in html       # Transactions 7
    assert rupees(ALL_TIME_AVG) in html             # Average transaction ₹400.00
    assert rupees(expected_month_total()) in html   # This month (current-month subset)
    # Every seeded transaction is listed when unfiltered.
    for description in ("June food", "July transport", "August bills",
                        "September food"):
        assert description in html


# --------------------------------------------------------------------------- #
# Route: the filter form                                                      #
# --------------------------------------------------------------------------- #

def test_filter_form_present_and_targets_profile(auth_client):
    """DoD #2: a GET form to /profile with start + end date inputs is rendered."""
    html = auth_client.get("/profile").get_data(as_text=True)

    assert "<form" in html
    assert 'method="GET"' in html
    assert 'action="/profile"' in html          # url_for('profile')
    assert 'name="start"' in html
    assert 'name="end"' in html
    assert 'type="date"' in html


def test_filter_form_has_submit_control(auth_client):
    """DoD #2: the filter form exposes a submit control ("Apply")."""
    html = auth_client.get("/profile").get_data(as_text=True)

    assert 'type="submit"' in html
    assert "Apply" in html


# --------------------------------------------------------------------------- #
# Route: an active date range scopes all three sections                       #
# --------------------------------------------------------------------------- #

def test_range_scopes_summary_stats(auth_client):
    """DoD #3: start+end scope the stat tiles to expenses in [start, end]."""
    resp = auth_client.get("/profile", query_string=AUG)

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert rupees(300.00 + 400.00 + 500.00) in html          # total ₹1,200.00
    assert stat_value(3) in html                              # 3 transactions
    assert rupees(400.00) in html                             # average ₹400.00
    assert rupees(expected_month_total(**AUG)) in html        # month_total, not range-adjusted


def test_range_scopes_category_breakdown(auth_client):
    """DoD #3: start+end scope the category bars to expenses in [start, end]."""
    html = auth_client.get("/profile", query_string=AUG).get_data(as_text=True)

    assert cat_row("Food") in html
    assert cat_row("Bills") in html
    assert cat_row("Shopping") in html
    # Categories with no spend inside the window drop out entirely.
    assert cat_row("Transport") not in html
    assert cat_row("Health") not in html


def test_range_scopes_recent_transactions(auth_client):
    """DoD #3: start+end scope the transactions table to expenses in [start, end]."""
    html = auth_client.get("/profile", query_string=AUG).get_data(as_text=True)

    assert "August bills" in html       # date == start  (inclusive lower bound)
    assert "August food" in html
    assert "August shopping" in html    # date == end    (inclusive upper bound)
    assert "July transport" not in html
    assert "September health" not in html


def test_range_bounds_are_inclusive_single_day(auth_client):
    """Spec Routes: [start, end] is inclusive — a start==end day keeps that day's row."""
    html = auth_client.get(
        "/profile", query_string={"start": "2026-08-15", "end": "2026-08-15"}
    ).get_data(as_text=True)

    assert stat_value(1) in html
    assert "August food" in html
    assert "August bills" not in html
    assert "August shopping" not in html


# --------------------------------------------------------------------------- #
# Route: open-ended ranges                                                    #
# --------------------------------------------------------------------------- #

def test_open_ended_start_only(auth_client):
    """DoD #6: ?start= with no end filters as an open-ended range from that date."""
    resp = auth_client.get("/profile", query_string={"start": "2026-08-15"})

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # 08-15, 08-31, 09-05, 09-20 -> 400 + 500 + 600 + 700
    assert rupees(2200.00) in html
    assert stat_value(4) in html
    assert rupees(550.00) in html                 # average
    assert "August food" in html
    assert "August bills" not in html             # 08-01 is before the lower bound
    assert "From Aug 15, 2026" in html            # open-ended caption


def test_open_ended_end_only(auth_client):
    """DoD #6: ?end= with no start filters as an open-ended range up to that date."""
    resp = auth_client.get("/profile", query_string={"end": "2026-08-15"})

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # 06-10, 07-15, 08-01, 08-15 -> 100 + 200 + 300 + 400
    assert rupees(1000.00) in html
    assert stat_value(4) in html
    assert rupees(250.00) in html                 # average
    assert "August food" in html
    assert "August shopping" not in html          # 08-31 is after the upper bound
    assert "September food" not in html
    assert "Through Aug 15, 2026" in html         # open-ended caption


# --------------------------------------------------------------------------- #
# Route: submitted dates persist in the form                                  #
# --------------------------------------------------------------------------- #

def test_submitted_dates_are_repopulated(auth_client):
    """DoD #4: the chosen start/end values are written back into the inputs."""
    html = auth_client.get("/profile", query_string=AUG).get_data(as_text=True)

    assert 'value="2026-08-01"' in html
    assert 'value="2026-08-31"' in html


# --------------------------------------------------------------------------- #
# Route: active vs inactive filter chrome (caption + Clear link)              #
# --------------------------------------------------------------------------- #

def test_active_filter_shows_caption_and_clear_link(auth_client):
    """DoD #5: an active filter shows a human-readable range caption and Clear link."""
    html = auth_client.get("/profile", query_string=AUG).get_data(as_text=True)

    assert "profile-filter-caption" in html
    assert "Aug 01, 2026" in html
    assert "Aug 31, 2026" in html
    assert "profile-filter-clear" in html
    assert ">Clear<" in html


def test_clear_link_points_at_bare_profile(auth_client):
    """DoD #5: the Clear link returns to an unfiltered /profile (no query string)."""
    html = auth_client.get("/profile", query_string=AUG).get_data(as_text=True)

    assert '<a class="profile-filter-clear" href="/profile">' in html


def test_inactive_filter_hides_caption_and_clear_link(auth_client):
    """DoD #5 (negative): with no filter, neither caption nor Clear link appears."""
    html = auth_client.get("/profile").get_data(as_text=True)

    assert "profile-filter-caption" not in html
    assert "profile-filter-clear" not in html
    assert ">Clear<" not in html


# --------------------------------------------------------------------------- #
# Route: malformed / degenerate filter params                                #
# --------------------------------------------------------------------------- #

def test_invalid_date_param_renders_unfiltered_no_500(auth_client):
    """DoD #7: a non-date param is ignored — HTTP 200, page renders unfiltered."""
    resp = auth_client.get("/profile", query_string={"start": "banana"})

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert rupees(ALL_TIME_TOTAL) in html          # still all-time figures
    assert stat_value(ALL_TIME_COUNT) in html
    assert "profile-filter-caption" not in html    # bad bound => filter inactive
    assert "profile-filter-clear" not in html


def test_partial_invalid_param_ignores_only_the_bad_bound(auth_client):
    """Spec Routes: an invalid bound is treated as absent; the valid bound still filters."""
    resp = auth_client.get(
        "/profile", query_string={"start": "banana", "end": "2026-08-31"}
    )

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # end applies (<= 08-31): 100 + 200 + 300 + 400 + 500
    assert rupees(1500.00) in html
    assert stat_value(5) in html
    assert "Through Aug 31, 2026" in html          # active, open-ended on end
    assert 'value="2026-08-31"' in html
    assert 'value=""' in html                      # start input rendered empty


def test_start_after_end_yields_empty_state_no_error(auth_client):
    """DoD #8: start later than end renders empty sections with the existing message."""
    resp = auth_client.get(
        "/profile", query_string={"start": "2026-12-01", "end": "2026-01-01"}
    )

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "No expenses recorded yet." in html      # reused .profile-empty message
    assert html.count("No expenses recorded yet.") >= 2  # category + history sections
    assert rupees(0.0) in html                      # total ₹0.00
    assert stat_value(0) in html                    # 0 transactions
    assert "June food" not in html
    assert "profile-filter-caption" in html         # filter is still "active"


# --------------------------------------------------------------------------- #
# Route: auth guard                                                          #
# --------------------------------------------------------------------------- #

def test_profile_requires_login_without_params(client):
    """Auth guard: logged-out GET /profile redirects to /login."""
    resp = client.get("/profile")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_requires_login_with_filter_params(client):
    """Auth guard: the redirect also applies when filter params are supplied."""
    resp = client.get("/profile", query_string=AUG)

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# --------------------------------------------------------------------------- #
# DB helpers: get_summary_stats(user_id, start=None, end=None)                #
# --------------------------------------------------------------------------- #

def test_summary_stats_no_kwargs_unchanged(seeded_db):
    """DB: called without start/end, get_summary_stats behaves exactly as before."""
    stats = seeded_db.get_summary_stats(USER_ID)

    assert stats["total"] == pytest.approx(ALL_TIME_TOTAL)
    assert stats["txn_count"] == ALL_TIME_COUNT
    assert stats["avg_amount"] == pytest.approx(ALL_TIME_AVG)
    assert stats["month_total"] == pytest.approx(expected_month_total())


def test_summary_stats_with_range(seeded_db):
    """DB: start/end scope total, count and average to expenses in [start, end]."""
    stats = seeded_db.get_summary_stats(USER_ID, start="2026-08-01", end="2026-08-31")

    assert stats["total"] == pytest.approx(1200.00)
    assert stats["txn_count"] == 3
    assert stats["avg_amount"] == pytest.approx(400.00)


def test_summary_stats_month_total_not_range_adjusted(seeded_db):
    """DB: month_total keeps meaning 'current calendar month', not 'range total'."""
    full = seeded_db.get_summary_stats(USER_ID, start="2026-01-01", end="2026-12-31")

    assert full["total"] == pytest.approx(ALL_TIME_TOTAL)
    # month_total is the current-month subset of the seed data, never the range sum.
    assert full["month_total"] == pytest.approx(expected_month_total("2026-01-01", "2026-12-31"))
    assert full["month_total"] != pytest.approx(full["total"])


def test_summary_stats_empty_range_no_divide_by_zero(seeded_db):
    """DB: an out-of-data range returns zeroed figures (COALESCE), not an error."""
    stats = seeded_db.get_summary_stats(USER_ID, start="2100-01-01")

    assert stats["total"] == 0
    assert stats["txn_count"] == 0
    assert stats["avg_amount"] == 0
    assert stats["month_total"] == 0


# --------------------------------------------------------------------------- #
# DB helpers: get_category_breakdown(user_id, start=None, end=None)           #
# --------------------------------------------------------------------------- #

def test_category_breakdown_no_kwargs_unchanged(seeded_db):
    """DB: without start/end, breakdown covers every category with spend."""
    breakdown = seeded_db.get_category_breakdown(USER_ID)

    assert [row["category"] for row in breakdown] == [
        "Food", "Transport", "Bills", "Health", "Shopping",
    ]
    totals = {row["category"]: row["total"] for row in breakdown}
    assert totals["Food"] == pytest.approx(1200.00)     # 100 + 400 + 700
    assert totals["Transport"] == pytest.approx(200.00)
    assert totals["Health"] == pytest.approx(600.00)


def test_category_breakdown_with_range(seeded_db):
    """DB: start/end scope the per-category totals to expenses in [start, end]."""
    breakdown = seeded_db.get_category_breakdown(
        USER_ID, start="2026-08-01", end="2026-08-31"
    )

    assert [row["category"] for row in breakdown] == ["Food", "Bills", "Shopping"]
    totals = {row["category"]: row["total"] for row in breakdown}
    assert totals["Food"] == pytest.approx(400.00)
    assert totals["Bills"] == pytest.approx(300.00)
    assert totals["Shopping"] == pytest.approx(500.00)


def test_category_breakdown_empty_range_returns_empty_list(seeded_db):
    """DB: no rows in range -> [] (existing empty behaviour, no new guard needed)."""
    assert seeded_db.get_category_breakdown(
        USER_ID, start="2026-12-01", end="2026-01-01"
    ) == []


# --------------------------------------------------------------------------- #
# DB helpers: get_recent_transactions(user_id, limit=10, start=None, end=None)#
# --------------------------------------------------------------------------- #

def test_recent_transactions_no_kwargs_unchanged(seeded_db):
    """DB: without start/end, returns every expense newest-first (ORDER BY unchanged)."""
    txns = seeded_db.get_recent_transactions(USER_ID)

    assert [t["description"] for t in txns] == [
        "September food", "September health", "August shopping",
        "August food", "August bills", "July transport", "June food",
    ]


def test_recent_transactions_with_range(seeded_db):
    """DB: start/end restrict the rows to expenses in [start, end], still newest-first."""
    txns = seeded_db.get_recent_transactions(
        USER_ID, start="2026-08-01", end="2026-08-31"
    )

    assert [t["description"] for t in txns] == [
        "August shopping", "August food", "August bills",
    ]


def test_recent_transactions_open_ended_start(seeded_db):
    """DB: start alone gives an open-ended lower-bound filter."""
    txns = seeded_db.get_recent_transactions(USER_ID, start="2026-08-15")

    assert [t["description"] for t in txns] == [
        "September food", "September health", "August shopping", "August food",
    ]


def test_recent_transactions_open_ended_end(seeded_db):
    """DB: end alone gives an open-ended upper-bound filter."""
    txns = seeded_db.get_recent_transactions(USER_ID, end="2026-08-15")

    assert [t["description"] for t in txns] == [
        "August food", "August bills", "July transport", "June food",
    ]


def test_recent_transactions_limit_still_applies_with_range(seeded_db):
    """DB: the existing LIMIT clause is untouched by the new date clauses."""
    assert len(seeded_db.get_recent_transactions(USER_ID, limit=2)) == 2
    assert len(
        seeded_db.get_recent_transactions(
            USER_ID, limit=2, start="2026-01-01", end="2026-12-31"
        )
    ) == 2


def test_recent_transactions_start_after_end_is_empty(seeded_db):
    """DB: start later than end simply yields no rows (no error)."""
    assert seeded_db.get_recent_transactions(
        USER_ID, start="2026-12-01", end="2026-01-01"
    ) == []
