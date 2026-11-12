"""Passt eine Stelle zu diesen Bedingungen? - EINE Funktion (#1307, #1308).

Die Frage stellen drei Wege:

* `stellen_bulk_bewerten` (einmaliges Aussortieren oder Zurueckholen nach
  Filtern) - bis v1.8.1 stand die Regel dort als innere Funktion
  `_matches`;
* gespeicherte **Ansichten** (`stellen_anzeigen(ansicht=...)`, die Auswahl im
  Stellen-Tab);
* gespeicherte **Regeln**, die neue Treffer nach jeder Suche aussortieren
  (`gespeicherte_filter.py`).

Alle drei rufen `passt` mit denselben Bedingungen. Eine zweite Fassung waere
die Lage aus #963 (dieselbe Frage, verschiedene Antworten).

## Bedingungen

Alle optional, verknuepft mit UND:

* ``min_score`` / ``max_score`` - Punktebereich (gespeicherter Wert der Stelle)
* ``min_alter_tage`` / ``max_alter_tage`` - Tage seit dem Fund (`found_at`);
  eine Stelle ohne Funddatum faellt bei einer Altersbedingung heraus
* ``quelle`` - wie in der Datenbank (#557): mit Unterstrich, ``manuell`` und
  ``google_jobs`` genau, sonst als Teil ("linkedin" trifft "jobspy_linkedin")
* ``firma`` - Teil des Firmennamens, ohne Gross/Klein
* ``titel_enthaelt`` - ALLE Begriffe im Titel
* ``titel_enthaelt_nicht`` - KEINER der Begriffe im Titel
* ``beschreibung_enthaelt`` - ALLE Begriffe in der Beschreibung (neu)
* ``beschreibung_enthaelt_nicht`` - KEINER der Begriffe in der Beschreibung
* ``sprache`` - Liste aus `sprache.SPRACHEN` (neu, #1308); die Sprache wird
  beim Lesen erkannt. ``unbekannt`` trifft nur, wenn es ausdruecklich in der
  Liste steht.

Abgrenzung: `stellen_filter_standard.py` speichert die VOREINSTELLUNG der
Filter im Stellen-Tab (welche Schalter beim Oeffnen gesetzt sind);
`stellen_liste.py` filtert und sortiert die Liste des Stellen-Tabs und ruft
fuer Ansicht und Sprache diese Funktion; `gespeicherte_filter.py` haelt
benannte Bedingungen als Ansicht oder Regel.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from . import sprache as _sprache

#: Die Bedingungen und ihr Typ. Eine Liste, damit Werkzeug, Speicher und
#: Oberflaeche dieselben Namen kennen.
ZAHLEN = ("min_score", "max_score", "min_alter_tage", "max_alter_tage")
TEXTE = ("quelle", "firma")
LISTEN = ("titel_enthaelt", "titel_enthaelt_nicht", "beschreibung_enthaelt",
          "beschreibung_enthaelt_nicht", "sprache")
BEDINGUNGEN = ZAHLEN + TEXTE + LISTEN

#: Kurztext je Bedingung (Klartext-Beschreibung einer gespeicherten Ansicht).
_KLARTEXT = {
    "min_score": "mindestens {} Punkte",
    "max_score": "höchstens {} Punkte",
    "min_alter_tage": "mindestens {} Tage alt",
    "max_alter_tage": "höchstens {} Tage alt",
    "quelle": "Quelle „{}“",
    "firma": "Firma enthält „{}“",
    "titel_enthaelt": "Titel enthält {}",
    "titel_enthaelt_nicht": "Titel enthält nicht {}",
    "beschreibung_enthaelt": "Anzeige enthält {}",
    "beschreibung_enthaelt_nicht": "Anzeige enthält nicht {}",
    "sprache": "Sprache: {}",
}


class UngueltigeBedingung(ValueError):
    """Eine Bedingung, die es nicht gibt oder deren Wert nicht passt - benannt statt ignoriert (#988)."""


def bedingungen_lesen(roh: Optional[dict]) -> dict:
    """Prueft und bereinigt Bedingungen; leere Werte fallen weg.

    Wirft `UngueltigeBedingung` bei einem unbekannten Namen, einer Zahl, die
    keine ist, oder einer unbekannten Sprache."""
    if roh is None:
        return {}
    if not isinstance(roh, dict):
        raise UngueltigeBedingung("Die Bedingungen müssen als Objekt kommen.")
    ergebnis: dict = {}
    for name, wert in roh.items():
        if name not in BEDINGUNGEN:
            raise UngueltigeBedingung(
                f"Unbekannte Bedingung '{name}'. Möglich: {', '.join(BEDINGUNGEN)}.")
        if wert is None or wert == "" or wert == []:
            continue
        if name in ZAHLEN:
            if isinstance(wert, bool):
                raise UngueltigeBedingung(f"'{name}' muss eine ganze Zahl sein.")
            try:
                ergebnis[name] = int(wert)
            except (TypeError, ValueError):
                raise UngueltigeBedingung(f"'{name}' muss eine ganze Zahl sein, nicht {wert!r}.") from None
        elif name in TEXTE:
            text = str(wert).strip()
            if text:
                ergebnis[name] = text
        else:
            werte = [wert] if isinstance(wert, str) else list(wert)
            werte = [str(w).strip() for w in werte if str(w or "").strip()]
            if name == "sprache":
                werte = [w.lower() for w in werte]
                falsch = [w for w in werte if w not in _sprache.SPRACHEN]
                if falsch:
                    raise UngueltigeBedingung(
                        f"Unbekannte Sprache {', '.join(falsch)}. Möglich: {', '.join(_sprache.SPRACHEN)}.")
            if werte:
                ergebnis[name] = list(dict.fromkeys(werte))
    return ergebnis


def _quelle_passt(quelle: str, job_quelle: str) -> bool:
    q = quelle.lower()
    j = (job_quelle or "").lower()
    if "_" in quelle or quelle in ("manuell", "google_jobs"):
        return j == q
    return j == q or q in j


def _alter_tage(found_at: str, jetzt: datetime) -> Optional[int]:
    if not found_at:
        return None
    # #1386: found_at gibt es mit Zone (UTC) und ohne (Ortszeit); beide werden
    # zum selben Zeitpunkt. Frueher schnitt "+00:00" die Zone einfach ab.
    from . import uhr
    gefunden = uhr.zeitpunkt(found_at)
    if gefunden is None:
        return None
    jetzt_z = jetzt if jetzt.tzinfo else jetzt.astimezone()
    return (jetzt_z - gefunden).days


def passt(job: dict, bedingungen: dict, *, jetzt: Optional[datetime] = None,
          sprache_von: Optional[Callable[[dict], str]] = None) -> bool:
    """True, wenn die Stelle ALLE Bedingungen erfuellt.

    `bedingungen` kommt aus `bedingungen_lesen`. `sprache_von` erlaubt einem
    Aufrufer, die Erkennung je Stelle einmal zu rechnen (Liste mit mehreren
    Durchgaengen); ohne ihn rechnet `sprache.erkennen_stelle`."""
    b = bedingungen or {}
    if not b:
        return True
    if "min_score" in b or "max_score" in b:
        # Wie bis v1.8.1: die Untergrenze vergleicht den gespeicherten Wert
        # (in der Datenbank `score>=?`), die Obergrenze den ganzzahligen.
        try:
            wert = float(job.get("score") or 0)
        except (TypeError, ValueError):
            wert = 0.0
        if "min_score" in b and wert < b["min_score"]:
            return False
        if "max_score" in b and int(wert) > b["max_score"]:
            return False
    if "min_alter_tage" in b or "max_alter_tage" in b:
        alter = _alter_tage(job.get("found_at") or "", jetzt or datetime.now())
        if alter is None:
            return False
        if "min_alter_tage" in b and alter < b["min_alter_tage"]:
            return False
        if "max_alter_tage" in b and alter > b["max_alter_tage"]:
            return False
    if "quelle" in b and not _quelle_passt(b["quelle"], job.get("source") or ""):
        return False
    if "firma" in b and b["firma"].lower() not in (job.get("company") or "").lower():
        return False
    if "titel_enthaelt" in b or "titel_enthaelt_nicht" in b:
        titel = (job.get("title") or "").lower()
        if any(t.lower() not in titel for t in b.get("titel_enthaelt", ())):
            return False
        if any(t.lower() in titel for t in b.get("titel_enthaelt_nicht", ())):
            return False
    if "beschreibung_enthaelt" in b or "beschreibung_enthaelt_nicht" in b:
        text = (job.get("description") or "").lower()
        if any(t.lower() not in text for t in b.get("beschreibung_enthaelt", ())):
            return False
        if any(t.lower() in text for t in b.get("beschreibung_enthaelt_nicht", ())):
            return False
    if "sprache" in b:
        code = (sprache_von or _sprache.erkennen_stelle)(job)
        if code not in b["sprache"]:
            return False
    return True


def sprach_speicher() -> Callable[[dict], str]:
    """Eine Erkennung, die jede Stelle nur einmal liest (je Hash und Textlaenge)."""
    gemerkt: dict = {}

    def sprache_von(job: dict) -> str:
        schluessel = (job.get("hash"), len(job.get("description") or ""), job.get("title"))
        if schluessel not in gemerkt:
            gemerkt[schluessel] = _sprache.erkennen_stelle(job)
        return gemerkt[schluessel]
    return sprache_von


def filtern(jobs: list, bedingungen: dict, *, jetzt: Optional[datetime] = None,
            sprache_von: Optional[Callable[[dict], str]] = None) -> list:
    """Die Stellen, die passen - in der Reihenfolge der Eingabe."""
    if not bedingungen:
        return list(jobs)
    jetzt = jetzt or datetime.now()
    sv = sprache_von or sprach_speicher()
    return [j for j in jobs if passt(j, bedingungen, jetzt=jetzt, sprache_von=sv)]


def klartext(bedingungen: dict) -> str:
    """Die Bedingungen als ein Satz fuer Menschen."""
    teile = []
    for name in BEDINGUNGEN:
        if name not in (bedingungen or {}):
            continue
        wert = bedingungen[name]
        if name == "sprache":
            wert = ", ".join(_sprache.KLARTEXT.get(w, w).split(" (")[0] for w in wert)
        elif isinstance(wert, list):
            wert = ", ".join(f"„{w}“" for w in wert)
        teile.append(_KLARTEXT[name].format(wert))
    return "; ".join(teile) if teile else "keine Bedingung"
