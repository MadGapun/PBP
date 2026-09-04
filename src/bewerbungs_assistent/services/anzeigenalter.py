"""Wie alt ist eine Stellenanzeige? (#949 Befund 2, v1.7.26)

PBP kannte bisher nur `found_at` — wann PBP die Stelle GESEHEN hat. Das
ist etwas anderes als ihr Veroeffentlichungsdatum: eine seit einem
halben Jahr laufende Anzeige, die gestern neu gescraped wurde, sah in
PBP taufrisch aus.

Belegter Fall vom 21.08.2026: eine Anzeige lief laut Portal seit sechs
Monaten bei fuenf Bewerbungsklicks. In PBP war davon nichts sichtbar —
aufgefallen ist es nur, weil der Nutzer die Originalanzeige selbst
geoeffnet hat.

Warum das Alter ein eigenstaendiges Signal ist, unabhaengig vom
fachlichen Fit:

* Sechs Monate Laufzeit bei wenigen Klicks deutet auf eine
  Dauerausschreibung ohne konkrete Vakanz — eine Bewerbung landet dort
  in einer Datenbank.
* Oder die Stelle ist real und seit sechs Monaten unbesetzt; dann
  treffen Anforderungen oder Verguetung den Markt nicht.
* Umgekehrt ist eine frische Anzeige der Moment mit der besten Chance.
  Genau das ist die Begruendung des Nutzers dafuer, die manuellen
  Kanaele hoechstens woechentlich zu pruefen: eine Stelle, die er erst
  nach vier Wochen sieht, ist als Bewerbungschance tot.

**Bewusst ein HINWEIS, kein Score-Malus.** Eine lang laufende Anzeige
kann schlicht eine schwer zu besetzende Spezialistenrolle sein, und die
Leitlinie lautet Recall vor Praezision. Dieselbe Zurueckhaltung wie bei
der Entfernungs-Guete (#965): die Luecke wird benannt, nicht gerechnet.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

# Ab hier wird die Laufzeit erwaehnenswert. 90 Tage ist der Wert aus
# dem Issue — lang genug, dass eine normale Vakanz besetzt waere.
SCHWELLE_TAGE = 90

# Feldnamen, unter denen Quellen das Veroeffentlichungsdatum liefern.
# Bewusst breit: welcher Schluessel wirklich kommt, unterscheidet sich
# je Portal und je API-Version. Was nicht passt, wird nicht geraten.
_DATUMS_SCHLUESSEL = (
    # Der Feldname der Bundesagentur, live gegen die API geprueft
    # (v6-Antwort, 04.09.2026). v1.7.26 hatte hier die falsche
    # Wortstellung geraten — die Erkennung feuerte bei der einzigen
    # angebundenen Quelle deshalb NIE. MERKE: Feldnamen einer fremden
    # API nachschlagen, nicht plausibel erfinden; ein defensiver
    # Mehrfachversuch ersetzt keine Pruefung.
    "datumErsteVeroeffentlichung",
    "aktuelleVeroeffentlichungsdatum",
    "ersteVeroeffentlichungsdatum",
    "veroeffentlichungsdatum",
    "publicationDate",
    "datePosted",
    "posted_at",
    "published_at",
    "created_at",
    "date",
)

_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DEUTSCH = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")


def aus_rohdaten(rohdaten: dict) -> Optional[str]:
    """Veroeffentlichungsdatum aus einer Quellen-Antwort lesen.

    Gibt ein ISO-Datum (YYYY-MM-DD) zurueck oder None. Bewusst tolerant
    gegenueber dem Schluesselnamen und streng gegenueber dem Wert: was
    sich nicht als Datum lesen laesst, wird nicht uebernommen. Ein
    falsches Datum waere schlimmer als keines — es wuerde ein
    Frischesignal erfinden.
    """
    if not isinstance(rohdaten, dict):
        return None
    for schluessel in _DATUMS_SCHLUESSEL:
        wert = rohdaten.get(schluessel)
        if not wert:
            continue
        iso = normalisiere(wert)
        if iso:
            return iso
    return None


def normalisiere(wert) -> Optional[str]:
    """Einen Datumswert auf YYYY-MM-DD bringen, oder None."""
    if not wert:
        return None
    text = str(wert).strip()
    m = _ISO.search(text)
    if m:
        try:
            date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except ValueError:
            return None
    m = _DEUTSCH.search(text)
    if m:
        tag, monat, jahr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(jahr, monat, tag).isoformat()
        except ValueError:
            return None
    return None


def alter_tage(veroeffentlicht_am, heute: Optional[date] = None) -> Optional[int]:
    """Wie viele Tage laeuft die Anzeige? None, wenn unbekannt."""
    iso = normalisiere(veroeffentlicht_am)
    if not iso:
        return None
    try:
        gesetzt = datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    tage = ((heute or date.today()) - gesetzt).days
    # Ein Datum in der Zukunft ist ein Datenfehler, kein negatives Alter.
    return tage if tage >= 0 else None


def einordnung(job: dict, heute: Optional[date] = None) -> dict:
    """Alter und Hinweis fuer die Ausgabe.

    Liefert immer ein dict mit `guete`; bei 'unbekannt' wird ausdruecklich
    gesagt, dass `found_at` etwas ANDERES ist — sonst liest der Nutzer
    das Fundatum als Anzeigenalter.
    """
    tage = alter_tage((job or {}).get("veroeffentlicht_am"), heute)
    if tage is None:
        return {
            "guete": "unbekannt",
            "hinweis": ("Die Quelle liefert kein Veroeffentlichungsdatum. "
                        "`found_at` sagt nur, wann PBP die Stelle gesehen "
                        "hat — eine seit Monaten laufende Anzeige sieht "
                        "dort taufrisch aus."),
        }
    erg = {"guete": "belegt", "anzeigenalter_tage": tage}
    if tage >= SCHWELLE_TAGE:
        erg["hinweis"] = (
            f"Die Anzeige laeuft seit {tage} Tagen. Das kann eine "
            "Dauerausschreibung ohne konkrete Vakanz sein — oder eine "
            "real unbesetzte Stelle, deren Anforderungen oder Verguetung "
            "den Markt nicht treffen. Kein Score-Malus, nur ein Hinweis.")
    elif tage <= 7:
        erg["hinweis"] = (
            f"Frisch veroeffentlicht (vor {tage} Tagen) — erfahrungs"
            "gemaess der Moment mit der besten Chance.")
    return erg
