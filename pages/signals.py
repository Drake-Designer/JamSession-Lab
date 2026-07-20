from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from jamsession.cloudinary_cleanup import (
    cleanup_file_on_delete,
    cleanup_old_file_on_change,
)

from .models import AboutOrganiser, HomeCarouselSlide


@receiver(pre_save, sender=HomeCarouselSlide)
def delete_old_carousel_image(sender, instance, **kwargs):
    """Remove the previous Cloudinary asset when the slide image is replaced."""
    cleanup_old_file_on_change(sender, instance, "image")


@receiver(post_delete, sender=HomeCarouselSlide)
def delete_carousel_image_on_remove(sender, instance, **kwargs):
    """Remove the Cloudinary asset when a slide is deleted (including bulk delete)."""
    cleanup_file_on_delete(sender, instance, "image")


@receiver(pre_save, sender=AboutOrganiser)
def delete_old_organiser_photo(sender, instance, **kwargs):
    """Remove the previous Cloudinary asset when the organiser photo is replaced."""
    cleanup_old_file_on_change(sender, instance, "photo")


@receiver(post_delete, sender=AboutOrganiser)
def delete_organiser_photo_on_remove(sender, instance, **kwargs):
    """Remove the Cloudinary asset when an organiser is deleted (including bulk delete)."""
    cleanup_file_on_delete(sender, instance, "photo")
