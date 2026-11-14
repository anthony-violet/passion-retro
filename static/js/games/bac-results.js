document.addEventListener('DOMContentLoaded', () => {
    const players = document.querySelector('#playersList');
    const gameId = document.querySelector(".container").dataset.gameId;

    const fetchPlayersList = async () => {
        try {
            const response = await fetch(`/games/api/bac/${gameId}/players`);
            const data = await response.json();

            // Met à jour la liste des joueurs
            players.innerHTML = "";
            data.players.forEach(player => {
                const listItem = document.createElement("li");
                const badge = createLevelBadge(player.level, player.level_title);
                if (badge) {
                    listItem.appendChild(badge);
                }
                const status = player.status === "playing" ? 'En train de jouer...' : 'A fini de jouer';
                listItem.appendChild(document.createTextNode(` ${player.username} (${status})`));
                players.appendChild(listItem);
            });
        } catch (error) {
            console.error("Erreur lors de la récupération des joueurs :", error);
        }
    };

    fetchPlayersList();
});