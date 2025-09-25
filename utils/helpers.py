"""
Helper functions and decorators
"""

from functools import wraps
from flask import redirect, url_for, request
from services.auth_service import auth_service


def wrap(content, user):
    """Wrap content with base layout - placeholder for now"""
    # This would render the full page layout
    # For now, return the content directly
    return content


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_logged_in, user_data, redirect_url = auth_service.require_login()
        if not is_logged_in:
            return redirect(redirect_url)
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_admin, user_data, redirect_url = auth_service.require_admin()
        if not is_admin:
            return redirect(redirect_url)
        return f(*args, **kwargs)
    return decorated_function