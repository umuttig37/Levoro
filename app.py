import os
import secrets
import datetime
import requests

from flask import Flask, request, redirect, url_for, session, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
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
METRO_GROSS = float(os.getenv("METRO_GROSS", "30"))  # 30–32€ → default 30€
MID_KM = 170.0  # “about 150–200 km”
MID_GROSS = float(os.getenv("MID_GROSS", "90"))  # ~90€
LONG_KM = 600.0
LONG_GROSS = float(os.getenv("LONG_GROSS", "230"))  # ~230€
ROUNDTRIP_DISCOUNT = 0.30  # 30% off return leg

SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
SEED_ADMIN_PASS = os.getenv("SEED_ADMIN_PASS", "admin123")
SEED_ADMIN_NAME = os.getenv("SEED_ADMIN_NAME", "Admin")

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
# NOMINATIM_URL removed - using Google Places API only
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"

USER_AGENT = "Umut-Autotransport-Portal/1.0 (contact: example@example.com)"

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
            "created_at": datetime.datetime.utcnow(),
        })



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
    """Compute driving distance in km with OSRM. Falls back to 0.0 on error."""
    lat1, lon1 = geocode(pickup_addr)
    lat2, lon2 = geocode(dropoff_addr)
    url = OSRM_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
    r.raise_for_status()
    j = r.json()
    if not j.get("routes"):
        raise ValueError("Route not found")
    meters = j["routes"][0]["distance"]
    return meters / 1000.0


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
    from flask import url_for
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

    return head + content + foot


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
        <div class="hero-feature">PK-seudulla kuljetukset 30€</div>
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
        "created_at": datetime.datetime.utcnow(),
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

        print(f"[DEBUG] Google Places API request: {url}")
        print(f"[DEBUG] Request params: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        print(f"[DEBUG] HTTP Status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        print(f"[DEBUG] Google API Response: {data}")

        if data.get("status") == "OK":
            print(f"[DEBUG] Success: Found {len(data.get('predictions', []))} predictions")
            return jsonify({
                "predictions": data.get("predictions", []),
                "status": data.get("status"),
                "source": "google"
            })
        else:
            error_msg = f"Google Places API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            print(f"[ERROR] {error_msg}")
            return jsonify({"error": error_msg}), 500

    except requests.exceptions.RequestException as e:
        error_msg = f"HTTP request failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_msg = f"Google Places API failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
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
        
        print(f"[DEBUG] Testing Google Places API with geocoding: {url}")
        response = requests.get(url, params=params, timeout=10)
        print(f"[DEBUG] Test response status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        print(f"[DEBUG] Test response data: {data}")
        
        return jsonify({
            "status": "success",
            "api_key_valid": data.get("status") == "OK",
            "google_response": data
        })
        
    except Exception as e:
        error_msg = f"API test failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.post("/api/route_geo")
def api_route_geo():
    data = request.get_json(force=True, silent=True) or {}
    pickup = (data.get("pickup") or "").strip()
    dropoff = (data.get("dropoff") or "").strip()
    if not pickup or not dropoff:
        return jsonify({"error": "pickup and dropoff required"}), 400

    # geocode -> lat/lon
    lat1, lon1 = geocode(pickup)
    lat2, lon2 = geocode(dropoff)

    # OSRM with full geometry for map
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        "?overview=full&geometries=geojson"
    )
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if not j.get("routes"):
        return jsonify({"error": "no route"}), 404
    route = j["routes"][0]
    km = route["distance"] / 1000.0
    coords = route["geometry"]["coordinates"]  # [ [lon,lat], ... ]
    # muunna [lon,lat] -> [lat,lon] Leafletille:
    latlngs = [[c[1], c[0]] for c in coords]
    return jsonify({"km": round(km, 2), "latlngs": latlngs, "start": [lat1, lon1], "end": [lat2, lon2]})


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

    step = progress_step(r.get("status", "NEW"))

    # Progress bar with better styling
    bar = f"""
<div class="order-progress">
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
    body = f"""
<link rel='stylesheet' href='/static/css/order-view.css'>
<div class="order-container">
  <div class="order-header">
    <h1 class="order-title">Tilaus #{r['id']}</h1>
    <div class="order-status">
      <span class="status-label">Tila:</span>
      <span class="status-badge status-{r.get('status','NEW').lower()}">{status_fi}</span>
    </div>
  </div>
  
  {bar}
  
  <div class="order-details">
    <div class="detail-section full-width">
      <h3 class="section-title">Reitti</h3>
      <div class="route-info">
        <div class="route-point pickup">
          <span class="route-label">Nouto:</span>
          <span class="route-address">{r.get('pickup_address','?')}</span>
        </div>
        <div class="route-arrow">→</div>
        <div class="route-point delivery">
          <span class="route-label">Toimitus:</span>
          <span class="route-address">{r.get('dropoff_address','?')}</span>
        </div>
      </div>
    </div>
    
    <div class="detail-section">
      <h3 class="section-title">Ajoneuvo</h3>
      <div class="vehicle-info">
        <div class="vehicle-detail">
          <span class="detail-label">Rekisterinumero:</span>
          <span class="detail-value">{r.get('reg_number','') or 'Ei tiedossa'}</span>
        </div>
        <div class="vehicle-detail">
          <span class="detail-label">Talvirenkaat:</span>
          <span class="detail-value">{"Kyllä" if r.get('winter_tires') else "Ei"}</span>
        </div>
      </div>
    </div>
    
    <div class="detail-section">
      <h3 class="section-title">Hinta ja matka</h3>
      <div class="price-info">
        <div class="price-detail">
          <span class="detail-label">Matka:</span>
          <span class="detail-value">{distance_km:.1f} km</span>
        </div>
        <div class="price-detail highlight">
          <span class="detail-label">Hinta:</span>
          <span class="detail-value price">{price_gross:.2f} €</span>
        </div>
      </div>
    </div>

    <div class="detail-section full-width">
      <h3 class="section-title">Yhteystiedot</h3>
      <div class="contact-info">
        <div class="contact-detail">
          <span class="detail-label">Nimi:</span>
          <span class="detail-value">{r.get('customer_name','') or 'Ei tiedossa'}</span>
        </div>
        <div class="contact-detail">
          <span class="detail-label">Sähköposti:</span>
          <span class="detail-value">{r.get('email','') or 'Ei tiedossa'}</span>
        </div>
        <div class="contact-detail">
          <span class="detail-label">Puhelin:</span>
          <span class="detail-value">{r.get('phone','') or 'Ei tiedossa'}</span>
        </div>
      </div>
    </div>

    {f'''<div class="detail-section full-width">
      <h3 class="section-title">Lisätiedot</h3>
      <div class="additional-info">
        <p>{(r.get('additional_info') or 'Ei lisätietoja').replace('<', '&lt;')}</p>
      </div>
    </div>''' if r.get('additional_info') else ''}
  </div>
  
  <div class="order-actions">
    <a href="/dashboard" class="btn btn-ghost">← Takaisin tilauksiin</a>
  </div>
</div>
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
        tr += f"""
<tr>
  <td>#{r['id']}</td>
  <td><span class="status {r['status']}">{status_fi}</span></td>
  <td>{r.get('user_name','?')} &lt;{r.get('user_email','?')}&gt;</td>
  <td>{r['pickup_address']} → {r['dropoff_address']}</td>
  <td>{distance_km:.1f} km</td>
  <td>{price_gross:.2f} €</td>
  <td>
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
    <thead><tr><th>ID</th><th>Tila</th><th>Asiakas</th><th>Reitti</th><th>Km</th><th>Hinta</th><th>Päivitä</th></tr></thead>
    <tbody>{tr or "<tr><td colspan='7' class='muted'>Ei tilauksia</td></tr>"}</tbody>
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
  <td>{user.get('created_at', '').strftime('%d.%m.%Y %H:%M') if user.get('created_at') else '-'}</td>
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



@app.get("/order/new")
def order_new_redirect():
    return redirect("/order/new/step1")


def progress_step(status: str) -> int:
    # 3-vaiheinen palkki: 1=Picked up, 2=In transit, 3=Delivered
    status = (status or "").upper()
    mapping = {
        "NEW": 1,          # oletus: ennen noutoa -> näytetään 1. vaihe
        "CONFIRMED": 1,    # vahvistettu, odottaa noutoa
        "IN_TRANSIT": 2,   # kuljetuksessa
        "DELIVERED": 3,    # toimitettu
        "CANCELLED": 1     # peruttu -> jätetään alkuun
    }
    return mapping.get(status, 1)


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
        return jsonify({"error": "pickup and dropoff required"}), 400
    try:
        km = route_km(pickup, dropoff)
        net, vat, gross, details = price_from_km(km, pickup, dropoff, return_leg=return_leg)
        return jsonify({"km": round(km, 2), "net": net, "vat": vat, "gross": gross, "details": details})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
