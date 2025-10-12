import os
import secrets
import datetime
import requests
import uuid
from zoneinfo import ZoneInfo

from flask import Flask, request, redirect, url_for, session, abort, jsonify, flash, render_template
from werkzeug.security import generate_password_hash
import sys
from pymongo import MongoClient, ReturnDocument
from dotenv import load_dotenv
load_dotenv()

# Import new service layer
from services.auth_service import auth_service
from services.order_service import order_service
from services.image_service import image_service
from services.email_service import email_service
from utils.formatters import format_helsinki_time

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
DB_NAME = os.getenv("DB_NAME", "carrental")
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
# NOMINATIM_URL removed - using Google Places API only
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"

USER_AGENT = "Umut-Autotransport-Portal/1.0 (contact: example@example.com)"

# Image upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'orders')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_WIDTH = 1200
IMAGE_QUALITY = 80

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))

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

def format_helsinki_time(dt):
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

@app.template_filter('extract_city')
def extract_city_filter(address):
    """Extract city name from full address"""
    if not address or not isinstance(address, str):
        return 'Tuntematon kaupunki'

    # Finnish address format: "Street, PostalCode City, Country"
    # We want to extract the city part
    parts = address.split(',')

    if len(parts) >= 2:
        # Get the part with postal code and city (second part usually)
        city_part = parts[1].strip()
        # Remove postal code (5 digits at start)
        import re
        city_match = re.sub(r'^\d{5}\s*', '', city_part)
        return city_match.strip() if city_match else 'Tuntematon kaupunki'
    elif len(parts) == 1:
        # If no comma, try to extract city from the string
        # Look for pattern: digits followed by city name
        import re
        match = re.search(r'\d{5}\s+([A-Za-zäöåÄÖÅ\s]+)', address)
        if match:
            return match.group(1).strip()

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
      <button class="mobile-menu-toggle" aria-label="Avaa menu" onclick="toggleMobileMenu()">
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
        <p style="margin: 0; opacity: 0.8;">© 2025 Levoro – Luotettava autonkuljetus</p>
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
    if not user:
        auth = "<a href='/login' class='nav-link'>Kirjaudu</a> <a href='/register' class='nav-link'>Luo tili</a>"
    else:
        auth = f"<span class='pill'>Hei, {user['name']}</span> <a class='nav-link' href='/logout'>Ulos</a>"

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
            user_links = '<a href="/order/new/step1" class="nav-link">Uusi tilaus</a><a href="/dashboard" class="nav-link">Oma sivu</a>'
    else:
        # Non-authenticated users can see Uusi tilaus
        user_links = '<a href="/order/new/step1" class="nav-link">Uusi tilaus</a>'

    # Google Maps script if API key is available
    google_script = ""
    if GOOGLE_PLACES_API_KEY:
        google_script = f'<script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_PLACES_API_KEY}&libraries=places&loading=async" async defer></script>'

    # Footer calculator button based on authentication
    if not user:
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
    if not pickup or not dropoff:
        return jsonify({"error": "Lähtö- ja kohdeosoite vaaditaan"}), 400

    try:
        # Use order service for geocoding
        pickup_coords = order_service._geocode_address(pickup)
        dropoff_coords = order_service._geocode_address(dropoff)

        if not pickup_coords or not dropoff_coords:
            return jsonify({"error": "Osoitteiden geokoodaus epäonnistui"}), 400

        lat1, lon1 = pickup_coords["lat"], pickup_coords["lng"]
        lat2, lon2 = dropoff_coords["lat"], dropoff_coords["lng"]

        # OSRM with full geometry for map
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}"
            "?overview=full&geometries=geojson"
        )

        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
        r.raise_for_status()
        j = r.json()

        if not j.get("routes"):
            return jsonify({"error": "Reittiä ei löytynyt annetuille osoitteille"}), 404

        route = j["routes"][0]
        km = route["distance"] / 1000.0
        coords = route["geometry"]["coordinates"]  # [ [lon,lat], ... ]
        # muunna [lon,lat] -> [lat,lon] Leafletille:
        latlngs = [[c[1], c[0]] for c in coords]
        return jsonify({"km": round(km, 2), "latlngs": latlngs, "start": [lat1, lon1], "end": [lat2, lon2]})

    except requests.exceptions.Timeout:
        return jsonify({"error": "Karttapalvelussa on ruuhkaa, odota hetken kuluttua uudestaan"}), 503
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Karttapalvelu ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan"}), 503
    except requests.exceptions.HTTPError:
        return jsonify({"error": "Karttapalvelu on tilapäisesti pois käytöstä, yritä hetken kuluttua uudestaan"}), 503
    except ValueError as e:
        # Geocoding errors or other validation issues
        if "Address not found" in str(e):
            return jsonify({"error": "Osoitetta ei löytynyt. Tarkista osoitteiden oikeinkirjoitus."}), 400
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Log unexpected errors but don't expose them to user
        print(f"Unexpected error in route_geo: {str(e)}")
        return jsonify({"error": "Karttapalvelu ei ole saatavilla juust nyt, yritä hetken kuluttua uudestaan"}), 500


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
            "reg_number": 1, "winter_tires": 1, "pickup_date": 1,
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

    # Smart content logic
    has_reg_number = bool(r.get('reg_number', '').strip())
    has_winter_tires = r.get('winter_tires') is not None
    has_customer_info = bool(
        r.get('customer_name', '').strip() or r.get('email', '').strip() or r.get('phone', '').strip() or
        r.get('orderer_name', '').strip() or r.get('orderer_email', '').strip() or r.get('orderer_phone', '').strip() or
        r.get('customer_phone', '').strip()
    )
    has_images = bool(r.get('images', {}))

    # Show vehicle section only if there's meaningful data
    show_vehicle_section = has_reg_number or has_winter_tires

    return render_with_context('dashboard/order_view.html',
        order=r,
        distance_km=distance_km,
        price_gross=price_gross,
        progress_bar=progress_bar,
        status_fi=status_fi,
        status_description=status_description,
        has_reg_number=has_reg_number,
        has_winter_tires=has_winter_tires,
        has_customer_info=has_customer_info,
        has_images=has_images,
        show_vehicle_section=show_vehicle_section
    )





# ----------------- ADMIN -----------------
# Legacy admin route removed - now handled by main.py blueprint
















@app.get("/order/new")
def order_new_redirect():
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
    payload = request.get_json(force=True, silent=True) or {}
    pickup = payload.get("pickup", "").strip()
    dropoff = payload.get("dropoff", "").strip()
    # NOTE: return_leg parameter exists but is not used in the current UI
    return_leg = bool(payload.get("return_leg", False))  # optional flag
    if not pickup or not dropoff:
        return jsonify({"error": "Lähtö- ja kohdeosoite vaaditaan"}), 400

    try:
        km = order_service.route_km(pickup, dropoff)
        net, vat, gross, details = order_service.price_from_km(km, pickup, dropoff, return_leg=return_leg)
        return jsonify({"km": round(km, 2), "net": net, "vat": vat, "gross": gross, "details": details})
    except ValueError as e:
        # These are user-friendly messages from route_km() when OSRM is unavailable
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        # Unexpected errors - log but don't expose details
        print(f"Unexpected error in quote_for_addresses: {str(e)}")
        return jsonify({"error": "Hintalaskenta ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan"}), 500


@app.get("/api/quote")
def api_quote():
    try:
        km = float(request.args.get("km", "0"))
    except:
        return jsonify({"error": "bad km"}), 400
    net, vat, gross, _ = order_service.price_from_km(km)
    return jsonify({"net": net, "vat": vat, "gross": gross})


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

    # Get form data
    application_data = {
        "first_name": (request.form.get("first_name") or "").strip(),
        "last_name": (request.form.get("last_name") or "").strip(),
        "email": (request.form.get("email") or "").strip(),
        "phone": (request.form.get("phone") or "").strip(),
        "password": (request.form.get("password") or "").strip(),
        "password_confirm": (request.form.get("password_confirm") or "").strip()
    }
    application_data["name"] = " ".join(
        part for part in [application_data["first_name"], application_data["last_name"]]
        if part
    ).strip()

    # Validate required fields
    required_fields = ["first_name", "last_name", "email", "phone", "password", "password_confirm"]
    field_labels = {
        "first_name": "Etunimi",
        "last_name": "Sukunimi",
        "email": "Sähköposti",
        "phone": "Puhelinnumero",
        "password": "Salasana",
        "password_confirm": "Salasanan vahvistus"
    }

    for field in required_fields:
        if not application_data.get(field):
            label = field_labels.get(field, field)
            flash(f"Virhe: {label} on pakollinen kenttä", "error")
            return render_template('driver_application.html')

    # Validate license images
    license_front = request.files.get('license_front')
    license_back = request.files.get('license_back')

    if not license_front or license_front.filename == '':
        flash("Virhe: Ajokortin etupuoli on pakollinen", "error")
        return render_template('driver_application.html')

    if not license_back or license_back.filename == '':
        flash("Virhe: Ajokortin takapuoli on pakollinen", "error")
        return render_template('driver_application.html')

    if not application_data["name"]:
        flash("Virhe: Lisää etu- ja sukunimi", "error")
        return render_template('driver_application.html')

    # Validate password confirmation
    if application_data["password"] != application_data["password_confirm"]:
        flash("Salasanat eivät täsmää", "error")
        return render_template('driver_application.html')

    # Validate password length
    if len(application_data["password"]) < 6:
        flash("Salasana tulee olla vähintään 6 merkkiä pitkä", "error")
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
    if error:
        flash(f"Virhe hakemuksen lähettämisessä: {error}", "error")
        return render_template('driver_application.html')

    # Process and upload license images
    application_id = application["id"]
    license_images = {"front": None, "back": None}

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
        front_extension = image_service._get_file_extension(license_front.filename)
        front_unique_filename = f"license_{application_id}_front_{uuid.uuid4().hex}.{front_extension}"
        front_temp_path = os.path.join(image_service.upload_folder, front_unique_filename)
        license_front.save(front_temp_path)

        # Process image (resize, optimize)
        front_processed_path = image_service._process_image(front_temp_path)
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
        back_extension = image_service._get_file_extension(license_back.filename)
        back_unique_filename = f"license_{application_id}_back_{uuid.uuid4().hex}.{back_extension}"
        back_temp_path = os.path.join(image_service.upload_folder, back_unique_filename)
        license_back.save(back_temp_path)

        # Process image (resize, optimize)
        back_processed_path = image_service._process_image(back_temp_path)
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
        email_service.send_admin_driver_application_notification(application)
    except Exception as e:
        print(f"Failed to send admin notification: {e}")

    applicant_name = application_data["first_name"] or application_data["name"]

    return render_template(
        'driver_application_success.html',
        applicant_name=applicant_name,
        application_id=application["id"]
    )


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
import order_wizard
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