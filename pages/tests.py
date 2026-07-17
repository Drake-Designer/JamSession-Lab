import tempfile
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

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
