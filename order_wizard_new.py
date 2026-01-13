# order_wizard_new.py - Modern Template-Based Order Wizard
"""
New order wizard implementation using separate Jinja2 templates
that match the redesigned calculator page style.
"""

import datetime
import re
from flask import request, redirect, url_for, session, render_template
from services.auth_service import auth_service
from services.order_service import order_service
from models.database import db_manager
from models.order import order_model
from utils.rate_limiter import check_rate_limit
from html import unescape


def sanitize_text(value: str, max_length: int = 1000) -> str:
    """Strip HTML tags and trim length to reduce XSS/stored content risks."""
    if not value:
        return ""
    # Basic tag strip
    cleaned = re.sub(r"<[^>]+>", "", unescape(str(value)))
    cleaned = cleaned.replace("\x00", "")
    return cleaned.strip()[:max_length]

def get_app():
    from app import app
    return app

app = get_app()

def validate_phone_number(phone):
    """Validate that phone number contains only digits, spaces, +, -, and ()"""
    if not phone:
        return False
    pattern = r'^[+]?[0-9\s\-()]+$'
    return bool(re.match(pattern, phone))

def get_accessible_steps(session_data):
    """Determine which steps user can navigate to based on completed data"""
    accessible = [1]
    if session_data.get("pickup"):
        accessible.append(2)
    if session_data.get("dropoff"):
        accessible.append(3)
    if session_data.get("reg_number"):
        accessible.append(4)
    if (session_data.get("orderer_name") and 
        session_data.get("orderer_email") and 
        session_data.get("orderer_phone")):
        accessible.append(5)
    if session_data.get("additional_info") is not None:
        accessible.append(6)
    return accessible

def validate_step_access(required_step, session_data):
    """Validate if user can access the requested step"""
    accessible_steps = get_accessible_steps(session_data)
    if required_step not in accessible_steps:
        highest_step = max(accessible_steps)
        return redirect(f"/order/new/step{highest_step}")
    return None


def _require_login():
    """Ensure user is authenticated before allowing order flow"""
    u = auth_service.get_current_user()
    if not u:
        return None, redirect(url_for("auth.login", next=request.path))
    return u, None


# =============================================================================
# STEP 1: Pickup
# =============================================================================
@app.route("/order/new/step1", methods=["GET", "POST"])
def order_step1_v2():
    u, redirect_resp = _require_login()
    if redirect_resp:
        return redirect_resp

    if request.method == "POST":
        d = session.get("order_draft", {})
        d["pickup"] = request.form.get("pickup", "").strip()
        d["pickup_place_id"] = request.form.get("pickup_place_id", "").strip()
        d["pickup_date"] = request.form.get("pickup_date", "").strip()
        d["pickup_time"] = request.form.get("pickup_time", "").strip() or None
        d["paluu_auto"] = bool(request.form.get("paluu_auto"))
        if not d["paluu_auto"]:
            d["return_delivery_date"] = None
        session["order_draft"] = d
        return redirect("/order/new/step2")

    # GET
    d = session.get("order_draft", {})
    
    # Handle query params from calculator
    qp_pick = request.args.get("pickup", "").strip()
    qp_drop = request.args.get("dropoff", "").strip()
    if qp_pick:
        d["pickup"] = qp_pick
    if qp_drop:
        d["dropoff"] = qp_drop
    session["order_draft"] = d

    # Date handling
    today = datetime.date.today()
    pickup_date = d.get("pickup_date", "")
    try:
        if pickup_date:
            pd = datetime.datetime.strptime(pickup_date, "%Y-%m-%d").date()
            if pd < today:
                pickup_date = today.isoformat()
        else:
            pickup_date = today.isoformat()
    except:
        pickup_date = today.isoformat()

    error_message = session.pop("error_message", None)

    return render_template("order/step1.html",
        current_user=u,
        active_step=1,
        accessible_steps=get_accessible_steps(d),
        error_message=error_message,
        pickup_value=d.get("pickup", ""),
        pickup_place_id=d.get("pickup_place_id", ""),
        pickup_date=pickup_date,
        pickup_time=d.get("pickup_time", ""),
        paluu_auto=d.get("paluu_auto", False)
    )


# =============================================================================
# STEP 2: Delivery
# =============================================================================
@app.route("/order/new/step2", methods=["GET", "POST"])
def order_step2_v2():
    u, redirect_resp = _require_login()
    if redirect_resp:
        return redirect_resp

    session_data = session.get("order_draft", {})
    access_check = validate_step_access(2, session_data)
    if access_check:
        return access_check

    if request.method == "POST":
        d = session.get("order_draft", {})
        d["dropoff"] = request.form.get("dropoff", "").strip()
        d["dropoff_place_id"] = request.form.get("dropoff_place_id", "").strip()
        d["saved_dropoff_phone"] = request.form.get("saved_dropoff_phone", "").strip()
        d["last_delivery_date"] = request.form.get("last_delivery_date") or None
        d["delivery_time"] = request.form.get("delivery_time", "").strip() or None
        
        if d.get("paluu_auto"):
            d["return_delivery_date"] = d.get("last_delivery_date") or d.get("pickup_date")
        
        action = request.form.get("action")
        if action == "back":
            session["order_draft"] = d
            return redirect("/order/new/step1")
        
        # Validate addresses before proceeding
        pickup_addr = d.get("pickup", "").strip()
        dropoff_addr = d.get("dropoff", "").strip()
        
        # Check if addresses are the same
        if pickup_addr.lower() == dropoff_addr.lower():
            session["error_message"] = "Nouto- ja toimitusosoite eivät voi olla samat. Tarkista osoitteet."
            session["order_draft"] = d
            return redirect("/order/new/step2")
        
        # Try to calculate route to validate addresses
        try:
            km = order_service.route_km(
                pickup_addr, dropoff_addr,
                d.get("pickup_place_id", ""),
                d.get("dropoff_place_id", "")
            )
            if km <= 0:
                session["error_message"] = "Reitin laskenta epäonnistui. Tarkista että osoitteet ovat oikein."
                session["order_draft"] = d
                return redirect("/order/new/step2")
        except Exception as e:
            session["error_message"] = "Reitin laskenta epäonnistui. Tarkista että osoitteet ovat oikein ja yritä uudelleen."
            session["order_draft"] = d
            return redirect("/order/new/step2")
        
        session["order_draft"] = d
        return redirect("/order/new/step3")

    # GET
    d = session.get("order_draft", {})
    
    # Date handling
    pickup_date = d.get("pickup_date") or datetime.date.today().isoformat()
    delivery_date = d.get("last_delivery_date") or pickup_date

    error_message = session.pop("error_message", None)

    return render_template("order/step2.html",
        current_user=u,
        active_step=2,
        accessible_steps=get_accessible_steps(d),
        error_message=error_message,
        pickup_address=d.get("pickup", ""),
        pickup_date=pickup_date,
        dropoff_value=d.get("dropoff", ""),
        dropoff_place_id=d.get("dropoff_place_id", ""),
        delivery_date=delivery_date,
        delivery_time=d.get("delivery_time", ""),
        saved_phone=d.get("saved_dropoff_phone", "")
    )


# =============================================================================
# STEP 3: Vehicle
# =============================================================================
@app.route("/order/new/step3", methods=["GET", "POST"])
def order_step3_v2():
    u, redirect_resp = _require_login()
    if redirect_resp:
        return redirect_resp

    session_data = session.get("order_draft", {})
    access_check = validate_step_access(3, session_data)
    if access_check:
        return access_check

    if request.method == "POST":
        d = session.get("order_draft", {})
        d["reg_number"] = request.form.get("reg_number", "").strip().upper()
        d["winter_tires"] = bool(request.form.get("winter_tires"))
        
        if d.get("paluu_auto"):
            d["return_reg_number"] = request.form.get("return_reg_number", "").strip().upper()
            d["return_winter_tires"] = bool(request.form.get("return_winter_tires"))
        else:
            d["return_reg_number"] = None
            d["return_winter_tires"] = False
        
        session["order_draft"] = d
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step2")
        return redirect("/order/new/step4")

    # GET
    d = session.get("order_draft", {})
    error_message = session.pop("error_message", None)

    return render_template("order/step3.html",
        current_user=u,
        active_step=3,
        accessible_steps=get_accessible_steps(d),
        error_message=error_message,
        reg_number=d.get("reg_number", ""),
        winter_tires=d.get("winter_tires", False),
        paluu_auto=d.get("paluu_auto", False),
        return_reg_number=d.get("return_reg_number", ""),
        return_winter_tires=d.get("return_winter_tires", False)
    )


# =============================================================================
# STEP 4: Contact
# =============================================================================
@app.route("/order/new/step4", methods=["GET", "POST"])
def order_step4_v2():
    u, redirect_resp = _require_login()
    if redirect_resp:
        return redirect_resp

    session_data = session.get("order_draft", {})
    access_check = validate_step_access(4, session_data)
    if access_check:
        return access_check

    if request.method == "POST":
        d = session.get("order_draft", {})
        d["orderer_name"] = request.form.get("orderer_name", "").strip()
        d["orderer_email"] = request.form.get("orderer_email", "").strip()
        d["orderer_phone"] = request.form.get("orderer_phone", "").strip()
        d["customer_name"] = request.form.get("customer_name", "").strip()
        d["customer_phone"] = request.form.get("customer_phone", "").strip()
        
        # Validate orderer phone
        if not validate_phone_number(d["orderer_phone"]):
            session["error_message"] = "Tilaajan puhelinnumero ei ole kelvollinen."
            session["order_draft"] = d
            return redirect("/order/new/step4")
        
        # Validate customer phone if provided
        if d["customer_phone"] and not validate_phone_number(d["customer_phone"]):
            session["error_message"] = "Asiakkaan puhelinnumero ei ole kelvollinen."
            session["order_draft"] = d
            return redirect("/order/new/step4")
        
        d["phone"] = d["customer_phone"]  # Legacy compatibility
        session["order_draft"] = d
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step3")
        return redirect("/order/new/step5")

    # GET
    d = session.get("order_draft", {})
    
    # Auto-fill from user profile
    saved_phone = d.get("saved_dropoff_phone", "").strip()
    if not d.get("orderer_name"):
        d["orderer_name"] = u.get("name", "")
    if not d.get("orderer_email"):
        d["orderer_email"] = u.get("email", "")
    if saved_phone:
        d["orderer_phone"] = saved_phone
    elif not d.get("orderer_phone"):
        d["orderer_phone"] = u.get("phone", "")
    
    session["order_draft"] = d
    error_message = session.pop("error_message", None)

    return render_template("order/step4.html",
        current_user=u,
        active_step=4,
        accessible_steps=get_accessible_steps(d),
        error_message=error_message,
        orderer_name=d.get("orderer_name", ""),
        orderer_email=d.get("orderer_email", ""),
        orderer_phone=d.get("orderer_phone", ""),
        customer_name=d.get("customer_name", ""),
        customer_phone=d.get("customer_phone", "")
    )


# =============================================================================
# STEP 5: Notes
# =============================================================================
@app.route("/order/new/step5", methods=["GET", "POST"])
def order_step5_v2():
    u, redirect_resp = _require_login()
    if redirect_resp:
        return redirect_resp

    session_data = session.get("order_draft", {})
    access_check = validate_step_access(5, session_data)
    if access_check:
        return access_check

    if request.method == "POST":
        d = session.get("order_draft", {})
        d["additional_info"] = request.form.get("additional_info", "").strip()
        d["direct_to_customer"] = bool(request.form.get("direct_to_customer"))
        session["order_draft"] = d
        
        action = request.form.get("action")
        if action == "back":
            return redirect("/order/new/step4")
        return redirect("/order/new/confirm")

    # GET
    d = session.get("order_draft", {})
    error_message = session.pop("error_message", None)

    return render_template("order/step5.html",
        current_user=u,
        active_step=5,
        accessible_steps=get_accessible_steps(d),
        error_message=error_message,
        additional_info=d.get("additional_info", ""),
        direct_to_customer=d.get("direct_to_customer", False)
    )


# =============================================================================
# STEP 6: Confirm
# =============================================================================
@app.route("/order/new/confirm", methods=["GET", "POST"])
def order_confirm_v2():
    u, redirect_resp = _require_login()
    if redirect_resp:
        return redirect_resp

    session_data = session.get("order_draft", {})
    access_check = validate_step_access(6, session_data)
    if access_check:
        return access_check

    d = session.get("order_draft", {})
    required = ["pickup", "dropoff", "reg_number", "orderer_name", "orderer_email", "orderer_phone"]
    missing = [k for k in required if not d.get(k)]
    
    if missing:
        if "pickup" in missing or "dropoff" in missing:
            session["error_message"] = "Osoitetiedot puuttuvat."
            return redirect("/order/new/step1")
        if "reg_number" in missing:
            session["error_message"] = "Ajoneuvon tiedot puuttuvat."
            return redirect("/order/new/step3")
        session["error_message"] = "Yhteystiedot puuttuvat."
        return redirect("/order/new/step4")

    # Calculate pricing
    pricing_error = None
    km = 0.0
    net = vat = gross = 0.0
    outbound_original_net = 0.0
    
    try:
        km = order_service.route_km(
            d["pickup"], d["dropoff"],
            d.get("pickup_place_id", ""),
            d.get("dropoff_place_id", "")
        )
    except Exception as e:
        pricing_error = "Reitin laskenta epäonnistui. Tarkista osoitteet."

    user_id = int(u["id"]) if u.get("id") else None
    is_first_order = False
    if user_id:
        try:
            existing = order_service.get_user_orders(user_id, limit=1)
            is_first_order = len(existing) == 0
        except:
            pass

    outbound_discount_amount = 0.0
    if km > 0 and not pricing_error:
        pricing = order_service.price_from_km_with_discounts(
            km,
            pickup_addr=d.get("pickup"),
            dropoff_addr=d.get("dropoff"),
            return_leg=False,
            user_id=user_id,
            promo_code=d.get("promo_code"),
            is_first_order=is_first_order
        )
        net = pricing.get("final_net", 0.0)
        vat = pricing.get("final_vat", 0.0)
        gross = pricing.get("final_gross", 0.0)
        outbound_discount_amount = pricing.get("discount_amount", 0.0)
        outbound_original_net = pricing.get("display_original_net", pricing.get("original_net", net))

    # Return trip calculations
    paluu_auto = d.get("paluu_auto", False)
    return_km = 0.0
    return_net = return_vat = return_gross = 0.0
    return_original_net = 0.0
    return_discount_amount = 0.0
    
    if paluu_auto and not pricing_error:
        try:
            return_km = order_service.route_km(
                d["dropoff"], d["pickup"],
                d.get("dropoff_place_id", ""),
                d.get("pickup_place_id", "")
            )
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
                return_original_net = return_pricing.get("display_original_net", return_pricing.get("original_net", return_net))
        except:
            pricing_error = "Paluumatkan laskenta epäonnistui."

    total_km = km + return_km
    total_net = net + return_net
    total_vat = vat + return_vat
    total_gross = gross + return_gross
    total_discount_amount = outbound_discount_amount + return_discount_amount
    total_original_net = outbound_original_net + return_original_net

    # Date formatting
    def fmt_date(s):
        try:
            if not s:
                return None
            dt = datetime.datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except:
            return s

    pickup_date_display = fmt_date(d.get("pickup_date"))
    if d.get("pickup_time"):
        pickup_date_display = f"{pickup_date_display} klo {d.get('pickup_time')}"
    
    delivery_date_display = fmt_date(d.get("last_delivery_date"))
    if d.get("delivery_time"):
        delivery_date_display = f"{delivery_date_display} klo {d.get('delivery_time')}"

    return_pickup_display = fmt_date(d.get("last_delivery_date") or d.get("pickup_date"))
    return_delivery_display = fmt_date(d.get("return_delivery_date"))

    # Handle POST (order submission)
    if request.method == "POST":
        if pricing_error:
            session["error_message"] = pricing_error
            return redirect("/order/new/confirm")

        # Create outbound order
        order_data = {
            "pickup_address": sanitize_text(d.get("pickup")),
            "dropoff_address": sanitize_text(d.get("dropoff")),
            "pickup_place_id": sanitize_text(d.get("pickup_place_id")),
            "dropoff_place_id": sanitize_text(d.get("dropoff_place_id")),
            "reg_number": sanitize_text(d.get("reg_number")),
            "pickup_date": d.get("pickup_date"),
            "last_delivery_date": d.get("last_delivery_date"),
            "pickup_time": d.get("pickup_time"),
            "delivery_time": d.get("delivery_time"),
            "orderer_name": sanitize_text(d.get("orderer_name")),
            "orderer_email": sanitize_text(d.get("orderer_email")),
            "orderer_phone": sanitize_text(d.get("orderer_phone")),
            "customer_name": sanitize_text(d.get("customer_name")),
            "customer_phone": sanitize_text(d.get("customer_phone")),
            "phone": sanitize_text(d.get("customer_phone")),
            "additional_info": sanitize_text(d.get("additional_info"), max_length=2000),
            "direct_to_customer": d.get("direct_to_customer", False),
            "distance_km": float(round(km, 2)),
            "price_net": float(net),
            "price_vat": float(vat),
            "price_gross": float(gross),
            "discount_amount": float(round(outbound_discount_amount, 2)),
            "winter_tires": d.get("winter_tires", False),
            "trip_type": order_model.TRIP_TYPE_OUTBOUND if paluu_auto else None
        }

        success, order, error = order_service.create_order(int(u["id"]), order_data)

        if success and order:
            outbound_order_id = order['id']
            
            if paluu_auto:
                return_data = {
                    "pickup_address": sanitize_text(d.get("dropoff")),
                    "dropoff_address": sanitize_text(d.get("pickup")),
                    "pickup_place_id": sanitize_text(d.get("dropoff_place_id")),
                    "dropoff_place_id": sanitize_text(d.get("pickup_place_id")),
                    "reg_number": sanitize_text(d.get("return_reg_number") or d.get("reg_number")),
                    "pickup_date": d.get("last_delivery_date") or d.get("pickup_date"),
                    "last_delivery_date": d.get("return_delivery_date"),
                    "orderer_name": sanitize_text(d.get("orderer_name")),
                    "orderer_email": sanitize_text(d.get("orderer_email")),
                    "orderer_phone": sanitize_text(d.get("orderer_phone")),
                    "customer_name": sanitize_text(d.get("customer_name")),
                    "customer_phone": sanitize_text(d.get("customer_phone")),
                    "phone": sanitize_text(d.get("customer_phone")),
                    "additional_info": sanitize_text(d.get("additional_info"), max_length=2000),
                    "distance_km": float(round(return_km, 2)),
                    "price_net": float(return_net),
                    "price_vat": float(return_vat),
                    "price_gross": float(return_gross),
                    "discount_amount": float(round(return_discount_amount, 2)),
                    "winter_tires": d.get("return_winter_tires", False),
                    "trip_type": order_model.TRIP_TYPE_RETURN,
                    "parent_order_id": outbound_order_id,
                    "return_leg": True
                }
                
                ret_success, ret_order, ret_error = order_service.create_order(int(u["id"]), return_data)
                
                if ret_success and ret_order:
                    db_manager.get_collection("orders").update_one(
                        {"id": outbound_order_id},
                        {"$set": {"return_order_id": ret_order['id']}}
                    )

            session.pop("order_draft", None)
            return redirect(f"/order/{outbound_order_id}")
        else:
            session["error_message"] = f"Tilauksen luominen epäonnistui: {error}"

    error_message = session.pop("error_message", None)

    return render_template("order/confirm.html",
        current_user=u,
        active_step=6,
        accessible_steps=get_accessible_steps(d),
        error_message=error_message,
        pricing_error=pricing_error,
        
        # Addresses
        pickup_address=d.get("pickup", ""),
        dropoff_address=d.get("dropoff", ""),
        pickup_place_id=d.get("pickup_place_id", ""),
        dropoff_place_id=d.get("dropoff_place_id", ""),
        
        # Dates
        pickup_date_display=pickup_date_display,
        delivery_date_display=delivery_date_display,
        return_pickup_display=return_pickup_display,
        return_delivery_display=return_delivery_display,
        
        # Vehicle
        reg_number=d.get("reg_number", ""),
        winter_tires=d.get("winter_tires", False),
        return_reg_number=d.get("return_reg_number", ""),
        return_winter_tires=d.get("return_winter_tires", False),
        
        # Contact
        orderer_name=d.get("orderer_name", ""),
        orderer_email=d.get("orderer_email", ""),
        orderer_phone=d.get("orderer_phone", ""),
        customer_name=d.get("customer_name", ""),
        customer_phone=d.get("customer_phone", ""),
        additional_info=d.get("additional_info", ""),
        direct_to_customer=d.get("direct_to_customer", False),
        
        # Pricing
        paluu_auto=paluu_auto,
        km=km,
        net=net,
        vat=vat,
        gross=gross,
        outbound_original_net=outbound_original_net,
        return_km=return_km,
        return_net=return_net,
        return_vat=return_vat,
        return_gross=return_gross,
        return_original_net=return_original_net,
        total_km=total_km,
        total_net=total_net,
        total_vat=total_vat,
        total_gross=total_gross,
        total_discount_amount=total_discount_amount,
        total_original_net=total_original_net
    )


# =============================================================================
# SPA WIZARD - Single Page Application Version
# =============================================================================
@app.route("/order/new", methods=["GET"])
def order_wizard_spa():
    """Single-page application version of the order wizard"""
    u = auth_service.get_current_user()
    return render_template("order/wizard_spa.html", current_user=u)


@app.route("/api/order/submit", methods=["POST"])
def api_order_submit():
    """AJAX endpoint for SPA wizard order submission"""
    from flask import jsonify
    
    u = auth_service.get_current_user()
    if not u:
        return jsonify({"error": "Kirjaudu sisään luodaksesi tilauksen"}), 401

    allowed, retry_after = check_rate_limit(f"order_submit:{request.remote_addr}", limit=10, window_seconds=300, lockout_seconds=900)
    if not allowed:
        return jsonify({"error": "Liikaa pyyntöjä, yritä myöhemmin"}), 429
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ["pickup_address", "dropoff_address", "reg_number", "orderer_name", "orderer_email", "orderer_phone"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            return jsonify({"error": f"Pakolliset kentät puuttuvat: {', '.join(missing)}"}), 400
        
        # Calculate pricing
        try:
            km = order_service.route_km(data["pickup_address"], data["dropoff_address"])
        except Exception as e:
            return jsonify({"error": "Reitin laskenta epäonnistui"}), 400
        
        user_id = int(u["id"])
        
        # Check if first order
        is_first_order = False
        try:
            existing = order_service.get_user_orders(user_id, limit=1)
            is_first_order = len(existing) == 0
        except:
            pass
        
        # Calculate pricing
        pricing = order_service.price_from_km_with_discounts(
            km,
            pickup_addr=data.get("pickup_address"),
            dropoff_addr=data.get("dropoff_address"),
            return_leg=False,
            user_id=user_id,
            is_first_order=is_first_order
        )
        
        # Create order
        order_data = {
            "pickup_address": sanitize_text(data.get("pickup_address")),
            "dropoff_address": sanitize_text(data.get("dropoff_address")),
            "reg_number": sanitize_text(data.get("reg_number", "").upper()),
            "pickup_date": data.get("pickup_date"),
            "last_delivery_date": data.get("delivery_date"),
            "pickup_time": data.get("pickup_time"),
            "delivery_time": data.get("delivery_time"),
            "orderer_name": sanitize_text(data.get("orderer_name")),
            "orderer_email": sanitize_text(data.get("orderer_email")),
            "orderer_phone": sanitize_text(data.get("orderer_phone")),
            "customer_name": sanitize_text(data.get("customer_name")),
            "customer_phone": sanitize_text(data.get("customer_phone")),
            "phone": sanitize_text(data.get("customer_phone")),
            "additional_info": sanitize_text(data.get("additional_info"), max_length=2000),
            "direct_to_customer": data.get("direct_to_customer", False),
            "distance_km": float(round(km, 2)),
            "price_net": float(pricing.get("final_net", 0)),
            "price_vat": float(pricing.get("final_vat", 0)),
            "price_gross": float(pricing.get("final_gross", 0)),
            "winter_tires": data.get("winter_tires", False),
            "trip_type": order_model.TRIP_TYPE_OUTBOUND if data.get("paluu_auto") else None
        }
        
        success, order, error = order_service.create_order(user_id, order_data)
        
        if success and order:
            outbound_order_id = order['id']
            
            # Create return order if needed
            if data.get("paluu_auto"):
                try:
                    return_km = order_service.route_km(data["dropoff_address"], data["pickup_address"])
                    return_pricing = order_service.price_from_km_with_discounts(
                        return_km,
                        pickup_addr=data.get("dropoff_address"),
                        dropoff_addr=data.get("pickup_address"),
                        return_leg=True,
                        user_id=user_id,
                        is_first_order=is_first_order
                    )
                    
                    return_data = {
                        "pickup_address": sanitize_text(data.get("dropoff_address")),
                        "dropoff_address": sanitize_text(data.get("pickup_address")),
                        "reg_number": sanitize_text(data.get("return_reg_number", "").upper() or data.get("reg_number", "").upper()),
                        "pickup_date": data.get("delivery_date") or data.get("pickup_date"),
                        "orderer_name": sanitize_text(data.get("orderer_name")),
                        "orderer_email": sanitize_text(data.get("orderer_email")),
                        "orderer_phone": sanitize_text(data.get("orderer_phone")),
                        "customer_name": sanitize_text(data.get("customer_name")),
                        "customer_phone": sanitize_text(data.get("customer_phone")),
                        "phone": sanitize_text(data.get("customer_phone")),
                        "additional_info": sanitize_text(data.get("additional_info"), max_length=2000),
                        "distance_km": float(round(return_km, 2)),
                        "price_net": float(return_pricing.get("final_net", 0)),
                        "price_vat": float(return_pricing.get("final_vat", 0)),
                        "price_gross": float(return_pricing.get("final_gross", 0)),
                        "winter_tires": data.get("return_winter_tires", False),
                        "trip_type": order_model.TRIP_TYPE_RETURN,
                        "parent_order_id": outbound_order_id,
                        "return_leg": True
                    }
                    
                    ret_success, ret_order, ret_error = order_service.create_order(user_id, return_data)
                    
                    if ret_success and ret_order:
                        db_manager.get_collection("orders").update_one(
                            {"id": outbound_order_id},
                            {"$set": {"return_order_id": ret_order['id']}}
                        )
                except Exception as e:
                    pass  # Return trip creation failed, but main order succeeded
            
            return jsonify({"success": True, "order_id": outbound_order_id})
        else:
            return jsonify({"error": f"Tilauksen luominen epäonnistui: {error}"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
