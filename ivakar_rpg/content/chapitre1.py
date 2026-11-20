"""Scénario d'exemple — « Les Brumes de Précalm » (plaines d'Agasur).

Contenu de départ chargé par ``python manage.py load_ivakar`` : il sert à tester
le moteur, il n'est pas une campagne officielle. Rien ici n'est repris du roman
Soleris – Chroniques d'Ivakar. Les références entre objets se font par slug ;
une fois chargé, tout se modifie dans l'admin.

Fil rouge :
1. Précalm : Maela, l'aubergiste, demande qu'on abatte le loup alpha de la lisière.
2. Le croc de l'alpha convainc l'ermite Tobald (Forêt des Murmures) de révéler
   le secret des brumes : la clé runique dort au fond de la mine.
3. La clé ouvre la crypte sous les ruines de Vel-Ithar, où attend le Roi-Brume.

Tests : 2D6 + ⌊caractéristique ÷ 3⌋ contre 10 (facile), 13 (moyenne) ou 16 (difficile).
"""

ITEMS = [
    # slug, nom, type, rareté, prix, attaque, défense, pv, soin, description
    ('baton-noueux', "Bâton noueux", 'weapon', 'common', 4, 1, 0, 0, 0, "Un bâton de marche durci au feu."),
    ('epee-courte', "Épée courte", 'weapon', 'common', 25, 2, 0, 0, 0, "Forgée au bourg, simple et fiable."),
    ('hache-bucheron', "Hache de bûcheron", 'weapon', 'rare', 70, 4, 0, 0, 0, "Lourde, elle fend le bois comme les os."),
    ('epee-vel-ithar', "Lame de Vel-Ithar", 'weapon', 'legendary', 0, 7, 1, 0, 0,
     "L'épée des anciens rois. Sa lame dissipe la brume."),
    ('veste-cuir', "Veste de cuir", 'armor', 'common', 20, 0, 1, 0, 0, "Du cuir épais, cousu serré."),
    ('cotte-mailles', "Cotte de mailles", 'armor', 'rare', 80, 0, 3, 5, 0, "Des anneaux d'acier qui arrêtent les lames."),
    ('amulette-brumes', "Amulette des brumes", 'armor', 'epic', 0, 0, 2, 10, 0,
     "Offerte par les fées. Elle t'enveloppe d'un voile protecteur."),
    ('pain', "Miche de pain", 'consumable', 'common', 3, 0, 0, 0, 5, "De quoi tenir une journée de marche."),
    ('potion-soin', "Potion de soin", 'consumable', 'common', 10, 0, 0, 0, 12, "Un élixir rouge préparé par l'apothicaire."),
    ('grande-potion', "Grande potion de soin", 'consumable', 'rare', 25, 0, 0, 0, 30, "Distillée par l'apothicaire du bourg."),
    ('lanterne', "Lanterne à huile", 'misc', 'common', 30, 0, 0, 0, 0, "Indispensable pour descendre à la mine."),
    ('soie-araignee', "Soie d'araignée", 'misc', 'common', 8, 0, 0, 0, 0, "Résistante et fine, recherchée par les tisserands."),
    ('croc-alpha', "Croc de l'alpha", 'quest', 'rare', 0, 0, 0, 0, 0, "Preuve que la meute n'a plus de chef."),
    ('cle-runique', "Clé runique", 'quest', 'epic', 0, 0, 0, 0, 0, "Elle vibre doucement près des ruines."),
]

LOCATIONS = [
    {
        'slug': 'precalm', 'map_x': 250, 'map_y': 857, 'name': "Précalm", 'order': 1, 'is_start': True, 'is_safe': True,
        'has_inn': True, 'inn_price': 5, 'has_merchant': True, 'recommended_level': 1, 'calm_weight': 2,
        'description': (
            "Une petite bourgade des plaines d'Agasur, sans rempart ni garde : quelques maisons autour d'une "
            "place pavée, une forge qui fume et l'auberge du [b]Pot Cassé[/b]. Depuis que la brume est tombée "
            "sur les plaines, plus aucun voyageur n'est arrivé par la route de Haut-Chateau."
        ),
        'wares': ['epee-courte', 'hache-bucheron', 'veste-cuir', 'cotte-mailles', 'pain', 'potion-soin',
                  'grande-potion', 'lanterne'],
    },
    {
        'slug': 'lisiere', 'map_x': 400, 'map_y': 743, 'name': "La Lisière brumeuse", 'order': 2, 'recommended_level': 1, 'calm_weight': 2,
        'description': (
            "Les premiers arbres émergent du brouillard comme des sentinelles. On entend des hurlements "
            "au loin, et parfois, des rires aigus qui ne présagent rien de bon."
        ),
    },
    {
        'slug': 'foret-murmures', 'map_x': 570, 'map_y': 529, 'name': "La Forêt des Murmures", 'order': 3, 'recommended_level': 2,
        'calm_weight': 2,
        'description': (
            "Les troncs sont si serrés que la lumière peine à passer. Le vent fait chuchoter les feuilles : "
            "on jurerait entendre des noms."
        ),
    },
    {
        'slug': 'mine-abandonnee', 'map_x': 170, 'map_y': 471, 'name': "La Mine abandonnée", 'order': 4, 'recommended_level': 3,
        'calm_weight': 1,
        'description': (
            "Des rails rouillés s'enfoncent dans la montagne. L'air sent la poussière et l'huile froide. "
            "Ta lanterne dessine des ombres qui semblent bouger."
        ),
    },
    {
        'slug': 'ruines-vel-ithar', 'map_x': 760, 'map_y': 271, 'name': "Les Ruines de Vel-Ithar", 'order': 5, 'recommended_level': 4,
        'calm_weight': 2,
        'description': (
            "Les restes d'une cité royale, colonnes brisées et statues sans visage. Ici, la brume est si "
            "épaisse qu'elle semble respirer. Un escalier descend sous l'ancien palais."
        ),
    },
    {
        'slug': 'crypte-roi-brume', 'map_x': 820, 'map_y': 390, 'name': "La Crypte du Roi-Brume", 'order': 6, 'recommended_level': 5,
        'calm_weight': 0,
        'description': (
            "Un froid de tombeau. Au centre de la salle, un trône de pierre noire, et sur le trône, "
            "une silhouette faite de brume et de colère."
        ),
    },
]

# from, to, libellé, niveau requis, objet requis, marqueur requis, message si bloqué
EXITS = [
    ('precalm', 'lisiere', "Prendre le chemin de la lisière", 0, None, '', ''),
    ('lisiere', 'precalm', "Rentrer à Précalm", 0, None, '', ''),
    ('lisiere', 'foret-murmures', "S'enfoncer dans la Forêt des Murmures", 2, None, '',
     "La forêt est trop dangereuse avant le niveau 2."),
    ('lisiere', 'mine-abandonnee', "Suivre les rails vers la mine", 0, 'lanterne', '',
     "Il fait noir comme dans un four : il te faut une lanterne (en vente au bourg)."),
    ('foret-murmures', 'lisiere', "Revenir à la lisière", 0, None, '', ''),
    ('foret-murmures', 'ruines-vel-ithar', "Suivre les pierres levées vers les ruines", 0, None, 'brume_secret',
     "Les sentiers tournent en rond. Quelqu'un dans la forêt connaît peut-être le chemin."),
    ('mine-abandonnee', 'lisiere', "Remonter à l'air libre", 0, None, '', ''),
    ('ruines-vel-ithar', 'foret-murmures', "Retourner dans la forêt", 0, None, '', ''),
    ('ruines-vel-ithar', 'crypte-roi-brume', "Descendre l'escalier du palais", 0, 'cle-runique', '',
     "Une porte runique scellée bloque l'escalier. Il doit exister une clé."),
    ('crypte-roi-brume', 'ruines-vel-ithar', "Remonter vers les ruines", 0, None, '', ''),
]

# Seuils (10 facile, 13 moyen, 16 difficile) que le héros doit atteindre avec sa Dextérité.
MONSTERS = [
    # slug, nom, niveau, pv, toucher, esquiver, fuir, dégâts min, max, armure, xp, écus min, max, boss,
    # description, [(objet, %)]
    ('gobelin-chapardeur', "Gobelin chapardeur", 1, 10, 10, 10, 10, 1, 3, 0, 10, 2, 6, False,
     "Petit, vif, et ses poches tintent de pièces volées.", [('potion-soin', 20)]),
    ('loup-gris', "Loup gris", 1, 12, 10, 10, 13, 2, 4, 0, 12, 0, 2, False,
     "Le poil hérissé, les crocs découverts.", []),
    ('loup-alpha', "Loup alpha", 2, 24, 10, 13, 13, 3, 5, 1, 40, 3, 8, False,
     "Le chef de la meute. Une cicatrice blanche lui barre le museau.", []),
    ('araignee-murmures', "Araignée des murmures", 2, 18, 13, 10, 13, 2, 5, 1, 18, 0, 3, False,
     "Grande comme un chien, elle tisse en silence entre les troncs.", [('soie-araignee', 60)]),
    ('sanglier-furieux', "Sanglier furieux", 2, 26, 10, 13, 10, 3, 6, 2, 22, 0, 0, False,
     "Une masse de muscles et de défenses qui charge sans hésiter.", [('pain', 40)]),
    ('rat-geant', "Rat géant", 3, 20, 10, 13, 13, 2, 5, 1, 20, 1, 4, False,
     "Les galeries lui appartiennent depuis que les mineurs sont partis.", []),
    ('kobold-mineur', "Kobold mineur", 3, 28, 13, 13, 13, 3, 6, 2, 28, 5, 12, False,
     "Il a gardé sa pioche. Et sa rancune.", [('potion-soin', 30)]),
    ('squelette-garde', "Squelette de la garde", 4, 34, 13, 13, 13, 4, 7, 3, 35, 4, 10, False,
     "Il monte encore la garde pour un roi disparu depuis des siècles.", [('grande-potion', 15)]),
    ('spectre-brume', "Spectre de brume", 4, 30, 16, 13, 16, 4, 8, 2, 45, 6, 14, False,
     "On ne le distingue qu'en le regardant de biais.", [('grande-potion', 20)]),
    ('roi-brume', "Le Roi-Brume", 6, 80, 13, 16, 16, 6, 10, 4, 150, 60, 100, True,
     "L'ancien souverain de Vel-Ithar, qui refusa la mort et devint brouillard.", [('epee-vel-ithar', 100)]),
]

# Origines proposées à la création (valeurs de départ entre 1 et 20, total libre).
ORIGINS = [
    # slug, nom, description, {caractéristique: valeur}
    ('soldat-garnison', "Soldat de garnison", "Des années de garde aux remparts : solide, discipliné, peu bavard.",
     {'force': 15, 'constitution': 14, 'dexterite': 11, 'perception': 9, 'intelligence': 7, 'mental': 12,
      'charisme': 8}),
    ('eclaireur', "Éclaireur", "Habitué aux sentiers et aux embuscades, il voit et entend avant les autres.",
     {'force': 9, 'constitution': 10, 'dexterite': 15, 'perception': 16, 'intelligence': 9, 'mental': 10,
      'charisme': 7}),
    ('lettre', "Lettré", "Élevé parmi les livres et les cartes : il comprend vite et ne se laisse pas impressionner.",
     {'force': 6, 'constitution': 8, 'dexterite': 9, 'perception': 11, 'intelligence': 16, 'mental': 13,
      'charisme': 10}),
    ('heraut', "Héraut", "Porteur de messages entre seigneurs : sa parole ouvre les portes et apaise les colères.",
     {'force': 8, 'constitution': 9, 'dexterite': 10, 'perception': 10, 'intelligence': 11, 'mental': 12,
      'charisme': 16}),
    ('forgeron', "Forgeron", "Le marteau, l'enclume et la chaleur des forges l'ont rendu dur à la tâche.",
     {'force': 14, 'constitution': 15, 'dexterite': 12, 'perception': 8, 'intelligence': 10, 'mental': 11,
      'charisme': 7}),
]

# lieu, monstre, poids
ENCOUNTERS = [
    ('lisiere', 'loup-gris', 3), ('lisiere', 'gobelin-chapardeur', 2),
    ('foret-murmures', 'araignee-murmures', 3), ('foret-murmures', 'sanglier-furieux', 2),
    ('foret-murmures', 'loup-gris', 1),
    ('mine-abandonnee', 'rat-geant', 3), ('mine-abandonnee', 'kobold-mineur', 2),
    ('ruines-vel-ithar', 'squelette-garde', 3), ('ruines-vel-ithar', 'spectre-brume', 2),
]

QUESTS = [
    {'slug': 'loups-lisiere', 'title': "Les loups de la lisière", 'order': 1, 'reward_xp': 50, 'reward_coins': 30,
     'summary': "Maela, l'aubergiste du Pot Cassé, n'en peut plus : les loups rôdent jusqu'aux palissades.",
     'objective': "Trouve la tanière des loups à la lisière et règle son compte à l'alpha."},
    {'slug': 'secret-brumes', 'title': "Le secret des brumes", 'order': 2, 'reward_xp': 80, 'reward_coins': 40,
     'summary': "L'ermite Tobald affirme que la brume vient des ruines de Vel-Ithar, scellées par une clé runique.",
     'objective': "Trouve la clé runique au fond de la mine abandonnée."},
    {'slug': 'roi-brume', 'title': "Le Roi-Brume", 'order': 3, 'reward_xp': 200, 'reward_coins': 150,
     'reward_item': 'amulette-brumes',
     'summary': "La clé runique ouvre la crypte sous le palais de Vel-Ithar. Quelque chose y attend.",
     'objective': "Descends dans la crypte et affronte le Roi-Brume."},
]

# Scènes. ``choices`` : liste de dicts ; ``success`` / ``failure`` : conséquences.
# ``test`` : (caractéristique, seuil). ``wound`` : (gravité 1-3, description). ``strain`` : sollicite les blessures.
SCENES = [
    # --- Précalm ----------------------------------------------------------
    {
        'slug': 'pot-casse', 'title': "L'auberge du Pot Cassé", 'location': 'precalm', 'explore_weight': 3,
        'text': (
            "La salle est basse et enfumée. On y parle à mi-voix, comme si la brume pouvait écouter. "
            "Derrière le comptoir, [b]Maela[/b] te jauge longuement : « Tu as l'allure de ceux qui partent. "
            "Reste à savoir si tu es de ceux qui reviennent. »"
        ),
        'choices': [
            {'label': "Demander s'il y a une tâche à accomplir", 'forbidden_flag': 'quete_loups',
             'success': {'text': "« Les loups. Depuis que la brume est tombée, ils rôdent jusqu'aux premières maisons. "
                                 "Leur chef a une cicatrice blanche. Abats-le, et la meute se dispersera. »",
                         'start_quest': 'loups-lisiere', 'set_flag': 'quete_loups'}},
            {'label': "Prêter l'oreille aux conversations", 'test': ('perception', 10),
             'success': {'text': "Deux bûcherons évoquent Tobald, l'ermite de la Forêt des Murmures : "
                                 "« Il dit que la brume monte des ruines de Vel-Ithar. »"},
             'failure': {'text': "Les voix se perdent dans le brouhaha."}},
            {'label': "Offrir une tournée (5 écus)", 'required_coins': 5,
             'success': {'text': "Les chopes se lèvent à ta santé. Les langues se délient, les récits d'anciens "
                                 "voyageurs se mêlent aux chansons.", 'xp': 8}},
            {'label': "Repartir", 'order': 9, 'success': {}},
        ],
    },
    {
        'slug': 'puits-ancien', 'title': "Le puits ancien", 'location': 'precalm', 'explore_weight': 1,
        'once': True,
        'text': "Au coin de la place, un puits plus vieux que le village. Quelque chose brille faiblement au fond.",
        'choices': [
            {'label': "Scruter le fond du puits", 'test': ('perception', 13),
             'success': {'text': "Une bourse de cuir accrochée à une pierre descellée. Tu la remontes avec la corde.",
                         'coins': 12},
             'failure': {'text': "Ce n'était qu'un reflet sur l'eau noire."}},
            {'label': "Passer ton chemin", 'success': {}},
        ],
    },
    # --- La Lisière ----------------------------------------------------------
    {
        'slug': 'taniere-loups', 'title': "La tanière des loups", 'location': 'lisiere', 'explore_weight': 4,
        'required_flag': 'quete_loups', 'forbidden_flag': 'loups_vaincus',
        'text': ("Des os rongés, une odeur âcre et un grondement sourd : sous les racines d'un chêne mort, "
                 "l'alpha à la cicatrice blanche te fixe de ses yeux jaunes."),
        'choices': [
            {'label': "Affronter l'alpha", 'success': {'combat': 'loup-alpha', 'next_scene': 'taniere-apres'}},
            {'label': "Le contourner pour le prendre de flanc", 'test': ('dexterite', 13),
             'success': {'text': "Pas un bruit. Tu es sur lui avant qu'il ne se retourne.",
                         'xp': 10, 'combat': 'loup-alpha', 'next_scene': 'taniere-apres'},
             'failure': {'text': "Une branche cède sous ton pied. L'alpha bondit et ses crocs se referment sur ton bras.",
                         'hp': -4, 'wound': (1, "morsure au bras"), 'combat': 'loup-alpha',
                         'next_scene': 'taniere-apres'}},
            {'label': "Reculer", 'success': {'text': "Tu reviendras mieux préparé."}},
        ],
    },
    {
        'slug': 'taniere-apres', 'title': "Le silence de la tanière",
        'text': "L'alpha gît dans la poussière. Privée de son chef, la meute s'est dispersée dans la brume.",
        'choices': [
            {'label': "Prendre un croc en trophée et rentrer à Précalm",
             'success': {'text': "Maela pose une chope devant toi sans un mot. C'est sa façon de dire merci.",
                         'give_item': 'croc-alpha', 'set_flag': 'loups_vaincus', 'complete_quest': 'loups-lisiere',
                         'move_to': 'precalm'}},
        ],
    },
    {
        'slug': 'colporteur-blesse', 'title': "Le colporteur blessé", 'location': 'lisiere', 'explore_weight': 2,
        'once': True,
        'text': "Adossé à sa charrette renversée, un colporteur se tient la jambe. « Des gobelins… ils ont tout pris. »",
        'choices': [
            {'label': "Lui donner une potion de soin", 'required_item': 'potion-soin',
             'success': {'text': "Il boit et se redresse. « Prends ceci, c'est tout ce qu'ils ont laissé. "
                                 "Et si tu descends à la mine, emporte une lanterne. »",
                         'take_item': 'potion-soin', 'xp': 20, 'coins': 15}},
            {'label': "Bander sa plaie avec ce que tu as", 'test': ('intelligence', 13),
             'success': {'text': "Ton bandage tient. Il te serre la main, ému.", 'xp': 15, 'coins': 5},
             'failure': {'text': "Le bandage glisse. Il repart en boitant vers le village."}},
            {'label': "Passer ton chemin", 'success': {}},
        ],
    },
    {
        'slug': 'champignons-luisants', 'title': "Champignons luisants", 'location': 'lisiere', 'explore_weight': 2,
        'text': "Au pied d'une souche, des champignons bleutés luisent doucement dans le brouillard.",
        'choices': [
            {'label': "En goûter un", 'test': ('constitution', 10),
             'success': {'text': "Une chaleur agréable t'envahit. Tu te sens revigoré.", 'hp': 6},
             'failure': {'text': "Ton estomac se tord.", 'hp': -3}},
            {'label': "Les examiner avant tout", 'test': ('intelligence', 13),
             'success': {'text': "Tu reconnais une espèce décrite dans les herbiers : comestible et réparatrice.",
                         'hp': 8},
             'failure': {'text': "Impossible de savoir s'ils sont sûrs. Tu préfères t'abstenir."}},
            {'label': "Les laisser", 'success': {}},
        ],
    },
    # --- Forêt des Murmures --------------------------------------------------
    {
        'slug': 'ermite-tobald', 'title': "La cabane de l'ermite", 'location': 'foret-murmures', 'explore_weight': 3,
        'forbidden_flag': 'brume_secret',
        'text': ("Une cabane couverte de mousse, un feu qui fume vert. [b]Tobald[/b], la barbe jusqu'à la "
                 "ceinture, ne lève pas les yeux. « La brume. Tous veulent savoir d'où elle vient. "
                 "Aucun n'a rien fait pour le mériter. »"),
        'choices': [
            {'label': "Lui montrer le croc de l'alpha", 'required_item': 'croc-alpha',
             'success': {'text': "Ses yeux s'allument. « Voilà quelqu'un qui agit. La brume monte de la crypte de "
                                 "Vel-Ithar. Le sceau s'ouvre avec la clé runique, perdue au fond de la mine. "
                                 "Suis les pierres levées jusqu'aux ruines. »",
                         'take_item': 'croc-alpha', 'xp': 30, 'set_flag': 'brume_secret',
                         'start_quest': 'secret-brumes'}},
            {'label': "Le convaincre de parler", 'test': ('charisme', 16),
             'success': {'text': "Il soupire longuement. « Soit. La crypte de Vel-Ithar, la clé runique dans la mine, "
                                 "les pierres levées. Va, et ne me fais pas regretter ma confiance. »",
                         'xp': 30, 'set_flag': 'brume_secret', 'start_quest': 'secret-brumes'},
             'failure': {'text': "« Des mots. Rapporte-moi le croc de l'alpha, et nous parlerons. »"}},
            {'label': "Le laisser à ses murmures", 'success': {}},
        ],
    },
    {
        'slug': 'clairiere-fees', 'title': "La clairière des fées", 'location': 'foret-murmures', 'explore_weight': 1,
        'once': True, 'min_level': 2,
        'text': "Un cercle de champignons parfait. Des lueurs dansent au-dessus, et des voix minuscules te mettent au défi.",
        'choices': [
            {'label': "Entrer dans leur ronde", 'test': ('dexterite', 13),
             'success': {'text': "Les fées rient, ravies. L'une d'elles te passe une amulette autour du cou.",
                         'give_item': 'amulette-brumes', 'xp': 25},
             'failure': {'text': "Tu trébuches dans le cercle. Les lueurs te piquent en riant.", 'hp': -4}},
            {'label': "Résoudre leur énigme", 'test': ('intelligence', 13),
             'success': {'text': "« Bien répondu ! » Une amulette tombe à tes pieds.",
                         'give_item': 'amulette-brumes', 'xp': 25},
             'failure': {'text': "Mauvaise réponse. Les lueurs s'éteignent d'un coup."}},
            {'label': "T'éloigner sans un bruit", 'success': {}},
        ],
    },
    # --- Mine abandonnée -----------------------------------------------------
    {
        'slug': 'grille-runique', 'title': "La grille runique", 'location': 'mine-abandonnee', 'explore_weight': 4,
        'required_flag': 'brume_secret', 'forbidden_flag': 'cle_trouvee',
        'text': ("Au bout d'une galerie effondrée, une grille gravée de runes protège une niche. À l'intérieur, "
                 "une clé de pierre bleutée pulse faiblement."),
        'choices': [
            {'label': "Forcer la grille", 'test': ('force', 16),
             'success': {'text': "Le métal cède dans un long grincement. La clé runique est à toi.",
                         'strain': True, 'give_item': 'cle-runique', 'set_flag': 'cle_trouvee',
                         'complete_quest': 'secret-brumes', 'start_quest': 'roi-brume'},
             'failure': {'text': "La grille ne bouge pas. Ton épaule, si.", 'strain': True,
                         'wound': (1, "épaule froissée")}},
            {'label': "Déchiffrer les runes", 'test': ('intelligence', 13),
             'success': {'text': "Tu prononces les runes dans l'ordre. La grille s'ouvre d'elle-même.",
                         'give_item': 'cle-runique', 'set_flag': 'cle_trouvee', 'complete_quest': 'secret-brumes',
                         'start_quest': 'roi-brume'},
             'failure': {'text': "Les runes s'embrasent et te brûlent les doigts.", 'hp': -3}},
            {'label': "Faire demi-tour", 'success': {}},
        ],
    },
    {
        'slug': 'filon-cuivre', 'title': "Un filon oublié", 'location': 'mine-abandonnee', 'explore_weight': 2,
        'text': "Une veine de cuivre brille dans la roche. Une vieille pioche traîne juste à côté.",
        'choices': [
            {'label': "Miner le filon", 'test': ('force', 10),
             'success': {'text': "Quelques belles pépites. Le marchand t'en donnera un bon prix.", 'coins': 12,
                         'strain': True},
             'failure': {'text': "La pioche dérape et heurte la roche ; le choc te remonte dans les bras.", 'hp': -2,
                         'strain': True}},
            {'label': "Laisser le filon", 'success': {}},
        ],
    },
    # --- Ruines de Vel-Ithar -------------------------------------------------
    {
        'slug': 'fresque-rois', 'title': "La fresque des rois", 'location': 'ruines-vel-ithar', 'explore_weight': 2,
        'once': True,
        'text': ("Sur un mur encore debout, une fresque : un roi couronné tend les mains vers une brume qui "
                 "l'engloutit. Une inscription court en dessous."),
        'choices': [
            {'label': "Déchiffrer l'inscription", 'test': ('intelligence', 13),
             'success': {'text': "« Qui refusa la mort devint le brouillard. » Tu comprends ce qui t'attend.",
                         'xp': 20},
             'failure': {'text': "L'écriture est trop ancienne pour toi.", 'xp': 5}},
            {'label': "Poursuivre ta route", 'success': {}},
        ],
    },
    {
        'slug': 'autel-offrandes', 'title': "L'autel des offrandes", 'location': 'ruines-vel-ithar',
        'explore_weight': 1,
        'text': "Un autel fissuré. Des pièces anciennes y sont encore posées, couvertes de givre.",
        'choices': [
            {'label': "Examiner les alentours de l'autel", 'test': ('perception', 13),
             'success': {'text': "Une dalle mal ajustée cache une fiole intacte.", 'give_item': 'grande-potion'},
             'failure': {'text': "Rien que de la poussière et du givre."}},
            {'label': "Empocher discrètement les pièces", 'test': ('dexterite', 13),
             'success': {'text': "Tu files avec les pièces avant que quoi que ce soit ne réagisse.", 'coins': 20},
             'failure': {'text': "Les os d'un garde se redressent derrière l'autel !", 'combat': 'squelette-garde'}},
            {'label': "Ne toucher à rien", 'success': {}},
        ],
    },
    # --- Crypte du Roi-Brume -------------------------------------------------
    {
        'slug': 'trone-roi-brume', 'title': "Le trône de brume", 'location': 'crypte-roi-brume', 'explore_weight': 1,
        'forbidden_flag': 'roi_vaincu',
        'text': ("La silhouette se lève. Sa voix est un vent glacé : « Un héros de plus. Ils finissent tous "
                 "en brouillard, à mes pieds. »"),
        'choices': [
            {'label': "Tenir bon face à sa présence", 'test': ('mental', 13),
             'success': {'text': "Tu soutiens son regard vide. Le froid recule. Tu lèves ton arme.",
                         'combat': 'roi-brume', 'next_scene': 'roi-vaincu'},
             'failure': {'text': "La terreur te glace les os, mais tu te forces à avancer.", 'hp': -5,
                         'combat': 'roi-brume', 'next_scene': 'roi-vaincu'}},
            {'label': "Remonter vers les ruines",
             'success': {'text': "Pas aujourd'hui.", 'move_to': 'ruines-vel-ithar'}},
        ],
    },
    {
        'slug': 'roi-vaincu', 'title': "La fin des brumes",
        'text': ("Le Roi-Brume se dissout dans un long soupir. Au-dessus de toi, pour la première fois depuis "
                 "des mois, un rayon de soleil perce jusqu'aux ruines."),
        'choices': [
            {'label': "Rentrer à Précalm",
             'success': {'text': "Tout le village t'attend sur la place. On allume des feux sur les collines, "
                                 "et ton nom passe de bouche en bouche. [i]Fin du scénario d'exemple.[/i]",
                         'set_flag': 'roi_vaincu', 'complete_quest': 'roi-brume', 'move_to': 'precalm'}},
        ],
    },
    {
        'slug': 'crypte-silencieuse', 'title': "Une crypte silencieuse", 'location': 'crypte-roi-brume',
        'explore_weight': 1, 'required_flag': 'roi_vaincu',
        'text': "Le trône est vide. Il ne reste qu'un peu de givre et le souvenir d'un combat.",
        'choices': [],
    },
]

# Paliers : niveau, type, libellé, description, objet du site (slug css de shop.Item), xp site
LEVEL_REWARDS = [
    (2, 'site_xp', "Premiers pas à Ivakar", "+20 XP de membre", None, 20),
    (5, 'title', "Aventurier d'Ivakar", "Titre affiché sur ton profil", None, 0),
    (10, 'site_item', "Cadre d'Ivakar", "Cadre d'avatar exclusif", 'cadre-ivakar', 0),
    (15, 'title', "Pourfendeur des Brumes", "Titre affiché sur ton profil", None, 0),
    (20, 'site_item', "Insigne du Héros d'Ivakar", "Badge de collection pour ta vitrine", 'insigne-heros-ivakar', 0),
]

# Objets de la boutique du site offerts par les paliers (jamais en vente).
SITE_ITEMS = [
    # css_class (slug), nom, type, rareté, description
    ('cadre-ivakar', "Cadre d'Ivakar", 'frame', 'epic', "Offert aux héros d'Ivakar ayant atteint le niveau 10."),
    ('insigne-heros-ivakar', "Insigne du Héros d'Ivakar", 'collectible', 'legendary',
     "Réservé aux héros d'Ivakar de niveau 20. Ne s'achète pas : se mérite."),
]
