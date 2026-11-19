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


from datetime import timedelta

from django.utils import timezone

from games import mystery
from games.models import MysteryAttempt, MysteryClue, MysteryGame


def _make_mystery(day=None, clues=4, title='The Legend of Zelda', aliases='TLOZ'):
    game = MysteryGame.objects.create(
        title=title, aliases=aliases, publish_date=day or timezone.localdate()
    )
    for i in range(1, clues + 1):
        MysteryClue.objects.create(game=game, order=i, text=f'Indice secret {i}')
    return game


class MysteryAnswerMatchingTest(TestCase):
    def setUp(self):
        self.game = _make_mystery(title='Final Fantasy VII', aliases='FF7\nFinal Fantasy 7')

    def test_accepts_exact_alias_and_variants(self):
        for guess in ['Final Fantasy VII', 'final fantasy 7', 'FF7', 'ff 7', 'Final Fantasy VII !']:
            self.assertTrue(mystery.is_correct(guess, self.game), guess)

    def test_tolerates_small_typo(self):
        self.assertTrue(mystery.is_correct('Final Fantazy VII', self.game))

    def test_rejects_other_games(self):
        for guess in ['Final Fantasy VI', 'Final Fantasy', 'Zelda', '', '   ']:
            self.assertFalse(mystery.is_correct(guess, self.game), guess)

    def test_accents_and_articles_ignored(self):
        game = _make_mystery(day=timezone.localdate() + timedelta(days=1),
                             title='The Legend of Zelda', aliases='')
        self.assertTrue(mystery.is_correct('legend of zelda', game))
        self.assertTrue(mystery.is_correct('Thé Légend of Zelda', game))


class MysteryPlayTest(TestCase):
    def setUp(self):

        self.user = User.objects.create_user(
            username='joueur', email='j@test.com', password='pass12345', active=True
        )
        self.user.levels.create(level=1, experience=0)
        self.game = _make_mystery(clues=4)
        self.client.login(username='joueur', password='pass12345')

    def _attempt(self):
        return MysteryAttempt.objects.get(user=self.user, game=self.game)

    def _gold(self):
        self.user.refresh_from_db()
        return self.user.gold

    def test_only_revealed_clues_are_sent(self):
        response = self.client.get(reverse('mystery_home'))
        self.assertContains(response, 'Indice secret 1')
        self.assertNotContains(response, 'Indice secret 2')
        self.assertNotContains(response, 'Legend of Zelda')

    def test_wrong_guess_reveals_next_clue(self):
        response = self.client.post(reverse('mystery_guess'), {'guess': 'Mario'})
        # On revient directement sur le bloc de jeu, pas en haut de la page.
        self.assertEqual(response['Location'], reverse('mystery_home') + '#partie')
        attempt = self._attempt()
        self.assertEqual(attempt.clues_revealed, 2)
        self.assertEqual(attempt.status, 'playing')
        response = self.client.get(reverse('mystery_home'))
        self.assertContains(response, 'Indice secret 2')
        self.assertNotContains(response, 'Indice secret 3')

    def test_right_guess_rewards_once(self):
        self.client.post(reverse('mystery_reveal'))
        self.client.post(reverse('mystery_guess'), {'guess': 'zelda tloz'})  # faux
        self.client.post(reverse('mystery_guess'), {'guess': 'TLOZ'})
        attempt = self._attempt()
        self.assertEqual(attempt.status, 'won')
        self.assertEqual(attempt.clues_revealed, 3)
        xp, gold = mystery.rewards_for(3, 4)
        self.assertEqual((attempt.xp_earned, attempt.gold_earned), (xp, gold))
        self.assertEqual(self.user.levels.get().experience, xp)
        gold_after_win = self._gold()

        # Rejouer après la victoire ne rapporte plus rien.
        self.client.post(reverse('mystery_guess'), {'guess': 'TLOZ'})
        self.assertEqual(self.user.levels.get().experience, xp)
        self.assertEqual(self._gold(), gold_after_win)

    def test_fewer_clues_means_more_reward(self):
        self.assertGreater(mystery.rewards_for(1, 6), mystery.rewards_for(2, 6))
        self.assertEqual(mystery.rewards_for(6, 6), (mystery.XP_BASE, mystery.GOLD_BASE))

    def test_wrong_guess_on_last_clue_loses(self):
        for _ in range(4):
            self.client.post(reverse('mystery_guess'), {'guess': 'Sonic'})
        attempt = self._attempt()
        self.assertEqual(attempt.status, 'lost')
        self.assertEqual(attempt.xp_earned, 0)
        response = self.client.get(reverse('mystery_home'))
        self.assertContains(response, 'The Legend of Zelda')
        self.assertContains(response, 'Indice secret 4')

    def test_give_up_shows_answer_without_reward(self):
        self.client.post(reverse('mystery_give_up'))
        self.assertEqual(self._attempt().status, 'lost')
        self.assertEqual(self.user.levels.get().experience, 0)

    def test_get_does_not_play(self):
        response = self.client.get(reverse('mystery_guess'))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(MysteryAttempt.objects.exists())

    def test_anonymous_sees_first_clue_but_cannot_play(self):
        self.client.logout()
        response = self.client.get(reverse('mystery_home'))
        self.assertContains(response, 'Indice secret 1')
        self.assertContains(response, 'Connecte-toi pour jouer')
        response = self.client.post(reverse('mystery_guess'), {'guess': 'TLOZ'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MysteryAttempt.objects.exists())

    def test_future_game_not_playable(self):
        self.game.publish_date = timezone.localdate() + timedelta(days=1)
        self.game.save()
        response = self.client.get(reverse('mystery_home'))
        self.assertContains(response, "Pas de jeu mystère aujourd'hui")
        self.assertNotContains(response, 'Indice secret 1')

    def test_archives_hide_today_and_future(self):
        past = _make_mystery(day=timezone.localdate() - timedelta(days=1), title='Tetris', aliases='')
        response = self.client.get(reverse('mystery_archives'))
        self.assertContains(response, past.title)
        self.assertNotContains(response, 'Legend of Zelda')


class MysteryStreakTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='serie', email='s@test.com', password='pass12345', active=True
        )
        today = timezone.localdate()
        self.games = [_make_mystery(day=today - timedelta(days=i), title=f'Jeu {i}', aliases='')
                      for i in range(4)]

    def _win(self, game):
        MysteryAttempt.objects.create(user=self.user, game=game, status='won')

    def test_streak_counts_consecutive_wins_and_today_is_optional(self):
        self._win(self.games[1])
        self._win(self.games[2])
        self.assertEqual(mystery.streak(self.user), 2)
        self._win(self.games[0])
        self.assertEqual(mystery.streak(self.user), 3)

    def test_missed_day_breaks_streak(self):
        self._win(self.games[0])
        self._win(self.games[2])
        self._win(self.games[3])
        self.assertEqual(mystery.streak(self.user), 1)


class MysteryPanelTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin', email='a@test.com', password='pass12345', active=True, is_staff=True
        )
        self.client.login(username='admin', password='pass12345')

    def test_create_game_with_clues_skips_empty_slots(self):
        response = self.client.post(reverse('panel_games_mystery_create'), {
            'title': 'Tetris', 'aliases': 'Тетрис', 'publish_date': '2026-12-01',
            'clue_1_text': 'Sorti en 1984', 'clue_3_text': 'Créé par un Soviétique',
            'clue_6_text': 'Des briques qui tombent',
        })
        self.assertRedirects(response, reverse('panel_games_mystery'))
        game = MysteryGame.objects.get()
        self.assertEqual(list(game.clues.values_list('order', 'text')),
                         [(1, 'Sorti en 1984'), (2, 'Créé par un Soviétique'), (3, 'Des briques qui tombent')])

    def test_same_day_twice_is_refused(self):
        _make_mystery(day=timezone.localdate())
        response = self.client.post(reverse('panel_games_mystery_create'), {
            'title': 'Tetris', 'publish_date': timezone.localdate().isoformat(),
            'clue_1_text': 'a', 'clue_2_text': 'b', 'clue_3_text': 'c',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MysteryGame.objects.count(), 1)

    def test_non_staff_redirected(self):
        self.client.logout()
        response = self.client.get(reverse('panel_games_mystery'))
        self.assertEqual(response.status_code, 302)


def _proposal_data(title='Tetris', **extra):
    data = {'title': title, 'aliases': '', 'clue_1_text': 'Sorti en 1984',
            'clue_2_text': 'Puzzle', 'clue_3_text': 'Des briques qui tombent'}
    data.update(extra)
    return data


class MysteryProposalTest(TestCase):
    def setUp(self):

        User.objects.create_user(username='RetroBot', email='bot@test.com', password='x', active=True)
        self.member = User.objects.create_user(
            username='membre', email='m@test.com', password='pass12345', active=True
        )
        self.member.levels.create(level=1, experience=0)
        self.staff = User.objects.create_user(
            username='modo', email='modo@test.com', password='pass12345', active=True, is_staff=True
        )
        self.client.login(username='membre', password='pass12345')

    def _propose(self, **extra):
        return self.client.post(reverse('mystery_propose'), _proposal_data(**extra))

    def test_member_proposal_is_pending_and_never_scheduled(self):
        response = self._propose(publish_date=timezone.localdate().isoformat())
        self.assertRedirects(response, reverse('mystery_my_proposals'))
        game = MysteryGame.objects.get()
        self.assertEqual((game.status, game.author, game.publish_date), ('pending', self.member, None))
        self.assertEqual(game.clues.count(), 3)
        self.assertIsNone(mystery.today_game())

    def test_needs_minimum_clues(self):
        self.client.post(reverse('mystery_propose'), {'title': 'Tetris', 'clue_1_text': 'x'})
        self.assertFalse(MysteryGame.objects.exists())

    def test_pending_limit(self):
        for i in range(mystery.MAX_PENDING_PROPOSALS):
            self._propose(title=f'Jeu {i}')
        response = self._propose(title='Un de trop')
        self.assertRedirects(response, reverse('mystery_my_proposals'))
        self.assertEqual(MysteryGame.objects.count(), mystery.MAX_PENDING_PROPOSALS)

    def test_cannot_edit_someone_elses_or_approved_proposal(self):
        self._propose()
        game = MysteryGame.objects.get()
        other = User.objects.create_user(username='autre', email='o@test.com', password='pass12345', active=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('mystery_proposal_edit', args=[game.pk])).status_code, 404)
        self.client.force_login(self.member)
        mystery.approve(game, self.staff)
        self.client.post(reverse('mystery_proposal_edit', args=[game.pk]), _proposal_data(title='Changé'))
        game.refresh_from_db()
        self.assertEqual(game.title, 'Tetris')

    def test_approve_rewards_author_once_and_notifies(self):
        from messagerie.models import PrivateMessageSubject

        self._propose()
        game = MysteryGame.objects.get()
        self.client.force_login(self.staff)
        url = reverse('panel_games_mystery_review', args=[game.pk])
        self.client.post(url, {'action': 'approve'})
        self.client.post(url, {'action': 'approve'})
        game.refresh_from_db()
        self.assertEqual(game.status, 'approved')
        self.assertEqual(self.member.levels.get().experience, mystery.XP_PROPOSAL_APPROVED)
        # (RetroBot peut aussi envoyer un message de passage de niveau.)
        self.assertEqual(PrivateMessageSubject.objects.filter(
            receiver=self.member, subject__contains='jeu mystère').count(), 1)

    def test_reject_keeps_reason_and_author_can_resubmit(self):
        self._propose()
        game = MysteryGame.objects.get()
        self.client.force_login(self.staff)
        self.client.post(reverse('panel_games_mystery_review', args=[game.pk]),
                         {'action': 'reject', 'rejection_reason': "L'indice 1 donne la réponse"})
        game.refresh_from_db()
        self.assertEqual((game.status, game.rejection_reason), ('rejected', "L'indice 1 donne la réponse"))
        self.assertEqual(self.member.levels.get().experience, 0)

        self.client.force_login(self.member)
        response = self.client.get(reverse('mystery_my_proposals'))
        self.assertContains(response, "L&#x27;indice 1 donne la réponse")
        self.client.post(reverse('mystery_proposal_edit', args=[game.pk]), _proposal_data(title='Tetris DX'))
        game.refresh_from_db()
        self.assertEqual((game.status, game.title, game.rejection_reason), ('pending', 'Tetris DX', ''))

    def test_panel_refuses_to_schedule_pending_proposal(self):
        self._propose()
        game = MysteryGame.objects.get()
        self.client.force_login(self.staff)
        self.client.post(reverse('panel_games_mystery_edit', args=[game.pk]),
                         _proposal_data(publish_date=timezone.localdate().isoformat()))
        game.refresh_from_db()
        self.assertIsNone(game.publish_date)

    def test_author_cannot_play_own_game(self):
        self._propose()
        game = MysteryGame.objects.get()
        mystery.approve(game, self.staff)
        game.publish_date = timezone.localdate()
        game.save()
        response = self.client.get(reverse('mystery_home'))
        self.assertContains(response, "ton</strong> jeu mystère")
        self.assertNotContains(response, 'name="guess"')
        self.client.post(reverse('mystery_guess'), {'guess': 'Tetris'})
        self.assertFalse(MysteryAttempt.objects.exists())
        self.assertEqual(self.member.levels.get().experience, mystery.XP_PROPOSAL_APPROVED)

        other = User.objects.create_user(username='joueur2', email='j2@test.com', password='pass12345', active=True)
        self.client.force_login(other)
        self.assertContains(self.client.get(reverse('mystery_home')), 'Proposé par membre')


class GamesPagesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='visiteur', email='v@test.com', password='pass12345', active=True
        )
        self.user.levels.create(level=1, experience=0)

    def test_portal_highlights_today_mystery(self):
        _make_mystery()
        response = self.client.get(reverse('portal_games'))
        self.assertContains(response, 'Le jeu mystère du jour')
        self.assertContains(response, reverse('mystery_propose'))
        self.assertNotContains(response, 'Legend of Zelda')

    def test_sidebar_widget_exposes_first_clue_only(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from games.context_processors import mystery_widget

        _make_mystery()
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        widget = mystery_widget(request)['mystery_widget']()
        self.assertEqual(widget['first_clue'].text, 'Indice secret 1')
        self.assertEqual(widget['clues_total'], 4)
        self.assertNotIn('title', widget)

    def test_quiz_home_splits_played_and_unplayed(self):
        from quiz.models import Quiz, UserQuiz

        author = User.objects.create_user(username='auteur', email='a@test.com', password='x', active=True)
        played = Quiz.objects.create(author=author, name='Quiz joué')
        Quiz.objects.create(author=author, name='Quiz neuf')
        UserQuiz.objects.create(user=self.user, quiz=played, score=3)
        self.client.force_login(self.user)
        response = self.client.get(reverse('quiz_home'))
        self.assertEqual([q.name for q in response.context['to_play']], ['Quiz neuf'])
        self.assertEqual([q.name for q in response.context['played']], ['Quiz joué'])
        self.assertContains(response, 'Mon score : 3/0')
