from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator

from jamsession.image_formats import IMAGE_EXTENSIONS_INCLUDING_HEIC, is_heic_upload

_extension_validator = FileExtensionValidator(
    allowed_extensions=IMAGE_EXTENSIONS_INCLUDING_HEIC,
)


def validate_carousel_image(value):
    """
    Validate carousel uploads on new files only.

    Existing Cloudinary ImageField values are stored as public IDs without a
    file extension (e.g. ``JamSession Lab/site/home_carousel/photo_abc``).
    Re-validating them with FileExtensionValidator breaks admin edits that
    change caption/alt text without re-uploading the image.
    """
    if value is None:
        return

    if not isinstance(value, UploadedFile):
        return

    _extension_validator(value)


def validate_carousel_image_upload(uploaded_file):
    """Admin form helper — reject non-image uploads for new files."""
    if not uploaded_file or not isinstance(uploaded_file, UploadedFile):
        return

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if not content_type.startswith("image/") and not is_heic_upload(uploaded_file):
        raise ValidationError("Only image files are allowed for carousel slides.")


def validate_organiser_photo(value):
    """
    Validate organiser photo uploads on new files only.

    Same Cloudinary public-ID caveat as ``validate_carousel_image``.
    """
    if value is None:
        return

    if not isinstance(value, UploadedFile):
        return

    _extension_validator(value)


def validate_organiser_photo_upload(uploaded_file):
    """Admin form helper — reject non-image uploads for new organiser photos."""
    if not uploaded_file or not isinstance(uploaded_file, UploadedFile):
        return

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if not content_type.startswith("image/") and not is_heic_upload(uploaded_file):
        raise ValidationError("Only image files are allowed for organiser photos.")
