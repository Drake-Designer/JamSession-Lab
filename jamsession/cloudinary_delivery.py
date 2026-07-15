"""Browser-friendly Cloudinary image delivery helpers."""

from __future__ import annotations


def _build_transformation(*, width=None, height=None, crop=None, quality="auto"):
    transformation = {"fetch_format": "auto", "quality": quality}

    if width:
        transformation["width"] = width
    if height:
        transformation["height"] = height
    if crop:
        transformation["crop"] = crop

    return [transformation]


def web_image_url(image_field, *, width=None, height=None, crop=None, quality="auto"):
    """
    Return a browser-compatible Cloudinary URL for an image field.

    HEIC/HEIF and other non-web formats are converted on delivery via f_auto.
    Works with ImageField (MediaCloudinaryStorage) and CloudinaryField.
    """
    if not image_field:
        return ""

    transformation = _build_transformation(
        width=width,
        height=height,
        crop=crop,
        quality=quality,
    )

    if hasattr(image_field, "build_url"):
        return image_field.build_url(
            transformation=transformation,
        )

    name = getattr(image_field, "name", None)
    if name:
        from cloudinary import CloudinaryImage

        return CloudinaryImage(name).build_url(
            transformation=transformation,
        )

    return getattr(image_field, "url", "")
