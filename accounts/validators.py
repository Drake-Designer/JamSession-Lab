from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator, RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from jamsession.image_formats import IMAGE_EXTENSIONS_INCLUDING_HEIC

MINIMUM_REGISTRATION_AGE = 18

UNDERAGE_ERROR_MESSAGE = _("You must be at least 18 years old to register.")

MAX_PROFILE_PICTURE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

PROFILE_PICTURE_TOO_LARGE_MESSAGE = _(
    "Profile picture must be smaller than 10MB. Please choose a smaller "
    "photo or compress it before uploading."
)

# Digits only, optional leading + for the country code (e.g. +353871234567).
# Model max_length=15 caps the full string length.
phone_number_validator = RegexValidator(
    regex=r"^\+?[0-9]{7,15}$",
    message=_(
        "Enter a valid phone number using digits only, with an optional "
        "leading + for the country code (e.g. +353871234567)."
    ),
)

_profile_picture_extension_validator = FileExtensionValidator(
    allowed_extensions=IMAGE_EXTENSIONS_INCLUDING_HEIC,
)


def validate_profile_picture(value):
    """
    Validate new profile picture uploads only.

    Existing Cloudinary ImageField values are stored as public IDs without a
    file extension, so re-validating them would break profile edits that do
    not replace the photo.
    """
    if value is None or not isinstance(value, UploadedFile):
        return

    _profile_picture_extension_validator(value)

    if value.size > MAX_PROFILE_PICTURE_SIZE_BYTES:
        raise ValidationError(PROFILE_PICTURE_TOO_LARGE_MESSAGE)


def calculate_age(date_of_birth, today=None):
    """Return full years between date_of_birth and today."""
    if today is None:
        today = timezone.localdate()

    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def validate_minimum_age(date_of_birth):
    """Block registration for anyone under 18 (self-certified via date of birth)."""
    if date_of_birth is None:
        return

    if date_of_birth > timezone.localdate():
        raise ValidationError(_("Date of birth cannot be in the future."))

    if calculate_age(date_of_birth) < MINIMUM_REGISTRATION_AGE:
        raise ValidationError(UNDERAGE_ERROR_MESSAGE)


YEARS_OF_EXPERIENCE_EXCEED_AGE_MESSAGE = _(
    "Years of experience cannot exceed your age."
)

MAX_YEARS_OF_EXPERIENCE = 80


def experience_started_year_from_years(years, today=None):
    """
    Convert a declared years-of-experience value into a calendar start year.

    Example: 10 years declared in 2026 → started in 2016. On 1 January 2027
    the computed years become 11 automatically.
    """
    if years is None:
        return None
    if today is None:
        today = timezone.localdate()
    return today.year - int(years)


def years_of_experience_from_started_year(started_year, today=None):
    """Return full calendar years of experience from a start year."""
    if started_year is None:
        return None
    if today is None:
        today = timezone.localdate()
    return max(0, today.year - int(started_year))


def validate_years_of_experience_against_age(years, date_of_birth, today=None):
    """Reject experience that would imply playing before the user was born."""
    if years is None or date_of_birth is None:
        return
    if today is None:
        today = timezone.localdate()
    age = calculate_age(date_of_birth, today=today)
    if years > age:
        raise ValidationError(YEARS_OF_EXPERIENCE_EXCEED_AGE_MESSAGE)
