"""Charge le scénario d'exemple d'Ivakar (idempotent).

Par défaut, seuls les éléments absents sont créés : les retouches faites dans
l'admin sont préservées. ``--update`` réécrit les éléments du scénario avec les
valeurs du fichier.

Les éléments sont reconnus par leur identifiant (slug) : un élément dont le slug
a été changé dans le panel sera recréé. Vérifier avant de relancer la commande.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ivakar_rpg.content import chapitre1 as content
from ivakar_rpg.engine.character import ensure_characteristics
from ivakar_rpg.models import (
    Characteristic, Choice, Item, LevelReward, Location, LocationEncounter, LocationExit, Monster, MonsterLoot,
    Origin, OriginCharacteristic, Outcome, Quest, Scene,
)


class Command(BaseCommand):
    help = "Charge le scénario d'exemple d'Ivakar (lieux, scènes, monstres, objets, quêtes, paliers)."

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true',
                            help="Réécrit les éléments existants avec les valeurs du scénario.")

    def _save(self, model, lookup, values):
        if self.update:
            obj, created = model.objects.update_or_create(**lookup, defaults=values)
        else:
            obj, created = model.objects.get_or_create(**lookup, defaults=values)
        self.counts[model.__name__] = self.counts.get(model.__name__, 0) + int(created)
        return obj, created

    @transaction.atomic
    def handle(self, *args, update=False, **options):
        self.update = update
        self.counts = {}
        ensure_characteristics()
        stats = {c.code: c for c in Characteristic.objects.all()}

        items = {}
        for slug, name, kind, rarity, price, atk, dfn, hp, heal, description in content.ITEMS:
            items[slug], _ = self._save(Item, {'slug': slug}, {
                'name': name, 'kind': kind, 'rarity': rarity, 'price': price, 'attack_bonus': atk,
                'defense_bonus': dfn, 'hp_bonus': hp, 'heal': heal, 'description': description,
            })

        locations = {}
        for data in content.LOCATIONS:
            data = dict(data)
            wares = data.pop('wares', [])
            slug = data.pop('slug')
            position = {'map_x': data.pop('map_x', None), 'map_y': data.pop('map_y', None)}
            locations[slug], created = self._save(Location, {'slug': slug}, data)
            # Position sur la carte : posée si le lieu n'est pas encore placé (sans écraser un placement du panel).
            if self.update or locations[slug].map_x is None:
                Location.objects.filter(pk=locations[slug].pk).update(**position)
            if created or self.update:
                for ware in wares:
                    items[ware].sold_at.add(locations[slug])

        for origin_slug, to_slug, label, level, item, flag, locked in content.EXITS:
            self._save(LocationExit, {'from_location': locations[origin_slug], 'to_location': locations[to_slug]}, {
                'label': label, 'required_level': level, 'required_item': items.get(item),
                'required_flag': flag, 'locked_text': locked,
            })

        monsters = {}
        for (slug, name, level, hp, hit, dodge, flee, dmin, dmax, armor, xp, cmin, cmax, boss, description,
             loot) in content.MONSTERS:
            monsters[slug], created = self._save(Monster, {'slug': slug}, {
                'name': name, 'level': level, 'hp': hp, 'hit_difficulty': hit, 'dodge_difficulty': dodge,
                'flee_difficulty': flee, 'damage_min': dmin, 'damage_max': dmax, 'armor': armor, 'xp': xp,
                'coins_min': cmin, 'coins_max': cmax, 'is_boss': boss, 'description': description,
            })
            for item_slug, chance in loot:
                self._save(MonsterLoot, {'monster': monsters[slug], 'item': items[item_slug]}, {'chance': chance})

        for location_slug, monster_slug, weight in content.ENCOUNTERS:
            self._save(LocationEncounter, {'location': locations[location_slug], 'monster': monsters[monster_slug]},
                       {'weight': weight})

        for slug, name, description, values in content.ORIGINS:
            origin, _ = self._save(Origin, {'slug': slug}, {'name': name, 'description': description,
                                                           'order': list(o[0] for o in content.ORIGINS).index(slug)})
            for code, value in values.items():
                self._save(OriginCharacteristic, {'origin': origin, 'characteristic': stats[code]}, {'value': value})

        quests = {}
        for data in content.QUESTS:
            data = dict(data)
            slug = data.pop('slug')
            data['reward_item'] = items.get(data.pop('reward_item', None))
            quests[slug], _ = self._save(Quest, {'slug': slug}, data)

        # Les scènes d'abord (les conséquences peuvent pointer vers une scène plus loin).
        scenes = {}
        for data in content.SCENES:
            scenes[data['slug']], _ = self._save(Scene, {'slug': data['slug']}, {
                'title': data['title'], 'text': data['text'], 'location': locations.get(data.get('location')),
                'explore_weight': data.get('explore_weight', 0), 'once': data.get('once', False),
                'min_level': data.get('min_level', 0), 'required_flag': data.get('required_flag', ''),
                'forbidden_flag': data.get('forbidden_flag', ''),
            })
        for data in content.SCENES:
            scene = scenes[data['slug']]
            for order, choice_data in enumerate(data['choices'], start=1):
                test = choice_data.get('test')
                choice, _ = self._save(Choice, {'scene': scene, 'label': choice_data['label']}, {
                    'order': choice_data.get('order', order),
                    'required_item': items.get(choice_data.get('required_item')),
                    'required_coins': choice_data.get('required_coins', 0),
                    'required_flag': choice_data.get('required_flag', ''),
                    'forbidden_flag': choice_data.get('forbidden_flag', ''),
                    'test_characteristic': stats[test[0]] if test else None,
                    'test_difficulty': test[1] if test else 13,
                })
                for result in (Outcome.RESULT_SUCCESS, Outcome.RESULT_FAILURE):
                    outcome = choice_data.get(result)
                    if outcome is None:
                        continue
                    wound = outcome.get('wound') or (0, '')
                    self._save(Outcome, {'choice': choice, 'result': result}, {
                        'text': outcome.get('text', ''), 'xp': outcome.get('xp', 0),
                        'coins': outcome.get('coins', 0), 'hp': outcome.get('hp', 0),
                        'wound': wound[0], 'wound_label': wound[1], 'strain_wounds': outcome.get('strain', False),
                        'give_item': items.get(outcome.get('give_item')),
                        'take_item': items.get(outcome.get('take_item')),
                        'set_flag': outcome.get('set_flag', ''),
                        'start_quest': quests.get(outcome.get('start_quest')),
                        'complete_quest': quests.get(outcome.get('complete_quest')),
                        'move_to': locations.get(outcome.get('move_to')),
                        'combat': monsters.get(outcome.get('combat')),
                        'next_scene': scenes.get(outcome.get('next_scene')),
                    })

        site_items = self._site_items()
        for level, kind, label, description, site_item, site_xp in content.LEVEL_REWARDS:
            self._save(LevelReward, {'level': level, 'kind': kind, 'label': label}, {
                'description': description, 'shop_item': site_items.get(site_item), 'site_xp': site_xp,
            })

        created = ", ".join(f"{name} : {count}" for name, count in self.counts.items() if count) or "rien de neuf"
        if options.get('verbosity', 1):
            self.stdout.write(self.style.SUCCESS(f"Scénario d'Ivakar chargé ({created})."))

    def _site_items(self):
        """Objets de la boutique du site offerts par les paliers : catégorie et objets inactifs (jamais en vente)."""
        from shop.models import Category, Item as ShopItem

        category, _ = Category.objects.get_or_create(
            name="Ivakar", defaults={'description': "Récompenses des héros d'Ivakar.", 'is_active': False},
        )
        result = {}
        for slug, name, kind, rarity, description in content.SITE_ITEMS:
            result[slug], _ = self._save(ShopItem, {'css_class': slug}, {
                'category': category, 'name': name, 'kind': kind, 'rarity': rarity, 'description': description,
                'price': 0, 'is_active': False,
            })
        return result
