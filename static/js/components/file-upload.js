/**
 * File Upload Component
 * Handles image upload functionality with progress indicators and validation
 */

class FileUploadManager {
    constructor() {
        this.maxFileSize = 5 * 1024 * 1024; // 5MB
        this.allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

        this.initEventListeners();
    }

    initEventListeners() {
        // Handle file input changes globally
        document.addEventListener('change', (e) => {
            if (e.target.type === 'file' && e.target.accept && e.target.accept.includes('image')) {
                this.handleFileSelection(e.target);
            }
        });

        // Handle form submissions with file uploads
        document.addEventListener('submit', (e) => {
            if (e.target.enctype === 'multipart/form-data') {
                this.handleFormSubmission(e);
            }
        });
    }

    handleFileSelection(fileInput) {
        const files = Array.from(fileInput.files);

        if (files.length === 0) return;

        // Validate each file
        for (const file of files) {
            const validation = this.validateFile(file);
            if (!validation.valid) {
                this.showError(validation.message);
                fileInput.value = ''; // Clear invalid selection
                return;
            }
        }

        // Show preview if single image
        if (files.length === 1) {
            this.showImagePreview(files[0], fileInput);
        }

        // Enable submit button if form exists
        const form = fileInput.closest('form');
        const submitBtn = form?.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = false;
        }

        // Auto-submit if configured
        if (fileInput.dataset.autoSubmit === 'true') {
            this.submitImageForm(fileInput);
        }
    }

    handleFormSubmission(form) {
        const fileInputs = form.querySelectorAll('input[type="file"]');
        let hasFiles = false;

        for (const input of fileInputs) {
            if (input.files && input.files.length > 0) {
                hasFiles = true;
                break;
            }
        }

        if (hasFiles) {
            this.showUploadProgress(form);
        }
    }

    validateFile(file) {
        // Check file type
        if (!this.allowedTypes.includes(file.type)) {
            return {
                valid: false,
                message: 'Virheellinen tiedostotyyppi. Sallitut tiedostot: JPG, PNG, WebP'
            };
        }

        // Check file size
        if (file.size > this.maxFileSize) {
            return {
                valid: false,
                message: 'Tiedosto on liian suuri. Maksimikoko: 5MB'
            };
        }

        return { valid: true };
    }

    showImagePreview(file, fileInput) {
        const reader = new FileReader();
        reader.onload = (e) => {
            // Find or create preview container
            let preview = fileInput.parentNode.querySelector('.file-preview');
            if (!preview) {
                preview = document.createElement('div');
                preview.className = 'file-preview';
                fileInput.parentNode.appendChild(preview);
            }

            preview.innerHTML = `
                <div class="preview-image">
                    <img src="${e.target.result}" alt="Preview" style="max-width: 150px; max-height: 150px; border-radius: 8px;">
                    <div class="preview-info">
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">${this.formatFileSize(file.size)}</span>
                    </div>
                </div>
            `;
        };
        reader.readAsDataURL(file);
    }

    showUploadProgress(form) {
        // Find or create progress container
        let progressContainer = form.querySelector('.upload-progress');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.className = 'upload-progress';
            form.appendChild(progressContainer);
        }

        // Show progress indicator
        const uploadStatus = form.querySelector('.upload-status');
        const submitButton = form.querySelector('button[type="submit"]');

        if (uploadStatus) {
            uploadStatus.style.display = 'block';
            uploadStatus.textContent = 'Ladataan...';
        }

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'Ladataan...';
        }

        // Add spinner animation
        progressContainer.innerHTML = `
            <div class="upload-spinner">
                <div class="spinner"></div>
                <span>Ladataan kuvaa...</span>
            </div>
        `;
    }

    showError(message) {
        // Create or update error message
        let errorDiv = document.querySelector('.upload-error');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'upload-error alert alert-danger';
            document.body.appendChild(errorDiv);

            // Auto-remove after 5 seconds
            setTimeout(() => {
                errorDiv.remove();
            }, 5000);
        }

        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Public method to trigger file upload programmatically
    submitImageForm(fileInput) {
        if (fileInput.files && fileInput.files.length > 0) {
            const form = fileInput.closest('form');
            if (form) {
                this.showUploadProgress(form);
                form.submit();
            }
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.fileUploadManager = new FileUploadManager();
});

// Legacy function for backward compatibility
function submitImageForm(fileInput) {
    if (window.fileUploadManager) {
        window.fileUploadManager.submitImageForm(fileInput);
    }
}