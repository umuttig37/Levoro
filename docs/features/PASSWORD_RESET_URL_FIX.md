# Password Reset Email URL Fix

**Date**: October 8, 2025  
**Issue**: Password reset emails showing localhost URL in production  
**Status**: ✅ Fixed

## Problem

Password reset emails were showing incorrect URLs in production environments:

```
Vaihtoehtoinen tapa
Jos painike ei toimi, kopioi ja liitä alla oleva linkki selaimeesi:

http://127.0.0.1:8000/reset-password/gkGoAXinV4YC7tYHhBnM25A7Gqz5CbGcP8hpifT1FHg
```

**Expected**: `https://levoro.onrender.com/reset-password/...`  
**Actual**: `http://127.0.0.1:8000/reset-password/...`

This made password reset completely non-functional in production since users couldn't access localhost URLs.

## Root Cause

The code in `services/auth_service.py` was using Flask's `url_for()` function to generate the reset URL:

```python
# OLD CODE - INCORRECT
from flask import url_for
reset_url = url_for('auth.reset_password', token=token, _external=True)
```

### Why This Failed

`url_for()` with `_external=True` generates URLs based on the **request context**:

1. **In development**: Request comes from browser → `http://localhost:8000` → URL correct ✅
2. **In production**: Request might come from:
   - Internal proxy → `http://127.0.0.1:8000` → URL wrong ❌
   - Load balancer → Internal IP → URL wrong ❌
   - Reverse proxy → Can have various internal addresses → URL wrong ❌

The request context doesn't always match the public-facing URL in production environments, especially with:
- **Render.com** hosting (uses internal routing)
- **Heroku** dynos (uses internal network)
- **Docker** containers (uses internal container IPs)
- **Nginx** reverse proxies (forwards from internal ports)

## Solution

Changed to use the `BASE_URL` environment variable, matching the pattern used by all other email templates:

```python
# NEW CODE - CORRECT
import os
base_url = os.getenv("BASE_URL", "http://localhost:8000")
reset_url = f"{base_url}/reset-password/{token}"
```

### Why This Works

1. **Environment-aware**: Uses `BASE_URL` set in `.env` file
2. **Consistent**: Same approach as all other email notifications
3. **Production-safe**: `BASE_URL` is explicitly set to production domain
4. **Fallback**: Defaults to `http://localhost:8000` for local development

## Code Changes

### File: `services/auth_service.py`

**Before:**
```python
def request_password_reset(self, email: str) -> Tuple[bool, Optional[str]]:
    """Request password reset - generates token and sends email"""
    # Generate reset token
    token, error = self.user_model.generate_reset_token(email)
    
    if error:
        return True, None
    
    # Send password reset email
    try:
        from services.email_service import email_service
        from flask import url_for
        
        user = self.user_model.find_by_email(email)
        if user:
            # Generate reset URL
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            email_service.send_password_reset_email(user["email"], user["name"], reset_url, token)
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
    
    return True, None
```

**After:**
```python
def request_password_reset(self, email: str) -> Tuple[bool, Optional[str]]:
    """Request password reset - generates token and sends email"""
    # Generate reset token
    token, error = self.user_model.generate_reset_token(email)
    
    if error:
        return True, None
    
    # Send password reset email
    try:
        from services.email_service import email_service
        import os
        
        user = self.user_model.find_by_email(email)
        if user:
            # Generate reset URL using BASE_URL to ensure correct domain in production
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            reset_url = f"{base_url}/reset-password/{token}"
            email_service.send_password_reset_email(user["email"], user["name"], reset_url, token)
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
    
    return True, None
```

**Changes:**
1. ❌ Removed: `from flask import url_for`
2. ✅ Added: `import os`
3. ✅ Changed: URL generation from `url_for()` to `f"{base_url}/reset-password/{token}"`
4. ✅ Added: Comment explaining the fix

## Environment Configuration

### Development (.env)
```properties
FLASK_ENV=development
BASE_URL=http://localhost:8000
```

### Production (.env)
```properties
FLASK_ENV=production
BASE_URL=https://levoro.onrender.com
```

Or on Render.com, set as environment variable:
```
BASE_URL=https://levoro.onrender.com
```

## Consistency with Other Email Templates

This fix brings password reset emails in line with all other email notification URLs:

### Admin Driver Action Notification
```python
# services/email_service.py - line 276
base_url = os.getenv("BASE_URL", "http://localhost:3000")
admin_url = f"{base_url}/admin"
order_detail_url = f"{base_url}/admin/order/{order_data.get('id')}"
```

### Admin User Approval Notification
```python
# services/email_service.py - line 309
base_url = os.getenv("BASE_URL", "http://localhost:3000")
admin_users_url = f"{base_url}/admin/users"
user_detail_url = f"{base_url}/admin/user/{user_data.get('id')}"
```

### Driver Application Notification
```python
# services/email_service.py - line 367
base_url = os.getenv('BASE_URL', 'http://localhost:3000')
application_url = f"{base_url}/admin/driver-applications/{application['id']}"
```

### Driver Order Assignments
```python
# services/email_service.py - line 435
<a href="{os.getenv('BASE_URL', 'http://localhost:3000')}/driver/job/{order_data.get('id')}"
```

### Customer Order Links
```python
# services/email_service.py - line 502
<a href="{os.getenv('BASE_URL', 'http://localhost:3000')}/order/{order_data.get('id')}"
```

All email templates now consistently use `BASE_URL` environment variable! ✅

## Testing

### Manual Testing

1. **Development Environment:**
   ```bash
   # In .env
   BASE_URL=http://localhost:8000
   
   # Test password reset
   python test_password_reset.py
   
   # Check dev_emails/index.html
   # URL should be: http://localhost:8000/reset-password/...
   ```

2. **Production Environment:**
   ```bash
   # Set on Render.com dashboard
   BASE_URL=https://levoro.onrender.com
   
   # Request password reset via UI
   # Check email
   # URL should be: https://levoro.onrender.com/reset-password/...
   ```

### Expected Results

**Development:**
```
Vaihtoehtoinen tapa
Jos painike ei toimi, kopioi ja liitä alla oleva linkki selaimeesi:

http://localhost:8000/reset-password/ABC123TOKEN...
```

**Production:**
```
Vaihtoehtoinen tapa
Jos painike ei toimi, kopioi ja liitä alla oleva linkki selaimeesi:

https://levoro.onrender.com/reset-password/ABC123TOKEN...
```

### Test Checklist

- [x] Code changed in `auth_service.py`
- [x] Uses `BASE_URL` environment variable
- [x] Falls back to `http://localhost:8000` if not set
- [x] Matches pattern used in other email templates
- [ ] **TODO**: Test in development - verify localhost URL
- [ ] **TODO**: Test in production - verify production domain URL
- [ ] **TODO**: Verify email link works (can click and reset password)
- [ ] **TODO**: Verify token validation still works

## Related Files

- **Email Template**: `templates/emails/password_reset.html` (uses `{{ reset_url }}` variable)
- **Route Handler**: `routes/auth.py` - `reset_password()` route (handles `/reset-password/<token>`)
- **Token Generation**: `models/user.py` - `generate_reset_token()` (creates token)
- **Token Validation**: `models/user.py` - `validate_reset_token()` (verifies token)
- **Password Reset**: `models/user.py` - `reset_password_with_token()` (updates password)

## Benefits

✅ **Production Functionality**: Users can now actually reset passwords in production  
✅ **Environment Awareness**: Correct URLs for dev/staging/production  
✅ **Consistency**: All emails now use same URL generation pattern  
✅ **Maintainability**: Easy to update production domain (just change `BASE_URL`)  
✅ **Security**: No internal IPs exposed in user-facing emails  
✅ **Debugging**: Clear environment variable makes issues easy to diagnose  

## Deployment Checklist

When deploying to production:

1. ✅ Ensure `BASE_URL` environment variable is set on hosting platform
2. ✅ Set to public-facing domain (e.g., `https://levoro.onrender.com`)
3. ✅ Do NOT include trailing slash
4. ✅ Use `https://` in production (not `http://`)
5. ✅ Restart application after environment variable change
6. ✅ Test password reset flow end-to-end
7. ✅ Verify email contains correct production URL

## Why Not Use `url_for()` for Other Emails?

You might wonder why we don't use `url_for()` for other email links either. The answer:

**Problem**: `url_for()` only works within a **request context**
- ✅ Works: When handling a web request (route handler)
- ❌ Fails: In background jobs, scheduled tasks, CLI commands, or when request context is unreliable

**Email sending often happens outside request context:**
- Cron jobs sending reminder emails
- Background workers processing queues
- Admin scripts sending bulk notifications
- Scheduled reports

**Solution**: Always use explicit `BASE_URL` environment variable for:
- Email links
- Webhook callbacks
- API endpoints shared externally
- Any URL that leaves the application

**When `url_for()` IS appropriate:**
- Template rendering during request handling
- Redirects in route handlers
- Internal navigation links
- Form action attributes

## Alternative Solutions Considered

### Option 1: Configure Flask `SERVER_NAME`
```python
# app.py
app.config['SERVER_NAME'] = 'levoro.onrender.com'
```

**Rejected because:**
- ❌ Affects ALL routing, not just emails
- ❌ Can break local development
- ❌ Doesn't work well with proxies/load balancers
- ❌ Causes CORS issues in some browsers

### Option 2: Trust Proxy Headers
```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
```

**Rejected because:**
- ❌ Relies on proxy configuration (can be unreliable)
- ❌ Security risk if misconfigured
- ❌ Still might not work with all hosting platforms
- ❌ More complex than just using `BASE_URL`

### Option 3: Use Environment Variable ✅ CHOSEN
```python
base_url = os.getenv("BASE_URL", "http://localhost:8000")
reset_url = f"{base_url}/reset-password/{token}"
```

**Chosen because:**
- ✅ Simple and explicit
- ✅ Works in all environments
- ✅ Easy to configure per environment
- ✅ Consistent with existing codebase
- ✅ No dependencies on Flask internals
- ✅ Clear and maintainable

## Notes

- The password reset token is still valid for 2 hours (configured in `user.py`)
- Token can only be used once (marked as used after successful reset)
- Security: Email timing attacks prevented by always returning success message
- The email template (`password_reset.html`) didn't need changes - it just uses `{{ reset_url }}`
- This fix applies to ALL environments (development, staging, production)

## Future Improvements

1. **Add URL validation**: Ensure `BASE_URL` is set and valid at application startup
2. **Log warnings**: Alert if `BASE_URL` is not configured in production
3. **Health check**: Include BASE_URL in `/health` endpoint for monitoring
4. **Documentation**: Add BASE_URL to required environment variables in README
