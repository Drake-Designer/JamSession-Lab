from django.db import models
from django.utils.translation import gettext_lazy as _

from .upload_paths import home_carousel_upload_path


class SlideType(models.TextChoices):
    EVENT_HIGHLIGHT = "event_highlight", _("Event highlight")
    GENERIC = "generic", _("Generic")


class HomeCarouselSlide(models.Model):
    image = models.ImageField(
        upload_to=home_carousel_upload_path,
        help_text=_("Displayed in the home page carousel."),
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
    slide_type = models.CharField(
        max_length=20,
        choices=SlideType.choices,
        default=SlideType.GENERIC,
        help_text=_("Helps you organise slides in the admin panel."),
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
