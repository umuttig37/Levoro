"""
Authentication Routes
"""

from flask import Blueprint, request, redirect, url_for, flash, render_template
from services.auth_service import auth_service

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
        flash("Sähköposti ja salasana vaaditaan", "error")
        return redirect(url_for("auth.login"))

    # Use auth service for login
    success, _, error = auth_service.login(email, password)

    if not success:
        flash(error, "error")
        return redirect(url_for("auth.login"))

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
    phone = request.form.get("phone", "").strip()

    success, user, error = auth_service.register(email, password, name, phone)

    if not success:
        flash(error, "error")
        return redirect(url_for("auth.register"))

    flash("Rekisteröinti onnistui! Odota admin hyväksyntää.", "success")
    return redirect(url_for("auth.login"))