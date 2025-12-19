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


# ==================== DISCOUNT MANAGEMENT ====================

@admin_bp.route("/discounts")
@admin_required
def discounts():
    """Admin discount management page"""
    from services.discount_service import discount_service

    # Get filter parameters
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    all_discounts = discount_service.get_all_discounts(include_inactive=include_inactive)

    # Add formatted labels to discounts
    for d in all_discounts:
        d['type_label'] = discount_service.get_discount_type_label(d.get('type', ''))
        d['scope_label'] = discount_service.get_scope_label(d.get('scope', ''))
        d['value_formatted'] = discount_service.format_discount_value(d)
        d['conditions'] = discount_service.format_conditions(d)
        d['assigned_count'] = len(d.get('assigned_users', []))

    return render_template(
        "admin/discounts.html",
        discounts=all_discounts,
        include_inactive=include_inactive,
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/discounts/new")
@admin_required
def discount_new():
    """Create new discount form"""
    from models.discount import DiscountModel
    from services.discount_service import discount_service
    from app import users_col

    # Get all regular users for preview
    all_users = list(users_col().find(
        {"role": "user", "status": "active"},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).sort("name", 1))

    return render_template(
        "admin/discount_form.html",
        discount=None,
        is_new=True,
        assigned_users=[],
        all_users=all_users,
        discount_types=[
            {"value": DiscountModel.TYPE_PERCENTAGE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_PERCENTAGE)},
            {"value": DiscountModel.TYPE_FIXED_AMOUNT, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FIXED_AMOUNT)},
            {"value": DiscountModel.TYPE_FREE_KILOMETERS, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FREE_KILOMETERS)},
            {"value": DiscountModel.TYPE_PRICE_CAP, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_PRICE_CAP)},
            {"value": DiscountModel.TYPE_CUSTOM_RATE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_CUSTOM_RATE)},
            {"value": DiscountModel.TYPE_TIERED_PERCENTAGE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_TIERED_PERCENTAGE)},
        ],
        discount_scopes=[
            {"value": DiscountModel.SCOPE_ACCOUNT, "label": discount_service.get_scope_label(DiscountModel.SCOPE_ACCOUNT)},
            {"value": DiscountModel.SCOPE_GLOBAL, "label": discount_service.get_scope_label(DiscountModel.SCOPE_GLOBAL)},
            {"value": DiscountModel.SCOPE_CODE, "label": discount_service.get_scope_label(DiscountModel.SCOPE_CODE)},
            {"value": DiscountModel.SCOPE_FIRST_ORDER, "label": discount_service.get_scope_label(DiscountModel.SCOPE_FIRST_ORDER)},
        ],
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/discounts", methods=["POST"])
@admin_required
def discount_create():
    """Create a new discount"""
    from services.discount_service import discount_service
    from datetime import datetime
    import json

    current_user = auth_service.get_current_user()

    # Parse form data
    discount_data = {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "type": request.form.get("type", "").strip(),
        "value": request.form.get("value", "0"),
        "scope": request.form.get("scope", "account"),
        "code": request.form.get("code", "").strip(),
        "min_distance_km": request.form.get("min_distance_km", ""),
        "max_distance_km": request.form.get("max_distance_km", ""),
        "min_order_value": request.form.get("min_order_value", ""),
        "max_order_value": request.form.get("max_order_value", ""),
        "max_uses_total": request.form.get("max_uses_total", ""),
        "max_uses_per_user": request.form.get("max_uses_per_user", ""),
        "stackable": request.form.get("stackable") == "on",
        "priority": request.form.get("priority", "10"),
        "active": request.form.get("active") == "on",
        "hide_from_customer": request.form.get("hide_from_customer") == "on",
        "created_by": current_user.get("id") if current_user else None
    }

    # Parse date fields
    valid_from = request.form.get("valid_from", "").strip()
    valid_until = request.form.get("valid_until", "").strip()
    
    if valid_from:
        try:
            discount_data["valid_from"] = datetime.strptime(valid_from, "%Y-%m-%d")
        except ValueError:
            pass
    
    if valid_until:
        try:
            discount_data["valid_until"] = datetime.strptime(valid_until, "%Y-%m-%d")
        except ValueError:
            pass

    # Parse tiered discounts
    tiers_json = request.form.get("tiers", "[]")
    try:
        discount_data["tiers"] = json.loads(tiers_json) if tiers_json else []
    except json.JSONDecodeError:
        discount_data["tiers"] = []

    # Parse city restrictions
    allowed_pickup = request.form.get("allowed_pickup_cities", "").strip()
    allowed_dropoff = request.form.get("allowed_dropoff_cities", "").strip()
    excluded = request.form.get("excluded_cities", "").strip()

    discount_data["allowed_pickup_cities"] = [c.strip() for c in allowed_pickup.split(",") if c.strip()] if allowed_pickup else []
    discount_data["allowed_dropoff_cities"] = [c.strip() for c in allowed_dropoff.split(",") if c.strip()] if allowed_dropoff else []
    discount_data["excluded_cities"] = [c.strip() for c in excluded.split(",") if c.strip()] if excluded else []

    assigned_user_ids = request.form.getlist("assigned_users")
    if assigned_user_ids:
        discount_data["assigned_users"] = [int(uid) for uid in assigned_user_ids if uid.isdigit()]
    else:
        discount_data["assigned_users"] = []

    discount, error = discount_service.create_discount(discount_data, created_by=current_user.get("id") if current_user else None)

    if error:
        flash(f"Virhe alennuksen luomisessa: {error}", "error")
        return redirect(url_for("admin.discount_new"))

    flash(f"Alennus '{discount.get('name')}' luotu onnistuneesti!", "success")
    return redirect(url_for("admin.discounts"))


@admin_bp.route("/discounts/<int:discount_id>")
@admin_required
def discount_detail(discount_id):
    """View/edit discount details"""
    from services.discount_service import discount_service
    from models.discount import DiscountModel
    from app import users_col

    discount = discount_service.get_discount(discount_id)
    if not discount:
        flash("Alennusta ei löytynyt", "error")
        return redirect(url_for("admin.discounts"))

    # Get statistics
    stats = discount_service.get_statistics(discount_id)

    # Get assigned users details
    assigned_user_ids = discount.get("assigned_users", [])
    assigned_users = list(users_col().find(
        {"id": {"$in": assigned_user_ids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    )) if assigned_user_ids else []

    # Get all users for assignment dropdown (exclude drivers and admins)
    all_users = list(users_col().find(
        {"role": "user", "status": "active"},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).sort("name", 1))

    return render_template(
        "admin/discount_form.html",
        discount=discount,
        is_new=False,
        stats=stats,
        assigned_users=assigned_users,
        all_users=all_users,
        discount_types=[
            {"value": DiscountModel.TYPE_PERCENTAGE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_PERCENTAGE)},
            {"value": DiscountModel.TYPE_FIXED_AMOUNT, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FIXED_AMOUNT)},
            {"value": DiscountModel.TYPE_FREE_KILOMETERS, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FREE_KILOMETERS)},
            {"value": DiscountModel.TYPE_PRICE_CAP, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_PRICE_CAP)},
            {"value": DiscountModel.TYPE_CUSTOM_RATE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_CUSTOM_RATE)},
            {"value": DiscountModel.TYPE_TIERED_PERCENTAGE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_TIERED_PERCENTAGE)},
        ],
        discount_scopes=[
            {"value": DiscountModel.SCOPE_ACCOUNT, "label": discount_service.get_scope_label(DiscountModel.SCOPE_ACCOUNT)},
            {"value": DiscountModel.SCOPE_GLOBAL, "label": discount_service.get_scope_label(DiscountModel.SCOPE_GLOBAL)},
            {"value": DiscountModel.SCOPE_CODE, "label": discount_service.get_scope_label(DiscountModel.SCOPE_CODE)},
            {"value": DiscountModel.SCOPE_FIRST_ORDER, "label": discount_service.get_scope_label(DiscountModel.SCOPE_FIRST_ORDER)},
        ],
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/discounts/<int:discount_id>", methods=["POST"])
@admin_required
def discount_update(discount_id):
    """Update an existing discount"""
    from services.discount_service import discount_service
    from datetime import datetime
    import json

    # Parse form data
    update_data = {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "type": request.form.get("type", "").strip(),
        "value": request.form.get("value", "0"),
        "scope": request.form.get("scope", "account"),
        "code": request.form.get("code", "").strip(),
        "min_distance_km": request.form.get("min_distance_km", ""),
        "max_distance_km": request.form.get("max_distance_km", ""),
        "min_order_value": request.form.get("min_order_value", ""),
        "max_order_value": request.form.get("max_order_value", ""),
        "max_uses_total": request.form.get("max_uses_total", ""),
        "max_uses_per_user": request.form.get("max_uses_per_user", ""),
        "stackable": request.form.get("stackable") == "on",
        "priority": request.form.get("priority", "10"),
        "active": request.form.get("active") == "on",
        "hide_from_customer": request.form.get("hide_from_customer") == "on"
    }

    # Parse date fields
    valid_from = request.form.get("valid_from", "").strip()
    valid_until = request.form.get("valid_until", "").strip()
    
    if valid_from:
        try:
            update_data["valid_from"] = datetime.strptime(valid_from, "%Y-%m-%d")
        except ValueError:
            update_data["valid_from"] = None
    else:
        update_data["valid_from"] = None
    
    if valid_until:
        try:
            update_data["valid_until"] = datetime.strptime(valid_until, "%Y-%m-%d")
        except ValueError:
            update_data["valid_until"] = None
    else:
        update_data["valid_until"] = None

    # Parse tiered discounts
    tiers_json = request.form.get("tiers", "[]")
    try:
        update_data["tiers"] = json.loads(tiers_json) if tiers_json else []
    except json.JSONDecodeError:
        update_data["tiers"] = []

    # Parse city restrictions
    allowed_pickup = request.form.get("allowed_pickup_cities", "").strip()
    allowed_dropoff = request.form.get("allowed_dropoff_cities", "").strip()
    excluded = request.form.get("excluded_cities", "").strip()

    update_data["allowed_pickup_cities"] = [c.strip() for c in allowed_pickup.split(",") if c.strip()] if allowed_pickup else []
    update_data["allowed_dropoff_cities"] = [c.strip() for c in allowed_dropoff.split(",") if c.strip()] if allowed_dropoff else []
    update_data["excluded_cities"] = [c.strip() for c in excluded.split(",") if c.strip()] if excluded else []

    success, error = discount_service.update_discount(discount_id, update_data)

    if error:
        flash(f"Virhe alennuksen päivityksessä: {error}", "error")
    else:
        flash("Alennus päivitetty onnistuneesti!", "success")

    return redirect(url_for("admin.discount_detail", discount_id=discount_id))


@admin_bp.route("/discounts/<int:discount_id>/toggle", methods=["POST"])
@admin_required
def discount_toggle(discount_id):
    """Toggle discount active status"""
    from services.discount_service import discount_service

    discount = discount_service.get_discount(discount_id)
    if not discount:
        flash("Alennusta ei löytynyt", "error")
        return redirect(url_for("admin.discounts"))

    if discount.get("active"):
        success, error = discount_service.deactivate_discount(discount_id)
        action = "poistettu käytöstä"
    else:
        success, error = discount_service.activate_discount(discount_id)
        action = "aktivoitu"

    if error:
        flash(f"Virhe: {error}", "error")
    else:
        flash(f"Alennus {action} onnistuneesti!", "success")

    return redirect(url_for("admin.discounts"))


@admin_bp.route("/discounts/<int:discount_id>/assign", methods=["POST"])
@admin_required
def discount_assign_user(discount_id):
    """Assign discount to a user"""
    from services.discount_service import discount_service

    user_id = request.form.get("user_id")
    if not user_id:
        flash("Valitse käyttäjä", "error")
        return redirect(url_for("admin.discount_detail", discount_id=discount_id))

    success, error = discount_service.assign_to_user(discount_id, int(user_id))

    if error:
        flash(f"Virhe käyttäjän lisäämisessä: {error}", "error")
    else:
        flash("Käyttäjä lisätty alennukseen!", "success")

    return redirect(url_for("admin.discount_detail", discount_id=discount_id))


@admin_bp.route("/discounts/<int:discount_id>/unassign/<int:user_id>", methods=["POST"])
@admin_required
def discount_unassign_user(discount_id, user_id):
    """Remove discount from a user"""
    from services.discount_service import discount_service

    success, error = discount_service.remove_from_user(discount_id, user_id)

    if error:
        flash(f"Virhe käyttäjän poistamisessa: {error}", "error")
    else:
        flash("Käyttäjä poistettu alennuksesta!", "success")

    return redirect(url_for("admin.discount_detail", discount_id=discount_id))


# ==================== API Endpoints for Discounts ====================

@admin_bp.route("/api/discounts/validate-code", methods=["POST"])
@admin_required
def api_validate_promo_code():
    """Validate a promo code"""
    from services.discount_service import discount_service

    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "").strip()

    discount, error = discount_service.validate_promo_code(code)

    if error:
        return jsonify({"valid": False, "error": error}), 400

    return jsonify({
        "valid": True,
        "discount": {
            "id": discount.get("id"),
            "name": discount.get("name"),
            "type": discount.get("type"),
            "value": discount.get("value")
        }
    })


@admin_bp.route("/api/discounts/preview-price", methods=["POST"])
@admin_required
def api_preview_discounted_price():
    """Preview price with discounts applied"""
    from services.order_service import order_service

    data = request.get_json(force=True, silent=True) or {}
    
    distance_km = float(data.get("distance_km", 0))
    pickup_addr = data.get("pickup_addr", "")
    dropoff_addr = data.get("dropoff_addr", "")
    user_id = data.get("user_id")
    promo_code = data.get("promo_code")

    if distance_km <= 0:
        return jsonify({"error": "Etäisyys vaaditaan"}), 400

    result = order_service.price_from_km_with_discounts(
        distance_km=distance_km,
        pickup_addr=pickup_addr,
        dropoff_addr=dropoff_addr,
        user_id=int(user_id) if user_id else None,
        promo_code=promo_code
    )

    return jsonify(result)
