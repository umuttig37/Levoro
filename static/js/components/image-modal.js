/**
 * Image Modal Component
 * Handles basic image modal functionality for client views
 */

class ImageModal {
    constructor() {
        this.modal = document.getElementById('imageModal');
        this.modalImage = document.getElementById('modalImage');
        this.modalClose = document.querySelector('.modal-close');

        this.initEventListeners();
    }

    initEventListeners() {
        // Close modal events
        if (this.modalClose) {
            this.modalClose.addEventListener('click', () => this.close());
        }

        // Close on outside click
        if (this.modal) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.close();
                }
            });
        }

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen()) {
                this.close();
            }
        });
    }

    open(imageSrc) {
        if (!this.modal || !this.modalImage) return;

        this.modalImage.src = imageSrc;
        this.modal.style.display = 'block';
        document.body.style.overflow = 'hidden';

        // Focus management for accessibility
        this.modal.setAttribute('aria-hidden', 'false');
        this.modalClose?.focus();

        // Emit custom event
        this.emit('opened', { imageSrc });
    }

    close() {
        if (!this.modal) return;

        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';

        // Reset image source to save memory
        if (this.modalImage) {
            this.modalImage.src = '';
        }

        // Accessibility
        this.modal.setAttribute('aria-hidden', 'true');

        // Emit custom event
        this.emit('closed');
    }

    isOpen() {
        return this.modal?.style.display === 'block';
    }

    // Event emitter functionality
    emit(eventName, data = {}) {
        const event = new CustomEvent(`imageModal:${eventName}`, {
            detail: data,
            bubbles: true
        });
        document.dispatchEvent(event);
    }

    // Open modal by finding image element with specific ID
    openByImageId(imageType, imageId) {
        const imageElement = document.querySelector(`img[onclick*='${imageId}']`);
        if (imageElement) {
            this.open(imageElement.src);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.imageModal = new ImageModal();
});

// Legacy functions for backward compatibility
function openImageModal(imageSrc) {
    if (window.imageModal) {
        window.imageModal.open(imageSrc);
    }
}

function openClientImageModal(imageType, imageId) {
    if (window.imageModal) {
        window.imageModal.openByImageId(imageType, imageId);
    }
}

function closeImageModal() {
    if (window.imageModal) {
        window.imageModal.close();
    }
}