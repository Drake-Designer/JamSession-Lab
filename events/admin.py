from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from jamsession.cloudinary_delivery import web_image_url

from .models import Event
from .validators import validate_event_poster_upload


class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = "__all__"

    def clean_poster(self):
        poster = self.cleaned_data.get("poster")
        validate_event_poster_upload(poster)
        return poster


@admin.register(Event)
class EventAdmin(ModelAdmin):
    form = EventAdminForm
    list_display = (
        "venue_name",
        "title",
        "starts_at",
        "display_is_active",
        "display_registrations_open",
    )
    list_filter = ("is_active", "registrations_open")
    search_fields = ("venue_name", "title", "address")
    readonly_fields = ("title", "created_at", "updated_at")
    ordering = ("starts_at",)

    fieldsets = (
        (
            _("Event"),
            {
                "classes": ["tab"],
                "fields": (
                    "venue_name",
                    "title",
                    "address",
                    "location_url",
                    "starts_at",
                    "ends_at",
                    "poster",
                    "description",
                ),
            },
        ),
        (
            _("Visibility & registrations"),
            {
                "classes": ["tab"],
                "fields": ("is_active", "registrations_open"),
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

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active

    @display(
        description=_("Registrations open"),
        boolean=True,
        ordering="registrations_open",
    )
    def display_registrations_open(self, obj):
        return obj.registrations_open

    @display(description=_("Poster"), header=True)
    def poster_thumbnail(self, obj):
        if obj.poster:
            return (
                None,
                None,
                None,
                {
                    "path": web_image_url(obj.poster, width=160, height=80, crop="fill"),
                    "width": 80,
                    "height": 40,
                },
            )
        return (None, None, "—", None)
