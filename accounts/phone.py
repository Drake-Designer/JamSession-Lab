"""
Phone number helpers: country calling codes and E.164 combine/split.

Stored on the User model as a single E.164-style string (e.g. +353871234567).
Registration and profile forms collect country code + national number separately.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .validators import phone_number_validator

# Default for JamSession Lab (Ireland-based).
DEFAULT_PHONE_COUNTRY_CODE = "+353"

# Curated list: Ireland first, then alphabetical by country name.
# Values are unique dialling prefixes including the leading +.
COUNTRY_CALLING_CODES: list[tuple[str, str]] = [
    ("+353", _("Ireland (+353)")),
    ("+61", _("Australia (+61)")),
    ("+43", _("Austria (+43)")),
    ("+32", _("Belgium (+32)")),
    ("+55", _("Brazil (+55)")),
    ("+359", _("Bulgaria (+359)")),
    ("+1", _("Canada / USA (+1)")),
    ("+385", _("Croatia (+385)")),
    ("+357", _("Cyprus (+357)")),
    ("+420", _("Czechia (+420)")),
    ("+45", _("Denmark (+45)")),
    ("+372", _("Estonia (+372)")),
    ("+358", _("Finland (+358)")),
    ("+33", _("France (+33)")),
    ("+49", _("Germany (+49)")),
    ("+30", _("Greece (+30)")),
    ("+36", _("Hungary (+36)")),
    ("+39", _("Italy (+39)")),
    ("+371", _("Latvia (+371)")),
    ("+370", _("Lithuania (+370)")),
    ("+352", _("Luxembourg (+352)")),
    ("+356", _("Malta (+356)")),
    ("+31", _("Netherlands (+31)")),
    ("+64", _("New Zealand (+64)")),
    ("+48", _("Poland (+48)")),
    ("+351", _("Portugal (+351)")),
    ("+40", _("Romania (+40)")),
    ("+421", _("Slovakia (+421)")),
    ("+386", _("Slovenia (+386)")),
    ("+34", _("Spain (+34)")),
    ("+46", _("Sweden (+46)")),
    ("+41", _("Switzerland (+41)")),
    ("+90", _("Türkiye (+90)")),
    ("+380", _("Ukraine (+380)")),
    ("+44", _("United Kingdom (+44)")),
]

# Longest prefixes first so +353 wins over +35, +1, etc.
_CODES_BY_LENGTH = tuple(
    sorted(
        {code for code, _label in COUNTRY_CALLING_CODES},
        key=len,
        reverse=True,
    )
)

_DIGITS_AND_SPACES = re.compile(r"[\s\-().]")


def normalise_national_number(national_number: str) -> str:
    """Strip spaces/punctuation and a single leading trunk 0 (e.g. 087 → 87)."""
    cleaned = _DIGITS_AND_SPACES.sub("", (national_number or "").strip())
    if cleaned.startswith("0"):
        cleaned = cleaned.lstrip("0")
    return cleaned


def combine_phone_number(country_code: str, national_number: str) -> str:
    """Build an E.164-style string from country code + national digits."""
    code = (country_code or "").strip()
    if code and not code.startswith("+"):
        code = f"+{code}"
    national = normalise_national_number(national_number)
    return f"{code}{national}"


def split_phone_number(phone_number: str) -> tuple[str, str]:
    """
    Split a stored E.164 phone into (country_code, national_number).

    Falls back to Ireland (+353) when the prefix is unknown or empty.
    """
    phone = _DIGITS_AND_SPACES.sub("", (phone_number or "").strip())
    if not phone:
        return DEFAULT_PHONE_COUNTRY_CODE, ""

    if not phone.startswith("+"):
        return DEFAULT_PHONE_COUNTRY_CODE, normalise_national_number(phone)

    for code in _CODES_BY_LENGTH:
        if phone.startswith(code):
            return code, phone[len(code) :]

    # Unknown international prefix — keep digits after + as the national part
    # and default the selector to Ireland so the form still renders cleanly.
    return DEFAULT_PHONE_COUNTRY_CODE, phone.lstrip("+")


def validate_combined_phone(country_code: str, national_number: str) -> str:
    """
    Combine, validate, and return the E.164 phone string.

    Raises ValidationError with a user-facing message on failure.
    """
    if not (national_number or "").strip():
        raise ValidationError(_("Enter your phone number."))

    combined = combine_phone_number(country_code, national_number)
    if len(combined) > 15:
        raise ValidationError(
            _(
                "That phone number is too long. Use your country code and "
                "local number only (no spaces)."
            )
        )
    try:
        phone_number_validator(combined)
    except ValidationError as exc:
        raise ValidationError(
            _(
                "Enter a valid phone number using digits only "
                "(e.g. 87 123 4567 for an Irish mobile)."
            )
        ) from exc
    return combined
