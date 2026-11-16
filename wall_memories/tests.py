from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import User, UserLevel

from .models import Console, Memory, MemoryComment, MemoryFavorite, MemoryReaction
from .services import (
    COMMENT_XP_DAILY_LIMIT,
    XP_COMMENT,
    XP_MEMORY_PUBLISHED,
    era_for_user,
    memory_of_the_day,
)
from .templatetags.wall_memories_tags import plain_excerpt, safe_bbcode
from .views import THEMES

LONG_COMMENT = "Moi aussi ! J'avais Pokémon Bleu et on échangeait nos Pokémon à la récréation avec le câble link."


def make_user(username, **extra):
    return User.objects.create_user(
        username=username, email=f'{username}@test.com', password='pass12345', active=True, **extra
    )


def xp_of(user):
    level = UserLevel.objects.filter(user=user).first()
    return level.experience if level else 0


class WallMemoriesTestCase(TestCase):
    def setUp(self):
        self.author = make_user('conteur')
        self.reader = make_user('lecteur')
        self.staff = make_user('modo', is_staff=True)
        self.snes = Console.objects.get(slug='super-nintendo')

    def publish(self, title='Mon premier Noël avec une Super Nintendo', **extra):
        memory = Memory.objects.create(
            author=self.author,
            title=title,
            content="Je me souviens encore du bruit de la cartouche en l'insérant dans la console.",
            status=Memory.STATUS_PUBLISHED,
            published_at=timezone.now(),
            **extra,
        )
        memory.consoles.add(self.snes)
        return memory


class SeedAndModelTest(WallMemoriesTestCase):
    def test_consoles_are_seeded(self):
        self.assertTrue(Console.objects.filter(name='PlayStation').exists())
        self.assertGreaterEqual(Console.objects.count(), 20)

    def test_slug_and_url(self):
        memory = self.publish()
        self.assertEqual(memory.slug, 'mon-premier-noel-avec-une-super-nintendo')
        self.assertEqual(memory.get_absolute_url(), f'/mur-des-souvenirs/{memory.pk}/{memory.slug}/')


class WallViewTest(WallMemoriesTestCase):
    def test_wall_lists_only_published(self):
        self.publish(title='Souvenir publié')
        Memory.objects.create(author=self.author, title='Souvenir en attente', content='x' * 30)
        response = self.client.get(reverse('wall_memories:wall'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Souvenir publié')
        self.assertNotContains(response, 'Souvenir en attente')

    def test_every_theme_renders_wall_and_detail(self):
        memory = self.publish()
        MemoryComment.objects.create(memory=memory, author=self.reader, content='Trop bien !')
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.reader.theme = theme
                self.reader.save(update_fields=['theme'])
                self.client.force_login(self.reader)
                for url in (
                    reverse('wall_memories:wall'),
                    memory.get_absolute_url(),
                    reverse('wall_memories:create'),
                    reverse('wall_memories:mine'),
                    reverse('wall_memories:favorites'),
                ):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200, f'{theme} {url}')
                    self.assertContains(response, f'wm--{theme}')
                    self.assertContains(response, f'wall_memories/css/{theme}.css')
                wall = self.client.get(reverse('wall_memories:wall'))
                self.assertTemplateUsed(wall, f'wall_memories/{theme}/card.html')
                self.assertTemplateUsed(wall, f'wall_memories/{theme}/form_modal.html')

    def test_publish_modal_has_fields_on_every_page(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        for url in (
            reverse('wall_memories:wall'),
            memory.get_absolute_url(),
            reverse('wall_memories:mine'),
            reverse('wall_memories:favorites'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'id="wm-modal"')
                self.assertContains(response, 'name="title"')
                self.assertContains(response, 'name="content"')
                self.assertContains(response, 'name="consoles"')

    def test_sorts_and_filters(self):
        liked = self.publish(title='Le plus aimé', era=Memory.ERA_80S)
        liked.reactions_count = 10
        liked.save()
        self.publish(title='Le plus récent', era=Memory.ERA_90S)

        response = self.client.get(reverse('wall_memories:wall'), {'tri': 'liked'})
        titles = [m.title for m in response.context['memories']]
        self.assertEqual(titles[0], 'Le plus aimé')

        response = self.client.get(reverse('wall_memories:wall'), {'epoque': '80s'})
        self.assertEqual([m.title for m in response.context['memories']], ['Le plus aimé'])

        response = self.client.get(reverse('wall_memories:wall'), {'console': 'super-nintendo'})
        self.assertEqual(len(response.context['memories']), 2)

        response = self.client.get(reverse('wall_memories:wall'), {'tri': 'random'})
        self.assertEqual(len(response.context['memories']), 2)

    def test_era_sort_uses_birth_date(self):
        self.publish(title='Années 80', era=Memory.ERA_80S)
        self.publish(title='Années 90', era=Memory.ERA_90S)
        self.reader.birth_date = date(1986, 5, 1)
        self.reader.save()
        self.client.force_login(self.reader)
        response = self.client.get(reverse('wall_memories:wall'), {'tri': 'era'})
        self.assertEqual([m.title for m in response.context['memories']], ['Années 90'])

    def test_era_sort_without_birth_date_shows_hint(self):
        self.publish()
        self.client.force_login(self.reader)
        response = self.client.get(reverse('wall_memories:wall'), {'tri': 'era'})
        self.assertTrue(response.context['era_missing'])
        self.assertEqual(len(response.context['memories']), 1)

    def test_random_redirect(self):
        memory = self.publish()
        response = self.client.get(reverse('wall_memories:random'))
        self.assertRedirects(response, memory.get_absolute_url())


class DetailVisibilityTest(WallMemoriesTestCase):
    def test_pending_memory_hidden_from_others(self):
        memory = Memory.objects.create(author=self.author, title='Secret', content='x' * 30)
        url = memory.get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_wrong_slug_redirects(self):
        memory = self.publish()
        response = self.client.get(reverse('wall_memories:detail', args=[memory.pk, 'mauvais']))
        self.assertRedirects(response, memory.get_absolute_url(), status_code=301)

    def test_hidden_comments_not_shown(self):
        memory = self.publish()
        MemoryComment.objects.create(memory=memory, author=self.reader, content='Visible')
        MemoryComment.objects.create(
            memory=memory, author=self.reader, content='Commentaire masqué', status=MemoryComment.STATUS_HIDDEN
        )
        response = self.client.get(memory.get_absolute_url())
        self.assertContains(response, 'Visible')
        self.assertNotContains(response, 'Commentaire masqué')


class CreateAndEditTest(WallMemoriesTestCase):
    def test_login_required(self):
        response = self.client.get(reverse('wall_memories:create'))
        self.assertEqual(response.status_code, 302)

    def test_create_goes_to_moderation(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('wall_memories:create'), {
            'title': 'GoldenEye le mercredi',
            'content': 'Les mercredis après-midi chez mon meilleur pote sur GoldenEye 007.',
            'consoles': [Console.objects.get(slug='nintendo-64').pk],
            'era': '90s',
            'question': 'Vous jouiez avec quel personnage ?',
        })
        self.assertRedirects(response, reverse('wall_memories:mine'))
        memory = Memory.objects.get(title='GoldenEye le mercredi')
        self.assertEqual(memory.status, Memory.STATUS_PENDING)
        self.assertEqual(memory.author, self.author)
        self.assertEqual(list(memory.consoles.values_list('slug', flat=True)), ['nintendo-64'])
        self.assertEqual(xp_of(self.author), 0)

    def test_invalid_form_rerenders(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('wall_memories:create'), {'title': 'x', 'content': 'court', 'era': '90s'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Memory.objects.exists())

    def test_inactive_console_not_selectable(self):
        self.snes.is_active = False
        self.snes.save()
        self.client.force_login(self.author)
        self.client.post(reverse('wall_memories:create'), {
            'title': 'Titre valide', 'content': 'Un contenu suffisamment long pour passer.',
            'era': '90s', 'consoles': [self.snes.pk],
        })
        self.assertFalse(Memory.objects.exists())

    def test_rejected_memory_resubmitted_on_edit(self):
        memory = Memory.objects.create(
            author=self.author, title='À revoir', content='x' * 30,
            status=Memory.STATUS_REJECTED, rejection_reason='Trop court',
        )
        self.client.force_login(self.author)
        self.client.post(reverse('wall_memories:edit', args=[memory.pk]), {
            'title': 'À revoir', 'content': 'Une version bien plus détaillée du souvenir.', 'era': '90s',
        })
        memory.refresh_from_db()
        self.assertEqual(memory.status, Memory.STATUS_PENDING)
        self.assertEqual(memory.rejection_reason, '')

    def test_member_cannot_edit_published_or_others(self):
        memory = self.publish()
        self.client.force_login(self.author)
        self.assertRedirects(self.client.get(reverse('wall_memories:edit', args=[memory.pk])), memory.get_absolute_url())
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse('wall_memories:edit', args=[memory.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('wall_memories:delete', args=[memory.pk])).status_code, 404)

    def test_author_can_delete(self):
        memory = self.publish()
        self.client.force_login(self.author)
        self.client.post(reverse('wall_memories:delete', args=[memory.pk]))
        self.assertFalse(Memory.objects.filter(pk=memory.pk).exists())


class InteractionsTest(WallMemoriesTestCase):
    def test_reaction_toggle_json(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        url = reverse('wall_memories:react', args=[memory.pk])
        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

        data = self.client.post(url, {'type': 'nostalgia'}, **headers).json()
        self.assertEqual(data, {'active': True, 'count': 1, 'total': 1})
        self.client.post(url, {'type': 'love'}, **headers)
        memory.refresh_from_db()
        self.assertEqual(memory.reactions_count, 2)

        data = self.client.post(url, {'type': 'nostalgia'}, **headers).json()
        self.assertEqual(data['active'], False)
        memory.refresh_from_db()
        self.assertEqual(memory.reactions_count, 1)

    def test_reaction_rejects_unknown_type_and_unpublished(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        url = reverse('wall_memories:react', args=[memory.pk])
        self.assertEqual(self.client.post(url, {'type': 'hack'}).status_code, 400)
        pending = Memory.objects.create(author=self.author, title='Attente', content='x' * 30)
        self.assertEqual(
            self.client.post(reverse('wall_memories:react', args=[pending.pk]), {'type': 'love'}).status_code, 404
        )

    def test_reactions_and_favorites_give_no_xp(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        self.client.post(reverse('wall_memories:react', args=[memory.pk]), {'type': 'love'})
        self.client.post(reverse('wall_memories:favorite', args=[memory.pk]))
        self.assertEqual(xp_of(self.reader), 0)
        self.assertEqual(xp_of(self.author), 0)

    def test_favorite_toggle_and_list(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        url = reverse('wall_memories:favorite', args=[memory.pk])
        self.client.post(url)
        self.assertTrue(MemoryFavorite.objects.filter(memory=memory, user=self.reader).exists())
        response = self.client.get(reverse('wall_memories:favorites'))
        self.assertContains(response, memory.title)
        self.client.post(url)
        self.assertFalse(MemoryFavorite.objects.exists())

    def test_next_redirect_is_safe(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse('wall_memories:favorite', args=[memory.pk]), {'next': 'https://evil.example/'}
        )
        self.assertRedirects(response, memory.get_absolute_url())


class CommentTest(WallMemoriesTestCase):
    def comment(self, memory, content=LONG_COMMENT):
        return self.client.post(reverse('wall_memories:comment', args=[memory.pk]), {'content': content})

    def test_comment_published_immediately_with_xp(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        self.comment(memory)
        memory.refresh_from_db()
        self.assertEqual(memory.comments_count, 1)
        self.assertEqual(MemoryComment.objects.get().status, MemoryComment.STATUS_PUBLISHED)
        self.assertEqual(xp_of(self.reader), XP_COMMENT)

    def test_short_comment_gives_no_xp(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        self.comment(memory, 'Trop bien !')
        self.assertEqual(xp_of(self.reader), 0)

    def test_comment_xp_daily_limit(self):
        memory = self.publish()
        self.client.force_login(self.reader)
        for _ in range(COMMENT_XP_DAILY_LIMIT + 2):
            self.comment(memory)
        self.assertEqual(xp_of(self.reader), XP_COMMENT * COMMENT_XP_DAILY_LIMIT)

    def test_own_memory_comment_gives_no_xp(self):
        memory = self.publish()
        self.client.force_login(self.author)
        self.comment(memory)
        self.assertEqual(xp_of(self.author), 0)

    def test_delete_comment_permissions(self):
        memory = self.publish()
        comment = MemoryComment.objects.create(memory=memory, author=self.reader, content='À supprimer')
        url = reverse('wall_memories:delete_comment', args=[comment.pk])
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.reader)
        self.client.post(url)
        self.assertFalse(MemoryComment.objects.exists())


class SafeBBCodeTest(TestCase):
    def test_html_is_escaped(self):
        html = safe_bbcode('<script>alert(1)</script>[b]gras[/b]')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('<strong>gras</strong>', html)

    def test_javascript_urls_are_neutralised(self):
        self.assertIn('href="#"', safe_bbcode('[url=javascript:alert(1)]x[/url]'))
        self.assertIn('href="https://ok.fr"', safe_bbcode('[url=https://ok.fr]ok[/url]'))

    def test_comment_xss_not_rendered(self):
        author = make_user('xss')
        memory = Memory.objects.create(
            author=author, title='XSS', content='Contenu normal du souvenir.',
            status=Memory.STATUS_PUBLISHED, published_at=timezone.now(),
        )
        MemoryComment.objects.create(memory=memory, author=author, content='<img src=x onerror=alert(1)>')
        response = self.client.get(memory.get_absolute_url())
        self.assertNotContains(response, '<img src=x onerror')

    def test_plain_excerpt(self):
        self.assertEqual(plain_excerpt('[b]Salut[/b]   toi'), 'Salut toi')
        self.assertTrue(plain_excerpt('mot ' * 200, 20).endswith('…'))


class ServicesTest(WallMemoriesTestCase):
    def test_era_for_user(self):
        self.assertIsNone(era_for_user(self.reader))
        for year, era in ((1975, '80s'), (1985, '90s'), (1995, '00s'), (2005, 'other')):
            self.reader.birth_date = date(year, 1, 1)
            self.assertEqual(era_for_user(self.reader), era)

    def test_memory_of_the_day_needs_one_year(self):
        recent = self.publish()
        self.assertIsNone(memory_of_the_day())
        old = self.publish(title='Ancien souvenir')
        Memory.objects.filter(pk=old.pk).update(published_at=timezone.now() - timedelta(days=400))
        self.assertEqual(memory_of_the_day(), old)
        self.assertNotEqual(memory_of_the_day(), recent)


class PanelTest(WallMemoriesTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def test_panel_requires_staff(self):
        self.client.force_login(self.reader)
        self.assertRedirects(self.client.get(reverse('panel_memories')), reverse('home'), fetch_redirect_response=False)

    def test_panel_pages_render(self):
        memory = self.publish()
        comment = MemoryComment.objects.create(memory=memory, author=self.reader, content='Coucou')
        for url in (
            reverse('panel_memories'),
            reverse('panel_memories') + '?status=all',
            reverse('panel_memory_review', args=[memory.pk]),
            reverse('panel_memory_comments'),
            reverse('panel_memory_consoles'),
            reverse('panel_memory_console_create'),
            reverse('panel_memory_console_edit', args=[self.snes.pk]),
            reverse('panel_dashboard'),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(comment.pk)

    def test_approve_publishes_and_grants_xp_once(self):
        memory = Memory.objects.create(author=self.author, title='À valider', content='x' * 30)
        url = reverse('panel_memory_review', args=[memory.pk])
        self.client.post(url, {'action': 'approve'})
        memory.refresh_from_db()
        self.assertEqual(memory.status, Memory.STATUS_PUBLISHED)
        self.assertIsNotNone(memory.published_at)
        self.assertEqual(memory.reviewed_by, self.staff)
        self.assertEqual(xp_of(self.author), XP_MEMORY_PUBLISHED)

        # Masquer puis republier ne redonne pas d'XP.
        self.client.post(url, {'action': 'hide'})
        self.client.post(url, {'action': 'approve'})
        self.assertEqual(xp_of(self.author), XP_MEMORY_PUBLISHED)

    def test_reject_with_reason(self):
        memory = Memory.objects.create(author=self.author, title='Refus', content='x' * 30)
        self.client.post(reverse('panel_memory_review', args=[memory.pk]), {
            'action': 'reject', 'rejection_reason': 'Hors sujet',
        })
        memory.refresh_from_db()
        self.assertEqual(memory.status, Memory.STATUS_REJECTED)
        self.assertEqual(memory.rejection_reason, 'Hors sujet')
        self.assertEqual(xp_of(self.author), 0)

    def test_comment_toggle_updates_counter(self):
        memory = self.publish()
        comment = MemoryComment.objects.create(memory=memory, author=self.reader, content='A masquer')
        memory.refresh_counters()
        self.client.post(reverse('panel_memory_comment_toggle', args=[comment.pk]))
        comment.refresh_from_db()
        memory.refresh_from_db()
        self.assertEqual(comment.status, MemoryComment.STATUS_HIDDEN)
        self.assertEqual(memory.comments_count, 0)

    def test_console_crud(self):
        self.client.post(reverse('panel_memory_console_create'), {
            'name': 'Virtual Boy', 'manufacturer': 'Nintendo', 'release_year': '1995', 'order': '5', 'is_active': 'on',
        })
        console = Console.objects.get(name='Virtual Boy')
        self.assertEqual(console.slug, 'virtual-boy')
        self.assertTrue(console.is_active)

        self.client.post(reverse('panel_memory_console_edit', args=[console.pk]), {
            'name': 'Virtual Boy', 'manufacturer': 'Nintendo', 'release_year': '1995', 'order': '5',
        })
        console.refresh_from_db()
        self.assertFalse(console.is_active)

        self.client.post(reverse('panel_memory_console_create'), {'name': 'virtual boy'})
        self.assertEqual(Console.objects.filter(name__iexact='virtual boy').count(), 1)

        self.client.post(reverse('panel_memory_console_delete', args=[console.pk]))
        self.assertFalse(Console.objects.filter(pk=console.pk).exists())

    def test_used_console_is_deactivated_not_deleted(self):
        self.publish()
        self.client.post(reverse('panel_memory_console_delete', args=[self.snes.pk]))
        self.snes.refresh_from_db()
        self.assertFalse(self.snes.is_active)

    def test_reaction_model_emoji(self):
        memory = self.publish()
        reaction = MemoryReaction.objects.create(memory=memory, user=self.reader, type=MemoryReaction.SAME)
        self.assertEqual(reaction.emoji, '🎮')


class SeoTest(WallMemoriesTestCase):
    def test_sitemap_lists_wall_and_only_published_memories(self):
        published = self.publish(title='Souvenir indexable')
        pending = Memory.objects.create(author=self.author, title='En attente', content='x' * 30)
        hidden = self.publish(title='Masqué')
        hidden.status = Memory.STATUS_HIDDEN
        hidden.save()

        xml = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('/mur-des-souvenirs/</loc>', xml)
        self.assertIn(published.get_absolute_url(), xml)
        self.assertNotIn(f'/mur-des-souvenirs/{pending.pk}/', xml)
        self.assertNotIn(f'/mur-des-souvenirs/{hidden.pk}/', xml)

    def test_robots_blocks_personal_and_action_pages(self):
        robots = self.client.get('/robots.txt').content.decode()
        for path in ('partager/', 'mes-souvenirs/', 'mes-favoris/', 'au-hasard/'):
            self.assertIn(f'Disallow: /mur-des-souvenirs/{path}', robots)
        self.assertNotIn('Disallow: /mur-des-souvenirs/\n', robots)


class PromotionTest(WallMemoriesTestCase):
    def test_discover_shows_latest_memories(self):
        memory = self.publish(title='Souvenir sur Découvrir')
        response = self.client.get(reverse('discover'))
        self.assertContains(response, 'Le Mur des souvenirs')
        self.assertContains(response, memory.get_absolute_url())
        self.assertContains(response, 'Raconter un souvenir')

    def test_home_features_latest_memory(self):
        memory = self.publish(title='Souvenir mis en avant')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Le dernier souvenir partagé')
        self.assertContains(response, memory.get_absolute_url())

    def test_home_without_memories(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('wall_memories:wall'))


class AuthorRetroBadgeTest(WallMemoriesTestCase):
    def test_detail_shows_author_retro_badge(self):
        self.author.favorite_console = 'NES, Game Boy'
        self.author.favorite_game = 'Tetris'
        self.author.save()
        memory = self.publish()
        response = self.client.get(memory.get_absolute_url())
        self.assertContains(response, 'member-retro-badge')
        self.assertContains(response, '🎮 NES')
        self.assertContains(response, '🕹️ Tetris')
