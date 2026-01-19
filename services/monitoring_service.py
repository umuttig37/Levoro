"""
Monitoring Service
Centralized error logging and performance monitoring
Supports optional Sentry integration
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from functools import wraps
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('levoro')


class MonitoringService:
    """Service for error tracking and performance monitoring"""
    
    def __init__(self):
        self.sentry_enabled = False
        self.sentry_dsn = os.getenv("SENTRY_DSN")
        
        if self.sentry_dsn:
            self._init_sentry()
        else:
            logger.info("[Monitoring] Sentry not configured - using local logging only")
    
    def _init_sentry(self):
        """Initialize Sentry if configured"""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            
            sentry_sdk.init(
                dsn=self.sentry_dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.1,  # 10% of transactions for performance
                profiles_sample_rate=0.1,
                environment=os.getenv("FLASK_ENV", "production")
            )
            self.sentry_enabled = True
            logger.info("[Monitoring] Sentry initialized successfully")
        except ImportError:
            logger.warning("[Monitoring] sentry-sdk not installed - run: pip install sentry-sdk[flask]")
        except Exception as e:
            logger.error(f"[Monitoring] Sentry initialization failed: {e}")
    
    def capture_exception(self, exception: Exception, context: Dict[str, Any] = None) -> str:
        """
        Capture and log an exception
        
        Returns:
            Error ID for reference
        """
        error_id = str(uuid.uuid4())[:8]
        
        # Log locally
        logger.error(f"[{error_id}] Exception: {str(exception)}", exc_info=True)
        if context:
            logger.error(f"[{error_id}] Context: {context}")
        
        # Send to Sentry if available
        if self.sentry_enabled:
            try:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("error_id", error_id)
                    if context:
                        for key, value in context.items():
                            scope.set_extra(key, value)
                    sentry_sdk.capture_exception(exception)
            except Exception as e:
                logger.error(f"Failed to send to Sentry: {e}")
        
        return error_id
    
    def capture_message(self, message: str, level: str = "info", context: Dict[str, Any] = None):
        """Capture and log a message"""
        log_func = getattr(logger, level, logger.info)
        log_func(message)
        
        if self.sentry_enabled:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(message, level=level)
            except Exception:
                pass
    
    def log_request_time(self, endpoint: str, duration_ms: float, status_code: int):
        """Log request performance metrics"""
        if duration_ms > 1000:  # Log slow requests (> 1 second)
            logger.warning(f"Slow request: {endpoint} took {duration_ms:.0f}ms (status: {status_code})")
        elif duration_ms > 500:
            logger.info(f"Request: {endpoint} took {duration_ms:.0f}ms (status: {status_code})")
    
    def set_user_context(self, user_id: int, email: str = None, role: str = None):
        """Set user context for error tracking"""
        if self.sentry_enabled:
            try:
                import sentry_sdk
                sentry_sdk.set_user({
                    "id": str(user_id),
                    "email": email,
                    "role": role
                })
            except Exception:
                pass


def timed(name: str = None):
    """Decorator to measure function execution time"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (time.time() - start) * 1000
                func_name = name or func.__name__
                if duration > 100:  # Log if > 100ms
                    logger.info(f"[Performance] {func_name}: {duration:.0f}ms")
        return wrapper
    return decorator


# Global instance
monitoring_service = MonitoringService()
