from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from jamsession.cloudinary_delivery import web_image_url

from .forms import GalleryItemAdminForm
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
    form = GalleryItemAdminForm
    list_display = (
        "media_thumbnail",
        "pin_order",
        "display_uploaded_by",
        "display_event",
        "display_media_type",
        "display_status",
        "title",
        "created_at",
    )
    list_display_links = ("media_thumbnail", "title")
    list_editable = ("pin_order",)
    list_filter = ("status", "media_type", "event", "uploaded_by")
    search_fields = ("title", "caption", "uploaded_by__username", "event__venue_name")
    readonly_fields = (
        "media_preview",
        "media_type",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )
    actions = [approve_gallery_items, reject_gallery_items]
    autocomplete_fields = ("uploaded_by", "event")

    class Media:
        css = {"all": ("gallery/css/admin_gallery.css",)}

    fieldsets = (
        (
            _("Media"),
            {
                "classes": ["tab"],
                "fields": (
                    "media_preview",
                    "file",
                    "uploaded_by",
                    "event",
                    "media_type",
                    "title",
                    "caption",
                ),
            },
        ),
        (
            _("Display order"),
            {
                "classes": ["tab"],
                "fields": ("pin_order",),
                "description": _(
                    "Pin a few favourites to the top of the Photos or Videos "
                    "section. Example: set three photos to 1, 2 and 3 — they "
                    "appear first in that order; everything else keeps normal "
                    "newest-first order. Each pin number can be used only once "
                    "per section (photos and videos are separate)."
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

    def get_queryset(self, request):
        return super().get_queryset(request).order_by(*GalleryItem.display_order_by())

    def get_form_kwargs(self, request, obj=None):
        kwargs = super().get_form_kwargs(request, obj)
        kwargs["user"] = request.user
        return kwargs

    @display(description=_("Current media"))
    def media_preview(self, obj):
        """Large preview at the top of the Media tab when editing an item."""
        if not obj or not obj.pk or not obj.file:
            return _("No media uploaded yet.")

        if obj.is_video:
            video_url = obj.display_media_url
            poster_url = obj.display_image_url
            if not video_url:
                return "-"
            return format_html(
                '<video src="{}" poster="{}" controls preload="metadata" '
                'class="gallery-admin-preview gallery-admin-preview--video"></video>',
                video_url,
                poster_url or "",
            )

        image_url = (
            web_image_url(obj.file, width=960, crop="limit") or obj.display_image_url
        )
        if not image_url:
            return "-"
        return format_html(
            '<img src="{}" alt="{}" '
            'class="gallery-admin-preview gallery-admin-preview--image">',
            image_url,
            obj.title or _("Gallery media"),
        )

    @display(description=_("Preview"), header=True)
    def media_thumbnail(self, obj):
        if not obj.file:
            return (None, None, "-", None)

        if obj.is_video:
            return (
                None,
                None,
                None,
                {
                    "path": obj.display_image_url,
                    "width": 48,
                    "height": 48,
                },
            )

        return (
            None,
            None,
            None,
            {
                "path": web_image_url(obj.file, width=96, height=96, crop="fill"),
                "width": 48,
                "height": 48,
            },
        )

    @display(description=_("Uploaded by"), ordering="uploaded_by__username")
    def display_uploaded_by(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.username
        return _("(deleted account)")

    @display(description=_("Event"), ordering="event__starts_at")
    def display_event(self, obj):
        if obj.event:
            return str(obj.event)
        return "-"

    @display(description=_("Type"), ordering="media_type")
    def display_media_type(self, obj):
        if obj.media_type:
            return obj.get_media_type_display()
        return "-"

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
