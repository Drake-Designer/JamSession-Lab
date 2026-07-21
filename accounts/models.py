import math
import uuid
from collections import namedtuple
from datetime import timedelta

from cloudinary_storage.storage import MediaCloudinaryStorage
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url

from .constants import (
    OTHER_GENRE_MAX_LENGTH,
    OTHER_INSTRUMENT_MAX_LENGTH,
    County,
    ExperienceLevel,
    Instrument,
    MusicGenre,
)
from .upload_paths import profile_picture_upload_path
from .validators import (
    MAX_YEARS_OF_EXPERIENCE,
    calculate_age,
    experience_started_year_from_years,
    phone_number_validator,
    validate_profile_picture,
    validate_years_of_experience_against_age,
    years_of_experience_from_started_year,
)


# Single source of truth for public membership badges (label + CSS class).
BadgeInfo = namedtuple("BadgeInfo", ["label", "css_class"])
MEMBER_BADGE_DAYS = 30

# Fields that count toward profile completion (equal weight). Labels match
# ProfileEditForm / edit template wording for highlight UI consistency.
PROFILE_COMPLETION_FIELDS = (
    ("profile_picture", _("Profile picture")),
    ("display_name", _("Display Name")),
    ("phone_number", _("Phone number")),
    ("county", _("County")),
    ("town_city", _("Town / City")),
    ("instruments", _("Instruments played")),
    ("preferred_genres", _("Preferred music genres")),
    ("years_of_experience", _("Years of experience")),
    ("experience_level", _("Experience level")),
    ("bio", _("Bio")),
    ("social_links", _("Social / music links")),
)


class User(AbstractUser):
    # First and last name are required on this site (AbstractUser makes them
    # optional by default).
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)

    # Email is the unique contact address; the registration form also uses it
    # to send the verification link.
    email = models.EmailField(_("email address"), unique=True)

    # Set while a verified member confirms a new address. Login keeps using
    # ``email`` until the pending address is verified via the emailed link.
    pending_email = models.EmailField(
        _("pending email address"),
        blank=True,
        help_text=_(
            "New email awaiting confirmation. Empty when no change is in progress."
        ),
    )

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
        max_length=15,
        blank=True,
        validators=[phone_number_validator],
        help_text=_(
            "Private contact number. Never shown on the public profile — "
            "used only to send an automatic invitation to the community "
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
    # Percentages (0–100) for CSS object-position when the photo is cropped
    # to a circle — set only when uploading / replacing the picture.
    profile_picture_focus_x = models.FloatField(
        _("profile picture focus X"),
        default=50,
        help_text=_(
            "Horizontal focal point as a percentage (0 = left, 100 = right)."
        ),
    )
    profile_picture_focus_y = models.FloatField(
        _("profile picture focus Y"),
        default=50,
        help_text=_(
            "Vertical focal point as a percentage (0 = top, 100 = bottom)."
        ),
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text="Used to calculate age automatically.",
    )

    # Public profile privacy — all default to hidden for visitors.
    # The owner always sees their own data on their profile.
    show_age_publicly = models.BooleanField(
        _("show age publicly"),
        default=False,
        help_text=_("If enabled, your age (not date of birth) is visible on your public profile."),
    )
    show_phone_publicly = models.BooleanField(
        _("show phone publicly"),
        default=False,
        help_text=_(
            "Unused: phone numbers are never shown on public profiles. "
            "Kept for database compatibility."
        ),
    )
    show_location_publicly = models.BooleanField(
        _("show location publicly"),
        default=False,
        help_text=_("If enabled, your town and county are visible on your public profile."),
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
    other_genre = models.CharField(
        _("other genre"),
        max_length=OTHER_GENRE_MAX_LENGTH,
        blank=True,
        help_text=_("Specify your genre if you selected 'Other'."),
    )

    # Stored as the calendar year the musician started playing. Public
    # "years of experience" is derived as current_year - this value, so it
    # increases automatically every 1 January without a cron job.
    experience_started_year = models.PositiveSmallIntegerField(
        _("experience started year"),
        blank=True,
        null=True,
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(2100),
        ],
        help_text=_(
            "Calendar year the musician started playing. Years of experience "
            "are calculated from this value and increase each 1 January."
        ),
    )
    experience_level = models.CharField(
        _("experience level"),
        max_length=20,
        choices=ExperienceLevel.choices,
        blank=True,
    )

    bio = models.TextField(_("bio"), blank=True)

    # Unverified members are soft-blocked by EmailVerificationMiddleware
    # until they confirm via the emailed link (or staff sets this in admin).
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    email_verification_send_count = models.PositiveSmallIntegerField(
        _("verification emails sent"),
        default=0,
        help_text=_(
            "How many verification emails have been sent while this account "
            "is still unverified. After the limit, the member must contact "
            "JamSession Lab for manual activation."
        ),
    )

    # When the user ticked the Terms of Service checkbox at registration.
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    force_member_badge = models.BooleanField(
        _("force Member badge"),
        default=False,
        help_text=_(
            "If enabled, shows 'Member' badge instead of 'New Member' even if "
            "joined less than 30 days ago."
        ),
    )

    # Admin-only: hide from the community members sidebar without disabling login.
    hide_from_members_list = models.BooleanField(
        _("hide from members list"),
        default=False,
        help_text=_(
            "If enabled, this user is omitted from the community members sidebar. "
            "They can still log in and use the site normally."
        ),
    )

    @property
    def age(self):
        if self.date_of_birth is None:
            return None
        return calculate_age(self.date_of_birth)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse(
            "accounts:profile_detail",
            kwargs={"username": self.username},
        )

    @property
    def has_pending_email_change(self):
        """True when the member must confirm a new email address."""
        return bool((self.pending_email or "").strip())

    def clear_pending_email(self, *, save=True):
        """Drop an in-progress email change without touching the current email."""
        self.pending_email = ""
        if save:
            self.save(update_fields=["pending_email"])

    def apply_pending_email(self):
        """
        Move ``pending_email`` into ``email`` after the confirmation link is opened.

        Returns the new email on success, or None if there was nothing to apply
        or the address is no longer available.
        """
        new_email = (self.pending_email or "").strip()
        if not new_email:
            return None

        conflict = (
            User.objects.filter(email__iexact=new_email)
            .exclude(pk=self.pk)
            .exists()
        )
        if conflict:
            return None

        self.email = new_email
        self.pending_email = ""
        self.is_email_verified = True
        self.save(update_fields=["email", "pending_email", "is_email_verified"])
        return new_email

    @property
    def years_of_experience(self):
        """
        Playing experience in full calendar years.

        Increases automatically on 1 January each year (e.g. 10 in 2026 → 11
        in 2027) because it is derived from experience_started_year.
        """
        return years_of_experience_from_started_year(self.experience_started_year)

    @years_of_experience.setter
    def years_of_experience(self, years):
        """Accept a declared years value and store the matching start year."""
        if years is None:
            self.experience_started_year = None
            return
        years = int(years)
        if years < 0 or years > MAX_YEARS_OF_EXPERIENCE:
            raise ValidationError(
                _(
                    "Years of experience must be between 0 and %(max)s."
                )
                % {"max": MAX_YEARS_OF_EXPERIENCE}
            )
        validate_years_of_experience_against_age(years, self.date_of_birth)
        self.experience_started_year = experience_started_year_from_years(years)

    @property
    def badge_info(self):
        """
        Public membership badge for this user.

        Precedence (strict, no exceptions):
        1. superuser → Founder
        2. staff (non-superuser) → STAFF
        3. force_member_badge or joined ≥ 30 days → Member
        4. otherwise → New Member
        """
        if self.is_superuser:
            return BadgeInfo(label="Founder", css_class="badge-founder")
        if self.is_staff:
            return BadgeInfo(label="STAFF", css_class="badge-staff")
        joined_at = self.date_joined or timezone.now()
        is_established = (timezone.now() - joined_at) >= timedelta(
            days=MEMBER_BADGE_DAYS
        )
        if self.force_member_badge or is_established:
            return BadgeInfo(label="Member", css_class="badge-member")
        return BadgeInfo(label="New Member", css_class="badge-new-member")

    @property
    def public_display_name(self):
        """Name shown publicly; falls back to username if display_name is blank."""
        name = (self.display_name or "").strip()
        return name or self.username

    @property
    def display_profile_picture_url(self):
        """
        Browser-friendly profile photo URL — scaled, not hard-cropped.

        Cropping is done in CSS with object-fit/object-position so
        profile_picture_focus_x/y still apply on circular avatars.
        """
        if not self.profile_picture:
            return ""
        return web_image_url(
            self.profile_picture,
            width=640,
            crop="limit",
            quality="auto",
        )

    @property
    def profile_picture_focus_style(self):
        """CSS object-position value derived from the stored focal point."""
        return (
            f"{self.profile_picture_focus_x:g}% "
            f"{self.profile_picture_focus_y:g}%"
        )

    def _profile_field_is_complete(self, field_key):
        """Return True when a completion-tracked field has a usable value."""
        if field_key == "profile_picture":
            return bool(self.profile_picture)
        if field_key == "display_name":
            return bool((self.display_name or "").strip())
        if field_key == "phone_number":
            return bool((self.phone_number or "").strip())
        if field_key == "county":
            return bool(self.county)
        if field_key == "town_city":
            return bool((self.town_city or "").strip())
        if field_key == "instruments":
            return bool(self.instruments)
        if field_key == "preferred_genres":
            return bool(self.preferred_genres)
        if field_key == "years_of_experience":
            # 0 years is a valid answer — only a missing start year counts.
            return self.experience_started_year is not None
        if field_key == "experience_level":
            return bool(self.experience_level)
        if field_key == "bio":
            return bool((self.bio or "").strip())
        if field_key == "social_links":
            # Prefer the prefetched cache when profile_detail loaded it.
            return any(True for _ in self.social_links.all())
        return False

    @property
    def profile_completion_percentage(self):
        """
        Share of profile fields that are filled, rounded to the nearest int.

        Every field in PROFILE_COMPLETION_FIELDS has equal weight.
        """
        total = len(PROFILE_COMPLETION_FIELDS)
        if total == 0:
            return 100
        filled = sum(
            1
            for field_key, _label in PROFILE_COMPLETION_FIELDS
            if self._profile_field_is_complete(field_key)
        )
        return round((filled / total) * 100)

    @property
    def profile_completion_dashoffset(self):
        """
        SVG stroke-dashoffset for the 60px progress ring (radius 26).

        Full circle = 0 offset; empty = full circumference.
        """
        circumference = 2 * math.pi * 26
        return round(
            circumference * (1 - self.profile_completion_percentage / 100),
            4,
        )

    @property
    def missing_field_keys(self):
        """Machine names of incomplete profile fields (for form highlighting)."""
        return [
            field_key
            for field_key, _label in PROFILE_COMPLETION_FIELDS
            if not self._profile_field_is_complete(field_key)
        ]

    @property
    def missing_fields(self):
        """Human-readable labels of incomplete profile fields."""
        return [
            str(label)
            for field_key, label in PROFILE_COMPLETION_FIELDS
            if not self._profile_field_is_complete(field_key)
        ]

    def clean(self):
        super().clean()

        if Instrument.OTHER in (self.instruments or []) and not self.other_instrument:
            raise ValidationError(
                {"other_instrument": _("Please specify your instrument.")}
            )

        if MusicGenre.OTHER in (self.preferred_genres or []) and not self.other_genre:
            raise ValidationError(
                {"other_genre": _("Please specify your genre.")}
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
                labels.append(
                    Instrument(code).label if code in Instrument.values else code
                )
        return ", ".join(str(label) for label in labels)

    def get_genres_display(self):
        """Human-readable list of preferred genres, with 'Other' spelled out."""
        labels = []
        for code in self.preferred_genres or []:
            if code == MusicGenre.OTHER and self.other_genre:
                labels.append(self.other_genre)
            else:
                labels.append(
                    MusicGenre(code).label if code in MusicGenre.values else code
                )
        return ", ".join(str(label) for label in labels)

    def regenerate_email_verification_token(self):
        """Issue a fresh token, invalidating any previously emailed link."""
        self.email_verification_token = uuid.uuid4()
        self.save(update_fields=["email_verification_token"])

    def has_exhausted_verification_emails(self, limit: int) -> bool:
        """True when no more verification emails may be sent for this user."""
        return self.email_verification_send_count >= limit

    def record_verification_email_sent(self) -> None:
        """Increment the verification-email counter (concurrency-safe)."""
        type(self).objects.filter(pk=self.pk).update(
            email_verification_send_count=F("email_verification_send_count") + 1
        )
        self.refresh_from_db(fields=["email_verification_send_count"])

    def __str__(self):
        return self.display_name or self.username

    class Meta:
        constraints = [
            # Allow many blank phones (incomplete profiles); enforce uniqueness
            # only when a real number is stored.
            models.UniqueConstraint(
                fields=["phone_number"],
                condition=~models.Q(phone_number=""),
                name="accounts_user_nonempty_phone_uniq",
            ),
        ]


class SocialLink(models.Model):
    """
    One social / music profile URL belonging to a user.

    Multiple rows per user are allowed (Instagram + Spotify + …). Display
    order on the public profile follows the ``order`` field.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_links",
        verbose_name=_("user"),
    )
    url = models.URLField(_("URL"), max_length=200)
    order = models.PositiveSmallIntegerField(_("order"), default=0, db_index=True)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = _("social / music link")
        verbose_name_plural = _("social / music links")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "url"],
                name="accounts_sociallink_user_url_uniq",
            ),
        ]

    def __str__(self):
        return self.url
