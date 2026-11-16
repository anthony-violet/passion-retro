/* Mur des souvenirs : fenêtre de publication + réactions et favoris sans rechargement.
 * Tout fonctionne aussi sans JavaScript (liens et formulaires classiques). */
(function () {
    'use strict';

    function initModal() {
        var modal = document.getElementById('wm-modal');
        if (!modal || typeof modal.showModal !== 'function') return;

        document.querySelectorAll('[data-wm-open]').forEach(function (trigger) {
            trigger.addEventListener('click', function (event) {
                event.preventDefault();
                modal.showModal();
                var first = modal.querySelector('input[type="text"], textarea');
                if (first) first.focus();
            });
        });

        modal.querySelectorAll('[data-wm-close]').forEach(function (btn) {
            btn.addEventListener('click', function () { modal.close(); });
        });

        // Clic sur le fond assombri : on ferme.
        modal.addEventListener('click', function (event) {
            if (event.target === modal) modal.close();
        });
    }

    function post(form) {
        return fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        }).then(function (response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        });
    }

    function initReactions() {
        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (form.classList.contains('wm-react-form')) {
                event.preventDefault();
                var button = form.querySelector('.wm-react');
                button.disabled = true;
                post(form).then(function (data) {
                    // Le même souvenir peut apparaître deux fois (souvenir du jour + grille).
                    var memory = form.closest('.wm-reactions').dataset.memory;
                    var type = form.querySelector('input[name="type"]').value;
                    document.querySelectorAll('.wm-reactions[data-memory="' + memory + '"] .wm-react-form').forEach(function (f) {
                        if (f.querySelector('input[name="type"]').value !== type) return;
                        var b = f.querySelector('.wm-react');
                        b.classList.toggle('is-active', data.active);
                        b.setAttribute('aria-pressed', data.active ? 'true' : 'false');
                        b.querySelector('.wm-react__count').textContent = data.count;
                        if (data.active) {
                            b.classList.remove('wm-pop');
                            void b.offsetWidth;
                            b.classList.add('wm-pop');
                        }
                    });
                }).catch(function () {
                    form.submit();
                }).finally(function () {
                    button.disabled = false;
                });
            } else if (form.classList.contains('wm-fav-form')) {
                event.preventDefault();
                post(form).then(function (data) {
                    var memory = form.closest('.wm-reactions').dataset.memory;
                    document.querySelectorAll('.wm-reactions[data-memory="' + memory + '"] .wm-fav').forEach(function (b) {
                        b.classList.toggle('is-active', data.active);
                        b.setAttribute('aria-pressed', data.active ? 'true' : 'false');
                        b.title = data.active ? 'Retirer de mes favoris' : 'Garder dans mes favoris';
                        var label = b.querySelector('.wm-fav__label');
                        if (label) label.textContent = data.active ? 'Dans mes favoris' : 'Favori';
                    });
                }).catch(function () {
                    form.submit();
                });
            }
        });
    }

    /* Mosaïque : chaque carte s'étend sur autant de rangées de 4px que sa hauteur
     * l'exige. L'ordre reste de gauche à droite et il n'y a plus de trous. */
    var ROW = 4;

    function initMasonry() {
        if (typeof ResizeObserver !== 'function') return;

        document.querySelectorAll('.wm-grid[data-wm-masonry]').forEach(function (grid) {
            // L'écart vertical voulu par le thème, lu avant de passer en mosaïque.
            var gap = parseFloat(getComputedStyle(grid).rowGap) || 0;
            grid.classList.add('is-masonry');

            // Avec align-items: start, la hauteur d'une carte ne dépend pas de son
            // nombre de rangées : pas de boucle avec le ResizeObserver.
            function place(item) {
                var height = item.offsetHeight;
                item.style.gridRowEnd = 'span ' + Math.max(1, Math.ceil((height + gap) / ROW));
            }

            var observer = new ResizeObserver(function (entries) {
                entries.forEach(function (entry) { place(entry.target); });
            });
            Array.prototype.forEach.call(grid.children, function (item) {
                place(item);
                observer.observe(item);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initModal();
        initReactions();
        initMasonry();
    });
})();
