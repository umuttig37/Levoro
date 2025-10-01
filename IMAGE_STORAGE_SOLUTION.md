# Image Storage Problem & Solutions

## Problem Summary

### The Issue
Images uploaded to the application (pickup/delivery photos) are currently stored in the local filesystem at `static/uploads/orders/`. When deployed on **Render**, the filesystem is **ephemeral** - meaning all uploaded files are **lost on every deployment or container restart**.

### What Happened
1. Admin A uploads pickup images → saved to Container A's filesystem
2. Image metadata saved to MongoDB (persists ✓)
3. Developer deploys code update → New Container B created with empty filesystem
4. Admin B views the order → Database has image records, but files don't exist → **Images show as broken/missing**
5. Admin A uploads new delivery images → saved to Container B → Now visible

### Root Cause
**Render uses ephemeral containers** - each deployment creates a new instance with a fresh filesystem. Local file storage does not persist between deployments.

---

## Current Image Processing (Preserved in Both Solutions)

The app currently processes images with Pillow (PIL):
- **Resize**: Max width 1200px (maintains aspect ratio)
- **Compress**: Converts to JPEG at 80% quality with optimize flag
- **Convert transparency**: Adds white background for PNG alpha channels
- **Result**: 5MB uploads typically become 200-500KB

**Both solutions below maintain this processing** - we only change the final storage location.

---

## Solution Options

## Option 1: Google Cloud Storage (GCS) - Recommended

### Why GCS?
- ✅ Already using Google APIs (Places API)
- ✅ Direct browser access via public URLs (no Flask proxy)
- ✅ Built-in CDN support with Cloud CDN
- ✅ Lower cost than Render Disk ($0.020/GB/month)
- ✅ Industry standard for image hosting
- ✅ Scalable and reliable (99.95% SLA)
- ✅ Works on any hosting platform (not Render-specific)

### Implementation Overview

#### 1. Google Cloud Setup (One-time)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select existing project
3. Enable Cloud Storage API
4. Create storage bucket:
   - Name: `levoro-transport-images` (or similar)
   - Location: `europe-north1` (Finland) for low latency
   - Storage class: Standard
   - Access control: Uniform (public read)
5. Create service account:
   - IAM & Admin → Service Accounts → Create
   - Role: "Storage Object Admin"
   - Create key → Download JSON
6. Set bucket to public access:
   ```bash
   gsutil iam ch allUsers:objectViewer gs://levoro-transport-images
   ```

#### 2. Code Changes Required

**Add dependency to `requirements.txt`:**
```
google-cloud-storage==2.18.2
```

**Create `services/gcs_service.py`:**
- Initialize GCS client with credentials
- `upload_image(local_path, blob_name)` → returns public URL
- `delete_image(blob_name)` → removes from bucket
- Handle base64-encoded credentials from env

**Update `services/image_service.py`:**
- After `_process_image()`, upload to GCS
- Update `file_path` in image_info to GCS public URL
- Delete temp local file after upload
- On image delete, also delete from GCS bucket

**No template changes needed** - templates already use `{{ img.file_path }}`

#### 3. Environment Variables

Add to `.env` (local) and Render (production):
```bash
# Google Cloud Storage
GCS_BUCKET_NAME=levoro-transport-images
GCS_PROJECT_ID=your-project-id
GCS_CREDENTIALS_JSON=base64_encoded_service_account_json_key
```

To base64-encode your JSON key:
```bash
# Linux/Mac
base64 -w 0 service-account-key.json

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("service-account-key.json"))
```

#### 4. Development Fallback
Add logic to fall back to local storage if GCS credentials are missing (for local development).

### Cost Estimate (GCS)
- Storage: $0.020/GB/month
- Network egress (Europe): $0.12/GB (first 1TB)
- Example: 10GB images + 50GB traffic/month = ~$6.20/month
- Free tier: 5GB storage, 1GB egress/month

---

## Option 2: Render Persistent Disk

### Why Render Disk?
- ✅ Simpler setup (no external service)
- ✅ No code changes required
- ✅ Works with current implementation
- ❌ Only available on **paid Render plans** ($25/month minimum)
- ❌ Not portable (locked to Render)
- ❌ Higher storage cost ($0.25/GB/month)
- ❌ Manual backup management required

### Implementation Overview

#### 1. Render Setup
1. Upgrade to Render **Standard plan** or higher ($25/month+)
2. Go to your web service dashboard
3. Navigate to "Disks" tab
4. Click "Add Disk"
   - Name: `levoro-uploads`
   - Mount path: `/opt/render/project/src/static/uploads`
   - Size: 10GB (start small, can expand)
5. Deploy changes

#### 2. Code Changes
**None required** - current implementation works as-is with persistent disk.

#### 3. Considerations
- Images served through Flask app (requires bandwidth from Render)
- No CDN unless you add CloudFlare/similar
- Disk size limited by plan
- Backup strategy: manual snapshots or use Render's backup features

### Cost Estimate (Render Disk)
- Standard plan: $25/month (includes 10GB disk)
- Additional storage: $0.25/GB/month
- Example: 20GB total = $25 + (10GB × $0.25) = $27.50/month

**Note**: You also pay for bandwidth serving images through your Flask app.

---

## Recommendation

**Use Google Cloud Storage (Option 1)** because:
1. **Lower total cost** ($6-10/month vs $25+/month)
2. **Better performance** (CDN-ready, direct URLs)
3. **More flexible** (works on any hosting platform)
4. **Scalable** (handles traffic spikes automatically)
5. **You already use Google APIs** (simpler credential management)

Render Disk only makes sense if:
- You need a quick fix and budget isn't a concern
- You're already on a Render paid plan for other reasons
- You want to avoid external dependencies

---

## Migration Plan (For Chosen Solution)

### Phase 1: Implement New Storage
1. Add new storage backend (GCS or Render Disk)
2. Configure environment variables
3. Deploy to production
4. Test with new uploads

### Phase 2: Handle Existing Images
**New uploads** will automatically use the new storage.

**Existing images** in database have paths like `/static/uploads/orders/image.jpg`:
- These will return 404 on Render (files lost)
- Options:
  - Let them stay broken (if few/unimportant)
  - Manually re-upload from local backups
  - Create migration script to update old paths (if you have files backed up)

### Phase 3: Cleanup
- Remove old upload folders from repo (if present)
- Update documentation
- Monitor storage costs and usage

---

## Current Image Flow (Preserved)

```
User uploads image (up to 5MB)
         ↓
Flask receives file
         ↓
ImageService.save_order_image()
         ↓
Validate file (type, size)
         ↓
Save temp file locally
         ↓
Process image:
  - Resize to max 1200px width
  - Convert to JPEG (80% quality)
  - Optimize compression
  - Add white background (if PNG with transparency)
         ↓
Result: ~200-500KB JPEG file
         ↓
[NEW STEP] Upload to GCS / Save to Render Disk
         ↓
Store metadata in MongoDB:
  - filename
  - file_path (GCS URL or local path)
  - uploaded_by
  - uploaded_at
         ↓
Delete temp local file (if using GCS)
```

---

## Next Steps

1. Choose solution (GCS recommended)
2. Complete setup steps for chosen option
3. Update environment variables
4. Deploy and test with new uploads
5. Monitor storage usage and costs