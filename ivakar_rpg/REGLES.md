# Ivakar — état des règles dans le moteur

Le moteur suit les règles d'Ivakar (heroic fantasy épique, moteur fait maison,
BRP SRD 1.0 seulement comme référence comparative). Ce fichier sépare ce qui est
**validé** de ce que le code a dû **supposer** pour que le jeu tourne. Chaque
supposition est marquée `PROVISOIRE` dans le code, regroupée dans peu de
fichiers, et doit être tranchée ou remplacée lors des phases de test.

## Validé (implémenté tel quel)

| Règle | Où |
|---|---|
| Résolution : 2D6 + ⌊caractéristique ÷ 3⌋ ≥ seuil | `engine/rules.py` → `resolve()` |
| Seuils : Facile 10, Moyenne 13, Difficile 16 | `models.DIFFICULTY_*` (choix imposés dans l'admin) |
| Sept caractéristiques : Force, Constitution, Dextérité, Perception, Intelligence, Mental, Charisme | `engine/rules.py` → `CHARACTERISTICS` |
| Niveau 1 : chaque caractéristique entre 1 et 20, pas de total imposé, valeurs fixées automatiquement par le choix initial | modèle `Origin` (éditable dans l'admin), `create_character()` |
| Niveaux 1 à 25, 3 points de progression par niveau, répartition libre, aucune hausse automatique | `gain_xp()`, `spend_point()` |
| Plafond absolu d'une caractéristique : 100 | `spend_point()` |
| Blessures : légère, modérée, grave ; aggravation possible, non systématique | modèle `Wound`, `engine/wounds.py` |
| Blessures et états distincts (KO) | `Character.state` ≠ `Wound` |
| 0 PV ≠ mort : risque de blessure critique | `knock_out()` |
| Aggravation : D10 × 10 ≤ caractéristique × coefficient (×5 / ×4 / ×3) → stable, sinon aggravation | `rules.aggravation_check()` |
| Contexte → Force ; temps sans soins → Mental ; jamais moyennés ni compensés | `context_check()`, `time_check()` |

## Provisoire (à valider ou remplacer)

| Sujet | Choix actuel | Où |
|---|---|---|
| Points de vie | 10 + Constitution + 2 par niveau après le 1er (+ bonus d'objet) | `character.py` (`HP_BASE`, `HP_PER_LEVEL`) |
| Courbe d'XP | 25 × (niveau − 1) × niveau | `xp_for_level()` |
| Combat contre les monstres | Manches à actions comme les duels (`engine/clash.py`) : le héros choisit parmi les 6 actions, le monstre joue l'action décidée d'avance selon son comportement (brute, prudent, rusé, équilibré). Chaque échange est une opposition entre les caractéristiques du héros et celles du monstre (Force, Dextérité, Perception, Intelligence, Mental), ce qui garde la difficulté relative à tout niveau. Le Coup puissant du monstre est toujours annoncé ; le reste ne l'est qu'après un Observer réussi | `engine/combat.py` |
| Dégâts | Héros : 1D6 + ⌊Force ÷ 3⌋ + bonus d'arme ; monstre : sa fourchette ; − armure (min. 1) ; selon l'écart : ÷ 2 (1-2), normal (3-5), +1D6 (6+) ; Coup puissant +1D6 | `clash.py` |
| Potion, fuite | Boire ou tenter de fuir prend la manche (le monstre agit quand même) ; fuite = Dextérité contre Dextérité, impossible face à un boss | `combat.py` |
| Chute simultanée | Si héros et monstre tombent dans la même manche, le héros gagne et garde 1 PV | `combat.py` |
| Blessure à 0 PV | Constitution contre 13 : réussite → modérée, échec → grave | `wounds.py` (`KO_CRITICAL_THRESHOLD`) |
| Réveil après KO | Retour au lieu de départ à mi-PV | `wake_up()` |
| Déclencheur « contexte » | Uniquement quand une conséquence de scène coche « Sollicite les blessures » | `Outcome.strain_wounds` |
| Déclencheur « temps sans soins » | Un tirage tous les 3 voyages | `wounds.TIME_CHECK_EVERY` |
| Aggravation d'une blessure grave | Reste grave (rien de défini au-delà) | `wounds._check()` |
| Effets des blessures | Aucun malus mécanique pour l'instant | — |
| Soins | Une nuit à l'auberge : PV au max, chaque blessure perd un degré ; potions = PV seulement | `rest()`, `treat_all()` |
| Duels (oppositions) | Manches à choix secrets et simultanés parmi 6 actions, chacune sur une caractéristique (Frappe et Garde : Dextérité, Coup puissant : Force, Feinte : Intelligence contre Perception, Intimidation : Charisme contre Mental, Observer : Perception contre Intelligence). Attaque = opposition 2D6 + ⌊carac ÷ 3⌋ des deux côtés, égalité au défenseur ; écart 1-2 effleure (dégâts ÷ 2), 3-5 touche, 6+ coup appuyé (+1D6). PV à part, sans blessure ni KO ; forfait après 24 h | `engine/duel.py`, `engine/clash.py` |
| Événements de serveur | Un assaut par héros toutes les N minutes (réglable) ; assaut et esquive de la riposte = opposition Dextérité du héros contre Dextérité de la menace ; récompenses égales pour tout participant, objet pour le meilleur | `engine/events.py` |
| Tâches quotidiennes | 3 par jour (minuit, heure de Paris), tirées selon leur poids parmi celles du niveau du héros ; progression = écart du compteur depuis le tirage ; récompense dès l'objectif atteint ; bonus « journée complète » +10 XP et +15 écus | `engine/progress.py` |
| Succès | Débloqués quand un compteur atteint l'objectif (ou qu'un marqueur est obtenu), vérifiés à l'affichage des pages ; récompense une seule fois ; au-delà de 2 d'un coup, un seul popup | `engine/progress.py`, `content/progression.py` |
| PNJ | « Parler » ouvre la scène de la première entrée de dialogue dont les conditions (niveau, marqueurs) sont remplies ; aucun moteur de dialogue à part | `engine/npcs.py` |
| Compétences | Propres aux origines (les « classes »), obtenues au niveau requis ; s'utilisent en combat et en duel comme une action de base (type), avec leurs caractéristiques, un bonus au jet, des D6 et un bonus fixe ; recharge de N manches après usage | `engine/skills.py`, `clash.py` |
| Origines proposées | Soldat, Éclaireur, Lettré, Héraut, Forgeron (valeurs dans `content/chapitre1.py`) | admin → Origines |

## Contenu

`content/chapitre1.py` (« Les Brumes de Précalm ») est un scénario d'exemple
pour tester le moteur, pas une campagne. Aucun élément du roman *Soleris –
Chroniques d'Ivakar* n'y est repris. Chargement : `python manage.py load_ivakar`
(`--update` pour réécrire avec les valeurs du fichier).
