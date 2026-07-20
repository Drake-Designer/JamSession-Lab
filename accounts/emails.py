"""Transactional email helpers for the accounts app."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from email.utils import parseaddr

import requests
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)

VERIFICATION_EMAIL_SUBJECT = "Welcome to JamSession Lab · please verify your email"
EMAIL_CHANGE_SUBJECT = "Confirm your new email · JamSession Lab"
EMAIL_CHANGE_NOTICE_SUBJECT = "Email change requested · JamSession Lab"
PASSWORD_RESET_SUBJECT = "Reset your password · JamSession Lab"
NEW_USER_ALERT_SUBJECT = "New member registered · JamSession Lab"


@dataclass(frozen=True)
class EmailContent:
    """Plain-text + HTML parts for a transactional message."""

    text: str
    html: str
    subject: str


def _absolute_static_url(request, relative_path: str) -> str:
    """Build an absolute URL for a static asset (required inside HTML emails)."""
    return request.build_absolute_uri(staticfiles_storage.url(relative_path))


def _common_email_context(user, request) -> dict:
    """Shared template variables for account transactional emails."""
    return {
        "user": user,
        "whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK,
        "site_url": request.build_absolute_uri("/"),
        "logo_url": _absolute_static_url(
            request,
            "images/jamsession-lab-logo.jpg",
        ),
    }


def _build_verification_message(user, request) -> EmailContent:
    """Build absolute URLs and text/HTML bodies (safe to call in the request thread)."""
    verify_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"token": user.email_verification_token},
        )
    )
    context = {
        **_common_email_context(user, request),
        "verify_url": verify_url,
    }
    text = render_to_string("accounts/emails/verify_email.txt", context)
    html = render_to_string("accounts/emails/verify_email.html", context)
    return EmailContent(text=text, html=html, subject=VERIFICATION_EMAIL_SUBJECT)


def _build_email_change_message(user, request) -> EmailContent:
    """Confirmation message sent to the pending (new) email address."""
    verify_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"token": user.email_verification_token},
        )
    )
    context = {
        **_common_email_context(user, request),
        "verify_url": verify_url,
        "new_email": user.pending_email,
        "current_email": user.email,
    }
    text = render_to_string("accounts/emails/change_email.txt", context)
    html = render_to_string("accounts/emails/change_email.html", context)
    return EmailContent(text=text, html=html, subject=EMAIL_CHANGE_SUBJECT)


def _build_email_change_notice(user, request, *, old_email: str, new_email: str) -> EmailContent:
    """Security notice sent to the previous email address."""
    context = {
        **_common_email_context(user, request),
        "old_email": old_email,
        "new_email": new_email,
        "settings_url": request.build_absolute_uri(
            reverse("accounts:account_settings")
        ),
    }
    text = render_to_string("accounts/emails/change_email_notice.txt", context)
    html = render_to_string("accounts/emails/change_email_notice.html", context)
    return EmailContent(text=text, html=html, subject=EMAIL_CHANGE_NOTICE_SUBJECT)


def _parse_from_email(from_email: str) -> tuple[str, str]:
    """Split ``Name <addr@example.com>`` into (name, email)."""
    name, address = parseaddr(from_email or "")
    if not address:
        address = (from_email or "").strip()
    if not name:
        name = "JamSession Lab"
    return name, address


def _should_use_resend_api() -> bool:
    """Prefer Resend HTTPS API in production when an API key is configured."""
    if getattr(settings, "TESTING", False):
        return False
    if not getattr(settings, "RESEND_API_KEY", ""):
        return False
    backend = settings.EMAIL_BACKEND or ""
    # Honour emergency / local console override.
    if backend.endswith("console.EmailBackend"):
        return False
    if backend.endswith("locmem.EmailBackend"):
        return False
    return True


def _build_password_reset_message(context: dict) -> EmailContent:
    """
    Build text/HTML bodies for a password-reset link email.

    ``context`` is the dict produced by Django's PasswordResetForm.save()
    (uid, token, user, protocol, domain, plus any extra_email_context).
    """
    reset_path = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": context["uid"], "token": context["token"]},
    )
    reset_url = f"{context['protocol']}://{context['domain']}{reset_path}"
    site_url = context.get("site_url") or f"{context['protocol']}://{context['domain']}/"
    email_context = {
        "user": context["user"],
        "reset_url": reset_url,
        "site_url": site_url,
        "logo_url": context.get("logo_url", ""),
        "whatsapp_link": context.get(
            "whatsapp_link",
            getattr(settings, "WHATSAPP_COMMUNITY_LINK", ""),
        ),
    }
    text = render_to_string("accounts/emails/password_reset.txt", email_context)
    html = render_to_string("accounts/emails/password_reset.html", email_context)
    return EmailContent(text=text, html=html, subject=PASSWORD_RESET_SUBJECT)


def send_password_reset_email(recipient: str, context: dict) -> bool:
    """
    Send a password-reset message via Resend API or Django's email backend.

    Called from PasswordResetRequestForm.send_mail. Never raises — Django's
    reset flow always shows the "email sent" page to avoid account enumeration.
    """
    user = context.get("user")
    user_pk = getattr(user, "pk", 0) or 0
    content = _build_password_reset_message(context)
    return _deliver_email(recipient, user_pk, content)


def send_verification_email(user, request) -> bool:
    """
    Send the welcome + email verification message synchronously.

    Returns True on success, False on any failure. Never raises — callers
    (registration, resend) must not break the HTTP request over mail issues.

    With the console email backend the full message (including the
    verification link) is printed to the runserver / gunicorn logs.
    """
    content = _build_verification_message(user, request)
    return _deliver_email(user.email, user.pk, content)


def queue_verification_email(user, request) -> None:
    """
    Schedule a verification email without blocking the HTTP response.

    Builds the message on the request thread (needs ``request``), then sends
    in a daemon thread so a slow mail provider cannot trigger Gunicorn
    WORKER TIMEOUT / SIGKILL on the signup request.

    In tests / console / locmem backends the send stays synchronous so
    Django's ``mail.outbox`` assertions remain deterministic.

    TODO: replace the daemon-thread approach with a proper task queue
    (Celery, Django-Q, or RQ) once Redis or another broker is available on
    Render. Threads are acceptable only as a short-term safeguard on a
    single free-tier worker.
    """
    recipient = user.email
    user_pk = user.pk
    content = _build_verification_message(user, request)
    _queue_or_send(recipient, user_pk, content)


def _superuser_alert_recipients():
    """
    Active superuser emails (the personal inbox(es) that should hear about
    new sign-ups). Skips blank addresses. Deduplicated, order-stable.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    emails = []
    seen = set()
    for email in (
        User.objects.filter(is_active=True, is_superuser=True)
        .exclude(email="")
        .values_list("email", flat=True)
    ):
        normalised = (email or "").strip().lower()
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        emails.append(email.strip())
    return emails


def _build_new_user_alert(member, request) -> EmailContent:
    """Staff alert: branded notice that a new member signed up."""
    instruments = member.get_instruments_display()
    context = {
        **_common_email_context(member, request),
        "member": member,
        "instruments_display": ", ".join(instruments) if instruments else "",
        "profile_url": request.build_absolute_uri(
            reverse(
                "accounts:profile_detail",
                kwargs={"username": member.username},
            )
        ),
    }
    text = render_to_string("accounts/emails/new_user_alert.txt", context)
    html = render_to_string("accounts/emails/new_user_alert.html", context)
    return EmailContent(text=text, html=html, subject=NEW_USER_ALERT_SUBJECT)


def queue_new_user_alert(member, request) -> None:
    """
    Notify every active superuser that ``member`` just registered.

    Non-blocking in production (same pattern as verification). Never raises.
    Uses each superuser's personal account email as the recipient; the From
    address stays ``DEFAULT_FROM_EMAIL`` (staff@jamsessionlab.ie) for
    deliverability on the verified sending domain.
    """
    recipients = _superuser_alert_recipients()
    if not recipients:
        logger.warning(
            "New-user alert skipped for user %s — no active superuser emails",
            member.pk,
        )
        return

    content = _build_new_user_alert(member, request)
    for recipient in recipients:
        _queue_or_send(recipient, member.pk, content)


def send_email_change_verification(user, request) -> bool:
    """Send the confirm-new-email message to ``user.pending_email``."""
    recipient = (user.pending_email or "").strip()
    if not recipient:
        return False
    content = _build_email_change_message(user, request)
    return _deliver_email(recipient, user.pk, content)


def send_email_change_notice(user, request, *, old_email: str, new_email: str) -> bool:
    """Notify the previous address that an email change was requested."""
    recipient = (old_email or "").strip()
    if not recipient:
        return False
    content = _build_email_change_notice(
        user,
        request,
        old_email=old_email,
        new_email=new_email,
    )
    return _deliver_email(recipient, user.pk, content)


def queue_email_change_verification(user, request) -> None:
    """Background-friendly send of the pending-email confirmation message."""
    recipient = (user.pending_email or "").strip()
    if not recipient:
        return
    content = _build_email_change_message(user, request)
    _queue_or_send(recipient, user.pk, content)


def _queue_or_send(recipient: str, user_pk: int, content: EmailContent) -> None:
    """Send now in tests/local backends; otherwise dispatch a daemon thread."""
    backend = settings.EMAIL_BACKEND or ""
    use_background = not getattr(settings, "TESTING", False) and (
        _should_use_resend_api() or backend.endswith("smtp.EmailBackend")
    )

    if not use_background:
        _deliver_email(recipient, user_pk, content)
        return

    def _worker():
        _deliver_email(recipient, user_pk, content)

    thread = threading.Thread(
        target=_worker,
        name=f"account-email-user-{user_pk}",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Queued account email for user %s to %s (background thread)",
        user_pk,
        recipient,
    )


def _deliver_email(recipient, user_pk, content: EmailContent) -> bool:
    """Route to Resend HTTP API or Django mail backend. Never raises."""
    if _should_use_resend_api():
        return _deliver_via_resend_api(recipient, user_pk, content)
    return _deliver_via_django(recipient, user_pk, content)


def _deliver_via_resend_api(recipient, user_pk, content: EmailContent) -> bool:
    """Send via Resend transactional HTTPS API (works on Render free)."""
    from_email = settings.DEFAULT_FROM_EMAIL
    _, sender_email = _parse_from_email(from_email)
    payload = {
        "from": from_email,
        "to": [recipient],
        "subject": content.subject,
        "text": content.text,
        "html": content.html,
    }
    try:
        response = requests.post(
            settings.RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.EMAIL_TIMEOUT,
        )
        if not response.ok:
            logger.error(
                "Resend API rejected email for user %s to %s "
                "(status=%s body=%s sender=%s subject=%s)",
                user_pk,
                recipient,
                response.status_code,
                response.text[:500],
                sender_email,
                content.subject,
            )
            return False
    except Exception:
        logger.exception(
            "Failed to send email via Resend API for user %s to %s",
            user_pk,
            recipient,
        )
        return False

    logger.info(
        "Email sent via Resend API for user %s to %s (subject=%s)",
        user_pk,
        recipient,
        content.subject,
    )
    return True


def _deliver_via_django(recipient, user_pk, content: EmailContent) -> bool:
    """SMTP / console / locmem via Django's email backend (text + HTML)."""
    try:
        message = EmailMultiAlternatives(
            subject=content.subject,
            body=content.text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(content.html, "text/html")
        message.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send email for user %s to %s "
            "(backend=%s host=%s port=%s timeout=%s subject=%s)",
            user_pk,
            recipient,
            settings.EMAIL_BACKEND,
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            getattr(settings, "EMAIL_TIMEOUT", None),
            content.subject,
        )
        return False

    logger.info(
        "Email sent for user %s to %s (subject=%s)",
        user_pk,
        recipient,
        content.subject,
    )
    return True
