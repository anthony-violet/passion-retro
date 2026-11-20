"""Succès et tâches quotidiennes fournis par défaut (modifiables ensuite dans le panel).

Chargés par la migration 0009 (pour qu'ils existent partout) et par ``load_ivakar``.
"""

ACHIEVEMENTS = [
    # slug, nom, description, icône, compteur, objectif, marqueur, secret, xp, écus
    ('premier-sang', "Premier sang", "Remporter un premier combat.", "🗡️", 'victories', 1, '', False, 10, 0),
    ('chasseur', "Chasseur", "Remporter 25 combats.", "🐺", 'victories', 25, '', False, 50, 20),
    ('fleau-des-brumes', "Fléau des brumes", "Remporter 100 combats.", "⚔️", 'victories', 100, '', False, 150, 60),
    ('fouineur', "Fouineur", "Explorer 50 fois.", "🔦", 'explorations', 50, '', False, 30, 10),
    ('explorateur', "Explorateur", "Découvrir 3 lieux.", "🧭", 'locations', 3, '', False, 20, 0),
    ('cartographe', "Cartographe", "Découvrir 6 lieux.", "🗺️", 'locations', 6, '', False, 60, 20),
    ('grand-voyageur', "Grand voyageur", "Voyager 50 fois d'un lieu à l'autre.", "🥾", 'travels', 50, '', False, 40, 10),
    ('premier-service', "Premier service", "Accomplir une quête.", "📖", 'quests', 1, '', False, 15, 0),
    ('tombeur-du-roi', "Tombeur du Roi-Brume", "Vaincre le Roi-Brume.", "👑", 'flag', 1, 'roi_vaincu', True, 100, 50),
    ('heros-confirme', "Héros confirmé", "Atteindre le niveau 5.", "⭐", 'level', 5, '', False, 0, 30),
    ('veteran', "Vétéran d'Ivakar", "Atteindre le niveau 10.", "🌟", 'level', 10, '', False, 0, 80),
    ('duelliste', "Duelliste", "Gagner un duel.", "🤺", 'duels_won', 1, '', False, 10, 10),
    ('maitre-d-armes', "Maître d'armes", "Gagner 10 duels.", "🥇", 'duels_won', 10, '', False, 50, 40),
    ('marchand', "Bon marchand", "Conclure 5 échanges avec d'autres héros.", "🤝", 'trades', 5, '', False, 20, 20),
    ('visage-connu', "Visage connu", "Faire la connaissance de 2 habitants des plaines.", "🗣️", 'npcs', 2, '', False,
     15, 5),
    ('pilier-de-taverne', "Pilier de taverne", "Écrire 20 messages à la taverne.", "🍺", 'tavern', 20, '', False, 10, 10),
    ('rempart', "Rempart d'Agasur", "Lancer 10 assauts contre des menaces de serveur.", "🌍", 'event_attacks', 10, '',
     False, 40, 20),
    ('assidu', "Assidu", "Accomplir 10 tâches quotidiennes.", "✅", 'daily_done', 10, '', False, 0, 30),
    ('increvable', "Increvable", "Tomber cinq fois… et se relever cinq fois.", "💫", 'knockouts', 5, '', True, 20, 0),
]

DAILY_TASKS = [
    # slug, nom, compteur, objectif, xp, écus, niveau minimum, poids
    ('chasse-du-jour', "Chasser 3 monstres", 'victories', 3, 15, 8, 1, 3),
    ('ronde-du-jour', "Explorer 5 fois", 'explorations', 5, 10, 6, 1, 3),
    ('route-du-jour', "Voyager 4 fois", 'travels', 4, 10, 6, 1, 2),
    ('histoires-du-jour', "Faire 3 choix dans des scènes", 'choices', 3, 12, 6, 1, 2),
    ('taverne-du-jour', "Dire un mot à la taverne", 'tavern', 1, 5, 4, 1, 1),
    ('duel-du-jour', "Livrer un duel amical", 'duels_fought', 1, 15, 8, 2, 1),
    ('grande-chasse', "Chasser 8 monstres", 'victories', 8, 35, 15, 4, 1),
]


def seed(Achievement, DailyTask, update=False):
    """Crée (ou remet à jour avec ``update``) les succès et tâches par défaut. Renvoie le nombre créé."""
    created = 0
    save = 'update_or_create' if update else 'get_or_create'
    for order, (slug, name, description, icon, metric, goal, flag, hidden, xp, coins) in enumerate(ACHIEVEMENTS):
        _, new = getattr(Achievement.objects, save)(slug=slug, defaults={
            'name': name, 'description': description, 'icon': icon, 'metric': metric, 'goal': goal, 'flag': flag,
            'hidden': hidden, 'reward_xp': xp, 'reward_coins': coins, 'order': order,
        })
        created += int(new)
    for slug, name, metric, goal, xp, coins, min_level, weight in DAILY_TASKS:
        _, new = getattr(DailyTask.objects, save)(slug=slug, defaults={
            'name': name, 'metric': metric, 'goal': goal, 'reward_xp': xp, 'reward_coins': coins,
            'min_level': min_level, 'weight': weight,
        })
        created += int(new)
    return created
