"""
Order Model
Handles order data operations and business logic
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from .database import BaseModel, counter_manager


class OrderModel(BaseModel):
    """Order model for transport order management"""

    collection_name = "orders"

    # Order status definitions
    STATUS_NEW = "NEW"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_ASSIGNED_TO_DRIVER = "ASSIGNED_TO_DRIVER"
    STATUS_DRIVER_ARRIVED = "DRIVER_ARRIVED"
    STATUS_PICKUP_IMAGES_ADDED = "PICKUP_IMAGES_ADDED"
    STATUS_IN_TRANSIT = "IN_TRANSIT"
    STATUS_DELIVERY_ARRIVED = "DELIVERY_ARRIVED"
    STATUS_DELIVERY_IMAGES_ADDED = "DELIVERY_IMAGES_ADDED"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_CANCELLED = "CANCELLED"

    VALID_STATUSES = [
        STATUS_NEW, STATUS_CONFIRMED, STATUS_ASSIGNED_TO_DRIVER, STATUS_DRIVER_ARRIVED,
        STATUS_PICKUP_IMAGES_ADDED, STATUS_IN_TRANSIT, STATUS_DELIVERY_ARRIVED,
        STATUS_DELIVERY_IMAGES_ADDED, STATUS_DELIVERED, STATUS_CANCELLED
    ]

    # All statuses now trigger email notifications for better user experience
    NO_EMAIL_STATUSES = []

    # Driver projection - excludes customer pricing information
    DRIVER_PROJECTION = {
        "_id": 0,
        "price_gross": 0,
        "price_net": 0,
        "price_vat": 0
    }

    def create_order(self, user_id: int, order_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
        """Create a new order"""
        try:
            # Generate new order ID
            order_id = counter_manager.get_next_id("orders")

            # Prepare order document
            order_doc = {
                "id": order_id,
                "user_id": int(user_id),
                "status": self.STATUS_NEW,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                **order_data
            }

            # Ensure images structure exists
            if "images" not in order_doc:
                order_doc["images"] = {"pickup": [], "delivery": []}

            self.insert_one(order_doc)
            return order_doc, None

        except Exception as e:
            error_str = str(e)
            # Handle duplicate key error - this can happen if counter is desynced
            if "duplicate key error" in error_str.lower() or "E11000" in error_str:
                print(f"Duplicate key error for order ID {order_id}, forcing counter resync...")
                # Force resync counter and retry once
                from models.database import db_manager
                db_manager.sync_counter("orders", "orders", "id")

                # Get new ID and retry
                order_id = counter_manager.get_next_id("orders")
                order_doc["id"] = order_id

                try:
                    self.insert_one(order_doc)
                    return order_doc, None
                except Exception as retry_error:
                    return None, f"Tilauksen luominen epäonnistui (retry): {str(retry_error)}"

            return None, f"Tilauksen luominen epäonnistui: {error_str}"

    def find_by_id(self, order_id: int, user_id: Optional[int] = None, projection: Optional[Dict] = None) -> Optional[Dict]:
        """Find order by ID, optionally filtered by user"""
        filter_dict = {"id": int(order_id)}
        if user_id is not None:
            filter_dict["user_id"] = int(user_id)

        return self.find_one(filter_dict, projection=projection)

    def get_user_orders(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get all orders for a specific user"""
        return self.find(
            {"user_id": int(user_id)},
            sort=[("created_at", -1)],
            limit=limit
        )

    def get_all_orders(self, limit: int = 300) -> List[Dict]:
        """Get all orders with user information (for admin)"""
        pipeline = [
            {"$sort": {"id": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "id",
                "as": "user"
            }},
            {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0,
                "id": 1, "status": 1,
                "pickup_address": 1, "dropoff_address": 1,
                "distance_km": 1, "price_gross": 1,
                "created_at": 1, "updated_at": 1,
                "images": 1,
                "user_name": "$user.name",
                "user_email": "$user.email"
            }}
        ]
        return self.aggregate(pipeline)

    def update_status(self, order_id: int, new_status: str) -> Tuple[bool, Optional[str]]:
        """Update order status"""
        if new_status not in self.VALID_STATUSES:
            return False, f"Virheellinen tila: {new_status}"

        try:
            success = self.update_one(
                {"id": int(order_id)},
                {"$set": {
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return success, None
        except Exception as e:
            return False, f"Tilan päivitys epäonnistui: {str(e)}"

    def update_order_data(self, order_id: int, update_data: Dict, user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Update order data"""
        try:
            filter_dict = {"id": int(order_id)}
            if user_id is not None:
                filter_dict["user_id"] = int(user_id)

            # Add updated timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            success = self.update_one(filter_dict, {"$set": update_data})
            return success, None
        except Exception as e:
            return False, f"Tilauksen päivitys epäonnistui: {str(e)}"

    def add_image(self, order_id: int, image_type: str, image_data: Dict) -> Tuple[bool, Optional[str]]:
        """Add image to order using atomic MongoDB $push operation"""
        if image_type not in ["pickup", "delivery"]:
            return False, "Virheellinen kuvatyyppi"

        try:
            # First, verify order exists and check current image count
            order = self.find_by_id(order_id)
            if not order:
                return False, "Tilausta ei löytynyt"

            # Get current images for the type
            images = order.get("images", {})
            current_images = images.get(image_type, [])

            # Handle migration from old single image format
            if not isinstance(current_images, list):
                current_images = [current_images] if current_images else []

            # Check image limit (15 images per type)
            if len(current_images) >= 15:
                return False, "Maksimimäärä (15) kuvia saavutettu"

            # Set order number and timestamp for new image
            image_data["order"] = len(current_images) + 1
            image_data["uploaded_at"] = datetime.now(timezone.utc)

            # Use atomic $push to append image (safe for concurrent uploads)
            result = self.collection.update_one(
                {"id": int(order_id)},
                {
                    "$push": {f"images.{image_type}": image_data},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            return result.modified_count > 0, None

        except Exception as e:
            return False, f"Kuvan lisääminen epäonnistui: {str(e)}"

    def remove_image(self, order_id: int, image_type: str, image_id: str) -> Tuple[bool, Optional[str]]:
        """Remove image from order by ID"""
        if image_type not in ["pickup", "delivery"]:
            return False, "Virheellinen kuvatyyppi"

        try:
            # Get current order
            order = self.find_by_id(order_id)
            if not order:
                return False, "Tilausta ei löytynyt"

            # Get current images
            images = order.get("images", {})
            current_images = images.get(image_type, [])

            # Handle migration from old format
            if not isinstance(current_images, list):
                current_images = [current_images] if current_images else []

            # Find and remove image
            updated_images = [img for img in current_images if img.get("id") != image_id]

            if len(updated_images) == len(current_images):
                return False, "Kuvaa ei löytynyt"

            # Update order numbers for remaining images
            for i, img in enumerate(updated_images):
                img["order"] = i + 1

            # Update order
            success = self.update_one(
                {"id": int(order_id)},
                {"$set": {
                    f"images.{image_type}": updated_images,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

            return success, None

        except Exception as e:
            return False, f"Kuvan poistaminen epäonnistui: {str(e)}"

    def get_orders_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Get orders by status"""
        if status not in self.VALID_STATUSES:
            return []

        return self.find(
            {"status": status},
            sort=[("created_at", -1)],
            limit=limit
        )

    def get_order_statistics(self) -> Dict:
        """Get order statistics"""
        total_orders = self.count_documents()

        stats = {"total": total_orders}

        for status in self.VALID_STATUSES:
            stats[status.lower()] = self.count_documents({"status": status})

        return stats

    def search_orders(self, search_term: str, user_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
        """Search orders by address or registration number"""
        # Build search filter
        search_filter = {
            "$or": [
                {"pickup_address": {"$regex": search_term, "$options": "i"}},
                {"dropoff_address": {"$regex": search_term, "$options": "i"}},
                {"reg_number": {"$regex": search_term, "$options": "i"}}
            ]
        }

        # Add user filter if specified
        if user_id is not None:
            search_filter["user_id"] = int(user_id)

        return self.find(
            search_filter,
            sort=[("created_at", -1)],
            limit=limit
        )

    def get_recent_orders(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """Get recent orders within specified days"""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        return self.find(
            {"created_at": {"$gte": cutoff_date}},
            sort=[("created_at", -1)],
            limit=limit
        )

    def assign_driver(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Assign driver to order"""
        try:
            success = self.update_one(
                {"id": int(order_id)},
                {"$set": {
                    "driver_id": int(driver_id),
                    "status": self.STATUS_ASSIGNED_TO_DRIVER,
                    "assigned_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return success, None
        except Exception as e:
            return False, f"Kuljettajan määritys epäonnistui: {str(e)}"

    def update_driver_reward(self, order_id: int, driver_reward: float) -> Tuple[bool, Optional[str]]:
        """Update driver reward for an order"""
        try:
            if driver_reward <= 0:
                return False, "Kuskin palkkio tulee olla suurempi kuin 0"

            success = self.update_one(
                {"id": int(order_id)},
                {"$set": {
                    "driver_reward": float(driver_reward),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return success, None
        except Exception as e:
            return False, f"Palkkion päivitys epäonnistui: {str(e)}"

    def update_order_details(self, order_id: int, car_model: Optional[str] = None,
                            car_brand: Optional[str] = None, additional_info: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Update order details (car model, brand, additional info)"""
        try:
            update_fields = {"updated_at": datetime.now(timezone.utc)}

            if car_model is not None:
                update_fields["car_model"] = car_model.strip()
            if car_brand is not None:
                update_fields["car_brand"] = car_brand.strip()
            if additional_info is not None:
                update_fields["additional_info"] = additional_info.strip()

            success = self.update_one(
                {"id": int(order_id)},
                {"$set": update_fields}
            )
            return success, None
        except Exception as e:
            return False, f"Tietojen päivitys epäonnistui: {str(e)}"

    def update_driver_status(self, order_id: int, new_status: str, timestamp_field: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Update order status with optional timestamp field"""
        if new_status not in self.VALID_STATUSES:
            return False, f"Virheellinen tila: {new_status}"

        try:
            update_data = {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc)
            }

            # Add timestamp for specific actions
            if timestamp_field:
                update_data[timestamp_field] = datetime.now(timezone.utc)

            success = self.update_one(
                {"id": int(order_id)},
                {"$set": update_data}
            )
            return success, None
        except Exception as e:
            return False, f"Tilan päivitys epäonnistui: {str(e)}"

    def get_available_orders(self, limit: int = 50) -> List[Dict]:
        """Get orders available for driver assignment - requires driver_reward to be set"""
        return self.find(
            {
                "status": self.STATUS_CONFIRMED,
                "driver_id": {"$exists": False},
                "driver_reward": {"$exists": True, "$ne": None, "$gt": 0}
            },
            projection=self.DRIVER_PROJECTION,
            sort=[("created_at", 1)],  # Oldest first
            limit=limit
        )

    def get_driver_orders(self, driver_id: int, limit: int = 50) -> List[Dict]:
        """Get all orders assigned to a specific driver"""
        return self.find(
            {"driver_id": int(driver_id)},
            projection=self.DRIVER_PROJECTION,
            sort=[("created_at", -1)],
            limit=limit
        )

    def get_active_driver_orders(self, driver_id: int) -> List[Dict]:
        """Get active orders for a driver (not completed/cancelled)"""
        active_statuses = [
            self.STATUS_ASSIGNED_TO_DRIVER, self.STATUS_DRIVER_ARRIVED,
            self.STATUS_PICKUP_IMAGES_ADDED, self.STATUS_IN_TRANSIT,
            self.STATUS_DELIVERY_ARRIVED, self.STATUS_DELIVERY_IMAGES_ADDED
        ]

        return self.find(
            {
                "driver_id": int(driver_id),
                "status": {"$in": active_statuses}
            },
            projection=self.DRIVER_PROJECTION,
            sort=[("created_at", -1)]
        )

    def get_orders_with_driver_info(self, limit: int = 300) -> List[Dict]:
        """Get all orders with driver information (for admin)"""
        pipeline = [
            {"$sort": {"id": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "id",
                "as": "customer"
            }},
            {"$lookup": {
                "from": "users",
                "localField": "driver_id",
                "foreignField": "id",
                "as": "driver"
            }},
            {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$driver", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0,
                "id": 1, "status": 1,
                "pickup_address": 1, "dropoff_address": 1,
                "distance_km": 1, "price_gross": 1,
                "created_at": 1, "updated_at": 1,
                "assigned_at": 1, "arrival_time": 1,
                "pickup_started": 1, "delivery_completed": 1,
                "images": 1,
                "reg_number": 1, "winter_tires": 1,
                "pickup_date": 1, "additional_info": 1,
                # Orderer (Tilaaja) fields - from order document
                "orderer_name": 1,
                "orderer_email": 1,
                "orderer_phone": 1,
                # Customer (Asiakas) fields - from order document
                "customer_reference": 1,
                "customer_name": 1,
                "customer_phone": 1,
                "customer_email": 1,
                # Legacy fields for backward compatibility
                "user_name": "$customer.name",
                "user_email": "$customer.email",
                "email": 1, "phone": 1, "company": 1,
                # Driver information from lookup
                "driver_name": "$driver.name",
                "driver_email": "$driver.email",
                "driver_phone": "$driver.phone"
            }}
        ]
        return self.aggregate(pipeline)


# Global instance
order_model = OrderModel()