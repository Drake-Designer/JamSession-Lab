"""Transactional email helpers for the accounts app."""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def _build_verification_message(user, request):
    """Build absolute verify URL and plain-text body (safe to call in the request thread)."""
    verify_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"token": user.email_verification_token},
        )
    )
    message = render_to_string(
        "accounts/emails/verify_email.txt",
        {
            "user": user,
            "verify_url": verify_url,
            "whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK,
        },
    )
    return message


def send_verification_email(user, request) -> bool:
    """
    Send the welcome + email verification message synchronously.

    Returns True on success, False on any failure. Never raises — callers
    (registration, resend) must not break the HTTP request over SMTP issues.

    With the console email backend the full message (including the
    verification link) is printed to the runserver / gunicorn logs.
    """
    message = _build_verification_message(user, request)
    return _deliver_verification_email(user.email, user.pk, message)


def queue_verification_email(user, request) -> None:
    """
    Schedule a verification email without blocking the HTTP response.

    Builds the message on the request thread (needs ``request``), then sends
    in a daemon thread so a slow/hung SMTP connect cannot trigger Gunicorn
    WORKER TIMEOUT / SIGKILL on the signup request.

    In tests / non-SMTP backends the send stays synchronous so Django's
    ``mail.outbox`` assertions remain deterministic.

    TODO: replace the daemon-thread approach with a proper task queue
    (Celery, Django-Q, or RQ) once Redis or another broker is available on
    Render. Threads are acceptable only as a short-term safeguard on a
    single free-tier worker.
    """
    recipient = user.email
    user_pk = user.pk
    message = _build_verification_message(user, request)

    backend = settings.EMAIL_BACKEND or ""
    use_background = (
        not getattr(settings, "TESTING", False)
        and backend.endswith("smtp.EmailBackend")
    )

    if not use_background:
        _deliver_verification_email(recipient, user_pk, message)
        return

    def _worker():
        _deliver_verification_email(recipient, user_pk, message)

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


def _deliver_verification_email(recipient, user_pk, message) -> bool:
    """Low-level SMTP/console send. Logs and returns False on failure."""
    try:
        send_mail(
            subject="Welcome to JamSession Lab — please verify your email",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        # Timeout, connection refused, auth errors, etc. — never propagate.
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
