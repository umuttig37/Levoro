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
