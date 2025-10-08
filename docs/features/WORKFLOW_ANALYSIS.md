# Workflow Analysis: Order Status & Email Notifications

## Expected Workflow (from requirements)

### Step 1: Customer makes an order
- **Action**: Customer submits order
- **Status**: NEW
- **Email**: Admin notified ✓

### Step 2: Admin gives details and accepts order
- **Action**: Admin sets car details, reward, and accepts
- **Status**: NEW → CONFIRMED
- **Email**: Order becomes available to drivers
- **Customer notification**: VAHVISTETTU (CONFIRMED)

### Step 3: Driver picks a job
- **Action**: Driver accepts job
- **Status**: CONFIRMED → KULJETTAJA MÄÄRITETTY (ASSIGNED_TO_DRIVER)
- **Email**: **ONLY admin should be notified** ❌
- **Requirement**: "email sent only to admin"

### Step 4: Driver adds pickup photos
- **Action**: Driver marks arrival → uploads photos
- **Status**: ASSIGNED_TO_DRIVER → DRIVER_ARRIVED → PICKUP_IMAGES_ADDED
- **Email**: **ONLY admin notified** ✓
- **Admin action**: Verifies photos and manually marks as KULJETUKSESSA (IN_TRANSIT)
- **Customer notification**: KULJETUKSESSA (IN_TRANSIT)

### Step 5: Driver clicks arrived on destination
- **Action**: Driver marks arrival at delivery location
- **Status**: IN_TRANSIT → DELIVERY_ARRIVED
- **Email**: **ONLY admin notified** ✓

### Step 6: Driver adds delivery photos
- **Action**: Driver uploads delivery photos
- **Status**: DELIVERY_ARRIVED → DELIVERY_IMAGES_ADDED
- **Email**: **ONLY admin notified** ✓
- **Admin action**: Verifies photos and marks as TOIMITETTU (DELIVERED)
- **Customer notification**: TOIMITETTU (DELIVERED)

### Critical Requirements
1. **Driver CANNOT set statuses to KULJETUKSESSA or TOIMITETTU** - must be verified by admin
2. **User only notified on**: VAHVISTETTU, KULJETTAJA MÄÄRITETTY, KULJETUKSESSA, TOIMITETTU

---

## Current Implementation Analysis

### Code Configuration

**Location**: `services/order_service.py` line ~175
```python
CUSTOMER_EMAIL_STATUSES = [
    "CONFIRMED",           # Order received/confirmed
    "ASSIGNED_TO_DRIVER",  # Driver assigned
    "IN_TRANSIT",          # In transit
    "DELIVERED"            # Delivered
]
```

### Status Flow Mapping

| Step | User Action | Status Change | Current Email Behavior | Expected Behavior | Issue? |
|------|-------------|---------------|------------------------|-------------------|---------|
| 1 | Customer creates order | NEW | Admin notified ✓ | Admin notified | ✓ CORRECT |
| 2 | Admin confirms order | NEW → CONFIRMED | Customer notified ✓ | Customer notified | ✓ CORRECT |
| 3 | Driver accepts job | CONFIRMED → ASSIGNED_TO_DRIVER | **Customer notified** ✓<br>Admin notified ✓ | **ONLY admin** | ❌ **ISSUE #1** |
| 4a | Driver: "Saavuin" | ASSIGNED_TO_DRIVER → DRIVER_ARRIVED | Admin only ✓ | Admin only | ✓ CORRECT |
| 4b | Driver uploads pickup photos | DRIVER_ARRIVED → PICKUP_IMAGES_ADDED | Admin only ✓ | Admin only | ✓ CORRECT |
| 4c | Driver: "Aloita kuljetus" | PICKUP_IMAGES_ADDED → IN_TRANSIT | **Customer notified** ✓<br>Admin notified ✓ | **Admin verifies first** | ❌ **ISSUE #2** |
| 4d | Admin marks as IN_TRANSIT | (Admin action) → IN_TRANSIT | Customer notified ✓ | Customer notified | ✓ CORRECT |
| 5 | Driver: "Saavuin toimituspaikalle" | IN_TRANSIT → DELIVERY_ARRIVED | Admin only ✓ | Admin only | ✓ CORRECT |
| 6a | Driver uploads delivery photos | DELIVERY_ARRIVED → DELIVERY_IMAGES_ADDED | Admin only ✓ | Admin only | ✓ CORRECT |
| 6b | Driver: "Päätä toimitus" | DELIVERY_IMAGES_ADDED → DELIVERED | **Customer notified** ✓<br>Admin notified ✓ | **Admin verifies first** | ❌ **ISSUE #3** |
| 6c | Admin marks as DELIVERED | (Admin action) → DELIVERED | Customer notified ✓ | Customer notified | ✓ CORRECT |

---

## Issues Found

### ❌ ISSUE #1: Driver Accept Sends Customer Email
**Location**: When driver accepts job (step 3)
- **Current**: Customer receives "Kuljettaja määritetty" email immediately
- **Expected**: Only admin should be notified
- **Root Cause**: `ASSIGNED_TO_DRIVER` is in `CUSTOMER_EMAIL_STATUSES`
- **Impact**: Customer notified before admin review

**Code Flow**:
```python
# services/driver_service.py line ~44
def accept_job(self, order_id: int, driver_id: int):
    # Assigns driver (status → ASSIGNED_TO_DRIVER)
    success, error = order_model.assign_driver(order_id, driver_id)
    
    # Sends admin notification ✓
    email_service.send_admin_driver_action_notification(...)
    
    # BUT: ASSIGNED_TO_DRIVER in CUSTOMER_EMAIL_STATUSES
    # So assign_driver() also triggers customer email via order_service.assign_driver_to_order()
```

**Files Involved**:
- `services/order_service.py`: Line ~245 `assign_driver_to_order()` sends customer email
- `services/driver_service.py`: Line ~44 `accept_job()` calls assign_driver
- `models/order.py`: Line ~278 `assign_driver()` changes status

---

### ❌ ISSUE #2: Driver Can Start Transport (Aloita kuljetus)
**Location**: Driver job detail page has "Aloita kuljetus" button
- **Current**: Driver can click "Aloita kuljetus" after adding pickup photos, automatically setting status to IN_TRANSIT
- **Expected**: Admin should verify pickup photos first, then manually set to IN_TRANSIT
- **Root Cause**: `start_transport()` route exists and is accessible to drivers
- **Impact**: Bypasses admin verification step

**Code Flow**:
```python
# templates/driver/job_detail.html line ~298
{% elif order.status == 'PICKUP_IMAGES_ADDED' %}
<form method="POST" action="{{ url_for('driver.start_transport', order_id=order.id) }}">
  <button type="submit" class="btn btn-primary w-full">
    🚗 Aloita kuljetus
  </button>
</form>

# routes/driver.py line ~96
@driver_bp.route('/job/<int:order_id>/start', methods=['POST'])
@driver_required
def start_transport(order_id):
    success, error = driver_service.start_transport(order_id, driver['id'])
    # Changes status to IN_TRANSIT → customer notified
```

**Files Involved**:
- `templates/driver/job_detail.html`: Line ~298 - "Aloita kuljetus" button
- `routes/driver.py`: Line ~96 `start_transport()` route
- `services/driver_service.py`: Line ~67 `start_transport()` sets IN_TRANSIT

---

### ❌ ISSUE #3: Driver Can Complete Delivery (Päätä toimitus)
**Location**: Driver job detail page has "Päätä toimitus" button
- **Current**: Driver can click "Päätä toimitus" after adding delivery photos, automatically setting status to DELIVERED
- **Expected**: Admin should verify delivery photos first, then manually mark as DELIVERED
- **Root Cause**: `complete_delivery()` route exists and is accessible to drivers
- **Impact**: Bypasses admin verification step, customer immediately notified

**Code Flow**:
```python
# templates/driver/job_detail.html line ~313
{% elif order.status == 'DELIVERY_IMAGES_ADDED' %}
<form method="POST" action="{{ url_for('driver.complete_delivery', order_id=order.id) }}">
  <button type="submit" class="btn btn-primary w-full"
          onclick="return confirm('Haluatko varmasti merkitä toimituksen valmiiksi?')">
    ✅ Päätä toimitus
  </button>
</form>

# routes/driver.py line ~118
@driver_bp.route('/job/<int:order_id>/complete', methods=['POST'])
@driver_required
def complete_delivery(order_id):
    success, error = driver_service.complete_delivery(order_id, driver['id'])
    # Changes status to DELIVERED → customer notified
```

**Files Involved**:
- `templates/driver/job_detail.html`: Line ~313 - "Päätä toimitus" button
- `routes/driver.py`: Line ~118 `complete_delivery()` route
- `services/driver_service.py`: Line ~80 `complete_delivery()` sets DELIVERED

---

## Correct Behaviors (No Issues)

### ✓ Step 1: Order Creation
- Customer creates order → Admin notified ✓
- Code: `services/email_service.py` line ~89 `send_admin_new_order_notification()`

### ✓ Step 2: Admin Confirms
- Admin sets status to CONFIRMED → Customer notified ✓
- Customer email properly sent for CONFIRMED status

### ✓ Step 4a: Driver Arrives at Pickup
- Driver clicks "Saavuin noutopaikalle" → Only admin notified ✓
- DRIVER_ARRIVED not in CUSTOMER_EMAIL_STATUSES ✓

### ✓ Step 4b: Driver Adds Pickup Photos
- Driver uploads photos → Only admin notified ✓
- PICKUP_IMAGES_ADDED not in CUSTOMER_EMAIL_STATUSES ✓

### ✓ Step 5: Driver Arrives at Delivery
- Driver clicks "Saavuin toimituspaikalle" → Only admin notified ✓
- DELIVERY_ARRIVED not in CUSTOMER_EMAIL_STATUSES ✓

### ✓ Step 6a: Driver Adds Delivery Photos
- Driver uploads photos → Only admin notified ✓
- DELIVERY_IMAGES_ADDED not in CUSTOMER_EMAIL_STATUSES ✓

### ✓ Admin Status Updates
- When admin manually changes status from admin panel, correct emails are sent
- Code: `routes/admin.py` line ~372 uses `order_service.update_order_status()`

---

## Summary

### Issues to Fix:

1. **Remove ASSIGNED_TO_DRIVER from customer email statuses** - Customer should not be notified when driver accepts, only admin
2. **Remove "Aloita kuljetus" button** - Driver should not be able to set IN_TRANSIT status
3. **Remove "Päätä toimitus" button** - Driver should not be able to set DELIVERED status

### Correct Workflow After Fixes:

```
Customer → NEW (admin notified)
Admin → CONFIRMED (customer notified: "Vahvistettu")
Driver accepts → ASSIGNED_TO_DRIVER (admin only)
Driver arrives → DRIVER_ARRIVED (admin only)
Driver adds photos → PICKUP_IMAGES_ADDED (admin only)
Admin verifies → IN_TRANSIT (customer notified: "Kuljetuksessa")
Driver arrives → DELIVERY_ARRIVED (admin only)
Driver adds photos → DELIVERY_IMAGES_ADDED (admin only)
Admin verifies → DELIVERED (customer notified: "Toimitettu")
```

### Customer Notifications Should Be:
- VAHVISTETTU (CONFIRMED) ✓
- ~~KULJETTAJA MÄÄRITETTY (ASSIGNED_TO_DRIVER)~~ ❌ (should be removed)
- KULJETUKSESSA (IN_TRANSIT) ✓
- TOIMITETTU (DELIVERED) ✓

**Update customer email statuses to**: `["CONFIRMED", "IN_TRANSIT", "DELIVERED"]`
