"""Tests for the Unfold admin sidebar navigation layout."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.staff_permissions import ensure_staff_group, sync_user_staff_group
from jamsession.admin_navigation import UNFOLD_SIDEBAR

User = get_user_model()


class AdminSidebarNavigationTests(TestCase):
    def test_sidebar_includes_likes_and_core_categories(self):
        titles = {
            str(group["title"]): [str(item["title"]) for item in group["items"]]
            for group in UNFOLD_SIDEBAR["navigation"]
        }

        self.assertIn("Overview", titles)
        self.assertIn("Website", titles)
        self.assertIn("Gallery", titles)
        self.assertIn("Community", titles)
        self.assertIn("Events", titles)
        self.assertIn("Members", titles)
        self.assertIn("System", titles)

        self.assertIn("Likes", titles["Community"])
        self.assertIn("Pending comments", titles["Community"])
        self.assertIn("Admin Tool", titles["Overview"])

    def test_staff_admin_index_renders_sidebar_labels(self):
        ensure_staff_group()
        staff = User.objects.create_user(
            username="sidebar_staff",
            email="sidebar_staff@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        sync_user_staff_group(staff)
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Community")
        self.assertContains(response, "Likes")
        self.assertContains(response, "Admin Tool")
