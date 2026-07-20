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
    path(
        "verify-email/required/",
        views.verification_required,
        name="verification_required",
    ),
    path(
        "verify-email/resend/",
        views.resend_verification,
        name="resend_verification",
    ),
    path("profile/", views.my_profile, name="profile"),
    # Must come before profile/<username>/ so "edit" is not read as a username.
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path(
        "profile/picture/remove/",
        views.profile_picture_remove,
        name="profile_picture_remove",
    ),
    path(
        "profile/picture/preview/",
        views.profile_picture_preview,
        name="profile_picture_preview",
    ),
    path(
        "profile/picture/upload/",
        views.profile_picture_upload,
        name="profile_picture_upload",
    ),
    path(
        "profile/social-links/<int:pk>/delete/",
        views.social_link_delete,
        name="social_link_delete",
    ),
    path("profile/delete/", views.account_delete, name="account_delete"),
    path("profile/<str:username>/", views.profile_detail, name="profile_detail"),
    path(
        "verify-email/<uuid:token>/",
        views.verify_email,
        name="verify_email",
    ),
]
