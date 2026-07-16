from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.files.uploadedfile import UploadedFile
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from jamsession.image_formats import convert_heic_upload_to_jpeg

from .constants import County, Instrument, MusicGenre, TOWNS_BY_COUNTY
from .models import User
from .validators import validate_minimum_age, validate_profile_picture
from .widgets import ProfilePictureInput

# Shared Tailwind classes so every input matches the brand-dark style.
TEXT_INPUT_CLASSES = (
    "w-full rounded-xl border border-jam-grey-light bg-jam-black px-4 py-3 "
    "text-sm text-jam-white placeholder:text-jam-muted-dark "
    "focus:border-jam-red focus:outline-none focus:ring-1 focus:ring-jam-red"
)
SELECT_CLASSES = TEXT_INPUT_CLASSES


def generate_unique_username(display_name):
    """
    Build an internal username from the public display name.

    Django usernames cannot contain spaces, so "Jam Fan 99" becomes
    "jam_fan_99". A numeric suffix is added if the name is already taken.
    """
    base = slugify(display_name).replace("-", "_")[:100] or "member"
    username = base
    counter = 2
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


class RegistrationForm(UserCreationForm):
    """Public sign-up form with the full musician profile required fields."""

    date_of_birth = forms.DateField(
        label=_("Date of birth"),
        required=True,
        validators=[validate_minimum_age],
        widget=forms.DateInput(
            attrs={"type": "date", "class": TEXT_INPUT_CLASSES},
        ),
        help_text=_("You must be at least 18 years old to register."),
    )
    county = forms.ChoiceField(
        label=_("County"),
        required=True,
        choices=[("", _("Select your county"))] + list(County.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )
    town_city = forms.CharField(
        label=_("Town / City"),
        required=True,
        max_length=60,
        # Rendered as a <select> whose options are filled by register.js
        # based on the chosen county; validated server-side in clean().
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )
    instruments = forms.MultipleChoiceField(
        label=_("Instruments played"),
        required=True,
        choices=Instrument.choices,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": _("Please select at least one instrument."),
        },
    )
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={
            "required": _("You must accept the Terms of Service to register."),
        },
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "display_name",
            "email",
            "phone_number",
            "date_of_birth",
            "county",
            "town_city",
            "instruments",
            "other_instrument",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "last_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "display_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "email": forms.EmailInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "phone_number": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "placeholder": "+353 87 123 4567",
                },
            ),
            "other_instrument": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "maxlength": "15",
                },
            ),
        }
        labels = {
            "display_name": _("Nickname / Display name"),
            "phone_number": _("Phone number"),
            "other_instrument": _("Other instrument"),
        }
        help_texts = {
            "phone_number": _(
                "We use your phone number to send you an automatic invitation "
                "to the JamSession Lab community WhatsApp group."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["phone_number"].required = True
        self.fields["other_instrument"].required = False

        self.fields["accept_terms"].label = format_html(
            'I have read and accept the <a href="{}" target="_blank" '
            'class="text-jam-red underline hover:text-jam-red-hover">'
            "Terms of Service</a>.",
            reverse("pages:terms"),
        )

        for password_field in ("password1", "password2"):
            self.fields[password_field].widget.attrs.update(
                {
                    "class": TEXT_INPUT_CLASSES,
                    # "new-password" keeps password managers working and never
                    # blocks manual paste (unlike "off" in some browsers).
                    "autocomplete": "new-password",
                }
            )

        # Short, friendly summary instead of Django's default four-line list.
        # AUTH_PASSWORD_VALIDATORS still enforce the full strong policy.
        self.fields["password1"].help_text = _(
            "Must be at least 8 characters and not too common."
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("An account with this email address already exists.")
            )
        return email

    def clean_display_name(self):
        display_name = (self.cleaned_data.get("display_name") or "").strip()
        if display_name and User.objects.filter(
            display_name__iexact=display_name
        ).exists():
            raise forms.ValidationError(
                _("This display name is already taken. Please choose another.")
            )
        return display_name

    def clean(self):
        cleaned_data = super().clean()

        instruments = cleaned_data.get("instruments") or []
        other_instrument = (cleaned_data.get("other_instrument") or "").strip()
        if Instrument.OTHER in instruments and not other_instrument:
            self.add_error(
                "other_instrument",
                _("Please specify your instrument."),
            )
        if Instrument.OTHER not in instruments:
            cleaned_data["other_instrument"] = ""

        county = cleaned_data.get("county")
        town_city = cleaned_data.get("town_city")
        if county and town_city:
            valid_towns = TOWNS_BY_COUNTY.get(county, [])
            if town_city not in valid_towns:
                self.add_error(
                    "town_city",
                    _("Please choose a town or city in the selected county."),
                )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = generate_unique_username(user.display_name)
        user.terms_accepted_at = timezone.now()
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Sign-in form that accepts either the email address or the display name."""

    error_messages = {
        "invalid_login": _(
            "Your email/display name or password is incorrect. "
            "Please check them and try again."
        ),
        "inactive": _("This account is inactive."),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)

        self.fields["username"].label = _("Email or Display Name")
        self.fields["username"].widget.attrs.update(
            {"class": TEXT_INPUT_CLASSES, "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": TEXT_INPUT_CLASSES, "autocomplete": "current-password"}
        )

    def clean_username(self):
        """
        Resolve the public identifier to the internal Django username.

        Users sign in with their email address or display name — never with
        the internal slugified username, which they don't know.
        """
        identifier = (self.cleaned_data.get("username") or "").strip()

        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).first()
        else:
            match = User.objects.filter(display_name__iexact=identifier).first()

        if match is not None:
            return match.username

        # No account matches: authenticate() will fail and the generic
        # invalid_login error is shown, exactly as for a wrong password.
        return ""


class ProfileEditForm(forms.ModelForm):
    """
    Profile fields the owner can edit.

    Email, password, and date of birth are intentionally excluded — they will
    live in a separate "Account Settings" section.
    """

    county = forms.ChoiceField(
        label=_("County"),
        required=True,
        choices=[("", _("Select your county"))] + list(County.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )
    town_city = forms.CharField(
        label=_("Town / City"),
        required=True,
        max_length=60,
        # Options are filled by register.js based on the chosen county.
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )
    instruments = forms.MultipleChoiceField(
        label=_("Instruments played"),
        required=True,
        choices=Instrument.choices,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": _("Please select at least one instrument."),
        },
    )
    preferred_genres = forms.MultipleChoiceField(
        label=_("Preferred music genres"),
        required=False,
        choices=MusicGenre.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = (
            "profile_picture",
            "display_name",
            "bio",
            "preferred_genres",
            "instruments",
            "other_instrument",
            "phone_number",
            "county",
            "town_city",
        )
        widgets = {
            "profile_picture": ProfilePictureInput(
                attrs={"accept": "image/*,.heic,.heif"},
            ),
            "display_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "bio": forms.Textarea(attrs={"class": TEXT_INPUT_CLASSES, "rows": 5}),
            "other_instrument": forms.TextInput(
                attrs={"class": TEXT_INPUT_CLASSES, "maxlength": "15"},
            ),
            "phone_number": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
        }
        labels = {
            "display_name": _("Nickname / Display name"),
            "other_instrument": _("Other instrument"),
            "phone_number": _("Phone number"),
        }
        help_texts = {
            "phone_number": _(
                "Only visible to you. Used for the community WhatsApp group "
                "invitation."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].required = True
        self.fields["other_instrument"].required = False

    def clean_display_name(self):
        display_name = (self.cleaned_data.get("display_name") or "").strip()
        conflict = (
            User.objects.filter(display_name__iexact=display_name)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if display_name and conflict:
            raise forms.ValidationError(
                _("This display name is already taken. Please choose another.")
            )
        return display_name

    def clean_profile_picture(self):
        picture = self.cleaned_data.get("profile_picture")
        if not isinstance(picture, UploadedFile):
            return picture

        # HEIC/HEIF from iPhones often fails Cloudinary's image endpoint and
        # cannot be shown natively in most browsers — convert to JPEG first.
        picture = convert_heic_upload_to_jpeg(
            picture,
            field_name="profile_picture",
        )
        validate_profile_picture(picture)
        return picture

    def clean(self):
        cleaned_data = super().clean()

        instruments = cleaned_data.get("instruments") or []
        other_instrument = (cleaned_data.get("other_instrument") or "").strip()
        if Instrument.OTHER in instruments and not other_instrument:
            self.add_error(
                "other_instrument",
                _("Please specify your instrument."),
            )
        if Instrument.OTHER not in instruments:
            cleaned_data["other_instrument"] = ""

        county = cleaned_data.get("county")
        town_city = cleaned_data.get("town_city")
        if county and town_city:
            valid_towns = TOWNS_BY_COUNTY.get(county, [])
            if town_city not in valid_towns:
                self.add_error(
                    "town_city",
                    _("Please choose a town or city in the selected county."),
                )

        return cleaned_data


class DeleteAccountForm(forms.Form):
    """Explicit confirmation before permanently deleting an account."""

    confirm = forms.BooleanField(
        label=_("I understand this action is permanent"),
        error_messages={
            "required": _(
                "Please tick the confirmation box to delete your account."
            ),
        },
    )
    password = forms.CharField(
        label=_("Current password"),
        widget=forms.PasswordInput(attrs={"class": TEXT_INPUT_CLASSES}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        if not self.user.check_password(password):
            raise forms.ValidationError(
                _("Your password was incorrect. Your account has not been deleted.")
            )
        return password
