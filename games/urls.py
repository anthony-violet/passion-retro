from django.urls import path
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # API REST
    path('api/<int:game_id>/start_countdown', views.game_start_countdown, name='game_start_countdown'),
    path('api/<int:game_id>/countdown_status', views.game_countdown_status, name='game_countdown_status'),
    path('api/bac/<int:game_id>/info', views.game_infos_little_bac, name='game_infos_little_bac'),
    path('api/bac/<int:game_id>/info_party', views.party_infos_little_bac, name='party_infos_little_bac'),
    path('api/bac/<int:game_id>/players', views.game_players_little_bac, name='game_players_little_bac'),
    path('api/bac/<int:game_id>/end_game', views.game_liitle_bac_end_game, name='end_game'),
    path('api/bac/<int:game_id>/player/<int:player_id>/toggle_ready', views.toggle_ready_status_little_bac, name='toggle_ready_status_little_bac'),


    path("", views.portal, name="portal_games"),
    path("mystere", views.mystery_home, name="mystery_home"),
    path("mystere/proposer", views.mystery_guess, name="mystery_guess"),
    path("mystere/indice", views.mystery_reveal, name="mystery_reveal"),
    path("mystere/abandonner", views.mystery_give_up, name="mystery_give_up"),
    path("mystere/archives", views.mystery_archives, name="mystery_archives"),
    path("mystere/soumettre", views.mystery_propose, name="mystery_propose"),
    path("mystere/mes-propositions", views.mystery_my_proposals, name="mystery_my_proposals"),
    path("mystere/mes-propositions/<int:game_id>/modifier", views.mystery_proposal_edit, name="mystery_proposal_edit"),
    path("bac", views.little_bac_home, name="bac_games"),
    path("bac/party", views.little_bac_start, name="bac_start_games"),
    path("bac/party/<int:party_id>", views.little_bac_party, name="bac_party_games"),
    path("bac/party/<int:party_id>/join", views.little_bac_party_join, name="bac_party_join_games"),
    path("bac/party/<int:party_id>/play", views.little_bac_party_play, name="bac_party_play_games"),
    path("bac/party/<int:party_id>/results", views.game_little_bac_results, name="bac_party_results_games"),
    path('party/<int:game_id>/new_round/', views.game_little_bac_start_new_round, name='bac_start_new_round'),

]