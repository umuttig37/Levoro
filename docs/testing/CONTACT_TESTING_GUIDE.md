# Contact Information and Footer Testing Guide

This guide provides comprehensive testing procedures for the contact information page and updated footer implementation.

## Overview of Changes

### 1. Footer Update
- **Location**: `templates/base/layout.html:125`
- **Change**: Updated from "Luotettava autonkuljetus" to "Levoro - Tiyouba Oy | Y-tunnus: 1541430-2"
- **Purpose**: Display proper company information and business ID for credibility

### 2. Contact Information Page
- **Route**: `/yhteystiedot`
- **Template**: `templates/contact.html`
- **Route Handler**: `marketing.py` - `contact()` function
- **Navigation**: Added "Yhteystiedot" link in main navigation

## Testing Procedures

### A. Footer Verification

#### Test 1: Footer Content Display
**Steps**:
1. Navigate to any page on the site (home, login, register, calculator, etc.)
2. Scroll to the bottom of the page
3. Locate the footer section

**Expected Result**:
- Footer should display: "© 2025 Levoro - Tiyouba Oy | Y-tunnus: 1541430-2"
- Text should be visible and properly styled
- Opacity should be 0.8 for subtle appearance

**Pages to Test**:
- Home page (`/`)
- Login page (`/login`)
- Register page (`/register`)
- Calculator page (`/calculator`)
- Dashboard pages (customer, driver, admin)
- Driver application page (`/hae-kuljettajaksi`)

#### Test 2: Footer Styling Consistency
**Steps**:
1. Check footer on desktop viewport (1920x1080)
2. Check footer on tablet viewport (768x1024)
3. Check footer on mobile viewport (375x667)

**Expected Result**:
- Footer text should remain centered
- Text should not overflow or wrap awkwardly
- Spacing should be consistent across viewports

### B. Contact Page Testing

#### Test 3: Navigation Link Access
**Steps**:
1. Navigate to home page (`/`)
2. Locate the "Yhteystiedot" link in the main navigation
3. Click the "Yhteystiedot" link

**Expected Result**:
- Link should be visible in navigation bar after "Etusivu"
- Clicking should navigate to `/yhteystiedot`
- Page should load without errors

#### Test 4: Contact Page Content Display
**Steps**:
1. Navigate to `/yhteystiedot`
2. Verify all sections are displayed

**Expected Result**:
Contact page should display four cards with the following information:

**Card 1 - Yritystiedot**:
- House icon (SVG)
- Title: "Yritystiedot"
- Company name: "Levoro - Tiyouba Oy"
- Business ID: "Y-tunnus: 1541430-2"

**Card 2 - Puhelinnumero**:
- Phone icon (SVG)
- Title: "Puhelinnumero"
- Phone number: "+358 40 123 4567" (clickable tel: link)
- Hours: "Ma-Pe 8:00 - 17:00"

**Card 3 - Sähköposti**:
- Email icon (SVG)
- Title: "Sähköposti"
- Email: "info@levoro.fi" (clickable mailto: link)
- Subtext: "Vastaamme 24h sisällä"

**Card 4 - Asiakastuki**:
- Help/Question icon (SVG)
- Title: "Asiakastuki"
- Email: "tuki@levoro.fi" (clickable mailto: link)
- Subtext: "Tekninen tuki ja kysymykset"

#### Test 5: Interactive Elements
**Steps**:
1. Navigate to `/yhteystiedot`
2. Click on phone number link
3. Click on info@levoro.fi email link
4. Click on tuki@levoro.fi email link

**Expected Result**:
- Phone link should open phone dialer (mobile) or default phone app (desktop)
- Email links should open default email client with recipient pre-filled

#### Test 6: CTA Section (Call-to-Action)
**Steps - Not Logged In**:
1. Navigate to `/yhteystiedot` without being logged in
2. Verify CTA section at bottom

**Expected Result**:
- Section with gradient background (blue gradient)
- Title: "Valmis aloittamaan?"
- Subtitle: "Rekisteröidy ja aloita kuljetusten tilaaminen jo tänään"
- Two buttons visible:
  - "Luo tili" (secondary style)
  - "Laske hinta" (outline white style)

**Steps - Logged In**:
1. Log in as a customer user
2. Navigate to `/yhteystiedot`
3. Verify CTA section buttons

**Expected Result**:
- Two different buttons visible:
  - "Laske hinta" (secondary style)
  - "Uusi tilaus" (outline white style)

#### Test 7: Responsive Design
**Desktop (1920x1080)**:
1. Navigate to `/yhteystiedot`
2. Verify layout

**Expected Result**:
- Cards displayed in 2-column grid
- All content visible and well-spaced
- Icons properly sized and aligned

**Tablet (768x1024)**:
1. Navigate to `/yhteystiedot`
2. Verify layout

**Expected Result**:
- Cards should adapt to tablet width
- Grid may collapse to 1 column depending on breakpoints
- Touch targets should be adequate size

**Mobile (375x667)**:
1. Navigate to `/yhteystiedot`
2. Verify layout

**Expected Result**:
- Cards displayed in single column
- All text readable without horizontal scrolling
- Icons and spacing appropriate for mobile

### C. Role-Based Testing

#### Test 8: Access Control
**Steps**:
1. Access `/yhteystiedot` as guest (not logged in)
2. Access `/yhteystiedot` as customer user
3. Access `/yhteystiedot` as driver user
4. Access `/yhteystiedot` as admin user

**Expected Result**:
- All user types (including guests) should have access
- Page should display correctly for all user roles
- CTA buttons should adapt based on login status (see Test 6)

### D. Cross-Browser Testing

#### Test 9: Browser Compatibility
Test contact page in the following browsers:
- Chrome/Edge (Chromium-based)
- Firefox
- Safari (macOS/iOS)

**Steps**:
1. Open `/yhteystiedot` in each browser
2. Verify SVG icons render correctly
3. Check mailto: and tel: links work
4. Verify gradient background displays correctly
5. Check responsive behavior

**Expected Result**:
- Consistent appearance across all browsers
- All interactive elements functional
- No console errors

### E. Navigation Testing

#### Test 10: Navigation Highlighting
**Steps**:
1. Navigate to `/yhteystiedot`
2. Check if "Yhteystiedot" link is highlighted/active in navigation
3. Navigate to other pages and verify "Yhteystiedot" link remains visible

**Expected Result**:
- "Yhteystiedot" link should be visible on all pages
- Link should maintain consistent styling with other nav links
- On mobile, link should be accessible in mobile menu

### F. Accessibility Testing

#### Test 11: Keyboard Navigation
**Steps**:
1. Navigate to `/yhteystiedot`
2. Use Tab key to navigate through all interactive elements
3. Use Enter key to activate links

**Expected Result**:
- All links should be keyboard accessible
- Focus indicators should be visible
- Tab order should be logical (top to bottom, left to right)

#### Test 12: Screen Reader Testing
**Steps**:
1. Enable screen reader (NVDA, JAWS, VoiceOver)
2. Navigate to `/yhteystiedot`
3. Have screen reader read page content

**Expected Result**:
- Page title should be announced
- All text content should be readable
- Links should be announced with purpose
- Icons should not confuse screen reader (using aria-hidden where appropriate)

## Contact Information Update Guide

If contact information needs to be updated in the future:

### Updating Phone Numbers
**File**: `templates/contact.html`
**Line**: Look for `<a href="tel:+358401234567">`

Update both:
1. The `href` attribute (tel: link)
2. The displayed text

### Updating Email Addresses
**File**: `templates/contact.html`
**Lines**: Look for `<a href="mailto:...">`

Update both:
1. The `href` attribute (mailto: link)
2. The displayed text

### Updating Business Hours
**File**: `templates/contact.html`
**Line**: Look for "Ma-Pe 8:00 - 17:00"

Update the text to reflect new business hours.

### Updating Company Information
**Files**:
1. `templates/base/layout.html:125` - Footer
2. `templates/contact.html` - Company info card

Ensure both are updated for consistency.

## Common Issues and Solutions

### Issue 1: Contact page not loading (404)
**Cause**: Route not registered
**Solution**: Verify `marketing.py` has the `@app.get("/yhteystiedot")` route and the file is imported in `app.py`

### Issue 2: Navigation link not visible
**Cause**: Template caching or navigation not updated
**Solution**:
1. Clear browser cache
2. Restart Flask development server
3. Verify `templates/base/layout.html` has the navigation link

### Issue 3: SVG icons not displaying
**Cause**: CSS stroke color not defined
**Solution**: Icons use `var(--color-primary)` - ensure this CSS variable is defined in `static/css/main.css`

### Issue 4: Email/phone links not working
**Cause**: Incorrect href format
**Solution**: Ensure `mailto:` and `tel:` links follow correct format (no spaces in href)

### Issue 5: Responsive layout broken
**Cause**: Grid system not working properly
**Solution**: Verify CSS classes `.grid` and `.grid-cols-2` are defined in main CSS file

## Test Completion Checklist

Mark each test as completed:

- [ ] Test 1: Footer Content Display
- [ ] Test 2: Footer Styling Consistency
- [ ] Test 3: Navigation Link Access
- [ ] Test 4: Contact Page Content Display
- [ ] Test 5: Interactive Elements
- [ ] Test 6: CTA Section
- [ ] Test 7: Responsive Design
- [ ] Test 8: Access Control
- [ ] Test 9: Browser Compatibility
- [ ] Test 10: Navigation Highlighting
- [ ] Test 11: Keyboard Navigation
- [ ] Test 12: Screen Reader Testing

## Notes

- The contact information (phone numbers and emails) in the template are placeholders
- Update them with actual company contact information before production deployment
- Ensure all email addresses are monitored and respond within stated timeframes
- Consider adding a contact form in future iterations for better user engagement
