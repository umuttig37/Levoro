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

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
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
    """Return (lat, lon) for address using Nominatim."""
    r = requests.get(NOMINATIM_URL, params={"format": "json", "q": addr},
                     headers={"User-Agent": USER_AGENT, "Accept-Language": "fi"},
                     timeout=12)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"Address not found: {addr}")
    return float(data[0]["lat"]), float(data[0]["lon"])


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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
<style>
:root{
  --bg:#ffffff; --text:#0b1020; --muted:#5b677d; --accent:#2563eb; --accent-2:#1d4ed8;
  --border:#e6e8ee; --card:#ffffff; --shadow:0 8px 24px rgba(16,24,40,.06);
  --ok:#16a34a; --warn:#ea580c; --bad:#dc2626;
}
#map { width:100%; height:320px; border-radius:14px; border:1px solid var(--border); }
.autocomplete { position:relative }
.ac-list { position:absolute; left:0; right:0; top:100%; z-index:20; background:#fff; border:1px solid var(--border); border-radius:12px; box-shadow:var(--shadow); overflow:hidden; display:none; }
.ac-item { padding:8px 10px; cursor:pointer; }
.ac-item:hover { background:#f3f6ff }

/* === Suggestion list / autocomplete === */
.autocomplete { position:relative }
.ac-list { position:absolute; left:0; right:0; top:100%; z-index:30; background:#fff;
  border:1px solid var(--line); border-radius:12px; box-shadow:0 12px 28px rgba(16,24,40,.12);
  overflow:hidden; display:none; max-height:260px; overflow-y:auto; }
.ac-item { padding:10px 12px; cursor:pointer; white-space:nowrap; text-overflow:ellipsis; overflow:hidden; }
.ac-item:hover, .ac-item.active { background:#eef2ff }
.ac-empty { padding:10px 12px; color:var(--muted) }

/* === Map === */
#map, .mini-map { width:100%; height:320px; border-radius:14px; border:1px solid var(--line) }
.mini-map { height:220px }
.leaflet-control-zoom a { border-radius:8px !important }


*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text)}
a{color:var(--accent);text-decoration:none}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--border);z-index:10}
.header-inner{max-width:1100px;margin:0 auto;padding:14px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.header-inner{max-width:1100px;margin:0 auto;padding:6px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}

.brand{display:flex;align-items:center}
.brand-link{display:flex;align-items:center; overflow:visible}
.brand .logo{
  width:36px; height:36px; display:block; object-fit:contain;
  transform: scale(3.5);           /* näyttää ~61px, mutta layout pysyy 36px */
  transform-origin: left center;   /* kasvu oikealle päin */
}
header{ overflow:visible; }         /* varmuuden vuoksi, ettei leikkaannu */


.nav{display:flex;gap:14px;flex-wrap:wrap}
.nav a{padding:8px 12px;border-radius:10px;color:#0b1020}
.nav a:hover{background:#f3f5f9}
main{max-width:1100px;margin:22px auto;padding:0 16px 48px}
footer{border-top:1px solid var(--border);padding:14px 16px;color:var(--muted);text-align:center;background:#fff}

.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:16px;box-shadow:var(--shadow)}
.card h2{margin:0 0 8px 0}
.grid{display:grid;gap:16px}
.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:900px){.cols-2{grid-template-columns:1fr}}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}

label{display:block;margin:8px 0 6px;color:var(--muted);font-size:13px}
input,textarea,select{width:100%;padding:12px 12px;border-radius:12px;border:1px solid var(--border);background:#fff;color:var(--text);outline:none}
input:focus,textarea:focus,select:focus{border-color:#c7d2fe;box-shadow:0 0 0 4px #e0e7ff}
button{background:var(--accent);color:#fff;border:none;padding:10px 14px;border-radius:12px;font-weight:600;cursor:pointer}
button:hover{background:var(--accent-2)}
.ghost{background:#f6f8fc;color:#0b1020;border:1px solid var(--border)}
.ghost:hover{background:#eef2f9}

table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid var(--border);padding:12px 10px;text-align:left;vertical-align:top}
thead th{font-size:13px;color:var(--muted);font-weight:600}

.status{font-weight:700}
.status.NEW{color:var(--warn)}
.status.CONFIRMED{color:var(--ok)}
.status.IN_TRANSIT{color:#2563eb}
.status.DELIVERED{color:#059669}
.status.CANCELLED{color:var(--bad)}

.pill{padding:6px 10px;border-radius:999px;border:1px solid var(--border);background:#f8fafc;font-size:13px;color:#0b1020}

.wizard{display:grid;grid-template-columns:280px 1fr;gap:20px}
@media(max-width:900px){.wizard{grid-template-columns:1fr}}
.stepnav{background:#fff;border:1px solid var(--border);border-radius:16px;padding:12px}
.stepnav .item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:12px}
.stepnav .item.active{background:#f3f6ff;border:1px solid #dbe5ff}

.progress{display:flex;gap:18px;align-items:center;margin:6px 0 14px}
.progress .node{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:110px}
.progress .dot{width:26px;height:26px;border-radius:999px;border:2px solid #d1d5db;background:#fff;
  display:grid;place-items:center;font-size:12px;color:#6b7280}
.progress .dot.done{background:#2563eb;color:#fff;border-color:#2563eb}
.progress .label{font-size:12px;color:#6b7280;text-align:center}
.progress .bar{height:2px;flex:1;background:#e5e7eb}
.progress .bar.done{background:#2563eb}

.tabs{display:flex;gap:8px;margin:8px 0 14px}
.tab{padding:8px 12px;border-radius:999px;border:1px solid var(--border);background:#fff;color:#0b1020}
.tab.active{background:#2563eb;color:#fff;border-color:#2563eb}

/* pieni “kuitti”-kortti hintaa varten */
.receipt{border:1px dashed #d1d5db;border-radius:14px;padding:12px;background:#fbfdff}
.receipt .rowline{display:flex;justify-content:space-between;margin:4px 0}
.receipt .total{font-weight:700;font-size:18px}
.small{font-size:12px;color:var(--muted)}

.callout{background:#f3f6ff;border:1px solid #dbe5ff;border-radius:12px;padding:10px}
</style>
</head><body>
<header>
  <div class="header-inner">
    <div class="brand">
        <a href="/" class="brand-link" aria-label="Etusivu">
        <img src="__LOGO__" alt="" class="logo">
      </a>
    </div>
    <nav class="nav">
      <a href="/">Etusivu</a>
      <a href="/order/new/step1">Uusi tilaus</a>
      <a href="/dashboard">Oma sivu</a>
      __ADMIN__
      __AUTH__
    </nav>
  </div>
</header>
<main>
"""

PAGE_FOOT = """
</main>
<footer class="muted" style="text-align:center">
© 2025 – Levoro
</footer>
</body></html>
"""


def wrap(content: str, user=None):
    # Yläpalkin oikea reuna: kirjautumislinkit tai käyttäjän nimi + ulos
    if not user:
        auth = "<a href='/login'>Kirjaudu</a> <a class='ghost' href='/register'>Luo tili</a>"
    else:
        auth = f"<span class='pill'>Hei, {user['name']}</span> <a class='ghost' href='/logout'>Ulos</a>"

    # Logo ja admin-linkki
    from flask import url_for
    logo_src = url_for('static', filename='LevoroLogo.png')
    admin_link = '<a href="/admin">Admin</a>' if (user and user.get("role") == "admin") else ""

    # Kootaan head
    head = (
        PAGE_HEAD
        .replace("__LOGO__", logo_src)
        .replace("__ADMIN__", admin_link)
        .replace("__AUTH__", auth)
    )

    # Etenemispalkin (progress-tracker) CSS – käytössä esim. order_view:ssa
    progress_css = """
    <style>
/* --- 3-step progress (Picked up -> In transit -> Delivered) --- */
.progress{
  display:flex;
  align-items:center;
  gap:12px;
  margin:10px 0 18px;
}

/* solmut (pallot + labelit) */
.progress .node{
  display:flex;
  flex-direction:column;
  align-items:center;
  gap:6px;
  flex:0 0 auto;              /* ei veny */
  min-width:72px;             /* pitää solmut paikoillaan */
}

/* pallo */
.progress .dot{
  position:static !important; /* yliajaa aiemman absolute-tyylin */
  transform:none !important;  /* ei siirtoja */
  width:28px;
  height:28px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:700;
  color:#9aa3b2;
  background:#eef1f7;
  border:3px solid #cfd8e3;
}
.progress .dot.done{
  background:#6c63ff;
  border-color:#6c63ff;
  color:#fff;
}

/* label pallon alla */
.progress .label{
  font-size:12px;
  color:#667085;
  white-space:nowrap;
  text-align:center;
}

/* väliviivat solmujen välissä */
.progress .bar{
  position:relative !important;  /* varmistetaan ettei absolute sotke */
  flex:1 1 auto;
  height:6px;
  border-radius:999px;
  background:#e9eef5;
}
.progress .bar.done{
  background:linear-gradient(90deg,#6c63ff 0%, #6c63ff 100%);
}
</style>

    """

    # Palautetaan koko sivu
    return head + progress_css + content + PAGE_FOOT



# ----------------- ROUTES: HOME -----------------
@app.get("/")
def home():
    u = current_user()
    body = """
<style>
  /* tausta hieman vaaleaksi, jotta kuplat erottuvat */
  html, body { background:#f8fafc; }

  .mx { max-width: 1100px; margin: 0 auto; padding: 0 16px; }

  /* --- Hero --- */
  .hero {
    margin: 28px auto 18px; border-radius: 18px; color: #fff;
    background:
      radial-gradient(800px 200px at 10% 10%, rgba(59,130,246,.35), transparent 60%),
      linear-gradient(180deg,#0b1020 0%,#111829 70%,#0b1020 100%);
    box-shadow: 0 16px 48px rgba(0,0,0,.25);
  }
  .hero-inner { padding: 40px 22px 26px 22px; }
  .badge {
    display:inline-block; padding:8px 12px; border-radius:999px;
    background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.2);
    font-size:13px
  }
  .title { font-size: clamp(38px, 5.2vw, 64px); line-height:1.04; letter-spacing:-.02em; margin:10px 0 6px }
  .sub   { font-size:18px; opacity:.9; max-width: 760px }
  .cta   { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px }
  .btn   { display:inline-flex; align-items:center; gap:10px; padding:12px 16px; border-radius:12px; font-weight:700; text-decoration:none }
  .btn-primary { background:linear-gradient(180deg,#3b82f6,#1d4ed8); color:#fff; box-shadow:0 10px 24px rgba(37,99,235,.35) }
  .btn-ghost   { background:rgba(255,255,255,.08); color:#fff; border:1px solid rgba(255,255,255,.2) }

  .chiprow{ display:flex; gap:10px; flex-wrap:wrap; margin-top:14px }
  .chip{
    padding:6px 10px; border-radius:999px;
    background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.22);
    font-size:13px; color:#fff
  }

  /* --- Content sections --- */
  .section { margin: 26px 0; }
  .h2 { font-size: 28px; margin: 0 0 10px 0; color:#0b1020 }

  .grid3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px }
  @media(max-width:900px){ .grid3{ grid-template-columns:1fr } }
  .card { background:#fff; border:1px solid #e6e8ee; border-radius:16px; padding:18px; box-shadow:0 8px 24px rgba(16,24,40,.06) }
  .card h3{ margin:6px 0 6px; color:#0b1020 }
  .card p{ color:#5b677d }
  .icon{ width:36px; height:36px; border-radius:10px; display:grid; place-items:center; background:#eef2ff; color:#1d4ed8; font-weight:800 }

  .steps{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px }
  @media(max-width:900px){ .steps{ grid-template-columns:1fr } }
  .step .num{
    width:28px; height:28px; border-radius:999px; display:inline-grid; place-items:center;
    font-weight:800; background:#111827; color:#fff; margin-right:8px
  }

  /* --- Vakuutusbanneri + iso ikoni --- */
  .banner{
    background:#0b1020; color:#fff; border-radius:16px; padding:18px;
    display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
  }
  .banner-left{ display:flex; align-items:center; gap:14px; }
  .shield{
    width:72px; height:72px; border-radius:18px;
    background: linear-gradient(180deg,#ecfdf5,#dcfce7);
    border:1px solid #bbf7d0; display:grid; place-items:center;
    box-shadow: 0 8px 20px rgba(16,185,129,.25);
  }
  .shield svg{ width:36px; height:36px; stroke:#16a34a; }
  .shield svg path{ vector-effect: non-scaling-stroke; }
  .banner-title{ font-weight:800; font-size:18px; line-height:1.25; margin-bottom:2px }
  .banner-sub{ opacity:.92 }

  /* --- Vihreät reunakuplat (elementteinä) --- */
  :root{
    --bubble-green-1: rgba(16,185,129,.28);
    --bubble-green-2: rgba(20,184,166,.22);
  }
  .bg-bubble{
    position: fixed; z-index: 0; pointer-events:none;
    width: 660px; height: 660px;
    background:
      radial-gradient(closest-side at 60% 40%, var(--bubble-green-1), rgba(0,0,0,0) 70%),
      radial-gradient(closest-side at 30% 70%, var(--bubble-green-2), rgba(0,0,0,0) 70%);
    filter: blur(1px);
  }
  .bg-bubble.left  { left:-180px; bottom:40px;  transform: rotate(-8deg); }
  .bg-bubble.right { right:-160px; top:120px;   transform: rotate(16deg); }

  /* sisältö varmasti kuplien päällä */
  .mx, .hero, .section { position: relative; z-index: 1; }

  /* mobiilissa pienemmäksi */
  @media (max-width: 900px){
    .bg-bubble{ width: 380px; height: 380px; }
    .bg-bubble.left{ left:-120px; bottom:10px; }
    .bg-bubble.right{ right:-110px; top:80px; }
  }
  
  /* Badge: iso emoji, teksti normaalina */
.badge{
  display:inline-flex; align-items:center; gap:8px;
  padding:8px 12px; border-radius:999px;
  background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.2);
  font-size:13px;  /* säilytä tekstin koko */
}
.badge-emoji{
  font-size:20px;   /* itse emojin koko */
  line-height:1; 
  transform: translateY(1px); /* tasaa emojin baselinea */
}
</style>

<!-- Reunakuplat -->
<div class="bg-bubble left"></div>
<div class="bg-bubble right"></div>

<!-- HERO -->
<div class="mx hero">
  <div class="hero-inner">
    <span class="badge"><span class="badge-emoji" aria-hidden="true">🚗</span> Saman päivän auton kuljetukset</span>
    <h1 class="title">Samana päivänä, ja halvin.<br/>Levorolla mahdollista.</h1>
    <p class="sub">Suomen nopein, edullisin ja luotettavin tapa siirtää autoja. Läpinäkyvä hinnoittelu, reaaliaikainen seuranta ja helppo tilausportaali.</p>
    <div class="cta">
      <a class="btn btn-primary" href="/calculator">Laske halvin hinta nyt</a>
      <a class="btn btn-ghost" href="#how">Miten se toimii</a>
    </div>
    <div class="chiprow">
      <div class="chip">Toimitus samana päivänä</div>
      <div class="chip">PK-seudulla kuljetukset 30€</div>
      <div class="chip">Kokeilualennus yritysasiakkaille</div>
    </div>
  </div>
</div>

<!-- MIKSI MEIDÄT -->
<div class="mx section">
  <h2 class="h2">Miksi valita meidät</h2>
  <div class="grid3">
    <div class="card">
      <div class="icon">⚡</div>
      <h3>Nopeus</h3>
      <p>Optimointi, eurooppalaiset vakioreitit ja oma verkosto. Useimmat toimitukset 3–5 päivässä.</p>
    </div>
    <div class="card">
      <div class="icon">💶</div>
      <h3>Hinta</h3>
      <p>Reilu ja läpinäkyvä. Ei piilokuluja – näet hinnan ennen tilausta.</p>
    </div>
    <div class="card">
      <div class="icon">🛡️</div>
      <h3>Luotettavuus</h3>
      <p>Vakuutus koko matkan, CMR-dokumentointi ja seuranta portaalissa.</p>
    </div>
  </div>
</div>

<!-- MITEN SE TOIMII -->
<div id="how" class="mx section">
  <h2 class="h2">Miten se toimii</h2>
  <div class="steps">
    <div class="card step"><h3><span class="num">1</span>Lähetä reitti</h3><p>Valitse nouto ja kohde portaalissa. Saat hinnan heti.</p></div>
    <div class="card step"><h3><span class="num">2</span>Vahvista tilaus</h3><p>Valitse sopiva aika ja lisää tiedot (avaimet, yhteyshenkilöt).</p></div>
    <div class="card step"><h3><span class="num">3</span>Seuraa toimitusta</h3><p>Näet etenemisen ja saat ilmoitukset – kuittaukset tallentuvat portaaliin.</p></div>
  </div>
</div>

<!-- VAKUUTUSBANNERI + ISO IKONI -->
<div class="mx section">
  <div class="banner">
    <div class="banner-left">
      <div class="shield">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3l7 3v5c0 5-3.5 9-7 10-3.5-1-7-5-7-10V6l7-3z" fill="none" stroke-width="2" stroke-linejoin="round"></path>
          <path d="M8 12l3 3 5-5" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
      </div>
      <div>
        <div class="banner-title">Kaikki ajamamme autot suojattu täysin vastuuvakuutuksella</div>
        <div class="banner-sub">Vakuutusturva koko kuljetuksen ajan – ilman lisämaksuja.</div>
      </div>
    </div>
    <a class="btn btn-primary" href="/calculator">Laske hinta →</a>
  </div>
</div>

<!-- FOOTER-CTA -->
<div class="mx section" style="text-align:center; margin-bottom:34px">
  <div style="font-size:14px; color:#5b677d">Onko sinulla jo tili?</div>
  <div class="cta" style="justify-content:center; margin-top:8px">
    <a class="btn btn-ghost" href="/login">Kirjaudu sisään</a>
    <a class="btn btn-ghost" href="/register">Luo yritystili</a>
  </div>
</div>
"""
    return wrap(body, u)




# ----------------- AUTH -----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return wrap("""
<div class="card">
  <h2>Luo tili</h2>
  <form method="POST" class="grid cols-2">
    <div class="card">
      <label>Nimi</label><input name="name" required>
      <label>Sähköposti</label><input type="email" name="email" required>
      <label>Salasana</label><input type="password" name="password" minlength="6" required>
      <button type="submit" style="margin-top:10px">Rekisteröidy</button>
    </div>
  </form>
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
        "created_at": datetime.datetime.utcnow(),
    })
    session["uid"] = uid
    return redirect("/dashboard")



@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")

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
        nxt = request.args.get("next", "/")
        body = """
<div class="card">
  <h2>Kirjaudu</h2>
  <form method="POST" class="grid cols-2">
    <div class="card">
      <label>Sähköposti</label><input type="email" name="email" required>
      <label>Salasana</label><input type="password" name="password" required>
      <input type="hidden" name="next" value="__NEXT__">
      <button type="submit" style="margin-top:10px">Kirjaudu</button>
    </div>
    <div class="card muted">Tarvitsetko tilin? <a href="/register">Luo tili</a>.</div>
  </form>
</div>
""".replace("__NEXT__", nxt)
        return wrap(body, current_user())

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    nxt = request.form.get("next") or "/"

    row = users_col().find_one({"email": email}, {"_id": 0, "id": 1, "password_hash": 1})
    if not row or not check_password_hash(row.get("password_hash", ""), password):
        return wrap("<div class='card'><h3>Väärä sähköposti tai salasana</h3></div>", current_user())

    session["uid"] = int(row["id"])
    return redirect(nxt or "/")



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
        rows += f"""
<tr>
  <td>#{r['id']}</td>
  <td><span class="status {r['status']}">{r['status']}</span></td>
  <td>{r['pickup_address']} → {r['dropoff_address']}</td>
  <td>{float(r['distance_km']):.1f} km</td>
  <td>{float(r['price_gross']):.2f} €</td>
  <td><a class="ghost" href="/order/{r['id']}">Avaa</a></td>
</tr>
"""

    tabs_html = f"""
<div class="tabs">
  <a href="/dashboard?tab=active" class="{'active' if tab=='active' else ''}">Aktiiviset</a>
  <a href="/dashboard?tab=completed" class="{'active' if tab=='completed' else ''}">Valmistuneet</a>
</div>
"""

    body = f"""
<div class="card">
  <h2>Omat tilaukset</h2>
  {tabs_html}
  <div class="row"><a class="ghost" href="/order/new/step1">+ Uusi tilaus</a></div>
  <table>
    <thead><tr><th>ID</th><th>Tila</th><th>Reitti</th><th>Km</th><th>Hinta</th><th></th></tr></thead>
    <tbody>{rows or "<tr><td colspan='6' class='muted'>Ei tilauksia</td></tr>"}</tbody>
  </table>
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

    # sama 3-step palkki kuin aiemmin
    bar = f"""
<div class="progress">
  <div class="node">
    <div class="dot {'done' if step >= 1 else ''}">1</div>
    <div class="label">Picked up</div>
  </div>
  <div class="bar {'done' if step >= 1 else ''}"></div>
  <div class="node">
    <div class="dot {'done' if step >= 2 else ''}">2</div>
    <div class="label">In transit</div>
  </div>
  <div class="bar {'done' if step >= 3 else ''}"></div>
  <div class="node">
    <div class="dot {'done' if step >= 3 else ''}">3</div>
    <div class="label">Delivered</div>
  </div>
</div>
"""

    body = f"""
<div class="card">
  <h2>Tilaus #{r['id']}</h2>
  <p><strong>Tila:</strong> <span class="status {r.get('status','NEW')}">{r.get('status','NEW')}</span></p>
  {bar}
  <table>
    <tr><th>Reitti</th><td>{r.get('pickup_address','?')} → {r.get('dropoff_address','?')}</td></tr>
    <tr><th>Ajoneuvo</th><td>{r.get('vin','') or ''} {r.get('make','') or ''} {r.get('model','') or ''}</td></tr>
    <tr><th>Talvirenkaat</th><td>{"Kyllä" if r.get('winter_tires') else "Ei"}</td></tr>
    <tr><th>Km</th><td>{distance_km:.1f}</td></tr>
    <tr><th>Hinta</th><td><strong>{price_gross:.2f} €</strong></td></tr>
    <tr><th>Lisätiedot</th><td>{(r.get('additional_info') or '').replace('<', '&lt;')}</td></tr>
    <tr><th>PIN</th><td><span class="pill">{r.get('pin','')}</span></td></tr>
  </table>
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
        tr += f"""
<tr>
  <td>#{r['id']}</td>
  <td><span class="status {r['status']}">{r['status']}</span></td>
  <td>{r.get('user_name','?')} &lt;{r.get('user_email','?')}&gt;</td>
  <td>{r['pickup_address']} → {r['dropoff_address']}</td>
  <td>{distance_km:.1f} km</td>
  <td>{price_gross:.2f} €</td>
  <td>
    <form method="POST" action="/admin/update" class="row" style="gap:6px">
      <input type="hidden" name="id" value="{r['id']}">
      <select name="status">
        <option {'selected' if r['status'] == 'NEW' else ''}>NEW</option>
        <option {'selected' if r['status'] == 'CONFIRMED' else ''}>CONFIRMED</option>
        <option {'selected' if r['status'] == 'IN_TRANSIT' else ''}>IN_TRANSIT</option>
        <option {'selected' if r['status'] == 'DELIVERED' else ''}>DELIVERED</option>
        <option {'selected' if r['status'] == 'CANCELLED' else ''}>CANCELLED</option>
      </select>
      <button>Päivitä</button>
    </form>
  </td>
</tr>
"""
    body = f"""
<div class="card">
  <div class="row" style="justify-content:space-between">
    <h2>Admin – Tilaukset</h2>
    <a class="ghost" href="/logout">Kirjaudu ulos</a>
  </div>
  <table>
    <thead><tr><th>ID</th><th>Tila</th><th>Asiakas</th><th>Reitti</th><th>Km</th><th>Hinta</th><th>Päivitä</th></tr></thead>
    <tbody>{tr or "<tr><td colspan='7' class='muted'>Ei tilauksia</td></tr>"}</tbody>
  </table>
</div>
"""
    return wrap(body, u)



@app.post("/admin/update")
def admin_update():
    admin_required()
    oid = int(request.form.get("id"))
    status = (request.form.get("status") or "NEW").strip()
    orders_col().update_one({"id": oid}, {"$set": {"status": status}})
    return redirect(url_for("admin_home"))



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
