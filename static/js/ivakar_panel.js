/*
 * Panel Ivakar : listes déroulantes avec recherche, création et modification en fenêtre
 * depuis n'importe quelle liste, liens qui s'ouvrent en fenêtre.
 *
 * - Toute <select> de plus de SEARCH_MIN options devient une liste avec recherche
 *   (la <select> d'origine reste dans le formulaire, cachée, et porte la valeur).
 * - Une <select> qui porte data-ivk-create-url / data-ivk-edit-url reçoit les boutons ＋ et ✎ :
 *   le formulaire s'ouvre dans une fenêtre ; à l'enregistrement, l'élément est ajouté ou renommé
 *   dans toutes les listes du même type et sélectionné dans la liste d'où l'on vient.
 * - Un lien a[data-ivk-popup] s'ouvre en fenêtre ; avec data-ivk-reload, la page se recharge ensuite.
 * - Le contexte de la page (data-ivk-context sur le formulaire ou la page) pré-remplit les créations.
 */
(function () {
    'use strict';

    var SEARCH_MIN = 8;

    function fold(text) {
        return (text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    }

    // ------------------------------------------------------------------
    // Listes avec recherche
    // ------------------------------------------------------------------
    function enhance(select) {
        if (select.dataset.ivkCombo || select.multiple || select.closest('template')) return;
        if (select.options.length <= SEARCH_MIN && !select.dataset.ivkCreateUrl) return;
        select.dataset.ivkCombo = '1';

        var box = document.createElement('div');
        box.className = 'ivk-combo';
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'ivk-combo__input';
        input.autocomplete = 'off';
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-label', select.getAttribute('aria-label') || labelFor(select) || 'Choisir');
        var list = document.createElement('ul');
        list.className = 'ivk-combo__list';
        list.setAttribute('role', 'listbox');
        list.hidden = true;

        select.parentNode.insertBefore(box, select);
        box.appendChild(input);
        box.appendChild(list);
        box.appendChild(select);
        select.classList.add('ivk-combo__native');
        select.tabIndex = -1;
        if (select.id) {
            input.id = select.id + '__search';
            var label = document.querySelector('label[for="' + select.id + '"]');
            if (label) label.htmlFor = input.id;
        }

        var active = -1;

        function current() {
            var option = select.options[select.selectedIndex];
            return option && option.value ? option.text : '';
        }

        function render(filter) {
            list.innerHTML = '';
            var needle = fold(filter);
            var count = 0;
            Array.prototype.forEach.call(select.options, function (option, index) {
                if (needle && fold(option.text).indexOf(needle) === -1) return;
                var item = document.createElement('li');
                item.setAttribute('role', 'option');
                item.dataset.index = index;
                item.textContent = option.text || '— aucun —';
                if (!option.value) item.classList.add('is-empty');
                if (index === select.selectedIndex) item.setAttribute('aria-selected', 'true');
                list.appendChild(item);
                count += 1;
            });
            if (!count) {
                var none = document.createElement('li');
                none.className = 'is-none';
                none.textContent = 'Aucun résultat';
                list.appendChild(none);
            }
            active = -1;
        }

        function open() {
            render(input.value === current() ? '' : input.value);
            list.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        function close() {
            list.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            input.value = current();
        }

        function pick(index) {
            select.selectedIndex = index;
            select.dispatchEvent(new Event('change', {bubbles: true}));
            close();
        }

        function highlight(step) {
            var items = list.querySelectorAll('li[data-index]');
            if (!items.length) return;
            active = (active + step + items.length) % items.length;
            items.forEach(function (li, i) { li.classList.toggle('is-active', i === active); });
            items[active].scrollIntoView({block: 'nearest'});
        }

        input.value = current();
        input.addEventListener('focus', function () { input.select(); open(); });
        input.addEventListener('input', function () {
            render(input.value);
            list.hidden = false;
        });
        input.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowDown') { event.preventDefault(); if (list.hidden) open(); highlight(1); }
            else if (event.key === 'ArrowUp') { event.preventDefault(); highlight(-1); }
            else if (event.key === 'Enter') {
                var chosen = list.querySelectorAll('li[data-index]')[active < 0 ? 0 : active];
                if (!list.hidden && chosen) { event.preventDefault(); pick(parseInt(chosen.dataset.index, 10)); }
            } else if (event.key === 'Escape') { close(); }
        });
        input.addEventListener('blur', function () { setTimeout(close, 150); });
        list.addEventListener('mousedown', function (event) {
            var item = event.target.closest('li[data-index]');
            if (item) { event.preventDefault(); pick(parseInt(item.dataset.index, 10)); }
        });
        select.addEventListener('change', function () { input.value = current(); });
        select.ivkRefresh = function () { input.value = current(); };
    }

    function labelFor(select) {
        var label = select.id && document.querySelector('label[for="' + select.id + '"]');
        if (label) return label.textContent.replace('*', '').trim();
        var cell = select.closest('td');
        if (cell) {
            var table = cell.closest('table');
            var header = table && table.querySelectorAll('thead th')[cell.cellIndex];
            if (header) return header.textContent.trim();
        }
        return '';
    }

    // ------------------------------------------------------------------
    // Fenêtre (formulaire du panel dans un cadre)
    // ------------------------------------------------------------------
    var dialog, frame, pending = null;

    function ensureDialog() {
        if (dialog) return;
        dialog = document.createElement('dialog');
        dialog.className = 'ivk-modal';
        dialog.innerHTML = '<div class="ivk-modal__bar"><strong class="ivk-modal__title"></strong>' +
            '<button type="button" class="btn btn-small" data-close>Fermer</button></div>' +
            '<iframe class="ivk-modal__frame" title="Formulaire"></iframe>';
        document.body.appendChild(dialog);
        frame = dialog.querySelector('iframe');
        dialog.querySelector('[data-close]').addEventListener('click', function () { dialog.close(); });
        dialog.addEventListener('close', function () { frame.src = 'about:blank'; pending = null; });
    }

    function context(element) {
        var holder = element.closest('[data-ivk-context]') || document.querySelector('[data-ivk-context]');
        if (!holder) return {};
        try { return JSON.parse(holder.dataset.ivkContext) || {}; } catch (e) { return {}; }
    }

    function withParams(url, params) {
        var query = new URLSearchParams({popup: '1'});
        Object.keys(params || {}).forEach(function (key) {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') query.append(key, params[key]);
        });
        return url + (url.indexOf('?') === -1 ? '?' : '&') + query.toString();
    }

    function openModal(url, title, onSaved) {
        ensureDialog();
        pending = onSaved;
        dialog.querySelector('.ivk-modal__title').textContent = title || '';
        frame.src = url;
        if (!dialog.open) dialog.showModal();
    }

    window.addEventListener('message', function (event) {
        if (event.origin !== window.location.origin || !event.data || event.data.type !== 'ivakar-saved') return;
        var callback = pending;
        if (dialog && dialog.open) dialog.close();
        if (callback) callback(event.data);
    });

    // ------------------------------------------------------------------
    // Boutons ＋ / ✎ à côté des listes reliées à une autre rubrique
    // ------------------------------------------------------------------
    function addRelatedButtons(select) {
        if (select.dataset.ivkRelatedReady || !select.dataset.ivkCreateUrl || select.closest('template')) return;
        select.dataset.ivkRelatedReady = '1';
        var anchor = select.closest('.ivk-combo') || select;
        var tools = document.createElement('span');
        tools.className = 'ivk-related';
        tools.innerHTML = '<button type="button" class="ivk-related__btn" data-create title="Créer">＋</button>' +
            '<button type="button" class="ivk-related__btn" data-edit title="Modifier l\'élément choisi">✎</button>';
        anchor.insertAdjacentElement('afterend', tools);
        var edit = tools.querySelector('[data-edit]');

        function sync() { edit.disabled = !select.value; }
        select.addEventListener('change', sync);
        sync();

        function saved(data) {
            document.querySelectorAll('select[data-ivk-related="' + data.section + '"]').forEach(function (other) {
                var option = Array.prototype.find.call(other.options, function (o) { return o.value === String(data.id); });
                if (!option) {
                    option = new Option(data.label, data.id);
                    other.add(option);
                } else {
                    option.text = data.label;
                }
                if (other.ivkRefresh) other.ivkRefresh();
            });
            select.value = String(data.id);
            select.dispatchEvent(new Event('change', {bubbles: true}));
        }

        tools.querySelector('[data-create]').addEventListener('click', function () {
            openModal(withParams(select.dataset.ivkCreateUrl, context(select)),
                'Créer : ' + (select.dataset.ivkSingular || labelFor(select)), saved);
        });
        edit.addEventListener('click', function () {
            if (!select.value) return;
            var url = select.dataset.ivkEditUrl.replace('/0/', '/' + select.value + '/');
            openModal(withParams(url, {}), 'Modifier : ' + select.options[select.selectedIndex].text, saved);
        });
    }

    // ------------------------------------------------------------------
    // Liens en fenêtre
    // ------------------------------------------------------------------
    document.addEventListener('click', function (event) {
        var link = event.target.closest('a[data-ivk-popup]');
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey) return;
        event.preventDefault();
        openModal(withParams(link.getAttribute('href'), {}), link.dataset.ivkPopup || link.textContent.trim(), function () {
            if (link.hasAttribute('data-ivk-reload')) window.location.reload();
        });
    });

    // ------------------------------------------------------------------
    // Mise en place (et pour les lignes ajoutées plus tard)
    // ------------------------------------------------------------------
    function setup(root) {
        var selects = root.matches && root.matches('select') ? [root] : root.querySelectorAll('select');
        Array.prototype.forEach.call(selects, function (select) {
            enhance(select);
            addRelatedButtons(select);
        });
    }

    window.IvakarPanel = {setup: setup, open: openModal};
    document.addEventListener('DOMContentLoaded', function () {
        setup(document);
        new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                m.addedNodes.forEach(function (node) { if (node.nodeType === 1) setup(node); });
            });
        }).observe(document.body, {childList: true, subtree: true});
    });
})();
