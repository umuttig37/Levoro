# Dev/Production Image Folder Separation

## Overview
Implemented environment-based image storage separation to prevent mixing development and production images in both local storage and Google Cloud Storage (GCS) buckets.

---

## Problem Solved
Previously, all images (dev and production) were stored in the same folders:
- Local: `static/uploads/orders/`
- GCS: `orders/{order_id}/{filename}`

This caused:
- Dev test images mixing with production data
- Difficulty cleaning up dev data
- Risk of accidentally affecting production images during development
- Confusion about which images are real vs test data

---

## Solution Implemented

### Environment Detection
The system now detects the environment using the `FLASK_ENV` environment variable:
- `FLASK_ENV=development` - Development mode
- `FLASK_ENV=production` or not set - Production mode

### Storage Paths

**Development Mode (`FLASK_ENV=development`):**
- Local: `static/uploads/dev/orders/{filename}`
- GCS: `dev/orders/{order_id}/{filename}`
- Image URLs: `/static/uploads/dev/orders/{filename}` (local) or GCS public URL

**Production Mode (`FLASK_ENV=production` or not set):**
- Local: `static/uploads/orders/{filename}`
- GCS: `orders/{order_id}/{filename}`
- Image URLs: `/static/uploads/orders/{filename}` (local) or GCS public URL

---

## Files Modified

### 1. services/image_service.py
**Changes:**
- Added environment detection: `IS_DEVELOPMENT = os.getenv("FLASK_ENV", "production") == "development"`
- Added environment prefix: `ENV_PREFIX = "dev/" if IS_DEVELOPMENT else ""`
- Updated `UPLOAD_FOLDER` path to include dev folder in development
- Modified GCS blob naming to include `dev/` prefix in development
- Updated local storage URLs to include dev path

**Key code:**
```python
# Environment detection
IS_DEVELOPMENT = os.getenv("FLASK_ENV", "production") == "development"
ENV_PREFIX = "dev/" if IS_DEVELOPMENT else ""

# Dynamic upload folder
upload_path_parts = ['static', 'uploads']
if IS_DEVELOPMENT:
    upload_path_parts.append('dev')
upload_path_parts.append('orders')
UPLOAD_FOLDER = os.path.join(base_path, *upload_path_parts)

# GCS blob naming
blob_name = f"{ENV_PREFIX}orders/{order_id}/{final_filename}"

# Local URL
file_path_url = f"/static/uploads/{ENV_PREFIX}orders/{final_filename}"
```

### 2. services/gcs_service.py
**Changes:**
- Added `is_development()` method to check environment
- Added `get_environment_prefix()` method to return appropriate prefix
- Added startup log showing environment mode and prefix
- Updated `extract_blob_name_from_url()` documentation to show dev examples

**Key code:**
```python
def is_development(self) -> bool:
    """Check if running in development environment"""
    return os.getenv("FLASK_ENV", "production") == "development"

def get_environment_prefix(self) -> str:
    """Get environment-based folder prefix (dev/ or empty)"""
    return "dev/" if self.is_development() else ""
```

**Startup log:**
```
GCS enabled in development mode - images will use prefix: 'dev/' (blank if production)
```

### 3. .env
**Changes:**
- Added documentation comment above `FLASK_ENV` explaining image storage impact

```bash
# Environment mode (affects image storage paths)
# - development: Images stored in static/uploads/dev/orders/ (local) or dev/orders/ (GCS)
# - production: Images stored in static/uploads/orders/ (local) or orders/ (GCS)
# This prevents mixing dev and production images
FLASK_ENV=development
```

### 4. CLAUDE.md
**Changes:**
- Updated "Image Storage Strategy" section with environment-based paths
- Added "Environment Separation" subsection
- Updated "Environment Variables" section to document `FLASK_ENV` impact

---

## Benefits

1. **Clean Separation**
   - Development images never mix with production images
   - Clear visual distinction in storage (dev/ prefix)

2. **Easy Cleanup**
   - Delete entire `dev/` folder to remove all dev images
   - No risk of accidentally deleting production images

3. **GCS Organization**
   - Clear folder structure in cloud buckets
   - Easy to identify and manage storage costs

4. **No Production Impact**
   - Production paths remain unchanged
   - Existing production images work without migration
   - Backward compatible

5. **Development Flexibility**
   - Developers can test image uploads freely
   - No need to manually separate or track dev images

---

## Usage

### For Developers (Local Development)

1. Ensure `.env` has `FLASK_ENV=development`:
```bash
FLASK_ENV=development
```

2. Start the development server:
```bash
python app.py
```

3. Upload images through the application (driver dashboard, admin panel, etc.)

4. Images will be stored in:
   - Local: `static/uploads/dev/orders/`
   - GCS: `dev/orders/{order_id}/`

5. Check startup logs for confirmation:
```
GCS enabled in development mode - images will use prefix: 'dev/' (blank if production)
```

### For Production Deployment

1. Set `FLASK_ENV=production` in production environment variables (Render, Heroku, etc.):
```bash
FLASK_ENV=production
```

2. Or simply don't set `FLASK_ENV` (defaults to production)

3. Deploy the application

4. Images will be stored in:
   - Local: `static/uploads/orders/`
   - GCS: `orders/{order_id}/`

---

## Testing Checklist

**Development Environment:**
- [ ] Set `FLASK_ENV=development` in `.env`
- [ ] Start Flask server
- [ ] Check startup logs for "development mode" message
- [ ] Upload pickup image from driver dashboard
- [ ] Verify image saved to `static/uploads/dev/orders/` (local)
- [ ] Verify GCS blob path includes `dev/` prefix (if GCS enabled)
- [ ] Verify image displays correctly in browser

**Production Environment:**
- [ ] Set `FLASK_ENV=production` or leave unset
- [ ] Deploy to production server
- [ ] Check startup logs for "production mode" message (if GCS enabled)
- [ ] Upload pickup image from driver dashboard
- [ ] Verify image saved to `static/uploads/orders/` (local)
- [ ] Verify GCS blob path has no `dev/` prefix (if GCS enabled)
- [ ] Verify image displays correctly

**Cross-Environment:**
- [ ] Verify production images (uploaded before this change) still display
- [ ] Verify image deletion works in both environments
- [ ] Test image upload in driver dashboard, admin panel
- [ ] Verify image URLs are correct in emails

---

## Backward Compatibility

### Existing Production Images
All images uploaded before this update remain accessible without any changes:
- They were stored at `orders/{order_id}/` in GCS (no prefix)
- They remain at `orders/{order_id}/` (production path is unchanged)
- No migration needed

### New Production Images
Will continue to be stored at `orders/{order_id}/` (same as before)

### Development Images
- Old dev images (if any) remain at `orders/{order_id}/`
- New dev images go to `dev/orders/{order_id}/`
- Old dev images can be manually cleaned up or left alone

---

## Folder Structure

### Local Storage

**Development:**
```
static/
  uploads/
    dev/
      orders/
        {order_id}_pickup_{uuid}.jpg
        {order_id}_delivery_{uuid}.jpg
```

**Production:**
```
static/
  uploads/
    orders/
      {order_id}_pickup_{uuid}.jpg
      {order_id}_delivery_{uuid}.jpg
```

### Google Cloud Storage

**Development:**
```
GCS Bucket: levoro-transport-images
  dev/
    orders/
      123/
        123_pickup_abc123.jpg
        123_delivery_def456.jpg
```

**Production:**
```
GCS Bucket: levoro-transport-images
  orders/
    456/
      456_pickup_xyz789.jpg
      456_delivery_uvw012.jpg
```

---

## Troubleshooting

### Images not going to dev folder
**Check:**
- `.env` file has `FLASK_ENV=development`
- Restart Flask server after changing `.env`
- Check startup logs for environment mode

### GCS images missing dev prefix
**Check:**
- `image_service.py` line 90: `blob_name = f"{ENV_PREFIX}orders/{order_id}/{final_filename}"`
- `ENV_PREFIX` should be "dev/" in development
- Check GCS service startup logs

### Images not displaying
**Check:**
- Image URL path matches storage path
- For local: URL should include `/dev/` in development
- For GCS: URL is automatically generated by GCS

### Production images not accessible after update
**This shouldn't happen** - production paths are unchanged. If it does:
- Verify `FLASK_ENV` is NOT set to "development" in production
- Check that production images are at `orders/{order_id}/` (no dev prefix)

---

## Cleanup Commands

### Remove All Dev Images (Local)
```bash
# Windows
rmdir /s /q static\uploads\dev

# Linux/Mac
rm -rf static/uploads/dev
```

### Remove All Dev Images (GCS)
Using Google Cloud Console or `gsutil`:
```bash
gsutil -m rm -r gs://levoro-transport-images/dev/
```

---

## Future Enhancements

Potential improvements for consideration:
1. Add environment indicator in UI (dev banner)
2. Add admin tool to move images between environments
3. Add automated cleanup of old dev images (e.g., older than 30 days)
4. Add storage usage metrics per environment

---

## Summary

This implementation provides a clean, automatic separation of development and production images with:
- Zero configuration needed by developers (just set FLASK_ENV)
- No migration required for existing data
- Easy cleanup of dev data
- Clear organization in storage
- Backward compatibility with existing images

The solution is production-ready and requires no changes to application code or workflows - it works automatically based on the environment variable.
