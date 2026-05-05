"""Typisierte ID-Praefixe (v1.7.0 #505).

PBP nutzt 8-stellige Hex-IDs fuer alle Entitaetstypen — Bewerbungen, Stellen,
Dokumente, Termine, Events, Profile usw. Sie sehen identisch aus, was zu
Verwechslungen fuehrt ("d60ac54b" — Dokument oder Bewerbung?").

Diese Datei stellt **Variante A** aus #505 bereit: nicht-breaking
typisierte Praefixe bei Outputs, beide Formen werden bei Inputs akzeptiert.

Beispiel:

    >>> format_id(IdKind.APPLICATION, "42061e46")
    'APP-42061e46'
    >>> parse_id("APP-42061e46")
    (<IdKind.APPLICATION: 'APP'>, '42061e46')
    >>> parse_id("42061e46")
    (None, '42061e46')
    >>> validate_id(IdKind.APPLICATION, "DOC-d60ac54b")
    Traceback (most recent call last):
        ...
    TypedIdMismatch: Erwartet APP-, bekam DOC-d60ac54b
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IdKind(str, Enum):
    """Bekannte Entitaets-Typen mit ihren Praefixen."""

    APPLICATION = "APP"   # applications.id (Bewerbung)
    JOB = "JOB"           # jobs.hash (Stelle) — public-Form ohne profile_id
    DOCUMENT = "DOC"      # documents.id
    EVENT = "EVT"         # application_events.id (Timeline-Eintrag)
    APPOINTMENT = "APT"   # application_meetings.id (Termin/Interview)
    EMAIL = "EML"         # application_emails.id
    PROFILE = "PRO"       # profile.id
    POSITION = "POS"      # positions.id
    PROJECT = "PRJ"       # projects.id
    SKILL = "SKL"         # skills.id
    EDUCATION = "EDU"     # education.id
    FOLLOWUP = "FUP"      # follow_ups.id


# Reverse-Lookup
_PREFIX_TO_KIND = {k.value: k for k in IdKind}


@dataclass
class TypedIdMismatch(Exception):
    """Wird geworfen wenn ein Input mit falschem Typ-Praefix kommt."""
    expected: IdKind
    got_prefix: str
    got_raw: str

    def __str__(self) -> str:
        return (
            f"Erwartet {self.expected.value}-, bekam "
            f"{self.got_prefix}-{self.got_raw}"
        )


def format_id(kind: IdKind, raw: Optional[str]) -> Optional[str]:
    """Formatiert eine Hex-ID mit Typ-Praefix.

    None bleibt None. Wenn raw bereits einen Praefix hat, wird der entfernt
    und durch den richtigen ersetzt (defensiv gegen doppeltes Praefixieren).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return s
    # Wenn schon ein bekannter Praefix dran ist: strippen
    if "-" in s:
        head, _, tail = s.partition("-")
        if head.upper() in _PREFIX_TO_KIND:
            s = tail
    return f"{kind.value}-{s}"


def parse_id(value: Optional[str]) -> tuple[Optional[IdKind], str]:
    """Zerlegt eine moeglicherweise typisierte ID in (Kind|None, Raw-Hex).

    Akzeptiert: 'APP-42061e46' → (APPLICATION, '42061e46')
                '42061e46'     → (None, '42061e46')
                None oder ''   → (None, '')
    """
    if value is None:
        return None, ""
    s = str(value).strip()
    if not s:
        return None, ""
    if "-" in s:
        head, _, tail = s.partition("-")
        kind = _PREFIX_TO_KIND.get(head.upper())
        if kind is not None:
            return kind, tail
    return None, s


def validate_id(expected: IdKind, value: Optional[str]) -> str:
    """Pruefe dass die ID zum erwarteten Typ passt, sonst werfen.

    Wenn die ID kein Praefix hat, wird das durchgewunken (Variante A:
    Tools akzeptieren beide Formen). Wenn sie ein anderes Praefix hat,
    wird `TypedIdMismatch` geworfen mit klarer Meldung.

    Gibt das raw-Hex (ohne Praefix) zurueck.
    """
    kind, raw = parse_id(value)
    if kind is None:
        return raw
    if kind != expected:
        raise TypedIdMismatch(
            expected=expected,
            got_prefix=kind.value,
            got_raw=raw,
        )
    return raw


def strip_prefix(value: Optional[str]) -> str:
    """Entfernt Praefix wenn vorhanden, gibt das raw-Hex zurueck.

    Convenience-Helper fuer Stellen, die nur die rohe ID brauchen
    ohne den Typ zu pruefen.
    """
    _, raw = parse_id(value)
    return raw
