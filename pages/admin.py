from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from jamsession.admin_mixins import UnfoldSortableAdminMixin
from jamsession.cloudinary_delivery import web_image_url

from .models import HomeCarouselSlide
from .validators import validate_carousel_image_upload


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
        return (None, None, "—", None)

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active
