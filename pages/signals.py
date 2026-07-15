from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import HomeCarouselSlide


def _delete_carousel_image(image_field):
    if not image_field:
        return

    image_field.delete(save=False)


@receiver(pre_save, sender=HomeCarouselSlide)
def delete_old_carousel_image(sender, instance, **kwargs):
    """Remove the previous Cloudinary asset when the slide image is replaced."""
    if instance.pk is None:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_image = old_instance.image
    new_image = instance.image

    if not old_image:
        return

    if old_image != new_image:
        _delete_carousel_image(old_image)


@receiver(post_delete, sender=HomeCarouselSlide)
def delete_carousel_image_on_remove(sender, instance, **kwargs):
    """Remove the Cloudinary asset when a slide is deleted (including bulk delete)."""
    _delete_carousel_image(instance.image)
