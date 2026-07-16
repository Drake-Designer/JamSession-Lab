from datetime import date
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from community.models import (
    CommunityComment,
    CommunityCommentMedia,
    CommunityPost,
    CommunityPostMedia,
)
from gallery.models import GalleryItem, MediaType
from jamsession.moderation import ApprovalStatus

from .forms import RegistrationForm
from .models import User
from .validators import UNDERAGE_ERROR_MESSAGE


def valid_registration_data(**overrides):
    """Complete, valid POST data for the registration form."""
    data = {
        "first_name": "Aoife",
        "last_name": "Byrne",
        "display_name": "Aoife B",
        "email": "aoife@example.com",
        "phone_number": "+353 87 123 4567",
        "password1": "brave-purple-drums!",
        "password2": "brave-purple-drums!",
        "date_of_birth": "1990-05-10",
        "county": "dublin",
        "town_city": "Swords",
        "instruments": ["electric_guitar", "vocals"],
        "accept_terms": "on",
    }
    data.update(overrides)
    return data


class RegistrationFormTests(TestCase):
    def test_valid_data_creates_user(self):
        form = RegistrationForm(data=valid_registration_data())
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        user = form.save()
        self.assertEqual(user.display_name, "Aoife B")
        self.assertEqual(user.username, "aoife_b")
        self.assertEqual(user.email, "aoife@example.com")
        self.assertEqual(user.instruments, ["electric_guitar", "vocals"])
        self.assertIsNotNone(user.terms_accepted_at)
        self.assertFalse(user.is_email_verified)

    def test_under_18_is_rejected(self):
        today = timezone.localdate()
        seventeen_years_ago = date(today.year - 17, today.month, 1)
        form = RegistrationForm(
            data=valid_registration_data(
                date_of_birth=seventeen_years_ago.isoformat(),
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            str(UNDERAGE_ERROR_MESSAGE),
            [str(error) for error in form.errors["date_of_birth"]],
        )

    def test_town_must_belong_to_selected_county(self):
        form = RegistrationForm(
            data=valid_registration_data(county="galway", town_city="Swords")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("town_city", form.errors)

    def test_other_instrument_required_when_other_selected(self):
        form = RegistrationForm(
            data=valid_registration_data(
                instruments=["other"],
                other_instrument="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("other_instrument", form.errors)

    def test_other_instrument_cleared_when_other_not_selected(self):
        form = RegistrationForm(
            data=valid_registration_data(other_instrument="Theremin")
        )

        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        self.assertEqual(form.cleaned_data["other_instrument"], "")

    def test_at_least_one_instrument_is_required(self):
        form = RegistrationForm(data=valid_registration_data(instruments=[]))

        self.assertFalse(form.is_valid())
        self.assertIn("instruments", form.errors)

    def test_display_name_is_unique_case_insensitive(self):
        form = RegistrationForm(data=valid_registration_data())
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        form.save()

        duplicate = RegistrationForm(
            data=valid_registration_data(
                display_name="AOIFE B",
                email="someone.else@example.com",
            )
        )
        self.assertFalse(duplicate.is_valid())
        self.assertIn("display_name", duplicate.errors)

    def test_email_is_unique_case_insensitive(self):
        form = RegistrationForm(data=valid_registration_data())
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        form.save()

        duplicate = RegistrationForm(
            data=valid_registration_data(
                display_name="Someone Else",
                email="AOIFE@example.com",
            )
        )
        self.assertFalse(duplicate.is_valid())
        self.assertIn("email", duplicate.errors)

    def test_terms_acceptance_is_required(self):
        data = valid_registration_data()
        del data["accept_terms"]
        form = RegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("accept_terms", form.errors)

    def test_username_collision_gets_numeric_suffix(self):
        first = RegistrationForm(data=valid_registration_data())
        self.assertTrue(first.is_valid(), msg=first.errors.as_json())
        first.save()

        # "Aoife-B" slugifies to the same username base as "Aoife B".
        second = RegistrationForm(
            data=valid_registration_data(
                display_name="Aoife-B",
                email="other@example.com",
            )
        )
        self.assertTrue(second.is_valid(), msg=second.errors.as_json())
        user = second.save()
        self.assertEqual(user.username, "aoife_b2")


class RegistrationViewTests(TestCase):
    def test_register_page_renders(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create My Account")

    def test_successful_registration_logs_in_and_sends_email(self):
        response = self.client.post(
            reverse("accounts:register"),
            data=valid_registration_data(),
        )

        self.assertRedirects(response, reverse("accounts:welcome"))
        user = User.objects.get(email="aoife@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(user.email_verification_token), mail.outbox[0].body)
        self.assertIn("aoife@example.com", mail.outbox[0].to)

    def test_welcome_page_shows_whatsapp_link(self):
        self.client.post(
            reverse("accounts:register"),
            data=valid_registration_data(),
        )
        with self.settings(WHATSAPP_COMMUNITY_LINK="https://chat.whatsapp.com/test"):
            response = self.client.get(reverse("accounts:welcome"))
        self.assertContains(response, "https://chat.whatsapp.com/test")


class EmailVerificationTests(TestCase):
    def _register_user(self):
        self.client.post(
            reverse("accounts:register"),
            data=valid_registration_data(),
        )
        return User.objects.get(email="aoife@example.com")

    def test_valid_token_verifies_email(self):
        user = self._register_user()
        self.assertFalse(user.is_email_verified)

        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": user.email_verification_token},
            )
        )

        self.assertContains(response, "Email verified")
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_already_verified_token_shows_notice(self):
        user = self._register_user()
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": user.email_verification_token},
            )
        )

        self.assertContains(response, "Already verified")

    def test_unknown_token_shows_invalid_link(self):
        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": "00000000-0000-0000-0000-000000000000"},
            )
        )

        self.assertContains(response, "Invalid verification link")


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.client.logout()
        self.user = User.objects.get(email="aoife@example.com")

    def test_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "aoife@example.com", "password": "brave-purple-drums!"},
        )
        self.assertRedirects(response, "/")

    def test_login_with_display_name(self):
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "Aoife B", "password": "brave-purple-drums!"},
        )
        self.assertRedirects(response, "/")

    def test_login_with_display_name_is_case_insensitive(self):
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "aoife b", "password": "brave-purple-drums!"},
        )
        self.assertRedirects(response, "/")

    def test_login_respects_next_parameter(self):
        response = self.client.post(
            reverse("accounts:login"),
            data={
                "username": "Aoife B",
                "password": "brave-purple-drums!",
                "next": reverse("gallery:upload"),
            },
        )
        self.assertRedirects(response, reverse("gallery:upload"))

    def test_wrong_password_shows_clear_error(self):
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "Aoife B", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Your email/display name or password is incorrect"
        )

    def test_unknown_identifier_shows_generic_error(self):
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "Nobody Here", "password": "brave-purple-drums!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Your email/display name or password is incorrect"
        )

    def test_protected_page_redirects_to_public_login(self):
        response = self.client.get(reverse("gallery:upload"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)

    def test_logout_post_redirects_home(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfilePageTests(TestCase):
    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.client.logout()
        self.user = User.objects.get(email="aoife@example.com")
        self.profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.user.username}
        )

    def test_profile_is_public_and_hides_phone(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aoife B")
        self.assertContains(response, "Swords")
        self.assertNotContains(response, "+353 87 123 4567")
        self.assertNotContains(response, "Edit Profile")

    def test_phone_is_never_shown_even_to_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertNotContains(response, "+353 87 123 4567")

    def test_owner_sees_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertContains(response, "Edit Profile")

    def test_unknown_username_returns_404(self):
        response = self.client.get(
            reverse("accounts:profile_detail", kwargs={"username": "nobody"})
        )
        self.assertEqual(response.status_code, 404)

    def test_profile_shortcut_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_profile_shortcut_redirects_to_own_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, self.profile_url)


class ProfileMyPostsTests(TestCase):
    """Owner-only 'My posts' section on the profile page."""

    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.owner = User.objects.get(email="aoife@example.com")
        self.other = User.objects.create_user(
            username="other_musician",
            email="other@example.com",
            password="jam-session-test-pass1",
            display_name="Other Musician",
        )
        self.profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.owner.username}
        )

    def test_my_posts_section_only_visible_to_owner(self):
        CommunityPost.objects.create(
            author=self.owner,
            title="Owner pending jam",
            body="Waiting for approval",
            status=ApprovalStatus.PENDING,
        )

        self.client.force_login(self.other)
        stranger_view = self.client.get(self.profile_url)
        self.assertNotContains(stranger_view, "My posts")
        self.assertNotContains(stranger_view, "Owner pending jam")

        self.client.force_login(self.owner)
        owner_view = self.client.get(self.profile_url)
        self.assertContains(owner_view, "My posts")
        self.assertContains(owner_view, "Owner pending jam")

    def test_my_posts_lists_only_own_posts_including_pending(self):
        own_pending = CommunityPost.objects.create(
            author=self.owner,
            title="My pending post",
            body="Still in the queue",
            status=ApprovalStatus.PENDING,
        )
        own_approved = CommunityPost.objects.create(
            author=self.owner,
            title="My approved post",
            body="Live on the community",
            status=ApprovalStatus.APPROVED,
        )
        CommunityPost.objects.create(
            author=self.other,
            title="Someone else post",
            body="Should not appear",
            status=ApprovalStatus.APPROVED,
        )
        CommunityComment.objects.create(
            post=own_approved,
            author=self.owner,
            body="A comment must not appear in My posts",
            status=ApprovalStatus.APPROVED,
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.profile_url)

        self.assertEqual(list(response.context["my_posts"]), [own_approved, own_pending])
        self.assertContains(response, "My pending post")
        self.assertContains(response, "My approved post")
        self.assertContains(response, "Pending approval")
        self.assertContains(response, "Approved")
        self.assertNotContains(response, "Someone else post")
        self.assertNotContains(response, "A comment must not appear in My posts")

    def test_my_posts_title_links_to_post_detail(self):
        post = CommunityPost.objects.create(
            author=self.owner,
            title="Linkable jam",
            body="Open me",
            status=ApprovalStatus.PENDING,
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.profile_url)

        detail_url = reverse("community:post_detail", args=[post.slug])
        self.assertContains(response, f'href="{detail_url}"')

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Linkable jam")
        self.assertContains(detail_response, "Pending approval")

    def test_rejected_post_is_listed_but_not_linked_to_detail(self):
        post = CommunityPost.objects.create(
            author=self.owner,
            title="Rejected jam",
            body="Not suitable",
            status=ApprovalStatus.REJECTED,
        )
        detail_url = reverse("community:post_detail", args=[post.slug])

        self.client.force_login(self.owner)
        response = self.client.get(self.profile_url)

        self.assertContains(response, "Rejected jam")
        self.assertContains(response, "Rejected")
        self.assertNotContains(response, f'href="{detail_url}"')
        self.assertContains(
            response, f'action="{reverse("community:post_delete", args=[post.slug])}"'
        )

    def test_rejected_post_with_reason_shows_exact_reason_on_profile(self):
        reason = "Not related to jam sessions in Ireland."
        CommunityPost.objects.create(
            author=self.owner,
            title="Off-topic jam",
            body="Wrong topic",
            status=ApprovalStatus.REJECTED,
            rejection_reason=reason,
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.profile_url)

        self.assertEqual(response.context["my_posts"][0].rejection_reason, reason)
        self.assertContains(response, reason)
        self.assertContains(response, "Reason for rejection")
        self.assertNotContains(response, "No reason provided.")

    def test_rejected_post_without_reason_shows_fallback_message(self):
        CommunityPost.objects.create(
            author=self.owner,
            title="Rejected without note",
            body="No explanation stored",
            status=ApprovalStatus.REJECTED,
            rejection_reason="",
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.profile_url)

        self.assertEqual(response.context["my_posts"][0].rejection_reason, "")
        self.assertContains(response, "No reason provided.")

    def test_my_posts_delete_button_uses_community_post_delete(self):
        post = CommunityPost.objects.create(
            author=self.owner,
            title="Delete me from profile",
            body="Gone soon",
            status=ApprovalStatus.PENDING,
        )
        delete_url = reverse("community:post_delete", args=[post.slug])

        self.client.force_login(self.owner)
        profile_response = self.client.get(self.profile_url)
        self.assertContains(profile_response, f'action="{delete_url}"')

        delete_response = self.client.post(delete_url)
        self.assertRedirects(delete_response, reverse("community:list"))
        self.assertFalse(CommunityPost.objects.filter(pk=post.pk).exists())


class ProfileReviewItemsTests(TestCase):
    """Staff-only Review Items control on the owner profile."""

    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.regular = User.objects.get(email="aoife@example.com")
        self.staff = User.objects.create_user(
            username="review_staff",
            email="review_staff@example.com",
            password="jam-session-test-pass1",
            display_name="Review Staff",
            is_staff=True,
        )
        self.staff_profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.staff.username}
        )
        self.regular_profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.regular.username}
        )
        self.queue_url = reverse("community:moderation_queue")

    def test_non_staff_owner_does_not_see_review_items(self):
        self.client.force_login(self.regular)
        response = self.client.get(self.regular_profile_url)

        self.assertFalse(response.context["show_review_items"])
        self.assertNotContains(response, "Review Items")
        self.assertNotContains(response, self.queue_url)

    def test_staff_with_zero_pending_sees_disabled_review_items(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.staff_profile_url)

        self.assertTrue(response.context["show_review_items"])
        self.assertEqual(response.context["pending_review_count"], 0)
        self.assertContains(response, "Review Items")
        self.assertContains(response, "Nothing to review")
        self.assertContains(response, "profile-review-items--disabled")
        self.assertNotContains(response, f'href="{self.queue_url}"')

    def test_staff_with_pending_items_sees_active_link_and_correct_count(self):
        author = self.regular
        CommunityPost.objects.create(
            author=author,
            title="Pending A",
            body="Body A",
            status=ApprovalStatus.PENDING,
        )
        CommunityPost.objects.create(
            author=author,
            title="Pending B",
            body="Body B",
            status=ApprovalStatus.PENDING,
        )
        approved = CommunityPost.objects.create(
            author=author,
            title="Approved host",
            body="Host",
            status=ApprovalStatus.APPROVED,
        )
        CommunityComment.objects.create(
            post=approved,
            author=author,
            body="Pending comment",
            status=ApprovalStatus.PENDING,
        )
        GalleryItem.objects.create(
            uploaded_by=author,
            file="image/upload/v1/pending_gallery.jpg",
            media_type=MediaType.IMAGE,
            title="Pending gallery",
            status=ApprovalStatus.PENDING,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.staff_profile_url)

        # 2 pending posts + 1 pending comment + 1 pending gallery item
        self.assertEqual(response.context["pending_review_count"], 4)
        self.assertContains(response, "Review Items")
        self.assertContains(response, f'href="{self.queue_url}"')
        self.assertContains(response, "profile-review-items--active")
        self.assertContains(response, ">4<")
        self.assertNotContains(response, "Nothing to review")


class ProfileEditTests(TestCase):
    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.user = User.objects.get(email="aoife@example.com")
        self.edit_url = reverse("accounts:profile_edit")

    def _edit_data(self, **overrides):
        data = {
            "display_name": "Aoife B",
            "phone_number": "+353 87 123 4567",
            "county": "dublin",
            "town_city": "Swords",
            "instruments": ["electric_guitar", "vocals"],
            "other_instrument": "",
            "bio": "",
        }
        data.update(overrides)
        return data

    def test_edit_requires_login(self):
        self.client.logout()
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_owner_can_update_profile(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                bio="Guitarist from Dublin.",
                preferred_genres=["rock", "blues_rock"],
                county="wicklow",
                town_city="Bray",
            ),
        )

        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_detail", kwargs={"username": self.user.username}
            ),
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Guitarist from Dublin.")
        self.assertEqual(self.user.preferred_genres, ["rock", "blues_rock"])
        self.assertEqual(self.user.county, "wicklow")
        self.assertEqual(self.user.town_city, "Bray")

    def test_edit_rejects_town_outside_county(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(county="galway", town_city="Swords"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Please choose a town or city in the selected county."
        )

    def test_edit_rejects_taken_display_name(self):
        other = User.objects.create_user(
            username="someone",
            email="someone@example.com",
            password="brave-purple-drums!",
            display_name="Someone Else",
        )
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(display_name=other.display_name.upper()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This display name is already taken")

    def test_profile_page_uses_browser_friendly_picture_url(self):
        self.user.profile_picture.name = (
            "JamSession Lab/aoife_b/profile_pictures/IMG_4599"
        )
        self.user.save(update_fields=["profile_picture"])

        response = self.client.get(
            reverse(
                "accounts:profile_detail",
                kwargs={"username": self.user.username},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "f_auto")
        self.assertContains(response, "profile_pictures/IMG_4599")


class ProfilePictureHelpersTests(TestCase):
    def test_heic_upload_is_converted_to_jpeg(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from jamsession.image_formats import (
            convert_heic_upload_to_jpeg,
            register_heif_opener,
        )

        register_heif_opener()
        try:
            import pillow_heif  # noqa: F401
        except ImportError:
            self.skipTest("pillow-heif is not installed")

        # Build a tiny HEIC in memory when the encoder is available.
        rgb = Image.new("RGB", (8, 8), color=(255, 0, 0))
        buffer = BytesIO()
        try:
            rgb.save(buffer, format="HEIF")
        except Exception:
            self.skipTest("HEIF encoding is not available in this environment")

        uploaded = SimpleUploadedFile(
            "photo.heic",
            buffer.getvalue(),
            content_type="image/heic",
        )
        converted = convert_heic_upload_to_jpeg(
            uploaded,
            field_name="profile_picture",
        )
        self.assertTrue(converted.name.lower().endswith(".jpg"))
        self.assertEqual(converted.content_type, "image/jpeg")
        self.assertGreater(converted.size, 0)


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.user = User.objects.get(email="aoife@example.com")
        self.delete_url = reverse("accounts:account_delete")

    def test_delete_requires_login(self):
        self.client.logout()
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_delete_requires_post(self):
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 405)

    def test_wrong_password_does_not_delete(self):
        response = self.client.post(
            self.delete_url,
            data={"confirm": "on", "password": "wrong-password"},
        )
        self.assertRedirects(response, reverse("accounts:profile_edit"))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_missing_confirmation_does_not_delete(self):
        response = self.client.post(
            self.delete_url,
            data={"password": "brave-purple-drums!"},
        )
        self.assertRedirects(response, reverse("accounts:profile_edit"))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_confirmed_delete_removes_user_and_logs_out(self):
        response = self.client.post(
            self.delete_url,
            data={"confirm": "on", "password": "brave-purple-drums!"},
        )
        self.assertRedirects(response, "/")
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_gallery_items_survive_without_author(self):
        from gallery.models import ApprovalStatus, GalleryItem

        item = GalleryItem.objects.create(
            uploaded_by=self.user,
            file="v123/sample.jpg",
            media_type="image",
            status=ApprovalStatus.APPROVED,
        )

        self.client.post(
            self.delete_url,
            data={"confirm": "on", "password": "brave-purple-drums!"},
        )

        item.refresh_from_db()
        self.assertIsNone(item.uploaded_by)
        self.assertEqual(item.status, ApprovalStatus.APPROVED)


class UserProfilePictureCloudinaryCleanupTests(TestCase):
    """
    Account deletion must remove the profile picture from Cloudinary storage,
    but must NOT touch Cloudinary assets belonging to content that survives
    with author/uploaded_by set to NULL (posts, comments, gallery items).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="cleanup_user",
            email="cleanup_user@example.com",
            password="jam-session-test-pass1",
            display_name="Cleanup User",
            first_name="Cleanup",
            last_name="User",
        )
        self.user.profile_picture.name = (
            "JamSession Lab/cleanup_user/profile_pictures/avatar_id"
        )
        self.user.save(update_fields=["profile_picture"])

    def test_deleting_user_cleans_profile_picture_not_surviving_content(self):
        post = CommunityPost.objects.create(
            author=self.user,
            title="Survives account deletion",
            body="Body",
            status=ApprovalStatus.APPROVED,
        )
        CommunityPostMedia.objects.create(
            post=post,
            file="image/upload/v1/surviving_post_media.jpg",
            media_type=MediaType.IMAGE,
        )
        comment = CommunityComment.objects.create(
            post=post,
            author=self.user,
            body="Survives too",
            status=ApprovalStatus.APPROVED,
        )
        CommunityCommentMedia.objects.create(
            comment=comment,
            file="image/upload/v1/surviving_comment_media.jpg",
            media_type=MediaType.IMAGE,
        )
        gallery_item = GalleryItem.objects.create(
            uploaded_by=self.user,
            file="image/upload/v1/surviving_gallery.jpg",
            media_type=MediaType.IMAGE,
            status=ApprovalStatus.APPROVED,
        )

        with (
            patch("jamsession.cloudinary_cleanup._delete_stored_file") as mock_cleanup,
            patch("jamsession.cloudinary_cleanup.destroy") as mock_destroy,
        ):
            self.user.delete()

        mock_cleanup.assert_called_once()
        cleaned_value = mock_cleanup.call_args.args[0]
        self.assertEqual(
            cleaned_value.name,
            "JamSession Lab/cleanup_user/profile_pictures/avatar_id",
        )
        # Surviving moderated content must not trigger Cloudinary destroy.
        mock_destroy.assert_not_called()

        post.refresh_from_db()
        gallery_item.refresh_from_db()
        self.assertIsNone(post.author)
        self.assertIsNone(gallery_item.uploaded_by)
        self.assertTrue(CommunityPostMedia.objects.filter(post=post).exists())
        self.assertTrue(CommunityCommentMedia.objects.filter(comment=comment).exists())


class TermsPagesTests(TestCase):
    def test_terms_page_renders(self):
        response = self.client.get(reverse("pages:terms"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Terms of Service")
        self.assertContains(response, "18 years old")

    def test_privacy_page_renders(self):
        response = self.client.get(reverse("pages:privacy"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy Policy")

    def test_contact_page_renders(self):
        response = self.client.get(reverse("pages:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact Us")
        self.assertContains(response, "jamsessionlab")
