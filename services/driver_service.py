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
        """
        Driver accepts a job - only sets driver_id, does NOT change status
        Status remains CONFIRMED until admin manually changes it
        """
        # Check if order exists and is available
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("status") != order_model.STATUS_CONFIRMED:
            return False, "Tilaus ei ole saatavilla"

        if order.get("driver_id"):
            return False, "Tilaus on jo otettu toiselle kuljettajalle"

        # Assign driver to order WITHOUT changing status (status stays CONFIRMED)
        success = order_model.update_one(
            {"id": order_id},
            {
                "$set": {
                    "driver_id": driver_id,
                    "driver_progress": {},  # Initialize empty progress
                    "updated_at": datetime.now(timezone.utc)
                }
                # NOTE: Status remains CONFIRMED (admin controls customer-visible status)
            }
        )

        if not success:
            return False, "Tilauksen ottaminen epäonnistui"

        # Send admin notification about driver accepting job
        try:
            driver = user_model.find_by_id(driver_id)

            if driver:
                email_service.send_admin_driver_action_notification(
                    order_id,
                    driver["name"],
                    "JOB_ACCEPTED",  # Changed from ASSIGNED_TO_DRIVER
                    order
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def update_job_status(self, order_id: int, driver_id: int, new_status: str,
                         timestamp_field: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Update job status by driver - only notifies admin, not customer"""
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

        # Send admin notification about driver action (NOT customer)
        try:
            driver = user_model.find_by_id(driver_id)

            if driver:
                email_service.send_admin_driver_action_notification(
                    order_id,
                    driver["name"],
                    new_status,
                    order
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def driver_arrived_pickup(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver arrived at pickup location - updates progress only, NOT order status"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Update driver progress
        success, error = order_model.update_driver_progress(
            order_id,
            'arrived_at_pickup',
            {'timestamp': datetime.now(timezone.utc), 'notified': False}
        )

        if not success:
            return False, error

        # Send admin notification (will be implemented in email service)
        try:
            driver = user_model.find_by_id(driver_id)
            if driver:
                email_service.send_admin_driver_progress_notification(
                    order_id,
                    driver["name"],
                    "ARRIVED_PICKUP",
                    order
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def driver_complete_pickup_images(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver completed 5+ pickup images - updates progress, sends batch email"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Validate minimum 5 images
        meets_min, count = order_model.has_minimum_images(order_id, 'pickup', 5)
        if not meets_min:
            return False, f"Vähintään 5 noutokuvaa vaaditaan. Nyt: {count}"

        # Update driver progress
        success, error = order_model.update_driver_progress(
            order_id,
            'pickup_images_complete',
            {
                'timestamp': datetime.now(timezone.utc),
                'count': count,
                'notified': False
            }
        )

        if not success:
            return False, error

        # Send admin batch notification with image count
        try:
            driver = user_model.find_by_id(driver_id)
            if driver:
                email_service.send_admin_driver_progress_notification(
                    order_id,
                    driver["name"],
                    "PICKUP_IMAGES_COMPLETE",
                    order,
                    metadata={'count': count}
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def driver_start_transit(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver started transit - updates progress only, NO waiting for admin"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Update driver progress
        success, error = order_model.update_driver_progress(
            order_id,
            'started_transit',
            {'timestamp': datetime.now(timezone.utc), 'notified': False}
        )

        if not success:
            return False, error

        # Send admin notification
        try:
            driver = user_model.find_by_id(driver_id)
            if driver:
                email_service.send_admin_driver_progress_notification(
                    order_id,
                    driver["name"],
                    "STARTED_TRANSIT",
                    order
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def driver_arrived_delivery(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver arrived at delivery location - updates progress only"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Update driver progress
        success, error = order_model.update_driver_progress(
            order_id,
            'arrived_at_delivery',
            {'timestamp': datetime.now(timezone.utc), 'notified': False}
        )

        if not success:
            return False, error

        # Send admin notification
        try:
            driver = user_model.find_by_id(driver_id)
            if driver:
                email_service.send_admin_driver_progress_notification(
                    order_id,
                    driver["name"],
                    "ARRIVED_DELIVERY",
                    order
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def driver_complete_delivery_images(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver completed 5+ delivery images - updates progress, sends batch email"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Validate minimum 5 images
        meets_min, count = order_model.has_minimum_images(order_id, 'delivery', 5)
        if not meets_min:
            return False, f"Vähintään 5 toimituskuvaa vaaditaan. Nyt: {count}"

        # Update driver progress
        success, error = order_model.update_driver_progress(
            order_id,
            'delivery_images_complete',
            {
                'timestamp': datetime.now(timezone.utc),
                'count': count,
                'notified': False
            }
        )

        if not success:
            return False, error

        # Send admin batch notification with image count
        try:
            driver = user_model.find_by_id(driver_id)
            if driver:
                email_service.send_admin_driver_progress_notification(
                    order_id,
                    driver["name"],
                    "DELIVERY_IMAGES_COMPLETE",
                    order,
                    metadata={'count': count}
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def driver_mark_complete(self, order_id: int, driver_id: int) -> Tuple[bool, Optional[str]]:
        """Driver marked job complete - updates progress only, NO status change"""
        # Verify order belongs to driver
        order = order_model.find_by_id(order_id)
        if not order:
            return False, "Tilaus ei löytynyt"

        if order.get("driver_id") != driver_id:
            return False, "Tämä tilaus ei ole sinulle määritetty"

        # Update driver progress
        success, error = order_model.update_driver_progress(
            order_id,
            'marked_complete',
            {'timestamp': datetime.now(timezone.utc), 'notified': False}
        )

        if not success:
            return False, error

        # Send admin notification
        try:
            driver = user_model.find_by_id(driver_id)
            if driver:
                email_service.send_admin_driver_progress_notification(
                    order_id,
                    driver["name"],
                    "MARKED_COMPLETE",
                    order
                )
        except Exception as e:
            print(f"Admin notification failed: {e}")

        return True, None

    def can_add_pickup_images(self, order_id: int, driver_id: int) -> bool:
        """Check if driver can add pickup images - based on driver_progress, not status"""
        order = order_model.find_by_id(order_id)
        if not order or order.get("driver_id") != driver_id:
            return False

        # Driver can upload pickup images if they've arrived at pickup
        progress = order.get('driver_progress', {})
        return progress.get('arrived_at_pickup') is not None

    def can_add_delivery_images(self, order_id: int, driver_id: int) -> bool:
        """Check if driver can add delivery images - based on driver_progress, not status"""
        order = order_model.find_by_id(order_id)
        if not order or order.get("driver_id") != driver_id:
            return False

        # Driver can upload delivery images ONLY after arriving at delivery location
        progress = order.get('driver_progress', {})
        return progress.get('arrived_at_delivery') is not None

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