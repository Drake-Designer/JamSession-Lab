from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from jamsession.cloudinary_cleanup import (
    cleanup_file_on_delete,
    cleanup_old_file_on_change,
)


@receiver(pre_save, sender="gallery.GalleryItem")
def delete_old_gallery_file(sender, instance, **kwargs):
    cleanup_old_file_on_change(sender, instance, "file")


@receiver(post_delete, sender="gallery.GalleryItem")
def delete_gallery_file_on_remove(sender, instance, **kwargs):
    cleanup_file_on_delete(sender, instance, "file")
