from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .constants import Instrument, MusicGenre
from .models import SocialLink, User
from .widgets import ProfilePictureInput


class AdminUserChangeForm(UserChangeForm):
    """Renders the instruments/genres JSON lists as friendly checkbox groups."""

    instruments = forms.MultipleChoiceField(
        label=_("Instruments played"),
        choices=Instrument.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    preferred_genres = forms.MultipleChoiceField(
        label=_("Preferred music genres"),
        choices=MusicGenre.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "profile_picture" in self.fields:
            self.fields["profile_picture"].widget = ProfilePictureInput(
                attrs={"accept": "image/*,.heic,.heif"},
            )


class SocialLinkInline(TabularInline):
    model = SocialLink
    extra = 0
    fields = ("url", "order")
    ordering = ("order", "pk")


@admin.register(User)
class CustomUserAdmin(ModelAdmin, UserAdmin):
    form = AdminUserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    inlines = [SocialLinkInline]

    fieldsets = (
        (
            _("Account"),
            {
                "classes": ["tab"],
                "fields": (
                    "username",
                    "display_name",
                    "password",
                    "email",
                    "is_email_verified",
                    "phone_number",
                ),
            },
        ),
        (
            _("Profile"),
            {
                "classes": ["tab"],
                "description": _(
                    "Musician profile details shown on the community website."
                ),
                "fields": (
                    "profile_picture",
                    ("date_of_birth", "display_age"),
                    ("county", "town_city"),
                    "instruments",
                    "other_instrument",
                    "preferred_genres",
                    "other_genre",
                    ("years_of_experience", "experience_level"),
                    "bio",
                ),
            },
        ),
        (
            _("Permissions"),
            {
                "classes": ["tab"],
                "description": _(
                    "Control site access. Only change these if you know what they do."
                ),
                "fields": (
                    ("is_active", "is_staff", "is_superuser"),
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Important dates"),
            {
                "classes": ["tab", "collapse"],
                "fields": ("last_login", "date_joined", "terms_accepted_at"),
            },
        ),
    )
    add_fieldsets = (
        (
            _("Account"),
            {
                "classes": ["tab"],
                "fields": (
                    "username",
                    "usable_password",
                    "password1",
                    "password2",
                    "email",
                ),
            },
        ),
    )

    list_display = (
        "profile_picture_thumbnail",
        "display_name",
        "email",
        "display_age",
        "display_instruments",
        "display_is_verified",
        "display_is_staff",
        "display_is_active",
    )
    list_filter = ("county", "is_email_verified", "is_staff", "is_active", "is_superuser")
    search_fields = ("username", "display_name", "email", "first_name", "last_name")
    readonly_fields = (
        "last_login",
        "date_joined",
        "display_age",
        "terms_accepted_at",
    )
    filter_horizontal = ("groups", "user_permissions")
    ordering = ("username",)

    class Media:
        css = {"all": ("accounts/css/profile_picture_widget.css",)}
        js = ("accounts/js/instrument_toggle.js",)

    @staticmethod
    def _user_initials(user):
        if user.first_name and user.last_name:
            return f"{user.first_name[0]}{user.last_name[0]}".upper()
        if user.username:
            return user.username[:2].upper()
        return "?"

    @display(description=_("Photo"), header=True)
    def profile_picture_thumbnail(self, obj):
        picture_url = obj.display_profile_picture_url
        if picture_url:
            return (
                None,
                None,
                None,
                {
                    "path": picture_url,
                    "squared": True,
                    "width": 38,
                    "height": 38,
                },
            )
        # header=True always requires a list/tuple — use initials when no photo
        return (None, None, self._user_initials(obj), None)

    @display(description=_("Age"))
    def display_age(self, obj):
        age = obj.age
        if age is None:
            return "—"
        return f"{age} years old"

    @display(description=_("Instruments"))
    def display_instruments(self, obj):
        return obj.get_instruments_display() or "—"

    @display(description=_("Email verified"), boolean=True, ordering="is_email_verified")
    def display_is_verified(self, obj):
        return obj.is_email_verified

    @display(description=_("Staff"), boolean=True, ordering="is_staff")
    def display_is_staff(self, obj):
        return obj.is_staff

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active
