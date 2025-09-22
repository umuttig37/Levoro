# marketing.py
from flask import redirect, url_for
from app import app, wrap, current_user


@app.get("/calculator")
def calculator():
    u = current_user()
    if not u:
        return redirect(url_for("login", next="/calculator"))
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

          <div class="calculator-actions">
            <button class="btn btn-primary btn-lg" onclick="calc()">Laske hinta ja reitti</button>
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
            <div class="rowline total"><span>Kokonaishinta</span><span id="r_gross">—</span></div>
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

// ====== Google Places Autocomplete ======
class GooglePlacesAutocomplete {
  constructor(input, listEl){
    this.input = input;
    this.list = listEl;
    this.timer = null;
    this.items = [];
    this.cache = new Map();
    this.CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

    input.setAttribute('autocomplete','off');
    input.setAttribute('autocorrect','off');
    input.setAttribute('autocapitalize','off');
    input.setAttribute('spellcheck','false');

    input.addEventListener('input', ()=> this.onInput());
    input.addEventListener('keydown', (e)=> this.onKey(e));
    document.addEventListener('click', (e)=>{ if(!this.list.contains(e.target) && e.target!==this.input){ this.hide() }});
  }

  onInput(){
    clearTimeout(this.timer);
    const q = this.input.value.trim();
    if(!q){ this.hide(); this.list.innerHTML=''; return; }

    // Check cache first
    const cacheKey = q.toLowerCase();
    const cached = this.cache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp < this.CACHE_DURATION)) {
      this.items = cached.results;
      this.render();
      return;
    }

    this.showLoading();
    this.timer = setTimeout(()=> this.fetch(q), 200);
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
      console.warn('Places API error:', e);
      this.items = [];
      // Only show error after a longer delay to avoid premature error messages
      setTimeout(() => {
        if (this.list.style.display === 'block') {
          this.list.innerHTML = '<div class="ac-error" style="padding: 0.5rem; color: #ef4444;">Virhe osoitteiden haussa</div>';
        }
      }, 500);
    }
  }


  render(){
    if(!this.items.length){
      this.list.innerHTML = '<div class="ac-empty">Ei ehdotuksia</div>';
      this.show();
      return;
    }

    this.list.innerHTML = this.items.slice(0, 8).map((item, i) =>
      `<div class="ac-item" data-i="${i}">${item.description}</div>`
    ).join('');
    this.show();

    Array.from(this.list.children).forEach(el=>{
      if (el.classList.contains('ac-item')) {
        el.onclick = ()=> this.pick(+el.getAttribute('data-i'));
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
      console.log('Adding distance label:', distance, 'at position:', center);
      this.distanceLabel = L.marker(center, {
        icon: L.divIcon({
          className: 'distance-label',
          html: `<div class="distance-text">${distance} km</div>`,
          iconSize: [100, 35],
          iconAnchor: [50, 17]
        }),
        zIndexOffset: 1000
      }).addTo(this.map);
      console.log('Distance label added to map');
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
  }catch(e){ console.warn(e); }

  // 3) Jatka tilaukseen
  const url = '/order/new/step1?pickup='+encodeURIComponent(f)+'&dropoff='+encodeURIComponent(t);
  cont.href = url;
  cont.style.pointerEvents='auto'; cont.style.opacity='1';
}

function demo(){
  document.getElementById('from').value='Antaksentie 4, Vantaa';
  document.getElementById('to').value='Kirstinmäki 6, Espoo';
}

// --- Google Places Autocomplete bindings ---
const fromAutocomplete = new GooglePlacesAutocomplete(
  document.getElementById('from'),
  document.getElementById('ac_from')
);

const toAutocomplete = new GooglePlacesAutocomplete(
  document.getElementById('to'),
  document.getElementById('ac_to')
);
</script>
"""
    return wrap(body, u)
