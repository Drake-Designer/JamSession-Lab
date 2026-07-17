"""
Tests for the gallery app.

Covers (see PROJECT_PLAN.md, Phase 1):
- Public gallery listing shows only status=approved items (photos and videos).
- Batch upload: file size/type validation, mixed valid/invalid files in one submission.
- Auto-approval for staff/superusers vs "pending" for regular users
  (apply_initial_moderation).
- Admin actions approve_gallery_items / reject_gallery_items.
- Cloudinary cleanup signals (pre_save file replacement, post_delete removal).
- media_type sync after save (_sync_media_type).

Real network calls to Cloudinary are never made in these tests: file uploads are
short-circuited by patching cloudinary.uploader.upload_resource, and file deletions
by patching jamsession.cloudinary_cleanup.destroy (the shared Cloudinary cleanup
helper used by gallery/signals.py — see Phase 3 of PROJECT_PLAN.md).
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cloudinary
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from PIL import Image

from .admin import approve_gallery_items, reject_gallery_items
from .forms import GalleryBatchUploadForm
from .models import ApprovalStatus, GalleryItem, MediaType
from .validators import (
    detect_gallery_media_kind,
    gallery_file_rejection_reason,
    validate_gallery_file_size,
    validate_gallery_file_type,
)

User = get_user_model()


def _make_user(username, *, is_staff=False, is_superuser=False):
    """Create a minimal but valid user for gallery tests."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="jam-session-test-pass1",
        display_name=username,
        is_staff=is_staff,
        is_superuser=is_superuser,
    )


def _make_image_file(name="photo.jpg", size=(20, 20), colour=(230, 57, 70)):
    """Build a small, genuinely valid in-memory JPEG for upload tests."""
    buffer = BytesIO()
    Image.new("RGB", size, color=colour).save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def _make_large_image_file(name="large_photo.jpg", min_bytes=3_000_000):
    """
    Build a valid JPEG larger than Django's historical 2.5 MB request-body
    default, so upload tests prove RequestDataTooBig no longer fires early.
    """
    import os

    width = 1800
    while True:
        buffer = BytesIO()
        raw = os.urandom(width * width * 3)
        Image.frombytes("RGB", (width, width), raw).save(
            buffer, format="JPEG", quality=92
        )
        if buffer.tell() >= min_bytes:
            buffer.seek(0)
            return SimpleUploadedFile(
                name, buffer.read(), content_type="image/jpeg"
            )
        width += 400


def _make_invalid_file(name="notes.txt"):
    """Build a file that is neither a real image nor a recognised video container."""
    return SimpleUploadedFile(
        name,
        b"This is plain text, not a real photo or video.",
        content_type="text/plain",
    )


def _fake_upload_resource(file, **options):
    """
    Stand-in for cloudinary.uploader.upload_resource.

    Used to patch out real Cloudinary uploads in tests: inspects the file with the
    same detection helper used by the real validators, and returns a CloudinaryResource
    with a matching resource_type, so downstream logic (is_video, _sync_media_type)
    behaves the same way it would with a real upload.
    """
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


class GalleryFileValidationTests(TestCase):
    """Unit tests for the standalone size/type validators used by every upload path."""

    def test_accepts_file_within_size_limit(self):
        under_limit = SimpleNamespace(size=1_000)
        validate_gallery_file_size(under_limit)  # should not raise

    def test_accepts_file_exactly_at_size_limit(self):
        at_limit = SimpleNamespace(size=104_857_600)
        validate_gallery_file_size(at_limit)  # should not raise

    def test_rejects_file_over_size_limit(self):
        over_limit = SimpleNamespace(size=104_857_600 + 1)
        with self.assertRaises(ValidationError):
            validate_gallery_file_size(over_limit)

    def test_accepts_a_real_image_file(self):
        validate_gallery_file_type(_make_image_file())  # should not raise

    def test_rejects_a_non_media_file(self):
        with self.assertRaises(ValidationError):
            validate_gallery_file_type(_make_invalid_file())

    def test_rejection_reason_is_none_for_a_valid_file(self):
        self.assertIsNone(gallery_file_rejection_reason(_make_image_file()))

    def test_rejection_reason_reports_oversized_file(self):
        oversized = SimpleNamespace(size=104_857_600 + 1, read=lambda *a: b"")
        reason = gallery_file_rejection_reason(oversized)
        self.assertEqual(reason, "file exceeds 100MB limit")

    def test_rejection_reason_reports_invalid_type(self):
        reason = gallery_file_rejection_reason(_make_invalid_file())
        self.assertEqual(reason, "only photos and videos are allowed")


class ApplyInitialModerationTests(TestCase):
    """Unit tests for GalleryItem.apply_initial_moderation()."""

    def test_regular_user_upload_is_pending(self):
        user = _make_user("regular_uploader")
        item = GalleryItem(uploaded_by=user, file="image/upload/v1/a.jpg")

        item.apply_initial_moderation(user)

        self.assertEqual(item.status, ApprovalStatus.PENDING)
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)

    def test_staff_user_upload_is_auto_approved(self):
        staff = _make_user("staff_uploader", is_staff=True)
        item = GalleryItem(uploaded_by=staff, file="image/upload/v1/b.jpg")

        item.apply_initial_moderation(staff)

        self.assertEqual(item.status, ApprovalStatus.APPROVED)
        self.assertEqual(item.approved_by, staff)
        self.assertIsNotNone(item.approved_at)
        self.assertEqual(item.rejection_reason, "")

    def test_superuser_upload_is_auto_approved(self):
        superuser = _make_user("super_uploader", is_superuser=True)
        item = GalleryItem(uploaded_by=superuser, file="image/upload/v1/c.jpg")

        item.apply_initial_moderation(superuser)

        self.assertEqual(item.status, ApprovalStatus.APPROVED)
        self.assertEqual(item.approved_by, superuser)

    def test_re_evaluating_a_rejected_item_for_a_regular_user_clears_approval_fields(self):
        user = _make_user("previously_rejected")
        reviewer = _make_user("a_reviewer", is_staff=True)
        item = GalleryItem(
            uploaded_by=user,
            file="image/upload/v1/d.jpg",
            status=ApprovalStatus.REJECTED,
            approved_by=reviewer,
            rejection_reason="Not appropriate for this gallery.",
        )

        item.apply_initial_moderation(user)

        self.assertEqual(item.status, ApprovalStatus.PENDING)
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)


class GalleryListViewTests(TestCase):
    """The public gallery page must only ever surface approved media."""

    def test_only_approved_photos_and_videos_are_listed(self):
        approved_photo = GalleryItem.objects.create(
            file="image/upload/v1/approved_photo.jpg",
            media_type=MediaType.IMAGE,
            title="Approved Photo",
            status=ApprovalStatus.APPROVED,
        )
        approved_video = GalleryItem.objects.create(
            file="video/upload/v1/approved_video.mp4",
            media_type=MediaType.VIDEO,
            title="Approved Video",
            status=ApprovalStatus.APPROVED,
        )
        # GalleryItem.save() calls _sync_media_type(), which trusts
        # self.file.resource_type — a plain string (as opposed to a real
        # CloudinaryResource) has no such attribute, so on first save it
        # silently resets media_type back to "image". Force it back to
        # "video" at the database level (bypassing save()) so this test
        # reflects a genuinely approved video item.
        GalleryItem.objects.filter(pk=approved_video.pk).update(
            media_type=MediaType.VIDEO
        )
        approved_video.refresh_from_db()
        GalleryItem.objects.create(
            file="image/upload/v1/pending_photo.jpg",
            media_type=MediaType.IMAGE,
            title="Pending Photo",
            status=ApprovalStatus.PENDING,
        )
        GalleryItem.objects.create(
            file="image/upload/v1/rejected_photo.jpg",
            media_type=MediaType.IMAGE,
            title="Rejected Photo",
            status=ApprovalStatus.REJECTED,
        )

        response = self.client.get(reverse("gallery:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved Photo")
        self.assertContains(response, "Approved Video")
        self.assertNotContains(response, "Pending Photo")
        self.assertNotContains(response, "Rejected Photo")
        self.assertEqual(list(response.context["photo_items"]), [approved_photo])
        self.assertEqual(list(response.context["video_items"]), [approved_video])

    def test_empty_gallery_shows_placeholder_message(self):
        response = self.client.get(reverse("gallery:list"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_gallery_content"])
        self.assertContains(response, "No approved gallery items yet.")


class GalleryBatchUploadFormTests(TestCase):
    """Form-level tests for validation and mixed-batch handling."""

    def setUp(self):
        self.user = _make_user("batch_uploader")
        self.staff = _make_user("batch_staff", is_staff=True)

    def test_at_least_one_file_is_required(self):
        form = GalleryBatchUploadForm(
            data={"title": "", "caption": ""},
            files=MultiValueDict(),
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("files", form.errors)

    def test_mixed_batch_saves_valid_file_and_reports_invalid_file(self):
        valid_image = _make_image_file("good.jpg")
        invalid_file = _make_invalid_file("bad.txt")
        form = GalleryBatchUploadForm(
            data={"title": "", "caption": ""},
            files=MultiValueDict({"files": [valid_image, invalid_file]}),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            success_count, failures = form.process_uploads()

        self.assertEqual(success_count, 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0], ("bad.txt", "only photos and videos are allowed"))
        self.assertEqual(GalleryItem.objects.count(), 1)

    def test_all_invalid_batch_saves_nothing(self):
        form = GalleryBatchUploadForm(
            data={"title": "", "caption": ""},
            files=MultiValueDict({"files": [_make_invalid_file("bad.txt")]}),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            success_count, failures = form.process_uploads()

        self.assertEqual(success_count, 0)
        self.assertEqual(len(failures), 1)
        self.assertEqual(GalleryItem.objects.count(), 0)

    def test_regular_user_batch_upload_is_pending(self):
        form = GalleryBatchUploadForm(
            data={"title": "My Photo", "caption": ""},
            files=MultiValueDict({"files": [_make_image_file()]}),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            success_count, _failures = form.process_uploads()

        self.assertEqual(success_count, 1)
        item = GalleryItem.objects.get()
        self.assertEqual(item.status, ApprovalStatus.PENDING)
        self.assertEqual(item.uploaded_by, self.user)
        self.assertEqual(item.media_type, MediaType.IMAGE)

    def test_staff_batch_upload_is_auto_approved(self):
        form = GalleryBatchUploadForm(
            data={"title": "", "caption": ""},
            files=MultiValueDict({"files": [_make_image_file()]}),
            user=self.staff,
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            success_count, _failures = form.process_uploads()

        self.assertEqual(success_count, 1)
        item = GalleryItem.objects.get()
        self.assertEqual(item.status, ApprovalStatus.APPROVED)
        self.assertEqual(item.approved_by, self.staff)


class GalleryUploadViewTests(TestCase):
    """End-to-end coverage of the gallery_upload view through the test client."""

    def setUp(self):
        self.user = _make_user("view_uploader")
        self.staff = _make_user("view_staff", is_staff=True)

    def test_upload_requires_login(self):
        response = self.client.get(reverse("gallery:upload"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_regular_user_upload_is_pending_and_redirects_to_gallery(self):
        self.client.force_login(self.user)

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            response = self.client.post(
                reverse("gallery:upload"),
                data={"files": [_make_image_file()], "title": "", "caption": ""},
            )

        self.assertRedirects(response, reverse("gallery:list"))
        item = GalleryItem.objects.get()
        self.assertEqual(item.status, ApprovalStatus.PENDING)
        self.assertEqual(item.uploaded_by, self.user)

    def test_staff_upload_is_auto_published(self):
        self.client.force_login(self.staff)

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            response = self.client.post(
                reverse("gallery:upload"),
                data={"files": [_make_image_file()], "title": "", "caption": ""},
            )

        self.assertRedirects(response, reverse("gallery:list"))
        item = GalleryItem.objects.get()
        self.assertEqual(item.status, ApprovalStatus.APPROVED)

    def test_upload_with_no_valid_files_shows_error_and_does_not_redirect(self):
        self.client.force_login(self.user)

        with patch("cloudinary.uploader.upload_resource", side_effect=_fake_upload_resource):
            response = self.client.post(
                reverse("gallery:upload"),
                data={"files": [_make_invalid_file()], "title": "", "caption": ""},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(GalleryItem.objects.count(), 0)

    def test_upload_between_former_django_limit_and_100mb_is_not_bad_request(self):
        """
        Files between 2.5 MB and 100 MB must reach the form layer.

        Before DATA_UPLOAD_MAX_MEMORY_SIZE was raised, Django raised
        RequestDataTooBig (400 Bad Request) before any gallery validation.
        """
        from django.conf import settings
        from django.core.exceptions import RequestDataTooBig

        self.assertGreaterEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 3_000_000)
        self.assertGreaterEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 3_000_000)

        large_file = _make_large_image_file(min_bytes=3_000_000)
        self.assertGreater(large_file.size, 2_621_440)
        self.assertLessEqual(large_file.size, settings.DATA_UPLOAD_MAX_MEMORY_SIZE)

        self.client.force_login(self.user)

        try:
            with patch(
                "cloudinary.uploader.upload_resource",
                side_effect=_fake_upload_resource,
            ):
                response = self.client.post(
                    reverse("gallery:upload"),
                    data={
                        "files": [large_file],
                        "title": "Large shot",
                        "caption": "",
                    },
                )
        except RequestDataTooBig:
            self.fail(
                "Upload between 2.5 MB and 100 MB must not raise RequestDataTooBig"
            )

        # Accepted by the form — not a raw Django 400.
        self.assertNotEqual(response.status_code, 400)
        self.assertRedirects(response, reverse("gallery:list"))
        self.assertEqual(GalleryItem.objects.count(), 1)


class GalleryAdminActionsTests(TestCase):
    """Tests for the approve_gallery_items / reject_gallery_items admin actions."""

    def setUp(self):
        self.moderator = _make_user("moderator", is_staff=True)
        # These actions re-save already-persisted items, which triggers the
        # pre_save Cloudinary cleanup signal; that signal is exercised on its
        # own in CloudinaryCleanupSignalTests, so it is patched out here.
        self.destroy_patcher = patch("jamsession.cloudinary_cleanup.destroy")
        self.destroy_patcher.start()
        self.addCleanup(self.destroy_patcher.stop)

    def test_approve_action_approves_only_pending_items(self):
        pending = GalleryItem.objects.create(
            file="image/upload/v1/pending.jpg",
            media_type=MediaType.IMAGE,
            status=ApprovalStatus.PENDING,
        )
        already_approved = GalleryItem.objects.create(
            file="image/upload/v1/already_approved.jpg",
            media_type=MediaType.IMAGE,
            status=ApprovalStatus.APPROVED,
        )
        request = SimpleNamespace(user=self.moderator)
        modeladmin = Mock()

        approve_gallery_items(modeladmin, request, GalleryItem.objects.all())

        pending.refresh_from_db()
        already_approved.refresh_from_db()
        self.assertEqual(pending.status, ApprovalStatus.APPROVED)
        self.assertEqual(pending.approved_by, self.moderator)
        self.assertIsNotNone(pending.approved_at)
        # Untouched: the action only processes items that were pending.
        self.assertIsNone(already_approved.approved_by)
        modeladmin.message_user.assert_called_once()

    def test_reject_action_rejects_only_pending_items(self):
        pending = GalleryItem.objects.create(
            file="image/upload/v1/to_reject.jpg",
            media_type=MediaType.IMAGE,
            status=ApprovalStatus.PENDING,
        )
        already_rejected = GalleryItem.objects.create(
            file="image/upload/v1/already_rejected.jpg",
            media_type=MediaType.IMAGE,
            status=ApprovalStatus.REJECTED,
        )
        request = SimpleNamespace(user=self.moderator)
        modeladmin = Mock()

        reject_gallery_items(modeladmin, request, GalleryItem.objects.all())

        pending.refresh_from_db()
        already_rejected.refresh_from_db()
        self.assertEqual(pending.status, ApprovalStatus.REJECTED)
        self.assertEqual(pending.approved_by, self.moderator)
        # Untouched: the action only processes items that were pending.
        self.assertIsNone(already_rejected.approved_by)
        modeladmin.message_user.assert_called_once()


class CloudinaryCleanupSignalTests(TestCase):
    """Tests for the pre_save/post_delete Cloudinary cleanup signals."""

    def test_replacing_the_file_deletes_the_old_cloudinary_resource(self):
        item = GalleryItem.objects.create(
            file="image/upload/v1/old_id.jpg",
            media_type=MediaType.IMAGE,
        )
        item.refresh_from_db()

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            item.file = "image/upload/v1/new_id.jpg"
            item.save()

        mock_destroy.assert_called_once_with(
            "old_id", resource_type="image", invalidate=True
        )

    def test_deleting_an_item_removes_its_cloudinary_resource(self):
        item = GalleryItem.objects.create(
            file="video/upload/v1/clip_id.mp4",
            media_type=MediaType.VIDEO,
        )
        item.refresh_from_db()

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            item.delete()

        mock_destroy.assert_called_once_with(
            "clip_id", resource_type="video", invalidate=True
        )

    def test_creating_a_new_item_does_not_trigger_cleanup(self):
        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            GalleryItem.objects.create(
                file="image/upload/v1/brand_new.jpg",
                media_type=MediaType.IMAGE,
            )

        mock_destroy.assert_not_called()

    def test_saving_without_changing_the_file_does_not_delete_it(self):
        """
        Guards against deleting the resource that is still in use.

        HISTORY: CloudinaryResource defines no __eq__, so comparing old and
        new file values with plain `!=` falls back to Python's default
        object-identity comparison — always "different", even when nothing
        about the file actually changed, since delete_old_gallery_file()
        always re-fetches old_instance with a fresh query. This was a real
        bug, found by this exact test during Phase 1 of PROJECT_PLAN.md, and
        fixed by comparing CloudinaryResource.get_prep_value() instead. Phase
        3 moved that fix into the shared jamsession.cloudinary_cleanup helper
        (used by gallery/signals.py, accounts/signals.py and
        pages/signals.py) — this test's assertion is unchanged and must keep
        passing to prove the fix survived that extraction.
        """
        item = GalleryItem.objects.create(
            file="image/upload/v1/unchanged_id.jpg",
            media_type=MediaType.IMAGE,
            title="Original title",
        )
        item.refresh_from_db()

        with patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy:
            item.title = "Updated title"
            item.save()

        mock_destroy.assert_not_called()


class MediaTypeSyncTests(TestCase):
    """Tests for GalleryItem._sync_media_type()."""

    def setUp(self):
        # Re-saving an already-persisted item triggers the pre_save Cloudinary
        # cleanup signal (covered separately); patch it out here so these
        # tests only exercise media_type syncing.
        self.destroy_patcher = patch("jamsession.cloudinary_cleanup.destroy")
        self.destroy_patcher.start()
        self.addCleanup(self.destroy_patcher.stop)

    def test_media_type_is_corrected_to_match_the_actual_resource_type(self):
        item = GalleryItem.objects.create(
            file="video/upload/v1/clip_id.mp4",
            media_type=MediaType.IMAGE,  # deliberately wrong, to prove the sync fixes it
        )
        item.refresh_from_db()
        self.assertEqual(item.media_type, MediaType.IMAGE)  # not yet reconciled

        item.save()

        self.assertEqual(item.media_type, MediaType.VIDEO)
        item.refresh_from_db()
        self.assertEqual(item.media_type, MediaType.VIDEO)

    def test_media_type_is_left_unchanged_when_already_correct(self):
        item = GalleryItem.objects.create(
            file="image/upload/v1/photo_id.jpg",
            media_type=MediaType.IMAGE,
        )
        item.refresh_from_db()

        item.save()

        self.assertEqual(item.media_type, MediaType.IMAGE)
        item.refresh_from_db()
        self.assertEqual(item.media_type, MediaType.IMAGE)


class GalleryUploaderCreditLinkTests(TestCase):
    def test_uploader_name_links_to_profile_with_badge(self):
        uploader = _make_user("gallery_uploader")
        GalleryItem.objects.create(
            uploaded_by=uploader,
            file="image/upload/v1/credit_photo.jpg",
            media_type=MediaType.IMAGE,
            title="Credit Photo",
            status=ApprovalStatus.APPROVED,
        )

        response = self.client.get(reverse("gallery:list"))
        profile_url = reverse(
            "accounts:profile_detail", args=[uploader.username]
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, profile_url)
        self.assertContains(response, f"@{uploader.public_display_name}")
        self.assertContains(response, uploader.badge_info.label)
        self.assertContains(response, "gallery-item__credit-row")

    def test_deleted_uploader_shows_deleted_account_without_badge(self):
        uploader = _make_user("gone_uploader")
        GalleryItem.objects.create(
            uploaded_by=uploader,
            file="image/upload/v1/orphan_photo.jpg",
            media_type=MediaType.IMAGE,
            title="Orphan Photo",
            status=ApprovalStatus.APPROVED,
        )
        uploader.delete()

        response = self.client.get(reverse("gallery:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted account")
        self.assertContains(response, "Orphan Photo")
        self.assertNotContains(response, 'class="user-badge')
