# Driver Reward System - Testing Guidelines

**Feature:** Separate customer pricing from driver rewards. Drivers only see their reward amount (palkkio), admins manage both customer prices and driver rewards.

**Date:** 2025-10-06
**Status:** Implementation in progress

---

## Overview of Changes

### Database Changes
- Added `driver_reward` field (float) to orders collection
- Added `car_model` field (string, optional) to orders collection
- Added `car_brand` field (string, optional) to orders collection
- Updated `get_available_orders()` to only show orders with `driver_reward > 0`

### Admin Interface
- Admin can set/update driver reward, car model, car brand, and additional info
- Driver reward is REQUIRED before order can be confirmed to CONFIRMED status
- Visual indicators show if reward is set or missing
- Admin sees both customer pricing (net + VAT + gross) AND driver reward

### Driver Interface
- Drivers see ONLY "Palkkio" (reward amount)
- All VAT-related information removed from driver views
- "Hinta" label changed to "Palkkio" everywhere
- Lisätiedot (additional info) displayed to drivers after accepting job
- Timestamps (created_at, updated_at) removed from driver views

---

## Test Scenarios

### 1. Admin - Order Creation & Reward Setting

#### Test 1.1: Create Order Without Driver Reward
**Steps:**
1. Log in as admin
2. Customer creates an order (order goes to NEW status)
3. Admin opens order detail page
4. Verify warning message: "❌ Kuskin palkkio puuttuu!"
5. Verify "Vahvista tilaus" button is disabled
6. Try to submit confirmation form
7. **Expected:** Error message "Aseta kuskin palkkio ennen tilauksen vahvistamista"

**Pass Criteria:**
- ✅ Warning displayed when reward not set
- ✅ Confirm button disabled
- ✅ Cannot confirm without reward

---

#### Test 1.2: Set Driver Reward
**Steps:**
1. Admin opens order with NEW status
2. Scroll to "Kuskin palkkio ja lisätiedot" form
3. Enter driver reward: `150.00`
4. Enter car brand: `Toyota`
5. Enter car model: `Corolla`
6. Enter additional info: `Auto on punaisella pihalla. Avaimet postilaatikossa.`
7. Click "💾 Tallenna tiedot"
8. **Expected:** Success message "Tilauksen tiedot päivitetty onnistuneesti!"
9. Verify reward shows in "Kuskin palkkio" field

**Pass Criteria:**
- ✅ Form saves successfully
- ✅ Reward displayed prominently (green, bold)
- ✅ Car details displayed
- ✅ Additional info saved

---

#### Test 1.3: Confirm Order With Reward Set
**Steps:**
1. Admin opens order with NEW status and driver_reward set
2. Verify "Vahvista tilaus" button is enabled
3. Click "✅ Vahvista tilaus ja julkaise kuljettajille"
4. **Expected:** Order status changes to CONFIRMED
5. **Expected:** Success message displayed
6. **Expected:** Message indicates order is visible to drivers

**Pass Criteria:**
- ✅ Order confirmed successfully
- ✅ Status = CONFIRMED
- ✅ Customer receives confirmation email
- ✅ Message indicates visibility to drivers

---

#### Test 1.4: Confirm Order Without Reward (Edge Case)
**Steps:**
1. Create order, set reward, confirm order
2. Use database tool to manually remove driver_reward field
3. Change status back to NEW
4. Try to confirm again
5. **Expected:** Error message preventing confirmation

**Pass Criteria:**
- ✅ Validation catches missing reward
- ✅ Cannot bypass validation

---

### 2. Driver - Order Visibility

#### Test 2.1: Order Visible Only With Reward
**Steps:**
1. Admin creates order, confirms to CONFIRMED (without reward)
2. Log in as driver
3. Go to "Saatavilla" tab
4. **Expected:** Order does NOT appear
5. Admin sets driver_reward = 100
6. Driver refreshes page
7. **Expected:** Order NOW appears in list

**Pass Criteria:**
- ✅ Order invisible without reward
- ✅ Order visible with reward > 0
- ✅ Order shows "Palkkio: 100.00 €" (no ALV mention)

---

#### Test 2.2: Driver Sees Only Palkkio (Not Customer Price)
**Steps:**
1. Admin creates order:
   - Customer price: 200 € (net), 251 € (gross with VAT)
   - Driver reward: 120 €
2. Confirm order
3. Driver views available jobs
4. **Expected:** Driver sees "Palkkio: 120.00 €"
5. **Expected:** NO mention of 200 €, 251 €, ALV, VAT, net, gross

**Pass Criteria:**
- ✅ Only reward amount visible
- ✅ No customer pricing visible
- ✅ No VAT/ALV text anywhere

---

### 3. Driver - Job Details Before Accepting

#### Test 3.1: Limited Info Before Accepting
**Steps:**
1. Driver views available job (not yet accepted)
2. Click job to open details
3. **Expected visibility:**
   - ✅ City names only (not full addresses)
   - ✅ Distance (km)
   - ✅ Palkkio (reward amount)
   - ❌ NO full addresses
   - ❌ NO lisätiedot
   - ❌ NO car brand/model
   - ❌ NO customer contact details

**Pass Criteria:**
- ✅ Privacy protected before acceptance
- ✅ Enough info to decide if job is worth it

---

### 4. Driver - Job Details After Accepting

#### Test 4.1: Full Info After Accepting
**Steps:**
1. Driver accepts job
2. View job details
3. **Expected visibility:**
   - ✅ Full pickup address
   - ✅ Full dropoff address
   - ✅ Palkkio (reward)
   - ✅ Distance
   - ✅ Lisätiedot (admin notes)
   - ✅ Car brand/model (if set)
   - ✅ Customer name
   - ✅ Customer phone
   - ❌ NO created_at timestamp
   - ❌ NO updated_at timestamp
   - ❌ NO customer pricing
   - ❌ NO VAT information

**Pass Criteria:**
- ✅ All necessary job info visible
- ✅ Still no customer pricing visible
- ✅ Lisätiedot displayed clearly
- ✅ No timestamps cluttering interface

---

### 5. Driver Dashboard

#### Test 5.1: Active Jobs List
**Steps:**
1. Driver has 2 active jobs
2. Open driver dashboard
3. Go to "Aktiiviset työt" tab
4. **Expected for each job:**
   - Job title: "Tilaus #123"
   - Route: "Helsinki → Tampere"
   - Distance: "165.0 km"
   - Palkkio: "150.00 €" (bold, no ALV)
   - Status badge
   - "Avaa työ" button
   - ❌ NO created_at timestamp

**Pass Criteria:**
- ✅ Jobs listed correctly
- ✅ Only palkkio shown (no customer price)
- ✅ No timestamps
- ✅ Clean, readable layout

---

#### Test 5.2: Available Jobs List
**Steps:**
1. Multiple confirmed orders with rewards set
2. Driver views "Saatavilla" tab
3. **Expected:**
   - List of available jobs
   - Each shows palkkio
   - Preview of lisätiedot (first 50 chars) if admin set any
   - No timestamps

**Pass Criteria:**
- ✅ Available jobs displayed
- ✅ Palkkio prominent
- ✅ Lisätiedot preview helpful
- ✅ No pricing/VAT info

---

### 6. Mobile Responsiveness

#### Test 6.1: Admin Form on Mobile
**Steps:**
1. Open admin order detail on mobile device (or dev tools mobile view)
2. Try to set driver reward
3. **Expected:**
   - Form stacks vertically
   - Input fields full width
   - Easy to tap and type
   - Button easy to click

**Pass Criteria:**
- ✅ Form usable on mobile
- ✅ No horizontal scrolling
- ✅ Touch targets adequate size

---

#### Test 6.2: Driver Job Cards on Mobile
**Steps:**
1. View driver dashboard on mobile
2. Check job cards layout
3. **Expected:**
   - Cards stack vertically
   - Palkkio readable
   - Buttons accessible
   - No text cutoff

**Pass Criteria:**
- ✅ Layout adapts to mobile
- ✅ All info visible
- ✅ Easy to interact with

---

### 7. Edge Cases & Validation

#### Test 7.1: Negative/Zero Reward
**Steps:**
1. Admin tries to set driver_reward = 0
2. **Expected:** Error "Kuskin palkkio tulee olla suurempi kuin 0"
3. Try driver_reward = -50
4. **Expected:** Same error or form validation prevents it

**Pass Criteria:**
- ✅ Cannot set reward <= 0
- ✅ Clear error message

---

#### Test 7.2: Very Large Reward
**Steps:**
1. Admin sets driver_reward = 99999.99
2. Save successfully
3. Driver views job
4. **Expected:** Large number displays correctly (no overflow)

**Pass Criteria:**
- ✅ Large numbers handled
- ✅ UI doesn't break

---

#### Test 7.3: Lisätiedot with Special Characters
**Steps:**
1. Admin enters lisätiedot with:
   - Finnish characters (ä, ö, å)
   - Line breaks
   - Special chars (!@#$%)
2. Save
3. Driver views after accepting job
4. **Expected:** All characters display correctly

**Pass Criteria:**
- ✅ Special chars preserved
- ✅ Line breaks maintained
- ✅ No encoding issues

---

### 8. Backward Compatibility

#### Test 8.1: Existing Orders Without Reward
**Steps:**
1. Query database for orders created before this feature
2. Check if they have driver_reward field
3. **Expected:** Old orders work normally, just not visible to drivers
4. Admin can add reward to old orders
5. After reward added, order becomes visible

**Pass Criteria:**
- ✅ No errors on old orders
- ✅ Can add reward retroactively
- ✅ System handles missing field gracefully

---

## Test Data Setup

### Create Test Orders

**Order 1: Without Reward (should not be visible to drivers)**
```
User: customer@example.com
Pickup: Helsinki, Mannerheimintie 1
Dropoff: Tampere, Hämeenkatu 10
Customer price: 180 € (net), 226 € (gross)
Driver reward: NOT SET
Status: CONFIRMED
```

**Order 2: With Reward (should be visible to drivers)**
```
User: customer@example.com
Pickup: Espoo, Otakaari 1
Dropoff: Turku, Aurakatu 5
Customer price: 220 € (net), 276 € (gross)
Driver reward: 140 €
Car brand: Volkswagen
Car model: Golf
Additional info: "Avaimet toimistossa. Kysy Mattia."
Status: CONFIRMED
```

**Order 3: High Reward Order**
```
User: customer2@example.com
Pickup: Helsinki, Kluuvikatu 3
Dropoff: Oulu, Kirkkokatu 15
Customer price: 400 € (net), 502 € (gross)
Driver reward: 280 €
Car brand: BMW
Car model: 320i
Additional info: "Kiireellinen. Autossa arvo-osia, ole varovainen."
Status: CONFIRMED
```

---

## Regression Testing Checklist

After implementing driver reward system, verify these still work:

- [ ] Customer can create orders normally
- [ ] Admin can manage users
- [ ] Driver can upload pickup/delivery images
- [ ] Order status workflow progresses correctly
- [ ] Email notifications sent at right times
- [ ] Driver terms acceptance works
- [ ] Image gallery displays correctly
- [ ] Mobile navigation works
- [ ] Admin can assign drivers manually (if feature exists)
- [ ] Search/filter functions work
- [ ] Order history displays correctly

---

## Performance Testing

### Load Test: Many Available Jobs
1. Create 100 orders with driver_reward set
2. Driver views available jobs
3. **Expected:** Page loads in < 2 seconds
4. **Expected:** No browser lag when scrolling

---

## Security Testing

### Test: Driver Cannot See Customer Prices
1. Driver inspects network requests (browser dev tools)
2. Check API responses for job data
3. **Expected:** Response includes driver_reward but NOT price_net, price_gross, price_vat
4. **Expected:** No way to calculate customer price from available data

### Test: Driver Cannot Access Lisätiedot Before Accepting
1. Driver views available job (not accepted)
2. Check page source and API responses
3. **Expected:** additional_info field not sent to frontend
4. After accepting, verify additional_info IS sent

---

## Sign-Off

**Tested by:** _______________
**Date:** _______________
**Environment:** [ ] Development [ ] Staging [ ] Production
**Result:** [ ] Pass [ ] Fail [ ] Partial

**Notes:**
_____________________________________________________
_____________________________________________________
_____________________________________________________
