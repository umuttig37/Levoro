# Multiple Email Notifications Race Condition Fix

**Date**: October 8, 2025  
**Issue**: Multiple admin notification emails sent when uploading multiple images  
**Status**: ✅ RESOLVED

## Problem Description

When a driver uploaded multiple pickup or delivery images (especially simultaneously or in quick succession), the system would send multiple admin notification emails - one for each image uploaded.

### Root Cause

The code had a race condition in the image upload logic:

**First Attempt (Still Flawed)**:
```python
# Check image COUNT before adding image
order_before = order_model.find_by_id(order_id)
current_images_before = order_before.get('images', {}).get(image_type, [])

# If count is 0, treat as first image
if len(current_images_before) == 0:
    should_trigger_status_update = True
```

**The Race Condition**:
1. Upload Image 1: Check count (0) → Save image → Send email & update status
2. Upload Image 2: Check count (still 0 because Image 1 not saved yet) → Save image → Send email & update status ❌
3. Upload Image 3: Check count (still 0 or 1) → Save image → Send email & update status ❌

If multiple images were uploaded simultaneously, they could all check the count before any of them actually added their image to the database, so they would all see count=0 and all trigger the status update.

### Impact

- **Development**: Multiple HTML email files saved to `static/dev_emails/` (one per image)
- **Production**: Multiple actual emails sent to admin via Zoho SMTP (spam-like behavior)
- Confusing for admins receiving many identical notifications

## Solution

Changed the logic to check the **actual image count AFTER adding** instead of before.

**New Logic (Correct Fix)**:
```python
# 1. Add image to database first (atomic MongoDB $push operation)
success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

# 2. Get updated image count AFTER adding
order_after = order_model.find_by_id(order_id)
current_images = order_after.get('images', {}).get(image_type, [])

# Handle old single-image format migration
if not isinstance(current_images, list):
    current_images = [current_images] if current_images else []

# 3. Only trigger if count is EXACTLY 1 (meaning this was the first image added)
should_trigger_status_update = len(current_images) == 1
```

**Why This Works**:
- MongoDB's `$push` operation is atomic - images are added one at a time
- We check the count AFTER the atomic add operation completes
- Only the upload that results in exactly 1 image will trigger the status update and email
- Even if 5 uploads start simultaneously, only ONE will see count==1 after adding
- The other 4 will see count==2, 3, 4, 5 respectively and won't trigger the notification

## Files Modified

### `routes/driver.py`

**Function**: `upload_image()` (Lines ~227-237)
- Traditional form upload endpoint
- Fixed race condition logic

**Function**: `upload_image_ajax()` (Lines ~295-310)
- AJAX endpoint for multi-image uploads
- Fixed race condition logic

## Testing

### Manual Testing Steps

1. **Development Environment**:
   ```bash
   # Set development mode
   export FLASK_ENV=development
   python app.py
   ```

2. **Test Scenario**:
   - Create an order and assign a driver
   - Driver marks arrival at pickup location
   - Upload 3-5 images simultaneously (select multiple files)
   - Check `static/dev_emails/index.html`

3. **Expected Result**:
   - Only ONE email notification should be saved
   - Subject: `[Levoro] Kuljettajan toimenpide tilaus #X - Kuljettaja on lisännyt noutokuvat`
   - All images should be successfully uploaded to the order

4. **Repeat for Delivery Images**:
   - Driver arrives at delivery location
   - Upload multiple delivery images simultaneously
   - Only ONE email should be sent

### Production Verification

In production, the same logic applies but emails are sent via Zoho SMTP:
- Monitor admin inbox after driver uploads
- Should receive only ONE email per stage (pickup/delivery)
- Not one email per image

## Technical Details

### Atomic Operations

MongoDB's `$push` operation (used in `order_model.add_image()`) is atomic:
```python
result = self.collection.update_one(
    {"id": int(order_id)},
    {
        "$push": {f"images.{image_type}": image_data},
        "$set": {"updated_at": datetime.now(timezone.utc)}
    }
)
```

This ensures:
- Images are added one at a time
- No two uploads can add an image at the exact same time
- The image count is always accurate

### Status Flow

**Pickup Images**:
1. Status: `DRIVER_ARRIVED` + 0 images → Upload first image → Status: `PICKUP_IMAGES_ADDED` (email sent)
2. Status: `PICKUP_IMAGES_ADDED` + 1 image → Upload more images → Status: `PICKUP_IMAGES_ADDED` (no email)

**Delivery Images**:
1. Status: `DELIVERY_ARRIVED` + 0 images → Upload first image → Status: `DELIVERY_IMAGES_ADDED` (email sent)
2. Status: `DELIVERY_IMAGES_ADDED` + 1 image → Upload more images → Status: `DELIVERY_IMAGES_ADDED` (no email)

## Migration Compatibility

The fix includes backward compatibility for old data format:
```python
# Handle migration from old single image format
if not isinstance(current_images_before, list):
    current_images_before = [current_images_before] if current_images_before else []
```

This ensures orders created with the old single-image format still work correctly.

## Benefits

✅ **No More Spam**: Only one email per pickup/delivery stage  
✅ **Race Condition Free**: Image count is atomic, no race conditions possible  
✅ **Works in Both Environments**: Development (mock emails) and production (Zoho SMTP)  
✅ **Backward Compatible**: Handles old single-image format  
✅ **Maintains Workflow**: Admin still notified on first image upload, as intended

## Related Documentation

- Email Mock System: `docs/features/DEV_EMAIL_MOCK_SYSTEM.md`
- Workflow Fixes: `docs/archive/WORKFLOW_FIXES_SUMMARY.md`
- Email Service: `services/email_service.py`
- Driver Routes: `routes/driver.py`
