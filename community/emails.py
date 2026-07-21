"""Transactional email helpers for community / gallery moderation alerts."""

from __future__ import annotations

import logging

from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from accounts.emails import (
    EmailContent,
    _normalise_html_email,
    _queue_or_send,
    _superuser_alert_recipients,
)

logger = logging.getLogger(__name__)

MODERATION_ALERT_SUBJECT = "Content awaiting review · JamSession Lab"


def _absolute_static_url(request, relative_path: str) -> str:
    return request.build_absolute_uri(staticfiles_storage.url(relative_path))


def _review_url(request) -> str:
    return request.build_absolute_uri(
        f"{reverse('community:admin_tool')}?tab=review"
    )


def _base_context(request) -> dict:
    return {
        "site_url": request.build_absolute_uri("/"),
        "logo_url": _absolute_static_url(
            request,
            "images/jamsession-lab-logo.jpg",
        ),
        "review_url": _review_url(request),
    }


def _submitter_label(user) -> str:
    if user is None:
        return _("(deleted account)")
    display = getattr(user, "public_display_name", None) or user.get_username()
    return f"{display} (@{user.get_username()})"


def queue_moderation_alert(
    request,
    *,
    content_type: str,
    submitter,
    summary: str,
) -> None:
    """
    Notify every active superuser that one item entered the pending queue.

    Never raises. Non-blocking in production (same pattern as new-user alerts).
    """
    recipients = _superuser_alert_recipients()
    if not recipients:
        logger.warning(
            "Moderation alert skipped (%s) — no active superuser emails",
            content_type,
        )
        return

    context = {
        **_base_context(request),
        "content_type": content_type,
        "submitter_label": _submitter_label(submitter),
        "summary": summary,
        "item_count": 1,
        "is_batch": False,
    }
    text = render_to_string("community/emails/moderation_alert.txt", context)
    html = _normalise_html_email(
        render_to_string("community/emails/moderation_alert.html", context)
    )
    content = EmailContent(text=text, html=html, subject=MODERATION_ALERT_SUBJECT)
    submitter_pk = getattr(submitter, "pk", 0) or 0
    for recipient in recipients:
        _queue_or_send(recipient, submitter_pk, content)


def queue_gallery_batch_moderation_alert(
    request,
    *,
    submitter,
    item_count: int,
) -> None:
    """
    One summary email for a multi-file gallery upload that needs review.

    Never raises.
    """
    if item_count <= 0:
        return

    if item_count == 1:
        queue_moderation_alert(
            request,
            content_type=_("Gallery item"),
            submitter=submitter,
            summary=_("A new gallery upload is awaiting review."),
        )
        return

    recipients = _superuser_alert_recipients()
    if not recipients:
        logger.warning(
            "Gallery batch moderation alert skipped — no active superuser emails"
        )
        return

    context = {
        **_base_context(request),
        "content_type": _("Gallery items"),
        "submitter_label": _submitter_label(submitter),
        "summary": _(
            "%(count)d gallery uploads are awaiting review."
        )
        % {"count": item_count},
        "item_count": item_count,
        "is_batch": True,
    }
    text = render_to_string("community/emails/moderation_alert.txt", context)
    html = _normalise_html_email(
        render_to_string("community/emails/moderation_alert.html", context)
    )
    content = EmailContent(text=text, html=html, subject=MODERATION_ALERT_SUBJECT)
    submitter_pk = getattr(submitter, "pk", 0) or 0
    for recipient in recipients:
        _queue_or_send(recipient, submitter_pk, content)
