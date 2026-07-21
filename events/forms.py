from datetime import datetime, timedelta

from django import forms
from django.utils import timezone
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
    """
    Staff create/edit form.

    Events are single-evening jams: one date plus start/end times. These are
    combined into starts_at / ends_at on the model. If the end time is at or
    before the start time (e.g. 19:00 → 00:00), the end is stored on the
    following calendar day.
    """

    event_date = forms.DateField(
        label=_("Date"),
        widget=forms.DateInput(
            attrs={"class": INPUT_CLASSES, "type": "date"},
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d"],
    )
    start_time = forms.TimeField(
        label=_("Starts"),
        widget=forms.TimeInput(
            attrs={"class": INPUT_CLASSES, "type": "time"},
            format="%H:%M",
        ),
        input_formats=["%H:%M", "%H:%M:%S"],
    )
    end_time = forms.TimeField(
        label=_("Ends"),
        widget=forms.TimeInput(
            attrs={"class": INPUT_CLASSES, "type": "time"},
            format="%H:%M",
        ),
        input_formats=["%H:%M", "%H:%M:%S"],
        help_text=_(
            "Same evening, or after midnight (e.g. 00:00) if the jam runs past midnight."
        ),
    )

    class Meta:
        model = Event
        fields = (
            "venue_name",
            "address",
            "location_url",
            "poster",
            "description",
            "capacity",
            "is_active",
            "registrations_open",
        )
        widgets = {
            "venue_name": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "address": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "location_url": forms.URLInput(attrs={"class": INPUT_CLASSES}),
            "description": forms.Textarea(attrs={"class": TEXTAREA_CLASSES, "rows": 5}),
            "capacity": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "min": "1", "placeholder": ""}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "registrations_open": forms.CheckboxInput(
                attrs={"class": CHECKBOX_CLASSES}
            ),
        }
        labels = {
            "venue_name": _("Venue name"),
            "address": _("Address"),
            "location_url": _("Google Maps link"),
            "poster": _("Event poster"),
            "description": _("Description"),
            "capacity": _("Capacity"),
            "is_active": _("Active (visible on the site)"),
            "registrations_open": _("Registrations open"),
        }
        help_texts = {
            "venue_name": _(
                "The event title will be generated as “JamSession @ {venue name}”."
            ),
            "location_url": _("Paste the Google Maps URL for the venue."),
            "capacity": _(
                "Optional. Maximum number of active registrations. "
                "Leave blank for no limit."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["poster"].required = False
        self.fields["description"].required = False
        self.fields["capacity"].required = False

        instance = self.instance
        if instance and instance.pk and instance.starts_at and instance.ends_at:
            local_start = timezone.localtime(instance.starts_at)
            local_end = timezone.localtime(instance.ends_at)
            self.fields["event_date"].initial = local_start.date()
            self.fields["start_time"].initial = local_start.time().replace(
                second=0, microsecond=0
            )
            self.fields["end_time"].initial = local_end.time().replace(
                second=0, microsecond=0
            )

    def clean_poster(self):
        poster = self.cleaned_data.get("poster")
        validate_event_poster_upload(poster)
        return poster

    def clean_capacity(self):
        capacity = self.cleaned_data.get("capacity")
        if capacity is not None and capacity < 1:
            raise forms.ValidationError(
                _("Capacity must be at least 1, or left blank.")
            )
        return capacity

    def clean(self):
        cleaned_data = super().clean()
        event_date = cleaned_data.get("event_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if not (event_date and start_time and end_time):
            return cleaned_data

        tz = timezone.get_current_timezone()
        starts_at = timezone.make_aware(
            datetime.combine(event_date, start_time),
            tz,
        )
        ends_at = timezone.make_aware(
            datetime.combine(event_date, end_time),
            tz,
        )
        # End at or before start → after midnight on the next calendar day
        # (e.g. 19:00 → 00:00).
        if ends_at <= starts_at:
            ends_at = ends_at + timedelta(days=1)

        cleaned_data["starts_at"] = starts_at
        cleaned_data["ends_at"] = ends_at
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.starts_at = self.cleaned_data["starts_at"]
        instance.ends_at = self.cleaned_data["ends_at"]
        if commit:
            instance.save()
        return instance
