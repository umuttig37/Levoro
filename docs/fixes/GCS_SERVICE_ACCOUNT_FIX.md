# GCS Service Account Authentication Fix

## Problem
Driver license upload to private GCS bucket fails with error:
```
Virhe ajokortin etupuolen tallentamisessa: GCS private upload failed: ('invalid_grant: Invalid grant: account not found', {'error': 'invalid_grant', 'error_description': 'Invalid grant: account not found'})
```

**Root Cause:** The service account credentials are invalid, expired, or the service account was deleted from Google Cloud.

## Solution: Create/Update GCS Service Account

### Step 1: Access Google Cloud Console

1. Go to https://console.cloud.google.com/
2. Select project: **levoro-473806**

### Step 2: Create or Verify Service Account

#### Option A: Service Account Exists (Re-create Credentials)

If the service account `levoro-storage-uploader` exists:

1. Go to **IAM & Admin** → **Service Accounts**
2. Find: `levoro-storage-uploader@levoro-473806.iam.gserviceaccount.com`
3. Click on the service account
4. Go to **KEYS** tab
5. Click **ADD KEY** → **Create new key**
6. Choose **JSON** format
7. Click **CREATE** - a JSON file will download
8. **Delete the old key** for security (optional but recommended)

#### Option B: Service Account Doesn't Exist (Create New)

1. Go to **IAM & Admin** → **Service Accounts**
2. Click **+ CREATE SERVICE ACCOUNT**
3. Fill in details:
   - **Name:** `levoro-storage-uploader`
   - **Description:** `Service account for uploading images to GCS buckets`
4. Click **CREATE AND CONTINUE**
5. Grant these roles:
   - **Storage Object Admin** (for `levoro-transport-images` bucket)
   - **Storage Object Admin** (for `levoro-transport-images-private` bucket)
6. Click **CONTINUE** → **DONE**
7. Click on the newly created service account
8. Go to **KEYS** tab → **ADD KEY** → **Create new key**
9. Choose **JSON** format → **CREATE**
10. A JSON file will download

### Step 3: Verify Bucket Permissions

Ensure both buckets exist and have proper permissions:

#### Public Bucket: `levoro-transport-images`
1. Go to **Cloud Storage** → **Buckets**
2. Select `levoro-transport-images`
3. Go to **PERMISSIONS** tab
4. Verify the service account has **Storage Object Admin** role
5. Ensure bucket is publicly accessible (allUsers = Storage Object Viewer)

#### Private Bucket: `levoro-transport-images-private`
1. Go to **Cloud Storage** → **Buckets**
2. Select `levoro-transport-images-private`
3. Go to **PERMISSIONS** tab
4. Verify the service account has **Storage Object Admin** role
5. Ensure bucket is NOT publicly accessible (no allUsers permission)

**If buckets don't exist, create them:**

```bash
# Public bucket for order images
gsutil mb -p levoro-473806 -c STANDARD -l EUROPE-NORTH1 gs://levoro-transport-images
gsutil iam ch allUsers:objectViewer gs://levoro-transport-images

# Private bucket for driver licenses
gsutil mb -p levoro-473806 -c STANDARD -l EUROPE-NORTH1 gs://levoro-transport-images-private
# Do NOT add public access
```

### Step 4: Update Application Credentials

1. Open the downloaded JSON credentials file
2. Base64 encode the entire JSON content:

**On Windows (PowerShell):**
```powershell
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Content service-account-key.json -Raw)))
```

**On Linux/Mac:**
```bash
base64 -w 0 service-account-key.json
```

3. Copy the base64 output
4. Update `.env` file:
```env
GCS_CREDENTIALS_JSON=<paste base64 here>
```

5. Update production environment (Render.com):
   - Go to Render.com dashboard
   - Select your service
   - Go to **Environment** tab
   - Update `GCS_CREDENTIALS_JSON` with new base64 value
   - Save changes
   - Redeploy if necessary

### Step 5: Test the Fix

**Local Testing:**
```bash
# Activate virtual environment
.venv\Scripts\activate

# Run the application
python app.py

# Try submitting a driver application with license images
# Navigate to: http://localhost:8000/hae-kuljettajaksi
```

**Production Testing:**
1. Deploy updated environment variables to production
2. Submit a test driver application
3. Upload driver license images
4. Verify no errors in logs

### Step 6: Verify GCS Initialization

Check the application startup logs for:

**✅ Success:**
```
[GCS] Enabled - images will be stored in: orders/{order_id}/{filename}
[GCS] Bucket: levoro-transport-images
[GCS] Project: levoro-473806
```

**❌ Failure (Old Issue):**
```
[GCS] Failed to initialize GCS client: ('invalid_grant: Invalid grant: account not found', {...})
[GCS] Image uploads will fall back to local storage
```

## Security Best Practices

1. **Never commit service account JSON files to Git**
   - Always use base64-encoded environment variables
   - Add `*.json` to `.gitignore` (already done)

2. **Rotate credentials regularly**
   - Delete old keys after creating new ones
   - Best practice: rotate every 90 days

3. **Principle of least privilege**
   - Only grant necessary permissions (Storage Object Admin)
   - Don't grant Project Editor or Owner roles

4. **Monitor access**
   - Check Cloud Logging for unauthorized access attempts
   - Set up alerts for unusual activity

## Troubleshooting

### Issue: Still getting "account not found" error

**Solution:**
- Verify the base64 encoding is correct (no newlines, complete)
- Check that the JSON file contains all required fields
- Ensure the service account email matches what's in the JSON
- Try creating a completely new service account

### Issue: "Permission denied" errors

**Solution:**
- Verify service account has **Storage Object Admin** role on BOTH buckets
- Check bucket IAM policy includes the service account
- Ensure buckets exist in the same project

### Issue: Images uploaded but not accessible

**Solution:**
- Public bucket: Verify `allUsers` has `Storage Object Viewer` role
- Private bucket: Use signed URLs (already implemented in `gcs_service.py`)

## Files Modified
None - this is a configuration-only fix.

## Related Files
- `services/gcs_service.py` - GCS service implementation
- `app.py` - Driver license upload logic (lines 975-1010)
- `.env` - Environment configuration
