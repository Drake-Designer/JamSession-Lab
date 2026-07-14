from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ApprovalStatus, GalleryItem


class GalleryUploadForm(forms.ModelForm):
    class Meta:
        model = GalleryItem
        fields = ("file", "title", "caption")
        labels = {
            "file": _("Photo or video"),
            "title": _("Title (optional)"),
            "caption": _("Caption (optional)"),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.uploaded_by = self.user
        instance.status = ApprovalStatus.PENDING
        if commit:
            instance.save()
        return instance
