// Bouton « Collection » des éditeurs BBCode : liste les objets de collection
// du membre et insère [objet]ID[/objet] dans le message.
(function () {
    const URL = '/shop/inventaire/ma-collection.json';
    let panel = null;

    function close() {
        if (panel) { panel.remove(); panel = null; }
        document.removeEventListener('click', onOutside, true);
        document.removeEventListener('keydown', onKey);
    }
    function onOutside(event) { if (panel && !panel.contains(event.target)) close(); }
    function onKey(event) { if (event.key === 'Escape') close(); }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text) node.textContent = text;
        return node;
    }

    window.openCollectionPicker = function (button, onPick) {
        if (panel) { close(); return; }
        panel = el('div', 'collection-picker');
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Afficher un objet de ma collection');
        panel.appendChild(el('p', 'collection-picker__title', 'Afficher un objet de ma collection'));
        const body = el('div', 'collection-picker__body', 'Chargement…');
        panel.appendChild(body);
        document.body.appendChild(panel);

        const rect = button.getBoundingClientRect();
        const left = Math.min(rect.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - 296);
        panel.style.top = (rect.bottom + window.scrollY + 6) + 'px';
        panel.style.left = Math.max(8, left) + 'px';
        setTimeout(() => {
            document.addEventListener('click', onOutside, true);
            document.addEventListener('keydown', onKey);
        });

        fetch(URL, { credentials: 'same-origin' })
            .then((response) => response.json())
            .then((data) => {
                body.textContent = '';
                if (data.login_required) {
                    body.textContent = 'Connecte-toi pour afficher tes objets de collection.';
                    return;
                }
                if (!data.items.length) {
                    body.appendChild(el('span', '', "Tu n'as pas encore d'objet de collection. "));
                    const link = el('a', '', 'Voir la boutique');
                    link.href = '/shop/';
                    body.appendChild(link);
                    return;
                }
                data.items.forEach((item) => {
                    const choice = el('button', 'collection-picker__item');
                    choice.type = 'button';
                    if (item.image) {
                        const img = el('img');
                        img.src = item.image;
                        img.alt = '';
                        choice.appendChild(img);
                    } else {
                        choice.appendChild(el('span', 'collection-picker__icon', '💎'));
                    }
                    const label = el('span', 'collection-picker__label');
                    label.appendChild(el('strong', '', item.name));
                    label.appendChild(el('small', '', item.rarity));
                    choice.appendChild(label);
                    choice.addEventListener('click', () => {
                        onPick('[objet]' + item.id + '[/objet]');
                        close();
                    });
                    body.appendChild(choice);
                });
            })
            .catch(() => { body.textContent = 'Impossible de charger ta collection.'; });
    };
})();
