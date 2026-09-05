import math
import os
from datetime import date, datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from database.db import (
    CATEGORIES,
    authenticate_user,
    create_expense,
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

@app.template_filter("currency")
def format_currency(value):
    """Format a number as a rupee currency string, e.g. 1234.5 -> '₹1,234.50'."""
    return f"₹{value:,.2f}"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

ISO_DATE = "%Y-%m-%d"

# Upper bound for a single expense amount (exclusive) and the max length of a
# free-text description. Kept here as the single source of truth — the add
# form's maxlength attribute mirrors MAX_DESCRIPTION_LEN.
MAX_EXPENSE_AMOUNT = 10_000_000
MAX_DESCRIPTION_LEN = 200


def _parse_iso_date(value):
    """Parse a user-supplied YYYY-MM-DD string into a datetime, or None if absent
    or invalid.

    <input type="date"> always submits a zero-padded YYYY-MM-DD; this also
    tolerates loosely padded values (e.g. '2026-1-1') from hand-crafted query
    strings. strptime still rejects impossible dates and trailing junk.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, ISO_DATE)
    except ValueError:
        return None


def _parse_expense_form(form):
    """Validate the shared add/edit expense form fields.

    Returns (raw, fields, error). `raw` is always a dict of the four stripped
    submitted strings (`amount`, `category`, `date`, `description`) for sticky
    re-rendering. On success `error` is None and `fields` is a dict with the
    cleaned `amount` (float, 2 decimals), `category`, `date` (ISO string) and
    `description` (str or None). On failure `fields` is None and `error` is a
    single message string. Does no rendering and no DB work — parsing only.
    """
    raw = {
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", "").strip(),
        "description": form.get("description", "").strip(),
    }

    try:
        amount = round(float(raw["amount"]), 2)
    except ValueError:
        return raw, None, "Enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:
        return raw, None, "Amount must be greater than zero."
    if amount >= MAX_EXPENSE_AMOUNT:
        return raw, None, f"Amount must be less than ₹{MAX_EXPENSE_AMOUNT:,}."

    if raw["category"] not in CATEGORIES:
        return raw, None, "Choose a valid category."

    expense_date = _parse_iso_date(raw["date"])
    if expense_date is None:
        return raw, None, "Enter a valid date."

    if len(raw["description"]) > MAX_DESCRIPTION_LEN:
        return raw, None, f"Description must be {MAX_DESCRIPTION_LEN} characters or fewer."

    return raw, {
        "amount": amount,
        "category": raw["category"],
        "date": expense_date.strftime(ISO_DATE),
        "description": raw["description"] or None,
    }, None


def _format_filter_label(start, end):
    """Human-readable range caption from datetimes already validated by
    _parse_iso_date. Assumes at least one bound is non-None."""
    start_h = start.strftime("%b %d, %Y") if start else None
    end_h = end.strftime("%b %d, %Y") if end else None
    if start_h and end_h:
        return f"{start_h} to {end_h}"
    if start_h:
        return f"From {start_h}"
    return f"Through {end_h}"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html", last_updated=date.today().strftime("%B %d, %Y"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", last_updated=date.today().strftime("%B %d, %Y"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required", name=name, email=email)

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters", name=name, email=email)

    user_id = create_user(name, email, password)
    if user_id is None:
        return render_template("register.html", error="Email already registered", name=name, email=email)

    flash("Registration successful — please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Email and password are required", email=email)

    user = authenticate_user(email, password)
    if user is None:
        return render_template("login.html", error="Invalid email or password", email=email)

    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.")
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    member_since = datetime.strptime(user["created_at"][:10], "%Y-%m-%d").strftime("%B %d, %Y")

    # --- Date filter (Step 06) ---
    start = _parse_iso_date(request.args.get("start"))
    end = _parse_iso_date(request.args.get("end"))
    filter_active = start is not None or end is not None
    invalid_range = start is not None and end is not None and start > end
    filter_label = _format_filter_label(start, end) if filter_active else None
    start_iso = start.strftime(ISO_DATE) if start else None
    end_iso = end.strftime(ISO_DATE) if end else None

    # --- Transaction history (Step 05: transaction history) ---
    transactions = get_recent_transactions(user_id, start=start_iso, end=end_iso)

    # --- Summary stats (Step 05: summary stats) ---
    stats = get_summary_stats(user_id, start=start_iso, end=end_iso)

    # --- Category breakdown (Step 05: category breakdown) ---
    category_breakdown = get_category_breakdown(user_id, start=start_iso, end=end_iso)

    return render_template(
        "profile.html",
        user=user,
        member_since=member_since,
        transactions=transactions,
        stats=stats,
        category_breakdown=category_breakdown,
        start_iso=start_iso,
        end_iso=end_iso,
        filter_active=filter_active,
        invalid_range=invalid_range,
        filter_label=filter_label,
    )


@app.route("/analytics")
def analytics():
    # Static replica of the Figma "spendly_analytics" design. Sample figures
    # live in the template; no data is fetched yet.
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    today = date.today().strftime(ISO_DATE)

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            max_description_len=MAX_DESCRIPTION_LEN,
        )

    raw, fields, error = _parse_expense_form(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            max_description_len=MAX_DESCRIPTION_LEN,
            error=error,
            amount=raw["amount"],
            category=raw["category"],
            date=raw["date"],
            description=raw["description"],
        )

    create_expense(
        user_id, fields["amount"], fields["category"], fields["date"], fields["description"]
    )
    flash("Expense added.")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=CATEGORIES,
            max_description_len=MAX_DESCRIPTION_LEN,
            amount=None,
            category=None,
            date=None,
            description=None,
        )

    raw, fields, error = _parse_expense_form(request.form)
    if error:
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=CATEGORIES,
            max_description_len=MAX_DESCRIPTION_LEN,
            error=error,
            amount=raw["amount"],
            category=raw["category"],
            date=raw["date"],
            description=raw["description"],
        )

    update_expense(
        id, user_id, fields["amount"], fields["category"], fields["date"], fields["description"]
    )
    flash("Expense updated.")
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()

    app.run(debug=True, port=5001)
