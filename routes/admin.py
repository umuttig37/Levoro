"""
Admin Routes for user and system management
"""

from datetime import datetime, timezone
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from werkzeug.security import generate_password_hash
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
    """Admin user management page with search/filter"""
    from app import users_col

    search = request.args.get("search", "").strip()
    # Default to 'user' (customers) if no role specified, unless explicit "all" is requested (though UI won't offer "all")
    role_filter = request.args.get("role", "user").strip()
    status_filter = request.args.get("status", "").strip()

    query = {}
    if role_filter and role_filter != "all":
        query["role"] = role_filter
    if status_filter and status_filter != "all":
        query["status"] = status_filter
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
        ]

    users = list(users_col().find(query, {"_id": 0}).sort("created_at", -1))

    return render_template(
        "admin/users.html",
        users=users,
        current_user=auth_service.get_current_user(),
        search=search,
        role_filter=role_filter,
        status_filter=status_filter,
    )


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    """View details of a specific user/driver/admin"""
    from models.user import user_model
    from models.order import order_model
    from services.driver_service import driver_service
    from services.order_service import order_service
    
    user = user_model.find_by_id(user_id)
    if not user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))

    # Prepare context data based on role
    context = {
        "user": user,
        "current_user": auth_service.get_current_user(),
    }

    if user.get("role") == "driver":
        # specific data for drivers
        driver_stats = driver_service.get_driver_statistics(user_id)
        active_statuses = [
            order_model.STATUS_CONFIRMED,
            order_model.STATUS_ASSIGNED_TO_DRIVER,
            order_model.STATUS_DRIVER_ARRIVED,
            order_model.STATUS_PICKUP_IMAGES_ADDED,
            order_model.STATUS_IN_TRANSIT,
            order_model.STATUS_DELIVERY_ARRIVED,
            order_model.STATUS_DELIVERY_IMAGES_ADDED,
        ]
        driver_active_orders = order_model.find(
            {"driver_id": int(user_id), "status": {"$in": active_statuses}},
            sort=[("created_at", -1)]
        )
        driver_all_orders = order_model.find(
            {"driver_id": int(user_id)},
            sort=[("created_at", -1)],
            limit=200
        )
        active_ids = {order.get("id") for order in driver_active_orders if order.get("id") is not None}
        driver_order_history = [order for order in driver_all_orders if order.get("id") not in active_ids]
        context["driver_stats"] = driver_stats
        context["driver_active_orders"] = driver_active_orders
        context["driver_orders"] = driver_order_history
        
    elif user.get("role") == "user":
        # specific data for customers (order history)
        # Fetch detailed order history
        all_orders = order_model.get_user_orders(user_id)
        
        # Separate active orders from completed history
        completed_statuses = ['completed', 'cancelled', 'delivered']
        active_orders = [o for o in all_orders if o.get('status', '').lower() not in completed_statuses]
        order_history = [o for o in all_orders if o.get('status', '').lower() in completed_statuses]
        
        # Calculate total spent (sum of ALL orders)
        total_spent = 0
        for order in all_orders:
            price = order.get("price_gross")
            if price is None:
                price = order.get("price", 0)
            total_spent += price or 0
        
        context["active_orders"] = active_orders
        context["orders"] = order_history  # For backward compatibility with order history table
        context["total_orders"] = len(all_orders)
        context["total_spent"] = total_spent

    return render_template("admin/user_detail.html", **context)


@admin_bp.route("/users/approve", methods=["POST"])
@admin_required
def approve_user():
    """Approve a pending user"""
    from app import users_col
    from models.user import user_model

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


@admin_bp.route("/users/update", methods=["POST"])
@admin_required
def update_user():
    """Edit basic user details (non-driver)"""
    from models.user import user_model

    user_id = int(request.form.get("user_id", 0))
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()
    company_name = (request.form.get("company_name") or "").strip()
    business_id = (request.form.get("business_id") or "").strip()
    status = (request.form.get("status") or "").strip()

    if not user_id:
        flash("Virheellinen käyttäjä", "error")
        return redirect(url_for("admin.users"))

    user = user_model.find_by_id(user_id)
    if not user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))

    update_data = {}
    if name:
        update_data["name"] = name
    if email:
        update_data["email"] = email
    update_data["phone"] = phone or None
    # Only update company fields for non-driver users
    if user.get("role") != "driver":
        update_data["company_name"] = company_name or None
        update_data["business_id"] = business_id or None
    if status in ["active", "pending", "frozen"]:
        update_data["status"] = status

    success = user_model.update_one({"id": user_id}, {"$set": update_data})


    if success:
        flash("Käyttäjä päivitetty", "success")
    else:
        flash("Päivitys epäonnistui", "error")

    return redirect(url_for("admin.users"))


@admin_bp.route("/users/reset-password", methods=["POST"])
@admin_required
def reset_user_password():
    """Send a password reset link to the user's email"""
    from models.user import user_model

    try:
        user_id = int(request.form.get("user_id", 0))
    except (TypeError, ValueError):
        flash("Virheellinen käyttäjä", "error")
        return redirect(url_for("admin.users"))

    user = user_model.find_by_id(user_id)
    if not user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))

    email = user.get("email")
    if not email:
        flash("Käyttäjällä ei ole sähköpostiosoitetta", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    _, error = auth_service.request_password_reset(email)
    if error:
        flash("Salasanan nollaus epäonnistui", "error")
    else:
        flash("Nollauslinkki lähetetty käyttäjän sähköpostiin", "success")

    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/set-password", methods=["POST"])
@admin_required
def set_user_password():
    """Admin sets a new password for the user"""
    from models.user import user_model

    try:
        user_id = int(request.form.get("user_id", 0))
    except (TypeError, ValueError):
        flash("Virheellinen käyttäjä", "error")
        return redirect(url_for("admin.users"))

    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not new_password or not confirm_password:
        flash("Salasanakentät ovat pakollisia", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    if new_password != confirm_password:
        flash("Salasanat eivät täsmää", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    if len(new_password) < 6:
        flash("Salasana on liian heikko (vähintään 6 merkkiä)", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    user = user_model.find_by_id(user_id)
    if not user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))

    success = user_model.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": generate_password_hash(new_password),
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    if success:
        flash("Salasana päivitetty", "success")
    else:
        flash("Salasanan päivitys epäonnistui", "error")

    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/toggle-freeze", methods=["POST"])
@admin_required
def toggle_user_freeze():
    """Freeze or unfreeze a user account"""
    from models.user import user_model

    try:
        user_id = int(request.form.get("user_id", 0))
    except (TypeError, ValueError):
        flash("Virheellinen käyttäjä", "error")
        return redirect(url_for("admin.users"))

    user = user_model.find_by_id(user_id)
    if not user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))

    if user.get("role") == "admin":
        flash("Admin-käyttäjiä ei voi jäädyttää tältä sivulta", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    current_user = auth_service.get_current_user()
    if current_user and current_user.get("id") == user_id:
        flash("Et voi jäädyttää omaa tiliäsi", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    is_frozen = user.get("status") == "frozen"
    new_status = "active" if is_frozen else "frozen"
    success = user_model.update_one(
        {"id": user_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}}
    )

    if success:
        message = "Jäädytys poistettu" if is_frozen else "Käyttäjä jäädytetty"
        flash(message, "success")
    else:
        flash("Tapahtuma epäonnistui. Yritä uudelleen.", "error")

    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/verify-password", methods=["POST"])
@admin_required
def verify_admin_password():
    """Verify current admin's password for sensitive operations"""
    from models.user import user_model
    
    password = request.form.get("password", "")
    current_user = auth_service.get_current_user()
    
    if not current_user:
        return jsonify({"valid": False, "error": "Ei kirjautunut sisään"})
    
    is_valid = user_model.verify_password(current_user["id"], password)
    return jsonify({"valid": is_valid})


@admin_bp.route("/users/delete-admin", methods=["POST"])
@admin_required
def delete_admin_user():
    """Delete an admin user with password confirmation"""
    from models.user import user_model
    
    user_id = int(request.form.get("user_id", 0))
    admin_password = request.form.get("admin_password", "")
    
    current_user = auth_service.get_current_user()
    
    if not current_user:
        flash("Ei kirjautunut sisään", "error")
        return redirect(url_for("admin.users"))
    
    # Verify admin password
    if not user_model.verify_password(current_user["id"], admin_password):
        flash("Väärä salasana", "error")
        return redirect(url_for("admin.users"))
    
    # Get target user
    target_user = user_model.find_by_id(user_id)
    if not target_user:
        flash("Käyttäjää ei löytynyt", "error")
        return redirect(url_for("admin.users"))
    
    # Prevent self-deletion
    if target_user["id"] == current_user["id"]:
        flash("Et voi poistaa omaa tiliäsi", "error")
        return redirect(url_for("admin.users"))
    
    # Only allow deleting admin users through this endpoint
    if target_user.get("role") != "admin":
        flash("Tämä toiminto on vain admin-käyttäjille", "error")
        return redirect(url_for("admin.users"))
    
    # Delete the admin user
    from app import users_col
    result = users_col().delete_one({"id": user_id})
    
    if result.deleted_count > 0:
        flash(f"Admin-käyttäjä {target_user.get('name')} poistettu onnistuneesti", "success")
    else:
        flash("Käyttäjän poistaminen epäonnistui", "error")
    
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/create", methods=["POST"])
@admin_required
def create_user():
    """Admin creates a new user account"""
    from models.user import user_model
    
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password", "")
    phone = (request.form.get("phone") or "").strip()
    role = (request.form.get("role") or "user").strip()
    admin_password = request.form.get("admin_password", "")
    
    current_user = auth_service.get_current_user()
    
    if not current_user:
        flash("Ei kirjautunut sisään", "error")
        return redirect(url_for("admin.users"))
    
    # Validate required fields
    if not name or not email or not password:
        flash("Nimi, sähköposti ja salasana ovat pakollisia", "error")
        return redirect(url_for("admin.users"))
    
    # Validate role
    if role not in ["user", "admin"]:
        flash("Virheellinen rooli", "error")
        return redirect(url_for("admin.users"))
    
    # If creating admin, verify admin password
    if role == "admin":
        if not admin_password:
            flash("Salasanan vahvistus vaaditaan admin-käyttäjän luomiseen", "error")
            return redirect(url_for("admin.users"))
        
        if not user_model.verify_password(current_user["id"], admin_password):
            flash("Väärä salasana", "error")
            return redirect(url_for("admin.users"))
    
    # Create the user (admin users are automatically active, regular users are active when created by admin)
    user_data, error = user_model.create_user(
        email=email,
        password=password,
        name=name,
        role=role,
        phone=phone if phone else None
    )
    
    if error:
        flash(f"Käyttäjän luominen epäonnistui: {error}", "error")
        return redirect(url_for("admin.users"))
    
    # Ensure user created by admin is active
    if user_data and user_data.get("status") != "active":
        user_model.update_one({"id": user_data["id"]}, {"$set": {"status": "active"}})
    
    role_text = "Admin-käyttäjä" if role == "admin" else "Käyttäjä"
    flash(f"{role_text} {name} luotu onnistuneesti", "success")
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
    from flask import session
    from datetime import datetime, timezone
    from models.driver_application import driver_application_model

    # Mark applications as viewed
    session['admin_last_viewed_applications'] = datetime.now(timezone.utc)

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
    # Handle both JSON (AJAX) and Form data
    if request.is_json:
        data = request.get_json()
        order_id = int(data.get("id"))
        new_status = data.get("status")
    else:
        order_id = int(request.form.get("id"))
        new_status = request.form.get("status")

    # Validate status
    from models.order import order_model
    if new_status not in order_model.VALID_STATUSES:
        if request.is_json:
            return jsonify({"success": False, "error": "Virheellinen tila"}), 400
        return redirect(url_for("main.admin_dashboard"))

    # Use service layer to update order status (includes automatic email sending)
    success, error = order_service.update_order_status(order_id, new_status)

    if success:
        from models.order import order_model
        publish_success, publish_error = order_model.publish_pending_images(order_id)
        if not publish_success:
            flash(f"Kuvien julkaisu epäonnistui: {publish_error}", "warning")

    if request.is_json:
        if success:
            from app import translate_status
            status_fi = translate_status(new_status)
            return jsonify({
                "success": True, 
                "message": f"Tilauksen tila päivitetty: {status_fi}",
                "status": new_status,
                "status_fi": status_fi
            })
        else:
            return jsonify({
                "success": False, 
                "error": error or "Tilan päivitys epäonnistui"
            }), 400

    # Fallback for traditional form submission
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
    from services.rating_service import rating_service

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
            "pickup_time": 1, "delivery_time": 1,
            "pickup_from_eu": 1,
            "created_at": 1, "updated_at": 1,
            "extras": 1, "images": 1,
            "orderer_name": 1, "orderer_email": 1, "orderer_phone": 1,
            "customer_name": 1, "customer_phone": 1,
            "driver_reward": 1, "car_brand": 1, "car_model": 1, "additional_info": 1, "driver_notes": 1,
            "direct_to_customer": 1,
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
    
    # Ensure critical fields have default values to prevent template crashes
    order.setdefault('price_gross', 0)
    order.setdefault('distance_km', 0)
    order.setdefault('status', 'NEW')
    order.setdefault('pickup_address', '')
    order.setdefault('dropoff_address', '')
    order.setdefault('pickup_from_eu', False)
    
    status_fi = translate_status(order.get('status', 'NEW'))

    # Get available drivers for assignment dropdown
    from models.user import user_model
    available_drivers = user_model.get_all_drivers(limit=100)

    # Format dates to Finnish format (handle both datetime objects and strings)
    from datetime import datetime
    
    def format_date_fi(date_val):
        """Convert date to Finnish format DD.MM.YYYY"""
        if not date_val or date_val == 'Ei asetettu':
            return 'Ei asetettu' if date_val == 'Ei asetettu' else None
        # If it's a datetime/date object
        if hasattr(date_val, 'strftime'):
            return date_val.strftime('%d.%m.%Y')
        # If it's a string in ISO format (YYYY-MM-DD)
        if isinstance(date_val, str):
            try:
                parsed = datetime.strptime(date_val, '%Y-%m-%d')
                return parsed.strftime('%d.%m.%Y')
            except ValueError:
                try:
                    datetime.strptime(date_val, '%d.%m.%Y')
                    return date_val  # Already in Finnish format
                except ValueError:
                    return date_val
        return str(date_val) if date_val else None
    
    pickup_date_fi = format_date_fi(order.get('pickup_date', 'Ei asetettu'))
    last_delivery_date_fi = format_date_fi(order.get('last_delivery_date', None))
    pickup_time = (order.get('pickup_time') or '').strip()
    delivery_time = (order.get('delivery_time') or '').strip()

    # Get current user for navbar
    user = auth_service.get_current_user()

    return render_template('admin/order_detail.html',
        order=order,
        status_fi=status_fi,
        pickup_date_fi=pickup_date_fi,
        last_delivery_date_fi=last_delivery_date_fi,
        pickup_time=pickup_time,
        delivery_time=delivery_time,
        available_drivers=available_drivers,
        current_user=user,
        rating=rating_service.get_order_rating(order_id)
    )


@admin_bp.route("/order/<int:order_id>/upload", methods=["POST"])
@admin_required
def upload_order_image(order_id):
    """Upload image to order"""
    image_type = request.form.get("image_type")
    if image_type not in ["pickup", "delivery", "receipts"]:
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

    image_info["visible_to_customer"] = False

    # Add image to order using ImageService
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        flash(add_error, "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    image_type_fi = "Nouto" if image_type == "pickup" else ("Toimitus" if image_type == "delivery" else "Kuitti")
    flash(f"{image_type_fi} kuva ladattu onnistuneesti", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/api/order/<int:order_id>/upload", methods=["POST"])
@admin_required
def upload_order_image_ajax(order_id):
    """AJAX endpoint for uploading images (supports multiple uploads without page reload)"""
    admin_user = auth_service.get_current_user()
    image_type = request.form.get('image_type')

    # Validation
    if image_type not in ['pickup', 'delivery', 'receipts']:
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

    image_info["visible_to_customer"] = False

    # Add image to order using ImageService
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        return jsonify({'success': False, 'error': add_error}), 500

    # Get current image count
    from models.order import order_model
    order = order_model.find_by_id(order_id)
    current_images = order.get('images', {}).get(image_type, [])

    image_type_fi = 'Nouto' if image_type == 'pickup' else ('Toimitus' if image_type == 'delivery' else 'Kuitti')
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
    if image_type not in ['pickup', 'delivery', 'receipts']:
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
    if image_type not in ["pickup", "delivery", "receipts"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    success, message = image_service.delete_order_image(order_id, image_type, request.form.get('image_id'))

    image_type_fi = "Nouto" if image_type == "pickup" else ("Toimitus" if image_type == "delivery" else "Kuitti")

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
    if image_type not in ["pickup", "delivery", "receipts"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    success, message = image_service.delete_order_image(order_id, image_type, image_id)

    image_type_fi = "Nouto" if image_type == "pickup" else ("Toimitus" if image_type == "delivery" else "Kuitti")

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
    """Manually assign driver info to an order (name/phone, not from registered driver)"""
    driver_name = request.form.get("driver_name", "").strip()
    driver_phone = request.form.get("driver_phone", "").strip()

    if not driver_name:
        flash("Syötä kuljettajan nimi", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    # Update order with manual driver info
    from models.order import order_model
    success = order_model.update_one(
        {"id": int(order_id)},
        {"$set": {
            "manual_driver_name": driver_name,
            "manual_driver_phone": driver_phone,
            "driver_name": driver_name,
            "driver_phone": driver_phone
        }}
    )

    if success:
        flash(f"Kuljettaja '{driver_name}' määritetty onnistuneesti", "success")
    else:
        flash("Virhe kuljettajan määrityksessä", "error")

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
    price_gross = request.form.get('price_gross')
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

    # Update price (gross)
    if price_gross is not None and price_gross != '':
        try:
            normalized = price_gross.replace(',', '.')
            price_gross_float = float(normalized)
            if price_gross_float < 0:
                flash('Virhe: Hinta ei voi olla negatiivinen', 'error')
                return redirect(url_for('admin.order_detail', order_id=order_id))

            success, error = order_model.update_price_gross(order_id, price_gross_float)
            if not success:
                flash(f'Hinnan päivitys epäonnistui: {error}', 'error')
                return redirect(url_for('admin.order_detail', order_id=order_id))
        except ValueError:
            flash('Virhe: Virheellinen hinnan arvo', 'error')
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


@admin_bp.route("/order/<int:order_id>/delete", methods=["POST"])
@admin_required
def delete_order(order_id):
    """Delete an order (admin only)"""
    from models.order import order_model

    success, error = order_model.delete_order(order_id)
    if success:
        flash(f"Tilaus #{order_id} poistettu.", "success")
        return redirect(url_for("main.admin_dashboard"))
    else:
        flash(f"Virhe: {error}", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))


# ==================== DISCOUNT MANAGEMENT ====================


def _get_discount_form_choices(discount_service):
    """Build shared discount type/scope option lists."""
    from models.discount import DiscountModel

    discount_types = [
        {"value": DiscountModel.TYPE_PERCENTAGE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_PERCENTAGE)},
        {"value": DiscountModel.TYPE_FIXED_AMOUNT, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FIXED_AMOUNT)},
        {"value": DiscountModel.TYPE_FREE_KILOMETERS, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FREE_KILOMETERS)},
        {"value": DiscountModel.TYPE_PRICE_CAP, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_PRICE_CAP)},
        {"value": DiscountModel.TYPE_CUSTOM_RATE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_CUSTOM_RATE)},
        {"value": DiscountModel.TYPE_TIERED_PERCENTAGE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_TIERED_PERCENTAGE)},
        {"value": DiscountModel.TYPE_FIXED_PRICE, "label": discount_service.get_discount_type_label(DiscountModel.TYPE_FIXED_PRICE)},
    ]

    discount_scopes = [
        {"value": DiscountModel.SCOPE_ACCOUNT, "label": discount_service.get_scope_label(DiscountModel.SCOPE_ACCOUNT)},
        {"value": DiscountModel.SCOPE_GLOBAL, "label": discount_service.get_scope_label(DiscountModel.SCOPE_GLOBAL)},
        {"value": DiscountModel.SCOPE_CODE, "label": discount_service.get_scope_label(DiscountModel.SCOPE_CODE)},
        {"value": DiscountModel.SCOPE_FIRST_ORDER, "label": discount_service.get_scope_label(DiscountModel.SCOPE_FIRST_ORDER)},
    ]

    return discount_types, discount_scopes


def _get_active_regular_users():
    """Return active non-admin customer users for discount assignment."""
    from app import users_col

    query = {"role": "user", "status": "active"}
    projection = {"_id": 0, "id": 1, "name": 1, "email": 1}
    return list(users_col().find(query, projection).sort("name", 1))


def _parse_csv_list(value):
    """Convert comma-separated string into a list of trimmed items."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_date_field(value):
    """Parse YYYY-MM-DD date strings into datetime objects or None."""
    from datetime import datetime

    cleaned = (value or "").strip()
    if not cleaned:
        return None

    try:
        return datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError:
        return None


def _parse_tiers_json(raw_value):
    """Parse tier JSON payload with graceful fallback."""
    import json

    if not raw_value:
        return []

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return []

@admin_bp.route("/discounts")
@admin_required
def discounts():
    """Admin discount management page"""
    from services.discount_service import discount_service

    # Always get all discounts including inactive - client-side will filter
    all_discounts = discount_service.get_all_discounts(include_inactive=True)

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
        include_inactive=True,  # Always true now, client handles filtering
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/discounts/new")
@admin_required
def discount_new():
    """Create new discount form"""
    from services.discount_service import discount_service

    # Get all regular users for preview
    all_users = _get_active_regular_users()
    discount_types, discount_scopes = _get_discount_form_choices(discount_service)

    return render_template(
        "admin/discount_form.html",
        discount=None,
        is_new=True,
        assigned_users=[],
        all_users=all_users,
        discount_types=discount_types,
        discount_scopes=discount_scopes,
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/discounts", methods=["POST"])
@admin_required
def discount_create():
    """Create a new discount"""
    from services.discount_service import discount_service

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
    valid_from = _parse_date_field(request.form.get("valid_from", ""))
    valid_until = _parse_date_field(request.form.get("valid_until", ""))
    if valid_from:
        discount_data["valid_from"] = valid_from
    if valid_until:
        discount_data["valid_until"] = valid_until

    # Parse tiered discounts
    discount_data["tiers"] = _parse_tiers_json(request.form.get("tiers", "[]"))

    # Parse city restrictions
    discount_data["allowed_pickup_cities"] = _parse_csv_list(request.form.get("allowed_pickup_cities", "").strip())
    discount_data["allowed_dropoff_cities"] = _parse_csv_list(request.form.get("allowed_dropoff_cities", "").strip())
    discount_data["excluded_cities"] = _parse_csv_list(request.form.get("excluded_cities", "").strip())

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

    discount = discount_service.get_discount(discount_id)
    if not discount:
        flash("Alennusta ei löytynyt", "error")
        return redirect(url_for("admin.discounts"))

    # Get statistics
    stats = discount_service.get_statistics(discount_id)

    # Get assigned users details
    assigned_user_ids = discount.get("assigned_users", [])
    if assigned_user_ids:
        from app import users_col

        assigned_users = list(users_col().find(
            {"id": {"$in": assigned_user_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1}
        ))
    else:
        assigned_users = []

    # Get all users for assignment dropdown (exclude drivers and admins)
    all_users = _get_active_regular_users()
    discount_types, discount_scopes = _get_discount_form_choices(discount_service)

    return render_template(
        "admin/discount_form.html",
        discount=discount,
        is_new=False,
        stats=stats,
        assigned_users=assigned_users,
        all_users=all_users,
        discount_types=discount_types,
        discount_scopes=discount_scopes,
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/discounts/<int:discount_id>", methods=["POST"])
@admin_required
def discount_update(discount_id):
    """Update an existing discount"""
    from services.discount_service import discount_service

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
    update_data["valid_from"] = _parse_date_field(request.form.get("valid_from", ""))
    update_data["valid_until"] = _parse_date_field(request.form.get("valid_until", ""))

    # Parse tiered discounts
    update_data["tiers"] = _parse_tiers_json(request.form.get("tiers", "[]"))

    # Parse city restrictions
    update_data["allowed_pickup_cities"] = _parse_csv_list(request.form.get("allowed_pickup_cities", "").strip())
    update_data["allowed_dropoff_cities"] = _parse_csv_list(request.form.get("allowed_dropoff_cities", "").strip())
    update_data["excluded_cities"] = _parse_csv_list(request.form.get("excluded_cities", "").strip())

    # Parse assigned users (handle updates to user list)
    assigned_user_ids = request.form.getlist("assigned_users")
    if assigned_user_ids:
        update_data["assigned_users"] = [int(uid) for uid in assigned_user_ids if uid.isdigit()]
    else:
        # If no users are selected (or all removed), clear the list
        # BUT only if the scope is 'account'. If scope changed to global, we might want to clear it too.
        # Although the frontend creates validation/hidden inputs.
        # Safest is to just update it if we are submitting the form.
        # Note: If the form didn't include assigned_users field at all (e.g. some partial update), 
        # this would clear it. But since we use a full edit form, absence means empty.
        # However, we should be careful if scope != 'account'.
        update_data["assigned_users"] = []

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


# ----------------- REVIEWS MODERATION -----------------

@admin_bp.route("/reviews")
@admin_required
def reviews():
    """Admin reviews moderation page"""
    from flask import session
    from datetime import datetime, timezone
    from services.rating_service import rating_service
    from models.rating import rating_model
    
    # Mark reviews as viewed
    session['admin_last_viewed_reviews'] = datetime.now(timezone.utc)
    
    # Get all reviews with details
    reviews = rating_service.get_all_reviews_for_admin()
    
    # Calculate stats
    approved_reviews = [r for r in reviews if r.get("status") == "approved"]
    pending_count = len([r for r in reviews if r.get("status") == "pending"])
    
    avg_rating = 0
    if approved_reviews:
        avg_rating = sum(r["rating"] for r in approved_reviews) / len(approved_reviews)
    
    return render_template(
        "admin/reviews.html",
        reviews=reviews,
        avg_rating=avg_rating,
        pending_count=pending_count,
        current_user=auth_service.get_current_user()
    )


@admin_bp.route("/reviews/moderate", methods=["POST"])
@admin_required
def moderate_review():
    """Moderate a review (approve/hide)"""
    from services.rating_service import rating_service
    
    rating_id = int(request.form.get("rating_id", 0))
    action = request.form.get("action", "")
    
    if not rating_id or action not in ["approve", "hide"]:
        flash("Virheelliset parametrit", "error")
        return redirect(url_for("admin.reviews"))
    
    admin = auth_service.get_current_user()
    success, error = rating_service.moderate_review(rating_id, action, admin["id"])
    
    if success:
        action_text = "hyväksytty" if action == "approve" else "piilotettu"
        flash(f"Arvostelu {action_text}", "success")
    else:
        flash(error or "Moderointi epäonnistui", "error")
    
    return redirect(url_for("admin.reviews"))


@admin_bp.route("/reviews/toggle_landing", methods=["POST"])
@admin_required
def toggle_landing_review():
    """Toggle whether a review is shown on landing page"""
    from models.rating import rating_model
    
    rating_id = int(request.form.get("rating_id", 0))
    # Checkbox sends "on" if checked, nothing if unchecked. Logic needs careful handling if standard form submit.
    # However, for toggle buttons often usually easiest to send a specific value.
    # Let's assume the frontend sends "true" or "false" via AJAX or a specific value.
    # Actually for a simple form post, let's use a hidden input or button value.
    # Let's say the button sends the DESIRED state.
    
    target_state = request.form.get("state") == "true"
    
    if not rating_id:
        flash("Virheellinen tunniste", "error")
        return redirect(url_for("admin.reviews"))
        
    success, error = rating_model.toggle_landing_visibility(rating_id, target_state)
    
    if success:
        state_text = "lisätty etusivulle" if target_state else "poistettu etusivulta"
        flash(f"Arvostelu {state_text}", "success")
    else:
        flash(error or "Päivitys epäonnistui", "error")
        
    return redirect(url_for("admin.reviews"))


