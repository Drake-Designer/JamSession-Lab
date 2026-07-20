"""Transactional email helpers for the events app."""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.emails import (
    EmailContent,
    _absolute_static_url,
    _deliver_email,
    _queue_or_send,
    _should_use_resend_api,
)

logger = logging.getLogger(__name__)

User = get_user_model()

EVENT_ANNOUNCE_SUBJECT = "New jam session · JamSession Lab"


def _member_announce_recipients():
    """
    Active members with a non-blank email address.

    Includes unverified accounts so newly registered musicians still hear
    about upcoming sessions; skips empty emails.
    """
    return list(
        User.objects.filter(is_active=True)
        .exclude(email="")
        .only("pk", "email", "username", "display_name")
        .order_by("pk")
    )


def _build_event_announce_message(event, request, member) -> EmailContent:
    """Branded announcement for one member about ``event``."""
    event_url = request.build_absolute_uri(
        reverse("events:detail", kwargs={"pk": event.pk})
    )
    context = {
        "user": member,
        "event": event,
        "event_url": event_url,
        "site_url": request.build_absolute_uri("/"),
        "logo_url": _absolute_static_url(
            request,
            "images/jamsession-lab-logo.jpg",
        ),
        "whatsapp_link": settings.WHATSAPP_COMMUNITY_LINK,
    }
    text = render_to_string("events/emails/event_announce.txt", context)
    html = render_to_string("events/emails/event_announce.html", context)
    return EmailContent(
        text=text,
        html=html,
        subject=EVENT_ANNOUNCE_SUBJECT,
    )


def send_event_announcement_emails(event, request) -> tuple[int, int]:
    """
    Send the event announcement to every active member (synchronous).

    Returns ``(sent_count, failed_count)``. Never raises.
    """
    members = _member_announce_recipients()
    sent = 0
    failed = 0
    for member in members:
        content = _build_event_announce_message(event, request, member)
        if _deliver_email(member.email, member.pk, content):
            sent += 1
        else:
            failed += 1
    return sent, failed


def queue_event_announcement_emails(event, request) -> int:
    """
    Notify all active members about ``event``.

    Builds per-recipient messages on the request thread (needs absolute URLs),
    then sends in one background thread in production so the staff click stays
    responsive. In tests / console / locmem the send is synchronous.

    Returns the number of recipients queued (or sent synchronously).
    """
    members = _member_announce_recipients()
    if not members:
        return 0

    payloads = [
        (member.email, member.pk, _build_event_announce_message(event, request, member))
        for member in members
    ]

    backend = settings.EMAIL_BACKEND or ""
    use_background = not getattr(settings, "TESTING", False) and (
        _should_use_resend_api() or backend.endswith("smtp.EmailBackend")
    )

    if not use_background:
        for recipient, user_pk, content in payloads:
            _queue_or_send(recipient, user_pk, content)
        return len(payloads)

    def _worker():
        for recipient, user_pk, content in payloads:
            _deliver_email(recipient, user_pk, content)

    thread = threading.Thread(
        target=_worker,
        name=f"event-announce-{event.pk}",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Queued event announcement for event %s to %s members (background thread)",
        event.pk,
        len(payloads),
    )
    return len(payloads)
