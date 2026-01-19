import os
import secrets
import datetime
import requests
import uuid
import re
from zoneinfo import ZoneInfo

from flask import Flask, request, redirect, url_for, session, abort, jsonify, flash, render_template, Response
from werkzeug.security import generate_password_hash
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

# Import new service layer
from services.auth_service import auth_service
from services.order_service import order_service
from services.image_service import image_service
from services.email_service import email_service
from utils.formatters import format_helsinki_time
from typing import Any, Dict, Optional
from utils.rate_limiter import check_rate_limit

# Import modern next_id for consistent counter usage
from models.database import next_id, db_manager

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "carrental") # käytetään MongoDB:n kantanimenä

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI puuttuu (aseta ympäristömuuttuja).")

_mclient = MongoClient(MONGODB_URI)
_mdb = _mclient[DB_NAME]

def mongo_db():
    return _mdb

def users_col():
    return _mdb["users"]

def orders_col():
    return _mdb["orders"]

def counters_col():
    return _mdb["counters"]

sys.modules['app'] = sys.modules[__name__]

# ----------------- CONFIG -----------------
DB_HOST = os.getenv("DB_HOST", "localhost")
# DB_NAME already defined above for MongoDB
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "Salasana1")

BASE_FEE = float(os.getenv("BASE_FEE", "49"))
PER_KM = float(os.getenv("PER_KM", "1.20"))
VAT_RATE = float(os.getenv("VAT_RATE", "0.255"))  # 25.5% Finnish VAT
# --- Your business pricing anchors ---
# All prices below are NET prices (excl. VAT). VAT will be added on top.
METRO_CITIES = {"helsinki", "espoo", "vantaa", "kauniainen"}
METRO_NET = float(os.getenv("METRO_NET", "27"))  # Net price for metro area
MID_KM = 170.0  # "about 150–200 km"
MID_NET = float(os.getenv("MID_NET", "81"))  # Net price for mid-distance
LONG_KM = 600.0
LONG_NET = float(os.getenv("LONG_NET", "207"))  # Net price for long-distance
ROUNDTRIP_DISCOUNT = 0.30  # 30% off return leg

SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
SEED_ADMIN_PASS = os.getenv("SEED_ADMIN_PASS", "admin123")
SEED_ADMIN_NAME = os.getenv("SEED_ADMIN_NAME", "Admin")

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

# Image upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'orders')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_WIDTH = 1200
IMAGE_QUALITY = 80

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))

# Session configuration for "remember me" functionality
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Prefer secure cookies; allow opt-out for local HTTP via env flag
app.config['SESSION_COOKIE_SECURE'] = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
app.config['REMEMBER_COOKIE_SECURE'] = app.config['SESSION_COOKIE_SECURE']


@app.after_request
def set_security_headers(resp: Response) -> Response:
    # Conservative defaults; allow inline assets for existing templates
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; img-src 'self' https: data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return resp

# Configure email service
mail = email_service.configure_mail(app)
# --- Compat: pudota tuntematon 'partitioned' kwarg vanhasta Werkzeugista ---
try:
    from flask import Response as _FlaskResponse
    _orig_set_cookie = _FlaskResponse.set_cookie
    _orig_delete_cookie = _FlaskResponse.delete_cookie

    def _set_cookie_compat(self, *args, **kwargs):
        kwargs.pop('partitioned', None)
        return _orig_set_cookie(self, *args, **kwargs)

    def _delete_cookie_compat(self, *args, **kwargs):
        kwargs.pop('partitioned', None)
        return _orig_delete_cookie(self, *args, **kwargs)

    _FlaskResponse.set_cookie = _set_cookie_compat
    _FlaskResponse.delete_cookie = _delete_cookie_compat
except Exception:
    pass

# Import new order wizard (template-based, v2)
import order_wizard_new


# ----------------- DB HELPERS -----------------

def init_db():
    # indeksit
    users_col().create_index("email", unique=True)
    users_col().create_index("id", unique=True)

    orders_col().create_index([("id", 1)], unique=True)
    orders_col().create_index([("user_id", 1)])
    orders_col().create_index([("status", 1), ("id", -1)])

    # Sync counters with existing data to prevent duplicate key errors
    print("Syncing counters with existing data...")
    try:
        db_manager.sync_counter("users", "users", "id")
        db_manager.sync_counter("orders", "orders", "id")
        db_manager.sync_counter("driver_applications", "driver_applications", "id")
        db_manager.sync_counter("discounts", "discounts", "id")
    except Exception as e:
        print(f"Warning: Counter sync failed (may be concurrent initialization): {e}")

def seed_admin():
    if not users_col().find_one({"email": SEED_ADMIN_EMAIL}):
        users_col().insert_one({
            "id": next_id("users"),
            "name": SEED_ADMIN_NAME,
            "email": SEED_ADMIN_EMAIL,
            "password_hash": generate_password_hash(SEED_ADMIN_PASS),
            "role": "admin",
            "status": "active",  # Admin is always active
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        })

def seed_test_driver():
    """Seed test driver users for development"""
    test_drivers = [
        {
            "email": "kuljettaja@levoro.fi",
            "name": "Testi Kuljettaja",
            "password": "kuljettaja123"
        },
        {
            "email": "kuljettaja2@levoro.fi",
            "name": "Matti Virtanen",
            "password": "kuljettaja123"
        }
    ]

    for driver_data in test_drivers:
        if not users_col().find_one({"email": driver_data["email"]}):
            users_col().insert_one({
                "id": next_id("users"),
                "name": driver_data["name"],
                "email": driver_data["email"],
                "password_hash": generate_password_hash(driver_data["password"]),
                "role": "driver",
                "status": "active",  # Driver is active by default for testing
                "created_at": datetime.datetime.now(datetime.timezone.utc),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
            })
            print(f"Test driver created: {driver_data['email']} / {driver_data['password']}")
        else:
            print(f"Test driver already exists: {driver_data['email']}")

def migrate_images_to_array():
    """Migrate existing single image structure to array-based structure"""
    print("Starting image structure migration...")

    # Find all orders with the old image structure (single image objects)
    orders_with_old_images = orders_col().find({
        "$or": [
            {"images.pickup": {"$exists": True, "$not": {"$type": "array"}}},
            {"images.delivery": {"$exists": True, "$not": {"$type": "array"}}}
        ]
    })

    migrated_count = 0
    for order in orders_with_old_images:
        order_id = order["id"]
        images = order.get("images", {})

        # Prepare new image structure
        new_images = {}

        # Migrate pickup image if it exists
        if "pickup" in images and images["pickup"] and not isinstance(images["pickup"], list):
            pickup_img = images["pickup"]
            pickup_img["id"] = str(uuid.uuid4())  # Add unique ID
            pickup_img["order"] = 1  # Set as first image
            new_images["pickup"] = [pickup_img]  # Convert to array

        # Migrate delivery image if it exists
        if "delivery" in images and images["delivery"] and not isinstance(images["delivery"], list):
            delivery_img = images["delivery"]
            delivery_img["id"] = str(uuid.uuid4())  # Add unique ID
            delivery_img["order"] = 1  # Set as first image
            new_images["delivery"] = [delivery_img]  # Convert to array

        # Update the order with new structure
        if new_images:
            orders_col().update_one(
                {"id": order_id},
                {"$set": {"images": {**images, **new_images}}}
            )
            migrated_count += 1

    print(f"Migration completed. {migrated_count} orders migrated to new image structure.")


# ----------------- BUSINESS LOGIC -----------------

# Business logic functions moved to OrderService


# Pricing and geocoding functions moved to OrderService


# Image utility functions moved to ImageService


# ----------------- AUTH UTILS -----------------

def translate_status(status):
    """Translate English status to Finnish"""
    from utils.status_translations import translate_status as translate
    return translate(status)

def get_status_description(status):
    """Get user-friendly status description"""
    from utils.status_translations import get_status_description as get_desc
    return get_desc(status)

# Register status translation filters
@app.template_filter('translate_status')
def translate_status_filter(status):
    """Template filter to translate order status to Finnish"""
    return translate_status(status)

@app.template_filter('get_status_description')
def get_status_description_filter(status):
    """Template filter to get status description"""
    return get_status_description(status)

def format_helsinki_time(dt: Any) -> str:
    """Format datetime to Helsinki timezone string"""
    if dt is None:
        return 'Tuntematon'

    # If it's a string, return as-is
    if isinstance(dt, str):
        return dt

    # If it's not a datetime object, return as string
    if not hasattr(dt, 'strftime'):
        return str(dt)

    try:
        helsinki_tz = ZoneInfo("Europe/Helsinki")

        # If datetime is naive (no timezone info), assume it's UTC and convert
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)

        # Convert to Helsinki timezone
        helsinki_dt = dt.astimezone(helsinki_tz)

        # Format as Finnish time
        return helsinki_dt.strftime('%d.%m.%Y %H:%M')

    except Exception as e:
        # Fallback to original formatting if conversion fails
        return dt.strftime('%d.%m.%Y %H:%M') if hasattr(dt, 'strftime') else str(dt)

# Register template filter for timezone conversion
@app.template_filter('helsinki_time')
def helsinki_time_filter(dt):
    """Template filter to convert datetime to Helsinki timezone"""
    return format_helsinki_time(dt)

@app.template_filter('finnish_date')
def finnish_date_filter(date_value: object):
    """Format date string to Finnish style DD.MM.YYYY"""
    if not date_value:
        return ''
    
    # Handle different input formats
    try:
        from datetime import datetime, date
        
        # If it's already a string in DD.MM.YYYY format, return it
        if isinstance(date_value, str) and '.' in date_value and len(date_value.split('.')) == 3:
            return date_value
        
        # If it's a datetime object
        if isinstance(date_value, (datetime, date)):
            return date_value.strftime('%d.%m.%Y')
        
        # Try to parse various date formats
        for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%Y/%m/%d']:
            try:
                dt = datetime.strptime(str(date_value), fmt)
                return dt.strftime('%d.%m.%Y')
            except ValueError:
                continue
        
        # If all else fails, return the original string
        return str(date_value)
    except Exception as e:
        return str(date_value) if date_value else ''

@app.template_filter('extract_city')
def extract_city_filter(address):
    """Extract city name from full address"""
    if not address or not isinstance(address, str):
        return 'Tuntematon kaupunki'

    address = address.strip()

    # 1. Look for standard Finnish pattern: 5 digits + City
    # e.g. "00100 Helsinki", "33100 Tampere"
    match = re.search(r'\b(\d{5})\s+([A-Za-zäöåÄÖÅ\-\s]+)', address)
    if match:
        city_candidate = match.group(2).strip()
        # Filter out common false positives if any, though regex is fairly specific
        return city_candidate

    # 2. If there are no digits in the entire string, assume it is just the city name
    # e.g. "Helsinki", "Turku"
    if not re.search(r'\d', address):
        return address

    # 3. Fallback for comma separated values: "Street 1, City"
    parts = [p.strip() for p in address.split(',')]
    if len(parts) > 1:
        # Check parts from the end (ignoring country if present)
        for part in reversed(parts):
            if part.lower() in ['finland', 'suomi', 'fi']:
                continue
            # If part has no digits, it might be the city
            if not re.search(r'\d', part):
                return part

    return 'Tuntematon kaupunki'

@app.template_filter('format_price_with_vat')
def format_price_with_vat_filter(gross_price):
    """Format price with VAT breakdown - shows net price (ALV 0%) prominently with gross price below"""
    if not gross_price or gross_price <= 0:
        return '<span class="price-main">0,00 €</span>'

    # Calculate net and VAT from gross
    net = gross_price / (1 + VAT_RATE)

    # Format with Finnish number formatting (comma as decimal separator)
    net_str = f"{net:.2f}".replace('.', ',')
    gross_str = f"{gross_price:.2f}".replace('.', ',')

    # Return HTML with semantic classes (no inline styles)
    return f'''<div class="price-breakdown">
        <div class="price-main">
            <span class="price-amount">{net_str} €</span>
            <span class="price-vat-label">ALV 0%</span>
        </div>
        <div class="price-vat-info">Hinta sis. ALV = {gross_str} €</div>
    </div>'''

def current_user():
    """Get current user - using auth service"""
    return auth_service.get_current_user()

@app.context_processor
def inject_admin_notifications():
    """Inject admin notification counts into all templates"""
    user = current_user()
    
    # Only load for admin users
    if not user or user.get('role') != 'admin':
        return {'admin_notifications': None}
    
    try:
        from datetime import datetime, timezone
        
        # Get last viewed timestamps from session
        last_viewed_orders = session.get('admin_last_viewed_orders')
        last_viewed_reviews = session.get('admin_last_viewed_reviews')
        last_viewed_applications = session.get('admin_last_viewed_applications')
        
        # Count new orders created after last view
        orders_query: Dict[str, Any] = {'status': 'NEW'}
        if last_viewed_orders is not None:
            orders_query = {**orders_query, 'created_at': {'$gt': last_viewed_orders}}
        new_orders_count = orders_col().count_documents(orders_query)
        
        # Count pending reviews created after last view
        from models.rating import rating_model
        reviews_query: Dict[str, Any] = {'status': 'pending'}
        if last_viewed_reviews is not None:
            reviews_query = {**reviews_query, 'created_at': {'$gt': last_viewed_reviews}}
        pending_reviews_count = len(list(rating_model.find(reviews_query)))
        
        # Count pending applications created after last view
        from models.driver_application import driver_application_model
        apps_query: Dict[str, Any] = {'status': 'pending'}
        if last_viewed_applications is not None:
            apps_query = {**apps_query, 'created_at': {'$gt': last_viewed_applications}}
        pending_applications_count = driver_application_model.count_documents(apps_query)
        
        return {
            'admin_notifications': {
                'new_orders': new_orders_count,
                'pending_reviews': pending_reviews_count,
                'pending_applications': pending_applications_count
            }
        }
    except Exception as e:
        print(f"Error loading admin notifications: {e}")
        return {'admin_notifications': None}

# Template global removed - current_user now passed explicitly in blueprint routes



def admin_required():
    u = current_user()
    if not u or u["role"] != "admin":
        abort(403)


# ----------------- LAYOUT -----------------
PAGE_HEAD = """
<!doctype html><html lang="fi"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Autonkuljetus – Portaali</title>
<link
  rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
  crossorigin=""
/>
<script
  src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
  crossorigin=""
></script>
__GOOGLE_MAPS_SCRIPT__
<link rel="stylesheet" href="__CSS_MAIN__">
</head><body>
<header class="header">
  <div class="container">
    <div class="header-inner">
      <div class="brand">
        <a href="/" class="brand-link" aria-label="Etusivu">
          <img src="__LOGO__" alt="" class="brand-logo">
        </a>
      </div>
      <button class="mobile-menu-toggle" aria-label="Avaa menu" id="mobile-menu-toggle">
        <span></span>
        <span></span>
        <span></span>
      </button>
      <nav class="nav" id="nav-menu">
        <a href="/" class="nav-link">Etusivu</a>
        __USER_LINKS__
        __ADMIN__
        __AUTH__
      </nav>
    </div>
  </div>
</header>
<main>
"""

PAGE_FOOT = """
</main>
<footer class="footer">
  <div class="container">
    <div class="footer-inner">
      <div class="text-center">
        __FOOTER_CALCULATOR__
        <p style="margin: 0; opacity: 0.8;">© 2026 Levoro - Tiyouba Oy</p>
      </div>
    </div>
  </div>
</footer>
<script src="/static/js/core/navigation.js"></script>
<script>
// Ensure NavigationManager is initialized and toggle works
if (typeof window.navigationManager === 'undefined') {
    window.navigationManager = new NavigationManager();
}
function toggleMobileMenu() {
    if (window.navigationManager) {
        window.navigationManager.toggleMobileMenu();
    } else {
        // Fallback inline toggle
        const nav = document.getElementById('nav-menu');
        const toggle = document.querySelector('.mobile-menu-toggle');
        if (nav && toggle) {
            nav.classList.toggle('mobile-open');
            toggle.classList.toggle('active');
        }
    }
}
</script>
</body></html>
"""


def wrap(content: str, user=None):
    # Yläpalkin oikea reuna: kirjautumislinkit tai käyttäjän nimi + ulos
    if user is None:
        auth = "<a href='/login' class='nav-link'>Kirjaudu</a> <a href='/register' class='nav-link'>Luo tili</a>"
    else:
        auth = f"<span class='pill'>Hei, {user['name']}</span> <a class='nav-link' href='/logout'>Kirjaudu ulos</a>"

    # Logo ja role-based navigation
    from flask import url_for, get_flashed_messages
    logo_src = url_for('static', filename='LevoroLogo.png')

    # Build role-based navigation links
    user_links = ""
    admin_link = ""

    if user:
        if user.get("role") == "driver":
            user_links = '<a href="/driver/dashboard" class="nav-link">Kuljettajan sivu</a>'
        elif user.get("role") == "admin":
            # Admin users don't need Oma sivu link
            admin_link = '<a href="/admin" class="nav-link">Admin</a>'
        else:
            # Regular users get Uusi tilaus and Oma sivu links
            user_links = '<a href="/order/new/step1" class="nav-link">Uusi tilaus</a><a href="/dashboard" class="nav-link">Tilaukset</a>'
    else:
        # Non-authenticated users can see Uusi tilaus
        user_links = '<a href="/order/new/step1" class="nav-link">Uusi tilaus</a>'

    # Google Maps script if API key is available
    google_script = ""
    if GOOGLE_PLACES_API_KEY:
        google_script = f'<script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_PLACES_API_KEY}&libraries=places&loading=async" async defer></script>'

    # Footer calculator button based on authentication
    if user is None:
        footer_calculator = '<div class="footer-cta" style="margin-bottom: 1rem;"><a href="/register" class="btn btn-primary">Kirjaudu ja laske hinta</a></div>'
    else:
        footer_calculator = '<div class="footer-cta" style="margin-bottom: 1rem;"><a href="/calculator" class="btn btn-primary">Laske hinta</a></div>'

    # Flash messages
    flash_html = ""
    messages = get_flashed_messages(with_categories=True)
    if messages:
        flash_html = '<div class="flash-messages container" style="margin-top: 20px;">'
        for category, message in messages:
            flash_html += f'<div class="flash-message {category}">{message}</div>'
        flash_html += '</div>'

    # Kootaan head
    head = (
        PAGE_HEAD
        .replace('__LOGO__', logo_src)
        .replace('__USER_LINKS__', user_links)
        .replace('__ADMIN__', admin_link)
        .replace('__AUTH__', auth)
        .replace('__CSS_MAIN__', url_for('static', filename='css/main.css'))
        .replace('__GOOGLE_MAPS_SCRIPT__', google_script)
    )

    # Kootaan footer
    foot = (
        PAGE_FOOT
        .replace("__FOOTER_CALCULATOR__", footer_calculator)
    )

    return head + flash_html + content + foot


def render_with_context(template_name, **kwargs):
    """Render template with common context variables"""
    user = current_user()
    context = {
        'current_user': user,
        'google_places_api_key': GOOGLE_PLACES_API_KEY if GOOGLE_PLACES_API_KEY else None,
        **kwargs
    }
    return render_template(template_name, **context)


# ----------------- ROUTES: HOME -----------------
# Legacy home route removed - now handled by main.py blueprint




# ----------------- AUTH -----------------
# /register route removed - now handled by auth.py blueprint



@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.post("/api/places_autocomplete")
def api_places_autocomplete():
    """Google Places Autocomplete API endpoint"""
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Query required"}), 400

    # Check if Google Places API key is configured
    if not GOOGLE_PLACES_API_KEY:
        return jsonify({"error": "Google Places API key not configured"}), 500

    try:
        # Google Places Autocomplete API request
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": query,
            "key": GOOGLE_PLACES_API_KEY,
            "components": "country:FI",  # Restrict to Finland (uppercase country code)
            "language": "fi",
            "types": "address",  # Only address type to avoid API conflicts
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK":
            return jsonify({
                "predictions": data.get("predictions", []),
                "status": data.get("status"),
                "source": "google"
            })
        else:
            error_msg = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            return jsonify({"error": error_msg}), 500

    except requests.exceptions.RequestException as e:
        error_msg = f"HTTP request failed: {str(e)}"
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_msg = f"Google Places API failed: {str(e)}"
        return jsonify({"error": error_msg}), 500

@app.post("/api/route_geo")
def api_route_geo():
    data = request.get_json(force=True, silent=True) or {}
    pickup = (data.get("pickup") or "").strip()
    dropoff = (data.get("dropoff") or "").strip()
    pickup_place_id = (data.get("pickup_place_id") or "").strip()
    dropoff_place_id = (data.get("dropoff_place_id") or "").strip()
    if not pickup or not dropoff:
        return jsonify({"error": "Lahto- ja kohdeosoite vaaditaan"}), 400

    try:
        route = order_service.get_route(pickup, dropoff, pickup_place_id, dropoff_place_id)
        return jsonify({
            "km": round(route.get("distance_km", 0.0), 2),
            "latlngs": route.get("latlngs", []),
            "start": route.get("start"),
            "end": route.get("end"),
            "provider": route.get("provider", "osrm")
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Unexpected error in route_geo: {str(e)}")
        return jsonify({"error": "Karttapalvelu ei ole saatavilla juuri nyt, yrita hetken kuluttua uudestaan"}), 503


# /login route removed - now handled by auth.py blueprint



# ----------------- DASHBOARD -----------------
# Legacy dashboard route removed - now handled by main.py blueprint





@app.get("/order/<int:order_id>")
def order_view(order_id: int):
    u = current_user()
    if not u:
        return redirect(url_for("auth.login", next=f"/order/{order_id}"))

    # Get order with driver information
    from models.order import order_model
    pipeline = [
        {"$match": {"id": int(order_id), "user_id": int(u["id"])}},
        {"$lookup": {
            "from": "users",
            "localField": "driver_id",
            "foreignField": "id",
            "as": "driver"
        }},
        {"$unwind": {"path": "$driver", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "id": 1, "status": 1, "user_id": 1,
            "pickup_address": 1, "dropoff_address": 1,
            "distance_km": 1, "price_gross": 1,
            "reg_number": 1, "winter_tires": 1, "pickup_date": 1, "last_delivery_date": 1,
            "pickup_time": 1, "delivery_time": 1,
            "extras": 1, "images": 1, "customer_name": 1,
            "email": 1, "phone": 1,
            "orderer_name": 1, "orderer_email": 1, "orderer_phone": 1,
            "customer_phone": 1,
            "assigned_at": 1, "arrival_time": 1,
            "pickup_started": 1, "delivery_completed": 1,
            "created_at": 1, "updated_at": 1,
            "driver_name": "$driver.name",
            "driver_email": "$driver.email",
            "driver_phone": "$driver.phone"
        }}
    ]

    order_result = list(orders_col().aggregate(pipeline))
    r = order_result[0] if order_result else None
    if not r:
        return render_with_context('errors/no_access.html')

    def filter_customer_images(images):
        if not images:
            return {}

        filtered = {}
        for image_type, type_images in images.items():
            if not isinstance(type_images, list):
                type_images = [type_images] if type_images else []

            filtered[image_type] = [
                img for img in type_images
                if not isinstance(img, dict) or img.get("visible_to_customer", True)
            ]

        return filtered

    r["images"] = filter_customer_images(r.get("images", {}))

    # numerot tulostusta varten
    distance_km = float(r.get("distance_km", 0.0))
    price_gross = float(r.get("price_gross", 0.0))

    current_status = r.get("status", "NEW")
    step = progress_step(current_status)

    # Enhanced progress bar with detailed status tracking
    def get_detailed_progress_html(status, step):
        # 5-step progress with correct labels
        statuses = [
            {"key": "NEW", "label": "Tilaus luotu", "group": ["NEW"]},
            {"key": "CONFIRMED", "label": "Vahvistettu", "group": ["CONFIRMED"]},
            {"key": "ASSIGNED_TO_DRIVER", "label": "Noudossa", "group": ["ASSIGNED_TO_DRIVER", "DRIVER_ARRIVED", "PICKUP_IMAGES_ADDED"]},
            {"key": "IN_TRANSIT", "label": "Kuljetuksessa", "group": ["IN_TRANSIT", "DELIVERY_ARRIVED", "DELIVERY_IMAGES_ADDED"]},
            {"key": "DELIVERED", "label": "Toimitettu", "group": ["DELIVERED"]}
        ]

        # Find current step based on status
        current_step = 0
        for i, step_info in enumerate(statuses):
            if status in step_info["group"]:
                current_step = i
                break

        html_parts = ['<div class="simple-progress">']

        for i, step_info in enumerate(statuses):
            is_completed = i < current_step or (i == current_step and status == "DELIVERED")
            is_current = i == current_step and status != "DELIVERED"

            step_classes = ["progress-step"]
            if is_completed:
                step_classes.append("completed")
            elif is_current:
                step_classes.append("current")

            html_parts.append(f'<div class="{" ".join(step_classes)}">')
            html_parts.append(f'<div class="step-circle">{i + 1}</div>')
            html_parts.append(f'<div class="step-title">{step_info["label"]}</div>')
            html_parts.append('</div>')

            # Add connector line (except for last item)
            if i < len(statuses) - 1:
                line_class = "progress-connector completed" if is_completed else "progress-connector"
                html_parts.append(f'<div class="{line_class}"></div>')

        html_parts.append('</div>')

        # Add current status description
        status_description = get_status_description(status)
        html_parts.append(f'<div class="current-status-description">{status_description}</div>')

        return "".join(html_parts)

    progress_bar = get_detailed_progress_html(current_status, step)

    status_fi = translate_status(r.get('status', 'NEW'))
    status_description = get_status_description(r.get('status', 'NEW'))
    
    # Format dates to Finnish format
    pickup_date_raw = r.get('pickup_date', None)
    last_delivery_date_raw = r.get('last_delivery_date', None)
    pickup_time = (r.get('pickup_time') or '').strip()
    delivery_time = (r.get('delivery_time') or '').strip()
    
    # Calculate estimated days between pickup and delivery
    estimated_days = None
    if pickup_date_raw and last_delivery_date_raw:
        try:
            # Handle both datetime and date objects
            from datetime import datetime, date
            if hasattr(pickup_date_raw, 'date'):
                pickup_dt = pickup_date_raw.date() if isinstance(pickup_date_raw, datetime) else pickup_date_raw
            elif isinstance(pickup_date_raw, str):
                pickup_dt = datetime.strptime(pickup_date_raw, '%Y-%m-%d').date()
            else:
                pickup_dt = pickup_date_raw
                
            if hasattr(last_delivery_date_raw, 'date'):
                delivery_dt = last_delivery_date_raw.date() if isinstance(last_delivery_date_raw, datetime) else last_delivery_date_raw
            elif isinstance(last_delivery_date_raw, str):
                delivery_dt = datetime.strptime(last_delivery_date_raw, '%Y-%m-%d').date()
            else:
                delivery_dt = last_delivery_date_raw
                
            estimated_days = (delivery_dt - pickup_dt).days
        except Exception as e:
            print(f"Error calculating estimated days: {e}")
            estimated_days = None
    
    # Format dates for display (handle both datetime objects and strings)
    from datetime import datetime
    
    def format_date_fi(date_val):
        """Convert date to Finnish format DD.MM.YYYY"""
        if not date_val:
            return None
        # If it's a datetime/date object
        if hasattr(date_val, 'strftime'):
            return date_val.strftime('%d.%m.%Y')
        # If it's a string in ISO format (YYYY-MM-DD)
        if isinstance(date_val, str):
            try:
                # Try to parse ISO format
                parsed = datetime.strptime(date_val, '%Y-%m-%d')
                return parsed.strftime('%d.%m.%Y')
            except ValueError:
                # Try DD.MM.YYYY format (already Finnish)
                try:
                    datetime.strptime(date_val, '%d.%m.%Y')
                    return date_val  # Already in correct format
                except ValueError:
                    return date_val  # Return as-is if can't parse
        return str(date_val) if date_val else None
    
    pickup_date_fi = format_date_fi(pickup_date_raw)
    last_delivery_date_fi = format_date_fi(last_delivery_date_raw)

    # Smart content logic
    has_reg_number = bool(r.get('reg_number', '').strip())
    has_winter_tires = r.get('winter_tires') is not None
    has_customer_info = bool(
        r.get('customer_name', '').strip() or r.get('email', '').strip() or r.get('phone', '').strip() or
        r.get('orderer_name', '').strip() or r.get('orderer_email', '').strip() or r.get('orderer_phone', '').strip() or
        r.get('customer_phone', '').strip()
    )
    has_images = any(
        r.get('images', {}).get(image_type) for image_type in ["pickup", "delivery", "receipts"]
    )

    # Show vehicle section only if there's meaningful data
    show_vehicle_section = has_reg_number or has_winter_tires

    # Check rating status for delivered orders
    can_rate = False
    existing_rating = None
    if current_status == 'DELIVERED':
        from models.rating import rating_model
        existing_rating = rating_model.get_order_rating(int(order_id))
        if not existing_rating:
            can_rate = True

    return render_with_context('dashboard/order_view.html',
        order=r,
        distance_km=distance_km,
        price_gross=price_gross,
        progress_bar=progress_bar,
        status_fi=status_fi,
        status_description=status_description,
        pickup_date_fi=pickup_date_fi,
        last_delivery_date_fi=last_delivery_date_fi,
        pickup_time=pickup_time,
        delivery_time=delivery_time,
        estimated_days=estimated_days,
        has_reg_number=has_reg_number,
        has_winter_tires=has_winter_tires,
        has_customer_info=has_customer_info,
        has_images=has_images,
        show_vehicle_section=show_vehicle_section,
        can_rate=can_rate,
        existing_rating=existing_rating
    )


@app.get("/order/<int:order_id>/invoice")
def invoice_view(order_id: int):
    u = current_user()
    if not u:
        return redirect(url_for("auth.login", next=f"/order/{order_id}/invoice"))

    # Reuse aggregation logic (simplified for invoice)
    from models.order import order_model
    from datetime import datetime, timedelta
    
    # Simple find first to check access
    r = orders_col().find_one({"id": int(order_id), "user_id": int(u["id"])})
    if not r:
        return render_with_context('errors/no_access.html')

    # Calculate pricing
    price_gross = float(r.get("price_gross", 0.0))
    vat_rate = 0.24 # hardcoded or from config
    net_price = price_gross / (1 + vat_rate)
    final_vat = price_gross - net_price
    
    # Dates
    issue_date = datetime.now().strftime("%d.%m.%Y")
    due_date = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y")
    
    # Delivery date fallback
    delivery_date_raw = r.get("pickup_date")
    if delivery_date_raw:
        if isinstance(delivery_date_raw, str):
             # Try to parse or just use
             delivery_date = delivery_date_raw
        else:
             delivery_date = delivery_date_raw.strftime("%d.%m.%Y")
    else:
        delivery_date = issue_date

    return render_template('dashboard/invoice_view.html',
        order=r,
        net_price=net_price,
        final_vat=final_vat,
        final_gross=price_gross,
        issue_date=issue_date,
        due_date=due_date,
        delivery_date=delivery_date
    )


@app.get("/order/<int:order_id>/receipt")
def receipt_view(order_id: int):
    """Customer receipt - similar to invoice but without payment info"""
    u = current_user()
    if not u:
        return redirect(url_for("auth.login", next=f"/order/{order_id}/receipt"))

    from datetime import datetime
    
    r = orders_col().find_one({"id": int(order_id), "user_id": int(u["id"])})
    if not r:
        return render_with_context('errors/no_access.html')

    # Calculate pricing with 25.5% VAT (Finnish standard rate)
    price_gross = float(r.get("price_gross", 0.0))
    vat_rate = 0.255
    net_price = price_gross / (1 + vat_rate)
    final_vat = price_gross - net_price
    
    # Dates
    issue_date = datetime.now().strftime("%d/%m/%Y")
    
    # Delivery date fallback
    delivery_date_raw = r.get("pickup_date")
    if delivery_date_raw:
        if isinstance(delivery_date_raw, str):
            delivery_date = delivery_date_raw
        else:
            delivery_date = delivery_date_raw.strftime("%d/%m/%Y")
    else:
        delivery_date = issue_date

    return render_template('dashboard/receipt_view.html',
        order=r,
        net_price=net_price,
        final_vat=final_vat,
        final_gross=price_gross,
        issue_date=issue_date,
        delivery_date=delivery_date
    )


# ----------------- ADMIN -----------------
# Legacy admin route removed - now handled by main.py blueprint
















@app.get("/order/new")
def order_new_redirect():
    u = current_user()
    if not u:
        return redirect(url_for("auth.login", next="/order/new/step1"))
    return redirect("/order/new/step1")


def progress_step(status: str) -> int:
    # 3-vaiheinen palkki: 1=Noudettu, 2=Kuljetuksessa, 3=Toimitettu
    status = (status or "").upper()
    mapping = {
        "NEW": 0,                      # uusi tilaus, ei vielä noudettu
        "CONFIRMED": 0,                # vahvistettu, odottaa kuljettajaa
        "ASSIGNED_TO_DRIVER": 0,       # kuljettaja määritetty, matkalla
        "DRIVER_ARRIVED": 1,           # kuljettaja saapunut
        "PICKUP_IMAGES_ADDED": 1,      # noudettu
        "IN_TRANSIT": 2,               # kuljetuksessa
        "DELIVERY_ARRIVED": 2,         # saapunut kohteeseen
        "DELIVERY_IMAGES_ADDED": 2,    # valmis luovutukseen
        "DELIVERED": 3,                # toimitettu
        "CANCELLED": 0                 # peruttu -> ei edistystä
    }
    return mapping.get(status, 0)


def is_active_status(status: str) -> bool:
    return (status or "").upper() in (
        "NEW", "CONFIRMED", "ASSIGNED_TO_DRIVER", "DRIVER_ARRIVED",
        "PICKUP_IMAGES_ADDED", "IN_TRANSIT", "DELIVERY_ARRIVED", "DELIVERY_IMAGES_ADDED"
    )


# ----------------- API -----------------
@app.post("/api/quote_for_addresses")
def api_quote_for_addresses():
    user = auth_service.get_current_user()
    if not user:
        return jsonify({"error": "Kirjaudu sisään käyttääksesi hintalaskuria"}), 401

    allowed, retry_after = check_rate_limit(f"quote:{request.remote_addr}", limit=20, window_seconds=60, lockout_seconds=300)
    if not allowed:
        return jsonify({"error": "Liikaa pyyntöjä, yritä hetken kuluttua"}), 429

    payload = request.get_json(force=True, silent=True) or {}
    pickup = payload.get("pickup", "").strip()
    dropoff = payload.get("dropoff", "").strip()
    pickup_place_id = (payload.get("pickup_place_id") or "").strip()
    dropoff_place_id = (payload.get("dropoff_place_id") or "").strip()
    # NOTE: return_leg parameter exists but is not used in the current UI
    return_leg = bool(payload.get("return_leg", False))  # optional flag
    if not pickup or not dropoff:
        return jsonify({"error": "Lähtö- ja kohdeosoite vaaditaan"}), 400

    try:
        km = order_service.route_km(pickup, dropoff, pickup_place_id, dropoff_place_id)

        # Determine current user and first-order info for personalized discounts
        user_id = int(user["id"]) if user and user.get("id") else None
        is_first_order = False
        if user_id:
            try:
                existing_orders = order_service.get_user_orders(user_id, limit=1)
                is_first_order = len(existing_orders) == 0
            except Exception as e:
                print(f"Failed to determine first-order status for quote: {e}")

        pricing = order_service.price_from_km_with_discounts(
            km,
            pickup_addr=pickup,
            dropoff_addr=dropoff,
            return_leg=return_leg,
            user_id=user_id,
            promo_code=payload.get("promo_code"),
            is_first_order=is_first_order
        )

        response = {
            "km": round(km, 2),
            "net": pricing.get("final_net", 0.0),
            "vat": pricing.get("final_vat", 0.0),
            "gross": pricing.get("final_gross", 0.0),
            "details": pricing.get("details"),
            "original_net": pricing.get("original_net", pricing.get("final_net", 0.0)),
            "original_vat": pricing.get("original_vat", pricing.get("final_vat", 0.0)),
            "original_gross": pricing.get("original_gross", pricing.get("final_gross", 0.0)),
            "display_original_net": pricing.get("display_original_net", pricing.get("original_net", pricing.get("final_net", 0.0))),
            "display_original_vat": pricing.get("display_original_vat", pricing.get("original_vat", pricing.get("final_vat", 0.0))),
            "display_original_gross": pricing.get("display_original_gross", pricing.get("original_gross", pricing.get("final_gross", 0.0))),
            "discount_amount": pricing.get("discount_amount", 0.0),
            "applied_discounts": pricing.get("applied_discounts", []),
        }
        return jsonify(response)
    except ValueError as e:
        # These are user-friendly messages from route_km() when routing is unavailable
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        # Unexpected errors - log but don't expose details
        print(f"Unexpected error in quote_for_addresses: {str(e)}")
        return jsonify({"error": "Hintalaskenta ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan"}), 500


@app.get("/api/quote")
def api_quote():
    user = auth_service.get_current_user()
    if not user:
        return jsonify({"error": "Kirjaudu sisään käyttääksesi hintalaskuria"}), 401

    allowed, retry_after = check_rate_limit(f"quote_simple:{request.remote_addr}", limit=30, window_seconds=60, lockout_seconds=300)
    if not allowed:
        return jsonify({"error": "Liikaa pyyntöjä, yritä hetken kuluttua"}), 429

    try:
        km = float(request.args.get("km", "0"))
    except:
        return jsonify({"error": "bad km"}), 400
    net, vat, gross, _ = order_service.price_from_km(km)
    return jsonify({"net": net, "vat": vat, "gross": gross})


# ----------------- SAVED ADDRESSES (server-side persistence) -----------------
PHONE_REGEX = re.compile(r'^[+]?[0-9\s\-()]+$')

def _is_valid_phone(phone_val: str) -> bool:
    """Allow digits, spaces, +, -, and parentheses; empty is ok."""
    if phone_val is None:
        return True
    phone_val = str(phone_val).strip()
    if not phone_val:
        return True
    return bool(PHONE_REGEX.match(phone_val))

def _get_user_required():
    u = current_user()
    if not u:
        abort(401)
    return u

@app.get("/api/saved_addresses")
def api_saved_addresses_list():
    import uuid
    u = _get_user_required()
    user_doc = users_col().find_one({"id": int(u["id"])}, {"_id": 0, "saved_addresses": 1}) or {}
    addrs = list(user_doc.get("saved_addresses") or [])
    
    # Self-healing: Ensure all addresses have IDs
    modified = False
    for a in addrs:
        if not a.get("id") or str(a.get("id")) == "None":
            a["id"] = str(uuid.uuid4())
            modified = True
        else:
            a["id"] = str(a.get("id"))

        # Normalize other fields
        a["displayName"] = a.get("displayName") or a.get("name") or ""
        a["fullAddress"] = a.get("fullAddress") or a.get("address") or ""
        phone_raw = a.get("phone")
        a["phone"] = str(phone_raw).strip() if phone_raw else ""
            
    if modified:
        users_col().update_one({"id": int(u["id"])}, {"$set": {"saved_addresses": addrs}})
        
    return jsonify({"items": addrs})

@app.post("/api/saved_addresses")
def api_saved_addresses_create():
    u = _get_user_required()
    data = request.get_json(force=True, silent=True) or {}
    display = (data.get("displayName") or "").strip()
    full = (data.get("fullAddress") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not display or not full:
        return jsonify({"error": "displayName and fullAddress required"}), 400
    if phone and not _is_valid_phone(phone):
        return jsonify({"error": "invalid phone"}), 400

    import uuid, datetime as _dt
    item = {
        "id": str(uuid.uuid4()),
        "displayName": display,
        "fullAddress": full,
        "phone": phone,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat()
    }

    # Upsert array on user
    doc = users_col().find_one({"id": int(u["id"])}, {"_id": 0, "saved_addresses": 1}) or {}
    arr = list(doc.get("saved_addresses") or [])
    arr.append(item)
    users_col().update_one({"id": int(u["id"])}, {"$set": {"saved_addresses": arr}})
    return jsonify({"item": item})

@app.put("/api/saved_addresses/<addr_id>")
def api_saved_addresses_update(addr_id: str):
    u = _get_user_required()
    data = request.get_json(force=True, silent=True) or {}
    display = (data.get("displayName") or "").strip()
    full = (data.get("fullAddress") or "").strip()
    phone_raw = data.get("phone", None)
    phone = (phone_raw or "").strip() if phone_raw is not None else None
    if not display or not full:
        return jsonify({"error": "displayName and fullAddress required"}), 400
    if phone and not _is_valid_phone(phone):
        return jsonify({"error": "invalid phone"}), 400

    doc = users_col().find_one({"id": int(u["id"])}, {"_id": 0, "saved_addresses": 1}) or {}
    arr = list(doc.get("saved_addresses") or [])
    found = False
    for a in arr:
        if str(a.get("id")) == str(addr_id):
            a["displayName"] = display
            a["fullAddress"] = full
            if phone is not None:
                a["phone"] = phone
            found = True
            break
    if not found:
        return jsonify({"error": "not found"}), 404
    users_col().update_one({"id": int(u["id"])}, {"$set": {"saved_addresses": arr}})
    return jsonify({"item": next(a for a in arr if str(a.get("id")) == str(addr_id))})

@app.delete("/api/saved_addresses/<addr_id>")
def api_saved_addresses_delete(addr_id: str):
    u = _get_user_required()
    doc = users_col().find_one({"id": int(u["id"])}, {"_id": 0, "saved_addresses": 1}) or {}
    arr = list(doc.get("saved_addresses") or [])
    
    new_arr = [a for a in arr if str(a.get("id")) != str(addr_id)]

    if len(new_arr) == len(arr):
        return jsonify({"error": "not found"}), 404
    
    users_col().update_one({"id": int(u["id"])}, {"$set": {"saved_addresses": new_arr}})
    return jsonify({"ok": True})


@app.get("/api/common_additional_info")
def api_common_additional_info():
    """Get user's most commonly used additional_info texts from past orders"""
    u = _get_user_required()
    
    # Find all orders with additional_info for this user
    orders_cursor = orders_col().find(
        {"user_id": int(u["id"]), "additional_info": {"$exists": True, "$ne": ""}},
        {"_id": 0, "additional_info": 1}
    ).sort("id", -1).limit(50)  # Last 50 orders
    
    orders_list = list(orders_cursor)
    
    # Count occurrences of each unique additional_info text
    from collections import Counter
    info_counter = Counter()
    
    for order in orders_list:
        info = order.get("additional_info", "").strip()
        if info:
            # Count full text
            info_counter[info] += 1
            # Also split by newlines to find common phrases
            for line in info.split('\n'):
                line = line.strip()
                if line and len(line) > 3 and line != info:  # Ignore very short phrases and duplicates
                    info_counter[line] += 1
    
    # Get top 6 most common, filter out generic ones already in default suggestions
    default_suggestions = {'aikataulu joustava', 'toimitus on kiireellinen', 'nouto takapihalta', 'soita ennen noutoa'}
    
    common = []
    for text, count in info_counter.most_common(15):
        if text.lower() not in default_suggestions and count >= 2:
            common.append({"text": text})
            if len(common) >= 6:
                break
    
    return jsonify({"items": common})


# ----------------- DRIVER APPLICATION ROUTES -----------------

@app.get("/hae-kuljettajaksi")
def driver_application_form():
    """Display driver application form"""
    return render_template('driver_application.html')


@app.post("/hae-kuljettajaksi")
def submit_driver_application():
    """Process driver application submission"""
    from models.driver_application import driver_application_model
    from services.email_service import email_service
    from services.image_service import image_service
    from services.gcs_service import gcs_service

    # Get form data (no password - admin creates account upon approval)
    application_data = {
        "first_name": (request.form.get("first_name") or "").strip(),
        "last_name": (request.form.get("last_name") or "").strip(),
        "email": (request.form.get("email") or "").strip(),
        "phone": (request.form.get("phone") or "").strip(),
        # New fields
        "birth_date": (request.form.get("birth_date") or "").strip(),
        "street_address": (request.form.get("street_address") or "").strip(),
        "postal_code": (request.form.get("postal_code") or "").strip(),
        "city": (request.form.get("city") or "").strip(),
        "about_me": (request.form.get("about_me") or "").strip(),
        "driving_experience": (request.form.get("driving_experience") or "").strip(),
        "languages": (request.form.get("languages") or "").strip(),
        "terms_accepted": request.form.get("terms_accepted") == "on"
    }
    application_data["name"] = " ".join(
        part for part in [application_data["first_name"], application_data["last_name"]]
        if part
    ).strip()

    # Validate required fields
    required_fields = ["first_name", "last_name", "email", "phone", "birth_date", 
                       "street_address", "postal_code", "city", "about_me"]
    field_labels = {
        "first_name": "Etunimi",
        "last_name": "Sukunimi",
        "email": "Sähköposti",
        "phone": "Puhelinnumero",
        "birth_date": "Syntymäaika",
        "street_address": "Katuosoite",
        "postal_code": "Postinumero",
        "city": "Kaupunki",
        "about_me": "Esittelyteksti"
    }

    for field in required_fields:
        if not application_data.get(field):
            label = field_labels.get(field, field)
            flash(f"Virhe: {label} on pakollinen kenttä", "error")
            return render_template('driver_application.html')

    # Validate terms acceptance
    if not application_data.get("terms_accepted"):
        flash("Virhe: Sinun tulee hyväksyä käyttöehdot", "error")
        return render_template('driver_application.html')

    # Validate license images
    license_front = request.files.get('license_front')
    license_back = request.files.get('license_back')

    if license_front is None or license_front.filename == '':
        flash("Virhe: Ajokortin etupuoli on pakollinen", "error")
        return render_template('driver_application.html')

    if license_back is None or license_back.filename == '':
        flash("Virhe: Ajokortin takapuoli on pakollinen", "error")
        return render_template('driver_application.html')
    assert license_front is not None
    assert license_back is not None

    if not application_data["name"]:
        flash("Virhe: Lisää etu- ja sukunimi", "error")
        return render_template('driver_application.html')

    # Check if application already exists (but allow re-application if user was deleted)
    existing = driver_application_model.find_by_email(application_data["email"])
    if existing:
        # If there's an existing application, check if it's still valid
        # Allow re-application if the previous application was approved BUT the user no longer exists
        # (meaning they were deleted and need to re-register)
        from models.user import user_model
        existing_user = user_model.find_by_email(application_data["email"])

        # If user exists, block duplicate application
        if existing_user:
            flash("Sähköpostiosoite on jo käytössä järjestelmässä", "error")
            return render_template('driver_application.html')

        # If user doesn't exist, this is an orphaned application record
        # Delete it regardless of status to allow re-registration
        # This handles cases where a user was deleted but their application remained
        print(f"Cleaning up orphaned application for {application_data['email']} (status: {existing.get('status')})")
        driver_application_model.delete_one({"id": existing['id']})

        # Note: We no longer block re-registration for pending applications if the user doesn't exist
        # This fixes the issue where deleted users couldn't re-register

    # Create application
    application, error = driver_application_model.create_application(application_data)
    if error is not None:
        flash(f"Virhe hakemuksen lähettämisessä: {error}", "error")
        return render_template('driver_application.html')

    # Process and upload license images
    if application is None:
        flash("Hakemuksen luonti epäonnistui", "error")
        return render_template('driver_application.html')

    application_id = application.get("id")
    if application_id is None:
        flash("Hakemuksen luonti epäonnistui (ID puuttuu)", "error")
        return render_template('driver_application.html')
    license_images: Dict[str, Optional[str]] = {"front": None, "back": None}
    application_dict: Dict[str, Any] = application

    try:
        import uuid
        from werkzeug.utils import secure_filename

        # Process front image
        # Validate file
        front_validation_error = image_service._validate_file(license_front)
        if front_validation_error:
            flash(f"Virhe ajokortin etupuolessa: {front_validation_error}", "error")
            return render_template('driver_application.html')

        # Generate unique filename and save temporarily
        front_extension = image_service._get_file_extension(license_front.filename or "")
        front_unique_filename = f"license_{application_id}_front_{uuid.uuid4().hex}.{front_extension}"
        front_temp_path = os.path.join(image_service.upload_folder, front_unique_filename)
        license_front.save(front_temp_path)

        # Process image with higher quality for license images
        front_processed_path = image_service._process_image(front_temp_path, max_width=None, quality=95)
        if not front_processed_path:
            image_service._cleanup_file(front_temp_path)
            flash("Virhe ajokortin etupuolen käsittelyssä - tarkista että kuva ei ole vioittunut", "error")
            return render_template('driver_application.html')

        # Upload front image to GCS privately
        front_blob_name = f"driver-licenses/{application_id}/front.jpg"
        front_blob, front_upload_error = gcs_service.upload_private_file(
            front_processed_path,
            front_blob_name
        )
        if front_upload_error:
            flash(f"Virhe ajokortin etupuolen tallentamisessa: {front_upload_error}", "error")
            image_service._cleanup_file(front_processed_path)
            return render_template('driver_application.html')

        license_images["front"] = front_blob_name
        image_service._cleanup_file(front_processed_path)  # Clean up temp file

        # Process back image
        # Validate file
        back_validation_error = image_service._validate_file(license_back)
        if back_validation_error:
            flash(f"Virhe ajokortin takapuolessa: {back_validation_error}", "error")
            return render_template('driver_application.html')

        # Generate unique filename and save temporarily
        back_extension = image_service._get_file_extension(license_back.filename or "")
        back_unique_filename = f"license_{application_id}_back_{uuid.uuid4().hex}.{back_extension}"
        back_temp_path = os.path.join(image_service.upload_folder, back_unique_filename)
        license_back.save(back_temp_path)

        # Process image with higher quality for license images
        back_processed_path = image_service._process_image(back_temp_path, max_width=None, quality=95)
        if not back_processed_path:
            image_service._cleanup_file(back_temp_path)
            flash("Virhe ajokortin takapuolen käsittelyssä - tarkista että kuva ei ole vioittunut", "error")
            return render_template('driver_application.html')

        # Upload back image to GCS privately
        back_blob_name = f"driver-licenses/{application_id}/back.jpg"
        back_blob, back_upload_error = gcs_service.upload_private_file(
            back_processed_path,
            back_blob_name
        )
        if back_upload_error:
            flash(f"Virhe ajokortin takapuolen tallentamisessa: {back_upload_error}", "error")
            image_service._cleanup_file(back_processed_path)
            return render_template('driver_application.html')

        license_images["back"] = back_blob_name
        image_service._cleanup_file(back_processed_path)  # Clean up temp file

        # Update application with license image blob names
        driver_application_model.update_one(
            {"id": application_id},
            {"$set": {"license_images": license_images}}
        )

    except Exception as e:
        print(f"Error processing license images: {e}")
        flash(f"Virhe ajokorttikuvien käsittelyssä: {str(e)}", "error")
        return render_template('driver_application.html')

    # Send confirmation email to applicant
    try:
        email_service.send_driver_application_confirmation(application_data["email"], application_data["name"])
    except Exception as e:
        print(f"Failed to send confirmation email: {e}")

    # Send notification email to admin
    try:
        email_service.send_admin_driver_application_notification(application_dict)
    except Exception as e:
        print(f"Failed to send admin notification: {e}")

    applicant_name = application_data["first_name"] or application_data["name"]

    return render_template(
        'driver_application_success.html',
        applicant_name=applicant_name,
        application_id=application_id
    )


# ----------------- HEALTH CHECK ENDPOINTS -----------------

@app.get("/health")
def health_check():
    """Basic health check - returns OK if app is running"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

@app.get("/health/live")
def health_live():
    """Liveness probe - is the app alive?"""
    return jsonify({"status": "ok", "live": True})

@app.get("/health/ready")
def health_ready():
    """Readiness probe - is the app ready to serve traffic?"""
    try:
        # Test database connection
        _mdb.command("ping")
        db_ok = True
    except Exception:
        db_ok = False

    is_ready = db_ok

    return jsonify({
        "status": "ok" if is_ready else "degraded",
        "ready": is_ready
    }), 200 if is_ready else 503


# ----------------- ERROR HANDLERS -----------------

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors with a friendly page"""
    return render_template("errors/404.html", current_user=current_user()), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors with error tracking"""
    from services.monitoring_service import monitoring_service
    
    # Generate error ID and capture
    error_id = monitoring_service.capture_exception(e, context={
        "url": request.url if request else None,
        "method": request.method if request else None,
        "user_id": session.get("user_id") if session else None
    })
    
    return render_template("errors/500.html", 
                          error_id=error_id, 
                          current_user=current_user()), 500

@app.errorhandler(403)
def forbidden(e):
    """Handle 403 forbidden errors"""
    flash("Sinulla ei ole oikeutta tähän sivuun", "error")
    return redirect(url_for("main.home"))

# ----------------- RATING ROUTES -----------------

@app.get("/order/<int:order_id>/rate")
def rate_order_page(order_id):
    """Show rating form for an order"""
    from services.rating_service import rating_service
    from models.order import order_model
    from models.user import user_model
    
    user = current_user()
    if user is None:
        flash("Kirjaudu sisään arvostellaksesi tilauksen", "error")
        return redirect(url_for("auth.login"))

    user_id = user["id"]

    # Check if can rate
    can_rate, reason = rating_service.can_rate_order(order_id, user_id)
    if not can_rate:
        flash(reason or "Arvostelu ei ole sallittu", "error")
        return redirect(url_for("main.dashboard"))
    
    order = order_model.find_by_id(order_id)
    if order is None:
        flash("Tilausta ei löydy", "error")
        return redirect(url_for("main.dashboard"))
    driver = None
    if order.get("driver_id"):
        driver = user_model.find_by_id(order["driver_id"])
    
    return render_template("rating/submit_rating.html", 
                          order=order, 
                          driver=driver,
                          current_user=user)

@app.post("/order/<int:order_id>/rate")
def submit_rating(order_id):
    """Submit a rating for an order"""
    from services.rating_service import rating_service
    
    user = current_user()
    if user is None:
        flash("Kirjaudu sisään arvostellaksesi tilauksen", "error")
        return redirect(url_for("auth.login"))

    user_id = user["id"]

    rating = int(request.form.get("rating", 0))
    comment = request.form.get("comment", "").strip()
    
    result, error = rating_service.submit_rating(order_id, user_id, rating, comment)
    
    if error is not None:
        flash(error, "error")
        return redirect(url_for("rate_order_page", order_id=order_id))
    
    flash("Kiitos arvostelustasi!", "success")
    return redirect(url_for("main.dashboard"))


# Register blueprints
from routes.main import main_bp
from routes.driver import driver_bp
from routes.auth import auth_bp
from routes.admin import admin_bp
app.register_blueprint(main_bp)
app.register_blueprint(driver_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# Import feature modules
# import order_wizard  # OLD WIZARD - replaced by order_wizard_new
import marketing

# ----------------- START -----------------
if __name__ == "__main__":
    init_db()
    seed_admin()

    # Only seed test drivers in development environment
    if os.getenv("FLASK_ENV", "production") == "development":
        seed_test_driver()

    migrate_images_to_array()  # Migrate existing single images to array format
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
