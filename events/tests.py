from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from registrations.models import EventRegistration, RsvpStatus

from .models import Event

User = get_user_model()


def _make_user(username, *, is_staff=False, is_superuser=False, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="jam-session-test-pass1",
        display_name=username[:20],
        instruments=extra.pop("instruments", ["electric_guitar"]),
        experience_level=extra.pop("experience_level", "intermediate"),
        is_staff=is_staff,
        is_superuser=is_superuser,
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
        "description": "A night of original music and jamming.",
        "is_active": True,
        "registrations_open": True,
    }
    data.update(overrides)
    return Event.objects.create(**data)


class EventModelTests(TestCase):
    def test_title_generated_from_venue_name(self):
        event = _make_event(venue_name="Whelan's")
        self.assertEqual(event.title, "JamSession @ Whelan's")

    def test_title_regenerated_when_venue_name_changes(self):
        event = _make_event(venue_name="Whelan's")
        event.venue_name = "The Workman's Club"
        event.save()
        event.refresh_from_db()
        self.assertEqual(event.title, "JamSession @ The Workman's Club")

    def test_ends_at_must_be_after_starts_at(self):
        now = timezone.now()
        event = Event(
            venue_name="Bad Times",
            address="Somewhere",
            location_url="https://maps.google.com/?q=x",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(hours=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            event.full_clean()
        self.assertIn("ends_at", ctx.exception.message_dict)

    def test_is_registration_allowed_respects_flags_and_time(self):
        event = _make_event()
        self.assertTrue(event.is_registration_allowed)

        event.registrations_open = False
        event.save(update_fields=["registrations_open", "updated_at"])
        self.assertFalse(event.is_registration_allowed)

        event.registrations_open = True
        event.is_active = False
        event.save(update_fields=["registrations_open", "is_active", "updated_at"])
        self.assertFalse(event.is_registration_allowed)

        past = _make_event(
            venue_name="Past Venue",
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(past.is_upcoming)
        self.assertFalse(past.is_registration_allowed)


class EventViewTests(TestCase):
    def setUp(self):
        self.event = _make_event()
        self.staff = _make_user("staffer", is_staff=True)
        self.member = _make_user("member1")

    def test_detail_public(self):
        response = self.client.get(
            reverse("events:detail", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)

    def test_home_shows_next_event(self):
        response = self.client.get(reverse("pages:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Register")

    def test_public_events_list_shows_active_events(self):
        response = self.client.get(reverse("events:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Register")

    def test_home_shows_view_when_user_already_registered(self):
        EventRegistration.objects.create(
            user=self.member,
            event=self.event,
            join_open_mic=True,
            rsvp_status=RsvpStatus.REGISTERED,
            instruments_snapshot=["electric_guitar"],
            experience_level_snapshot="intermediate",
        )
        self.client.login(username="member1", password="jam-session-test-pass1")
        response = self.client.get(reverse("pages:home"))
        self.assertContains(response, "View")
        self.assertContains(
            response, reverse("events:detail", kwargs={"pk": self.event.pk})
        )
        self.assertNotContains(response, f'href="{reverse("events:register", kwargs={"pk": self.event.pk})}"')

    def test_manage_requires_moderator(self):
        self.client.login(username="member1", password="jam-session-test-pass1")
        response = self.client.get(reverse("events:manage"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_open_manage_list(self):
        self.client.login(username="staffer", password="jam-session-test-pass1")
        response = self.client.get(reverse("events:manage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, reverse("events:create"))
        self.assertContains(response, "Registrations")
        self.assertContains(response, "Cancellations")
        self.assertContains(response, f'id="event-{self.event.pk}"')

    def test_staff_create_requires_moderator(self):
        self.client.login(username="member1", password="jam-session-test-pass1")
        response = self.client.get(reverse("events:create"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_create_event(self):
        self.client.login(username="staffer", password="jam-session-test-pass1")
        now = timezone.now()
        response = self.client.post(
            reverse("events:create"),
            {
                "venue_name": "New Venue",
                "address": "2 Main St",
                "location_url": "https://maps.google.com/?q=new",
                "starts_at": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": (now + timedelta(days=30, hours=2)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "description": "Test",
                "is_active": "on",
                "registrations_open": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Event.objects.get(venue_name="New Venue")
        self.assertEqual(created.title, "JamSession @ New Venue")

    def test_toggle_active_post_only(self):
        self.client.login(username="staffer", password="jam-session-test-pass1")
        url = reverse("events:toggle_active", kwargs={"pk": self.event.pk})
        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 405)
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_active)

        post_response = self.client.post(url)
        self.assertEqual(post_response.status_code, 302)
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_active)

    def test_toggle_registrations_post_only(self):
        self.client.login(username="staffer", password="jam-session-test-pass1")
        url = reverse("events:toggle_registrations", kwargs={"pk": self.event.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.event.refresh_from_db()
        self.assertFalse(self.event.registrations_open)

    def test_toggle_forbidden_for_member(self):
        self.client.login(username="member1", password="jam-session-test-pass1")
        response = self.client.post(
            reverse("events:toggle_active", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_notify_members_requires_moderator(self):
        self.client.login(username="member1", password="jam-session-test-pass1")
        response = self.client.get(
            reverse("events:notify_members", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_notify_members_confirm_page_for_staff(self):
        self.client.login(username="staffer", password="jam-session-test-pass1")
        response = self.client.get(
            reverse("events:notify_members", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email all members?")
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Yes, send emails")

    def test_notify_members_sends_branded_email_to_active_members(self):
        from django.core import mail

        other = _make_user("member2")
        self.client.login(username="staffer", password="jam-session-test-pass1")
        response = self.client.post(
            reverse("events:notify_members", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(response.status_code, 302)
        # staffer + member1 + member2
        self.assertEqual(len(mail.outbox), 3)
        detail_path = reverse("events:detail", kwargs={"pk": self.event.pk})
        for message in mail.outbox:
            self.assertIn("New jam session", message.subject)
            self.assertIn(detail_path, message.body)
            html_parts = [
                content
                for content, mime in message.alternatives
                if mime == "text/html"
            ]
            self.assertEqual(len(html_parts), 1)
            self.assertIn("View event", html_parts[0])
            self.assertIn(detail_path, html_parts[0])
            self.assertIn("#E63946", html_parts[0])
            self.assertIn(self.event.title, html_parts[0])

        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(
            recipients,
            {
                self.staff.email,
                self.member.email,
                other.email,
            },
        )

    def test_manage_page_shows_notify_action(self):
        self.client.login(username="staffer", password="jam-session-test-pass1")
        response = self.client.get(reverse("events:manage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email all members")
        self.assertContains(
            response,
            reverse("events:notify_members", kwargs={"pk": self.event.pk}),
        )
