"""
User Model
Handles user data operations and business logic
"""

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from .database import BaseModel, counter_manager


class UserModel(BaseModel):
    """User model for authentication and user management"""

    collection_name = "users"

    def create_user(self, email, password, name, role="user", phone=None):
        """Create a new user"""
        # Check if user already exists
        if self.find_by_email(email):
            return None, "Sähköposti on jo käytössä"

        # Generate new user ID
        user_id = counter_manager.get_next_id("users")

        # Create user document
        user_data = {
            "id": user_id,
            "email": email.lower().strip(),
            "password_hash": generate_password_hash(password),
            "name": name.strip(),
            "role": role,
            "phone": phone.strip() if phone else None,
            "status": "pending" if role == "user" else "active",
            "terms_accepted": False if role == "driver" else True,  # Drivers must accept terms
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        try:
            self.insert_one(user_data)
            return user_data, None
        except Exception as e:
            return None, f"Käyttäjän luominen epäonnistui: {str(e)}"

    def find_by_email(self, email):
        """Find user by email"""
        return self.find_one({"email": email.lower().strip()})

    def find_by_id(self, user_id):
        """Find user by ID"""
        return self.find_one({"id": int(user_id)})

    def authenticate(self, email, password):
        """Authenticate user with email and password"""
        user = self.find_by_email(email)
        if not user:
            return None, "Käyttäjää ei löytynyt"

        if not check_password_hash(user["password_hash"], password):
            return None, "Väärä salasana"

        if user.get("status") != "active":
            return None, "Käyttäjätili ei ole vielä aktivoitu"

        # Update last login
        self.update_last_login(user["id"])
        return user, None

    def update_last_login(self, user_id):
        """Update user's last login timestamp"""
        return self.update_one(
            {"id": int(user_id)},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )

    def update_phone(self, user_id, phone):
        """Update user's phone number"""
        return self.update_one(
            {"id": int(user_id)},
            {"$set": {
                "phone": phone.strip() if phone else None,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

    def approve_user(self, user_id):
        """Approve a pending user"""
        return self.update_one(
            {"id": int(user_id)},
            {"$set": {
                "status": "active",
                "updated_at": datetime.now(timezone.utc)
            }}
        )

    def deny_user(self, user_id):
        """Deny a pending user"""
        return self.delete_one({"id": int(user_id)})

    def get_pending_users(self):
        """Get all users pending approval"""
        return self.find(
            {"status": "pending"},
            sort=[("created_at", -1)]
        )

    def get_all_users(self, limit=100):
        """Get all users with optional limit"""
        return self.find(
            projection={"password_hash": 0},  # Exclude password hash
            sort=[("created_at", -1)],
            limit=limit
        )

    def update_user_profile(self, user_id, name=None, email=None):
        """Update user profile information"""
        update_data = {"updated_at": datetime.now(timezone.utc)}

        if name:
            update_data["name"] = name.strip()
        if email:
            # Check if email is already taken by another user
            existing_user = self.find_by_email(email)
            if existing_user and existing_user["id"] != int(user_id):
                return False, "Sähköposti on jo käytössä"
            update_data["email"] = email.lower().strip()

        try:
            success = self.update_one(
                {"id": int(user_id)},
                {"$set": update_data}
            )
            return success, None
        except Exception as e:
            return False, f"Päivitys epäonnistui: {str(e)}"

    def change_password(self, user_id, current_password, new_password):
        """Change user password"""
        user = self.find_by_id(user_id)
        if not user:
            return False, "Käyttäjää ei löytynyt"

        if not check_password_hash(user["password_hash"], current_password):
            return False, "Nykyinen salasana on väärä"

        # Update password
        success = self.update_one(
            {"id": int(user_id)},
            {"$set": {
                "password_hash": generate_password_hash(new_password),
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        return success, None if success else "Salasanan vaihto epäonnistui"

    def is_admin(self, user_id):
        """Check if user is admin"""
        user = self.find_by_id(user_id)
        return user and user.get("role") == "admin"

    def is_driver(self, user_id):
        """Check if user is driver"""
        user = self.find_by_id(user_id)
        return user and user.get("role") == "driver"

    def create_driver(self, email, password, name):
        """Create a new driver user"""
        return self.create_user(email, password, name, role="driver")

    def get_all_drivers(self, limit=100):
        """Get all active drivers"""
        return self.find(
            {"role": "driver", "status": "active"},
            projection={"password_hash": 0},
            sort=[("name", 1)],
            limit=limit
        )

    def get_driver_stats(self):
        """Get driver statistics"""
        total_drivers = self.count_documents({"role": "driver"})
        active_drivers = self.count_documents({"role": "driver", "status": "active"})
        pending_drivers = self.count_documents({"role": "driver", "status": "pending"})

        return {
            "total": total_drivers,
            "active": active_drivers,
            "pending": pending_drivers
        }

    def accept_terms(self, user_id):
        """Mark that driver has accepted terms and conditions"""
        return self.update_one(
            {"id": int(user_id)},
            {"$set": {
                "terms_accepted": True,
                "terms_accepted_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )

    def get_user_stats(self):
        """Get user statistics"""
        total_users = self.count_documents()
        pending_users = self.count_documents({"status": "pending"})
        active_users = self.count_documents({"status": "active"})
        admin_users = self.count_documents({"role": "admin"})
        driver_users = self.count_documents({"role": "driver"})
        customer_users = self.count_documents({"role": {"$in": ["user", "customer"]}})

        return {
            "total": total_users,
            "pending": pending_users,
            "active": active_users,
            "admins": admin_users,
            "drivers": driver_users,
            "customers": customer_users
        }


# Global instance
user_model = UserModel()