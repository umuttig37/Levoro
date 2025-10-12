# GCS New Bucket Setup Guide - Complete Migration

## Overview

This guide walks you through setting up new Google Cloud Storage buckets for a new billing account and project while maintaining the same bucket names and policies from your existing setup.

**Current Setup:**
- Project: `levoro-473806`
- Public Bucket: `levoro-kuljetus-images`
- Private Bucket: `levoro-kuljetus-images-private`
- Region: `EUROPE-NORTH1`

**New Setup:**
- Project: `[NEW_PROJECT_ID]` ← You'll choose this
- Public Bucket: `levoro-kuljetus-images` (same name)
- Private Bucket: `levoro-kuljetus-images-private` (same name)
- Region: `EUROPE-NORTH1` (same)

---

## Part 1: Google Cloud Console Setup

### Step 1: Create New Google Cloud Project

1. **Go to Google Cloud Console:** https://console.cloud.google.com/
2. **Click Project Dropdown** (top navigation bar)
3. **Click "NEW PROJECT"**
4. **Fill in project details:**
   - **Project name:** `Levoro kuljetus` (or your preferred name)
   - **Project ID:** `levoro-XXXXXX` (must be globally unique)
     - Google will suggest one, but you can customize
     - **Write this down** - you'll need it later
   - **Organization:** Select your organization or "No organization"
   - **Location:** Browse to select your billing account
5. **Click "CREATE"**
6. **Wait** for project creation (usually takes 1-2 minutes)

---

### Step 2: Link New Billing Account

1. **Navigate to:** Billing → Account Management
2. **Ensure** your new billing account is linked to the project
3. **If not linked:**
   - Click "LINK A BILLING ACCOUNT"
   - Select your new billing account
   - Confirm

---

### Step 3: Enable Required APIs

1. **Navigate to:** APIs & Services → Library
2. **Enable these APIs:**
   - **Cloud Storage API** (search "Cloud Storage")
   - **Cloud Storage JSON API** (should auto-enable)

**Or use gcloud CLI:**
```bash
gcloud services enable storage-api.googleapis.com --project=[NEW_PROJECT_ID]
gcloud services enable storage-component.googleapis.com --project=[NEW_PROJECT_ID]
```

---

### Step 4: Create Service Account

This service account will be used by your application to upload images.

1. **Navigate to:** IAM & Admin → Service Accounts
2. **Click:** + CREATE SERVICE ACCOUNT
3. **Fill in details:**
   - **Service account name:** `levoro-storage-uploader`
   - **Service account ID:** `levoro-storage-uploader` (auto-fills)
   - **Description:** `Service account for uploading images to GCS buckets`
4. **Click:** CREATE AND CONTINUE
5. **Grant roles:**
   - Click "Select a role"
   - Search for "Storage Object Admin"
   - Select **Storage Object Admin**
   - **Click:** + ADD ANOTHER ROLE (to add it again for second bucket)
   - Select **Storage Object Admin** again
6. **Click:** CONTINUE → DONE

**Service account email will be:**
```
levoro-storage-uploader@[NEW_PROJECT_ID].iam.gserviceaccount.com
```

---

### Step 5: Create Service Account Key (Credentials)

1. **In Service Accounts page**, click on `levoro-storage-uploader`
2. **Go to KEYS tab**
3. **Click:** ADD KEY → Create new key
4. **Choose:** JSON format
5. **Click:** CREATE
6. **A JSON file downloads** - keep it safe!
   - ⚠️ **IMPORTANT:** Never commit this file to Git
   - Store securely (password manager, encrypted folder)
   - Named something like: `levoro-XXXXXX-abc123def456.json`

---

### Step 6: Create Storage Buckets

#### Option A: Using Google Cloud Console (GUI)

##### Public Bucket: `levoro-kuljetus-images`

1. **Navigate to:** Cloud Storage → Buckets
2. **Click:** CREATE
3. **Configure bucket:**
   - **Name:** `levoro-kuljetus-images`
   - **Location type:** Region
   - **Region:** `europe-north1` (Finland)
   - **Storage class:** Standard
   - **Access control:** Uniform (recommended)
   - **Protection tools:**
     - ❌ Uncheck "Enforce public access prevention"
     - ✅ Keep "Soft delete policy" enabled (7 days retention)
   - **Encryption:** Google-managed key
4. **Click:** CREATE
5. **If warning about public access:** Click "CONFIRM" to allow

**Set public access:**
1. Click on the newly created bucket
2. Go to **PERMISSIONS** tab
3. Click **GRANT ACCESS**
4. **Add principals:**
   - **New principals:** `allUsers`
   - **Role:** Storage Object Viewer
5. Click **SAVE**
6. **Confirm** public access warning

##### Private Bucket: `levoro-kuljetus-images-private`

1. **Navigate to:** Cloud Storage → Buckets
2. **Click:** CREATE
3. **Configure bucket:**
   - **Name:** `levoro-kuljetus-images-private`
   - **Location type:** Region
   - **Region:** `europe-north1` (Finland)
   - **Storage class:** Standard
   - **Access control:** Uniform (recommended)
   - **Protection tools:**
     - ✅ Enforce public access prevention (KEEP CHECKED)
     - ✅ Keep "Soft delete policy" enabled (7 days retention)
   - **Encryption:** Google-managed key
4. **Click:** CREATE
5. **Do NOT add public access** - this bucket should remain private

---

#### Option B: Using gcloud CLI (Faster)

**Prerequisites:**
```bash
# Install Google Cloud SDK if not already installed
# Download from: https://cloud.google.com/sdk/docs/install

# Initialize and authenticate
gcloud init
gcloud auth login

# Set your new project
gcloud config set project [NEW_PROJECT_ID]
```

**Create buckets:**
```bash
# Create PUBLIC bucket for order images
gsutil mb -p [NEW_PROJECT_ID] -c STANDARD -l EUROPE-NORTH1 gs://levoro-kuljetus-images

# Make bucket publicly readable
gsutil iam ch allUsers:objectViewer gs://levoro-kuljetus-images

# Verify public access
gsutil iam get gs://levoro-kuljetus-images

# Create PRIVATE bucket for driver licenses
gsutil mb -p [NEW_PROJECT_ID] -c STANDARD -l EUROPE-NORTH1 gs://levoro-kuljetus-images-private

# Verify private bucket (should NOT have allUsers)
gsutil iam get gs://levoro-kuljetus-images-private
```

**Expected output for public bucket:**
```json
{
  "bindings": [
    {
      "members": [
        "allUsers"
      ],
      "role": "roles/storage.objectViewer"
    }
  ]
}
```

---

### Step 7: Grant Service Account Bucket Permissions

**For each bucket, grant Storage Object Admin role to service account:**

#### Using Google Cloud Console:

1. **Navigate to:** Cloud Storage → Buckets
2. **Click on bucket:** `levoro-kuljetus-images`
3. **Go to:** PERMISSIONS tab
4. **Click:** GRANT ACCESS
5. **Add principals:**
   - **New principals:** `levoro-storage-uploader@[NEW_PROJECT_ID].iam.gserviceaccount.com`
   - **Role:** Storage Object Admin
6. **Click:** SAVE
7. **Repeat for:** `levoro-kuljetus-images-private` bucket

#### Using gcloud CLI:

```bash
# Grant permissions to PUBLIC bucket
gsutil iam ch serviceAccount:levoro-storage-uploader@[NEW_PROJECT_ID].iam.gserviceaccount.com:roles/storage.objectAdmin gs://levoro-kuljetus-images

# Grant permissions to PRIVATE bucket
gsutil iam ch serviceAccount:levoro-storage-uploader@[NEW_PROJECT_ID].iam.gserviceaccount.com:roles/storage.objectAdmin gs://levoro-kuljetus-images-private

# Verify permissions
gsutil iam get gs://levoro-kuljetus-images
gsutil iam get gs://levoro-kuljetus-images-private
```

---

### Step 8: Configure CORS (Optional but Recommended)

This allows your web app to directly upload from browser (if you implement that later).

**Create `cors.json` file:**
```json
[
  {
    "origin": ["https://your-production-domain.com", "http://localhost:8000"],
    "method": ["GET", "POST", "PUT", "DELETE"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
```

**Apply CORS configuration:**
```bash
gsutil cors set cors.json gs://levoro-kuljetus-images
gsutil cors set cors.json gs://levoro-kuljetus-images-private
```

---

## Part 2: Application Configuration

### Step 9: Prepare Service Account Credentials

You need to convert the JSON credentials to base64 format for secure storage.

#### On Windows (PowerShell):

```powershell
# Navigate to where you saved the JSON file
cd C:\path\to\downloaded\file

# Convert to base64
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Content levoro-XXXXXX-abc123def456.json -Raw)))
```

#### On Linux/Mac:

```bash
# Navigate to where you saved the JSON file
cd /path/to/downloaded/file

# Convert to base64 (no line breaks)
base64 -w 0 levoro-XXXXXX-abc123def456.json

# Or on Mac:
base64 -i levoro-XXXXXX-abc123def456.json
```

**Copy the entire base64 output** - you'll need it in the next steps.

---

### Step 10: Update Local Environment (.env)

Edit your `.env` file and update these variables:

```env
# Google Cloud Storage Configuration
GCS_PROJECT_ID=[NEW_PROJECT_ID]
GCS_BUCKET_NAME=levoro-kuljetus-images
GCS_PRIVATE_BUCKET_NAME=levoro-kuljetus-images-private
GCS_CREDENTIALS_JSON=[PASTE_BASE64_HERE]
```

**Example:**
```env
GCS_PROJECT_ID=levoro-789012
GCS_BUCKET_NAME=levoro-kuljetus-images
GCS_PRIVATE_BUCKET_NAME=levoro-kuljetus-images-private
GCS_CREDENTIALS_JSON=ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAibGV2b3JvLTQ3MzgwNiIsCiAgInByaXZhdGVfa2V5X2lkIjogImFiY2RlZjEyMzQ1NiIsCiAgInByaXZhdGVfa2V5IjogIi0tLS0tQkVHSU4gUFJJVkFURSBLRVktLS0tLVxuLi4uXG4tLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tXG4iLAogICJjbGllbnRfZW1haWwiOiAibGV2b3JvLXN0b3JhZ2UtdXBsb2FkZXJAbGV2b3JvLTQ3MzgwNi5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsCiAgImNsaWVudF9pZCI6ICIxMjM0NTY3ODkwIiwKICAiYXV0aF91cmkiOiAiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLAogICJ0b2tlbl91cmkiOiAiaHR0cHM6Ly9vYXV0aDIuZ29vZ2xlYXBpcy5jb20vdG9rZW4iLAogICJhdXRoX3Byb3ZpZGVyX3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vb2F1dGgyL3YxL2NlcnRzIiwKICAiY2xpZW50X3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vcm9ib3QvdjEvbWV0YWRhdGEveDUwOS9sZXZvcm8tc3RvcmFnZS11cGxvYWRlciU0MGxldm9yby00NzM4MDYuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iCn0K
```

**⚠️ Security Warning:**
- Never commit `.env` file to Git
- The base64 string will be very long (2000+ characters) - that's normal
- Make sure there are no line breaks in the base64 string

---

### Step 11: Update Production Environment

If you're using Render.com, Heroku, or another hosting platform:

#### Render.com:
1. Go to your Render.com dashboard
2. Select your service
3. Go to **Environment** tab
4. Update/Add these environment variables:
   - `GCS_PROJECT_ID` = `[NEW_PROJECT_ID]`
   - `GCS_BUCKET_NAME` = `levoro-kuljetus-images`
   - `GCS_PRIVATE_BUCKET_NAME` = `levoro-kuljetus-images-private`
   - `GCS_CREDENTIALS_JSON` = `[PASTE_BASE64_HERE]`
5. Click **Save Changes**
6. **Manual Deploy** (if auto-deploy isn't triggered)

#### Heroku:
```bash
heroku config:set GCS_PROJECT_ID=[NEW_PROJECT_ID] --app your-app-name
heroku config:set GCS_BUCKET_NAME=levoro-kuljetus-images --app your-app-name
heroku config:set GCS_PRIVATE_BUCKET_NAME=levoro-kuljetus-images-private --app your-app-name
heroku config:set GCS_CREDENTIALS_JSON=[PASTE_BASE64_HERE] --app your-app-name
```

#### Other Platforms:
- Set the same environment variables through your platform's configuration interface

---

## Part 3: Testing & Verification

### Step 12: Test Local Development

```bash
# Activate virtual environment
.venv\Scripts\activate

# Run application
python app.py
```

**Check startup logs for:**
```
[GCS] Enabled - images will be stored in: orders/{order_id}/{filename}
[GCS] Bucket: levoro-kuljetus-images
[GCS] Project: [NEW_PROJECT_ID]
```

**✅ If you see this, GCS is working!**

**❌ If you see errors:**
```
[GCS] Not configured - image upload will use local storage
[GCS] Missing environment variables: ...
```
→ Go back and check your `.env` file

---

### Step 13: Test Image Upload

#### Test 1: Order Images (Public Bucket)

1. **Create a test order:**
   - Navigate to: http://localhost:8000/order/new/step1
   - Complete all steps
   - Submit order

2. **Accept order as driver** (if you have test driver account)

3. **Upload pickup images:**
   - Navigate to driver dashboard
   - Click on order
   - Upload images at pickup location

4. **Check logs** for successful upload:
```
[GCS] Uploading to public bucket: orders/123/pickup_abc123.jpg
```

5. **Verify in GCS Console:**
   - Go to Cloud Storage → Buckets
   - Open `levoro-kuljetus-images`
   - Check for `orders/123/` folder with images

6. **Verify public access:**
   - Copy the public URL from logs or bucket view
   - Open in incognito browser window
   - Image should load without authentication

---

#### Test 2: Driver License Images (Private Bucket)

1. **Submit driver application:**
   - Navigate to: http://localhost:8000/hae-kuljettajaksi
   - Fill in all fields
   - Upload driver license images (front and back)
   - Submit

2. **Check logs** for successful upload:
```
[GCS] Uploading to private bucket: driver-licenses/123/front.jpg
[GCS] Uploading to private bucket: driver-licenses/123/back.jpg
```

3. **Verify in GCS Console:**
   - Go to Cloud Storage → Buckets
   - Open `levoro-kuljetus-images-private`
   - Check for `driver-licenses/123/` folder with images

4. **Verify private access:**
   - Try to access blob URL directly
   - Should get "Access Denied" error (this is correct!)
   - Access should only work through signed URLs generated by app

---

### Step 14: Test Production Deployment

1. **Deploy to production** with updated environment variables
2. **Wait for deployment** to complete
3. **Check production logs** for GCS initialization
4. **Repeat Test 13** on production URL
5. **Monitor for errors** in logs

---

## Part 4: Monitoring & Maintenance

### Step 15: Set Up Monitoring (Optional but Recommended)

#### Enable Cloud Monitoring:
1. **Navigate to:** Monitoring → Dashboards
2. **Create dashboard** for storage metrics
3. **Add charts:**
   - Storage usage (bytes)
   - Request count
   - Egress bandwidth
   - Error rate

#### Set Up Alerts:
1. **Navigate to:** Monitoring → Alerting
2. **Create alert policies:**
   - High error rate (>5% errors in 5 minutes)
   - Unusual traffic spike (>1000 requests in 1 minute)
   - Storage quota warnings

#### Enable Cloud Logging:
1. **Navigate to:** Logging → Logs Explorer
2. **Filter by resource:**
   - Resource type: GCS Bucket
   - Bucket name: levoro-kuljetus-images
3. **Create log sinks** (optional):
   - Export logs to BigQuery for analysis
   - Export to Cloud Storage for archival

---

### Step 16: Configure Budget Alerts

1. **Navigate to:** Billing → Budgets & alerts
2. **Click:** CREATE BUDGET
3. **Set budget:**
   - **Name:** `GCS Storage Budget`
   - **Budget amount:** (your choice, e.g., 50 EUR/month)
   - **Threshold alerts:**
     - 50% of budget
     - 90% of budget
     - 100% of budget
   - **Email notifications:** Add your email
4. **Click:** FINISH

---

### Step 17: Security Best Practices

#### Rotate Service Account Keys Regularly:

**Every 90 days:**
1. Create new service account key (Step 5)
2. Update `.env` and production environment
3. Test the new credentials
4. Delete old key from GCS Console

#### Review IAM Permissions:

**Monthly:**
1. Navigate to IAM & Admin → IAM
2. Review all service accounts
3. Remove unused accounts
4. Verify principle of least privilege

#### Enable Audit Logging:

1. **Navigate to:** IAM & Admin → Audit Logs
2. **Enable for Cloud Storage:**
   - ✅ Admin Read
   - ✅ Data Read (careful - can be expensive)
   - ✅ Data Write

#### Enable VPC Service Controls (Advanced):

If your organization requires extra security:
1. Navigate to VPC Service Controls
2. Create security perimeter around GCS buckets
3. Restrict access to specific IP ranges or VPN

---

## Part 5: Migration Checklist

Use this checklist to ensure complete migration:

### Google Cloud Setup:
- [ ] New project created
- [ ] Billing account linked
- [ ] Cloud Storage API enabled
- [ ] Service account created (`levoro-storage-uploader`)
- [ ] Service account key downloaded (JSON)
- [ ] Public bucket created (`levoro-kuljetus-images`)
- [ ] Private bucket created (`levoro-kuljetus-images-private`)
- [ ] Public bucket has `allUsers:objectViewer` permission
- [ ] Private bucket does NOT have public access
- [ ] Service account has `Storage Object Admin` on both buckets
- [ ] CORS configured (optional)

### Application Configuration:
- [ ] Service account JSON converted to base64
- [ ] Local `.env` file updated
- [ ] Production environment variables updated
- [ ] Application restarted/redeployed

### Testing:
- [ ] Local startup logs show GCS enabled
- [ ] Order image upload works (public bucket)
- [ ] Driver license upload works (private bucket)
- [ ] Public images accessible via URL
- [ ] Private images NOT accessible via direct URL
- [ ] Production deployment successful
- [ ] Production image uploads working

### Monitoring & Security:
- [ ] Cloud Monitoring dashboard created
- [ ] Budget alerts configured
- [ ] Audit logging enabled
- [ ] Key rotation schedule set (90 days)
- [ ] Documentation updated

---

## Troubleshooting

### Issue: "Invalid grant: account not found"

**Causes:**
- Service account JSON is corrupted
- Base64 encoding has line breaks
- Service account was deleted

**Solutions:**
1. Verify base64 string has no newlines:
   ```bash
   # Should be one continuous string
   echo $GCS_CREDENTIALS_JSON | wc -l
   # Output should be: 1
   ```

2. Re-create service account key (Step 5)
3. Re-encode to base64 (Step 9)
4. Update environment variables (Step 10-11)

---

### Issue: "Permission denied" when uploading

**Causes:**
- Service account lacks permissions
- Bucket doesn't exist
- Wrong bucket name in environment variables

**Solutions:**
1. Verify bucket exists:
   ```bash
   gsutil ls -p [NEW_PROJECT_ID]
   ```

2. Check service account permissions:
   ```bash
   gsutil iam get gs://levoro-kuljetus-images
   ```

3. Grant permissions again (Step 7):
   ```bash
   gsutil iam ch serviceAccount:levoro-storage-uploader@[NEW_PROJECT_ID].iam.gserviceaccount.com:roles/storage.objectAdmin gs://levoro-kuljetus-images
   ```

---

### Issue: Public images not accessible

**Causes:**
- `allUsers` permission not set
- Public access prevention enabled

**Solutions:**
1. Check public access:
   ```bash
   gsutil iam get gs://levoro-kuljetus-images | grep allUsers
   ```

2. Add public access:
   ```bash
   gsutil iam ch allUsers:objectViewer gs://levoro-kuljetus-images
   ```

3. Verify in browser (incognito):
   ```
   https://storage.googleapis.com/levoro-kuljetus-images/orders/123/pickup_abc.jpg
   ```

---

### Issue: GCS initialization fails silently

**Causes:**
- Missing environment variables
- Typo in environment variable names

**Solutions:**
1. Print environment variables (don't log credentials!):
   ```python
   import os
   print(f"GCS_PROJECT_ID: {bool(os.getenv('GCS_PROJECT_ID'))}")
   print(f"GCS_BUCKET_NAME: {bool(os.getenv('GCS_BUCKET_NAME'))}")
   print(f"GCS_PRIVATE_BUCKET_NAME: {bool(os.getenv('GCS_PRIVATE_BUCKET_NAME'))}")
   print(f"GCS_CREDENTIALS_JSON: {bool(os.getenv('GCS_CREDENTIALS_JSON'))}")
   ```

2. Check for typos in `.env` file:
   - No spaces around `=`
   - No quotes around values (unless value contains spaces)
   - Correct variable names

---

### Issue: Images uploaded but with wrong path

**Causes:**
- `FLASK_ENV` not set correctly
- Image service using wrong environment detection

**Solutions:**
1. Check `FLASK_ENV`:
   ```bash
   # Development
   FLASK_ENV=development

   # Production (or leave unset)
   FLASK_ENV=production
   ```

2. Verify path in logs:
   ```
   # Development should use:
   dev/orders/123/pickup_abc.jpg

   # Production should use:
   orders/123/pickup_abc.jpg
   ```

---

## Cost Estimation

Based on typical usage patterns for a kuljetus service:

### Storage Costs (EUROPE-NORTH1):
- **Standard Storage:** ~€0.020 per GB/month
- **Estimated usage:** 10 GB (1000 orders × 10 images × 1 MB each)
- **Monthly cost:** €0.20

### Network Costs:
- **Egress to internet:** €0.12 per GB (first 1 TB)
- **Estimated usage:** 5 GB/month (image views)
- **Monthly cost:** €0.60

### Operations Costs:
- **Class A operations** (writes): €0.05 per 10,000 ops
- **Class B operations** (reads): €0.004 per 10,000 ops
- **Estimated usage:** 1,000 writes + 10,000 reads per month
- **Monthly cost:** €0.009

**Total estimated cost:** ~€1-2 EUR/month for small scale
**At 1000 orders/month:** ~€5-10 EUR/month

**Note:** First 5 GB egress per month is FREE on new billing accounts.

---

## Next Steps After Setup

1. **Monitor costs** for first month to establish baseline
2. **Set up lifecycle policies** (optional - auto-delete old dev images)
3. **Enable object versioning** (optional - recover deleted images)
4. **Consider CDN** (Cloud CDN) if you have high traffic
5. **Implement image optimization** (reduce storage/bandwidth costs)

---

## Support Resources

- **Google Cloud Storage Documentation:** https://cloud.google.com/storage/docs
- **Service Accounts Guide:** https://cloud.google.com/iam/docs/service-accounts
- **Pricing Calculator:** https://cloud.google.com/products/calculator
- **Support:** https://cloud.google.com/support

---

## Files Referenced

- `services/gcs_service.py` - GCS service implementation
- `.env` - Local environment configuration
- `CLAUDE.md` - Application architecture documentation
- `docs/fixes/GCS_SERVICE_ACCOUNT_FIX.md` - Original GCS troubleshooting guide

---

**Document created:** 2025-01-08
**Author:** GitHub Copilot
**Last updated:** 2025-01-08
**Version:** 1.0
