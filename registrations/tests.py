from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from events.views import event_detail
from pages.views import home

from .forms import EventRegistrationForm, RegistrationSongFormSet
from .models import AttendanceStatus, EventRegistration, RegistrationSong, RsvpStatus

User = get_user_model()


def _make_user(username, *, is_staff=False, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="jam-session-test-pass1",
        display_name=username[:20],
        instruments=extra.pop("instruments", ["electric_guitar", "vocals"]),
        experience_level=extra.pop("experience_level", "intermediate"),
        other_instrument=extra.pop("other_instrument", ""),
        is_staff=is_staff,
        is_email_verified=extra.pop("is_email_verified", True),
        **extra,
    )


def _make_event(**overrides):
    now = timezone.now()
    data = {
        "venue_name": "The Sound House",
        "address": "1 Temple Bar, Dublin",
        "location_url": "https://maps.google.com/?q=Sound+House",
        "starts_at": now + timedelta(days=14),
        "ends_at": now + timedelta(days=14, hours=3),
        "is_active": True,
        "registrations_open": True,
    }
    data.update(overrides)
    return Event.objects.create(**data)


def _song_formset_data(prefix="songs", songs=None, extra_empty=1):
    """Build management form + song rows for the RSVP formset."""
    songs = songs or []
    total = len(songs) + extra_empty
    data = {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for index, song in enumerate(songs):
        data[f"{prefix}-{index}-title"] = song.get("title", "")
        data[f"{prefix}-{index}-song_key"] = song.get("song_key", "")
        data[f"{prefix}-{index}-basic_chords"] = song.get("basic_chords", "")
    for index in range(len(songs), total):
        data[f"{prefix}-{index}-title"] = ""
        data[f"{prefix}-{index}-song_key"] = ""
        data[f"{prefix}-{index}-basic_chords"] = ""
    return data


def _rsvp_post_data(**overrides):
    data = {
        "join_open_mic": "on",
        "join_open_jam": "on",
        "originals_choice": "no",
        "notes": "",
    }
    data.update(_song_formset_data())
    data.update(overrides)
    return data


class EventRegistrationFormTests(TestCase):
    def setUp(self):
        self.event = _make_event()
        self.user = _make_user("player1")

    def test_requires_at_least_one_session(self):
        data = _rsvp_post_data()
        data.pop("join_open_mic")
        data.pop("join_open_jam")
        formset = RegistrationSongFormSet(data, prefix="songs")
        form = EventRegistrationForm(
            data, event=self.event, user=self.user, song_formset=formset
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_originals_yes_requires_at_least_one_song_server_side(self):
        data = _rsvp_post_data(
            join_open_mic="",
            originals_choice="yes",
        )
        # No valid songs in formset
        data.update(_song_formset_data(songs=[], extra_empty=1))
        data["join_open_jam"] = "on"
        formset = RegistrationSongFormSet(data, prefix="songs")
        form = EventRegistrationForm(
            data, event=self.event, user=self.user, song_formset=formset
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_originals_yes_with_song_is_valid(self):
        data = _rsvp_post_data(originals_choice="yes")
        data.update(
            _song_formset_data(
                songs=[
                    {
                        "title": "River Song",
                        "song_key": "G",
                        "basic_chords": "G C D",
                    }
                ],
                extra_empty=0,
            )
        )
        formset = RegistrationSongFormSet(data, prefix="songs")
        form = EventRegistrationForm(
            data, event=self.event, user=self.user, song_formset=formset
        )
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        self.assertTrue(form.cleaned_data["wants_originals_in_jam"])


class EventRegistrationFlowTests(TestCase):
    def setUp(self):
        self.event = _make_event()
        self.user = _make_user("player2")
        self.staff = _make_user("mod_staff", is_staff=True)

    def test_anonymous_redirects_to_account_register_with_next(self):
        url = reverse("events:register", kwargs={"pk": self.event.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:register"), response.url)
        self.assertIn("next=", response.url)

    def test_account_register_shows_event_banner(self):
        next_path = reverse("events:register", kwargs={"pk": self.event.pk})
        response = self.client.get(
            reverse("accounts:register"), {"next": next_path}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "To register for an event you need to create your JamSession Lab account first",
        )

    def test_successful_rsvp_redirects_to_confirmation_prg(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        url = reverse("events:register", kwargs={"pk": self.event.pk})
        response = self.client.post(url, _rsvp_post_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("events:register_confirmation", kwargs={"pk": self.event.pk}),
        )
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        self.assertEqual(reg.rsvp_status, RsvpStatus.REGISTERED)
        self.assertEqual(reg.instruments_snapshot, ["electric_guitar", "vocals"])
        self.assertEqual(reg.experience_level_snapshot, "intermediate")

        # Confirmation GET is idempotent — no duplicate rows
        confirm = self.client.get(
            reverse("events:register_confirmation", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(
            EventRegistration.objects.filter(
                user=self.user, event=self.event
            ).count(),
            1,
        )

    def test_unique_constraint_one_row_per_user_event(self):
        EventRegistration.objects.create(
            user=self.user,
            event=self.event,
            join_open_mic=True,
            rsvp_status=RsvpStatus.REGISTERED,
            instruments_snapshot=["electric_guitar"],
            experience_level_snapshot="intermediate",
            first_registered_at=timezone.now(),
            registered_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            EventRegistration.objects.create(
                user=self.user,
                event=self.event,
                join_open_jam=True,
                rsvp_status=RsvpStatus.REGISTERED,
                instruments_snapshot=["vocals"],
                experience_level_snapshot="beginner",
                first_registered_at=timezone.now(),
                registered_at=timezone.now(),
            )

    def test_edit_registration_updates_sessions(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        register_url = reverse("events:register", kwargs={"pk": self.event.pk})
        self.client.post(register_url, _rsvp_post_data())
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        first_at = reg.first_registered_at
        self.assertTrue(reg.join_open_mic)
        self.assertTrue(reg.join_open_jam)

        edit_url = reverse("events:register_edit", kwargs={"pk": self.event.pk})
        get_response = self.client.get(edit_url)
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "Edit registration")
        self.assertContains(get_response, "Save changes")

        post_data = _rsvp_post_data()
        post_data.pop("join_open_jam")
        post_data["originals_choice"] = ""
        post_data["notes"] = "Changed my mind — Open Mic only."
        response = self.client.post(edit_url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("events:register_confirmation", kwargs={"pk": self.event.pk}),
        )

        reg.refresh_from_db()
        self.assertTrue(reg.join_open_mic)
        self.assertFalse(reg.join_open_jam)
        self.assertIsNone(reg.wants_originals_in_jam)
        self.assertEqual(reg.notes, "Changed my mind — Open Mic only.")
        self.assertEqual(reg.first_registered_at, first_at)
        self.assertEqual(reg.rsvp_status, RsvpStatus.REGISTERED)

    def test_cancel_post_only_and_rejoin_preserves_first_registered_at(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        register_url = reverse("events:register", kwargs={"pk": self.event.pk})
        register_data = _rsvp_post_data(
            originals_choice="yes",
            notes="Bring a spare cable",
        )
        register_data.update(
            _song_formset_data(
                songs=[{"title": "Wonderwall", "song_key": "C", "basic_chords": "C G"}],
                extra_empty=0,
            )
        )
        self.client.post(register_url, register_data)
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        first_at = reg.first_registered_at
        registered_at_before = reg.registered_at
        self.assertEqual(reg.notes, "Bring a spare cable")
        self.assertEqual(reg.songs.count(), 1)

        cancel_url = reverse("events:cancel", kwargs={"pk": self.event.pk})
        self.assertEqual(self.client.get(cancel_url).status_code, 405)

        cancel_response = self.client.post(cancel_url)
        self.assertEqual(cancel_response.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.rsvp_status, RsvpStatus.CANCELLED)
        self.assertIsNotNone(reg.cancelled_at)
        self.assertEqual(reg.first_registered_at, first_at)
        self.assertEqual(reg.notes, "")
        self.assertEqual(reg.songs.count(), 0)

        # Rejoin
        rejoin = self.client.post(
            register_url,
            _rsvp_post_data(join_open_mic="", join_open_jam="on", notes="Back again"),
        )
        self.assertEqual(rejoin.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.rsvp_status, RsvpStatus.REGISTERED)
        self.assertIsNone(reg.cancelled_at)
        self.assertEqual(reg.first_registered_at, first_at)
        self.assertGreaterEqual(reg.registered_at, registered_at_before)
        self.assertEqual(
            EventRegistration.objects.filter(
                user=self.user, event=self.event
            ).count(),
            1,
        )

    def test_post_blocked_when_registrations_closed(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        self.event.registrations_open = False
        self.event.save(update_fields=["registrations_open", "updated_at"])
        response = self.client.post(
            reverse("events:register", kwargs={"pk": self.event.pk}),
            _rsvp_post_data(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrations are currently closed")
        self.assertFalse(
            EventRegistration.objects.filter(
                user=self.user, event=self.event
            ).exists()
        )

    def test_post_blocked_when_event_inactive(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        self.event.is_active = False
        self.event.save(update_fields=["is_active", "updated_at"])
        response = self.client.post(
            reverse("events:register", kwargs={"pk": self.event.pk}),
            _rsvp_post_data(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            EventRegistration.objects.filter(
                user=self.user, event=self.event
            ).exists()
        )

    def test_snapshot_updated_on_reregistration(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        url = reverse("events:register", kwargs={"pk": self.event.pk})
        self.client.post(url, _rsvp_post_data())
        self.client.post(reverse("events:cancel", kwargs={"pk": self.event.pk}))

        self.user.instruments = ["drums"]
        self.user.experience_level = "advanced"
        self.user.save(update_fields=["instruments", "experience_level"])

        self.client.post(url, _rsvp_post_data(join_open_jam="on", join_open_mic=""))
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        self.assertEqual(reg.instruments_snapshot, ["drums"])
        self.assertEqual(reg.experience_level_snapshot, "advanced")

    def test_songs_replaced_on_submit(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        url = reverse("events:register", kwargs={"pk": self.event.pk})
        data = _rsvp_post_data(originals_choice="yes")
        data.update(
            _song_formset_data(
                songs=[
                    {
                        "title": "First",
                        "song_key": "C",
                        "basic_chords": "C F G",
                    }
                ],
                extra_empty=0,
            )
        )
        self.client.post(url, data)
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        self.assertEqual(reg.songs.count(), 1)
        self.assertEqual(reg.songs.first().title, "First")

        self.client.post(reverse("events:cancel", kwargs={"pk": self.event.pk}))
        data2 = _rsvp_post_data(originals_choice="yes")
        data2.update(
            _song_formset_data(
                songs=[
                    {
                        "title": "Second",
                        "song_key": "Am",
                        "basic_chords": "Am G F",
                    }
                ],
                extra_empty=0,
            )
        )
        self.client.post(url, data2)
        reg.refresh_from_db()
        self.assertEqual(reg.songs.count(), 1)
        self.assertEqual(reg.songs.first().title, "Second")

    def test_staff_lists_forbidden_for_member(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        response = self.client.get(
            reverse("events:attendees", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_lists_show_registered_and_cancelled(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        self.client.post(
            reverse("events:register", kwargs={"pk": self.event.pk}),
            _rsvp_post_data(),
        )
        self.client.post(reverse("events:cancel", kwargs={"pk": self.event.pk}))

        self.client.login(username="mod_staff", password="jam-session-test-pass1")
        response = self.client.get(
            reverse("events:attendees", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancellations")
        self.assertContains(response, "@player2")

    def test_post_blocked_when_event_is_full(self):
        self.event.capacity = 1
        self.event.save(update_fields=["capacity", "updated_at"])
        other = _make_user("early_bird")
        EventRegistration.objects.create(
            user=other,
            event=self.event,
            join_open_mic=True,
            rsvp_status=RsvpStatus.REGISTERED,
            instruments_snapshot=["vocals"],
            experience_level_snapshot="beginner",
            first_registered_at=timezone.now(),
            registered_at=timezone.now(),
        )
        self.client.login(username="player2", password="jam-session-test-pass1")
        response = self.client.post(
            reverse("events:register", kwargs={"pk": self.event.pk}),
            _rsvp_post_data(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This event is full")
        self.assertFalse(
            EventRegistration.objects.filter(
                user=self.user, event=self.event, rsvp_status=RsvpStatus.REGISTERED
            ).exists()
        )

    def test_staff_can_set_attendance(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        self.client.post(
            reverse("events:register", kwargs={"pk": self.event.pk}),
            _rsvp_post_data(),
        )
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        self.assertEqual(reg.attendance_status, AttendanceStatus.UNKNOWN)

        self.client.login(username="mod_staff", password="jam-session-test-pass1")
        url = reverse(
            "events:set_attendance",
            kwargs={"pk": self.event.pk, "reg_pk": reg.pk},
        )
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(
            url, {"attendance_status": AttendanceStatus.ATTENDED}
        )
        self.assertEqual(response.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.attendance_status, AttendanceStatus.ATTENDED)

        attendees = self.client.get(
            reverse("events:attendees", kwargs={"pk": self.event.pk})
        )
        self.assertContains(attendees, "Attendance")
        self.assertContains(attendees, "Attended")

    def test_member_cannot_set_attendance(self):
        self.client.login(username="player2", password="jam-session-test-pass1")
        self.client.post(
            reverse("events:register", kwargs={"pk": self.event.pk}),
            _rsvp_post_data(),
        )
        reg = EventRegistration.objects.get(user=self.user, event=self.event)
        response = self.client.post(
            reverse(
                "events:set_attendance",
                kwargs={"pk": self.event.pk, "reg_pk": reg.pk},
            ),
            {"attendance_status": AttendanceStatus.ATTENDED},
        )
        self.assertEqual(response.status_code, 403)


class QueryCountTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.event = _make_event()

    def test_home_view_query_count(self):
        request = self.factory.get("/")
        request.user = User()  # anonymous-like; home does not use user
        # Force anonymous: SimpleLazyObject not needed for home
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        with self.assertNumQueries(2):
            home(request)

    def test_detail_view_query_count_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get(f"/events/{self.event.pk}/")
        request.user = AnonymousUser()
        with self.assertNumQueries(1):
            event_detail(request, pk=self.event.pk)
