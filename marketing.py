# marketing.py
from app import app, wrap, current_user


@app.get("/calculator")
def calculator():
    u = current_user()
    body = """
<div class="grid cols-2">
  <div class="card">
    <h2>Laske hinta</h2>
    <p class="small">Kirjoita lähtö ja kohde — saat reitin kartalle sekä hinnan.</p>

    <div class="autocomplete">
      <label>Lähtöosoite</label>
      <input id="from" placeholder="Esim. Antaksentie 4, Vantaa"
             autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" name="from_addr">
      <div id="ac_from" class="ac-list"></div>
    </div>

    <div class="autocomplete">
      <label>Kohdeosoite</label>
      <input id="to" placeholder="Esim. Kirstinmäki 6, Espoo"
             autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" name="to_addr">
      <div id="ac_to" class="ac-list"></div>
    </div>


    <div class="row" style="margin-top:10px">
      <button onclick="calc()">Laske hinta ja reitti</button>
      <button class="ghost" onclick="demo()">Täytä esimerkki</button>
    </div>
    <p id="err" class="small" style="display:none;color:#b91c1c;margin-top:8px"></p>

    <div id="map" style="margin-top:12px"></div>
  </div>

  <div class="card" id="quick">
    <h2>Nopea aloitus</h2>
    <div class="callout small">Kun hinta on laskettu, voit jatkaa suoraan tilaukseen samoilla osoitteilla.</div>

    <div id="receipt" class="receipt" style="display:none;margin-top:12px">
      <div class="rowline"><span>Matka</span><span id="r_km">—</span></div>
      <div class="rowline total"><span>Hinta</span><span id="r_gross">—</span></div>
    </div>

    <div class="row" style="margin-top:12px">
      <a id="continueBtn" href="/order/new/step1" style="pointer-events:none;opacity:.5">
        <button>Jatka tilaukseen →</button>
      </a>
      <a class="ghost" href="/dashboard">Omat tilaukset</a>
    </div>
  </div>
</div>

<script>
// ====== Utilities ======
const FI_VIEWBOX = '19,59,32,71'; // Suomi (lon_min,lat_min,lon_max,lat_max)

function shortFi(adr = {}) {
  const road = adr.road || adr.pedestrian || adr.cycleway || adr.footway || "";
  const num  = adr.house_number ? " " + adr.house_number : "";
  const city = adr.city || adr.town || adr.municipality || adr.village || adr.suburb || adr.city_district || "";
  return `${road}${num}${city ? ", " + city : ""}`.trim();
}
function euro(n){ return (Number(n).toFixed(2)+' €').replace('.',','); }
function kmfmt(n){ return Number(n).toFixed(1).replace('.',',')+' km'; }

// ====== Autocomplete (Flovi-tyyli: debouncaus, nuolinäppäimet, dedupe, vain FI) ======
class AddressAutocomplete {
  constructor(input, listEl){
    this.input = input;
    this.list = listEl;
    this.timer = null;
    this.items = [];
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
    this.timer = setTimeout(()=> this.fetch(q), 200);
  }
  async fetch(q){
    try{
      const url = 'https://nominatim.openstreetmap.org/search'
        + '?format=jsonv2&addressdetails=1&limit=10&dedupe=1&countrycodes=fi'
        + '&viewbox='+FI_VIEWBOX+'&bounded=1&q='+encodeURIComponent(q);
      const r = await fetch(url, { headers:{'User-Agent':'Portal/1.0','Accept-Language':'fi'} });
      const arr = await r.json();

      const seen = new Set();
      const out = [];
      for(const p of arr){
        if(!(p.address && p.address.country_code === 'fi')) continue;
        const label = shortFi(p.address);
        if(!label) continue;
        const key = label.toLowerCase();
        if(seen.has(key)) continue;
        seen.add(key);
        out.push({label, lat: +p.lat, lon: +p.lon, hasNumber: !!p.address.house_number});
      }
      out.sort((a,b)=> Number(b.hasNumber)-Number(a.hasNumber));
      this.items = out.slice(0, 8);
      this.render();
    }catch(_){
      this.items = [];
      this.list.innerHTML = '<div class="ac-empty">Ei ehdotuksia</div>';
      this.show();
    }
  }
  render(){
    if(!this.items.length){ this.list.innerHTML = '<div class="ac-empty">Ei ehdotuksia</div>'; this.show(); return; }
    this.list.innerHTML = this.items.map((it,i)=>(
      `<div class="ac-item" data-i="${i}">${it.label}</div>`
    )).join('');
    this.show();
    Array.from(this.list.children).forEach(el=>{
      el.onclick = ()=> this.pick(+el.getAttribute('data-i'));
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
    const it = this.items[i]; if(!it) return;
    this.input.value = it.label; this.hide();
    // reverse: siisti teksti pisteestä (jos Nominatim antaa paremman)
    try{
      const rr = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&accept-language=fi&lat=${it.lat}&lon=${it.lon}`, {headers:{'User-Agent':'Portal/1.0'}});
      const jj = await rr.json();
      const fixed = shortFi(jj.address||{});
      if(fixed) this.input.value = fixed;
    }catch(_){}
    this.input.dispatchEvent(new Event('change'));
  }
  show(){ this.list.style.display='block'; }
  hide(){ this.list.style.display='none'; }
}

// ====== Leaflet Route Map (tyylikäs polyline + markerit) ======
class RouteMap {
  constructor(elId, mini=false){
    this.map = L.map(elId, { zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{ maxZoom: 19 }).addTo(this.map);
    this.map.setView([61.9241,25.7482], mini?5:6); // Suomi
    this.poly = null; this.m1 = null; this.m2 = null;
  }
  draw(latlngs, start, end){
    if(this.poly) this.poly.remove();
    if(this.m1) this.m1.remove();
    if(this.m2) this.m2.remove();
    this.poly = L.polyline(latlngs, { weight: 5, opacity: 0.9 }).addTo(this.map);
    this.m1 = L.marker([start[0],start[1]]).addTo(this.map);
    this.m2 = L.marker([end[0],end[1]]).addTo(this.map);
    this.map.fitBounds(this.poly.getBounds(), { padding:[24,24] });
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
  document.getElementById(receiptIds.box).style.display='block';

  // reitti
  const rr = await fetch('/api/route_geo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup:f,dropoff:t})});
  const jj = await rr.json();
  if(rr.ok){ mapInst.draw(jj.latlngs, jj.start, jj.end); }

  // jatka tilaukseen
  const cont = document.getElementById(continueId);
  cont.href = '/order/new/step1?pickup='+encodeURIComponent(f)+'&dropoff='+encodeURIComponent(t);
  cont.style.pointerEvents='auto'; cont.style.opacity='1';
}

// === Helppo init molemmille sivuille ===
function initQuoteUI(cfg){
  // 1) Autocomplete (nuolinäppäimet + dedupe + vain Suomi)
  const acFrom = new AddressAutocomplete(document.getElementById(cfg.fromId), document.getElementById(cfg.acFromId));
  const acTo   = new AddressAutocomplete(document.getElementById(cfg.toId),   document.getElementById(cfg.acToId));

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
  errEl.style.display='none';
  rec.style.display='none'; cont.style.pointerEvents='none'; cont.style.opacity='.5';

  if(!f||!t){ errEl.textContent='Syötä molemmat osoitteet.'; errEl.style.display='block'; return; }

  // 1) Hinta
  try{
    const r=await fetch('/api/quote_for_addresses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup:f,dropoff:t})});
    const j=await r.json();
    if(!r.ok) throw new Error(j.error||'Tuntematon virhe');
    document.getElementById('r_km').textContent = kmfmt(j.km);
    document.getElementById('r_gross').textContent = euro(j.gross);
    rec.style.display='block';
  }catch(e){ errEl.textContent='Hinnan laskenta epäonnistui: '+e.message; errEl.style.display='block'; return; }

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

// --- Autocomplete (Nominatim) ---
let acTimer=null;
function fiShortAddress(adr){
  const road = adr.road || adr.pedestrian || adr.cycleway || adr.footway || "";
  const num  = adr.house_number ? " " + adr.house_number : "";
  const city = adr.city || adr.town || adr.municipality || adr.village || adr.suburb || adr.city_district || "";
  // HUOM: EI postinumeroa tarkoituksella → vältytään vääriltä koodeilta
  return `${road}${num}${city ? ", " + city : ""}`.trim();
}

function bindAC(inputId, listId){
  const inp  = document.getElementById(inputId);
  const list = document.getElementById(listId);
  let timer  = null;

  // varmistetaan että selaimen oma muistilista ei näy
  inp.setAttribute('autocomplete','off');
  inp.setAttribute('autocorrect','off');
  inp.setAttribute('autocapitalize','off');
  inp.setAttribute('spellcheck','false');

  inp.addEventListener('input', ()=>{
    clearTimeout(timer);
    const q = inp.value.trim();
    if(!q){ list.style.display='none'; list.innerHTML=''; return; }

    timer = setTimeout(async ()=>{
      try{
        const url = 'https://nominatim.openstreetmap.org/search'
          + '?format=jsonv2'
          + '&addressdetails=1'
          + '&limit=10'
          + '&dedupe=1'
          + '&countrycodes=fi'
          + '&viewbox=19,59,32,71'   // lon_min,lat_min,lon_max,lat_max (Suomi)
          + '&bounded=1'
          + '&q=' + encodeURIComponent(q);

        const resp = await fetch(url, { headers:{'User-Agent':'Portal/1.0','Accept-Language':'fi'} });
        const arr  = await resp.json();

        // 1) suodata vain FI-osoitteet
        const candidates = arr.filter(p => (p.address && p.address.country_code === 'fi'));

        // 2) tee lyhyt label ja poista duplikaatit (sama katu+numero+kaupunki)
        const seen = new Set();
        const items = [];
        for(const p of candidates){
          const adr = p.address || {};
          const short = fiShortAddress(adr);
          if(!short) continue;

          // suositaan “talonumero löytyy” -tuloksia
          const hasNumber = !!adr.house_number;

          // avain dedupeen
          const key = (short.toLowerCase());

          if(!seen.has(key)){
            seen.add(key);
            items.push({ short, lat: p.lat, lon: p.lon, hasNumber });
          }
        }

        // 3) järjestä: ensin osoitteet joissa on talonumero, sitten muut
        items.sort((a,b)=> (Number(b.hasNumber) - Number(a.hasNumber)));

        list.innerHTML = items.slice(0,8).map(it =>
          `<div class="ac-item" data-label="${it.short.replace(/"/g,'&quot;')}" data-lat="${it.lat}" data-lon="${it.lon}">${it.short}</div>`
        ).join('');
        list.style.display = items.length ? 'block' : 'none';

        // 4) klikkaus: aseta lyhyt osoite ja yritä tarkentaa reverse-geocodella
        Array.from(list.children).forEach(el=>{
          el.onclick = async ()=>{
            const label = el.getAttribute('data-label');
            const lat   = el.getAttribute('data-lat');
            const lon   = el.getAttribute('data-lon');
            inp.value = label;
            list.style.display='none';

            // Reverse: haetaan täsmällinen osoite pisteestä ja kirjoitetaan lyhyenä (ilman postinumeroa)
            try{
              const r = await fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&accept-language=fi'
                                    + '&lat='+encodeURIComponent(lat)+'&lon='+encodeURIComponent(lon),
                                    { headers:{'User-Agent':'Portal/1.0'} });
              const pr = await r.json();
              const fixed = fiShortAddress(pr.address || {});
              if(fixed) inp.value = fixed;
            }catch(_){}
          };
        });
      }catch(e){
        list.style.display='none';
        list.innerHTML='';
      }
    }, 220);
  });

  // klik ulos → piilota lista
  document.addEventListener('click', (e)=>{
    if(!list.contains(e.target) && e.target!==inp){ list.style.display='none'; }
  });
}

// kutsut FUNKTION ulkopuolella:
bindAC('from','ac_from');
bindAC('to','ac_to');
</script>
"""
    return wrap(body, u)
