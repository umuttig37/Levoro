"""
Rating Service
Business logic for customer ratings and driver performance
"""

from typing import Optional, Dict, Tuple
from models.rating import rating_model
from models.order import order_model
from models.user import user_model


class RatingService:
    """Service for handling rating operations"""

    def can_rate_order(self, order_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user can rate this order
        
        Returns:
            Tuple[bool, Optional[str]]: (can_rate, reason)
        """
        order = order_model.find_by_id(order_id)
        
        if not order:
            return False, "Tilausta ei löytynyt"
        
        # Check if user is the order owner
        if order.get("user_id") != user_id:
            return False, "Et voi arvostella tätä tilausta"
        
        # Check if order is delivered
        if order.get("status") != "DELIVERED":
            return False, "Vain valmiit tilaukset voi arvostella"
        
        # Check if already rated
        existing = rating_model.get_order_rating(order_id)
        if existing:
            return False, "Olet jo arvostellut tämän tilauksen"
        
        return True, None

    def get_order_rating(self, order_id: int) -> Optional[Dict]:
        """Get existing rating for an order"""
        return rating_model.get_order_rating(order_id)

    def submit_rating(self, order_id: int, user_id: int, rating: int, 
                      comment: str = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Submit a rating for an order
        
        Args:
            order_id: Order to rate
            user_id: User submitting rating
            rating: 1-5 star rating
            comment: Optional text review
        """
        # Validate can rate
        can_rate, reason = self.can_rate_order(order_id, user_id)
        if not can_rate:
            return None, reason
        
        order = order_model.find_by_id(order_id)
        driver_id = order.get("driver_id")  # May be None if no driver assigned
        
        return rating_model.create_rating(
            order_id=order_id,
            customer_id=user_id,
            driver_id=driver_id,
            rating=rating,
            comment=comment
        )

    def get_driver_stats(self, driver_id: int) -> Dict:
        """Get driver performance statistics"""
        return rating_model.get_driver_performance(driver_id)

    def get_driver_reviews(self, driver_id: int, limit: int = 10) -> list:
        """Get recent reviews for a driver"""
        return rating_model.get_driver_ratings(driver_id, limit)

    def get_all_reviews_for_admin(self, status: str = None) -> list:
        """Get all reviews for admin moderation panel"""
        return rating_model.get_reviews_with_details()

    def moderate_review(self, rating_id: int, action: str, admin_id: int) -> Tuple[bool, Optional[str]]:
        """
        Moderate a review
        
        Args:
            rating_id: Rating to moderate
            action: 'approve' or 'hide'
            admin_id: Admin performing action
        """
        if action == "approve":
            new_status = rating_model.STATUS_APPROVED
        elif action == "hide":
            new_status = rating_model.STATUS_HIDDEN
        else:
            return False, "Virheellinen toiminto"
        
        return rating_model.moderate_review(rating_id, new_status, admin_id)


# Global instance
rating_service = RatingService()
