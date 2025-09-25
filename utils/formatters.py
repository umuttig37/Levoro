"""
Formatting Utilities
Date, currency, and other formatting functions
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def format_helsinki_time(dt):
    """Format datetime to Helsinki timezone string"""
    if not dt:
        return "N/A"

    try:
        # If it's already timezone-aware, convert to Helsinki time
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            helsinki_dt = dt.astimezone(ZoneInfo("Europe/Helsinki"))
        else:
            # Assume UTC and convert
            utc_dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            helsinki_dt = utc_dt.astimezone(ZoneInfo("Europe/Helsinki"))

        return helsinki_dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        # Fallback for any datetime issues
        if hasattr(dt, 'strftime'):
            return dt.strftime("%d.%m.%Y %H:%M")
        return str(dt)


def format_currency(amount, currency="EUR", locale="fi_FI"):
    """Format currency amount"""
    try:
        if currency == "EUR":
            return f"{amount:.2f} €"
        else:
            return f"{amount:.2f} {currency}"
    except (TypeError, ValueError):
        return "0.00 €"


def format_distance(distance_km):
    """Format distance in kilometers"""
    try:
        return f"{distance_km:.1f} km"
    except (TypeError, ValueError):
        return "0.0 km"


def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_names[i]}"


def truncate_text(text, max_length=100, suffix="..."):
    """Truncate text to specified length"""
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def format_phone_number(phone):
    """Format Finnish phone number"""
    if not phone:
        return ""

    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))

    # Handle different formats
    if digits.startswith('358'):
        # International format +358
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:]}"
    elif digits.startswith('0'):
        # National format 0xx
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"

    return phone  # Return as-is if unrecognized format


def format_registration_number(reg_number):
    """Format Finnish vehicle registration number"""
    if not reg_number:
        return ""

    # Remove spaces and convert to uppercase
    formatted = reg_number.replace(" ", "").upper()

    # Add hyphen if missing
    if "-" not in formatted and len(formatted) >= 5:
        # Assume format like ABC123 -> ABC-123
        letters = ""
        numbers = ""
        for char in formatted:
            if char.isalpha():
                letters += char
            elif char.isdigit():
                numbers += char

        if letters and numbers:
            formatted = f"{letters}-{numbers}"

    return formatted