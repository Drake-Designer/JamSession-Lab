from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .constants import Instrument, MusicGenre
from .models import SocialLink, User
from .validators import (
    MAX_YEARS_OF_EXPERIENCE,
    validate_years_of_experience_against_age,
)
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
    years_of_experience = forms.IntegerField(
        label=_("Years of experience"),
        required=False,
        min_value=0,
        max_value=MAX_YEARS_OF_EXPERIENCE,
        help_text=_(
            "Increases automatically by one year every 1 January "
            "(derived from the stored start year)."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "profile_picture" in self.fields:
            self.fields["profile_picture"].widget = ProfilePictureInput(
                attrs={"accept": "image/*,.heic,.heif"},
            )
        if self.instance and self.instance.pk:
            self.fields["years_of_experience"].initial = (
                self.instance.years_of_experience
            )

    def clean_years_of_experience(self):
        years = self.cleaned_data.get("years_of_experience")
        if years is None:
            return years
        validate_years_of_experience_against_age(
            years,
            self.cleaned_data.get("date_of_birth") or self.instance.date_of_birth,
        )
        return years

    def save(self, commit=True):
        user = super().save(commit=False)
        years = self.cleaned_data.get("years_of_experience")
        user.years_of_experience = years
        if commit:
            user.save()
            self.save_m2m()
        return user


class SocialLinkInline(TabularInline):
    model = SocialLink
    extra = 0
    fields = ("url", "order")
    ordering = ("order", "pk")
    tab = True
    verbose_name = "social_link"
    verbose_name_plural = _("Social / music links")


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
                    "email_verification_send_count",
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
                    "experience_started_year",
                    "bio",
                ),
            },
        ),
        (
            _("Permissions"),
            {
                "classes": ["tab"],
                "description": _(
                    "Access flags and Django permissions. "
                    "Turning on Staff automatically adds the user to the Staff group "
                    "(carousel, gallery, community, events, and user profile edits, "
                    "not user deletion). Superuser bypasses all permission checks and "
                    "is the only role that can delete user accounts."
                ),
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "force_member_badge",
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
        "display_is_superuser",
        "display_is_active",
    )
    list_filter = (
        "county",
        "is_email_verified",
        "is_staff",
        "is_active",
        "is_superuser",
        "force_member_badge",
    )
    search_fields = ("username", "display_name", "email", "first_name", "last_name")
    readonly_fields = (
        "last_login",
        "date_joined",
        "display_age",
        "experience_started_year",
        "terms_accepted_at",
    )
    filter_horizontal = ("groups", "user_permissions")
    ordering = ("username",)

    class Media:
        css = {
            "all": (
                "accounts/css/profile_picture_widget.css",
                "accounts/css/admin_permissions.css",
            )
        }
        js = ("accounts/js/instrument_toggle.js",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        permission_help = {
            "is_active": _(
                "Off = account disabled (cannot log in). Prefer this over deleting."
            ),
            "is_staff": _(
                "On = site moderator (REVIEW, ADMIN TOOL, EVENTS) and admin access "
                "via the Staff group: carousel, gallery, community, events, and "
                "editing user profiles. Staff cannot delete user accounts."
            ),
            "is_superuser": _(
                "On = full access to every admin page and every action, including "
                "deleting users. Shows the Founder badge on the site."
            ),
            "force_member_badge": _(
                "Regular members only. If on, shows “Member” instead of “New Member” "
                "even if they joined less than 30 days ago. Hidden for staff/superuser."
            ),
            "groups": _(
                "Staff users are auto-added to the Staff group when Staff status is on. "
                "You can still add other groups here if needed."
            ),
            "user_permissions": _(
                "Extra individual permissions for this user only. "
                "Usually unnecessary for staff: the Staff group already covers "
                "carousel, gallery, community, events, and profile edits."
            ),
        }
        for field_name, help_text in permission_help.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = help_text
        return form

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        hide_force_member = obj is not None and (obj.is_staff or obj.is_superuser)
        if not hide_force_member:
            return fieldsets

        trimmed = []
        for name, options in fieldsets:
            fields = options.get("fields")
            if fields and "force_member_badge" in fields:
                options = {
                    **options,
                    "fields": tuple(
                        field for field in fields if field != "force_member_badge"
                    ),
                }
            trimmed.append((name, options))
        return trimmed

    def has_delete_permission(self, request, obj=None):
        """Only superusers may delete user accounts."""
        return bool(request.user.is_superuser)

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
            return "-"
        return f"{age} years old"

    @display(description=_("Instruments"))
    def display_instruments(self, obj):
        return obj.get_instruments_display() or "-"

    @display(description=_("Email verified"), boolean=True, ordering="is_email_verified")
    def display_is_verified(self, obj):
        return obj.is_email_verified

    @display(description=_("Staff"), boolean=True, ordering="is_staff")
    def display_is_staff(self, obj):
        return obj.is_staff

    @display(description=_("Superuser"), boolean=True, ordering="is_superuser")
    def display_is_superuser(self, obj):
        return obj.is_superuser

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active
