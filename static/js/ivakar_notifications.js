/* Ivakar : notifications en popup (à fermer) ou en toast (éphémère).
   Les messages de confirmation et d'erreur du site deviennent aussi des toasts sur les pages du jeu. */
(function () {
    var toasts = document.querySelector('[data-ivk-toasts]');
    var popup = document.querySelector('[data-ivk-popup]');
    if (!toasts || !popup) return;

    // --- Toasts -------------------------------------------------------------
    function toast(options) {
        var el = document.createElement(options.url ? 'a' : 'div');
        el.className = 'ivk-toast ivk-toast--' + (options.level || 'info');
        if (options.url) el.href = options.url;
        var icon = document.createElement('span');
        icon.className = 'ivk-toast__icon';
        icon.textContent = options.icon || (options.level === 'error' ? '⚠️' : options.level === 'success' ? '✅' : 'ℹ️');
        var text = document.createElement('span');
        text.className = 'ivk-toast__text';
        var title = document.createElement('strong');
        title.textContent = options.title;
        text.append(title);
        if (options.body) {
            var body = document.createElement('span');
            body.textContent = options.body;
            text.append(body);
        }
        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'ivk-toast__close';
        close.setAttribute('aria-label', 'Fermer');
        close.textContent = '×';
        close.addEventListener('click', function (event) { event.preventDefault(); hide(); });
        el.append(icon, text, close);
        toasts.append(el);
        requestAnimationFrame(function () { el.classList.add('is-visible'); });
        var timer = setTimeout(hide, options.level === 'error' ? 9000 : 6000);
        el.addEventListener('mouseenter', function () { clearTimeout(timer); });
        el.addEventListener('mouseleave', function () { timer = setTimeout(hide, 3000); });
        function hide() {
            clearTimeout(timer);
            el.classList.remove('is-visible');
            setTimeout(function () { el.remove(); }, 300);
        }
    }

    // Messages Django (« Échange conclu ! », erreurs…) -> toasts, sans repousser la page vers le bas.
    document.querySelectorAll('.notification .messages').forEach(function (list) {
        list.querySelectorAll('li').forEach(function (li) {
            var level = /error/.test(li.className) ? 'error' : /success/.test(li.className) ? 'success' : 'info';
            toast({title: li.textContent.trim(), level: level});
        });
        var box = list.closest('.notification');
        if (box) box.hidden = true;
    });

    // --- Popups (une à la fois, file d'attente) -------------------------------
    var config = document.querySelector('[data-ivk-notifications]');
    if (!config) return;
    var queue = [], shown = {}, current = null;

    function dismiss(id) {
        var body = new FormData();
        body.append('csrfmiddlewaretoken', config.dataset.csrf);
        return fetch(config.dataset.dismiss.replace(/0\/vu$/, id + '/vu'),
                     {method: 'POST', body: body, credentials: 'same-origin'}).catch(function () {});
    }
    function next() {
        if (current || !queue.length) return;
        current = queue.shift();
        popup.querySelector('[data-icon]').textContent = current.icon || '🔔';
        popup.querySelector('[data-title]').textContent = current.title;
        popup.querySelector('[data-body]').textContent = current.body || '';
        var go = popup.querySelector('[data-go]');
        go.hidden = !current.url;
        go.href = current.url || '#';
        if (typeof popup.showModal === 'function') popup.showModal(); else popup.setAttribute('open', '');
    }
    function closePopup() {
        if (!current) return;
        dismiss(current.id);
        current = null;
        if (popup.open) popup.close(); else popup.removeAttribute('open');
        next();
    }
    popup.querySelector('[data-close]').addEventListener('click', closePopup);
    popup.addEventListener('cancel', function (event) { event.preventDefault(); closePopup(); });
    popup.querySelector('[data-go]').addEventListener('click', function (event) {
        if (!current) return;
        event.preventDefault();
        var url = current.url;
        dismiss(current.id).then(function () { location.href = url; });
    });

    var delay = 10000;
    function poll() {
        if (document.hidden) { setTimeout(poll, delay); return; }
        fetch(config.dataset.feed, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
            .then(function (r) {
                var type = r.headers.get('content-type') || '';
                return r.ok && type.indexOf('json') !== -1 ? r.json() : null;
            })
            .then(function (data) {
                if (!data) return;
                if (data.poll) delay = data.poll * 1000;
                data.notifications.forEach(function (n) {
                    if (shown[n.id]) return;
                    shown[n.id] = true;
                    // Les pages peuvent réagir (ex. la liste des duels se met à jour).
                    document.dispatchEvent(new CustomEvent('ivakar:notification', {detail: n}));
                    if (n.style === 'popup') queue.push(n);
                    else toast({title: n.title, body: n.body, url: n.url, icon: n.icon});
                });
                next();
            })
            .catch(function () {})
            .finally(function () { setTimeout(poll, delay); });
    }
    poll();
})();
