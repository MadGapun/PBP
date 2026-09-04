"""Wie heisst derselbe Beruf noch? (#969, v1.7.28)

Belegt in #968: eine Pflegekraft traegt "Pflegefachkraft" als
MUSS-Begriff ein — das Naheliegendste. "Gesundheits- und
Krankenpflegerin" bekommt Score 0 und erscheint nicht in der Liste,
obwohl es derselbe Beruf ist (die Amtsbezeichnung vor der
Pflegeberufereform 2020). Das MUSS-Tor kannte Synonyme nur fuer vier
Produktnamen, also ausschliesslich fuer ein technisches Berufsfeld.

**Warum keine gepflegte Liste.** Dieselbe Lehre wie bei
`issue_text_pruefen` (#946) und bei der Kompetenz-Erkennung: eine
kuratierte Synonymliste im Repo deckt genau die Berufsfelder ab, an die
jemand gedacht hat, und ist immer nur so gut wie ihre letzte Pflege.

**Warum nicht BERUFENET.** Naheliegend waere die Klassifikation der
Berufe. Live geprueft am 04.09.2026: die Berufe-Endpunkte der
Bundesagentur antworten mit dem oeffentlichen Jobsuche-Schluessel
durchgehend 403 beziehungsweise 404. Sie sind also nicht ohne
Registrierung erreichbar, und PBP soll ohne Anmeldung laufen.

**Was stattdessen funktioniert.** Die Jobsuche-API selbst liefert zu
jeder Suchanfrage eine Facette `beruf` — die amtlichen
Berufsbezeichnungen der Treffer, nach Haeufigkeit sortiert. Fuer
"Pflegefachkraft" sind das (live gemessen):

    9373  Altenpfleger/in
    7218  Pflegefachmann/-frau (Altenpflege)
    6723  Gesundheits- und Krankenpfleger/in
    1728  Krankenschwester/-pfleger

Also genau die Bezeichnungen, an denen das MUSS-Tor scheiterte. Der
Markt selbst sagt, wie derselbe Beruf noch heisst — ohne Registrierung,
ohne Pflege und in jedem Berufsfeld.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

API_URL = ("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
           "/pc/v6/jobs")
API_KEY = "jobboerse-jobsuche"  # oeffentlich, ohne Registrierung
_USER_AGENT = ("Jobsuche/2.9.3 (de.arbeitsagentur.jobboerse; build:1078; "
               "iOS 15.1.0)")

# Wie viele Bezeichnungen uebernehmen? Genug fuer die gaengigen
# Schreibweisen, wenig genug, dass ein MUSS-Begriff nicht zum Freifahrt-
# schein wird. Die Facette ist nach Haeufigkeit sortiert, die vorderen
# Eintraege sind die belastbaren.
MAX_SYNONYME = 8

# Ab wie vielen Treffern zaehlt eine Bezeichnung? Ein Beruf, der in drei
# von 25.000 Anzeigen vorkommt, ist ein Ausreisser und kein Synonym.
MIN_ANTEIL = 0.02

_cache: dict[str, list[str]] = {}
_cache_lock = threading.Lock()


def aktiv() -> bool:
    """Darf die Abfrage ins Netz? Abschaltbar ueber PBP_BERUFE_LOOKUP=0.

    Die Testsuite schaltet sie in der conftest ab: ein Suchlauf-Test
    darf keine fremde API anrufen, sonst haengt die CI an einer
    Netzwerksperre oder misst fremde Latenz. Tests, die das Verhalten
    pruefen, reichen stattdessen einen eigenen Client herein.
    """
    import os
    return (os.environ.get("PBP_BERUFE_LOOKUP", "1") or "1").strip() != "0"


def _formen(bezeichnung: str) -> list[str]:
    """Amtliche Schreibweise in suchbare Wortformen zerlegen.

    Die Bundesagentur schreibt "Gesundheits- und Krankenpfleger/in",
    "Pflegefachmann/-frau (Altenpflege)" oder
    "Sozialpaedagoge/paedagogin". Als Keyword taugt das nicht.

    Gebaut wird nur, was sich SICHER bilden laesst — was unklar bleibt,
    faellt weg. Eine naive Verkettung erzeugte im ersten Versuch
    "Pflegefachmannfrau" und "Sozialpaedagogepaedagogin"; als
    MUSS-Synonym waere so ein Unwort harmlos (es matcht nie), ein
    FRAGMENT wie "Gesundheits" dagegen gefaehrlich — es traefe jedes
    Kompositum von Gesundheitsmanagement bis Gesundheitsamt.
    """
    if not bezeichnung:
        return []
    # Klammerzusaetze sind Praezisierungen, keine eigene Bezeichnung.
    text = re.sub(r"\([^)]*\)", " ", str(bezeichnung))
    formen: list[str] = []

    for stueck in re.split(r"\s+|,", text):
        stueck = stueck.strip(" ,;")
        if not stueck:
            continue
        # Kompositum-Vorderteil ("Gesundheits-") ist kein Wort.
        if stueck.endswith("-"):
            continue
        if stueck.lower() in ("und", "oder", "fuer", "für", "-"):
            continue

        if "/" not in stueck:
            if len(stueck) >= 4 and stueck[:1].isupper():
                formen.append(stueck)
            continue

        stamm, _, rest = stueck.partition("/")
        stamm = stamm.strip(" -")
        ersetzung = rest.startswith("-")
        rest = rest.strip(" -")
        if len(stamm) >= 4:
            formen.append(stamm)
        if not rest:
            continue

        if ersetzung:
            # "Pflegefachmann/-frau": der Teil hinter dem Schraegstrich
            # ERSETZT die Endung des Stamms.
            if stamm.lower().endswith("mann") and rest.lower() == "frau":
                formen.append(stamm[:-4] + "frau")
            elif len(rest) >= 4 and rest[:1].isupper():
                formen.append(rest)
            continue

        if rest.lower() in ("in", "innen", "r", "e", "er"):
            formen.append(stamm + rest.lower())
            continue

        # "Sozialpaedagoge/paedagogin": der Rest wiederholt einen Teil
        # des Stamms — dort zusammenfuegen statt anhaengen.
        anker = rest[:4].lower()
        i = stamm.lower().find(anker)
        if i > 0:
            formen.append(stamm[:i] + rest)
        elif rest[:1].isupper() and len(rest) >= 4:
            formen.append(rest)

    sauber: list[str] = []
    for f in formen:
        f = f.strip(" -/,;")
        if len(f) < 4 or not f[:1].isupper():
            continue
        if not any(f.lower() == vorhanden.lower() for vorhanden in sauber):
            sauber.append(f)
    return sauber


def _aus_facette(daten: dict) -> list[str]:
    """Amtliche Berufsbezeichnungen aus einer v6-Antwort lesen."""
    facette = ((daten or {}).get("facetten") or {}).get("beruf") or {}
    counts = facette.get("counts") if isinstance(facette, dict) else None
    if not isinstance(counts, dict) or not counts:
        return []
    gesamt = sum(counts.values()) or 1
    gereiht = sorted(counts.items(), key=lambda p: -p[1])
    return [name for name, n in gereiht
            if n / gesamt >= MIN_ANTEIL][:MAX_SYNONYME]


def synonyme(begriff: str, *, client=None) -> list[str]:
    """Wie heisst dieser Beruf sonst noch? Leere Liste, wenn unbekannt.

    Faellt die Quelle aus, wird das protokolliert und PBP arbeitet
    weiter wie bisher — eine fehlende Auskunft darf keine Suche
    verhindern.
    """
    begriff = (begriff or "").strip()
    if len(begriff) < 3:
        return []
    if client is None and not aktiv():
        return []
    schluessel = begriff.lower()
    with _cache_lock:
        if schluessel in _cache:
            return list(_cache[schluessel])

    ergebnis: list[str] = []
    try:
        import httpx
        eigener = client is None
        client = client or httpx.Client(timeout=15)
        try:
            antwort = client.get(
                API_URL,
                params={"was": begriff, "size": 1},
                headers={"X-API-Key": API_KEY, "User-Agent": _USER_AGENT},
            )
            if antwort.status_code == 200:
                amtlich = _aus_facette(antwort.json())
                for bezeichnung in amtlich:
                    for form in _formen(bezeichnung):
                        if (form.lower() != schluessel
                                and not any(form.lower() == e.lower()
                                            for e in ergebnis)):
                            ergebnis.append(form)
            else:
                logger.debug("Berufs-Facette: HTTP %s fuer %r",
                             antwort.status_code, begriff)
        finally:
            if eigener:
                client.close()
    except Exception as exc:  # pragma: no cover — Ausfall darf nie stoeren
        logger.debug("Berufsbezeichnungen nicht abrufbar (%s): %s",
                     begriff, exc)
        return []

    ergebnis = ergebnis[:MAX_SYNONYME * 2]
    with _cache_lock:
        _cache[schluessel] = list(ergebnis)
    return ergebnis


def erweitere(begriffe: list[str], *, client=None) -> dict[str, list[str]]:
    """Zu jedem MUSS-Begriff die bekannten Alternativbezeichnungen.

    Wird EINMAL je Suchlauf aufgerufen und ueber die Kriterien
    weitergereicht — dasselbe Muster wie die IDF-Faktoren (#778). Eine
    Netzabfrage je Stelle und Keyword waere unbrauchbar.
    """
    erg: dict[str, list[str]] = {}
    for b in begriffe or []:
        gefunden = synonyme(b, client=client)
        if gefunden:
            erg[b] = gefunden
    return erg


def cache_leeren() -> None:
    """Nur fuer Tests."""
    with _cache_lock:
        _cache.clear()
