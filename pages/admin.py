from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from jamsession.admin_mixins import UnfoldSortableAdminMixin
from jamsession.cloudinary_delivery import web_image_url

from .models import AboutOrganiser, HomeCarouselSlide
from .validators import (
    validate_carousel_image_upload,
    validate_organiser_photo_upload,
)


class HomeCarouselSlideAdminForm(forms.ModelForm):
    class Meta:
        model = HomeCarouselSlide
        fields = "__all__"

    def clean_image(self):
        image = self.cleaned_data.get("image")
        validate_carousel_image_upload(image)
        return image


@admin.register(HomeCarouselSlide)
class HomeCarouselSlideAdmin(UnfoldSortableAdminMixin, ModelAdmin):
    form = HomeCarouselSlideAdminForm
    list_display = (
        "_reorder_",
        "image_thumbnail",
        "alt_text",
        "display_is_active",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("alt_text", "caption")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            _("Slide"),
            {
                "classes": ["tab"],
                "fields": (
                    "image",
                    "alt_text",
                    "caption",
                    "is_active",
                ),
            },
        ),
        (
            _("Timestamps"),
            {
                "classes": ["tab", "collapse"],
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @display(description=_("Preview"), header=True)
    def image_thumbnail(self, obj):
        if obj.image:
            return (
                None,
                None,
                None,
                {
                    "path": web_image_url(obj.image, width=160, height=80, crop="fill"),
                    "width": 80,
                    "height": 40,
                },
            )
        return (None, None, "-", None)

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active


class AboutOrganiserAdminForm(forms.ModelForm):
    class Meta:
        model = AboutOrganiser
        fields = "__all__"
        widgets = {
            "photo_focus_x": forms.HiddenInput(attrs={"id": "id_photo_focus_x"}),
            "photo_focus_y": forms.HiddenInput(attrs={"id": "id_photo_focus_y"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hidden focus fields are always present in the admin UI via JS;
        # allow omit on text-only edits.
        self.fields["photo_focus_x"].required = False
        self.fields["photo_focus_y"].required = False

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        validate_organiser_photo_upload(photo)
        return photo

    def clean_photo_focus_x(self):
        value = self.cleaned_data.get("photo_focus_x")
        if value is None:
            return 50.0
        return max(0.0, min(100.0, float(value)))

    def clean_photo_focus_y(self):
        value = self.cleaned_data.get("photo_focus_y")
        if value is None:
            return 50.0
        return max(0.0, min(100.0, float(value)))


@admin.register(AboutOrganiser)
class AboutOrganiserAdmin(UnfoldSortableAdminMixin, ModelAdmin):
    form = AboutOrganiserAdminForm
    list_display = (
        "_reorder_",
        "photo_thumbnail",
        "name",
        "role",
        "display_is_active",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "role", "bio")
    readonly_fields = ("photo_crop_editor", "created_at", "updated_at")

    fieldsets = (
        (
            _("Organiser"),
            {
                "classes": ["tab"],
                "fields": (
                    "name",
                    "role",
                    "bio",
                    "initials",
                    "photo",
                    "photo_crop_editor",
                    "photo_focus_x",
                    "photo_focus_y",
                    "is_active",
                ),
            },
        ),
        (
            _("Timestamps"),
            {
                "classes": ["tab", "collapse"],
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    class Media:
        css = {"all": ("pages/css/organiser-photo-focus.css",)}
        js = ("community/js/cover-focus.js",)

    @admin.display(description=_("Photo crop"))
    def photo_crop_editor(self, obj):
        existing_url = ""
        if obj and obj.pk and obj.photo:
            existing_url = obj.display_photo_url

        # Start visible when a photo already exists; JS shows it on new upload.
        hidden_attr = "" if existing_url else " hidden"

        return format_html(
            """
            <div
                id="cover-focus-picker"
                class="cover-focus"
                data-cover-ratio="1"
                data-focus-x-id="id_photo_focus_x"
                data-focus-y-id="id_photo_focus_y"
                data-file-input="#id_photo"
                data-existing-cover-url="{existing}"
                {hidden}
            >
                <p class="cover-focus__hint">
                    Drag the circle to choose which part of the photo appears
                    on the About page. The dimmed area is cropped away.
                </p>
                <div id="cover-focus-workspace" class="cover-focus__workspace">
                    <img id="cover-focus-preview" class="cover-focus__image" alt="Full organiser photo" draggable="false">
                    <div
                        id="cover-focus-crop"
                        class="cover-focus__crop"
                        role="slider"
                        tabindex="0"
                        aria-label="Visible area of the photo"
                    >
                        <span class="cover-focus__crop-label">Visible area</span>
                    </div>
                </div>
                <div class="cover-focus__legend" aria-hidden="true">
                    <span class="cover-focus__legend-item cover-focus__legend-item--kept">Visible</span>
                    <span class="cover-focus__legend-item cover-focus__legend-item--cut">Cropped</span>
                </div>
                <div class="cover-focus__result">
                    <p class="cover-focus__result-label">How it will look on the site</p>
                    <div class="cover-focus__result-frame cover-focus__result-frame--circle">
                        <img id="cover-focus-result-image" class="cover-focus__result-image" alt="Organiser photo preview" draggable="false">
                    </div>
                </div>
            </div>
            """,
            existing=existing_url,
            hidden=hidden_attr,
        )

    @display(description=_("Photo"), header=True)
    def photo_thumbnail(self, obj):
        if obj.photo:
            return (
                None,
                None,
                None,
                {
                    "path": web_image_url(obj.photo, width=80, height=80, crop="fill"),
                    "width": 40,
                    "height": 40,
                },
            )
        return (None, None, obj.initials or "-", None)

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active
