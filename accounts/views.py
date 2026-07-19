import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

import cloudinary.exceptions

from community.models import CommunityComment, CommunityPost
from gallery.models import GalleryItem
from jamsession.image_formats import convert_heic_upload_to_jpeg
from jamsession.moderation import ApprovalStatus
from registrations.models import EventRegistration, RsvpStatus

from .constants import TOWNS_BY_COUNTY, Instrument, MusicGenre
from .emails import send_verification_email
from .forms import (
    DeleteAccountForm,
    LoginForm,
    ProfileEditForm,
    RegistrationForm,
    SocialLinkFormSet,
)
from .models import SocialLink, User
from .social_platforms import detect_social_platform
from .validators import validate_profile_picture


AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"
RESEND_VERIFICATION_COOLDOWN_SECONDS = 60
RESEND_VERIFICATION_SESSION_KEY = "email_verification_last_sent_at"
SOCIAL_LINKS_FORMSET_PREFIX = "social_links"


class LoginView(auth_views.LoginView):
    """Public sign-in page (email or username)."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if (
            user.is_authenticated
            and not user.is_email_verified
            and not user.is_staff
            and not user.is_superuser
        ):
            return reverse("accounts:verification_required")
        return super().get_success_url()


def _safe_next_url(request, candidate):
    """Return candidate if it is a safe same-host path, else empty string."""
    from django.utils.http import url_has_allowed_host_and_scheme

    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}
    ):
        return candidate
    return ""


@require_http_methods(["GET", "POST"])
def register(request):
    """Public sign-up page."""
    if request.user.is_authenticated:
        return redirect("pages:home")

    next_url = _safe_next_url(
        request, request.POST.get("next") or request.GET.get("next")
    )
    show_event_rsvp_banner = "/events/" in next_url and next_url.rstrip("/").endswith(
        "register"
    )

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(user, request)
            # Soft-block: stay signed in, but middleware restricts member
            # actions until the email is verified.
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect("accounts:welcome")
    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            # Serialised by json_script in the template and read by
            # register.js to fill the dependent Town/City dropdown.
            "towns_by_county": TOWNS_BY_COUNTY,
            "selected_town": (request.POST.get("town_city") or ""),
            "next": next_url,
            "show_event_rsvp_banner": show_event_rsvp_banner,
        },
    )


@login_required
def welcome(request):
    """Post-registration page with the WhatsApp community invitation."""
    return render(
        request,
        "accounts/welcome.html",
        {"whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK},
    )


@login_required
def verification_required(request):
    """Landing page for members who must verify their email before continuing."""
    if request.user.is_email_verified:
        return redirect("pages:home")
    return render(
        request,
        "accounts/verification_required.html",
        {"whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK},
    )


@login_required
@require_POST
def resend_verification(request):
    """Re-send the verification email, with a simple session rate limit."""
    if request.user.is_email_verified:
        return redirect("pages:home")

    now = time.time()
    last_sent = request.session.get(RESEND_VERIFICATION_SESSION_KEY)
    if (
        last_sent is not None
        and now - float(last_sent) < RESEND_VERIFICATION_COOLDOWN_SECONDS
    ):
        messages.warning(
            request,
            _(
                "Please wait a minute before requesting another verification email."
            ),
        )
        return redirect("accounts:verification_required")

    request.user.regenerate_email_verification_token()
    send_verification_email(request.user, request)
    request.session[RESEND_VERIFICATION_SESSION_KEY] = now
    messages.success(
        request,
        _("A new verification email has been sent. Please check your inbox."),
    )
    return redirect("accounts:verification_required")


def _instrument_labels(user):
    """Alphabetical instrument labels, with 'Other' spelled out."""
    labels = []
    for code in user.instruments or []:
        if code == Instrument.OTHER:
            labels.append(user.other_instrument or str(Instrument.OTHER.label))
        elif code in Instrument.values:
            labels.append(str(Instrument(code).label))
    return sorted(labels, key=str.casefold)


def _genre_labels(user):
    """Alphabetical labels for the user's preferred genres, with 'Other' spelled out."""
    labels = []
    for code in user.preferred_genres or []:
        if code == MusicGenre.OTHER:
            labels.append(user.other_genre or str(MusicGenre.OTHER.label))
        elif code in MusicGenre.values:
            labels.append(str(MusicGenre(code).label))
    return sorted(labels, key=str.casefold)


@login_required
def my_profile(request):
    """Shortcut: /accounts/profile/ goes to the signed-in user's profile."""
    return redirect("accounts:profile_detail", username=request.user.username)


def profile_detail(request, username):
    """Public profile page, visible to everyone including anonymous visitors."""
    profile_user = get_object_or_404(
        User.objects.prefetch_related("social_links"),
        username=username,
        is_active=True,
    )

    is_owner = request.user.is_authenticated and request.user == profile_user

    # Owner-only: every post they authored (pending/approved/rejected), newest
    # first. Comments are intentionally excluded — this is "My posts", not a
    # full activity feed. Delete buttons reuse community:post_delete.
    my_posts = []
    my_event_registrations = []
    if is_owner:
        my_posts = list(
            CommunityPost.objects.filter(author=profile_user).order_by("-created_at")
        )
        my_event_registrations = list(
            EventRegistration.objects.filter(
                user=profile_user,
                rsvp_status=RsvpStatus.REGISTERED,
            )
            .select_related("event")
            .order_by("event__starts_at")
        )

    # Staff/superuser owners see REVIEW / ADMIN TOOL / EVENTS on their profile.
    # REVIEW is shown in the template only when pending_review_count > 0.
    show_staff_tools = False
    pending_review_count = 0
    if is_owner and (request.user.is_staff or request.user.is_superuser):
        show_staff_tools = True
        pending_review_count = (
            CommunityPost.objects.filter(status=ApprovalStatus.PENDING).count()
            + CommunityComment.objects.filter(status=ApprovalStatus.PENDING).count()
            + GalleryItem.objects.filter(status=ApprovalStatus.PENDING).count()
        )

    social_links = []
    for link in profile_user.social_links.all():
        platform = detect_social_platform(link.url)
        if platform is None:
            continue
        social_links.append({"url": link.url, "platform": platform})

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": profile_user,
            "instrument_labels": _instrument_labels(profile_user),
            "genre_labels": _genre_labels(profile_user),
            "social_links": social_links,
            "is_owner": is_owner,
            "my_posts": my_posts,
            "my_event_registrations": my_event_registrations,
            "show_staff_tools": show_staff_tools,
            "pending_review_count": pending_review_count,
            # Owner-only completion ring — visitors never see this.
            "profile_completion_percentage": (
                profile_user.profile_completion_percentage if is_owner else None
            ),
            "missing_fields": (
                profile_user.missing_fields if is_owner else []
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    """Let the signed-in user edit their own profile."""
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        formset = SocialLinkFormSet(
            request.POST,
            instance=request.user,
            prefix=SOCIAL_LINKS_FORMSET_PREFIX,
        )
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
            except cloudinary.exceptions.Error:
                form.add_error(
                    "profile_picture",
                    _(
                        "We couldn't process that image. Please try a "
                        "different photo (JPG, PNG, or HEIC) under 10MB."
                    ),
                )
            else:
                messages.success(request, _("Your profile has been updated."))
                return redirect(
                    "accounts:profile_detail", username=request.user.username
                )
    else:
        form = ProfileEditForm(instance=request.user)
        formset = SocialLinkFormSet(
            instance=request.user,
            prefix=SOCIAL_LINKS_FORMSET_PREFIX,
        )

    selected_town = (
        request.POST.get("town_city")
        if request.method == "POST"
        else request.user.town_city
    )

    highlight_missing = request.GET.get("highlight_missing") == "1"
    missing_field_keys = (
        request.user.missing_field_keys if highlight_missing else []
    )

    return render(
        request,
        "accounts/profile_edit.html",
        {
            "form": form,
            "social_link_formset": formset,
            "delete_form": DeleteAccountForm(user=request.user),
            "towns_by_county": TOWNS_BY_COUNTY,
            "selected_town": selected_town or "",
            "highlight_missing": highlight_missing,
            "missing_field_keys": missing_field_keys,
        },
    )


@login_required
@require_POST
def profile_picture_remove(request):
    """Delete the signed-in user's profile photo immediately (AJAX)."""
    user = request.user
    if user.profile_picture:
        user.profile_picture = None
        user.save(update_fields=["profile_picture"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def profile_picture_upload(request):
    """Upload / replace the signed-in user's profile photo immediately (AJAX)."""
    uploaded = request.FILES.get("profile_picture")
    if uploaded is None:
        return JsonResponse(
            {"ok": False, "error": str(_("Please choose a photo to upload."))},
            status=400,
        )

    try:
        picture = convert_heic_upload_to_jpeg(
            uploaded,
            field_name="profile_picture",
        )
        validate_profile_picture(picture)
    except ValidationError as exc:
        message = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
        return JsonResponse({"ok": False, "error": message}, status=400)

    user = request.user
    try:
        user.profile_picture = picture
        user.save(update_fields=["profile_picture"])
    except cloudinary.exceptions.Error:
        return JsonResponse(
            {
                "ok": False,
                "error": str(
                    _(
                        "We couldn't process that image. Please try a "
                        "different photo (JPG, PNG, or HEIC) under 10MB."
                    )
                ),
            },
            status=400,
        )

    return JsonResponse({"ok": True})


@login_required
@require_POST
def social_link_delete(request, pk):
    """Delete one of the signed-in user's social links immediately (AJAX)."""
    link = get_object_or_404(SocialLink, pk=pk, user=request.user)
    link.delete()

    # Keep display order contiguous after a mid-list deletion.
    remaining = list(request.user.social_links.order_by("order", "pk"))
    for index, item in enumerate(remaining):
        if item.order != index:
            SocialLink.objects.filter(pk=item.pk).update(order=index)

    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["POST"])
def account_delete(request):
    """
    Permanently delete the signed-in user's account.

    Gallery items survive with uploaded_by set to NULL (SET_NULL on the
    foreign key), so approved media stays visible without an author.
    """
    form = DeleteAccountForm(request.POST, user=request.user)

    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return redirect("accounts:profile_edit")

    user = request.user
    logout(request)  # Flushes the session before the user row disappears.
    user.delete()
    messages.success(
        request,
        _("Your account has been permanently deleted. We're sorry to see you go."),
    )
    return redirect("pages:home")


def verify_email(request, token):
    """Confirm an email address from the link sent at registration."""
    user = User.objects.filter(email_verification_token=token).first()

    if user is None:
        return render(
            request,
            "accounts/email_verify_result.html",
            {
                "verified": False,
                "already_verified": False,
            },
        )

    if user.is_email_verified:
        messages.info(
            request,
            _("This email address has already been verified."),
        )
    else:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        messages.success(
            request,
            _("Your email address has been verified. Welcome!"),
        )

    if not request.user.is_authenticated:
        login(request, user, backend=AUTH_BACKEND)

    return redirect("pages:home")
