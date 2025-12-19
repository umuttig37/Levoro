"""
Discount Service
Handles discount calculation and application logic
"""

import re
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from models.discount import discount_model, DiscountModel
from models.database import DatabaseManager


def round_half_up(value: float, decimals: int = 2) -> float:
    """Round using arithmetic rounding (round half up)"""
    if value is None:
        return 0.0
    decimal_value = Decimal(str(value))
    quantizer = Decimal(10) ** -decimals
    rounded = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)
    return float(rounded)


class DiscountService:
    """Service for handling discount operations and price calculations"""

    def __init__(self):
        self.discount_model = discount_model
        self.usage_collection = DatabaseManager().get_collection("discount_usage")

    # ==================== CRUD Operations ====================

    def create_discount(self, discount_data: Dict, created_by: Optional[int] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Create a new discount"""
        discount_data["created_by"] = created_by
        return self.discount_model.create_discount(discount_data)

    def update_discount(self, discount_id: int, update_data: Dict) -> Tuple[bool, Optional[str]]:
        """Update an existing discount"""
        return self.discount_model.update_discount(discount_id, update_data)

    def get_discount(self, discount_id: int) -> Optional[Dict]:
        """Get discount by ID"""
        return self.discount_model.find_by_id(discount_id)

    def get_all_discounts(self, include_inactive: bool = False) -> List[Dict]:
        """Get all discounts"""
        return self.discount_model.get_all_discounts(include_inactive)

    def deactivate_discount(self, discount_id: int) -> Tuple[bool, Optional[str]]:
        """Deactivate a discount"""
        return self.discount_model.deactivate(discount_id)

    def activate_discount(self, discount_id: int) -> Tuple[bool, Optional[str]]:
        """Activate a discount"""
        return self.discount_model.activate(discount_id)

    def validate_promo_code(self, code: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Validate a promo code"""
        if not code:
            return None, "Syötä kampanjakoodi"
        
        discount = self.discount_model.find_by_code(code)
        if not discount:
            return None, "Virheellinen kampanjakoodi"
        
        # Check if still valid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        valid_from = discount.get("valid_from")
        valid_until = discount.get("valid_until")
        
        if valid_from and valid_from > now:
            return None, "Kampanjakoodi ei ole vielä voimassa"
        
        if valid_until and valid_until < now:
            return None, "Kampanjakoodi on vanhentunut"
        
        max_uses = discount.get("max_uses_total")
        if max_uses and discount.get("current_uses", 0) >= max_uses:
            return None, "Kampanjakoodi on käytetty loppuun"
        
        return discount, None

    # ==================== User Assignment ====================

    def assign_to_user(self, discount_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Assign a discount to a user"""
        return self.discount_model.assign_to_user(discount_id, user_id)

    def remove_from_user(self, discount_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Remove a discount from a user"""
        return self.discount_model.remove_from_user(discount_id, user_id)

    def get_user_discounts(self, user_id: int) -> List[Dict]:
        """Get all discounts for a user"""
        return self.discount_model.get_user_discounts(user_id)

    # ==================== Price Calculation ====================

    def calculate_discount_amount(
        self,
        discount: Dict,
        base_net_price: float,
        distance_km: float
    ) -> float:
        """Calculate the discount amount for a single discount"""
        discount_type = discount.get("type")
        value = float(discount.get("value", 0))

        if discount_type == DiscountModel.TYPE_PERCENTAGE:
            # X% off
            return round_half_up(base_net_price * (value / 100), 2)

        elif discount_type == DiscountModel.TYPE_FIXED_AMOUNT:
            # €X off (but not more than the price)
            return min(value, base_net_price)

        elif discount_type == DiscountModel.TYPE_FREE_KILOMETERS:
            # First X km free - recalculate price without those km
            from services.order_service import order_service
            if distance_km <= value:
                # All km are free, use minimum price
                return base_net_price - 20.0  # Minimum 20€ net
            else:
                # Calculate price for reduced distance
                reduced_km = distance_km - value
                # Get price for reduced distance
                _, _, reduced_gross, _ = order_service.price_from_km(reduced_km)
                reduced_net = reduced_gross / 1.255  # Convert back to net
                discount_amount = base_net_price - reduced_net
                return max(0, round_half_up(discount_amount, 2))

        elif discount_type == DiscountModel.TYPE_PRICE_CAP:
            # Maximum price limit (net)
            if base_net_price > value:
                return round_half_up(base_net_price - value, 2)
            return 0.0

        elif discount_type == DiscountModel.TYPE_CUSTOM_RATE:
            # Custom €/km rate
            from services.order_service import order_service
            custom_net_price = distance_km * value
            custom_net_price = max(custom_net_price, 20.0)  # Minimum 20€
            discount_amount = base_net_price - custom_net_price
            return max(0, round_half_up(discount_amount, 2))

        elif discount_type == DiscountModel.TYPE_TIERED_PERCENTAGE:
            # Tiered percentage based on distance
            tiers = discount.get("tiers", [])
            if not tiers:
                return 0.0
            
            # Sort tiers by min_km descending to find the applicable tier
            sorted_tiers = sorted(tiers, key=lambda t: t.get("min_km", 0), reverse=True)
            
            for tier in sorted_tiers:
                min_km = tier.get("min_km", 0)
                percentage = tier.get("percentage", 0)
                
                if distance_km >= min_km:
                    return round_half_up(base_net_price * (percentage / 100), 2)
            
            return 0.0

        return 0.0

    def apply_discounts(
        self,
        user_id: Optional[int],
        base_net_price: float,
        distance_km: float,
        pickup_city: str = "",
        dropoff_city: str = "",
        promo_code: Optional[str] = None,
        is_first_order: bool = False
    ) -> Dict:
        """
        Apply all applicable discounts and return pricing breakdown.
        
        Returns:
            {
                "original_net": float,
                "total_discount": float,
                "final_net": float,
                "final_vat": float,
                "final_gross": float,
                "applied_discounts": [
                    {"id": int, "name": str, "type": str, "amount": float}
                ],
                "best_discount": {...} or None (if non-stackable, the best one used)
            }
        """
        VAT_RATE = 0.255  # Finnish VAT

        result = {
            "original_net": round_half_up(base_net_price, 2),
            "total_discount": 0.0,
            "final_net": round_half_up(base_net_price, 2),
            "final_vat": 0.0,
            "final_gross": 0.0,
            "applied_discounts": [],
            "best_discount": None
        }

        # Get applicable discounts
        applicable = self.discount_model.get_applicable_discounts(
            user_id=user_id,
            distance_km=distance_km,
            base_price=base_net_price,
            pickup_city=pickup_city,
            dropoff_city=dropoff_city,
            promo_code=promo_code,
            is_first_order=is_first_order
        )

        if not applicable:
            result["final_vat"] = round_half_up(base_net_price * VAT_RATE, 2)
            result["final_gross"] = round_half_up(base_net_price * (1 + VAT_RATE), 2)
            return result

        # Separate stackable and non-stackable discounts
        stackable_discounts = [d for d in applicable if d.get("stackable", False)]
        non_stackable_discounts = [d for d in applicable if not d.get("stackable", False)]

        total_discount = 0.0
        applied = []
        current_net = base_net_price

        # For non-stackable discounts, find the best one
        best_non_stackable = None
        best_non_stackable_amount = 0.0

        for discount in non_stackable_discounts:
            amount = self.calculate_discount_amount(discount, base_net_price, distance_km)
            if amount > best_non_stackable_amount:
                best_non_stackable_amount = amount
                best_non_stackable = discount

        # Apply best non-stackable discount first (if any)
        if best_non_stackable:
            current_net -= best_non_stackable_amount
            total_discount += best_non_stackable_amount
            applied.append({
                "id": best_non_stackable["id"],
                "name": best_non_stackable["name"],
                "type": best_non_stackable["type"],
                "amount": best_non_stackable_amount,
                "hide_from_customer": bool(best_non_stackable.get("hide_from_customer", False))
            })
            result["best_discount"] = best_non_stackable

        # Apply stackable discounts on top
        for discount in stackable_discounts:
            # Calculate on remaining price
            amount = self.calculate_discount_amount(discount, current_net, distance_km)
            if amount > 0:
                current_net -= amount
                total_discount += amount
                applied.append({
                    "id": discount["id"],
                    "name": discount["name"],
                    "type": discount["type"],
                    "amount": amount,
                    "hide_from_customer": bool(discount.get("hide_from_customer", False))
                })

        # Ensure minimum price (20€ net)
        current_net = max(current_net, 20.0)
        total_discount = base_net_price - current_net

        result["total_discount"] = round_half_up(total_discount, 2)
        result["final_net"] = round_half_up(current_net, 2)
        result["final_vat"] = round_half_up(current_net * VAT_RATE, 2)
        result["final_gross"] = round_half_up(current_net * (1 + VAT_RATE), 2)
        result["applied_discounts"] = applied

        return result

    def record_usage(
        self,
        discount_id: int,
        user_id: Optional[int],
        order_id: int,
        amount_saved: float
    ) -> bool:
        """Record discount usage for tracking"""
        from datetime import datetime, timezone
        
        try:
            # Record in usage collection
            self.usage_collection.insert_one({
                "discount_id": int(discount_id),
                "user_id": int(user_id) if user_id else None,
                "order_id": int(order_id),
                "amount_saved": float(amount_saved),
                "applied_at": datetime.now(timezone.utc)
            })

            # Increment usage counter
            self.discount_model.increment_usage(discount_id, user_id)

            return True
        except Exception as e:
            print(f"Failed to record discount usage: {e}")
            return False

    def get_statistics(self, discount_id: int) -> Dict:
        """Get usage statistics for a discount"""
        return self.discount_model.get_discount_statistics(discount_id)

    # ==================== Helper Methods ====================

    def extract_city_from_address(self, address: str) -> str:
        """Extract city name from a Finnish address"""
        if not address or not isinstance(address, str):
            return ""

        parts = address.split(',')

        if len(parts) >= 2:
            city_part = parts[1].strip()
            # Remove postal code (5 digits at start)
            city_match = re.sub(r'^\d{5}\s*', '', city_part)
            return city_match.strip().lower() if city_match else ""
        elif len(parts) == 1:
            match = re.search(r'\d{5}\s+([A-Za-zäöåÄÖÅ\s]+)', address)
            if match:
                return match.group(1).strip().lower()

        return ""

    def get_discount_type_label(self, discount_type: str) -> str:
        """Get Finnish label for discount type"""
        labels = {
            DiscountModel.TYPE_PERCENTAGE: "Prosenttialennus",
            DiscountModel.TYPE_FIXED_AMOUNT: "Kiinteä alennus (€)",
            DiscountModel.TYPE_FREE_KILOMETERS: "Ilmaiset kilometrit",
            DiscountModel.TYPE_PRICE_CAP: "Maksimihinta",
            DiscountModel.TYPE_CUSTOM_RATE: "Mukautettu km-hinta",
            DiscountModel.TYPE_TIERED_PERCENTAGE: "Porrastettu alennus"
        }
        return labels.get(discount_type, discount_type)

    def get_scope_label(self, scope: str) -> str:
        """Get Finnish label for discount scope"""
        labels = {
            DiscountModel.SCOPE_ACCOUNT: "Asiakaskohtainen",
            DiscountModel.SCOPE_GLOBAL: "Kaikille",
            DiscountModel.SCOPE_CODE: "Kampanjakoodi",
            DiscountModel.SCOPE_FIRST_ORDER: "Ensimmäinen tilaus"
        }
        return labels.get(scope, scope)

    def format_discount_value(self, discount: Dict) -> str:
        """Format discount value for display"""
        discount_type = discount.get("type")
        value = discount.get("value", 0)

        if discount_type == DiscountModel.TYPE_PERCENTAGE:
            return f"{value}%"
        elif discount_type == DiscountModel.TYPE_FIXED_AMOUNT:
            return f"{value:.2f} €"
        elif discount_type == DiscountModel.TYPE_FREE_KILOMETERS:
            return f"{value:.0f} km ilmaiseksi"
        elif discount_type == DiscountModel.TYPE_PRICE_CAP:
            return f"Max {value:.2f} €"
        elif discount_type == DiscountModel.TYPE_CUSTOM_RATE:
            return f"{value:.2f} €/km"
        elif discount_type == DiscountModel.TYPE_TIERED_PERCENTAGE:
            tiers = discount.get("tiers", [])
            if tiers:
                tier_strs = [f"{t.get('percentage', 0)}% yli {t.get('min_km', 0)} km" for t in tiers]
                return ", ".join(tier_strs)
            return "Porrastettu"
        
        return str(value)

    def format_conditions(self, discount: Dict) -> List[str]:
        """Format discount conditions for display"""
        conditions = []

        min_km = discount.get("min_distance_km")
        max_km = discount.get("max_distance_km")
        min_price = discount.get("min_order_value")
        max_price = discount.get("max_order_value")

        if min_km:
            conditions.append(f"Vähintään {min_km:.0f} km")
        if max_km:
            conditions.append(f"Enintään {max_km:.0f} km")
        if min_price:
            conditions.append(f"Tilaus yli {min_price:.2f} €")
        if max_price:
            conditions.append(f"Tilaus alle {max_price:.2f} €")

        allowed_pickup = discount.get("allowed_pickup_cities", [])
        allowed_dropoff = discount.get("allowed_dropoff_cities", [])
        
        if allowed_pickup:
            conditions.append(f"Nouto: {', '.join(allowed_pickup)}")
        if allowed_dropoff:
            conditions.append(f"Toimitus: {', '.join(allowed_dropoff)}")

        return conditions


# Singleton instance
discount_service = DiscountService()
