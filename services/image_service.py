"""
Image Service
Handles image upload, processing, and file management
"""

import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from models.order import order_model
from services.gcs_service import gcs_service

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads', 'orders')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_WIDTH = 1200
IMAGE_QUALITY = 80


class ImageService:
    """Service for handling image operations"""

    def __init__(self):
        self.order_model = order_model
        self.upload_folder = UPLOAD_FOLDER
        self.allowed_extensions = ALLOWED_EXTENSIONS
        self.max_file_size = MAX_FILE_SIZE

        # Ensure upload directory exists
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)

    def save_order_image(self, file, order_id: int, image_type: str, uploaded_by: str = "system") -> Tuple[Optional[Dict], Optional[str]]:
        """
        Save and process uploaded image for an order

        Args:
            file: Uploaded file object
            order_id: Order ID
            image_type: 'pickup' or 'delivery'
            uploaded_by: User who uploaded the image

        Returns:
            Tuple[Optional[Dict], Optional[str]]: (image_info, error_message)
        """
        try:
            # Validate file
            validation_error = self._validate_file(file)
            if validation_error:
                return None, validation_error

            # Generate unique filename
            file_extension = self._get_file_extension(file.filename)
            unique_filename = f"{order_id}_{image_type}_{uuid.uuid4().hex}.{file_extension}"
            file_path = os.path.join(self.upload_folder, unique_filename)

            # Save file temporarily
            file.save(file_path)

            # Process image (resize, optimize)
            processed_path = self._process_image(file_path)
            if not processed_path:
                self._cleanup_file(file_path)
                return None, "Kuvan käsittely epäonnistui - tarkista että kuva ei ole vioittunut"

            # Update filename if processing changed the extension
            final_filename = os.path.basename(processed_path)

            # Upload to GCS if enabled, otherwise use local storage
            file_path_url = None
            if gcs_service.enabled:
                # Upload to Google Cloud Storage (organized by order ID)
                blob_name = f"orders/{order_id}/{final_filename}"
                public_url, gcs_error = gcs_service.upload_file(processed_path, blob_name)

                if gcs_error:
                    # Fallback to local storage on GCS error
                    print(f"GCS upload failed, using local storage: {gcs_error}")
                    file_path_url = f"/static/uploads/orders/{final_filename}"
                else:
                    file_path_url = public_url
                    # Clean up local file after successful GCS upload
                    self._cleanup_file(processed_path)
            else:
                # Use local storage (development mode)
                file_path_url = f"/static/uploads/orders/{final_filename}"

            # Create image info
            image_info = {
                "id": str(uuid.uuid4()),
                "filename": final_filename,
                "original_filename": secure_filename(file.filename),
                "file_path": file_path_url,
                "file_size": os.path.getsize(processed_path) if os.path.exists(processed_path) else 0,
                "image_type": image_type,
                "uploaded_at": datetime.utcnow(),
                "uploaded_by": uploaded_by
            }

            return image_info, None

        except Exception as e:
            # Cleanup on error
            if 'file_path' in locals():
                self._cleanup_file(file_path)
            return None, f"Kuvan tallennus epäonnistui: {str(e)}"

    def delete_order_image(self, order_id: int, image_type: str, image_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete an image from an order

        Args:
            order_id: Order ID
            image_type: 'pickup' or 'delivery'
            image_id: Image ID to delete

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            # Get order
            order = self.order_model.find_by_id(order_id)
            if not order:
                return False, "Tilausta ei löytynyt"

            # Find image
            images = order.get("images", {})
            current_images = images.get(image_type, [])

            # Handle old format
            if not isinstance(current_images, list):
                current_images = [current_images] if current_images else []

            # Find the image to delete
            image_to_delete = None
            for img in current_images:
                if img.get("id") == image_id:
                    image_to_delete = img
                    break

            if not image_to_delete:
                return False, "Kuvaa ei löytynyt"

            # Delete physical file (from GCS or local storage)
            if "file_path" in image_to_delete:
                file_path_url = image_to_delete["file_path"]

                # Check if it's a GCS URL
                if 'storage.googleapis.com' in file_path_url:
                    # Delete from GCS
                    blob_name = gcs_service.extract_blob_name_from_url(file_path_url)
                    if blob_name:
                        gcs_service.delete_file(blob_name)
                else:
                    # Delete from local filesystem
                    if "filename" in image_to_delete:
                        file_path = os.path.join(self.upload_folder, image_to_delete["filename"])
                        self._cleanup_file(file_path)

            # Remove from database
            success, error = self.order_model.remove_image(order_id, image_type, image_id)
            return success, error

        except Exception as e:
            return False, f"Kuvan poisto epäonnistui: {str(e)}"

    def add_image_to_order(self, order_id: int, image_type: str, image_info: Dict) -> Tuple[bool, Optional[str]]:
        """Add processed image info to order"""
        return self.order_model.add_image(order_id, image_type, image_info)

    def get_order_images(self, order_id: int, image_type: Optional[str] = None) -> List[Dict]:
        """
        Get images for an order

        Args:
            order_id: Order ID
            image_type: Optional filter by image type

        Returns:
            List of image dictionaries
        """
        order = self.order_model.find_by_id(order_id)
        if not order:
            return []

        images = order.get("images", {})

        if image_type:
            # Return specific type
            type_images = images.get(image_type, [])
            if not isinstance(type_images, list):
                type_images = [type_images] if type_images else []
            return type_images
        else:
            # Return all images
            all_images = []
            for img_type in ["pickup", "delivery"]:
                type_images = images.get(img_type, [])
                if not isinstance(type_images, list):
                    type_images = [type_images] if type_images else []
                all_images.extend(type_images)
            return all_images

    def validate_image_limit(self, order_id: int, image_type: str, max_images: int = 15) -> Tuple[bool, Optional[str]]:
        """Check if order has reached image limit"""
        images = self.get_order_images(order_id, image_type)

        if len(images) >= max_images:
            image_type_fi = "nouto" if image_type == "pickup" else "toimitus"
            return False, f"Maksimimäärä ({max_images}) {image_type_fi} kuvia saavutettu"

        return True, None

    def cleanup_orphaned_images(self) -> int:
        """Clean up image files that are no longer referenced in database"""
        cleaned_count = 0

        try:
            # Get all files in upload directory
            if not os.path.exists(self.upload_folder):
                return 0

            all_files = set(os.listdir(self.upload_folder))

            # Get all referenced filenames from database
            orders = self.order_model.find({}, {"images": 1})
            referenced_files = set()

            for order in orders:
                images = order.get("images", {})
                for image_type in ["pickup", "delivery"]:
                    type_images = images.get(image_type, [])
                    if not isinstance(type_images, list):
                        type_images = [type_images] if type_images else []

                    for img in type_images:
                        if "filename" in img:
                            referenced_files.add(img["filename"])

            # Delete orphaned files
            orphaned_files = all_files - referenced_files
            for filename in orphaned_files:
                file_path = os.path.join(self.upload_folder, filename)
                if self._cleanup_file(file_path):
                    cleaned_count += 1

        except Exception as e:
            print(f"Error cleaning up orphaned images: {e}")

        return cleaned_count

    # Private helper methods
    def _validate_file(self, file) -> Optional[str]:
        """Validate uploaded file"""
        if not file or not file.filename:
            return "Tiedostoa ei valittu"

        # Check file extension
        if not self._allowed_file(file.filename):
            return "Virheellinen tiedostotyyppi. Sallitut: JPG, JPEG, PNG, WebP"

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer

        if file_size > self.max_file_size:
            return "Tiedosto on liian suuri (max 5MB)"

        if file_size == 0:
            return "Tiedosto on tyhjä"

        # Validate that PIL can read the image
        try:
            # Create a copy of file content for PIL validation
            file_content = file.read()
            file.seek(0)  # Reset file pointer for later use

            from io import BytesIO
            with Image.open(BytesIO(file_content)) as img:
                # Basic validation - ensure it's a valid image
                img.verify()  # This will raise an exception if the image is corrupted

                # Check if it's actually an image format we can process
                if img.format not in ['JPEG', 'PNG', 'WEBP', 'MPO']:
                    return f"Kuvaformaatti {img.format or 'tuntematon'} ei ole tuettu"

        except Exception as e:
            return f"Kuvatiedosto on vioittunut tai ei kelvollinen: {str(e)}"

        return None

    def _allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        if not filename:
            return False
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def _get_file_extension(self, filename: str) -> str:
        """Get file extension"""
        if not filename or '.' not in filename:
            return 'jpg'
        return filename.rsplit('.', 1)[1].lower()

    def _process_image(self, file_path: str) -> Optional[str]:
        """Process and optimize image"""
        try:
            # First validate that PIL can open the image
            with Image.open(file_path) as img:
                # Validate image format
                if img.format not in ['JPEG', 'PNG', 'WEBP', 'MPO']:
                    print(f"Image processing error: Unsupported image format {img.format}")
                    return None

                # Convert RGBA to RGB if necessary for JPEG compatibility
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                # Resize if too large
                if img.width > MAX_IMAGE_WIDTH:
                    # Calculate new height maintaining aspect ratio
                    new_height = int((MAX_IMAGE_WIDTH / img.width) * img.height)
                    img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)

                # Determine output format and extension
                output_path = file_path
                if not file_path.lower().endswith('.jpg'):
                    # Change extension to .jpg since we're saving as JPEG
                    base_path = file_path.rsplit('.', 1)[0]
                    output_path = f"{base_path}.jpg"

                # Save optimized image as JPEG
                img.save(output_path, 'JPEG', quality=IMAGE_QUALITY, optimize=True)

                # Remove original file if we changed the extension
                if output_path != file_path:
                    self._cleanup_file(file_path)

            return output_path

        except Exception as e:
            print(f"Image processing error for {file_path}: {str(e)}")
            # Log more specific error details
            try:
                with Image.open(file_path) as test_img:
                    print(f"Image details - Format: {test_img.format}, Mode: {test_img.mode}, Size: {test_img.size}")
            except Exception as inner_e:
                print(f"Cannot read image file: {str(inner_e)}")
            return None

    def _cleanup_file(self, file_path: str) -> bool:
        """Remove file safely"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            print(f"Error removing file {file_path}: {e}")
        return False


# Global instance
image_service = ImageService()