from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

from accounts.constants import ExperienceLevel, Instrument
from events.models import Event

from .forms import (
    EventRegistrationForm,
    RegistrationSongFormSet,
    song_formset_initial_from_registration,
)
from .models import EventRegistration, RegistrationSong, RsvpStatus


def _require_moderator(user):
    """Raise PermissionDenied unless the user is staff/superuser."""
    if not (user.is_staff or user.is_superuser):
        raise PermissionDenied


def _snapshot_instruments(user):
    return list(user.instruments or [])


def _snapshot_experience_level(user):
    return user.experience_level or ""


def _instrument_labels(codes, other_instrument=""):
    labels = []
    for code in codes or []:
        if code == Instrument.OTHER and other_instrument:
            labels.append(other_instrument)
        else:
            try:
                labels.append(Instrument(code).label)
            except ValueError:
                labels.append(code)
    return labels


def _experience_level_label(code):
    if not code:
        return ""
    try:
        return ExperienceLevel(code).label
    except ValueError:
        return code


def _replace_songs(registration, song_formset, wants_originals):
    """Delete all songs and recreate from the formset when originals are Yes."""
    registration.songs.all().delete()
    if not wants_originals:
        return
    for form in song_formset.forms:
        if not hasattr(form, "cleaned_data") or not form.cleaned_data:
            continue
        if form.cleaned_data.get("DELETE"):
            continue
        title = (form.cleaned_data.get("title") or "").strip()
        song_key = (form.cleaned_data.get("song_key") or "").strip()
        chords = (form.cleaned_data.get("basic_chords") or "").strip()
        if title and song_key and chords:
            RegistrationSong.objects.create(
                registration=registration,
                title=title,
                song_key=song_key,
                basic_chords=chords,
            )


def _render_register(request, event, form, song_formset):
    return render(
        request,
        "registrations/register.html",
        {
            "event": event,
            "form": form,
            "song_formset": song_formset,
            "profile_instruments": _instrument_labels(
                request.user.instruments, request.user.other_instrument
            ),
            "profile_level": _experience_level_label(request.user.experience_level),
        },
    )


@require_http_methods(["GET", "POST"])
def register(request, pk):
    """RSVP form: GET shows form; POST validates, saves, redirects (PRG)."""
    event = get_object_or_404(Event, pk=pk)

    if not request.user.is_authenticated:
        register_url = reverse("accounts:register")
        next_path = reverse("events:register", kwargs={"pk": pk})
        return redirect(f"{register_url}?next={next_path}")

    existing = (
        EventRegistration.objects.filter(user=request.user, event=event)
        .prefetch_related("songs")
        .first()
    )

    if existing and existing.rsvp_status == RsvpStatus.REGISTERED:
        return render(
            request,
            "registrations/already_registered.html",
            {"event": event, "registration": existing},
        )

    if request.method == "GET" and not event.is_registration_allowed:
        return render(
            request,
            "registrations/registrations_closed.html",
            {"event": event},
        )

    instance = existing

    if request.method == "POST":
        song_formset = RegistrationSongFormSet(request.POST, prefix="songs")
        form = EventRegistrationForm(
            request.POST,
            instance=instance,
            event=event,
            user=request.user,
            song_formset=song_formset,
        )

        form_valid = form.is_valid()
        formset_valid = song_formset.is_valid()

        if form_valid and formset_valid:
            with transaction.atomic():
                locked_event = Event.objects.select_for_update().get(pk=event.pk)
                if not locked_event.is_registration_allowed:
                    messages.error(
                        request,
                        _("Registrations are currently closed."),
                    )
                    return render(
                        request,
                        "registrations/registrations_closed.html",
                        {"event": locked_event},
                    )

                current = (
                    EventRegistration.objects.select_for_update()
                    .filter(user=request.user, event=locked_event)
                    .first()
                )
                if current and current.rsvp_status == RsvpStatus.REGISTERED:
                    messages.info(
                        request,
                        _("You are already registered for this event."),
                    )
                    return redirect(
                        "events:register_confirmation", pk=locked_event.pk
                    )

                now = timezone.now()
                registration = form.save(commit=False)
                registration.user = request.user
                registration.event = locked_event
                registration.rsvp_status = RsvpStatus.REGISTERED
                registration.wants_originals_in_jam = form.cleaned_data.get(
                    "wants_originals_in_jam"
                )
                if not registration.join_open_jam:
                    registration.wants_originals_in_jam = None
                registration.instruments_snapshot = _snapshot_instruments(
                    request.user
                )
                registration.experience_level_snapshot = _snapshot_experience_level(
                    request.user
                )
                registration.registered_at = now
                registration.cancelled_at = None
                if current is not None:
                    registration.pk = current.pk
                    registration.first_registered_at = current.first_registered_at
                else:
                    registration.first_registered_at = now
                registration.save()

                wants = bool(registration.wants_originals_in_jam)
                _replace_songs(registration, song_formset, wants)

            messages.success(request, _("You are registered for this event."))
            return redirect("events:register_confirmation", pk=locked_event.pk)

        return _render_register(request, event, form, song_formset)

    form = EventRegistrationForm(instance=instance, event=event, user=request.user)
    initial_songs = song_formset_initial_from_registration(instance)
    song_formset = RegistrationSongFormSet(
        prefix="songs",
        initial=initial_songs,
    )
    return _render_register(request, event, form, song_formset)


@login_required
@require_http_methods(["GET"])
def register_confirmation(request, pk):
    """Idempotent confirmation page (GET only)."""
    event = get_object_or_404(Event, pk=pk)
    registration = get_object_or_404(
        EventRegistration.objects.prefetch_related("songs"),
        user=request.user,
        event=event,
        rsvp_status=RsvpStatus.REGISTERED,
    )
    return render(
        request,
        "registrations/register_confirmation.html",
        {
            "event": event,
            "registration": registration,
            "instrument_labels": _instrument_labels(
                registration.instruments_snapshot,
                request.user.other_instrument,
            ),
            "level_label": _experience_level_label(
                registration.experience_level_snapshot
            ),
        },
    )


@login_required
@require_POST
def cancel(request, pk):
    """Soft-cancel RSVP (POST only)."""
    event = get_object_or_404(Event, pk=pk)
    registration = get_object_or_404(
        EventRegistration,
        user=request.user,
        event=event,
        rsvp_status=RsvpStatus.REGISTERED,
    )
    registration.rsvp_status = RsvpStatus.CANCELLED
    registration.cancelled_at = timezone.now()
    registration.save(update_fields=["rsvp_status", "cancelled_at"])
    messages.success(request, _("Your registration has been cancelled."))
    next_url = request.POST.get("next") or reverse("events:detail", kwargs={"pk": pk})
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        next_url = reverse("events:detail", kwargs={"pk": pk})
    return redirect(next_url)


@login_required
@require_http_methods(["GET"])
def staff_lists(request, pk):
    """Staff lists: Registered and Cancelled for one event."""
    _require_moderator(request.user)
    event = get_object_or_404(Event, pk=pk)
    registered = (
        EventRegistration.objects.filter(
            event=event, rsvp_status=RsvpStatus.REGISTERED
        )
        .select_related("user")
        .prefetch_related("songs")
        .order_by("registered_at")
    )
    cancelled = (
        EventRegistration.objects.filter(
            event=event, rsvp_status=RsvpStatus.CANCELLED
        )
        .select_related("user")
        .prefetch_related("songs")
        .order_by("-cancelled_at")
    )

    def enrich(qs):
        rows = []
        for reg in qs:
            rows.append(
                {
                    "registration": reg,
                    "instrument_labels": _instrument_labels(
                        reg.instruments_snapshot,
                        getattr(reg.user, "other_instrument", ""),
                    ),
                    "level_label": _experience_level_label(
                        reg.experience_level_snapshot
                    ),
                }
            )
        return rows

    return render(
        request,
        "registrations/staff_lists.html",
        {
            "event": event,
            "registered_rows": enrich(registered),
            "cancelled_rows": enrich(cancelled),
        },
    )
