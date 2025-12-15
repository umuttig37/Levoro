"""
API Routes for pricing and quotes
"""

from flask import Blueprint, request, jsonify
from services.order_service import order_service

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route("/quote-for-addresses", methods=["POST"])
def quote_for_addresses():
    """Get pricing quote for specific addresses"""
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "JSON payload required"}), 400

    pickup = payload.get("pickup", "").strip()
    dropoff = payload.get("dropoff", "").strip()
    pickup_place_id = (payload.get("pickup_place_id") or "").strip()
    dropoff_place_id = (payload.get("dropoff_place_id") or "").strip()
    # NOTE: return_leg parameter exists but is not used in the current UI
    return_leg = bool(payload.get("return_leg", False))

    if not pickup or not dropoff:
        return jsonify({"error": "Lähtö- ja kohdeosoite vaaditaan"}), 400

    try:
        km = order_service.route_km(pickup, dropoff, pickup_place_id, dropoff_place_id)
        net, vat, gross, details = order_service.price_from_km(km, pickup, dropoff, return_leg=return_leg)
        return jsonify({"km": round(km, 2), "net": net, "vat": vat, "gross": gross, "details": details})
    except ValueError as e:
        # These are user-friendly messages from route_km() when routing is unavailable
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        # Unexpected errors - log but don't expose details
        print(f"Unexpected error in quote_for_addresses: {str(e)}")
        return jsonify({"error": "Hintalaskenta ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan"}), 500


@api_bp.route("/quote")
def api_quote():
    """Get pricing quote for distance in km"""
    try:
        km = float(request.args.get("km", "0"))
    except:
        return jsonify({"error": "bad km"}), 400

    net, vat, gross = order_service.price_from_km(km)
    return jsonify({"net": net, "vat": vat, "gross": gross})
