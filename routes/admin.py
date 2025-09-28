"""
Admin Routes for user and system management
"""

from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from services.auth_service import auth_service
from services.order_service import order_service
from services.image_service import image_service
from utils.helpers import login_required, admin_required
from utils.formatters import format_helsinki_time

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route("/")
@admin_required
def dashboard():
    """Admin dashboard - redirects to main admin dashboard"""
    return redirect(url_for("main.admin_dashboard"))


@admin_bp.route("/users")
@admin_required
def users():
    """Admin user management page"""
    from app import users_col

    # Get all users sorted by creation date (newest first)
    users = list(users_col().find({}, {"_id": 0}).sort("created_at", -1))

    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/approve", methods=["POST"])
@admin_required
def approve_user():
    """Approve a pending user"""
    from app import users_col

    user_id = int(request.form.get("user_id"))

    # Update user status to active
    result = users_col().update_one(
        {"id": user_id},
        {"$set": {"status": "active"}}
    )

    if result.modified_count > 0:
        flash("Käyttäjä hyväksytty onnistuneesti", "success")
    else:
        flash("Käyttäjän hyväksyminen epäonnistui", "error")

    return redirect(url_for("admin.users"))


@admin_bp.route("/users/deny", methods=["POST"])
@admin_required
def deny_user():
    """Deny/delete a user"""
    from app import users_col

    user_id = int(request.form.get("user_id"))

    # Delete the user completely
    result = users_col().delete_one({"id": user_id})

    if result.deleted_count > 0:
        flash("Käyttäjä poistettu onnistuneesti", "success")
    else:
        flash("Käyttäjän poistaminen epäonnistui", "error")

    return redirect(url_for("admin.users"))
@admin_bp.route("/drivers")
@admin_required
def drivers():
    """Admin driver management page"""
    # Get all drivers with their performance data
    from services.driver_service import driver_service
    from models.order import order_model

    drivers_performance = driver_service.get_driver_performance_data()

    # Get available orders that can be assigned
    available_orders = order_model.get_available_orders(limit=20)

    return render_template("admin/drivers.html",
                         drivers_performance=drivers_performance,
                         available_orders=available_orders)


@admin_bp.route("/assign_driver", methods=["POST"])
@admin_required
def assign_driver():
    """Assign a driver to an order"""
    order_id = int(request.form.get("order_id"))
    driver_id = int(request.form.get("driver_id"))

    if not order_id or not driver_id:
        flash("Tilaus ID ja kuljettaja ID vaaditaan", "error")
        return redirect(url_for("admin.drivers"))

    # Use order service to assign driver
    success, error = order_service.assign_driver_to_order(order_id, driver_id)

    if success:
        flash(f"Kuljettaja määritetty tilaukselle #{order_id} onnistuneesti", "success")
    else:
        flash(f"Virhe kuljettajan määrityksessä: {error}", "error")

    return redirect(url_for("admin.drivers"))
@admin_bp.route("/driver-applications")
@admin_required
def driver_applications():
    """Admin interface for managing driver applications"""
    from models.driver_application import driver_application_model

    # Get all applications
    applications = list(driver_application_model.get_all_applications(limit=100))

    return render_template("admin/driver_applications.html", applications=applications)


@admin_bp.route("/driver-applications/approve", methods=["POST"])
@admin_required
def approve_driver_application():
    """Approve driver application and create driver account"""
    from app import driver_applications_col
    from services.driver_service import driver_service

    application_id = int(request.form.get("application_id"))

    # Get application details
    app = driver_applications_col().find_one({"id": application_id, "status": "pending"}, {"_id": 0})
    if not app:
        flash("Hakemusta ei löytynyt tai se on jo käsitelty", "error")
        return redirect(url_for("admin.driver_applications"))

    # Create driver user account and approve application
    success, error = driver_service.approve_driver_application(application_id)

    if success:
        flash(f"Kuljettajahakemus hyväksytty: {app['name']}", "success")
    else:
        flash(f"Virhe hakemuksen hyväksynnässä: {error}", "error")

    return redirect(url_for("admin.driver_applications"))


@admin_bp.route("/driver-applications/deny", methods=["POST"])
@admin_required
def deny_driver_application():
    """Deny driver application"""
    from app import driver_applications_col
    from models.driver_application import driver_application_model
    from utils.helpers import current_user

    application_id = int(request.form.get("application_id"))
    u = current_user()

    # Get application details
    app = driver_applications_col().find_one({"id": application_id, "status": "pending"}, {"_id": 0})
    if not app:
        flash("Hakemusta ei löytynyt tai se on jo käsitelty", "error")
        return redirect(url_for("admin.driver_applications"))

    # Mark application as denied
    driver_application_model.deny_application(application_id, u["id"])

    flash(f"Hakemus hylätty: {app['name']}", "warning")
    return redirect(url_for("admin.driver_applications"))


# Order management routes will be added here