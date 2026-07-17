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
