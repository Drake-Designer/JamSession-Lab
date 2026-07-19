from datetime import date
from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, TestCase
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
from .models import SocialLink, User
from .social_platforms import detect_social_platform
from .validators import (
    UNDERAGE_ERROR_MESSAGE,
    YEARS_OF_EXPERIENCE_EXCEED_AGE_MESSAGE,
)


def social_links_formset_data(urls=None, existing_ids=None):
    """
    Build POST keys for the SocialLink inline formset (prefix social_links).

    ``urls`` is a list of URL strings for the submitted rows.
    ``existing_ids`` maps row index → SocialLink pk for INITIAL_FORMS rows.
    """
    urls = list(urls or [])
    existing_ids = existing_ids or {}
    initial = len(existing_ids)
    # Always keep at least one row (matching extra=1 on an empty set).
    if not urls:
        urls = [""]
    total = len(urls)
    data = {
        "social_links-TOTAL_FORMS": str(total),
        "social_links-INITIAL_FORMS": str(initial),
        "social_links-MIN_NUM_FORMS": "0",
        "social_links-MAX_NUM_FORMS": "5",
    }
    for index, url in enumerate(urls):
        data[f"social_links-{index}-url"] = url
        data[f"social_links-{index}-id"] = str(existing_ids.get(index, ""))
        data[f"social_links-{index}-DELETE"] = ""
    return data


class SocialPlatformDetectionTests(SimpleTestCase):
    def test_detects_known_hosts(self):
        cases = (
            ("https://open.spotify.com/artist/abc", "spotify", "Spotify"),
            ("https://www.instagram.com/jamlab/", "instagram", "Instagram"),
            ("https://youtu.be/abc123", "youtube", "YouTube"),
            ("https://music.youtube.com/channel/x", "youtube", "YouTube"),
            ("https://www.facebook.com/page", "facebook", "Facebook"),
            ("https://soundcloud.com/artist/track", "soundcloud", "SoundCloud"),
            ("https://www.tiktok.com/@user", "tiktok", "TikTok"),
            ("https://myband.ie/about", "website", "Website"),
        )
        for url, key, label in cases:
            platform = detect_social_platform(url)
            self.assertIsNotNone(platform)
            self.assertEqual(platform.key, key, msg=url)
            self.assertEqual(str(platform.label), label, msg=url)

    def test_empty_url_returns_none(self):
        self.assertIsNone(detect_social_platform(""))
        self.assertIsNone(detect_social_platform(None))


def valid_registration_data(**overrides):
    """Complete, valid POST data for the registration form."""
    data = {
        "first_name": "Aoife",
        "last_name": "Byrne",
        "display_name": "Aoife B",
        "email": "aoife@example.com",
        "phone_number": "+353871234567",
        "password1": "brave-purple-drums!",
        "password2": "brave-purple-drums!",
        "date_of_birth": "1990-05-10",
        "county": "dublin",
        "town_city": "Swords",
        "instruments": ["electric_guitar", "vocals"],
        "years_of_experience": "5",
        "experience_level": "intermediate",
        "accept_terms": "on",
    }
    data.update(overrides)
    return data


def mark_email_verified(user):
    """Mark a user as email-verified (needed for member-action tests)."""
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    return user


class RegistrationFormTests(TestCase):
    def test_valid_data_creates_user(self):
        form = RegistrationForm(data=valid_registration_data())
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

        user = form.save()
        self.assertEqual(user.display_name, "Aoife B")
        self.assertEqual(user.username, "aoife_b")
        self.assertEqual(user.email, "aoife@example.com")
        self.assertEqual(user.instruments, ["electric_guitar", "vocals"])
        self.assertEqual(user.years_of_experience, 5)
        self.assertEqual(user.experience_level, "intermediate")
        self.assertEqual(
            user.experience_started_year,
            timezone.localdate().year - 5,
        )
        self.assertIsNotNone(user.terms_accepted_at)
        self.assertFalse(user.is_email_verified)

    def test_years_of_experience_is_required(self):
        form = RegistrationForm(
            data=valid_registration_data(years_of_experience="")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("years_of_experience", form.errors)

    def test_experience_level_is_required(self):
        form = RegistrationForm(data=valid_registration_data(experience_level=""))
        self.assertFalse(form.is_valid())
        self.assertIn("experience_level", form.errors)

    def test_years_of_experience_cannot_exceed_age(self):
        form = RegistrationForm(
            data=valid_registration_data(
                date_of_birth="2005-01-01",
                years_of_experience="40",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("years_of_experience", form.errors)
        self.assertIn(
            str(YEARS_OF_EXPERIENCE_EXCEED_AGE_MESSAGE),
            [str(error) for error in form.errors["years_of_experience"]],
        )

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


class YearsOfExperienceAutoIncrementTests(TestCase):
    """Years of experience are derived from a start year and rise each 1 January."""

    def test_declared_years_store_start_year_and_increment_on_new_year(self):
        user = User(
            username="pippo",
            email="pippo@example.com",
            date_of_birth=date(2000, 2, 5),
        )
        with patch(
            "accounts.validators.timezone.localdate",
            return_value=date(2026, 7, 18),
        ):
            user.years_of_experience = 10

        self.assertEqual(user.experience_started_year, 2016)

        with patch(
            "accounts.validators.timezone.localdate",
            return_value=date(2026, 7, 18),
        ):
            self.assertEqual(user.years_of_experience, 10)

        with patch(
            "accounts.validators.timezone.localdate",
            return_value=date(2027, 1, 1),
        ):
            self.assertEqual(user.years_of_experience, 11)

    def test_property_uses_validator_helpers_consistently(self):
        from .validators import (
            experience_started_year_from_years,
            years_of_experience_from_started_year,
        )

        today = date(2026, 7, 18)
        started = experience_started_year_from_years(10, today=today)
        self.assertEqual(started, 2016)
        self.assertEqual(
            years_of_experience_from_started_year(started, today=date(2027, 1, 1)),
            11,
        )


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
        self.client.logout()
        return User.objects.get(email="aoife@example.com")

    def test_valid_token_verifies_email_and_logs_in(self):
        user = self._register_user()
        self.assertFalse(user.is_email_verified)

        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": user.email_verification_token},
            )
        )

        self.assertRedirects(response, reverse("pages:home"))
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_already_verified_token_redirects_home(self):
        user = self._register_user()
        mark_email_verified(user)

        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": user.email_verification_token},
            )
        )

        self.assertRedirects(response, reverse("pages:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_unknown_token_shows_invalid_link(self):
        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": "00000000-0000-0000-0000-000000000000"},
            )
        )

        self.assertContains(response, "Invalid verification link")


class EmailVerificationEnforcementTests(TestCase):
    """Unverified members are soft-blocked from profiles and member actions."""

    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.user = User.objects.get(email="aoife@example.com")
        self.other = User.objects.create_user(
            username="other_musician",
            email="other@example.com",
            password="jam-session-test-pass1",
            display_name="Other Musician",
            is_email_verified=True,
        )
        self.verification_url = reverse("accounts:verification_required")
        self.other_profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.other.username}
        )
        self.own_profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.user.username}
        )

    def test_unverified_user_blocked_from_own_profile(self):
        response = self.client.get(self.own_profile_url)
        self.assertRedirects(response, self.verification_url)

    def test_unverified_user_blocked_from_other_profile(self):
        response = self.client.get(self.other_profile_url)
        self.assertRedirects(response, self.verification_url)

    def test_unverified_user_blocked_from_profile_edit(self):
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertRedirects(response, self.verification_url)

    def test_unverified_user_blocked_from_gallery_upload(self):
        response = self.client.get(reverse("gallery:upload"))
        self.assertRedirects(response, self.verification_url)

    def test_unverified_user_can_browse_home(self):
        response = self.client.get(reverse("pages:home"))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_visitor_can_still_view_profiles(self):
        self.client.logout()
        response = self.client.get(self.own_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aoife B")

    def test_verified_user_can_view_profiles(self):
        mark_email_verified(self.user)
        response = self.client.get(self.other_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Other Musician")

    def test_staff_bypasses_verification_gate(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertFalse(self.user.is_email_verified)

        response = self.client.get(self.own_profile_url)
        self.assertEqual(response.status_code, 200)

    def test_admin_can_mark_email_verified(self):
        self.assertFalse(self.user.is_email_verified)
        mark_email_verified(self.user)
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertEqual(response.status_code, 200)

    def test_resend_verification_sends_new_token(self):
        old_token = self.user.email_verification_token
        mail.outbox.clear()

        response = self.client.post(reverse("accounts:resend_verification"))
        self.assertRedirects(response, self.verification_url)

        self.user.refresh_from_db()
        self.assertNotEqual(self.user.email_verification_token, old_token)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(self.user.email_verification_token), mail.outbox[0].body)

    def test_resend_verification_rate_limited(self):
        self.client.post(reverse("accounts:resend_verification"))
        mail.outbox.clear()

        response = self.client.post(reverse("accounts:resend_verification"))
        self.assertRedirects(response, self.verification_url)
        self.assertEqual(len(mail.outbox), 0)

    def test_unverified_login_redirects_to_verification_required(self):
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "aoife@example.com", "password": "brave-purple-drums!"},
        )
        self.assertRedirects(response, self.verification_url)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.client.logout()
        self.user = User.objects.get(email="aoife@example.com")
        mark_email_verified(self.user)

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
        mark_email_verified(self.user)
        self.profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.user.username}
        )

    def test_profile_is_public_and_hides_phone(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aoife B")
        self.assertContains(response, "Swords")
        self.assertNotContains(response, "+353871234567")
        self.assertNotContains(response, "Edit Profile")

    def test_phone_is_never_shown_even_to_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertNotContains(response, "+353871234567")

    def test_owner_sees_edit_button(self):
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertContains(response, "Edit profile")

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

    def test_public_profile_renders_clickable_social_link(self):
        SocialLink.objects.create(
            user=self.user,
            url="https://open.spotify.com/artist/example",
            order=0,
        )
        self.user.other_instrument = "Theremin"
        self.user.instruments = ["other", "vocals"]
        self.user.preferred_genres = ["rock", "other"]
        self.user.other_genre = "Celtic Fusion"
        self.user.years_of_experience = 8
        self.user.experience_level = "advanced"
        self.user.save()

        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spotify")
        self.assertContains(response, "profile-social__link--spotify")
        self.assertContains(
            response,
            'href="https://open.spotify.com/artist/example"',
        )
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertNotContains(
            response, ">https://open.spotify.com/artist/example<"
        )
        self.assertNotContains(response, "View link")
        self.assertContains(response, "Theremin")
        self.assertContains(response, "Celtic Fusion")
        self.assertContains(response, "Years of experience")
        self.assertContains(response, "8")
        self.assertContains(response, "Advanced")
        self.assertEqual(len(response.context["social_links"]), 1)
        self.assertEqual(
            response.context["social_links"][0]["platform"].key, "spotify"
        )

    def test_public_profile_shows_multiple_social_chips(self):
        SocialLink.objects.create(
            user=self.user,
            url="https://www.instagram.com/rockgirl/",
            order=0,
        )
        SocialLink.objects.create(
            user=self.user,
            url="https://open.spotify.com/artist/example",
            order=1,
        )
        response = self.client.get(self.profile_url)
        self.assertContains(response, "Instagram")
        self.assertContains(response, "Spotify")
        self.assertContains(response, "profile-social__link--instagram")
        self.assertContains(response, "profile-social__link--spotify")
        self.assertEqual(len(response.context["social_links"]), 2)

    def test_public_profile_detects_youtube_and_generic_website(self):
        SocialLink.objects.create(
            user=self.user,
            url="https://youtu.be/dQw4w9WgXcQ",
            order=0,
        )
        response = self.client.get(self.profile_url)
        self.assertContains(response, "YouTube")
        self.assertContains(response, "profile-social__link--youtube")

        SocialLink.objects.all().delete()
        SocialLink.objects.create(
            user=self.user,
            url="https://example.com/my-band",
            order=0,
        )
        response = self.client.get(self.profile_url)
        self.assertContains(response, "Website")
        self.assertContains(response, "profile-social__link--website")

    def test_public_profile_shows_other_badges_without_raw_other_code(self):
        self.user.instruments = ["other"]
        self.user.other_instrument = "Handpan"
        self.user.preferred_genres = ["other"]
        self.user.other_genre = "Afrobeat"
        self.user.save()

        response = self.client.get(self.profile_url)
        self.assertContains(response, "Handpan")
        self.assertContains(response, "Afrobeat")
        self.assertEqual(response.context["instrument_labels"], ["Handpan"])
        self.assertEqual(response.context["genre_labels"], ["Afrobeat"])


class ProfileMyPostsTests(TestCase):
    """Owner-only 'My posts' section on the profile page."""

    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.owner = User.objects.get(email="aoife@example.com")
        mark_email_verified(self.owner)
        self.other = User.objects.create_user(
            username="other_musician",
            email="other@example.com",
            password="jam-session-test-pass1",
            display_name="Other Musician",
            is_email_verified=True,
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
    """Staff-only REVIEW / ADMIN TOOL / EVENTS controls on the owner profile."""

    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.regular = User.objects.get(email="aoife@example.com")
        mark_email_verified(self.regular)
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
        self.admin_tool_url = reverse("community:admin_tool")
        self.events_manage_url = reverse("events:manage")

    def test_non_staff_owner_does_not_see_staff_tools(self):
        self.client.force_login(self.regular)
        response = self.client.get(self.regular_profile_url)

        self.assertFalse(response.context["show_staff_tools"])
        self.assertContains(response, "Edit profile")
        self.assertContains(response, "profile-edit-btn")
        self.assertNotContains(response, "REVIEW")
        self.assertNotContains(response, "ADMIN TOOL")
        self.assertNotContains(response, "EVENTS")
        self.assertNotContains(response, self.queue_url)
        self.assertNotContains(response, self.admin_tool_url)
        self.assertNotContains(response, self.events_manage_url)

    def test_staff_with_zero_pending_hides_review_but_shows_admin_and_events(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.staff_profile_url)

        self.assertTrue(response.context["show_staff_tools"])
        self.assertEqual(response.context["pending_review_count"], 0)
        self.assertContains(response, "Edit profile")
        self.assertContains(response, "profile-edit-btn")
        self.assertNotContains(response, "REVIEW")
        self.assertNotContains(response, f'href="{self.queue_url}"')
        self.assertContains(response, "ADMIN TOOL")
        self.assertContains(response, f'href="{self.admin_tool_url}"')
        self.assertContains(response, "EVENTS")
        self.assertContains(response, f'href="{self.events_manage_url}"')

    def test_staff_with_pending_items_sees_review_link_and_correct_count(self):
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
        self.assertContains(response, "REVIEW")
        self.assertContains(response, f'href="{self.queue_url}"')
        self.assertContains(response, "profile-staff-btn--review")
        self.assertContains(response, ">4<")
        self.assertContains(response, "ADMIN TOOL")
        self.assertContains(response, f'href="{self.admin_tool_url}"')
        self.assertContains(response, "EVENTS")
        self.assertContains(response, f'href="{self.events_manage_url}"')


class ProfileEditTests(TestCase):
    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.user = User.objects.get(email="aoife@example.com")
        mark_email_verified(self.user)
        self.edit_url = reverse("accounts:profile_edit")

    def _edit_data(self, **overrides):
        data = {
            "display_name": "Aoife B",
            "phone_number": "+353871234567",
            "county": "dublin",
            "town_city": "Swords",
            "instruments": ["electric_guitar", "vocals"],
            "other_instrument": "",
            "preferred_genres": [],
            "other_genre": "",
            "years_of_experience": "5",
            "experience_level": "intermediate",
            "bio": "",
        }
        data.update(social_links_formset_data())
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

    def test_edit_requires_years_of_experience(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(years_of_experience=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    def test_edit_requires_experience_level(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(experience_level=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

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

    def test_edit_form_shows_immediate_picture_remove_control(self):
        storage_path = "JamSession Lab/aoife_b/profile_pictures/IMG_4599"
        self.user.profile_picture.name = storage_path
        self.user.save(update_fields=["profile_picture"])

        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)

        # Custom widget: circular preview image, not Django's "Currently: <a>url</a>".
        self.assertContains(response, 'class="profile-picture-widget__preview"')
        self.assertContains(response, "<img")
        self.assertContains(response, "Change photo")
        self.assertContains(response, "data-profile-picture-remove")
        self.assertContains(response, "data-immediate-remove-url")
        self.assertContains(response, "data-immediate-upload-url")
        self.assertNotContains(response, "Currently:")
        # Storage path must not appear as visible link text (old ClearableFileInput).
        self.assertNotContains(response, f">{storage_path}<")
        self.assertNotContains(response, f'href="{self.user.profile_picture.url}"')

    def test_profile_picture_remove_endpoint_clears_immediately(self):
        """
        Remove photo via AJAX clears the DB field AND deletes the remote
        Cloudinary asset without submitting the full edit form.
        """
        self.user.profile_picture.name = (
            "JamSession Lab/aoife_b/profile_pictures/to_clear"
        )
        self.user.save(update_fields=["profile_picture"])

        with patch("jamsession.cloudinary_cleanup._delete_stored_file") as mock_cleanup:
            response = self.client.post(
                reverse("accounts:profile_picture_remove")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile_picture))
        mock_cleanup.assert_called_once()
        cleaned_value = mock_cleanup.call_args.args[0]
        self.assertEqual(
            cleaned_value.name,
            "JamSession Lab/aoife_b/profile_pictures/to_clear",
        )

    def test_profile_picture_upload_endpoint_saves_immediately(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (40, 40), color=(20, 20, 20)).save(buffer, format="JPEG")
        upload = SimpleUploadedFile(
            "avatar.jpg",
            buffer.getvalue(),
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("accounts:profile_picture_upload"),
            data={"profile_picture": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile_picture))

    def test_profile_picture_upload_endpoint_rejects_missing_file(self):
        response = self.client.post(reverse("accounts:profile_picture_upload"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_social_link_delete_endpoint_removes_immediately(self):
        keep = SocialLink.objects.create(
            user=self.user,
            url="https://open.spotify.com/artist/keep",
            order=0,
        )
        drop = SocialLink.objects.create(
            user=self.user,
            url="https://www.instagram.com/drop/",
            order=1,
        )

        response = self.client.post(
            reverse("accounts:social_link_delete", kwargs={"pk": drop.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertFalse(SocialLink.objects.filter(pk=drop.pk).exists())
        keep.refresh_from_db()
        self.assertEqual(keep.order, 0)
        self.assertEqual(self.user.social_links.count(), 1)

    def test_social_link_delete_rejects_other_users_links(self):
        other = User.objects.create_user(
            username="other_link_owner",
            email="otherlink@example.com",
            password="brave-purple-drums!",
            display_name="Other Link",
        )
        link = SocialLink.objects.create(
            user=other,
            url="https://www.instagram.com/other/",
            order=0,
        )
        response = self.client.post(
            reverse("accounts:social_link_delete", kwargs={"pk": link.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SocialLink.objects.filter(pk=link.pk).exists())

    def test_edit_form_hides_remove_on_empty_social_link_row(self):
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "social-links-row__delete-wrap is-hidden")
        self.assertContains(response, "Add another link")
        self.assertContains(response, "social-links-forms")

    def test_replacing_profile_picture_triggers_cloudinary_cleanup(self):
        """
        Change photo (replace without Remove) must delete the previous
        Cloudinary asset via cleanup_old_file_on_change on pre_save.
        """
        self.user.profile_picture.name = (
            "JamSession Lab/aoife_b/profile_pictures/old_pic"
        )
        self.user.save(update_fields=["profile_picture"])

        with patch("jamsession.cloudinary_cleanup._delete_stored_file") as mock_cleanup:
            self.user.profile_picture.name = (
                "JamSession Lab/aoife_b/profile_pictures/new_pic"
            )
            self.user.save(update_fields=["profile_picture"])

        mock_cleanup.assert_called_once()
        cleaned_value = mock_cleanup.call_args.args[0]
        self.assertEqual(
            cleaned_value.name,
            "JamSession Lab/aoife_b/profile_pictures/old_pic",
        )

    def test_required_fields_reject_empty_submit(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                display_name="",
                phone_number="",
                county="",
                town_city="",
                instruments=[],
            ),
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        for field_name in (
            "display_name",
            "phone_number",
            "county",
            "town_city",
            "instruments",
        ):
            self.assertIn(field_name, form.errors)

    def test_other_instrument_requires_free_text(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                instruments=["other"],
                other_instrument="",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please specify your instrument.")

    def test_other_instrument_saves_free_text(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                instruments=["other"],
                other_instrument="Theremin",
            ),
        )
        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_detail", kwargs={"username": self.user.username}
            ),
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.instruments, ["other"])
        self.assertEqual(self.user.other_instrument, "Theremin")

    def test_other_genre_requires_free_text(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                preferred_genres=["other"],
                other_genre="",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please specify your genre.")

    def test_other_genre_saves_free_text(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                preferred_genres=["rock", "other"],
                other_genre="Celtic Fusion",
            ),
        )
        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_detail", kwargs={"username": self.user.username}
            ),
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_genres, ["rock", "other"])
        self.assertEqual(self.user.other_genre, "Celtic Fusion")

    def test_removed_genres_are_not_valid_choices(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(preferred_genres=["irish_traditional", "ska"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("preferred_genres", response.context["form"].errors)

    def test_social_link_rejects_url_without_scheme(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(**social_links_formset_data(["www.spotify.com/artist/x"])),
        )
        self.assertEqual(response.status_code, 200)
        formset = response.context["social_link_formset"]
        self.assertTrue(formset.errors)
        self.assertContains(
            response, "Enter a full URL starting with http:// or https://"
        )

    def test_social_link_rejects_non_http_schemes(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                **social_links_formset_data(["ftp://files.example.com/track"])
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Enter a full URL starting with http:// or https://"
        )

    def test_social_link_accepts_https(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                years_of_experience="5",
                experience_level="intermediate",
                **social_links_formset_data(
                    ["https://open.spotify.com/artist/example"]
                ),
            ),
        )
        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_detail", kwargs={"username": self.user.username}
            ),
        )
        self.user.refresh_from_db()
        links = list(self.user.social_links.order_by("order"))
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].url, "https://open.spotify.com/artist/example")
        self.assertEqual(self.user.years_of_experience, 5)
        self.assertEqual(self.user.experience_level, "intermediate")

    def test_can_save_multiple_social_links(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                **social_links_formset_data(
                    [
                        "https://www.instagram.com/aoife/",
                        "https://open.spotify.com/artist/aoife",
                        "https://youtube.com/@aoife",
                    ]
                )
            ),
        )
        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_detail", kwargs={"username": self.user.username}
            ),
        )
        urls = list(
            self.user.social_links.order_by("order").values_list("url", flat=True)
        )
        self.assertEqual(
            urls,
            [
                "https://www.instagram.com/aoife/",
                "https://open.spotify.com/artist/aoife",
                "https://youtube.com/@aoife",
            ],
        )

    def test_duplicate_social_links_rejected(self):
        response = self.client.post(
            self.edit_url,
            data=self._edit_data(
                **social_links_formset_data(
                    [
                        "https://www.instagram.com/aoife/",
                        "https://www.instagram.com/aoife/",
                    ]
                )
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You have already added this link.")
        self.assertEqual(self.user.social_links.count(), 0)

    def test_edit_form_maxlength_on_display_name_and_phone(self):
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_display_name"')
        self.assertContains(response, 'maxlength="20"')
        self.assertContains(response, 'id="id_phone_number"')
        self.assertContains(response, 'maxlength="15"')
        self.assertContains(response, "Display Name")
        self.assertContains(response, "jam-input--display-name")
        self.assertContains(response, "jam-input--phone-number")
        self.assertContains(response, "Add another link")
        self.assertContains(response, "social-links-forms")


class ProfileCompletionTests(TestCase):
    """Profile completion percentage, ring UI, and edit-form highlighting."""

    TOTAL_FIELDS = 11

    def setUp(self):
        self.client.post(reverse("accounts:register"), data=valid_registration_data())
        self.user = User.objects.get(email="aoife@example.com")
        mark_email_verified(self.user)
        self.profile_url = reverse(
            "accounts:profile_detail", kwargs={"username": self.user.username}
        )
        self.edit_url = reverse("accounts:profile_edit")

    def _empty_user(self):
        """User with every completion-tracked field blank (0%)."""
        return User.objects.create_user(
            username="empty_profile",
            email="empty@example.com",
            password="test-pass-12345!",
            first_name="Empty",
            last_name="Profile",
            display_name="",
            phone_number="",
            county="",
            town_city="",
            instruments=[],
            preferred_genres=[],
            experience_started_year=None,
            experience_level="",
            bio="",
        )

    def _complete_profile(self, user):
        """Fill every completion-tracked field (100%)."""
        user.profile_picture.name = (
            "JamSession Lab/aoife_b/profile_pictures/complete_pic"
        )
        user.display_name = user.display_name or "Complete User"
        user.phone_number = user.phone_number or "+353871234567"
        user.county = user.county or "dublin"
        user.town_city = user.town_city or "Swords"
        user.instruments = user.instruments or ["vocals"]
        user.preferred_genres = ["rock"]
        user.years_of_experience = 5
        user.experience_level = "intermediate"
        user.bio = "Guitarist from Dublin."
        user.save()
        if not user.social_links.exists():
            SocialLink.objects.create(
                user=user,
                url="https://open.spotify.com/artist/example",
                order=0,
            )

    def test_empty_profile_is_zero_percent(self):
        user = self._empty_user()
        self.assertEqual(user.profile_completion_percentage, 0)
        self.assertEqual(len(user.missing_fields), self.TOTAL_FIELDS)
        self.assertEqual(
            set(user.missing_field_keys),
            {
                "profile_picture",
                "display_name",
                "phone_number",
                "county",
                "town_city",
                "instruments",
                "preferred_genres",
                "years_of_experience",
                "experience_level",
                "bio",
                "social_links",
            },
        )

    def test_partial_profile_percentage_after_registration(self):
        # Registration fills display_name, phone, county, town, instruments,
        # years of experience, and experience level.
        self.assertEqual(self.user.profile_completion_percentage, round(7 / 11 * 100))
        self.assertEqual(self.user.profile_completion_percentage, 64)
        expected_missing = {
            "Profile picture",
            "Preferred music genres",
            "Bio",
            "Social / music links",
        }
        self.assertEqual(set(self.user.missing_fields), expected_missing)

    def test_eight_of_eleven_fields_rounds_correctly(self):
        self.user.bio = "Almost there."
        self.user.save(update_fields=["bio"])
        self.assertEqual(self.user.profile_completion_percentage, round(8 / 11 * 100))
        self.assertEqual(self.user.profile_completion_percentage, 73)
        self.assertNotIn("Bio", self.user.missing_fields)

    def test_complete_profile_is_one_hundred_percent(self):
        self._complete_profile(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_completion_percentage, 100)
        self.assertEqual(self.user.missing_fields, [])
        self.assertEqual(self.user.missing_field_keys, [])
        self.assertEqual(self.user.profile_completion_dashoffset, 0.0)

    def test_zero_years_of_experience_counts_as_filled(self):
        self.user.years_of_experience = 0
        self.user.save(update_fields=["experience_started_year"])
        self.assertNotIn("years_of_experience", self.user.missing_field_keys)

    def test_completion_ring_hidden_from_visitors(self):
        self.client.logout()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "profile-completion")

    def test_incomplete_owner_sees_clickable_ring_with_query_param(self):
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "profile-completion--incomplete")
        self.assertContains(response, "Profile 64% complete")
        edit_with_highlight = f"{self.edit_url}?highlight_missing=1"
        self.assertContains(response, f'href="{edit_with_highlight}"')
        self.assertContains(response, "stroke-dasharray")
        self.assertContains(response, "stroke-dashoffset")

    def test_complete_owner_ring_is_not_a_link(self):
        self._complete_profile(self.user)
        self.client.force_login(self.user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "profile-completion--complete")
        self.assertContains(response, "Profile 100% complete")
        self.assertNotContains(
            response, f'href="{self.edit_url}?highlight_missing=1"'
        )
        self.assertNotContains(response, "profile-completion--incomplete")
        # Complete ring is a non-link container (div), never an <a>.
        content = response.content.decode()
        complete_idx = content.find("profile-completion--complete")
        self.assertGreater(complete_idx, 0)
        snippet = content[max(0, complete_idx - 80) : complete_idx]
        self.assertIn("<div", snippet)
        self.assertNotIn("<a", snippet)

    def test_highlight_missing_marks_empty_fields_on_edit_form(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{self.edit_url}?highlight_missing=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-field--missing")
        self.assertContains(response, "form-field__missing-badge")
        content = response.content.decode()
        # Filled at registration — must not be highlighted.
        self.assertNotRegex(
            content,
            r'form-field--missing[^>]*>\s*<label[^>]*for="id_display_name"',
        )
        self.assertIn("Preferred music genres", content)
        self.assertRegex(
            content,
            r'form-field--missing[^>]*>[\s\S]*?Preferred music genres',
        )
        self.assertRegex(
            content,
            r'social-links-fieldset form-field--missing',
        )

    def test_edit_without_highlight_param_has_no_missing_class(self):
        self.client.force_login(self.user)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "form-field--missing")
        self.assertNotContains(response, "form-field__missing-badge")


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
        mark_email_verified(self.user)
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
            with self.captureOnCommitCallbacks(execute=True):
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


class UserBadgeInfoTests(TestCase):
    """badge_info is the single source of truth for membership badges."""

    def _make_user(self, username, **kwargs):
        defaults = {
            "username": username,
            "email": f"{username}@example.com",
            "password": "jam-session-test-pass1",
            "display_name": username,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    def test_superuser_is_founder_regardless_of_date_joined(self):
        user = self._make_user(
            "founder",
            is_superuser=True,
            is_staff=True,
        )
        user.date_joined = timezone.now()
        user.save(update_fields=["date_joined"])

        info = user.badge_info
        self.assertEqual(info.label, "Founder")
        self.assertEqual(info.css_class, "badge-founder")

    def test_superuser_with_is_staff_true_is_always_founder_not_staff(self):
        """
        createsuperuser sets both is_superuser and is_staff True.

        Precedence must remain superuser > staff so the badge is Founder.
        """
        user = self._make_user(
            "founder_staff",
            is_superuser=True,
            is_staff=True,
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.badge_info.label, "Founder")
        self.assertEqual(user.badge_info.css_class, "badge-founder")
        self.assertNotEqual(user.badge_info.label, "STAFF")

    def test_staff_non_superuser_is_staff_regardless_of_date_joined(self):
        user = self._make_user("staffer", is_staff=True, is_superuser=False)
        user.date_joined = timezone.now()
        user.save(update_fields=["date_joined"])

        info = user.badge_info
        self.assertEqual(info.label, "STAFF")
        self.assertEqual(info.css_class, "badge-staff")

    def test_new_member_within_thirty_days(self):
        from datetime import timedelta

        user = self._make_user("newbie")
        user.date_joined = timezone.now() - timedelta(days=10)
        user.force_member_badge = False
        user.save(update_fields=["date_joined", "force_member_badge"])

        info = user.badge_info
        self.assertEqual(info.label, "New Member")
        self.assertEqual(info.css_class, "badge-new-member")

    def test_member_after_thirty_days(self):
        from datetime import timedelta

        user = self._make_user("veteran")
        user.date_joined = timezone.now() - timedelta(days=30)
        user.force_member_badge = False
        user.save(update_fields=["date_joined", "force_member_badge"])

        info = user.badge_info
        self.assertEqual(info.label, "Member")
        self.assertEqual(info.css_class, "badge-member")

    def test_force_member_badge_overrides_new_member(self):
        from datetime import timedelta

        user = self._make_user("promoted")
        user.date_joined = timezone.now() - timedelta(days=5)
        user.force_member_badge = True
        user.save(update_fields=["date_joined", "force_member_badge"])

        info = user.badge_info
        self.assertEqual(info.label, "Member")
        self.assertEqual(info.css_class, "badge-member")

    def test_profile_page_renders_membership_badge(self):
        user = self._make_user("badge_profile")
        response = self.client.get(
            reverse("accounts:profile_detail", args=[user.username])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "user-badge")
        self.assertContains(response, user.badge_info.label)


class ActiveMembersOrderingTests(TestCase):
    def test_members_sorted_case_insensitive_with_empty_display_name_fallback(self):
        from accounts.members import get_active_members

        charlie = User.objects.create_user(
            username="charlie_user",
            email="charlie@example.com",
            password="jam-session-test-pass1",
            display_name="charlie",
        )
        alice = User.objects.create_user(
            username="alice_user",
            email="alice@example.com",
            password="jam-session-test-pass1",
            display_name="Alice",
        )
        empty = User.objects.create_user(
            username="zeta_fallback",
            email="zeta@example.com",
            password="jam-session-test-pass1",
            display_name="temp_empty",
        )
        # Bypass form validation to simulate a blank nickname in the DB.
        User.objects.filter(pk=empty.pk).update(display_name="")
        empty.refresh_from_db()

        inactive = User.objects.create_user(
            username="inactive_user",
            email="inactive@example.com",
            password="jam-session-test-pass1",
            display_name="zzz_inactive",
            is_active=False,
        )

        ordered = list(get_active_members())
        names = [member.public_display_name for member in ordered]

        self.assertIn(alice, ordered)
        self.assertIn(charlie, ordered)
        self.assertIn(empty, ordered)
        self.assertNotIn(inactive, ordered)
        self.assertEqual(names, sorted(names, key=str.casefold))
        # Blank display_name falls back to username for sorting and display.
        self.assertEqual(empty.public_display_name, "zeta_fallback")
        self.assertLess(
            names.index("Alice"),
            names.index("charlie"),
        )
        self.assertLess(
            names.index("charlie"),
            names.index("zeta_fallback"),
        )
