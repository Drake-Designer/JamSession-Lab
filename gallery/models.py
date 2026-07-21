from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url
from jamsession.moderation import ApprovalStatus, ModeratedContent

from .fields import DynamicCloudinaryField


class MediaType(models.TextChoices):
    IMAGE = "image", _("Image")
    VIDEO = "video", _("Video")


class GalleryItem(ModeratedContent):
    # CASCADE removes the item (and Cloudinary file via signals) when the
    # uploader permanently deletes their account — required for privacy erasure.
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="gallery_items",
    )
    file = DynamicCloudinaryField(
        _("file"),
        resource_type="auto",
    )
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        blank=True,
    )
    title = models.CharField(max_length=120, blank=True)
    caption = models.TextField(blank=True)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gallery_items",
        verbose_name=_("event"),
    )
    pin_order = models.PositiveSmallIntegerField(
        _("pin order"),
        null=True,
        blank=True,
        validators=[MaxValueValidator(999)],
        help_text=_(
            "Optional. Set 1, 2, 3… to show this item first in its section "
            "(photos or videos). Each number can be used only once per section. "
            "Leave blank for normal newest-first order. Maximum three digits (1–999)."
        ),
    )
    # Override ModeratedContent's generic related_name to keep the exact
    # reverse accessor already used in production (and in the initial
    # migration): status/approved_at/rejection_reason are inherited as-is.
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_gallery_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pin_order", "-created_at"]
        verbose_name = _("gallery item")
        verbose_name_plural = _("gallery items")
        constraints = [
            models.UniqueConstraint(
                fields=["media_type", "pin_order"],
                condition=Q(pin_order__isnull=False) & ~Q(media_type=""),
                name="galleryitem_unique_pin_per_media_type",
            ),
        ]

    @staticmethod
    def display_order_by():
        """Pinned items first (1, 2, 3…), then newest-first for the rest."""
        return (F("pin_order").asc(nulls_last=True), "-created_at")

    def pin_section_key(self):
        """Photos and videos are pinned in separate sequences."""
        if self.media_type in {MediaType.IMAGE, MediaType.VIDEO}:
            return self.media_type
        return MediaType.VIDEO if self.is_video else MediaType.IMAGE

    def clean(self):
        super().clean()
        self.validate_unique_pin_order()

    def validate_unique_pin_order(self):
        """
        Ensure pin_order is unique within the photos or videos section.

        Raises ValidationError with a pin_order key when another item already
        uses the same number in the same section. Zero is treated as no pin.
        """
        if self.pin_order is None or self.pin_order == 0:
            self.pin_order = None
            return

        section = self.pin_section_key()
        clash = GalleryItem.objects.filter(
            media_type=section,
            pin_order=self.pin_order,
        )
        if self.pk:
            clash = clash.exclude(pk=self.pk)

        if clash.exists():
            kind = _("video") if section == MediaType.VIDEO else _("photo")
            raise ValidationError(
                {
                    "pin_order": _(
                        "Pin %(number)d is already used by another %(kind)s. "
                        "Choose a different number."
                    )
                    % {"number": self.pin_order, "kind": kind}
                }
            )

    def __str__(self):
        label = self.title or self.get_media_type_display()
        if self.uploaded_by:
            return f"{label} · @{self.uploaded_by.username}"
        return f"{label} · (deleted account)"

    def upload_options(self):
        """
        Per-instance Cloudinary upload options — called on every file upload.

        Returns the dynamic folder for this uploader:
        JamSession Lab/{username}/gallery/
        """
        if self.uploaded_by_id:
            username = self.uploaded_by.username
        elif self.uploaded_by:
            username = self.uploaded_by.username
        else:
            username = "unknown"

        return {
            "folder": f"JamSession Lab/{username}/gallery",
            "use_filename": True,
            "unique_filename": True,
        }

    def purge_media_after_rejection(self):
        """
        Destroy the Cloudinary asset for a rejected gallery upload.

        The rejected row is kept for moderation history; the file field is
        required so we destroy remote storage without clearing the DB value.
        """
        from django.db import transaction

        from jamsession.cloudinary_cleanup import _delete_stored_file

        file_value = self.file
        if file_value:
            transaction.on_commit(lambda: _delete_stored_file(file_value))

    @property
    def is_video(self):
        if self.media_type:
            return self.media_type == MediaType.VIDEO
        if self.file and hasattr(self.file, "resource_type"):
            return self.file.resource_type == "video"
        return False

    @property
    def display_image_url(self):
        """Grid thumbnail: image URL or a poster frame for videos."""
        if not self.file:
            return ""

        if self.is_video:
            return self.file.build_url(
                transformation=[
                    {"width": 900, "height": 675, "crop": "fill", "gravity": "auto"},
                ],
                format="jpg",
            )

        return web_image_url(
            self.file,
            width=900,
            height=675,
            crop="fill",
        )

    @property
    def display_media_url(self):
        """Full-size browser-friendly URL for gallery lightbox and detail views."""
        if not self.file:
            return ""

        if self.is_video:
            return self.file.url

        return web_image_url(
            self.file,
            width=1920,
            crop="limit",
            quality="auto:best",
        )

    @property
    def display_media_fallback_url(self):
        """H.264 fallback for browsers that cannot play the original video codec."""
        if not self.file or not self.is_video:
            return ""

        return self.file.build_url(
            transformation=[
                {"fetch_format": "mp4", "quality": "auto"},
            ],
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._sync_media_type()

    def _sync_media_type(self):
        if not self.file:
            return

        resource_type = getattr(self.file, "resource_type", "image")
        detected = (
            MediaType.VIDEO if resource_type == "video" else MediaType.IMAGE
        )
        if self.media_type != detected:
            GalleryItem.objects.filter(pk=self.pk).update(media_type=detected)
            self.media_type = detected

