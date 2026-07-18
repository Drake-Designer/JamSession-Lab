from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class RsvpStatus(models.TextChoices):
    REGISTERED = "registered", _("Registered")
    CANCELLED = "cancelled", _("Cancelled")


class AttendanceStatus(models.TextChoices):
    UNKNOWN = "unknown", _("Unknown")
    ATTENDED = "attended", _("Attended")
    NO_SHOW = "no_show", _("No-show")


class EventRegistration(models.Model):
    """One RSVP record per user per event (soft-cancel via rsvp_status)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_registrations",
        verbose_name=_("user"),
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name=_("event"),
    )
    rsvp_status = models.CharField(
        _("RSVP status"),
        max_length=20,
        choices=RsvpStatus.choices,
        default=RsvpStatus.REGISTERED,
    )
    join_open_mic = models.BooleanField(_("join Open Mic"), default=False)
    join_open_jam = models.BooleanField(_("join Open Jam"), default=False)
    wants_originals_in_jam = models.BooleanField(
        _("wants originals in jam"),
        null=True,
        blank=True,
    )
    notes = models.TextField(_("notes"), blank=True)
    instruments_snapshot = models.JSONField(
        _("instruments snapshot"),
        default=list,
        blank=True,
    )
    experience_level_snapshot = models.CharField(
        _("experience level snapshot"),
        max_length=20,
        blank=True,
    )
    attendance_status = models.CharField(
        _("attendance status"),
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.UNKNOWN,
    )
    registered_at = models.DateTimeField(_("registered at"), default=timezone.now)
    first_registered_at = models.DateTimeField(_("first registered at"))
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)

    class Meta:
        verbose_name = _("event registration")
        verbose_name_plural = _("event registrations")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                name="unique_user_event_registration",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "rsvp_status"]),
        ]
        ordering = ["registered_at"]

    def __str__(self):
        return f"{self.user} → {self.event} ({self.rsvp_status})"

    def clean(self):
        super().clean()
        if not self.join_open_mic and not self.join_open_jam:
            raise ValidationError(
                _("Please select at least one session (Open Mic and/or Open Jam).")
            )
        if self.join_open_jam and self.wants_originals_in_jam is None:
            raise ValidationError(
                {
                    "wants_originals_in_jam": _(
                        "Please say whether you have original songs for the jam."
                    )
                }
            )

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.first_registered_at is None:
            self.first_registered_at = now
        if self.registered_at is None:
            self.registered_at = now
        super().save(*args, **kwargs)


class RegistrationSong(models.Model):
    """Original song the member wants to play with others during the jam."""

    registration = models.ForeignKey(
        EventRegistration,
        on_delete=models.CASCADE,
        related_name="songs",
        verbose_name=_("registration"),
    )
    title = models.CharField(_("title"), max_length=200)
    song_key = models.CharField(_("key"), max_length=50)
    basic_chords = models.TextField(_("basic chords"))

    class Meta:
        verbose_name = _("registration song")
        verbose_name_plural = _("registration songs")
        ordering = ["id"]

    def __str__(self):
        return f"{self.title} ({self.song_key})"
