"""
Google Cloud Storage Service
Handles file uploads, deletions, and URL generation for GCS
"""

import os
import base64
import json
import tempfile
from typing import Optional, Tuple
from google.cloud import storage
from google.oauth2 import service_account


class GCSService:
    """Service for handling Google Cloud Storage operations"""

    def __init__(self):
        self.bucket_name = os.getenv('GCS_BUCKET_NAME')
        self.private_bucket_name = os.getenv('GCS_PRIVATE_BUCKET_NAME')  # New private bucket
        self.project_id = os.getenv('GCS_PROJECT_ID')
        self.credentials_b64 = os.getenv('GCS_CREDENTIALS_JSON')

        # Flag to check if GCS is enabled
        self.enabled = bool(self.bucket_name and self.project_id and self.credentials_b64)

        if self.enabled:
            self._initialize_client()
            env_mode = "development" if self.is_development() else "production"
            env_prefix = self.get_environment_prefix()
            print(f"GCS enabled in {env_mode} mode - images will use prefix: '{env_prefix}' (blank if production)")
        else:
            print("GCS not configured - image upload will use local storage")

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return os.getenv("FLASK_ENV", "production") == "development"

    def get_environment_prefix(self) -> str:
        """Get environment-based folder prefix (dev/ or empty)"""
        return "dev/" if self.is_development() else ""

    def _initialize_client(self):
        """Initialize GCS client with credentials"""
        try:
            # Decode base64 credentials
            credentials_json = base64.b64decode(self.credentials_b64).decode('utf-8')
            credentials_dict = json.loads(credentials_json)

            # Create credentials object
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict
            )

            # Initialize storage client
            self.client = storage.Client(
                credentials=credentials,
                project=self.project_id
            )

            # Get bucket references
            self.bucket = self.client.bucket(self.bucket_name)

            # Get private bucket reference if configured
            if self.private_bucket_name:
                self.private_bucket = self.client.bucket(self.private_bucket_name)
            else:
                self.private_bucket = self.bucket  # Fallback to public bucket
                print("⚠️  No private bucket configured - using public bucket for private files")

        except Exception as e:
            print(f"Failed to initialize GCS client: {e}")
            self.enabled = False

    def upload_file(self, local_file_path: str, destination_blob_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a file to GCS bucket

        Args:
            local_file_path: Path to local file
            destination_blob_name: Name for the file in GCS (e.g., "orders/123_pickup_abc.jpg")

        Returns:
            Tuple[Optional[str], Optional[str]]: (public_url, error_message)
        """
        if not self.enabled:
            return None, "GCS not enabled"

        try:
            # Create blob (file reference in GCS)
            blob = self.bucket.blob(destination_blob_name)

            # Upload file
            blob.upload_from_filename(local_file_path, content_type='image/jpeg')

            # Return public URL (no need to make_public - bucket already has public access via IAM)
            public_url = blob.public_url
            return public_url, None

        except Exception as e:
            error_msg = f"GCS upload failed: {str(e)}"
            print(error_msg)
            return None, error_msg

    def upload_private_file(self, local_file_path: str, destination_blob_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a file to PRIVATE GCS bucket (not publicly accessible)

        Args:
            local_file_path: Path to local file
            destination_blob_name: Name for the file in GCS (e.g., "driver-licenses/1/front.jpg")

        Returns:
            Tuple[Optional[str], Optional[str]]: (blob_name, error_message)
        """
        if not self.enabled:
            return None, "GCS not enabled"

        try:
            # Create blob in PRIVATE bucket (file reference in GCS)
            blob = self.private_bucket.blob(destination_blob_name)

            # Upload file
            blob.upload_from_filename(local_file_path, content_type='image/jpeg')

            # NOTE: Do NOT make public - this is private storage
            # Access will be via signed URLs only
            return destination_blob_name, None

        except Exception as e:
            error_msg = f"GCS private upload failed: {str(e)}"
            print(error_msg)
            return None, error_msg

    def generate_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> Optional[str]:
        """
        Generate temporary signed URL for private file access

        Args:
            blob_name: Name of the blob in PRIVATE GCS bucket
            expiration_minutes: URL validity period (default 1 hour)

        Returns:
            Signed URL valid for specified duration, or None on error
        """
        if not self.enabled:
            return None

        try:
            from datetime import timedelta
            blob = self.private_bucket.blob(blob_name)

            # Check if blob exists
            if not blob.exists():
                print(f"Blob not found: {blob_name}")
                return None

            # Generate signed URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            return url

        except Exception as e:
            print(f"Failed to generate signed URL: {e}")
            return None

    def delete_file(self, blob_name: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a file from GCS bucket

        Args:
            blob_name: Name of the blob to delete

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if not self.enabled:
            return False, "GCS not enabled"

        try:
            blob = self.bucket.blob(blob_name)

            # Check if blob exists
            if not blob.exists():
                return False, "File not found in GCS"

            # Delete the blob
            blob.delete()
            return True, None

        except Exception as e:
            error_msg = f"GCS deletion failed: {str(e)}"
            print(error_msg)
            return False, error_msg

    def get_public_url(self, blob_name: str) -> Optional[str]:
        """
        Get public URL for a blob

        Args:
            blob_name: Name of the blob

        Returns:
            Public URL or None
        """
        if not self.enabled:
            return None

        try:
            blob = self.bucket.blob(blob_name)
            return blob.public_url
        except Exception as e:
            print(f"Failed to get public URL: {e}")
            return None

    def extract_blob_name_from_url(self, public_url: str) -> Optional[str]:
        """
        Extract blob name from a GCS public URL

        Example:
            Production: https://storage.googleapis.com/levoro-transport-images/orders/123_pickup_abc.jpg
                     -> orders/123_pickup_abc.jpg
            Development: https://storage.googleapis.com/levoro-transport-images/dev/orders/123_pickup_abc.jpg
                      -> dev/orders/123_pickup_abc.jpg

        Args:
            public_url: The GCS public URL

        Returns:
            Blob name or None
        """
        if not public_url:
            return None

        try:
            # GCS public URLs have format: https://storage.googleapis.com/bucket-name/blob-name
            if 'storage.googleapis.com' in public_url:
                # Split by bucket name and get everything after (includes dev/ prefix if present)
                parts = public_url.split(f'{self.bucket_name}/')
                if len(parts) > 1:
                    return parts[1]
            return None
        except Exception as e:
            print(f"Failed to extract blob name: {e}")
            return None


# Global instance
gcs_service = GCSService()
