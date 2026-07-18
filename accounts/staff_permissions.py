"""
Staff role: Django Group with full admin access for site content.

Staff may change user profiles but must never delete user accounts
(only superusers can delete users).
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

STAFF_GROUP_NAME = "Staff"

# (app_label, model, permission actions)
# actions are subsets of add / change / delete / view
_STAFF_MODEL_PERMISSIONS = (
    ("pages", "homecarouselslide", ("add", "change", "delete", "view")),
    ("gallery", "galleryitem", ("add", "change", "delete", "view")),
    ("community", "communitypost", ("add", "change", "delete", "view")),
    ("community", "communitypostmedia", ("add", "change", "delete", "view")),
    ("community", "communitycomment", ("add", "change", "delete", "view")),
    ("community", "communitycommentmedia", ("add", "change", "delete", "view")),
    ("community", "communitylike", ("add", "change", "delete", "view")),
    ("events", "event", ("add", "change", "delete", "view")),
    ("registrations", "eventregistration", ("add", "change", "delete", "view")),
    ("registrations", "registrationsong", ("add", "change", "delete", "view")),
    ("accounts", "sociallink", ("add", "change", "delete", "view")),
    # Profiles: edit and view only — never delete (superuser only).
    ("accounts", "user", ("change", "view")),
)


def staff_permission_codenames():
    """Return the set of permission codenames assigned to the Staff group."""
    codenames = set()
    for _app, model, actions in _STAFF_MODEL_PERMISSIONS:
        for action in actions:
            codenames.add(f"{action}_{model}")
    return codenames


def ensure_staff_group():
    """
    Create/update the Staff group with the expected permissions.

    Safe to call repeatedly (idempotent). Missing ContentTypes (e.g. during
    early migrations) are skipped.
    """
    group, _created = Group.objects.get_or_create(name=STAFF_GROUP_NAME)
    permissions = []
    for app_label, model, actions in _STAFF_MODEL_PERMISSIONS:
        try:
            content_type = ContentType.objects.get(
                app_label=app_label, model=model
            )
        except ContentType.DoesNotExist:
            continue
        for action in actions:
            codename = f"{action}_{model}"
            try:
                permissions.append(
                    Permission.objects.get(
                        content_type=content_type, codename=codename
                    )
                )
            except Permission.DoesNotExist:
                continue
    group.permissions.set(permissions)
    return group


def sync_user_staff_group(user):
    """
    Keep Staff group membership aligned with is_staff.

    - Staff (including superusers marked staff) are added to the group.
    - Non-staff users are removed from the group.
    Also clears force_member_badge for staff/superuser (their badge is fixed).
    """
    if user.pk is None:
        return

    group = ensure_staff_group()
    in_group = user.groups.filter(pk=group.pk).exists()

    if user.is_staff:
        if not in_group:
            user.groups.add(group)
    elif in_group:
        user.groups.remove(group)

    if (user.is_staff or user.is_superuser) and user.force_member_badge:
        # QuerySet.update avoids a recursive post_save signal loop.
        type(user).objects.filter(pk=user.pk).update(force_member_badge=False)
        user.force_member_badge = False
