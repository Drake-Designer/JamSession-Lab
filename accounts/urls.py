from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    # LogoutView only accepts POST (CSRF-protected); redirect target comes
    # from LOGOUT_REDIRECT_URL in settings.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("welcome/", views.welcome, name="welcome"),
    path("profile/", views.my_profile, name="profile"),
    # Must come before profile/<username>/ so "edit" is not read as a username.
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/delete/", views.account_delete, name="account_delete"),
    path("profile/<str:username>/", views.profile_detail, name="profile_detail"),
    path(
        "verify-email/<uuid:token>/",
        views.verify_email,
        name="verify_email",
    ),
]
