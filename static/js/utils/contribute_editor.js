// Formulaire de contribution : éditeur BBCode, aperçu rendu par le serveur,
// gestion des chapitres d'un dossier et sauvegarde automatique du brouillon.
(function () {
    const form = document.getElementById('contrib-form');
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrfToken = csrfInput ? csrfInput.value : '';

    // ---------- Éditeur ----------
    function wrapSelection(textarea, open, close) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const value = textarea.value;
        const selected = value.slice(start, end);
        textarea.value = value.slice(0, start) + open + selected + close + value.slice(end);
        const cursor = selected ? start + open.length + selected.length + close.length : start + open.length;
        textarea.focus();
        textarea.setSelectionRange(selected ? cursor : cursor, cursor);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function countWords(text) {
        const words = text.replace(/\[[^\]]*\]/g, ' ').trim().split(/\s+/).filter(Boolean).length;
        return words + (words > 1 ? ' mots' : ' mot');
    }

    function setupEditor(editor) {
        if (editor.dataset.ready) return;
        editor.dataset.ready = '1';
        const textarea = editor.querySelector('[data-editor-input]');
        const preview = editor.querySelector('[data-editor-preview]');
        const counter = editor.querySelector('[data-editor-count]');
        const toolbar = editor.querySelector('.contrib-toolbar');
        const tabs = editor.querySelectorAll('.contrib-tab');

        const updateCount = () => { counter.textContent = countWords(textarea.value); };
        textarea.addEventListener('input', updateCount);
        updateCount();

        toolbar.addEventListener('click', (event) => {
            const button = event.target.closest('button');
            if (!button) return;
            if (button.dataset.open) {
                wrapSelection(textarea, button.dataset.open, button.dataset.close || '');
            } else if (button.dataset.insert === 'image') {
                const url = window.prompt("Adresse de l'image (tu peux la copier depuis ta galerie) :");
                if (url) wrapSelection(textarea, '[img]' + url.trim() + '[/img]', '');
            } else if (button.dataset.insert === 'link') {
                const url = window.prompt('Adresse du lien :', 'https://');
                if (url && url !== 'https://') wrapSelection(textarea, '[url=' + url.trim() + ']', '[/url]');
            }
        });

        function showTab(name) {
            tabs.forEach((tab) => {
                const active = tab.dataset.tab === name;
                tab.classList.toggle('is-active', active);
                tab.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            const isPreview = name === 'preview';
            textarea.hidden = isPreview;
            toolbar.classList.toggle('is-disabled', isPreview);
            preview.hidden = !isPreview;
            if (isPreview) renderPreview();
            else textarea.focus();
        }

        function renderPreview() {
            if (!textarea.value.trim()) {
                preview.innerHTML = '<p class="contrib-help">Rien à afficher pour l\'instant.</p>';
                return;
            }
            preview.innerHTML = '<p class="contrib-help">Chargement de l\'aperçu…</p>';
            const body = new FormData();
            body.append('content', textarea.value);
            fetch(editor.dataset.previewUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: body,
                credentials: 'same-origin',
            })
                .then((response) => {
                    if (!response.ok) throw new Error(response.status);
                    return response.json();
                })
                .then((data) => {
                    preview.innerHTML = data.html;
                    if (window.Prism) window.Prism.highlightAllUnder(preview);
                })
                .catch(() => {
                    preview.innerHTML = '<p class="contrib-error">Impossible de charger l\'aperçu. Réessaie dans un instant.</p>';
                });
        }

        tabs.forEach((tab) => tab.addEventListener('click', () => showTab(tab.dataset.tab)));
    }

    // Les éditeurs peuvent aussi être utilisés hors du formulaire de contribution
    // (ex. motif de refus dans le bandeau de relecture).
    document.querySelectorAll('[data-editor]').forEach(setupEditor);
    if (!form) return;

    // ---------- Format & chapitres ----------
    const chaptersSection = document.getElementById('contrib-chapters');
    const chapterList = document.getElementById('contrib-chapter-list');
    const chapterTemplate = document.getElementById('contrib-chapter-template');
    const addChapterButton = document.getElementById('contrib-add-chapter');

    function renumberChapters() {
        if (!chapterList) return;
        chapterList.querySelectorAll('[data-chapter]').forEach((chapter, index) => {
            chapter.querySelector('[data-chapter-number]').textContent = index + 1;
        });
    }

    function addChapter(values) {
        const fragment = chapterTemplate.content.cloneNode(true);
        const chapter = fragment.querySelector('[data-chapter]');
        if (values) {
            chapter.querySelector('[name=chapter_title]').value = values.title || '';
            chapter.querySelector('[name=chapter_content]').value = values.content || '';
        }
        chapterList.appendChild(fragment);
        const added = chapterList.lastElementChild;
        setupEditor(added.querySelector('[data-editor]'));
        renumberChapters();
        return added;
    }

    function isDossier() {
        const checked = form.querySelector('input[name=format]:checked');
        return checked && checked.value === 'dossier';
    }

    function applyFormat() {
        if (!chaptersSection) return;
        const dossier = isDossier();
        chaptersSection.hidden = !dossier;
        form.querySelectorAll('[data-label-solo]').forEach((el) => { el.hidden = dossier; });
        form.querySelectorAll('[data-label-dossier]').forEach((el) => { el.hidden = !dossier; });
        if (dossier && chapterList && !chapterList.querySelector('[data-chapter]')) addChapter();
    }

    if (chaptersSection) {
        form.querySelectorAll('input[name=format]').forEach((radio) => radio.addEventListener('change', applyFormat));
        addChapterButton.addEventListener('click', () => {
            const chapter = addChapter();
            chapter.querySelector('[name=chapter_title]').focus();
            saveDraft();
        });
        chapterList.addEventListener('click', (event) => {
            const button = event.target.closest('[data-chapter-remove]');
            if (!button) return;
            const chapter = button.closest('[data-chapter]');
            const hasContent = chapter.querySelector('[name=chapter_title]').value.trim()
                || chapter.querySelector('[name=chapter_content]').value.trim();
            if (hasContent && !window.confirm('Retirer ce chapitre ? Son contenu sera perdu.')) return;
            chapter.remove();
            renumberChapters();
            saveDraft();
        });
        renumberChapters();
        applyFormat();
    }

    // ---------- Brouillon local ----------
    const draftKey = form.dataset.draftKey;
    const draftNotice = document.getElementById('contrib-draft-notice');
    let dirty = false;

    function collectDraft() {
        const format = form.querySelector('input[name=format]:checked');
        const category = form.querySelector('[name=category]');
        return {
            category: category ? category.value : '',
            format: format ? format.value : 'solo',
            title: form.querySelector('[name=title]').value,
            content: form.querySelector('[name=content]').value,
            chapters: chapterList ? Array.from(chapterList.querySelectorAll('[data-chapter]')).map((chapter) => ({
                title: chapter.querySelector('[name=chapter_title]').value,
                content: chapter.querySelector('[name=chapter_content]').value,
            })) : [],
        };
    }

    function saveDraft() {
        if (!draftKey) return;
        try { localStorage.setItem(draftKey, JSON.stringify(collectDraft())); } catch (e) { /* stockage indisponible */ }
    }

    function clearDraft() {
        if (!draftKey) return;
        try { localStorage.removeItem(draftKey); } catch (e) { /* stockage indisponible */ }
    }

    function restoreDraft() {
        if (!draftKey) return;
        // Ne rien écraser si le serveur a renvoyé le formulaire avec des données.
        if (form.querySelector('[name=title]').value || form.querySelector('[name=content]').value) return;
        let draft = null;
        try { draft = JSON.parse(localStorage.getItem(draftKey) || 'null'); } catch (e) { draft = null; }
        if (!draft || !(draft.title || draft.content || (draft.chapters || []).some((c) => c.title || c.content))) return;

        const category = form.querySelector('[name=category]');
        if (category && draft.category && !category.value) category.value = draft.category;
        form.querySelector('[name=title]').value = draft.title || '';
        form.querySelector('[name=content]').value = draft.content || '';
        const formatRadio = form.querySelector('input[name=format][value="' + draft.format + '"]');
        if (formatRadio) formatRadio.checked = true;
        if (chapterList) {
            chapterList.innerHTML = '';
            (draft.chapters || []).forEach((chapter) => addChapter(chapter));
            applyFormat();
        }
        form.querySelectorAll('[data-editor-input]').forEach((textarea) => textarea.dispatchEvent(new Event('input')));
        draftNotice.hidden = false;
    }

    if (draftNotice) {
        document.getElementById('contrib-draft-clear').addEventListener('click', () => {
            clearDraft();
            dirty = false;
            window.location.reload();
        });
    }

    restoreDraft();

    let saveTimer = null;
    form.addEventListener('input', () => {
        dirty = true;
        clearTimeout(saveTimer);
        saveTimer = setTimeout(saveDraft, 400);
    });
    form.addEventListener('change', saveDraft);

    // ---------- Envoi ----------
    form.addEventListener('submit', (event) => {
        const savingDraft = event.submitter && event.submitter.value === 'draft';
        form.querySelectorAll('.is-invalid').forEach((el) => el.classList.remove('is-invalid'));
        const errors = [];
        if (savingDraft) {
            // Un brouillon n'exige que le titre.
            const draftTitle = form.querySelector('[name=title]');
            if (!draftTitle.value.trim()) {
                event.preventDefault();
                draftTitle.classList.add('is-invalid');
                draftTitle.focus();
                draftTitle.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            if (chaptersSection && !isDossier()) chapterList.innerHTML = '';
            dirty = false;
            clearDraft();
            return;
        }
        const category = form.querySelector('[name=category]');
        if (category && !category.value) errors.push(category);
        const title = form.querySelector('[name=title]');
        const content = form.querySelector('[name=content]');
        if (!title.value.trim()) errors.push(title);
        if (!content.value.trim()) errors.push(content);
        if (isDossier() && chapterList) {
            chapterList.querySelectorAll('[data-chapter]').forEach((chapter) => {
                const chapterTitle = chapter.querySelector('[name=chapter_title]');
                const chapterContent = chapter.querySelector('[name=chapter_content]');
                const filled = chapterTitle.value.trim() || chapterContent.value.trim();
                if (filled && !chapterTitle.value.trim()) errors.push(chapterTitle);
                if (filled && !chapterContent.value.trim()) errors.push(chapterContent);
            });
        }
        if (errors.length) {
            event.preventDefault();
            errors.forEach((el) => el.classList.add('is-invalid'));
            const first = errors[0];
            const editor = first.closest('[data-editor]');
            if (editor && first.hidden) editor.querySelector('[data-tab=write]').click();
            first.focus();
            first.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
        // Les chapitres masqués (format « Article seul ») ne doivent pas être envoyés.
        if (chaptersSection && !isDossier()) chapterList.innerHTML = '';
        dirty = false;
        clearDraft();
    });

    window.addEventListener('beforeunload', (event) => {
        if (!dirty) return;
        event.preventDefault();
        event.returnValue = '';
    });
})();
