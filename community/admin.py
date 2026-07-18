from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from gallery.models import MediaType
from jamsession.cloudinary_delivery import web_image_url
from jamsession.moderation import ApprovalStatus

from .models import (
    CommunityComment,
    CommunityCommentMedia,
    CommunityLike,
    CommunityPost,
    CommunityPostMedia,
)


def _bulk_approve(modeladmin, request, queryset, success_message):
    """
    Approve every pending object in the selection.

    Delegates to ModeratedContent.approve() so the moderation logic lives in
    one place (the model), never duplicated in the admin — mirrors
    approve_gallery_items in gallery/admin.py.
    """
    updated = 0
    for obj in queryset.filter(status=ApprovalStatus.PENDING):
        obj.approve(request.user)
        updated += 1
    modeladmin.message_user(
        request,
        success_message % {"count": updated},
        messages.SUCCESS,
    )


def _bulk_reject(modeladmin, request, queryset, warning_message):
    """
    Reject every pending object in the selection.

    Like gallery/admin.py, the bulk action rejects without collecting a
    reason (rejection_reason stays blank); a specific reason can be typed per
    item in the "Moderation" fieldset of the change form. Delegates to
    ModeratedContent.reject().
    """
    updated = 0
    for obj in queryset.filter(status=ApprovalStatus.PENDING):
        obj.reject(request.user)
        updated += 1
    modeladmin.message_user(
        request,
        warning_message % {"count": updated},
        messages.WARNING,
    )


@admin.action(description=_("Approve selected posts"))
def approve_posts(modeladmin, request, queryset):
    _bulk_approve(modeladmin, request, queryset, _("%(count)d post(s) approved."))


@admin.action(description=_("Reject selected posts"))
def reject_posts(modeladmin, request, queryset):
    _bulk_reject(modeladmin, request, queryset, _("%(count)d post(s) rejected."))


@admin.action(description=_("Approve selected comments"))
def approve_comments(modeladmin, request, queryset):
    _bulk_approve(modeladmin, request, queryset, _("%(count)d comment(s) approved."))


@admin.action(description=_("Reject selected comments"))
def reject_comments(modeladmin, request, queryset):
    _bulk_reject(modeladmin, request, queryset, _("%(count)d comment(s) rejected."))


def _cloudinary_file(obj):
    """
    Return obj.file as a CloudinaryResource when possible.

    Fresh Model.objects.create(file="image/upload/...") leaves .file as the
    raw stored string until the instance is reloaded. Admin change forms
    always load from the DB, but helpers/tests may see the string form —
    normalise it the same way CloudinaryField.to_python does.
    """
    file_value = obj.file
    if not file_value:
        return None

    if not isinstance(file_value, str):
        return file_value

    field = obj._meta.get_field("file")
    return field.to_python(file_value)


def _resolve_media_url(obj, *, width=220):
    """
    Return a browser-displayable URL for a community media attachment.

    Images go through web_image_url (f_auto) so HEIC/HEIF and other non-web
    formats actually render in the admin — the same delivery path Gallery
    already uses. Videos keep the raw Cloudinary URL. Failures resolve to
    an empty string so the caller can show an em dash instead of crashing
    the change form.
    """
    if not obj.pk:
        return ""

    file_value = _cloudinary_file(obj)
    if not file_value:
        return ""

    try:
        if obj.media_type == MediaType.VIDEO:
            return file_value.url or ""
        return web_image_url(file_value, width=width, crop="limit") or ""
    except (AttributeError, ValueError, TypeError):
        return ""


def _media_preview(obj, *, width=220, height=160):
    """
    Build an inline HTML preview of a media attachment for the admin.

    An <img> for images, a <video controls> for videos. Shared by both
    TabularInlines and the parent change-form gallery preview.
    """
    url = _resolve_media_url(obj, width=width)
    if not url:
        return "—"

    if obj.media_type == MediaType.VIDEO:
        return format_html(
            '<video src="{}" controls preload="metadata" '
            'width="{}" height="{}" '
            'style="max-width: {}px; max-height: {}px;"></video>',
            url,
            width,
            height,
            width,
            height,
        )

    return format_html(
        '<img src="{}" alt="" width="{}" height="{}" '
        'style="max-width: {}px; max-height: {}px; object-fit: cover;">',
        url,
        width,
        height,
        width,
        height,
    )


def _media_gallery_preview(media_queryset, *, width=300, height=300):
    """Render every attachment as a larger preview for the parent change form."""
    items = list(media_queryset)
    if not items:
        return _("No attachments.")

    return format_html(
        '<div style="display: flex; flex-wrap: wrap; gap: 12px;">{}</div>',
        format_html_join(
            "",
            "{}",
            ((_media_preview(item, width=width, height=height),) for item in items),
        ),
    )


class CommunityPostMediaInline(TabularInline):
    model = CommunityPostMedia
    extra = 0
    fields = ("media_preview", "file", "media_type", "order")
    readonly_fields = ("media_preview",)

    @display(description=_("Preview"))
    def media_preview(self, obj):
        return _media_preview(obj, width=220, height=160)


class CommunityCommentMediaInline(TabularInline):
    model = CommunityCommentMedia
    extra = 0
    fields = ("media_preview", "file", "media_type", "order")
    readonly_fields = ("media_preview",)

    @display(description=_("Preview"))
    def media_preview(self, obj):
        return _media_preview(obj, width=220, height=160)


@admin.register(CommunityPost)
class CommunityPostAdmin(ModelAdmin):
    inlines = [CommunityPostMediaInline]
    list_display = (
        "title",
        "display_author",
        "display_status",
        "display_attachment_count",
        "created_at",
    )
    list_filter = ("status", "author")
    search_fields = ("title", "body", "author__username")
    readonly_fields = (
        "slug",
        "media_gallery",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )
    actions = [approve_posts, reject_posts]
    autocomplete_fields = ("author",)

    fieldsets = (
        (
            _("Content"),
            {
                "classes": ["tab"],
                "fields": (
                    "title",
                    "slug",
                    "author",
                    "body",
                    "cover_image",
                    "cover_focus_x",
                    "cover_focus_y",
                ),
            },
        ),
        (
            _("Media"),
            {
                "classes": ["tab"],
                "fields": ("media_gallery",),
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

    @display(description=_("Author"), ordering="author__username")
    def display_author(self, obj):
        if obj.author:
            return obj.author.username
        return _("(deleted account)")

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
        return obj.status

    @display(description=_("Attachments"))
    def display_attachment_count(self, obj):
        return obj.media.count()

    @display(description=_("Attachments preview"))
    def media_gallery(self, obj):
        if not obj.pk:
            return "—"
        return _media_gallery_preview(obj.media.all(), width=300, height=300)


@admin.register(CommunityComment)
class CommunityCommentAdmin(ModelAdmin):
    inlines = [CommunityCommentMediaInline]
    list_display = (
        "display_excerpt",
        "display_author",
        "display_post",
        "display_status",
        "display_attachment_count",
        "created_at",
    )
    list_filter = ("status", "author")
    search_fields = ("body", "author__username", "post__title")
    readonly_fields = (
        "media_gallery",
        "approved_by",
        "approved_at",
        "created_at",
    )
    actions = [approve_comments, reject_comments]
    autocomplete_fields = ("post", "author")

    fieldsets = (
        (
            _("Content"),
            {
                "classes": ["tab"],
                "fields": (
                    "post",
                    "author",
                    "body",
                ),
            },
        ),
        (
            _("Media"),
            {
                "classes": ["tab"],
                "fields": ("media_gallery",),
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
                "fields": ("created_at",),
            },
        ),
    )

    @display(description=_("Comment"))
    def display_excerpt(self, obj):
        return Truncator(obj.body).chars(60)

    @display(description=_("Author"), ordering="author__username")
    def display_author(self, obj):
        if obj.author:
            return obj.author.username
        return _("(deleted account)")

    @display(description=_("Post"), ordering="post__title")
    def display_post(self, obj):
        return Truncator(obj.post.title).chars(40)

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
        return obj.status

    @display(description=_("Attachments"))
    def display_attachment_count(self, obj):
        return obj.media.count()

    @display(description=_("Attachments preview"))
    def media_gallery(self, obj):
        if not obj.pk:
            return "—"
        return _media_gallery_preview(obj.media.all(), width=300, height=300)


@admin.register(CommunityLike)
class CommunityLikeAdmin(ModelAdmin):
    """Read-only listing for debugging; likes are not moderated."""

    list_display = ("post", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("post__title", "user__username")
    readonly_fields = ("post", "user", "created_at")

    def has_add_permission(self, request):
        return False
