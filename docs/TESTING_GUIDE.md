# Driver Progress System - Comprehensive Testing Guide

## Prerequisites

### 1. Environment Setup
```bash
# Ensure .env has development mode enabled
FLASK_ENV=development
MONGODB_URI=<your-mongodb-uri>
DB_NAME=carrental
```

### 2. Run Migration
```bash
# This adds driver_progress field to all existing orders
python migrations/add_driver_progress.py

# Expected output:
# [MIGRATION] Starting driver_progress field migration...
# [OK] Order #123: Added driver_progress with X progress points
# [MIGRATION COMPLETE]
# - Migrated: X orders
# - Skipped: Y orders (already had driver_progress)
```

### 3. Start Application
```bash
python app.py

# Verify dev mode is active:
# - Output should show "Running in DEVELOPMENT mode"
# - Test drivers should be seeded automatically
```

## Test Accounts

Development mode automatically seeds test accounts:

- **Admin**: Check your SEED_ADMIN_EMAIL/.env settings
- **Test Driver 1**: kuljettaja@levoro.fi / kuljettaja123
- **Test Driver 2**: kuljettaja2@levoro.fi / kuljettaja123
- **Customer**: Create via registration or use existing

## Testing Workflow

### Test 1: Full Driver Workflow (Happy Path)

**Objective**: Verify driver proceeds through entire workflow without waiting

1. **Setup Order**
   - Login as admin
   - Create new order OR use existing NEW order
   - Set driver reward (e.g., 150.00 €)
   - Click "Vahvista ja julkaise" (status: NEW → CONFIRMED)
   - Note the order ID (e.g., #123)

2. **Assign Driver** (Optional - driver can also accept available jobs)
   - Admin panel → Order detail
   - Assign test driver (kuljettaja@levoro.fi)
   - Status changes to: ASSIGNED_TO_DRIVER

3. **Driver Login**
   - Logout from admin
   - Login as: kuljettaja@levoro.fi / kuljettaja123
   - Navigate to dashboard
   - Find assigned order #123

4. **Step 1: Accept Job** (if not assigned by admin)
   - Click "Ota työ vastaan"
   - ✅ Verify: Success message appears
   - ✅ Verify: Admin gets email (check dev inbox)

5. **Step 2: Arrive at Pickup**
   - Click "Saavuin noutopaikalle"
   - ✅ Verify: Button changes to image upload section
   - ✅ Verify: Counter shows "0/5 kuvaa (min)" in RED
   - ✅ Verify: "Vahvista noutokuvat" button is DISABLED
   - ✅ Verify: Admin email received: "Saapunut noutopaikalle"

6. **Step 3: Upload Pickup Images**
   - Upload 1st image
     - ✅ Counter updates: "1/5 kuvaa (min)" (RED)
     - ✅ Button remains DISABLED
     - ✅ NO email sent
   - Upload 2nd, 3rd, 4th images
     - ✅ Counter updates: "4/5 kuvaa (min)" (RED)
     - ✅ Button still DISABLED
   - Upload 5th image
     - ✅ Counter updates: "5/15 kuvaa" (GREEN)
     - ✅ Button ENABLES (no longer disabled, full opacity)
     - ✅ Hint text: "Valmis vahvistettavaksi!" (GREEN)

7. **Step 4: Confirm Pickup Images**
   - Click "Vahvista noutokuvat (min. 5 kuvaa)"
   - ✅ Verify: Success message appears
   - ✅ Verify: Button changes to "Aloita ajo" (NO WAITING MESSAGE!)
   - ✅ Verify: Admin email received: "lisännyt 5 noutokuvaa"

8. **Step 5: Start Transit** (NO WAITING FOR ADMIN!)
   - Click "Aloita ajo" immediately
   - ✅ Verify: Success message
   - ✅ Verify: Button changes to "Saavuin toimituspaikalle"
   - ✅ Verify: Admin email received: "aloittanut kuljetuksen"

9. **Step 6: Arrive at Delivery**
   - Click "Saavuin toimituspaikalle"
   - ✅ Verify: Button changes to delivery image upload section
   - ✅ Verify: Counter shows "0/5 kuvaa (min)" in RED
   - ✅ Verify: Admin email received: "Saapunut toimituspaikalle"

10. **Step 7: Upload Delivery Images**
    - Upload 5 delivery images (same process as pickup)
    - ✅ Counter updates after each upload
    - ✅ Button enables at 5 images

11. **Step 8: Confirm Delivery Images**
    - Click "Vahvista toimituskuvat (min. 5 kuvaa)"
    - ✅ Verify: Success message
    - ✅ Verify: Button changes to "Toimitettu" (NO WAITING!)
    - ✅ Verify: Admin email received: "lisännyt 5 toimituskuvaa"

12. **Step 9: Mark Complete** (NO WAITING FOR ADMIN!)
    - Click "Toimitettu" immediately
    - ✅ Verify: Success message
    - ✅ Verify: Completion state displayed: "Toimitus merkitty valmiiksi!"
    - ✅ Verify: "Admin käsittelee tilauksen" message
    - ✅ Verify: Admin email received: "merkinnyt toimituksen valmiiksi"

### Test 2: Dev Email System Verification

**Objective**: Verify all 6 driver progress emails are captured

1. **Open Dev Email Inbox**
   - Navigate to: `http://localhost:8000/static/dev_emails/index.html`
   - ✅ Verify: Page loads with email list

2. **Check Email Count**
   - After completing full workflow, inbox should show 6 admin emails:
     1. "Kuljettajan eteneminen - Tilaus #123" (ARRIVED_PICKUP)
     2. "Kuljettajan eteneminen - Tilaus #123" (PICKUP_IMAGES_COMPLETE)
     3. "Kuljettajan eteneminen - Tilaus #123" (STARTED_TRANSIT)
     4. "Kuljettajan eteneminen - Tilaus #123" (ARRIVED_DELIVERY)
     5. "Kuljettajan eteneminen - Tilaus #123" (DELIVERY_IMAGES_COMPLETE)
     6. "Kuljettajan eteneminen - Tilaus #123" (MARKED_COMPLETE)

3. **Verify Email Content**
   - Click each email "View Email" link
   - ✅ Check: Orange gradient header
   - ✅ Check: Event description in Finnish
   - ✅ Check: Driver name displayed
   - ✅ Check: Order route (pickup → delivery addresses)
   - ✅ Check: "Näytä tilaus admin-paneelissa" button
   - ✅ Check: Warning box: "Kuljettaja etenee itsenäisesti"

4. **Verify Email Metadata**
   - ✅ From: ZOHO_EMAIL from .env
   - ✅ To: ADMIN_EMAIL from .env (default: support@levoro.fi)
   - ✅ Subject: "[Levoro] Kuljettajan eteneminen - Tilaus #123"
   - ✅ Timestamp: Within last few minutes

### Test 3: Admin Panel Timeline

**Objective**: Verify admin sees driver progress timeline

1. **Login as Admin**
   - Navigate to order detail page for test order

2. **Check Driver Progress Section**
   - ✅ Section header: "Kuljettajan eteneminen" with clock icon
   - ✅ Timeline displays 7 items (acceptance + 6 progress steps)

3. **Verify Timeline Items**
   - ✅ Item 1: "Työ otettu vastaan" (green checkmark, always complete)
   - ✅ Item 2: "Saapunut noutopaikalle" (green if completed)
   - ✅ Item 3: "Noutokuvat vahvistettu" (shows image count: "5 kuvaa lisätty")
   - ✅ Item 4: "Kuljetus aloitettu" (green if completed)
   - ✅ Item 5: "Saapunut toimituspaikalle" (green if completed)
   - ✅ Item 6: "Toimituskuvat vahvistettu" (shows image count)
   - ✅ Item 7: "Toimitus merkitty valmiiksi" (green if completed, shows "Odottaa admin vahvistusta")

4. **Check Timestamps**
   - ✅ All completed items show Finnish timestamp (Helsinki timezone)
   - ✅ Format: "31.12.2024 14:30"

5. **Verify Waiting Message**
   - If driver hasn't marked complete:
     - ✅ Shows: "Kuljettaja jatkaa työtä itsenäisesti" (with clock icon)

### Test 4: Button Enable/Disable Logic

**Objective**: Verify image counter JavaScript works correctly

1. **Test Pickup Image Counter**
   - Start at arrive_pickup stage
   - Open browser console (F12)
   - Upload images one by one
   - ✅ Console logs: "[Driver Image Upload] Updated pickup button: X/5 images"
   - ✅ Counter updates in real-time without page reload
   - ✅ Button remains disabled until 5 images
   - ✅ Button style changes: opacity 0.5 → 1.0, cursor not-allowed → pointer

2. **Test Counter Persistence**
   - Upload 3 images
   - Refresh page
   - ✅ Counter still shows "3/5 kuvaa (min)"
   - ✅ Button still disabled

3. **Test Deletion**
   - Upload 5 images (button enabled)
   - Delete 1 image (click X on image thumbnail)
   - ✅ Counter updates: "4/5 kuvaa (min)"
   - ✅ Button disables again
   - ✅ Hint text updates: "Lataa vielä 1 kuvaa"

### Test 5: Admin Status Independence

**Objective**: Verify admin can change status without affecting driver

1. **Driver at Step 5** (started transit)
   - Driver has confirmed pickup images, started transit
   - Driver hasn't arrived at delivery yet

2. **Admin Changes Status**
   - Login as admin
   - Navigate to order detail
   - Change status to: IN_TRANSIT
   - ✅ Customer receives email: "Kuljetuksessa"

3. **Driver Continues Independently**
   - Driver clicks "Saavuin toimituspaikalle"
   - ✅ Action succeeds normally
   - ✅ Admin gets notification
   - ✅ Order status UNCHANGED (still IN_TRANSIT)
   - ✅ Driver proceeds to upload delivery images

4. **Admin Completes Order**
   - Driver marks complete
   - Admin changes status to: DELIVERED
   - ✅ Customer receives email: "Toimitettu"

### Test 6: Validation Edge Cases

**Objective**: Test error handling and edge cases

1. **Test: Confirm with <5 Images**
   - Upload only 4 pickup images
   - Try to click "Vahvista" button
   - ✅ Button should be disabled (can't click)
   - If somehow bypassed via console:
     - ✅ Server validation: "Vähintään 5 noutokuvaa vaaditaan. Nyt: 4"

2. **Test: Upload >15 Images**
   - Upload 15 pickup images
   - Try to upload 16th
   - ✅ Error: "Maksimimäärä (15) nouto kuvia saavutettu"

3. **Test: Invalid Image Format**
   - Try to upload .txt file renamed to .jpg
   - ✅ Error: "Kuvatiedosto on vioittunut tai ei kelvollinen"

4. **Test: File Too Large**
   - Try to upload 10MB image
   - ✅ Error: "Tiedosto on liian suuri (max 5MB)"

5. **Test: Concurrent Job Acceptance**
   - Open order in two driver sessions
   - Both click "Ota työ vastaan" simultaneously
   - ✅ First driver succeeds
   - ✅ Second driver gets: "Tilaus on jo otettu toiselle kuljettajalle"

### Test 7: Backward Compatibility

**Objective**: Verify old orders work with migration

1. **Check Migrated Order**
   - Find order created BEFORE migration (has old status system)
   - ✅ Order has driver_progress field
   - ✅ Progress inferred from status
   - ✅ notified=true on all items (no duplicate emails)

2. **Check Driver Access**
   - Login as driver assigned to old order
   - ✅ Job detail page loads
   - ✅ Shows appropriate button based on inferred progress
   - ✅ Driver can continue workflow

3. **Check Admin Timeline**
   - Admin views old order
   - ✅ Timeline shows inferred progress
   - ✅ Timestamps from order.updated_at or specific fields
   - ✅ Image counts accurate

## Troubleshooting

### Issue: Migration Fails

**Symptom**: `python migrations/add_driver_progress.py` crashes

**Solutions**:
1. Check MongoDB connection:
   ```bash
   # Test connection
   python -c "from models.database import db_manager; print(db_manager.db.name)"
   ```
2. Check for existing driver_progress fields:
   ```bash
   # Query MongoDB directly
   db.orders.find({"driver_progress": {$exists: true}}).count()
   ```
3. Run migration with backup first

### Issue: Dev Emails Not Saving

**Symptom**: No emails in `static/dev_emails/` folder

**Solutions**:
1. Verify FLASK_ENV:
   ```bash
   echo $FLASK_ENV  # Should output: development
   ```
2. Check folder exists:
   ```bash
   ls -la static/dev_emails/
   # Should contain: index.html, email_*.html files
   ```
3. Check application logs for email errors

### Issue: Buttons Not Enabling

**Symptom**: "Vahvista" button stays disabled even with 5+ images

**Solutions**:
1. Open browser console (F12)
2. Check for JavaScript errors
3. Verify script loaded:
   ```javascript
   // In console:
   console.log(typeof window.updateImageCounter);
   // Should output: "function"
   ```
4. Manually trigger update:
   ```javascript
   updateImageCounter('pickup', 5);
   ```

### Issue: Driver Can't Proceed

**Symptom**: "Virhe: Tämä tilaus ei ole sinulle määritetty"

**Solutions**:
1. Verify driver_id on order matches logged-in driver
2. Re-assign driver via admin panel
3. Check session hasn't expired

### Issue: Status Not Updating

**Symptom**: Admin changes status but nothing happens

**Solutions**:
1. Check browser network tab for errors
2. Verify form submits to correct URL
3. Check Flask logs for exceptions
4. Verify order exists in database
5. Check email service isn't blocking (SMTP timeout)

## Success Checklist

After completing all tests, verify:

- [ ] Migration ran successfully on all orders
- [ ] Driver completes full workflow without waiting
- [ ] All 6 admin emails received (not 10+)
- [ ] Batch emails show image counts
- [ ] Image counter updates in real-time
- [ ] Buttons enable/disable correctly
- [ ] Admin timeline displays all progress
- [ ] Status changes independent from driver progress
- [ ] Customer emails only on admin status change
- [ ] Dev email inbox shows all emails
- [ ] No JavaScript errors in console
- [ ] No Python exceptions in logs
- [ ] Backward compatible with old orders

## Performance Benchmarks

Expected timing for full driver workflow:
- Image upload (per image): <3 seconds
- Button state update: <100ms
- Email generation: <500ms
- Admin notification: <1 second
- Page load: <2 seconds
- Full workflow completion: <5 minutes (human time)

## Next Steps After Testing

1. **Production Deployment**
   - Run migration on production database
   - Set FLASK_ENV=production
   - Monitor first few orders closely

2. **User Training**
   - Brief drivers on new workflow
   - Emphasize: No waiting for admin
   - Show image counter requirement

3. **Monitoring**
   - Track email delivery rates
   - Monitor for stuck workflows
   - Check image upload success rates

4. **Documentation Updates**
   - Update user guides
   - Update driver handbook
   - Document new admin workflows
