# order_wizard.py
import datetime
import re
from typing import Dict, List
from flask import request, redirect, url_for, session
from services.auth_service import auth_service
from services.order_service import order_service
from models.database import db_manager
from models.order import order_model

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
        qp_pick_id = (request.args.get("pickup_place_id") or "").strip()
        qp_drop_id = (request.args.get("dropoff_place_id") or "").strip()
        if qp_pick or qp_drop or qp_pick_id or qp_drop_id:
            d = session.get("order_draft", {})
            if qp_pick:
                d["pickup"] = qp_pick
            if qp_drop:
                d["dropoff"] = qp_drop   # talletetaan jo tässä vaiheessa
            if qp_pick_id:
                d["pickup_place_id"] = qp_pick_id
            if qp_drop_id:
                d["dropoff_place_id"] = qp_drop_id
            session["order_draft"] = d

        d = session.get("order_draft", {})

        def _parse_iso_date(value):
            try:
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                return None

        today = datetime.date.today()
        pickup_date_obj = _parse_iso_date(d.get("pickup_date"))
        if not pickup_date_obj or pickup_date_obj < today:
            pickup_date_obj = today
        pickup_date_val = pickup_date_obj.isoformat()

        pickup_time_val = (d.get("pickup_time") or "").strip()

        pickup_val = (d.get("pickup", "") or "").replace('"', '&quot;')
        pickup_place_id_val = (d.get("pickup_place_id", "") or "").replace('"', '&quot;')
        paluu_auto_checked = "checked" if d.get("paluu_auto") else ""

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
    <input type="hidden" id="pickup_place_id" name="pickup_place_id" value="__PICKUP_PLACE_ID__">
    <div id="ac_from_step" class="ac-list"></div>
  </div>

  <!-- Date and Time Picker -->
  <div class="wizard-date-grid">
    <div class="wizard-field">
      <label>Noutopäivä *</label>
      <div class="wizard-input-box" onclick="openDatePicker('pickup_date')">
        <div class="wizard-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
        </div>
        <input type="date" id="pickup_date" name="pickup_date" required value="__PICKUP_DATE_VAL__">
      </div>
    </div>
    <div class="wizard-field">
      <label>Noutoaika (valinnainen)</label>
      <div class="wizard-input-box wizard-input-box--time" onclick="openTimePicker('pickup_time')">
        <div class="wizard-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        </div>
        <input type="time" id="pickup_time" name="pickup_time" value="__PICKUP_TIME_VAL__">
        <button type="button" id="pickup_time_clear" class="wizard-clear-btn" onclick="clearTimeInput('pickup_time')">×</button>
      </div>
    </div>
  </div>

  <!-- Saved Addresses - Compact -->
  <details class="saved-addresses-details" style="margin-top: 36px; padding: 0.5rem 0.75rem; border: 1px solid #e5e7eb; border-radius: 6px; background: #fafafa;">
    <summary style="display: flex; align-items: center; justify-content: space-between; padding: 0.25rem 0; cursor: pointer; font-size: 0.85rem; color: #64748b; list-style: none;">
      <span style="display: flex; align-items: center; gap: 6px;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
        Tallennetut osoitteet
      </span>
      <span style="display: flex; align-items: center; gap: 8px;">
        <button type="button" onclick="event.stopPropagation(); openAddressModal();" class="btn-link" style="font-size: 0.8rem; color: #2563eb; background: none; border: none; cursor: pointer; padding: 0;">+ Lisää</button>
        <svg class="chevron-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </span>
    </summary>
    <div id="savedAddressesList" style="padding: 0.5rem 0;">
      <div id="addressesContainer" style="max-height: 180px; overflow-y: auto;"></div>
    </div>
  </details>

  <!-- Paluuajo -->
  <div class='form-group' style="margin-top: 20px; padding: 14px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
      <label class='form-checkbox' style="margin: 0;">
        <input type='checkbox' id='paluu_auto_checkbox' name='paluu_auto' value='1' __PALUU_AUTO_CHECKED__>
        <span class='form-checkbox-label' style="font-weight: 600; font-size: 1.05rem; color: #1e293b; margin-left: 10px;">Paluuajo</span>
      </label>
      <span style="background: #f97316; color: white; font-weight: 600; font-size: 0.8rem; padding: 5px 12px; border-radius: 6px; white-space: nowrap;">-30% Alennus</span>
    </div>
    <p style="margin: 0; padding-left: 0; font-size: 0.875rem; color: #64748b; line-height: 1.5;">Säästä 30% paluukuljetuksesta</p>
  </div>

  <div class='calculator-actions mt-2' style="margin-top: 16px;">
    <button type='submit' class="btn btn-primary" aria-label="Jatka seuraavaan vaiheeseen">Jatka →</button>
  </div>
</form>

<style>
/* Wizard date/time picker styles */
.wizard-date-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.wizard-field label {
  display: block;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 6px;
  font-size: 14px;
}
.wizard-input-box {
  position: relative;
  display: flex;
  align-items: center;
  height: 48px;
  border: 1px solid #22c55e;
  border-radius: 8px;
  background: #fff;
  padding: 0 12px 0 44px;
}
.wizard-input-box:focus-within {
  border-color: #16a34a;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
}
.wizard-icon {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  z-index: 2;
}
.wizard-icon svg { display: block; }
.wizard-input-box--time { padding-right: 44px; }
.wizard-input-box input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 15px;
  color: #1e293b;
  outline: none;
  height: 100%;
  min-width: 0;
  width: 100%;
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
}
.wizard-input-box input[type="date"]::-webkit-date-and-time-value,
.wizard-input-box input[type="time"]::-webkit-date-and-time-value {
  text-align: left;
  margin: 0;
  padding: 0;
}
.wizard-input-box input::-webkit-calendar-picker-indicator {
  opacity: 0;
  cursor: pointer;
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
}
.wizard-clear-btn {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #94a3b8;
  font-size: 18px;
  border: none;
  background: none;
  padding: 0;
  opacity: 0;
  pointer-events: none;
  z-index: 2;
}
.wizard-clear-btn:hover { color: #64748b; }
@media (max-width: 640px) {
  .wizard-date-grid { grid-template-columns: 1fr; }
}
/* Saved addresses compact styling */
.saved-addresses-details summary::-webkit-details-marker { display: none; }
.saved-addresses-details[open] .chevron-icon { transform: rotate(180deg); }
.chevron-icon { transition: transform 0.2s ease; }
.saved-addresses-details { border-bottom: 1px solid #e5e7eb; }
.ac-item.saved-address { padding: 0.5rem 0.75rem !important; border-left: 2px solid #2563eb; background: #f8fafc; margin-bottom: 4px; border-radius: 4px; font-size: 0.9rem; }
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
function applySavedPhoneToStep2(phone){
  const hidden = document.getElementById('saved_dropoff_phone');
  if (!hidden) return;
  hidden.value = (phone || '').trim();
}

function openDatePicker(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.showPicker) {
    input.showPicker();
  } else {
    input.focus();
    input.click();
  }
}

function openTimePicker(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.showPicker) {
    input.showPicker();
  } else {
    input.focus();
    input.click();
  }
}

function clearTimeInput(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

function toggleClearButton(inputId, buttonId){
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);
  if (!input || !button) return;
  const hasValue = !!input.value;
  button.style.opacity = hasValue ? '1' : '0';
  button.style.pointerEvents = hasValue ? 'auto' : 'none';
}

function openDatePicker(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.showPicker) {
    input.showPicker();
  } else {
    input.focus();
    input.click();
  }
}

function openTimePicker(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.showPicker) {
    input.showPicker();
  } else {
    input.focus();
    input.click();
  }
}

function clearTimeInput(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

function toggleClearButton(inputId, buttonId){
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);
  if (!input || !button) return;
  const hasValue = !!input.value;
  button.style.opacity = hasValue ? '1' : '0';
  button.style.pointerEvents = hasValue ? 'auto' : 'none';
}

/* ===== Google Places Autocomplete for Wizard ===== */
class WizardGooglePlacesAutocomplete {
  constructor(input, listEl, options = {}){
    this.input = input;
    this.list = listEl;
    this.placeIdInput = options.placeIdInput || null;
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
    this.setPlaceId('');

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
    this.setPlaceId('');
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
    this.setPlaceId('');
    this.setPlaceId('');
    if (this.input && this.input.id === 'to_step') {
      applySavedPhoneToStep2(addr.phone || '');
    }
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

    if (this.input && this.input.id === 'to_step') {
      applySavedPhoneToStep2('');
    }
    this.input.value = item.description;
    this.hide();
    this.input.dispatchEvent(new Event('change'));
  }

  show(){ this.list.style.display='block'; }
  hide(){ this.list.style.display='none'; }

  setPlaceId(value){
    const val = value || '';
    if (this.placeIdInput) {
      this.placeIdInput.value = val;
    }
    if (this.input) {
      this.input.dataset.placeId = val;
    }
  }
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

async function createServerAddress(displayName, fullAddress, phone){
  const payload = { displayName, fullAddress };
  if (phone) payload.phone = phone;
  const data = await apiCall('/api/saved_addresses', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
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
      <div style="flex:1;">
        <div style="font-weight:600; color:#111827; margin-bottom:0.25rem;">${a.displayName}</div>
        <div style="font-size:0.875rem; color:#6b7280;">${a.fullAddress}</div>
        ${a.phone ? `<div style="font-size:0.85rem; color:#334155; margin-top:4px;">Puhelin: ${a.phone}</div>` : ''}
      </div>
      <button type="button" onclick="deleteAddressDirectly(${i})" class="btn-delete-address" style="border: 2px solid #2563eb; background: white; cursor: pointer; padding: 0.25rem 0.5rem; font-size: 1.25rem; line-height: 1; color: #2563eb; transition: all 0.2s; border-radius: 6px; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;" onmouseover="this.style.background='#2563eb'; this.style.color='white'" onmouseout="this.style.background='white'; this.style.color='#2563eb'" title="Poista">×</button>
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
      <div style="margin-bottom:0.75rem;">
        <label style="display:block; margin-bottom:0.25rem;">Puhelinnumero (valinnainen)</label>
        <input id="addrPhone" type="tel" class="form-input" placeholder="+358..." style="width:100%;">
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
  const phoneInput = document.getElementById('addrPhone');
  const phone = phoneInput ? phoneInput.value.trim() : '';
  if (!name || !addr) { alert('Täytä molemmat kentät'); return; }
  if (phone && !/^[+]?[0-9\s\-()]+$/.test(phone)) { alert('Syötä vain numeroita ja merkit +, -, ( )'); return; }
  let created=null; try{ created = await createServerAddress(name, addr, phone);}catch(e){}
  const item = created || { id: Date.now(), displayName: name, fullAddress: addr, phone };
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
  document.getElementById('ac_from_step'),
  { placeIdInput: document.getElementById('pickup_place_id') }
);
window.fromAutocomplete = step1Autocomplete;

/* Date validation for Step 1 */
(function() {
  const pickupDateInput = document.getElementById('pickup_date');

  function formatISODate(dateObj) {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function ensurePickupDefault() {
    if (!pickupDateInput) return;
    const today = new Date();
    const todayStr = formatISODate(today);
    pickupDateInput.min = todayStr;
    if (!pickupDateInput.value || pickupDateInput.value < todayStr) {
      pickupDateInput.value = todayStr;
    }
  }

  if (pickupDateInput) {
    ensurePickupDefault();
    pickupDateInput.addEventListener('change', ensurePickupDefault);
    pickupDateInput.addEventListener('input', ensurePickupDefault);
  }

  const pickupTimeInput = document.getElementById('pickup_time');
  if (pickupTimeInput) {
    toggleClearButton('pickup_time', 'pickup_time_clear');
    pickupTimeInput.addEventListener('input', () => toggleClearButton('pickup_time', 'pickup_time_clear'));
    pickupTimeInput.addEventListener('change', () => toggleClearButton('pickup_time', 'pickup_time_clear'));
  }
})();
</script>
"""
        inner = (
            inner
            .replace("__PICKUP_VAL__", pickup_val)
            .replace("__PICKUP_PLACE_ID__", pickup_place_id_val)
            .replace("__PICKUP_DATE_VAL__", pickup_date_val)
            .replace("__PICKUP_TIME_VAL__", pickup_time_val)
            .replace("__PALUU_AUTO_CHECKED__", paluu_auto_checked)
        )
        return get_wrap()(wizard_shell(1, inner, session.get("order_draft", {})), u)

    # POST → talteen ja seuraavaan steppiin
    d = session.get("order_draft", {})
    d["pickup"] = request.form.get("pickup", "").strip()
    d["pickup_place_id"] = request.form.get("pickup_place_id", "").strip()
    d["pickup_date"] = request.form.get("pickup_date", "").strip()
    pickup_time = request.form.get("pickup_time", "").strip()
    d["pickup_time"] = pickup_time or None
    paluu_auto_selected = bool(request.form.get("paluu_auto"))
    d["paluu_auto"] = paluu_auto_selected
    if not paluu_auto_selected:
        d["return_delivery_date"] = None
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
        d["dropoff_place_id"] = request.form.get("dropoff_place_id", "").strip()
        saved_phone = (request.form.get("saved_dropoff_phone") or "").strip()
        if saved_phone and not validate_phone_number(saved_phone):
            saved_phone = ""
        d["saved_dropoff_phone"] = saved_phone
        d["last_delivery_date"] = request.form.get("last_delivery_date") or None
        delivery_time = request.form.get("delivery_time", "").strip()
        d["delivery_time"] = delivery_time or None
        paluu_auto_selected = bool(d.get("paluu_auto"))
        if paluu_auto_selected:
            d["return_delivery_date"] = d.get("last_delivery_date") or d.get("pickup_date") or None
        else:
            d["return_delivery_date"] = None
        session["order_draft"] = d
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step1")
        else:
            return redirect("/order/new/step3")

    # GET → esitäyttö draftista
    d = session.get("order_draft", {})
    drop_val = (d.get('dropoff', '') or '').replace('"', '&quot;')
    drop_place_id_val = (d.get('dropoff_place_id', '') or '').replace('"', '&quot;')
    pick_val = (d.get('pickup', '') or '').replace('"', '&quot;')  # piilotettuun from_stepiin
    def _parse_iso_date(value):
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            return None

    pickup_date_obj = _parse_iso_date(d.get("pickup_date")) or datetime.date.today()
    pickup_date_val = pickup_date_obj.isoformat()
    last_delivery_obj = _parse_iso_date(d.get("last_delivery_date")) or pickup_date_obj
    last_delivery_date_val = last_delivery_obj.isoformat()
    delivery_time_val = (d.get("delivery_time") or "").strip()
    saved_phone_val = (d.get('saved_dropoff_phone', '') or '').replace('"', '&quot;')

    inner = """
<h2>Auton toimitus</h2>
<form method='POST' class='calculator-form'>
  <!-- piilotettu nouto, jotta kartta voi piirtyä (from_step löytyy DOMista) -->
  <input type="hidden" id="from_step" value="__PICK_VAL__">
  <input type="hidden" id="pickup_date_step2" value="__PICKUP_DATE_VAL__">
  <input type="hidden" id="saved_dropoff_phone" name="saved_dropoff_phone" value="__SAVED_PHONE_VAL__">
  
  <label class='form-label'>Toimitusosoite *</label>
  <div class="autocomplete">
    <input id="to_step" name="dropoff" required value="__DROP_VAL__" placeholder="Katu, kaupunki" class="form-input">
    <input type="hidden" id="dropoff_place_id" name="dropoff_place_id" value="__DROP_PLACE_ID__">
    <div id="ac_to_step" class="ac-list"></div>
  </div>

  <!-- Date and Time Picker -->
  <div class="wizard-date-grid">
    <div class="wizard-field">
      <label>Toimituspäivä *</label>
      <div class="wizard-input-box" onclick="openDatePicker('last_delivery_date')">
        <div class="wizard-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
        </div>
        <input type="date" id="last_delivery_date" name="last_delivery_date" required value="__LAST_DELIVERY_DATE_VAL__">
      </div>
    </div>
    <div class="wizard-field">
      <label>Toimitusaika (valinnainen)</label>
      <div class="wizard-input-box wizard-input-box--time" onclick="openTimePicker('delivery_time')">
        <div class="wizard-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        </div>
        <input type="time" id="delivery_time" name="delivery_time" value="__DELIVERY_TIME_VAL__">
        <button type="button" id="delivery_time_clear" class="wizard-clear-btn" onclick="clearTimeInput('delivery_time')">×</button>
      </div>
    </div>
  </div>

  
  <!-- Saved Addresses - Compact -->
  <details class="saved-addresses-details" style="margin-top: 36px; padding: 0.5rem 0.75rem; border: 1px solid #e5e7eb; border-radius: 6px; background: #fafafa;">
    <summary style="display: flex; align-items: center; justify-content: space-between; padding: 0.25rem 0; cursor: pointer; font-size: 0.85rem; color: #64748b; list-style: none;">
      <span style="display: flex; align-items: center; gap: 6px;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
        Tallennetut osoitteet
      </span>
      <span style="display: flex; align-items: center; gap: 8px;">
        <button type="button" onclick="event.stopPropagation(); openAddressModal();" class="btn-link" style="font-size: 0.8rem; color: #2563eb; background: none; border: none; cursor: pointer; padding: 0;">+ Lisää</button>
        <svg class="chevron-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </span>
    </summary>
    <div id="savedAddressesList" style="padding: 0.5rem 0;">
      <div id="addressesContainer" style="max-height: 180px; overflow-y: auto;"></div>
    </div>
  </details>
  
  <div class='calculator-actions mt-2' style="margin-top: 16px;">
    <button type='submit' name='action' value='back' class="btn btn-ghost">← Takaisin</button>
    <button type='submit' name='action' value='continue' class="btn btn-primary">Jatka →</button>
  </div>
</form>

<style>
/* Wizard date/time picker styles */
.wizard-date-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.wizard-field label {
  display: block;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 6px;
  font-size: 14px;
}
.wizard-input-box {
  position: relative;
  display: flex;
  align-items: center;
  height: 48px;
  border: 1px solid #22c55e;
  border-radius: 8px;
  background: #fff;
  padding: 0 12px 0 44px;
}
.wizard-input-box:focus-within {
  border-color: #16a34a;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
}
.wizard-icon {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  z-index: 2;
}
.wizard-icon svg { display: block; }
.wizard-input-box--time { padding-right: 44px; }
.wizard-input-box input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 15px;
  color: #1e293b;
  outline: none;
  height: 100%;
  min-width: 0;
  width: 100%;
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
}
.wizard-input-box input[type="date"]::-webkit-date-and-time-value,
.wizard-input-box input[type="time"]::-webkit-date-and-time-value {
  text-align: left;
  margin: 0;
  padding: 0;
}
.wizard-input-box input::-webkit-calendar-picker-indicator {
  opacity: 0;
  cursor: pointer;
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
}
.wizard-clear-btn {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #94a3b8;
  font-size: 18px;
  border: none;
  background: none;
  padding: 0;
  opacity: 0;
  pointer-events: none;
  z-index: 2;
}
.wizard-clear-btn:hover { color: #64748b; }
@media (max-width: 640px) {
  .wizard-date-grid { grid-template-columns: 1fr; }
}
/* Saved addresses compact styling */
.saved-addresses-details summary::-webkit-details-marker { display: none; }
.saved-addresses-details[open] .chevron-icon { transform: rotate(180deg); }
.chevron-icon { transition: transform 0.2s ease; }
.ac-item.saved-address { padding: 0.5rem 0.75rem !important; border-left: 2px solid #2563eb; background: #f8fafc; margin-bottom: 4px; border-radius: 4px; font-size: 0.9rem; }
.ac-item.saved-address:hover { background: #eef2ff; }
.menu-item:hover { background: #f3f4f6; }
.autocomplete { position: relative; }
.ac-list { position: absolute; top: 100%; left: 0; right: 0; z-index: 9999; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 8px 16px rgba(0,0,0,0.06); }
.ac-item { padding: 10px 12px; cursor: pointer; }
.ac-item.active { background: #eef2ff; }
.ac-empty, .ac-error { padding: 10px 12px; }
</style>

<script>
function applySavedPhoneToStep2(phone){
  const hidden = document.getElementById('saved_dropoff_phone');
  if (!hidden) return;
  hidden.value = (phone || '').trim();
}

function openDatePicker(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.showPicker) {
    input.showPicker();
  } else {
    input.focus();
    input.click();
  }
}

function openTimePicker(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.showPicker) {
    input.showPicker();
  } else {
    input.focus();
    input.click();
  }
}

function clearTimeInput(inputId){
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

function toggleClearButton(inputId, buttonId){
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);
  if (!input || !button) return;
  const hasValue = !!input.value;
  button.style.opacity = hasValue ? '1' : '0';
  button.style.pointerEvents = hasValue ? 'auto' : 'none';
}

/* ===== Google Places Autocomplete for Wizard Step 2 ===== */
class WizardGooglePlacesAutocomplete {
  constructor(input, listEl, options = {}){
    this.input = input;
    this.list = listEl;
    this.placeIdInput = options.placeIdInput || null;
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
    this.setPlaceId('');

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
    this.setPlaceId('');
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
    if (this.input && this.input.id === 'to_step') {
      applySavedPhoneToStep2(addr.phone || '');
    }
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

    if (this.input && this.input.id === 'to_step') {
      applySavedPhoneToStep2('');
    }
    this.input.value = item.description;
    this.setPlaceId(item.place_id || '');
    this.hide();
    this.input.dispatchEvent(new Event('change'));
  }

  show(){ this.list.style.display='block'; }
  hide(){ this.list.style.display='none'; }

  setPlaceId(value){
    const val = value || '';
    if (this.placeIdInput) {
      this.placeIdInput.value = val;
    }
    if (this.input) {
      this.input.dataset.placeId = val;
    }
  }
}

/* ===== Saved Addresses (Step 2 page) ===== */
const STORAGE_KEY = 'levoro.savedAddresses.v1';
const LEGACY_STORAGE_KEY = 'savedAddresses';
const COOKIE_KEY = 'levoro_saved_addresses';
window.savedAddresses = [];

async function apiCall(url, options={}){ const res=await fetch(url, options); let data=null; try{ data=await res.json(); }catch{} if(!res.ok) throw new Error((data&&(data.error||data.message))||('HTTP '+res.status)); return data; }
async function fetchServerAddresses(){ const d=await apiCall('/api/saved_addresses',{method:'GET'}); return Array.isArray(d.items)?d.items:[]; }
async function createServerAddress(displayName, fullAddress, phone){ const payload={displayName, fullAddress}; if(phone) payload.phone=phone; const d=await apiCall('/api/saved_addresses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); return d.item; }
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
        ${a.phone ? `<div style="font-size:0.85rem; color:#334155; margin-top:4px;">Puhelin: ${a.phone}</div>` : ''}\
      </div>\
      <button type="button" onclick="deleteAddressDirectly(${i})" class="btn-delete-address" style="border: 2px solid #2563eb; background: white; cursor: pointer; padding: 0.25rem 0.5rem; font-size: 1.25rem; line-height: 1; color: #2563eb; transition: all 0.2s; border-radius: 6px; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;" onmouseover="this.style.background='#2563eb'; this.style.color='white'" onmouseout="this.style.background='white'; this.style.color='#2563eb'" title="Poista">×</button>\
    </div>`).join(''); }
function toggleSavedAddresses(){ const list=document.getElementById('savedAddressesList'); const btn=document.getElementById('toggleAddresses'); if(!list||!btn) return; const show=list.style.display!=='block'; list.style.display=show?'block':'none'; btn.textContent=show?'Piilota tallennetut osoitteet':'Näytä tallennetut osoitteet'; }
function useAddress(id){ const a=(window.savedAddresses||[]).find(x=>String(x.id)===String(id)); if(!a) return; const inp=document.getElementById('to_step'); if(inp){ inp.value=a.fullAddress; inp.dispatchEvent(new Event('change')); } applySavedPhoneToStep2(a.phone||''); }
async function deleteAddressDirectly(index){ const item=(window.savedAddresses||[])[index]; if(!item) return; try{ if(item.id) await deleteServerAddress(item.id);}catch(e){} window.savedAddresses.splice(index,1); saveToStorage(); renderAddresses(); }
function openAddressModal(){
  const html = `<div id="addressModal" style="position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:9999;"><div style="background:white; padding:1.25rem; border-radius:12px; width:90%; max-width:480px;"><h3 style="margin:0 0 1rem 0; font-size:1.1rem; font-weight:600;">Lisää uusi osoite</h3><div style="margin-bottom:0.75rem;"><label style="display:block; margin-bottom:0.25rem;">Nimi *</label><input id="addrName" class="form-input" placeholder="Esim. Koti, Toimisto" style="width:100%;"></div><div style="margin-bottom:1rem;"><label style="display:block; margin-bottom:0.25rem;">Osoite *</label><input id="addrFull" class="form-input" placeholder="Esim. Mannerheimintie 1, Helsinki" style="width:100%;"></div><div style="margin-bottom:0.75rem;"><label style="display:block; margin-bottom:0.25rem;">Puhelinnumero (valinnainen)</label><input id="addrPhone" type="tel" class="form-input" placeholder="+358..." style="width:100%;"></div><div style="display:flex; gap:0.5rem; justify-content:flex-end;"><button type="button" class="btn btn-ghost" onclick="closeAddressModal()">Peruuta</button><button type="button" class="btn btn-primary" onclick="saveAddress()">Tallenna</button></div></div></div>`;
  document.body.insertAdjacentHTML('beforeend', html);
  document.getElementById('addrName').focus();
}
function closeAddressModal(){ const m=document.getElementById('addressModal'); if(m) m.remove(); }
async function saveAddress(){ const name=document.getElementById('addrName').value.trim(); const addr=document.getElementById('addrFull').value.trim(); const phoneInput=document.getElementById('addrPhone'); const phone=phoneInput?phoneInput.value.trim():''; if(!name||!addr){ alert('Täytä molemmat kentät'); return;} if(phone && !/^[+]?[0-9\s\-()]+$/.test(phone)){ alert('Syötä vain numeroita ja merkit +, -, ( )'); return;} let created=null; try{ created=await createServerAddress(name, addr, phone);}catch(e){} const item=created||{ id: Date.now(), displayName:name, fullAddress:addr, phone }; window.savedAddresses.push(item); saveToStorage(); renderAddresses(); closeAddressModal(); }
async function loadSavedAddresses(){ try{ window.savedAddresses=quickLocalLoad(); renderAddresses(); }catch(e){} try{ const server=await fetchServerAddresses(); if(Array.isArray(server)){ window.savedAddresses=server; saveToStorage(); renderAddresses(); } }catch(e){} }

/* Initialize saved addresses + autocomplete for Step 2 */
loadSavedAddresses();
const step2Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('to_step'),
  document.getElementById('ac_to_step'),
  { placeIdInput: document.getElementById('dropoff_place_id') }
);
window.toAutocomplete = step2Autocomplete;
const savedPhoneInputStep2 = document.getElementById('saved_dropoff_phone');
const toStepInput = document.getElementById('to_step');
if (toStepInput && savedPhoneInputStep2) {
  toStepInput.addEventListener('input', () => { savedPhoneInputStep2.value = ''; });
}

/* Date validation for Step 2 */
(function() {
  const pickupDateStep2 = document.getElementById('pickup_date_step2');
  const deliveryDateInput = document.getElementById('last_delivery_date');

  function formatISODate(dateObj) {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function ensureDeliveryDefault() {
    if (!deliveryDateInput) return;
    const today = new Date();
    const todayStr = formatISODate(today);
    const pickupValue = pickupDateStep2 ? pickupDateStep2.value : '';
    const minDate = pickupValue || todayStr;
    deliveryDateInput.min = minDate;
    if (!deliveryDateInput.value || deliveryDateInput.value < minDate) {
      deliveryDateInput.value = minDate;
    }
  }

  if (deliveryDateInput) {
    ensureDeliveryDefault();
    deliveryDateInput.addEventListener('change', ensureDeliveryDefault);
    deliveryDateInput.addEventListener('input', ensureDeliveryDefault);
  }

  const deliveryTimeInput = document.getElementById('delivery_time');
  if (deliveryTimeInput) {
    toggleClearButton('delivery_time', 'delivery_time_clear');
    deliveryTimeInput.addEventListener('input', () => toggleClearButton('delivery_time', 'delivery_time_clear'));
    deliveryTimeInput.addEventListener('change', () => toggleClearButton('delivery_time', 'delivery_time_clear'));
  }
})();
</script>
"""
    inner = (
        inner
        .replace("__DROP_VAL__", drop_val)
        .replace("__DROP_PLACE_ID__", drop_place_id_val)
        .replace("__PICK_VAL__", pick_val)
        .replace("__PICKUP_DATE_VAL__", pickup_date_val)
        .replace("__LAST_DELIVERY_DATE_VAL__", last_delivery_date_val)
        .replace("__DELIVERY_TIME_VAL__", delivery_time_val)
        .replace("__SAVED_PHONE_VAL__", saved_phone_val)
    )
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
        
        # Handle return car details if Paluu auto is checked
        if d.get("paluu_auto"):
            d["return_reg_number"] = request.form.get("return_reg_number","").strip()
            d["return_winter_tires"] = bool(request.form.get("return_winter_tires"))
        else:
            # Clear return car fields if Paluu auto is not checked
            d["return_reg_number"] = None
            d["return_winter_tires"] = False
        
        session["order_draft"] = d
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step2")
        else:
            return redirect("/order/new/step4")
    
    # GET - pre-fill form with existing values
    d = session.get("order_draft", {})
    reg_val = (d.get("reg_number", "") or "").replace('"', '&quot;')
    winter_checked = "checked" if d.get("winter_tires") else ""
    
    # Return car details
    return_reg_val = (d.get("return_reg_number", "") or "").replace('"', '&quot;')
    return_winter_checked = "checked" if d.get("return_winter_tires") else ""
    paluu_auto = d.get("paluu_auto", False)
    return_section_display = "block" if paluu_auto else "none"

    # Check for error message and display it
    error_msg = session.pop("error_message", None)
    error_html = f"<div class='error-message' style='margin-bottom: 1rem; padding: 0.75rem; background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 0.375rem;'>{error_msg}</div>" if error_msg else ""

    inner = f"""
<h2 class='card-title'>Ajoneuvon tiedot</h2>
{error_html}
<form method='POST' class='calculator-form'>
  <div style='padding: 1rem; border: 2px solid #e5e7eb; border-radius: 8px; background: #fafafa; margin-bottom: 1.5rem;'>
    <h3 style='margin: 0 0 1rem 0; font-size: 1.1rem; font-weight: 600; color: #374151;'>Menomatkan ajoneuvo</h3>
    <label class='form-label'>Rekisterinumero *</label>
    <input name='reg_number' required placeholder='ABC-123' class='form-input' value="{reg_val}">
    
    <div class='form-group mt-4'>
      <label class='form-checkbox'>
        <input type='checkbox' name='winter_tires' value='1' {winter_checked}>
        <span class='form-checkbox-label'>Autossa on talvirenkaat</span>
      </label>
    </div>
  </div>
  
  <div id='return_car_section' style='display: {return_section_display}; padding: 1rem; border: 2px solid #dbeafe; border-radius: 8px; background: linear-gradient(to bottom, #eff6ff, #ffffff); margin-bottom: 1.5rem;'>
    <h3 style='margin: 0 0 1rem 0; font-size: 1.1rem; font-weight: 600; color: #1e40af;'>Paluauton tiedot</h3>
    <label class='form-label'>Rekisterinumero (paluauto) *</label>
    <input name='return_reg_number' id='return_reg_number' placeholder='XYZ-456' class='form-input' value="{return_reg_val}" {("required" if paluu_auto else "")}>
    
    <div class='form-group mt-4'>
      <label class='form-checkbox'>
        <input type='checkbox' name='return_winter_tires' value='1' {return_winter_checked}>
        <span class='form-checkbox-label'>Autossa on talvirenkaat (paluauto)</span>
      </label>
    </div>
  </div>
  
  <div class='calculator-actions'>
    <button type='submit' name='action' value='back' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' name='action' value='continue' class='btn btn-primary'>Jatka →</button>
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
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step3")
        else:
            return redirect("/order/new/step5")

    # Get form values from session for pre-filling
    d = session.get("order_draft", {})

    saved_dropoff_phone = (d.get("saved_dropoff_phone") or "").strip()
    user_phone_default = (u.get("phone") or "").strip()

    # Auto-fill orderer basic info from logged-in user if missing
    if not d.get("orderer_name"):
        d["orderer_name"] = u.get("name", "")
    if not d.get("orderer_email"):
        d["orderer_email"] = u.get("email", "")

    # If a saved dropoff phone exists from Step 2, always use it for tilaajan puhelin.
    # This ensures that when you go back and pick another saved address with a phone,
    # the tilaajan phone is updated to match the latest selection.
    if saved_dropoff_phone:
        d["orderer_phone"] = saved_dropoff_phone
    elif not d.get("orderer_phone"):
        # Fallback to account phone only if nothing else is set
        d["orderer_phone"] = user_phone_default

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
    <button type='submit' name='action' value='back' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' name='action' value='continue' class='btn btn-primary'>Jatka →</button>
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
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step4")
        else:
            return redirect("/order/new/confirm")
    
    # GET - pre-fill form with existing values
    d = session.get("order_draft", {})
    additional_info_val = (d.get("additional_info", "") or "").replace('"', '&quot;')
    
    inner = f"""
<h2 class='card-title'>Lisätiedot tai erityistoiveet</h2>
<form method='POST' class='calculator-form'>
  <label class='form-label'>Kirjoita toiveet</label>
  <textarea name='additional_info' rows='5' placeholder='Esim. Autossa on talvirenkaat mukana, toimitus kiireellinen' class='form-input'>{additional_info_val}</textarea>
  <div class='row calculator-actions'>
    <button type='submit' name='action' value='back' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' name='action' value='continue' class='btn btn-primary'>Jatka →</button>
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

    def _parse_iso_date(value: str):
        try:
            if not value:
                return None
            return datetime.datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            return None

    # Calculate outbound km and pricing
    km = 0.0
    err = None
    pricing_error_messages = []
    outbound_route_ok = False
    try:
        km = order_service.route_km(
            d["pickup"],
            d["dropoff"],
            d.get("pickup_place_id", ""),
            d.get("dropoff_place_id", "")
        )
        outbound_route_ok = True
    except Exception as e:
        print(f"Outbound route calculation failed: {e}")
        pricing_error_messages.append(
            "Menomatkan reitin laskenta epäonnistui. Tilausta ei voida vahvistaa juuri nyt. Tarkista osoitteet ja yritä hetken kuluttua uudelleen."
        )

    user_id = None
    is_first_order = False
    if u and u.get("id"):
        try:
            user_id = int(u["id"])
            existing_orders = order_service.get_user_orders(user_id, limit=1)
            is_first_order = len(existing_orders) == 0
        except Exception as e:
            print(f"Failed to check first order status: {e}")
            user_id = int(u["id"])
    time_window = "flex" if not d.get("pickup_date") else "exact"
    return_leg = False
    net = vat = gross = 0.0
    outbound_discount_amount = 0.0
    outbound_applied_discounts: List[Dict] = []
    outbound_applied_discounts_db: List[Dict] = []
    outbound_original_net = 0.0
    pricing_result = None
    if outbound_route_ok:
        pricing_result = order_service.price_from_km_with_discounts(
            km,
            pickup_addr=d.get("pickup"),
            dropoff_addr=d.get("dropoff"),
            return_leg=return_leg,
            user_id=user_id,
            promo_code=d.get("promo_code"),
            is_first_order=is_first_order
        )
        net = pricing_result.get("final_net", 0.0)
        vat = pricing_result.get("final_vat", 0.0)
        gross = pricing_result.get("final_gross", 0.0)
        outbound_discount_amount = pricing_result.get("discount_amount", 0.0)
        outbound_applied_discounts = pricing_result.get("applied_discounts", []) or []
        outbound_applied_discounts_db = pricing_result.get("all_applied_discounts", outbound_applied_discounts)
    outbound_original_net = pricing_result.get("display_original_net", pricing_result.get("original_net", net)) if pricing_result else net
    total_discount_amount = outbound_discount_amount
    total_original_net = outbound_original_net

    # Calculate return leg if Paluu auto is checked
    paluu_auto = d.get("paluu_auto", False)
    return_km = 0.0
    return_net = 0.0
    return_pricing = None
    return_vat = 0.0
    return_gross = 0.0
    return_discount_amount = 0.0
    return_applied_discounts: List[Dict] = []
    return_applied_discounts_db: List[Dict] = []
    return_original_net = 0.0
    total_km = km
    total_net = net
    total_vat = vat
    total_gross = gross
    
    if paluu_auto:
        try:
            # Return trip is reversed: dropoff becomes pickup, pickup becomes dropoff
            return_km = order_service.route_km(
                d["dropoff"],
                d["pickup"],
                d.get("dropoff_place_id", ""),
                d.get("pickup_place_id", "")
            )
            total_km = km + return_km

            # Calculate return pricing (30% discount) only if routing succeeded
            if return_km > 0:
                return_pricing = order_service.price_from_km_with_discounts(
                    return_km,
                    pickup_addr=d.get("dropoff"),
                    dropoff_addr=d.get("pickup"),
                    return_leg=True,
                    user_id=user_id,
                    promo_code=d.get("promo_code"),
                    is_first_order=is_first_order
                )

                return_net = return_pricing.get("final_net", 0.0)
                return_vat = return_pricing.get("final_vat", 0.0)
                return_gross = return_pricing.get("final_gross", 0.0)
                return_discount_amount = return_pricing.get("discount_amount", 0.0)
                return_applied_discounts = return_pricing.get("applied_discounts", []) or []
                return_applied_discounts_db = return_pricing.get("all_applied_discounts", return_applied_discounts)
                return_original_net = return_pricing.get("display_original_net", return_pricing.get("original_net", return_net))

                # Total pricing
                total_net = net + return_net
                total_vat = vat + return_vat
                total_gross = gross + return_gross
                total_discount_amount += return_discount_amount
                total_original_net += return_original_net
            else:
                pricing_error_messages.append(
                    "Paluumatkan reitin laskenta epäonnistui. Tilausta ei voida vahvistaa juuri nyt. Yritä hetken kuluttua uudelleen."
                )
        except Exception as e:
            print(f"Return route calculation failed: {e}")
            pricing_error_messages.append(
                "Paluumatkan reitin laskenta epäonnistui. Tilausta ei voida vahvistaa juuri nyt. Yritä hetken kuluttua uudelleen."
            )

    pickup_date_iso = d.get("pickup_date") or None
    last_delivery_date_iso = d.get("last_delivery_date") or None
    return_delivery_date_iso = d.get("return_delivery_date") or None
    pickup_time_val = (d.get("pickup_time") or "").strip() or None
    delivery_time_val = (d.get("delivery_time") or "").strip() or None
    computed_return_pickup_iso = last_delivery_date_iso or pickup_date_iso

    if request.method == "POST":
        if pricing_error_messages:
            session["error_message"] = " ".join(pricing_error_messages)
            return redirect("/order/new/confirm")
        # Prepare outbound order data
        order_data = {
            "pickup_address": d.get("pickup"),
            "dropoff_address": d.get("dropoff"),
            "pickup_place_id": d.get("pickup_place_id"),
            "dropoff_place_id": d.get("dropoff_place_id"),
            "reg_number": d.get("reg_number"),
            "pickup_date": pickup_date_iso,
            "last_delivery_date": last_delivery_date_iso,
            "pickup_time": pickup_time_val,
            "delivery_time": delivery_time_val,

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
            "discount_amount": float(round(outbound_discount_amount, 2)),
            "applied_discounts": outbound_applied_discounts_db,

            "winter_tires": bool(d.get("winter_tires")) if "winter_tires" in d else False,
            
            # Paluu auto fields
            "trip_type": order_model.TRIP_TYPE_OUTBOUND if paluu_auto else None
        }

        # Create outbound order
        success, order, error = order_service.create_order(int(u["id"]), order_data)

        if success and order:
            outbound_order_id = order['id']
            
            # If Paluu auto is checked, create return order
            if paluu_auto:
                return_order_data = {
                    "pickup_address": d.get("dropoff"),  # Reversed
                    "dropoff_address": d.get("pickup"),  # Reversed
                    "pickup_place_id": d.get("dropoff_place_id"),
                    "dropoff_place_id": d.get("pickup_place_id"),
                    "reg_number": d.get("return_reg_number"),
                    "pickup_date": computed_return_pickup_iso or last_delivery_date_iso or pickup_date_iso,  # Paluuauton nouto tapahtuu viimeisen toimituspäivän kanssa samana päivänä
                    "last_delivery_date": return_delivery_date_iso,

                    # Orderer (Tilaaja) information - same as outbound
                    "orderer_name": d.get("orderer_name"),
                    "orderer_email": d.get("orderer_email"),
                    "orderer_phone": d.get("orderer_phone"),

                    # Customer (Asiakas) information - same as outbound
                    "customer_name": d.get("customer_name"),
                    "customer_phone": d.get("customer_phone"),

                    # Legacy fields
                    "phone": d.get("customer_phone"),
                    "company": d.get("company"),

                    "additional_info": d.get("additional_info"),

                    "distance_km": float(round(return_km, 2)),
                    "price_net": float(return_net),
                    "price_vat": float(return_vat),
                    "price_gross": float(return_gross),
                    "discount_amount": float(round(return_discount_amount, 2)),
                    "applied_discounts": return_applied_discounts_db,

                    "winter_tires": bool(d.get("return_winter_tires")) if "return_winter_tires" in d else False,
                    
                    # Paluu auto fields
                    "trip_type": order_model.TRIP_TYPE_RETURN,
                    "parent_order_id": outbound_order_id,
                    "return_leg": True  # Ensure backend recalculations keep the -30% discount
                }
                
                # Create return order
                return_success, return_order, return_error = order_service.create_order(int(u["id"]), return_order_data)
                
                if return_success and return_order:
                    # Link outbound order to return order
                    from models.database import db_manager
                    db_manager.get_collection("orders").update_one(
                        {"id": outbound_order_id},
                        {"$set": {"return_order_id": return_order['id']}}
                    )
                else:
                    # Return order creation failed - show error but keep outbound order
                    session["error_message"] = f"Paluutilauksen luominen epäonnistui: {return_error or 'Tuntematon virhe'}. Menomatkan tilaus luotiin onnistuneesti (ID: {outbound_order_id})."
                    return redirect(f"/order/{outbound_order_id}")
            
            # Clear session and redirect to outbound order view
            session.pop("order_draft", None)
            return redirect(f"/order/{outbound_order_id}")
        else:
            # Handle error case
            session["error_message"] = f"Tilauksen luominen epäonnistui: {error or 'Tuntematon virhe'}"
            # Stay on confirmation page to show error
            pass

    err = " ".join(pricing_error_messages) if pricing_error_messages else None

    # Check for error message in session
    error_msg = session.pop("error_message", None)
    error_html = f"<div class='alert alert-error' style='margin-bottom: 1rem; padding: 1rem; background: #fee; border: 1px solid #fcc; border-radius: 4px; color: #c00;'>{error_msg}</div>" if error_msg else ""

    # Format dates for display under addresses
    def _fmt_date(s: str):
        try:
            if not s:
                return None
            dt = datetime.datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%d.%m")
        except Exception:
            return s

    pickup_date_str = _fmt_date(pickup_date_iso)
    last_delivery_date_str = _fmt_date(last_delivery_date_iso)
    return_delivery_date_str = _fmt_date(return_delivery_date_iso)
    return_pickup_str = _fmt_date(computed_return_pickup_iso)

    date_fallback = "Ei asetettu"
    pickup_date_display = pickup_date_str or date_fallback
    delivery_date_display = last_delivery_date_str or date_fallback
    if pickup_time_val and pickup_date_str:
        pickup_date_display = f"{pickup_date_str} klo {pickup_time_val}"
    if delivery_time_val and last_delivery_date_str:
        delivery_date_display = f"{last_delivery_date_str} klo {delivery_time_val}"

    return_pickup_display = return_pickup_str or date_fallback
    return_delivery_display = return_delivery_date_str or date_fallback

    pickup_address = d.get("pickup") or ""
    dropoff_address = d.get("dropoff") or ""

    # Build simple, clean outbound section
    meno_section_html = f"""
<div class='trip-card trip-card--outbound'>
  <div class='trip-card__header'>
    <span class='trip-card__title'>Menomatka</span>
    <span class='trip-card__distance'>{km:.1f} km</span>
  </div>
  <div class='trip-card__route'>
    <div class='route-point route-point--start'>
      <div class='route-point__marker'></div>
      <div class='route-point__content'>
        <span class='route-point__label'>Nouto</span>
        <span class='route-point__address'>{pickup_address}</span>
        {f"<span class='route-point__date'>{pickup_date_display}</span>" if pickup_date_str else ""}
      </div>
    </div>
    <div class='route-line'></div>
    <div class='route-point route-point--end'>
      <div class='route-point__marker'></div>
      <div class='route-point__content'>
        <span class='route-point__label'>Toimitus</span>
        <span class='route-point__address'>{dropoff_address}</span>
        {f"<span class='route-point__date'>{delivery_date_display}</span>" if last_delivery_date_str else ""}
      </div>
    </div>
  </div>
  <div class='trip-card__footer'>
    <div class='trip-meta'>
      <span class='trip-meta__label'>Rekisterinumero</span>
      <span class='trip-meta__value'>{d.get('reg_number')}</span>
    </div>
    <div class='trip-meta'>
      <span class='trip-meta__label'>Talvirenkaat</span>
      <span class='trip-meta__value'>{"Kyllä" if d.get('winter_tires') else "Ei"}</span>
    </div>
  </div>
</div>
"""

    paluu_section_html = ""
    if paluu_auto:
        paluu_section_html = f"""
<div class='trip-card trip-card--return'>
  <div class='trip-card__header'>
    <span class='trip-card__title'>Paluumatka</span>
    <div class='trip-card__header-right'>
      <span class='trip-card__discount'>-30%</span>
      <span class='trip-card__distance'>{return_km:.1f} km</span>
    </div>
  </div>
  <div class='trip-card__route'>
    <div class='route-point route-point--start'>
      <div class='route-point__marker'></div>
      <div class='route-point__content'>
        <span class='route-point__label'>Nouto</span>
        <span class='route-point__address'>{dropoff_address}</span>
        {f"<span class='route-point__date'>{return_pickup_display}</span>" if return_pickup_str else ""}
      </div>
    </div>
    <div class='route-line'></div>
    <div class='route-point route-point--end'>
      <div class='route-point__marker'></div>
      <div class='route-point__content'>
        <span class='route-point__label'>Toimitus</span>
        <span class='route-point__address'>{pickup_address}</span>
        <span class='route-point__date'>{return_delivery_display}</span>
      </div>
    </div>
  </div>
  <div class='trip-card__footer'>
    <div class='trip-meta'>
      <span class='trip-meta__label'>Rekisterinumero</span>
      <span class='trip-meta__value'>{d.get('return_reg_number') or 'Ei asetettu'}</span>
    </div>
    <div class='trip-meta'>
      <span class='trip-meta__label'>Talvirenkaat</span>
      <span class='trip-meta__value'>{"Kyllä" if d.get('return_winter_tires') else "Ei"}</span>
    </div>
  </div>
</div>
"""

    customer_name = (d.get("customer_name") or "").strip()
    customer_phone = (d.get("customer_phone") or "").strip()
    company_name = (d.get("company") or "").strip()
    additional_info_text = (d.get("additional_info") or "").strip()

    # Build contact info section
    contact_section_html = f"""
<div class='contact-section'>
  <h3 class='section-title'>Yhteystiedot</h3>
  <div class='contact-grid'>
    <div class='contact-item'>
      <div class='contact-label'>Tilaaja</div>
      <div class='contact-name'>{d.get('orderer_name')}</div>
      <div class='contact-details'>{d.get('orderer_email')}</div>
      <div class='contact-details'>{d.get('orderer_phone')}</div>
    </div>
"""
    
    if customer_name or company_name or customer_phone:
        contact_section_html += f"""
    <div class='contact-item'>
      <div class='contact-label'>Asiakas</div>
      {f"<div class='contact-name'>{customer_name}</div>" if customer_name else ""}
      {f"<div class='contact-details'>{company_name}</div>" if company_name else ""}
      {f"<div class='contact-details'>{customer_phone}</div>" if customer_phone else ""}
    </div>
"""
    
    contact_section_html += """  </div>
</div>
"""

    additional_info_html = ""
    if additional_info_text:
        safe_additional = additional_info_text.replace('<','&lt;').replace('\n','<br>')
        additional_info_html = f"""
<div class='additional-info-section'>
  <h3 class='section-title'>Lisätiedot</h3>
  <div class='additional-info-content'>{safe_additional}</div>
</div>
"""


    leg_sections_html = f"{meno_section_html}{paluu_section_html}{contact_section_html}{additional_info_html}"

    # Build pricing summary with discount breakdown
    def _format_price_parts(current_value: float, original_value: float):
        current = f"{current_value:.2f} €"
        original = None
        if original_value and original_value - current_value > 0.009:
            original = f"{original_value:.2f} €"
        return current, original

    outbound_price_display, outbound_price_original = _format_price_parts(net, outbound_original_net)
    return_price_display, return_price_original = _format_price_parts(return_net, return_original_net)
    total_price_display, total_price_original = _format_price_parts(total_net, total_original_net)

    discount_sections = []
    if outbound_discount_amount > 0:
        discount_sections.append(("Menomatka", outbound_applied_discounts, outbound_discount_amount))
    if return_discount_amount > 0:
        discount_sections.append(("Paluumatka", return_applied_discounts, return_discount_amount))

    discount_html = ""
    if discount_sections:
        section_markup = []
        for title, discounts, section_total in discount_sections:
            rows = []
            if discounts:
                for disc in discounts:
                    amount = float(disc.get("amount", 0.0) or 0.0)
                    if amount <= 0:
                        continue
                    disc_name = disc.get("name") or "Alennus"
                    rows.append(
                        "<div style='display: flex; justify-content: space-between; font-size: 0.9rem; margin-top: 0.4rem;'>"
                        f"<span style='color: #166534;'>{disc_name}</span>"
                        f"<span style='color: #15803d; font-weight: 600;'>-{amount:.2f} €</span>"
                        "</div>"
                    )
            if not rows:
                rows.append("<div style='font-size: 0.9rem; color: #94a3b8; margin-top: 0.4rem;'>Ei erillisiä alennuksia</div>")
            rows.append(
                "<div style='display: flex; justify-content: space-between; font-size: 0.9rem; margin-top: 0.4rem; font-weight: 600;'>"
                "<span style='color: #166534;'>Yhteensä</span>"
                f"<span style='color: #15803d;'>-{section_total:.2f} €</span>"
                "</div>"
            )
            section_markup.append(
                "<div style='margin-top: 0.75rem;'>"
                f"<div style='font-weight: 700; color: #065f46; text-transform: uppercase; font-size: 0.8rem;'>{title}</div>"
                f"{''.join(rows)}"
                "</div>"
            )

        discount_html = (
            "<div style='margin-top: 1.25rem; padding: 1.1rem; background: #ecfdf5; border: 1px solid #d1fae5; border-radius: 14px;'>"
            "<div style='display: flex; justify-content: space-between; font-weight: 700; color: #065f46; font-size: 1rem;'>"
            "<span>Säästät yhteensä</span>"
            f"<span>-{total_discount_amount:.2f} €</span>"
            "</div>"
            f"{''.join(section_markup)}"
            "</div>"
        )

    def _build_leg_row(label: str, distance_value: float, current_price: str, original_price: str | None) -> str:
        original_html = (
            f"<div style='font-size: 0.85rem; color: #94a3b8; text-decoration: line-through;'>{original_price}</div>"
            if original_price else ""
        )
        return (
            "<div style='display: flex; justify-content: space-between; align-items: center; padding: 0.85rem 0; border-bottom: 1px solid #e2e8f0;'>"
            "<div>"
            f"<div style='font-weight: 600; color: #0f172a;'>{label}</div>"
            f"<div style='font-size: 0.85rem; color: #64748b;'>{distance_value:.1f} km</div>"
            "</div>"
            "<div style='text-align: right;'>"
            f"<div style='font-weight: 700; color: #0f172a;'>{current_price}</div>"
            f"{original_html}"
            "</div>"
            "</div>"
        )

    leg_rows = []
    leg_rows.append(_build_leg_row("Menomatka" if paluu_auto else "Matka", km, outbound_price_display, outbound_price_original))
    if paluu_auto:
        leg_rows.append(_build_leg_row("Paluumatka", return_km, return_price_display, return_price_original))
    legs_html = "".join(leg_rows)

    total_original_block = ""
    if total_price_original:
        total_original_block = (
            f"<div style='font-size: 1rem; color: #94a3b8; text-decoration: line-through; margin-top: -0.2rem;'>{total_price_original}</div>"
        )

    total_section = (
        "<div style='text-align: center; margin: 1.25rem 0 1.5rem;'>"
        f"<div style='display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.35rem 0.95rem; border-radius: 999px; font-size: 0.95rem; font-weight: 600; background: #eff6ff; color: #1d4ed8;'>{total_km:.1f} km yhteensä</div>"
        f"<div style='font-size: 3rem; font-weight: 800; color: #0f172a; line-height: 1; margin-top: 0.75rem;'>{total_net:.2f} €</div>"
        f"{total_original_block}"
        f"<div style='font-size: 0.95rem; color: #475569; margin-top: 0.5rem;'>ALV 25,5%: {total_vat:.2f} € • Sis. ALV: {total_gross:.2f} €</div>"
        "</div>"
    )

    error_block = (
        f"<div style='margin-top: 1rem; padding: 0.75rem; background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 10px; font-size: 0.9rem;'>{err}</div>"
        if err else ""
    )

    pricing_html = f"""
<div class='price-card' style='background: #ffffff; border: 1px solid #e2e8f0; border-radius: 20px; padding: 24px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); text-align: left;'>
  <div style='text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.85rem; color: #94a3b8; font-weight: 700;'>Yhteenveto</div>
  <div style='border: 1px solid #e2e8f0; border-radius: 16px; background: #f8fafc; padding: 0.25rem 1.1rem;'>
    {legs_html}
  </div>
  {total_section}
  {discount_html}
  {error_block}
</div>
"""
    disable_submission = bool(pricing_error_messages)
    submit_disabled_attr = "disabled" if disable_submission else ""
    submit_disabled_helper = f"<p class='muted' style='margin-top: 0.75rem; color: #dc2626;'>Hinnanlaskenta epäonnistui, joten tilausta ei voi lähettää. Yritä myöhemmin uudelleen.</p>" if disable_submission else ""

    inner = f"""
<h2 class='card-title'>Vahvista tilaus</h2>
{error_html}
<div class='confirmation-modern-layout'>
  <div class='confirmation-main'>
    {leg_sections_html}
  </div>
  <div class='confirmation-sidebar'>
    <div class='map-wrapper'>
      <h3 class='sidebar-title'>Reitti</h3>
      <div id='confirmation_map' class='confirmation-map'></div>
    </div>
    {pricing_html}
  </div>
</div>
<form method='POST' class='calculator-form' id='orderConfirmForm'>
  <div class='terms-checkbox-wrapper' style='margin-top: 1.5rem; padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;'>
    <label class='terms-checkbox-label' style='display: flex; align-items: flex-start; gap: 0.75rem; cursor: pointer;'>
      <input type='checkbox' id='termsCheckbox' required style='width: 20px; height: 20px; margin-top: 2px; accent-color: #3b82f6; cursor: pointer;'>
      <span style='font-size: 0.9rem; color: #475569; line-height: 1.5;'>
        Hyväksyn <a href='/ehdot' target='_blank' style='color: #3b82f6; text-decoration: underline;'>käyttöehdot</a> ja 
        <a href='/tietosuoja' target='_blank' style='color: #3b82f6; text-decoration: underline;'>tietosuojakäytännön</a>. 
        Ymmärrän, että tilaus on sitova vahvistuksen jälkeen.
      </span>
    </label>
  </div>
  <div class='calculator-actions' style='margin-top: 1.5rem;'>
    <button type='button' onclick='window.location.href="/order/new/step5"' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' class='btn btn-primary btn-large' id='submitOrderBtn' {submit_disabled_attr}>
      <span class='btn-text'>Vahvista ja lähetä tilaus</span>
      <span class='btn-spinner' style='display: none;'>
        <svg class='spinner-icon' viewBox='0 0 24 24' width='20' height='20'>
          <circle cx='12' cy='12' r='10' stroke='currentColor' stroke-width='3' fill='none' stroke-dasharray='31.4 31.4' stroke-linecap='round'>
            <animateTransform attributeName='transform' type='rotate' from='0 12 12' to='360 12 12' dur='0.8s' repeatCount='indefinite'/>
          </circle>
        </svg>
        Lähetetään...
      </span>
    </button>
  </div>
  {submit_disabled_helper}
</form>

<script>
document.addEventListener('DOMContentLoaded', function() {{
  const form = document.getElementById('orderConfirmForm');
  const submitBtn = document.getElementById('submitOrderBtn');
  const termsCheckbox = document.getElementById('termsCheckbox');
  
  if (form && submitBtn) {{
    form.addEventListener('submit', function(e) {{
      if (!termsCheckbox.checked) {{
        e.preventDefault();
        termsCheckbox.focus();
        return;
      }}
      
      // Show loading state
      submitBtn.disabled = true;
      submitBtn.querySelector('.btn-text').style.display = 'none';
      submitBtn.querySelector('.btn-spinner').style.display = 'inline-flex';
    }});
  }}
}});
</script>

<style>
.btn-spinner {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}}
.spinner-icon {{
  animation: spin 0.8s linear infinite;
}}
@keyframes spin {{
  from {{ transform: rotate(0deg); }}
  to {{ transform: rotate(360deg); }}
}}
</style>

<!-- Leaflet CSS and JS for map -->
<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css' crossorigin='' />
<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js' crossorigin=''></script>

<style>
/* Modern two-column layout */
.confirmation-modern-layout {{
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 2rem;
  margin-top: 1.5rem;
}}

.confirmation-main {{
  min-width: 0;
}}

.confirmation-sidebar {{
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}}

/* Trip card styling - Clean professional design */
.trip-card {{
  background: #fff;
  border-radius: 12px;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  overflow: hidden;
  border: 1px solid #e5e7eb;
}}

.trip-card--outbound {{
  border-color: #3b82f6;
}}

.trip-card--return {{
  border-color: #f59e0b;
}}

.trip-card__header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}}

.trip-card__title {{
  font-size: 0.95rem;
  font-weight: 600;
  color: #1e293b;
  letter-spacing: -0.01em;
}}

.trip-card__header-right {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
}}

.trip-card__distance {{
  font-size: 0.85rem;
  color: #64748b;
  font-weight: 500;
}}

.trip-card__discount {{
  background: #fef3c7;
  color: #d97706;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
}}

.trip-card__route {{
  padding: 1.25rem;
  position: relative;
}}

.route-point {{
  display: flex;
  gap: 1rem;
  position: relative;
  z-index: 1;
}}

.route-point--start {{
  margin-bottom: 0.5rem;
}}

.route-point--end {{
  margin-top: 0.5rem;
}}

.route-point__marker {{
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #3b82f6;
  margin-top: 4px;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}}

.trip-card--return .route-point__marker {{
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}}

.route-point--end .route-point__marker {{
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}}

.route-point__content {{
  flex: 1;
  min-width: 0;
}}

.route-point__label {{
  display: block;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  font-weight: 600;
  margin-bottom: 0.2rem;
}}

.route-point__address {{
  display: block;
  font-size: 0.9rem;
  color: #1e293b;
  font-weight: 500;
  line-height: 1.4;
}}

.route-point__date {{
  display: block;
  font-size: 0.8rem;
  color: #64748b;
  margin-top: 0.2rem;
}}

.route-line {{
  position: absolute;
  left: 1.25rem;
  top: 2.5rem;
  bottom: 2.5rem;
  width: 12px;
  display: flex;
  justify-content: center;
}}

.route-line::before {{
  content: '';
  width: 2px;
  height: 100%;
  background: linear-gradient(to bottom, #3b82f6, #10b981);
  border-radius: 1px;
}}

.trip-card--return .route-line::before {{
  background: linear-gradient(to bottom, #f59e0b, #10b981);
}}

.trip-card__footer {{
  display: flex;
  gap: 1.5rem;
  padding: 0.875rem 1.25rem;
  background: #fafafa;
  border-top: 1px solid #f1f5f9;
}}

.trip-meta {{
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}}

.trip-meta__label {{
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  font-weight: 600;
}}

.trip-meta__value {{
  font-size: 0.875rem;
  color: #1e293b;
  font-weight: 600;
}}

/* Legacy support - keeping old class names working */
.trip-section {{
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  padding: 0;
  margin-bottom: 1.5rem;
  overflow: hidden;
}}

.trip-section--return {{
  border-color: #fbbf24;
}}

.trip-header {{
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  padding: 1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

.trip-section--return .trip-header {{
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}}

.trip-badge {{
  color: white;
  font-weight: 700;
  font-size: 0.9rem;
  letter-spacing: 0.5px;
}}

.discount-badge {{
  background: rgba(255,255,255,0.25);
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
}}

.trip-details {{
  padding: 1.5rem;
}}

.detail-row {{
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}}

.detail-icon {{
  font-size: 1.5rem;
  line-height: 1;
  margin-top: 0.15rem;
}}

.detail-content {{
  flex: 1;
}}

.detail-label {{
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #64748b;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-bottom: 0.35rem;
}}

.detail-value {{
  font-size: 1rem;
  color: #1e293b;
  font-weight: 500;
  line-height: 1.4;
}}

.detail-meta {{
  font-size: 0.875rem;
  color: #64748b;
  margin-top: 0.25rem;
}}

.route-arrow {{
  text-align: center;
  color: #cbd5e1;
  font-size: 1.5rem;
  margin: 0.75rem 0;
  font-weight: 300;
}}

.detail-separator {{
  height: 1px;
  background: #e5e7eb;
  margin: 1.25rem 0;
}}

.detail-row-compact {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}}

.compact-item {{
  text-align: center;
}}

.compact-label {{
  font-size: 0.7rem;
  text-transform: uppercase;
  color: #94a3b8;
  font-weight: 600;
  letter-spacing: 0.3px;
  margin-bottom: 0.35rem;
}}

.compact-value {{
  font-size: 0.95rem;
  color: #1e293b;
  font-weight: 600;
}}

/* Contact section */
.contact-section,
.additional-info-section {{
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}}

.section-title {{
  font-size: 1rem;
  font-weight: 700;
  color: #334155;
  margin: 0 0 1rem 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-size: 0.85rem;
}}

.contact-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}}

.contact-item {{
  
}}

.contact-label {{
  font-size: 0.7rem;
  text-transform: uppercase;
  color: #64748b;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-bottom: 0.5rem;
}}

.contact-name {{
  font-size: 1rem;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 0.25rem;
}}

.contact-details {{
  font-size: 0.9rem;
  color: #475569;
  line-height: 1.6;
}}

.additional-info-content {{
  font-size: 0.95rem;
  color: #475569;
  line-height: 1.7;
  white-space: pre-wrap;
}}

/* Sidebar elements */
.map-wrapper {{
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 1rem;
}}

.sidebar-title {{
  font-size: 0.85rem;
  font-weight: 700;
  color: #334155;
  margin: 0 0 0.75rem 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}

.confirmation-map {{
  height: 250px;
  border-radius: 8px;
  overflow: hidden;
}}

.price-summary {{
  position: sticky;
  top: 1rem;
}}

.price-card {{
  background: linear-gradient(135deg, #f8fafc 0%, #fff 100%);
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  padding: 1.5rem;
}}

.price-title {{
  font-size: 0.85rem;
  font-weight: 700;
  color: #334155;
  margin: 0 0 1rem 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}

.price-details {{
  text-align: center;
}}

.distance {{
  display: inline-block;
  background: #eff6ff;
  color: #2563eb;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 1rem;
}}

.btn-large {{
  padding: 0.875rem 2rem;
  font-size: 1.05rem;
  font-weight: 600;
}}

/* Distance label on map */
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
}}

@media (max-width: 1024px) {{
  .confirmation-modern-layout {{
    grid-template-columns: 1fr;
  }}
  
  .confirmation-sidebar {{
    order: -1;
  }}
  
  .price-summary {{
    position: static;
  }}
  
  .detail-row-compact {{
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }}
  
  .compact-item {{
    text-align: left;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid #f1f5f9;
  }}
  
  .compact-item:last-child {{
    border-bottom: none;
  }}
}}

@media (max-width: 640px) {{
  .contact-grid {{
    grid-template-columns: 1fr;
  }}
  
  .confirmation-map {{
    height: 200px;
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
  const pickupPlaceId = '{d.get("pickup_place_id") or ""}';
  const dropoffPlaceId = '{d.get("dropoff_place_id") or ""}';

  fetch('/api/route_geo', {{
    method: 'POST',
    headers: {{
      'Content-Type': 'application/json'
    }},
    body: JSON.stringify({{ pickup: pickup, dropoff: dropoff, pickup_place_id: pickupPlaceId, dropoff_place_id: dropoffPlaceId }})
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
