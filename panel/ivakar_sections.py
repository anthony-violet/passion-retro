"""Registre des sections du panel Ivakar : modèle, formulaire, colonnes et sous-listes éditables.

Chaque section est éditée par les vues génériques de ``panel/views/ivakar.py``.
Les choix (et leurs conséquences), les héros et le change ont leurs propres vues.
"""
from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify

from ivakar_rpg.models import (
    Characteristic, Choice, Item, LevelReward, Location, LocationEncounter, LocationExit, Monster, MonsterLoot,
    Origin, OriginCharacteristic, Outcome, Quest, Scene,
)

TEXTAREAS = {'description': 4, 'text': 8, 'summary': 3}


class IvakarForm(forms.ModelForm):
    """Formulaire de base : grandes zones de texte, slug déduit du nom s'il est laissé vide."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in TEXTAREAS:
                field.widget = forms.Textarea(attrs={'rows': TEXTAREAS[name]})
            if isinstance(field, forms.ModelMultipleChoiceField):
                field.widget = forms.CheckboxSelectMultiple(choices=field.choices)
        if 'slug' in self.fields:
            self.fields['slug'].required = False
            self.fields['slug'].help_text = ("Identifiant technique. Vide = déduit du nom. Évite de le changer "
                                             "ensuite : la commande load_ivakar s'en sert pour reconnaître les "
                                             "éléments du scénario.")

    def clean(self):
        data = super().clean()
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
        'form': form_for(Scene, ['title', 'slug', 'location', 'text', 'image', 'explore_weight', 'once',
                                 'min_level', 'required_flag', 'forbidden_flag']),
        'columns': [("Titre", 'title'), ("Lieu", 'location'), ("Poids", 'explore_weight'), ("Unique", 'once'),
                    ("Choix", 'choices.count')],
        'search': ['title', 'slug', 'text'],
        'filter': ('location', Location, "Tous les lieux"),
        'inlines': [],
        'has_choices': True,
    },
    'monstres': {
        'model': Monster, 'title': "Monstres", 'singular': "un monstre", 'icon': "👹",
        'help': "Chaque monstre est décrit par les seuils (10 / 13 / 16) que le héros doit atteindre avec sa "
                "Dextérité pour le toucher, esquiver ses attaques ou le fuir.",
        'form': form_for(Monster, ['name', 'slug', 'description', 'image', 'level', 'hp', 'hit_difficulty',
                                   'dodge_difficulty', 'flee_difficulty', 'damage_min', 'damage_max', 'armor', 'xp',
                                   'coins_min', 'coins_max', 'is_boss']),
        'columns': [("Nom", 'name'), ("Niv.", 'level'), ("PV", 'hp'), ("Toucher", 'hit_difficulty'),
                    ("Esquiver", 'dodge_difficulty'), ("Dégâts", 'damage_range'), ("XP", 'xp'), ("Boss", 'is_boss')],
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
        'columns': [("Nom", 'name'), ("Total", 'values_total'), ("Proposée", 'is_active'), ("Ordre", 'order')],
        'search': ['name', 'slug'],
        'inlines': [inline(Origin, OriginCharacteristic, ['characteristic', 'value'], title="Caractéristiques de départ",
                           extra=0, initial=_missing_characteristics)],
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

ChoiceForm = form_for(Choice, ['label', 'order', 'test_characteristic', 'test_difficulty', 'required_level',
                               'required_item', 'required_coins', 'required_flag', 'forbidden_flag',
                               'hide_if_unavailable'])
OutcomeForm = form_for(Outcome, ['text', 'xp', 'coins', 'hp', 'wound', 'wound_label', 'strain_wounds', 'give_item',
                                 'take_item', 'set_flag', 'start_quest', 'complete_quest', 'move_to', 'combat',
                                 'next_scene'])
