"""
Driver Service
Handles driver-related business logic and operations
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from flask import session
from models.user import user_model
from models.order import order_model
from services.email_service import email_service


class DriverService:
    """Service layer for driver operations"""

    def get_current_driver(self) -> Optional[Dict]:
        """Get current logged-in driver"""
        user_id = session.get("user_id")
        if not user_id:
            return None

        user = user_model.find_by_id(user_id)
        if not user or user.get("role") != "driver":
            return None

        return user

    def is_driver_logged_in(self) -> bool:
        """Check if a driver is currently logged in"""
        return self.get_current_driver() is not None

    def get_available_jobs(self, limit: int = 50) -> List[Dict]:
        """Get jobs available for driver assignment"""
        return order_model.get_available_orders(limit)

    def get_driver_jobs(self, driver_id: int, limit: int = 50) -> List[Dict]:
        """Get all jobs assigned to a driver"""
        return order_model.get_driver_orders(driver_id, limit)

    def get_active_driver_jobs(self, driver_id: int) -> List[Dict]:
        """Get active jobs for a driver"""
        return order_model.get_active_driver_orders(driver_id)

    def accept_job(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver accepts a job"""
        # Check if order exists and is available
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("status") != order_model.STATUS_CONFIRMED:
            return False, "Tilaus ei ole saatavilla"

        if order.get("driver_id"):
            return False, "Tilaus on jo otettu toiselle kuljettajalle"

        # Assign driver to order
        success, error = order_model.assign_driver(order_id, driver_id)
        if not success:
            return False, error

        # Send notification email to customer
        try:
            driver = user_model.find_by_id(driver_id)
            customer = user_model.find_by_id(order["user_id"])

            if customer and driver:
                email_service.send_status_update_email(
                    customer["email"],
                    customer["name"],
                    order_id,
                    "ASSIGNED_TO_DRIVER",
                    driver_name=driver["name"]
                )
        except Exception as e:
            print(f"Email notification failed: {e}")

        return True, None

    def update_job_status(self, order_id: int, driver_id: int, new_status: str,
                         timestamp_field: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Update job status by driver"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Update status
        success, error = order_model.update_driver_status(order_id, new_status, timestamp_field)
        if not success:
            return False, error

        # Send email notification to customer for all status changes
        try:
            customer = user_model.find_by_id(order["user_id"])
            driver = user_model.find_by_id(driver_id)

            if customer and driver:
                email_service.send_status_update_email(
                    customer["email"],
                    customer["name"],
                    order_id,
                    new_status,
                    driver_name=driver["name"]
                )
        except Exception as e:
            print(f"Email notification failed: {e}")

        return True, None

    def mark_arrival(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Mark driver arrival at pickup location"""
        return self.update_job_status(
            order_id, driver_id,
            order_model.STATUS_DRIVER_ARRIVED,
            "arrival_time"
        )

    def start_transport(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Start transport after pickup images are added"""
        # Verify pickup images are added
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("status") != order_model.STATUS_PICKUP_IMAGES_ADDED:
            return False, "Lisää ensin noutokuvat ennen kuljetuksen aloittamista"

        return self.update_job_status(
            order_id, driver_id,
            order_model.STATUS_IN_TRANSIT,
            "pickup_started"
        )

    def arrive_at_delivery(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Mark arrival at delivery location"""
        return self.update_job_status(
            order_id, driver_id,
            order_model.STATUS_DELIVERY_ARRIVED,
            "delivery_arrival_time"
        )

    def complete_delivery(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Complete delivery after delivery images are added"""
        # Verify delivery images are added
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("status") != order_model.STATUS_DELIVERY_IMAGES_ADDED:
            return False, "Lisää ensin toimituskuvat ennen toimituksen päättämistä"

        return self.update_job_status(
            order_id, driver_id,
            order_model.STATUS_DELIVERED,
            "delivery_completed"
        )

    def can_add_pickup_images(self, order_id: int, driver_id: int) -> bool:
        """Check if driver can add pickup images"""
        order = order_model.find_by_id(order_id)
        if not order or order.get("driver_id") != driver_id:
            return False

        return order.get("status") in [order_model.STATUS_DRIVER_ARRIVED, order_model.STATUS_PICKUP_IMAGES_ADDED]

    def can_add_delivery_images(self, order_id: int, driver_id: int) -> bool:
        """Check if driver can add delivery images"""
        order = order_model.find_by_id(order_id)
        if not order or order.get("driver_id") != driver_id:
            return False

        return order.get("status") in [order_model.STATUS_DELIVERY_ARRIVED, order_model.STATUS_DELIVERY_IMAGES_ADDED]

    def update_pickup_images_status(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Update status after pickup images are added"""
        return self.update_job_status(
            order_id, driver_id,
            order_model.STATUS_PICKUP_IMAGES_ADDED
        )

    def update_delivery_images_status(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Update status after delivery images are added"""
        return self.update_job_status(
            order_id, driver_id,
            order_model.STATUS_DELIVERY_IMAGES_ADDED
        )

    def get_driver_statistics(self, driver_id: int) -> Dict:
        """Get statistics for a specific driver"""
        all_orders = order_model.get_driver_orders(driver_id, limit=1000)

        total_jobs = len(all_orders)
        completed_jobs = len([o for o in all_orders if o.get("status") == order_model.STATUS_DELIVERED])
        active_jobs = len(order_model.get_active_driver_orders(driver_id))

        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "active_jobs": active_jobs
        }

    def get_all_drivers(self) -> List[Dict]:
        """Get all active drivers for admin"""
        return user_model.get_all_drivers()

    def get_driver_performance_data(self) -> List[Dict]:
        """Get performance data for all drivers (admin view)"""
        drivers = self.get_all_drivers()
        performance_data = []

        for driver in drivers:
            stats = self.get_driver_statistics(driver["id"])
            performance_data.append({
                **driver,
                **stats
            })

        return performance_data

    def approve_driver_application(self, application_id: int) -> Tuple[bool, Optional[str]]:
        """Approve driver application and create driver account"""
        try:
            from models.driver_application import driver_application_model
            from services.auth_service import auth_service

            # Get application
            application = driver_application_model.find_by_id(application_id)
            if not application:
                return False, "Hakemusta ei löytynyt"

            if application.get('status') != 'pending':
                return False, "Hakemus on jo käsitelty"

            # Check if user already exists
            existing_user = user_model.find_by_email(application['email'])
            if existing_user:
                # If user exists and is a driver, application may have been approved before
                if existing_user.get('role') == 'driver':
                    print(f"Driver account already exists for {application['email']}, marking application as approved")
                    driver_application_model.approve_application(application_id, session.get('user_id', 0))
                    return True, None
                else:
                    return False, f"Sähköposti on jo käytössä ({existing_user.get('role')} tili)"

            # Generate new user ID
            from models.database import counter_manager
            user_id = counter_manager.get_next_id("users")

            # Create driver user document directly with already-hashed password
            user_data = {
                "id": user_id,
                "email": application['email'].lower().strip(),
                "password_hash": application['password_hash'],  # Already hashed, don't hash again
                "name": application['name'].strip(),
                "role": "driver",
                "phone": application.get('phone', '').strip() if application.get('phone') else None,
                "status": "active",
                "terms_accepted": False,  # Driver must accept terms on first login
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            # Insert user directly
            user_created = False
            try:
                user_model.insert_one(user_data)
                user_created = True
                print(f"✓ Driver account created for {application['email']} (User ID: {user_id})")
            except Exception as e:
                print(f"✗ CRITICAL: Failed to create driver account for application #{application_id}: {str(e)}")
                return False, f"Kuljettajatilin luominen epäonnistui: {str(e)}"

            # ONLY mark application as approved if user creation succeeded
            if user_created:
                try:
                    driver_application_model.approve_application(application_id, session.get('user_id', 0))
                    print(f"✓ Application #{application_id} marked as approved")
                except Exception as e:
                    print(f"✗ WARNING: User created but failed to mark application as approved: {str(e)}")
                    # User exists but application not marked - this is recoverable
                    # The integrity check script will detect this

            # Send approval email
            try:
                email_service.send_driver_application_approved(
                    application['email'],
                    application['name']
                )
            except Exception as e:
                print(f"Failed to send approval email: {e}")
                # Don't fail the approval if email fails

            return True, None

        except Exception as e:
            print(f"✗ CRITICAL ERROR in approve_driver_application: {str(e)}")
            return False, f"Virhe hakemuksen käsittelyssä: {str(e)}"


# Global service instance
driver_service = DriverService()