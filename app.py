import os
import secrets
import datetime
import requests
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, request, redirect, url_for, session, abort, jsonify, send_file, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import sys
from pymongo import MongoClient, ReturnDocument
from dotenv import load_dotenv
load_dotenv()

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
VAT_RATE = float(os.getenv("VAT_RATE", "0.24"))
# --- Your business pricing anchors ---
# All prices below are TARGET **gross** (incl. VAT) that we want to hit.
METRO_CITIES = {"helsinki", "espoo", "vantaa", "kauniainen"}
METRO_GROSS = float(os.getenv("METRO_GROSS", "27"))  # 30–32€ → default 27€ (10% reduction)
MID_KM = 170.0  # “about 150–200 km”
MID_GROSS = float(os.getenv("MID_GROSS", "81"))  # ~81€ (10% reduction)
LONG_KM = 600.0
LONG_GROSS = float(os.getenv("LONG_GROSS", "207"))  # ~207€ (10% reduction)
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

def next_id(seq_name: str) -> int:
    doc = counters_col().find_one_and_update(
        {"_id": seq_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return int(doc["seq"])

def init_db():
    # indeksit
    users_col().create_index("email", unique=True)
    users_col().create_index("id", unique=True)

    orders_col().create_index([("id", 1)], unique=True)
    orders_col().create_index([("user_id", 1)])
    orders_col().create_index([("status", 1), ("id", -1)])

    # counters init (jos puuttuu)
    counters_col().update_one({"_id": "users"}, {"$setOnInsert": {"seq": 0}}, upsert=True)
    counters_col().update_one({"_id": "orders"}, {"$setOnInsert": {"seq": 0}}, upsert=True)

def seed_admin():
    if not users_col().find_one({"email": SEED_ADMIN_EMAIL}):
        users_col().insert_one({
            "id": next_id("users"),
            "name": SEED_ADMIN_NAME,
            "email": SEED_ADMIN_EMAIL,
            "password_hash": generate_password_hash(SEED_ADMIN_PASS),
            "role": "admin",
            "approved": True,  # Admin is always approved
            "created_at": datetime.datetime.now(ZoneInfo("Europe/Helsinki")),
        })

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

def _looks_like_city(addr: str, city: str) -> bool:
    return city.lower() in (addr or "").lower()


def both_in_metro(pickup_addr: str, dropoff_addr: str) -> bool:
    return any(_looks_like_city(pickup_addr, c) for c in METRO_CITIES) and \
        any(_looks_like_city(dropoff_addr, c) for c in METRO_CITIES)


def split_gross_to_net_vat(gross: float):
    net = gross / (1.0 + VAT_RATE)
    vat = gross - net
    return round(net, 2), round(vat, 2)


def interpolate(x, x1, y1, x2, y2):
    # Linear interpolation between (x1,y1) and (x2,y2)
    if x2 == x1:
        return y1
    t = max(0.0, min(1.0, (x - x1) / (x2 - x1)))
    return y1 + t * (y2 - y1)


def price_from_km(km: float, pickup_addr: str = "", dropoff_addr: str = "", return_leg: bool = False):
    """
    Returns (net, vat, gross, details) using your anchor pricing.
    - Metro inner (both addresses in HMA): flat METRO_GROSS
    - ~170 km: MID_GROSS
    - 600 km: LONG_GROSS
    - Between anchors: linear
    - Beyond 600 km: LONG_GROSS + tail_rate*(km-LONG_KM)
    - return_leg=True => 30% discount on gross
    """
    km = max(0.0, float(km))

    # 1) Metro flat if both are in HMA
    if both_in_metro(pickup_addr, dropoff_addr):
        gross = METRO_GROSS

    else:
        # 2) Build gross from anchors
        if km <= 20:  # tiny non-metro runs shouldn’t undercut metro
            gross = max(METRO_GROSS, interpolate(km, 0, METRO_GROSS, MID_KM, MID_GROSS))
        elif km <= MID_KM:
            gross = interpolate(km, 20, max(32.0, METRO_GROSS), MID_KM, MID_GROSS)  # gentle ramp
        elif km <= LONG_KM:
            gross = interpolate(km, MID_KM, MID_GROSS, LONG_KM, LONG_GROSS)
        else:
            # 3) Beyond 600 km, mild tail per km (tweakable)
            tail_rate = 0.18  # €/km on top after 600 km
            gross = LONG_GROSS + tail_rate * (km - LONG_KM)

    # 4) Apply return-leg discount if requested
    if return_leg:
        gross *= (1.0 - ROUNDTRIP_DISCOUNT)

    # ensure sane floor
    gross = max(gross, 20.0)

    net, vat = split_gross_to_net_vat(gross)
    return net, vat, round(gross, 2), {
        "km": round(km, 1),
        "metro": both_in_metro(pickup_addr, dropoff_addr),
        "anchors": {"metro": METRO_GROSS, "mid": (MID_KM, MID_GROSS), "long": (LONG_KM, LONG_GROSS)},
        "return_leg": return_leg
    }


def geocode(addr: str):
    """Return (lat, lon) for address using Google Places Geocoding API."""
    if not GOOGLE_PLACES_API_KEY:
        raise ValueError("Google Places API key not configured")
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": addr,
        "key": GOOGLE_PLACES_API_KEY,
        "components": "country:FI",
        "language": "fi"
    }
    
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"Address not found: {addr}")
    
    location = data["results"][0]["geometry"]["location"]
    return float(location["lat"]), float(location["lng"])


def route_km(pickup_addr: str, dropoff_addr: str):
    """Compute driving distance in km with OSRM. Raises exception on error - no fallback pricing."""
    lat1, lon1 = geocode(pickup_addr)
    lat2, lon2 = geocode(dropoff_addr)
    url = OSRM_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)

    try:
        # Reduced timeout to fail faster when service is slow
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
        r.raise_for_status()
        j = r.json()

        if not j.get("routes"):
            raise ValueError("Route not found by OSRM")

        meters = j["routes"][0]["distance"]
        return meters / 1000.0

    except requests.exceptions.Timeout:
        raise ValueError("Palvelussamme on ruuhkaa, odota hetken kuluttua uudestaan")
    except requests.exceptions.ConnectionError:
        raise ValueError("Reittihaku ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan")
    except requests.exceptions.HTTPError:
        raise ValueError("Reittihaku on tilapäisesti pois käytöstä, yritä hetken kuluttua uudestaan")
    except Exception as e:
        print(f"OSRM error: {str(e)}")  # Log for debugging
        raise ValueError("Reittihaku ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan")


# ----------------- IMAGE UTILS -----------------

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(file_path, max_width=MAX_IMAGE_WIDTH, quality=IMAGE_QUALITY):
    """Process uploaded image: resize and compress"""
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Resize if too wide
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Save with compression
            img.save(file_path, 'JPEG', quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Error processing image: {e}")
        return False

def save_order_image(file, order_id, image_type):
    """Save and process an uploaded image for an order"""
    if not file or not allowed_file(file.filename):
        return None, "Invalid file type"

    # Create order directory
    order_dir = os.path.join(UPLOAD_FOLDER, str(order_id))
    os.makedirs(order_dir, exist_ok=True)

    # Generate filename with timestamp
    timestamp = int(time.time())
    filename = f"{image_type}_{timestamp}.jpg"
    file_path = os.path.join(order_dir, filename)

    # Save file temporarily
    try:
        file.save(file_path)

        # Check file size
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            os.remove(file_path)
            return None, "File too large (max 5MB)"

        # Process image
        if not process_image(file_path):
            os.remove(file_path)
            return None, "Error processing image"

        return {
            "id": str(uuid.uuid4()),  # Unique identifier for this image
            "filename": filename,
            "original_name": file.filename,
            "file_size": os.path.getsize(file_path),
            "uploaded_at": datetime.datetime.now(ZoneInfo("Europe/Helsinki")),
            "file_path": f"/static/uploads/orders/{order_id}/{filename}",
            "order": 1  # Will be updated when added to array
        }, None

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return None, f"Upload failed: {str(e)}"

def delete_order_image(order_id, image_type):
    """Delete an order image and its metadata"""
    try:
        order = orders_col().find_one({"id": int(order_id)}, {"images": 1})
        if not order or "images" not in order:
            return False, "Order or image not found"

        image_info = order["images"].get(image_type)
        if not image_info:
            return False, "Image not found"

        # Delete physical file
        order_dir = os.path.join(UPLOAD_FOLDER, str(order_id))
        file_path = os.path.join(order_dir, image_info["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)

        # Update database
        orders_col().update_one(
            {"id": int(order_id)},
            {"$unset": {f"images.{image_type}": ""}}
        )

        return True, "Image deleted successfully"

    except Exception as e:
        return False, f"Delete failed: {str(e)}"

def delete_order_image_by_id(order_id, image_type, image_id):
    """Delete a specific image by ID from an order's image array"""
    try:
        order = orders_col().find_one({"id": int(order_id)}, {"images": 1})
        if not order or "images" not in order:
            return False, "Order or image not found"

        images = order["images"].get(image_type, [])
        if not isinstance(images, list):
            images = [images] if images else []

        # Find the image with the matching ID
        image_to_delete = None
        updated_images = []

        for img in images:
            if img.get("id") == image_id:
                image_to_delete = img
            else:
                updated_images.append(img)

        if not image_to_delete:
            return False, "Image not found"

        # Delete physical file
        order_dir = os.path.join(UPLOAD_FOLDER, str(order_id))
        file_path = os.path.join(order_dir, image_to_delete["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)

        # Re-order the remaining images
        for i, img in enumerate(updated_images):
            img["order"] = i + 1

        # Update database with the filtered array
        orders_col().update_one(
            {"id": int(order_id)},
            {"$set": {f"images.{image_type}": updated_images}}
        )

        return True, "Image deleted successfully"

    except Exception as e:
        return False, f"Delete failed: {str(e)}"


# ----------------- AUTH UTILS -----------------

def translate_status(status):
    """Translate English status to Finnish"""
    translations = {
        'NEW': 'UUSI',
        'CONFIRMED': 'VAHVISTETTU',
        'IN_TRANSIT': 'KULJETUKSESSA',
        'DELIVERED': 'TOIMITETTU',
        'CANCELLED': 'PERUUTETTU'
    }
    return translations.get(status, status)

def get_status_description(status):
    """Get user-friendly status description"""
    descriptions = {
        'NEW': 'Tilaus odottaa vahvistusta',
        'CONFIRMED': 'Tilaus vahvistettu, odottaa noutoa',
        'IN_TRANSIT': 'Ajoneuvo on kuljetuksessa',
        'DELIVERED': 'Kuljetus suoritettu onnistuneesti',
        'CANCELLED': 'Tilaus on peruutettu'
    }
    return descriptions.get(status, 'Tuntematon tila')

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
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    u = users_col().find_one({"id": int(uid)}, {"_id": 0})
    return u



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
        <a href="/order/new/step1" class="nav-link">Uusi tilaus</a>
        <a href="/dashboard" class="nav-link">Oma sivu</a>
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
<script>
function toggleMobileMenu() {
  const nav = document.getElementById('nav-menu');
  const toggle = document.querySelector('.mobile-menu-toggle');
  nav.classList.toggle('mobile-open');
  toggle.classList.toggle('active');
}

// Close mobile menu when clicking on a link
document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    const nav = document.getElementById('nav-menu');
    const toggle = document.querySelector('.mobile-menu-toggle');
    nav.classList.remove('mobile-open');
    toggle.classList.remove('active');
  });
});

// Close mobile menu when clicking outside
document.addEventListener('click', (e) => {
  const nav = document.getElementById('nav-menu');
  const toggle = document.querySelector('.mobile-menu-toggle');
  if (!nav.contains(e.target) && !toggle.contains(e.target)) {
    nav.classList.remove('mobile-open');
    toggle.classList.remove('active');
  }
});

</script>
</body></html>
"""


def wrap(content: str, user=None):
    # Yläpalkin oikea reuna: kirjautumislinkit tai käyttäjän nimi + ulos
    if not user:
        auth = "<a href='/login' class='nav-link'>Kirjaudu</a> <a href='/register' class='nav-link'>Luo tili</a>"
    else:
        auth = f"<span class='pill'>Hei, {user['name']}</span> <a class='nav-link' href='/logout'>Ulos</a>"

    # Logo ja admin-linkki
    from flask import url_for, get_flashed_messages
    logo_src = url_for('static', filename='LevoroLogo.png')
    admin_link = '<a href="/admin" class="nav-link">Admin</a>' if (user and user.get("role") == "admin") else ""

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
        .replace("__LOGO__", logo_src)
        .replace("__ADMIN__", admin_link)
        .replace("__AUTH__", auth)
        .replace("__CSS_MAIN__", url_for('static', filename='css/main.css'))
        .replace("__GOOGLE_MAPS_SCRIPT__", google_script)
    )

    # Kootaan footer
    foot = (
        PAGE_FOOT
        .replace("__FOOTER_CALCULATOR__", footer_calculator)
    )

    return head + flash_html + content + foot


# ----------------- ROUTES: HOME -----------------
@app.get("/")
def home():
    u = current_user()
    body = """
<!-- HERO -->
<div class="container">
  <div class="hero">
    <div class="hero-content">
      <div class="hero-badge">
        <span aria-hidden="true">🚗</span> 
        Saman päivän auton kuljetukset
      </div>
      <h1 class="hero-title">Samana päivänä, ja halvin.<br/>Levorolla mahdollista.</h1>
      <p class="hero-subtitle">Suomen nopein, edullisin ja luotettavin tapa siirtää autoja. Läpinäkyvä hinnoittelu, reaaliaikainen seuranta ja helppo tilausportaali.</p>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="/calculator">Laske halvin hinta nyt</a>
        <a class="btn btn-secondary btn-lg" href="#how">Miten se toimii</a>
      </div>
      <div class="hero-features">
        <div class="hero-feature">Toimitus samana päivänä</div>
        <div class="hero-feature">PK-seudulla kuljetukset 27€</div>
        <div class="hero-feature">Kokeilualennus yritysasiakkaille
        </div>
      </div>
    </div>
  </div>
</div>

<!-- MIKSI MEIDÄT -->
<div class="container">
  <section class="section-padding">
    <div class="section-header">
      <h2 class="section-title">Miksi valita meidät</h2>
    </div>
    <div class="grid grid-cols-3">
      <div class="feature-card">
        <div class="feature-icon">⚡</div>
        <h3 class="feature-title">Nopeus</h3>
        <p class="feature-description">Optimointi, eurooppalaiset vakioreitit ja oma verkosto. Useimmat toimitukset 3–5 päivässä.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">💶</div>
        <h3 class="feature-title">Hinta</h3>
        <p class="feature-description">Reilu ja läpinäkyvä. Ei piilokuluja – näet hinnan ennen tilausta.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">🛡️</div>
        <h3 class="feature-title">Luotettavuus</h3>
        <p class="feature-description">Vakuutus koko matkan, CMR-dokumentointi ja seuranta portaalissa.</p>
      </div>
    </div>
  </section>
</div>

<!-- MITEN SE TOIMII -->
<div id="how" class="container">
  <section class="section-padding">
    <h2 class="section-title">Miten se toimii</h2>
    <div class="grid grid-cols-3">
      <div class="feature-card">
        <h3 class="feature-title">
          <span class="step-number">1</span>
          Lähetä reitti
        </h3>
        <p class="feature-description">Valitse nouto ja kohde portaalissa. Saat hinnan heti.</p>
      </div>
      <div class="feature-card">
        <h3 class="feature-title">
          <span class="step-number">2</span>
          Vahvista tilaus
        </h3>
        <p class="feature-description">Valitse sopiva aika ja lisää tiedot (avaimet, yhteyshenkilöt).</p>
      </div>
      <div class="feature-card">
        <h3 class="feature-title">
          <span class="step-number">3</span>
          Seuraa toimitusta
        </h3>
        <p class="feature-description">Näet etenemisen ja saat ilmoitukset – kuittaukset tallentuvat portaaliin.</p>
      </div>
    </div>
  </section>
</div>


<!-- VAKUUTUSBANNERI -->
<div class="container">
  <section class="section-padding">
    <div class="trust-banner">
      <div class="trust-content">
        <div class="trust-icon">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3l7 3v5c0 5-3.5 9-7 10-3.5-1-7-5-7-10V6l7-3z" fill="none" stroke-width="2" stroke-linejoin="round"></path>
            <path d="M8 12l3 3 5-5" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </div>
        <div class="trust-text">
          <h3>Kaikki ajamamme autot suojattu täysin vastuuvakuutuksella</h3>
          <p>Vakuutusturva koko kuljetuksen ajan – ilman lisämaksuja.</p>
        </div>
      </div>
      <a class="btn btn-primary btn-lg" href="/calculator">Laske hinta →</a>
    </div>
  </section>
</div>

<!-- FOOTER-CTA -->
<div class="container">
  <section class="section-padding text-center">
    <p class="text-muted">Onko sinulla jo tili?</p>
    <div class="flex justify-center gap-4 mt-4 footer-cta">
      <a class="btn btn-ghost" href="/login">Kirjaudu sisään</a>
      <a class="btn btn-ghost" href="/register">Luo yritystili</a>
    </div>
  </section>
</div>
"""
    return wrap(body, u)




# ----------------- AUTH -----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return wrap("""
<div class="container">
  <div class="section-padding">
    <div class="text-center mb-8">
      <h1 class="calculator-title">Luo yritystili</h1>
      <p class="calculator-subtitle">Täytä tiedot alla luodaksesi tilin kuljetuspalveluun</p>
    </div>
  </div>
  
  <div class="calculator-grid" style="grid-template-columns: 1fr; max-width: 600px; margin: 0 auto;">
    <div class="card calculator-form">
      <div class="card-header">
        <h2 class="card-title">Rekisteröintitiedot</h2>
        <p class="card-subtitle">Kaikki kentät ovat pakollisia</p>
      </div>
      
      <div class="card-body">
        <form method="POST">
          <div class="form-group">
            <label class="form-label">Nimi *</label>
            <input name="name" required class="form-input" placeholder="Etunimi Sukunimi">
          </div>
          
          <div class="form-group">
            <label class="form-label">Sähköposti *</label>
            <input type="email" name="email" required class="form-input" placeholder="nimi@yritys.fi">
          </div>
          
          <div class="form-group">
            <label class="form-label">Salasana *</label>
            <input type="password" name="password" minlength="6" required class="form-input" placeholder="Vähintään 6 merkkiä">
          </div>
          
          <div class="calculator-actions">
            <button type="submit" class="btn btn-primary btn-lg">Rekisteröidy</button>
            <a href="/login" class="btn btn-ghost">Onko sinulla jo tili? Kirjaudu</a>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>
""", current_user())

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not name or not email or len(password) < 6:
        return wrap("<div class='card'><h3>Tarkista tiedot</h3></div>", current_user())

    if users_col().find_one({"email": email}):
        return wrap("<div class='card'><h3>Sähköposti on jo käytössä</h3></div>", current_user())

    uid = next_id("users")
    users_col().insert_one({
        "id": uid,
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": "customer",
        "approved": False,  # Require admin approval
        "created_at": datetime.datetime.now(ZoneInfo("Europe/Helsinki")),
    })

    # Don't log in immediately - require admin approval first
    return wrap("""
<div class="container">
  <div class="section-padding">
    <div class="text-center mb-8">
      <h1 class="calculator-title">Rekisteröinti onnistui!</h1>
      <p class="calculator-subtitle">Tilisi odottaa ylläpidon hyväksyntää. Saat sähköpostiviestin kun tili on aktivoitu.</p>
    </div>
  </div>

  <div class="calculator-grid" style="grid-template-columns: 1fr; max-width: 600px; margin: 0 auto;">
    <div class="card calculator-form">
      <div class="card-header">
        <h2 class="card-title">Mitä tapahtuu seuraavaksi?</h2>
        <p class="card-subtitle">Ylläpitäjämme tarkistaa tilisi tiedot ja aktivoi sen mahdollisimman pian</p>
      </div>

      <div class="card-body">
        <div class="calculator-actions">
          <a href="/login" class="btn btn-primary btn-lg">Takaisin kirjautumissivulle</a>
          <a href="/" class="btn btn-ghost">Etusivulle</a>
        </div>
      </div>
    </div>
  </div>
</div>
""", current_user())



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

@app.get("/api/test_places_api")
def test_places_api():
    """Test endpoint to validate Google Places API configuration"""
    if not GOOGLE_PLACES_API_KEY:
        return jsonify({"error": "Google Places API key not configured"}), 500
    
    try:
        # Test with a simple geocoding request
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": "Helsinki, Finland",
            "key": GOOGLE_PLACES_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return jsonify({
            "status": "success",
            "api_key_valid": data.get("status") == "OK",
            "google_response": data
        })
        
    except Exception as e:
        error_msg = f"API test failed: {str(e)}"
        return jsonify({"error": error_msg}), 500

@app.post("/api/route_geo")
def api_route_geo():
    data = request.get_json(force=True, silent=True) or {}
    pickup = (data.get("pickup") or "").strip()
    dropoff = (data.get("dropoff") or "").strip()
    if not pickup or not dropoff:
        return jsonify({"error": "Lähtö- ja kohdeosoite vaaditaan"}), 400

    try:
        # geocode -> lat/lon
        lat1, lon1 = geocode(pickup)
        lat2, lon2 = geocode(dropoff)

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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        nxt = request.args.get("next", "")
        body = """
<div class="container">
  <div class="section-padding">
    <div class="text-center mb-8">
      <h1 class="calculator-title">Kirjaudu sisään</h1>
      <p class="calculator-subtitle">Syötä tunnuksesi päästäksesi omalle sivullesi</p>
    </div>
  </div>
  
  <div class="calculator-grid" style="grid-template-columns: 1fr; max-width: 600px; margin: 0 auto;">
    <div class="card calculator-form">
      <div class="card-header">
        <h2 class="card-title">Kirjautumistiedot</h2>
        <p class="card-subtitle">Syötä sähköpostisi ja salasanasi</p>
      </div>
      
      <div class="card-body">
        <form method="POST">
          <div class="form-group">
            <label class="form-label">Sähköposti</label>
            <input type="email" name="email" required class="form-input" placeholder="nimi@yritys.fi">
          </div>
          
          <div class="form-group">
            <label class="form-label">Salasana</label>
            <input type="password" name="password" required class="form-input" placeholder="Salasanasi">
          </div>
          
          <input type="hidden" name="next" value="__NEXT__">
          
          <div class="calculator-actions">
            <button type="submit" class="btn btn-primary btn-lg">Kirjaudu</button>
            <a href="/register" class="btn btn-ghost">Tarvitsetko tilin? Luo tili</a>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>
""".replace("__NEXT__", nxt)
        return wrap(body, current_user())

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    nxt = request.form.get("next") or ""

    row = users_col().find_one({"email": email}, {"_id": 0, "id": 1, "password_hash": 1, "approved": 1, "role": 1})
    if not row or not check_password_hash(row.get("password_hash", ""), password):
        return wrap("<div class='card'><h3>Väärä sähköposti tai salasana</h3></div>", current_user())

    # Check if user is approved (admins are always approved)
    if not row.get("approved", False) and row.get("role") != "admin":
        return wrap("<div class='card'><h3>Tilisi odottaa ylläpidon hyväksyntää. Yritä myöhemmin uudelleen.</h3></div>", current_user())

    session["uid"] = int(row["id"])
    return redirect(nxt or "/dashboard")



# ----------------- DASHBOARD -----------------
@app.get("/dashboard")
def dashboard():
    u = current_user()
    if not u:
        return redirect(url_for("login", next="/dashboard"))

    tab = (request.args.get("tab", "active") or "active").lower()
    all_orders = list(orders_col().find({"user_id": int(u["id"])}).sort("id", -1))

    def is_active_status(s: str) -> bool:
        return s in {"NEW", "CONFIRMED", "IN_TRANSIT"}

    if tab == "completed":
        orders = [r for r in all_orders if not is_active_status(r.get("status","NEW"))]
    else:
        orders = [r for r in all_orders if is_active_status(r.get("status","NEW"))]

    rows = ""
    for r in orders:
        status_fi = translate_status(r['status'])
        rows += f"""
<tr>
  <td>#{r['id']}</td>
  <td><span class="status {r['status']}">{status_fi}</span></td>
  <td>{r['pickup_address']} → {r['dropoff_address']}</td>
  <td>{float(r['distance_km']):.1f} km</td>
  <td>{float(r['price_gross']):.2f} €</td>
  <td><a class="btn btn-ghost btn-sm" href="/order/{r['id']}">Avaa</a></td>
</tr>
"""

    tabs_html = f"""
<div class="tabs mb-4">
  <a href="/dashboard?tab=active" class="btn {'btn-primary' if tab=='active' else 'btn-ghost'} mr-2">Aktiiviset</a>
  <a href="/dashboard?tab=completed" class="btn {'btn-primary' if tab=='completed' else 'btn-ghost'}">Valmistuneet</a>
</div>
"""

    body = f"""
<div class="container">
  <div class="section-padding">
    <div class="text-center mb-8">
      <h1 class="calculator-title">Omat tilaukset</h1>
      <p class="calculator-subtitle">Hallinnoi kuljetustilauksiasi ja seuraa niiden etenemistä</p>
    </div>
  </div>

  <div class="calculator-grid" style="grid-template-columns: 1fr; max-width: 1200px; margin: 0 auto;">
    <div class="card calculator-form">
      <div class="card-header">
        <h2 class="card-title">Tilaushistoria</h2>
        <p class="card-subtitle">Näet kaikki tilauksesi ja niiden tilan alla</p>
      </div>
      
      <div class="card-body">
        {tabs_html}
        <div class="calculator-actions mb-4">
          <a class="btn btn-primary" href="/order/new/step1">+ Uusi tilaus</a>
        </div>
        <table class="dashboard-table">
          <thead><tr><th>ID</th><th>Tila</th><th>Reitti</th><th>Km</th><th>Hinta</th><th></th></tr></thead>
          <tbody>{rows or "<tr><td colspan='6' style='text-align: center; color: var(--text-muted); font-style: italic;'>Ei tilauksia</td></tr>"}</tbody>
        </table>
      </div>
    </div>
  </div>
</div>
"""
    return wrap(body, u)



def create_client_image_section(images_dict, image_type):
    """Create HTML for client-side image display with grid layout"""
    image_data = images_dict.get(image_type)

    # Handle both old single image format and new array format
    if isinstance(image_data, list):
        images = image_data
    else:
        # Old single image format - convert to list
        images = [image_data] if image_data else []

    image_type_fi = "Nouto" if image_type == "pickup" else "Toimitus"
    images_count = len(images)

    if images_count == 0:
        status_text = "Nouto odottaa" if image_type == "pickup" else "Toimitus odottaa"
        return f"""
        <div class="client-image-placeholder">
            <div class="placeholder-icon">📷</div>
            <div class="placeholder-text">
                <p class="placeholder-title">Ei kuvaa vielä</p>
                <p class="placeholder-subtitle">{status_text}</p>
            </div>
        </div>"""

    # Sort images by order
    images.sort(key=lambda x: x.get('order', 1))

    # Generate grid of images
    images_html = ""
    for img in images:
        upload_date = format_helsinki_time(img.get('uploaded_at'))
        images_html += f"""
        <div class="client-image-item">
            <img src="{img['file_path']}" alt="{image_type_fi} kuva" class="client-image-thumbnail"
                 onclick="openClientImageModal('{image_type}', '{img['id']}')">
            <div class="client-image-info">
                <small class="client-image-date">Kuvattu: {upload_date}</small>
            </div>
        </div>"""

    return f"""
    <div class="client-image-section">
        <div class="client-image-counter">
            <span class="client-image-count">{images_count} kuvaa</span>
        </div>
        <div class="client-images-grid">
            {images_html}
        </div>
    </div>"""


@app.get("/order/<int:order_id>")
def order_view(order_id: int):
    u = current_user()
    if not u:
        return redirect(url_for("login", next=f"/order/{order_id}"))

    # Hae tilaus Mongosta samalla ehdolla kuin ennen MySQL:ssä
    r = orders_col().find_one(
        {"id": int(order_id), "user_id": int(u["id"])},
        {"_id": 0}
    )
    if not r:
        return wrap("<div class='card'><h2>Ei oikeuksia tähän tilaukseen</h2></div>", u)

    # numerot tulostusta varten
    distance_km = float(r.get("distance_km", 0.0))
    price_gross = float(r.get("price_gross", 0.0))

    current_status = r.get("status", "NEW")
    step = progress_step(current_status)

    # Progress bar with better styling
    bar = f"""
<div class="order-progress" data-step="{step}" data-status="{current_status}">
  <div class="progress-step {'completed' if step >= 1 else ''}">
    <div class="step-number">1</div>
    <div class="step-label">Noudettu</div>
  </div>
  <div class="progress-line {'completed' if step >= 2 else ''}"></div>
  <div class="progress-step {'completed' if step >= 2 else ''}">
    <div class="step-number">2</div>
    <div class="step-label">Kuljetuksessa</div>
  </div>
  <div class="progress-line {'completed' if step >= 3 else ''}"></div>
  <div class="progress-step {'completed' if step >= 3 else ''}">
    <div class="step-number">3</div>
    <div class="step-label">Toimitettu</div>
  </div>
</div>
"""

    status_fi = translate_status(r.get('status', 'NEW'))
    status_description = get_status_description(r.get('status', 'NEW'))

    # Smart content logic
    has_reg_number = bool(r.get('reg_number', '').strip())
    has_winter_tires = r.get('winter_tires') is not None
    has_customer_info = bool(r.get('customer_name', '').strip() or r.get('email', '').strip() or r.get('phone', '').strip())
    has_additional_info = bool(r.get('additional_info', '').strip())
    has_images = bool(r.get('images', {}))

    # Show vehicle section only if there's meaningful data
    show_vehicle_section = has_reg_number or has_winter_tires

    body = f"""
<link rel='stylesheet' href='/static/css/order-view.css'>
<link rel='stylesheet' href='/static/css/client-images.css'>
<div class="order-container">
  <!-- Hero Section with Key Information -->
  <div class="order-hero status-{r.get('status','NEW').lower()}">
    <div class="hero-content">
      <div class="hero-header">
        <h1 class="order-title">Tilaus #{r['id']}</h1>
        <div class="order-status-main">
          <span class="status-badge status-{r.get('status','NEW').lower()}">{status_fi}</span>
          <p class="status-description">{status_description}</p>
        </div>
      </div>

      <!-- Route Display - Most Important Information -->
      <div class="hero-route">
        <div class="route-card">
          <div class="route-point pickup">
            <div class="point-icon">📍</div>
            <div class="point-details">
              <span class="point-label">Nouto</span>
              <span class="point-address">{r.get('pickup_address','?')}</span>
            </div>
          </div>
          <div class="route-connector">
            <div class="route-line"></div>
            <div class="route-arrow">→</div>
          </div>
          <div class="route-point delivery">
            <div class="point-icon">📍</div>
            <div class="point-details">
              <span class="point-label">Toimitus</span>
              <span class="point-address">{r.get('dropoff_address','?')}</span>
            </div>
          </div>
        </div>

        <!-- Key Metrics -->
        <div class="hero-metrics">
          <div class="metric-card">
            <span class="metric-value">{distance_km:.1f} km</span>
            <span class="metric-label">Matka</span>
          </div>
          <div class="metric-card price-card">
            <span class="metric-value">{price_gross:.2f} €</span>
            <span class="metric-label">Hinta</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Progress Section -->
  <div class="progress-section">
    {bar}
  </div>
  
  <!-- Secondary Information -->
  <div class="order-details">
    <div class="details-grid">
      {f'''<div class="detail-card">
        <h3 class="card-title">🚗 Ajoneuvo</h3>
        <div class="card-content">
          {f'<div class="detail-row"><span class="detail-label">Rekisterinumero</span><span class="detail-value">{r.get("reg_number","")}</span></div>' if has_reg_number else ''}
          {f'<div class="detail-row"><span class="detail-label">Talvirenkaat</span><span class="detail-value">{"Kyllä" if r.get("winter_tires") else "Ei"}</span></div>' if has_winter_tires else ''}
          {'''<div class="detail-row empty-state">
            <span class="detail-label">📝</span>
            <span class="detail-value">Ajoneuvotiedot täydennetään noudettaessa</span>
          </div>''' if not show_vehicle_section else ''}
        </div>
      </div>''' if show_vehicle_section or r.get('status') == 'NEW' else ''}

      {f'''<div class="detail-card">
        <h3 class="card-title">👤 Yhteystiedot</h3>
        <div class="card-content">
          {f'<div class="detail-row"><span class="detail-label">Nimi</span><span class="detail-value">{r.get("customer_name","")}</span></div>' if r.get('customer_name','').strip() else ''}
          {f'<div class="detail-row"><span class="detail-label">Sähköposti</span><span class="detail-value">{r.get("email","")}</span></div>' if r.get('email','').strip() else ''}
          {f'<div class="detail-row"><span class="detail-label">Puhelin</span><span class="detail-value">{r.get("phone","")}</span></div>' if r.get('phone','').strip() else ''}
          {'''<div class="detail-row empty-state">
            <span class="detail-label">📞</span>
            <span class="detail-value">Yhteystiedot päivitetään tilauksen käsittelyn yhteydessä</span>
          </div>''' if not has_customer_info else ''}
        </div>
      </div>''' if has_customer_info or r.get('status') == 'NEW' else ''}
    </div>

    {f'''
    <div class="detail-card full-width">
      <h3 class="card-title">📝 Lisätiedot</h3>
      <div class="card-content">
        <p class="additional-info-text">{(r.get('additional_info') or 'Ei lisätietoja').replace('<', '&lt;')}</p>
      </div>
    </div>''' if r.get('additional_info') else ''}

    {f'''<div class="detail-card full-width">
      <h3 class="card-title">📷 Kuljetuskuvat</h3>
      <div class="card-content">
        <div class="images-grid">
          <div class="image-section">
            <h4 class="image-section-title">Nouto</h4>
            {create_client_image_section(r.get('images', {}), 'pickup')}
          </div>
          <div class="image-section">
            <h4 class="image-section-title">Toimitus</h4>
            {create_client_image_section(r.get('images', {}), 'delivery')}
          </div>
        </div>
        {'''<div class="images-status">
          <p class="status-info">📸 Kuljetuskuvat lisätään kuljetuksen aikana</p>
        </div>''' if not has_images and r.get('status') in ['NEW', 'CONFIRMED'] else ''}
      </div>
    </div>''' if has_images or r.get('status') in ['NEW', 'CONFIRMED', 'IN_TRANSIT'] else ''}
  </div>

  <div class="order-actions">
    <a href="/dashboard" class="btn btn-ghost">← Takaisin tilauksiin</a>
  </div>
</div>

<!-- Image Modal -->
<div id="imageModal" class="image-modal" onclick="closeImageModal()">
  <div class="modal-content">
    <span class="modal-close" onclick="closeImageModal()">&times;</span>
    <img id="modalImage" src="" alt="Kuva">
  </div>
</div>

<script>
function openImageModal(imageSrc) {{
  document.getElementById('imageModal').style.display = 'block';
  document.getElementById('modalImage').src = imageSrc;
  document.body.style.overflow = 'hidden';
}}

function openClientImageModal(imageType, imageId) {{
  // Find the image by ID from the current order
  const imageElement = document.querySelector(`img[onclick*='${{imageId}}']`);
  if (imageElement) {{
    openImageModal(imageElement.src);
  }}
}}

function closeImageModal() {{
  document.getElementById('imageModal').style.display = 'none';
  document.body.style.overflow = 'auto';
}}

document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') {{
    closeImageModal();
  }}
}});
</script>
"""
    return wrap(body, u)





# ----------------- ADMIN -----------------
@app.get("/admin")
def admin_home():
    u = current_user()
    if not u or u.get("role") != "admin":
        return wrap("<div class='card'><h2>Adminalue</h2><p class='muted'>Kirjaudu admin-käyttäjänä.</p></div>", u)

    pipeline = [
        {"$sort": {"id": -1}},
        {"$limit": 300},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "id",
            "as": "user"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "id": 1, "status": 1,
            "pickup_address": 1, "dropoff_address": 1,
            "distance_km": 1, "price_gross": 1,
            "images": 1,
            "user_name": "$user.name",
            "user_email": "$user.email"
        }}
    ]
    rows = list(orders_col().aggregate(pipeline))

    tr = ""
    for r in rows:
        distance_km = float(r.get("distance_km", 0.0))
        price_gross = float(r.get("price_gross", 0.0))
        status_fi = translate_status(r['status'])

        # Image indicators
        images = r.get("images", {})
        pickup_icon = "📷" if images.get("pickup") else "⭕"
        delivery_icon = "📷" if images.get("delivery") else "⭕"
        image_status = f"{pickup_icon} {delivery_icon}"

        tr += f"""
<tr class="admin-table-row" onclick="window.location.href='/admin/order/{r['id']}'" style="cursor: pointer;">
  <td><strong>#{r['id']}</strong></td>
  <td><span class="status {r['status']}">{status_fi}</span></td>
  <td>{r.get('user_name','?')} &lt;{r.get('user_email','?')}&gt;</td>
  <td>{r['pickup_address']} → {r['dropoff_address']}</td>
  <td>{distance_km:.1f} km</td>
  <td>{price_gross:.2f} €</td>
  <td class="image-status">{image_status}</td>
  <td onclick="event.stopPropagation();">
    <form method="POST" action="/admin/update" class="admin-inline-form">
      <input type="hidden" name="id" value="{r['id']}">
      <select name="status">
        <option value="NEW" {'selected' if r['status'] == 'NEW' else ''}>UUSI</option>
        <option value="CONFIRMED" {'selected' if r['status'] == 'CONFIRMED' else ''}>VAHVISTETTU</option>
        <option value="IN_TRANSIT" {'selected' if r['status'] == 'IN_TRANSIT' else ''}>KULJETUKSESSA</option>
        <option value="DELIVERED" {'selected' if r['status'] == 'DELIVERED' else ''}>TOIMITETTU</option>
        <option value="CANCELLED" {'selected' if r['status'] == 'CANCELLED' else ''}>PERUUTETTU</option>
      </select>
      <button type="submit">Päivitä</button>
    </form>
  </td>
</tr>
"""
    body = f"""
<div class="admin-container">
  <div class="admin-header">
    <h2>Admin – Tilaukset</h2>
    <div class="admin-actions">
      <a class="btn btn-ghost" href="/admin/users">Käyttäjät</a>
      <a class="btn btn-secondary" href="/logout">Kirjaudu ulos</a>
    </div>
  </div>
  <table class="admin-table">
    <thead><tr><th>ID</th><th>Tila</th><th>Asiakas</th><th>Reitti</th><th>Km</th><th>Hinta</th><th>Kuvat</th><th>Päivitä</th></tr></thead>
    <tbody>{tr or "<tr><td colspan='8' class='muted'>Ei tilauksia</td></tr>"}</tbody>
  </table>
</div>
"""
    return wrap(body, u)



@app.get("/admin/users")
def admin_users():
    u = current_user()
    if not u or u.get("role") != "admin":
        return wrap("<div class='card'><h2>Adminalue</h2><p class='muted'>Kirjaudu admin-käyttäjänä.</p></div>", u)

    # Get all users sorted by creation date (newest first)
    users = list(users_col().find({}, {"_id": 0}).sort("created_at", -1))

    user_rows = ""
    for user in users:
        approved_status = "✅ Hyväksytty" if user.get("approved", False) else "⏳ Odottaa"
        role_badge = "Admin" if user.get("role") == "admin" else "Asiakas"

        action_buttons = ""
        if user.get("role") != "admin":  # Don't allow modifying admin accounts
            if user.get("approved", False):
                action_buttons = f"""
                <form method="POST" action="/admin/users/deny" class="admin-inline-form">
                  <input type="hidden" name="user_id" value="{user['id']}">
                  <button type="submit" class="btn btn-sm" style="background: #dc2626; color: white;">Hylkää</button>
                </form>
                """
            else:
                action_buttons = f"""
                <div class="admin-inline-form">
                  <form method="POST" action="/admin/users/approve" class="admin-inline-form">
                    <input type="hidden" name="user_id" value="{user['id']}">
                    <button type="submit" class="btn btn-success btn-sm">Hyväksy</button>
                  </form>
                  <form method="POST" action="/admin/users/deny" class="admin-inline-form">
                    <input type="hidden" name="user_id" value="{user['id']}">
                    <button type="submit" class="btn btn-sm" style="background: #dc2626; color: white;">Hylkää</button>
                  </form>
                </div>
                """

        user_rows += f"""
<tr>
  <td>#{user['id']}</td>
  <td>{user['name']}</td>
  <td>{user['email']}</td>
  <td><span class="pill">{role_badge}</span></td>
  <td><span class="status {'status-confirmed' if user.get('approved', False) else 'status-new'}">{approved_status}</span></td>
  <td>{format_helsinki_time(user.get('created_at')) if user.get('created_at') else '-'}</td>
  <td>{action_buttons}</td>
</tr>
"""

    body = f"""
<div class="admin-container">
  <div class="admin-header">
    <h2>Käyttäjien hallinta</h2>
    <div class="admin-actions">
      <a class="btn btn-ghost" href="/admin">Takaisin tilauksiin</a>
      <a class="btn btn-secondary" href="/logout">Kirjaudu ulos</a>
    </div>
  </div>
  <p class="text-muted">Hallinnoi käyttäjätilien hyväksyntää ja hylkäämistä.</p>
  <table class="admin-table admin-users-table">
    <thead><tr><th>ID</th><th>Nimi</th><th>Sähköposti</th><th>Rooli</th><th>Tila</th><th>Luotu</th><th>Toiminnot</th></tr></thead>
    <tbody>{user_rows or "<tr><td colspan='7' class='muted'>Ei käyttäjiä</td></tr>"}</tbody>
  </table>
</div>
"""
    return wrap(body, u)



@app.post("/admin/users/approve")
def admin_approve_user():
    admin_required()
    user_id = int(request.form.get("user_id"))
    users_col().update_one({"id": user_id}, {"$set": {"approved": True}})
    return redirect(url_for("admin_users"))


@app.post("/admin/users/deny")
def admin_deny_user():
    admin_required()
    user_id = int(request.form.get("user_id"))
    users_col().update_one({"id": user_id}, {"$set": {"approved": False}})
    return redirect(url_for("admin_users"))


@app.post("/admin/update")
def admin_update_order():
    u = current_user()
    if not u or u.get("role") != "admin":
        return redirect(url_for("login"))

    order_id = int(request.form.get("id"))
    new_status = request.form.get("status")

    # Validate status
    valid_statuses = ["NEW", "CONFIRMED", "IN_TRANSIT", "DELIVERED", "CANCELLED"]
    if new_status not in valid_statuses:
        return redirect(url_for("admin_home"))

    # Update order status
    result = orders_col().update_one(
        {"id": order_id},
        {"$set": {"status": new_status}}
    )

    # Add debug feedback
    if result.modified_count > 0:
        flash(f"Tilauksen #{order_id} tila päivitetty: {translate_status(new_status)}", "success")
    else:
        flash(f"Virhe: Tilauksen #{order_id} tilaa ei voitu päivittää", "error")

    return redirect(url_for("admin_home"))

def create_multi_image_section(images, image_type, order_id):
    """Create HTML for multi-image grid display"""
    # Handle both old single image format and new array format
    if not isinstance(images, list):
        images = [images] if images else []

    # Sort images by order
    images.sort(key=lambda x: x.get('order', 1))

    image_type_fi = "Nouto" if image_type == "pickup" else "Toimitus"
    images_count = len(images)

    if images_count == 0:
        # No images - show upload form
        return f"""
        <div class="image-section">
            <h3>{image_type_fi} kuvat</h3>
            <div class="image-counter">
                <span class="image-counter-text">0/15 kuvaa</span>
                <span class="image-counter-limit">Maksimi 15 kuvaa</span>
            </div>
            <form method="POST" action="/admin/order/{order_id}/upload" enctype="multipart/form-data" class="upload-form" id="{image_type}-form-{order_id}">
                <input type="hidden" name="image_type" value="{image_type}">
                <input type="file" name="image" accept=".jpg,.jpeg,.png,.webp" required onchange="submitImageForm(this)">
                <button type="submit" class="btn btn-primary">Lataa {image_type_fi.lower()} kuva</button>
                <div class="upload-status" style="display: none;">
                    <span class="uploading">Ladataan...</span>
                </div>
            </form>
        </div>"""

    # Generate grid of images
    images_html = ""
    for img in images:
        upload_date = format_helsinki_time(img.get('uploaded_at'))
        images_html += f"""
        <div class="image-item" data-image-type="{image_type}">
            <img src="{img['file_path']}" alt="{image_type_fi} kuva" class="image-thumbnail"
                 data-image-id="{img['id']}" onclick="openImageModal('{image_type}', '{img['id']}')">
            <div class="image-actions">
                <button class="image-action-btn delete" onclick="deleteImage('{order_id}', '{image_type}', '{img['id']}')"
                        title="Poista kuva">×</button>
            </div>
        </div>"""

    # Add upload form if under limit
    upload_form = ""
    if images_count < 15:
        upload_form = f"""
        <form method="POST" action="/admin/order/{order_id}/upload" enctype="multipart/form-data" class="upload-form" id="{image_type}-form-{order_id}">
            <input type="hidden" name="image_type" value="{image_type}">
            <input type="file" name="image" accept=".jpg,.jpeg,.png,.webp" required onchange="submitImageForm(this)">
            <button type="submit" class="btn btn-primary">Lataa lisää kuvia</button>
            <div class="upload-status" style="display: none;">
                <span class="uploading">Ladataan...</span>
            </div>
        </form>"""

    return f"""
    <div class="image-section">
        <h3>{image_type_fi} kuvat</h3>
        <div class="image-counter">
            <span class="image-counter-text">{images_count}/15 kuvaa</span>
            <span class="image-counter-limit">Maksimi 15 kuvaa</span>
        </div>
        <div class="images-grid">
            {images_html}
        </div>
        {upload_form}
    </div>"""


@app.get("/admin/order/<int:order_id>")
def admin_order_detail(order_id):
    u = current_user()
    if not u or u.get("role") != "admin":
        return redirect(url_for("login"))

    # Get order with user info
    pipeline = [
        {"$match": {"id": int(order_id)}},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "id",
            "as": "user"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "id": 1, "status": 1,
            "pickup_address": 1, "dropoff_address": 1,
            "distance_km": 1, "price_gross": 1,
            "reg_number": 1, "winter_tires": 1, "pickup_date": 1,
            "extras": 1, "images": 1,
            "user_name": "$user.name",
            "user_email": "$user.email"
        }}
    ]
    order_result = list(orders_col().aggregate(pipeline))

    if not order_result:
        return wrap("<div class='card'><h2>Tilaus ei löytynyt</h2></div>", u)

    order = order_result[0]

    # Get image info
    images = order.get("images", {})
    pickup_image = images.get("pickup")
    delivery_image = images.get("delivery")

    status_fi = translate_status(order.get('status', 'NEW'))

    # Create multi-image sections
    pickup_section = create_multi_image_section(images.get("pickup", []), "pickup", order_id)
    delivery_section = create_multi_image_section(images.get("delivery", []), "delivery", order_id)

    pickup_date_fi = order.get('pickup_date', 'Ei asetettu')
    if pickup_date_fi and pickup_date_fi != 'Ei asetettu':
        try:
            # Try to format the date if it's a datetime object
            if hasattr(pickup_date_fi, 'strftime'):
                pickup_date_fi = pickup_date_fi.strftime('%d.%m.%Y')
        except:
            pass

    body = f"""
    <link rel='stylesheet' href='/static/css/admin-images.css'>
    <div class="container">
        <div class="admin-order-detail">
            <div class="order-header">
                <h2>Tilaus #{order['id']} - {status_fi}</h2>
                <a href="/admin" class="btn btn-secondary">Takaisin tilauksiin</a>
            </div>

            <div class="order-info">
                <div class="info-section">
                    <h3>Tilauksen tiedot</h3>
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Asiakas:</span>
                            <span class="info-value">{order.get('user_name', 'Tuntematon')} ({order.get('user_email', 'Tuntematon')})</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Rekisterinumero:</span>
                            <span class="info-value">{order.get('reg_number', 'Ei tiedossa')}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Talvirenkaat:</span>
                            <span class="info-value">{"Kyllä" if order.get('winter_tires') else "Ei"}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Reitti:</span>
                            <span class="info-value">{order['pickup_address']} → {order['dropoff_address']}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Matka:</span>
                            <span class="info-value">{float(order.get('distance_km', 0)):.1f} km</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Hinta:</span>
                            <span class="info-value">{float(order.get('price_gross', 0)):.2f} €</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Noutopäivä:</span>
                            <span class="info-value">{pickup_date_fi}</span>
                        </div>
                    </div>
                </div>

                <div class="status-section">
                    <h3>Päivitä tila</h3>
                    <form method="POST" action="/admin/update">
                        <input type="hidden" name="id" value="{order['id']}">
                        <select name="status" class="status-select">
                            <option value="NEW" {'selected' if order['status'] == 'NEW' else ''}>UUSI</option>
                            <option value="CONFIRMED" {'selected' if order['status'] == 'CONFIRMED' else ''}>VAHVISTETTU</option>
                            <option value="IN_TRANSIT" {'selected' if order['status'] == 'IN_TRANSIT' else ''}>KULJETUKSESSA</option>
                            <option value="DELIVERED" {'selected' if order['status'] == 'DELIVERED' else ''}>TOIMITETTU</option>
                            <option value="CANCELLED" {'selected' if order['status'] == 'CANCELLED' else ''}>PERUUTETTU</option>
                        </select>
                        <button type="submit" class="btn btn-primary">Päivitä</button>
                    </form>
                </div>
            </div>

            <div class="images-section">
                {pickup_section}
                {delivery_section}
            </div>
        </div>
    </div>

    <!-- Image Modal -->
    <div id="imageModal" class="image-modal">
        <div class="image-modal-content">
            <div class="modal-header">
                <h3 class="modal-title" id="modalTitle">Kuva</h3>
                <button class="modal-close" onclick="closeImageModal()">&times;</button>
            </div>
            <div class="modal-image-container">
                <button class="modal-nav prev" onclick="prevImage()">&lsaquo;</button>
                <img id="modalImage" class="modal-image" src="" alt="">
                <button class="modal-nav next" onclick="nextImage()">&rsaquo;</button>
            </div>
            <div class="modal-footer">
                <div class="modal-image-info" id="modalImageInfo">Kuva 1/1</div>
                <div class="modal-actions">
                    <button class="btn btn-danger btn-sm" onclick="deleteCurrentImage()">Poista kuva</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    let currentImages = {{}};
    let currentImageType = '';
    let currentImageIndex = 0;
    let currentOrderId = {order_id};

    // Collect image data for modal
    function initImageModal() {{
        currentImages = {{}};

        // Collect pickup images
        currentImages.pickup = [];
        document.querySelectorAll('[data-image-type="pickup"] .image-thumbnail').forEach((img, index) => {{
            const imageId = img.getAttribute('data-image-id');
            const imageSrc = img.src;
            currentImages.pickup.push({{id: imageId, src: imageSrc, index: index}});
        }});

        // Collect delivery images
        currentImages.delivery = [];
        document.querySelectorAll('[data-image-type="delivery"] .image-thumbnail').forEach((img, index) => {{
            const imageId = img.getAttribute('data-image-id');
            const imageSrc = img.src;
            currentImages.delivery.push({{id: imageId, src: imageSrc, index: index}});
        }});
    }}

    function openImageModal(imageType, imageId) {{
        initImageModal();

        currentImageType = imageType;
        const images = currentImages[imageType];
        const imageIndex = images.findIndex(img => img.id === imageId);

        if (imageIndex !== -1) {{
            currentImageIndex = imageIndex;
            showCurrentImage();
            document.getElementById('imageModal').style.display = 'block';
        }}
    }}

    function closeImageModal() {{
        document.getElementById('imageModal').style.display = 'none';
    }}

    function showCurrentImage() {{
        const images = currentImages[currentImageType];
        if (images && images.length > 0) {{
            const currentImage = images[currentImageIndex];
            const modalImage = document.getElementById('modalImage');
            const modalTitle = document.getElementById('modalTitle');
            const modalInfo = document.getElementById('modalImageInfo');

            modalImage.src = currentImage.src;
            modalTitle.textContent = currentImageType === 'pickup' ? 'Nouto kuva' : 'Toimitus kuva';
            modalInfo.textContent = `Kuva ${{currentImageIndex + 1}}/${{images.length}}`;

            // Show/hide navigation arrows
            const prevBtn = document.querySelector('.modal-nav.prev');
            const nextBtn = document.querySelector('.modal-nav.next');

            prevBtn.style.display = images.length > 1 && currentImageIndex > 0 ? 'flex' : 'none';
            nextBtn.style.display = images.length > 1 && currentImageIndex < images.length - 1 ? 'flex' : 'none';
        }}
    }}

    function prevImage() {{
        const images = currentImages[currentImageType];
        if (currentImageIndex > 0) {{
            currentImageIndex--;
            showCurrentImage();
        }}
    }}

    function nextImage() {{
        const images = currentImages[currentImageType];
        if (currentImageIndex < images.length - 1) {{
            currentImageIndex++;
            showCurrentImage();
        }}
    }}

    function deleteCurrentImage() {{
        const images = currentImages[currentImageType];
        if (images && images.length > 0) {{
            const currentImage = images[currentImageIndex];
            deleteImage(currentOrderId, currentImageType, currentImage.id);
        }}
    }}

    function deleteImage(orderId, imageType, imageId) {{
        if (confirm('Oletko varma, että haluat poistaa tämän kuvan?')) {{
            // Create and submit delete form
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/admin/order/${{orderId}}/image/${{imageType}}/${{imageId}}/delete`;
            document.body.appendChild(form);
            form.submit();
        }}
    }}

    function submitImageForm(fileInput) {{
        if (fileInput.files && fileInput.files.length > 0) {{
            // Show loading indicator
            const form = fileInput.closest('form');
            const uploadStatus = form.querySelector('.upload-status');
            const submitButton = form.querySelector('button[type="submit"]');

            uploadStatus.style.display = 'block';
            submitButton.style.display = 'none';

            // Submit the form
            form.submit();
        }}
    }}

    // Close modal when clicking outside
    window.onclick = function(event) {{
        const modal = document.getElementById('imageModal');
        if (event.target === modal) {{
            closeImageModal();
        }}
    }}

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {{
        const modal = document.getElementById('imageModal');
        if (modal.style.display === 'block') {{
            if (e.key === 'Escape') {{
                closeImageModal();
            }} else if (e.key === 'ArrowLeft') {{
                prevImage();
            }} else if (e.key === 'ArrowRight') {{
                nextImage();
            }}
        }}
    }});
    </script>
    """

    return wrap(body, u)


@app.post("/admin/order/<int:order_id>/upload")
def admin_upload_image(order_id):
    u = current_user()
    if not u or u.get("role") != "admin":
        return redirect(url_for("login"))

    image_type = request.form.get("image_type")
    if image_type not in ["pickup", "delivery"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    if 'image' not in request.files:
        flash("Kuvaa ei valittu", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    file = request.files['image']
    if file.filename == '':
        flash("Kuvaa ei valittu", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    # Save and process image
    image_info, error = save_order_image(file, order_id, image_type)

    if error:
        # Translate common error messages to Finnish
        finnish_error = error
        if "File too large" in error:
            finnish_error = "Tiedosto on liian suuri (max 5MB)"
        elif "Invalid file type" in error:
            finnish_error = "Virheellinen tiedostotyyppi"
        elif "Error processing image" in error:
            finnish_error = "Virhe kuvan käsittelyssä"
        elif "Upload failed" in error:
            finnish_error = "Lataus epäonnistui"

        flash(finnish_error, "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    # Update order with image metadata
    image_info["uploaded_by"] = u.get("email", "admin")

    # Get current order to check existing images
    order = orders_col().find_one({"id": int(order_id)}, {"images": 1})
    images = order.get("images", {}) if order else {}
    current_images = images.get(image_type, [])

    # Ensure current_images is a list (handle migration from old format)
    if not isinstance(current_images, list):
        current_images = [current_images] if current_images else []

    # Check 15-image limit
    if len(current_images) >= 15:
        image_type_fi = "nouto" if image_type == "pickup" else "toimitus"
        flash(f"Maksimimäärä (15) {image_type_fi} kuvia saavutettu", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    # Set the order number for the new image
    image_info["order"] = len(current_images) + 1

    # Add new image to the array
    current_images.append(image_info)

    # Update the database with the new images array
    orders_col().update_one(
        {"id": int(order_id)},
        {"$set": {f"images.{image_type}": current_images}}
    )

    image_type_fi = "Nouto" if image_type == "pickup" else "Toimitus"
    flash(f"{image_type_fi} kuva ladattu onnistuneesti", "success")
    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.post("/admin/order/<int:order_id>/image/<image_type>/delete")
def admin_delete_image(order_id, image_type):
    u = current_user()
    if not u or u.get("role") != "admin":
        return redirect(url_for("login"))

    if image_type not in ["pickup", "delivery"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    success, message = delete_order_image(order_id, image_type)

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

    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.post("/admin/order/<int:order_id>/image/<image_type>/<image_id>/delete")
def admin_delete_image_by_id(order_id, image_type, image_id):
    u = current_user()
    if not u or u.get("role") != "admin":
        return redirect(url_for("login"))

    if image_type not in ["pickup", "delivery"]:
        flash("Virheellinen kuvatyyppi", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    success, message = delete_order_image_by_id(order_id, image_type, image_id)

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

    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.get("/order/new")
def order_new_redirect():
    return redirect("/order/new/step1")


def progress_step(status: str) -> int:
    # 3-vaiheinen palkki: 1=Noudettu, 2=Kuljetuksessa, 3=Toimitettu
    status = (status or "").upper()
    mapping = {
        "NEW": 0,          # uusi tilaus, ei vielä noudettu
        "CONFIRMED": 0,    # vahvistettu, odottaa noutoa
        "IN_TRANSIT": 2,   # kuljetuksessa (noudettu + kuljetuksessa)
        "DELIVERED": 3,    # toimitettu (kaikki vaiheet valmiit)
        "CANCELLED": 0     # peruttu -> ei edistystä
    }
    return mapping.get(status, 0)


def is_active_status(status: str) -> bool:
    return (status or "").upper() in ("NEW", "CONFIRMED", "IN_TRANSIT")


# ----------------- API -----------------
@app.post("/api/quote_for_addresses")
def api_quote_for_addresses():
    payload = request.get_json(force=True, silent=True) or {}
    pickup = payload.get("pickup", "").strip()
    dropoff = payload.get("dropoff", "").strip()
    return_leg = bool(payload.get("return_leg", False))  # optional flag
    if not pickup or not dropoff:
        return jsonify({"error": "Lähtö- ja kohdeosoite vaaditaan"}), 400

    try:
        km = route_km(pickup, dropoff)
        net, vat, gross, details = price_from_km(km, pickup, dropoff, return_leg=return_leg)
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
    net, vat, gross = price_from_km(km)
    return jsonify({"net": net, "vat": vat, "gross": gross})


import order_wizard
import marketing

# ----------------- START -----------------
if __name__ == "__main__":
    init_db()
    seed_admin()
    migrate_images_to_array()  # Migrate existing single images to array format
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
