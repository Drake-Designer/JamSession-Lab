"""Restrict unverified members until they confirm their email address."""

from django.shortcuts import redirect
from django.urls import Resolver404, resolve


# URL names unverified (but authenticated) users may still reach.
# Profiles are intentionally excluded — own and others.
_ALLOWED_URL_NAMES = frozenset(
    {
        "accounts:register",
        "accounts:login",
        "accounts:logout",
        "accounts:welcome",
        "accounts:verify_email",
        "accounts:verification_required",
        "accounts:resend_verification",
        "pages:home",
        "pages:about",
        "pages:terms",
        "pages:privacy",
        "pages:contact",
        "events:list",
        "events:detail",
        "gallery:list",
        "community:list",
        "community:post_detail",
    }
)

_ALLOWED_PATH_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
)


class EmailVerificationMiddleware:
    """
    Soft-block: keep the session after sign-up/login, but send unverified
    non-staff users to the verification page for any non-allowlisted URL.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_block(request):
            return redirect("accounts:verification_required")
        return self.get_response(request)

    def _should_block(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return False
        if getattr(user, "is_email_verified", False):
            return False
        if self._is_allowed_path(request.path_info):
            return False
        return not self._is_allowed_url(request.path_info)

    @staticmethod
    def _is_allowed_path(path):
        return any(path.startswith(prefix) for prefix in _ALLOWED_PATH_PREFIXES)

    @staticmethod
    def _is_allowed_url(path):
        try:
            match = resolve(path)
        except Resolver404:
            # Let Django's normal 404 handling run.
            return True
        return match.view_name in _ALLOWED_URL_NAMES
