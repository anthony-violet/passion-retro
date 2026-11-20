"""Registre des sections du panel Ivakar : modèle, formulaire, colonnes et sous-listes éditables.

Chaque section est éditée par les vues génériques de ``panel/views/ivakar.py``.
Les choix (et leurs conséquences), les héros et le change ont leurs propres vues.
"""
from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify

from ivakar_rpg.models import (
    Achievement, Characteristic, Choice, DailyTask, Item, Npc, NpcDialogue, Skill, LevelReward, Location, LocationEncounter, LocationExit, Monster, MonsterLoot,
    Origin, OriginCharacteristic, Outcome, Quest, Scene, WorldEvent,
)

TEXTAREAS = {'description': 4, 'text': 8, 'summary': 3}


class IvakarForm(forms.ModelForm):
    """Formulaire de base : grandes zones de texte, slug déduit du nom s'il est laissé vide."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in TEXTAREAS and not getattr(field, 'max_length', None):  # textes courts : une ligne
                field.widget = forms.Textarea(attrs={'rows': TEXTAREAS[name]})
            if isinstance(field, forms.ModelMultipleChoiceField):
                field.widget = forms.CheckboxSelectMultiple(choices=field.choices)
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
                field.input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']
        if 'hp_left' in self.fields:
            self.fields['hp_left'].help_text = "Remis aux PV de la menace à la création ; à corriger seulement en cas de souci."
            self.fields['hp_left'].required = False
        if 'slug' in self.fields:
            self.fields['slug'].required = False
            self.fields['slug'].help_text = ("Identifiant technique. Vide = déduit du nom. Évite de le changer "
                                             "ensuite : la commande load_ivakar s'en sert pour reconnaître les "
                                             "éléments du scénario.")

    def clean(self):
        data = super().clean()
        if 'hp_left' in self.fields and data.get('hp_left') is None:
            data['hp_left'] = data.get('hp_total') or 0
        if 'slug' in self.fields and not data.get('slug'):
            source = data.get('name') or data.get('title') or ''
            data['slug'] = slugify(source)[:60]
            if not data['slug']:
                self.add_error('slug', "Impossible de déduire l'identifiant : renseigne un nom.")
        return data


def form_for(model, fields):
    return forms.modelform_factory(model, form=IvakarForm, fields=fields)


def inline(parent, model, fields, fk_name=None, title='', extra=1, initial=None):
    return {
        'title': title,
        'formset': inlineformset_factory(parent, model, form=IvakarForm, fields=fields, fk_name=fk_name,
                                         extra=extra, can_delete=True),
        'initial': initial,
    }


def _missing_characteristics(origin):
    """Lignes pré-remplies pour les caractéristiques qu'une origine n'a pas encore."""
    from ivakar_rpg.engine.character import ensure_characteristics

    ensure_characteristics()  # filet de sécurité si la base n'a pas encore les sept caractéristiques
    have = set(origin.values.values_list('characteristic_id', flat=True)) if origin.pk else set()
    return [{'characteristic': c.pk, 'value': 10} for c in Characteristic.objects.exclude(pk__in=have)]


SECTIONS = {
    'lieux': {
        'model': Location, 'title': "Lieux", 'singular': "un lieu", 'icon': "🗺️",
        'help': "Les lieux du monde, leurs chemins et les monstres qu'on y croise en explorant.",
        'form': form_for(Location, ['name', 'slug', 'description', 'image', 'is_start', 'is_safe', 'has_inn',
                                    'inn_price', 'has_merchant', 'recommended_level', 'calm_weight', 'order',
                                    'map_x', 'map_y']),
        'columns': [("Nom", 'name'), ("Niv.", 'recommended_level'), ("Départ", 'is_start'), ("Sûr", 'is_safe'),
                    ("Auberge", 'has_inn'), ("Marchand", 'has_merchant'), ("Ordre", 'order')],
        'search': ['name', 'slug'],
        'inlines': [
            inline(Location, LocationExit, ['to_location', 'label', 'required_level', 'required_item',
                                            'required_flag', 'locked_text', 'order'],
                   fk_name='from_location', title="Chemins (sorties)"),
            inline(Location, LocationEncounter, ['monster', 'weight'], title="Rencontres en exploration"),
        ],
    },
    'scenes': {
        'model': Scene, 'title': "Scènes", 'singular': "une scène", 'icon': "📜",
        'help': "Les événements à choix. Une scène apparaît en explorant son lieu (poids > 0) ou à la suite d'un "
                "choix. Sans illustration propre, elle reprend celle de son lieu.",
        'form': form_for(Scene, ['title', 'slug', 'location', 'npc', 'text', 'image', 'explore_weight', 'once',
                                 'min_level', 'required_flag', 'forbidden_flag']),
        'columns': [("Titre", 'title'), ("Lieu", 'location'), ("Poids", 'explore_weight'), ("Unique", 'once'),
                    ("Choix", 'choices.count')],
        'search': ['title', 'slug', 'text'],
        'filter': ('location', Location, "Tous les lieux"),
        'inlines': [],
        'has_choices': True,
    },
    'pnj': {
        'model': Npc, 'title': "PNJ", 'singular': "un PNJ", 'icon': "🧑",
        'help': "Les habitants du monde. Dans chaque lieu coché, le joueur voit le PNJ et peut lui parler : cela "
                "ouvre la scène de la première entrée de dialogue dont les conditions sont remplies. Ses répliques "
                "évoluent donc avec les marqueurs du héros.",
        'form': form_for(Npc, ['name', 'slug', 'role', 'description', 'image', 'locations', 'order', 'is_active']),
        'columns': [("Nom", 'name'), ("Rôle", 'role'), ("Lieux", 'locations_display'),
                    ("Dialogues", 'dialogues.count'), ("Présent", 'is_active')],
        'search': ['name', 'slug', 'role'],
        'inlines': [inline(Npc, NpcDialogue, ['scene', 'label', 'order', 'min_level', 'required_flag',
                                              'forbidden_flag'], title="Dialogues (la première entrée valable "
                                                                       "l'emporte)")],
    },
    'monstres': {
        'model': Monster, 'title': "Monstres", 'singular': "un monstre", 'icon': "👹",
        'help': "Chaque monstre a ses caractéristiques : en combat, chaque échange l'oppose au héros (2D6 + "
                "⌊caractéristique ÷ 3⌋ de chaque côté). Repère : un héros a environ 15 + 2 × (niveau − 1) dans sa "
                "spécialité ; un monstre du même niveau à peu près autant en Dextérité.",
        'form': form_for(Monster, ['name', 'slug', 'description', 'image', 'level', 'hp', 'behavior', 'force',
                                   'dexterite', 'perception', 'intelligence', 'mental', 'damage_min', 'damage_max',
                                   'armor', 'xp', 'coins_min', 'coins_max', 'is_boss']),
        'columns': [("Nom", 'name'), ("Niv.", 'level'), ("PV", 'hp'), ("Comportement", 'behavior_short'),
                    ("For.", 'force'), ("Dex.", 'dexterite'), ("Dégâts", 'damage_range'), ("XP", 'xp'),
                    ("Boss", 'is_boss')],
        'search': ['name', 'slug'],
        'inlines': [inline(Monster, MonsterLoot, ['item', 'chance'], title="Butin")],
    },
    'objets': {
        'model': Item, 'title': "Objets", 'singular': "un objet", 'icon': "🎒",
        'help': "Armes, armures, consommables et objets de quête. Cocher un lieu met l'objet en vente chez son marchand.",
        'form': form_for(Item, ['name', 'slug', 'description', 'image', 'kind', 'rarity', 'price', 'attack_bonus',
                                'defense_bonus', 'hp_bonus', 'heal', 'sold_at']),
        'columns': [("Nom", 'name'), ("Type", 'kind'), ("Rareté", 'rarity'), ("Prix", 'price'),
                    ("Dégâts", 'attack_bonus'), ("Armure", 'defense_bonus'), ("Soin", 'heal')],
        'search': ['name', 'slug'],
        'inlines': [],
    },
    'quetes': {
        'model': Quest, 'title': "Quêtes", 'singular': "une quête", 'icon': "📖",
        'help': "Une quête démarre et se termine par les conséquences des choix (« Démarre / Termine la quête »).",
        'form': form_for(Quest, ['title', 'slug', 'summary', 'objective', 'reward_xp', 'reward_coins',
                                 'reward_item', 'order']),
        'columns': [("Titre", 'title'), ("XP", 'reward_xp'), ("Écus", 'reward_coins'), ("Objet", 'reward_item'),
                    ("Ordre", 'order')],
        'search': ['title', 'slug'],
        'inlines': [],
    },
    'origines': {
        'model': Origin, 'title': "Origines", 'singular': "une origine", 'icon': "🧬",
        'help': "Le choix initial du héros : il fixe ses sept caractéristiques de départ (de 1 à 20 chacune, "
                "sans total imposé).",
        'form': form_for(Origin, ['name', 'slug', 'description', 'order', 'is_active']),
        'columns': [("Nom", 'name'), ("Total", 'values_total'), ("Compétences", 'skills.count'),
                    ("Proposée", 'is_active'), ("Ordre", 'order')],
        'search': ['name', 'slug'],
        'inlines': [inline(Origin, OriginCharacteristic, ['characteristic', 'value'], title="Caractéristiques de départ",
                           extra=0, initial=_missing_characteristics)],
    },
    'competences': {
        'model': Skill, 'title': "Compétences", 'singular': "une compétence", 'icon': "✨",
        'help': "Actions de combat propres aux origines (les classes), utilisables en combat et en duel. Le héros "
                "obtient chaque compétence de son origine en atteignant son niveau requis ; après usage, elle se "
                "recharge pendant quelques manches. Son type dit comment elle se comporte face à l'action adverse ; "
                "les caractéristiques, le bonus au jet et les dés en plus en font une version propre à la classe.",
        'form': form_for(Skill, ['name', 'slug', 'icon', 'description', 'kind', 'stat', 'against', 'roll_bonus',
                                 'extra_dice', 'flat_bonus', 'cooldown', 'min_level', 'origins', 'order',
                                 'is_active']),
        'columns': [("", 'icon'), ("Nom", 'name'), ("Type", 'kind'), ("Carac.", 'stat'), ("Niv.", 'min_level'),
                    ("Recharge", 'cooldown'), ("Origines", 'origins_display'), ("Active", 'is_active')],
        'search': ['name', 'slug', 'description'],
        'filter': ('origins', Origin, "Toutes les origines"),
        'inlines': [],
    },
    'paliers': {
        'model': LevelReward, 'title': "Paliers", 'singular': "un palier", 'icon': "🏅",
        'help': "Ce qu'un niveau d'Ivakar débloque sur le site : un titre, un objet de la boutique du site "
                "(cadre, badge…) ou de l'XP de membre. Chaque palier n'est accordé qu'une fois.",
        'form': form_for(LevelReward, ['level', 'kind', 'label', 'description', 'shop_item', 'site_xp']),
        'columns': [("Niveau", 'level'), ("Type", 'kind'), ("Libellé", 'label'), ("Objet du site", 'shop_item'),
                    ("XP site", 'site_xp')],
        'search': ['label'],
        'inlines': [],
    },
}

SECTIONS['succes'] = {
    'model': Achievement, 'title': "Succès", 'singular': "un succès", 'icon': "🏆",
    'help': "Objectifs à vie, débloqués dès que le compteur suivi atteint l'objectif (vérifié à chaque page du "
            "jeu). « Marqueur d'histoire obtenu » relie un succès à un moment du scénario.",
    'form': form_for(Achievement, ['name', 'slug', 'icon', 'description', 'metric', 'goal', 'flag', 'hidden',
                                   'reward_xp', 'reward_coins', 'order', 'is_active']),
    'columns': [("", 'icon'), ("Nom", 'name'), ("Compteur", 'metric'), ("Objectif", 'goal_display'),
                ("Secret", 'hidden'), ("XP", 'reward_xp'), ("Écus", 'reward_coins'), ("Actif", 'is_active')],
    'search': ['name', 'slug', 'flag'],
    'inlines': [],
}

SECTIONS['quotidiennes'] = {
    'model': DailyTask, 'title': "Tâches du jour", 'singular': "une tâche quotidienne", 'icon': "🎯",
    'help': "Chaque jour à minuit, 3 tâches sont tirées pour chaque héros parmi les tâches actives de son niveau "
            "(selon leur poids). La progression compte ce qui est fait depuis le tirage.",
    'form': form_for(DailyTask, ['name', 'slug', 'metric', 'goal', 'reward_xp', 'reward_coins', 'min_level',
                                 'weight', 'is_active']),
    'columns': [("Nom", 'name'), ("Compteur", 'metric'), ("Objectif", 'goal'), ("Niv. min", 'min_level'),
                ("Poids", 'weight'), ("XP", 'reward_xp'), ("Écus", 'reward_coins'), ("Active", 'is_active')],
    'search': ['name', 'slug'],
    'inlines': [],
}

SECTIONS['evenements'] = {
    'model': WorldEvent, 'title': "Événements", 'singular': "un événement", 'icon': "🌍",
    'help': "Une menace commune que tous les héros affaiblissent, chacun à son rythme, entre le début et la fin. "
            "Vaincue, elle récompense chaque participant. Sans illustration, elle reprend celle de sa créature.",
    'form': form_for(WorldEvent, ['name', 'slug', 'description', 'image', 'monster', 'location', 'starts_at',
                                  'ends_at', 'hp_total', 'hp_left', 'dexterite',
                                  'damage_min', 'damage_max', 'cooldown_minutes', 'reward_xp', 'reward_coins',
                                  'top_reward_item']),
    'columns': [("Nom", 'name'), ("État", 'status_label'), ("PV", 'hp_display'), ("Lieu", 'location'),
                ("Début", 'starts_at'), ("Fin", 'ends_at')],
    'search': ['name', 'slug'],
    'inlines': [],
}

ChoiceForm = form_for(Choice, ['label', 'order', 'test_characteristic', 'test_difficulty', 'required_level',
                               'required_item', 'required_coins', 'required_flag', 'forbidden_flag',
                               'hide_if_unavailable'])
OutcomeForm = form_for(Outcome, ['text', 'xp', 'coins', 'hp', 'wound', 'wound_label', 'strain_wounds', 'give_item',
                                 'take_item', 'set_flag', 'start_quest', 'complete_quest', 'move_to', 'combat',
                                 'next_scene'])
