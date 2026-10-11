"""Auflagen je Quelle: was PBP bei einer Quelle NICHT tut, auch wenn es technisch ginge (#1189, B78).

Anlass ist jobtic.com (IT-Freelance-Projekte). Die AGB des Betreibers untersagen das automatisierte Auslesen und die
Aufnahme von Kontaktdaten in fremde Datenbanken; die Quelle laeuft deshalb nur ueber den eigenen, angemeldeten Browser
und von Hand gestartet. Eine Auflage, die nur in einer Anleitung an Claude steht, waere keine Kontrolle (Lehre L66):
PBP selbst darf diese Seiten nie abrufen (Anzeigentext nachladen, Aging-Check) und darf aus einem Lauf keine
Kontaktdaten uebernehmen.

Die Daten stehen im Quellenverzeichnis (`SOURCE_REGISTRY[...]["auflagen"]`), neben dem Rest der Quelle. Hier steht nur
die Frage dazu, an EINER Stelle, damit Nachladen, Aging-Check, Anlage und Anleitung nicht je eine eigene Fassung davon
haben:

* `kein_automatischer_abruf` - PBP ruft die Adresse nie selbst ab.
* `keine_kontaktdaten`       - Ansprechpartner aus dem Lauf werden nicht uebernommen; der Mensch traegt sie selbst ein.
* `stellenart`               - Vorgabe fuer die Stellenart, wenn keine andere genannt ist.
* `hinweis`                  - der Auftrag an Claude (Handstart, Seitenzahl, Pausen, was nie uebernommen wird).

Abgrenzung: `url_to_source` ordnet eine Adresse einer Quelle zu, `quellen_texte` sagt dem Menschen, was eine Quelle ist,
`browser_handoff` fuehrt die Quellen auf, die nur im Browser laufen. Dieses Modul beantwortet nur: "Was gilt fuer diese
Quelle oder diese Adresse?"
"""
from __future__ import annotations


def _registry() -> dict:
    # Spaet importiert: `job_scraper` ist gross, und `nachladen` und `url_health` brauchen es sonst nie.
    from ..job_scraper import SOURCE_REGISTRY
    return SOURCE_REGISTRY


def auflagen(quelle: str = "", url: str = "") -> dict:
    """Die Auflagen der Quelle - leer, wenn es keine gibt.

    Die ausdruecklich genannte Quelle zaehlt zuerst; hat sie keine, entscheidet die Adresse. Eine Stelle von jobtic mit
    `quelle='manuell'` oder einer falsch gesetzten Quelle bleibt so trotzdem unter der Auflage.
    """
    registry = _registry()
    schluessel = [str(quelle or "").strip().lower()]
    if url:
        from .url_to_source import detect_source_from_url
        schluessel.append(detect_source_from_url(str(url)))
    for key in schluessel:
        eintrag = registry.get(key) or {}
        gefunden = eintrag.get("auflagen")
        if isinstance(gefunden, dict) and gefunden:
            return gefunden
    return {}


def kein_automatischer_abruf(quelle: str = "", url: str = "") -> bool:
    """Darf PBP diese Adresse NICHT selbst abrufen?"""
    return bool(auflagen(quelle, url).get("kein_automatischer_abruf"))


def keine_kontaktdaten(quelle: str = "", url: str = "") -> bool:
    """Werden Ansprechpartner aus einem Lauf bei dieser Quelle nicht uebernommen?"""
    return bool(auflagen(quelle, url).get("keine_kontaktdaten"))


def sql_ohne_abruf(spalte: str = "url") -> tuple[str, list]:
    """Eine SQL-Bedingung, die Adressen von Quellen ohne automatischen Abruf ausschliesst.

    Fuer Auswahlen mit LIMIT: filtert man erst danach, fuellen Stellen mit Auflage das LIMIT und verdraengen
    jedes Mal dieselben anderen. Rueckgabe: (" AND ...", parameter) - leer, wenn keine Quelle eine Auflage hat.
    `spalte` ist ein fester Spaltenname des Aufrufers, nie eine Eingabe.
    """
    from .url_to_source import hosts_von
    muster: list[str] = []
    for key, eintrag in _registry().items():
        if (eintrag.get("auflagen") or {}).get("kein_automatischer_abruf"):
            muster.extend(hosts_von(key))
    bedingung = "".join(f" AND LOWER({spalte}) NOT LIKE ?" for _ in muster)
    return bedingung, [f"%{m.lower()}%" for m in muster]


def hinweis_fuer_claude(quelle: str = "", url: str = "") -> str:
    """Der Auftrag an Claude zu dieser Quelle - leer, wenn es keinen gibt."""
    return str(auflagen(quelle, url).get("hinweis") or "")
