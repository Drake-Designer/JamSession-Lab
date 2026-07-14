from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import User


@admin.register(User)
class CustomUserAdmin(ModelAdmin, UserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    fieldsets = (
        (
            _("Account"),
            {
                "classes": ["tab"],
                "fields": (
                    "username",
                    "password",
                    "email",
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
                    "instrument",
                    "instrument_other",
                    "favourite_genre",
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
                "fields": ("last_login", "date_joined"),
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
                    ("instrument", "instrument_other"),
                ),
            },
        ),
        (
            _("Profile"),
            {
                "classes": ["tab", "collapse"],
                "description": _(
                    "Optional — the musician can complete these details after signing in."
                ),
                "fields": (
                    "profile_picture",
                    "date_of_birth",
                    "favourite_genre",
                    "bio",
                ),
            },
        ),
    )

    list_display = (
        "profile_picture_thumbnail",
        "username",
        "email",
        "display_age",
        "display_instrument",
        "display_is_staff",
        "display_is_active",
    )
    list_filter = ("instrument", "is_staff", "is_active", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    readonly_fields = ("last_login", "date_joined", "display_age")
    filter_horizontal = ("groups", "user_permissions")
    ordering = ("username",)

    class Media:
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
        if obj.profile_picture:
            return (
                None,
                None,
                None,
                {
                    "path": obj.profile_picture.url,
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

    @display(description=_("Instrument"), ordering="instrument")
    def display_instrument(self, obj):
        return obj.get_instrument_display_full()

    @display(description=_("Staff"), boolean=True, ordering="is_staff")
    def display_is_staff(self, obj):
        return obj.is_staff

    @display(description=_("Active"), boolean=True, ordering="is_active")
    def display_is_active(self, obj):
        return obj.is_active
