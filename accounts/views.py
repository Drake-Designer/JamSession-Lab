import math
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

import cloudinary.exceptions

from community.models import CommunityComment, CommunityPost
from gallery.models import GalleryItem
from jamsession.image_formats import convert_heic_upload_to_jpeg
from jamsession.moderation import ApprovalStatus
from registrations.models import EventRegistration, RsvpStatus

from .constants import TOWNS_BY_COUNTY, Instrument, MusicGenre
from .emails import (
    queue_verification_email,
    send_email_change_notice,
    send_email_change_verification,
    send_verification_email,
)
from .forms import (
    AccountPasswordChangeForm,
    ChangeEmailForm,
    DeleteAccountForm,
    LoginForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    ProfileEditForm,
    RegistrationForm,
    SocialLinkFormSet,
)
from .models import SocialLink, User
from .social_platforms import detect_social_platform
from .validators import validate_profile_picture


AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"
RESEND_VERIFICATION_COOLDOWN_SECONDS = 20
RESEND_VERIFICATION_SESSION_KEY = "email_verification_last_sent_at"
MAX_VERIFICATION_EMAILS = 5
SOCIAL_LINKS_FORMSET_PREFIX = "social_links"


def _verification_cooldown_remaining(request) -> int:
    """Seconds left before another verification email may be sent."""
    last_sent = request.session.get(RESEND_VERIFICATION_SESSION_KEY)
    if last_sent is None:
        return 0
    remaining = RESEND_VERIFICATION_COOLDOWN_SECONDS - (time.time() - float(last_sent))
    # ceil so a just-sent email still shows a full cooldown (not 9s for 10).
    return max(0, math.ceil(remaining))


def _mark_verification_email_sent(request) -> None:
    """Record the send time used by the resend cooldown."""
    request.session[RESEND_VERIFICATION_SESSION_KEY] = time.time()


def _verification_send_limit_reached(user) -> bool:
    """True when this member has used up automatic verification emails."""
    return user.has_exhausted_verification_emails(MAX_VERIFICATION_EMAILS)


def _verification_page_context(request):
    """Shared template context for welcome / verification_required."""
    limit_reached = _verification_send_limit_reached(request.user)
    return {
        "whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK,
        "resend_cooldown_seconds": (
            0 if limit_reached else _verification_cooldown_remaining(request)
        ),
        "verification_send_limit_reached": limit_reached,
        "max_verification_emails": MAX_VERIFICATION_EMAILS,
    }


def _maybe_send_verification_on_login(request, user) -> None:
    """
    Auto-send a verification email only after a fresh sign-in.

    Visiting /accounts/verify-email/required/ while already logged in does
    not send; the member must use Resend (until the send limit is reached).
    """
    if (
        not user.is_authenticated
        or user.is_email_verified
        or user.is_staff
        or user.is_superuser
        or _verification_send_limit_reached(user)
    ):
        return

    user.regenerate_email_verification_token()
    queue_verification_email(user, request)
    user.record_verification_email_sent()
    _mark_verification_email_sent(request)
    messages.info(
        request,
        _(
            "A verification email has been sent to %(email)s. "
            "Please check your inbox."
        )
        % {"email": user.email},
    )


class LoginView(auth_views.LoginView):
    """Public sign-in page (email or username)."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        _maybe_send_verification_on_login(self.request, self.request.user)
        return response

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


def _password_reset_email_context(request):
    """Extra template vars for the branded password-reset email."""
    from django.contrib.staticfiles.storage import staticfiles_storage

    return {
        "site_url": request.build_absolute_uri("/"),
        "logo_url": request.build_absolute_uri(
            staticfiles_storage.url("images/jamsession-lab-logo.jpg")
        ),
        "whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK,
    }


class PasswordResetView(auth_views.PasswordResetView):
    """Ask for an email address and send a one-time reset link."""

    template_name = "accounts/password_reset.html"
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy("accounts:password_reset_done")
    # Subject/body templates are unused: PasswordResetRequestForm.send_mail
    # builds branded content via accounts.emails.send_password_reset_email.
    email_template_name = "accounts/emails/password_reset.txt"
    subject_template_name = "accounts/emails/password_reset_subject.txt"

    def form_valid(self, form):
        # Inject absolute site/logo URLs before Django's form.save() runs.
        self.extra_email_context = _password_reset_email_context(self.request)
        return super().form_valid(form)


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    """Confirmation that a reset email was (or would be) sent."""

    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """Choose a new password after opening the email link."""

    template_name = "accounts/password_reset_confirm.html"
    form_class = PasswordResetConfirmForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """Success page after the password has been changed."""

    template_name = "accounts/password_reset_complete.html"


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
            # Non-blocking: SMTP hangs must not kill the Gunicorn worker or
            # turn a successful signup into a 500. Failures are logged inside
            # accounts.emails; the member can use "resend verification".
            queue_verification_email(user, request)
            user.record_verification_email_sent()
            # Soft-block: stay signed in, but middleware restricts member
            # actions until the email is verified.
            login(request, user)
            # Start the resend cooldown so welcome / verification_required
            # do not immediately auto-send a second email.
            _mark_verification_email_sent(request)
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
        _verification_page_context(request),
    )


@login_required
def verification_required(request):
    """Landing page for members who must verify their email before continuing."""
    if request.user.is_email_verified:
        return redirect("pages:home")

    # No auto-send here: revisiting this page while already signed in requires
    # an explicit Resend click. Auto-send happens only on a fresh login.
    return render(
        request,
        "accounts/verification_required.html",
        _verification_page_context(request),
    )


@login_required
@require_POST
def resend_verification(request):
    """Re-send the verification email, with a simple session rate limit."""
    if request.user.is_email_verified:
        return redirect("pages:home")

    if _verification_send_limit_reached(request.user):
        messages.error(
            request,
            _(
                "We have already sent the maximum number of verification emails. "
                "Please contact JamSession Lab to activate your account."
            ),
        )
        return redirect("accounts:verification_required")

    remaining = _verification_cooldown_remaining(request)
    if remaining > 0:
        messages.warning(
            request,
            _(
                "Please wait %(seconds)s seconds before requesting another "
                "verification email."
            )
            % {"seconds": remaining},
        )
        return redirect("accounts:verification_required")

    request.user.regenerate_email_verification_token()
    # Synchronous here so we can tell the user if delivery failed; EMAIL_TIMEOUT
    # keeps a hung SMTP connect from exceeding the Gunicorn worker limit.
    sent = send_verification_email(request.user, request)
    if not sent:
        messages.error(
            request,
            _(
                "We could not send the verification email just now. "
                "Please try again in a few seconds."
            ),
        )
        return redirect("accounts:verification_required")

    request.user.record_verification_email_sent()
    _mark_verification_email_sent(request)
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
        user.profile_picture_focus_x = 50.0
        user.profile_picture_focus_y = 50.0
        user.save(
            update_fields=[
                "profile_picture",
                "profile_picture_focus_x",
                "profile_picture_focus_y",
            ]
        )
    return JsonResponse({"ok": True})


def _parse_profile_picture_focus(raw_value, *, default=50.0):
    """Clamp a focus percentage from the upload form to 0–100."""
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, value))


@login_required
@require_POST
def profile_picture_preview(request):
    """
    Convert an upload (including HEIC) to a browser-safe JPEG for the crop UI.

    Does not save the photo — only returns JPEG bytes so the cropper can run
    in browsers that cannot decode HEIC natively.
    """
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
    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": str(
                    _(
                        "We couldn't open that photo. Please try a "
                        "JPG or PNG instead."
                    )
                ),
            },
            status=400,
        )

    picture.seek(0)
    response = HttpResponse(picture.read(), content_type="image/jpeg")
    response["Cache-Control"] = "no-store"
    return response


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

    focus_x = _parse_profile_picture_focus(request.POST.get("profile_picture_focus_x"))
    focus_y = _parse_profile_picture_focus(request.POST.get("profile_picture_focus_y"))

    user = request.user
    try:
        user.profile_picture = picture
        user.profile_picture_focus_x = focus_x
        user.profile_picture_focus_y = focus_y
        user.save(
            update_fields=[
                "profile_picture",
                "profile_picture_focus_x",
                "profile_picture_focus_y",
            ]
        )
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
    Permanently delete the signed-in user's account and all personal content.

    Community posts/comments and gallery uploads cascade-delete with the user
    (Cloudinary assets are removed by post_delete signals). Registrations,
    social links, and likes are also removed via CASCADE.
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
    """
    Confirm an email address from a verification link.

    Handles both first-time registration verification and pending email
    changes from Account Settings.
    """
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

    if user.has_pending_email_change:
        new_email = user.apply_pending_email()
        if new_email is None:
            messages.error(
                request,
                _(
                    "We could not confirm that email address because it is no "
                    "longer available. Please request a new email change."
                ),
            )
            if not request.user.is_authenticated:
                login(request, user, backend=AUTH_BACKEND)
            return redirect("accounts:account_settings")

        messages.success(
            request,
            _(
                "Your email address has been updated to %(email)s. "
                "You can now sign in with this address."
            )
            % {"email": new_email},
        )
    elif user.is_email_verified:
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


@login_required
@require_http_methods(["GET"])
def account_settings(request):
    """Account Settings: change email and password."""
    return render(
        request,
        "accounts/account_settings.html",
        {
            "email_form": ChangeEmailForm(user=request.user),
            "password_form": AccountPasswordChangeForm(user=request.user),
        },
    )


@login_required
@require_POST
def account_change_email(request):
    """Start an email change: store pending_email and send confirmation."""
    form = ChangeEmailForm(request.POST, user=request.user)
    if not form.is_valid():
        return render(
            request,
            "accounts/account_settings.html",
            {
                "email_form": form,
                "password_form": AccountPasswordChangeForm(user=request.user),
            },
            status=400,
        )

    user = request.user
    old_email = user.email
    new_email = form.cleaned_data["new_email"]

    user.pending_email = new_email
    user.regenerate_email_verification_token()
    user.save(update_fields=["pending_email"])

    sent = send_email_change_verification(user, request)
    if not sent:
        user.clear_pending_email()
        messages.error(
            request,
            _(
                "We could not send the confirmation email just now. "
                "Please try again in a few seconds."
            ),
        )
        return redirect("accounts:account_settings")

    send_email_change_notice(
        user,
        request,
        old_email=old_email,
        new_email=new_email,
    )
    messages.success(
        request,
        _(
            "A confirmation link has been sent to %(email)s. "
            "Your current email stays active until you confirm the new one."
        )
        % {"email": new_email},
    )
    return redirect("accounts:account_settings")


@login_required
@require_POST
def account_cancel_pending_email(request):
    """Cancel an in-progress email change."""
    if request.user.has_pending_email_change:
        request.user.clear_pending_email()
        messages.success(
            request,
            _("The pending email change has been cancelled."),
        )
    return redirect("accounts:account_settings")


@login_required
@require_POST
def account_resend_pending_email(request):
    """Re-send the confirmation email for a pending address change."""
    user = request.user
    if not user.has_pending_email_change:
        messages.info(request, _("There is no pending email change to confirm."))
        return redirect("accounts:account_settings")

    remaining = _verification_cooldown_remaining(request)
    if remaining > 0:
        messages.warning(
            request,
            _(
                "Please wait %(seconds)s seconds before requesting another "
                "confirmation email."
            )
            % {"seconds": remaining},
        )
        return redirect("accounts:account_settings")

    user.regenerate_email_verification_token()
    sent = send_email_change_verification(user, request)
    if not sent:
        messages.error(
            request,
            _(
                "We could not send the confirmation email just now. "
                "Please try again in a few seconds."
            ),
        )
        return redirect("accounts:account_settings")

    _mark_verification_email_sent(request)
    messages.success(
        request,
        _("A new confirmation email has been sent to %(email)s.")
        % {"email": user.pending_email},
    )
    return redirect("accounts:account_settings")


@login_required
@require_POST
def account_change_password(request):
    """Update the signed-in user's password and keep the session valid."""
    form = AccountPasswordChangeForm(user=request.user, data=request.POST)
    if not form.is_valid():
        return render(
            request,
            "accounts/account_settings.html",
            {
                "email_form": ChangeEmailForm(user=request.user),
                "password_form": form,
            },
            status=400,
        )

    form.save()
    update_session_auth_hash(request, form.user)
    messages.success(request, _("Your password has been updated."))
    return redirect("accounts:account_settings")
