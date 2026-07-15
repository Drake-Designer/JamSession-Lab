from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url

from .fields import DynamicCloudinaryField


class MediaType(models.TextChoices):
    IMAGE = "image", _("Image")
    VIDEO = "video", _("Video")


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", _("Pending approval")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class GalleryItem(models.Model):
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
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
    status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_gallery_items",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("gallery item")
        verbose_name_plural = _("gallery items")

    def __str__(self):
        label = self.title or self.get_media_type_display()
        return f"{label} — @{self.uploaded_by.username}"

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

    def apply_initial_moderation(self, uploader):
        """
        Set approval status for a newly created item based on uploader role.

        Staff and superusers are auto-approved; everyone else starts as pending.
        Call this before the first save — used by both public and admin uploads.
        """
        if uploader.is_staff or uploader.is_superuser:
            self.status = ApprovalStatus.APPROVED
            self.approved_by = uploader
            self.approved_at = timezone.now()
            self.rejection_reason = ""
        else:
            self.status = ApprovalStatus.PENDING
            self.approved_by = None
            self.approved_at = None

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

    def approve(self, reviewer):
        self.status = ApprovalStatus.APPROVED
        self.approved_by = reviewer
        self.approved_at = timezone.now()
        self.rejection_reason = ""
        self.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "rejection_reason",
                "updated_at",
            ]
        )

    def reject(self, reviewer, reason=""):
        self.status = ApprovalStatus.REJECTED
        self.approved_by = reviewer
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "rejection_reason",
                "updated_at",
            ]
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

