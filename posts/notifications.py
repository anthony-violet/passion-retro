"""Messages privés envoyés au membre quand l'équipe traite sa contribution."""
from django.urls import reverse
from django.utils.text import Truncator

from messagerie.models import PrivateMessage, PrivateMessageSubject
from users.models import User

BOT_USERNAME = 'RetroBot'


def _send(moderator, receiver, subject, message):
    # Inutile de prévenir un modérateur qui traite son propre article.
    if moderator.pk == receiver.pk:
        return None
    # Les notifications sont signées par le robot du site ; à défaut, par le modérateur.
    sender = User.objects.filter(username=BOT_USERNAME).first() or moderator
    thread = PrivateMessageSubject.objects.create(
        receiver=receiver,
        sender=sender,
        subject=Truncator(subject).chars(100),
    )
    PrivateMessage.objects.create(subject=thread, author=sender, message=message)
    return thread


def notify_contribution_approved(post, moderator, chapters_count=0):
    url = reverse('view_post', args=[post.slug])
    kind = 'dossier' if chapters_count or post.child_posts.exists() else 'article'
    if not post.parent:
        kind = 'chapitre'
    lines = [
        f"Bonne nouvelle [b]{post.author.username}[/b] !",
        "",
        f"Ton {kind} [b]« {post.title} »[/b] a été relu et il est maintenant en ligne. 🎉",
    ]
    if chapters_count:
        lines.append(f"{chapters_count} chapitre{'s' if chapters_count > 1 else ''} {'ont' if chapters_count > 1 else 'a'} été publié{'s' if chapters_count > 1 else ''} en même temps.")
    section = post.nav_section if post.parent else None
    if section:
        lines.append(f"Tu le retrouveras dans le menu Magazine › {section.label}.")
    lines += [
        "",
        f"[url={url}]Voir la page publiée[/url]",
        "",
        "Merci pour ta contribution !",
    ]
    return _send(moderator, post.author, f"Ta contribution « {post.title} » est en ligne", "\n".join(lines))


def notify_contribution_rejected(post, moderator, chapters_count=0):
    edit_url = reverse('edit_post', args=[post.post_parent_id or post.pk])
    lines = [
        f"Bonjour [b]{post.author.username}[/b],",
        "",
        f"Ta contribution [b]« {post.title} »[/b] n'a pas pu être publiée en l'état.",
    ]
    if chapters_count:
        lines.append(
            f"Ses {chapters_count} chapitres ont été refusés avec elle." if chapters_count > 1
            else "Son chapitre a été refusé avec elle."
        )
    if post.rejection_reason:
        lines += ["", f"[citation=Motif]{post.rejection_reason}[/citation]"]
    lines += [
        "",
        "Pas d'inquiétude : tu peux la corriger et la renvoyer en relecture quand tu veux.",
        f"[url={edit_url}]Modifier ma contribution[/url]",
    ]
    return _send(moderator, post.author, f"Ta contribution « {post.title} » est à revoir", "\n".join(lines))
