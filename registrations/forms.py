from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils.translation import gettext_lazy as _

from .models import EventRegistration

INPUT_CLASSES = (
    "w-full rounded-xl border border-jam-grey-light bg-jam-black px-4 py-3 "
    "text-sm text-jam-white placeholder:text-jam-muted-dark "
    "focus:border-jam-red focus:outline-none focus:ring-1 focus:ring-jam-red"
)
CHECKBOX_CLASSES = "h-4 w-4 rounded border-jam-grey-light text-jam-red focus:ring-jam-red"
TEXTAREA_CLASSES = INPUT_CLASSES

YES_NO_CHOICES = (
    ("yes", _("Yes")),
    ("no", _("No")),
)


class EventRegistrationForm(forms.ModelForm):
    """Member RSVP form with server-side session and song rules."""

    # Separate name from the model BooleanField to avoid widget/type clashes.
    originals_choice = forms.ChoiceField(
        label=_(
            "Do you have any original songs you want to play with other musicians "
            "during the Jam Session?"
        ),
        choices=YES_NO_CHOICES,
        widget=forms.RadioSelect,
        required=False,
    )

    class Meta:
        model = EventRegistration
        fields = (
            "join_open_mic",
            "join_open_jam",
            "notes",
        )
        widgets = {
            "join_open_mic": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "join_open_jam": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "notes": forms.Textarea(
                attrs={
                    "class": TEXTAREA_CLASSES,
                    "rows": 4,
                    "placeholder": _(
                        "Feel free to share any suggestions, special requests, "
                        "or anything else you would like us to know."
                    ),
                }
            ),
        }
        labels = {
            "join_open_mic": _(
                "Open Mic (Solo, Duo, or Trio performing original songs only) — "
                "This session is dedicated exclusively to original music and is "
                "designed for artists who want to showcase their own material"
            ),
            "join_open_jam": _(
                "Open Jam Session (Covers, free improvisation, or playing songs "
                "by artists performing during the Open Mic) — This session is "
                "about playing with different people, learning to adapt, "
                "collaborating on the spot, and developing improvisation skills "
                "in a supportive environment"
            ),
            "notes": _("Notes (optional)"),
        }

    def __init__(self, *args, event=None, user=None, song_formset=None, **kwargs):
        self.event = event
        self.user = user
        self.song_formset = song_formset
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
        instance = kwargs.get("instance") or getattr(self, "instance", None)
        if instance and instance.pk and instance.wants_originals_in_jam is not None:
            self.fields["originals_choice"].initial = (
                "yes" if instance.wants_originals_in_jam else "no"
            )

    def _count_valid_songs(self):
        if self.song_formset is None:
            return 0
        if self.song_formset.is_bound:
            self.song_formset.is_valid()
        valid_songs = 0
        for form in self.song_formset.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            title = (form.cleaned_data.get("title") or "").strip()
            song_key = (form.cleaned_data.get("song_key") or "").strip()
            chords = (form.cleaned_data.get("basic_chords") or "").strip()
            if title and song_key and chords:
                valid_songs += 1
        return valid_songs

    def clean(self):
        cleaned = super().clean()
        join_open_mic = cleaned.get("join_open_mic")
        join_open_jam = cleaned.get("join_open_jam")
        originals_choice = cleaned.get("originals_choice")

        if not join_open_mic and not join_open_jam:
            raise forms.ValidationError(
                _("Please select at least one session (Open Mic and/or Open Jam).")
            )

        if not join_open_jam:
            cleaned["wants_originals_in_jam"] = None
            # Apply to instance so ModelForm._post_clean / model.clean() see it.
            self.instance.wants_originals_in_jam = None
            return cleaned

        if originals_choice not in ("yes", "no"):
            self.add_error(
                "originals_choice",
                _("Please say whether you have original songs for the jam."),
            )
            return cleaned

        wants_bool = originals_choice == "yes"
        cleaned["wants_originals_in_jam"] = wants_bool
        self.instance.wants_originals_in_jam = wants_bool

        if wants_bool and self._count_valid_songs() < 1:
            raise forms.ValidationError(
                _(
                    "Please add at least one original song (title, key, and "
                    "basic chords) for the jam session."
                )
            )

        return cleaned


class RegistrationSongForm(forms.Form):
    """Standalone song row (not an inline ModelForm — avoids FK issues on create)."""

    title = forms.CharField(
        label=_("Song title"),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES}),
    )
    song_key = forms.CharField(
        label=_("Key"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASSES}),
    )
    basic_chords = forms.CharField(
        label=_("Basic chords"),
        required=False,
        widget=forms.Textarea(attrs={"class": TEXTAREA_CLASSES, "rows": 3}),
    )


class BaseRegistrationSongFormSet(BaseFormSet):
    def clean(self):
        super().clean()


RegistrationSongFormSet = formset_factory(
    RegistrationSongForm,
    formset=BaseRegistrationSongFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


def song_formset_initial_from_registration(registration):
    """Build initial data for the song formset from an existing registration."""
    if registration is None or not registration.pk:
        return None
    return [
        {
            "title": song.title,
            "song_key": song.song_key,
            "basic_chords": song.basic_chords,
        }
        for song in registration.songs.all()
    ]
