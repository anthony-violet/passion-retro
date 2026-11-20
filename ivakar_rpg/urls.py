from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="rpg_home"),
    path("creer", views.create, name="rpg_create"),
    path("jouer", views.play, name="rpg_play"),
    path("jouer/explorer", views.explore, name="rpg_explore"),
    path("jouer/aller/<int:exit_id>", views.move, name="rpg_move"),
    path("jouer/choix/<int:choice_id>", views.choose, name="rpg_choose"),
    path("jouer/continuer", views.leave_scene, name="rpg_leave_scene"),
    path("jouer/combat", views.combat_action, name="rpg_combat"),
    path("jouer/auberge", views.rest, name="rpg_rest"),
    path("jouer/reveil", views.wake_up, name="rpg_wake_up"),
    path("heros", views.sheet, name="rpg_sheet"),
    path("heros/point", views.spend_point, name="rpg_spend_point"),
    path("heros/titre", views.toggle_title, name="rpg_toggle_title"),
    path("inventaire", views.inventory, name="rpg_inventory"),
    path("inventaire/<int:item_id>/equiper", views.equip, name="rpg_equip"),
    path("inventaire/<int:item_id>/utiliser", views.use, name="rpg_use"),
    path("quetes", views.quests, name="rpg_quests"),
    path("carte", views.world_map, name="rpg_map"),
    path("marchand", views.merchant, name="rpg_merchant"),
    path("marchand/acheter/<int:item_id>", views.buy, name="rpg_buy"),
    path("marchand/vendre/<int:item_id>", views.sell, name="rpg_sell"),
    path("change", views.exchange, name="rpg_exchange"),
    path("recompenses", views.rewards, name="rpg_rewards"),
]
