"""
Driver Application Model
Handles driver application data operations and business logic
"""

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
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

        # Prepare application document
        application = {
            "id": application_id,
            "first_name": first_name,
            "last_name": last_name,
            "name": full_name,
            "email": application_data.get("email", "").lower().strip(),
            "phone": application_data.get("phone", "").strip(),
            "password_hash": generate_password_hash(application_data.get("password", "")),
            "status": "pending",  # pending, approved, denied
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "processed_at": None,
            "processed_by": None
        }

        try:
            self.insert_one(application)
            return application, None
        except Exception as e:
            return None, f"Hakemuksen luominen epäonnistui: {str(e)}"

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