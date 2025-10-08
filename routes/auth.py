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


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request password reset"""
    if request.method == "GET":
        if auth_service.is_authenticated():
            return redirect(url_for("main.dashboard"))
        
        return render_template("auth/forgot_password.html")
    
    email = request.form.get("email", "").strip().lower()
    
    if not email:
        flash("Sähköposti vaaditaan", "error")
        return redirect(url_for("auth.forgot_password"))
    
    # Request password reset
    success, error = auth_service.request_password_reset(email)
    
    # Always show success message for security (don't reveal if email exists)
    flash("Jos sähköpostiosoite on rekisteröity, saat pian ohjeet salasanan vaihtoon.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset password with token"""
    if request.method == "GET":
        if auth_service.is_authenticated():
            return redirect(url_for("main.dashboard"))
        
        # Validate token
        valid, user, error = auth_service.validate_reset_token(token)
        
        if not valid:
            flash(error, "error")
            return redirect(url_for("auth.forgot_password"))
        
        return render_template("auth/reset_password.html", token=token, user=user)
    
    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    
    if not new_password or not confirm_password:
        flash("Molemmat salasanakentät vaaditaan", "error")
        return redirect(url_for("auth.reset_password", token=token))
    
    if new_password != confirm_password:
        flash("Salasanat eivät täsmää", "error")
        return redirect(url_for("auth.reset_password", token=token))
    
    # Reset password
    success, error = auth_service.reset_password(token, new_password)
    
    if not success:
        flash(error, "error")
        return redirect(url_for("auth.reset_password", token=token))
    
    flash("Salasana vaihdettu onnistuneesti! Voit nyt kirjautua sisään.", "success")
    return redirect(url_for("auth.login"))