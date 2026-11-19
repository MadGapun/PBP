"""Die Art einer Station im Lebenslauf (#1374).

Abgrenzung zu `services/stellenart.py`: dort steht, welche Art von
STELLENANZEIGE gesucht wird (Anstellungsform und Umfang einer Anzeige,
Suchprofil). Hier steht, wie eine STATION im eigenen Lebenslauf heisst
(`positions.employment_type`). Beide Listen duerfen sich ueberschneiden
(festanstellung, freelance, praktikum, werkstudent), gehoeren aber
verschiedenen Fragen und werden nicht gegeneinander geprueft.

PBP richtet sich auch an Menschen mit Ehrenamt, Pflegezeit, Elternzeit
und Luecken. Ein Wert ausserhalb dieser Liste wird NICHT verworfen und
nicht umgedeutet: er wird gespeichert und in der Antwort gemeldet
(Lehre L7: Unbekannt ist ein eigener Zustand).
"""
from __future__ import annotations

# Wert (Umschrift, wird gespeichert) -> sichtbarer Text
STATIONSARTEN: dict[str, str] = {
    "festanstellung": "Festanstellung",
    "teilzeit": "Teilzeit",
    "vollzeit": "Vollzeit",
    "freelance": "Freelance",
    "praktikum": "Praktikum",
    "werkstudent": "Werkstudent",
    "ehrenamt": "Ehrenamt",
    "elternzeit": "Elternzeit",
    "pflegezeit": "Pflegezeit",
    "weiterbildung": "Weiterbildung",
    "auszeit": "Auszeit",
}

# Schreibweisen, die eindeutig eine der Arten meinen.
_ALIASE = {
    "ehrenamtlich": "ehrenamt", "freiwilligenarbeit": "ehrenamt",
    "freiberuflich": "freelance", "freiberufler": "freelance",
    "selbststaendig": "freelance", "selbstaendig": "freelance",
    "praktikant": "praktikum", "praktikantin": "praktikum",
    "werkstudentin": "werkstudent",
    "erziehungszeit": "elternzeit",
    "pflege": "pflegezeit", "angehoerigenpflege": "pflegezeit",
    "fortbildung": "weiterbildung", "umschulung": "weiterbildung",
    "sabbatical": "auszeit", "luecke": "auszeit",
    "festangestellt": "festanstellung", "angestellt": "festanstellung",
}

STANDARD = "festanstellung"


def _schluessel(wert) -> str:
    text = str(wert or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return text


def pruefen(wert) -> tuple[str, str]:
    """Liefert (zu speichernder Wert, Hinweis). Der Hinweis ist leer, wenn alles passt.

    Leer ergibt die Vorgabe. Eine bekannte Schreibweise wird auf den Wert
    der Liste gebracht (der Hinweis nennt es). Alles andere bleibt, wie es
    kam, und der Hinweis sagt, dass es nicht zur Liste gehört.
    """
    roh = str(wert or "").strip()
    if not roh:
        return STANDARD, ""
    key = _schluessel(roh)
    if key in STATIONSARTEN:
        return key, ""
    if key in _ALIASE:
        ziel = _ALIASE[key]
        return ziel, f"Anstellungsart '{roh}' als '{ziel}' gespeichert."
    return roh, (
        f"Anstellungsart '{roh}' gehört nicht zur Liste "
        f"({', '.join(STATIONSARTEN)}); sie wurde unverändert gespeichert "
        "und erscheint so im Dashboard und im Lebenslauf. Passt eine der "
        "Arten, ändere sie mit profil_bearbeiten(bereich='position', "
        "aktion='aendern', daten={'employment_type': ...}).")


def bezeichnung(wert) -> str:
    """Sichtbarer Text einer Art; Unbekanntes erscheint, wie es gespeichert ist."""
    roh = str(wert or "").strip()
    return STATIONSARTEN.get(_schluessel(roh), roh)
