"""Remote-Grad fuer JobSpy-Treffer aus dem Text statt aus `is_remote` (#1072).

JobSpy setzt fuer Indeed und LinkedIn `is_remote = True`, sobald die
Zeichenfolge "remote", "work from home" oder "wfh" IRGENDWO in
Beschreibung, Ort oder Attributen steht (`jobspy/indeed/util.py`,
`is_job_remote`), und `False` in jedem anderen Fall — nie `None`. PBP
uebernahm beides ungeprueft:

* `True` wurde "vollstaendig remote", die Entfernung fiel weg. Belegter
  Fall: "Hybrides Arbeitsmodell mit bis zu 50 % remote work im Monat",
  Hamburg, im Rahmendaumen als "Vollstaendig remote" gefuehrt.
* `False` wurde "vor Ort", obwohl es nur heisst: kein Stichwort gefunden.

Gemessen am 22.09.2026 (Indeed, Hamburg, je 30 Treffer): Suchbegriff
"Strategie" 13 von 30 mit `is_remote=True`, "Aufbau" 12 von 30.

Jetzt entscheidet PBPs eigene Erkennung auf Titel, Ort und dem GANZEN
Anzeigentext; Hybrid-Signale gehen dabei vor dem blossen Wort "remote".
`is_remote=True` ist nur noch ein Hinweis fuer den Fall, dass der Text
gar nichts sagt — und dann `hybrid`, nicht `remote`. `False` heisst
`unbekannt`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Quellen, deren `remote_level` aus `is_remote` stammen konnte.
QUELLEN = ("jobspy_indeed", "jobspy_linkedin", "jobspy_google",
           "jobspy_glassdoor", "jobspy_zip_recruiter")

MARKER = "remote_jobspy_1072_nachgezogen"


def bestimmen(title: str, location: str, description: str,
              is_remote=None) -> str:
    """remote | hybrid | vor_ort | unbekannt — der Text entscheidet."""
    from ..job_scraper import detect_remote_level
    eigen = detect_remote_level(
        f"{title or ''} {location or ''} {description or ''}")
    if eigen != "unbekannt":
        return eigen
    # Der Text sagt nichts. Dann stammt JobSpys `True` aus Ort oder
    # Attributen — und dort traegt auch Indeeds "Hybrid remote" das Wort.
    # Ein Hinweis ohne Beleg bekommt die vorsichtige Stufe: ein falsches
    # "hybrid" kostet einen Entfernungsabzug, ein falsches "remote"
    # blendet die Entfernung aus. Stichprobe am 23.09.2026: von zehn
    # gespeicherten "remote"-Stellen nannten sieben das Wort gar nicht.
    if is_remote is True:
        return "hybrid"
    return "unbekannt"


def bestand_nachziehen(db) -> dict:
    """Einmalige Nachberechnung fuer den Bestand (#1072 AK 3). Idempotent.

    Angefasst werden nur JobSpy-Stellen, deren gespeicherter Wert aus
    `is_remote` stammen konnte (`remote` oder `vor_ort`). Der Score wird
    nicht umgeschrieben — der Rahmendaumen liest `remote_level` beim
    Anzeigen; die gespeicherte Rahmenzahl zieht `scores_neu_berechnen()`
    nach.
    """
    try:
        if db.get_setting(MARKER):
            return {"status": "schon_erledigt"}
    except Exception:  # pragma: no cover
        return {"status": "uebersprungen"}
    conn = db.connect()
    platz = ",".join("?" * len(QUELLEN))
    zeilen = conn.execute(
        "SELECT hash, title, location, description, remote_level FROM jobs "
        f"WHERE source IN ({platz}) AND remote_level IN ('remote', 'vor_ort')",
        QUELLEN).fetchall()
    geaendert: dict = {}
    for r in zeilen:
        # Aus dem Bestand ist nicht mehr zu sehen, ob JobSpy "True"
        # meldete — nur, dass PBP daraus `remote` machte. Also gilt der
        # Hinweis hier als vorhanden, wo `remote` gespeichert ist.
        neu = bestimmen(r["title"], r["location"], r["description"],
                        is_remote=(r["remote_level"] == "remote"))
        if neu != r["remote_level"]:
            conn.execute("UPDATE jobs SET remote_level=? WHERE hash=?",
                         (neu, r["hash"]))
            schluessel = f"{r['remote_level']}->{neu}"
            geaendert[schluessel] = geaendert.get(schluessel, 0) + 1
    conn.commit()
    db.set_setting(MARKER, "1")
    if geaendert:
        logger.info("Safety-Net #1072: Remote-Grad von %d JobSpy-Stellen "
                    "nachgezogen: %s", sum(geaendert.values()), geaendert)
    return {"status": "nachgezogen", "geprueft": len(zeilen),
            "geaendert": geaendert}
