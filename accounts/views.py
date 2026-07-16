from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

import cloudinary.exceptions

from community.models import CommunityComment, CommunityPost
from gallery.models import GalleryItem
from jamsession.moderation import ApprovalStatus

from .constants import TOWNS_BY_COUNTY, Instrument, MusicGenre
from .emails import send_verification_email
from .forms import (
    DeleteAccountForm,
    LoginForm,
    ProfileEditForm,
    RegistrationForm,
)
from .models import User


class LoginView(auth_views.LoginView):
    """Public sign-in page (email or username)."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@require_http_methods(["GET", "POST"])
def register(request):
    """Public sign-up page."""
    if request.user.is_authenticated:
        return redirect("pages:home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(user, request)
            # Sign the new member in straight away — email verification is
            # prepared but not enforced yet.
            login(request, user)
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
    """Alphabetical labels for the user's preferred genres."""
    labels = [
        str(MusicGenre(code).label)
        for code in user.preferred_genres or []
        if code in MusicGenre.values
    ]
    return sorted(labels, key=str.casefold)


@login_required
def my_profile(request):
    """Shortcut: /accounts/profile/ goes to the signed-in user's profile."""
    return redirect("accounts:profile_detail", username=request.user.username)


def profile_detail(request, username):
    """Public profile page, visible to everyone including anonymous visitors."""
    profile_user = get_object_or_404(User, username=username, is_active=True)

    is_owner = request.user.is_authenticated and request.user == profile_user

    # Owner-only: every post they authored (pending/approved/rejected), newest
    # first. Comments are intentionally excluded — this is "My posts", not a
    # full activity feed. Delete buttons reuse community:post_delete.
    my_posts = []
    if is_owner:
        my_posts = list(
            CommunityPost.objects.filter(author=profile_user).order_by("-created_at")
        )

    # Staff/superuser owners see a "Review Items" entry on their own profile.
    # No dedicated context processor exists for badge counts yet, so the
    # pending total is computed here and passed to the template.
    show_review_items = False
    pending_review_count = 0
    if is_owner and (request.user.is_staff or request.user.is_superuser):
        show_review_items = True
        pending_review_count = (
            CommunityPost.objects.filter(status=ApprovalStatus.PENDING).count()
            + CommunityComment.objects.filter(status=ApprovalStatus.PENDING).count()
            + GalleryItem.objects.filter(status=ApprovalStatus.PENDING).count()
        )

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": profile_user,
            "instrument_labels": _instrument_labels(profile_user),
            "genre_labels": _genre_labels(profile_user),
            "is_owner": is_owner,
            "my_posts": my_posts,
            "show_review_items": show_review_items,
            "pending_review_count": pending_review_count,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    """Let the signed-in user edit their own profile."""
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            try:
                form.save()
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

    selected_town = (
        request.POST.get("town_city")
        if request.method == "POST"
        else request.user.town_city
    )

    return render(
        request,
        "accounts/profile_edit.html",
        {
            "form": form,
            "delete_form": DeleteAccountForm(user=request.user),
            "towns_by_county": TOWNS_BY_COUNTY,
            "selected_town": selected_town or "",
        },
    )


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

    verified = False
    already_verified = False

    if user is not None:
        if user.is_email_verified:
            already_verified = True
        else:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
            verified = True

    return render(
        request,
        "accounts/email_verify_result.html",
        {
            "verified": verified,
            "already_verified": already_verified,
        },
    )
