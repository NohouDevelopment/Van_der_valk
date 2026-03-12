"""
Auth Blueprint — login, logout routes.
"""

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from models import Gebruiker

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None
    email = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        wachtwoord = request.form.get("wachtwoord", "")

        gebruiker = Gebruiker.query.filter_by(email=email).first()

        if gebruiker and gebruiker.check_wachtwoord(wachtwoord):
            login_user(gebruiker, remember=True)
            next_page = request.args.get("next")
            if next_page and (not next_page.startswith("/") or next_page.startswith("//")):
                next_page = None
            return redirect(next_page or url_for("dashboard"))
        else:
            error = "E-mailadres of wachtwoord klopt niet."

    return render_template("login.html", error=error, email=email)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
