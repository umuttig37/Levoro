# Email Notification Testing Guidelines

## Overview
This document provides comprehensive testing procedures for the updated email notification system. The system has been refactored to ensure customers receive emails only for key order statuses, while admins are notified of all driver actions.

---

## Changes Implemented

### Customer Email Behavior
**Customers receive emails ONLY for these 4 statuses:**
1. `CONFIRMED` - Order received/confirmed
2. `ASSIGNED_TO_DRIVER` - Driver assigned to order
3. `IN_TRANSIT` - Transport started
4. `DELIVERED` - Order delivered

**Customers DO NOT receive emails for:**
- `DRIVER_ARRIVED` - Driver arrived at pickup
- `PICKUP_IMAGES_ADDED` - Pickup images uploaded
- `DELIVERY_ARRIVED` - Driver arrived at delivery location
- `DELIVERY_IMAGES_ADDED` - Delivery images uploaded

### Admin Email Behavior
**Admin (support@levoro.fi) receives notifications for:**
- All driver actions (arrived, started transport, image uploads, etc.)
- New orders
- New user registrations
- Driver applications

---

## Test Scenarios

### 1. Order Creation Flow

**Test Steps:**
1. Log in as customer
2. Create a new order through the order wizard
3. Complete all 6 steps and submit

**Expected Results:**
- Customer receives: "Tilausvahvistus" email (order created)
- Admin receives: "Uusi tilaus" notification email
- Order status: `NEW`

**Files Modified:**
- `order_wizard.py:289` - calls `order_service.create_order()`
- `services/order_service.py:86-102` - sends customer and admin emails

---

### 2. Admin Confirms Order

**Test Steps:**
1. Log in as admin
2. Navigate to admin dashboard
3. Click "Vahvista tilaus" button for a NEW order

**Expected Results:**
- Customer receives: "Tilaus vahvistettu" email
- Order status: `CONFIRMED`
- Order becomes visible to drivers

**Files Modified:**
- `routes/admin.py:676` - calls `order_service.update_order_status()`
- `services/order_service.py:117-159` - filters emails by status

---

### 3. Driver Accepts Job

**Test Steps:**
1. Log in as driver
2. View available jobs
3. Click "Ota tehtävä" to accept a job

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Tilaus määritetty kuljettajalle" email
- Driver receives: "Uusi tehtävä" assignment email
- Order status: `ASSIGNED_TO_DRIVER`

**Files Modified:**
- `routes/driver.py:118-131` - calls `driver_service.accept_job()`
- `services/driver_service.py:45-77` - sends admin notification instead of customer email

**IMPORTANT:** This is a critical test - verify customer does NOT receive an email when driver accepts.

---

### 4. Admin Assigns Driver Manually

**Test Steps:**
1. Log in as admin
2. Open order detail page
3. Select driver from dropdown
4. Click "Määritä kuljettaja"

**Expected Results:**
- Customer receives: "Kuljettaja määritetty" email (includes driver name and phone)
- Driver receives: "Uusi tehtävä" assignment email
- Order status: `ASSIGNED_TO_DRIVER`

**Files Modified:**
- `routes/admin.py:640-657` - calls `order_service.assign_driver_to_order()`
- `services/order_service.py:365-400` - sends customer and driver emails

---

### 5. Driver Arrives at Pickup Location

**Test Steps:**
1. Log in as driver
2. Open assigned job
3. Click "Saavuin" button

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Kuljettaja on saapunut noutopaikalle" email
- Order status: `DRIVER_ARRIVED`

**Files Modified:**
- `routes/driver.py:134-147` - calls `driver_service.mark_arrival()`
- `services/driver_service.py:113-121` - calls `update_job_status()` which sends admin notification

---

### 6. Driver Uploads Pickup Images

**Test Steps:**
1. Log in as driver
2. Open job (status must be DRIVER_ARRIVED)
3. Upload 1-3 pickup images

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Kuljettaja on lisännyt noutokuvat" email
- Order status: `PICKUP_IMAGES_ADDED` (after first image)

**Files Modified:**
- `routes/driver.py:198-262` - image upload endpoint
- `services/driver_service.py:179-184` - updates status after first image
- Status update triggers admin notification via `update_job_status()`

---

### 7. Driver Starts Transport

**Test Steps:**
1. Log in as driver
2. Open job (must have pickup images uploaded)
3. Click "Aloita kuljetus" button

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Kuljettaja on aloittanut kuljetuksen" email
- Order status: `IN_TRANSIT`

**Files Modified:**
- `routes/driver.py:150-163` - calls `driver_service.start_transport()`
- `services/driver_service.py:123-137` - sends admin notification

**IMPORTANT:** Customer does NOT receive email when driver starts. They only get email when admin changes status to IN_TRANSIT.

---

### 8. Admin Changes Status to IN_TRANSIT

**Test Steps:**
1. Log in as admin
2. Open order detail
3. Change status to "IN_TRANSIT" from dropdown
4. Submit status update

**Expected Results:**
- Customer receives: "Kuljetuksessa" status update email
- Order status: `IN_TRANSIT`

**Files Modified:**
- `routes/admin.py:359-381` - calls `order_service.update_order_status()`
- `services/order_service.py:117-159` - sends customer email because IN_TRANSIT is in CUSTOMER_EMAIL_STATUSES

---

### 9. Driver Arrives at Delivery Location

**Test Steps:**
1. Log in as driver
2. Open job (status must be IN_TRANSIT)
3. Click "Saavuin toimitusosoitteeseen" button

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Kuljettaja on saapunut toimituspaikalle" email
- Order status: `DELIVERY_ARRIVED`

**Files Modified:**
- `routes/driver.py:166-179` - calls `driver_service.arrive_at_delivery()`
- `services/driver_service.py:139-145` - sends admin notification

---

### 10. Driver Uploads Delivery Images

**Test Steps:**
1. Log in as driver
2. Open job (status must be DELIVERY_ARRIVED)
3. Upload 1-3 delivery images

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Kuljettaja on lisännyt toimituskuvat" email
- Order status: `DELIVERY_IMAGES_ADDED` (after first image)

**Files Modified:**
- `routes/driver.py:198-262` - image upload endpoint
- `services/driver_service.py:186-191` - updates status after first image

---

### 11. Driver Completes Delivery

**Test Steps:**
1. Log in as driver
2. Open job (must have delivery images uploaded)
3. Click "Päätä toimitus" button

**Expected Results:**
- **Customer receives: NO EMAIL**
- Admin receives: "Kuljettajan toimenpide - Kuljettaja on merkinnyt toimituksen valmiiksi" email
- Order status: `DELIVERED`

**Files Modified:**
- `routes/driver.py:182-195` - calls `driver_service.complete_delivery()`
- `services/driver_service.py:147-161` - sends admin notification

**IMPORTANT:** Customer does NOT receive email when driver completes. They only get email when admin confirms DELIVERED status.

---

### 12. Admin Changes Status to DELIVERED

**Test Steps:**
1. Log in as admin
2. Open order detail
3. Change status to "DELIVERED" from dropdown
4. Submit status update

**Expected Results:**
- Customer receives: "Toimitettu" status update email
- Order status: `DELIVERED`

**Files Modified:**
- `routes/admin.py:359-381` - calls `order_service.update_order_status()`
- `services/order_service.py:117-159` - sends customer email because DELIVERED is in CUSTOMER_EMAIL_STATUSES

---

## Email Content Verification

### Customer Emails to Check

1. **Order Created** (`send_order_created_email`)
   - Subject: "Tilausvahvistus #[ORDER_ID] - Levoro"
   - Contains: pickup/dropoff addresses, price, order ID
   - Template: `templates/emails/order_created.html`

2. **Order Confirmed** (`send_status_update_email` with status=CONFIRMED)
   - Subject: "Tilaus #[ORDER_ID] - Vahvistettu"
   - Contains: confirmation message
   - Template: `templates/emails/status_update.html`

3. **Driver Assigned** (`send_customer_driver_assigned_email`)
   - Subject: "Kuljettaja määritetty tilaukselle #[ORDER_ID] - Levoro"
   - Contains: driver name, driver phone, order details
   - Inline HTML (services/email_service.py:440-490)

4. **In Transit** (`send_status_update_email` with status=IN_TRANSIT)
   - Subject: "Tilaus #[ORDER_ID] - Kuljetuksessa"
   - Contains: transit status, driver name
   - Template: `templates/emails/status_update.html`

5. **Delivered** (`send_status_update_email` with status=DELIVERED)
   - Subject: "Tilaus #[ORDER_ID] - Toimitettu"
   - Contains: delivery confirmation
   - Template: `templates/emails/status_update.html`

### Admin Emails to Check

1. **New Order** (`send_admin_new_order_notification`)
   - Subject: "[Levoro] Uusi tilaus #[ORDER_ID] - Vahvistus tarvitaan"
   - Contains: order details, customer info, admin panel link
   - Template: `templates/emails/admin_new_order.html`

2. **Driver Action** (`send_admin_driver_action_notification`)
   - Subject: "[Levoro] Kuljettajan toimenpide tilaus #[ORDER_ID] - [ACTION]"
   - Contains: driver name, action description, order details, admin link
   - Inline HTML (services/email_service.py:546-598)

---

## Test Environment Setup

### Prerequisites
1. Email service configured with valid SMTP credentials
2. Environment variables set:
   - `ADMIN_EMAIL=support@levoro.fi` (or test admin email)
   - `BASE_URL` (for email links)
   - Zoho SMTP settings configured

### Test Users Required
1. **Admin account**
   - Email: support@levoro.fi (or test admin email)
   - Role: admin

2. **Customer account**
   - Email: customer@test.com (use real email for testing)
   - Role: customer

3. **Driver account**
   - Email: driver@test.com (use real email for testing)
   - Role: driver
   - Terms accepted: true

### Email Testing Tool
- Use a real email account or email testing service (e.g., Mailtrap, Gmail)
- Verify emails arrive in correct inboxes
- Check email formatting and links

---

## Regression Testing Checklist

After implementing changes, verify:

- [ ] Customer receives exactly 4 types of emails (created, confirmed, assigned, in transit, delivered)
- [ ] Customer does NOT receive emails for driver intermediate actions
- [ ] Admin receives notifications for all driver actions
- [ ] Email subjects are correct and professional
- [ ] Email content is properly formatted (no broken HTML)
- [ ] Links in emails work correctly (admin panel, order detail pages)
- [ ] Driver receives assignment email when assigned by admin
- [ ] No duplicate emails are sent
- [ ] Email logging appears in console during development
- [ ] SMTP errors are handled gracefully (don't break order flow)

---

## Code Reference

### Key Files Modified

1. **services/email_service.py**
   - Added: `send_admin_driver_action_notification()` (line 520-608)
   - Maps driver actions to Finnish descriptions
   - Sends formatted HTML email to admin

2. **services/driver_service.py**
   - Modified: `accept_job()` (line 45-77) - removed customer email, added admin notification
   - Modified: `update_job_status()` (line 81-111) - removed customer email, added admin notification
   - All driver status updates now notify admin only

3. **services/order_service.py**
   - Modified: `update_order_status()` (line 117-159) - added CUSTOMER_EMAIL_STATUSES filter
   - Only sends customer emails for: CONFIRMED, ASSIGNED_TO_DRIVER, IN_TRANSIT, DELIVERED
   - Modified: `assign_driver_to_order()` (line 365-400) - added comment clarifying customer notification

4. **models/order.py**
   - Status definitions remain unchanged (line 17-32)
   - `NO_EMAIL_STATUSES` list cleared (line 35) - filtering now handled in service layer

---

## Troubleshooting

### Issue: Emails not sending
**Check:**
- SMTP credentials in environment variables
- Email service is initialized in app.py
- Console logs for email errors
- Network connectivity to SMTP server

### Issue: Customer receives unwanted emails
**Check:**
- `services/order_service.py:128-133` - CUSTOMER_EMAIL_STATUSES list
- `services/driver_service.py` - ensure no `send_status_update_email()` calls to customer

### Issue: Admin not receiving notifications
**Check:**
- `ADMIN_EMAIL` environment variable is set correctly
- `services/driver_service.py` - verify `send_admin_driver_action_notification()` calls
- Email service logs for errors

### Issue: Missing driver information in customer emails
**Check:**
- `services/order_service.py:142-149` - driver lookup logic
- Ensure order has `driver_id` field populated

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Test all scenarios in staging environment
- [ ] Verify admin email address is correct (support@levoro.fi)
- [ ] Confirm SMTP credentials are production-ready
- [ ] Test email delivery to real customer addresses
- [ ] Monitor logs for email errors during first few orders
- [ ] Prepare rollback plan if issues occur
- [ ] Document any additional changes needed

---

## Support

If you encounter issues during testing, check:
1. Console logs for detailed error messages
2. Email service configuration in `.env` file
3. Network connectivity to SMTP server
4. This testing guide for expected behavior

For production issues, check admin email inbox for driver action notifications to verify system is working correctly.
