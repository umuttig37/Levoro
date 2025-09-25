"""
Authentication Service
Handles user authentication, session management, and authorization
"""

from typing import Optional, Dict, Tuple
from flask import session, request
from models.user import user_model


class AuthService:
    """Service for handling authentication and authorization"""

    def __init__(self):
        self.user_model = user_model

    def login(self, email: str, password: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Authenticate user and create session

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]: (success, user_data, error_message)
        """
        user, error = self.user_model.authenticate(email, password)

        if error:
            return False, None, error

        # Create session (using existing session key format)
        session["uid"] = user["id"]
        session["user_email"] = user["email"]
        session["user_role"] = user["role"]

        return True, user, None

    def logout(self) -> None:
        """Clear user session"""
        session.clear()

    def register(self, email: str, password: str, name: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Register a new user

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]: (success, user_data, error_message)
        """
        # Validate input
        if not self._validate_registration_data(email, password, name):
            return False, None, "Tarkista tiedot"

        user, error = self.user_model.create_user(email, password, name)

        # Send registration email if user was created successfully
        if user is not None and error is None:
            try:
                from services.email_service import email_service
                email_service.send_registration_email(user["email"], user["name"])
            except Exception as e:
                # Log error but don't fail registration
                print(f"Failed to send registration email: {e}")

        return user is not None, user, error

    def get_current_user(self) -> Optional[Dict]:
        """Get current logged-in user from session"""
        user_id = session.get("uid")
        if not user_id:
            return None

        return self.user_model.find_by_id(user_id)

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return "uid" in session

    def is_admin(self, user: Optional[Dict] = None) -> bool:
        """Check if current user or provided user is admin"""
        if user is None:
            user = self.get_current_user()

        return user is not None and user.get("role") == "admin"

    def require_login(self) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Require user to be logged in

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]: (is_logged_in, user_data, redirect_url)
        """
        user = self.get_current_user()
        if not user:
            # Build redirect URL
            next_url = request.url if request.method == "GET" else None
            redirect_url = f"/login{f'?next={next_url}' if next_url else ''}"
            return False, None, redirect_url

        return True, user, None

    def require_admin(self) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Require user to be admin

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]: (is_admin, user_data, redirect_url)
        """
        is_logged_in, user, redirect_url = self.require_login()
        if not is_logged_in:
            return False, None, redirect_url

        if not self.is_admin(user):
            return False, user, "/login"

        return True, user, None

    def approve_user(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Approve a pending user (admin only)"""
        # Get user details before approval for email
        user = self.user_model.find_by_id(user_id)
        if not user:
            return False, "Käyttäjää ei löytynyt"

        success = self.user_model.approve_user(user_id)
        if success:
            # Send approval email
            try:
                from services.email_service import email_service
                email_service.send_account_approved_email(user["email"], user["name"])
            except Exception as e:
                # Log error but don't fail approval
                print(f"Failed to send account approved email: {e}")

            return True, None
        return False, "Käyttäjän hyväksyminen epäonnistui"

    def deny_user(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Deny a pending user (admin only)"""
        success = self.user_model.deny_user(user_id)
        if success:
            return True, None
        return False, "Käyttäjän hylkääminen epäonnistui"

    def get_pending_users(self) -> list:
        """Get all users pending approval (admin only)"""
        return self.user_model.get_pending_users()

    def update_profile(self, user_id: int, name: str = None, email: str = None) -> Tuple[bool, Optional[str]]:
        """Update user profile"""
        success, error = self.user_model.update_user_profile(user_id, name, email)

        # Update session if email changed
        if success and email and session.get("uid") == user_id:
            session["user_email"] = email

        return success, error

    def change_password(self, user_id: int, current_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """Change user password"""
        if not self._validate_password(new_password):
            return False, "Salasana on liian heikko"

        return self.user_model.change_password(user_id, current_password, new_password)

    def _validate_registration_data(self, email: str, password: str, name: str) -> bool:
        """Validate registration data"""
        # Basic validation
        if not email or not password or not name:
            return False

        if len(email.strip()) < 5 or "@" not in email:
            return False

        if len(password) < 6:
            return False

        if len(name.strip()) < 2:
            return False

        return True

    def _validate_password(self, password: str) -> bool:
        """Validate password strength"""
        if len(password) < 6:
            return False

        # Could add more complexity requirements here
        return True


# Global instance
auth_service = AuthService()