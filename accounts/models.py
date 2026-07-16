import uuid

from cloudinary_storage.storage import MediaCloudinaryStorage
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url

from .constants import (
    OTHER_INSTRUMENT_MAX_LENGTH,
    County,
    Instrument,
)
from .upload_paths import profile_picture_upload_path
from .validators import calculate_age, phone_number_validator, validate_profile_picture


class User(AbstractUser):
    # First and last name are required on this site (AbstractUser makes them
    # optional by default).
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)

    # Email is the unique contact address; the registration form also uses it
    # to send the verification link.
    email = models.EmailField(_("email address"), unique=True)

    # Public nickname shown across the site (gallery credits, forum, etc.).
    # Spaces are allowed, unlike Django's username field.
    display_name = models.CharField(
        _("display name"),
        max_length=20,
        unique=True,
        help_text=_("Public nickname, maximum 20 characters including spaces."),
    )

    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        blank=True,
        validators=[phone_number_validator],
        help_text=_(
            "Used to send you an automatic invitation to the community "
            "WhatsApp group."
        ),
    )

    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        storage=MediaCloudinaryStorage(resource_type="image"),
        blank=True,
        null=True,
        validators=[validate_profile_picture],
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text="Used to calculate age automatically.",
    )

    county = models.CharField(
        _("county"),
        max_length=20,
        choices=County.choices,
        blank=True,
    )
    town_city = models.CharField(
        _("town / city"),
        max_length=60,
        blank=True,
    )

    # List of Instrument codes, e.g. ["electric_guitar", "vocals"].
    instruments = models.JSONField(
        _("instruments played"),
        default=list,
        blank=True,
    )
    other_instrument = models.CharField(
        _("other instrument"),
        max_length=OTHER_INSTRUMENT_MAX_LENGTH,
        blank=True,
        help_text=_("Specify your instrument if you selected 'Other'."),
    )

    # List of MusicGenre codes, e.g. ["rock", "blues_rock"].
    preferred_genres = models.JSONField(
        _("preferred music genres"),
        default=list,
        blank=True,
    )
    bio = models.TextField(_("bio"), blank=True)

    # Email verification is prepared but not enforced yet. Once a real SMTP
    # backend is configured, unverified accounts can be restricted by
    # checking this flag.
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )

    # When the user ticked the Terms of Service checkbox at registration.
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    @property
    def age(self):
        if self.date_of_birth is None:
            return None
        return calculate_age(self.date_of_birth)

    @property
    def display_profile_picture_url(self):
        """Browser-friendly profile photo URL (converts HEIC on delivery)."""
        return web_image_url(
            self.profile_picture,
            width=400,
            height=400,
            crop="fill",
        )

    def clean(self):
        super().clean()

        if Instrument.OTHER in (self.instruments or []) and not self.other_instrument:
            raise ValidationError(
                {"other_instrument": _("Please specify your instrument.")}
            )

        if self.county and self.town_city:
            from .constants import TOWNS_BY_COUNTY

            valid_towns = TOWNS_BY_COUNTY.get(self.county, [])
            if valid_towns and self.town_city not in valid_towns:
                raise ValidationError(
                    {
                        "town_city": _(
                            "Please choose a town or city in the selected county."
                        )
                    }
                )

    def get_instruments_display(self):
        """Human-readable list of instruments, with 'Other' spelled out."""
        labels = []
        for code in self.instruments or []:
            if code == Instrument.OTHER and self.other_instrument:
                labels.append(self.other_instrument)
            else:
                labels.append(Instrument(code).label if code in Instrument.values else code)
        return ", ".join(str(label) for label in labels)

    def regenerate_email_verification_token(self):
        """Issue a fresh token, invalidating any previously emailed link."""
        self.email_verification_token = uuid.uuid4()
        self.save(update_fields=["email_verification_token"])

    def __str__(self):
        return self.display_name or self.username
