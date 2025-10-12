# GCS Bucket Migration - Quick Start Guide

## 🚀 Quick Setup (3 Steps)

### Step 1: Create New Project & Buckets

**On Windows:**
```powershell
# Open PowerShell as Administrator
cd C:\Users\Lenovo\Desktop\DEV\vscode\Levoro\scripts

# Run setup script with your NEW project ID
.\setup-gcs-buckets.ps1 -ProjectId "levoro-XXXXXX"
```

**On Linux/Mac:**
```bash
# Make executable
chmod +x setup-gcs-buckets.sh

# Run setup script with your NEW project ID
./setup-gcs-buckets.sh levoro-XXXXXX
```

**What this does:**
- ✅ Enables Cloud Storage APIs
- ✅ Creates service account (`levoro-storage-uploader`)
- ✅ Creates public bucket (`levoro-transport-images`)
- ✅ Creates private bucket (`levoro-transport-images-private`)
- ✅ Sets up permissions correctly
- ✅ Downloads service account key
- ✅ Converts credentials to base64
- ✅ Displays environment variables to copy

---

### Step 2: Update Your Environment

The script outputs something like this:

```
========================================
Setup Complete!
========================================

Add these to your .env file:

GCS_PROJECT_ID=levoro-789012
GCS_BUCKET_NAME=levoro-transport-images
GCS_PRIVATE_BUCKET_NAME=levoro-transport-images-private
GCS_CREDENTIALS_JSON=eyJwcm9qZWN0X2lkIjogImxldm9yby00NzM4MDYiLC...
```

**Copy these values to your `.env` file:**

1. Open `.env` file in VS Code
2. Find the GCS section (or add it)
3. Paste the values from script output
4. Save the file

**Example `.env`:**
```env
# ... other variables ...

# Google Cloud Storage Configuration
GCS_PROJECT_ID=levoro-789012
GCS_BUCKET_NAME=levoro-transport-images
GCS_PRIVATE_BUCKET_NAME=levoro-transport-images-private
GCS_CREDENTIALS_JSON=eyJwcm9qZWN0X2lkIjogImxldm9yby00NzM4MDYiLC4uLg==
```

---

### Step 3: Verify & Test

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
# OR
source .venv/bin/activate  # Linux/Mac

# Run verification script
python scripts/verify-gcs-setup.py
```

**Expected output:**
```
✅ All checks passed! GCS is ready to use.
```

---

## 📋 Complete Checklist

### Pre-Setup
- [ ] Google Cloud account with billing enabled
- [ ] New billing account created
- [ ] gcloud CLI installed ([Install here](https://cloud.google.com/sdk/docs/install))
- [ ] Authenticated with gcloud: `gcloud auth login`

### Google Cloud Setup (Automated by script)
- [ ] New project created in Google Cloud Console
- [ ] Project ID noted down
- [ ] Ran setup script successfully
- [ ] Service account key downloaded

### Application Setup
- [ ] Copied environment variables to `.env`
- [ ] Ran `verify-gcs-setup.py` successfully
- [ ] Restarted local development server
- [ ] Checked startup logs for GCS initialization

### Production Setup
- [ ] Updated production environment variables (Render/Heroku)
- [ ] Deployed to production
- [ ] Verified GCS in production logs

### Testing
- [ ] Created test order
- [ ] Uploaded order images (public bucket)
- [ ] Submitted driver application (private bucket)
- [ ] Verified images accessible
- [ ] Verified private images NOT directly accessible

### Cleanup
- [ ] Deleted service account key file from local machine
- [ ] Added `*.json` to `.gitignore` (already done)
- [ ] Documented project ID in secure location

---

## 🔧 Manual Setup (If You Need It)

If you prefer to set everything up manually or the script fails, follow the detailed guide:

📖 **[Complete Setup Guide](./GCS_NEW_BUCKET_SETUP_GUIDE.md)**

This includes:
- Step-by-step Google Cloud Console instructions
- Detailed explanations of each step
- Troubleshooting section
- Security best practices
- Cost estimation
- Monitoring setup

---

## 🧪 Testing Guide

### Test 1: Local Development

```bash
# Start application
python app.py

# Check startup logs for:
[GCS] Enabled - images will be stored in: orders/{order_id}/{filename}
[GCS] Bucket: levoro-transport-images
[GCS] Project: levoro-XXXXXX
```

### Test 2: Order Images (Public Bucket)

1. Navigate to: http://localhost:8000/order/new/step1
2. Create complete order
3. Accept order as driver (if you have test driver)
4. Upload images at pickup
5. Check logs for successful upload
6. Verify images in GCS Console

### Test 3: Driver License Images (Private Bucket)

1. Navigate to: http://localhost:8000/hae-kuljettajaksi
2. Fill application form
3. Upload driver license images
4. Check logs for successful upload
5. Verify images in GCS Console (should be private)

---

## 🆘 Troubleshooting

### Issue: "gcloud: command not found"

**Solution:**
1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
2. Restart terminal
3. Run: `gcloud auth login`

---

### Issue: "Permission denied" when creating buckets

**Solution:**
1. Check you're authenticated: `gcloud auth list`
2. Check correct project is set: `gcloud config get-value project`
3. Ensure you have Owner or Editor role on project

---

### Issue: Verification script fails

**Check:**
1. `.env` file has correct variables
2. No spaces around `=` in `.env`
3. No line breaks in `GCS_CREDENTIALS_JSON`
4. Virtual environment is activated

---

### Issue: Images still uploading to local storage

**Check:**
1. Restart application after updating `.env`
2. Check startup logs for GCS status
3. Run verification script: `python scripts/verify-gcs-setup.py`
4. Ensure `GCS_CREDENTIALS_JSON` is complete (very long string)

---

### Issue: Public images not accessible

**Check:**
1. Run: `gsutil iam get gs://levoro-transport-images | grep allUsers`
2. Should see: `"members": ["allUsers"]`
3. If not, run: `gsutil iam ch allUsers:objectViewer gs://levoro-transport-images`

---

## 📁 Files Created

```
scripts/
├── setup-gcs-buckets.ps1       # Windows setup script
├── setup-gcs-buckets.sh        # Linux/Mac setup script
├── verify-gcs-setup.py         # Verification script
├── cors.json                   # CORS configuration
└── .env.gcs.template          # Environment template

docs/
├── GCS_NEW_BUCKET_SETUP_GUIDE.md      # Complete detailed guide
├── GCS_MIGRATION_SCRIPTS.md           # Script documentation
└── GCS_QUICK_START.md                 # This file
```

---

## 🔐 Security Reminders

1. **Never commit service account JSON files to Git**
   - Already in `.gitignore`
   - Delete after converting to base64

2. **Keep base64 credentials secure**
   - Store in password manager
   - Rotate every 90 days

3. **Monitor access**
   - Set up budget alerts in Google Cloud
   - Review Cloud Logging periodically

4. **Use environment variables**
   - Never hardcode credentials
   - Different credentials for dev/prod

---

## 💰 Cost Monitoring

After setup, monitor costs in Google Cloud Console:

1. **Navigate to:** Billing → Reports
2. **Filter by:** Cloud Storage
3. **Check:** Daily/Weekly costs

**Expected costs:** €1-5/month for small scale

**Set up budget alert:**
1. Billing → Budgets & alerts
2. Create budget (e.g., €10/month)
3. Set alerts at 50%, 90%, 100%

---

## 📞 Support

**Documentation:**
- [Main Guide](./GCS_NEW_BUCKET_SETUP_GUIDE.md) - Complete setup instructions
- [Scripts Reference](./GCS_MIGRATION_SCRIPTS.md) - All script details
- [Original Fix Guide](./fixes/GCS_SERVICE_ACCOUNT_FIX.md) - Troubleshooting reference

**External Resources:**
- [Google Cloud Storage Docs](https://cloud.google.com/storage/docs)
- [Service Accounts Guide](https://cloud.google.com/iam/docs/service-accounts)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)

---

## ✅ Success Criteria

You've successfully migrated when:

- ✅ Verification script passes all checks
- ✅ Application starts with `[GCS] Enabled` in logs
- ✅ Order images upload to new public bucket
- ✅ Driver license images upload to new private bucket
- ✅ Public images accessible via URL
- ✅ Private images NOT directly accessible
- ✅ Production deployment works correctly

---

**Last updated:** 2025-01-08
**Version:** 1.0
