# Recent Changes

## Summary
This document outlines the recent changes made to the Levoro car transport application, focusing on pricing updates, VAT handling, UI improvements, and role-based access control.

---

## 1. Progress Bar Fix - DELIVERED Status

**Issue**: When an order was marked as DELIVERED in the admin panel, the final step in the progress indicator did not turn green.

**Solution**: Updated the progress bar logic in `app.py:674-675` to mark the last step as completed when status is DELIVERED.

**Files Changed**:
- `app.py` (line 674-675)

**Code Change**:
```python
# Before
is_completed = i < current_step

# After
is_completed = i < current_step or (i == current_step and status == "DELIVERED")
is_current = i == current_step and status != "DELIVERED"
```

---

## 2. VAT Rate Update - 25.5%

**Change**: Updated Finnish VAT rate from 24% to 25.5% across the application.

**Files Changed**:
- `services/order_service.py` (line 15)
- `app.py` (line 56)

**Code Change**:
```python
# Before
VAT_RATE = float(os.getenv("VAT_RATE", "0.24"))

# After
VAT_RATE = float(os.getenv("VAT_RATE", "0.255"))  # 25.5% Finnish VAT
```

---

## 3. Pricing Model Change - Net-Based Pricing

**Issue**: Prices were stored as gross (including VAT), making it difficult to display VAT breakdown clearly to customers.

**Solution**: Changed pricing model to net-based. All pricing tiers now represent net prices, with VAT added on top.

**Files Changed**:
- `services/order_service.py` (lines 17-28, 133-163)
- `app.py` (lines 58-65)

**Changes**:
- `METRO_GROSS` → `METRO_NET` (27€ net)
- `MID_GROSS` → `MID_NET` (81€ net)
- `LONG_GROSS` → `LONG_NET` (207€ net)
- `MINIMUM_ORDER_PRICE` → `MINIMUM_ORDER_PRICE_NET` (20€ net)

**Pricing Example**:
- Old: 27€ gross (includes 24% VAT) → 21.77€ net + 5.23€ VAT
- New: 27€ net → 27€ + 6.89€ VAT (25.5%) = **33.89€ gross**

**Updated Calculation Logic**:
```python
def calculate_price(self, distance_km: float, ...) -> float:
    """Returns GROSS price (including VAT)"""
    # Calculate NET price first
    if self._both_in_metro(pickup_addr, dropoff_addr):
        net_price = METRO_NET  # 27€
    # ... [interpolation logic]

    # Add VAT to get gross price
    gross_price = net_price * (1 + VAT_RATE)  # 27 * 1.255 = 33.89€
    return round(gross_price, 2)
```

---

## 4. Price Display - VAT Breakdown

**Issue**: Customers need to see the net price prominently, with VAT shown separately for transparency.

**Solution**: Created a new display format showing net price (large), VAT amount (small), and total (small).

### 4.1 Jinja2 Template Filter

**File**: `app.py` (lines 305-325)

Created `format_price_with_vat` filter:
```python
@app.template_filter('format_price_with_vat')
def format_price_with_vat_filter(gross_price):
    """Format price with VAT breakdown"""
    net = gross_price / (1 + VAT_RATE)
    vat = gross_price - net

    return f'''<div class="price-breakdown">
        <div class="price-main">{net_str} €</div>
        <div class="price-vat">+ alv {vat_str} €</div>
        <div class="price-total">Yhteensä {gross_str} €</div>
    </div>'''
```

### 4.2 Updated Templates

**Price Display Format**:
```
27,00 €              (large, net price - most important)
+ alv 6,89 €         (small, VAT amount)
Yhteensä 33,89 €     (small, gross total)
```

**Files Changed**:

1. **Calculator** (`marketing.py` lines 78-82, 461-464)
   - Shows net, VAT, and gross in results panel
   - JavaScript updated to use API response: `j.net`, `j.vat`, `j.gross`

2. **Customer Order View** (`templates/dashboard/order_view.html` line 53)
   - Hero section price card uses filter: `{{ price_gross|format_price_with_vat|safe }}`

3. **Admin Order Detail** (`templates/admin/order_detail.html` line 43)
   - Order details section uses filter

4. **Driver Job Detail** (`templates/driver/job_detail.html` line 93)
   - Job price display uses filter

5. **Customer Dashboard** (`templates/dashboard/user_dashboard.html` lines 101-106)
   - Order list table shows breakdown inline:
   ```html
   <div style="line-height: 1.3;">
     <div style="font-size: 0.95rem; font-weight: 600;">27,00 €</div>
     <div style="font-size: 0.7rem; color: #6b7280;">+ alv 6,89 €</div>
     <div style="font-size: 0.75rem; color: #6b7280;">= 33,89 €</div>
   </div>
   ```

6. **Email Templates**:
   - `templates/emails/order_created.html` (lines 89-103, 200-205)
     - Added CSS styles for price breakdown
     - Shows net prominently, VAT and total below

   - `templates/emails/admin_new_order.html` (lines 191-204)
     - Shows three separate rows: net, VAT, total

---

## 5. Calculator Access Restriction for Drivers

**Issue**: Driver role users should not have access to the price calculator, as it's only relevant for customers placing orders.

**Solution**: Added role-based access control to hide calculator from drivers.

### 5.1 Route Protection

**File**: `marketing.py` (lines 22-24)

```python
@app.get("/calculator")
def calculator():
    u = auth_service.get_current_user()
    if not u:
        return redirect(url_for("auth.login", next="/calculator"))

    # Drivers cannot access calculator - redirect to their dashboard
    if u.get('role') == 'driver':
        return redirect(url_for("driver.dashboard"))
```

### 5.2 UI Element Hiding

**Files Changed**:

1. **Layout Footer** (`templates/base/layout.html` lines 119-123)
   ```jinja
   {% if current_user and current_user.role != 'driver' %}
   <a href="/calculator" class="btn btn-primary">Laske hinta</a>
   {% elif not current_user %}
   <a href="/register" class="btn btn-primary">Kirjaudu ja laske hinta</a>
   {% endif %}
   ```

2. **Home Page Hero** (`templates/home.html` lines 17-19)
   ```jinja
   {% if not current_user or current_user.role != 'driver' %}
   <a class="btn btn-primary btn-lg" href="/calculator">Laske halvin hinta nyt</a>
   {% endif %}
   ```

3. **Home Page Insurance Banner** (`templates/home.html` lines 106-108)
   ```jinja
   {% if not current_user or current_user.role != 'driver' %}
   <a class="btn btn-primary btn-lg" href="/calculator">Laske hinta →</a>
   {% endif %}
   ```

**Result**:
- Drivers cannot access `/calculator` (redirected to dashboard)
- All calculator buttons hidden from driver users
- Calculator remains accessible to customers and admins

---

## Migration Notes

### Environment Variables
Update `.env` file with new values:
```bash
VAT_RATE=0.255

# Pricing tiers are now NET prices (VAT added on top)
METRO_NET=27
MID_NET=81
LONG_NET=207
```

### Database
No database migration required. Existing `price_gross` values remain unchanged and are correctly interpreted as gross prices including VAT.

### Testing Checklist
- [ ] Verify calculator shows correct VAT breakdown (27€ → 33.89€)
- [ ] Check progress bar turns green on DELIVERED status
- [ ] Confirm drivers cannot access `/calculator`
- [ ] Verify all price displays show VAT breakdown
- [ ] Test email templates render prices correctly
- [ ] Validate pricing calculations match expected values

---

## Files Modified Summary

### Core Application
- `app.py` - VAT rate, pricing constants, progress bar logic, template filter
- `services/order_service.py` - VAT rate, net-based pricing logic
- `marketing.py` - Calculator access restriction, price display HTML

### Templates
- `templates/base/layout.html` - Footer calculator button hiding
- `templates/home.html` - Hero and banner calculator buttons hiding
- `templates/dashboard/order_view.html` - Price display with VAT
- `templates/dashboard/user_dashboard.html` - Order list price breakdown
- `templates/admin/order_detail.html` - Admin price display
- `templates/driver/job_detail.html` - Driver job price display
- `templates/emails/order_created.html` - Customer email price display
- `templates/emails/admin_new_order.html` - Admin notification price display

---

*Document generated: 2025-10-02*
*Changes implemented by: Claude Code*
