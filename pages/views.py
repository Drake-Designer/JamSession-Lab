from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from events.models import Event
from registrations.models import EventRegistration, RsvpStatus

from .emails import send_contact_email
from .forms import ContactForm
from .models import AboutOrganiser, HomeCarouselSlide


def home(request):
    """Render the public home page."""
    carousel_slides = HomeCarouselSlide.objects.filter(is_active=True).order_by("order")
    next_event = (
        Event.objects.filter(is_active=True, starts_at__gt=timezone.now())
        .annotate(
            _registered_count=Count(
                "registrations",
                filter=Q(registrations__rsvp_status=RsvpStatus.REGISTERED),
            )
        )
        .order_by("starts_at")
        .first()
    )
    is_registered_for_next_event = False
    if request.user.is_authenticated and next_event is not None:
        is_registered_for_next_event = EventRegistration.objects.filter(
            user=request.user,
            event=next_event,
            rsvp_status=RsvpStatus.REGISTERED,
        ).exists()
    return render(
        request,
        "pages/home.html",
        {
            "carousel_slides": carousel_slides,
            "next_event": next_event,
            "is_registered_for_next_event": is_registered_for_next_event,
        },
    )


def about(request):
    """Render the public About page."""
    organisers = AboutOrganiser.objects.filter(is_active=True).order_by("order")
    return render(request, "pages/about.html", {"organisers": organisers})


def terms(request):
    """Render the public Terms of Service page."""
    return render(request, "pages/terms.html")


def privacy(request):
    """Render the Privacy Policy page."""
    return render(request, "pages/privacy.html")


def contact(request):
    """Public Contact Us page with email form to the staff inbox."""
    if request.method == "POST":
        # Honeypot filled → pretend success without sending (do not tip off bots).
        if (request.POST.get("website") or "").strip():
            messages.success(
                request,
                _("Thanks. Your message has been sent. We will reply soon."),
            )
            return redirect("pages:contact")

        form = ContactForm(request.POST)

        last_sent = request.session.get("contact_form_sent_at")
        if last_sent and (timezone.now().timestamp() - float(last_sent)) < 60:
            messages.error(
                request,
                _("Please wait a minute before sending another message."),
            )
            return render(request, "pages/contact.html", {"form": form})

        if form.is_valid():
            sent = send_contact_email(
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                subject=form.cleaned_data["subject"],
                message=form.cleaned_data["message"],
                request=request,
            )
            if sent:
                request.session["contact_form_sent_at"] = str(timezone.now().timestamp())
                messages.success(
                    request,
                    _("Thanks. Your message has been sent. We will reply soon."),
                )
                return redirect("pages:contact")
            messages.error(
                request,
                _(
                    "Sorry, we could not send your message just now. "
                    "Please try again later or message us on Instagram."
                ),
            )
    else:
        form = ContactForm()

    return render(request, "pages/contact.html", {"form": form})


def bad_request(request, exception=None):
    """Custom 400 error page — rendered only when DEBUG=False."""
    return render(request, "errors/400.html", status=400)


def permission_denied(request, exception=None):
    """Custom 403 error page — rendered only when DEBUG=False."""
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    """Custom 404 error page — rendered only when DEBUG=False."""
    return render(request, "errors/404.html", status=404)


def server_error(request):
    """Custom 500 error page — rendered only when DEBUG=False."""
    return render(request, "errors/500.html", status=500)