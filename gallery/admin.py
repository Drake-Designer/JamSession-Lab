from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import ApprovalStatus, GalleryItem


@admin.action(description=_("Approve selected gallery items"))
def approve_gallery_items(modeladmin, request, queryset):
    updated = 0
    for item in queryset.filter(status=ApprovalStatus.PENDING):
        item.approve(request.user)
        updated += 1
    modeladmin.message_user(
        request,
        _("%(count)d item(s) approved.") % {"count": updated},
        messages.SUCCESS,
    )


@admin.action(description=_("Reject selected gallery items"))
def reject_gallery_items(modeladmin, request, queryset):
    updated = 0
    for item in queryset.filter(status=ApprovalStatus.PENDING):
        item.reject(request.user)
        updated += 1
    modeladmin.message_user(
        request,
        _("%(count)d item(s) rejected.") % {"count": updated},
        messages.WARNING,
    )


@admin.register(GalleryItem)
class GalleryItemAdmin(ModelAdmin):
    list_display = (
        "media_thumbnail",
        "display_uploaded_by",
        "display_media_type",
        "display_status",
        "title",
        "created_at",
    )
    list_filter = ("status", "media_type", "uploaded_by")
    search_fields = ("title", "caption", "uploaded_by__username")
    readonly_fields = (
        "media_type",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )
    actions = [approve_gallery_items, reject_gallery_items]
    autocomplete_fields = ("uploaded_by",)

    fieldsets = (
        (
            _("Media"),
            {
                "classes": ["tab"],
                "fields": (
                    "file",
                    "uploaded_by",
                    "media_type",
                    "title",
                    "caption",
                ),
            },
        ),
        (
            _("Moderation"),
            {
                "classes": ["tab"],
                "fields": (
                    "status",
                    "rejection_reason",
                    "approved_by",
                    "approved_at",
                ),
            },
        ),
        (
            _("Timestamps"),
            {
                "classes": ["tab", "collapse"],
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.uploaded_by_id:
                obj.uploaded_by = request.user
            if request.user.is_staff and obj.status == ApprovalStatus.PENDING:
                obj.status = ApprovalStatus.APPROVED
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)

    @display(description=_("Preview"), header=True)
    def media_thumbnail(self, obj):
        if not obj.file:
            return (None, None, "—", None)

        return (
            None,
            None,
            None,
            {
                "path": obj.file.url,
                "width": 48,
                "height": 48,
            },
        )

    @display(description=_("Uploaded by"), ordering="uploaded_by__username")
    def display_uploaded_by(self, obj):
        return obj.uploaded_by.username

    @display(description=_("Type"), ordering="media_type")
    def display_media_type(self, obj):
        if obj.media_type:
            return obj.get_media_type_display()
        return "—"

    @display(
        description=_("Status"),
        ordering="status",
        label={
            "pending": "warning",
            "approved": "success",
            "rejected": "danger",
        },
    )
    def display_status(self, obj):
        return obj.get_status_display()
