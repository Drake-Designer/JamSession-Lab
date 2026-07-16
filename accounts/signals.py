from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from jamsession.cloudinary_cleanup import (
    cleanup_file_on_delete,
    cleanup_old_file_on_change,
)


@receiver(pre_save, sender="accounts.User")
def delete_old_profile_picture(sender, instance, **kwargs):
    cleanup_old_file_on_change(sender, instance, "profile_picture")


@receiver(post_delete, sender="accounts.User")
def delete_profile_picture_on_remove(sender, instance, **kwargs):
    cleanup_file_on_delete(sender, instance, "profile_picture")
