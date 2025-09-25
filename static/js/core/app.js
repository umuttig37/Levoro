/**
 * Core Application Initialization
 * Global app setup, utilities, and initialization coordination
 */

class LevoroApp {
    constructor() {
        this.version = '1.0.0';
        this.debug = this.isDevelopment();
        this.components = new Map();

        this.init();
    }

    init() {
        this.log('Levoro App initializing...');

        // Set up global error handling
        this.setupErrorHandling();

        // Initialize core components
        this.initializeComponents();

        // Set up global utilities
        this.setupGlobalUtilities();

        // App ready
        this.onReady();
    }

    setupErrorHandling() {
        window.addEventListener('error', (e) => {
            this.logError('JavaScript Error:', e.error);
        });

        window.addEventListener('unhandledrejection', (e) => {
            this.logError('Unhandled Promise Rejection:', e.reason);
        });
    }

    initializeComponents() {
        // Components are initialized by their own modules
        // This just sets up the registry
        this.log('Component registry ready');
    }

    setupGlobalUtilities() {
        // Global utility functions
        window.utils = {
            formatDate: this.formatDate.bind(this),
            formatCurrency: this.formatCurrency.bind(this),
            debounce: this.debounce.bind(this),
            throttle: this.throttle.bind(this),
            getCookie: this.getCookie.bind(this),
            setCookie: this.setCookie.bind(this)
        };
    }

    onReady() {
        this.log('Levoro App ready');

        // Emit app ready event
        document.dispatchEvent(new CustomEvent('app:ready', {
            detail: { app: this }
        }));

        // Remove loading states if present
        const loadingElements = document.querySelectorAll('.loading, [data-loading]');
        loadingElements.forEach(el => {
            el.classList.remove('loading');
            el.removeAttribute('data-loading');
        });
    }

    // Component registration
    registerComponent(name, instance) {
        this.components.set(name, instance);
        this.log(`Component registered: ${name}`);
    }

    getComponent(name) {
        return this.components.get(name);
    }

    // Utility functions
    formatDate(date, options = {}) {
        const defaultOptions = {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            ...options
        };

        return new Intl.DateTimeFormat('fi-FI', defaultOptions).format(new Date(date));
    }

    formatCurrency(amount, currency = 'EUR') {
        return new Intl.NumberFormat('fi-FI', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }

    setCookie(name, value, days = 7) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
    }

    // Development helpers
    isDevelopment() {
        return location.hostname === 'localhost' ||
               location.hostname === '127.0.0.1' ||
               location.hostname.includes('workspace');
    }

    log(...args) {
        if (this.debug) {
            console.log('[Levoro]', ...args);
        }
    }

    logError(...args) {
        console.error('[Levoro Error]', ...args);
    }

    // API helpers
    async makeRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin',
            ...options
        };

        try {
            const response = await fetch(url, defaultOptions);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }

            return await response.text();
        } catch (error) {
            this.logError('Request failed:', error);
            throw error;
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.levoroApp = new LevoroApp();
});

// Export for modules that need it
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LevoroApp;
}