"""Parcours complet d'une partie de Petit Bac."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from games.models import LittleBacGames, LittleBacPlayers, LittleBacRounds
from users.models import User


class LittleBacFlowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username='hote', password='pass')
        cls.guest = User.objects.create_user(username='invite', password='pass')

    def start_game(self):
        self.client.force_login(self.host)
        response = self.client.get(reverse('bac_start_games'))
        game = LittleBacGames.objects.get(author=self.host)
        self.assertRedirects(response, reverse('bac_party_games', args=[game.id]))
        return game

    def test_start_creates_game_player_and_first_round(self):
        game = self.start_game()
        self.assertEqual(game.players.count(), 1)
        round_ = LittleBacRounds.objects.get(game=game)
        self.assertEqual(round_.round_counter, 1)
        self.assertTrue(round_.letter.isalpha())
        self.assertEqual(self.client.get(reverse('bac_party_games', args=[game.id])).status_code, 200)

    def test_guest_joins_once(self):
        game = self.start_game()
        self.client.force_login(self.guest)
        self.client.get(reverse('bac_party_join_games', args=[game.id]))
        self.client.get(reverse('bac_party_join_games', args=[game.id]))
        self.assertEqual(game.players.filter(user=self.guest).count(), 1)

    def test_non_player_redirected_from_party(self):
        game = self.start_game()
        self.client.force_login(self.guest)
        response = self.client.get(reverse('bac_party_games', args=[game.id]))
        self.assertRedirects(response, reverse('bac_games'))

    def test_player_toggles_own_ready_status(self):
        game = self.start_game()
        url = reverse('toggle_ready_status_little_bac', args=[game.id, self.host.id])
        self.assertTrue(self.client.get(url).json()['is_ready'])
        self.assertFalse(self.client.get(url).json()['is_ready'])

    def test_player_cannot_toggle_someone_else(self):
        game = self.start_game()
        self.client.force_login(self.guest)
        url = reverse('toggle_ready_status_little_bac', args=[game.id, self.host.id])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertFalse(LittleBacPlayers.objects.get(game=game, user=self.host).is_ready)

    def test_only_host_starts_new_round(self):
        game = self.start_game()
        self.client.force_login(self.guest)
        self.client.get(reverse('bac_start_new_round', args=[game.id]))
        self.assertEqual(game.rounds.count(), 1)
        self.client.force_login(self.host)
        self.client.get(reverse('bac_start_new_round', args=[game.id]))
        self.assertEqual(game.rounds.count(), 2)
        self.assertEqual(game.rounds.order_by('round_counter').last().round_counter, 2)

    def test_new_round_requires_login(self):
        game = self.start_game()
        self.client.logout()
        response = self.client.get(reverse('bac_start_new_round', args=[game.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login', response['Location'])

    def test_countdown_flow(self):
        game = self.start_game()
        status_url = reverse('game_countdown_status', args=[game.id])
        self.assertFalse(self.client.get(status_url).json()['countdown_started'])
        data = self.client.get(reverse('game_start_countdown', args=[game.id]), {'type': 'ready_game'}).json()
        self.assertTrue(data['success'])
        self.assertTrue(self.client.get(status_url).json()['countdown_started'])

    def test_play_moves_game_in_progress_and_validates_letter(self):
        game = self.start_game()
        self.client.get(reverse('bac_party_play_games', args=[game.id]))
        game.refresh_from_db()
        self.assertEqual(game.status, 'in_progress')

    def test_unknown_game_ids_return_404(self):
        self.client.force_login(self.host)
        for name in ('bac_party_games', 'bac_party_join_games', 'bac_party_play_games',
                     'bac_party_results_games', 'bac_start_new_round', 'game_countdown_status'):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name, args=[999999])).status_code, 404)


class LittleBacEndGameTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = User.objects.create_user(username='hote', password='pass')
        cls.guest = User.objects.create_user(username='invite', password='pass')
        cls.stranger = User.objects.create_user(username='intrus', password='pass')

    def setUp(self):
        self.game = LittleBacGames.objects.create(name='Partie', author=self.host, status='in_progress')
        self.host_player = LittleBacPlayers.objects.create(game=self.game, user=self.host, score=0)
        self.guest_player = LittleBacPlayers.objects.create(game=self.game, user=self.guest, score=0)
        self.url = reverse('end_game', args=[self.game.id])

    def start_final_countdown(self, seconds_ago):
        self.game.current_phase = 'finish_game'
        self.game.countdown_started = True
        self.game.countdown_time = 60
        self.game.countdown_start_time = timezone.now() - timedelta(seconds=seconds_ago)
        self.game.save()

    def assertStatus(self, status):
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, status)

    def test_get_is_refused(self):
        self.client.force_login(self.host)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertStatus('in_progress')

    def test_anonymous_cannot_end(self):
        self.client.post(self.url)
        self.assertStatus('in_progress')

    def test_stranger_cannot_end(self):
        self.start_final_countdown(seconds_ago=120)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertStatus('in_progress')

    def test_cannot_end_while_players_are_still_playing(self):
        self.client.force_login(self.guest)
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.assertStatus('in_progress')

    def test_cannot_end_before_final_countdown_is_over(self):
        self.start_final_countdown(seconds_ago=10)
        self.client.force_login(self.guest)
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.assertStatus('in_progress')

    def test_player_ends_after_final_countdown(self):
        self.start_final_countdown(seconds_ago=59)
        self.client.force_login(self.guest)
        self.assertTrue(self.client.post(self.url).json()['success'])
        self.assertStatus('finished')
        self.assertFalse(self.game.players.exclude(status='overed').exists())

    def test_player_ends_when_everyone_finished(self):
        LittleBacPlayers.objects.filter(game=self.game).update(status='overed')
        self.client.force_login(self.host)
        self.assertTrue(self.client.post(self.url).json()['success'])
        self.assertStatus('finished')

    def test_ending_twice_is_harmless(self):
        LittleBacPlayers.objects.filter(game=self.game).update(status='overed')
        for user in (self.host, self.guest):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url).status_code, 200)
        self.assertStatus('finished')

    def test_waiting_game_cannot_end(self):
        LittleBacGames.objects.filter(pk=self.game.pk).update(status='waiting')
        LittleBacPlayers.objects.filter(game=self.game).update(status='overed')
        self.client.force_login(self.host)
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.assertStatus('waiting')

    def test_unknown_game(self):
        self.client.force_login(self.host)
        self.assertEqual(self.client.post(reverse('end_game', args=[999999])).status_code, 404)
