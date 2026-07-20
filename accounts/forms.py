from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from jamsession.image_formats import convert_heic_upload_to_jpeg

from .constants import (
    OTHER_GENRE_MAX_LENGTH,
    OTHER_INSTRUMENT_MAX_LENGTH,
    County,
    ExperienceLevel,
    Instrument,
    MusicGenre,
    TOWNS_BY_COUNTY,
)
from .models import SocialLink, User
from .phone import (
    COUNTRY_CALLING_CODES,
    DEFAULT_PHONE_COUNTRY_CODE,
    split_phone_number,
    validate_combined_phone,
)
from .social_platforms import MAX_SOCIAL_LINKS
from .validators import (
    MAX_YEARS_OF_EXPERIENCE,
    validate_minimum_age,
    validate_profile_picture,
    validate_years_of_experience_against_age,
)
from .widgets import ProfilePictureInput

# Shared Tailwind classes so every input matches the brand-dark style.
TEXT_INPUT_CLASSES = (
    "w-full rounded-xl border border-jam-grey-light bg-jam-black px-4 py-3 "
    "text-sm text-jam-white placeholder:text-jam-muted-dark "
    "focus:border-jam-red focus:outline-none focus:ring-1 focus:ring-jam-red"
)
# Display Name / Phone use fixed ch widths (no w-full) — see forms.css.
SIZED_INPUT_CLASSES = (
    "rounded-xl border border-jam-grey-light bg-jam-black px-4 py-3 "
    "text-sm text-jam-white placeholder:text-jam-muted-dark "
    "focus:border-jam-red focus:outline-none focus:ring-1 focus:ring-jam-red"
)
SELECT_CLASSES = TEXT_INPUT_CLASSES

YEARS_OF_EXPERIENCE_HELP_TEXT = _(
    "How many years you have been playing (0–%(max)s). "
    "This increases automatically by one year every 1 January."
) % {"max": MAX_YEARS_OF_EXPERIENCE}


def years_of_experience_form_field(*, required=True):
    """Shared integer field shown on registration and profile edit."""
    return forms.IntegerField(
        label=_("Years of experience"),
        required=required,
        min_value=0,
        max_value=MAX_YEARS_OF_EXPERIENCE,
        help_text=YEARS_OF_EXPERIENCE_HELP_TEXT,
        widget=forms.NumberInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "min": "0",
                "max": str(MAX_YEARS_OF_EXPERIENCE),
                "inputmode": "numeric",
            },
        ),
    )


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


PHONE_COUNTRY_SELECT_CLASSES = (
    "jam-input--phone-country rounded-xl border border-jam-grey-light "
    "bg-jam-black px-3 py-3 text-sm text-jam-white "
    "focus:border-jam-red focus:outline-none focus:ring-1 focus:ring-jam-red"
)
PHONE_NATIONAL_INPUT_CLASSES = (
    f"{SIZED_INPUT_CLASSES} jam-input--phone-number"
)


class PhoneNumberFieldsMixin:
    """
    Split phone UI: country calling code (left) + national number (right).

    The combined E.164 value is stored on User.phone_number. Fields are added
    in ``__init__`` (not as class attributes) so they work with ModelForm's
    metaclass field collection.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_country_code"] = forms.ChoiceField(
            label=_("Country code"),
            choices=COUNTRY_CALLING_CODES,
            initial=DEFAULT_PHONE_COUNTRY_CODE,
            widget=forms.Select(attrs={"class": PHONE_COUNTRY_SELECT_CLASSES}),
        )
        self.fields["phone_national_number"] = forms.CharField(
            label=_("Phone number"),
            required=True,
            max_length=12,
            widget=forms.TextInput(
                attrs={
                    "class": PHONE_NATIONAL_INPUT_CLASSES,
                    "maxlength": "12",
                    "placeholder": "87 123 4567",
                    "inputmode": "tel",
                    "autocomplete": "tel-national",
                },
            ),
        )
        self._init_phone_fields()

    def _init_phone_fields(self):
        """Populate split fields from an existing User.phone_number when editing."""
        instance = getattr(self, "instance", None)
        if instance is not None and getattr(instance, "pk", None):
            country, national = split_phone_number(instance.phone_number or "")
            self.fields["phone_country_code"].initial = country
            self.fields["phone_national_number"].initial = national
        else:
            self.fields["phone_country_code"].initial = DEFAULT_PHONE_COUNTRY_CODE

    def _clean_phone_fields(self, cleaned_data):
        """Validate, enforce uniqueness, and set cleaned_data['phone_number']."""
        country = cleaned_data.get("phone_country_code") or DEFAULT_PHONE_COUNTRY_CODE
        national = cleaned_data.get("phone_national_number")
        # Skip if the national field already failed required/max_length checks.
        if "phone_national_number" in self.errors:
            return cleaned_data
        try:
            combined = validate_combined_phone(country, national)
        except ValidationError as exc:
            self.add_error("phone_national_number", exc)
            return cleaned_data

        conflict = User.objects.filter(phone_number=combined)
        instance = getattr(self, "instance", None)
        if instance is not None and getattr(instance, "pk", None):
            conflict = conflict.exclude(pk=instance.pk)
        if conflict.exists():
            self.add_error(
                "phone_national_number",
                _(
                    "An account with this phone number already exists. "
                    "Please use a different number."
                ),
            )
            return cleaned_data

        cleaned_data["phone_number"] = combined
        return cleaned_data


class RegistrationForm(PhoneNumberFieldsMixin, UserCreationForm):
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
    years_of_experience = years_of_experience_form_field(required=True)
    experience_level = forms.ChoiceField(
        label=_("Experience level"),
        required=True,
        choices=[("", _("Select your level"))] + list(ExperienceLevel.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
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
            "date_of_birth",
            "county",
            "town_city",
            "instruments",
            "other_instrument",
            "experience_level",
        )
        widgets = {
            "first_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "last_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "display_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "email": forms.EmailInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "other_instrument": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "maxlength": str(OTHER_INSTRUMENT_MAX_LENGTH),
                },
            ),
        }
        labels = {
            "display_name": _("Nickname / Display name"),
            "other_instrument": _("Other instrument"),
        }
        help_texts = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
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
        cleaned_data = self._clean_phone_fields(cleaned_data)

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

        years = cleaned_data.get("years_of_experience")
        date_of_birth = cleaned_data.get("date_of_birth")
        if years is not None and date_of_birth is not None:
            try:
                validate_years_of_experience_against_age(years, date_of_birth)
            except ValidationError as exc:
                self.add_error("years_of_experience", exc)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone_number = self.cleaned_data["phone_number"]
        user.username = generate_unique_username(user.display_name)
        user.terms_accepted_at = timezone.now()
        user.years_of_experience = self.cleaned_data["years_of_experience"]
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


class ProfileEditForm(PhoneNumberFieldsMixin, forms.ModelForm):
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
    years_of_experience = years_of_experience_form_field(required=True)
    experience_level = forms.ChoiceField(
        label=_("Experience level"),
        required=True,
        choices=[("", _("Select your level"))] + list(ExperienceLevel.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
    )

    class Meta:
        model = User
        fields = (
            "profile_picture",
            "display_name",
            "county",
            "town_city",
            "instruments",
            "other_instrument",
            "preferred_genres",
            "other_genre",
            "experience_level",
            "bio",
        )
        widgets = {
            "profile_picture": ProfilePictureInput(
                attrs={"accept": "image/*,.heic,.heif"},
            ),
            "display_name": forms.TextInput(
                attrs={
                    "class": f"{SIZED_INPUT_CLASSES} jam-input--display-name",
                    "maxlength": "20",
                },
            ),
            "other_instrument": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "maxlength": str(OTHER_INSTRUMENT_MAX_LENGTH),
                },
            ),
            "other_genre": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "maxlength": str(OTHER_GENRE_MAX_LENGTH),
                },
            ),
            "bio": forms.Textarea(attrs={"class": TEXT_INPUT_CLASSES, "rows": 5}),
        }
        labels = {
            "display_name": _("Display Name"),
            "other_instrument": _("Other instrument"),
            "other_genre": _("Other genre"),
            "bio": _("Bio"),
        }
        help_texts = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].required = True
        self.fields["other_instrument"].required = False
        self.fields["other_genre"].required = False
        if self.instance and self.instance.pk:
            self.fields["years_of_experience"].initial = (
                self.instance.years_of_experience
            )
        self.fields["profile_picture"].widget.attrs[
            "data-immediate-remove-url"
        ] = reverse("accounts:profile_picture_remove")
        self.fields["profile_picture"].widget.attrs[
            "data-immediate-upload-url"
        ] = reverse("accounts:profile_picture_upload")
        self.fields["profile_picture"].widget.attrs[
            "data-heic-preview-url"
        ] = reverse("accounts:profile_picture_preview")

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
        cleaned_data = self._clean_phone_fields(cleaned_data)

        instruments = cleaned_data.get("instruments") or []
        other_instrument = (cleaned_data.get("other_instrument") or "").strip()
        if Instrument.OTHER in instruments and not other_instrument:
            self.add_error(
                "other_instrument",
                _("Please specify your instrument."),
            )
        if Instrument.OTHER not in instruments:
            cleaned_data["other_instrument"] = ""

        preferred_genres = cleaned_data.get("preferred_genres") or []
        other_genre = (cleaned_data.get("other_genre") or "").strip()
        if MusicGenre.OTHER in preferred_genres and not other_genre:
            self.add_error(
                "other_genre",
                _("Please specify your genre."),
            )
        if MusicGenre.OTHER not in preferred_genres:
            cleaned_data["other_genre"] = ""

        county = cleaned_data.get("county")
        town_city = cleaned_data.get("town_city")
        if county and town_city:
            valid_towns = TOWNS_BY_COUNTY.get(county, [])
            if town_city not in valid_towns:
                self.add_error(
                    "town_city",
                    _("Please choose a town or city in the selected county."),
                )

        years = cleaned_data.get("years_of_experience")
        if years is not None:
            try:
                validate_years_of_experience_against_age(
                    years,
                    self.instance.date_of_birth,
                )
            except ValidationError as exc:
                self.add_error("years_of_experience", exc)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone_number = self.cleaned_data["phone_number"]
        user.years_of_experience = self.cleaned_data["years_of_experience"]
        if commit:
            user.save()
            self.save_m2m()
        return user


class SocialLinkForm(forms.ModelForm):
    """Single optional URL row inside the profile edit formset."""

    class Meta:
        model = SocialLink
        fields = ("url",)
        widgets = {
            "url": forms.URLInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "placeholder": _(
                        "https://… (Instagram, Spotify or YouTube)"
                    ),
                    "autocomplete": "url",
                },
            ),
        }
        labels = {"url": _("Link URL")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["url"].required = False

    def clean_url(self):
        # Django's URLField may assume https:// for schemeless values — check
        # the raw submitted string so "www.…" is still rejected.
        raw = (self.data.get(self.add_prefix("url")) or "").strip()
        if not raw:
            return ""
        if not (raw.startswith("http://") or raw.startswith("https://")):
            raise forms.ValidationError(
                _("Enter a full URL starting with http:// or https://.")
            )
        return (self.cleaned_data.get("url") or raw).strip()


class BaseSocialLinkFormSet(BaseInlineFormSet):
    """Assign display order and reject duplicate URLs in one submit."""

    def clean(self):
        super().clean()

        seen = set()
        active_count = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            url = (form.cleaned_data.get("url") or "").strip()
            if not url:
                continue
            active_count += 1
            key = url.casefold().rstrip("/")
            if key in seen:
                form.add_error(
                    "url",
                    _("You have already added this link."),
                )
            seen.add(key)

        if active_count > MAX_SOCIAL_LINKS:
            raise forms.ValidationError(
                _("You can add at most %(max)s social / music links.")
                % {"max": MAX_SOCIAL_LINKS}
            )

    def validate_unique(self):
        """
        Replace Django's generic duplicate-constraint wording with our
        clearer field-level message (already set in clean()).
        """
        # Intentionally skip BaseModelFormSet.validate_unique — clean() above
        # already rejects duplicate URLs among the submitted rows, and the
        # DB UniqueConstraint remains as a safety net on save.
        return

    def save(self, commit=True):
        order = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            if not (form.cleaned_data.get("url") or "").strip():
                continue
            form.instance.order = order
            order += 1
        return super().save(commit=commit)


SocialLinkFormSet = inlineformset_factory(
    User,
    SocialLink,
    form=SocialLinkForm,
    formset=BaseSocialLinkFormSet,
    fields=("url",),
    extra=1,
    max_num=MAX_SOCIAL_LINKS,
    validate_max=True,
    can_delete=True,
)


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
