"""Transactional email helpers for the accounts app."""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse


def send_verification_email(user, request):
    """
    Send the welcome + email verification message.

    With the console email backend the full message (including the
    verification link) is printed to the runserver terminal.
    """
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

    send_mail(
        subject="Welcome to JamSession Lab — please verify your email",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
