"""
Discount Model
Handles discount data operations and business logic for advanced pricing discounts
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from .database import BaseModel, counter_manager


class DiscountModel(BaseModel):
    """Discount model for managing pricing discounts"""

    collection_name = "discounts"

    # Discount types
    TYPE_PERCENTAGE = "percentage"           # X% off total price
    TYPE_FIXED_AMOUNT = "fixed_amount"       # €X off total
    TYPE_FREE_KILOMETERS = "free_km"         # First X km free
    TYPE_PRICE_CAP = "price_cap"             # Maximum price limit
    TYPE_CUSTOM_RATE = "custom_rate"         # Custom €/km rate
    TYPE_TIERED_PERCENTAGE = "tiered"        # Different % at thresholds

    VALID_TYPES = [
        TYPE_PERCENTAGE, TYPE_FIXED_AMOUNT, TYPE_FREE_KILOMETERS,
        TYPE_PRICE_CAP, TYPE_CUSTOM_RATE, TYPE_TIERED_PERCENTAGE
    ]

    # Discount scopes
    SCOPE_ACCOUNT = "account"       # Assigned to specific users
    SCOPE_GLOBAL = "global"         # Applies to all users automatically
    SCOPE_CODE = "code"             # Requires promo code
    SCOPE_FIRST_ORDER = "first_order"  # First order only

    VALID_SCOPES = [SCOPE_ACCOUNT, SCOPE_GLOBAL, SCOPE_CODE, SCOPE_FIRST_ORDER]

    def create_discount(self, discount_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
        """Create a new discount"""
        try:
            # Generate new discount ID
            discount_id = counter_manager.get_next_id("discounts")

            # Validate required fields
            name = discount_data.get("name", "").strip()
            discount_type = discount_data.get("type", "").strip()
            
            if not name:
                return None, "Alennuksen nimi on pakollinen"
            
            if discount_type not in self.VALID_TYPES:
                return None, f"Virheellinen alennustyyppi: {discount_type}"

            # Prepare discount document
            discount_doc = {
                "id": discount_id,
                "name": name,
                "description": discount_data.get("description", "").strip(),
                "type": discount_type,
                "value": float(discount_data.get("value", 0)),
                "scope": discount_data.get("scope", self.SCOPE_ACCOUNT),
                
                # Promo code (for SCOPE_CODE)
                "code": discount_data.get("code", "").strip().upper() or None,
                
                # Distance conditions
                "min_distance_km": float(discount_data.get("min_distance_km", 0)) if discount_data.get("min_distance_km") else None,
                "max_distance_km": float(discount_data.get("max_distance_km", 0)) if discount_data.get("max_distance_km") else None,
                
                # Price conditions
                "min_order_value": float(discount_data.get("min_order_value", 0)) if discount_data.get("min_order_value") else None,
                "max_order_value": float(discount_data.get("max_order_value", 0)) if discount_data.get("max_order_value") else None,
                
                # Route conditions (city-based)
                "allowed_pickup_cities": discount_data.get("allowed_pickup_cities", []),
                "allowed_dropoff_cities": discount_data.get("allowed_dropoff_cities", []),
                "excluded_cities": discount_data.get("excluded_cities", []),
                
                # Tiered discount configuration (for TYPE_TIERED_PERCENTAGE)
                # Format: [{"min_km": 100, "percentage": 5}, {"min_km": 200, "percentage": 10}]
                "tiers": discount_data.get("tiers", []),
                
                # Validity period
                "valid_from": discount_data.get("valid_from"),
                "valid_until": discount_data.get("valid_until"),
                
                # Usage limits
                "max_uses_total": int(discount_data.get("max_uses_total", 0)) if discount_data.get("max_uses_total") else None,
                "max_uses_per_user": int(discount_data.get("max_uses_per_user", 0)) if discount_data.get("max_uses_per_user") else None,
                "current_uses": 0,
                
                # User assignments (for SCOPE_ACCOUNT)
                "assigned_users": discount_data.get("assigned_users", []),
                
                # Stacking rules
                "stackable": bool(discount_data.get("stackable", False)),
                "priority": int(discount_data.get("priority", 10)),  # Lower = higher priority
                "hide_from_customer": bool(discount_data.get("hide_from_customer", False)),
                
                # Status
                "active": bool(discount_data.get("active", True)),
                
                # Metadata
                "created_by": discount_data.get("created_by"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            self.insert_one(discount_doc)
            return discount_doc, None

        except Exception as e:
            error_str = str(e)
            if "duplicate key error" in error_str.lower() or "E11000" in error_str:
                # Handle duplicate key - resync counter and retry
                from models.database import db_manager
                db_manager.sync_counter("discounts", "discounts", "id")
                
                discount_id = counter_manager.get_next_id("discounts")
                discount_doc["id"] = discount_id
                
                try:
                    self.insert_one(discount_doc)
                    return discount_doc, None
                except Exception as retry_error:
                    return None, f"Alennuksen luominen epäonnistui: {str(retry_error)}"
            
            return None, f"Alennuksen luominen epäonnistui: {error_str}"

    def update_discount(self, discount_id: int, update_data: Dict) -> Tuple[bool, Optional[str]]:
        """Update an existing discount"""
        try:
            discount = self.find_by_id(discount_id)
            if not discount:
                return False, "Alennusta ei löytynyt"

            # Prepare update fields
            update_fields = {
                "updated_at": datetime.now(timezone.utc)
            }

            # Allowed fields to update
            allowed_fields = [
                "name", "description", "type", "value", "scope", "code",
                "min_distance_km", "max_distance_km", "min_order_value", "max_order_value",
                "allowed_pickup_cities", "allowed_dropoff_cities", "excluded_cities",
                "tiers", "valid_from", "valid_until",
                "max_uses_total", "max_uses_per_user",
                "assigned_users", "stackable", "priority", "active", "hide_from_customer"
            ]

            for field in allowed_fields:
                if field in update_data:
                    value = update_data[field]
                    
                    # Type conversions
                    if field in ["min_distance_km", "max_distance_km", "min_order_value", "max_order_value", "value"]:
                        value = float(value) if value else None
                    elif field in ["max_uses_total", "max_uses_per_user", "priority"]:
                        value = int(value) if value else None
                    elif field in ["stackable", "active", "hide_from_customer"]:
                        value = bool(value)
                    elif field == "code" and value:
                        value = value.strip().upper()
                    elif field in ["assigned_users", "allowed_pickup_cities", "allowed_dropoff_cities", "excluded_cities", "tiers"]:
                        value = value if isinstance(value, list) else []
                    
                    update_fields[field] = value

            result = self.update_one(
                {"id": int(discount_id)},
                {"$set": update_fields}
            )

            return True, None

        except Exception as e:
            return False, f"Alennuksen päivittäminen epäonnistui: {str(e)}"

    def find_by_id(self, discount_id: int) -> Optional[Dict]:
        """Find discount by ID"""
        return self.find_one({"id": int(discount_id)})

    def find_by_code(self, code: str) -> Optional[Dict]:
        """Find discount by promo code"""
        if not code:
            return None
        return self.find_one({"code": code.strip().upper(), "active": True})

    def get_all_discounts(self, include_inactive: bool = False) -> List[Dict]:
        """Get all discounts"""
        query = {} if include_inactive else {"active": True}
        return list(self.find(query, sort=[("priority", 1), ("created_at", -1)]))

    def get_user_discounts(self, user_id: int) -> List[Dict]:
        """Get all active discounts for a specific user"""
        now = datetime.now(timezone.utc)
        
        return list(self.collection.find({
            "active": True,
            "$or": [
                {"scope": self.SCOPE_GLOBAL},
                {"scope": self.SCOPE_FIRST_ORDER},
                {"assigned_users": int(user_id)}
            ],
            "$and": [
                {"$or": [{"valid_from": None}, {"valid_from": {"$lte": now}}]},
                {"$or": [{"valid_until": None}, {"valid_until": {"$gte": now}}]}
            ]
        }).sort([("priority", 1)]))

    def get_applicable_discounts(
        self,
        user_id: Optional[int],
        distance_km: float,
        base_price: float,
        pickup_city: str = "",
        dropoff_city: str = "",
        promo_code: Optional[str] = None,
        is_first_order: bool = False
    ) -> List[Dict]:
        """Get all discounts applicable to an order"""
        now = datetime.now(timezone.utc)
        applicable = []

        # Build base query
        query = {
            "active": True,
            "$and": [
                {"$or": [{"valid_from": None}, {"valid_from": {"$lte": now}}]},
                {"$or": [{"valid_until": None}, {"valid_until": {"$gte": now}}]}
            ]
        }

        # Get all potentially applicable discounts
        all_discounts = list(self.collection.find(query).sort([("priority", 1)]))

        pickup_city_lower = pickup_city.lower().strip() if pickup_city else ""
        dropoff_city_lower = dropoff_city.lower().strip() if dropoff_city else ""

        for discount in all_discounts:
            # Check scope
            scope = discount.get("scope")
            
            if scope == self.SCOPE_ACCOUNT:
                # Must be assigned to user
                if not user_id or int(user_id) not in discount.get("assigned_users", []):
                    continue
                    
            elif scope == self.SCOPE_CODE:
                # Must match promo code
                if not promo_code or discount.get("code") != promo_code.strip().upper():
                    continue
                    
            elif scope == self.SCOPE_FIRST_ORDER:
                # Must be first order
                if not is_first_order:
                    continue
            # SCOPE_GLOBAL applies to everyone

            # Check usage limits
            max_total = discount.get("max_uses_total")
            if max_total and discount.get("current_uses", 0) >= max_total:
                continue

            # Check distance conditions
            min_km = discount.get("min_distance_km")
            max_km = discount.get("max_distance_km")
            
            if min_km and distance_km < min_km:
                continue
            if max_km and distance_km > max_km:
                continue

            # Check price conditions
            min_price = discount.get("min_order_value")
            max_price = discount.get("max_order_value")
            
            if min_price and base_price < min_price:
                continue
            if max_price and base_price > max_price:
                continue

            # Check city restrictions
            allowed_pickup = discount.get("allowed_pickup_cities", [])
            allowed_dropoff = discount.get("allowed_dropoff_cities", [])
            excluded = discount.get("excluded_cities", [])

            if allowed_pickup and pickup_city_lower not in [c.lower() for c in allowed_pickup]:
                continue
            if allowed_dropoff and dropoff_city_lower not in [c.lower() for c in allowed_dropoff]:
                continue
            if excluded:
                excluded_lower = [c.lower() for c in excluded]
                if pickup_city_lower in excluded_lower or dropoff_city_lower in excluded_lower:
                    continue

            applicable.append(discount)

        return applicable

    def assign_to_user(self, discount_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Assign a discount to a user"""
        try:
            discount = self.find_by_id(discount_id)
            if not discount:
                return False, "Alennusta ei löytynyt"

            assigned_users = discount.get("assigned_users", [])
            if int(user_id) in assigned_users:
                return True, None  # Already assigned

            result = self.update_one(
                {"id": int(discount_id)},
                {
                    "$push": {"assigned_users": int(user_id)},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            return True, None

        except Exception as e:
            return False, f"Käyttäjän lisääminen alennukseen epäonnistui: {str(e)}"

    def remove_from_user(self, discount_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Remove a discount from a user"""
        try:
            result = self.update_one(
                {"id": int(discount_id)},
                {
                    "$pull": {"assigned_users": int(user_id)},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            return True, None

        except Exception as e:
            return False, f"Käyttäjän poistaminen alennuksesta epäonnistui: {str(e)}"

    def increment_usage(self, discount_id: int, user_id: Optional[int] = None) -> bool:
        """Increment discount usage counter"""
        try:
            self.update_one(
                {"id": int(discount_id)},
                {"$inc": {"current_uses": 1}}
            )
            return True
        except Exception:
            return False

    def deactivate(self, discount_id: int) -> Tuple[bool, Optional[str]]:
        """Deactivate a discount"""
        try:
            result = self.update_one(
                {"id": int(discount_id)},
                {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}}
            )
            return True, None
        except Exception as e:
            return False, f"Alennuksen poistaminen käytöstä epäonnistui: {str(e)}"

    def activate(self, discount_id: int) -> Tuple[bool, Optional[str]]:
        """Activate a discount"""
        try:
            result = self.update_one(
                {"id": int(discount_id)},
                {"$set": {"active": True, "updated_at": datetime.now(timezone.utc)}}
            )
            return True, None
        except Exception as e:
            return False, f"Alennuksen aktivointi epäonnistui: {str(e)}"

    def get_discount_statistics(self, discount_id: int) -> Dict:
        """Get usage statistics for a discount"""
        discount = self.find_by_id(discount_id)
        if not discount:
            return {}

        # Get usage from discount_usage collection
        from .database import DatabaseManager
        usage_col = DatabaseManager().get_collection("discount_usage")
        
        usage_docs = list(usage_col.find({"discount_id": int(discount_id)}))
        
        total_saved = sum(u.get("amount_saved", 0) for u in usage_docs)
        unique_users = len(set(u.get("user_id") for u in usage_docs if u.get("user_id")))
        average_discount = total_saved / len(usage_docs) if usage_docs else 0.0

        return {
            "discount": discount,
            "total_uses": discount.get("current_uses", 0),
            "total_saved": total_saved,
            "total_discount_given": total_saved,
            "average_discount": average_discount,
            "unique_users": unique_users,
            "recent_usage": usage_docs[-10:] if usage_docs else []
        }


# Singleton instance
discount_model = DiscountModel()
