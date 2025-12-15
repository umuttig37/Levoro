"""
Order Service
Handles order business logic, pricing, and operations
"""

import os
import requests
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from models.order import order_model


def round_half_up(value: float, decimals: int = 2) -> float:
    """
    Round using arithmetic rounding (round half up) instead of banker's rounding.
    This follows Finnish standard: when the next decimal is 5 or more, round up.

    Examples:
        33.885 -> 33.89 (not 33.88)
        6.885 -> 6.89 (not 6.88)
    """
    if value is None:
        return 0.0

    # Convert to Decimal for precise rounding
    decimal_value = Decimal(str(value))
    # Create quantizer for desired precision (e.g., '0.01' for 2 decimals)
    quantizer = Decimal(10) ** -decimals
    # Round using ROUND_HALF_UP mode
    rounded = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)

    return float(rounded)


# Configuration from environment
BASE_FEE = float(os.getenv("BASE_FEE", "49"))
PER_KM = float(os.getenv("PER_KM", "1.20"))
VAT_RATE = float(os.getenv("VAT_RATE", "0.255"))  # 25.5% Finnish VAT

# Pricing tiers (NET prices - VAT will be added on top)
METRO_CITIES = {"helsinki", "espoo", "vantaa", "kauniainen"}
METRO_NET = float(os.getenv("METRO_NET", "27"))  # Net price for metro area
MID_KM = 170.0
MID_NET = float(os.getenv("MID_NET", "81"))  # Net price for mid-distance
LONG_KM = 600.0
LONG_NET = float(os.getenv("LONG_NET", "207"))  # Net price for long-distance
# NOTE: Return leg discount is not currently used in the application UI
# This feature is preserved for potential future use
ROUNDTRIP_DISCOUNT = 0.30
# Short-distance special rule: any trip up to this distance uses SHORT_DISTANCE_NET
SHORT_DISTANCE_KM = float(os.getenv("SHORT_DISTANCE_KM", "30"))
SHORT_DISTANCE_NET = float(os.getenv("SHORT_DISTANCE_NET", "27"))
# Minimum order price - all orders must be at least this amount (net)
MINIMUM_ORDER_PRICE_NET = 20.0

# External API configuration
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
GOOGLE_DIRECTIONS_URL = os.getenv(
    "GOOGLE_DIRECTIONS_URL",
    "https://maps.googleapis.com/maps/api/directions/json"
)
# When routing fails entirely, inflate straight-line distance to avoid underpricing
STRAIGHT_LINE_DISTANCE_FACTOR = float(os.getenv("STRAIGHT_LINE_DISTANCE_FACTOR", "1.2"))


class OrderService:
    """Service for handling order operations and business logic"""

    def __init__(self):
        self.order_model = order_model

    def create_order(self, user_id: int, order_data: Dict) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Create a new order with pricing calculation"""
        try:
            # Calculate pricing if addresses are provided
            if "pickup_address" in order_data and "dropoff_address" in order_data:
                pickup_place_id = order_data.get("pickup_place_id", "")
                dropoff_place_id = order_data.get("dropoff_place_id", "")
                distance_km = self.calculate_route_distance(
                    order_data["pickup_address"],
                    order_data["dropoff_address"],
                    pickup_place_id,
                    dropoff_place_id
                )
                if distance_km > 0:
                    order_data["distance_km"] = distance_km
                    gross_price = self.calculate_price(
                        distance_km,
                        order_data["pickup_address"],
                        order_data["dropoff_address"],
                        order_data.get("return_leg", False)
                    )
                    order_data["price_gross"] = gross_price
                    net_price, vat_amount = self._split_gross_to_net_vat(gross_price)
                    order_data["price_net"] = net_price
                    order_data["price_vat"] = vat_amount

            order, error = self.order_model.create_order(user_id, order_data)

            # Send order created email if successful
            if order is not None and error is None:
                try:
                    from services.email_service import email_service
                    from models.user import user_model

                    # Get user details for email
                    user = user_model.find_by_id(user_id)
                    if user:
                        # Send email to customer
                        email_service.send_order_created_email(user["email"], user["name"], order)

                        # Send admin notification
                        email_service.send_admin_new_order_notification(order, user)
                except Exception as e:
                    # Log error but don't fail order creation
                    print(f"Failed to send order emails: {e}")

            return order is not None, order, error

        except Exception as e:
            return False, None, f"Tilauksen luominen epäonnistui: {str(e)}"

    def get_user_orders(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get all orders for a user"""
        return self.order_model.get_user_orders(user_id, limit)

    def get_order_details(self, order_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """Get order details with user validation"""
        return self.order_model.find_by_id(order_id, user_id)

    def update_order_status(self, order_id: int, new_status: str) -> Tuple[bool, Optional[str]]:
        """Update order status (admin only) - only sends customer email for key statuses"""
        # Get order and user details before update for email
        order = self.order_model.find_by_id(order_id)
        if not order:
            return False, "Tilausta ei löytynyt"

        success, error = self.order_model.update_status(order_id, new_status)

        if success:
            # Only send customer email for these key statuses
            # NOTE: ASSIGNED_TO_DRIVER removed - driver acceptance only notifies admin
            CUSTOMER_EMAIL_STATUSES = [
                "CONFIRMED",           # Order received/confirmed
                "IN_TRANSIT",          # In transit
                "DELIVERED"            # Delivered
            ]

            # Send status update email only for key statuses
            if new_status in CUSTOMER_EMAIL_STATUSES:
                try:
                    from services.email_service import email_service
                    from models.user import user_model

                    # Get user and driver details for email
                    user = user_model.find_by_id(order.get("user_id"))
                    driver_id = order.get("driver_id")
                    driver_name = None

                    if driver_id:
                        driver = user_model.find_by_id(driver_id)
                        if driver:
                            driver_name = driver.get("name")

                    if user:
                        email_service.send_status_update_email(
                            user["email"], user["name"], order_id, new_status, driver_name=driver_name
                        )
                except Exception as e:
                    # Log error but don't fail status update
                    print(f"Failed to send status update email: {e}")

        return success, error

    def get_all_orders(self, limit: int = 300) -> List[Dict]:
        """Get all orders with user information (admin only)"""
        return self.order_model.get_all_orders(limit)

    def search_orders(self, search_term: str, user_id: Optional[int] = None) -> List[Dict]:
        """Search orders"""
        return self.order_model.search_orders(search_term, user_id)

    def get_order_statistics(self) -> Dict:
        """Get order statistics"""
        return self.order_model.get_order_statistics()

    # Pricing and routing methods
    def calculate_price(self, distance_km: float, pickup_addr: str = "", dropoff_addr: str = "", return_leg: bool = False) -> float:
        """Calculate transport price based on distance and addresses - returns GROSS price (including VAT)"""
        if distance_km <= 0:
            return 0.0

        # Calculate NET price first
        min_net_price = MINIMUM_ORDER_PRICE_NET
        if distance_km <= SHORT_DISTANCE_KM:
            # All short trips cost SHORT_DISTANCE_NET regardless of city pairing
            net_price = SHORT_DISTANCE_NET
            min_net_price = SHORT_DISTANCE_NET
        # Check if both addresses are in metro area
        elif self._both_in_metro(pickup_addr, dropoff_addr):
            net_price = METRO_NET
            min_net_price = MINIMUM_ORDER_PRICE_NET
        elif distance_km <= MID_KM:
            # Interpolate between short-distance baseline and mid-distance tier
            net_price = self._interpolate(distance_km, SHORT_DISTANCE_KM, SHORT_DISTANCE_NET, MID_KM, MID_NET)
            min_net_price = MINIMUM_ORDER_PRICE_NET
        elif distance_km <= LONG_KM:
            # Interpolate between mid and long distance
            net_price = self._interpolate(distance_km, MID_KM, MID_NET, LONG_KM, LONG_NET)
            min_net_price = MINIMUM_ORDER_PRICE_NET
        else:
            # Long distance: fixed rate per km
            rate_per_km = LONG_NET / LONG_KM
            net_price = distance_km * rate_per_km
            min_net_price = MINIMUM_ORDER_PRICE_NET

        # Apply return trip discount (NOTE: This feature is not currently used in the UI)
        if return_leg:
            net_price *= (1 - ROUNDTRIP_DISCOUNT)
            # Allow paluuauto discount to lower short-distance fares below the 27€ floor
            if distance_km <= SHORT_DISTANCE_KM:
                discounted_floor = SHORT_DISTANCE_NET * (1 - ROUNDTRIP_DISCOUNT)
                min_net_price = min(min_net_price, discounted_floor)

        # Enforce minimum order price (net)
        net_price = max(net_price, min_net_price)

        # Add VAT to get gross price
        gross_price = net_price * (1 + VAT_RATE)

        return round_half_up(gross_price, 2)

    def calculate_route_distance(
        self,
        pickup_addr: str,
        dropoff_addr: str,
        pickup_place_id: str = "",
        dropoff_place_id: str = ""
    ) -> float:
        """Calculate route distance using Google Directions with fallbacks."""
        try:
            route = self.get_route(pickup_addr, dropoff_addr, pickup_place_id, dropoff_place_id)
            return round(route.get("distance_km", 0.0), 1)
        except Exception as e:
            print(f"Route calculation error: {e}")

        return 0.0

    def route_km(
        self,
        pickup_addr: str,
        dropoff_addr: str,
        pickup_place_id: str = "",
        dropoff_place_id: str = ""
    ) -> float:
        """Calculate route distance - alias for calculate_route_distance"""
        route = self.get_route(
            pickup_addr,
            dropoff_addr,
            pickup_place_id,
            dropoff_place_id
        )
        distance = route.get("distance_km", 0.0)
        if distance <= 0:
            raise ValueError("Reititys ei ole saatavilla juuri nyt, yrita hetken kuluttua uudestaan")
        return distance

    def price_from_km(self, distance_km: float, pickup_addr: str = "", dropoff_addr: str = "", return_leg: bool = False) -> Tuple[float, float, float, str]:
        """Calculate price from distance - returns net, vat, gross, details"""
        gross_price = self.calculate_price(distance_km, pickup_addr, dropoff_addr, return_leg)
        net_price, vat_amount = self._split_gross_to_net_vat(gross_price)

        # Determine pricing tier for details
        if pickup_addr and dropoff_addr and self._both_in_metro(pickup_addr, dropoff_addr):
            details = "metro"
        elif distance_km <= MID_KM:
            details = "mid"
        else:
            details = "long"

        return round_half_up(net_price, 2), round_half_up(vat_amount, 2), round_half_up(gross_price, 2), details

    def get_price_quote(self, pickup_addr: str, dropoff_addr: str, return_leg: bool = False) -> Dict:
        """Get price quote for addresses"""
        distance_km = self.calculate_route_distance(pickup_addr, dropoff_addr)

        if distance_km <= 0:
            return {
                "success": False,
                "error": "Reitin laskeminen epäonnistui"
            }

        price = self.calculate_price(distance_km, pickup_addr, dropoff_addr, return_leg)

        return {
            "success": True,
            "distance_km": distance_km,
            "price_gross": price,
            "pickup_address": pickup_addr,
            "dropoff_address": dropoff_addr
        }

    # Status and translation methods
    def translate_status(self, status: str) -> str:
        """Translate order status to Finnish"""
        from utils.status_translations import translate_status
        return translate_status(status)

    def get_status_description(self, status: str) -> str:
        """Get user-friendly status description"""
        from utils.status_translations import get_status_description
        return get_status_description(status)

    def get_progress_step(self, status: str) -> int:
        """Get progress step for status (1-3)"""
        status_map = {
            "NEW": 0,
            "CONFIRMED": 1,
            "IN_TRANSIT": 2,
            "DELIVERED": 3,
            "CANCELLED": 0
        }
        return status_map.get(status, 0)

    def is_active_status(self, status: str) -> bool:
        """Check if status represents an active order"""
        return status in ["NEW", "CONFIRMED", "IN_TRANSIT"]

    # Private helper methods
    def _decode_polyline(self, polyline_str: Optional[str]) -> List[List[float]]:
        """Decode a Google polyline string into a list of [lat, lng]."""
        if not polyline_str:
            return []

        points: List[List[float]] = []
        index = 0
        lat = 0
        lng = 0
        length = len(polyline_str)

        while index < length:
            result = 0
            shift = 0

            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break

            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += delta

            result = 0
            shift = 0

            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break

            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            lng += delta

            points.append([lat / 1e5, lng / 1e5])

        return points

    def _fetch_google_route(
        self,
        origin: str,
        destination: str,
        fallback_start: List[float],
        fallback_end: List[float]
    ) -> Dict:
        """Fetch driving route from Google Directions API."""
        if not GOOGLE_PLACES_API_KEY:
            raise ValueError("Google Maps API -avain puuttuu")

        params = {
            "origin": origin,
            "destination": destination,
            "mode": "driving",
            "region": "fi",
            "language": "fi",
            "units": "metric",
            "key": GOOGLE_PLACES_API_KEY
        }

        res = requests.get(GOOGLE_DIRECTIONS_URL, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        status = data.get("status")
        if status != "OK" or not data.get("routes"):
            error_msg = data.get("error_message") or status or "Unknown error"
            raise ValueError(f"Reitin laskenta epaonnistui: {error_msg}")

        route = data["routes"][0]
        legs = route.get("legs") or []
        if not legs:
            raise ValueError("Reitti ei sisalla leg-tietoja")

        leg = legs[0]
        distance_m = (leg.get("distance") or {}).get("value")
        if distance_m is None:
            raise ValueError("Reitin etaisyystieto puuttuu")

        start_loc = leg.get("start_location") or {}
        end_loc = leg.get("end_location") or {}

        start = [
            start_loc.get("lat", fallback_start[0]),
            start_loc.get("lng", fallback_start[1])
        ]
        end = [
            end_loc.get("lat", fallback_end[0]),
            end_loc.get("lng", fallback_end[1])
        ]

        overview_polyline = (route.get("overview_polyline") or {}).get("points")
        latlngs = self._decode_polyline(overview_polyline)
        if not latlngs:
            latlngs = [start, end]

        return {
            "distance_km": distance_m / 1000.0,
            "latlngs": latlngs,
            "start": start,
            "end": end,
            "provider": "google-directions"
        }

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two points in kilometers."""
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_route(
        self,
        pickup_addr: str,
        dropoff_addr: str,
        pickup_place_id: str = "",
        dropoff_place_id: str = ""
    ) -> Dict:
        """Resolve geocodes and return route data with fallbacks."""
        pickup_coords = self._geocode_address(pickup_addr, pickup_place_id)
        dropoff_coords = self._geocode_address(dropoff_addr, dropoff_place_id)

        if not pickup_coords or not dropoff_coords:
            raise ValueError("Osoitteiden geokoodaus epaonnistui")

        lat1, lon1 = pickup_coords["lat"], pickup_coords["lng"]
        lat2, lon2 = dropoff_coords["lat"], dropoff_coords["lng"]

        origin = f"place_id:{pickup_place_id}" if pickup_place_id else f"{lat1},{lon1}"
        destination = f"place_id:{dropoff_place_id}" if dropoff_place_id else f"{lat2},{lon2}"

        try:
            return self._fetch_google_route(origin, destination, [lat1, lon1], [lat2, lon2])
        except ValueError:
            raise
        except Exception as e:
            print(f"Google Directions error: {e}")

        straight_km = self._haversine_distance(lat1, lon1, lat2, lon2)
        adjusted_km = straight_km * STRAIGHT_LINE_DISTANCE_FACTOR
        if adjusted_km <= 0:
            raise ValueError("Reititys ei ole saatavilla juuri nyt, yrita hetken kuluttua uudestaan")

        return {
            "distance_km": adjusted_km,
            "latlngs": [[lat1, lon1], [lat2, lon2]],
            "start": [lat1, lon1],
            "end": [lat2, lon2],
            "provider": "straight-line-fallback"
        }

    def _geocode_address(self, address: str, place_id: Optional[str] = None) -> Optional[Dict]:
        """Geocode address using Google Places/Geocode APIs"""
        if not GOOGLE_PLACES_API_KEY or (not address and not place_id):
            return None

        try:
            # 1) If we received a Places place_id from the UI, resolve it directly
            if place_id:
                url = "https://maps.googleapis.com/maps/api/place/details/json"
                params = {
                    "place_id": place_id,
                    "fields": "geometry/location",
                    "language": "fi",
                    "key": GOOGLE_PLACES_API_KEY
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "OK":
                    location = (
                        data.get("result", {})
                        .get("geometry", {})
                        .get("location")
                    )
                    if location:
                        return {"lat": location["lat"], "lng": location["lng"]}

            # 2) Fall back to Places Find Place for plain text addresses
            if address:
                url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
                params = {
                    "input": address,
                    "inputtype": "textquery",
                    "fields": "geometry/location",
                    "language": "fi",
                    "key": GOOGLE_PLACES_API_KEY,
                    "region": "fi"
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "OK" and data.get("candidates"):
                    location = (
                        data["candidates"][0]
                        .get("geometry", {})
                        .get("location")
                    )
                    if location:
                        return {"lat": location["lat"], "lng": location["lng"]}

                # 3) Absolute fallback to legacy Geocoding API if Places failed
                legacy_url = "https://maps.googleapis.com/maps/api/geocode/json"
                legacy_params = {
                    "address": address,
                    "key": GOOGLE_PLACES_API_KEY,
                    "region": "fi"
                }
                response = requests.get(legacy_url, params=legacy_params, timeout=10)
                response.raise_for_status()
                legacy_data = response.json()
                if legacy_data.get("status") == "OK" and legacy_data.get("results"):
                    location = legacy_data["results"][0]["geometry"]["location"]
                    return {"lat": location["lat"], "lng": location["lng"]}

        except Exception as e:
            print(f"Geocoding error: {e}")

        return None

    def _both_in_metro(self, pickup_addr: str, dropoff_addr: str) -> bool:
        """Check if both addresses are in metro area"""
        pickup_city = self._extract_city(pickup_addr)
        dropoff_city = self._extract_city(dropoff_addr)

        return (pickup_city in METRO_CITIES and dropoff_city in METRO_CITIES)

    def _extract_city(self, address: str) -> str:
        """Extract city name from address"""
        if not address:
            return ""

        # Simple city extraction logic
        address_lower = address.lower()
        for city in METRO_CITIES:
            if city in address_lower:
                return city

        return ""

    def _interpolate(self, x: float, x1: float, y1: float, x2: float, y2: float) -> float:
        """Linear interpolation between two points"""
        if x2 == x1:
            return y1
        return y1 + (y2 - y1) * (x - x1) / (x2 - x1)

    def _split_gross_to_net_vat(self, gross: float) -> Tuple[float, float]:
        """Split gross price to net and VAT"""
        net = gross / (1 + VAT_RATE)
        vat = gross - net
        return round_half_up(net, 2), round_half_up(vat, 2)

    def assign_driver_to_order(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Assign or reassign a driver to an order"""
        try:
            # Verify driver exists and is active
            from models.user import user_model
            driver = user_model.find_by_id(driver_id)

            if not driver or driver.get('role') != 'driver':
                return False, "Kuljettajaa ei löytynyt tai käyttäjä ei ole kuljettaja"

            if driver.get('status') != 'active':
                return False, "Kuljettaja ei ole aktiivinen"

            # Assign driver using order model (this changes status to ASSIGNED_TO_DRIVER)
            success, error = self.order_model.assign_driver(order_id, driver_id)

            if success:
                # Send notification emails
                try:
                    from services.email_service import email_service
                    order = self.order_model.find_by_id(order_id)
                    if order:
                        # Notify driver about assignment
                        email_service.send_driver_assignment_email(driver['email'], driver['name'], order)

                        # NOTE: Customer email removed - only admin should be notified when driver accepts
                        # Customer will be notified when admin marks status as IN_TRANSIT after verifying pickup photos
                except Exception as e:
                    print(f"Failed to send assignment emails: {e}")

            return success, error

        except Exception as e:
            return False, f"Virhe kuljettajan määrityksessä: {str(e)}"


# Global instance
order_service = OrderService()
