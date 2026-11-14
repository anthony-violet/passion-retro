(function () {
    const EMBED_URL = '/gallery/embed/';

    function getRoot(element) {
        return element.closest('.gallery-content, .content-gallery');
    }

    function getFolder(root) {
        const state = root ? root.querySelector('.gallery-state') : null;
        return state ? (state.dataset.folder || '') : '';
    }

    async function loadFolder(root, folder) {
        if (!root) {
            return;
        }

        const url = EMBED_URL + (folder ? '?folder=' + encodeURIComponent(folder) : '');
        const response = await fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'},
            credentials: 'same-origin'
        });

        if (!response.ok) {
            return;
        }

        root.innerHTML = await response.text();

        if (root.classList.contains('gallery-content')) {
            const pageUrl = '/gallery/' + (folder ? '?folder=' + encodeURIComponent(folder) : '');
            window.history.replaceState({}, '', pageUrl);
        }
    }

    function folderFromResponse(response, fallback) {
        try {
            const url = new URL(response.url, window.location.origin);
            return url.searchParams.get('folder') || '';
        } catch (error) {
            return fallback;
        }
    }

    function toggleImportPanel(trigger) {
        const root = getRoot(trigger);
        if (!root) {
            return false;
        }

        const panel = root.querySelector('[data-gallery-import-panel]');
        if (!panel) {
            return false;
        }

        panel.classList.toggle('gallery-import-shown');
        if (panel.classList.contains('gallery-import-shown')) {
            const fileInput = panel.querySelector('input[type="file"]');
            if (fileInput) {
                fileInput.focus();
            }
        }
        return true;
    }

    document.addEventListener('submit', async (event) => {
        const form = event.target.closest('form[data-gallery-action]');
        if (!form || event.defaultPrevented) {
            return;
        }

        const confirmMessage = form.dataset.confirm;
        if (confirmMessage && !window.confirm(confirmMessage)) {
            event.preventDefault();
            return;
        }

        event.preventDefault();

        const root = getRoot(form);
        const currentFolder = getFolder(root);
        const submitButton = form.querySelector('button[type="submit"]');

        if (submitButton) {
            submitButton.disabled = true;
        }

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                credentials: 'same-origin'
            });

            await loadFolder(root, folderFromResponse(response, currentFolder));
        } catch (error) {
            await loadFolder(root, currentFolder);
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
            }
        }
    });

    document.addEventListener('click', (event) => {
        const importTrigger = event.target.closest('[data-gallery-import]');
        if (importTrigger) {
            event.preventDefault();
            const root = getRoot(importTrigger);
            if (root && root.classList.contains('gallery-content') && toggleImportPanel(importTrigger)) {
                return;
            }

            const url = new URL(importTrigger.dataset.importUrl, window.location.origin);
            url.searchParams.set('popup', '1');
            openPopup(url.toString());
            return;
        }

        const link = event.target.closest('a[data-gallery-folder]');
        if (!link || event.defaultPrevented || event.button !== 0) {
            return;
        }

        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }

        const root = getRoot(link);
        if (!root || !root.classList.contains('content-gallery')) {
            return;
        }

        event.preventDefault();
        loadFolder(root, link.dataset.galleryFolder || '');
    });

    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) {
            return;
        }
        if (!event.data || event.data.type !== 'gallery-imported') {
            return;
        }

        const root = document.querySelector('.gallery-content') || document.querySelector('.content-gallery');
        if (root) {
            loadFolder(root, getFolder(root));
        }
    });
})();
