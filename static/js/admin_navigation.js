document.addEventListener('DOMContentLoaded', function () {
    const mainContent = document.querySelector('main');
    if (!mainContent) return;

    document.body.addEventListener('click', async function (e) {
        const link = e.target.closest('.admin-nav-link');
        if (!link) return;

        // Don't intercept if modifier keys are pressed (e.g. Ctrl+Click for new tab)
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

        e.preventDefault();
        const url = link.href;

        // Show loading state (optional)
        mainContent.style.opacity = '0.5';
        mainContent.style.pointerEvents = 'none';

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Network response was not ok');

            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newContent = doc.querySelector('main');
            if (newContent) {
                mainContent.innerHTML = newContent.innerHTML;

                // Update URL
                history.pushState({}, '', url);

                // Extract and execute scripts
                const scripts = mainContent.querySelectorAll('script');
                scripts.forEach(oldScript => {
                    const newScript = document.createElement('script');
                    Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
                    newScript.appendChild(document.createTextNode(oldScript.innerHTML));
                    oldScript.parentNode.replaceChild(newScript, oldScript);
                });

                // Re-initialize specific components if needed
                // e.g. if you have global init functions
            }
        } catch (error) {
            console.error('Navigation error:', error);
            // Fallback to normal navigation
            window.location.href = url;
        } finally {
            mainContent.style.opacity = '';
            mainContent.style.pointerEvents = '';
        }
    });

    // Handle back/forward buttons
    window.addEventListener('popstate', () => {
        window.location.reload();
    });
});
