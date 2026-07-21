"""Helpers for listing active community members (sidebar and related UI)."""

from django.contrib.auth import get_user_model
from django.db.models import CharField, F, Value
from django.db.models.functions import Coalesce, Lower, NullIf, Trim

User = get_user_model()


def get_active_members():
    """
    Active users ordered alphabetically by public display name (case-insensitive).

    Users with ``hide_from_members_list`` are excluded (admin-only flag).
    Empty / whitespace-only ``display_name`` falls back to ``username`` for
    sorting so blank nicknames never break the sidebar.
    """
    return (
        User.objects.filter(is_active=True, hide_from_members_list=False)
        .annotate(
            _sort_name=Lower(
                Coalesce(
                    NullIf(Trim("display_name"), Value("")),
                    F("username"),
                    output_field=CharField(),
                )
            )
        )
        .order_by("_sort_name", "pk")
    )
