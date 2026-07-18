from django.db import migrations


def create_staff_group_and_assign_members(apps, schema_editor):
    """Create the Staff group and attach every existing is_staff user."""
    # Import from the live module so permission definitions stay in one place.
    from accounts.staff_permissions import (
        STAFF_GROUP_NAME,
        ensure_staff_group,
    )

    ensure_staff_group()

    User = apps.get_model("accounts", "User")
    Group = apps.get_model("auth", "Group")
    try:
        group = Group.objects.get(name=STAFF_GROUP_NAME)
    except Group.DoesNotExist:
        return

    staff_users = User.objects.filter(is_staff=True)
    for user in staff_users.iterator():
        user.groups.add(group)
        if user.is_staff or user.is_superuser:
            if getattr(user, "force_member_badge", False):
                User.objects.filter(pk=user.pk).update(force_member_badge=False)


def remove_staff_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Staff").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_experience_started_year"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("pages", "0004_update_carousel_image_validator"),
        ("gallery", "0003_alter_galleryitem_uploaded_by"),
        ("community", "0003_communitypost_cover_focus"),
        ("events", "0001_initial"),
        ("registrations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_staff_group_and_assign_members,
            remove_staff_group,
        ),
    ]
