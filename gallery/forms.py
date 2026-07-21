from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from events.models import Event

from .models import GalleryItem
from .validators import (
    gallery_file_rejection_reason,
    validate_gallery_file_size,
    validate_gallery_file_type,
)


class GalleryFileValidationMixin:
    def clean_file(self):
        file = self.cleaned_data.get("file")
        validate_gallery_file_size(file)
        validate_gallery_file_type(file)
        return file


class GalleryItemSaveMixin:
    """Shared save logic for public and admin gallery forms."""

    def _save_gallery_item(self, instance, *, commit):
        is_new = instance.pk is None

        if is_new and not instance.uploaded_by_id and self.user:
            instance.uploaded_by = self.user

        if is_new and self.user:
            instance.apply_initial_moderation(self.user)

        if commit:
            instance.save()

        return instance


class MultipleGalleryFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            upload_list = files.getlist(name)
            if upload_list:
                return upload_list
        return files.get(name)


class MultipleGalleryFileField(forms.FileField):
    widget = MultipleGalleryFileInput

    def clean(self, data, initial=None):
        if data in self.empty_values:
            if self.required:
                raise ValidationError(
                    self.error_messages["required"],
                    code="required",
                )
            return []

        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned_files = []
        for uploaded_file in data:
            if uploaded_file in self.empty_values:
                continue
            cleaned_files.append(
                forms.FileField.clean(self, uploaded_file, initial)
            )

        if self.required and not cleaned_files:
            raise ValidationError(
                self.error_messages["required"],
                code="required",
            )

        return cleaned_files


class GalleryBatchUploadForm(forms.Form):
    """Upload one or more gallery files in a single submission."""

    files = MultipleGalleryFileField(
        label=_("Photos or videos"),
        widget=MultipleGalleryFileInput(
            attrs={"accept": "image/*,video/*"},
        ),
        help_text=_(
            "Select one or more photos and/or videos. Each file becomes a separate "
            "gallery item. Maximum 100 MB per file (and 100 MB total per upload). "
            "Phone videos are often larger — compress them (or lower the camera "
            "quality) before uploading."
        ),
    )
    event = forms.ModelChoiceField(
        label=_("Related event (optional)"),
        queryset=Event.objects.none(),
        required=False,
        empty_label=_("No specific event"),
        help_text=_("Link these uploads to a jam night when possible."),
    )
    title = forms.CharField(
        label=_("Title (optional)"),
        max_length=120,
        required=False,
    )
    caption = forms.CharField(
        label=_("Caption (optional)"),
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = Event.objects.filter(
            is_active=True
        ).order_by("-starts_at")
        self.fields["event"].label_from_instance = str

    def clean_files(self):
        files = self.cleaned_data.get("files") or []
        if not files:
            raise ValidationError(_("Please select at least one photo or video."))
        return files

    def process_uploads(self):
        """
        Validate and save each uploaded file independently.

        Returns (success_count, failures) where failures is a list of
        (filename, reason) tuples for files that could not be saved.
        """
        if not self.is_valid():
            raise ValueError("Form must be valid before processing uploads.")

        title = self.cleaned_data.get("title", "")
        caption = self.cleaned_data.get("caption", "")
        event = self.cleaned_data.get("event")
        files = self.cleaned_data["files"]

        success_count = 0
        failures = []

        for uploaded_file in files:
            rejection_reason = gallery_file_rejection_reason(uploaded_file)
            if rejection_reason:
                failures.append((uploaded_file.name, rejection_reason))
                continue

            try:
                item = GalleryItem(
                    uploaded_by=self.user,
                    file=uploaded_file,
                    title=title,
                    caption=caption,
                    event=event,
                )
                item.apply_initial_moderation(self.user)
                item.save()
                success_count += 1
            except Exception:
                failures.append(
                    (uploaded_file.name, "upload failed: please try again")
                )

        return success_count, failures


class GalleryItemAdminForm(
    GalleryFileValidationMixin, GalleryItemSaveMixin, forms.ModelForm
):
    class Meta:
        model = GalleryItem
        fields = "__all__"
        widgets = {
            "pin_order": forms.TextInput(
                attrs={
                    "inputmode": "numeric",
                    "pattern": "[0-9]*",
                    "maxlength": "3",
                    "autocomplete": "off",
                    "class": "gallery-admin-pin-order",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_pin_order(self):
        pin_order = self.cleaned_data.get("pin_order")
        if pin_order in (None, ""):
            return None
        try:
            pin_order = int(pin_order)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                _("Pin order must contain digits only (1–999).")
            ) from exc
        if pin_order == 0:
            return None
        self.instance.pin_order = pin_order
        try:
            self.instance.validate_unique_pin_order()
        except ValidationError as exc:
            if hasattr(exc, "error_dict") and "pin_order" in exc.error_dict:
                raise ValidationError(exc.error_dict["pin_order"]) from exc
            raise
        return pin_order

    def save(self, commit=True):
        instance = super().save(commit=False)
        return self._save_gallery_item(instance, commit=commit)
