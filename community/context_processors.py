"""Template context shared across Community pages."""

from accounts.members import get_active_members

# Public Community pages that show the members sidebar.
_COMMUNITY_SIDEBAR_URL_NAMES = frozenset(
    {
        "list",
        "post_detail",
        "post_create",
    }
)


def community_members(request):
    """
    Inject the active-members list on list / detail / create Community pages.

    Other Community routes (moderation, admin tool) are left alone so staff
    tools keep a full-width layout.

    The queryset is evaluated once into a list so the template can iterate and
    show a count without a second COUNT query (and without N+1 risk —
    ``badge_info`` / avatars only use columns already on the User row).
    """
    match = getattr(request, "resolver_match", None)
    if match is None or match.app_name != "community":
        return {}
    if match.url_name not in _COMMUNITY_SIDEBAR_URL_NAMES:
        return {}

    members = list(get_active_members())
    return {
        "community_members": members,
        "community_members_count": len(members),
    }
