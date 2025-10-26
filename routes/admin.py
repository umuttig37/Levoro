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

    # Get all users EXCEPT drivers (drivers are managed separately)
    users = list(users_col().find({"role": {"$ne": "driver"}}, {"_id": 0}).sort("created_at", -1))

    return render_template("admin/users.html", users=users, current_user=auth_service.get_current_user())


@admin_bp.route("/users/approve", methods=["POST"])
@admin_required
def approve_user():
    """Approve a pending user"""
    from app import users_col
    from models.user import user_model

    user_id = int(request.form.get("user_id"))

    # SAFETY: Prevent approving drivers from users page
    user = user_model.find_by_id(user_id)
    if user and user.get('role') == 'driver':
        flash("Kuljettajia ei voi hyväksyä täältä. Käytä Kuljettajahakemukset-sivua.", "error")
        return redirect(url_for("admin.users"))

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
    """Deny/delete a user with comprehensive cleanup"""
    from app import users_col
    from models.user import user_model
    from models.driver_application import driver_application_model

    user_id = int(request.form.get("user_id"))

    # Get user details before deletion (to find corresponding application)
    user = user_model.find_by_id(user_id)

    if not user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))

    # SAFETY: Prevent deleting drivers from users page
    if user.get('role') == 'driver':
        flash("Kuljettajia ei voi poistaa täältä. Käytä Kuljettajat-sivua.", "error")
        return redirect(url_for("admin.users"))

    user_email = user.get('email')
    user_role = user.get('role')
    deletion_successful = True
    app_deletion_successful = True

    # If this is a driver, delete their driver application record first
    if user_role == 'driver' and user_email:
        try:
            driver_app = driver_application_model.find_by_email(user_email)
            if driver_app:
                result = driver_application_model.delete_one({"id": driver_app['id']})
                if not result:
                    app_deletion_successful = False
                    print(f"Warning: Failed to delete driver application for {user_email}")
            else:
                print(f"Info: No driver application found for {user_email} (this is OK)")
        except Exception as e:
            app_deletion_successful = False
            print(f"Error deleting driver application for {user_email}: {str(e)}")

    # Delete the user from users collection
    try:
        result = users_col().delete_one({"id": user_id})
        if result.deleted_count == 0:
            deletion_successful = False
    except Exception as e:
        deletion_successful = False
        print(f"Error deleting user {user_id}: {str(e)}")

    # Provide appropriate feedback
    if deletion_successful and app_deletion_successful:
        flash("Käyttäjä ja siihen liittyvät tiedot poistettu onnistuneesti", "success")
    elif deletion_successful and not app_deletion_successful:
        flash("Käyttäjä poistettu, mutta kuljettajahakemuksen poisto epäonnistui. Ota yhteyttä ylläpitäjään.", "warning")
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


@admin_bp.route("/drivers/<int:driver_id>/delete", methods=["POST"])
@admin_required
def delete_driver(driver_id):
    """Delete a driver user account (preserves orders and driver applications)"""
    from app import users_col
    from models.user import user_model
    from models.order import order_model

    # Get driver details before deletion
    driver = user_model.find_by_id(driver_id)

    if not driver:
        flash("Kuljettajaa ei löytynyt", "error")
        return redirect(url_for("admin.drivers"))

    # SAFETY: Ensure this is actually a driver
    if driver.get('role') != 'driver':
        flash("Tämä käyttäjä ei ole kuljettaja", "error")
        return redirect(url_for("admin.drivers"))

    driver_name = driver.get('name', 'Tuntematon')

    # Check if driver has active orders assigned
    active_orders = order_model.find(
        {"driver_id": driver_id, "status": {"$nin": ["DELIVERED", "CANCELLED"]}},
        limit=1
    )

    if active_orders:
        flash(f"Virhe: Kuljettajalla {driver_name} on aktiivisia tilauksia. Poista ensin tilausten määritykset tai merkitse ne valmiiksi.", "error")
        return redirect(url_for("admin.drivers"))

    # NOTE: Orders and driver applications are preserved for record keeping
    # Only the driver user account is deleted

    # Delete the driver user account
    deletion_successful = True
    try:
        result = users_col().delete_one({"id": driver_id})
        if result.deleted_count == 0:
            deletion_successful = False
    except Exception as e:
        deletion_successful = False
        print(f"Error deleting driver {driver_id}: {str(e)}")

    # Provide appropriate feedback
    if deletion_successful:
        flash(f"Kuljettaja {driver_name} poistettu onnistuneesti. Tilaukset ja hakemustiedot säilytetty.", "success")
    else:
        flash("Kuljettajan poistaminen epäonnistui", "error")

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
    """Deny driver application and clean up any associated driver account"""
    from models.driver_application import driver_application_model
    from models.user import user_model
    from app import users_col

    application_id = int(request.form.get("application_id"))

    # Get current user for logging
    user = auth_service.get_current_user()

    # Get application details
    app = driver_application_model.find_by_id(application_id)
    if not app or app.get('status') != 'pending':
        flash("Hakemusta ei löytynyt tai se on jo käsitelty", "error")
        return redirect(url_for("admin.driver_applications"))

    # Check if a driver user account was already created (orphaned or accidental)
    app_email = app.get('email')
    existing_user = user_model.find_by_email(app_email)

    if existing_user and existing_user.get('role') == 'driver':
        # Delete the orphaned driver account
        try:
            users_col().delete_one({"id": existing_user['id']})
            flash(f"Hakemus hylätty ja liittyvä kuljettajatili poistettu: {app['name']}", "warning")
        except Exception as e:
            print(f"Failed to delete orphaned driver account: {e}")
            flash(f"Hakemus hylätty, mutta kuljettajatilin poistaminen epäonnistui: {app['name']}", "error")
            return redirect(url_for("admin.driver_applications"))
    else:
        flash(f"Hakemus hylätty: {app['name']}", "warning")

    # Mark application as denied
    driver_application_model.deny_application(application_id, user["id"])

    return redirect(url_for("admin.driver_applications"))


@admin_bp.route("/driver-applications/<int:application_id>/delete", methods=["POST"])
@admin_required
def delete_driver_application(application_id):
    """Permanently delete driver application and associated user account"""
    from models.driver_application import driver_application_model
    from models.user import user_model
    from app import users_col

    # Get current user for logging
    user = auth_service.get_current_user()

    # Get application details
    app = driver_application_model.find_by_id(application_id)
    if not app:
        flash("Hakemusta ei löytynyt", "error")
        return redirect(url_for("admin.driver_applications"))

    app_name = app.get('name', 'Tuntematon')
    app_email = app.get('email', '')
    app_status = app.get('status', 'unknown')

    # Check if user account exists
    existing_user = user_model.find_by_email(app_email)
    user_deleted = False
    user_info = ""

    if existing_user:
        user_id = existing_user.get('id')
        user_role = existing_user.get('role')
        user_status = existing_user.get('status')

        # Delete user account
        try:
            users_col().delete_one({"id": user_id})
            user_deleted = True
            user_info = f"Käyttäjätili #{user_id} poistettu ({user_role}, {user_status})"
            print(f"✓ Deleted user account #{user_id} ({app_email})")
        except Exception as e:
            print(f"✗ Failed to delete user account: {e}")
            flash(f"Virhe käyttäjätilin poistamisessa: {str(e)}", "error")
            return redirect(url_for("admin.driver_application_detail", application_id=application_id))

    # Delete driver application
    try:
        driver_application_model.delete_one({"id": application_id})
        print(f"✓ Deleted driver application #{application_id} ({app_email})")
    except Exception as e:
        print(f"✗ Failed to delete driver application: {e}")
        flash(f"Virhe hakemuksen poistamisessa: {str(e)}", "error")
        return redirect(url_for("admin.driver_application_detail", application_id=application_id))

    # Build success message
    success_msg = f"✓ Hakemus #{application_id} poistettu ({app_name} - {app_email})"
    if user_deleted:
        success_msg += f"\n✓ {user_info}"
    else:
        success_msg += "\nℹ️ Käyttäjätiliä ei löytynyt"

    flash(success_msg, "success")
    print(f"✓ Admin {user.get('name')} deleted driver application #{application_id}")

    return redirect(url_for("admin.driver_applications"))


@admin_bp.route("/driver-applications/<int:application_id>/license/<string:image_type>")
@admin_required
def view_license_image(application_id, image_type):
    """Generate signed URL for viewing driver license image"""
    from models.driver_application import driver_application_model
    from services.gcs_service import gcs_service

    # Validate image_type
    if image_type not in ['front', 'back']:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin.driver_application_detail", application_id=application_id))

    # Get application
    application = driver_application_model.find_by_id(application_id)
    if not application:
        flash("Hakemusta ei löytynyt", "error")
        return redirect(url_for("admin.driver_applications"))

    # Get license images
    license_images = application.get("license_images", {})
    blob_name = license_images.get(image_type)

    if not blob_name:
        flash(f"Ajokortin {image_type} kuvaa ei löytynyt", "error")
        return redirect(url_for("admin.driver_application_detail", application_id=application_id))

    # Generate signed URL (1 hour expiration)
    signed_url = gcs_service.generate_signed_url(blob_name, expiration_minutes=60)

    if not signed_url:
        flash("Virhe kuvan URL:n generoinnissa", "error")
        return redirect(url_for("admin.driver_application_detail", application_id=application_id))

    # Redirect to signed URL
    return redirect(signed_url)


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

    return redirect(url_for("admin.order_detail", order_id=order_id))


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
            "reg_number": 1, "winter_tires": 1, "pickup_date": 1, "last_delivery_date": 1,
            "extras": 1, "images": 1,
            "orderer_name": 1, "orderer_email": 1, "orderer_phone": 1,
            "customer_name": 1, "customer_phone": 1,
            "driver_reward": 1, "car_brand": 1, "car_model": 1, "additional_info": 1, "driver_notes": 1,
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
    
    # Format last delivery date
    last_delivery_date_fi = order.get('last_delivery_date', None)
    if last_delivery_date_fi:
        try:
            if hasattr(last_delivery_date_fi, 'strftime'):
                last_delivery_date_fi = last_delivery_date_fi.strftime('%d.%m.%Y')
        except Exception:
            pass

    # Get current user for navbar
    user = auth_service.get_current_user()

    return render_template('admin/order_detail.html',
        order=order,
        status_fi=status_fi,
        pickup_date_fi=pickup_date_fi,
        last_delivery_date_fi=last_delivery_date_fi,
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
    u = auth_service.get_current_user()
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


@admin_bp.route("/api/order/<int:order_id>/upload", methods=["POST"])
@admin_required
def upload_order_image_ajax(order_id):
    """AJAX endpoint for uploading images (supports multiple uploads without page reload)"""
    admin_user = auth_service.get_current_user()
    image_type = request.form.get('image_type')

    # Validation
    if image_type not in ['pickup', 'delivery']:
        return jsonify({'success': False, 'error': 'Virheellinen kuvatyyppi'}), 400

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'Kuvaa ei valittu'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Kuvaa ei valittu'}), 400

    # Check image limit
    can_add, limit_error = image_service.validate_image_limit(order_id, image_type, max_images=15)
    if not can_add:
        return jsonify({'success': False, 'error': limit_error}), 400

    # Save and process image using ImageService
    image_info, error = image_service.save_order_image(file, order_id, image_type, admin_user.get('email', 'admin'))

    if error:
        return jsonify({'success': False, 'error': error}), 400

    # Add image to order using ImageService
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        return jsonify({'success': False, 'error': add_error}), 500

    # Get current image count
    from models.order import order_model
    order = order_model.find_by_id(order_id)
    current_images = order.get('images', {}).get(image_type, [])

    image_type_fi = 'Nouto' if image_type == 'pickup' else 'Toimitus'
    message = f'{image_type_fi}kuva lisätty onnistuneesti'

    return jsonify({
        'success': True,
        'message': message,
        'image': image_info,
        'image_count': len(current_images)
    })


@admin_bp.route("/api/order/<int:order_id>/image/<string:image_type>/<string:image_id>", methods=["DELETE"])
@admin_required
def delete_order_image_ajax(order_id, image_type, image_id):
    """AJAX endpoint for deleting images"""

    # Validation
    if image_type not in ['pickup', 'delivery']:
        return jsonify({'success': False, 'error': 'Virheellinen kuvatyyppi'}), 400

    # Delete image using ImageService
    success, message = image_service.delete_order_image(order_id, image_type, image_id)

    if not success:
        # Translate error messages to Finnish
        finnish_message = message
        if "Order or image not found" in message:
            finnish_message = "Tilausta tai kuvaa ei löytynyt"
        elif "Image not found" in message:
            finnish_message = "Kuvaa ei löytynyt"
        elif "Delete failed" in message:
            finnish_message = "Poisto epäonnistui"

        return jsonify({'success': False, 'error': finnish_message}), 400

    # Get updated image count
    from models.order import order_model
    order = order_model.find_by_id(order_id)
    current_images = order.get('images', {}).get(image_type, [])

    return jsonify({
        'success': True,
        'message': 'Kuva poistettu',
        'image_count': len(current_images)
    })


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

    # Check if driver_reward is set before confirming
    if not order.get('driver_reward') or order.get('driver_reward') <= 0:
        flash('Virhe: Aseta kuskin palkkio ennen tilauksen vahvistamista', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    # Update to CONFIRMED status (will trigger email notification automatically)
    success, error = order_service.update_order_status(order_id, 'CONFIRMED')

    if success:
        flash("Tilaus vahvistettu! Asiakas on saanut vahvistusviestin ja tilaus on nyt kuljettajien saatavilla.", "success")
    else:
        flash(f"Virhe: {error}", "error")

    return redirect(url_for("admin.order_detail", order_id=order_id))


# DEPRECATED: Old driver approval workflow (removed in driver_progress system)
# Admin no longer approves individual driver progress steps via quick action buttons.
# Admin manually updates customer-visible status using the status dropdown.
# Driver proceeds independently through their workflow using driver_progress field.
#
# @admin_bp.route("/order/<int:order_id>/approve-pickup-images", methods=["POST"])
# @admin_required
# def approve_pickup_images(order_id):
#     """Quick action: Approve pickup images and move to IN_TRANSIT status"""
#     ...
#
# @admin_bp.route("/order/<int:order_id>/approve-delivery-images", methods=["POST"])
# @admin_required
# def approve_delivery_images(order_id):
#     """Quick action: Approve delivery images and move to DELIVERED status"""
#     ...


@admin_bp.route("/order/<int:order_id>/update-details", methods=["POST"])
@admin_required
def update_order_details(order_id):
    """Update order details (driver reward, car info, additional info, driver notes)"""
    from models.order import order_model

    # Get form data
    driver_reward = request.form.get('driver_reward')
    car_brand = request.form.get('car_brand', '').strip()
    car_model = request.form.get('car_model', '').strip()
    additional_info = request.form.get('additional_info', '').strip()
    driver_notes = request.form.get('driver_notes', '').strip()

    # Validate and update driver reward
    if driver_reward:
        try:
            driver_reward_float = float(driver_reward)
            if driver_reward_float <= 0:
                flash('Virhe: Kuskin palkkio tulee olla suurempi kuin 0', 'error')
                return redirect(url_for('admin.order_detail', order_id=order_id))

            success, error = order_model.update_driver_reward(order_id, driver_reward_float)
            if not success:
                flash(f'Virhe palkkion päivityksessä: {error}', 'error')
                return redirect(url_for('admin.order_detail', order_id=order_id))
        except ValueError:
            flash('Virhe: Virheellinen palkkion arvo', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))

    # Update order details (including additional_info which is now admin-editable)
    success, error = order_model.update_order_details(
        order_id,
        car_model=car_model if car_model else None,
        car_brand=car_brand if car_brand else None,
        additional_info=additional_info if additional_info else None,
        driver_notes=driver_notes if driver_notes else None
    )

    if success:
        flash('Tilauksen tiedot päivitetty onnistuneesti!', 'success')
    else:
        flash(f'Virhe: {error}', 'error')

    return redirect(url_for('admin.order_detail', order_id=order_id))