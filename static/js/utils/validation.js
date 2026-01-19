/**
 * Global Custom Form Validation
 * Replaces browser native validation with toast messages
 */

document.addEventListener('DOMContentLoaded', () => {
    // Select all forms (they should have novalidate in HTML)
    const forms = document.querySelectorAll('form:not(.no-custom-validation)');

    forms.forEach(form => {
        // Handle Form Submission
        form.addEventListener('submit', (e) => {
            let isValid = true;
            let firstInvalid = null;
            let errorMessages = [];

            // Find all inputs, selects, textareas
            const inputs = form.querySelectorAll('input, select, textarea');

            inputs.forEach(input => {
                // Skip hidden inputs
                if (input.type === 'hidden' || input.disabled || input.readOnly) return;

                // Skip invisible inputs
                if (input.offsetParent === null) return;

                // Clear previous error styling
                clearError(input);

                if (!input.checkValidity()) {
                    let message = getValidationMessage(input, form);
                    
                    if (!errorMessages.includes(message)) {
                        errorMessages.push(message);
                    }
                    
                    showError(input);
                    isValid = false;
                    if (!firstInvalid) firstInvalid = input;
                }
            });

            if (!isValid) {
                e.preventDefault();
                e.stopPropagation();

                // Show toast with first error message
                if (errorMessages.length > 0 && typeof showToast === 'function') {
                    showToast(errorMessages[0], 'warning');
                }

                if (firstInvalid) {
                    firstInvalid.focus();
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });

        // Add real-time validation clearing
        form.querySelectorAll('input, select, textarea').forEach(input => {
            input.addEventListener('input', () => clearError(input));
            input.addEventListener('change', () => clearError(input));
        });
    });

    /**
     * Get user-friendly validation message in Finnish
     */
    function getValidationMessage(input, form) {
        // Try to get field label
        const labelEl = input.closest('.form-group')?.querySelector('label') 
            || input.closest('.contact-form-group')?.querySelector('label')
            || form.querySelector(`label[for="${input.id}"]`);
        const fieldName = labelEl?.textContent?.replace('*', '').trim() || input.placeholder || 'Tämä kenttä';

        if (input.validity.valueMissing) {
            if (input.type === 'checkbox') {
                return "Hyväksy ehdot jatkaaksesi";
            } else if (input.type === 'radio') {
                return "Valitse yksi vaihtoehto";
            } else {
                return `${fieldName} on pakollinen`;
            }
        } else if (input.validity.typeMismatch) {
            if (input.type === 'email') {
                return "Syötä kelvollinen sähköpostiosoite";
            } else if (input.type === 'url') {
                return "Syötä kelvollinen URL-osoite";
            } else if (input.type === 'tel') {
                return "Syötä kelvollinen puhelinnumero";
            }
        } else if (input.validity.patternMismatch) {
            return input.title || "Tarkista kentän muoto";
        } else if (input.validity.tooShort) {
            return `Vähintään ${input.minLength} merkkiä vaaditaan`;
        } else if (input.validity.tooLong) {
            return `Enintään ${input.maxLength} merkkiä sallittu`;
        } else if (input.validity.rangeUnderflow) {
            return `Arvon on oltava vähintään ${input.min}`;
        } else if (input.validity.rangeOverflow) {
            return `Arvon on oltava enintään ${input.max}`;
        }

        // Password confirmation check
        if (input.id === 'password-confirm' || input.name === 'confirm_password' || input.name === 'password_confirm') {
            const pw = form.querySelector('input[name="password"]') || form.querySelector('#password');
            if (pw && pw.value !== input.value) {
                return "Salasanat eivät täsmää";
            }
        }

        return "Tarkista kentän arvo";
    }

    function showError(input) {
        input.classList.add('input-error');
        // Add red border styling
        input.style.borderColor = '#f87171';
        input.style.boxShadow = '0 0 0 3px rgba(248, 113, 113, 0.15)';
    }

    function clearError(input) {
        input.classList.remove('input-error');
        input.style.borderColor = '';
        input.style.boxShadow = '';
    }
});