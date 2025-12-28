"""
Main Application Routes
"""

import os
from flask import Blueprint, request, redirect, url_for, flash, jsonify, render_template
from services.auth_service import auth_service
from services.order_service import order_service
from services.image_service import image_service
from utils.helpers import wrap, login_required, admin_required
from utils.formatters import format_helsinki_time

main_bp = Blueprint('main', __name__)

# Get Google Places API key from environment
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")


@main_bp.route("/")
def index():
    """Home page - marketing content for visitors"""
    user = auth_service.get_current_user()
    return render_template("home.html", current_user=user, google_places_api_key=GOOGLE_PLACES_API_KEY)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard - show user's orders"""
    user = auth_service.get_current_user()

    if user.get('role') == 'driver':
        return redirect(url_for("driver.dashboard"))

    if auth_service.is_admin(user):
        return redirect(url_for("main.admin_dashboard"))

    # Get all user's orders - client-side will handle filtering
    all_orders = order_service.get_user_orders(user["id"])

    return render_template("dashboard/user_dashboard.html", all_orders=all_orders, orders=all_orders, current_user=user)


@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard - show all orders with driver info"""
    from flask import session
    from datetime import datetime, timezone
    
    # Mark orders as viewed (update session timestamp)
    session['admin_last_viewed_orders'] = datetime.now(timezone.utc)
    
    # Get filter parameters
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    date_filter = request.args.get('date_filter', '30days')
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    # Validate page number
    if page < 1:
        page = 1
    
    # Get orders with filtering and pagination
    from models.order import order_model
    orders, total_orders = order_model.get_orders_with_driver_info_paginated(
        search=search if search else None,
        status=status if status else None,
        date_filter=date_filter if date_filter else None,
        page=page,
        per_page=per_page
    )
    
    # Calculate pagination info
    total_pages = (total_orders + per_page - 1) // per_page if total_orders > 0 else 1
    start_order = (page - 1) * per_page + 1 if total_orders > 0 else 0
    end_order = min(page * per_page, total_orders)
    
    user = auth_service.get_current_user()
    return render_template(
        "admin/dashboard.html", 
        orders=orders, 
        current_user=user,
        # Pagination context
        total_orders=total_orders,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        start_order=start_order,
        end_order=end_order,
        # Filter context
        search=search,
        status=status,
        date_filter=date_filter
    )