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
