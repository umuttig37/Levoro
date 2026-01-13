/**
 * Global Custom Form Validation
 * Replaces browser native validation with custom UI
 */

document.addEventListener('DOMContentLoaded', () => {
    // Select all forms that shouldn't be excluded (add .no-custom-validation class if needed)
    const forms = document.querySelectorAll('form:not(.no-custom-validation)');

    forms.forEach(form => {
        // Disable browser native validation UI
        form.setAttribute('novalidate', 'true');

        // Handle Form Submission
        form.addEventListener('submit', (e) => {
            let isValid = true;
            let firstInvalid = null;

            // Find all inputs, selects, textareas
            const inputs = form.querySelectorAll('input, select, textarea');

            inputs.forEach(input => {
                // Skip hidden inputs (unless they need validation? usually native validation ignores them anyway)
                if (input.type === 'hidden' || input.disabled || input.readOnly) return;

                // If the input is in a hidden container (e.g., hidden step in wizard), 
                // we generally shouldn't validate it unless the logic specifically handles it.
                // For a global script, checking offsetParent === null is a good way to see if it's visible.
                if (input.offsetParent === null) return;

                if (!validateInput(input)) {
                    isValid = false;
                    if (!firstInvalid) firstInvalid = input;
                }
            });

            if (!isValid) {
                e.preventDefault();
                e.stopPropagation();

                if (firstInvalid) {
                    firstInvalid.focus();
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });

        // specific handling for remember-me checkbox or similar
        // usually we don't validate checkboxes unless required.

        // Add real-time validation clearing
        form.querySelectorAll('input, select, textarea').forEach(input => {
            // Clear error on interact
            input.addEventListener('input', () => clearError(input));
            input.addEventListener('change', () => clearError(input));

            // Validate on blur (optional, maybe too aggressive? Let's stick to just clearing for now, 
            // or validate only if it was already marked invalid?)
            // A good pattern is: validate on blur, but only if user has visited field. 
            // For now, let's just clear errors on input to keep it simple and less annoying.

            // Exception: For empty required fields lost focus, we might want to alert? 
            // Let's stick to submit-time validation + clear-on-input for the "cleanest" modern feel without being nagging.
        });
    });

    /**
     * Validates a single input.
     * Returns true if valid, false otherwise.
     */
    function validateInput(input) {
        // Clear previous error
        clearError(input);

        // Check validity
        if (!input.checkValidity()) {
            let message = input.validationMessage;

            // Custom Finnish messages override
            if (input.validity.valueMissing) {
                if (input.type === 'checkbox') {
                    message = "Valitse tämä ruutu jatkaaksesi";
                } else if (input.type === 'radio') {
                    message = "Valitse yksi vaihtoehto";
                } else {
                    message = "Täytä tämä kenttä";
                }
            } else if (input.validity.typeMismatch) {
                if (input.type === 'email') {
                    message = "Syötä kelvollinen sähköpostiosoite";
                } else if (input.type === 'url') {
                    message = "Syötä kelvollinen URL-osoite";
                }
            } else if (input.validity.patternMismatch) {
                // Use title if available
                if (input.title) message = input.title;
                else message = "Tarkista tiedot (muoto on virheellinen)";
            } else if (input.validity.tooShort) {
                message = `Liian lyhyt (vähintään ${input.minLength} merkkiä)`;
            } else if (input.validity.tooLong) {
                message = `Liian pitkä (enintään ${input.maxLength} merkkiä)`;
            } else if (input.validity.rangeUnderflow) {
                message = `Arvon on oltava vähintään ${input.min}`;
            } else if (input.validity.rangeOverflow) {
                message = `Arvon on oltava enintään ${input.max}`;
            }

            // Custom checks for specific IDs if needed (e.g. password match)
            if (input.id === 'password-confirm' || input.name === 'confirm_password') {
                const pw = form.querySelector('input[name="password"]');
                if (pw && pw.value !== input.value) {
                    message = "Salasanat eivät täsmää";
                    input.setCustomValidity(message); // Force invalid
                } else {
                    input.setCustomValidity(''); // Reset
                }
            }

            showError(input, message);
            return false;
        }
        return true;
    }

    function showError(input, message) {
        input.classList.add('input-error');

        // Create error message element
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-text';
        errorDiv.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16" class="flex-shrink-0"><path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12ZM12 8.25a.75.75 0 0 1 .75.75v3.75a.75.75 0 0 1-1.5 0V9a.75.75 0 0 1 .75-.75Zm0 8.25a.75.75 0 1 0 0-1.5 .75.75 0 0 0 0 1.5Z" clip-rule="evenodd" /></svg>${message}`;

        // Determine insertion point
        // 1. If input is inside a .input-group or .password-input-wrapper, append after that wrapper
        // 2. Otherwise append after input

        const wrapper = input.closest('.input-group') ||
            input.closest('.password-input-wrapper') ||
            input.closest('.relative');

        if (wrapper) {
            // Check if error already exists in wrapper to avoid duplicates (though we clear first)
            if (wrapper.nextElementSibling && wrapper.nextElementSibling.classList.contains('error-text')) {
                wrapper.nextElementSibling.remove();
            }
            // Insert after wrapper
            wrapper.parentNode.insertBefore(errorDiv, wrapper.nextSibling);
        } else {
            // Insert after input
            input.parentNode.insertBefore(errorDiv, input.nextSibling);
        }
    }

    function clearError(input) {
        input.classList.remove('input-error');

        // Find related error text
        // It might be next sibling, or after the wrapper

        // Check next sibling
        if (input.nextElementSibling && input.nextElementSibling.classList.contains('error-text')) {
            input.nextElementSibling.remove();
            return;
        }

        // Check wrapper's next sibling
        const wrapper = input.closest('.input-group') ||
            input.closest('.password-input-wrapper') ||
            input.closest('.relative');

        if (wrapper && wrapper.nextElementSibling && wrapper.nextElementSibling.classList.contains('error-text')) {
            wrapper.nextElementSibling.remove();
        }
    }
});