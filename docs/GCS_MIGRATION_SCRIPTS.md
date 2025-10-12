# GCS Migration Helper Scripts

This document contains ready-to-use scripts for migrating to new GCS buckets.

## Quick Setup Script (PowerShell - Windows)

Save this as `setup-gcs-buckets.ps1`:

```powershell
# GCS Bucket Setup Script for Windows
# Usage: .\setup-gcs-buckets.ps1 -ProjectId "levoro-XXXXXX"

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "EUROPE-NORTH1",
    [string]$PublicBucket = "levoro-transport-images",
    [string]$PrivateBucket = "levoro-transport-images-private",
    [string]$ServiceAccountName = "levoro-storage-uploader"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GCS Bucket Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project ID: $ProjectId" -ForegroundColor Green
Write-Host "Region: $Region" -ForegroundColor Green
Write-Host "Public Bucket: $PublicBucket" -ForegroundColor Green
Write-Host "Private Bucket: $PrivateBucket" -ForegroundColor Green
Write-Host ""

# Check if gcloud is installed
Write-Host "Checking gcloud installation..." -ForegroundColor Yellow
try {
    $gcloudVersion = gcloud version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud not found"
    }
    Write-Host "✓ gcloud is installed" -ForegroundColor Green
} catch {
    Write-Host "✗ gcloud CLI is not installed" -ForegroundColor Red
    Write-Host "Please install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Set project
Write-Host "Setting project..." -ForegroundColor Yellow
gcloud config set project $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to set project. Does it exist?" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Project set successfully" -ForegroundColor Green
Write-Host ""

# Enable APIs
Write-Host "Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable storage-api.googleapis.com
gcloud services enable storage-component.googleapis.com
Write-Host "✓ APIs enabled" -ForegroundColor Green
Write-Host ""

# Create service account
Write-Host "Creating service account..." -ForegroundColor Yellow
$ServiceAccountEmail = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"

gcloud iam service-accounts create $ServiceAccountName `
    --display-name="Levoro Storage Uploader" `
    --description="Service account for uploading images to GCS buckets" 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Service account created: $ServiceAccountEmail" -ForegroundColor Green
} else {
    Write-Host "! Service account may already exist, continuing..." -ForegroundColor Yellow
}
Write-Host ""

# Create public bucket
Write-Host "Creating public bucket: $PublicBucket..." -ForegroundColor Yellow
gsutil mb -p $ProjectId -c STANDARD -l $Region gs://$PublicBucket 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Public bucket created" -ForegroundColor Green
} else {
    Write-Host "! Bucket may already exist, continuing..." -ForegroundColor Yellow
}

# Set public access
Write-Host "Setting public access..." -ForegroundColor Yellow
gsutil iam ch allUsers:objectViewer gs://$PublicBucket
Write-Host "✓ Public access configured" -ForegroundColor Green

# Grant service account permissions
Write-Host "Granting service account permissions to public bucket..." -ForegroundColor Yellow
gsutil iam ch "serviceAccount:${ServiceAccountEmail}:roles/storage.objectAdmin" gs://$PublicBucket
Write-Host "✓ Permissions granted" -ForegroundColor Green
Write-Host ""

# Create private bucket
Write-Host "Creating private bucket: $PrivateBucket..." -ForegroundColor Yellow
gsutil mb -p $ProjectId -c STANDARD -l $Region gs://$PrivateBucket 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Private bucket created" -ForegroundColor Green
} else {
    Write-Host "! Bucket may already exist, continuing..." -ForegroundColor Yellow
}

# Grant service account permissions (no public access)
Write-Host "Granting service account permissions to private bucket..." -ForegroundColor Yellow
gsutil iam ch "serviceAccount:${ServiceAccountEmail}:roles/storage.objectAdmin" gs://$PrivateBucket
Write-Host "✓ Permissions granted" -ForegroundColor Green
Write-Host ""

# Create service account key
Write-Host "Creating service account key..." -ForegroundColor Yellow
$KeyFile = "levoro-$ProjectId-key.json"
gcloud iam service-accounts keys create $KeyFile `
    --iam-account=$ServiceAccountEmail

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Service account key created: $KeyFile" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to create service account key" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Convert to base64
Write-Host "Converting credentials to base64..." -ForegroundColor Yellow
$Base64Creds = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Content $KeyFile -Raw)))
Write-Host "✓ Credentials converted to base64" -ForegroundColor Green
Write-Host ""

# Display summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Add these to your .env file:" -ForegroundColor Yellow
Write-Host ""
Write-Host "GCS_PROJECT_ID=$ProjectId" -ForegroundColor White
Write-Host "GCS_BUCKET_NAME=$PublicBucket" -ForegroundColor White
Write-Host "GCS_PRIVATE_BUCKET_NAME=$PrivateBucket" -ForegroundColor White
Write-Host "GCS_CREDENTIALS_JSON=$Base64Creds" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  IMPORTANT: Keep the key file ($KeyFile) secure!" -ForegroundColor Red
Write-Host "⚠️  Do NOT commit it to Git!" -ForegroundColor Red
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Copy the above variables to your .env file" -ForegroundColor White
Write-Host "2. Update production environment variables" -ForegroundColor White
Write-Host "3. Test image uploads" -ForegroundColor White
Write-Host "4. Delete the key file after testing: Remove-Item $KeyFile" -ForegroundColor White
Write-Host ""
```

**Usage:**
```powershell
# Make sure you're authenticated with gcloud first
gcloud auth login

# Run the script
.\setup-gcs-buckets.ps1 -ProjectId "your-new-project-id"
```

---

## Quick Setup Script (Bash - Linux/Mac)

Save this as `setup-gcs-buckets.sh`:

```bash
#!/bin/bash

# GCS Bucket Setup Script for Linux/Mac
# Usage: ./setup-gcs-buckets.sh YOUR_PROJECT_ID

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${1:-}"
REGION="EUROPE-NORTH1"
PUBLIC_BUCKET="levoro-transport-images"
PRIVATE_BUCKET="levoro-transport-images-private"
SERVICE_ACCOUNT_NAME="levoro-storage-uploader"

# Check if project ID provided
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: Project ID is required${NC}"
    echo "Usage: $0 YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${CYAN}========================================"
echo "GCS Bucket Setup Script"
echo -e "========================================${NC}"
echo ""
echo -e "${GREEN}Project ID: $PROJECT_ID${NC}"
echo -e "${GREEN}Region: $REGION${NC}"
echo -e "${GREEN}Public Bucket: $PUBLIC_BUCKET${NC}"
echo -e "${GREEN}Private Bucket: $PRIVATE_BUCKET${NC}"
echo ""

# Check if gcloud is installed
echo -e "${YELLOW}Checking gcloud installation...${NC}"
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}✗ gcloud CLI is not installed${NC}"
    echo -e "${YELLOW}Please install from: https://cloud.google.com/sdk/docs/install${NC}"
    exit 1
fi
echo -e "${GREEN}✓ gcloud is installed${NC}"
echo ""

# Set project
echo -e "${YELLOW}Setting project...${NC}"
gcloud config set project "$PROJECT_ID"
echo -e "${GREEN}✓ Project set successfully${NC}"
echo ""

# Enable APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable storage-api.googleapis.com
gcloud services enable storage-component.googleapis.com
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Create service account
echo -e "${YELLOW}Creating service account...${NC}"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="Levoro Storage Uploader" \
    --description="Service account for uploading images to GCS buckets" 2>/dev/null || true

echo -e "${GREEN}✓ Service account: $SERVICE_ACCOUNT_EMAIL${NC}"
echo ""

# Create public bucket
echo -e "${YELLOW}Creating public bucket: $PUBLIC_BUCKET...${NC}"
gsutil mb -p "$PROJECT_ID" -c STANDARD -l "$REGION" "gs://$PUBLIC_BUCKET" 2>/dev/null || true
echo -e "${GREEN}✓ Public bucket ready${NC}"

# Set public access
echo -e "${YELLOW}Setting public access...${NC}"
gsutil iam ch allUsers:objectViewer "gs://$PUBLIC_BUCKET"
echo -e "${GREEN}✓ Public access configured${NC}"

# Grant service account permissions
echo -e "${YELLOW}Granting service account permissions to public bucket...${NC}"
gsutil iam ch "serviceAccount:${SERVICE_ACCOUNT_EMAIL}:roles/storage.objectAdmin" "gs://$PUBLIC_BUCKET"
echo -e "${GREEN}✓ Permissions granted${NC}"
echo ""

# Create private bucket
echo -e "${YELLOW}Creating private bucket: $PRIVATE_BUCKET...${NC}"
gsutil mb -p "$PROJECT_ID" -c STANDARD -l "$REGION" "gs://$PRIVATE_BUCKET" 2>/dev/null || true
echo -e "${GREEN}✓ Private bucket ready${NC}"

# Grant service account permissions (no public access)
echo -e "${YELLOW}Granting service account permissions to private bucket...${NC}"
gsutil iam ch "serviceAccount:${SERVICE_ACCOUNT_EMAIL}:roles/storage.objectAdmin" "gs://$PRIVATE_BUCKET"
echo -e "${GREEN}✓ Permissions granted${NC}"
echo ""

# Create service account key
echo -e "${YELLOW}Creating service account key...${NC}"
KEY_FILE="levoro-$PROJECT_ID-key.json"
gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SERVICE_ACCOUNT_EMAIL"

echo -e "${GREEN}✓ Service account key created: $KEY_FILE${NC}"
echo ""

# Convert to base64
echo -e "${YELLOW}Converting credentials to base64...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac
    BASE64_CREDS=$(base64 -i "$KEY_FILE")
else
    # Linux
    BASE64_CREDS=$(base64 -w 0 "$KEY_FILE")
fi
echo -e "${GREEN}✓ Credentials converted to base64${NC}"
echo ""

# Display summary
echo -e "${CYAN}========================================"
echo "Setup Complete!"
echo -e "========================================${NC}"
echo ""
echo -e "${YELLOW}Add these to your .env file:${NC}"
echo ""
echo "GCS_PROJECT_ID=$PROJECT_ID"
echo "GCS_BUCKET_NAME=$PUBLIC_BUCKET"
echo "GCS_PRIVATE_BUCKET_NAME=$PRIVATE_BUCKET"
echo "GCS_CREDENTIALS_JSON=$BASE64_CREDS"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Keep the key file ($KEY_FILE) secure!${NC}"
echo -e "${RED}⚠️  Do NOT commit it to Git!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Copy the above variables to your .env file"
echo "2. Update production environment variables"
echo "3. Test image uploads"
echo "4. Delete the key file after testing: rm $KEY_FILE"
echo ""
```

**Usage:**
```bash
# Make executable
chmod +x setup-gcs-buckets.sh

# Authenticate with gcloud
gcloud auth login

# Run the script
./setup-gcs-buckets.sh your-new-project-id
```

---

## Verification Script

Save this as `verify-gcs-setup.py`:

```python
#!/usr/bin/env python3
"""
GCS Setup Verification Script

Checks if GCS is properly configured and accessible.
Run this after setting up buckets to verify everything works.

Usage:
    python verify-gcs-setup.py
"""

import os
import sys
import base64
import json
from pathlib import Path

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_env_vars():
    """Check if all required environment variables are set"""
    print("\n" + "="*50)
    print("Checking Environment Variables")
    print("="*50)
    
    required_vars = [
        'GCS_PROJECT_ID',
        'GCS_BUCKET_NAME',
        'GCS_PRIVATE_BUCKET_NAME',
        'GCS_CREDENTIALS_JSON'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == 'GCS_CREDENTIALS_JSON':
                print(f"✓ {var}: Present (length: {len(value)} chars)")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: Missing")
            missing.append(var)
    
    if missing:
        print(f"\n❌ Missing variables: {', '.join(missing)}")
        return False
    
    print("\n✅ All environment variables are set")
    return True


def verify_credentials():
    """Verify that credentials are valid JSON"""
    print("\n" + "="*50)
    print("Verifying Credentials Format")
    print("="*50)
    
    creds_b64 = os.getenv('GCS_CREDENTIALS_JSON')
    if not creds_b64:
        print("❌ GCS_CREDENTIALS_JSON not set")
        return False
    
    try:
        # Decode base64
        creds_json = base64.b64decode(creds_b64).decode('utf-8')
        print("✓ Base64 decoding successful")
    except Exception as e:
        print(f"❌ Base64 decoding failed: {e}")
        return False
    
    try:
        # Parse JSON
        creds_dict = json.loads(creds_json)
        print("✓ JSON parsing successful")
    except Exception as e:
        print(f"❌ JSON parsing failed: {e}")
        return False
    
    # Check required fields
    required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 
                      'client_email', 'client_id']
    missing_fields = [f for f in required_fields if f not in creds_dict]
    
    if missing_fields:
        print(f"❌ Missing fields in credentials: {', '.join(missing_fields)}")
        return False
    
    print("\n✅ Credentials format is valid")
    print(f"   Project ID: {creds_dict.get('project_id')}")
    print(f"   Client Email: {creds_dict.get('client_email')}")
    
    return True


def test_gcs_initialization():
    """Test if GCS service initializes correctly"""
    print("\n" + "="*50)
    print("Testing GCS Service Initialization")
    print("="*50)
    
    try:
        from services.gcs_service import gcs_service
        
        if not gcs_service.enabled:
            print("❌ GCS service is not enabled")
            return False
        
        print("✓ GCS service initialized successfully")
        print(f"   Public Bucket: {gcs_service.bucket_name}")
        print(f"   Private Bucket: {gcs_service.private_bucket_name}")
        print(f"   Project ID: {gcs_service.project_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ GCS initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bucket_access():
    """Test if buckets are accessible"""
    print("\n" + "="*50)
    print("Testing Bucket Access")
    print("="*50)
    
    try:
        from services.gcs_service import gcs_service
        
        if not gcs_service.enabled:
            print("❌ GCS not enabled, skipping bucket access test")
            return False
        
        # Test public bucket
        print("\nTesting public bucket access...")
        try:
            blobs = list(gcs_service.bucket.list_blobs(max_results=1))
            print(f"✓ Public bucket accessible")
        except Exception as e:
            print(f"❌ Public bucket not accessible: {e}")
            return False
        
        # Test private bucket
        print("\nTesting private bucket access...")
        try:
            blobs = list(gcs_service.private_bucket.list_blobs(max_results=1))
            print(f"✓ Private bucket accessible")
        except Exception as e:
            print(f"❌ Private bucket not accessible: {e}")
            return False
        
        print("\n✅ Both buckets are accessible")
        return True
        
    except Exception as e:
        print(f"❌ Bucket access test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification checks"""
    print("\n" + "="*50)
    print("GCS Setup Verification")
    print("="*50)
    
    # Load environment variables from .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ .env file loaded")
    except ImportError:
        print("! python-dotenv not installed, using system environment only")
    except Exception as e:
        print(f"! Could not load .env file: {e}")
    
    # Run checks
    checks = [
        ("Environment Variables", check_env_vars),
        ("Credentials Format", verify_credentials),
        ("GCS Initialization", test_gcs_initialization),
        ("Bucket Access", test_bucket_access),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*50)
    print("Verification Summary")
    print("="*50)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "="*50)
    if all_passed:
        print("✅ All checks passed! GCS is ready to use.")
        print("="*50)
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("="*50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Usage:**
```bash
# Make sure you're in the project root directory
python verify-gcs-setup.py
```

---

## CORS Configuration File

Save this as `cors.json` for configuring CORS on your buckets:

```json
[
  {
    "origin": ["https://your-production-domain.com", "http://localhost:8000", "http://localhost:5000"],
    "method": ["GET", "POST", "PUT", "DELETE", "HEAD"],
    "responseHeader": ["Content-Type", "Content-Length", "Date", "Server", "Transfer-Encoding", "X-GUploader-UploadID"],
    "maxAgeSeconds": 3600
  }
]
```

**Apply CORS:**
```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Apply to public bucket
gsutil cors set cors.json gs://levoro-transport-images

# Apply to private bucket (if needed)
gsutil cors set cors.json gs://levoro-transport-images-private

# Verify CORS configuration
gsutil cors get gs://levoro-transport-images
```

---

## Bucket Lifecycle Policy (Optional)

Save this as `lifecycle.json` to automatically clean up old development images:

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 90,
          "matchesPrefix": ["dev/"]
        }
      }
    ]
  }
}
```

**Apply lifecycle policy:**
```bash
# This will auto-delete files in dev/ folder after 90 days
gsutil lifecycle set lifecycle.json gs://levoro-transport-images
```

---

## Quick Environment Variable Template

Save this as `.env.gcs.template`:

```env
# Google Cloud Storage Configuration
# Copy these values to your .env file after running setup script

# Your new Google Cloud Project ID
GCS_PROJECT_ID=

# Public bucket for order images (publicly accessible)
GCS_BUCKET_NAME=levoro-transport-images

# Private bucket for driver licenses (signed URLs only)
GCS_PRIVATE_BUCKET_NAME=levoro-transport-images-private

# Base64-encoded service account JSON credentials
# Get this from the setup script output
GCS_CREDENTIALS_JSON=

# Optional: Enable GCS debug logging
# GCS_DEBUG=true
```

---

## Production Environment Update Script (Render.com)

Save this as `update-render-env.sh`:

```bash
#!/bin/bash

# Update Render.com environment variables
# Requires: render CLI (https://render.com/docs/cli)

SERVICE_ID="${1:-}"
PROJECT_ID="${2:-}"
BASE64_CREDS="${3:-}"

if [ -z "$SERVICE_ID" ] || [ -z "$PROJECT_ID" ] || [ -z "$BASE64_CREDS" ]; then
    echo "Usage: $0 SERVICE_ID PROJECT_ID BASE64_CREDS"
    echo ""
    echo "Example:"
    echo "  $0 srv-abc123 levoro-789012 eyJwcm9qZWN0X2lkIjo..."
    exit 1
fi

echo "Updating Render.com environment variables..."
echo "Service ID: $SERVICE_ID"
echo "Project ID: $PROJECT_ID"
echo ""

# Update environment variables
render env set GCS_PROJECT_ID="$PROJECT_ID" --service="$SERVICE_ID"
render env set GCS_BUCKET_NAME="levoro-transport-images" --service="$SERVICE_ID"
render env set GCS_PRIVATE_BUCKET_NAME="levoro-transport-images-private" --service="$SERVICE_ID"
render env set GCS_CREDENTIALS_JSON="$BASE64_CREDS" --service="$SERVICE_ID"

echo ""
echo "✓ Environment variables updated"
echo ""
echo "Next steps:"
echo "1. Trigger manual deploy in Render.com dashboard"
echo "2. Check deployment logs for GCS initialization"
echo "3. Test image uploads"
```

---

## Files Created

- `setup-gcs-buckets.ps1` - Windows PowerShell setup script
- `setup-gcs-buckets.sh` - Linux/Mac Bash setup script
- `verify-gcs-setup.py` - Python verification script
- `cors.json` - CORS configuration
- `lifecycle.json` - Lifecycle policy for auto-cleanup
- `.env.gcs.template` - Environment variable template
- `update-render-env.sh` - Render.com environment update script

---

**Document created:** 2025-01-08
**Last updated:** 2025-01-08
