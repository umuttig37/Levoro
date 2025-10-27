# marketing.py
from flask import redirect, url_for
from services.auth_service import auth_service

# Import wrap function and app from app - will be available after app initialization
def get_wrap():
    from app import wrap
    return wrap

def get_app():
    from app import app
    return app

app = get_app()

@app.get("/yhteystiedot")
def contact():
    u = auth_service.get_current_user()
    from app import render_template
    return render_template("contact.html", current_user=u)

@app.get("/calculator")
def calculator():
    u = auth_service.get_current_user()
    if not u:
        return redirect(url_for("auth.login", next="/calculator"))

    # Drivers cannot access calculator - redirect to their dashboard
    if u.get('role') == 'driver':
        return redirect(url_for("driver.dashboard"))

    body = """
<div class="container">
  <!-- Page Header -->
  <div class="section-padding">
    <div class="text-center mb-8">
      <h1 class="calculator-title">Laske kuljetushinta</h1>
      <p class="calculator-subtitle">Syötä lähtö- ja kohdeosoitteet saadaksesi tarkan hinnan ja nähdäksesi reitin kartalla.</p>
    </div>
  </div>

  <!-- Main Calculator -->
  <div class="calculator-grid">
    <!-- Left Column: Form + Results -->
    <div class="calculator-left-column">
      <!-- Calculator Form -->
      <div class="card calculator-form">
        <div class="card-header">
          <h2 class="card-title">Reitin tiedot</h2>
          <p class="card-subtitle">Täytä osoitteet alla oleviin kenttiin</p>
        </div>
        
        <div class="card-body">
          <div class="form-group">
            <label class="form-label">Lähtöosoite</label>
            <div class="autocomplete">
              <input id="from" class="form-input" placeholder="Esim. Antaksentie 4, Vantaa"
                     autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" name="from_addr">
              <div id="ac_from" class="ac-list"></div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Kohdeosoite</label>
            <div class="autocomplete">
              <input id="to" class="form-input" placeholder="Esim. Kirstinmäki 6, Espoo"
                     autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" name="to_addr">
              <div id="ac_to" class="ac-list"></div>
            </div>
          </div>

          <!-- Saved Addresses Section -->
          <div style="margin-top: 1.5rem; padding: 1.25rem; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
              <h3 style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #333;">Tallennetut osoitteet</h3>
              <button onclick="openAddressModal()" class="btn btn-primary btn-sm" style="font-size: 0.875rem;">
                + Lisää uusi osoite
              </button>
            </div>
            
            <button id="toggleAddresses" onclick="toggleSavedAddresses()" class="btn btn-ghost btn-sm" style="width: 100%; margin-bottom: 0.75rem;">
              Näytä tallennetut osoitteet
            </button>
            
            <div id="savedAddressesList" style="display: none;">
              <div id="addressesContainer" style="max-height: 300px; overflow-y: auto;">
                <!-- Addresses will be loaded here -->
              </div>
            </div>
          </div>

          <div class="calculator-actions">
            <button id="calcBtn" class="btn btn-primary btn-lg" onclick="calc()">Laske hinta ja reitti</button>
            <button class="btn btn-ghost" onclick="demo()">Täytä esimerkki</button>
          </div>
          
          <p id="err" class="form-error-message hidden mt-3"></p>
        </div>
      </div>

      <!-- Results Panel -->
      <div class="card calculator-results">
        <div class="card-header">
          <h2 class="card-title">Hinta ja reitti</h2>
          <p class="card-subtitle">Tulos näkyy tässä laskennan jälkeen</p>
        </div>
        
        <div class="card-body">
          <div id="receipt" class="receipt hidden">
            <div class="rowline"><span>Matka</span><span id="r_km">—</span></div>
            <div class="rowline price-main-row" style="margin: 16px 0; padding: 16px 0; border-top: 2px solid var(--color-primary); border-bottom: 2px solid var(--color-primary);">
              <span style="font-size: 1.1em; font-weight: 600;">Hinta</span>
              <div style="text-align: right;">
                <div style="font-size: 2.5em; font-weight: 800; line-height: 1.1;" id="r_net">—</div>
                <div style="font-size: 1.2em; font-weight: 700; margin-top: 4px;">ALV 0%</div>
              </div>
            </div>
            <div class="rowline" style="font-size: 0.75em; opacity: 0.6; margin: 8px 0;">
              <span>ALV 25,5%: <span id="r_vat">—</span></span>
              <span>Yhteensä sis. ALV: <span id="r_gross">—</span></span>
            </div>
          </div>

          <div id="no-results" class="calculator-no-results">
            <div class="mb-4" style="font-size: 3rem;">🗺️</div>
            <p>Syötä osoitteet laskeaksesi hinnan</p>
          </div>

          <div class="calculator-continue">
            <a id="continueBtn" href="/order/new/step1" class="btn btn-success btn-lg link-disabled">
              Jatka tilaukseen →
            </a>
          </div>
          
          <div class="calculator-footer">
            <a class="btn btn-ghost btn-sm" href="/dashboard">Omat tilaukset</a>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Column: Map -->
    <div class="calculator-right-column">
      <div class="card calculator-map">
        <div class="card-header">
          <h3 class="card-title">Reitti kartalla</h3>
          <p class="card-subtitle">Kuljetusreitti näkyy kartalla laskennan jälkeen</p>
        </div>
        <div class="calculator-map-container">
          <div id="map" class="calculator-map-element"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
// ====== Utilities ======
function euro(n){ return (Number(n).toFixed(2)+' €').replace('.',','); }
function kmfmt(n){ return Number(n).toFixed(1).replace('.',',')+' km'; }

// Add custom styles for saved addresses in autocomplete
const style = document.createElement('style');
style.textContent = `
  .ac-item.saved-address {
    padding: 0.75rem !important;
    border-left: 3px solid var(--color-primary, #007bff);
    background: #f8f9fa;
  }
  .ac-item.saved-address:hover {
    background: #e9ecef;
  }
  .menu-item:hover {
    background: #f3f4f6;
  }
`;
document.head.appendChild(style);

// ====== Google Places Autocomplete ======
class GooglePlacesAutocomplete {
  constructor(input, listEl){
    this.input = input;
    this.list = listEl;
    this.timer = null;
    this.items = [];
    this.cache = new Map();
    this.CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
    this.lastRequestTime = 0;
    this.MIN_REQUEST_INTERVAL = 500; // 500ms minimum between actual API requests
    this.isRequestInProgress = false;

    input.setAttribute('autocomplete','off');
    input.setAttribute('autocorrect','off');
    input.setAttribute('autocapitalize','off');
    input.setAttribute('spellcheck','false');

    input.addEventListener('input', ()=> this.onInput());
    input.addEventListener('focus', ()=> this.onFocus());
    input.addEventListener('keydown', (e)=> this.onKey(e));
    document.addEventListener('click', (e)=>{ if(!this.list.contains(e.target) && e.target!==this.input){ this.hide() }});
  }

  onFocus(){
    // Show saved addresses when input is focused
    const q = this.input.value.trim();
    if (!q) {
      this.showSavedAddresses();
    }
  }

  showSavedAddresses(){
    if (!window.savedAddresses || window.savedAddresses.length === 0) {
      return;
    }
    
    let html = '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e0e0e0;">Tallennetut osoitteet</div>';
    
    window.savedAddresses.slice(0, 8).forEach((addr, i) => {
      html += `<div class="ac-item saved-address" data-type="saved" data-i="${i}">
        <div style="font-weight: 600; color: #333;">${addr.displayName}</div>
        <div style="font-size: 0.875rem; color: #666;">${addr.fullAddress}</div>
      </div>`;
    });
    
    this.list.innerHTML = html;
    this.show();
    
    Array.from(this.list.querySelectorAll('.ac-item')).forEach(el=>{
      el.onclick = ()=> {
        const type = el.getAttribute('data-type');
        const index = +el.getAttribute('data-i');
        if (type === 'saved') {
          this.pickSaved(index);
        }
      };
    });
  }

  pickSaved(index){
    const addr = window.savedAddresses[index];
    if (!addr) return;
    this.input.value = addr.fullAddress;
    this.hide();
    this.input.dispatchEvent(new Event('change'));
  }

  onInput(){
    clearTimeout(this.timer);
    const q = this.input.value.trim();
    if(!q){ 
      this.showSavedAddresses();
      return; 
    }

    // Check cache first
    const cacheKey = q.toLowerCase();
    const cached = this.cache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp < this.CACHE_DURATION)) {
      this.items = cached.results;
      this.render();
      return;
    }

    // Don't start loading immediately - wait for debounce
    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequestTime;
    const debounceDelay = Math.max(400, this.MIN_REQUEST_INTERVAL - timeSinceLastRequest);

    this.timer = setTimeout(()=> {
      // Double-check we're not already making a request
      if (this.isRequestInProgress) {
        return;
      }
      this.showLoading();
      this.fetch(q);
    }, debounceDelay);
  }

  showLoading() {
    this.list.innerHTML = '<div class="ac-loading" style="padding: 0.75rem; color: #666; display: flex; align-items: center; gap: 0.5rem;"><div class="spinner"></div>Haetaan osoitteita...</div>';
    this.list.style.display = 'block';
    
    // Add spinner CSS if not already present
    if (!document.querySelector('#spinner-css')) {
      const style = document.createElement('style');
      style.id = 'spinner-css';
      style.textContent = `
        .spinner {
          width: 16px;
          height: 16px;
          border: 2px solid #e0e0e0;
          border-top: 2px solid #666;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          flex-shrink: 0;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }

  async fetch(q){
    // Prevent overlapping requests
    if (this.isRequestInProgress) {
      return;
    }

    this.isRequestInProgress = true;
    this.lastRequestTime = Date.now();

    // Use server endpoint for consistent address suggestions
    try {
      const response = await fetch('/api/places_autocomplete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: q })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      this.items = data.predictions || [];

      // Cache the results
      const cacheKey = q.toLowerCase();
      this.cache.set(cacheKey, {
        results: this.items,
        timestamp: Date.now()
      });

      this.render();
    } catch (e) {
      // Places API error - silently handle
      this.items = [];
      // Only show error after a longer delay to avoid premature error messages
      setTimeout(() => {
        if (this.list.style.display === 'block') {
          this.list.innerHTML = '<div class="ac-error" style="padding: 0.5rem; color: #ef4444;">Osoitetta ei löytynyt, yritä uudestaan</div>';
        }
      }, 500);
    } finally {
      this.isRequestInProgress = false;
    }
  }


  render(){
    const q = this.input.value.trim().toLowerCase();
    
    // Filter saved addresses that match the query
    let filteredSaved = [];
    if (q && window.savedAddresses) {
      filteredSaved = window.savedAddresses.filter(addr => 
        addr.displayName.toLowerCase().includes(q) || 
        addr.fullAddress.toLowerCase().includes(q)
      ).slice(0, 5);
    }
    
    let html = '';
    
    // Show saved addresses section if there are matches
    if (filteredSaved.length > 0) {
      html += '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e0e0e0;">Tallennetut osoitteet</div>';
      filteredSaved.forEach((addr, i) => {
        html += `<div class="ac-item saved-address" data-type="saved" data-i="${window.savedAddresses.indexOf(addr)}">
          <div style="font-weight: 600; color: #333;">${addr.displayName}</div>
          <div style="font-size: 0.875rem; color: #666;">${addr.fullAddress}</div>
        </div>`;
      });
    }
    
    // Show map search results
    if (this.items.length > 0) {
      if (filteredSaved.length > 0) {
        html += '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e0e0e0; margin-top: 0.5rem;">Karttahaku</div>';
      }
      html += this.items.slice(0, 8).map((item, i) =>
        `<div class="ac-item" data-type="map" data-i="${i}">${item.description}</div>`
      ).join('');
    }
    
    if (!html) {
      this.list.innerHTML = '<div class="ac-empty">Ei ehdotuksia</div>';
      this.show();
      return;
    }
    
    this.list.innerHTML = html;
    this.show();

    Array.from(this.list.children).forEach(el=>{
      if (el.classList.contains('ac-item')) {
        const type = el.getAttribute('data-type');
        const index = +el.getAttribute('data-i');
        el.onclick = ()=> {
          if (type === 'saved') {
            this.pickSaved(index);
          } else {
            this.pick(index);
          }
        };
      }
    });
    this.activeIndex = -1;
  }

  onKey(e){
    if(this.list.style.display!=='block') return;
    const max = this.items.length - 1;
    if(e.key==='ArrowDown'){ e.preventDefault(); this.activeIndex = Math.min(max, (this.activeIndex??-1)+1); this.paintActive(); }
    else if(e.key==='ArrowUp'){ e.preventDefault(); this.activeIndex = Math.max(0, (this.activeIndex??0)-1); this.paintActive(); }
    else if(e.key==='Enter'){ if(this.activeIndex>=0){ e.preventDefault(); this.pick(this.activeIndex); } }
    else if(e.key==='Escape'){ this.hide(); }
  }

  paintActive(){
    Array.from(this.list.children).forEach((el,i)=> el.classList.toggle('active', i===this.activeIndex));
  }

  async pick(i){
    const item = this.items[i];
    if(!item) return;

    this.input.value = item.description;
    this.hide();
    this.input.dispatchEvent(new Event('change'));
  }

  show(){ this.list.style.display='block'; }
  hide(){ this.list.style.display='none'; }
}

// ====== Leaflet Route Map (tyylikäs polyline + markerit) ======
class RouteMap {
  constructor(elId, mini=false){
    this.map = L.map(elId, { 
      zoomControl: false,
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{ maxZoom: 19 }).addTo(this.map);
    this.map.setView([61.9241,25.7482], mini?5:6); // Suomi
    this.poly = null; this.m1 = null; this.m2 = null; this.distanceLabel = null;
  }
  draw(latlngs, start, end, distance){
    if(this.poly) this.poly.remove();
    if(this.m1) this.m1.remove();
    if(this.m2) this.m2.remove();
    if(this.distanceLabel) this.distanceLabel.remove();
    
    this.poly = L.polyline(latlngs, { weight: 5, opacity: 0.9 }).addTo(this.map);
    this.m1 = L.marker([start[0],start[1]]).addTo(this.map);
    this.m2 = L.marker([end[0],end[1]]).addTo(this.map);
    this.map.fitBounds(this.poly.getBounds(), { padding:[24,24] });
    
    // Add distance label in the center of the route
    if(distance) {
      const bounds = this.poly.getBounds();
      const center = bounds.getCenter();
      this.distanceLabel = L.marker(center, {
        icon: L.divIcon({
          className: 'distance-label',
          html: `<div class="distance-text">${distance} km</div>`,
          iconSize: [100, 35],
          iconAnchor: [50, 17]
        }),
        zIndexOffset: 1000
      }).addTo(this.map);
    }
  }
}

// ====== “Flovi-tyylinen” laskuri: sidonta ja UI päivitys ======
async function calcAndRender({fromId, toId, receiptIds, continueId, mapInst}){
  const f = document.getElementById(fromId).value.trim();
  const t = document.getElementById(toId).value.trim();
  if(!f || !t) return;

  // hinta
  const r = await fetch('/api/quote_for_addresses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup:f,dropoff:t})});
  const j = await r.json();
  if(!r.ok){ alert(j.error||'Hinnan laskenta epäonnistui'); return; }
  document.getElementById(receiptIds.km).textContent   = kmfmt(j.km);
  document.getElementById(receiptIds.gross).textContent= euro(j.gross);
  document.getElementById(receiptIds.box).classList.remove('hidden');

  // reitti
  const rr = await fetch('/api/route_geo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup:f,dropoff:t})});
  const jj = await rr.json();
  if(rr.ok){ mapInst.draw(jj.latlngs, jj.start, jj.end, j.km); }

  // jatka tilaukseen
  cont.classList.remove('link-disabled');
}

// === Helppo init molemmille sivuille ===
function initQuoteUI(cfg){
  // 1) Google Places Autocomplete
  const acFrom = new GooglePlacesAutocomplete(document.getElementById(cfg.fromId), document.getElementById(cfg.acFromId));
  const acTo   = new GooglePlacesAutocomplete(document.getElementById(cfg.toId),   document.getElementById(cfg.acToId));

  // 2) Kartta
  const map = new RouteMap(cfg.mapId, cfg.miniMap||false);

  // 3) Laske-nappi
  document.getElementById(cfg.calcBtnId).addEventListener('click', ()=>{
    calcAndRender({fromId:cfg.fromId, toId:cfg.toId, receiptIds:cfg.receiptIds, continueId:cfg.continueId, mapInst:map});
  });

  // 4) Kun käyttäjä valitsee ehdotuksen (change), yritetään laskea heti jos molemmat ovat valmiit
  ['change'].forEach(evt=>{
    document.getElementById(cfg.fromId).addEventListener(evt, ()=>{
      if(document.getElementById(cfg.toId).value.trim()) document.getElementById(cfg.calcBtnId).click();
    });
    document.getElementById(cfg.toId).addEventListener(evt, ()=>{
      if(document.getElementById(cfg.fromId).value.trim()) document.getElementById(cfg.calcBtnId).click();
    });
  });
}



let map, routeLayer, fromMarker, toMarker;
let isCalculating = false;
let lastCalculationTime = 0;
const RATE_LIMIT_MS = 2000; // 2 second cooldown between calculations

function initMap(){
  if(map) return;
  map = L.map('map');
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom: 19, attribution:'&copy; OpenStreetMap'
  }).addTo(map);
  map.setView([60.1699, 24.9384], 7); // Suomi keskitys
}

function euro(n){ return (Number(n).toFixed(2)+' €').replace('.',','); }
function kmfmt(n){ return Number(n).toFixed(1).replace('.',',')+' km'; }

async function calc(){
  // Rate limiting check
  const now = Date.now();
  const timeSinceLastCalc = now - lastCalculationTime;

  if (isCalculating) {
    return; // Prevent multiple simultaneous requests
  }

  if (timeSinceLastCalc < RATE_LIMIT_MS) {
    const remainingTime = Math.ceil((RATE_LIMIT_MS - timeSinceLastCalc) / 1000);
    const errEl = document.getElementById('err');
    errEl.textContent = `Odota ${remainingTime} sekuntia ennen uutta laskentaa.`;
    errEl.classList.remove('hidden');
    return;
  }

  // Set loading state
  isCalculating = true;
  lastCalculationTime = now;
  // Prefer button with id (more robust), fall back to onclick selector
  let calcBtn = document.getElementById('calcBtn');
  if (!calcBtn) calcBtn = document.querySelector('button[onclick="calc()"]');
  let originalText = '';
  if (calcBtn) {
    originalText = calcBtn.textContent;
    calcBtn.disabled = true;
    calcBtn.textContent = 'Lasketaan...';
    calcBtn.classList.add('btn-loading');
  }

  try {
    initMap();
    const f=document.getElementById('from').value.trim(), t=document.getElementById('to').value.trim();
    const errEl=document.getElementById('err'), rec=document.getElementById('receipt'), cont=document.getElementById('continueBtn');
    const noResults = document.getElementById('no-results');

    errEl.classList.add('hidden');
    rec.classList.add('hidden');
    cont.classList.add('link-disabled');
    if(noResults) noResults.style.display = 'block';

    if(!f||!t){
      errEl.textContent='Syötä molemmat osoitteet.';
      errEl.classList.remove('hidden');
      return;
    }

    // 1) Hinta
    try{
      const r=await fetch('/api/quote_for_addresses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup:f,dropoff:t})});
      const j=await r.json();
      if(!r.ok) throw new Error(j.error||'Tuntematon virhe');
      document.getElementById('r_km').textContent = kmfmt(j.km);
      document.getElementById('r_net').textContent = euro(j.net);
      document.getElementById('r_vat').textContent = euro(j.vat);
      document.getElementById('r_gross').textContent = euro(j.gross);
      rec.classList.remove('hidden');
      if(noResults) noResults.style.display = 'none';
      cont.classList.remove('link-disabled');
    }catch(e){
      errEl.textContent='Hinnan laskenta epäonnistui: '+e.message;
      errEl.classList.remove('hidden');
      return;
    }

    // 2) Reittigeometria kartalle
    try{
      const r=await fetch('/api/route_geo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup:f,dropoff:t})});
      const j=await r.json();
      if(!r.ok) throw new Error(j.error||'Route error');

      if(routeLayer){ routeLayer.remove(); }
      if(fromMarker){ fromMarker.remove(); }
      if(toMarker){ toMarker.remove(); }

      routeLayer = L.polyline(j.latlngs).addTo(map);
      fromMarker = L.marker([j.start[0], j.start[1]]).addTo(map);
      toMarker = L.marker([j.end[0], j.end[1]]).addTo(map);
      map.fitBounds(routeLayer.getBounds(), {padding:[20,20]});
    }catch(e){ /* Route error - silently handle */ }

    // 3) Jatka tilaukseen
    const url = '/order/new/step1?pickup='+encodeURIComponent(f)+'&dropoff='+encodeURIComponent(t);
    cont.href = url;
    cont.style.pointerEvents='auto'; cont.style.opacity='1';
  } finally {
    // Reset loading state
    isCalculating = false;
    if (calcBtn) {
      calcBtn.disabled = false;
      calcBtn.textContent = originalText;
      calcBtn.classList.remove('btn-loading');
    }
  }
}

function demo(){
  document.getElementById('from').value='Antaksentie 4, Vantaa';
  document.getElementById('to').value='Kirstinmäki 6, Espoo';
}

// --- Google Places Autocomplete bindings ---
// Load saved addresses first, then initialize autocomplete
loadSavedAddresses();

// Initialize after a short delay to ensure navigation.js has initialized first
// This prevents conflicts with the mobile menu toggle
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCalculatorAutocomplete);
} else {
  // DOM already loaded, initialize immediately
  initCalculatorAutocomplete();
}

function initCalculatorAutocomplete() {
  // Small delay to ensure navigation.js has set up mobile menu first
  setTimeout(function() {
    const fromInput = document.getElementById('from');
    const toInput = document.getElementById('to');
    const acFrom = document.getElementById('ac_from');
    const acTo = document.getElementById('ac_to');

    if (fromInput && acFrom) {
      window.fromAutocomplete = new GooglePlacesAutocomplete(fromInput, acFrom);
    }

    if (toInput && acTo) {
      window.toAutocomplete = new GooglePlacesAutocomplete(toInput, acTo);
    }
  }, 50);
}

// ====== Saved Addresses Functionality ======
// Storage keys (use namespaced key to avoid collisions)
const STORAGE_KEY = 'levoro.savedAddresses.v1';
const LEGACY_STORAGE_KEY = 'savedAddresses';
const COOKIE_KEY = 'levoro_saved_addresses';

// Declare globally so autocomplete can access it
window.savedAddresses = [];
let isAddressesVisible = false;
let editingAddressId = null;

// ----- Server API helpers for saved addresses -----
async function apiCall(url, options = {}){
  const res = await fetch(url, options);
  let data = null;
  try { data = await res.json(); } catch {}
  if (!res.ok) {
    const msg = (data && (data.error || data.message)) || (`HTTP ${res.status}`);
    throw new Error(msg);
  }
  return data;
}

async function fetchServerAddresses(){
  const data = await apiCall('/api/saved_addresses', { method: 'GET' });
  return Array.isArray(data.items) ? data.items : [];
}

async function createServerAddress(displayName, fullAddress){
  const data = await apiCall('/api/saved_addresses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ displayName, fullAddress })
  });
  return data.item;
}

async function updateServerAddress(id, displayName, fullAddress){
  const data = await apiCall(`/api/saved_addresses/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ displayName, fullAddress })
  });
  return data.item;
}

async function deleteServerAddress(id){
  await apiCall(`/api/saved_addresses/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

function quickLocalLoad() {
  let arr = [];
  let source = 'none';
  // Try namespaced key first
  try {
    const v1 = localStorage.getItem(STORAGE_KEY);
    if (v1) {
      const parsed = JSON.parse(v1);
      if (Array.isArray(parsed) && parsed.length > 0) {
        arr = parsed;
        source = 'localStorage-v1';
      }
    }
  } catch (e) {
    console.warn('[SavedAddresses] localStorage v1 read failed:', e);
  }
  // Fallback to legacy key
  if (arr.length === 0) {
    try {
      const legacy = localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacy) {
        const parsedLegacy = JSON.parse(legacy);
        if (Array.isArray(parsedLegacy) && parsedLegacy.length > 0) {
          arr = parsedLegacy;
          source = 'localStorage-legacy';
          try { localStorage.setItem(STORAGE_KEY, JSON.stringify(arr)); } catch {}
        }
      }
    } catch (e) {
      console.warn('[SavedAddresses] localStorage legacy read failed:', e);
    }
  }
  // Cookie fallback
  if (arr.length === 0) {
    try {
      const cookieVal = getCookie(COOKIE_KEY);
      if (cookieVal) {
        const parsedCookie = JSON.parse(decodeURIComponent(cookieVal));
        if (Array.isArray(parsedCookie) && parsedCookie.length > 0) {
          arr = parsedCookie;
          source = 'cookie';
        }
      }
    } catch (e) {
      console.warn('[SavedAddresses] cookie read failed:', e);
    }
  }
  // Validate
  arr = (arr || []).filter(x => x && typeof x === 'object' && typeof x.displayName === 'string' && typeof x.fullAddress === 'string');
  return { arr, source };
}

function refreshAutocompleteSavedIfFocus(){
  const ae = document.activeElement;
  if (ae && (ae.id === 'from' || ae.id === 'to') && !ae.value.trim()){
    if (ae.id === 'from' && window.fromAutocomplete){ window.fromAutocomplete.showSavedAddresses(); }
    if (ae.id === 'to' && window.toAutocomplete){ window.toAutocomplete.showSavedAddresses(); }
  }
}

async function loadSavedAddresses() {
  console.log('[SavedAddresses] Fast-loading local cache, then refreshing from server...');
  // Phase 1: instant local render
  try {
    const { arr, source } = quickLocalLoad();
    window.savedAddresses = arr;
    console.log(`[SavedAddresses] Quick-loaded ${arr.length} from ${source}`);
    window.savedAddresses.sort((a, b) => a.displayName.localeCompare(b.displayName, 'fi', { sensitivity: 'base' }));
    renderAddresses();
    refreshAutocompleteSavedIfFocus();
  } catch (e) {
    console.warn('[SavedAddresses] Quick-load failed:', e);
  }

  // Phase 2: server refresh (non-blocking)
  try {
    const serverItems = await fetchServerAddresses();
    if (Array.isArray(serverItems)) {
      window.savedAddresses = serverItems;
      console.log(`[SavedAddresses] Refreshed ${serverItems.length} from server`);
      saveToStorage();
      window.savedAddresses.sort((a, b) => a.displayName.localeCompare(b.displayName, 'fi', { sensitivity: 'base' }));
      renderAddresses();
      refreshAutocompleteSavedIfFocus();
    }
  } catch (e) {
    console.warn('[SavedAddresses] Server refresh failed:', e.message || e);
  }
}

function saveToStorage() {
  console.log(`[SavedAddresses] Saving ${(window.savedAddresses || []).length} addresses...`);
  let savedToLocal = false;
  let savedToCookie = false;
  
  try {
    const payload = JSON.stringify(window.savedAddresses || []);
    
    // Try localStorage first
    try {
      localStorage.setItem(STORAGE_KEY, payload);
      localStorage.setItem(LEGACY_STORAGE_KEY, payload);
      savedToLocal = true;
      console.log('[SavedAddresses] Saved to localStorage');
    } catch (e) {
      console.warn('[SavedAddresses] localStorage write failed:', e);
    }
    
    // Always save to cookie as backup (90 days)
    try {
      setCookie(COOKIE_KEY, encodeURIComponent(payload), 90);
      savedToCookie = true;
      console.log('[SavedAddresses] Saved to cookie');
    } catch (e) {
      console.warn('[SavedAddresses] cookie write failed:', e);
    }
    
    if (!savedToLocal && !savedToCookie) {
      console.error('[SavedAddresses] CRITICAL: Failed to save to any storage!');
    }
  } catch (e) {
    console.error('[SavedAddresses] Error saving:', e);
  }
}

function setCookie(name, value, days) {
  try {
    const d = new Date();
    d.setTime(d.getTime() + (days*24*60*60*1000));
    const expires = 'expires=' + d.toUTCString();
    document.cookie = name + '=' + value + ';' + expires + ';path=/;SameSite=Lax';
  } catch (e) {
    console.error('[SavedAddresses] setCookie error:', e);
  }
}

function getCookie(name) {
  try {
    const cname = name + '=';
    const ca = document.cookie.split(';');
    for (let i=0; i<ca.length; i++) {
      let c = ca[i].trim();
      if (c.indexOf(cname) === 0) return c.substring(cname.length, c.length);
    }
  } catch (e) {
    console.error('[SavedAddresses] getCookie error:', e);
  }
  return '';
}

function toggleSavedAddresses() {
  isAddressesVisible = !isAddressesVisible;
  const list = document.getElementById('savedAddressesList');
  const btn = document.getElementById('toggleAddresses');
  
  if (isAddressesVisible) {
    list.style.display = 'block';
    btn.textContent = 'Piilota tallennetut osoitteet';
  } else {
    list.style.display = 'none';
    btn.textContent = 'Näytä tallennetut osoitteet';
  }
}

function renderAddresses() {
  const container = document.getElementById('addressesContainer');
  
  if (window.savedAddresses.length === 0) {
    container.innerHTML = '<p style="color: #999; padding: 1rem; text-align: center; font-size: 0.875rem;">Ei vielä tallennettuja osoitteita.</p>';
    return;
  }
  
  let html = '';
  window.savedAddresses.forEach((addr, index) => {
    html += `
      <div style="padding: 0.75rem; border: 1px solid #e0e0e0; border-radius: 6px; margin-bottom: 0.5rem; background: white; position: relative;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
          <div style="flex: 1; cursor: pointer;" onclick="editAddress(${index})">
            <div style="font-weight: 600; color: #333; margin-bottom: 0.25rem;">${addr.displayName}</div>
            <div style="font-size: 0.875rem; color: #666;">${addr.fullAddress}</div>
          </div>
          <button onclick="deleteAddressDirectly(${index})" class="btn-delete-address" style="border: none; background: none; cursor: pointer; padding: 0.25rem 0.5rem; font-size: 1.25rem; line-height: 1; color: #999; transition: color 0.2s;" onmouseover="this.style.color='#dc2626'" onmouseout="this.style.color='#999'" title="Poista">×</button>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

async function deleteAddressDirectly(index) {
  try {
    const item = window.savedAddresses[index];
    if (!item) return;
    if (item.id) {
      try { await deleteServerAddress(item.id); } catch (e) { console.warn('[SavedAddresses] server delete failed:', e.message || e); }
    }
  } finally {
    window.savedAddresses.splice(index, 1);
    saveToStorage();
    renderAddresses();
  }
}

function toggleAddressMenu(index, event) {
  // Not needed anymore, keeping for compatibility
}

function closeAllMenus() {
  // Not needed anymore, keeping for compatibility
}


function openAddressModal(editIndex = null) {
  editingAddressId = editIndex;
  const addr = editIndex !== null ? window.savedAddresses[editIndex] : null;
  
  const modalHtml = `
    <div id="addressModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999;">
      <div style="background: white; padding: 2rem; border-radius: 12px; max-width: 500px; width: 90%;">
        <h3 style="margin: 0 0 1.5rem 0; font-size: 1.25rem; font-weight: 600;">${editIndex !== null ? 'Muokkaa osoitetta' : 'Lisää uusi osoite'}</h3>
        
        <div style="margin-bottom: 1rem;">
          <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Nimi *</label>
          <input id="addrName" type="text" class="form-input" placeholder="Esim. Koti, Toimisto, Varasto" value="${addr ? addr.displayName : ''}" style="width: 100%;">
        </div>
        
        <div style="margin-bottom: 1.5rem;">
          <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Osoite *</label>
          <input id="addrFull" type="text" class="form-input" placeholder="Esim. Mannerheimintie 1, Helsinki" value="${addr ? addr.fullAddress : ''}" style="width: 100%;">
        </div>
        
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end;">
          <button onclick="closeAddressModal()" class="btn btn-ghost">Peruuta</button>
          <button onclick="saveAddress()" class="btn btn-primary">Tallenna</button>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  document.getElementById('addrName').focus();
}

function closeAddressModal() {
  const modal = document.getElementById('addressModal');
  if (modal) modal.remove();
  editingAddressId = null;
}

async function saveAddress() {
  const name = document.getElementById('addrName').value.trim();
  const address = document.getElementById('addrFull').value.trim();
  
  if (!name || !address) {
    alert('Täytä molemmat kentät');
    return;
  }
  
  try {
    if (editingAddressId !== null) {
      // Update existing
      const current = window.savedAddresses[editingAddressId];
      let updated = null;
      if (current && current.id) {
        try {
          updated = await updateServerAddress(current.id, name, address);
        } catch (e) {
          console.warn('[SavedAddresses] server update failed, falling back to local:', e.message || e);
        }
      }
      const newAddr = updated || { id: current && current.id || Date.now(), displayName: name, fullAddress: address };
      window.savedAddresses[editingAddressId] = newAddr;
    } else {
      // Create new
      let created = null;
      try {
        created = await createServerAddress(name, address);
      } catch (e) {
        console.warn('[SavedAddresses] server create failed, storing locally:', e.message || e);
      }
      const newAddr = created || { id: Date.now(), displayName: name, fullAddress: address };
      window.savedAddresses.push(newAddr);
    }
  } finally {
    saveToStorage();
    loadSavedAddresses();
    closeAddressModal();
  }
}

function editAddress(index) {
  openAddressModal(index);
}

</script>

<!-- Load React Saved Addresses Component from Vite Dev Server -->
<script type="module" src="http://localhost:5173/src/savedAddresses.tsx"></script>
"""
    return get_wrap()(body, u)
