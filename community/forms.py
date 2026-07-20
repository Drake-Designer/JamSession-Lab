from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from gallery.forms import MultipleGalleryFileField, MultipleGalleryFileInput
from gallery.models import MediaType
from gallery.validators import detect_gallery_media_kind, gallery_file_rejection_reason

from .models import (
    CommunityComment,
    CommunityCommentMedia,
    CommunityPost,
    CommunityPostMedia,
)


def _media_type_for(uploaded_file):
    """Map a validated upload to the shared gallery MediaType."""
    kind = detect_gallery_media_kind(uploaded_file)
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return MediaType.VIDEO if kind == "video" else MediaType.IMAGE


class CommunityMediaMixin:
    """
    Shared optional multi-file attachment handling for posts and comments.

    Reuses the gallery multi-file field and the same "magic bytes" validators,
    so a Community upload is accepted or rejected on exactly the same rules as
    a gallery upload.
    """

    def _clean_media_files(self):
        files = self.cleaned_data.get("files") or []
        for uploaded_file in files:
            reason = gallery_file_rejection_reason(uploaded_file)
            if reason:
                raise ValidationError(
                    _("'%(name)s' could not be uploaded: %(reason)s.")
                    % {"name": uploaded_file.name, "reason": reason}
                )
        return files

    def _save_media(self, media_model, parent_field_name, parent):
        files = self.cleaned_data.get("files") or []
        if not files:
            return

        existing = media_model.objects.filter(
            **{parent_field_name: parent}
        ).count()
        for index, uploaded_file in enumerate(files):
            media_model.objects.create(
                **{parent_field_name: parent},
                file=uploaded_file,
                media_type=_media_type_for(uploaded_file),
                order=existing + index,
            )


class CommunityPostForm(CommunityMediaMixin, forms.ModelForm):
    cover_image = forms.FileField(
        label=_("Cover image (optional)"),
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/*",
                "id": "id_cover_image",
                "data-cover-focus-input": "true",
            }
        ),
        help_text=_(
            "Optional header image shown on the community list and at the top "
            "of your post. Photos only, maximum 100 MB. After choosing a photo, "
            "drag the bright frame to choose exactly what stays visible."
        ),
    )
    cover_focus_x = forms.FloatField(
        required=False,
        min_value=0,
        max_value=100,
        initial=50,
        widget=forms.HiddenInput(attrs={"id": "id_cover_focus_x"}),
    )
    cover_focus_y = forms.FloatField(
        required=False,
        min_value=0,
        max_value=100,
        initial=50,
        widget=forms.HiddenInput(attrs={"id": "id_cover_focus_y"}),
    )
    files = MultipleGalleryFileField(
        label=_("Photos or videos (optional)"),
        required=False,
        widget=MultipleGalleryFileInput(attrs={"accept": "image/*,video/*"}),
        help_text=_(
            "Attach one or more photos and/or videos. Maximum 100 MB each "
            "(and 100 MB total per upload). Phone videos are often larger — "
            "compress them before uploading."
        ),
    )

    class Meta:
        model = CommunityPost
        fields = ["title", "body", "cover_focus_x", "cover_focus_y"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["cover_focus_x"].initial = self.instance.cover_focus_x
            self.fields["cover_focus_y"].initial = self.instance.cover_focus_y

    def clean_cover_image(self):
        cover = self.cleaned_data.get("cover_image")
        if not cover:
            return cover

        reason = gallery_file_rejection_reason(cover)
        if reason:
            raise ValidationError(
                _("'%(name)s' could not be uploaded: %(reason)s.")
                % {"name": cover.name, "reason": reason}
            )

        # Covers are header images — reject videos even though the shared
        # gallery validators accept them for regular attachments.
        if detect_gallery_media_kind(cover) != "image":
            raise ValidationError(
                _("Cover image must be a photo, not a video.")
            )
        return cover

    def clean_cover_focus_x(self):
        value = self.cleaned_data.get("cover_focus_x")
        return 50.0 if value is None else value

    def clean_cover_focus_y(self):
        value = self.cleaned_data.get("cover_focus_y")
        return 50.0 if value is None else value

    def clean_files(self):
        return self._clean_media_files()

    def save(self, commit=True):
        is_edit = self.instance.pk is not None
        post = super().save(commit=False)

        if is_edit:
            # Keep the original author. Non-staff edits go back through
            # moderation so changed text/media is reviewed again; staff/
            # superuser edits leave the current status untouched.
            if self.user and not (self.user.is_staff or self.user.is_superuser):
                post.apply_initial_moderation(self.user)
        elif self.user:
            post.author = self.user
            post.apply_initial_moderation(self.user)

        cover = self.cleaned_data.get("cover_image")
        if cover:
            post.cover_image = cover

        post.cover_focus_x = self.cleaned_data["cover_focus_x"]
        post.cover_focus_y = self.cleaned_data["cover_focus_y"]

        if commit:
            post.save()
            self._save_media(CommunityPostMedia, "post", post)

        return post


class CommunityCommentForm(CommunityMediaMixin, forms.ModelForm):
    files = MultipleGalleryFileField(
        label=_("Photos or videos (optional)"),
        required=False,
        widget=MultipleGalleryFileInput(attrs={"accept": "image/*,video/*"}),
        help_text=_(
            "Attach one or more photos and/or videos. Maximum 100 MB each "
            "(and 100 MB total per upload). Phone videos are often larger — "
            "compress them before uploading."
        ),
    )

    class Meta:
        model = CommunityComment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, post=None, **kwargs):
        self.user = user
        self.post = post
        super().__init__(*args, **kwargs)

    def clean_files(self):
        return self._clean_media_files()

    def save(self, commit=True):
        is_edit = self.instance.pk is not None
        comment = super().save(commit=False)

        if is_edit:
            # Keep the original author and parent post. Non-staff edits
            # re-enter the approval queue; staff/superuser edits keep status.
            if self.user and not (self.user.is_staff or self.user.is_superuser):
                comment.apply_initial_moderation(self.user)
        else:
            comment.post = self.post
            if self.user:
                comment.author = self.user
                comment.apply_initial_moderation(self.user)

        if commit:
            comment.save()
            self._save_media(CommunityCommentMedia, "comment", comment)

        return comment
