import os
from datetime import date

from flask import Flask, flash, redirect, render_template, request, url_for

from database.db import create_user, get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.urandom(24)


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


@app.route("/login")
def login():
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
    with app.app_context():
        init_db()
        seed_db()

    app.run(debug=True, port=5001)
