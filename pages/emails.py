"""Contact-form email delivery for the pages app."""

from __future__ import annotations

import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _parse_from_email(from_email: str) -> tuple[str, str]:
    name, address = parseaddr(from_email or "")
    if not address:
        address = (from_email or "").strip()
    if not name:
        name = "JamSession Lab"
    return name, address


def _should_use_resend_api() -> bool:
    if getattr(settings, "TESTING", False):
        return False
    if not getattr(settings, "RESEND_API_KEY", ""):
        return False
    backend = settings.EMAIL_BACKEND or ""
    if backend.endswith("console.EmailBackend"):
        return False
    if backend.endswith("locmem.EmailBackend"):
        return False
    return True


def _absolute_static_url(request, relative_path: str) -> str:
    return request.build_absolute_uri(staticfiles_storage.url(relative_path))


def send_contact_email(*, name, email, subject, message, request) -> bool:
    """
    Send a contact-form message to the staff inbox.

    ``Reply-To`` is set to the visitor's address so staff can reply directly.
    Never raises — returns True/False for the view to show success/error.
    """
    site_url = request.build_absolute_uri("/")
    context = {
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
        "site_url": site_url,
        "logo_url": _absolute_static_url(
            request,
            "images/jamsession-lab-logo.jpg",
        ),
    }
    text_body = render_to_string("pages/emails/contact_message.txt", context)
    html_body = render_to_string("pages/emails/contact_message.html", context)
    mail_subject = f"[Contact] {subject}"
    recipient = settings.CONTACT_EMAIL
    from_email = settings.DEFAULT_FROM_EMAIL

    if _should_use_resend_api():
        return _deliver_via_resend(
            recipient=recipient,
            from_email=from_email,
            reply_to=email,
            subject=mail_subject,
            text_body=text_body,
            html_body=html_body,
        )
    return _deliver_via_django(
        recipient=recipient,
        from_email=from_email,
        reply_to=email,
        subject=mail_subject,
        text_body=text_body,
        html_body=html_body,
    )


def _deliver_via_resend(
    *,
    recipient,
    from_email,
    reply_to,
    subject,
    text_body,
    html_body,
) -> bool:
    _, sender_email = _parse_from_email(from_email)
    payload = {
        "from": from_email,
        "to": [recipient],
        "reply_to": reply_to,
        "subject": subject,
        "text": text_body,
        "html": html_body,
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
                "Resend API rejected contact email to %s "
                "(status=%s body=%s sender=%s)",
                recipient,
                response.status_code,
                response.text[:500],
                sender_email,
            )
            return False
    except Exception:
        logger.exception("Failed to send contact email via Resend API to %s", recipient)
        return False

    logger.info("Contact email sent via Resend API to %s", recipient)
    return True


def _deliver_via_django(
    *,
    recipient,
    from_email,
    reply_to,
    subject,
    text_body,
    html_body,
) -> bool:
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[recipient],
            reply_to=[reply_to],
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send contact email to %s", recipient)
        return False

    logger.info("Contact email sent to %s", recipient)
    return True
