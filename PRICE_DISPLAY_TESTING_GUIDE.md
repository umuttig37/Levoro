# Price Display Testing Guide

This guide covers testing the updated price rendering across the application. All prices now display **NET price (ALV 0%)** prominently with VAT details shown smaller and less emphasized.

## Testing Objective

Verify that all price displays follow the new pattern:
- ✅ **NET price**: Large, bold, heavily emphasized
- ✅ **"+ ALV 0%" label**: Prominent and clearly visible
- ✅ **VAT breakdown**: Small text, low opacity, de-emphasized

---

## 1. Email Templates Testing

### 1.1 Order Created Email (Customer)
**Trigger**: Create a new order through the order wizard

**Steps**:
1. Go to `/order/new` and create a complete order
2. Check the customer's email inbox for "Tilaus vastaanotettu" email

**Expected Result**:
- Price section shows NET price in very large text (42px)
- "ALV 0%" label displayed prominently below the price
- VAT breakdown shown in much smaller text (10px) with reduced opacity
- Format: Main price → "ALV 0%" → Small VAT details line

### 1.2 Admin New Order Email
**Trigger**: Create a new order (admin receives notification)

**Steps**:
1. Create a new order
2. Check admin email inbox for "Uusi tilaus" notification

**Expected Result**:
- NET price displayed at 24px with bold "ALV 0%" label inline
- VAT breakdown shown below in 11px with reduced opacity
- Clear visual hierarchy: NET price stands out prominently

### 1.3 Status Update Email (Customer)
**Trigger**: Admin updates order status

**Steps**:
1. Admin changes order status (e.g., NEW → CONFIRMED)
2. Check customer email for status update notification

**Expected Result**:
- Price section shows NET price at 24px with "ALV 0%" label
- VAT details compressed into single line at 10px with low opacity
- Price clearly emphasized over VAT breakdown

---

## 2. Order Wizard & Confirmation Page

### 2.1 Calculator Page
**URL**: `/hinta-arvio` or `/calculator`

**Steps**:
1. Navigate to calculator page
2. Enter two addresses (e.g., "Helsinki" → "Tampere")
3. Click "Laske hinta ja reitti"
4. Observe the price receipt that appears

**Expected Result**:
- Receipt shows NET price at 2.5em (very large)
- "ALV 0%" displayed prominently at 1.2em below price
- VAT breakdown in single line at 0.75em with 0.6 opacity
- NET price dominates visually

### 2.2 Order Confirmation Page
**URL**: `/order/new/confirm` (step 6 of wizard)

**Steps**:
1. Complete order wizard steps 1-5
2. Review confirmation page

**Expected Result**:
- Three price displays, all showing NET prominently:
  - **Top summary card**: NET at 1.5em with "ALV 0%" label
  - **Map card meta**: NET at 1.3em bold with "ALV 0%"
  - **Price summary box**: NET at 2.5em with "ALV 0%" at 1.2em, VAT details at 0.75em
- All emphasize NET over VAT

---

## 3. Admin Dashboard Testing

### 3.1 Main Admin Dashboard
**URL**: `/admin/dashboard`

**Login**: Admin account required

**Steps**:
1. Login as admin
2. View orders table

**Expected Result**:
- "Hinta (ALV 0%)" column shows:
  - NET price at 1.1em bold
  - "ALV 0%" label at 0.85em with reduced opacity
- Prices clearly readable and emphasized

### 3.2 Order Detail Page
**URL**: `/admin/order/{order_id}`

**Steps**:
1. Click on any order from admin dashboard
2. View order detail page

**Expected Result**:
- Price uses `format_price_with_vat` filter
- Shows NET at 1.8em bold with "ALV 0%" at 1.1em
- VAT breakdown in single line at 0.7em with low opacity

### 3.3 Driver Assignment Page
**URL**: `/admin/drivers`

**Steps**:
1. Navigate to admin drivers page
2. View unassigned orders table

**Expected Result**:
- Price column shows NET at 1.1em bold
- "ALV 0%" label at 0.85em with reduced opacity
- Consistent with main dashboard styling

---

## 4. User Dashboard Testing

### 4.1 Customer Dashboard
**URL**: `/dashboard`

**Login**: Customer account required

**Steps**:
1. Login as customer (not admin, not driver)
2. View orders table

**Expected Result**:
- Price column shows:
  - NET price at 1.3rem bold (800 weight)
  - "ALV 0%" at 0.85rem bold
  - VAT breakdown at 0.65rem with 0.6 opacity in single line
- NET price clearly dominates

### 4.2 Order View Page
**URL**: `/order/{order_id}`

**Steps**:
1. Click "Näytä tilaus" on any order
2. View order detail metrics

**Expected Result**:
- Price metric card uses `format_price_with_vat` filter
- NET at 1.8em bold, "ALV 0%" at 1.1em, VAT details at 0.7em
- Consistent with admin order detail

---

## 5. Driver Dashboard Testing

### 5.1 Available Jobs List
**URL**: `/driver/dashboard`

**Login**: Driver account required

**Steps**:
1. Login as driver
2. Ensure driver has accepted terms
3. View "Saatavilla olevat työt" section

**Expected Result**:
- Each job card shows NET price in bold with "ALV 0%" label
- Price clearly visible and emphasized

### 5.2 Active Jobs List
**URL**: `/driver/dashboard` (Aktiiviset työt section)

**Steps**:
1. Accept a job or view existing active jobs
2. Check active jobs section

**Expected Result**:
- Job meta shows NET bold with "ALV 0%"
- Format consistent with available jobs

### 5.3 Completed Jobs List
**URL**: `/driver/dashboard` (Valmiit työt section)

**Steps**:
1. View completed jobs section

**Expected Result**:
- Completed job cards show NET bold with "ALV 0%"
- Consistent pricing format

### 5.4 Job Detail Page (Jobs List)
**URL**: `/driver/jobs`

**Steps**:
1. Navigate to available jobs list
2. View job cards

**Expected Result**:
- "Hinta:" field shows NET at 1.15em bold with "ALV 0%" label
- Clear visual emphasis

### 5.5 My Jobs Page
**URL**: `/driver/my-jobs`

**Steps**:
1. Navigate to driver's personal jobs page
2. View job cards

**Expected Result**:
- Job info shows NET at 1.1em bold with "ALV 0%"
- Consistent styling

### 5.6 Job Detail Page
**URL**: `/driver/job/{order_id}`

**Steps**:
1. Click into specific job detail
2. View price display

**Expected Result**:
- Uses `format_price_with_vat` filter
- NET at 1.8em, "ALV 0%" at 1.1em, VAT details de-emphasized

---

## 6. Visual Testing Checklist

For each page tested, verify:

### Typography
- [ ] NET price is significantly larger than VAT details (at least 1.5x - 2.5x larger)
- [ ] NET price uses bold weight (700-800)
- [ ] "ALV 0%" label is clearly visible and bold
- [ ] VAT breakdown uses smaller font (0.65em - 0.75em)

### Visual Hierarchy
- [ ] NET price immediately catches the eye
- [ ] "ALV 0%" label is secondary but prominent
- [ ] VAT breakdown is tertiary, easily ignored if not needed
- [ ] No confusion about which price is the "main" price

### Opacity & Contrast
- [ ] NET price at full opacity (1.0)
- [ ] "ALV 0%" label at high opacity (0.9-1.0)
- [ ] VAT breakdown at reduced opacity (0.5-0.6)

### Layout
- [ ] NET price and "ALV 0%" clearly grouped together
- [ ] VAT breakdown separated (often in single line with pipe separator)
- [ ] Adequate spacing between price sections

---

## 7. Cross-Browser Testing

Test on:
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (if available)

Check for:
- Font rendering consistency
- Bold weights displaying properly
- Opacity levels rendering correctly
- Layout alignment maintained

---

## 8. Responsive Testing

Test on different screen sizes:
- [ ] Desktop (1920x1080)
- [ ] Tablet (768x1024)
- [ ] Mobile (375x667)

Verify:
- Price text scales appropriately
- Hierarchy maintained on smaller screens
- No text overflow or wrapping issues
- Readability maintained

---

## 9. Sample Test Data

### Test Addresses
- **Short distance** (PK-seutu): Helsinki → Espoo (~20 km)
- **Medium distance**: Helsinki → Tampere (~180 km)
- **Long distance**: Helsinki → Oulu (~600 km)

### Expected Price Format Example
For 180 km route (NET ≈ 88.00 €, GROSS ≈ 110.44 €):

```
88.00 €        <- Large, bold (1.8em - 2.5em)
+ ALV 0%       <- Prominent (1.1em - 1.2em, bold)
ALV 25,5%: 22.44 € | Yhteensä sis. ALV: 110.44 €  <- Small (0.65em - 0.75em, opacity 0.5-0.6)
```

---

## 10. Known Issues to Watch For

- [ ] Division by zero if price_gross is 0 or None
- [ ] Rounding errors in NET calculation (should be price_gross / 1.255)
- [ ] Inconsistent decimal formatting (should be 2 decimals)
- [ ] Missing "€" symbol
- [ ] Incorrect VAT rate (should be 25.5%)

---

## 11. Regression Testing

Ensure existing functionality still works:
- [ ] Order creation completes successfully
- [ ] Email sending works (no template errors)
- [ ] Price calculations are mathematically correct
- [ ] Driver job acceptance works
- [ ] Admin order management works
- [ ] Status updates work

---

## Test Sign-off

| Area | Tester | Date | Status | Notes |
|------|--------|------|--------|-------|
| Email Templates | | | | |
| Order Wizard | | | | |
| Admin Dashboard | | | | |
| User Dashboard | | | | |
| Driver Dashboard | | | | |
| Calculator Page | | | | |
| Cross-browser | | | | |
| Responsive | | | | |

---

## Quick Test Commands

```bash
# Start development server
python app.py

# Access points:
# Calculator: http://127.0.0.1:8000/calculator
# Admin: http://127.0.0.1:8000/admin/dashboard
# User Dashboard: http://127.0.0.1:8000/dashboard
# Driver Dashboard: http://127.0.0.1:8000/driver/dashboard

# Test accounts (development environment):
# Admin: SEED_ADMIN_EMAIL / SEED_ADMIN_PASS
# Driver: kuljettaja@levoro.fi / kuljettaja123
# Customer: Create via /register
```

---

## Success Criteria

All tests pass when:
1. ✅ NET prices are visually dominant across all pages
2. ✅ "ALV 0%" label is clear and prominent
3. ✅ VAT breakdown is de-emphasized but still accessible
4. ✅ No mathematical errors in price calculations
5. ✅ Consistent styling across all interfaces
6. ✅ Responsive design maintained
7. ✅ All existing functionality works
8. ✅ No email template errors
