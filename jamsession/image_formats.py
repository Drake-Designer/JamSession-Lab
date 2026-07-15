"""Shared HEIC/HEIF image format support for uploads."""

from __future__ import annotations

import os
from functools import lru_cache

HEIC_FILE_EXTENSIONS = (".heic", ".heif")

HEIC_CONTENT_TYPES = frozenset(
    {
        "image/heic",
        "image/heif",
        "image/heic-sequence",
        "image/heif-sequence",
    }
)

# ISO BMFF "ftyp" major brands used by HEIC/HEIF still images.
HEIC_FTYP_BRANDS = frozenset(
    {
        b"heic",
        b"heix",
        b"hevc",
        b"hevx",
        b"heim",
        b"heis",
        b"hevm",
        b"hevs",
        b"mif1",
        b"msf1",
    }
)

STANDARD_IMAGE_EXTENSIONS = [
    "bmp",
    "dib",
    "gif",
    "jfif",
    "jpe",
    "jpeg",
    "jpg",
    "png",
    "apng",
    "tif",
    "tiff",
    "webp",
]

IMAGE_EXTENSIONS_INCLUDING_HEIC = [
    *STANDARD_IMAGE_EXTENSIONS,
    "heic",
    "heif",
]


@lru_cache(maxsize=1)
def register_heif_opener() -> None:
    """Register HEIC/HEIF decoding with Pillow when pillow-heif is available."""
    try:
        from pillow_heif import register_heif_opener as _register

        _register()
    except ImportError:
        pass


def read_upload_header(uploaded_file, length=32) -> bytes:
    if uploaded_file is None or not hasattr(uploaded_file, "read"):
        return b""

    position = uploaded_file.tell()
    uploaded_file.seek(0)
    header = uploaded_file.read(length)
    uploaded_file.seek(position)
    return header


def is_heic_container(header: bytes) -> bool:
    if len(header) < 12 or header[4:8] != b"ftyp":
        return False
    return header[8:12].lower() in HEIC_FTYP_BRANDS


def has_heic_filename(name: str) -> bool:
    if not name:
        return False
    return os.path.splitext(name)[1].lower() in HEIC_FILE_EXTENSIONS


def has_heic_content_type(content_type: str) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return normalized in HEIC_CONTENT_TYPES or normalized.startswith("image/hei")


def is_heic_upload(uploaded_file) -> bool:
    """Return True when the upload looks like a HEIC/HEIF image."""
    if uploaded_file is None:
        return False

    name = getattr(uploaded_file, "name", "") or ""
    if has_heic_filename(name):
        return True

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if has_heic_content_type(content_type):
        return True

    header = read_upload_header(uploaded_file)
    return is_heic_container(header)


def verify_image_upload(uploaded_file) -> bool:
    """Verify the file is a real image by parsing it with Pillow."""
    from PIL import Image, UnidentifiedImageError

    if uploaded_file is None or not hasattr(uploaded_file, "read"):
        return False

    register_heif_opener()
    position = uploaded_file.tell()
    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, SyntaxError):
        return False
    finally:
        uploaded_file.seek(position)
