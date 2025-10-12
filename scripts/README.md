# GCS Bucket Setup Scripts

## 🚀 Quick Start

**For Windows users:**
```powershell
.\setup-gcs-buckets.ps1 -ProjectId "your-new-project-id"
```

**For Linux/Mac users:**
```bash
chmod +x setup-gcs-buckets.sh
./setup-gcs-buckets.sh your-new-project-id
```

---

## 📁 Files in This Folder

### Setup Scripts
- **`setup-gcs-buckets.ps1`** - Windows PowerShell automated setup
- **`setup-gcs-buckets.sh`** - Linux/Mac Bash automated setup

### Verification
- **`verify-gcs-setup.py`** - Test your configuration after setup

### Configuration Files
- **`cors.json`** - CORS configuration for buckets (optional)
- **`.env.gcs.template`** - Template for environment variables

---

## 📖 Documentation

Complete guides are in the `docs/` folder:

1. **[GCS_MIGRATION_SUMMARY.md](../docs/GCS_MIGRATION_SUMMARY.md)** ⭐ START HERE
   - Overview of everything
   - What was created and why
   - Quick checklist

2. **[GCS_QUICK_START.md](../docs/GCS_QUICK_START.md)** 🏃 FAST SETUP
   - 3-step setup process
   - Quick troubleshooting
   - Testing guide

3. **[GCS_NEW_BUCKET_SETUP_GUIDE.md](../docs/GCS_NEW_BUCKET_SETUP_GUIDE.md)** 📚 COMPLETE GUIDE
   - Detailed step-by-step instructions
   - Google Cloud Console screenshots
   - Comprehensive troubleshooting
   - Security best practices
   - Cost estimation

4. **[GCS_MIGRATION_SCRIPTS.md](../docs/GCS_MIGRATION_SCRIPTS.md)** 🛠️ TECHNICAL REFERENCE
   - Script documentation
   - Advanced usage
   - Custom configurations

---

## 🔧 Prerequisites

Before running scripts:

1. **Install gcloud CLI**
   - Windows: https://cloud.google.com/sdk/docs/install
   - Linux/Mac: `curl https://sdk.cloud.google.com | bash`

2. **Authenticate**
   ```bash
   gcloud auth login
   ```

3. **Create new project** in Google Cloud Console
   - Go to: https://console.cloud.google.com/
   - Create project and note the PROJECT_ID

---

## 📋 Step-by-Step Usage

### Step 1: Run Setup Script

**Windows:**
```powershell
# Open PowerShell in this directory
cd C:\Users\Lenovo\Desktop\DEV\vscode\Levoro\scripts

# Run setup
.\setup-gcs-buckets.ps1 -ProjectId "levoro-XXXXXX"
```

**Linux/Mac:**
```bash
# Make executable (first time only)
chmod +x setup-gcs-buckets.sh

# Run setup
./setup-gcs-buckets.sh levoro-XXXXXX
```

**Script will:**
- ✅ Enable Cloud Storage APIs
- ✅ Create service account
- ✅ Create both buckets
- ✅ Set up permissions
- ✅ Download credentials
- ✅ Convert to base64
- ✅ Display environment variables

---

### Step 2: Update .env File

Copy the output from the script to your `.env` file:

```env
GCS_PROJECT_ID=levoro-XXXXXX
GCS_BUCKET_NAME=levoro-transport-images
GCS_PRIVATE_BUCKET_NAME=levoro-transport-images-private
GCS_CREDENTIALS_JSON=eyJwcm9qZWN0X2lkIjogIm...
```

⚠️ **IMPORTANT:** Delete the downloaded JSON key file after copying!

---

### Step 3: Verify Setup

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run verification
python verify-gcs-setup.py
```

**Expected output:**
```
✅ All checks passed! GCS is ready to use.
```

---

### Step 4: Test Application

```bash
# Start application
python app.py

# Check logs for:
[GCS] Enabled - images will be stored in: orders/{order_id}/{filename}
[GCS] Bucket: levoro-transport-images
[GCS] Project: levoro-XXXXXX
```

---

## 🔍 Verification Script Details

The verification script checks:

1. ✅ Environment variables are set
2. ✅ Credentials format is valid JSON
3. ✅ GCS service initializes correctly
4. ✅ Both buckets are accessible

**Run it anytime:**
```bash
python verify-gcs-setup.py
```

---

## 🌐 Optional: Configure CORS

If you plan to upload files directly from browser:

```bash
# Update origins in cors.json first
# Then apply to buckets:
gsutil cors set cors.json gs://levoro-transport-images
gsutil cors set cors.json gs://levoro-transport-images-private
```

---

## 🆘 Troubleshooting

### "gcloud: command not found"
**Solution:** Install gcloud CLI (see Prerequisites)

### "Permission denied"
**Solution:** 
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### "Bucket already exists"
**Solution:** Script handles this - it will use existing bucket

### Verification fails
**Solution:**
1. Check `.env` file has correct values
2. Restart terminal/application
3. Run verification again

### Script fails mid-way
**Solution:**
- Script is idempotent (safe to re-run)
- Re-run the same command
- It will skip already-created resources

---

## 📚 Additional Resources

- **Application Docs:** `../CLAUDE.md`
- **Previous GCS Fix:** `../docs/fixes/GCS_SERVICE_ACCOUNT_FIX.md`
- **Google Cloud Docs:** https://cloud.google.com/storage/docs
- **Service Accounts:** https://cloud.google.com/iam/docs/service-accounts

---

## 🔐 Security Notes

1. **Never commit service account JSON files**
   - Already in `.gitignore`
   - Delete after converting to base64

2. **Keep credentials secure**
   - Store in password manager
   - Rotate every 90 days

3. **Use environment variables only**
   - Never hardcode credentials
   - Different creds for dev/prod

---

## 💡 Pro Tips

1. **Save setup script output**
   ```powershell
   # Windows
   .\setup-gcs-buckets.ps1 -ProjectId "levoro-XXX" | Tee-Object -FilePath setup-output.txt
   
   # Linux/Mac
   ./setup-gcs-buckets.sh levoro-XXX | tee setup-output.txt
   ```

2. **Verify buckets in console**
   - Go to: https://console.cloud.google.com/storage
   - Check both buckets exist
   - Verify permissions

3. **Test with small file first**
   - Upload one test image before migrating

4. **Keep old credentials as backup**
   - Until new setup is verified in production
   - Then delete old service account

---

## ✅ Success Checklist

After running scripts, you should have:

- ✅ Two buckets created in GCS
- ✅ Service account with correct permissions
- ✅ Credentials downloaded and converted
- ✅ `.env` file updated
- ✅ Verification script passes
- ✅ Application starts with `[GCS] Enabled`
- ✅ Test uploads working

---

## 🎉 What's Next?

After successful setup:

1. Test local image uploads
2. Update production environment
3. Deploy to production
4. Set up monitoring & alerts
5. Document new configuration
6. Schedule credential rotation

---

**Need help?** See the complete guides in `docs/` folder!

**Created:** 2025-01-08  
**Version:** 1.0
