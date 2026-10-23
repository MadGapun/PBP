"""Wann eine Automatik eine Stelle NICHT aussortieren darf (#1250).

Befund vom 19.10.2026 (Abgleich der aktiven Stellen): die lokale KI
sortierte eine Stelle aus, die der Mensch drei Tage vorher ausdruecklich
zurueckgeholt hatte und zu der ein gespeichertes Urteil BEDINGT vorlag.
Eine zweite Stelle mit Urteil EMPFOHLEN fiel auf demselben Weg. Der
Kandidatenfilter der Auto-Aussortierung fragte nur `dismiss_reason` - und
den loescht das Zurueckholen.

Die Regel ist EINE Funktion, damit jeder automatische Weg dieselbe
Antwort bekommt (L1-L3):

* der Mensch hat die Stelle zurueckgeholt oder als passend markiert
  (`jobs.zurueckgeholt_am`, gesetzt von `Database.restore_job`; sein eigenes
  Aussortieren loescht den Vermerk wieder), oder
* an der Stelle haengt ein gelesenes Urteil EMPFOHLEN oder BEDINGT
  (`stelle_urteil_speichern`, #1007).

Dann gilt das Wort des Menschen bzw. der Detailanalyse; eine Automatik
darf es nicht still ueberstimmen. Der Mensch selbst kann jederzeit
aussortieren - die Regel gilt nur fuer `herkunft="automatik"`.

Ausgenommen sind Gruende, die eine TATSACHE festhalten und kein Urteil
ueber die Passung sind: `veraltet_url` (der Server meldet die Anzeige als
entfernt) und `bewerbung_erstellt` (die Stelle wird geschlossen, WEIL sich
der Mensch beworben hat).

Abgrenzung: `aussortier_protokoll.py` beschreibt, WER aussortiert hat;
`aussortieren.py` fuehrt eine Aussortierung samt Lerneffekt aus; dieses
Modul entscheidet, ob eine Automatik es ueberhaupt darf. Durchgesetzt wird
die Regel im Nadeloehr `Database.dismiss_job` (doppelter Boden), gefragt
wird sie vorher in `auto_aussortierung.aussortieren` (die KI bekommt eine
geschuetzte Stelle gar nicht erst vorgelegt).
"""
from __future__ import annotations

#: Urteile, die eine Stelle vor jeder Automatik schuetzen.
GESCHUETZTE_URTEILE = frozenset({"EMPFOHLEN", "BEDINGT"})

#: Gruende, die eine Tatsache festhalten - fuer sie gilt der Schutz nicht.
TATSACHEN_GRUENDE = frozenset({"veraltet_url", "bewerbung_erstellt"})

ZURUECKGEHOLT = "zurueckgeholt"
URTEIL = "urteil"

KLARTEXT = {
    ZURUECKGEHOLT: "Du hast diese Stelle zurückgeholt oder als passend "
                   "markiert — die Automatik sortiert sie nicht aus.",
    URTEIL: "Zu dieser Stelle liegt ein gelesenes Urteil vor "
            "(empfohlen oder bedingt) — die Automatik sortiert sie "
            "nicht aus.",
}


def _kern(grund) -> str:
    kern = str(grund or "").strip().lower()
    if kern.startswith("auto:"):
        kern = kern[len("auto:"):]
    return kern.split(":", 1)[0].strip()


def schutz(job: dict | None) -> str:
    """Warum diese Stelle geschuetzt ist: `zurueckgeholt`, `urteil` oder ''."""
    if not job:
        return ""
    if job.get("zurueckgeholt_am"):
        return ZURUECKGEHOLT
    if str(job.get("analyse_urteil") or "").strip().upper() in GESCHUETZTE_URTEILE:
        return URTEIL
    return ""


def automatik_gesperrt(job: dict | None, grund) -> str:
    """'' = die Automatik darf mit diesem Grund aussortieren; sonst der
    Schutzgrund aus `schutz` (fuer Protokoll und Antwort)."""
    if _kern(grund) in TATSACHEN_GRUENDE:
        return ""
    return schutz(job)
