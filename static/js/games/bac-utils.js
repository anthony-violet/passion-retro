document.addEventListener('DOMContentLoaded', () => {
    const status = document.querySelector('#status');
    /* Fonction pour vérifier le statut de la partie */
    const updateStatus = () => {
        const statuses = {
            waiting: { text: 'En attente', style: 'color:orange;font-style:italic' },
            in_progress: { text: 'En cours', style: 'color:green;font-style:italic' },
            finished: { text: 'Terminée', style: 'color:red;font-style:italic' },
        };

        const currentStatus = statuses[status.textContent];
        if (currentStatus) {
            status.style = currentStatus.style;
            status.textContent = currentStatus.text;
        }
    };
    updateStatus();
})
/* Construit un badge de niveau identique à celui affiché sur le profil. */
function createLevelBadge(level, title) {
    if (!level) {
        return null;
    }

    const badge = document.createElement('span');
    badge.className = 'level-badge level-badge--inline level-badge--compact';
    const label = title ? `Niveau ${level} — ${title}` : `Niveau ${level}`;
    badge.title = label;
    badge.setAttribute('aria-label', label);

    const badgeLabel = document.createElement('span');
    badgeLabel.className = 'level-text';
    badgeLabel.textContent = 'LVL';

    const badgeNumber = document.createElement('span');
    badgeNumber.className = 'level-number';
    badgeNumber.textContent = level;

    badge.appendChild(badgeLabel);
    badge.appendChild(badgeNumber);
    return badge;
}
