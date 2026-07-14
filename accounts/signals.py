from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender="accounts.User")
def delete_old_profile_picture(sender, instance, **kwargs):
    if instance.pk is None:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_picture = old_instance.profile_picture
    new_picture = instance.profile_picture

    if not old_picture:
        return

    if old_picture != new_picture:
        old_picture.delete(save=False)
