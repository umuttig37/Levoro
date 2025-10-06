# Development Email Mock System

## Overview

In development mode (`FLASK_ENV=development`), the email system saves all emails as HTML files instead of sending them via SMTP. This allows you to:

- ✅ Test the email notification workflow without email server access
- ✅ Verify email content and formatting
- ✅ Track which emails are sent and when
- ✅ Debug email issues quickly

## How It Works

When `FLASK_ENV=development`, all emails are automatically saved to:
```
static/dev_emails/
```

Each email is saved as a timestamped HTML file with metadata.

## Accessing Development Emails

### Method 1: Email Inbox (Recommended)
Visit the development email inbox at:
```
http://localhost:8000/static/dev_emails/index.html
```

Features:
- 📧 List of all emails with timestamps
- 🔄 Auto-refreshes every 5 seconds
- 📊 Shows total email count
- 🎨 Beautiful, easy-to-browse interface

### Method 2: Direct File Access
Navigate to the folder:
```
static/dev_emails/
```

Open any `.html` file in your browser to view the email.

## Email File Format

Each email file contains:
- **Metadata section** (dark header):
  - From address
  - To address(es)
  - Subject
  - Timestamp
- **Email content** (white body):
  - The actual email HTML as it would be sent

## Testing the Workflow

### Step 1: Start Development Server
```bash
# Make sure FLASK_ENV is set to development
export FLASK_ENV=development  # Linux/Mac
set FLASK_ENV=development     # Windows CMD

python app.py
```

### Step 2: Trigger Email Events

#### Test Order Creation (Admin Notification)
1. Create a new order as a customer
2. Check `static/dev_emails/index.html`
3. Should see: "Uusi tilaus #X - Vahvistus tarvitaan"

#### Test Order Confirmation (Customer Notification)
1. Login as admin
2. Confirm an order (set status to CONFIRMED)
3. Check dev emails
4. Should see: "Tilaus #X - Vahvistettu"

#### Test Driver Accept (Admin Only)
1. Login as driver
2. Accept an available job
3. Check dev emails
4. Should see admin notification, NOT customer email
5. ✅ Verifies: Customer not notified when driver accepts

#### Test Pickup Photos (Admin Only)
1. Driver clicks "Saavuin noutopaikalle"
2. Driver uploads pickup photos
3. Check dev emails
4. Should see only admin notifications
5. ✅ Verifies: Customer not notified during pickup

#### Test In Transit (Customer Notification)
1. Admin manually sets order to IN_TRANSIT
2. Check dev emails
3. Should see: "Tilaus #X - Kuljetuksessa"
4. ✅ Verifies: Customer notified when admin starts transport

#### Test Delivery Photos (Admin Only)
1. Driver clicks "Saavuin toimituspaikalle"
2. Driver uploads delivery photos
3. Check dev emails
4. Should see only admin notifications
5. ✅ Verifies: Customer not notified during delivery

#### Test Delivered (Customer Notification)
1. Admin manually sets order to DELIVERED
2. Check dev emails
3. Should see: "Tilaus #X - Toimitettu"
4. ✅ Verifies: Customer notified when admin completes delivery

## Expected Email Counts

For a complete order workflow:

| Event | Admin Emails | Customer Emails | Driver Emails |
|-------|-------------|-----------------|---------------|
| Order created | 1 | 1 (order confirmation) | 0 |
| Admin confirms | 0 | 1 ("Vahvistettu") | 0 |
| Driver accepts | 1 | 0 ❌ (FIXED) | 1 |
| Driver arrives pickup | 1 | 0 | 0 |
| Driver uploads pickup | 1 | 0 | 0 |
| Admin → IN_TRANSIT | 0 | 1 ("Kuljetuksessa") | 0 |
| Driver arrives delivery | 1 | 0 | 0 |
| Driver uploads delivery | 1 | 0 | 0 |
| Admin → DELIVERED | 0 | 1 ("Toimitettu") | 0 |
| **TOTAL** | **5** | **4** | **1** |

## Verifying the Fix

### ✅ CORRECT Behavior:
- Customer receives exactly 4 emails:
  1. Order confirmation (when created)
  2. "Vahvistettu" (when admin confirms)
  3. "Kuljetuksessa" (when admin sets IN_TRANSIT)
  4. "Toimitettu" (when admin sets DELIVERED)

### ❌ INCORRECT Behavior (Before Fix):
- Customer would receive 5 emails (including "Kuljettaja määritetty")

## Console Output

The system prints detailed logs:

```
[EMAIL] Attempting to send email
   From: support@levoro.fi
   To: ['customer@example.com']
   Subject: Tilaus #123 - Vahvistettu
   [DEV MODE] Saving email to file instead of sending...
   ✅ [DEV] Email saved to: static/dev_emails/20251006_143052_123456_Tilaus_123_Vahvistettu.html
   🌐 [DEV] View at: http://localhost:8000/static/dev_emails/20251006_143052_123456_Tilaus_123_Vahvistettu.html
   📋 [DEV] Email index: http://localhost:8000/static/dev_emails/index.html
```

## Cleanup

### Clear All Emails
Delete all files in `static/dev_emails/` except `.gitkeep` (if present):

```bash
# Linux/Mac
rm -f static/dev_emails/*.html

# Windows PowerShell
Remove-Item static/dev_emails/*.html

# Windows CMD
del static\dev_emails\*.html
```

The index will automatically regenerate showing "No Emails Yet".

## Production Mode

In production (`FLASK_ENV=production` or not set):
- Emails are sent via Zoho SMTP normally
- No files are saved to disk
- Email mock system is completely disabled

## Troubleshooting

### Emails not appearing?
1. Check console for `[DEV MODE]` messages
2. Verify `FLASK_ENV=development` is set
3. Check that `static/dev_emails/` folder exists
4. Look for error messages in console

### Index not updating?
1. Refresh the page manually (auto-refresh is every 5 seconds)
2. Check browser console for errors
3. Verify files are being created in folder

### Email formatting broken?
1. Check the HTML source in the email file
2. Verify templates are rendering correctly
3. Check for template errors in console

## Tips

1. **Keep inbox open**: Leave `index.html` open in a browser tab while testing - it auto-refreshes
2. **Clear regularly**: Delete old emails to avoid clutter
3. **Check timestamps**: Verify email timing matches your actions
4. **Verify recipients**: Check "To" field to ensure correct notification routing
5. **Test all paths**: Go through complete order workflow to test all email triggers

## File Naming Convention

Files are named: `YYYYMMDD_HHMMSS_microseconds_subject.html`

Example:
```
20251006_143052_123456_Tilaus_123_Vahvistettu.html
```

This ensures:
- ✅ Chronological sorting
- ✅ Unique filenames
- ✅ Readable subject identification

## Benefits

✅ **No SMTP required**: Test locally without email server
✅ **Visual verification**: See exactly what customers receive
✅ **Debugging**: Catch email issues before production
✅ **Workflow validation**: Verify notification timing
✅ **Performance**: No network delays
✅ **History**: Keep all test emails for reference

## Security Note

⚠️ **Development only**: This system is for development environments only. In production, emails are sent normally via SMTP.

⚠️ **Sensitive data**: Don't commit `static/dev_emails/` to git - add to `.gitignore`
