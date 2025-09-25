/**
 * Form Validation Utilities
 * Client-side validation helpers for forms and inputs
 */

class ValidationUtils {
    constructor() {
        this.patterns = {
            email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
            phone: /^(\+358|0)[1-9][0-9]{6,10}$/,
            regNumber: /^[A-Z]{2,3}-[0-9]{1,3}$/,
            postalCode: /^[0-9]{5}$/
        };

        this.messages = {
            required: 'Tämä kenttä on pakollinen',
            email: 'Virheellinen sähköpostiosoite',
            phone: 'Virheellinen puhelinnumero',
            regNumber: 'Virheellinen rekisterinumero (esim. ABC-123)',
            postalCode: 'Virheellinen postinumero',
            minLength: 'Liian lyhyt, vähintään {min} merkkiä',
            maxLength: 'Liian pitkä, enintään {max} merkkiä',
            match: 'Kentät eivät täsmää'
        };
    }

    // Validate individual field
    validateField(field, rules = {}) {
        const value = field.value.trim();
        const errors = [];

        // Required validation
        if (rules.required && !value) {
            errors.push(this.messages.required);
            return { valid: false, errors };
        }

        // Skip other validations if field is empty and not required
        if (!value && !rules.required) {
            return { valid: true, errors: [] };
        }

        // Email validation
        if (rules.email && !this.patterns.email.test(value)) {
            errors.push(this.messages.email);
        }

        // Phone validation
        if (rules.phone && !this.patterns.phone.test(value)) {
            errors.push(this.messages.phone);
        }

        // Registration number validation
        if (rules.regNumber && !this.patterns.regNumber.test(value)) {
            errors.push(this.messages.regNumber);
        }

        // Postal code validation
        if (rules.postalCode && !this.patterns.postalCode.test(value)) {
            errors.push(this.messages.postalCode);
        }

        // Length validations
        if (rules.minLength && value.length < rules.minLength) {
            errors.push(this.messages.minLength.replace('{min}', rules.minLength));
        }

        if (rules.maxLength && value.length > rules.maxLength) {
            errors.push(this.messages.maxLength.replace('{max}', rules.maxLength));
        }

        // Match validation (for password confirmation, etc.)
        if (rules.match) {
            const matchField = document.querySelector(rules.match);
            if (matchField && value !== matchField.value.trim()) {
                errors.push(this.messages.match);
            }
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }

    // Validate entire form
    validateForm(form, fieldRules = {}) {
        const results = {};
        let isValid = true;

        // Get all form fields
        const fields = form.querySelectorAll('input, textarea, select');

        fields.forEach(field => {
            const fieldName = field.name || field.id;
            if (!fieldName || !fieldRules[fieldName]) return;

            const validation = this.validateField(field, fieldRules[fieldName]);
            results[fieldName] = validation;

            if (!validation.valid) {
                isValid = false;
                this.showFieldError(field, validation.errors);
            } else {
                this.clearFieldError(field);
            }
        });

        return {
            valid: isValid,
            results
        };
    }

    // Show field error
    showFieldError(field, errors) {
        this.clearFieldError(field);

        field.classList.add('error');

        // Create error message element
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.textContent = errors[0]; // Show first error

        // Insert after field
        field.parentNode.insertBefore(errorDiv, field.nextSibling);

        // Focus on first error field if not already focused
        if (document.activeElement !== field) {
            field.focus();
        }
    }

    // Clear field error
    clearFieldError(field) {
        field.classList.remove('error');

        // Remove existing error message
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
    }

    // Real-time validation setup
    setupRealtimeValidation(form, fieldRules = {}) {
        const fields = form.querySelectorAll('input, textarea, select');

        fields.forEach(field => {
            const fieldName = field.name || field.id;
            if (!fieldName || !fieldRules[fieldName]) return;

            // Validate on blur
            field.addEventListener('blur', () => {
                const validation = this.validateField(field, fieldRules[fieldName]);
                if (!validation.valid) {
                    this.showFieldError(field, validation.errors);
                } else {
                    this.clearFieldError(field);
                }
            });

            // Clear error on input
            field.addEventListener('input', () => {
                if (field.classList.contains('error')) {
                    this.clearFieldError(field);
                }
            });
        });

        // Validate on form submit
        form.addEventListener('submit', (e) => {
            const validation = this.validateForm(form, fieldRules);
            if (!validation.valid) {
                e.preventDefault();
                e.stopPropagation();

                // Focus first error field
                const firstErrorField = form.querySelector('.error');
                if (firstErrorField) {
                    firstErrorField.focus();
                }
            }
        });
    }

    // Custom validation function
    addCustomValidation(fieldName, validationFn, errorMessage) {
        // Store custom validations for later use
        if (!this.customValidations) {
            this.customValidations = {};
        }

        this.customValidations[fieldName] = {
            validate: validationFn,
            message: errorMessage
        };
    }

    // Address validation (specific to this app)
    validateAddress(address) {
        if (!address || address.trim().length < 5) {
            return {
                valid: false,
                error: 'Osoite on liian lyhyt'
            };
        }

        // Check for basic address components (street number, street name)
        const addressParts = address.trim().split(/\s+/);
        if (addressParts.length < 2) {
            return {
                valid: false,
                error: 'Syötä katu ja numero'
            };
        }

        return { valid: true };
    }
}

// Initialize validation utilities
document.addEventListener('DOMContentLoaded', () => {
    window.validationUtils = new ValidationUtils();
    window.levoroApp?.registerComponent('validation', window.validationUtils);
});

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ValidationUtils;
}