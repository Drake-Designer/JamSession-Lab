from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            'Profile',
            {
                'fields': (
                    'profile_picture',
                    'age',
                    'instrument',
                    'instrument_other',
                    'favourite_genre',
                    'bio',
                ),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            'Profile',
            {
                'fields': (
                    'instrument',
                    'instrument_other',
                    'profile_picture',
                    'age',
                    'favourite_genre',
                    'bio',
                ),
            },
        ),
    )
    list_display = ('username', 'email', 'instrument', 'is_staff')
    list_filter = ('instrument', 'is_staff', 'is_superuser', 'is_active')
