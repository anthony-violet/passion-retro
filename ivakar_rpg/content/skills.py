"""Compétences fournies par défaut, deux par origine du chapitre 1 (modifiables dans le panel).

Chargées par la migration 0011 (pour qu'elles existent partout) et par ``load_ivakar``.
"""

SKILLS = [
    # slug, nom, icône, description, type, carac du héros, contre, bonus au jet, D6 en plus, bonus fixe,
    # recharge, niveau requis, origines
    ('charge', "Charge", "🐂", "Tu te jettes sur l'adversaire de tout ton poids. Bloquée par une Garde.",
     'power', 'force', 'dexterite', 1, 1, 0, 3, 1, ['soldat-garnison']),
    ('garde-de-fer', "Garde de fer", "🛡️", "Une Garde solide : si l'adversaire charge, ta riposte frappe fort.",
     'guard', 'dexterite', 'dexterite', 2, 1, 0, 3, 3, ['soldat-garnison']),
    ('tir-vise', "Tir visé", "🎯", "Tu vises la faille : Perception contre Dextérité.",
     'strike', 'perception', 'dexterite', 1, 1, 0, 3, 1, ['eclaireur']),
    ('coup-bas', "Coup bas", "🗡️", "Une feinte sournoise qui ouvre une Garde et blesse.",
     'feint', 'dexterite', 'perception', 1, 1, 1, 3, 3, ['eclaireur']),
    ('point-faible', "Point faible", "🔍", "Tu frappes là où il faut : Intelligence contre Intelligence.",
     'strike', 'intelligence', 'intelligence', 0, 1, 1, 3, 1, ['lettre']),
    ('concentration', "Concentration", "🧘", "Tu reprends ton souffle et tes esprits : soin.",
     'heal', 'mental', 'mental', 0, 1, 2, 4, 3, ['lettre']),
    ('harangue', "Harangue", "📣", "Ta voix te redonne du cœur : soin.",
     'heal', 'charisme', 'charisme', 0, 1, 1, 4, 1, ['heraut']),
    ('cri-de-guerre', "Cri de guerre", "📯", "Une Intimidation renforcée : Charisme contre Mental, +2 au jet.",
     'shake', 'charisme', 'mental', 2, 0, 0, 3, 3, ['heraut']),
    ('coup-de-marteau', "Coup de marteau", "🔨", "Le geste de la forge, en plus lourd. Bloqué par une Garde.",
     'power', 'force', 'dexterite', 0, 1, 2, 3, 1, ['forgeron']),
    ('peau-de-cuir', "Peau de cuir", "🪖", "Une Garde endurcie : Constitution contre Dextérité.",
     'guard', 'constitution', 'dexterite', 2, 0, 1, 3, 3, ['forgeron']),
]


def seed(Skill, Origin, update=False):
    """Crée (ou remet à jour avec ``update``) les compétences par défaut. Renvoie le nombre créé."""
    created = 0
    save = 'update_or_create' if update else 'get_or_create'
    origins = {o.slug: o for o in Origin.objects.all()}
    for order, (slug, name, icon, description, kind, stat, against, roll, dice, flat, cooldown, level,
                origin_slugs) in enumerate(SKILLS):
        skill, new = getattr(Skill.objects, save)(slug=slug, defaults={
            'name': name, 'icon': icon, 'description': description, 'kind': kind, 'stat': stat, 'against': against,
            'roll_bonus': roll, 'extra_dice': dice, 'flat_bonus': flat, 'cooldown': cooldown, 'min_level': level,
            'order': order,
        })
        if new or update or not skill.origins.exists():  # origines absentes lors de la migration
            skill.origins.add(*(origins[s] for s in origin_slugs if s in origins))
        created += int(new)
    return created
