from cloudinary_storage.storage import MediaCloudinaryStorage
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url

from .upload_paths import event_poster_upload_path
from .validators import validate_event_poster


class Event(models.Model):
    """A JamSession Lab event that members can register for."""

    venue_name = models.CharField(_("venue name"), max_length=200)
    title = models.CharField(_("title"), max_length=255, editable=False)
    address = models.CharField(_("address"), max_length=500)
    location_url = models.URLField(_("location URL"))
    starts_at = models.DateTimeField(_("starts at"), db_index=True)
    ends_at = models.DateTimeField(_("ends at"))
    poster = models.ImageField(
        _("poster"),
        upload_to=event_poster_upload_path,
        storage=MediaCloudinaryStorage(resource_type="image"),
        blank=True,
        null=True,
        validators=[validate_event_poster],
    )
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    registrations_open = models.BooleanField(_("registrations open"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = _("event")
        verbose_name_plural = _("events")
        indexes = [
            models.Index(fields=["starts_at"]),
        ]

    def __str__(self):
        return self.title or f"JamSession @ {self.venue_name}"

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError(
                {"ends_at": _("End time must be after the start time.")}
            )

    def save(self, *args, **kwargs):
        self.title = f"JamSession @ {self.venue_name}".strip()
        super().save(*args, **kwargs)

    @property
    def is_upcoming(self):
        return self.starts_at > timezone.now()

    @property
    def is_registration_allowed(self):
        return (
            self.is_active
            and self.registrations_open
            and self.starts_at > timezone.now()
        )

    @property
    def display_poster_url(self):
        """Browser-friendly poster URL (converts HEIC on delivery)."""
        return web_image_url(self.poster)
