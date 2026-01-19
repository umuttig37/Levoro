"""
Simple in-memory rate limiter for low-volume endpoints.
Not production-grade (per-process only), but blocks rapid abuse.
"""

import time
from typing import Tuple

_buckets = {}


def check_rate_limit(key: str, limit: int, window_seconds: int, lockout_seconds: int = 60) -> Tuple[bool, float]:
    """
    Check whether the caller is within rate limits.

    Args:
        key: unique key per subject (e.g., IP or user+IP)
        limit: allowed attempts within window
        window_seconds: window size in seconds
        lockout_seconds: how long to block after exceeding limit

    Returns:
        (allowed: bool, retry_after: float seconds)
    """
    now = time.time()
    bucket = _buckets.get(key, {"count": 0, "start": now, "blocked_until": 0.0})

    # Still blocked?
    if bucket["blocked_until"] > now:
        return False, bucket["blocked_until"] - now

    # Reset window if expired
    if now - bucket["start"] > window_seconds:
        bucket = {"count": 0, "start": now, "blocked_until": 0.0}

    bucket["count"] += 1
    allowed = True
    retry_after = 0.0

    if bucket["count"] > limit:
        bucket["blocked_until"] = now + lockout_seconds
        allowed = False
        retry_after = lockout_seconds

    _buckets[key] = bucket
    return allowed, retry_after

