"""
Rating Model
Handles customer ratings and reviews for drivers
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from .database import BaseModel, counter_manager


class RatingModel(BaseModel):
    """Rating model for customer reviews of drivers"""

    collection_name = "ratings"

    # Rating statuses
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_HIDDEN = "hidden"

    def create_rating(self, order_id: int, customer_id: int, driver_id: int, 
                      rating: int, comment: str = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Create a new rating for an order
        
        Args:
            order_id: The order being rated
            customer_id: The customer submitting the rating
            driver_id: The driver being rated
            rating: 1-5 star rating
            comment: Optional text review
            
        Returns:
            Tuple[Optional[Dict], Optional[str]]: (rating_data, error_message)
        """
        # Validate rating value
        if not 1 <= rating <= 5:
            return None, "Arvosanan tulee olla 1-5 tähteä"

        # Check if rating already exists for this order
        existing = self.find_one({"order_id": order_id})
        if existing:
            return None, "Olet jo arvostellut tämän tilauksen"

        # Generate new rating ID
        rating_id = counter_manager.get_next_id("ratings")

        rating_data = {
            "id": rating_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "driver_id": driver_id,
            "rating": rating,
            "comment": comment.strip() if comment else None,
            "status": self.STATUS_APPROVED,  # Auto-approve by default
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        try:
            self.insert_one(rating_data)
            
            # Update driver's average rating
            self._update_driver_average(driver_id)
            
            return rating_data, None
        except Exception as e:
            return None, f"Arvostelun tallentaminen epäonnistui: {str(e)}"

    def _update_driver_average(self, driver_id: int):
        """Recalculate and update driver's average rating"""
        from models.user import user_model
        
        # Get all approved ratings for this driver
        ratings = list(self.find({
            "driver_id": driver_id,
            "status": self.STATUS_APPROVED
        }))
        
        if not ratings:
            return
        
        total = sum(r["rating"] for r in ratings)
        count = len(ratings)
        average = round(total / count, 2)
        
        # Update driver profile
        user_model.update_one(
            {"id": driver_id},
            {"$set": {
                "average_rating": average,
                "total_ratings": count,
                "rating_updated_at": datetime.now(timezone.utc)
            }}
        )

    def get_driver_ratings(self, driver_id: int, limit: int = 50) -> List[Dict]:
        """Get all ratings for a driver"""
        return list(self.find(
            {"driver_id": driver_id, "status": self.STATUS_APPROVED},
            sort=[("created_at", -1)],
            limit=limit
        ))

    def get_driver_performance(self, driver_id: int) -> Dict:
        """
        Get comprehensive driver performance stats
        
        Returns:
            Dict with average_rating, total_ratings, rating_distribution
        """
        ratings = list(self.find({
            "driver_id": driver_id,
            "status": self.STATUS_APPROVED
        }))
        
        if not ratings:
            return {
                "average_rating": 0,
                "total_ratings": 0,
                "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }
        
        total = sum(r["rating"] for r in ratings)
        count = len(ratings)
        
        # Calculate distribution
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in ratings:
            distribution[r["rating"]] += 1
        
        return {
            "average_rating": round(total / count, 2),
            "total_ratings": count,
            "distribution": distribution
        }

    def get_order_rating(self, order_id: int) -> Optional[Dict]:
        """Get rating for a specific order"""
        return self.find_one({"order_id": order_id})

    def get_all_reviews(self, status: str = None, limit: int = 100) -> List[Dict]:
        """Get all reviews with optional status filter (for admin)"""
        query = {}
        if status:
            query["status"] = status
        
        return list(self.find(
            query,
            sort=[("created_at", -1)],
            limit=limit
        ))

    def moderate_review(self, rating_id: int, new_status: str, admin_id: int) -> Tuple[bool, Optional[str]]:
        """
        Moderate a review (approve/hide)
        
        Args:
            rating_id: Rating to moderate
            new_status: New status (approved/hidden)
            admin_id: Admin performing the action
        """
        if new_status not in [self.STATUS_APPROVED, self.STATUS_HIDDEN]:
            return False, "Virheellinen tila"

        rating = self.find_one({"id": rating_id})
        if not rating:
            return False, "Arvostelua ei löytynyt"

        old_status = rating.get("status")
        
        success = self.update_one(
            {"id": rating_id},
            {"$set": {
                "status": new_status,
                "moderated_by": admin_id,
                "moderated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        if success:
            # Recalculate driver average if visibility changed
            if old_status != new_status:
                self._update_driver_average(rating["driver_id"])
            return True, None
        
        return False, "Moderointi epäonnistui"

    def get_reviews_with_details(self, limit: int = 100) -> List[Dict]:
        """Get reviews with customer and driver info (for admin)"""
        from models.user import user_model
        from models.order import order_model
        
        reviews = list(self.find(sort=[("created_at", -1)], limit=limit))
        
        # Enrich with user info
        for review in reviews:
            customer = user_model.find_by_id(review["customer_id"]) if review.get("customer_id") else None
            driver = user_model.find_by_id(review["driver_id"]) if review.get("driver_id") else None
            order = order_model.find_by_id(review["order_id"]) if review.get("order_id") else None
            
            review["customer_name"] = customer.get("name") if customer else "Tuntematon"
            review["driver_name"] = driver.get("name") if driver else "Ei kuljettajaa"
            review["order_reg_number"] = order.get("reg_number") if order else "-"
        
        return reviews


# Global instance
rating_model = RatingModel()
