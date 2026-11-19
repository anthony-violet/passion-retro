"""Noms des groupes d'utilisateurs : seule source de vérité pour tout le site."""

ADMIN_GROUP = 'Administrateur'
SUPER_ADMIN_GROUP = 'Super Admin'
MODERATOR_GROUP = 'Modérateur'
EDITOR_GROUP = 'Rédacteur'

# Administration du site
ADMIN_GROUPS = (ADMIN_GROUP, SUPER_ADMIN_GROUP)
# Modération du forum (verrouiller, désactiver, éditer les messages des autres)
FORUM_MODERATOR_GROUPS = (MODERATOR_GROUP, ADMIN_GROUP, SUPER_ADMIN_GROUP)
# Rédaction d'articles
EDITOR_GROUPS = (EDITOR_GROUP, ADMIN_GROUP, SUPER_ADMIN_GROUP)

# Anciennes orthographes rencontrées dans le code, fusionnées dans ADMIN_GROUP.
LEGACY_ADMIN_NAMES = ('Administrateurs', 'Admininistrateur')


def is_in_groups(user, group_names):
    return bool(
        user.is_authenticated
        and user.groups.filter(name__in=group_names).exists()
    )
