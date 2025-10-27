# order_wizard.py
import datetime
import re
from flask import request, redirect, url_for, session
from services.auth_service import auth_service
from services.order_service import order_service
from models.database import db_manager

def validate_phone_number(phone):
    """Validate that phone number contains only digits, spaces, +, -, and ()"""
    if not phone:
        return False
    # Allow: digits, spaces, +, -, (, )
    # Pattern: optional + at start, then digits/spaces/hyphens/parentheses
    pattern = r'^[+]?[0-9\s\-()]+$'
    return bool(re.match(pattern, phone))

# Import app and wrap function - available after app initialization
def get_app():
    from app import app
    return app

def get_wrap():
    from app import wrap
    return wrap

app = get_app()

def get_accessible_steps(session_data):
    """Determine which steps user can navigate to based on completed data"""
    accessible = [1]  # Step 1 always accessible

    if session_data.get("pickup"):
        accessible.append(2)
    if session_data.get("dropoff"):
        accessible.append(3)
    if session_data.get("reg_number"):
        accessible.append(4)
    # Check for orderer required fields only (customer fields are now optional)
    if (session_data.get("orderer_name") and session_data.get("orderer_email") and session_data.get("orderer_phone")):
        accessible.append(5)
    if session_data.get("additional_info") is not None:  # Can be empty string
        accessible.append(6)

    return accessible

def validate_step_access(required_step, session_data):
    """Validate if user can access the requested step"""
    accessible_steps = get_accessible_steps(session_data)
    if required_step not in accessible_steps:
        # Redirect to highest accessible step
        highest_step = max(accessible_steps)
        return redirect(f"/order/new/step{highest_step}")
    return None

def wizard_shell(active: int, inner_html: str, session_data: dict = None) -> str:
  steps = ["Nouto", "Toimitus", "Ajoneuvo", "Yhteystiedot", "Lisätiedot", "Vahvistus"]
  accessible_steps = get_accessible_steps(session_data or {})

  nav = "<div class='stepnav'>"
  for i, s in enumerate(steps, start=1):
    if i == active:
      cls = "item active"
      nav += f"<div class='{cls}'>{i}. {s}</div>"
    elif i in accessible_steps:
      cls = "item clickable"
      step_url = "/order/new/confirm" if i == 6 else f"/order/new/step{i}"
      nav += f"<a href='{step_url}' class='{cls}'>{i}. {s}</a>"
    else:
      cls = "item disabled"
      nav += f"<div class='{cls}'>{i}. {s}</div>"
  nav += "</div>"
  css_link = "<link rel='stylesheet' href='/static/css/stepnav.css'>"
  wizard_css = "<link rel='stylesheet' href='/static/css/wizard.css'>"
  # Two-column layout for wizard
  layout = f"""
  <div class='wizard-row'>
    <div class='wizard-col wizard-steps'>{nav}</div>
    <div class='wizard-col wizard-form'><div class='card'>{inner_html}</div></div>
  </div>
  """
  return f"{css_link}{wizard_css}{layout}"

# STEP 1: Pickup
# order_wizard.py -> order_step1()
@app.route("/order/new/step1", methods=["GET","POST"])
def order_step1():
    u = auth_service.get_current_user()
    if not u:
        return redirect(url_for("auth.login", next="/order/new/step1"))

    if request.method == "GET":
        # esitäyttö query-parametreilla (jatka tilaukseen -napista)
        qp_pick = (request.args.get("pickup") or "").strip()
        qp_drop = (request.args.get("dropoff") or "").strip()
        if qp_pick or qp_drop:
            d = session.get("order_draft", {})
            if qp_pick:
                d["pickup"] = qp_pick
            if qp_drop:
                d["dropoff"] = qp_drop   # talletetaan jo tässä vaiheessa
            session["order_draft"] = d

        d = session.get("order_draft", {})
        pickup_val = (d.get("pickup", "") or "").replace('"', '&quot;')

        # Check for error message and display it
        error_msg = session.pop("error_message", None)
        error_html = f"<div class='error-message' style='margin-bottom: 1rem; padding: 0.75rem; background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 0.375rem;'>{error_msg}</div>" if error_msg else ""

        inner = """
<h2>Auton nouto</h2>
""" + error_html + """
<form method='POST'>
  <label>Nouto-osoite *</label>
  <div class="autocomplete">
    <input id="from_step" name="pickup" required value="__PICKUP_VAL__" placeholder="Katu, kaupunki">
    <div id="ac_from_step" class="ac-list"></div>
  </div>

  <div class="date-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;">
    <div class="date-field">
      <label for="pickup_date">Toivottu noutopäivä</label>
      <div class="date-input-wrap" style="position: relative;">
        <svg class="calendar-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); z-index: 1;">
          <rect x="3" y="4" width="18" height="18" rx="2" stroke="#64748b" stroke-width="2"/>
          <line x1="8" y1="2.5" x2="8" y2="6" stroke="#64748b" stroke-width="2"/>
          <line x1="16" y1="2.5" x2="16" y2="6" stroke="#64748b" stroke-width="2"/>
          <line x1="3" y1="10" x2="21" y2="10" stroke="#64748b" stroke-width="2"/>
        </svg>
        <input type="date" name="pickup_date" id="pickup_date" required class="form-input date-input" style="padding-left: 40px; height: 44px; font-size: 0.95rem; width: 100%;">
      </div>
    </div>
    <div class="date-field">
      <label for="last_delivery_date">Viimeinen toimituspäivä</label>
      <div class="date-input-wrap" style="position: relative;">
        <svg class="calendar-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); z-index: 1;">
          <rect x="3" y="4" width="18" height="18" rx="2" stroke="#64748b" stroke-width="2"/>
          <line x1="8" y1="2.5" x2="8" y2="6" stroke="#64748b" stroke-width="2"/>
          <line x1="16" y1="2.5" x2="16" y2="6" stroke="#64748b" stroke-width="2"/>
          <line x1="3" y1="10" x2="21" y2="10" stroke="#64748b" stroke-width="2"/>
        </svg>
        <input type="date" name="last_delivery_date" id="last_delivery_date" class="form-input date-input" style="padding-left: 40px; height: 44px; font-size: 0.95rem; width: 100%;">
      </div>
    </div>
  </div>

  <!-- Saved Addresses Section -->
  <div style="margin-top: 16px; padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; background: #fafafa;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
      <h3 style="margin: 0; font-size: 1rem; font-weight: 600; color: #374151;">Tallennetut osoitteet</h3>
      <button type="button" onclick="openAddressModal()" class="btn btn-primary btn-sm" style="font-size: 0.875rem;">+ Lisää uusi osoite</button>
    </div>

    <button id="toggleAddresses" type="button" onclick="toggleSavedAddresses()" class="btn btn-ghost btn-sm" style="width: 100%; margin-bottom: 0.75rem;">Näytä tallennetut osoitteet</button>

    <div id="savedAddressesList" style="display: none;">
      <div id="addressesContainer" style="max-height: 260px; overflow-y: auto;"></div>
    </div>
  </div>

  <div class='calculator-actions mt-2' style="margin-top: 16px;">
    <button type='submit' class="btn btn-primary" aria-label="Jatka seuraavaan vaiheeseen">Jatka →</button>
  </div>
</form>

<style>
/* Keep date inputs compact and icons centered */
.date-input-wrap { position: relative; display: grid; align-items: center; }
.date-input { padding-left: 40px; height: 44px; line-height: 44px; box-sizing: border-box; -webkit-appearance: none; appearance: none; }
.date-input:focus { outline: none; }
.calendar-icon-svg { pointer-events: none; transition: transform 120ms ease-out; }
/* Move native date picker icon to the left visually (keep it clickable) */
.date-input::-webkit-calendar-picker-indicator {
  position: absolute;
  left: 0;
  right: auto;
  width: 44px;
  height: 44px;
  opacity: 0; /* hide default icon */
  cursor: pointer;
}
/* Saved addresses styling */
.ac-item.saved-address { padding: 0.75rem !important; border-left: 3px solid var(--color-primary, #2563eb); background: #f8fafc; }
.ac-item.saved-address:hover { background: #eef2ff; }
.menu-item:hover { background: #f3f4f6; }
/* Autocomplete dropdown: ensure clickability and on-top rendering */
.autocomplete { position: relative; }
.ac-list { position: absolute; top: 100%; left: 0; right: 0; z-index: 9999; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 8px 16px rgba(0,0,0,0.06); }
.ac-item { padding: 10px 12px; cursor: pointer; }
.ac-item.active { background: #eef2ff; }
.ac-empty, .ac-error { padding: 10px 12px; }
@media (max-width: 640px) {
  .date-grid { grid-template-columns: 1fr !important; }
}
</style>

<script>
/* ===== Google Places Autocomplete for Wizard ===== */
class WizardGooglePlacesAutocomplete {
  constructor(input, listEl){
    this.input = input;
    this.list = listEl;
    this.timer = null;
    this.items = [];
    this.cache = new Map();
    this.CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
    this.autocompleteService = null;
    this.googleMapsLoaded = false;
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
  // Use closest to avoid accidental hides and ensure clicks inside list work
  document.addEventListener('mousedown', (e)=>{ if(!e.target.closest || !e.target.closest('#'+this.list.id)) { if(e.target!==this.input) this.hide(); } });
    // Event delegation: handle selection on the list itself
    this.list.addEventListener('mousedown', (e)=>{
      const el = e.target.closest ? e.target.closest('.ac-item') : null;
      if (!el) return;
      e.preventDefault();
      const type = el.getAttribute('data-type');
      if (type === 'saved') {
        const id = el.getAttribute('data-id');
        this.pickSaved(id);
      } else {
        const idxAttr = el.getAttribute('data-i');
        const i = idxAttr ? +idxAttr : -1;
        if (i >= 0) this.pick(i);
      }
    });

    // Initialize Google Maps API when available
    this.initGoogleMaps();
  }

  async initGoogleMaps() {
    // Wait for Google Maps to load if available
    let attempts = 0;
    const maxAttempts = 50; // 5 seconds

    while (attempts < maxAttempts) {
      if (typeof google !== 'undefined' && google.maps && google.maps.places) {
        this.autocompleteService = new google.maps.places.AutocompleteService();
        this.googleMapsLoaded = true;
        // Google Places client-side API initialized
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
      attempts++;
    }

    if (!this.googleMapsLoaded) {
      // Google Maps API not available
    }
  }

  onFocus(){
    const q = this.input.value.trim();
    if (!q) {
      this.showSavedAddresses();
    }
  }

  onInput(){
    clearTimeout(this.timer);
    const q = this.input.value.trim();
    if(!q){ this.showSavedAddresses(); return; }

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

    // Use server-side endpoint for address suggestions
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
    let html = '';

    // Saved addresses filtered by query
    let filteredSaved = [];
    if (q && window.savedAddresses) {
      filteredSaved = window.savedAddresses.filter(a =>
        a.displayName?.toLowerCase().includes(q) || a.fullAddress?.toLowerCase().includes(q)
      ).slice(0,5);
    }

    if (filteredSaved.length > 0) {
      html += '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e5e7eb;">Tallennetut osoitteet</div>';
      html += filteredSaved.map(a =>
        `<div class="ac-item saved-address" data-type="saved" data-id="${a.id}">
           <div style="font-weight:600; color:#111827;">${a.displayName}</div>
           <div style="font-size:0.875rem; color:#6b7280;">${a.fullAddress}</div>
         </div>`
      ).join('');
    }

    if (this.items.length > 0) {
      if (filteredSaved.length > 0) {
        html += '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e5e7eb; margin-top: 0.5rem;">Karttahaku</div>';
      }
      html += this.items.slice(0,8).map((item,i)=>`<div class="ac-item" data-type="map" data-i="${i}">${item.description}</div>`).join('');
    }

    if (!html) {
      this.list.innerHTML = '<div class="ac-empty">Ei ehdotuksia</div>';
      this.show();
      return;
    }

    this.list.innerHTML = html;
    this.show();

    // No per-item handlers needed; handled by delegated listener above
    this.activeIndex = -1;
  }

  showSavedAddresses(){
    if (!window.savedAddresses || window.savedAddresses.length === 0) return;
    let html = '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e5e7eb;">Tallennetut osoitteet</div>';
    html += window.savedAddresses.slice(0,8).map(a=>
      `<div class="ac-item saved-address" data-type="saved" data-id="${a.id}">
         <div style="font-weight:600; color:#111827;">${a.displayName}</div>
         <div style="font-size:0.875rem; color:#6b7280;">${a.fullAddress}</div>
       </div>`
    ).join('');
    this.list.innerHTML = html;
    this.show();
  }

  pickSaved(id){
    const addr = (window.savedAddresses||[]).find(a=>String(a.id)===String(id));
    if (!addr) return;
    this.input.value = addr.fullAddress;
    this.hide();
    this.input.dispatchEvent(new Event('change'));
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

/* ===== Saved Addresses (shared with calculator) ===== */
const STORAGE_KEY = 'levoro.savedAddresses.v1';
const LEGACY_STORAGE_KEY = 'savedAddresses';
const COOKIE_KEY = 'levoro_saved_addresses';
window.savedAddresses = [];

async function apiCall(url, options={}){
  const res = await fetch(url, options);
  let data = null; try { data = await res.json(); } catch {}
  if (!res.ok) throw new Error((data && (data.error||data.message)) || ('HTTP '+res.status));
  return data;
}

async function fetchServerAddresses(){
  const data = await apiCall('/api/saved_addresses', { method: 'GET' });
  return Array.isArray(data.items) ? data.items : [];
}

async function createServerAddress(displayName, fullAddress){
  const data = await apiCall('/api/saved_addresses', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({displayName, fullAddress}) });
  return data.item;
}

async function deleteServerAddress(id){
  await apiCall(`/api/saved_addresses/${encodeURIComponent(id)}`, { method:'DELETE' });
}

function setCookie(name, value, days){ try{ const d=new Date(); d.setTime(d.getTime()+days*864e5); document.cookie = name+'='+value+';expires='+d.toUTCString()+';path=/;SameSite=Lax'; }catch(e){} }
function getCookie(name){ try{ const cname=name+'='; return document.cookie.split(';').map(s=>s.trim()).find(c=>c.indexOf(cname)===0)?.substring(cname.length)||''; }catch(e){return '';} }

function quickLocalLoad(){
  let arr = [];
  try{ const v1 = localStorage.getItem(STORAGE_KEY); if (v1){ const p=JSON.parse(v1); if(Array.isArray(p)&&p.length) arr=p; } }catch(e){}
  if (!arr.length){ try{ const legacy=localStorage.getItem(LEGACY_STORAGE_KEY); if(legacy){ const p=JSON.parse(legacy); if(Array.isArray(p)&&p.length){ arr=p; localStorage.setItem(STORAGE_KEY, JSON.stringify(arr)); } } }catch(e){} }
  if (!arr.length){ try{ const cv=getCookie(COOKIE_KEY); if(cv){ const p=JSON.parse(decodeURIComponent(cv)); if(Array.isArray(p)&&p.length) arr=p; } }catch(e){} }
  return arr.filter(x=>x && typeof x==='object' && typeof x.displayName==='string' && typeof x.fullAddress==='string');
}

function saveToStorage(){ try{ const payload=JSON.stringify(window.savedAddresses||[]); try{ localStorage.setItem(STORAGE_KEY, payload); localStorage.setItem(LEGACY_STORAGE_KEY, payload);}catch(e){} try{ setCookie(COOKIE_KEY, encodeURIComponent(payload), 90);}catch(e){} }catch(e){} }

function renderAddresses(){
  const container = document.getElementById('addressesContainer');
  if (!container) return;
  const list = window.savedAddresses||[];
  if (!list.length){ container.innerHTML = '<p style="color:#9ca3af; padding: 0.5rem; text-align:center; font-size:0.875rem;">Ei vielä tallennettuja osoitteita.</p>'; return; }
  container.innerHTML = list.map((a,i)=>`
    <div style="padding: 0.75rem; border:1px solid #e5e7eb; border-radius:6px; margin-bottom:0.5rem; background:white; display:flex; justify-content:space-between; align-items:start;">
      <div style="flex:1; cursor:pointer;" onclick="useAddress('${a.id}')">
        <div style="font-weight:600; color:#111827; margin-bottom:0.25rem;">${a.displayName}</div>
        <div style="font-size:0.875rem; color:#6b7280;">${a.fullAddress}</div>
      </div>
      <button type="button" onclick="deleteAddressDirectly(${i})" class="btn btn-ghost" title="Poista">×</button>
    </div>`).join('');
}

function toggleSavedAddresses(){
  const list = document.getElementById('savedAddressesList');
  const btn = document.getElementById('toggleAddresses');
  if (!list||!btn) return;
  const show = list.style.display !== 'block';
  list.style.display = show ? 'block':'none';
  btn.textContent = show ? 'Piilota tallennetut osoitteet' : 'Näytä tallennetut osoitteet';
}

function useAddress(id){
  const a = (window.savedAddresses||[]).find(x=>String(x.id)===String(id));
  if (!a) return;
  const inp = document.getElementById('from_step');
  if (inp){ inp.value = a.fullAddress; inp.dispatchEvent(new Event('change')); }
}

async function deleteAddressDirectly(index){
  const item = (window.savedAddresses||[])[index];
  if (!item) return;
  try { if (item.id) await deleteServerAddress(item.id); } catch(e) {}
  window.savedAddresses.splice(index,1);
  saveToStorage();
  renderAddresses();
}

function openAddressModal(){
  const html = `
  <div id="addressModal" style="position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:9999;">
    <div style="background:white; padding:1.25rem; border-radius:12px; width:90%; max-width:480px;">
      <h3 style="margin:0 0 1rem 0; font-size:1.1rem; font-weight:600;">Lisää uusi osoite</h3>
      <div style="margin-bottom:0.75rem;">
        <label style="display:block; margin-bottom:0.25rem;">Nimi *</label>
        <input id="addrName" class="form-input" placeholder="Esim. Koti, Toimisto" style="width:100%;">
      </div>
      <div style="margin-bottom:1rem;">
        <label style="display:block; margin-bottom:0.25rem;">Osoite *</label>
        <input id="addrFull" class="form-input" placeholder="Esim. Mannerheimintie 1, Helsinki" style="width:100%;">
      </div>
      <div style="display:flex; gap:0.5rem; justify-content:flex-end;">
        <button type="button" class="btn btn-ghost" onclick="closeAddressModal()">Peruuta</button>
        <button type="button" class="btn btn-primary" onclick="saveAddress()">Tallenna</button>
      </div>
    </div>
  </div>`;
  document.body.insertAdjacentHTML('beforeend', html);
  document.getElementById('addrName').focus();
}

function closeAddressModal(){ const m=document.getElementById('addressModal'); if(m) m.remove(); }

async function saveAddress(){
  const name = document.getElementById('addrName').value.trim();
  const addr = document.getElementById('addrFull').value.trim();
  if (!name || !addr) { alert('Täytä molemmat kentät'); return; }
  let created=null; try{ created = await createServerAddress(name, addr);}catch(e){}
  const item = created || { id: Date.now(), displayName: name, fullAddress: addr };
  window.savedAddresses.push(item);
  saveToStorage();
  renderAddresses();
  closeAddressModal();
}

async function loadSavedAddresses(){
  try { window.savedAddresses = quickLocalLoad(); renderAddresses(); } catch(e){}
  try { const server = await fetchServerAddresses(); if (Array.isArray(server)) { window.savedAddresses = server; saveToStorage(); renderAddresses(); } } catch(e){}
}

/* Initialize for Step 1 */
loadSavedAddresses();
const step1Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('from_step'),
  document.getElementById('ac_from_step')
);
window.fromAutocomplete = step1Autocomplete;

/* Date validation for Step 1 */
(function() {
  const pickupDateInput = document.getElementById('pickup_date');
  const lastDeliveryDateInput = document.getElementById('last_delivery_date');
  
  if (pickupDateInput && lastDeliveryDateInput) {
    // Set minimum date for pickup to today
    const today = new Date().toISOString().split('T')[0];
    pickupDateInput.min = today;
    
    // Function to update last delivery date minimum (allow same-day delivery)
    function updateLastDeliveryMin() {
      const pickupDate = pickupDateInput.value;
      if (pickupDate) {
        // Same day allowed: min = pickupDate (no +1)
        const minDeliveryDate = new Date(pickupDate);
        lastDeliveryDateInput.min = minDeliveryDate.toISOString().split('T')[0];
        
        // Auto-adjust only if last delivery is before pickup (same day allowed)
        const lastDeliveryValue = lastDeliveryDateInput.value;
        if (lastDeliveryValue && lastDeliveryValue < pickupDate) {
          lastDeliveryDateInput.value = lastDeliveryDateInput.min;
        }
      }
    }
    
    // Update on pickup date change
    pickupDateInput.addEventListener('change', updateLastDeliveryMin);
    
    // Initial update
    updateLastDeliveryMin();
  }
})();
</script>
"""
        inner = inner.replace("__PICKUP_VAL__", pickup_val)
        return get_wrap()(wizard_shell(1, inner, session.get("order_draft", {})), u)

    # POST → talteen ja seuraavaan steppiin
    d = session.get("order_draft", {})
    d["pickup"] = request.form.get("pickup", "").strip()
    d["pickup_date"] = request.form.get("pickup_date", "").strip()
    d["last_delivery_date"] = request.form.get("last_delivery_date") or None
    session["order_draft"] = d
    return redirect("/order/new/step2")



# STEP 2: Delivery
@app.route("/order/new/step2", methods=["GET","POST"])
def order_step2():
    u = auth_service.get_current_user()
    if not u:
        return redirect(url_for("auth.login", next="/order/new/step2"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(2, session_data)
    if access_check:
        return access_check

    if request.method == "POST":
        d = session.get("order_draft", {})
        d["dropoff"] = request.form.get("dropoff", "").strip()
        d["last_delivery_date"] = request.form.get("last_delivery_date") or None
        session["order_draft"] = d
        return redirect("/order/new/step3")

    # GET → esitäyttö draftista
    d = session.get("order_draft", {})
    drop_val = (d.get('dropoff', '') or '').replace('"', '&quot;')
    pick_val = (d.get('pickup', '') or '').replace('"', '&quot;')  # piilotettuun from_stepiin
    pickup_date_val = d.get('pickup_date', '')
    last_delivery_date_val = d.get('last_delivery_date', '')

    inner = """
<h2>Auton toimitus</h2>
<form method='POST' class='calculator-form'>
  <!-- piilotettu nouto, jotta kartta voi piirtyä (from_step löytyy DOMista) -->
  <input type="hidden" id="from_step" value="__PICK_VAL__">
  <input type="hidden" id="pickup_date_step2" value="__PICKUP_DATE_VAL__">
  
  <label class='form-label'>Toimitusosoite *</label>
  <div class="autocomplete">
    <input id="to_step" name="dropoff" required value="__DROP_VAL__" placeholder="Katu, kaupunki" class="form-input">
    <div id="ac_to_step" class="ac-list"></div>
  </div>
  
  <!-- Saved Addresses Section (Step 2) -->
  <div style="margin-top: 16px; padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; background: #fafafa;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
      <h3 style="margin: 0; font-size: 1rem; font-weight: 600; color: #374151;">Tallennetut osoitteet</h3>
      <button type="button" onclick="openAddressModal()" class="btn btn-primary btn-sm" style="font-size: 0.875rem;">+ Lisää uusi osoite</button>
    </div>

    <button id="toggleAddresses" type="button" onclick="toggleSavedAddresses()" class="btn btn-ghost btn-sm" style="width: 100%; margin-bottom: 0.75rem;">Näytä tallennetut osoitteet</button>

    <div id="savedAddressesList" style="display: none;">
      <div id="addressesContainer" style="max-height: 260px; overflow-y: auto;"></div>
    </div>
  </div>
  
  <div style="margin-top: 12px;">
    <label for="last_delivery_date_step2">Viimeinen toimituspäivä</label>
    <div class="date-input-wrap" style="position: relative;">
      <svg class="calendar-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); z-index: 1;">
        <rect x="3" y="4" width="18" height="18" rx="2" stroke="#64748b" stroke-width="2"/>
        <line x1="8" y1="2.5" x2="8" y2="6" stroke="#64748b" stroke-width="2"/>
        <line x1="16" y1="2.5" x2="16" y2="6" stroke="#64748b" stroke-width="2"/>
        <line x1="3" y1="10" x2="21" y2="10" stroke="#64748b" stroke-width="2"/>
      </svg>
      <input type="date" name="last_delivery_date" id="last_delivery_date_step2" value="__LAST_DELIVERY_DATE_VAL__" class="form-input date-input" style="padding-left: 40px; height: 44px; font-size: 0.95rem; width: 100%;">
    </div>
  </div>
  
  <div class='calculator-actions mt-2' style="margin-top: 16px;">
    <button type='button' onclick='window.location.href="/order/new/step1"' class="btn btn-ghost">← Takaisin</button>
    <button type='submit' class="btn btn-primary">Jatka →</button>
  </div>
</form>

<style>
/* Keep date inputs compact and icons centered */
.date-input-wrap { position: relative; display: grid; align-items: center; }
.date-input { padding-left: 40px; height: 44px; line-height: 44px; box-sizing: border-box; -webkit-appearance: none; appearance: none; }
.date-input:focus { outline: none; }
.calendar-icon-svg { pointer-events: none; transition: transform 120ms ease-out; }
/* Move native date picker icon to the left visually (keep it clickable) */
.date-input::-webkit-calendar-picker-indicator {
  position: absolute;
  left: 0;
  right: auto;
  width: 44px;
  height: 44px;
  opacity: 0; /* hide default icon */
  cursor: pointer;
}
/* Saved addresses styling and autocomplete dropdown */
.ac-item.saved-address { padding: 0.75rem !important; border-left: 3px solid var(--color-primary, #2563eb); background: #f8fafc; }
.ac-item.saved-address:hover { background: #eef2ff; }
.menu-item:hover { background: #f3f4f6; }
.autocomplete { position: relative; }
.ac-list { position: absolute; top: 100%; left: 0; right: 0; z-index: 9999; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 8px 16px rgba(0,0,0,0.06); }
.ac-item { padding: 10px 12px; cursor: pointer; }
.ac-item.active { background: #eef2ff; }
.ac-empty, .ac-error { padding: 10px 12px; }
</style>

<script>
/* ===== Google Places Autocomplete for Wizard Step 2 ===== */
class WizardGooglePlacesAutocomplete {
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
    document.addEventListener('mousedown', (e)=>{ if(!e.target.closest || !e.target.closest('#'+this.list.id)) { if(e.target!==this.input) this.hide(); } });
    this.list.addEventListener('mousedown', (e)=>{
      const el = e.target.closest ? e.target.closest('.ac-item') : null;
      if (!el) return;
      e.preventDefault();
      const type = el.getAttribute('data-type');
      if (type === 'saved') {
        const id = el.getAttribute('data-id');
        this.pickSaved(id);
      } else {
        const idxAttr = el.getAttribute('data-i');
        const i = idxAttr ? +idxAttr : -1;
        if (i >= 0) this.pick(i);
      }
    });
  }

  onFocus(){
    const q = this.input.value.trim();
    if (!q) { this.showSavedAddresses(); }
  }

  onInput(){
    clearTimeout(this.timer);
    const q = this.input.value.trim();
    if(!q){ this.showSavedAddresses(); return; }

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
    // Use server-side endpoint for address suggestions
    try {
      const response = await fetch('/api/places_autocomplete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      this.items = data.predictions || [];

      // Cache and render
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
    }
  }

  render(){
    const q = this.input.value.trim().toLowerCase();
    let html = '';

    // Saved addresses filtered by query
    let filteredSaved = [];
    if (q && window.savedAddresses) {
      filteredSaved = window.savedAddresses.filter(a =>
        a.displayName?.toLowerCase().includes(q) || a.fullAddress?.toLowerCase().includes(q)
      ).slice(0,5);
    }

    if (filteredSaved.length > 0) {
      html += '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e5e7eb;">Tallennetut osoitteet</div>';
      html += filteredSaved.map(a =>
        `<div class="ac-item saved-address" data-type="saved" data-id="${a.id}">\
           <div style=\"font-weight:600; color:#111827;\">${a.displayName}</div>\
           <div style=\"font-size:0.875rem; color:#6b7280;\">${a.fullAddress}</div>\
         </div>`
      ).join('');
    }

    if (this.items.length > 0) {
      if (filteredSaved.length > 0) {
        html += '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e5e7eb; margin-top: 0.5rem;">Karttahaku</div>';
      }
      html += this.items.slice(0,8).map((item,i)=>`<div class=\"ac-item\" data-type=\"map\" data-i=\"${i}\">${item.description}</div>`).join('');
    }

    if (!html) {
      this.list.innerHTML = '<div class="ac-empty">Ei ehdotuksia</div>';
      this.show();
      return;
    }

    this.list.innerHTML = html;
    this.show();
    this.activeIndex = -1;
  }

  showSavedAddresses(){
    if (!window.savedAddresses || window.savedAddresses.length === 0) return;
    let html = '<div style="padding: 0.5rem; font-weight: 600; font-size: 0.875rem; color: #666; border-bottom: 1px solid #e5e7eb;">Tallennetut osoitteet</div>';
    html += window.savedAddresses.slice(0,8).map(a=>
      `<div class="ac-item saved-address" data-type="saved" data-id="${a.id}">\
         <div style=\"font-weight:600; color:#111827;\">${a.displayName}</div>\
         <div style=\"font-size:0.875rem; color:#6b7280;\">${a.fullAddress}</div>\
       </div>`
    ).join('');
    this.list.innerHTML = html;
    this.show();
  }

  pickSaved(id){
    const addr = (window.savedAddresses||[]).find(a=>String(a.id)===String(id));
    if (!addr) return;
    this.input.value = addr.fullAddress;
    this.hide();
    this.input.dispatchEvent(new Event('change'));
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

/* ===== Saved Addresses (Step 2 page) ===== */
const STORAGE_KEY = 'levoro.savedAddresses.v1';
const LEGACY_STORAGE_KEY = 'savedAddresses';
const COOKIE_KEY = 'levoro_saved_addresses';
window.savedAddresses = [];

async function apiCall(url, options={}){ const res=await fetch(url, options); let data=null; try{ data=await res.json(); }catch{} if(!res.ok) throw new Error((data&&(data.error||data.message))||('HTTP '+res.status)); return data; }
async function fetchServerAddresses(){ const d=await apiCall('/api/saved_addresses',{method:'GET'}); return Array.isArray(d.items)?d.items:[]; }
async function createServerAddress(displayName, fullAddress){ const d=await apiCall('/api/saved_addresses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({displayName, fullAddress})}); return d.item; }
async function deleteServerAddress(id){ await apiCall(`/api/saved_addresses/${encodeURIComponent(id)}`, { method:'DELETE' }); }
function setCookie(name, value, days){ try{ const d=new Date(); d.setTime(d.getTime()+days*864e5); document.cookie=name+'='+value+';expires='+d.toUTCString()+';path=/;SameSite=Lax'; }catch(e){} }
function getCookie(name){ try{ const cname=name+'='; return document.cookie.split(';').map(s=>s.trim()).find(c=>c.indexOf(cname)===0)?.substring(cname.length)||''; }catch(e){return '';} }
function quickLocalLoad(){ let arr=[]; try{ const v1=localStorage.getItem(STORAGE_KEY); if(v1){ const p=JSON.parse(v1); if(Array.isArray(p)&&p.length) arr=p; } }catch(e){} if(!arr.length){ try{ const legacy=localStorage.getItem(LEGACY_STORAGE_KEY); if(legacy){ const p=JSON.parse(legacy); if(Array.isArray(p)&&p.length){ arr=p; localStorage.setItem(STORAGE_KEY, JSON.stringify(arr)); } } }catch(e){} } if(!arr.length){ try{ const cv=getCookie(COOKIE_KEY); if(cv){ const p=JSON.parse(decodeURIComponent(cv)); if(Array.isArray(p)&&p.length) arr=p; } }catch(e){} } return arr.filter(x=>x&&typeof x==='object'&&typeof x.displayName==='string'&&typeof x.fullAddress==='string'); }
function saveToStorage(){ try{ const payload=JSON.stringify(window.savedAddresses||[]); try{ localStorage.setItem(STORAGE_KEY, payload); localStorage.setItem(LEGACY_STORAGE_KEY, payload);}catch(e){} try{ setCookie(COOKIE_KEY, encodeURIComponent(payload), 90);}catch(e){} }catch(e){} }
function renderAddresses(){ const container=document.getElementById('addressesContainer'); if(!container) return; const list=window.savedAddresses||[]; if(!list.length){ container.innerHTML='<p style="color:#9ca3af; padding: 0.5rem; text-align:center; font-size:0.875rem;">Ei vielä tallennettuja osoitteita.</p>'; return;} container.innerHTML=list.map((a,i)=>`\
    <div style="padding: 0.75rem; border:1px solid #e5e7eb; border-radius:6px; margin-bottom:0.5rem; background:white; display:flex; justify-content:space-between; align-items:start;">\
      <div style="flex:1; cursor:pointer;" onclick="useAddress('${a.id}')">\
        <div style="font-weight:600; color:#111827; margin-bottom:0.25rem;">${a.displayName}</div>\
        <div style="font-size:0.875rem; color:#6b7280;">${a.fullAddress}</div>\
      </div>\
      <button type="button" onclick="deleteAddressDirectly(${i})" class="btn btn-ghost" title="Poista">×</button>\
    </div>`).join(''); }
function toggleSavedAddresses(){ const list=document.getElementById('savedAddressesList'); const btn=document.getElementById('toggleAddresses'); if(!list||!btn) return; const show=list.style.display!=='block'; list.style.display=show?'block':'none'; btn.textContent=show?'Piilota tallennetut osoitteet':'Näytä tallennetut osoitteet'; }
function useAddress(id){ const a=(window.savedAddresses||[]).find(x=>String(x.id)===String(id)); if(!a) return; const inp=document.getElementById('to_step'); if(inp){ inp.value=a.fullAddress; inp.dispatchEvent(new Event('change')); } }
async function deleteAddressDirectly(index){ const item=(window.savedAddresses||[])[index]; if(!item) return; try{ if(item.id) await deleteServerAddress(item.id);}catch(e){} window.savedAddresses.splice(index,1); saveToStorage(); renderAddresses(); }
function openAddressModal(){ const html=`<div id=\"addressModal\" style=\"position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:9999;\"><div style=\"background:white; padding:1.25rem; border-radius:12px; width:90%; max-width:480px;\"><h3 style=\"margin:0 0 1rem 0; font-size:1.1rem; font-weight:600;\">Lisää uusi osoite</h3><div style=\"margin-bottom:0.75rem;\"><label style=\"display:block; margin-bottom:0.25rem;\">Nimi *</label><input id=\"addrName\" class=\"form-input\" placeholder=\"Esim. Koti, Toimisto\" style=\"width:100%;\"></div><div style=\"margin-bottom:1rem;\"><label style=\"display:block; margin-bottom:0.25rem;\">Osoite *</label><input id=\"addrFull\" class=\"form-input\" placeholder=\"Esim. Mannerheimintie 1, Helsinki\" style=\"width:100%;\"></div><div style=\"display:flex; gap:0.5rem; justify-content:flex-end;\"><button type=\"button\" class=\"btn btn-ghost\" onclick=\"closeAddressModal()\">Peruuta</button><button type=\"button\" class=\"btn btn-primary\" onclick=\"saveAddress()\">Tallenna</button></div></div></div>`; document.body.insertAdjacentHTML('beforeend', html); document.getElementById('addrName').focus(); }
function closeAddressModal(){ const m=document.getElementById('addressModal'); if(m) m.remove(); }
async function saveAddress(){ const name=document.getElementById('addrName').value.trim(); const addr=document.getElementById('addrFull').value.trim(); if(!name||!addr){ alert('Täytä molemmat kentät'); return;} let created=null; try{ created=await createServerAddress(name, addr);}catch(e){} const item=created||{ id: Date.now(), displayName:name, fullAddress:addr }; window.savedAddresses.push(item); saveToStorage(); renderAddresses(); closeAddressModal(); }
async function loadSavedAddresses(){ try{ window.savedAddresses=quickLocalLoad(); renderAddresses(); }catch(e){} try{ const server=await fetchServerAddresses(); if(Array.isArray(server)){ window.savedAddresses=server; saveToStorage(); renderAddresses(); } }catch(e){} }

/* Initialize saved addresses + autocomplete for Step 2 */
loadSavedAddresses();
const step2Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('to_step'),
  document.getElementById('ac_to_step')
);
window.toAutocomplete = step2Autocomplete;

/* Date validation for Step 2 */
(function() {
  const pickupDateStep2 = document.getElementById('pickup_date_step2');
  const lastDeliveryDateStep2 = document.getElementById('last_delivery_date_step2');
  
  if (pickupDateStep2 && lastDeliveryDateStep2) {
    const pickupDate = pickupDateStep2.value;
    
    if (pickupDate) {
      // Same day allowed: min = pickupDate (no +1)
      const minDeliveryDate = new Date(pickupDate);
      lastDeliveryDateStep2.min = minDeliveryDate.toISOString().split('T')[0];
      
      // Auto-adjust only if last delivery is before pickup (same day allowed)
      const lastDeliveryValue = lastDeliveryDateStep2.value;
      if (lastDeliveryValue && lastDeliveryValue < pickupDate) {
        lastDeliveryDateStep2.value = lastDeliveryDateStep2.min;
      }
    }
  }
})();
</script>
"""
    inner = inner.replace("__DROP_VAL__", drop_val).replace("__PICK_VAL__", pick_val).replace("__PICKUP_DATE_VAL__", pickup_date_val).replace("__LAST_DELIVERY_DATE_VAL__", last_delivery_date_val)
    return get_wrap()(wizard_shell(2, inner, session.get("order_draft", {})), u)



# STEP 3: Vehicle
@app.route("/order/new/step3", methods=["GET","POST"])
def order_step3():
    u = auth_service.get_current_user()
    if not u: return redirect(url_for("auth.login", next="/order/new/step3"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(3, session_data)
    if access_check:
        return access_check
    if request.method == "POST":
        d = session.get("order_draft", {})
        d["reg_number"] = request.form.get("reg_number","").strip()
        d["winter_tires"] = bool(request.form.get("winter_tires"))
        session["order_draft"] = d
        return redirect("/order/new/step4")
    
    # GET - pre-fill form with existing values
    d = session.get("order_draft", {})
    reg_val = (d.get("reg_number", "") or "").replace('"', '&quot;')
    winter_checked = "checked" if d.get("winter_tires") else ""

    # Check for error message and display it
    error_msg = session.pop("error_message", None)
    error_html = f"<div class='error-message' style='margin-bottom: 1rem; padding: 0.75rem; background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 0.375rem;'>{error_msg}</div>" if error_msg else ""

    inner = f"""
<h2 class='card-title'>Ajoneuvon tiedot</h2>
{error_html}
<form method='POST' class='calculator-form'>
  <label class='form-label'>Rekisterinumero *</label>
  <input name='reg_number' required placeholder='ABC-123' class='form-input' value="{reg_val}">
  
  <div class='form-group mt-4'>
    <label class='form-checkbox'>
      <input type='checkbox' name='winter_tires' value='1' {winter_checked}>
      <span class='form-checkbox-label'>Autossa on talvirenkaat</span>
    </label>
  </div>
  
  <div class='calculator-actions'>
    <button type='button' onclick='window.location.href="/order/new/step2"' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' class='btn btn-primary'>Jatka →</button>
  </div>
</form>"""
    return get_wrap()(wizard_shell(3, inner, session.get("order_draft", {})), u)

# STEP 4: Contact
@app.route("/order/new/step4", methods=["GET","POST"])
def order_step4():
    u = auth_service.get_current_user()
    if not u: return redirect(url_for("auth.login", next="/order/new/step4"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(4, session_data)
    if access_check:
        return access_check

    if request.method == "POST":
        d = session.get("order_draft", {})
        # Orderer (Tilaaja) fields
        d["orderer_name"] = request.form.get("orderer_name","").strip()
        d["orderer_email"] = request.form.get("orderer_email","").strip()
        d["orderer_phone"] = request.form.get("orderer_phone","").strip()
        # Customer (Asiakas) fields
        d["customer_name"] = request.form.get("customer_name","").strip()
        d["customer_phone"] = request.form.get("customer_phone","").strip()
        
        # Validate phone numbers
        if not validate_phone_number(d["orderer_phone"]):
            session["error_message"] = "Tilaajan puhelinnumero ei ole kelvollinen. Käytä vain numeroita ja merkkejä +, -, ( )"
            session["order_draft"] = d
            return redirect("/order/new/step4")
        
        # Validate customer phone only if provided
        if d["customer_phone"] and not validate_phone_number(d["customer_phone"]):
            session["error_message"] = "Asiakkaan puhelinnumero ei ole kelvollinen. Käytä vain numeroita ja merkkejä +, -, ( )"
            session["order_draft"] = d
            return redirect("/order/new/step4")
        
        # Legacy field for backward compatibility
        d["phone"] = d["customer_phone"]
        session["order_draft"] = d
        return redirect("/order/new/step5")

    # Get form values from session for pre-filling
    d = session.get("order_draft", {})

    # Auto-fill orderer from logged-in user if not already filled
    if not d.get("orderer_name"):
        d["orderer_name"] = u.get("name", "")
        d["orderer_email"] = u.get("email", "")
        d["orderer_phone"] = u.get("phone", "")
        session["order_draft"] = d

    orderer_name_val = (d.get("orderer_name", "") or "").replace('"', '&quot;')
    orderer_email_val = (d.get("orderer_email", "") or "").replace('"', '&quot;')
    orderer_phone_val = (d.get("orderer_phone", "") or "").replace('"', '&quot;')

    customer_name_val = (d.get("customer_name", "") or "").replace('"', '&quot;')
    customer_phone_val = (d.get("customer_phone", "") or "").replace('"', '&quot;')

    # Check for error message and display it
    error_msg = session.pop("error_message", None)
    error_html = f"<div class='error-message'>{error_msg}</div>" if error_msg else ""

    inner = f"""
<h2 class='card-title'>Yhteystiedot</h2>
{error_html}
<form method='POST' class='calculator-form'>
  <!-- Orderer Section -->
  <div style='background: #f0f9ff; padding: 1.25rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px solid #bfdbfe;'>
    <h3 style='margin-top: 0; margin-bottom: 1rem; color: #1e40af; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;'>
      Tilaajan tiedot
      <span style='font-size: 0.8rem; font-weight: normal; color: #64748b;'>(Kuka tilaa kuljetuksen)</span>
    </h3>
    <label class='form-label'>Tilaajan nimi *</label>
    <input name='orderer_name' required class='form-input' value="{orderer_name_val}" placeholder="Yrityksen nimi tai yhteyshenkilö">
    <label class='form-label'>Tilaajan sähköposti *</label>
    <input type='email' name='orderer_email' required class='form-input' value="{orderer_email_val}" placeholder="yritys@example.com">
    <label class='form-label'>Tilaajan puhelin *</label>
    <input type='tel' name='orderer_phone' required class='form-input' value="{orderer_phone_val}" placeholder="+358..." pattern="[+]?[0-9\\s\\-()]+" title="Käytä vain numeroita ja merkkejä +, -, ( )" aria-label="Tilaajan puhelinnumero">
  </div>

  <!-- Customer Section -->
  <div style='background: #fefce8; padding: 1.25rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px solid #fde047;'>
    <h3 style='margin-top: 0; margin-bottom: 1rem; color: #854d0e; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;'>
      Asiakkaan tiedot
      <span style='font-size: 0.8rem; font-weight: normal; color: #64748b;'>(Valinnainen)</span>
    </h3>
    <label class='form-label'>Asiakkaan nimi </label>
    <input name='customer_name'  class='form-input' value="{customer_name_val}" placeholder="Vastaanottajan nimi">
    <label class='form-label'>Asiakkaan puhelinnumero </label>
    <input type='tel' name='customer_phone'  class='form-input' value="{customer_phone_val}" placeholder="+358..." pattern="[+]?[0-9\\s\\-()]+" title="Käytä vain numeroita ja merkkejä +, -, ( )" aria-label="Asiakkaan puhelinnumero">
  </div>

  <div class='row calculator-actions'>
    <button type='button' onclick='window.location.href="/order/new/step3"' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' class='btn btn-primary'>Jatka →</button>
  </div>
</form>
<script>
// Phone number validation with real-time feedback
(function() {{
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    const phonePattern = /^[+]?[0-9\\s\\-()]+$/;
    
    phoneInputs.forEach(input => {{
        // Create error message element
        const errorMsg = document.createElement('small');
        errorMsg.style.cssText = 'color: #dc2626; font-size: 0.875rem; margin-top: -18px; margin-bottom: 12px; display: none;';
        errorMsg.textContent = 'Käytä vain numeroita ja merkkejä +, -, ( )';
        input.parentNode.insertBefore(errorMsg, input.nextSibling);
        
        // Real-time validation
        input.addEventListener('input', function() {{
            const value = this.value.trim();
            
            if (value && !phonePattern.test(value)) {{
                errorMsg.style.display = 'block';
                this.setCustomValidity('Virheellinen puhelinnumero');
            }} else {{
                errorMsg.style.display = 'none';
                this.setCustomValidity('');
            }}
        }});
        
        // Validation on blur
        input.addEventListener('blur', function() {{
            if (this.value.trim() && !phonePattern.test(this.value.trim())) {{
                errorMsg.style.display = 'block';
            }}
        }});
    }});
}})();
</script>"""
    return get_wrap()(wizard_shell(4, inner, session.get("order_draft", {})), u)

# STEP 5: Notes
@app.route("/order/new/step5", methods=["GET","POST"])
def order_step5():
    u = auth_service.get_current_user()
    if not u: return redirect(url_for("auth.login", next="/order/new/step5"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(5, session_data)
    if access_check:
        return access_check
    if request.method == "POST":
        d = session.get("order_draft", {})
        d["additional_info"] = request.form.get("additional_info","").strip()
        session["order_draft"] = d
        return redirect("/order/new/confirm")
    inner = """
<h2 class='card-title'>Lisätiedot tai erityistoiveet</h2>
<form method='POST' class='calculator-form'>
  <label class='form-label'>Kirjoita toiveet</label>
  <textarea name='additional_info' rows='5' placeholder='Esim. Autossa on talvirenkaat mukana, toimitus kiireellinen' class='form-input'></textarea>
  <div class='row calculator-actions'>
    <button type='button' onclick='window.location.href="/order/new/step4"' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' class='btn btn-primary'>Jatka →</button>
  </div>
</form>"""
    return get_wrap()(wizard_shell(5, inner, session.get("order_draft", {})), u)

# STEP 6: Confirm
@app.route("/order/new/confirm", methods=["GET","POST"])
def order_confirm():
    u = auth_service.get_current_user()
    if not u: return redirect(url_for("auth.login", next="/order/new/confirm"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(6, session_data)
    if access_check:
        return access_check
    d = session.get("order_draft", {})
    required = ["pickup","dropoff","reg_number",
                "orderer_name","orderer_email","orderer_phone"]

    # Check which fields are missing and redirect to appropriate step
    missing_fields = [k for k in required if not d.get(k)]
    if missing_fields:
        # Enhanced debug logging with session data inspection
        print(f"VALIDATION ERROR - Missing required fields: {missing_fields}")
        print(f"Current session data: {d}")

        # Create more specific error messages
        if any(field in missing_fields for field in ["pickup", "dropoff"]):
            if "pickup" in missing_fields and "dropoff" in missing_fields:
                session["error_message"] = "Sekä nouto- että toimitusosoite puuttuvat. Täytä molemmat osoitteet."
            elif "pickup" in missing_fields:
                session["error_message"] = "Noutoosoite puuttuu. Täytä noutoosoite."
            else:
                session["error_message"] = "Toimitusosoite puuttuu. Täytä toimitusosoite."
            return redirect("/order/new/step1")
        elif "reg_number" in missing_fields:
            session["error_message"] = "Ajoneuvon rekisterinumero puuttuu. Täytä rekisterinumero."
            return redirect("/order/new/step3")
        elif any(field in missing_fields for field in ["orderer_name", "orderer_email", "orderer_phone"]):
            missing_contact_fields = [f for f in ["orderer_name", "orderer_email", "orderer_phone"] if f in missing_fields]
            field_names = {
                "orderer_name": "tilaajan nimi", "orderer_email": "tilaajan sähköposti", "orderer_phone": "tilaajan puhelinnumero"
            }
            missing_names = [field_names[f] for f in missing_contact_fields]
            session["error_message"] = f"Tilaajan yhteystiedot puuttuvat: {', '.join(missing_names)}. Täytä puuttuvat tiedot."
            return redirect("/order/new/step4")

    km = 0.0
    err = None
    try:
        km = order_service.route_km(d["pickup"], d["dropoff"])
    except Exception as e:
        err = f"Hinnanlaskenta epäonnistui: {e}"
    u = auth_service.get_current_user()
    # esim. otetaan joustava nouto jos käyttäjä EI antanut noutopäivää:
    time_window = "flex" if not d.get("pickup_date") else "exact"
    return_leg = False  # if you later add a checkbox for round-trip, set True accordingly
    net, vat, gross, _ = order_service.price_from_km(
        km,
        pickup_addr=d.get("pickup"),
        dropoff_addr=d.get("dropoff"),
        return_leg=return_leg
    )

    if request.method == "POST":
        # Prepare order data for service layer (excludes id, user_id, created_at, status - handled by service)
        order_data = {
            "pickup_address": d.get("pickup"),
            "dropoff_address": d.get("dropoff"),
            "reg_number": d.get("reg_number"),
            "pickup_date": d.get("pickup_date") or None,
            "last_delivery_date": d.get("last_delivery_date") or None,

            # Orderer (Tilaaja) information
            "orderer_name": d.get("orderer_name"),
            "orderer_email": d.get("orderer_email"),
            "orderer_phone": d.get("orderer_phone"),

            # Customer (Asiakas) information
            "customer_name": d.get("customer_name"),
            "customer_phone": d.get("customer_phone"),

            # Legacy fields for backward compatibility
            "phone": d.get("customer_phone"),
            "company": d.get("company"),

            "additional_info": d.get("additional_info"),

            "distance_km": float(round(km, 2)),
            "price_net": float(net),
            "price_vat": float(vat),
            "price_gross": float(gross),

            "winter_tires": bool(d.get("winter_tires")) if "winter_tires" in d else False
        }

        # Use service layer to create order (includes automatic email sending)
        success, order, error = order_service.create_order(int(u["id"]), order_data)

        if success and order:
            # Clear session and redirect to order view
            session.pop("order_draft", None)
            return redirect(f"/order/{order['id']}")
        else:
            # Handle error case
            session["error_message"] = f"Tilauksen luominen epäonnistui: {error or 'Tuntematon virhe'}"
            # Stay on confirmation page to show error
            pass

    price_block = f"<div class='card'><strong style='font-size: 0.9em;'>Hinta:</strong> <span style='font-size: 1.5em; font-weight: 800;'>{net:.2f} €</span> <strong style='font-size: 1.1em;'>ALV 0%</strong> <span style='opacity: 0.6; font-size: 0.85em;'>({km:.1f} km)</span></div>"
    if err: price_block = f"<div class='card'><span class='muted'>{err}</span><br>{price_block}</div>"

    # Check for error message in session
    error_msg = session.pop("error_message", None)
    error_html = f"<div class='alert alert-error' style='margin-bottom: 1rem; padding: 1rem; background: #fee; border: 1px solid #fcc; border-radius: 4px; color: #c00;'>{error_msg}</div>" if error_msg else ""

    # Format dates for display under addresses
    def _fmt_date(s: str):
        try:
            if not s:
                return None
            dt = datetime.datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return s

    pickup_date_str = _fmt_date(d.get("pickup_date"))
    last_delivery_date_str = _fmt_date(d.get("last_delivery_date"))

    pickup_date_html = f"<p class='confirmation-meta'>Toivottu noutopäivä: {pickup_date_str}</p>" if pickup_date_str else ""
    delivery_date_html = f"<p class='confirmation-meta'>Viimeinen toimituspäivä: {last_delivery_date_str}</p>" if last_delivery_date_str else ""

    inner = f"""
<h2 class='card-title'>Vahvista tilaus</h2>
{error_html}
<div class='confirmation-layout'>
  <div class='confirmation-grid'>
    <div class='confirmation-card'><h3 class='confirmation-title'>Nouto</h3><p class='confirmation-text'>{d.get('pickup')}</p>{pickup_date_html}</div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Toimitus</h3><p class='confirmation-text'>{d.get('dropoff')}</p>{delivery_date_html}</div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Ajoneuvo</h3><p class='confirmation-text'>Rekisteri: {d.get('reg_number')}</p><p class='confirmation-meta'>Talvirenkaat: {"Kyllä" if d.get('winter_tires') else "Ei"}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Tilaajan tiedot</h3><p class='confirmation-text'>{d.get('orderer_name')}</p><p class='confirmation-meta'>{d.get('orderer_email')} / {d.get('orderer_phone')}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Asiakkaan tiedot</h3><p class='confirmation-text'>{d.get('customer_name')}</p><p class='confirmation-meta'>{d.get('customer_phone')}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Lisätiedot</h3><p class='confirmation-text'>{(d.get('additional_info') or '-').replace('<','&lt;')}</p></div>
  </div>
  <div class='confirmation-map-container'>
    <div class='confirmation-card map-card'>
      <h3 class='confirmation-title'>Reitti</h3>
      <div id="confirmation_map" class="confirmation-map"></div>
      <p class='confirmation-meta'><strong style='font-size: 1.3em; font-weight: 800;'>{net:.2f} €</strong> <strong>ALV 0%</strong></p>
    </div>
  </div>
</div>
<div class='price-summary'>
  <div class='price-card'>
    <h3 class='price-title'>Hinta</h3>
    <div class='price-details'>
      <span class='distance'>{km:.1f} km</span>
      <div class='price-breakdown-confirm'>
        <div class='price-main-confirm' style="font-size: 2.5em; font-weight: 800; line-height: 1.1; margin-bottom: 4px;">{net:.2f} €</div>
        <div style="font-size: 1.2em; font-weight: 700; margin-bottom: 12px;">ALV 0%</div>
        <div class='price-vat-confirm' style="font-size: 0.75em; opacity: 0.5; margin-top: 8px;">ALV 25,5%: {vat:.2f} € | Yhteensä sis. ALV: {gross:.2f} €</div>
      </div>
    </div>
    {f'<p class="price-error">{err}</p>' if err else ''}
  </div>
</div>
<form method='POST' class='calculator-form'>
  <div class='calculator-actions'>
    <button type='button' onclick='window.location.href="/order/new/step5"' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' class='btn btn-primary'>Lähetä tilaus</button>
  </div>
</form>

<!-- Leaflet CSS and JS for map -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>

<style>
.confirmation-layout {{
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}}

.confirmation-grid {{
  flex: 1;
  min-width: 300px;
}}

.confirmation-map-container {{
  flex: 1;
  min-width: 300px;
}}

.confirmation-map {{
  height: 250px;
  border-radius: 0.5rem;
  margin: 0.75rem 0;
}}

.map-card {{
  height: auto;
}}

/* Distance label styling for map */
.distance-label {{
  background: transparent;
  border: none;
}}

.distance-text {{
  background: rgba(59, 130, 246, 0.95);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 1.5rem;
  font-weight: 700;
  font-size: 0.95rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  white-space: nowrap;
  text-align: center;
}}

@media (max-width: 768px) {{
  .confirmation-layout {{
    flex-direction: column;
  }}

  .confirmation-map {{
    height: 200px;
  }}
  
  .distance-text {{
    font-size: 0.85rem;
    padding: 0.4rem 0.8rem;
  }}
}}
</style>

<script>
class RouteMap {{
  constructor(elId, mini=false){{
    this.map = L.map(elId, {{
      zoomControl: false,
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false
    }});
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{ maxZoom: 19 }}).addTo(this.map);
    this.map.setView([61.9241,25.7482], mini?5:6);
    this.poly = null; this.m1 = null; this.m2 = null; this.distanceLabel = null;
  }}

  draw(latlngs, start, end, distance){{
    if(this.poly) this.poly.remove();
    if(this.m1) this.m1.remove();
    if(this.m2) this.m2.remove();
    if(this.distanceLabel) this.distanceLabel.remove();

    this.poly = L.polyline(latlngs, {{ weight: 5, opacity: 0.9 }}).addTo(this.map);
    this.m1 = L.marker([start[0],start[1]]).addTo(this.map);
    this.m2 = L.marker([end[0],end[1]]).addTo(this.map);
    this.map.fitBounds(this.poly.getBounds(), {{ padding:[24,24] }});

    // Add distance label in the center of the route
    if(distance) {{
      const bounds = this.poly.getBounds();
      const center = bounds.getCenter();
      this.distanceLabel = L.marker(center, {{
        icon: L.divIcon({{
          className: 'distance-label',
          html: `<div class="distance-text">${{distance}} km</div>`,
          iconSize: [100, 35],
          iconAnchor: [50, 17]
        }}),
        zIndexOffset: 1000
      }}).addTo(this.map);
    }}
  }}
}}

// Initialize map when page loads
document.addEventListener('DOMContentLoaded', function() {{
  const map = new RouteMap('confirmation_map', true);

  // Fetch route data using the same endpoint as calculator
  const pickup = '{d.get("pickup")}';
  const dropoff = '{d.get("dropoff")}';

  fetch('/api/route_geo', {{
    method: 'POST',
    headers: {{
      'Content-Type': 'application/json'
    }},
    body: JSON.stringify({{ pickup: pickup, dropoff: dropoff }})
  }})
    .then(response => response.json())
    .then(data => {{
      if (data.latlngs && data.start && data.end) {{
        map.draw(data.latlngs, data.start, data.end, {km:.1f});
      }}
    }})
    .catch(error => {{ 
      console.error('Map loading error:', error);
      /* Could not load route - silently handle */ 
    }});
}});
</script>
"""
    return get_wrap()(wizard_shell(6, inner, session.get("order_draft", {})), u)
