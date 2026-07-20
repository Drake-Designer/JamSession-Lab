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


@dataclass(frozen=True)
class EmailContent:
    """Plain-text + HTML parts for a transactional message."""

    text: str
    html: str


def _absolute_static_url(request, relative_path: str) -> str:
    """Build an absolute URL for a static asset (required inside HTML emails)."""
    return request.build_absolute_uri(staticfiles_storage.url(relative_path))


def _build_verification_message(user, request) -> EmailContent:
    """Build absolute URLs and text/HTML bodies (safe to call in the request thread)."""
    verify_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"token": user.email_verification_token},
        )
    )
    site_url = request.build_absolute_uri("/")
    context = {
        "user": user,
        "verify_url": verify_url,
        "whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK,
        "site_url": site_url,
        "logo_url": _absolute_static_url(
            request,
            "images/jamsession-lab-logo.jpg",
        ),
    }
    text = render_to_string("accounts/emails/verify_email.txt", context)
    html = render_to_string("accounts/emails/verify_email.html", context)
    return EmailContent(text=text, html=html)


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


def send_verification_email(user, request) -> bool:
    """
    Send the welcome + email verification message synchronously.

    Returns True on success, False on any failure. Never raises — callers
    (registration, resend) must not break the HTTP request over mail issues.

    With the console email backend the full message (including the
    verification link) is printed to the runserver / gunicorn logs.
    """
    content = _build_verification_message(user, request)
    return _deliver_verification_email(user.email, user.pk, content)


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

    backend = settings.EMAIL_BACKEND or ""
    use_background = not getattr(settings, "TESTING", False) and (
        _should_use_resend_api() or backend.endswith("smtp.EmailBackend")
    )

    if not use_background:
        _deliver_verification_email(recipient, user_pk, content)
        return

    def _worker():
        _deliver_verification_email(recipient, user_pk, content)

    thread = threading.Thread(
        target=_worker,
        name=f"verify-email-user-{user_pk}",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Queued verification email for user %s (background thread)",
        user_pk,
    )


def _deliver_verification_email(recipient, user_pk, content: EmailContent) -> bool:
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
        "subject": VERIFICATION_EMAIL_SUBJECT,
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
                "Resend API rejected verification email for user %s to %s "
                "(status=%s body=%s sender=%s)",
                user_pk,
                recipient,
                response.status_code,
                response.text[:500],
                sender_email,
            )
            return False
    except Exception:
        logger.exception(
            "Failed to send verification email via Resend API for user %s to %s",
            user_pk,
            recipient,
        )
        return False

    logger.info(
        "Verification email sent via Resend API for user %s to %s",
        user_pk,
        recipient,
    )
    return True


def _deliver_via_django(recipient, user_pk, content: EmailContent) -> bool:
    """SMTP / console / locmem via Django's email backend (text + HTML)."""
    try:
        message = EmailMultiAlternatives(
            subject=VERIFICATION_EMAIL_SUBJECT,
            body=content.text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(content.html, "text/html")
        message.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send verification email for user %s to %s "
            "(backend=%s host=%s port=%s timeout=%s)",
            user_pk,
            recipient,
            settings.EMAIL_BACKEND,
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            getattr(settings, "EMAIL_TIMEOUT", None),
        )
        return False

    logger.info("Verification email sent for user %s to %s", user_pk, recipient)
    return True
