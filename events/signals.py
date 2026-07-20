from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from jamsession.cloudinary_cleanup import (
    cleanup_file_on_delete,
    cleanup_old_file_on_change,
)


@receiver(pre_save, sender="events.Event")
def delete_old_event_poster(sender, instance, **kwargs):
    cleanup_old_file_on_change(sender, instance, "poster")


@receiver(post_delete, sender="events.Event")
def delete_event_poster_on_remove(sender, instance, **kwargs):
    cleanup_file_on_delete(sender, instance, "poster")
