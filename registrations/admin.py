from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from .models import EventRegistration, RegistrationSong


class RegistrationSongInline(TabularInline):
    model = RegistrationSong
    extra = 0
    fields = ("title", "song_key", "basic_chords")


@admin.register(EventRegistration)
class EventRegistrationAdmin(ModelAdmin):
    list_display = (
        "user",
        "event",
        "rsvp_status",
        "attendance_status",
        "registered_at",
    )
    list_filter = ("rsvp_status", "attendance_status", "join_open_mic", "join_open_jam")
    search_fields = (
        "user__display_name",
        "user__email",
        "user__username",
        "event__venue_name",
        "event__title",
    )
    readonly_fields = (
        "instruments_snapshot",
        "experience_level_snapshot",
        "registered_at",
        "first_registered_at",
        "cancelled_at",
    )
    inlines = [RegistrationSongInline]
    autocomplete_fields = ("user", "event")

    fieldsets = (
        (
            _("Registration"),
            {
                "classes": ["tab"],
                "fields": (
                    "user",
                    "event",
                    "rsvp_status",
                    "attendance_status",
                    "join_open_mic",
                    "join_open_jam",
                    "wants_originals_in_jam",
                    "notes",
                ),
            },
        ),
        (
            _("Profile snapshot"),
            {
                "classes": ["tab"],
                "fields": ("instruments_snapshot", "experience_level_snapshot"),
            },
        ),
        (
            _("Timestamps"),
            {
                "classes": ["tab", "collapse"],
                "fields": (
                    "registered_at",
                    "first_registered_at",
                    "cancelled_at",
                ),
            },
        ),
    )
