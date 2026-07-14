from cloudinary.uploader import destroy
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver


def _delete_cloudinary_file(file_value):
    if not file_value:
        return

    public_id = getattr(file_value, "public_id", None)
    if not public_id:
        return

    resource_type = getattr(file_value, "resource_type", "image")
    destroy(public_id, resource_type=resource_type, invalidate=True)


@receiver(pre_save, sender="gallery.GalleryItem")
def delete_old_gallery_file(sender, instance, **kwargs):
    if instance.pk is None:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_file = old_instance.file
    new_file = instance.file

    if not old_file:
        return

    if old_file != new_file:
        _delete_cloudinary_file(old_file)


@receiver(post_delete, sender="gallery.GalleryItem")
def delete_gallery_file_on_remove(sender, instance, **kwargs):
    _delete_cloudinary_file(instance.file)
