"""Template context processors for the pages app."""

from __future__ import annotations

import json

from django.conf import settings
from django.templatetags.static import static


def seo(request):
    """
    Site-wide SEO defaults for meta tags, Open Graph, and JSON-LD.

    Templates override title, description, robots, and og:image via blocks.
    """
    site_url = settings.SITE_URL.rstrip("/")
    og_image_path = static(settings.SEO_DEFAULT_OG_IMAGE)
    og_image = f"{site_url}{og_image_path}"

    organisation = {
        "@type": "Organization",
        "@id": f"{site_url}/#organisation",
        "name": settings.SITE_NAME,
        "url": site_url,
        "logo": {
            "@type": "ImageObject",
            "url": og_image,
        },
        "email": settings.CONTACT_EMAIL,
        "sameAs": list(settings.SEO_SAME_AS),
        "areaServed": {
            "@type": "AdministrativeArea",
            "name": "Dublin, Ireland",
        },
    }

    website = {
        "@type": "WebSite",
        "@id": f"{site_url}/#website",
        "name": settings.SITE_NAME,
        "url": site_url,
        "description": settings.DEFAULT_META_DESCRIPTION,
        "inLanguage": "en-GB",
        "publisher": {"@id": f"{site_url}/#organisation"},
    }

    structured_data = {
        "@context": "https://schema.org",
        "@graph": [organisation, website],
    }

    return {
        "seo_site_name": settings.SITE_NAME,
        "seo_site_url": site_url,
        "seo_canonical_url": f"{site_url}{request.path}",
        "seo_default_description": settings.DEFAULT_META_DESCRIPTION,
        "seo_og_image": og_image,
        "seo_og_image_alt": settings.SEO_DEFAULT_OG_IMAGE_ALT,
        "seo_locale": settings.SEO_LOCALE,
        "seo_twitter_handle": settings.SEO_TWITTER_HANDLE,
        "seo_google_verification": settings.GOOGLE_SITE_VERIFICATION,
        "seo_default_json_ld": json.dumps(
            structured_data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
