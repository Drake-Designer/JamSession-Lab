"""Template context shared across Community pages."""

from accounts.members import get_active_members

# Members sidebar only on the main Community list (logged-in members only).
_COMMUNITY_SIDEBAR_URL_NAMES = frozenset({"list"})


def community_members(request):
    """
    Inject the active-members list on Community pages that show the sidebar.

    Anonymous visitors never receive this context — the Members list is for
    registered members only. Staff tools (moderation, admin tool) are left
    alone so they keep a full-width layout.

    The queryset is evaluated once into a list so the template can iterate and
    show a count without a second COUNT query (and without N+1 risk —
    ``badge_info`` / avatars only use columns already on the User row).
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

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
