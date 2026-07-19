from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

from registrations.models import EventRegistration, RsvpStatus
from registrations.views import registration_list_context

from .forms import EventForm
from .models import Event


def _require_moderator(user):
    """Raise PermissionDenied unless the user is staff/superuser."""
    if not (user.is_staff or user.is_superuser):
        raise PermissionDenied


def event_list(request):
    """Public list of active events with key details and register/view CTAs."""
    events = list(
        Event.objects.filter(is_active=True).order_by("starts_at")
    )
    registered_event_ids = set()
    if request.user.is_authenticated and events:
        registered_event_ids = set(
            EventRegistration.objects.filter(
                user=request.user,
                event_id__in=[event.pk for event in events],
                rsvp_status=RsvpStatus.REGISTERED,
            ).values_list("event_id", flat=True)
        )

    event_cards = [
        {
            "event": event,
            "is_registered": event.pk in registered_event_ids,
        }
        for event in events
    ]
    return render(
        request,
        "events/event_list.html",
        {"event_cards": event_cards},
    )


@login_required
@require_http_methods(["GET"])
def event_manage(request):
    """Staff-only: inline event detail, tools, and attendee lists."""
    _require_moderator(request.user)
    events = Event.objects.order_by("-starts_at")
    managed_events = []
    for event in events:
        lists = registration_list_context(event)
        managed_events.append(
            {
                "event": event,
                "registered_rows": lists["registered_rows"],
                "cancelled_rows": lists["cancelled_rows"],
            }
        )
    return render(
        request,
        "events/event_manage.html",
        {"managed_events": managed_events},
    )


def event_detail(request, pk):
    """Public event detail page."""
    event = get_object_or_404(Event, pk=pk)
    if not event.is_active and not (
        request.user.is_authenticated
        and (request.user.is_staff or request.user.is_superuser)
    ):
        raise PermissionDenied

    user_registration = None
    if request.user.is_authenticated:
        user_registration = (
            EventRegistration.objects.filter(user=request.user, event=event)
            .prefetch_related("songs")
            .first()
        )

    return render(
        request,
        "events/event_detail.html",
        {
            "event": event,
            "user_registration": user_registration,
            "is_registered": bool(
                user_registration
                and user_registration.rsvp_status == RsvpStatus.REGISTERED
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def event_create(request):
    """Staff-only: create a new event."""
    _require_moderator(request.user)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save()
            messages.success(request, _("Event created successfully."))
            return redirect("events:manage")
    else:
        form = EventForm()
    return render(
        request,
        "events/event_form.html",
        {"form": form, "is_edit": False},
    )


@login_required
@require_http_methods(["GET", "POST"])
def event_edit(request, pk):
    """Staff-only: edit an existing event."""
    _require_moderator(request.user)
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, _("Event updated successfully."))
            return redirect(f"{reverse('events:manage')}#event-{event.pk}")
    else:
        form = EventForm(instance=event)
    return render(
        request,
        "events/event_form.html",
        {"form": form, "event": event, "is_edit": True},
    )


@login_required
@require_http_methods(["GET", "POST"])
def event_delete(request, pk):
    """Staff-only: confirm and delete an event."""
    _require_moderator(request.user)
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        event.delete()
        messages.success(request, _("Event deleted."))
        return redirect("events:manage")
    return render(
        request,
        "events/event_confirm_delete.html",
        {"event": event},
    )


@login_required
@require_POST
def event_toggle_active(request, pk):
    """Staff-only: toggle is_active (POST only)."""
    _require_moderator(request.user)
    event = get_object_or_404(Event, pk=pk)
    event.is_active = not event.is_active
    event.save(update_fields=["is_active", "updated_at"])
    if event.is_active:
        messages.success(request, _("Event is now active."))
    else:
        messages.success(request, _("Event is now inactive."))
    return redirect(f"{reverse('events:manage')}#event-{event.pk}")


@login_required
@require_POST
def event_toggle_registrations(request, pk):
    """Staff-only: toggle registrations_open (POST only)."""
    _require_moderator(request.user)
    event = get_object_or_404(Event, pk=pk)
    event.registrations_open = not event.registrations_open
    event.save(update_fields=["registrations_open", "updated_at"])
    if event.registrations_open:
        messages.success(request, _("Registrations are now open."))
    else:
        messages.success(request, _("Registrations are now closed."))
    return redirect(f"{reverse('events:manage')}#event-{event.pk}")
