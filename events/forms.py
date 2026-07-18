from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Event
from .validators import validate_event_poster_upload

INPUT_CLASSES = (
    "w-full rounded-xl border border-jam-grey-light bg-jam-black px-4 py-3 "
    "text-jam-white placeholder:text-jam-muted focus:border-jam-red "
    "focus:outline-none focus:ring-1 focus:ring-jam-red"
)
TEXTAREA_CLASSES = INPUT_CLASSES
CHECKBOX_CLASSES = "h-4 w-4 rounded border-jam-grey-light text-jam-red focus:ring-jam-red"


class EventForm(forms.ModelForm):
    """Staff create/edit form. Title is generated from venue_name on save."""

    class Meta:
        model = Event
        fields = (
            "venue_name",
            "address",
            "location_url",
            "starts_at",
            "ends_at",
            "poster",
            "description",
            "is_active",
            "registrations_open",
        )
        widgets = {
            "venue_name": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "address": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "location_url": forms.URLInput(attrs={"class": INPUT_CLASSES}),
            "starts_at": forms.DateTimeInput(
                attrs={"class": INPUT_CLASSES, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"class": INPUT_CLASSES, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "description": forms.Textarea(attrs={"class": TEXTAREA_CLASSES, "rows": 5}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "registrations_open": forms.CheckboxInput(
                attrs={"class": CHECKBOX_CLASSES}
            ),
        }
        labels = {
            "venue_name": _("Venue name"),
            "address": _("Address"),
            "location_url": _("Google Maps link"),
            "starts_at": _("Starts at"),
            "ends_at": _("Ends at"),
            "poster": _("Event poster"),
            "description": _("Description"),
            "is_active": _("Active (visible on the site)"),
            "registrations_open": _("Registrations open"),
        }
        help_texts = {
            "venue_name": _(
                "The event title will be generated as “JamSession @ {venue name}”."
            ),
            "location_url": _("Paste the Google Maps URL for the venue."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        self.fields["ends_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        self.fields["poster"].required = False
        self.fields["description"].required = False

    def clean_poster(self):
        poster = self.cleaned_data.get("poster")
        validate_event_poster_upload(poster)
        return poster
