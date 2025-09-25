/**
 * Advanced Admin Image Modal Component
 * Handles image modal with navigation, deletion, and multi-image support
 */

class AdminImageModal {
    constructor() {
        this.modal = document.getElementById('imageModal');
        this.modalImage = document.getElementById('modalImage');
        this.modalTitle = document.getElementById('modalTitle');
        this.modalInfo = document.getElementById('modalImageInfo');
        this.prevBtn = document.querySelector('.modal-nav.prev');
        this.nextBtn = document.querySelector('.modal-nav.next');
        this.deleteBtn = document.querySelector('.modal-delete, .btn-danger');

        this.currentImages = { pickup: [], delivery: [] };
        this.currentImageType = '';
        this.currentImageIndex = 0;
        this.currentOrderId = null;

        this.initEventListeners();
    }

    initEventListeners() {
        // Navigation buttons
        if (this.prevBtn) {
            this.prevBtn.addEventListener('click', () => this.prevImage());
        }
        if (this.nextBtn) {
            this.nextBtn.addEventListener('click', () => this.nextImage());
        }

        // Delete button
        if (this.deleteBtn) {
            this.deleteBtn.addEventListener('click', () => this.deleteCurrentImage());
        }

        // Close modal
        const closeBtn = document.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }

        // Close on outside click
        window.addEventListener('click', (event) => {
            if (event.target === this.modal) {
                this.close();
            }
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (this.isOpen()) {
                switch (e.key) {
                    case 'Escape':
                        this.close();
                        break;
                    case 'ArrowLeft':
                        this.prevImage();
                        break;
                    case 'ArrowRight':
                        this.nextImage();
                        break;
                    case 'Delete':
                    case 'Backspace':
                        if (e.ctrlKey || e.metaKey) {
                            this.deleteCurrentImage();
                        }
                        break;
                }
            }
        });
    }

    initImageModal(orderId) {
        this.currentOrderId = orderId;
        this.currentImages = { pickup: [], delivery: [] };

        // Collect pickup images
        document.querySelectorAll('[data-image-type="pickup"] .image-thumbnail').forEach((img, index) => {
            const imageId = img.getAttribute('data-image-id');
            const imageSrc = img.src;
            this.currentImages.pickup.push({ id: imageId, src: imageSrc, index: index });
        });

        // Collect delivery images
        document.querySelectorAll('[data-image-type="delivery"] .image-thumbnail').forEach((img, index) => {
            const imageId = img.getAttribute('data-image-id');
            const imageSrc = img.src;
            this.currentImages.delivery.push({ id: imageId, src: imageSrc, index: index });
        });
    }

    open(imageType, imageId, orderId = null) {
        if (orderId) {
            this.initImageModal(orderId);
        }

        this.currentImageType = imageType;
        const images = this.currentImages[imageType];
        const imageIndex = images.findIndex(img => img.id === imageId);

        if (imageIndex !== -1) {
            this.currentImageIndex = imageIndex;
            this.showCurrentImage();
            this.modal.style.display = 'block';

            // Accessibility
            this.modal.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
        }
    }

    close() {
        if (this.modal) {
            this.modal.style.display = 'none';
            this.modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = 'auto';
        }
    }

    isOpen() {
        return this.modal?.style.display === 'block';
    }

    showCurrentImage() {
        const images = this.currentImages[this.currentImageType];
        if (!images || images.length === 0) return;

        const currentImage = images[this.currentImageIndex];

        if (this.modalImage) {
            this.modalImage.src = currentImage.src;
            this.modalImage.alt = `${this.currentImageType === 'pickup' ? 'Nouto' : 'Toimitus'} kuva`;
        }

        if (this.modalTitle) {
            this.modalTitle.textContent = this.currentImageType === 'pickup' ? 'Nouto kuva' : 'Toimitus kuva';
        }

        if (this.modalInfo) {
            this.modalInfo.textContent = `Kuva ${this.currentImageIndex + 1}/${images.length}`;
        }

        // Update navigation button visibility
        this.updateNavigationButtons(images);
    }

    updateNavigationButtons(images) {
        if (this.prevBtn) {
            this.prevBtn.style.display = images.length > 1 && this.currentImageIndex > 0 ? 'flex' : 'none';
        }
        if (this.nextBtn) {
            this.nextBtn.style.display = images.length > 1 && this.currentImageIndex < images.length - 1 ? 'flex' : 'none';
        }
    }

    prevImage() {
        const images = this.currentImages[this.currentImageType];
        if (this.currentImageIndex > 0) {
            this.currentImageIndex--;
            this.showCurrentImage();
        }
    }

    nextImage() {
        const images = this.currentImages[this.currentImageType];
        if (this.currentImageIndex < images.length - 1) {
            this.currentImageIndex++;
            this.showCurrentImage();
        }
    }

    deleteCurrentImage() {
        const images = this.currentImages[this.currentImageType];
        if (images && images.length > 0) {
            const currentImage = images[this.currentImageIndex];
            this.deleteImage(this.currentOrderId, this.currentImageType, currentImage.id);
        }
    }

    deleteImage(orderId, imageType, imageId) {
        const confirmMessage = 'Oletko varma, että haluat poistaa tämän kuvan?';
        if (confirm(confirmMessage)) {
            // Create and submit delete form
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/admin/order/${orderId}/image/${imageType}/${imageId}/delete`;
            form.style.display = 'none';

            // Add CSRF token if available
            const csrfToken = document.querySelector('input[name="csrf_token"]');
            if (csrfToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken.value;
                form.appendChild(csrfInput);
            }

            document.body.appendChild(form);
            form.submit();
        }
    }

    // Get current image data
    getCurrentImage() {
        const images = this.currentImages[this.currentImageType];
        return images?.[this.currentImageIndex] || null;
    }

    // Get total images count for current type
    getTotalImages() {
        return this.currentImages[this.currentImageType]?.length || 0;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.adminImageModal = new AdminImageModal();
});

// Legacy functions for backward compatibility
function openImageModal(imageType, imageId) {
    if (window.adminImageModal) {
        // Extract order ID from current page context
        const orderId = window.currentOrderId || document.querySelector('[data-order-id]')?.getAttribute('data-order-id');
        window.adminImageModal.open(imageType, imageId, orderId);
    }
}

function closeImageModal() {
    if (window.adminImageModal) {
        window.adminImageModal.close();
    }
}

function prevImage() {
    if (window.adminImageModal) {
        window.adminImageModal.prevImage();
    }
}

function nextImage() {
    if (window.adminImageModal) {
        window.adminImageModal.nextImage();
    }
}

function deleteCurrentImage() {
    if (window.adminImageModal) {
        window.adminImageModal.deleteCurrentImage();
    }
}

function deleteImage(orderId, imageType, imageId) {
    if (window.adminImageModal) {
        window.adminImageModal.deleteImage(orderId, imageType, imageId);
    }
}