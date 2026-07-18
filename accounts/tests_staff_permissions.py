from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from .models import User
from .staff_permissions import (
    STAFF_GROUP_NAME,
    ensure_staff_group,
    staff_permission_codenames,
)


class StaffGroupTests(TestCase):
    def test_ensure_staff_group_has_expected_permissions(self):
        group = ensure_staff_group()
        self.assertEqual(group.name, STAFF_GROUP_NAME)
        codenames = set(group.permissions.values_list("codename", flat=True))
        expected = staff_permission_codenames()
        self.assertTrue(expected.issubset(codenames))
        self.assertNotIn("delete_user", codenames)
        self.assertIn("change_user", codenames)
        self.assertIn("view_user", codenames)
        self.assertIn("add_event", codenames)
        self.assertIn("change_homecarouselslide", codenames)

    def test_setting_is_staff_adds_user_to_staff_group(self):
        user = User.objects.create_user(
            username="newstaff",
            email="newstaff@example.com",
            password="jam-session-test-pass1",
            display_name="New Staff",
        )
        self.assertFalse(user.groups.filter(name=STAFF_GROUP_NAME).exists())

        user.is_staff = True
        user.force_member_badge = True
        user.save()

        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name=STAFF_GROUP_NAME).exists())
        self.assertFalse(user.force_member_badge)

    def test_removing_is_staff_removes_staff_group(self):
        user = User.objects.create_user(
            username="exstaff",
            email="exstaff@example.com",
            password="jam-session-test-pass1",
            display_name="Ex Staff",
            is_staff=True,
        )
        self.assertTrue(user.groups.filter(name=STAFF_GROUP_NAME).exists())

        user.is_staff = False
        user.save()
        self.assertFalse(user.groups.filter(name=STAFF_GROUP_NAME).exists())

    def test_staff_cannot_delete_users_in_admin(self):
        staff = User.objects.create_user(
            username="staffdel",
            email="staffdel@example.com",
            password="jam-session-test-pass1",
            display_name="Staff Del",
            is_staff=True,
        )
        target = User.objects.create_user(
            username="targetuser",
            email="targetuser@example.com",
            password="jam-session-test-pass1",
            display_name="Target User",
        )
        self.client.force_login(staff)
        url = reverse("admin:accounts_user_delete", args=[target.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_delete_users_in_admin(self):
        superuser = User.objects.create_superuser(
            username="boss",
            email="boss@example.com",
            password="jam-session-test-pass1",
        )
        target = User.objects.create_user(
            username="goneuser",
            email="goneuser@example.com",
            password="jam-session-test-pass1",
            display_name="Gone User",
        )
        self.client.force_login(superuser)
        url = reverse("admin:accounts_user_delete", args=[target.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_force_member_badge_hidden_on_staff_change_form(self):
        staff = User.objects.create_user(
            username="staffform",
            email="staffform@example.com",
            password="jam-session-test-pass1",
            display_name="Staff Form",
            is_staff=True,
        )
        superuser = User.objects.create_superuser(
            username="adminboss",
            email="adminboss@example.com",
            password="jam-session-test-pass1",
        )
        self.client.force_login(superuser)
        response = self.client.get(
            reverse("admin:accounts_user_change", args=[staff.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "id_force_member_badge")
