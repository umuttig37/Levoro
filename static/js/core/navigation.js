/**
 * Navigation and Mobile Menu Management
 * Handles mobile menu toggle and navigation interactions
 */

class NavigationManager {
    constructor() {
        this.nav = document.getElementById('nav-menu');
        this.toggle = document.querySelector('.mobile-menu-toggle');
        this.navLinks = document.querySelectorAll('.nav-link');

        this.initEventListeners();
    }

    initEventListeners() {
        // Mobile menu toggle
        if (this.toggle) {
            this.toggle.addEventListener('click', () => this.toggleMobileMenu());
        }

        // Close mobile menu when clicking on navigation links
        this.navLinks.forEach(link => {
            link.addEventListener('click', () => this.closeMobileMenu());
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', (e) => this.handleOutsideClick(e));

        // Handle escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeMobileMenu();
            }
        });
    }

    toggleMobileMenu() {
        if (!this.nav || !this.toggle) return;

        this.nav.classList.toggle('mobile-open');
        this.toggle.classList.toggle('active');

        // Update ARIA attributes for accessibility
        const isOpen = this.nav.classList.contains('mobile-open');
        this.toggle.setAttribute('aria-expanded', isOpen);
        this.nav.setAttribute('aria-hidden', !isOpen);
    }

    closeMobileMenu() {
        if (!this.nav || !this.toggle) return;

        this.nav.classList.remove('mobile-open');
        this.toggle.classList.remove('active');

        // Update ARIA attributes
        this.toggle.setAttribute('aria-expanded', 'false');
        this.nav.setAttribute('aria-hidden', 'true');
    }

    handleOutsideClick(e) {
        if (!this.nav || !this.toggle) return;

        if (!this.nav.contains(e.target) && !this.toggle.contains(e.target)) {
            this.closeMobileMenu();
        }
    }

    // Public method to check if mobile menu is open
    isMobileMenuOpen() {
        return this.nav?.classList.contains('mobile-open') || false;
    }
}

// Initialize navigation when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.navigationManager = new NavigationManager();
});

// Legacy function for backward compatibility
function toggleMobileMenu() {
    if (window.navigationManager) {
        window.navigationManager.toggleMobileMenu();
    }
}