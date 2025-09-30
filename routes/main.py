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
    """Home page - marketing content for visitors"""
    user = auth_service.get_current_user()
    return render_template("home.html", current_user=user)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard - show user's orders"""
    user = auth_service.get_current_user()

    if user.get('role') == 'driver':
        return redirect(url_for("driver.dashboard"))

    if auth_service.is_admin(user):
        return redirect(url_for("main.admin_dashboard"))

    # Get tab parameter for filtering
    tab = (request.args.get("tab", "active") or "active").lower()

    # Get user's orders
    all_orders = order_service.get_user_orders(user["id"])

    # Filter orders based on tab (active vs completed)
    def is_active_status(status):
        return status in {"NEW", "CONFIRMED", "ASSIGNED_TO_DRIVER", "DRIVER_ARRIVED",
                         "PICKUP_IMAGES_ADDED", "IN_TRANSIT", "DELIVERY_ARRIVED",
                         "DELIVERY_IMAGES_ADDED"}

    if tab == "completed":
        orders = [order for order in all_orders if not is_active_status(order.get("status", "NEW"))]
    else:
        orders = [order for order in all_orders if is_active_status(order.get("status", "NEW"))]

    return render_template("dashboard/user_dashboard.html", orders=orders, current_user=user)


@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard - show all orders with driver info"""
    # Get orders with driver information (like in the legacy route)
    from models.order import order_model
    orders = order_model.get_orders_with_driver_info(300)

    user = auth_service.get_current_user()
    return render_template("admin/dashboard.html", orders=orders, current_user=user)