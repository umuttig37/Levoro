# order_wizard.py
import secrets, datetime
from flask import request, redirect, url_for, session
from app import app, wrap, price_from_km, route_km, current_user, next_id, orders_col

def wizard_shell(active: int, inner_html: str) -> str:
    steps = ["Pickup", "Delivery", "Vehicle", "Contact", "Notes", "Confirm"]
    nav = "<div class='stepnav'>"
    for i, s in enumerate(steps, start=1):
        cls = "item active" if i == active else "item"
        nav += f"<div class='{cls}'> {i}. {s}</div>"
    nav += "</div>"
    return f"<div class='wizard'>{nav}<div class='card'>{inner_html}</div></div>"

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

        inner = """
<h2>Auton nouto</h2>
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
  <div style="margin-top:8px" id="mini_map1" class="mini-map"></div>
  <div class='row' style='margin-top:8px'>
    <button type="button" class="ghost" id="step1_calc">Päivitä kartta</button>
    <button type='submit'>Jatka →</button>
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
/* ===== Yksinkertainen FI-osoite-autocomplete (Nominatim) ===== */
function fiShortAddress(adr){
  const road = adr.road || adr.pedestrian || adr.cycleway || adr.footway || "";
  const num  = adr.house_number ? " " + adr.house_number : "";
  const city = adr.city || adr.town || adr.municipality || adr.village || adr.suburb || adr.city_district || "";
  return `${road}${num}${city ? ", " + city : ""}`.trim();
}

function bindAC(inputId, listId){
  const inp  = document.getElementById(inputId);
  const list = document.getElementById(listId);
  let timer  = null;

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
          + '?format=jsonv2&addressdetails=1&limit=10&dedupe=1&countrycodes=fi'
          + '&viewbox=19,59,32,71&bounded=1'
          + '&q=' + encodeURIComponent(q);
        const resp = await fetch(url, { headers:{'Accept-Language':'fi'} });
        const arr  = await resp.json();

        const seen = new Set();
        const items = [];
        for(const p of arr){
          const adr = p.address || {};
          if(adr.country_code !== 'fi') continue;
          const short = fiShortAddress(adr);
          if(!short) continue;
          const key = short.toLowerCase();
          if(seen.has(key)) continue;
          seen.add(key);
          items.push({ short, lat: p.lat, lon: p.lon, hasNumber: !!adr.house_number });
        }

        items.sort((a,b)=> Number(b.hasNumber)-Number(a.hasNumber));

        list.innerHTML = items.slice(0,8).map(it =>
          `<div class="ac-item" data-label="${it.short.replace(/"/g,'&quot;')}" data-lat="${it.lat}" data-lon="${it.lon}">${it.short}</div>`
        ).join('');
        list.style.display = items.length ? 'block' : 'none';

        Array.from(list.children).forEach(el=>{
          el.onclick = async ()=>{
            const label = el.getAttribute('data-label');
            const lat   = el.getAttribute('data-lat');
            const lon   = el.getAttribute('data-lon');
            inp.value = label;
            list.style.display='none';
            try{
              const rr = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&accept-language=fi&lat=${lat}&lon=${lon}`);
              const jj = await rr.json();
              const fixed = fiShortAddress(jj.address||{});
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

  document.addEventListener('click', (e)=>{
    if(!list.contains(e.target) && e.target!==inp){ list.style.display='none'; }
  });
}

/* Käyttö Step 1:lle */
bindAC('from_step','ac_from_step');
</script>
"""
        inner = inner.replace("__PICKUP_VAL__", pickup_val)
        return wrap(wizard_shell(1, inner), u)

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
<form method='POST'>
  <!-- piilotettu nouto, jotta kartta voi piirtyä (from_step löytyy DOMista) -->
  <input type="hidden" id="from_step" value="__PICK_VAL__">
  <label>Toimitusosoite *</label>
  <div class="autocomplete">
    <input id="to_step" name="dropoff" required value="__DROP_VAL__" placeholder="Katu, kaupunki">
    <div id="ac_to_step" class="ac-list"></div>
  </div>
  <div style="margin-top:8px" id="mini_map2" class="mini-map"></div>
  <div class='row' style='margin-top:8px'>
    <button type="button" class="ghost" id="step2_calc">Päivitä kartta</button>
    <button type='submit'>Jatka →</button>
  </div>
</form>

<script>
/* Sama autocomplete-apuri kuin Step 1:ssä */
function fiShortAddress(adr){
  const road = adr.road || adr.pedestrian || adr.cycleway || adr.footway || "";
  const num  = adr.house_number ? " " + adr.house_number : "";
  const city = adr.city || adr.town || adr.municipality || adr.village || adr.suburb || adr.city_district || "";
  return `${road}${num}${city ? ", " + city : ""}`.trim();
}
function bindAC(inputId, listId){
  const inp  = document.getElementById(inputId);
  const list = document.getElementById(listId);
  let timer  = null;

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
          + '?format=jsonv2&addressdetails=1&limit=10&dedupe=1&countrycodes=fi'
          + '&viewbox=19,59,32,71&bounded=1'
          + '&q=' + encodeURIComponent(q);
        const resp = await fetch(url, { headers:{'Accept-Language':'fi'} });
        const arr  = await resp.json();

        const seen = new Set();
        const items = [];
        for(const p of arr){
          const adr = p.address || {};
          if(adr.country_code !== 'fi') continue;
          const short = fiShortAddress(adr);
          if(!short) continue;
          const key = short.toLowerCase();
          if(seen.has(key)) continue;
          seen.add(key);
          items.push({ short, lat: p.lat, lon: p.lon, hasNumber: !!adr.house_number });
        }
        items.sort((a,b)=> Number(b.hasNumber)-Number(a.hasNumber));

        list.innerHTML = items.slice(0,8).map(it =>
          `<div class="ac-item" data-label="${it.short.replace(/"/g,'&quot;')}" data-lat="${it.lat}" data-lon="${it.lon}">${it.short}</div>`
        ).join('');
        list.style.display = items.length ? 'block' : 'none';

        Array.from(list.children).forEach(el=>{
          el.onclick = async ()=>{
            const label = el.getAttribute('data-label');
            const lat   = el.getAttribute('data-lat');
            const lon   = el.getAttribute('data-lon');
            inp.value = label;
            list.style.display='none';
            try{
              const rr = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&accept-language=fi&lat=${lat}&lon=${lon}`);
              const jj = await rr.json();
              const fixed = fiShortAddress(jj.address||{});
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

  document.addEventListener('click', (e)=>{
    if(!list.contains(e.target) && e.target!==inp){ list.style.display='none'; }
  });
}

/* Käyttö Step 2:lle (toimitusosoite) */
bindAC('to_step','ac_to_step');
</script>
"""
    inner = inner.replace("__DROP_VAL__", drop_val).replace("__PICK_VAL__", pick_val)
    return wrap(wizard_shell(2, inner), u)



# STEP 3: Vehicle
@app.route("/order/new/step3", methods=["GET","POST"])
def order_step3():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/step3"))
    if request.method == "POST":
        d = session.get("order_draft", {})
        d["reg_number"] = request.form.get("reg_number","").strip()
        session["order_draft"] = d
        return redirect("/order/new/step4")
    inner = """
<h2>Ajoneuvon tiedot</h2>
<form method='POST'>
  <label>Rekisterinumero *</label><input name='reg_number' required placeholder='ABC-123'>
  <div class='row'><button type='submit'>Jatka →</button></div>
</form>"""
    return wrap(wizard_shell(3, inner), u)

# STEP 4: Contact
@app.route("/order/new/step4", methods=["GET","POST"])
def order_step4():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/step4"))
    if request.method == "POST":
        d = session.get("order_draft", {})
        d["customer_name"] = request.form.get("customer_name","").strip()
        d["company"] = request.form.get("company","").strip()
        d["email"] = request.form.get("email","").strip()
        d["phone"] = request.form.get("phone","").strip()
        session["order_draft"] = d
        return redirect("/order/new/step5")
    inner = """
<h2>Yhteystiedot</h2>
<form method='POST'>
  <label>Nimi *</label><input name='customer_name' required>
  <label>Yritys</label><input name='company'>
  <label>Sähköposti *</label><input type='email' name='email' required>
  <label>Puhelin *</label><input name='phone' required>
  <div class='row'><button type='submit'>Jatka →</button></div>
</form>"""
    return wrap(wizard_shell(4, inner), u)

# STEP 5: Notes
@app.route("/order/new/step5", methods=["GET","POST"])
def order_step5():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/step5"))
    if request.method == "POST":
        d = session.get("order_draft", {})
        d["additional_info"] = request.form.get("additional_info","").strip()
        session["order_draft"] = d
        return redirect("/order/new/confirm")
    inner = """
<h2>Lisätiedot tai erityistoiveet</h2>
<form method='POST'>
  <label>Kirjoita toiveet</label>
  <textarea name='additional_info' rows='5' placeholder='Esim. Autossa on talvirenkaat mukana, toimitus kiireellinen'></textarea>
  <div class='row'><button type='submit'>Jatka →</button></div>
</form>"""
    return wrap(wizard_shell(5, inner), u)

# STEP 6: Confirm
@app.route("/order/new/confirm", methods=["GET","POST"])
def order_confirm():
    u = current_user()
    if not u: return redirect(url_for("login", next="/order/new/confirm"))
    d = session.get("order_draft", {})
    required = ["pickup","dropoff","reg_number","customer_name","email","phone"]
    if any(not d.get(k) for k in required):
        return redirect("/order/new/step1")

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
        pin = secrets.token_hex(2).upper()
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
            "pin": pin,
            "winter_tires": bool(d.get("winter_tires")) if "winter_tires" in d else False
        }

        orders_col().insert_one(doc)
        # tyhjennä luonnos ja siirry tilausnäkymään
        session.pop("order_draft", None)
        return redirect(f"/order/{oid}")

    price_block = f"<div class='card'><strong>Arvioitu hinta:</strong> {km:.1f} km → {gross:.2f} €</div>"
    if err: price_block = f"<div class='card'><span class='muted'>{err}</span><br>{price_block}</div>"

    inner = f"""
<h2>Vahvista tilaus</h2>
<div class='grid cols-2'>
  <div class='card'><h3>Nouto</h3><p>{d.get('pickup')}</p><p class='muted'>{d.get('pickup_date') or 'Heti'}</p></div>
  <div class='card'><h3>Toimitus</h3><p>{d.get('dropoff')}</p></div>
  <div class='card'><h3>Ajoneuvo</h3><p>Rekisteri: {d.get('reg_number')}</p></div>
  <div class='card'><h3>Yhteystiedot</h3><p>{d.get('customer_name')} ({d.get('company') or '-'})</p><p class='muted'>{d.get('email')} / {d.get('phone')}</p></div>
  <div class='card'><h3>Lisätiedot</h3><p>{(d.get('additional_info') or '-').replace('<','&lt;')}</p></div>
</div>
{price_block}
<form method='POST' style='margin-top:12px'><button type='submit'>Lähetä tilaus ✓</button> <a class='ghost' href='/order/new/step1'>Takaisin</a></form>
"""
    return wrap(wizard_shell(6, inner), u)
