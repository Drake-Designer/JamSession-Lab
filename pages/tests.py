import tempfile
from unittest.mock import patch

from django.core import mail
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from pages.admin import HomeCarouselSlideAdminForm
from pages.models import HomeCarouselSlide

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
class HomeCarouselSlideAdminTests(TestCase):
    def setUp(self):
        self._media_root = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media_root)
        self._override.enable()

        self.slide = HomeCarouselSlide.objects.create(
            image=SimpleUploadedFile(
                "test-slide.png",
                MINIMAL_PNG,
                content_type="image/png",
            ),
            alt_text="Test slide",
            caption="Original caption",
        )
        self.slide.refresh_from_db()
        self.slide.image.name = "JamSession Lab/site/home_carousel/test_slide_id"

    def tearDown(self):
        self._override.disable()

    def test_edit_caption_without_reuploading_image_is_valid(self):
        form = HomeCarouselSlideAdminForm(
            data={
                "alt_text": self.slide.alt_text,
                "caption": "Updated caption only",
                "is_active": True,
                "order": self.slide.order,
            },
            instance=self.slide,
        )

        self.assertTrue(
            form.is_valid(),
            msg=form.errors.as_json(),
        )
        self.assertEqual(form.cleaned_data["caption"], "Updated caption only")

    @patch.object(FileSystemStorage, "delete", return_value=None)
    def test_delete_slide_removes_stored_image(self, mock_delete):
        image_name = self.slide.image.name

        with self.captureOnCommitCallbacks(execute=True):
            self.slide.delete()

        mock_delete.assert_called_once_with(image_name)


class ContactFormViewTests(TestCase):
    def setUp(self):
        self.url = reverse("pages:contact")

    def test_contact_page_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send message")

    def test_valid_contact_sends_email(self):
        response = self.client.post(
            self.url,
            data={
                "name": "Aoife Byrne",
                "email": "aoife@example.com",
                "subject": "Question about the next jam",
                "message": "Hi — what time does the next jam start?",
                "website": "",
            },
        )
        self.assertRedirects(response, self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Question about the next jam", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["staff@jamsessionlab.ie"])
        self.assertEqual(mail.outbox[0].reply_to, ["aoife@example.com"])
        self.assertIn("Aoife Byrne", mail.outbox[0].body)

    def test_honeypot_skips_sending(self):
        response = self.client.post(
            self.url,
            data={
                "name": "Bot",
                "email": "bot@example.com",
                "subject": "Spam",
                "message": "Buy cheap products now please",
                "website": "http://spam.example",
            },
        )
        self.assertRedirects(response, self.url)
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit_blocks_second_send(self):
        data = {
            "name": "Aoife Byrne",
            "email": "aoife@example.com",
            "subject": "First message",
            "message": "This is a valid first contact message.",
            "website": "",
        }
        self.client.post(self.url, data=data)
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            self.url,
            data={**data, "subject": "Second message"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(response, "Please wait a minute")


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
class AboutOrganiserTests(TestCase):
    def setUp(self):
        self._media_root = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media_root)
        self._override.enable()

        from pages.models import AboutOrganiser

        self.organiser = AboutOrganiser.objects.create(
            name="Dario",
            role="Founder",
            bio="Founder bio for tests.",
            initials="D",
            order=0,
            is_active=True,
            photo=SimpleUploadedFile(
                "dario.png",
                MINIMAL_PNG,
                content_type="image/png",
            ),
        )
        AboutOrganiser.objects.filter(pk=self.organiser.pk).update(
            photo="JamSession Lab/site/about_organisers/dario_id"
        )
        self.organiser.refresh_from_db()

    def tearDown(self):
        self._override.disable()

    def test_about_page_shows_active_organisers(self):
        from pages.models import AboutOrganiser

        AboutOrganiser.objects.create(
            name="Hidden",
            role="Staff",
            bio="Should not appear.",
            initials="H",
            order=9,
            is_active=False,
        )
        response = self.client.get(reverse("pages:about"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dario")
        self.assertContains(response, "Founder")
        self.assertContains(response, "Founder bio for tests.")
        self.assertNotContains(response, "Should not appear.")

    def test_edit_role_without_reuploading_photo_is_valid(self):
        from pages.admin import AboutOrganiserAdminForm

        form = AboutOrganiserAdminForm(
            data={
                "name": self.organiser.name,
                "role": "Founder",
                "bio": "Updated bio only.",
                "initials": self.organiser.initials,
                "is_active": True,
                "order": self.organiser.order,
            },
            instance=self.organiser,
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        self.assertEqual(form.cleaned_data["bio"], "Updated bio only.")

    @patch.object(FileSystemStorage, "delete", return_value=None)
    def test_delete_organiser_removes_stored_photo(self, mock_delete):
        photo_name = self.organiser.photo.name

        with self.captureOnCommitCallbacks(execute=True):
            self.organiser.delete()

        mock_delete.assert_called_once_with(photo_name)

    @patch.object(FileSystemStorage, "delete", return_value=None)
    def test_replace_photo_deletes_previous_file(self, mock_delete):
        from pages.models import AboutOrganiser

        old_name = self.organiser.photo.name
        self.organiser.photo = SimpleUploadedFile(
            "dario-new.png",
            MINIMAL_PNG,
            content_type="image/png",
        )
        self.organiser.save()

        mock_delete.assert_called_once_with(old_name)
        refreshed = AboutOrganiser.objects.get(pk=self.organiser.pk)
        self.assertNotEqual(refreshed.photo.name, old_name)

    def test_admin_form_saves_photo_focus(self):
        from pages.admin import AboutOrganiserAdminForm

        form = AboutOrganiserAdminForm(
            data={
                "name": self.organiser.name,
                "role": self.organiser.role,
                "bio": self.organiser.bio,
                "initials": self.organiser.initials,
                "is_active": True,
                "order": self.organiser.order,
                "photo_focus_x": "30",
                "photo_focus_y": "70",
            },
            instance=self.organiser,
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        organiser = form.save()
        self.assertEqual(organiser.photo_focus_x, 30.0)
        self.assertEqual(organiser.photo_focus_y, 70.0)
