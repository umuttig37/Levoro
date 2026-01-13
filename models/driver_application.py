"""
Driver Application Model
Handles driver application data operations and business logic
"""

from datetime import datetime, timezone
from .database import BaseModel, counter_manager


class DriverApplicationModel(BaseModel):
    """Driver application model for managing driver applications"""

    collection_name = "driver_applications"

    def create_application(self, application_data):
        """Create a new driver application"""
        # Generate new application ID
        application_id = counter_manager.get_next_id("driver_applications")

        first_name = application_data.get("first_name", "").strip()
        last_name = application_data.get("last_name", "").strip()
        full_name = (application_data.get("name") or " ".join(filter(None, [first_name, last_name]))).strip()

        # Prepare application document (no password - admin creates account on approval)
        application = {
            "id": application_id,
            "first_name": first_name,
            "last_name": last_name,
            "name": full_name,
            "email": application_data.get("email", "").lower().strip(),
            "phone": application_data.get("phone", "").strip(),
            # New fields
            "birth_date": application_data.get("birth_date", "").strip(),
            "address": {
                "street": application_data.get("street_address", "").strip(),
                "postal_code": application_data.get("postal_code", "").strip(),
                "city": application_data.get("city", "").strip()
            },
            "about_me": application_data.get("about_me", "").strip(),
            "driving_experience": application_data.get("driving_experience", ""),
            "languages": application_data.get("languages", "").strip(),
            "terms_accepted": application_data.get("terms_accepted", False),
            "terms_accepted_at": datetime.now(timezone.utc) if application_data.get("terms_accepted") else None,
            # Status fields
            "status": "pending",  # pending, approved, denied
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "processed_at": None,
            "processed_by": None,
            "license_images": {
                "front": None,  # GCS blob name (e.g., "driver-licenses/1/front.jpg")
                "back": None    # GCS blob name (e.g., "driver-licenses/1/back.jpg")
            }
        }

        try:
            self.insert_one(application)
            return application, None
        except Exception as e:
            error_str = str(e)
            # Handle duplicate key error - this can happen if counter is desynced
            if "duplicate key error" in error_str.lower() or "E11000" in error_str:
                print(f"Duplicate key error for driver application ID {application_id}, forcing counter resync...")
                # Force resync counter and retry once
                from models.database import db_manager
                db_manager.sync_counter("driver_applications", "driver_applications", "id")

                # Get new ID and retry
                application_id = counter_manager.get_next_id("driver_applications")
                application["id"] = application_id

                try:
                    self.insert_one(application)
                    return application, None
                except Exception as retry_error:
                    return None, f"Hakemuksen luominen epäonnistui (retry): {str(retry_error)}"

            return None, f"Hakemuksen luominen epäonnistui: {error_str}"

    def find_by_id(self, application_id):
        """Find application by ID"""
        return self.find_one({"id": int(application_id)})

    def find_by_email(self, email):
        """Find application by email"""
        return self.find_one({"email": email.lower().strip()})

    def get_pending_applications(self):
        """Get all pending applications"""
        return self.find(
            {"status": "pending"},
            sort=[("created_at", -1)]
        )

    def get_all_applications(self, limit=100):
        """Get all applications with optional limit"""
        return self.find(
            sort=[("created_at", -1)],
            limit=limit
        )

    def approve_application(self, application_id, processed_by):
        """Approve a driver application"""
        return self.update_one(
            {"id": int(application_id)},
            {"$set": {
                "status": "approved",
                "processed_at": datetime.now(timezone.utc),
                "processed_by": processed_by,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

    def deny_application(self, application_id, processed_by):
        """Deny a driver application"""
        return self.update_one(
            {"id": int(application_id)},
            {"$set": {
                "status": "denied",
                "processed_at": datetime.now(timezone.utc),
                "processed_by": processed_by,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

    def get_application_statistics(self):
        """Get application statistics"""
        total = self.count_documents({})
        pending = self.count_documents({"status": "pending"})
        approved = self.count_documents({"status": "approved"})
        denied = self.count_documents({"status": "denied"})

        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "denied": denied
        }


# Global instance
driver_application_model = DriverApplicationModel()