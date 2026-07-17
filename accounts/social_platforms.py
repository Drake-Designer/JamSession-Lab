"""
Detect social / music platforms from a profile URL.

Used on the public profile to show a branded label and icon for each
SocialLink instead of a raw URL.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

from django.utils.translation import gettext_lazy as _

# Soft cap for the edit-profile formset (keeps the public header tidy).
MAX_SOCIAL_LINKS = 5


@dataclass(frozen=True)
class SocialPlatform:
    """Recognised platform for a social / music profile URL."""

    key: str
    label: str


# Host suffixes → platform (checked longest/most specific first via order).
_PLATFORM_HOST_RULES = (
    (("open.spotify.com", "spotify.com", "spotify.link"), "spotify", _("Spotify")),
    (("music.youtube.com", "youtube.com", "youtu.be"), "youtube", _("YouTube")),
    (("instagram.com", "instagr.am"), "instagram", _("Instagram")),
    (("facebook.com", "fb.com", "fb.watch", "fb.me"), "facebook", _("Facebook")),
    (("soundcloud.com",), "soundcloud", _("SoundCloud")),
    (("tiktok.com",), "tiktok", _("TikTok")),
)

_GENERIC = SocialPlatform(key="website", label=_("Website"))


def _host_matches(hostname: str, suffix: str) -> bool:
    return hostname == suffix or hostname.endswith("." + suffix)


def detect_social_platform(url: str) -> SocialPlatform | None:
    """
    Return the platform for a URL, or None if the URL is empty.

    Unknown hosts fall back to a generic "Website" label so the link remains
    clickable and readable.
    """
    raw = (url or "").strip()
    if not raw:
        return None

    try:
        hostname = (urlparse(raw).hostname or "").lower()
    except ValueError:
        return _GENERIC

    if not hostname:
        return _GENERIC

    # Strip a leading "www."
    if hostname.startswith("www."):
        hostname = hostname[4:]

    for suffixes, key, label in _PLATFORM_HOST_RULES:
        if any(_host_matches(hostname, suffix) for suffix in suffixes):
            return SocialPlatform(key=key, label=label)

    return _GENERIC
