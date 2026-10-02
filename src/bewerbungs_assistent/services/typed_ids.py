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
    CONTACT = "CON"       # contacts.id (#684: CON-Prefix muss beim Input akzeptiert werden)


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


def kurz_job_kennung(job_hash: Optional[str], laenge: int = 8) -> str:
    """Die Kurz-Kennung einer Stelle — aus dem OEFFENTLICHEN Teil des Hashes.

    v1.7.92 (#1029): gespeicherte Hashes haben die Form
    `<Profil, 8 Zeichen>:<Stelle, 12 Zeichen>`. Wo der Speicherwert mit
    `[:8]` gekuerzt wurde, kam deshalb IMMER der Profil-Praefix heraus:
    `gehaelter_neu_auswerten` zeigte fuenfzehnmal dieselbe Kennung, und
    alle Lernereignisse `auto_dismiss_zurueckgeholt` trugen dieselbe
    `entity_id`. Schlimmer noch: als Eingabe traf diese Kennung ueber den
    Praefix-Rueckfall von `_find_job_row` irgendeine Stelle des Profils.

    Fuer einen oeffentlichen Hash (ohne Doppelpunkt) ist das Ergebnis
    dasselbe wie `[:8]` — die Funktion ist also fuer beide Formen richtig
    und muss nicht wissen, welche sie bekommt.
    """
    if not job_hash:
        return ""
    return str(job_hash).split(":", 1)[-1][:laenge]


def strip_prefix(value: Optional[str]) -> str:
    """Entfernt Praefix wenn vorhanden, gibt das raw-Hex zurueck.

    Convenience-Helper fuer Stellen, die nur die rohe ID brauchen
    ohne den Typ zu pruefen.
    """
    _, raw = parse_id(value)
    return raw


# ── Eine Stelle fuer alle Werkzeuge (#1148 Punkt 9) ────────────────────────────────────────────
#
# PBP GIBT typisierte Kennungen aus (`APP-42061e46`, `hash_typed` mit `JOB-`), aber nur einzelne
# Werkzeuge NAHMEN sie an: `meetings_anzeigen(bewerbung_id='APP-…')` antwortete „Bewerbung nicht
# gefunden“, `todos_anzeigen` und `skill_zeitraeume_anzeigen` antworteten leer, `fit_analyse(JOB-…)`
# wurde abgewiesen. Statt 250 Werkzeuge einzeln anzufassen, entfernt `normalisiere_argumente` das
# Praefix an EINER Stelle (der Middleware in `server.py`), bevor ein Werkzeug die Argumente sieht.

#: Wie die Art in einer Fehlermeldung heisst.
ART_NAMEN = {
    IdKind.APPLICATION: "Bewerbungs-Kennung",
    IdKind.JOB: "Stellen-Kennung",
    IdKind.DOCUMENT: "Dokument-Kennung",
    IdKind.EVENT: "Verlaufs-Kennung",
    IdKind.APPOINTMENT: "Termin-Kennung",
    IdKind.EMAIL: "E-Mail-Kennung",
    IdKind.PROFILE: "Profil-Kennung",
    IdKind.POSITION: "Positions-Kennung",
    IdKind.PROJECT: "Projekt-Kennung",
    IdKind.SKILL: "Skill-Kennung",
    IdKind.EDUCATION: "Ausbildungs-Kennung",
    IdKind.FOLLOWUP: "Nachfass-Kennung",
    IdKind.CONTACT: "Kontakt-Kennung",
}

#: Welcher Parameter welche Art Kennung traegt. Ein Parameter, der hier fehlt, wird nicht angefasst.
PARAMETER_ARTEN = {
    "bewerbung_id": IdKind.APPLICATION,
    "application_id": IdKind.APPLICATION,
    "job_hash": IdKind.JOB,
    "stellen_hash": IdKind.JOB,
    "hash_a": IdKind.JOB,
    "hash_b": IdKind.JOB,
    "master_hash": IdKind.JOB,
    "duplikat_hash": IdKind.JOB,
    "dokument_id": IdKind.DOCUMENT,
    "document_id": IdKind.DOCUMENT,
    "document_ids": IdKind.DOCUMENT,
    "meeting_id": IdKind.APPOINTMENT,
    "termin_ids": IdKind.APPOINTMENT,
    "master_id": IdKind.APPOINTMENT,
    "duplikat_id": IdKind.APPOINTMENT,
    "email_id": IdKind.EMAIL,
    "event_id": IdKind.EVENT,
    "profil_id": IdKind.PROFILE,
    "position_id": IdKind.POSITION,
    "projekt_id": IdKind.PROJECT,
    "skill_id": IdKind.SKILL,
    "follow_up_id": IdKind.FOLLOWUP,
    "kontakt_id": IdKind.CONTACT,
}

#: Parameter, die je nach Aufruf verschiedene Arten tragen (`profil_bearbeiten(bereich=…, element_id=…)`,
#: `kontakt_verknuepfen(ziel_id=…)`, `positionen_anzeigen(nur_id=…)` fuer Position ODER Ausbildung):
#: das Praefix faellt weg, ohne die Art zu pruefen.
PARAMETER_BELIEBIG = frozenset({"element_id", "ziel_id", "nur_id"})

#: Parameter mit Kennungs-Namen, die KEINE typisierte Form haben (ein Praefix gibt es dort nicht).
#: Steht ein neuer Kennungs-Parameter weder hier noch oben, schlaegt ein Test an: dann ist zu
#: entscheiden, ob es eine typisierte Form gibt.
OHNE_TYPISIERUNG = frozenset({
    "todo_id", "grund_id", "zeitraum_id", "referenz_id", "reflexion_id", "kosten_id", "titel_id",
    "kategorie_id", "link_id", "entry_id", "extraction_id", "version_id", "befund_id", "hint_id",
    "erkenntnis_id", "geo_id", "job_id",
    # nur 1.8-Linie: `custom_quelle_loeschen(quelle_id)` — die Kennung einer Custom-Quelle ist frei vergeben
    "quelle_id",
    # nur 1.8-Linie: `mail_quelle_einstellen(freigabe_id)` (#947) — die Kennung einer Ordner-Freigabe (`mo_…`) ist rein intern
    "freigabe_id",
    # nur 1.8-Linie: Firmen-Stammsatz (#1080) - Kennungen sind intern (`fi_...`), Schreibweisen zaehlen als Zahl
    "firma_id", "alias_id", "mutterfirma_id",
})


class FalscheKennung(ValueError):
    """Eine Kennung der falschen Art (zum Beispiel `DOC-…` statt `APP-…`)."""


def _eine_kennung(parameter: str, wert, erwartet: Optional[IdKind]):
    if not isinstance(wert, str):
        return wert
    art, roh = parse_id(wert)
    if art is None:
        return wert
    if erwartet is not None and art != erwartet:
        raise FalscheKennung(
            f"'{parameter}' erwartet eine {ART_NAMEN[erwartet]} ({erwartet.value}-…); "
            f"'{wert.strip()}' ist eine {ART_NAMEN[art]} ({art.value}-…). Nimm die Kennung "
            f"aus dem passenden Feld der Antwort."
        )
    return roh


def normalisiere_argumente(arguments) -> Optional[dict]:
    """Entfernt das Typ-Praefix aus den Kennungs-Parametern eines Werkzeugaufrufs (#1148 Punkt 9).

    Gibt ein NEUES Dict zurueck, wenn sich etwas geaendert hat, sonst `None`. Die Kennung der
    falschen Art (`DOC-…` fuer `bewerbung_id`) wirft `FalscheKennung` mit einer Meldung, die sagt,
    was erwartet wurde — statt eines irrefuehrenden „nicht gefunden“. Nur Zeichenketten mit einem
    BEKANNTEN Praefix und Bindestrich werden angefasst; eine Hex-Kennung hat keinen.
    """
    if not isinstance(arguments, dict) or not arguments:
        return None
    ersatz = {}
    for name, wert in arguments.items():
        if name in PARAMETER_BELIEBIG:
            erwartet = None
        elif name in PARAMETER_ARTEN:
            erwartet = PARAMETER_ARTEN[name]
        else:
            continue
        if isinstance(wert, (list, tuple)):
            neu = [_eine_kennung(name, w, erwartet) for w in wert]
            if neu != list(wert):
                ersatz[name] = neu
        else:
            neu = _eine_kennung(name, wert, erwartet)
            if neu != wert:
                ersatz[name] = neu
    if not ersatz:
        return None
    return {**arguments, **ersatz}
