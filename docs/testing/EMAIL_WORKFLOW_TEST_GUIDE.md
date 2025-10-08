# Quick Start: Testing Email Workflow

## 🚀 Setup (One-Time)

1. **Set Development Mode**
   ```bash
   # Windows CMD
   set FLASK_ENV=development
   
   # Windows PowerShell
   $env:FLASK_ENV="development"
   
   # Linux/Mac
   export FLASK_ENV=development
   ```

2. **Start Server**
   ```bash
   python app.py
   ```

3. **Open Email Inbox** (in browser)
   ```
   http://localhost:8000/static/dev_emails/index.html
   ```
   Keep this tab open - it auto-refreshes every 5 seconds!

---

## 🧪 Test Email Workflow

### Test 1: Quick Email Test (Verify System Works)

Run the test script:
```bash
python test_email_mock.py
```

**Expected Output:**
```
📧 Test 1: Customer Order Confirmation Email
✅ [DEV] Email saved to: static/dev_emails/...
📧 Test 2: Admin Order Notification Email
✅ [DEV] Email saved to: static/dev_emails/...
📧 Test 3: Admin Driver Action Notification
✅ [DEV] Email saved to: static/dev_emails/...
✅ Generated 3 email files
```

**Check inbox** - you should see 3 emails! ✅

---

### Test 2: Complete Order Workflow (Full Verification)

Follow this complete flow and count emails:

#### 1️⃣ **Customer Creates Order**
- Go to: http://localhost:8000/order/new
- Complete the order wizard
- Submit order

**Check inbox:** 
- ✅ 1 admin email: "Uusi tilaus #X - Vahvistus tarvitaan"
- ✅ 1 customer email: "Tilausvahvistus #X"
- **Total so far: 2 emails**

---

#### 2️⃣ **Admin Confirms Order**
- Login as admin
- Go to admin dashboard
- Find the order
- Set car details (brand, model, driver reward)
- Change status to **CONFIRMED**

**Check inbox:**
- ✅ 1 customer email: "Tilaus #X - Vahvistettu"
- **Total so far: 3 emails**

---

#### 3️⃣ **Driver Accepts Job** ⚠️ Critical Test!
- Logout, login as driver
- Go to driver dashboard
- Click on available job
- Click "Ota työ"

**Check inbox:**
- ✅ 1 admin email: "Kuljettajan toimenpide tilaus #X"
- ✅ 1 driver email: "Uusi tehtävä #X"
- ❌ **NO customer email!** (This is the fix!)
- **Total so far: 5 emails**

**✅ CORRECT**: Customer NOT notified when driver accepts
**❌ WRONG**: If you see customer email here, fix didn't work

---

#### 4️⃣ **Driver Arrives at Pickup**
- Click "📍 Saavuin noutopaikalle"

**Check inbox:**
- ✅ 1 admin email: "Kuljettajan toimenpide - Saapunut noutopaikalle"
- ❌ NO customer email
- **Total so far: 6 emails**

---

#### 5️⃣ **Driver Uploads Pickup Photos**
- Upload 1-2 photos

**Check inbox:**
- ✅ 1 admin email per photo upload
- ❌ NO customer email
- **Total so far: 7-8 emails**

**Driver UI Check:**
- ✅ Should see: "⏳ Odottaa admin hyväksyntää"
- ❌ Should NOT see: "Aloita kuljetus" button

---

#### 6️⃣ **Admin Starts Transport** ⚠️ Critical Test!
- Login as admin
- Go to order detail
- Change status to **IN_TRANSIT**

**Check inbox:**
- ✅ 1 customer email: "Tilaus #X - Kuljetuksessa"
- **Total so far: 8-9 emails**

**✅ CORRECT**: Customer NOW notified after admin verification

---

#### 7️⃣ **Driver Arrives at Delivery**
- Login as driver
- Click "📍 Saavuin toimituspaikalle"

**Check inbox:**
- ✅ 1 admin email: "Saapunut toimituspaikalle"
- ❌ NO customer email
- **Total so far: 9-10 emails**

---

#### 8️⃣ **Driver Uploads Delivery Photos**
- Upload 1-2 photos

**Check inbox:**
- ✅ 1 admin email per photo upload
- ❌ NO customer email
- **Total so far: 10-12 emails**

**Driver UI Check:**
- ✅ Should see: "⏳ Odottaa admin hyväksyntää"
- ❌ Should NOT see: "Päätä toimitus" button

---

#### 9️⃣ **Admin Completes Delivery** ⚠️ Critical Test!
- Login as admin
- Go to order detail
- Change status to **DELIVERED**

**Check inbox:**
- ✅ 1 customer email: "Tilaus #X - Toimitettu"
- **Total so far: 11-13 emails**

**✅ CORRECT**: Customer NOW notified after admin verification

---

## 📊 Expected Email Count Summary

| Recipient | Expected Count | Key Emails |
|-----------|----------------|------------|
| **Customer** | **4 emails** | Order confirmation, Vahvistettu, Kuljetuksessa, Toimitettu |
| **Admin** | **5-7 emails** | New order, driver actions (accept, arrive×2, photos) |
| **Driver** | **1 email** | Assignment notification |
| **TOTAL** | **10-12 emails** | Varies with photo uploads |

---

## ✅ Success Criteria

### Customer Emails (4 total):
1. ✅ "Tilausvahvistus" - when order created
2. ✅ "Vahvistettu" - when admin confirms
3. ✅ "Kuljetuksessa" - when admin sets IN_TRANSIT
4. ✅ "Toimitettu" - when admin sets DELIVERED

### Customer Should NOT Receive:
- ❌ Email when driver accepts job
- ❌ Email when driver arrives at pickup
- ❌ Email when driver uploads pickup photos
- ❌ Email when driver arrives at delivery
- ❌ Email when driver uploads delivery photos

### Admin Should Receive:
- ✅ Email when customer creates order
- ✅ Email when driver accepts job
- ✅ Email for all driver actions (arrive, photos)

---

## 🐛 Troubleshooting

### No emails appearing?
```bash
# Check console output
# Should see: [DEV MODE] Saving email to file instead of sending...
```

### Wrong email count?
1. Clear emails: `del static\dev_emails\*.html`
2. Start fresh test from step 1
3. Count carefully at each step

### Can't find inbox?
```
http://localhost:8000/static/dev_emails/index.html
```

### Want to start over?
```bash
# Delete all test emails
del static\dev_emails\*.html  # Windows
rm -f static/dev_emails/*.html  # Linux/Mac
```

---

## 🎯 Critical Tests

**Test A: Driver Accept (Step 3)**
- ✅ PASS: Customer gets NO email
- ❌ FAIL: Customer gets "Kuljettaja määritetty" email

**Test B: Driver Cannot Start Transport (Step 5)**
- ✅ PASS: Driver sees "⏳ Odottaa admin hyväksyntää"
- ❌ FAIL: Driver sees "Aloita kuljetus" button

**Test C: Driver Cannot Complete (Step 8)**
- ✅ PASS: Driver sees "⏳ Odottaa admin hyväksyntää"
- ❌ FAIL: Driver sees "Päätä toimitus" button

**Test D: Customer Email Count**
- ✅ PASS: Customer receives exactly 4 emails
- ❌ FAIL: Customer receives 5 or more emails

---

## 📸 What You Should See

### Email Inbox (index.html):
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Development Email Inbox
All emails are saved here instead of being sent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Emails: 12 | Last Updated: 2025-10-06 14:30:52

📨 Tilaus 999 Toimitettu
   🕐 2025-10-06 14:30:52
   [View Email]

📨 Kuljettajan toimenpide tilaus 999
   🕐 2025-10-06 14:28:15
   [View Email]

📨 Tilaus 999 Kuljetuksessa
   🕐 2025-10-06 14:25:30
   [View Email]

... (more emails)
```

### Console Output:
```
[EMAIL] Attempting to send email
   From: support@levoro.fi
   To: ['customer@example.com']
   Subject: Tilaus #999 - Vahvistettu
   [DEV MODE] Saving email to file instead of sending...
   ✅ [DEV] Email saved to: static/dev_emails/20251006_143052_Tilaus_999_Vahvistettu.html
   🌐 [DEV] View at: http://localhost:8000/static/dev_emails/20251006_143052_Tilaus_999_Vahvistettu.html
   📋 [DEV] Email index: http://localhost:8000/static/dev_emails/index.html
```

---

## 💡 Tips

1. **Keep inbox open** - it auto-refreshes, so you see new emails instantly
2. **Check console** - every email prints a confirmation
3. **Count emails** - verify customer gets exactly 4 emails
4. **Test multiple times** - workflow should be consistent
5. **Clear between tests** - fresh start helps catch issues

---

## 🎉 When Tests Pass

You've successfully verified:
- ✅ Email workflow fixed
- ✅ Customer only gets key notifications
- ✅ Admin verification workflow working
- ✅ Driver UI restrictions in place
- ✅ Ready for production testing!

Next step: Test in production environment with real email delivery.
