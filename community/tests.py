"""
Tests for the community app.

Model scope (Phase 4, first sub-block): creation, relations, on_delete
behaviour, unique constraints, moderation and slug generation.

View/permission scope (Phase 4, second sub-block): list/detail visibility,
login-gated creation with role-based moderation, like toggling, and — most
importantly — deletion permission rules enforced in the view itself (a normal
user must not be able to delete another user's post or comment even by POSTing
directly to the URL, without going through any template button).

Real Cloudinary uploads are never made: cloudinary.uploader.upload_resource is
patched with the same fake used by the gallery tests. Views are exercised
against the real community templates (Phase 4, template sub-block), the same
way gallery's own view tests exercise gallery_list.html/upload.html.
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cloudinary
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from gallery.models import GalleryItem, MediaType
from gallery.validators import detect_gallery_media_kind
from jamsession.moderation import ApprovalStatus

from .admin import (
    CommunityCommentAdmin,
    CommunityPostAdmin,
    _media_preview,
    _resolve_media_url,
    approve_comments,
    approve_posts,
    reject_comments,
    reject_posts,
)
from .forms import CommunityPostForm
from .models import (
    CommunityComment,
    CommunityCommentMedia,
    CommunityLike,
    CommunityPost,
    CommunityPostMedia,
)
from .templatetags.community_extras import urlize_blank

User = get_user_model()


def _make_user(username, *, is_staff=False, is_superuser=False):
    """Create a minimal but valid user for community tests."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="jam-session-test-pass1",
        display_name=username,
        is_staff=is_staff,
        is_superuser=is_superuser,
        is_email_verified=True,
    )


def _make_image_file(name="photo.jpg", size=(20, 20), colour=(230, 57, 70)):
    """Build a small, genuinely valid in-memory JPEG for upload tests."""
    buffer = BytesIO()
    Image.new("RGB", size, color=colour).save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def _make_invalid_file(name="notes.txt"):
    """Build a file that is neither a real image nor a recognised video."""
    return SimpleUploadedFile(
        name,
        b"This is plain text, not a real photo or video.",
        content_type="text/plain",
    )


def _make_minimal_mp4(name="clip.mp4"):
    """
    Tiny bytes that pass the gallery video magic-byte check (ftyp/isom).

    Used only to assert cover_image rejects videos (covers are photos only).
    """
    return SimpleUploadedFile(
        name,
        b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2mp41",
        content_type="video/mp4",
    )


def _attach_cover(post, public_id="image/upload/v1/cover.jpg"):
    """Set a stored Cloudinary path as cover and reload for display URLs."""
    post.cover_image = public_id
    post.save(update_fields=["cover_image"])
    post.refresh_from_db()
    return post


def _fake_upload_resource(file, **options):
    """Stand-in for cloudinary.uploader.upload_resource (mirrors gallery tests)."""
    kind = detect_gallery_media_kind(file) or "image"
    resource_type = "video" if kind == "video" else "image"
    if hasattr(file, "seek"):
        file.seek(0)
    return cloudinary.CloudinaryResource(
        f"jamsession-lab-tests/{getattr(file, 'name', 'upload')}",
        version="1",
        format="mp4" if resource_type == "video" else "jpg",
        type="upload",
        resource_type=resource_type,
    )


def _make_post(author, **overrides):
    """
    Create a post without an explicit slug, letting CommunityPost.save()
    auto-generate one — this is how posts will actually be created once the
    creation view/form exists.
    """
    defaults = {
        "author": author,
        "title": "Test post",
        "body": "Test body",
    }
    defaults.update(overrides)
    return CommunityPost.objects.create(**defaults)


class CommunityUrlizeBlankFilterTests(TestCase):
    def test_http_url_becomes_blank_target_link(self):
        result = urlize_blank("See https://example.com/jam for details")

        self.assertIn('href="https://example.com/jam"', result)
        self.assertIn('target="_blank"', result)
        self.assertIn('rel="nofollow noopener noreferrer"', result)
        self.assertIn("https://example.com/jam", result)

    def test_plain_text_without_url_is_unchanged(self):
        result = urlize_blank("No links here")

        self.assertEqual(result, "No links here")
        self.assertNotIn("<a ", result)

    def test_html_in_body_is_escaped(self):
        result = urlize_blank('<script>alert("x")</script> https://safe.example')

        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn('href="https://safe.example"', result)


class CommunityPostModelTests(TestCase):
    def setUp(self):
        self.author = _make_user("post_author")

    def test_create_post_with_required_fields(self):
        post = _make_post(self.author)

        self.assertEqual(post.author, self.author)
        self.assertEqual(post.title, "Test post")
        self.assertEqual(post.status, ApprovalStatus.PENDING)
        self.assertIsNotNone(post.created_at)
        self.assertIsNotNone(post.updated_at)

    def test_slug_must_be_unique(self):
        """
        Guards the underlying database constraint directly, bypassing the
        auto-generation in save() by assigning the same slug to both posts
        explicitly (still possible, since the field is not read-only).
        """
        _make_post(self.author, slug="same-slug")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _make_post(self.author, slug="same-slug", title="Another title")

    def test_slug_is_generated_automatically_from_the_title(self):
        post = _make_post(self.author, title="My First Jam Session Story")

        self.assertEqual(post.slug, "my-first-jam-session-story")

    def test_posts_with_the_same_title_get_a_unique_slug_suffix(self):
        first = _make_post(self.author, title="Great Gig Last Night")
        second = _make_post(self.author, title="Great Gig Last Night")

        self.assertEqual(first.slug, "great-gig-last-night")
        self.assertEqual(second.slug, "great-gig-last-night-2")

    def test_explicit_slug_is_not_overwritten(self):
        post = _make_post(
            self.author, title="Custom Slug Post", slug="my-custom-slug"
        )

        self.assertEqual(post.slug, "my-custom-slug")

    def test_editing_title_after_creation_does_not_change_existing_slug(self):
        post = _make_post(self.author, title="Original Title")
        original_slug = post.slug

        post.title = "Completely Different Title"
        post.save()

        self.assertEqual(post.slug, original_slug)

    def test_deleting_author_cascades_posts_for_privacy(self):
        post = _make_post(self.author)
        post_pk = post.pk

        self.author.delete()

        self.assertFalse(CommunityPost.objects.filter(pk=post_pk).exists())
        self.assertEqual(CommunityPost.objects.count(), 0)

    def test_apply_initial_moderation_reused_from_gallery(self):
        """Same ModeratedContent behaviour already proven for GalleryItem."""
        staff = _make_user("post_staff", is_staff=True)
        regular = _make_user("post_regular")

        staff_post = CommunityPost(author=staff, title="Staff post", body="body")
        staff_post.apply_initial_moderation(staff)
        staff_post.save()

        regular_post = CommunityPost(author=regular, title="Regular post", body="body")
        regular_post.apply_initial_moderation(regular)
        regular_post.save()

        self.assertEqual(staff_post.status, ApprovalStatus.APPROVED)
        self.assertEqual(staff_post.approved_by, staff)
        self.assertEqual(regular_post.status, ApprovalStatus.PENDING)
        self.assertIsNone(regular_post.approved_by)

    def test_approve_and_reject_update_expected_fields(self):
        moderator = _make_user("post_moderator", is_staff=True)
        post = _make_post(self.author)

        post.approve(moderator)
        self.assertEqual(post.status, ApprovalStatus.APPROVED)
        self.assertEqual(post.approved_by, moderator)
        self.assertIsNotNone(post.approved_at)

        post.reject(moderator, reason="Not relevant to jam sessions")
        self.assertEqual(post.status, ApprovalStatus.REJECTED)
        self.assertEqual(post.approved_by, moderator)
        self.assertEqual(post.rejection_reason, "Not relevant to jam sessions")


class CommunityPostMediaModelTests(TestCase):
    def setUp(self):
        self.author = _make_user("media_author")
        self.post = _make_post(self.author)

    def test_create_media_linked_to_post(self):
        media = CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )

        self.assertEqual(media.post, self.post)
        self.assertIn(media, self.post.media.all())

    def test_display_url_uses_web_friendly_image_delivery(self):
        media = CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )
        media.refresh_from_db()

        self.assertIn("photo_id", media.display_url)
        self.assertIn("f_auto", media.display_url)

    def test_deleting_post_cascades_to_its_media(self):
        media = CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )

        with patch("jamsession.cloudinary_cleanup.destroy"):
            with self.captureOnCommitCallbacks(execute=True):
                self.post.delete()

        self.assertFalse(CommunityPostMedia.objects.filter(pk=media.pk).exists())


class CommunityCommentModelTests(TestCase):
    def setUp(self):
        self.post_author = _make_user("comment_post_author")
        self.commenter = _make_user("commenter")
        self.post = _make_post(self.post_author)

    def test_create_comment_linked_to_post_and_author(self):
        comment = CommunityComment.objects.create(
            post=self.post, author=self.commenter, body="Nice jam!"
        )

        self.assertEqual(comment.post, self.post)
        self.assertEqual(comment.author, self.commenter)
        self.assertIn(comment, self.post.comments.all())
        self.assertEqual(comment.status, ApprovalStatus.PENDING)

    def test_deleting_commenter_cascades_comments_for_privacy(self):
        comment = CommunityComment.objects.create(
            post=self.post, author=self.commenter, body="Nice jam!"
        )
        comment_pk = comment.pk

        self.commenter.delete()

        self.assertFalse(CommunityComment.objects.filter(pk=comment_pk).exists())
        self.assertEqual(CommunityComment.objects.count(), 0)

    def test_deleting_post_cascades_to_its_comments(self):
        comment = CommunityComment.objects.create(
            post=self.post, author=self.commenter, body="Nice jam!"
        )

        self.post.delete()

        self.assertFalse(CommunityComment.objects.filter(pk=comment.pk).exists())


class CommunityCommentMediaModelTests(TestCase):
    def setUp(self):
        self.author = _make_user("comment_media_author")
        self.post = _make_post(self.author)
        self.comment = CommunityComment.objects.create(
            post=self.post, author=self.author, body="Check this out"
        )

    def test_create_media_linked_to_comment(self):
        media = CommunityCommentMedia.objects.create(
            comment=self.comment,
            file="video/upload/v1/clip_id.mp4",
            media_type=MediaType.VIDEO,
        )

        self.assertEqual(media.comment, self.comment)
        self.assertIn(media, self.comment.media.all())

    def test_deleting_comment_cascades_to_its_media(self):
        media = CommunityCommentMedia.objects.create(
            comment=self.comment,
            file="video/upload/v1/clip_id.mp4",
            media_type=MediaType.VIDEO,
        )

        with patch("jamsession.cloudinary_cleanup.destroy"):
            with self.captureOnCommitCallbacks(execute=True):
                self.comment.delete()

        self.assertFalse(CommunityCommentMedia.objects.filter(pk=media.pk).exists())


class CommunityLikeModelTests(TestCase):
    def setUp(self):
        self.post_author = _make_user("like_post_author")
        self.liker = _make_user("liker")
        self.post = _make_post(self.post_author)

    def test_create_like_linked_to_post_and_user(self):
        like = CommunityLike.objects.create(post=self.post, user=self.liker)

        self.assertEqual(like.post, self.post)
        self.assertEqual(like.user, self.liker)
        self.assertIn(like, self.post.likes.all())
        self.assertIsNotNone(like.created_at)

    def test_duplicate_like_from_same_user_is_rejected(self):
        CommunityLike.objects.create(post=self.post, user=self.liker)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CommunityLike.objects.create(post=self.post, user=self.liker)

    def test_deleting_post_cascades_to_its_likes(self):
        like = CommunityLike.objects.create(post=self.post, user=self.liker)

        self.post.delete()

        self.assertFalse(CommunityLike.objects.filter(pk=like.pk).exists())

    def test_deleting_liking_user_cascades_to_the_like(self):
        like = CommunityLike.objects.create(post=self.post, user=self.liker)

        self.liker.delete()

        self.assertFalse(CommunityLike.objects.filter(pk=like.pk).exists())


class CommunityPostListViewTests(TestCase):
    def setUp(self):
        self.author = _make_user("list_author")

    def test_only_approved_posts_are_listed(self):
        approved = _make_post(
            self.author, title="Approved", status=ApprovalStatus.APPROVED
        )
        _make_post(self.author, title="Pending", status=ApprovalStatus.PENDING)
        _make_post(self.author, title="Rejected", status=ApprovalStatus.REJECTED)

        response = self.client.get(reverse("community:list"))

        self.assertEqual(response.status_code, 200)
        listed = list(response.context["page_obj"].object_list)
        self.assertEqual(listed, [approved])

    def test_list_is_paginated(self):
        for index in range(12):
            _make_post(
                self.author,
                title=f"Post {index}",
                status=ApprovalStatus.APPROVED,
            )

        first_page = self.client.get(reverse("community:list"))
        second_page = self.client.get(reverse("community:list"), {"page": 2})

        self.assertEqual(len(first_page.context["page_obj"].object_list), 10)
        self.assertEqual(len(second_page.context["page_obj"].object_list), 2)

    def test_list_page_renders_the_post_title_as_a_link_to_its_detail_page(self):
        post = _make_post(
            self.author, title="A Great Session", status=ApprovalStatus.APPROVED
        )

        response = self.client.get(reverse("community:list"))

        self.assertContains(response, "A Great Session")
        # Anonymous visitors are sent through login with next= detail URL.
        detail_url = reverse("community:post_detail", args=[post.slug])
        self.assertContains(response, detail_url)
        self.assertContains(response, "Log in to read")
        self.assertContains(response, "community-layout--solo")
        self.assertNotContains(response, "members-sidebar")

    def test_authenticated_list_links_directly_to_detail_and_shows_members(self):
        post = _make_post(
            self.author, title="Member Session", status=ApprovalStatus.APPROVED
        )
        self.client.force_login(self.author)

        response = self.client.get(reverse("community:list"))

        self.assertContains(response, "Member Session")
        self.assertContains(
            response, reverse("community:post_detail", args=[post.slug])
        )
        self.assertContains(response, "Read more")
        self.assertNotContains(response, "community-layout--solo")
        self.assertContains(response, "members-sidebar")

    def test_empty_list_shows_the_empty_state_message(self):
        response = self.client.get(reverse("community:list"))

        self.assertContains(response, "No community posts yet")

    def test_list_shows_cover_image_url_when_present(self):
        post = _make_post(
            self.author, title="Covered", status=ApprovalStatus.APPROVED
        )
        _attach_cover(post)
        expected_url = post.cover_display_url

        response = self.client.get(reverse("community:list"))

        self.assertTrue(expected_url)
        self.assertContains(response, expected_url)
        self.assertContains(response, 'src="%s"' % expected_url)
        self.assertContains(response, "community-card__cover-image")
        self.assertNotContains(response, "community-card__cover--fallback")

    def test_list_shows_cover_fallback_when_absent(self):
        _make_post(self.author, title="No cover", status=ApprovalStatus.APPROVED)

        response = self.client.get(reverse("community:list"))

        self.assertContains(response, "community-card__cover--fallback")
        self.assertNotContains(response, "community-card__cover-image")


class CommunityPostDetailViewTests(TestCase):
    def setUp(self):
        self.author = _make_user("detail_author")
        self.other = _make_user("detail_other")

    def test_approved_post_requires_login(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        detail_url = reverse("community:post_detail", args=[post.slug])

        response = self.client.get(detail_url)

        self.assertRedirects(response, f"/accounts/login/?next={detail_url}")

    def test_approved_post_is_readable_by_members(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_pending_preview"])

    def test_detail_shows_cover_image_url_when_present(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        _attach_cover(post)
        expected_url = post.cover_detail_url
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertTrue(expected_url)
        self.assertContains(response, expected_url)
        self.assertContains(response, f'src="{expected_url}"')
        self.assertContains(response, "community-post__cover-image")
        self.assertNotContains(response, "community-post__cover--fallback")

    def test_detail_shows_cover_fallback_when_absent(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertContains(response, "community-post__cover--fallback")
        self.assertNotContains(response, "community-post__cover-image")

    def test_author_can_preview_own_pending_post(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.author)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_pending_preview"])

    def test_other_user_cannot_see_pending_post(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_see_pending_post(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        detail_url = reverse("community:post_detail", args=[post.slug])

        response = self.client.get(detail_url)

        self.assertRedirects(response, f"/accounts/login/?next={detail_url}")

    def test_author_cannot_open_own_rejected_post(self):
        post = _make_post(self.author, status=ApprovalStatus.REJECTED)
        self.client.force_login(self.author)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_open_rejected_post(self):
        post = _make_post(self.author, status=ApprovalStatus.REJECTED)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_open_rejected_post(self):
        post = _make_post(self.author, status=ApprovalStatus.REJECTED)
        detail_url = reverse("community:post_detail", args=[post.slug])

        response = self.client.get(detail_url)

        self.assertRedirects(response, f"/accounts/login/?next={detail_url}")

    def test_pending_badge_is_shown_to_the_author_previewing_their_own_post(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.author)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertContains(response, "Pending approval")

    def test_approved_post_page_does_not_show_pending_badge(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertNotContains(response, "Pending approval")

    def test_detail_page_renders_attached_media(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertContains(response, "community-media-item__image")
        self.assertContains(response, 'data-gallery-group="photos"')
        self.assertContains(response, 'id="gallery-lightbox"')
        self.assertContains(response, "gallery/js/gallery")

    def test_author_sees_the_delete_button_on_their_own_post(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.author)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertContains(response, "Delete post")

    def test_other_user_does_not_see_the_delete_button(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertNotContains(response, "Delete post")

    def test_like_button_reflects_whether_the_current_user_already_liked_the_post(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        CommunityLike.objects.create(post=post, user=self.other)
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )

        self.assertTrue(response.context["user_has_liked"])
        self.assertContains(response, "Liked")


class CommunityPostCreateViewTests(TestCase):
    def setUp(self):
        self.user = _make_user("creator")
        self.staff = _make_user("creator_staff", is_staff=True)

    def test_create_requires_login(self):
        response = self.client.get(reverse("community:post_create"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_regular_user_post_is_pending(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("community:post_create"),
            data={"title": "My jam", "body": "Great night"},
        )

        post = CommunityPost.objects.get()
        self.assertRedirects(
            response,
            reverse("community:post_detail", args=[post.slug]),
        )
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.status, ApprovalStatus.PENDING)

    def test_staff_post_is_auto_approved(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse("community:post_create"),
            data={"title": "Staff jam", "body": "Published now"},
        )

        post = CommunityPost.objects.get()
        self.assertEqual(post.status, ApprovalStatus.APPROVED)
        self.assertEqual(post.approved_by, self.staff)

    def test_post_with_media_creates_attachments(self):
        self.client.force_login(self.user)

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            self.client.post(
                reverse("community:post_create"),
                data={
                    "title": "With photo",
                    "body": "See attached",
                    "files": [_make_image_file()],
                },
            )

        post = CommunityPost.objects.get()
        self.assertEqual(post.media.count(), 1)
        self.assertEqual(post.media.first().media_type, MediaType.IMAGE)

    def test_post_with_invalid_media_is_rejected_and_saves_nothing(self):
        self.client.force_login(self.user)

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            response = self.client.post(
                reverse("community:post_create"),
                data={
                    "title": "Bad file",
                    "body": "Should fail",
                    "files": [_make_invalid_file()],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CommunityPost.objects.count(), 0)
        self.assertEqual(CommunityPostMedia.objects.count(), 0)

    def test_post_with_valid_cover_image_is_saved(self):
        self.client.force_login(self.user)

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            self.client.post(
                reverse("community:post_create"),
                data={
                    "title": "With cover",
                    "body": "Header photo",
                    "cover_image": _make_image_file(name="cover.jpg"),
                    "cover_focus_x": "35",
                    "cover_focus_y": "20",
                },
            )

        post = CommunityPost.objects.get()
        self.assertTrue(post.cover_image)
        self.assertTrue(post.cover_display_url)
        self.assertEqual(post.cover_focus_x, 35.0)
        self.assertEqual(post.cover_focus_y, 20.0)

    def test_post_with_invalid_cover_image_is_rejected_and_saves_nothing(self):
        self.client.force_login(self.user)

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            response = self.client.post(
                reverse("community:post_create"),
                data={
                    "title": "Bad cover",
                    "body": "Should fail",
                    "cover_image": _make_invalid_file(),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CommunityPost.objects.count(), 0)


class CommunityPostCoverFormTests(TestCase):
    """Unit tests for optional cover_image validation on CommunityPostForm."""

    def setUp(self):
        self.user = _make_user("cover_form_user")

    def test_form_accepts_a_valid_cover_image(self):
        form = CommunityPostForm(
            data={
                "title": "Covered jam",
                "body": "Body",
                "cover_focus_x": "40",
                "cover_focus_y": "25",
            },
            files={"cover_image": _make_image_file(name="hero.jpg")},
            user=self.user,
        )

        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            post = form.save()

        self.assertTrue(post.cover_image)
        self.assertEqual(post.cover_focus_x, 40.0)
        self.assertEqual(post.cover_focus_y, 25.0)

    def test_form_defaults_cover_focus_to_centre(self):
        form = CommunityPostForm(
            data={"title": "No focus sent", "body": "Body"},
            user=self.user,
        )

        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        post = form.save()
        self.assertEqual(post.cover_focus_x, 50.0)
        self.assertEqual(post.cover_focus_y, 50.0)
        self.assertEqual(post.author, self.user)

    def test_form_rejects_an_invalid_cover_image(self):
        form = CommunityPostForm(
            data={"title": "Bad cover", "body": "Body"},
            files={"cover_image": _make_invalid_file()},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("cover_image", form.errors)

    def test_form_rejects_a_video_as_cover_image(self):
        form = CommunityPostForm(
            data={"title": "Video cover", "body": "Body"},
            files={"cover_image": _make_minimal_mp4()},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("cover_image", form.errors)
        self.assertIn("photo", form.errors["cover_image"][0].lower())

    def test_form_allows_omitting_cover_image(self):
        form = CommunityPostForm(
            data={"title": "No cover", "body": "Body"},
            user=self.user,
        )

        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            post = form.save()

        self.assertFalse(bool(post.cover_image))


class CommunityCommentCreateViewTests(TestCase):
    def setUp(self):
        self.author = _make_user("cmt_author")
        self.commenter = _make_user("cmt_commenter")
        self.staff = _make_user("cmt_staff", is_staff=True)
        self.post = _make_post(self.author, status=ApprovalStatus.APPROVED)

    def test_comment_requires_login(self):
        response = self.client.post(
            reverse("community:comment_add", args=[self.post.slug]),
            data={"body": "Nice!"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        self.assertEqual(CommunityComment.objects.count(), 0)

    def test_regular_user_comment_is_pending(self):
        self.client.force_login(self.commenter)

        response = self.client.post(
            reverse("community:comment_add", args=[self.post.slug]),
            data={"body": "Great jam!"},
        )

        self.assertRedirects(
            response,
            reverse("community:post_detail", args=[self.post.slug]),
        )
        comment = CommunityComment.objects.get()
        self.assertEqual(comment.author, self.commenter)
        self.assertEqual(comment.post, self.post)
        self.assertEqual(comment.status, ApprovalStatus.PENDING)

    def test_staff_comment_is_auto_approved(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse("community:comment_add", args=[self.post.slug]),
            data={"body": "Approved instantly"},
        )

        comment = CommunityComment.objects.get()
        self.assertEqual(comment.status, ApprovalStatus.APPROVED)
        self.assertEqual(comment.approved_by, self.staff)

    def test_comment_with_media_creates_attachments(self):
        self.client.force_login(self.commenter)

        with patch(
            "cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource
        ):
            self.client.post(
                reverse("community:comment_add", args=[self.post.slug]),
                data={"body": "Look", "files": [_make_image_file()]},
            )

        comment = CommunityComment.objects.get()
        self.assertEqual(comment.media.count(), 1)
        self.assertEqual(CommunityCommentMedia.objects.count(), 1)

    def test_comment_author_sees_the_delete_button_on_their_own_comment(self):
        comment = CommunityComment.objects.create(
            post=self.post,
            author=self.commenter,
            body="A published comment",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.commenter)

        response = self.client.get(
            reverse("community:post_detail", args=[self.post.slug])
        )
        delete_url = reverse("community:comment_delete", args=[comment.pk])
        edit_url = reverse("community:comment_edit", args=[comment.pk])

        self.assertContains(response, comment.body)
        self.assertContains(response, f'action="{delete_url}"')
        self.assertContains(response, f'href="{edit_url}"')

    def test_other_user_does_not_see_the_comment_delete_button(self):
        comment = CommunityComment.objects.create(
            post=self.post,
            author=self.commenter,
            body="A published comment",
            status=ApprovalStatus.APPROVED,
        )
        other = _make_user("cmt_other")
        self.client.force_login(other)

        response = self.client.get(
            reverse("community:post_detail", args=[self.post.slug])
        )
        delete_url = reverse("community:comment_delete", args=[comment.pk])
        edit_url = reverse("community:comment_edit", args=[comment.pk])

        self.assertNotContains(response, f'action="{delete_url}"')
        self.assertNotContains(response, f'href="{edit_url}"')

    def test_comment_card_template_comment_does_not_leak_into_html(self):
        """
        Multi-line {# ... #} comments are not stripped by Django's lexer, so
        the partial must use {% comment %} / {% endcomment %} instead.
        """
        CommunityComment.objects.create(
            post=self.post,
            author=self.commenter,
            body="Wo wo wo!",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.commenter)

        response = self.client.get(
            reverse("community:post_detail", args=[self.post.slug])
        )

        self.assertContains(response, "Wo wo wo!")
        self.assertNotContains(response, "Single comment card")
        self.assertNotContains(response, "{#")
        self.assertNotContains(response, "#}")

    def test_comment_form_textarea_starts_compact(self):
        self.client.force_login(self.commenter)

        response = self.client.get(
            reverse("community:post_detail", args=[self.post.slug])
        )

        self.assertContains(response, 'rows="3"')
        self.assertContains(response, "Add a comment")


class CommunityUiPermissionConsistencyTests(TestCase):
    """
    UI placement rules for edit/delete/like controls:

    - Comment edit/delete and like toggle: only on community:post_detail
    - Post edit/delete: on community:post_detail and the owner's profile "My posts"
    """

    def setUp(self):
        self.author = _make_user("ui_perm_author")
        self.commenter = _make_user("ui_perm_commenter")
        self.post = _make_post(
            self.author,
            title="Permission UI post",
            status=ApprovalStatus.APPROVED,
        )
        self.comment = CommunityComment.objects.create(
            post=self.post,
            author=self.commenter,
            body="Permission UI comment",
            status=ApprovalStatus.APPROVED,
        )
        self.comment_delete_url = reverse(
            "community:comment_delete", args=[self.comment.pk]
        )
        self.comment_edit_url = reverse(
            "community:comment_edit", args=[self.comment.pk]
        )
        self.post_delete_url = reverse(
            "community:post_delete", args=[self.post.slug]
        )
        self.post_edit_url = reverse(
            "community:post_edit", args=[self.post.slug]
        )
        self.like_url = reverse("community:like_toggle", args=[self.post.slug])

    def test_post_detail_shows_comment_manage_like_and_post_manage(self):
        self.client.force_login(self.author)
        author_response = self.client.get(
            reverse("community:post_detail", args=[self.post.slug])
        )
        self.assertContains(author_response, f'action="{self.post_delete_url}"')
        self.assertContains(author_response, f'href="{self.post_edit_url}"')
        self.assertContains(author_response, f'action="{self.like_url}"')

        self.client.force_login(self.commenter)
        commenter_response = self.client.get(
            reverse("community:post_detail", args=[self.post.slug])
        )
        self.assertContains(
            commenter_response, f'action="{self.comment_delete_url}"'
        )
        self.assertContains(
            commenter_response, f'href="{self.comment_edit_url}"'
        )
        self.assertContains(commenter_response, f'action="{self.like_url}"')
        self.assertNotContains(
            commenter_response, f'action="{self.post_delete_url}"'
        )
        self.assertNotContains(
            commenter_response, f'href="{self.post_edit_url}"'
        )

    def test_post_list_has_no_comment_manage_like_toggle_or_post_manage(self):
        self.client.force_login(self.author)

        response = self.client.get(reverse("community:list"))

        self.assertContains(response, self.post.title)
        self.assertNotContains(response, f'action="{self.comment_delete_url}"')
        self.assertNotContains(response, f'href="{self.comment_edit_url}"')
        self.assertNotContains(response, f'action="{self.post_delete_url}"')
        self.assertNotContains(response, f'href="{self.post_edit_url}"')
        self.assertNotContains(response, f'action="{self.like_url}"')
        self.assertNotContains(response, "community:comment_delete")
        self.assertNotContains(response, "community:like_toggle")

    def test_owner_profile_has_post_manage_but_not_comment_manage_or_like(self):
        self.client.force_login(self.author)

        response = self.client.get(
            reverse(
                "accounts:profile_detail", kwargs={"username": self.author.username}
            )
        )

        self.assertContains(response, "My posts")
        self.assertContains(response, f'action="{self.post_delete_url}"')
        self.assertContains(response, f'href="{self.post_edit_url}"')
        self.assertNotContains(response, f'action="{self.comment_delete_url}"')
        self.assertNotContains(response, f'href="{self.comment_edit_url}"')
        self.assertNotContains(response, f'action="{self.like_url}"')


class CommunityLikeToggleViewTests(TestCase):
    def setUp(self):
        self.author = _make_user("like_view_author")
        self.liker = _make_user("like_view_liker")
        self.post = _make_post(self.author, status=ApprovalStatus.APPROVED)

    def test_like_requires_login(self):
        response = self.client.post(
            reverse("community:like_toggle", args=[self.post.slug])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        self.assertEqual(CommunityLike.objects.count(), 0)

    def test_like_only_accepts_post_requests(self):
        self.client.force_login(self.liker)

        response = self.client.get(
            reverse("community:like_toggle", args=[self.post.slug])
        )

        self.assertEqual(response.status_code, 405)

    def test_like_on_pending_post_returns_404(self):
        pending = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.liker)

        response = self.client.post(
            reverse("community:like_toggle", args=[pending.slug])
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(CommunityLike.objects.count(), 0)

    def test_toggle_adds_then_removes_the_like(self):
        self.client.force_login(self.liker)
        url = reverse("community:like_toggle", args=[self.post.slug])

        self.client.post(url)
        self.assertEqual(
            CommunityLike.objects.filter(post=self.post, user=self.liker).count(),
            1,
        )

        self.client.post(url)
        self.assertEqual(
            CommunityLike.objects.filter(post=self.post, user=self.liker).count(),
            0,
        )


class CommunityPostDeletePermissionTests(TestCase):
    def setUp(self):
        self.author = _make_user("del_post_author")
        self.other = _make_user("del_post_other")
        self.staff = _make_user("del_post_staff", is_staff=True)

    def test_delete_requires_login(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)

        response = self.client.post(
            reverse("community:post_delete", args=[post.slug])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_author_can_delete_own_post(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.author)

        response = self.client.post(
            reverse("community:post_delete", args=[post.slug])
        )

        self.assertRedirects(response, reverse("community:list"))
        self.assertFalse(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_other_user_cannot_delete_another_users_post_even_by_direct_post(self):
        """A forged direct POST (no template button) must still be refused."""
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("community:post_delete", args=[post.slug])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_staff_can_delete_another_users_post(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:post_delete", args=[post.slug])
        )

        self.assertRedirects(response, reverse("community:list"))
        self.assertFalse(CommunityPost.objects.filter(pk=post.pk).exists())


class CommunityCommentDeletePermissionTests(TestCase):
    def setUp(self):
        self.post_author = _make_user("delc_post_author")
        self.comment_author = _make_user("delc_author")
        self.other = _make_user("delc_other")
        self.staff = _make_user("delc_staff", is_staff=True)
        self.post = _make_post(self.post_author, status=ApprovalStatus.APPROVED)

    def _make_comment(self):
        return CommunityComment.objects.create(
            post=self.post,
            author=self.comment_author,
            body="A comment",
            status=ApprovalStatus.APPROVED,
        )

    def test_delete_requires_login(self):
        comment = self._make_comment()

        response = self.client.post(
            reverse("community:comment_delete", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        self.assertTrue(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_author_can_delete_own_comment(self):
        comment = self._make_comment()
        self.client.force_login(self.comment_author)

        response = self.client.post(
            reverse("community:comment_delete", args=[comment.pk])
        )

        self.assertRedirects(
            response,
            reverse("community:post_detail", args=[self.post.slug]),
        )
        self.assertFalse(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_other_user_cannot_delete_another_users_comment_even_by_direct_post(self):
        comment = self._make_comment()
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("community:comment_delete", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_staff_can_delete_another_users_comment(self):
        comment = self._make_comment()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:comment_delete", args=[comment.pk])
        )

        self.assertRedirects(
            response,
            reverse("community:post_detail", args=[self.post.slug]),
        )
        self.assertFalse(CommunityComment.objects.filter(pk=comment.pk).exists())


class CommunityPostEditPermissionTests(TestCase):
    def setUp(self):
        self.author = _make_user("edit_post_author")
        self.other = _make_user("edit_post_other")
        self.staff = _make_user("edit_post_staff", is_staff=True)

    def test_edit_requires_login(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)

        response = self.client.get(
            reverse("community:post_edit", args=[post.slug])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_author_can_edit_own_post_and_returns_to_pending(self):
        post = _make_post(
            self.author,
            title="Original title",
            body="Original body",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.author)

        response = self.client.post(
            reverse("community:post_edit", args=[post.slug]),
            {"title": "Updated title", "body": "Updated body"},
        )

        post.refresh_from_db()
        self.assertRedirects(
            response, reverse("community:post_detail", args=[post.slug])
        )
        self.assertEqual(post.title, "Updated title")
        self.assertEqual(post.body, "Updated body")
        self.assertEqual(post.author_id, self.author.id)
        self.assertEqual(post.status, ApprovalStatus.PENDING)

    def test_other_user_cannot_edit_another_users_post(self):
        post = _make_post(
            self.author,
            title="Keep me",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("community:post_edit", args=[post.slug]),
            {"title": "Hijacked", "body": "Nope"},
        )

        post.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(post.title, "Keep me")
        self.assertEqual(post.status, ApprovalStatus.APPROVED)

    def test_staff_can_edit_another_users_post_without_losing_approval(self):
        post = _make_post(
            self.author,
            title="Staff edit me",
            body="Before",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:post_edit", args=[post.slug]),
            {"title": "Staff edited", "body": "After"},
        )

        post.refresh_from_db()
        self.assertRedirects(
            response, reverse("community:post_detail", args=[post.slug])
        )
        self.assertEqual(post.title, "Staff edited")
        self.assertEqual(post.body, "After")
        self.assertEqual(post.author_id, self.author.id)
        self.assertEqual(post.status, ApprovalStatus.APPROVED)


class CommunityCommentEditPermissionTests(TestCase):
    def setUp(self):
        self.post_author = _make_user("editc_post_author")
        self.comment_author = _make_user("editc_author")
        self.other = _make_user("editc_other")
        self.staff = _make_user("editc_staff", is_staff=True)
        self.post = _make_post(self.post_author, status=ApprovalStatus.APPROVED)

    def _make_comment(self, body="A comment"):
        return CommunityComment.objects.create(
            post=self.post,
            author=self.comment_author,
            body=body,
            status=ApprovalStatus.APPROVED,
        )

    def test_edit_requires_login(self):
        comment = self._make_comment()

        response = self.client.get(
            reverse("community:comment_edit", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_author_can_edit_own_comment_and_returns_to_pending(self):
        comment = self._make_comment(body="Original comment")
        self.client.force_login(self.comment_author)

        response = self.client.post(
            reverse("community:comment_edit", args=[comment.pk]),
            {"body": "Updated comment"},
        )

        comment.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("community:post_detail", args=[self.post.slug]),
        )
        self.assertEqual(comment.body, "Updated comment")
        self.assertEqual(comment.author_id, self.comment_author.id)
        self.assertEqual(comment.status, ApprovalStatus.PENDING)

    def test_other_user_cannot_edit_another_users_comment(self):
        comment = self._make_comment(body="Keep me")
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("community:comment_edit", args=[comment.pk]),
            {"body": "Hijacked"},
        )

        comment.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(comment.body, "Keep me")
        self.assertEqual(comment.status, ApprovalStatus.APPROVED)

    def test_staff_can_edit_another_users_comment_without_losing_approval(self):
        comment = self._make_comment(body="Before")
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:comment_edit", args=[comment.pk]),
            {"body": "After"},
        )

        comment.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("community:post_detail", args=[self.post.slug]),
        )
        self.assertEqual(comment.body, "After")
        self.assertEqual(comment.author_id, self.comment_author.id)
        self.assertEqual(comment.status, ApprovalStatus.APPROVED)


class CommunityPostAdminActionsTests(TestCase):
    """Tests for approve_posts / reject_posts (mirrors GalleryAdminActionsTests)."""

    def setUp(self):
        self.moderator = _make_user("post_mod", is_staff=True)
        self.author = _make_user("post_admin_author")

    def test_approve_posts_action_approves_only_pending_posts(self):
        pending = _make_post(
            self.author, title="Pending", status=ApprovalStatus.PENDING
        )
        already_approved = _make_post(
            self.author, title="Already", status=ApprovalStatus.APPROVED
        )
        request = SimpleNamespace(user=self.moderator)
        modeladmin = Mock()

        approve_posts(modeladmin, request, CommunityPost.objects.all())

        pending.refresh_from_db()
        already_approved.refresh_from_db()
        self.assertEqual(pending.status, ApprovalStatus.APPROVED)
        self.assertEqual(pending.approved_by, self.moderator)
        self.assertIsNotNone(pending.approved_at)
        # Untouched: the action only processes items that were pending.
        self.assertIsNone(already_approved.approved_by)
        modeladmin.message_user.assert_called_once()

    def test_reject_posts_action_rejects_only_pending_posts(self):
        pending = _make_post(
            self.author, title="To reject", status=ApprovalStatus.PENDING
        )
        already_rejected = _make_post(
            self.author, title="Already", status=ApprovalStatus.REJECTED
        )
        request = SimpleNamespace(user=self.moderator)
        modeladmin = Mock()

        reject_posts(modeladmin, request, CommunityPost.objects.all())

        pending.refresh_from_db()
        already_rejected.refresh_from_db()
        self.assertEqual(pending.status, ApprovalStatus.REJECTED)
        self.assertEqual(pending.approved_by, self.moderator)
        # Untouched: the action only processes items that were pending.
        self.assertIsNone(already_rejected.approved_by)
        modeladmin.message_user.assert_called_once()


class CommunityCommentAdminActionsTests(TestCase):
    """Tests for approve_comments / reject_comments (mirrors GalleryAdminActionsTests)."""

    def setUp(self):
        self.moderator = _make_user("comment_mod", is_staff=True)
        self.author = _make_user("comment_admin_author")
        self.post = _make_post(self.author, status=ApprovalStatus.APPROVED)

    def _make_comment(self, status):
        return CommunityComment.objects.create(
            post=self.post,
            author=self.author,
            body="A comment",
            status=status,
        )

    def test_approve_comments_action_approves_only_pending_comments(self):
        pending = self._make_comment(ApprovalStatus.PENDING)
        already_approved = self._make_comment(ApprovalStatus.APPROVED)
        request = SimpleNamespace(user=self.moderator)
        modeladmin = Mock()

        approve_comments(modeladmin, request, CommunityComment.objects.all())

        pending.refresh_from_db()
        already_approved.refresh_from_db()
        self.assertEqual(pending.status, ApprovalStatus.APPROVED)
        self.assertEqual(pending.approved_by, self.moderator)
        self.assertIsNotNone(pending.approved_at)
        self.assertIsNone(already_approved.approved_by)
        modeladmin.message_user.assert_called_once()

    def test_reject_comments_action_rejects_only_pending_comments(self):
        pending = self._make_comment(ApprovalStatus.PENDING)
        already_rejected = self._make_comment(ApprovalStatus.REJECTED)
        request = SimpleNamespace(user=self.moderator)
        modeladmin = Mock()

        reject_comments(modeladmin, request, CommunityComment.objects.all())

        pending.refresh_from_db()
        already_rejected.refresh_from_db()
        self.assertEqual(pending.status, ApprovalStatus.REJECTED)
        self.assertEqual(pending.approved_by, self.moderator)
        self.assertIsNone(already_rejected.approved_by)
        modeladmin.message_user.assert_called_once()


class CommunityAdminMediaPreviewTests(TestCase):
    """
    Admin media previews must emit a resolvable file URL in the rendered HTML.

    Images go through web_image_url (f_auto) so HEIC uploads are browser-safe;
    the change form must include that URL both in the inline column and in the
    parent Media fieldset gallery.
    """

    def setUp(self):
        self.staff = _make_user("admin_preview_staff", is_staff=True, is_superuser=True)
        self.author = _make_user("admin_preview_author")
        self.client.force_login(self.staff)

    def test_resolve_media_url_returns_web_friendly_image_url(self):
        post = _make_post(self.author)
        media = CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )

        url = _resolve_media_url(media, width=300)

        self.assertTrue(url)
        self.assertIn("photo_id", url)
        # f_auto is what makes HEIC/HEIF render in the browser.
        self.assertIn("f_auto", url)

    def test_media_preview_html_includes_file_url(self):
        post = _make_post(self.author)
        media = CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )

        html = str(_media_preview(media, width=300, height=300))

        self.assertIn("<img", html)
        self.assertIn(_resolve_media_url(media, width=300), html)

    def test_post_change_form_renders_media_preview_url(self):
        post = _make_post(self.author, title="Post with photo")
        media = CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )
        expected_url = _resolve_media_url(media, width=300)
        self.assertTrue(expected_url)

        response = self.client.get(
            reverse("admin:community_communitypost_change", args=[post.pk])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(expected_url, content)
        self.assertIn(f'src="{expected_url}"', content)

    def test_comment_change_form_renders_media_preview_url(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        comment = CommunityComment.objects.create(
            post=post, author=self.author, body="With clip"
        )
        media = CommunityCommentMedia.objects.create(
            comment=comment,
            file="video/upload/v1/clip_id.mp4",
            media_type=MediaType.VIDEO,
        )
        admin = CommunityCommentAdmin(CommunityComment, Mock())
        expected_url = _resolve_media_url(media)

        response = self.client.get(
            reverse("admin:community_communitycomment_change", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(expected_url, content)
        self.assertIn("<video", content)
        # Parent gallery preview method also exposes the URL.
        self.assertIn(expected_url, str(admin.media_gallery(comment)))

    def test_post_admin_media_gallery_includes_attachment_url(self):
        post = _make_post(self.author)
        media = CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )
        admin = CommunityPostAdmin(CommunityPost, Mock())

        html = str(admin.media_gallery(post))

        self.assertIn(_resolve_media_url(media, width=300), html)


class CommunityModerationQueueViewTests(TestCase):
    """
    Tests for the legacy moderation_queue URL and the Admin Tool To review tab.

    moderation_queue now redirects into Admin Tool (?tab=review). Content
    assertions hit the hub directly.
    """

    def setUp(self):
        self.staff = _make_user("queue_staff", is_staff=True)
        self.superuser = _make_user(
            "queue_super", is_staff=True, is_superuser=True
        )
        self.regular = _make_user("queue_regular")
        self.author = _make_user("queue_author")
        self.queue_url = reverse("community:moderation_queue")
        self.review_url = reverse("community:admin_tool") + "?tab=review"

    def test_queue_requires_login(self):
        response = self.client.get(self.queue_url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_regular_user_gets_403(self):
        self.client.force_login(self.regular)

        response = self.client.get(self.queue_url)

        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_access_the_queue(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.queue_url)

        self.assertRedirects(response, self.review_url)

    def test_superuser_can_access_the_queue(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.queue_url)

        self.assertRedirects(response, self.review_url)

    def test_only_pending_posts_and_comments_are_listed(self):
        pending_post = _make_post(
            self.author, title="Pending post", status=ApprovalStatus.PENDING
        )
        approved_post = _make_post(
            self.author, title="Approved post", status=ApprovalStatus.APPROVED
        )
        _make_post(self.author, title="Rejected post", status=ApprovalStatus.REJECTED)

        approved_post_for_comments = _make_post(
            self.author, title="Host post", status=ApprovalStatus.APPROVED
        )
        pending_comment = CommunityComment.objects.create(
            post=approved_post_for_comments,
            author=self.author,
            body="Pending comment",
            status=ApprovalStatus.PENDING,
        )
        CommunityComment.objects.create(
            post=approved_post_for_comments,
            author=self.author,
            body="Approved comment",
            status=ApprovalStatus.APPROVED,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.review_url)

        self.assertEqual(
            list(response.context["pending_posts"]), [pending_post]
        )
        self.assertEqual(
            list(response.context["pending_comments"]), [pending_comment]
        )
        self.assertContains(response, "Pending post")
        self.assertNotContains(response, "Approved post")
        self.assertContains(response, "Pending comment")
        self.assertNotContains(response, "Approved comment")

    def test_only_pending_gallery_items_are_listed(self):
        pending_item = GalleryItem.objects.create(
            uploaded_by=self.author,
            file="image/upload/v1/pending_gallery.jpg",
            media_type=MediaType.IMAGE,
            title="Pending gallery shot",
            status=ApprovalStatus.PENDING,
        )
        GalleryItem.objects.create(
            uploaded_by=self.author,
            file="image/upload/v1/approved_gallery.jpg",
            media_type=MediaType.IMAGE,
            title="Approved gallery shot",
            status=ApprovalStatus.APPROVED,
        )
        GalleryItem.objects.create(
            uploaded_by=self.author,
            file="image/upload/v1/rejected_gallery.jpg",
            media_type=MediaType.IMAGE,
            title="Rejected gallery shot",
            status=ApprovalStatus.REJECTED,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.review_url)

        self.assertEqual(
            list(response.context["pending_gallery_items"]), [pending_item]
        )
        self.assertContains(response, "Gallery submissions")
        self.assertContains(response, "Pending gallery shot")
        self.assertNotContains(response, "Approved gallery shot")
        self.assertNotContains(response, "Rejected gallery shot")

    def test_pending_items_are_ordered_oldest_first(self):
        older = _make_post(
            self.author, title="Older", status=ApprovalStatus.PENDING
        )
        newer = _make_post(
            self.author, title="Newer", status=ApprovalStatus.PENDING
        )
        # Force a clearly distinguishable order regardless of auto_now_add clock
        # resolution, the same way other tests in this file avoid timing flakiness.
        CommunityPost.objects.filter(pk=older.pk).update(
            created_at=newer.created_at - timezone.timedelta(days=1)
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.review_url)

        self.assertEqual(
            list(response.context["pending_posts"]), [older, newer]
        )

    def test_queue_shows_attached_media(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        media = CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )
        # Reload so CloudinaryField deserialises the stored path into a
        # CloudinaryResource (same shape the review-tab queryset sees).
        media.refresh_from_db()
        expected_url = media.display_url

        self.client.force_login(self.staff)
        response = self.client.get(self.review_url)

        self.assertTrue(expected_url)
        self.assertIn("f_auto", expected_url)
        self.assertContains(response, expected_url)
        self.assertContains(response, f'src="{expected_url}"')
        self.assertContains(response, "moderation-media-item__image")

    def test_queue_shows_gallery_item_media_preview(self):
        item = GalleryItem.objects.create(
            uploaded_by=self.author,
            file="image/upload/v1/gallery_preview.jpg",
            media_type=MediaType.IMAGE,
            title="Preview me",
            status=ApprovalStatus.PENDING,
        )
        item.refresh_from_db()
        expected_url = item.display_media_url

        self.client.force_login(self.staff)
        response = self.client.get(self.review_url)

        self.assertTrue(expected_url)
        self.assertIn("f_auto", expected_url)
        self.assertContains(response, expected_url)
        self.assertContains(response, f'src="{expected_url}"')
        self.assertContains(response, "moderation-media-item__image")

    def test_queue_shows_gallery_item_video_preview(self):
        item = GalleryItem.objects.create(
            uploaded_by=self.author,
            file="video/upload/v1/gallery_preview.mp4",
            media_type=MediaType.VIDEO,
            title="Preview video",
            status=ApprovalStatus.PENDING,
        )
        # Plain string paths have no resource_type, so save()'s
        # _sync_media_type() resets media_type to "image". Force VIDEO at
        # the DB level (same workaround as gallery list tests).
        GalleryItem.objects.filter(pk=item.pk).update(media_type=MediaType.VIDEO)
        item.refresh_from_db()
        expected_url = item.display_media_url

        self.client.force_login(self.staff)
        response = self.client.get(self.review_url)

        self.assertTrue(expected_url)
        self.assertTrue(item.is_video)
        self.assertContains(response, expected_url)
        self.assertContains(response, f'src="{expected_url}"')
        self.assertContains(response, "moderation-media-item__video")
        self.assertContains(response, "<video")
        self.assertNotContains(response, "moderation-media-item__image")


class CommunityModerationPostActionViewTests(TestCase):
    """Tests for moderation_post_approve/reject/delete."""

    def setUp(self):
        self.staff = _make_user("mod_post_staff", is_staff=True)
        self.regular = _make_user("mod_post_regular")
        self.author = _make_user("mod_post_author")

    def test_approve_requires_login(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)

        response = self.client.post(
            reverse("community:moderation_post_approve", args=[post.slug])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        post.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.PENDING)

    def test_regular_user_cannot_approve(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_post_approve", args=[post.slug])
        )

        self.assertEqual(response.status_code, 403)
        post.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.PENDING)

    def test_approve_only_accepts_post_requests(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("community:moderation_post_approve", args=[post.slug])
        )

        self.assertEqual(response.status_code, 405)

    def test_staff_can_approve_a_pending_post(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_post_approve", args=[post.slug])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        post.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.APPROVED)
        self.assertEqual(post.approved_by, self.staff)
        self.assertIsNotNone(post.approved_at)

    def test_approving_an_already_approved_post_returns_404(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_post_approve", args=[post.slug])
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_can_reject_a_pending_post_with_a_reason(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_post_reject", args=[post.slug]),
            {"reason": "Not related to jam sessions"},
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        post.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.REJECTED)
        self.assertEqual(post.approved_by, self.staff)
        self.assertEqual(post.rejection_reason, "Not related to jam sessions")

    def test_staff_can_reject_a_pending_post_without_a_reason(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_post_reject", args=[post.slug])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        post.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.REJECTED)
        self.assertEqual(post.rejection_reason, "")

    def test_regular_user_cannot_reject(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_post_reject", args=[post.slug])
        )

        self.assertEqual(response.status_code, 403)
        post.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.PENDING)

    def test_staff_can_delete_a_pending_post(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_post_delete", args=[post.slug])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        self.assertFalse(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_regular_user_cannot_delete_from_the_queue(self):
        post = _make_post(self.author, status=ApprovalStatus.PENDING)
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_post_delete", args=[post.slug])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_deleting_an_already_approved_post_via_the_queue_returns_404(self):
        post = _make_post(self.author, status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_post_delete", args=[post.slug])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())


class CommunityModerationCommentActionViewTests(TestCase):
    """Tests for moderation_comment_approve/reject/delete."""

    def setUp(self):
        self.staff = _make_user("mod_comment_staff", is_staff=True)
        self.regular = _make_user("mod_comment_regular")
        self.author = _make_user("mod_comment_author")
        self.post = _make_post(self.author, status=ApprovalStatus.APPROVED)

    def _make_comment(self, status=ApprovalStatus.PENDING):
        return CommunityComment.objects.create(
            post=self.post, author=self.author, body="A comment", status=status
        )

    def test_approve_requires_login(self):
        comment = self._make_comment()

        response = self.client.post(
            reverse("community:moderation_comment_approve", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        comment.refresh_from_db()
        self.assertEqual(comment.status, ApprovalStatus.PENDING)

    def test_regular_user_cannot_approve(self):
        comment = self._make_comment()
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_comment_approve", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.status, ApprovalStatus.PENDING)

    def test_staff_can_approve_a_pending_comment(self):
        comment = self._make_comment()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_comment_approve", args=[comment.pk])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        comment.refresh_from_db()
        self.assertEqual(comment.status, ApprovalStatus.APPROVED)
        self.assertEqual(comment.approved_by, self.staff)
        self.assertIsNotNone(comment.approved_at)

    def test_staff_can_reject_a_pending_comment_with_a_reason(self):
        comment = self._make_comment()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_comment_reject", args=[comment.pk]),
            {"reason": "Off-topic"},
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        comment.refresh_from_db()
        self.assertEqual(comment.status, ApprovalStatus.REJECTED)
        self.assertEqual(comment.approved_by, self.staff)
        self.assertEqual(comment.rejection_reason, "Off-topic")

    def test_regular_user_cannot_reject(self):
        comment = self._make_comment()
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_comment_reject", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.status, ApprovalStatus.PENDING)

    def test_staff_can_delete_a_pending_comment(self):
        comment = self._make_comment()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_comment_delete", args=[comment.pk])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        self.assertFalse(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_regular_user_cannot_delete_from_the_queue(self):
        comment = self._make_comment()
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_comment_delete", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_deleting_an_already_approved_comment_via_the_queue_returns_404(self):
        comment = self._make_comment(status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_comment_delete", args=[comment.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(CommunityComment.objects.filter(pk=comment.pk).exists())


class CommunityModerationGalleryActionViewTests(TestCase):
    """Tests for moderation_gallery_approve/reject/delete."""

    def setUp(self):
        self.staff = _make_user("mod_gallery_staff", is_staff=True)
        self.regular = _make_user("mod_gallery_regular")
        self.uploader = _make_user("mod_gallery_uploader")

    def _make_item(self, status=ApprovalStatus.PENDING, **overrides):
        defaults = {
            "uploaded_by": self.uploader,
            "file": "image/upload/v1/mod_gallery.jpg",
            "media_type": MediaType.IMAGE,
            "title": "Jam night shot",
            "status": status,
        }
        defaults.update(overrides)
        return GalleryItem.objects.create(**defaults)

    def test_approve_requires_login(self):
        item = self._make_item()

        response = self.client.post(
            reverse("community:moderation_gallery_approve", args=[item.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        item.refresh_from_db()
        self.assertEqual(item.status, ApprovalStatus.PENDING)

    def test_regular_user_cannot_approve(self):
        item = self._make_item()
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_gallery_approve", args=[item.pk])
        )

        self.assertEqual(response.status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.status, ApprovalStatus.PENDING)

    def test_approve_only_accepts_post_requests(self):
        item = self._make_item()
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("community:moderation_gallery_approve", args=[item.pk])
        )

        self.assertEqual(response.status_code, 405)

    def test_staff_can_approve_a_pending_gallery_item(self):
        item = self._make_item()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_gallery_approve", args=[item.pk])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        item.refresh_from_db()
        self.assertEqual(item.status, ApprovalStatus.APPROVED)
        self.assertEqual(item.approved_by, self.staff)
        self.assertIsNotNone(item.approved_at)

    def test_approving_an_already_approved_gallery_item_returns_404(self):
        item = self._make_item(status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_gallery_approve", args=[item.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_can_reject_a_pending_gallery_item_with_a_reason(self):
        item = self._make_item()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_gallery_reject", args=[item.pk]),
            {"reason": "Blurry photo"},
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        item.refresh_from_db()
        self.assertEqual(item.status, ApprovalStatus.REJECTED)
        self.assertEqual(item.approved_by, self.staff)
        self.assertEqual(item.rejection_reason, "Blurry photo")

    def test_staff_can_reject_a_pending_gallery_item_without_a_reason(self):
        item = self._make_item()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_gallery_reject", args=[item.pk])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        item.refresh_from_db()
        self.assertEqual(item.status, ApprovalStatus.REJECTED)
        self.assertEqual(item.rejection_reason, "")

    def test_regular_user_cannot_reject(self):
        item = self._make_item()
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_gallery_reject", args=[item.pk])
        )

        self.assertEqual(response.status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.status, ApprovalStatus.PENDING)

    def test_staff_can_delete_a_pending_gallery_item(self):
        item = self._make_item()
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_gallery_delete", args=[item.pk])
        )

        self.assertRedirects(response, reverse("community:admin_tool") + "?tab=review")
        self.assertFalse(GalleryItem.objects.filter(pk=item.pk).exists())

    def test_regular_user_cannot_delete_from_the_queue(self):
        item = self._make_item()
        self.client.force_login(self.regular)

        response = self.client.post(
            reverse("community:moderation_gallery_delete", args=[item.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(GalleryItem.objects.filter(pk=item.pk).exists())

    def test_deleting_an_already_approved_gallery_item_via_the_queue_returns_404(self):
        item = self._make_item(status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("community:moderation_gallery_delete", args=[item.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(GalleryItem.objects.filter(pk=item.pk).exists())


class CommunityCloudinaryCleanupSignalTests(TestCase):
    """
    Cloudinary cleanup for community attachments (and cover images).

    Real Cloudinary destroy() is always mocked — these tests only prove the
    shared jamsession.cloudinary_cleanup helpers are invoked correctly when
    rows are deleted, including CASCADE from a parent post/comment.
    """

    def setUp(self):
        self.author = _make_user("cleanup_author")
        self.post = _make_post(self.author, title="Cleanup post", body="Body")

    def test_deleting_post_destroys_every_attachment_on_cloudinary(self):
        CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/post_media_one.jpg",
            media_type=MediaType.IMAGE,
        )
        CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/post_media_two.jpg",
            media_type=MediaType.IMAGE,
        )
        CommunityPostMedia.objects.create(
            post=self.post,
            file="video/upload/v1/post_media_three.mp4",
            media_type=MediaType.VIDEO,
        )

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                self.post.delete()

        self.assertEqual(mock_destroy.call_count, 3)
        destroyed_ids = {call.args[0] for call in mock_destroy.call_args_list}
        self.assertEqual(
            destroyed_ids,
            {"post_media_one", "post_media_two", "post_media_three"},
        )

    def test_deleting_comment_destroys_its_attachments_on_cloudinary(self):
        comment = CommunityComment.objects.create(
            post=self.post, author=self.author, body="With media"
        )
        CommunityCommentMedia.objects.create(
            comment=comment,
            file="image/upload/v1/comment_media_one.jpg",
            media_type=MediaType.IMAGE,
        )
        CommunityCommentMedia.objects.create(
            comment=comment,
            file="video/upload/v1/comment_media_two.mp4",
            media_type=MediaType.VIDEO,
        )

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                comment.delete()

        self.assertEqual(mock_destroy.call_count, 2)
        destroyed_ids = {call.args[0] for call in mock_destroy.call_args_list}
        self.assertEqual(
            destroyed_ids,
            {"comment_media_one", "comment_media_two"},
        )

    def test_deleting_post_with_no_media_does_not_call_destroy(self):
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                self.post.delete()

        mock_destroy.assert_not_called()

    def test_deleting_comment_with_no_media_does_not_call_destroy(self):
        comment = CommunityComment.objects.create(
            post=self.post, author=self.author, body="Text only"
        )

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                comment.delete()

        mock_destroy.assert_not_called()

    def test_deleting_a_single_post_media_row_destroys_only_that_file(self):
        """
        Mirrors Django admin inline deletion: remove one CommunityPostMedia
        without deleting the parent CommunityPost.

        refresh_from_db() is required so CloudinaryField deserialises the
        stored path into a CloudinaryResource (same as gallery cleanup tests);
        otherwise post_delete sees a bare string and skips destroy().
        """
        keep = CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/keep_me.jpg",
            media_type=MediaType.IMAGE,
        )
        remove = CommunityPostMedia.objects.create(
            post=self.post,
            file="image/upload/v1/remove_me.jpg",
            media_type=MediaType.IMAGE,
        )
        remove.refresh_from_db()

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                remove.delete()

        mock_destroy.assert_called_once_with(
            "remove_me", resource_type="image", invalidate=True
        )
        self.assertTrue(CommunityPost.objects.filter(pk=self.post.pk).exists())
        self.assertTrue(CommunityPostMedia.objects.filter(pk=keep.pk).exists())
        self.assertFalse(CommunityPostMedia.objects.filter(pk=remove.pk).exists())

    def test_deleting_a_single_comment_media_row_destroys_only_that_file(self):
        comment = CommunityComment.objects.create(
            post=self.post, author=self.author, body="With one attachment"
        )
        media = CommunityCommentMedia.objects.create(
            comment=comment,
            file="image/upload/v1/solo_comment_media.jpg",
            media_type=MediaType.IMAGE,
        )
        media.refresh_from_db()

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                media.delete()

        mock_destroy.assert_called_once_with(
            "solo_comment_media", resource_type="image", invalidate=True
        )
        self.assertTrue(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_replacing_cover_image_destroys_the_old_cloudinary_resource(self):
        """pre_save cover cleanup: replacing cover_image must destroy the old asset."""
        _attach_cover(self.post, public_id="image/upload/v1/old_cover.jpg")

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            self.post.cover_image = "image/upload/v1/new_cover.jpg"
            self.post.save(update_fields=["cover_image"])

        mock_destroy.assert_called_once_with(
            "old_cover", resource_type="image", invalidate=True
        )

    def test_deleting_post_destroys_its_cover_image_on_cloudinary(self):
        """post_delete cover cleanup: deleting the post must destroy cover_image."""
        _attach_cover(self.post, public_id="image/upload/v1/cover_to_remove.jpg")

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                self.post.delete()

        mock_destroy.assert_called_once_with(
            "cover_to_remove", resource_type="image", invalidate=True
        )

    def test_saving_post_without_changing_cover_does_not_destroy_it(self):
        """Guards against accidental destroy when only non-cover fields change."""
        _attach_cover(self.post, public_id="image/upload/v1/stable_cover.jpg")

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            self.post.title = "Updated title only"
            self.post.save(update_fields=["title"])

        mock_destroy.assert_not_called()


class AdminToolTests(TestCase):
    """Staff Admin Tool listing, previews, single/bulk delete, and permissions."""

    def setUp(self):
        self.staff = _make_user("admin_tool_staff", is_staff=True)
        self.regular = _make_user("admin_tool_member")
        self.tool_url = reverse("community:admin_tool")
        self.gallery_tab_url = self.tool_url + "?tab=gallery"
        self.community_tab_url = self.tool_url + "?tab=community"
        self.review_tab_url = self.tool_url + "?tab=review"
        self.bulk_url = reverse("community:admin_tool_bulk_delete")
        self.bulk_moderate_url = reverse("community:admin_tool_bulk_moderate")

    def test_non_staff_gets_403(self):
        self.client.force_login(self.regular)
        response = self.client.get(self.tool_url)
        self.assertEqual(response.status_code, 403)

    def test_non_staff_gets_403_on_every_admin_tool_endpoint(self):
        """Every Admin Tool view must reject non-moderators with 403."""
        post = _make_post(
            self.regular, title="Gate post", status=ApprovalStatus.PENDING
        )
        comment = CommunityComment.objects.create(
            post=_make_post(
                self.regular, title="Gate host", status=ApprovalStatus.APPROVED
            ),
            author=self.regular,
            body="Gate comment",
            status=ApprovalStatus.REJECTED,
        )
        gallery = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/gate_gal.jpg",
            media_type=MediaType.IMAGE,
            title="Gate gallery",
            status=ApprovalStatus.APPROVED,
        )

        endpoints = (
            ("get", reverse("community:admin_tool")),
            (
                "get",
                reverse("community:admin_post_preview", kwargs={"slug": post.slug}),
            ),
            (
                "get",
                reverse(
                    "community:admin_comment_preview", kwargs={"pk": comment.pk}
                ),
            ),
            (
                "post",
                reverse(
                    "community:admin_tool_gallery_delete", kwargs={"pk": gallery.pk}
                ),
            ),
            (
                "post",
                reverse(
                    "community:admin_tool_post_delete", kwargs={"slug": post.slug}
                ),
            ),
            (
                "post",
                reverse(
                    "community:admin_tool_comment_delete", kwargs={"pk": comment.pk}
                ),
            ),
            ("post", reverse("community:admin_tool_bulk_delete")),
            ("post", reverse("community:admin_tool_bulk_moderate")),
            (
                "post",
                reverse(
                    "community:admin_tool_pin_order", kwargs={"pk": gallery.pk}
                ),
            ),
        )

        self.client.force_login(self.regular)
        for method, url in endpoints:
            with self.subTest(method=method, url=url):
                if method == "get":
                    response = self.client.get(url)
                else:
                    response = self.client.post(url)
                self.assertEqual(response.status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.tool_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_counts_include_all_statuses(self):
        _make_post(self.regular, title="Approved post", status=ApprovalStatus.APPROVED)
        _make_post(self.regular, title="Pending post", status=ApprovalStatus.PENDING)
        rejected = _make_post(
            self.regular, title="Rejected post", status=ApprovalStatus.REJECTED
        )
        host = _make_post(
            self.regular, title="Host for comments", status=ApprovalStatus.APPROVED
        )
        CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Approved comment",
            status=ApprovalStatus.APPROVED,
        )
        CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Pending comment",
            status=ApprovalStatus.PENDING,
        )
        CommunityComment.objects.create(
            post=rejected,
            author=self.regular,
            body="Rejected comment",
            status=ApprovalStatus.REJECTED,
        )
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/gal_approved.jpg",
            media_type=MediaType.IMAGE,
            title="Approved gallery",
            status=ApprovalStatus.APPROVED,
        )
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/gal_pending.jpg",
            media_type=MediaType.IMAGE,
            title="Pending gallery",
            status=ApprovalStatus.PENDING,
        )
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/gal_rejected.jpg",
            media_type=MediaType.IMAGE,
            title="Rejected gallery",
            status=ApprovalStatus.REJECTED,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.tool_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "review")
        self.assertEqual(response.context["gallery_count"], 3)
        self.assertEqual(response.context["gallery_photo_count"], 3)
        self.assertEqual(response.context["gallery_video_count"], 0)
        self.assertEqual(response.context["post_count"], 4)
        self.assertEqual(response.context["comment_count"], 3)

        gallery_page = self.client.get(self.gallery_tab_url)
        self.assertContains(gallery_page, "Photos (3)")
        self.assertContains(gallery_page, "Videos (0)")

        community_page = self.client.get(self.community_tab_url)
        self.assertContains(community_page, "Posts (4)")
        self.assertContains(community_page, "Comments (3)")

    def test_gallery_splits_photos_and_videos(self):
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/split_photo.jpg",
            media_type=MediaType.IMAGE,
            title="Split photo",
            status=ApprovalStatus.APPROVED,
        )
        video = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="video/upload/v1/split_video.mp4",
            media_type=MediaType.VIDEO,
            title="Split video",
            status=ApprovalStatus.APPROVED,
        )
        # CloudinaryField.save() may re-detect resource_type; pin video explicitly
        # the same way other community video tests do.
        GalleryItem.objects.filter(pk=video.pk).update(media_type=MediaType.VIDEO)

        self.client.force_login(self.staff)
        response = self.client.get(self.gallery_tab_url)

        self.assertEqual(response.context["gallery_photo_count"], 1)
        self.assertEqual(response.context["gallery_video_count"], 1)
        self.assertContains(response, "Photos (1)")
        self.assertContains(response, "Videos (1)")
        self.assertContains(response, "admin-tool-preview")
        self.assertContains(response, 'data-preview-type="image"')
        self.assertContains(response, 'data-preview-type="video"')

    def test_approved_post_links_to_public_detail(self):
        post = _make_post(
            self.regular, title="Public post", status=ApprovalStatus.APPROVED
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.community_tab_url)
        public_url = reverse("community:post_detail", kwargs={"slug": post.slug})
        self.assertContains(response, public_url)
        self.assertNotContains(
            response,
            reverse("community:admin_post_preview", kwargs={"slug": post.slug}),
        )

    def test_pending_post_links_to_staff_preview(self):
        post = _make_post(
            self.regular, title="Hidden pending", status=ApprovalStatus.PENDING
        )
        preview_url = reverse(
            "community:admin_post_preview", kwargs={"slug": post.slug}
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.community_tab_url)
        self.assertContains(response, preview_url)

        preview = self.client.get(preview_url)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Hidden pending")
        self.assertContains(preview, "Staff preview")

        # Public detail still 404 for non-author.
        self.client.force_login(self.staff)
        # Staff is not the author — public detail must 404 for pending.
        public = self.client.get(
            reverse("community:post_detail", kwargs={"slug": post.slug})
        )
        self.assertEqual(public.status_code, 404)

    def test_rejected_comment_preview_requires_staff(self):
        host = _make_post(
            self.regular, title="Host", status=ApprovalStatus.APPROVED
        )
        comment = CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Rejected body text",
            status=ApprovalStatus.REJECTED,
        )
        preview_url = reverse(
            "community:admin_comment_preview", kwargs={"pk": comment.pk}
        )

        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(preview_url).status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rejected body text")
        self.assertContains(response, "Staff preview")

    def test_single_gallery_delete(self):
        item = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/to_delete_gal.jpg",
            media_type=MediaType.IMAGE,
            title="Delete me",
            status=ApprovalStatus.APPROVED,
        )
        delete_url = reverse(
            "community:admin_tool_gallery_delete", kwargs={"pk": item.pk}
        )

        self.client.force_login(self.regular)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(GalleryItem.objects.filter(pk=item.pk).exists())

        self.client.force_login(self.staff)
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(delete_url)

        self.assertRedirects(response, self.tool_url + "?tab=gallery")
        self.assertFalse(GalleryItem.objects.filter(pk=item.pk).exists())
        mock_destroy.assert_called_once_with(
            "to_delete_gal", resource_type="image", invalidate=True
        )

    def test_single_post_delete(self):
        post = _make_post(
            self.regular, title="Delete this post", status=ApprovalStatus.APPROVED
        )
        delete_url = reverse(
            "community:admin_tool_post_delete", kwargs={"slug": post.slug}
        )

        self.client.force_login(self.regular)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())

        self.client.force_login(self.staff)
        response = self.client.post(delete_url)
        self.assertRedirects(response, self.tool_url + "?tab=community")
        self.assertFalse(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_section_counts_update_after_delete(self):
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/count_gal.jpg",
            media_type=MediaType.IMAGE,
            title="Count gallery",
            status=ApprovalStatus.APPROVED,
        )
        post = _make_post(
            self.regular, title="Count post", status=ApprovalStatus.APPROVED
        )
        CommunityComment.objects.create(
            post=post,
            author=self.regular,
            body="Count comment",
            status=ApprovalStatus.APPROVED,
        )

        self.client.force_login(self.staff)
        before_gallery = self.client.get(self.gallery_tab_url)
        before_community = self.client.get(self.community_tab_url)
        self.assertEqual(before_gallery.context["gallery_count"], 1)
        self.assertEqual(before_gallery.context["gallery_photo_count"], 1)
        self.assertEqual(before_community.context["post_count"], 1)
        self.assertEqual(before_community.context["comment_count"], 1)
        self.assertContains(before_gallery, "Photos (1)")
        self.assertContains(before_community, "Posts (1)")
        self.assertContains(before_community, "Comments (1)")

        self.client.post(
            reverse("community:admin_tool_post_delete", kwargs={"slug": post.slug})
        )
        # Deleting the post cascades its comments.
        after_gallery = self.client.get(self.gallery_tab_url)
        after_community = self.client.get(self.community_tab_url)
        self.assertEqual(after_gallery.context["gallery_count"], 1)
        self.assertEqual(after_community.context["post_count"], 0)
        self.assertEqual(after_community.context["comment_count"], 0)
        self.assertContains(after_gallery, "Photos (1)")
        self.assertContains(after_community, "Posts (0)")
        self.assertContains(after_community, "Comments (0)")

    def test_admin_tool_query_count_does_not_grow_with_row_count(self):
        """
        Authors are select_related; badge/avatar use User columns only.

        Query count for Admin Tool must stay constant from 5 to 25 rows
        per section (same pattern as the members sidebar check).
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def seed(prefix, count):
            for index in range(count):
                author = _make_user(f"{prefix}_u{index:02d}")
                GalleryItem.objects.create(
                    uploaded_by=author,
                    file=f"image/upload/v1/{prefix}_g{index:02d}.jpg",
                    media_type=MediaType.IMAGE,
                    title=f"{prefix} gal {index}",
                    status=ApprovalStatus.APPROVED,
                )
                post = _make_post(
                    author,
                    title=f"{prefix} post {index}",
                    status=ApprovalStatus.APPROVED,
                )
                CommunityComment.objects.create(
                    post=post,
                    author=author,
                    body=f"{prefix} comment {index}",
                    status=ApprovalStatus.APPROVED,
                )

        def tool_query_count():
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(self.tool_url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "user-author-chip")
            return len(captured)

        self.client.force_login(self.staff)
        seed("q5", 5)
        queries_with_5 = tool_query_count()
        seed("q25", 20)
        queries_with_25 = tool_query_count()

        self.assertEqual(
            queries_with_5,
            queries_with_25,
            msg=(
                f"Admin Tool queries grew with row count: "
                f"{queries_with_5} (5/section) vs {queries_with_25} (25/section)"
            ),
        )
        self.assertLessEqual(queries_with_25, 20)

    def test_bulk_delete_removes_only_selected_ids(self):
        keep_gallery = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/keep_gal.jpg",
            media_type=MediaType.IMAGE,
            title="Keep gallery",
            status=ApprovalStatus.APPROVED,
        )
        delete_gallery = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/bulk_gal.jpg",
            media_type=MediaType.IMAGE,
            title="Bulk gallery",
            status=ApprovalStatus.PENDING,
        )
        keep_post = _make_post(
            self.regular, title="Keep post", status=ApprovalStatus.APPROVED
        )
        delete_post = _make_post(
            self.regular, title="Bulk post", status=ApprovalStatus.REJECTED
        )
        host = _make_post(
            self.regular, title="Comment host", status=ApprovalStatus.APPROVED
        )
        keep_comment = CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Keep comment",
            status=ApprovalStatus.APPROVED,
        )
        delete_comment = CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Bulk comment",
            status=ApprovalStatus.PENDING,
        )

        self.client.force_login(self.staff)
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self.bulk_url,
                    data={
                        "gallery_ids": [str(delete_gallery.pk)],
                        "post_ids": [str(delete_post.pk)],
                        "comment_ids": [str(delete_comment.pk)],
                    },
                )

        self.assertRedirects(response, self.tool_url)
        self.assertTrue(GalleryItem.objects.filter(pk=keep_gallery.pk).exists())
        self.assertFalse(GalleryItem.objects.filter(pk=delete_gallery.pk).exists())
        self.assertTrue(CommunityPost.objects.filter(pk=keep_post.pk).exists())
        self.assertFalse(CommunityPost.objects.filter(pk=delete_post.pk).exists())
        self.assertTrue(CommunityComment.objects.filter(pk=keep_comment.pk).exists())
        self.assertFalse(CommunityComment.objects.filter(pk=delete_comment.pk).exists())
        mock_destroy.assert_called_once_with(
            "bulk_gal", resource_type="image", invalidate=True
        )

    def test_bulk_delete_destroys_cloudinary_for_each_gallery_media(self):
        first = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/bulk_one.jpg",
            media_type=MediaType.IMAGE,
            title="One",
            status=ApprovalStatus.APPROVED,
        )
        second = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/bulk_two.jpg",
            media_type=MediaType.IMAGE,
            title="Two",
            status=ApprovalStatus.REJECTED,
        )

        self.client.force_login(self.staff)
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(
                    self.bulk_url,
                    data={"gallery_ids": [str(first.pk), str(second.pk)]},
                )

        self.assertEqual(mock_destroy.call_count, 2)
        destroyed = {call.args[0] for call in mock_destroy.call_args_list}
        self.assertEqual(destroyed, {"bulk_one", "bulk_two"})

    def test_moderation_queue_still_lists_only_pending(self):
        """No regression: Review tab stays pending-only."""
        _make_post(self.regular, title="Pending only", status=ApprovalStatus.PENDING)
        _make_post(self.regular, title="Approved skip", status=ApprovalStatus.APPROVED)
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/pending_only.jpg",
            media_type=MediaType.IMAGE,
            title="Pending gal",
            status=ApprovalStatus.PENDING,
        )
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/approved_skip.jpg",
            media_type=MediaType.IMAGE,
            title="Approved gal",
            status=ApprovalStatus.APPROVED,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.review_tab_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["pending_posts"]), 1)
        self.assertEqual(len(response.context["pending_gallery_items"]), 1)
        self.assertContains(response, "Pending only")
        self.assertNotContains(response, "Approved skip")

    def test_rejected_post_links_to_staff_preview(self):
        post = _make_post(
            self.regular, title="Rejected hidden", status=ApprovalStatus.REJECTED
        )
        preview_url = reverse(
            "community:admin_post_preview", kwargs={"slug": post.slug}
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.community_tab_url)
        self.assertContains(response, preview_url)

        preview = self.client.get(preview_url)
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Rejected hidden")
        self.assertContains(preview, "Staff preview")

    def test_admin_post_preview_requires_staff(self):
        post = _make_post(
            self.regular, title="Preview gate", status=ApprovalStatus.PENDING
        )
        preview_url = reverse(
            "community:admin_post_preview", kwargs={"slug": post.slug}
        )
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(preview_url).status_code, 403)

    def test_approved_comment_link_includes_comment_anchor(self):
        host = _make_post(
            self.regular, title="Anchor host", status=ApprovalStatus.APPROVED
        )
        comment = CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Anchored comment",
            status=ApprovalStatus.APPROVED,
        )
        detail_url = reverse("community:post_detail", kwargs={"slug": host.slug})
        self.client.force_login(self.staff)
        response = self.client.get(self.community_tab_url)
        self.assertContains(response, f"{detail_url}#comment-{comment.pk}")

    def test_approved_gallery_opens_in_lightbox(self):
        item = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/anchor_gal.jpg",
            media_type=MediaType.IMAGE,
            title="Anchored gallery",
            status=ApprovalStatus.APPROVED,
        )
        gallery_url = reverse("gallery:list")
        self.client.force_login(self.staff)
        response = self.client.get(self.gallery_tab_url)
        self.assertNotContains(response, f"{gallery_url}#gallery-item-{item.pk}")
        self.assertContains(response, "Anchored gallery")
        self.assertContains(response, "admin-tool-preview")
        self.assertContains(response, 'data-preview-type="image"')
    def test_rows_reuse_author_chip_partial_with_badge(self):
        _make_post(self.regular, title="Badge row", status=ApprovalStatus.APPROVED)
        self.client.force_login(self.staff)
        response = self.client.get(self.community_tab_url)
        self.assertContains(response, "user-author-chip")
        self.assertContains(response, "user-avatar")
        self.assertContains(response, self.regular.badge_info.label)
        profile_url = reverse(
            "accounts:profile_detail", args=[self.regular.username]
        )
        self.assertContains(response, profile_url)

    def test_single_comment_delete(self):
        host = _make_post(
            self.regular, title="Comment delete host", status=ApprovalStatus.APPROVED
        )
        comment = CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="Delete me comment",
            status=ApprovalStatus.APPROVED,
        )
        delete_url = reverse(
            "community:admin_tool_comment_delete", kwargs={"pk": comment.pk}
        )

        self.client.force_login(self.regular)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(CommunityComment.objects.filter(pk=comment.pk).exists())

        self.client.force_login(self.staff)
        response = self.client.post(delete_url)
        self.assertRedirects(response, self.tool_url + "?tab=community")
        self.assertFalse(CommunityComment.objects.filter(pk=comment.pk).exists())

    def test_bulk_delete_non_staff_gets_403(self):
        post = _make_post(
            self.regular, title="Bulk 403 post", status=ApprovalStatus.APPROVED
        )
        self.client.force_login(self.regular)
        response = self.client.post(
            self.bulk_url, data={"post_ids": [str(post.pk)]}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(CommunityPost.objects.filter(pk=post.pk).exists())

    def test_bulk_delete_empty_selection_shows_info_message(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.bulk_url, data={}, follow=True)
        self.assertRedirects(response, self.tool_url)
        self.assertContains(response, "No items were selected for deletion.")

    def test_bulk_delete_rolls_back_when_one_delete_fails(self):
        first = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/rollback_one.jpg",
            media_type=MediaType.IMAGE,
            title="Rollback one",
            status=ApprovalStatus.APPROVED,
        )
        second = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/rollback_two.jpg",
            media_type=MediaType.IMAGE,
            title="Rollback two",
            status=ApprovalStatus.APPROVED,
        )
        original_delete = GalleryItem.delete
        call_count = {"n": 0}

        def flaky_delete(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise RuntimeError("simulated bulk delete failure")
            return original_delete(self, *args, **kwargs)

        self.client.force_login(self.staff)
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with patch.object(GalleryItem, "delete", flaky_delete):
                with self.assertRaises(RuntimeError):
                    with self.captureOnCommitCallbacks(execute=True):
                        self.client.post(
                            self.bulk_url,
                            data={"gallery_ids": [str(first.pk), str(second.pk)]},
                        )

            # Rolled-back deletes must not destroy Cloudinary assets.
            mock_destroy.assert_not_called()

        self.assertTrue(GalleryItem.objects.filter(pk=first.pk).exists())
        self.assertTrue(GalleryItem.objects.filter(pk=second.pk).exists())

    def test_bulk_delete_post_destroys_cloudinary_attachments(self):
        post = _make_post(
            self.regular, title="Bulk media post", status=ApprovalStatus.APPROVED
        )
        CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/bulk_post_media.jpg",
            media_type=MediaType.IMAGE,
        )

        self.client.force_login(self.staff)
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.bulk_url, data={"post_ids": [str(post.pk)]})

        self.assertFalse(CommunityPost.objects.filter(pk=post.pk).exists())
        mock_destroy.assert_called_once_with(
            "bulk_post_media", resource_type="image", invalidate=True
        )

    def test_bulk_delete_comment_destroys_cloudinary_attachments(self):
        host = _make_post(
            self.regular, title="Bulk media host", status=ApprovalStatus.APPROVED
        )
        comment = CommunityComment.objects.create(
            post=host,
            author=self.regular,
            body="With attachment",
            status=ApprovalStatus.APPROVED,
        )
        CommunityCommentMedia.objects.create(
            comment=comment,
            file="image/upload/v1/bulk_comment_media.jpg",
            media_type=MediaType.IMAGE,
        )

        self.client.force_login(self.staff)
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(
                    self.bulk_url, data={"comment_ids": [str(comment.pk)]}
                )

        self.assertFalse(CommunityComment.objects.filter(pk=comment.pk).exists())
        mock_destroy.assert_called_once_with(
            "bulk_comment_media", resource_type="image", invalidate=True
        )

    def test_pin_order_can_be_set_and_cleared(self):
        item = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/pin_me.jpg",
            media_type=MediaType.IMAGE,
            title="Pin me",
            status=ApprovalStatus.APPROVED,
        )
        pin_url = reverse("community:admin_tool_pin_order", kwargs={"pk": item.pk})

        self.client.force_login(self.staff)
        response = self.client.post(
            pin_url,
            data={"pin_order": "2", "next_tab": "gallery"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["pin_order"], 2)
        item.refresh_from_db()
        self.assertEqual(item.pin_order, 2)

        response = self.client.post(
            pin_url,
            data={"pin_order": "", "next_tab": "gallery"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIsNone(response.json()["pin_order"])
        item.refresh_from_db()
        self.assertIsNone(item.pin_order)

        response = self.client.post(
            pin_url,
            data={"pin_order": "0", "next_tab": "gallery"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIsNone(response.json()["pin_order"])
        item.refresh_from_db()
        self.assertIsNone(item.pin_order)

        response = self.client.post(
            pin_url,
            data={"pin_order": "12a", "next_tab": "gallery"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        item.refresh_from_db()
        self.assertIsNone(item.pin_order)

    def test_pin_order_must_be_unique_within_photos(self):
        first = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/pin_unique_a.jpg",
            media_type=MediaType.IMAGE,
            title="Pin A",
            status=ApprovalStatus.APPROVED,
            pin_order=1,
        )
        second = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/pin_unique_b.jpg",
            media_type=MediaType.IMAGE,
            title="Pin B",
            status=ApprovalStatus.APPROVED,
        )
        # A video may reuse the same pin number in its own section.
        video = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="video/upload/v1/pin_unique_v.mp4",
            media_type=MediaType.IMAGE,
            title="Pin V",
            status=ApprovalStatus.APPROVED,
        )
        GalleryItem.objects.filter(pk=video.pk).update(
            media_type=MediaType.VIDEO, pin_order=1
        )
        video.refresh_from_db()

        pin_url = reverse(
            "community:admin_tool_pin_order", kwargs={"pk": second.pk}
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            pin_url,
            data={"pin_order": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("already used", response.json()["message"].lower())
        second.refresh_from_db()
        self.assertIsNone(second.pin_order)
        first.refresh_from_db()
        self.assertEqual(first.pin_order, 1)
        self.assertEqual(video.pin_order, 1)

    def test_gallery_tab_renders_auto_save_pin_inputs(self):
        item = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/csrf_pin.jpg",
            media_type=MediaType.IMAGE,
            title="CSRF pin",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.gallery_tab_url)
        pin_url = reverse("community:admin_tool_pin_order", kwargs={"pk": item.pk})
        self.assertContains(response, 'data-pin-url="' + pin_url + '"')
        self.assertContains(response, "admin-tool-pin-form__input")
        self.assertNotContains(response, "Save pins")

    def test_bulk_approve_pending_items(self):
        post = _make_post(
            self.regular, title="Bulk approve post", status=ApprovalStatus.PENDING
        )
        item = GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/bulk_approve.jpg",
            media_type=MediaType.IMAGE,
            title="Bulk approve gal",
            status=ApprovalStatus.PENDING,
        )

        self.client.force_login(self.staff)
        response = self.client.post(
            self.bulk_moderate_url,
            data={
                "action": "approve",
                "post_ids": [str(post.pk)],
                "gallery_ids": [str(item.pk)],
            },
        )
        self.assertRedirects(response, self.review_tab_url)
        post.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(post.status, ApprovalStatus.APPROVED)
        self.assertEqual(item.status, ApprovalStatus.APPROVED)

    def test_status_filter_limits_gallery_tab(self):
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/filter_approved.jpg",
            media_type=MediaType.IMAGE,
            title="Filter approved",
            status=ApprovalStatus.APPROVED,
        )
        GalleryItem.objects.create(
            uploaded_by=self.regular,
            file="image/upload/v1/filter_pending.jpg",
            media_type=MediaType.IMAGE,
            title="Filter pending",
            status=ApprovalStatus.PENDING,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.tool_url + "?tab=gallery&status=approved")
        self.assertEqual(response.context["gallery_count"], 1)
        self.assertContains(response, "Filter approved")
        self.assertNotContains(response, "Filter pending")


class ModerationAlertEmailTests(TestCase):
    """Superuser email when content enters the pending queue."""

    def setUp(self):
        self.superuser = _make_user(
            "alert_super", is_staff=True, is_superuser=True
        )
        self.superuser.email = "super@example.com"
        self.superuser.save(update_fields=["email"])
        self.staff = _make_user("alert_staff", is_staff=True)
        self.staff.email = "staff@example.com"
        self.staff.save(update_fields=["email"])
        self.member = _make_user("alert_member")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_pending_post_emails_superuser_only(self):
        from django.core import mail

        self.client.force_login(self.member)
        response = self.client.post(
            reverse("community:post_create"),
            data={"title": "Needs review", "body": "Please approve me."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["super@example.com"])
        self.assertIn("Content awaiting review", mail.outbox[0].subject)
        self.assertIn("tab=review", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_staff_auto_approved_post_does_not_email(self):
        from django.core import mail

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("community:post_create"),
            data={"title": "Staff post", "body": "Published immediately."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)


class CommunityMembersSidebarTests(TestCase):
    def setUp(self):
        self.author = _make_user("sidebar_author")

    def test_anonymous_list_hides_members_sidebar(self):
        response = self.client.get(reverse("community:list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("community_members", response.context)
        self.assertNotContains(response, "members-sidebar")
        self.assertContains(response, "community-layout--solo")
        self.assertContains(response, "Log in")
        self.assertContains(response, "Register")
        self.assertContains(response, "community-visitor-btn--primary")
        self.assertContains(response, "community-visitor-btn--secondary")

    def test_list_includes_members_sorted_case_insensitive(self):
        zeta = _make_user("zeta_member")
        User.objects.filter(pk=zeta.pk).update(display_name="zeta")
        beta = _make_user("alpha_member")
        User.objects.filter(pk=beta.pk).update(display_name="Beta")
        alpha = _make_user("gamma_member")
        User.objects.filter(pk=alpha.pk).update(display_name="alpha")

        self.client.force_login(self.author)
        response = self.client.get(reverse("community:list"))

        self.assertEqual(response.status_code, 200)
        members = list(response.context["community_members"])
        names = [member.public_display_name for member in members]
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.assertEqual(names[0].casefold(), "alpha")
        self.assertContains(response, "members-sidebar")
        self.assertContains(response, "Members")

    def test_sidebar_present_on_list_only_not_create_or_detail(self):
        post = _make_post(
            self.author, title="Sidebar Post", status=ApprovalStatus.APPROVED
        )
        self.client.force_login(self.author)

        list_response = self.client.get(reverse("community:list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "members-sidebar")
        self.assertNotContains(list_response, "community-layout--solo")

        detail = self.client.get(reverse("community:post_detail", args=[post.slug]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "members-sidebar")
        self.assertContains(detail, "community-detail")

        create = self.client.get(reverse("community:post_create"))
        self.assertEqual(create.status_code, 200)
        self.assertNotIn("community_members", create.context)
        self.assertNotContains(create, "members-sidebar")
        self.assertContains(create, "community-layout--solo")

    def test_author_name_links_to_profile_on_list_and_detail(self):
        post = _make_post(
            self.author, title="Linkable Author", status=ApprovalStatus.APPROVED
        )
        profile_url = reverse(
            "accounts:profile_detail", args=[self.author.username]
        )
        self.client.force_login(self.author)

        list_response = self.client.get(reverse("community:list"))
        self.assertContains(list_response, profile_url)
        self.assertContains(list_response, f"@{self.author.public_display_name}")
        self.assertContains(list_response, self.author.badge_info.label)

        detail_response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )
        self.assertContains(detail_response, profile_url)

    def test_comment_author_links_to_profile(self):
        post = _make_post(
            self.author, title="Comment Link Post", status=ApprovalStatus.APPROVED
        )
        commenter = _make_user("comment_linker")
        CommunityComment.objects.create(
            post=post,
            author=commenter,
            body="Hello from the sidebar era.",
            status=ApprovalStatus.APPROVED,
        )
        self.client.force_login(self.author)

        response = self.client.get(
            reverse("community:post_detail", args=[post.slug])
        )
        profile_url = reverse(
            "accounts:profile_detail", args=[commenter.username]
        )
        self.assertContains(response, profile_url)
        self.assertContains(response, f"@{commenter.public_display_name}")

    def test_deleted_author_shows_no_badge(self):
        post = _make_post(
            self.author, title="Orphan Post", status=ApprovalStatus.APPROVED
        )
        # Simulate a retained orphan credit without cascade-deleting the post
        # (account erasure uses CASCADE; this path covers author=None display).
        CommunityPost.objects.filter(pk=post.pk).update(author=None)
        viewer = _make_user("orphan_viewer")
        self.client.force_login(viewer)

        response = self.client.get(reverse("community:list"))
        self.assertContains(response, "Deleted account")
        self.assertContains(response, "user-credit__deleted")
        # Live members in the sidebar still have badges; orphan credits must not.
        deleted_credit = response.content.decode().split("user-credit__deleted", 1)[1][
            :400
        ]
        self.assertNotIn('class="user-badge', deleted_credit)

    def test_sidebar_query_count_does_not_grow_with_member_count(self):
        """
        badge_info / avatars use only User columns — no per-member queries.

        Query count for community:list (empty feed) must stay constant when
        scaling from 10 to 50 members.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        viewer = _make_user("sidebar_perf_viewer")
        self.client.force_login(viewer)

        def member_list_query_count():
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(reverse("community:list"))
                self.assertEqual(response.status_code, 200)
                # Force template access to members + badges in the response body.
                self.assertContains(response, "members-sidebar")
                self.assertContains(response, "user-badge")
            return len(captured)

        for index in range(10):
            _make_user(f"perf10_{index:02d}")

        queries_with_10 = member_list_query_count()

        for index in range(40):
            _make_user(f"perf50_{index:02d}")

        queries_with_50 = member_list_query_count()

        self.assertEqual(
            queries_with_10,
            queries_with_50,
            msg=(
                f"Sidebar queries grew with member count: "
                f"{queries_with_10} (10 members) vs {queries_with_50} (50 members)"
            ),
        )
        # Sanity ceiling: empty list page should stay cheap (sessions + members).
        self.assertLessEqual(
            queries_with_50,
            12,
            msg=f"Unexpectedly high query count for empty list: {queries_with_50}",
        )
        # Documented baseline for reviewers (constant across 10 and 50 members).
        self.assertGreaterEqual(queries_with_50, 1)

    def test_mobile_accordion_markup_is_present_for_alpine(self):
        """
        Assert the Alpine accordion contract: closed by default, toggle wiring
        present, and community.js loaded (no browser automation in this project).
        """
        self.client.force_login(self.author)
        response = self.client.get(reverse("community:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'x-data="membersSidebar()"')
        self.assertContains(response, "members-sidebar__toggle")
        self.assertContains(response, 'aria-controls="community-members-panel"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, ':aria-expanded="open.toString()"')
        self.assertContains(
            response, ":class=\"{ 'members-sidebar__panel--open': open }\""
        )
        self.assertContains(response, "community/js/community")

    def test_create_form_has_no_members_sidebar(self):
        """Start a Discussion is a solo form page — Members only on the list."""
        self.client.force_login(self.author)
        response = self.client.get(reverse("community:post_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "community-layout--solo")
        self.assertContains(response, "community-layout__main")
        self.assertNotContains(response, "members-sidebar")
        self.assertContains(response, "max-w-2xl")
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="cover_image"')
        self.assertContains(response, 'name="files"')
