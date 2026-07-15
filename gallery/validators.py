from django.core.exceptions import ValidationError

from jamsession.image_formats import (
    is_heic_container,
    read_upload_header,
    verify_image_upload,
)

MAX_GALLERY_UPLOAD_SIZE_BYTES = 104_857_600  # 100 MB

FILE_TOO_LARGE_MESSAGE = (
    "File exceeds the 100MB limit. Please compress the video or "
    "reduce its quality before uploading."
)

INVALID_FILE_TYPE_MESSAGE = (
    "Only photo and video files are allowed. "
    "Please upload an image or video file."
)

# ISO BMFF brands that are audio-only (not gallery videos).
_AUDIO_FTYP_BRANDS = frozenset(
    {
        b"M4A ",
        b"M4B ",
        b"F4A ",
        b"F4B ",
    }
)


def _is_image_file(uploaded_file):
    """Verify the file is a real image by parsing it with Pillow."""
    return verify_image_upload(uploaded_file)


def _is_audio_only_ftyp(header):
    if len(header) < 12 or header[4:8] != b"ftyp":
        return False
    brand = header[8:12]
    return brand in _AUDIO_FTYP_BRANDS


def _is_video_file(uploaded_file):
    """Detect common video containers from file magic bytes."""
    header = read_upload_header(uploaded_file, 32)

    if _is_audio_only_ftyp(header):
        return False

    if is_heic_container(header):
        return False

    if len(header) >= 12 and header[4:8] == b"ftyp":
        return True

    if len(header) >= 4 and header[0:4] == b"\x1a\x45\xdf\xa3":
        return True

    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"AVI ":
        return True

    if len(header) >= 3 and header[0:3] == b"FLV":
        return True

    if len(header) >= 1 and header[0] == 0x47:
        return True

    return False


def _is_blocked_non_media(header):
    """Reject known audio and document signatures."""
    if header.startswith(b"ID3"):
        return True

    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return True

    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"WAVE":
        return True

    if header.startswith(b"OggS"):
        return True

    if header.startswith(b"fLaC"):
        return True

    if header.startswith(b"%PDF"):
        return True

    if header.startswith(b"PK\x03\x04"):
        return True

    return False


def detect_gallery_media_kind(uploaded_file):
    """
    Return 'image', 'video', or None.

    Images are verified with Pillow (real decode, not extension/MIME header).
    Videos are verified from container magic bytes.
    """
    if uploaded_file is None or not hasattr(uploaded_file, "read"):
        return None

    header = read_upload_header(uploaded_file, 32)

    if _is_blocked_non_media(header):
        return None

    if _is_image_file(uploaded_file):
        return "image"

    if _is_video_file(uploaded_file):
        return "video"

    return None


def validate_gallery_file_size(uploaded_file):
    """
    Reject new uploads over 100 MB before they are sent to Cloudinary.

    Skips validation when the value is an existing Cloudinary resource
    (edits that do not replace the file).
    """
    if uploaded_file is None:
        return

    if not hasattr(uploaded_file, "size"):
        return

    if uploaded_file.size > MAX_GALLERY_UPLOAD_SIZE_BYTES:
        raise ValidationError(FILE_TOO_LARGE_MESSAGE)


def validate_gallery_file_type(uploaded_file):
    """
    Reject uploads that are not real photos or videos.

    Skips validation when the value is an existing Cloudinary resource.
    """
    if uploaded_file is None:
        return

    if not hasattr(uploaded_file, "read"):
        return

    if detect_gallery_media_kind(uploaded_file) is None:
        raise ValidationError(INVALID_FILE_TYPE_MESSAGE)


def gallery_file_rejection_reason(uploaded_file):
    """
    Return a short English reason if the file is invalid, otherwise None.

    Used for per-file validation during batch uploads without stopping the loop.
    """
    try:
        validate_gallery_file_size(uploaded_file)
        validate_gallery_file_type(uploaded_file)
    except ValidationError as exc:
        message = exc.messages[0] if exc.messages else str(exc)
        if "100MB" in message:
            return "file exceeds 100MB limit"
        if "photo and video" in message:
            return "only photos and videos are allowed"
        return message
    return None
