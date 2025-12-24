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

    def generate_reset_token(self, email):
        """Generate password reset token for user"""
        import secrets
        from datetime import timedelta
        
        user = self.find_by_email(email)
        if not user:
            return None, "Käyttäjää ei löytynyt"
        
        # Generate secure token
        reset_token = secrets.token_urlsafe(32)
        reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=2)
        
        # Save token to database
        success = self.update_one(
            {"id": user["id"]},
            {"$set": {
                "reset_token": reset_token,
                "reset_token_expires": reset_token_expires,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        if not success:
            return None, "Token luominen epäonnistui"
        
        return reset_token, None
    
    def validate_reset_token(self, token):
        """Validate password reset token"""
        user = self.find_one({"reset_token": token})
        
        if not user:
            return None, "Virheellinen tai vanhentunut linkki"
        
        # Check if token has expired
        if user.get("reset_token_expires"):
            expires = user["reset_token_expires"]
            # Ensure timezone awareness for comparison
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            
            if expires < datetime.now(timezone.utc):
                return None, "Linkki on vanhentunut. Pyydä uusi salasanan palautuslinkki."
        
        return user, None
    
    def reset_password_with_token(self, token, new_password):
        """Reset password using valid token"""
        user, error = self.validate_reset_token(token)
        
        if error:
            return False, error
        
        # Update password and clear reset token
        success = self.update_one(
            {"id": user["id"]},
            {"$set": {
                "password_hash": generate_password_hash(new_password),
                "updated_at": datetime.now(timezone.utc)
            },
            "$unset": {
                "reset_token": "",
                "reset_token_expires": ""
            }}
        )
        
        if not success:
            return False, "Salasanan vaihto epäonnistui"
        
        return True, None

    def create_user(self, email, password, name, role="user", phone=None):
        """Create a new user"""
        # Check if user already exists
        if self.find_by_email(email):
            return None, "Sähköposti on jo käytössä"

        # Check if a driver application exists with this email (prevent duplicates)
        if role != "driver":  # Only check for non-driver registrations
            from models.driver_application import driver_application_model
            existing_application = driver_application_model.find_by_email(email)
            if existing_application and existing_application.get('status') == 'pending':
                return None, "Sähköpostiosoite on jo käytössä kuljettajahakemuksessa. Odota hakemuksen käsittelyä tai ota yhteyttä tukeen."

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
            error_str = str(e)
            # Handle duplicate key error - this can happen if counter is desynced
            if "duplicate key error" in error_str.lower() or "E11000" in error_str:
                print(f"Duplicate key error for user ID {user_id}, forcing counter resync...")
                # Force resync counter and retry once
                from models.database import db_manager
                db_manager.sync_counter("users", "users", "id")

                # Get new ID and retry
                user_id = counter_manager.get_next_id("users")
                user_data["id"] = user_id

                try:
                    self.insert_one(user_data)
                    return user_data, None
                except Exception as retry_error:
                    return None, f"Käyttäjän luominen epäonnistui (retry): {str(retry_error)}"

            return None, f"Käyttäjän luominen epäonnistui: {error_str}"

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

    def update_driver_rating(self, driver_id, average_rating, total_ratings):
        """Update driver's average rating and total ratings count"""
        return self.update_one(
            {"id": int(driver_id)},
            {"$set": {
                "average_rating": round(average_rating, 2),
                "total_ratings": total_ratings,
                "rating_updated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )

    def get_driver_rating(self, driver_id):
        """Get driver's rating information"""
        driver = self.find_by_id(driver_id)
        if not driver:
            return None
        return {
            "average_rating": driver.get("average_rating", 0.0),
            "total_ratings": driver.get("total_ratings", 0),
            "rating_updated_at": driver.get("rating_updated_at")
        }

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