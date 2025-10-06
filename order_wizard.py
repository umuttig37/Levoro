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
    # Check for both orderer and customer required fields
    if (session_data.get("orderer_name") and session_data.get("orderer_email") and session_data.get("orderer_phone") and
        session_data.get("customer_name") and session_data.get("customer_phone")):
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
  <label>Toivottu noutopäivä</label>
    <div class="date-left">
      <input type="date" name="pickup_date" id="pickup_date" aria-label="Valitse noutopäivä">
    </div>
  <div class='calculator-actions mt-2'>
    <button type='submit' class="btn btn-primary" aria-label="Jatka seuraavaan vaiheeseen">Jatka →</button>
  </div>
</form>

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
    input.addEventListener('keydown', (e)=> this.onKey(e));
    document.addEventListener('click', (e)=>{ if(!this.list.contains(e.target) && e.target!==this.input){ this.hide() }});

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

/* Initialize for Step 1 */
const step1Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('from_step'),
  document.getElementById('ac_from_step')
);
</script>
"""
        inner = inner.replace("__PICKUP_VAL__", pickup_val)
        return get_wrap()(wizard_shell(1, inner, session.get("order_draft", {})), u)

    # POST → talteen ja seuraavaan steppiin
    d = session.get("order_draft", {})
    d["pickup"] = request.form.get("pickup", "").strip()
    d["pickup_date"] = request.form.get("pickup_date", "").strip()
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
        session["order_draft"] = d
        return redirect("/order/new/step3")

    # GET → esitäyttö draftista
    d = session.get("order_draft", {})
    drop_val = (d.get('dropoff', '') or '').replace('"', '&quot;')
    pick_val = (d.get('pickup', '') or '').replace('"', '&quot;')  # piilotettuun from_stepiin

    inner = """
<h2>Auton toimitus</h2>
<form method='POST' class='calculator-form'>
  <!-- piilotettu nouto, jotta kartta voi piirtyä (from_step löytyy DOMista) -->
  <input type="hidden" id="from_step" value="__PICK_VAL__">
  <label class='form-label'>Toimitusosoite *</label>
  <div class="autocomplete">
    <input id="to_step" name="dropoff" required value="__DROP_VAL__" placeholder="Katu, kaupunki" class="form-input">
    <div id="ac_to_step" class="ac-list"></div>
  </div>
  <div class='calculator-actions mt-2'>
    <button type='button' onclick='window.location.href="/order/new/step1"' class="btn btn-ghost">← Takaisin</button>
    <button type='submit' class="btn btn-primary">Jatka →</button>
  </div>
</form>

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

/* Initialize autocomplete for Step 2 */
const step2Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('to_step'),
  document.getElementById('ac_to_step')
);
</script>
"""
    inner = inner.replace("__DROP_VAL__", drop_val).replace("__PICK_VAL__", pick_val)
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
        
        if not validate_phone_number(d["customer_phone"]):
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
    <input type='tel' name='orderer_phone' required class='form-input' value="{orderer_phone_val}" placeholder="+358..." pattern="[+]?[0-9\s\-()]+" title="Käytä vain numeroita ja merkkejä +, -, ( )" aria-label="Tilaajan puhelinnumero">
  </div>

  <!-- Customer Section -->
  <div style='background: #fefce8; padding: 1.25rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px solid #fde047;'>
    <h3 style='margin-top: 0; margin-bottom: 1rem; color: #854d0e; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;'>
      Asiakkaan tiedot
    </h3>
    <label class='form-label'>Asiakkaan nimi *</label>
    <input name='customer_name' required class='form-input' value="{customer_name_val}" placeholder="Vastaanottajan nimi">
    <label class='form-label'>Asiakkaan puhelinnumero *</label>
    <input type='tel' name='customer_phone' required class='form-input' value="{customer_phone_val}" placeholder="+358..." pattern="[+]?[0-9\s\-()]+" title="Käytä vain numeroita ja merkkejä +, -, ( )" aria-label="Asiakkaan puhelinnumero">
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
    const phonePattern = /^[+]?[0-9\s\-()]+$/;
    
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
                "orderer_name","orderer_email","orderer_phone",
                "customer_name","customer_phone"]

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
        elif any(field in missing_fields for field in ["orderer_name", "orderer_email", "orderer_phone",
                                                        "customer_name", "customer_phone"]):
            missing_contact_fields = [f for f in ["orderer_name", "orderer_email", "orderer_phone",
                                                   "customer_name", "customer_phone"] if f in missing_fields]
            field_names = {
                "orderer_name": "tilaajan nimi", "orderer_email": "tilaajan sähköposti", "orderer_phone": "tilaajan puhelinnumero",
                "customer_name": "asiakkaan nimi", "customer_phone": "asiakkaan puhelinnumero"
            }
            missing_names = [field_names[f] for f in missing_contact_fields]
            session["error_message"] = f"Yhteystiedot puuttuvat: {', '.join(missing_names)}. Täytä puuttuvat tiedot."
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

    inner = f"""
<h2 class='card-title'>Vahvista tilaus</h2>
{error_html}
<div class='confirmation-layout'>
  <div class='confirmation-grid'>
    <div class='confirmation-card'><h3 class='confirmation-title'>Nouto</h3><p class='confirmation-text'>{d.get('pickup')}</p><p class='confirmation-meta'>{d.get('pickup_date') or 'Heti'}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Toimitus</h3><p class='confirmation-text'>{d.get('dropoff')}</p></div>
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
    <button type='submit' class='btn btn-primary'>Lähetä tilaus ✓</button>
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
