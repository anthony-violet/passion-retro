"""Un objet de collection qui quitte l'inventaire disparaît aussi du profil et des messages."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


def _forget(entry):
    from users.models import User

    User.objects.filter(pk=entry.user_id, featured_collectible_id=entry.item_id).update(featured_collectible=None)


def connect():
    from users.models import UserInventory

    @receiver(post_delete, sender=UserInventory, weak=False, dispatch_uid='shop_forget_deleted_entry')
    def entry_deleted(sender, instance, **kwargs):
        _forget(instance)

    @receiver(post_save, sender=UserInventory, weak=False, dispatch_uid='shop_forget_empty_entry')
    def entry_saved(sender, instance, **kwargs):
        if instance.quantity <= 0:
            _forget(instance)
            if instance.showcased:
                sender.objects.filter(pk=instance.pk).update(showcased=False)
