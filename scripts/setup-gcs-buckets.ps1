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
