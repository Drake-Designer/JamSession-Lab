from django.conf import settings
from django.db import models
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
        ordering = ["-created_at"]
        verbose_name = _("gallery item")
        verbose_name_plural = _("gallery items")

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

