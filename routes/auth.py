"""
Authentication Routes
"""

from flask import Blueprint, request, redirect, url_for, flash, render_template
from services.auth_service import auth_service
from utils.helpers import wrap

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if auth_service.is_authenticated():
            return redirect(url_for("main.dashboard"))

        next_url = request.args.get("next", "")

        return render_template("auth/login.html", next_url=next_url)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    nxt = request.form.get("next", "")

    if not email or not password:
        return wrap("<div class='card'><h3>Sähköposti ja salasana vaaditaan</h3></div>", auth_service.get_current_user())

    # Use auth service for login
    success, _, error = auth_service.login(email, password)

    if not success:
        return wrap(f"<div class='card'><h3>{error}</h3></div>", auth_service.get_current_user())

    return redirect(nxt or "/dashboard")


@auth_bp.route("/logout")
def logout():
    auth_service.logout()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if auth_service.is_authenticated():
            return redirect(url_for("main.dashboard"))

        return render_template("auth/register.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()

    success, user, error = auth_service.register(email, password, name)

    if not success:
        flash(error, "error")
        return redirect(url_for("auth.register"))

    flash("Rekisteröinti onnistui! Odota admin hyväksyntää.", "success")
    return redirect(url_for("auth.login"))