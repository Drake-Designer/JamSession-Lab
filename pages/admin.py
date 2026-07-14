from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from jamsession.admin_mixins import UnfoldSortableAdminMixin

from .models import HomeCarouselSlide


@admin.register(HomeCarouselSlide)
class HomeCarouselSlideAdmin(UnfoldSortableAdminMixin, ModelAdmin):
    list_display = (
        "_reorder_",
        "image_thumbnail",
        "alt_text",
        "display_slide_type",
        "display_is_active",
        "updated_at",
    )
    list_filter = ("slide_type", "is_active")
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
                    "slide_type",
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
                    "path": obj.image.url,
                    "width": 80,
                    "height": 40,
                },
            )
        return (None, None, "—", None)

    @display(description=_("Type"), ordering="slide_type")
    def display_slide_type(self, obj):
        return obj.get_slide_type_display()

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active
