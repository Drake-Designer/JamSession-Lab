from django import forms
from django.utils.translation import gettext_lazy as _

TEXT_INPUT_CLASSES = (
    "w-full rounded-xl border border-jam-grey-light bg-jam-black px-4 py-3 "
    "text-sm text-jam-white placeholder:text-jam-muted-dark "
    "focus:border-jam-red focus:outline-none focus:ring-1 focus:ring-jam-red"
)
TEXTAREA_CLASSES = TEXT_INPUT_CLASSES


class ContactForm(forms.Form):
    """Public contact form — emails the JamSession Lab staff inbox."""

    name = forms.CharField(
        label=_("Your name"),
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "autocomplete": "name",
                "placeholder": _("Your name"),
            },
        ),
    )
    email = forms.EmailField(
        label=_("Your email"),
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "autocomplete": "email",
                "placeholder": _("you@example.com"),
            },
        ),
    )
    subject = forms.CharField(
        label=_("Subject"),
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "placeholder": _("What is this about?"),
            },
        ),
    )
    message = forms.CharField(
        label=_("Message"),
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "class": TEXTAREA_CLASSES,
                "rows": 6,
                "placeholder": _("How can we help?"),
            },
        ),
    )
    # Honeypot — leave empty. Bots that fill it are rejected silently in the view.
    website = forms.CharField(
        required=False,
        label=_("Website"),
        widget=forms.TextInput(
            attrs={
                "class": "contact-honeypot",
                "tabindex": "-1",
                "autocomplete": "off",
            },
        ),
    )

    def clean_message(self):
        message = (self.cleaned_data.get("message") or "").strip()
        if len(message) < 10:
            raise forms.ValidationError(
                _("Please write a slightly longer message (at least 10 characters).")
            )
        return message
