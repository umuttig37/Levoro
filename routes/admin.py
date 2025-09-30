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

    return render_template("admin/users.html", users=users, current_user=auth_service.get_current_user())


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
                         available_orders=available_orders,
                         current_user=auth_service.get_current_user())


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

    return render_template("admin/driver_applications.html", applications=applications, current_user=auth_service.get_current_user())


@admin_bp.route("/driver-applications/<int:application_id>")
@admin_required
def driver_application_detail(application_id):
    """View driver application details"""
    from models.driver_application import driver_application_model

    application = driver_application_model.find_by_id(application_id)

    if not application:
        flash("Hakemusta ei löytynyt", "error")
        return redirect(url_for("admin.driver_applications"))

    return render_template("admin/driver_application_detail.html",
                         application=application,
                         current_user=auth_service.get_current_user())


@admin_bp.route("/driver-applications/approve", methods=["POST"])
@admin_required
def approve_driver_application():
    """Approve driver application and create driver account"""
    from models.driver_application import driver_application_model
    from services.driver_service import driver_service

    application_id = int(request.form.get("application_id"))

    # Get application details
    app = driver_application_model.find_by_id(application_id)
    if not app or app.get('status') != 'pending':
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
    from models.driver_application import driver_application_model

    application_id = int(request.form.get("application_id"))

    # Get current user for logging
    user = auth_service.get_current_user()

    # Get application details
    app = driver_application_model.find_by_id(application_id)
    if not app or app.get('status') != 'pending':
        flash("Hakemusta ei löytynyt tai se on jo käsitelty", "error")
        return redirect(url_for("admin.driver_applications"))

    # Mark application as denied
    driver_application_model.deny_application(application_id, user["id"])

    flash(f"Hakemus hylätty: {app['name']}", "warning")
    return redirect(url_for("admin.driver_applications"))


@admin_bp.route("/update", methods=["POST"])
@admin_required
def update_order():
    """Update order status"""
    order_id = int(request.form.get("id"))
    new_status = request.form.get("status")

    # Validate status
    from models.order import order_model
    if new_status not in order_model.VALID_STATUSES:
        return redirect(url_for("main.admin_dashboard"))

    # Use service layer to update order status (includes automatic email sending)
    success, error = order_service.update_order_status(order_id, new_status)

    # Add debug feedback
    if success:
        from app import translate_status
        flash(f"Tilauksen #{order_id} tila päivitetty: {translate_status(new_status)}", "success")
    else:
        flash(f"Virhe: {error or f'Tilauksen #{order_id} tilaa ei voitu päivittää'}", "error")

    return redirect(url_for("main.admin_dashboard"))


@admin_bp.route("/order/<int:order_id>")
@admin_required
def order_detail(order_id):
    """Admin order detail view"""
    from app import orders_col, translate_status

    # Get order with user AND driver info
    pipeline = [
        {"$match": {"id": int(order_id)}},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "id",
            "as": "user"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "driver_id",
            "foreignField": "id",
            "as": "driver"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$driver", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "id": 1, "status": 1, "driver_id": 1,
            "pickup_address": 1, "dropoff_address": 1,
            "distance_km": 1, "price_gross": 1,
            "reg_number": 1, "winter_tires": 1, "pickup_date": 1,
            "extras": 1, "images": 1,
            "user_name": "$user.name",
            "user_email": "$user.email",
            "driver_name": "$driver.name",
            "driver_phone": "$driver.phone"
        }}
    ]
    order_result = list(orders_col().aggregate(pipeline))

    if not order_result:
        flash("Tilaus ei löytynyt", "error")
        return redirect(url_for("main.admin_dashboard"))

    order = order_result[0]
    status_fi = translate_status(order.get('status', 'NEW'))

    # Get available drivers for assignment dropdown
    from models.user import user_model
    available_drivers = user_model.get_all_drivers(limit=100)

    # Format pickup date
    pickup_date_fi = order.get('pickup_date', 'Ei asetettu')
    if pickup_date_fi and pickup_date_fi != 'Ei asetettu':
        try:
            # Try to format the date if it's a datetime object
            if hasattr(pickup_date_fi, 'strftime'):
                pickup_date_fi = pickup_date_fi.strftime('%d.%m.%Y')
        except:
            pass

    # Get current user for navbar
    user = auth_service.get_current_user()

    return render_template('admin/order_detail.html',
        order=order,
        status_fi=status_fi,
        pickup_date_fi=pickup_date_fi,
        available_drivers=available_drivers,
        current_user=user
    )


@admin_bp.route("/order/<int:order_id>/upload", methods=["POST"])
@admin_required
def upload_order_image(order_id):
    """Upload image to order"""
    image_type = request.form.get("image_type")
    if image_type not in ["pickup", "delivery"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    if 'image' not in request.files:
        flash("Kuvaa ei valittu", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    file = request.files['image']
    if file.filename == '':
        flash("Kuvaa ei valittu", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    # Save and process image using ImageService
    from utils.helpers import current_user
    u = current_user()
    image_info, error = image_service.save_order_image(file, order_id, image_type, u.get("email", "admin"))

    if error:
        flash(error, "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    # Add image to order using ImageService
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        flash(add_error, "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    image_type_fi = "Nouto" if image_type == "pickup" else "Toimitus"
    flash(f"{image_type_fi} kuva ladattu onnistuneesti", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/order/<int:order_id>/image/<image_type>/delete", methods=["POST"])
@admin_required
def delete_order_image(order_id, image_type):
    """Delete order image"""
    if image_type not in ["pickup", "delivery"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    success, message = image_service.delete_order_image(order_id, image_type, request.form.get('image_id'))

    image_type_fi = "Nouto" if image_type == "pickup" else "Toimitus"

    if success:
        flash(f"{image_type_fi} kuva poistettu onnistuneesti", "success")
    else:
        # Translate error messages
        finnish_message = message
        if "Order or image not found" in message:
            finnish_message = "Tilausta tai kuvaa ei löytynyt"
        elif "Image not found" in message:
            finnish_message = "Kuvaa ei löytynyt"
        elif "Delete failed" in message:
            finnish_message = "Poisto epäonnistui"

        flash(finnish_message, "error")

    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/order/<int:order_id>/image/<image_type>/<image_id>/delete", methods=["POST"])
@admin_required
def delete_order_image_by_id(order_id, image_type, image_id):
    """Delete specific order image by ID"""
    if image_type not in ["pickup", "delivery"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    success, message = image_service.delete_order_image(order_id, image_type, image_id)

    image_type_fi = "Nouto" if image_type == "pickup" else "Toimitus"

    if success:
        flash(f"{image_type_fi} kuva poistettu onnistuneesti", "success")
    else:
        # Translate error messages
        finnish_message = message
        if "Order or image not found" in message:
            finnish_message = "Tilausta tai kuvaa ei löytynyt"
        elif "Image not found" in message:
            finnish_message = "Kuvaa ei löytynyt"
        elif "Delete failed" in message:
            finnish_message = "Poisto epäonnistui"

        flash(finnish_message, "error")

    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/order/<int:order_id>/assign_driver", methods=["POST"])
@admin_required
def assign_driver_to_order(order_id):
    """Assign or change driver for an order"""
    driver_id = request.form.get("driver_id")

    if not driver_id:
        flash("Valitse kuljettaja", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    success, error = order_service.assign_driver_to_order(order_id, int(driver_id))

    if success:
        flash("Kuljettaja määritetty onnistuneesti", "success")
    else:
        flash(f"Virhe: {error}", "error")

    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/order/<int:order_id>/confirm", methods=["POST"])
@admin_required
def confirm_order(order_id):
    """Confirm order - changes status from NEW to CONFIRMED"""
    from models.order import order_model

    order = order_model.find_by_id(order_id)
    if not order:
        flash("Tilausta ei löytynyt", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    if order['status'] != 'NEW':
        flash("Tilaus on jo vahvistettu", "warning")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    # Update to CONFIRMED status (will trigger email notification automatically)
    success, error = order_service.update_order_status(order_id, 'CONFIRMED')

    if success:
        flash("Tilaus vahvistettu! Asiakas on saanut vahvistusviestin ja tilaus on nyt kuljettajien saatavilla.", "success")
    else:
        flash(f"Virhe: {error}", "error")

    return redirect(url_for("admin.order_detail", order_id=order_id))