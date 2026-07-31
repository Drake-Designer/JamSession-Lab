"""
Unfold admin sidebar navigation for JamSession Lab.

Keeps UNFOLD["SIDEBAR"] out of settings.py so categories, filtered links,
and pending badges stay easy to maintain in one place.
"""

from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _


def _pending_count(model):
    from jamsession.moderation import ApprovalStatus

    return model.objects.filter(status=ApprovalStatus.PENDING).count()


def gallery_pending_admin_link(request):
    return reverse("admin:gallery_galleryitem_changelist") + "?status__exact=pending"


def community_pending_posts_admin_link(request):
    return (
        reverse("admin:community_communitypost_changelist") + "?status__exact=pending"
    )


def community_pending_comments_admin_link(request):
    return (
        reverse("admin:community_communitycomment_changelist")
        + "?status__exact=pending"
    )


def pending_gallery_badge(request):
    from gallery.models import GalleryItem

    count = _pending_count(GalleryItem)
    return count or None


def pending_posts_badge(request):
    from community.models import CommunityPost

    count = _pending_count(CommunityPost)
    return count or None


def pending_comments_badge(request):
    from community.models import CommunityComment

    count = _pending_count(CommunityComment)
    return count or None


def pending_moderation_badge(request):
    """Total pending posts + comments + gallery items (Admin Tool shortcut)."""
    from community.models import CommunityComment, CommunityPost
    from gallery.models import GalleryItem

    count = (
        _pending_count(CommunityPost)
        + _pending_count(CommunityComment)
        + _pending_count(GalleryItem)
    )
    return count or None


def permission_staff(request):
    return bool(request.user.is_active and request.user.is_staff)


def permission_superuser(request):
    return bool(request.user.is_active and request.user.is_superuser)


def permission_view_gallery(request):
    return request.user.has_perm("gallery.view_galleryitem")


def permission_view_posts(request):
    return request.user.has_perm("community.view_communitypost")


def permission_view_comments(request):
    return request.user.has_perm("community.view_communitycomment")


def permission_view_likes(request):
    return request.user.has_perm("community.view_communitylike")


def permission_view_events(request):
    return request.user.has_perm("events.view_event")


def permission_view_registrations(request):
    return request.user.has_perm("registrations.view_eventregistration")


def permission_view_carousel(request):
    return request.user.has_perm("pages.view_homecarouselslide")


def permission_view_organisers(request):
    return request.user.has_perm("pages.view_aboutorganiser")


def permission_view_users(request):
    return request.user.has_perm("accounts.view_user")


UNFOLD_SIDEBAR = {
    "show_search": True,
    # Safety net: staff can still open the full app/model list if needed.
    "show_all_applications": True,
    "navigation": [
        {
            "title": _("Overview"),
            "separator": True,
            "items": [
                {
                    "title": _("Dashboard"),
                    "icon": "dashboard",
                    "link": reverse_lazy("admin:index"),
                    "permission": "jamsession.admin_navigation.permission_staff",
                },
                {
                    "title": _("Admin Tool"),
                    "icon": "admin_panel_settings",
                    "link": reverse_lazy("community:admin_tool"),
                    "badge": "jamsession.admin_navigation.pending_moderation_badge",
                    "badge_variant": "warning",
                    "permission": "jamsession.admin_navigation.permission_staff",
                },
                {
                    "title": _("View website"),
                    "icon": "language",
                    "link": reverse_lazy("pages:home"),
                    "permission": "jamsession.admin_navigation.permission_staff",
                },
            ],
        },
        {
            "title": _("Website"),
            "separator": True,
            "items": [
                {
                    "title": _("Carousel slides"),
                    "icon": "view_carousel",
                    "link": reverse_lazy("admin:pages_homecarouselslide_changelist"),
                    "permission": "jamsession.admin_navigation.permission_view_carousel",
                },
                {
                    "title": _("Organisers"),
                    "icon": "groups",
                    "link": reverse_lazy("admin:pages_aboutorganiser_changelist"),
                    "permission": (
                        "jamsession.admin_navigation.permission_view_organisers"
                    ),
                },
            ],
        },
        {
            "title": _("Gallery"),
            "separator": True,
            "items": [
                {
                    "title": _("All media"),
                    "icon": "photo_library",
                    "link": reverse_lazy("admin:gallery_galleryitem_changelist"),
                    "permission": "jamsession.admin_navigation.permission_view_gallery",
                },
                {
                    "title": _("Pending approval"),
                    "icon": "pending",
                    "link": gallery_pending_admin_link,
                    "badge": "jamsession.admin_navigation.pending_gallery_badge",
                    "badge_variant": "warning",
                    "permission": "jamsession.admin_navigation.permission_view_gallery",
                },
            ],
        },
        {
            "title": _("Community"),
            "separator": True,
            "items": [
                {
                    "title": _("Posts"),
                    "icon": "forum",
                    "link": reverse_lazy(
                        "admin:community_communitypost_changelist"
                    ),
                    "permission": "jamsession.admin_navigation.permission_view_posts",
                },
                {
                    "title": _("Pending posts"),
                    "icon": "pending_actions",
                    "link": community_pending_posts_admin_link,
                    "badge": "jamsession.admin_navigation.pending_posts_badge",
                    "badge_variant": "warning",
                    "permission": "jamsession.admin_navigation.permission_view_posts",
                },
                {
                    "title": _("Comments"),
                    "icon": "chat",
                    "link": reverse_lazy(
                        "admin:community_communitycomment_changelist"
                    ),
                    "permission": (
                        "jamsession.admin_navigation.permission_view_comments"
                    ),
                },
                {
                    "title": _("Pending comments"),
                    "icon": "mark_chat_unread",
                    "link": community_pending_comments_admin_link,
                    "badge": "jamsession.admin_navigation.pending_comments_badge",
                    "badge_variant": "warning",
                    "permission": (
                        "jamsession.admin_navigation.permission_view_comments"
                    ),
                },
                {
                    "title": _("Likes"),
                    "icon": "favorite",
                    "link": reverse_lazy(
                        "admin:community_communitylike_changelist"
                    ),
                    "permission": "jamsession.admin_navigation.permission_view_likes",
                },
            ],
        },
        {
            "title": _("Events"),
            "separator": True,
            "items": [
                {
                    "title": _("All events"),
                    "icon": "event",
                    "link": reverse_lazy("admin:events_event_changelist"),
                    "permission": "jamsession.admin_navigation.permission_view_events",
                },
                {
                    "title": _("Registrations"),
                    "icon": "how_to_reg",
                    "link": reverse_lazy(
                        "admin:registrations_eventregistration_changelist"
                    ),
                    "permission": (
                        "jamsession.admin_navigation.permission_view_registrations"
                    ),
                },
            ],
        },
        {
            "title": _("Members"),
            "separator": True,
            "items": [
                {
                    "title": _("Users"),
                    "icon": "people",
                    "link": reverse_lazy("admin:accounts_user_changelist"),
                    "permission": "jamsession.admin_navigation.permission_view_users",
                },
            ],
        },
        {
            "title": _("System"),
            "separator": True,
            "items": [
                {
                    "title": _("Groups"),
                    "icon": "security",
                    "link": reverse_lazy("admin:auth_group_changelist"),
                    "permission": "jamsession.admin_navigation.permission_superuser",
                },
            ],
        },
    ],
}
