# CSS Class Consolidation Analysis

## Problem Statement

The admin order detail page currently uses generic CSS class names that conflict with other dashboard styles, making it difficult to:
1. Maintain consistent heading sizes and styles
2. Debug styling issues
3. Update styles without affecting other pages
4. Understand which CSS file controls which elements

## Current Conflict Areas

### Generic Classes Used in `admin-order-detail.css`:

```
info-card
info-card-orderer
info-card-customer
info-card-route
info-card-pricing
info-card-title
info-card-body
info-row
info-row-highlight
info-label
info-value
info-value-highlight
info-value-price-large
```

These classes are too generic and could conflict with:
- `dashboard-table.css` (user orders)
- `driver-job-detail.css` (driver pages)
- Any future feature pages

## Proposed Solution

### Namespace all admin-specific classes with `admin-` prefix:

| Current Class | New Class | Usage |
|--------------|-----------|-------|
| `info-card` | `admin-info-card` | Base card styling |
| `info-card-orderer` | `admin-info-card-orderer` | Orderer info card |
| `info-card-customer` | `admin-info-card-customer` | Customer info card |
| `info-card-route` | `admin-info-card-route` | Route info card |
| `info-card-pricing` | `admin-info-card-pricing` | Pricing info card |
| `info-card-title` | `admin-info-card-title` | Card title/heading |
| `info-card-body` | `admin-info-card-body` | Card content wrapper |
| `info-row` | `admin-info-row` | Label-value row |
| `info-row-highlight` | `admin-info-row-highlight` | Highlighted row (kuskin palkkio) |
| `info-label` | `admin-info-label` | Field labels |
| `info-value` | `admin-info-value` | Field values |
| `info-value-highlight` | `admin-info-value-highlight` | Highlighted values |
| `info-value-price-large` | `admin-info-value-price-large` | Large price display |

### Classes Already Properly Namespaced (Keep as-is):

```
✓ admin-order-detail
✓ admin-config-section
✓ admin-actions-section
✓ admin-driver-section
✓ order-header
✓ order-main-grid
✓ order-info-section
✓ order-info-cards
✓ order-admin-section
✓ section-header
✓ section-header-config
✓ section-header-actions
✓ section-header-driver
✓ section-body
```

## Benefits

1. **Clear Separation**: Admin styles completely separate from user/driver styles
2. **Easy Debugging**: Immediately know which CSS file to check
3. **Maintainability**: Change admin styles without affecting other pages
4. **Consistency**: Single source of truth for admin page styles
5. **Scalability**: Easy to add new admin pages with consistent naming

## Implementation Steps

1. Update `admin-order-detail.css`: Rename all generic classes to admin-prefixed versions
2. Update `templates/admin/order_detail.html`: Use new class names
3. Test responsive behavior across all breakpoints
4. Document new class naming convention

## Files to Update

- `static/css/admin-order-detail.css` (primary changes)
- `templates/admin/order_detail.html` (class name updates)
- This documentation file

## Naming Convention Going Forward

**Rule**: All admin-specific classes MUST start with `admin-` prefix

**Examples**:
- ✓ `admin-info-card`
- ✓ `admin-status-badge`
- ✓ `admin-action-button`
- ✗ `info-card` (too generic)
- ✗ `status-badge` (too generic)
- ✗ `action-button` (too generic)

