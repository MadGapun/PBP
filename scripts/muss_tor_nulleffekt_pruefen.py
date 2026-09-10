"""Rechnet nach, ob das MUSS-Tor den eigenen Bestand veraendert (#968).

Zwei Behauptungen aus v1.7.68/v1.7.69 lassen sich nur am eigenen
Bestand pruefen, weil sie von den eigenen Kriterien abhaengen:

1. **In der Vorgabe aendert sich kein einziger Score** gegenueber der
   Fassung vor v1.7.68.
2. **Mit `gewichtet`** werden N zusaetzliche Anzeigen sichtbar, und
   zwar mit welchen Punktzahlen.

Beim Autor gemessen (09./10.09.2026, 2.491 Anzeigen): **0 Abweichungen**
in der Vorgabe; mit `gewichtet` 932 zusaetzlich sichtbare Anzeigen im
Bereich 0,5 bis 3,5 Punkte.

Die Zahlen stehen im CHANGELOG — die DATEN koennen nicht ins Repo, sie
sind der Bewerbungsbestand eines Menschen. Nachpruefbar wird die
Behauptung deshalb ueber dieses Skript: **jeder rechnet sie an seinem
eigenen Bestand nach.**

## Aufruf

Immer gegen eine KOPIE, nie gegen die laufende Datenbank:

    copy "%LOCALAPPDATA%\\BewerbungsAssistent\\data\\pbp.db" C:\\Temp\\pbp-kopie\\
    python scripts/muss_tor_nulleffekt_pruefen.py C:\\Temp\\pbp-kopie

Das Skript schreibt NICHTS. Es setzt `BA_DATA_DIR` auf das uebergebene
Verzeichnis und bricht ab, wenn die geoeffnete Datenbank nicht dort
liegt (QA-Isolations-Regel, harte Projektregel seit dem DB-Vorfall
2026-06-10).
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    ziel = Path(argv[1]).resolve()
    if not (ziel / "pbp.db").exists():
        print(f"Keine pbp.db in {ziel} — bitte erst eine Kopie ablegen.")
        return 2

    os.environ["BA_DATA_DIR"] = str(ziel)
    sys.path.insert(0, str(REPO / "src"))

    from bewerbungs_assistent import database
    importlib.reload(database)
    db = database.Database()
    db.initialize()
    # Harte Zusicherung, kein Kommentar: ein falscher Env-Var faellt
    # STILL auf die echte AppData-Datenbank zurueck.
    if str(ziel) not in str(db.db_path):
        print(f"ABBRUCH — Datenbank nicht isoliert: {db.db_path}")
        return 1
    print(f"Datenbank (Kopie): {db.db_path}\n")

    from bewerbungs_assistent.job_scraper import calculate_score
    from bewerbungs_assistent.services import muss_tor, scoring_kriterien

    krit = scoring_kriterien.fuer_scoring(db)
    muss = [k for k in (krit.get("keywords_muss") or []) if str(k).strip()]
    arten = krit.get("_muss_begriffsart") or {}
    art, warum = muss_tor.abgeleitet(arten)
    print(f"Pflichtbegriffe: {len(muss)}")
    print(f"Betriebsart    : {muss_tor.modus(db, krit)}  (abgeleitet: {art})")
    print(f"Begruendung    : {warum}\n")
    if not arten:
        print("  Hinweis: die Begriffsarten sind noch nicht bestimmt — sie")
        print("  entstehen beim naechsten Suchlauf. Bis dahin gilt 'hart'.\n")

    spalten = ("hash,title,description,score,remote_level,distance_km,"
               "employment_type,salary_min,salary_type")
    rows = db.connect().execute(f"SELECT {spalten} FROM jobs").fetchall()

    vorher = {k: v for k, v in krit.items() if k != "_muss_tor_modus"}
    hart = dict(krit, _muss_tor_modus=muss_tor.HART)
    gewichtet = dict(krit, _muss_tor_modus=muss_tor.GEWICHTET)

    abweichungen, zusaetzlich, punkte = 0, 0, []
    for r in rows:
        job = {k: r[k] for k in r.keys()}
        alt = calculate_score(dict(job), vorher)      # wie vor v1.7.68
        neu = calculate_score(dict(job), hart)        # Vorgabe heute
        if alt != neu:
            abweichungen += 1
        gew = calculate_score(dict(job), gewichtet)
        if neu == 0 and gew > 0:
            zusaetzlich += 1
            punkte.append(gew)

    print(f"Anzeigen geprueft                     : {len(rows)}")
    print(f"Score-Abweichung gegenueber v1.7.67   : {abweichungen}")
    print(f"Mit 'gewichtet' zusaetzlich sichtbar  : {zusaetzlich}")
    if punkte:
        print(f"   Punktespanne dieser Anzeigen       : "
              f"{min(punkte)} bis {max(punkte)}")
    print()
    if abweichungen:
        print("BEFUND: die Vorgabe ist NICHT wirkungsfrei — das "
              "widerspricht der Behauptung im CHANGELOG und gehoert "
              "gemeldet.")
        return 1
    print("Die Vorgabe ist wirkungsfrei: kein Score hat sich geaendert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
