from django.db import models
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url

from .upload_paths import about_organiser_upload_path, home_carousel_upload_path
from .validators import validate_carousel_image, validate_organiser_photo


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


class AboutOrganiser(models.Model):
    """Organiser card shown on the public About page (Meet the Organisers)."""

    name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=120,
        help_text=_("Short role label, e.g. Founder or Sound Engineer."),
    )
    bio = models.TextField(
        help_text=_("Short biography shown under the name."),
    )
    initials = models.CharField(
        max_length=3,
        help_text=_(
            "Shown as a placeholder when no photo is uploaded (e.g. D, R, De)."
        ),
    )
    photo = models.ImageField(
        upload_to=about_organiser_upload_path,
        blank=True,
        help_text=_("Optional profile photo. Replacing it deletes the previous file."),
        validators=[validate_organiser_photo],
    )
    # Percentages (0–100) for CSS object-position when the photo is cropped
    # to a circle — so admins can keep faces centred.
    photo_focus_x = models.FloatField(
        _("photo focus X"),
        default=50,
        help_text=_("Horizontal focal point as a percentage (0 = left, 100 = right)."),
    )
    photo_focus_y = models.FloatField(
        _("photo focus Y"),
        default=50,
        help_text=_("Vertical focal point as a percentage (0 = top, 100 = bottom)."),
    )
    order = models.PositiveIntegerField(
        _("order"),
        default=0,
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Inactive organisers are hidden from the public About page."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        verbose_name = _("organiser")
        verbose_name_plural = _("organisers")

    def __str__(self):
        return self.name

    @property
    def display_photo_url(self):
        """
        Browser-friendly photo URL — scaled, not hard-cropped.

        Cropping is done in CSS with object-fit/object-position so
        photo_focus_x/y still apply on the About page.
        """
        if not self.photo:
            return ""
        return web_image_url(self.photo, width=640, crop="limit", quality="auto")

    @property
    def photo_focus_style(self):
        """CSS object-position value derived from the stored focal point."""
        return f"{self.photo_focus_x:g}% {self.photo_focus_y:g}%"
