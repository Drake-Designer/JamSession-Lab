from datetime import date

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .upload_paths import profile_picture_upload_path


class Instrument(models.TextChoices):
    GUITAR = "guitar", "Guitar"
    BASS = "bass", "Bass"
    DRUMS = "drums", "Drums"
    VOCALS = "vocals", "Vocals"
    KEYS = "keys", "Keys"
    OTHER = "other", "Other"


class User(AbstractUser):
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        blank=True,
        null=True,
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text="Used to calculate age automatically.",
    )
    instrument = models.CharField(
        max_length=20,
        choices=Instrument.choices,
    )
    instrument_other = models.CharField(
        max_length=50,
        blank=True,
        help_text="Specify your instrument if you selected 'Other'.",
    )
    favourite_genre = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)

    @property
    def age(self):
        if self.date_of_birth is None:
            return None

        today = date.today()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (
            self.date_of_birth.month,
            self.date_of_birth.day,
        ):
            years -= 1
        return years

    def clean(self):
        super().clean()
        if self.instrument == Instrument.OTHER and not self.instrument_other:
            raise ValidationError(
                {
                    "instrument_other": "Please specify your instrument.",
                }
            )

    def get_instrument_display_full(self):
        if self.instrument == Instrument.OTHER:
            return self.instrument_other
        return self.get_instrument_display()

    def __str__(self):
        return self.username
