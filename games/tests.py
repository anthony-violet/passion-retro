from django.test import TestCase
from django.urls import reverse

from users.models import User
from games.models import (
    LittleBacAnswers,
    LittleBacCategories,
    LittleBacGames,
    LittleBacPlayers,
    LittleBacRounds,
)


class LittleBacRewardTest(TestCase):
    def setUp(self):
        self.player1 = User.objects.create_user(
            username='player1', email='p1@test.com', password='pass12345', active=True
        )
        self.player2 = User.objects.create_user(
            username='player2', email='p2@test.com', password='pass12345', active=True
        )
        self.player1.levels.create(level=1, experience=0)
        self.player2.levels.create(level=1, experience=0)

        self.game = LittleBacGames.objects.create(
            author=self.player1, name='Partie test', status='finished'
        )
        self.lb_player1 = LittleBacPlayers.objects.create(
            user=self.player1, game=self.game, score=0
        )
        self.lb_player2 = LittleBacPlayers.objects.create(
            user=self.player2, game=self.game, score=0
        )
        self.category = LittleBacCategories.objects.create(name='Animal')
        self.round = LittleBacRounds.objects.create(
            game=self.game, letter='C', round_counter=1
        )
        LittleBacAnswers.objects.create(
            round=self.round, player=self.lb_player1,
            category=self.category, answer='chat'
        )
        LittleBacAnswers.objects.create(
            round=self.round, player=self.lb_player2,
            category=self.category, answer='chien'
        )

    def _experience(self, user):
        return user.levels.get(user=user).experience

    def test_results_award_xp_once_regardless_of_visitor_session(self):
        url = reverse('bac_party_results_games', args=[self.game.id])

        self.client.login(username='player1', password='pass12345')
        self.client.get(url)

        self.player1.refresh_from_db()
        self.player2.refresh_from_db()
        self.assertEqual(self._experience(self.player1), 5)
        self.assertEqual(self._experience(self.player2), 5)
        self.round.refresh_from_db()
        self.assertTrue(self.round.xp_awarded)

        # Un autre visiteur (session différente) ne doit pas re-créditer l'XP.
        from django.test import Client

        other = Client()
        other.login(username='player2', password='pass12345')
        other.get(url)

        self.player1.refresh_from_db()
        self.player2.refresh_from_db()
        self.assertEqual(self._experience(self.player1), 5)
        self.assertEqual(self._experience(self.player2), 5)

    def test_players_api_includes_level_and_title(self):
        self.client.login(username='player1', password='pass12345')
        response = self.client.get(
            reverse('game_players_little_bac', args=[self.game.id])
        )

        players = response.json()['players']
        self.assertTrue(players)
        for player in players:
            self.assertEqual(player['level'], 1)
            self.assertEqual(player['level_title'], 'Novice')

    def test_results_display_level_and_ranking(self):
        self.client.login(username='player1', password='pass12345')
        response = self.client.get(
            reverse('bac_party_results_games', args=[self.game.id])
        )

        self.assertContains(response, 'Classement final')
        self.assertContains(response, 'Rang')
        self.assertContains(response, 'level-badge')
        self.assertContains(response, 'Novice')
        self.assertEqual(
            [entry['rank'] for entry in response.context['ranked_players']],
            [1, 1],
        )
