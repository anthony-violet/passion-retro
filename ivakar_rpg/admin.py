"""Atelier d'écriture d'Ivakar : l'équipe y construit le monde.

Parcours conseillé : Lieux (sorties, rencontres) → Scènes (choix) → chaque Choix
(ses conséquences en cas de réussite et d'échec).
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Character, CharacterCharacteristic, CharacterQuest, CharacterReward, Characteristic, Choice,
    CoinExchange, Combat, CombatReport, CombatSeat, Party, PartyMember, PartyMessage, InventoryItem, Item, LevelReward, Location, LocationEncounter, LocationExit,
    Monster, MonsterLoot, Origin, OriginCharacteristic, Outcome, Quest, Scene, Wound,
)


# --- Monde -----------------------------------------------------------------
class LocationExitInline(admin.TabularInline):
    model = LocationExit
    fk_name = 'from_location'
    extra = 1
    autocomplete_fields = ['to_location', 'required_item']


class LocationEncounterInline(admin.TabularInline):
    model = LocationEncounter
    extra = 1
    autocomplete_fields = ['monster']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'recommended_level', 'is_start', 'is_safe', 'has_inn', 'has_merchant', 'order']
    list_editable = ['order']
    list_filter = ['is_safe', 'has_inn', 'has_merchant']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}
    inlines = [LocationExitInline, LocationEncounterInline]


class ChoiceInline(admin.StackedInline):
    model = Choice
    extra = 1
    show_change_link = True
    autocomplete_fields = ['required_item']
    fields = [('label', 'order'), ('test_characteristic', 'test_difficulty'),
              ('required_level', 'required_item', 'required_coins'),
              ('required_flag', 'forbidden_flag', 'hide_if_unavailable')]


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'location', 'explore_weight', 'once', 'min_level']
    list_filter = ['location', 'once']
    search_fields = ['title', 'slug', 'text']
    prepopulated_fields = {'slug': ['title']}
    autocomplete_fields = ['location']
    inlines = [ChoiceInline]
    fieldsets = [
        (None, {'fields': ['title', 'slug', 'location', 'text']}),
        ("Apparition en exploration", {'fields': [('explore_weight', 'once', 'min_level'),
                                                  ('required_flag', 'forbidden_flag')]}),
    ]


class OutcomeInline(admin.StackedInline):
    model = Outcome
    extra = 2
    max_num = 2
    autocomplete_fields = ['give_item', 'take_item', 'start_quest', 'complete_quest', 'move_to',
                           'combat', 'next_scene']
    fields = ['result', 'text', ('xp', 'coins', 'hp'), ('wound', 'wound_label', 'strain_wounds'),
              ('give_item', 'take_item'), 'set_flag',
              ('start_quest', 'complete_quest'), ('move_to', 'combat'), 'next_scene']


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['label', 'scene_link', 'order', 'test_characteristic', 'test_difficulty']
    list_filter = ['scene__location']
    search_fields = ['label', 'scene__title']
    autocomplete_fields = ['scene', 'required_item']
    inlines = [OutcomeInline]

    @admin.display(description="Scène")
    def scene_link(self, obj):
        url = reverse('admin:ivakar_rpg_scene_change', args=[obj.scene_id])
        return format_html('<a href="{}">{}</a>', url, obj.scene)


# --- Monstres, objets, quêtes ---------------------------------------------
class MonsterLootInline(admin.TabularInline):
    model = MonsterLoot
    extra = 1
    autocomplete_fields = ['item']


@admin.register(Monster)
class MonsterAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'hp', 'behavior', 'force', 'dexterite', 'damage_min', 'damage_max',
                    'armor', 'xp', 'is_boss']
    list_filter = ['is_boss', 'level']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}
    inlines = [MonsterLootInline]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'rarity', 'price', 'attack_bonus', 'defense_bonus', 'hp_bonus', 'heal']
    list_filter = ['kind', 'rarity', 'sold_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}
    filter_horizontal = ['sold_at']


@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'reward_xp', 'reward_coins', 'reward_item', 'order']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ['title']}
    autocomplete_fields = ['reward_item']


class OriginCharacteristicInline(admin.TabularInline):
    model = OriginCharacteristic
    extra = 0


@admin.register(Origin)
class OriginAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ['name']}
    inlines = [OriginCharacteristicInline]


@admin.register(Characteristic)
class CharacteristicAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'order', 'is_hidden']
    list_editable = ['order']


@admin.register(LevelReward)
class LevelRewardAdmin(admin.ModelAdmin):
    list_display = ['level', 'kind', 'label', 'shop_item', 'site_xp']
    list_filter = ['kind']
    autocomplete_fields = ['shop_item']


# --- Joueurs (consultation / dépannage) -----------------------------------
class CharacterCharacteristicInline(admin.TabularInline):
    model = CharacterCharacteristic
    extra = 0


class WoundInline(admin.TabularInline):
    model = Wound
    extra = 0


class CharacterQuestInline(admin.TabularInline):
    model = CharacterQuest
    extra = 0


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'origin', 'level', 'xp', 'coins', 'hp', 'state', 'location', 'victories',
                    'knockouts']
    search_fields = ['name', 'user__username']
    list_filter = ['location']
    raw_id_fields = ['user']
    autocomplete_fields = ['location', 'scene']
    inlines = [CharacterCharacteristicInline, WoundInline, CharacterQuestInline]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['item', 'inventory', 'quantity', 'equipped']
    search_fields = ['item__name', 'inventory__character__name']


@admin.register(CoinExchange)
class CoinExchangeAdmin(admin.ModelAdmin):
    list_display = ['user', 'gold_spent', 'coins_received', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['user', 'gold_spent', 'coins_received', 'created_at']


admin.site.register(Combat)
admin.site.register(CombatSeat)


@admin.register(CombatReport)
class CombatReportAdmin(admin.ModelAdmin):
    list_display = ['character', 'monster_name', 'outcome', 'rounds', 'created_at']
    list_filter = ['outcome']
    search_fields = ['character__name', 'monster_name']
    raw_id_fields = ['character', 'monster']


class PartyMemberInline(admin.TabularInline):
    model = PartyMember
    extra = 0
    raw_id_fields = ['character']


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'created_at']
    raw_id_fields = ['leader']
    inlines = [PartyMemberInline]


@admin.register(PartyMessage)
class PartyMessageAdmin(admin.ModelAdmin):
    list_display = ['character', 'party', 'text', 'created_at']
    search_fields = ['character__name', 'text']
admin.site.register(CharacterReward)
