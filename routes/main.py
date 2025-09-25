"""
Main Application Routes
"""

from flask import Blueprint, request, redirect, url_for, flash, jsonify, render_template
from services.auth_service import auth_service
from services.order_service import order_service
from services.image_service import image_service
from utils.helpers import wrap, login_required, admin_required
from utils.formatters import format_helsinki_time

main_bp = Blueprint('main', __name__)


@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard - show user's orders"""
    user = auth_service.get_current_user()

    if auth_service.is_admin(user):
        return redirect(url_for("main.admin_dashboard"))

    # Get user's orders
    orders = order_service.get_user_orders(user["id"])

    return render_template("dashboard/user_dashboard.html", orders=orders)


@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    orders = order_service.get_all_orders()
    pending_users = auth_service.get_pending_users()

    return render_template("admin/dashboard.html", orders=orders, pending_users=pending_users)