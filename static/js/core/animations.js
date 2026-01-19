/**
 * Levoro Animation Controller
 * Professional animations for smooth, polished UX
 */

(function () {
    'use strict';

    // ==========================================================================
    // Scroll Animation Observer
    // ==========================================================================

    const scrollAnimationObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const delay = entry.target.dataset.delay || 0;
                setTimeout(() => {
                    entry.target.classList.add('animated');
                }, parseInt(delay));

                // Optionally unobserve after animation
                if (entry.target.dataset.once !== 'false') {
                    scrollAnimationObserver.unobserve(entry.target);
                }
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    // Initialize scroll animations
    function initScrollAnimations() {
        document.querySelectorAll('[data-animate]').forEach(el => {
            scrollAnimationObserver.observe(el);
        });

        // Also handle elements with animate-fade-up class
        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            el.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
            scrollAnimationObserver.observe(el);
        });
    }

    // ==========================================================================
    // Header Scroll Effects
    // ==========================================================================

    let lastScrollY = 0;
    let ticking = false;
    let headerScrolled = false; // Track current state to add hysteresis
    let lastHeaderToggleTime = 0; // Cooldown timer to prevent rapid toggling

    function updateHeader() {
        const header = document.querySelector('.header');
        if (!header) return;

        const scrollY = window.scrollY;
        const now = Date.now();
        const cooldownMs = 150; // Minimum time between class toggles

        // Add/remove scrolled class with hysteresis to prevent flashing
        // Use different thresholds for adding vs removing the class
        const scrollDownThreshold = 80;  // Add class when scrolling past 80px
        const scrollUpThreshold = 10;    // Remove class when scrolling above 10px

        // Only toggle if cooldown has passed
        if (now - lastHeaderToggleTime > cooldownMs) {
            if (!headerScrolled && scrollY > scrollDownThreshold) {
                header.classList.add('header-scrolled');
                headerScrolled = true;
                lastHeaderToggleTime = now;
            } else if (headerScrolled && scrollY < scrollUpThreshold) {
                header.classList.remove('header-scrolled');
                headerScrolled = false;
                lastHeaderToggleTime = now;
            }
        }

        // Hide/show header on scroll direction - require minimum scroll delta
        const scrollDelta = scrollY - lastScrollY;
        if (scrollDelta > 5 && scrollY > 200) {
            // Scrolling down significantly
            header.classList.add('header-hidden');
        } else if (scrollDelta < -5 || scrollY <= 100) {
            // Scrolling up significantly or near top
            header.classList.remove('header-hidden');
        }

        lastScrollY = scrollY;
        ticking = false;
    }

    function onScroll() {
        if (!ticking) {
            requestAnimationFrame(updateHeader);
            ticking = true;
        }
    }

    // ==========================================================================
    // Scroll to Top Button
    // ==========================================================================

    function initScrollTopButton() {
        const scrollBtn = document.getElementById('scrollTopBtn');
        if (!scrollBtn) return;

        window.addEventListener('scroll', () => {
            if (window.scrollY > 400) {
                scrollBtn.classList.add('visible');
            } else {
                scrollBtn.classList.remove('visible');
            }
        }, { passive: true });

        scrollBtn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // ==========================================================================
    // Smooth Scroll for Anchor Links
    // ==========================================================================

    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                const targetId = this.getAttribute('href');
                if (targetId === '#') return;

                const target = document.querySelector(targetId);
                if (target) {
                    e.preventDefault();
                    const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
                    const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight - 20;

                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    // ==========================================================================
    // Button Ripple Effect
    // ==========================================================================

    function createRipple(event) {
        const button = event.currentTarget;
        if (!button.classList.contains('btn-ripple-effect')) return;

        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;

        ripple.style.width = ripple.style.height = `${size}px`;
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        ripple.classList.add('ripple-effect');

        button.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    }

    function initRippleEffect() {
        document.querySelectorAll('.btn-ripple-effect').forEach(btn => {
            btn.addEventListener('click', createRipple);
        });
    }

    // ==========================================================================
    // Stagger Animation Helper
    // ==========================================================================

    function staggerElements(selector, delayMs = 100) {
        const elements = document.querySelectorAll(selector);
        elements.forEach((el, index) => {
            el.style.animationDelay = `${index * delayMs}ms`;
        });
    }

    // ==========================================================================
    // Page Load Animations
    // ==========================================================================

    function initPageLoadAnimations() {
        // Add loaded class to body for CSS animations
        document.body.classList.add('page-loaded');

        // Stagger hero elements
        staggerElements('.hero-feature', 100);
        staggerElements('.feature-card-new', 150);
        staggerElements('.category-card', 150);
    }

    // ==========================================================================
    // Form Input Animations
    // ==========================================================================

    function initFormAnimations() {
        // Add focus/blur animations to inputs
        document.querySelectorAll('.form-input, .form-textarea, .form-select, .form-input-new').forEach(input => {
            input.addEventListener('focus', () => {
                input.parentElement?.classList.add('input-focused');
            });

            input.addEventListener('blur', () => {
                input.parentElement?.classList.remove('input-focused');
                if (input.value) {
                    input.parentElement?.classList.add('input-filled');
                } else {
                    input.parentElement?.classList.remove('input-filled');
                }
            });
        });
    }

    // ==========================================================================
    // Mobile Menu Animation
    // ==========================================================================

    function initMobileMenu() {
        const toggle = document.getElementById('mobile-menu-toggle');
        const nav = document.getElementById('nav-menu');

        if (!toggle || !nav) return;

        toggle.addEventListener('click', () => {
            const isOpen = nav.classList.contains('nav-open');

            if (isOpen) {
                nav.classList.remove('nav-open');
                nav.classList.add('nav-closing');
                setTimeout(() => nav.classList.remove('nav-closing'), 300);
            } else {
                nav.classList.add('nav-open');
            }

            toggle.classList.toggle('menu-open');
        });
    }

    // ==========================================================================
    // Card Hover Sound (optional, subtle feedback)
    // ==========================================================================

    function initHoverEffects() {
        // Add subtle transform feedback on interactive cards
        document.querySelectorAll('.feature-card, .feature-card-new, .card-animated, .contact-info-card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-4px)';
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
            });
        });
    }

    // ==========================================================================
    // Counter Animation (for statistics)
    // ==========================================================================

    function animateCounter(element, target, duration = 2000) {
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function (ease-out)
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(start + (target - start) * easeOut);

            element.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                element.textContent = target.toLocaleString();
            }
        }

        requestAnimationFrame(update);
    }

    function initCounterAnimations() {
        const counters = document.querySelectorAll('[data-counter]');

        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const target = parseInt(entry.target.dataset.counter);
                    animateCounter(entry.target, target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(counter => counterObserver.observe(counter));
    }

    // ==========================================================================
    // Initialize Everything
    // ==========================================================================

    function init() {
        // Wait for DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initAll);
        } else {
            initAll();
        }
    }

    function initAll() {
        initScrollAnimations();
        initScrollTopButton();
        initSmoothScroll();
        initRippleEffect();
        initPageLoadAnimations();
        initFormAnimations();
        initMobileMenu();
        initHoverEffects();
        initCounterAnimations();

        // Add scroll listener for header
        window.addEventListener('scroll', onScroll, { passive: true });

        console.log('Levoro animations initialized');
    }

    // Start
    init();

    // Expose for external use
    window.LevoroAnimations = {
        staggerElements,
        animateCounter,
        initScrollAnimations
    };

})();
