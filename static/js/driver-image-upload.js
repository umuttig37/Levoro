/**
 * Driver Image Upload Manager
 * Handles dynamic button states and image counter updates for driver workflow
 *
 * Features:
 * - Updates confirmation button disabled state based on 5 image minimum
 * - Updates counter text to show progress
 * - Integrates with existing AJAX upload system
 * - Handles both pickup and delivery images independently
 */

(function () {
    'use strict';

    // Minimum images required for confirmation
    const MIN_IMAGES_REQUIRED = 5;

    /**
     * Initialize image upload manager
     */
    function initializeImageUploadManager() {
        // Update button states on page load
        updateConfirmButtonState('pickup');
        updateConfirmButtonState('delivery');

        // Override the existing addImageToGrid function to trigger updates
        if (typeof window.addImageToGrid === 'function') {
            const originalAddImageToGrid = window.addImageToGrid;
            window.addImageToGrid = function (imageData, imageType, orderId) {
                // Call original function
                originalAddImageToGrid(imageData, imageType, orderId);

                // Update confirmation button state
                updateConfirmButtonState(imageType);
            };
        }

        // Override the existing updateImageCounter function to show progress
        if (typeof window.updateImageCounter === 'function') {
            const originalUpdateImageCounter = window.updateImageCounter;
            window.updateImageCounter = function (imageType, count) {
                // Call original function
                originalUpdateImageCounter(imageType, count);

                // Update confirmation button state
                updateConfirmButtonState(imageType);

                // Update counter text to show progress
                updateCounterText(imageType, count);
            };
        }

        // Override the existing deleteDriverImage success handler
        // We need to update button state after deletion
        const originalFetch = window.fetch;
        window.fetch = function (...args) {
            return originalFetch.apply(this, args).then(response => {
                // Check if this is a delete image request
                const url = args[0];
                if (typeof url === 'string' && url.includes('/driver/api/job/') && url.includes('/image/')) {
                    const method = args[1]?.method;
                    if (method === 'DELETE') {
                        // Clone response to read it
                        return response.clone().json().then(data => {
                            if (data.success) {
                                // Extract image type from URL
                                const urlParts = url.split('/');
                                const imageType = urlParts[urlParts.length - 2];

                                // Update button state
                                setTimeout(() => {
                                    updateConfirmButtonState(imageType);
                                }, 100);
                            }
                            return response;
                        }).catch(() => response);
                    }
                }
                return response;
            });
        };

        console.log('[Driver Image Upload Manager] Initialized');
    }

    /**
     * Update confirmation button disabled state based on image count
     * @param {string} imageType - 'pickup' or 'delivery'
     */
    function updateConfirmButtonState(imageType) {
        const buttonId = `confirm-${imageType}-btn`;
        const button = document.getElementById(buttonId);

        if (!button) {
            // Button doesn't exist (not in the right progress state)
            return;
        }

        // Count current images
        const currentCount = countImages(imageType);

        // Update button state
        const shouldDisable = currentCount < MIN_IMAGES_REQUIRED;
        button.disabled = shouldDisable;

        // Update data attribute
        button.setAttribute('data-current-images', currentCount);

        // Update button styling for better UX
        if (shouldDisable) {
            button.style.opacity = '0.5';
            button.style.cursor = 'not-allowed';
        } else {
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
        }

        // Update hint text
        updateHintText(imageType, currentCount);

        console.log(`[Driver Image Upload] Updated ${imageType} button: ${currentCount}/${MIN_IMAGES_REQUIRED} images`);
    }

    /**
     * Count images for a specific type
     * @param {string} imageType - 'pickup' or 'delivery'
     * @returns {number} Number of images
     */
    function countImages(imageType) {
        const imageItems = document.querySelectorAll(`.image-item[data-image-type="${imageType}"]`);
        return imageItems.length;
    }

    /**
     * Update counter text to show progress toward minimum
     * @param {string} imageType - 'pickup' or 'delivery'
     * @param {number} count - Current image count
     */
    function updateCounterText(imageType, count) {
        const section = document.querySelector(`.image-section[data-image-type="${imageType}"]`);
        if (!section) return;

        const counterText = section.querySelector('.image-counter-text');
        if (!counterText) return;

        // Show progress toward minimum requirement
        if (count < MIN_IMAGES_REQUIRED) {
            counterText.textContent = `${count}/${MIN_IMAGES_REQUIRED} kuvaa (min)`;
            counterText.style.color = '#dc2626'; // Red color
        } else {
            counterText.textContent = `${count}/15 kuvaa`;
            counterText.style.color = '#16a34a'; // Green color
        }
    }

    /**
     * Update hint text below confirmation button
     * @param {string} imageType - 'pickup' or 'delivery'
     * @param {number} count - Current image count
     */
    function updateHintText(imageType, count) {
        const buttonId = `confirm-${imageType}-btn`;
        const button = document.getElementById(buttonId);
        if (!button) return;

        // Find hint text (next sibling paragraph)
        const form = button.closest('form');
        if (!form) return;

        let hintP = form.querySelector('.driver-action-hint');

        const remaining = MIN_IMAGES_REQUIRED - count;

        if (remaining > 0) {
            // Need more images
            if (!hintP) {
                hintP = document.createElement('p');
                hintP.className = 'driver-action-hint';
                hintP.style.textAlign = 'center';
                hintP.style.marginTop = '0.5rem';
                form.appendChild(hintP);
            }
            hintP.textContent = `Lataa vielä ${remaining} kuvaa`;
            hintP.style.color = '#dc2626'; // Red
        } else {
            // Ready to confirm
            if (hintP) {
                hintP.textContent = 'Valmis vahvistettavaksi!';
                hintP.style.color = '#16a34a'; // Green
            }
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeImageUploadManager);
    } else {
        initializeImageUploadManager();
    }

})();
