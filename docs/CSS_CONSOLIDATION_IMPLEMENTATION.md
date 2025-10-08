# CSS Class Consolidation Implementation

## Step-by-Step Rename Map

### Classes to Rename (in order of replacement):

```bash
# Generic info classes → admin-info classes
.info-card-orderer .info-card-title  →  .admin-info-card-orderer .admin-info-card-title
.info-card-customer .info-card-title  →  .admin-info-card-customer .admin-info-card-title
.info-card-route .info-card-title  →  .admin-info-card-route .admin-info-card-title
.info-card-pricing .info-card-title  →  .admin-info-card-pricing .admin-info-card-title

.info-card-orderer  →  .admin-info-card-orderer
.info-card-customer  →  .admin-info-card-customer
.info-card-route  →  .admin-info-card-route
.info-card-pricing  →  .admin-info-card-pricing

.info-row-highlight .info-label  →  .admin-info-row-highlight .admin-info-label
.info-row .info-label  →  .admin-info-row .admin-info-label
.info-row .info-value  →  .admin-info-row .admin-info-value

.info-row-highlight  →  .admin-info-row-highlight
.info-row:last-child  →  .admin-info-row:last-child
.info-row  →  .admin-info-row

.info-card-title  →  .admin-info-card-title
.info-card-body  →  .admin-info-card-body
.info-card:hover  →  .admin-info-card:hover
.info-card  →  .admin-info-card

.info-value-highlight  →  .admin-info-value-highlight
.info-value-price-large  →  .admin-info-value-price-large
```

## Order of Operations

1. **CSS File** (`admin-order-detail.css`):
   - Replace compound selectors first (most specific)
   - Then replace single classes
   - Update responsive breakpoints

2. **HTML File** (`templates/admin/order_detail.html`):
   - Find/replace class attributes
   - Update all instances

## Find/Replace Commands

### For CSS File:

```
Step 1: .info-card-orderer .info-card-title
Step 2: .info-card-customer .info-card-title
Step 3: .info-card-route .info-card-title
Step 4: .info-card-pricing .info-card-title
Step 5: .info-row-highlight .info-label
Step 6: .info-row .info-label
Step 7: .info-row .info-value
Step 8: .info-card-orderer
Step 9: .info-card-customer
Step 10: .info-card-route
Step 11: .info-card-pricing
Step 12: .info-row-highlight
Step 13: .info-row:last-child
Step 14: .info-row
Step 15: .info-card-title
Step 16: .info-card-body
Step 17: .info-card:hover
Step 18: .info-card
Step 19: .info-value-highlight
Step 20: .info-value-price-large
```

### For HTML File:

```
"info-card info-card-orderer" → "admin-info-card admin-info-card-orderer"
"info-card info-card-customer" → "admin-info-card admin-info-card-customer"
"info-card info-card-route" → "admin-info-card admin-info-card-route"
"info-card info-card-pricing" → "admin-info-card admin-info-card-pricing"
"info-card-title" → "admin-info-card-title"
"info-card-body" → "admin-info-card-body"
"info-row info-row-highlight" → "admin-info-row admin-info-row-highlight"
"info-row" → "admin-info-row"
"info-label" → "admin-info-label"
"info-value info-value-price-large" → "admin-info-value admin-info-value-price-large"
"info-value-highlight" → "admin-info-value-highlight"
"info-value" → "admin-info-value"
```

## Validation Checklist

After changes:
- [ ] CSS file has no `.info-` classes (except comments)
- [ ] HTML file has no `info-` classes (except admin-info-)
- [ ] Page renders correctly on mobile
- [ ] Page renders correctly on tablet
- [ ] Page renders correctly on desktop
- [ ] All headings use consistent sizes
- [ ] Hover states still work
- [ ] Responsive breakpoints still work

