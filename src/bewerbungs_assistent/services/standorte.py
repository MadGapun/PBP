"""Mehrere Standorte in einer Anzeige — der naechste zaehlt (#1082 AK 3).

Gemeldet am 23.09.2026: eine Stelle trug im Ortsfeld einen Ort in rund
450 km Entfernung, im Anzeigentext stand "Standorte: ... oder <Ort im
Umkreis>". PBP rechnete mit dem Ortsfeld, und die Stelle galt als weit
weg — obwohl sie am Wohnort zu besetzen gewesen waere.

**Was dieses Modul tut.** Es sucht im Anzeigentext Ortsangaben, aber nur
in einem ausdruecklichen Standort-Zusammenhang ("Standort(e)",
"Einsatzort", "Arbeitsort", "Dienstort", "Niederlassung",
"wahlweise in", "hybrid von"). Ein Ortsname irgendwo im Fliesstext
("Kunden in ganz Europa, Hauptsitz in ...") sagt nichts darueber, wo
die Stelle zu besetzen ist.

**Woher die Koordinaten kommen.** Aus einem Ortsverzeichnis, das PBP
schon kennt: die Orte der Stellen im Bestand, die bereits geocodet sind
(`jobs.lat/lon`, #965). Ein Score darf nicht an einer Netzabfrage
haengen (v1.7.36 MERKE 3) — dieselbe Stelle haette sonst online einen
anderen Wert als offline. **Die Grenze gehoert gesagt:** ein Ort, den
PBP noch nie gesehen hat, wird nicht nachgeschlagen. Er zaehlt dann
nicht, und die Entfernung bleibt die des Ortsfelds, also das
Verhalten von vorher.

**Wer es fragt.** Gerechnet wird allein in `entfernung.preis_km` — der
einen Stelle, die entscheidet, gegen welche Zahl gerechnet wird (#950
AK 6). Die Liste zeigt den Ort ueber `indikatoren.anhaengen`. Das
Verzeichnis reist ueber die Kriterien (`_standorte`, gesetzt in
`scoring_kriterien.fuer_scoring`), und zwar nur mit Inhalt
(v1.7.100 MERKE 6).
"""
from __future__ import annotations

import logging
import math
import re

logger = logging.getLogger(__name__)

# Nur hinter diesen Woertern steht eine Ortsangabe, die die Stelle meint.
_KONTEXT = re.compile(
    r"(?:\b(?:weitere[nr]?\s+)?(?:standort(?:e|en)?|einsatzort(?:e)?|"
    r"arbeitsort(?:e)?|dienstort(?:e)?|niederlassung(?:en)?)\b"
    r"\s*(?:in\s+|:\s*|-\s+|–\s*)?"
    r"|\bwahlweise\s+(?:in|am\s+standort)\s+"
    r"|\bhybrid\s+(?:von|ab|in)\s+)"
    r"([^\n.;!?]{2,160})",
    re.IGNORECASE)

_TRENNER = re.compile(r",|/|\||\bund\b|\boder\b|\bsowie\b|\bbzw\b", re.IGNORECASE)
_KLAMMER = re.compile(r"[(\[][^)\]]*[)\]]")
_CACHE: dict = {}


def _schluessel(ort: str) -> str:
    """Der Vergleichsschluessel eines Ortes: klein, ohne Zusaetze."""
    from .geocoding_service import normalisiere_ort
    teil = normalisiere_ort(str(ort or "")).split(",")[0]
    return re.sub(r"\s+", " ", teil).strip(" -–").lower()


def verzeichnis(db) -> dict:
    """Die Orte, zu denen PBP Koordinaten kennt: {schluessel: [lat, lon]}.

    Ein Schluessel mit Ziffern (Postleitzahl) oder unter drei Zeichen
    ist kein brauchbarer Ortsname — er traefe beliebige Textstellen.
    """
    try:
        conn = db.connect()
        # Zwischengespeichert, bis auf der Verbindung geschrieben wird:
        # die Scoring-Regler fragen je Stelle, und dieselbe Abfrage
        # tausendmal waere spuerbar. `total_changes` kostet keine Abfrage.
        schluessel = (str(getattr(db, "db_path", "")), id(conn),
                      conn.total_changes)
        if _CACHE.get("schluessel") == schluessel:
            return _CACHE["orte"]
        zeilen = conn.execute(
            "SELECT DISTINCT location, lat, lon FROM jobs "
            "WHERE lat IS NOT NULL AND lon IS NOT NULL "
            "AND location IS NOT NULL AND location != ''").fetchall()
    except Exception as exc:  # pragma: no cover — nie eine Liste stoppen
        logger.debug("Ortsverzeichnis nicht lesbar: %s", exc)
        return {}
    orte: dict = {}
    for location, lat, lon in zeilen:
        k = _schluessel(location)
        if len(k) < 3 or any(z.isdigit() for z in k):
            continue
        orte.setdefault(k, [float(lat), float(lon)])
    _CACHE.clear()
    _CACHE.update(schluessel=schluessel, orte=orte)
    return orte


def genannte_orte(text: str) -> list[str]:
    """Die Ortsangaben im Standort-Zusammenhang, in Reihenfolge."""
    gefunden: list[str] = []
    for treffer in _KONTEXT.finditer(str(text or "")):
        abschnitt = _KLAMMER.sub(" ", treffer.group(1))
        for teil in _TRENNER.split(abschnitt):
            name = re.sub(r"\s+", " ", teil).strip(" :-–\t")
            if name and name.lower() not in (g.lower() for g in gefunden):
                gefunden.append(name)
    return gefunden


def _luftlinie(a, b) -> float:
    """Grosskreis-Entfernung in km — ohne Abhaengigkeit, auf 0,5 % genau."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return round(2 * 6371.0 * math.asin(min(1.0, math.sqrt(h))), 1)


def naechster(job, criteria) -> dict | None:
    """Der naechstgelegene weitere Standort — oder None.

    Nur ein Standort, der NAEHER liegt als das Ortsfeld, zaehlt. Einer,
    der weiter weg liegt, aendert nichts, und ihn zu nennen waere
    Rauschen.
    """
    if not isinstance(job, dict) or not isinstance(criteria, dict):
        return None
    orte = criteria.get("_standorte") or {}
    try:
        heim = (float(criteria["standort_lat"]), float(criteria["standort_lon"]))
    except (KeyError, TypeError, ValueError):
        return None
    if not orte:
        return None
    eigener = _schluessel(job.get("location") or "")
    bester = None
    for name in genannte_orte(job.get("description") or ""):
        k = _schluessel(name)
        if not k or k == eigener or k not in orte:
            continue
        km = _luftlinie(heim, orte[k])
        if bester is None or km < bester["luftlinie_km"]:
            bester = {"ort": name, "luftlinie_km": km}
    if bester is None:
        return None
    try:
        eigen_km = float(job.get("distance_km"))
    except (TypeError, ValueError):
        eigen_km = None
    if eigen_km is not None and bester["luftlinie_km"] >= eigen_km:
        return None
    return bester
