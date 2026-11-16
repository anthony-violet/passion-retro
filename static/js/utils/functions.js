function openPopup(url) {
    window.open(
        url,
        'PopupWindow',
        'width=400,height=400,scrollbars=no,resizable=no'
    );
}

function copyToClipboard(event) {
    // Récupère le bouton qui a déclenché l'événement
    const button = event.target;

    // Récupère la valeur de l'attribut data-tag
    const tag = button.getAttribute('data-tag');

    // Utilise l'API Clipboard pour copier dans le presse-papiers
    navigator.clipboard.writeText(tag)
}

function modal(id, price) {
    const modal = document.querySelector('.modal');
    if (modal) {
        modal.style.display = 'block';
        const close = document.querySelector('.modal-close');
        const accept = modal.querySelector('#accept');
        accept.innerHTML = `Payer <span class="money">${price}</span>`;
        const decline = modal.querySelector('#decline');

        accept.addEventListener('click', () => {
            window.location.href = `/shop/buy/${id}`;
        });

        decline.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        close.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const burger = document.querySelector('.burger-icon');
    const menu = document.querySelector('.menu-horizontal');
    if (!burger || !menu) return;

    const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

    // Toggle burger menu
    burger.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = menu.classList.toggle('open');
        burger.setAttribute('aria-expanded', open ? 'true' : 'false');
        burger.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
    });

    // Fermer le menu au clic extérieur
    document.addEventListener('click', (e) => {
        if (menu.classList.contains('open') &&
            !menu.contains(e.target) &&
            !burger.contains(e.target)) {
            menu.classList.remove('open');
            burger.setAttribute('aria-expanded', 'false');
            burger.setAttribute('aria-label', 'Ouvrir le menu');
        }
    });

    // Fermer le menu à la touche Échap
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && menu.classList.contains('open')) {
            menu.classList.remove('open');
            burger.setAttribute('aria-expanded', 'false');
            burger.setAttribute('aria-label', 'Ouvrir le menu');
        }
    });

    // Toggle des sous‑menus au tactile (mobile uniquement)
    document.querySelectorAll('.menu-dropdown-toggle').forEach(toggle => {
        toggle.addEventListener('click', (e) => {
            if (!isMobile()) return;
            e.preventDefault();
            const li = toggle.closest('li');
            if (!li) return;

            // Fermer les autres ouverts
            li.parentElement.querySelectorAll('li.open').forEach(openLi => {
                if (openLi !== li) {
                    openLi.classList.remove('open');
                    const other = openLi.querySelector('.menu-dropdown-toggle');
                    if (other) other.setAttribute('aria-expanded', 'false');
                    const otherUl = openLi.querySelector('.dropdown');
                    if (otherUl) otherUl.style.display = 'none';
                }
            });

            // Basculer le actuel
            const isOpen = li.classList.contains('open');
            li.classList.toggle('open', !isOpen);
            toggle.setAttribute('aria-expanded', String(!isOpen));
            const ul = li.querySelector('.dropdown');
            if (ul) ul.style.display = isOpen ? 'none' : 'block';
        });
    });

    // Réinitialiser au passage en desktop
    window.matchMedia('(min-width: 769px)').addEventListener('change', (e) => {
        if (!e.matches) return;
        if (menu.classList.contains('open')) {
            menu.classList.remove('open');
            burger.setAttribute('aria-expanded', 'false');
            burger.setAttribute('aria-label', 'Ouvrir le menu');
        }
        document.querySelectorAll('.menu-dropdown-toggle').forEach(t => {
            t.setAttribute('aria-expanded', 'false');
            const ul = t.closest('li').querySelector('.dropdown');
            if (ul) ul.style.display = 'none';
        });
        document.querySelectorAll('li.open').forEach(li => li.classList.remove('open'));
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const avatars = document.querySelectorAll('.cadre-retro-gameboy');
    avatars.forEach(avatar => {
        console.log("on a trouvé l'avatar");
        const divButtons = document.createElement('div');
        const divCross = document.createElement('div');
        const divStartSelect = document.createElement('div');
        divButtons.classList.add('buttons');
        divCross.classList.add('controls');
        divStartSelect.classList.add('start-select');
        avatar.appendChild(divButtons);
        avatar.appendChild(divCross);
        avatar.appendChild(divStartSelect);
    });
});