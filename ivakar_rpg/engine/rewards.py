"""Paliers de niveau RPG qui débloquent des récompenses sur le site."""
from ..models import CharacterReward, LevelReward
from django.urls import reverse

from .character import add_log
from .notifications import notify


def grant_level_rewards(character):
    """Accorde (une seule fois) les paliers atteints. Renvoie les récompenses accordées."""
    from users.leveling import grant_experience
    from users.models import UserInventory

    claimed = CharacterReward.objects.filter(character=character).values_list('reward_id', flat=True)
    granted = []
    rewards = (LevelReward.objects.filter(level__lte=character.level).exclude(pk__in=list(claimed))
               .select_related('shop_item'))
    for reward in rewards:
        _, created = CharacterReward.objects.get_or_create(character=character, reward=reward)
        if not created:
            continue
        if reward.kind == LevelReward.KIND_SITE_ITEM and reward.shop_item_id:
            UserInventory.objects.get_or_create(user=character.user, item=reward.shop_item,
                                                defaults={'quantity': 1})
            add_log(character, f"Récompense sur le site : {reward.shop_item.name} rejoint ton inventaire !", 'good')
            notify(character, 'site_reward', f"{reward.shop_item.name} rejoint ton inventaire du site !",
                   reward.description, reverse('shop_inventory'))
        elif reward.kind == LevelReward.KIND_SITE_XP and reward.site_xp:
            grant_experience(character.user, reward.site_xp, boost=False)
            add_log(character, f"Récompense sur le site : +{reward.site_xp} XP de membre !", 'good')
            notify(character, 'site_reward', f"+{reward.site_xp} XP de membre sur le site !", reward.label,
                   reverse('rpg_rewards'))
        elif reward.kind == LevelReward.KIND_TITLE:
            add_log(character, f"Nouveau titre sur le site : « {reward.label} » !", 'good')
            notify(character, 'site_reward', f"Nouveau titre : « {reward.label} »",
                   "Il s'affiche désormais sur ton profil.", reverse('rpg_sheet'))
        granted.append(reward)
    return granted


def current_title(character, respect_visibility=True):
    """Le titre du plus haut palier atteint, ou ``''`` (masqué si le joueur l'a caché)."""
    if character is None or (respect_visibility and not character.show_title):
        return ''
    entry = (CharacterReward.objects.filter(character=character, reward__kind=LevelReward.KIND_TITLE)
             .select_related('reward').order_by('-reward__level').first())
    return entry.reward.label if entry else ''


def reward_track(character):
    """Tous les paliers, avec ``unlocked`` pour l'affichage."""
    claimed = set(CharacterReward.objects.filter(character=character).values_list('reward_id', flat=True)) \
        if character else set()
    return [{'reward': reward, 'unlocked': reward.pk in claimed}
            for reward in LevelReward.objects.select_related('shop_item')]
