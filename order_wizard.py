# order_wizard.py
import datetime
from flask import request, redirect, url_for, session
from app import app, wrap, price_from_km, route_km, current_user, next_id, orders_col

def get_accessible_steps(session_data):
    """Determine which steps user can navigate to based on completed data"""
    accessible = [1]  # Step 1 always accessible

    if session_data.get("pickup"):
        accessible.append(2)
    if session_data.get("dropoff"):
        accessible.append(3)
    if session_data.get("reg_number"):
        accessible.append(4)
    if session_data.get("customer_name") and session_data.get("email") and session_data.get("phone"):
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
    u = current_user()
    if not u:
        return redirect(url_for("login", next="/order/new/step1"))

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
      <input type="date" name="pickup_date" id="pickup_date">
    </div>
  <div class='calculator-actions mt-2'>
    <button type='submit' class="btn btn-primary">Jatka →</button>
  </div>
</form>
<style>
  /* tee päivämääräkentästä kapea ja vasempaan */
  .date-left{ max-width:260px; }
  .date-left input[type="date"]{ width:100%; }

  /* valinnainen: siirrä kalenteri-ikoni vasemmalle (Chromium/Safari) */
  .date-left{ position:relative; }
  .date-left input[type="date"]{ padding-left:40px; }
  .date-left input[type="date"]::-webkit-calendar-picker-indicator{
    position:absolute; left:10px; right:auto; opacity:1; cursor:pointer;
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

/* Initialize for Step 1 */
const step1Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('from_step'),
  document.getElementById('ac_from_step')
);
</script>
"""
        inner = inner.replace("__PICKUP_VAL__", pickup_val)
        return wrap(wizard_shell(1, inner, session.get("order_draft", {})), u)

    # POST → talteen ja seuraavaan steppiin
    d = session.get("order_draft", {})
    d["pickup"] = request.form.get("pickup", "").strip()
    d["pickup_date"] = request.form.get("pickup_date", "").strip()
    session["order_draft"] = d
    return redirect("/order/new/step2")



# STEP 2: Delivery
@app.route("/order/new/step2", methods=["GET","POST"])
def order_step2():
    u = current_user()
    if not u:
        return redirect(url_for("login", next="/order/new/step2"))

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

/* Initialize autocomplete for Step 2 */
const step2Autocomplete = new WizardGooglePlacesAutocomplete(
  document.getElementById('to_step'),
  document.getElementById('ac_to_step')
);
</script>
"""
    inner = inner.replace("__DROP_VAL__", drop_val).replace("__PICK_VAL__", pick_val)
    return wrap(wizard_shell(2, inner, session.get("order_draft", {})), u)



# STEP 3: Vehicle
@app.route("/order/new/step3", methods=["GET","POST"])
def order_step3():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/step3"))

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
    return wrap(wizard_shell(3, inner, session.get("order_draft", {})), u)

# STEP 4: Contact
@app.route("/order/new/step4", methods=["GET","POST"])
def order_step4():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/step4"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(4, session_data)
    if access_check:
        return access_check
    if request.method == "POST":
        d = session.get("order_draft", {})
        d["customer_name"] = request.form.get("customer_name","").strip()
        d["company"] = request.form.get("company","").strip()
        d["email"] = request.form.get("email","").strip()
        d["phone"] = request.form.get("phone","").strip()
        session["order_draft"] = d
        return redirect("/order/new/step5")

    # Get form values from session for pre-filling
    d = session.get("order_draft", {})
    customer_name_val = (d.get("customer_name", "") or "").replace('"', '&quot;')
    company_val = (d.get("company", "") or "").replace('"', '&quot;')
    email_val = (d.get("email", "") or "").replace('"', '&quot;')
    phone_val = (d.get("phone", "") or "").replace('"', '&quot;')

    # Check for error message and display it
    error_msg = session.pop("error_message", None)
    error_html = f"<div class='error-message' style='margin-bottom: 1rem; padding: 0.75rem; background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 0.375rem;'>{error_msg}</div>" if error_msg else ""

    inner = f"""
<h2 class='card-title'>Yhteystiedot</h2>
{error_html}
<form method='POST' class='calculator-form'>
  <label class='form-label'>Nimi *</label>
  <input name='customer_name' required class='form-input' value="{customer_name_val}">
  <label class='form-label'>Yritys</label>
  <input name='company' class='form-input' value="{company_val}">
  <label class='form-label'>Sähköposti *</label>
  <input type='email' name='email' required class='form-input' value="{email_val}">
  <label class='form-label'>Puhelin *</label>
  <input name='phone' required class='form-input' value="{phone_val}">
  <div class='row calculator-actions'>
    <button type='button' onclick='window.location.href="/order/new/step3"' class='btn btn-ghost'>← Takaisin</button>
    <button type='submit' class='btn btn-primary'>Jatka →</button>
  </div>
</form>"""
    return wrap(wizard_shell(4, inner, session.get("order_draft", {})), u)

# STEP 5: Notes
@app.route("/order/new/step5", methods=["GET","POST"])
def order_step5():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/step5"))

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
    return wrap(wizard_shell(5, inner, session.get("order_draft", {})), u)

# STEP 6: Confirm
@app.route("/order/new/confirm", methods=["GET","POST"])
def order_confirm():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/confirm"))

    # Validate step access
    session_data = session.get("order_draft", {})
    access_check = validate_step_access(6, session_data)
    if access_check:
        return access_check
    d = session.get("order_draft", {})
    required = ["pickup","dropoff","reg_number","customer_name","email","phone"]

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
        elif any(field in missing_fields for field in ["customer_name", "email", "phone"]):
            missing_contact_fields = [f for f in ["customer_name", "email", "phone"] if f in missing_fields]
            field_names = {"customer_name": "nimi", "email": "sähköposti", "phone": "puhelinnumero"};
            missing_names = [field_names[f] for f in missing_contact_fields];
            session["error_message"] = f"Yhteystiedot puuttuvat: {', '.join(missing_names)}. Täytä puuttuvat tiedot."
            return redirect("/order/new/step4")

    km = 0.0
    err = None
    try:
        km = route_km(d["pickup"], d["dropoff"])
    except Exception as e:
        err = f"Hinnanlaskenta epäonnistui: {e}"
    u = current_user()
    # esim. otetaan joustava nouto jos käyttäjä EI antanut noutopäivää:
    time_window = "flex" if not d.get("pickup_date") else "exact"
    return_leg = False  # if you later add a checkbox for round-trip, set True accordingly
    net, vat, gross, _ = price_from_km(
        km,
        pickup_addr=d.get("pickup"),
        dropoff_addr=d.get("dropoff"),
        return_leg=return_leg
    )

    if request.method == "POST":
        oid = next_id("orders")

        doc = {
            "id": oid,
            "user_id": int(u["id"]),
            "created_at": datetime.datetime.utcnow(),

            "pickup_address": d.get("pickup"),
            "dropoff_address": d.get("dropoff"),
            "reg_number": d.get("reg_number"),
            "pickup_date": d.get("pickup_date") or None,

            "customer_name": d.get("customer_name"),
            "company": d.get("company"),
            "email": d.get("email"),
            "phone": d.get("phone"),
            "additional_info": d.get("additional_info"),

            "distance_km": float(round(km, 2)),
            "price_net": float(net),
            "price_vat": float(vat),
            "price_gross": float(gross),

            "status": "NEW",
            "winter_tires": bool(d.get("winter_tires")) if "winter_tires" in d else False
        }

        orders_col().insert_one(doc)
        # tyhjennä luonnos ja siirry tilausnäkymään
        session.pop("order_draft", None)
        return redirect(f"/order/{oid}")

    price_block = f"<div class='card'><strong>Arvioitu hinta:</strong> {km:.1f} km → {gross:.2f} €</div>"
    if err: price_block = f"<div class='card'><span class='muted'>{err}</span><br>{price_block}</div>"

    inner = f"""
<h2 class='card-title'>Vahvista tilaus</h2>
<div class='confirmation-layout'>
  <div class='confirmation-grid'>
    <div class='confirmation-card'><h3 class='confirmation-title'>Nouto</h3><p class='confirmation-text'>{d.get('pickup')}</p><p class='confirmation-meta'>{d.get('pickup_date') or 'Heti'}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Toimitus</h3><p class='confirmation-text'>{d.get('dropoff')}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Ajoneuvo</h3><p class='confirmation-text'>Rekisteri: {d.get('reg_number')}</p><p class='confirmation-meta'>Talvirenkaat: {"Kyllä" if d.get('winter_tires') else "Ei"}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Yhteystiedot</h3><p class='confirmation-text'>{d.get('customer_name')} ({d.get('company') or '-'})</p><p class='confirmation-meta'>{d.get('email')} / {d.get('phone')}</p></div>
    <div class='confirmation-card'><h3 class='confirmation-title'>Lisätiedot</h3><p class='confirmation-text'>{(d.get('additional_info') or '-').replace('<','&lt;')}</p></div>
  </div>
  <div class='confirmation-map-container'>
    <div class='confirmation-card map-card'>
      <h3 class='confirmation-title'>Reitti</h3>
      <div id="confirmation_map" class="confirmation-map"></div>
      <p class='confirmation-meta'>Arvioitu hinta: {gross:.2f} €</p>
    </div>
  </div>
</div>
<div class='price-summary'>
  <div class='price-card'>
    <h3 class='price-title'>Arvioitu hinta</h3>
    <div class='price-details'>
      <span class='distance'>{km:.1f} km</span>
      <span class='price'>{gross:.2f} €</span>
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

@media (max-width: 768px) {{
  .confirmation-layout {{
    flex-direction: column;
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

  // Fetch route data
  const pickup = encodeURIComponent('{d.get("pickup")}');
  const dropoff = encodeURIComponent('{d.get("dropoff")}');

  fetch(`/route?from=${{pickup}}&to=${{dropoff}}`)
    .then(response => response.json())
    .then(data => {{
      if (data.latlngs && data.start && data.end) {{
        map.draw(data.latlngs, data.start, data.end, {km:.1f});
      }}
    }})
    .catch(error => {{ /* Could not load route - silently handle */ }});
}});
</script>
"""
    return wrap(wizard_shell(6, inner, session.get("order_draft", {})), u)
