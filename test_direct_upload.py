"""
Test direct upload without checking bucket metadata
"""
import os
import tempfile
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

from services.gcs_service import gcs_service

print("Testing direct upload to GCS buckets...")
print("="*60)

# Create a test image
img = Image.new('RGB', (100, 100), color='blue')
img_byte_arr = BytesIO()
img.save(img_byte_arr, format='JPEG')
img_byte_arr.seek(0)

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
temp_file.write(img_byte_arr.read())
temp_file.close()

print("\n1. Testing PUBLIC bucket upload...")
print(f"   Bucket: {gcs_service.bucket_name}")

blob_name = "test/verification_upload.jpg"
public_url, error = gcs_service.upload_file(temp_file.name, blob_name)

if error:
    print(f"   [FAIL] Upload failed: {error}")
    print("\n   This means your service account lacks permission to upload to the public bucket.")
    print("   You need to grant 'Storage Object Admin' role to:")
    print(f"   {gcs_service.client.credentials.service_account_email}")
else:
    print(f"   [OK] Upload successful!")
    print(f"   URL: {public_url}")

    # Clean up
    print("\n   Cleaning up test file...")
    success, del_error = gcs_service.delete_file(blob_name)
    if success:
        print("   [OK] Test file deleted")
    else:
        print(f"   [WARN] Could not delete test file: {del_error}")

print("\n2. Testing PRIVATE bucket upload...")
print(f"   Bucket: {gcs_service.private_bucket_name}")

blob_name = "test/verification_private_upload.jpg"
result_blob, error = gcs_service.upload_private_file(temp_file.name, blob_name)

if error:
    print(f"   [FAIL] Upload failed: {error}")
    print("\n   This means your service account lacks permission to upload to the private bucket.")
    print("   You need to grant 'Storage Object Admin' role to:")
    print(f"   {gcs_service.client.credentials.service_account_email}")
else:
    print(f"   [OK] Upload successful!")
    print(f"   Blob: {result_blob}")

    # Test signed URL
    print("\n   Testing signed URL generation...")
    signed_url = gcs_service.generate_signed_url(result_blob, expiration_minutes=5)
    if signed_url:
        print(f"   [OK] Signed URL generated (valid for 5 minutes)")
        print(f"   URL: {signed_url[:100]}...")
    else:
        print("   [FAIL] Could not generate signed URL")

    # Clean up
    print("\n   Cleaning up test file...")
    try:
        blob = gcs_service.private_bucket.blob(result_blob)
        blob.delete()
        print("   [OK] Test file deleted")
    except Exception as e:
        print(f"   [WARN] Could not delete test file: {e}")

# Clean up temp file
os.unlink(temp_file.name)

print("\n" + "="*60)
print("NEXT STEPS:")
print("="*60)
print("\nIf uploads failed, grant 'Storage Object Admin' role:")
print("1. Go to: https://console.cloud.google.com/storage/browser")
print(f"2. For EACH bucket ({gcs_service.bucket_name}, {gcs_service.private_bucket_name}):")
print("   - Click the bucket name")
print("   - Go to 'PERMISSIONS' tab")
print("   - Click 'GRANT ACCESS'")
print(f"   - Add principal: levoro-storage-uploader@gen-lang-client-0187210205.iam.gserviceaccount.com")
print("   - Role: 'Storage Object Admin'")
print("   - Click 'SAVE'")
print("\n" + "="*60)
