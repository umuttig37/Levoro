"""
Order Service
Handles order business logic, pricing, and operations
"""

import os
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from models.order import order_model

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
# Minimum order price - all orders must be at least this amount (net)
MINIMUM_ORDER_PRICE_NET = 20.0

# External API configuration
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
USER_AGENT = "Umut-Autotransport-Portal/1.0 (contact: example@example.com)"


class OrderService:
    """Service for handling order operations and business logic"""

    def __init__(self):
        self.order_model = order_model

    def create_order(self, user_id: int, order_data: Dict) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Create a new order with pricing calculation"""
        try:
            # Calculate pricing if addresses are provided
            if "pickup_address" in order_data and "dropoff_address" in order_data:
                distance_km = self.calculate_route_distance(
                    order_data["pickup_address"],
                    order_data["dropoff_address"]
                )
                if distance_km > 0:
                    order_data["distance_km"] = distance_km
                    order_data["price_gross"] = self.calculate_price(
                        distance_km,
                        order_data["pickup_address"],
                        order_data["dropoff_address"],
                        order_data.get("return_leg", False)
                    )

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
        """Update order status (admin only)"""
        # Get order and user details before update for email
        order = self.order_model.find_by_id(order_id)
        if not order:
            return False, "Tilausta ei löytynyt"

        success, error = self.order_model.update_status(order_id, new_status)

        if success:
            # Send status update email
            try:
                from services.email_service import email_service
                from models.user import user_model

                # Get user details for email
                user = user_model.find_by_id(order.get("user_id"))
                if user:
                    email_service.send_status_update_email(
                        user["email"], user["name"], order_id, new_status
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
        # Check if both addresses are in metro area
        if self._both_in_metro(pickup_addr, dropoff_addr):
            net_price = METRO_NET
        elif distance_km <= MID_KM:
            # Interpolate between metro and mid-distance
            net_price = self._interpolate(distance_km, 50, METRO_NET, MID_KM, MID_NET)
        elif distance_km <= LONG_KM:
            # Interpolate between mid and long distance
            net_price = self._interpolate(distance_km, MID_KM, MID_NET, LONG_KM, LONG_NET)
        else:
            # Long distance: fixed rate per km
            rate_per_km = LONG_NET / LONG_KM
            net_price = distance_km * rate_per_km

        # Apply return trip discount (NOTE: This feature is not currently used in the UI)
        if return_leg:
            net_price *= (1 - ROUNDTRIP_DISCOUNT)

        # Enforce minimum order price (net)
        net_price = max(net_price, MINIMUM_ORDER_PRICE_NET)

        # Add VAT to get gross price
        gross_price = net_price * (1 + VAT_RATE)

        return round(gross_price, 2)

    def calculate_route_distance(self, pickup_addr: str, dropoff_addr: str) -> float:
        """Calculate route distance using OSRM API"""
        try:
            # Geocode addresses
            pickup_coords = self._geocode_address(pickup_addr)
            dropoff_coords = self._geocode_address(dropoff_addr)

            if not pickup_coords or not dropoff_coords:
                return 0.0

            # Get route from OSRM
            url = OSRM_URL.format(
                lon1=pickup_coords["lng"],
                lat1=pickup_coords["lat"],
                lon2=dropoff_coords["lng"],
                lat2=dropoff_coords["lat"]
            )

            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    # Distance is in meters, convert to kilometers
                    distance_m = data["routes"][0]["distance"]
                    return round(distance_m / 1000.0, 1)

        except Exception as e:
            print(f"Route calculation error: {e}")

        return 0.0

    def route_km(self, pickup_addr: str, dropoff_addr: str) -> float:
        """Calculate route distance - alias for calculate_route_distance"""
        distance = self.calculate_route_distance(pickup_addr, dropoff_addr)
        if distance <= 0:
            raise ValueError("Reititys ei ole saatavilla juuri nyt, yritä hetken kuluttua uudestaan")
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

        return round(net_price, 2), round(vat_amount, 2), round(gross_price, 2), details

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
    def _geocode_address(self, address: str) -> Optional[Dict]:
        """Geocode address using Google Places API"""
        if not GOOGLE_PLACES_API_KEY or not address:
            return None

        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": address,
                "key": GOOGLE_PLACES_API_KEY,
                "region": "fi"
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and data.get("results"):
                    location = data["results"][0]["geometry"]["location"]
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
        return round(net, 2), round(vat, 2)

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

            # Assign driver using order model
            success, error = self.order_model.assign_driver(order_id, driver_id)

            if success:
                # Send notification emails
                try:
                    from services.email_service import email_service
                    order = self.order_model.find_by_id(order_id)
                    if order:
                        # Notify driver about assignment
                        email_service.send_driver_assignment_email(driver['email'], driver['name'], order)

                        # Notify customer that driver has been assigned
                        user = user_model.find_by_id(order['user_id'])
                        if user:
                            email_service.send_customer_driver_assigned_email(user['email'], user['name'], order, driver)
                except Exception as e:
                    print(f"Failed to send assignment emails: {e}")

            return success, error

        except Exception as e:
            return False, f"Virhe kuljettajan määrityksessä: {str(e)}"


# Global instance
order_service = OrderService()