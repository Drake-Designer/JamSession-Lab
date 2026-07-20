"""Public sitemaps for search engines."""

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from events.models import Event

User = get_user_model()


class SiteUrlSitemap(Sitemap):
    """Force absolute URLs from SITE_URL (not the request host / testserver)."""

    def get_protocol(self, protocol=None):
        return urlparse(settings.SITE_URL).scheme or "https"

    def get_domain(self, site=None):
        return urlparse(settings.SITE_URL).netloc


class StaticViewSitemap(SiteUrlSitemap):
    """Marketing and always-public informational pages."""

    changefreq = "weekly"

    def items(self):
        return [
            "pages:home",
            "pages:about",
            "pages:contact",
            "pages:terms",
            "pages:privacy",
            "events:list",
            "gallery:list",
            "community:list",
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == "pages:home":
            return 1.0
        if item in {"events:list", "gallery:list", "community:list"}:
            return 0.9
        if item in {"pages:about", "pages:contact"}:
            return 0.7
        return 0.4


class EventSitemap(SiteUrlSitemap):
    """Active jam session events."""

    changefreq = "daily"
    priority = 0.85

    def items(self):
        return Event.objects.filter(is_active=True).order_by("-starts_at")

    def lastmod(self, obj):
        return obj.updated_at


class ProfileSitemap(SiteUrlSitemap):
    """Public member profiles (verified, active accounts only)."""

    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return (
            User.objects.filter(is_active=True, is_email_verified=True)
            .order_by("username")
            .only("username", "date_joined")
        )

    def lastmod(self, obj):
        return obj.date_joined


sitemaps = {
    "static": StaticViewSitemap,
    "events": EventSitemap,
    "profiles": ProfileSitemap,
}
