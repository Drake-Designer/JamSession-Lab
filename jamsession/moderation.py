"""
Shared moderation pattern for user-submitted content that must go through an
admin approval queue before becoming publicly visible.

GalleryItem was the first model to need this (status/approved_by/approved_at/
rejection_reason, with staff/superuser submissions auto-approved). Community
posts and comments are expected to reuse this same abstract base instead of
duplicating the pattern (see PROJECT_PLAN.md).
"""

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", _("Pending approval")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class ModeratedContent(models.Model):
    """
    Abstract base adding an admin approval workflow to a model.

    Concrete subclasses gain a status field plus who/when approved or
    rejected it, and the methods driving that workflow:
    apply_initial_moderation(), approve(), reject().
    """

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
        related_name="%(app_label)s_%(class)s_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        abstract = True

    def apply_initial_moderation(self, uploader):
        """
        Set approval status for newly created content based on the author's role.

        Staff and superusers are auto-approved; everyone else starts as pending.
        Call this before the first save — used by both public and admin
        submission forms.
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

    def _moderation_update_fields(self):
        """
        Fields written by approve()/reject().

        "updated_at" is only included when the concrete model actually
        defines one: auto_now fields are only refreshed in the database when
        explicitly listed in update_fields, so this keeps existing models
        (e.g. GalleryItem) behaving exactly as before, without forcing every
        future subclass to define an updated_at field it doesn't need.
        """
        fields = ["status", "approved_by", "approved_at", "rejection_reason"]
        try:
            self._meta.get_field("updated_at")
        except FieldDoesNotExist:
            pass
        else:
            fields.append("updated_at")
        return fields

    def approve(self, reviewer):
        self.status = ApprovalStatus.APPROVED
        self.approved_by = reviewer
        self.approved_at = timezone.now()
        self.rejection_reason = ""
        self.save(update_fields=self._moderation_update_fields())

    def reject(self, reviewer, reason=""):
        self.status = ApprovalStatus.REJECTED
        self.approved_by = reviewer
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=self._moderation_update_fields())
