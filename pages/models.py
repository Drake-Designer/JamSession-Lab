from django.db import models
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url

from .upload_paths import home_carousel_upload_path
from .validators import validate_carousel_image


class HomeCarouselSlide(models.Model):
    image = models.ImageField(
        upload_to=home_carousel_upload_path,
        help_text=_("Displayed in the home page carousel."),
        validators=[validate_carousel_image],
    )
    alt_text = models.CharField(
        max_length=255,
        help_text=_("Describe the image for screen readers and SEO."),
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional short text shown over the slide."),
    )
    order = models.PositiveIntegerField(
        _("order"),
        default=0,
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Inactive slides are hidden from the public home page."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        verbose_name = _("carousel slide")
        verbose_name_plural = _("carousel slides")

    def __str__(self):
        return self.alt_text

    @property
    def display_image_url(self):
        """Browser-friendly carousel image URL (converts HEIC on delivery)."""
        return web_image_url(self.image)
