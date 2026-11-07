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

Dieselbe Regel gilt fuer Treffer aus Google Jobs, die Claude im Browser uebernimmt
(`stelle_manuell_anlegen`, #1184): siehe `google_angaben`.

Seit #1298/#1299 steht hier auch die EINE Normalisierung einer Remote-Angabe von aussen
(`normalisieren`): die Browser-Uebernahme, die LinkedIn-Uebernahme und die Handkorrektur
(`stelle_aendern`) fragen hier, statt je eine eigene Fassung zu haben. Ein `remote: true` aus
dem Browserlauf wurde vorher per `str()` zu "True" und still gespeichert; der Rahmen prueft auf
genau "remote", und voll remote ausgeschriebene Stellen fielen unter die 40-km-Grenze.
`ungueltige_bereinigen` bildet solche Altwerte beim Start auf das Vokabular ab.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

#: Das Vokabular von `jobs.remote_level` — dieselben vier Stufen wie `set_job_remote_level`.
STUFEN = ("remote", "hybrid", "vor_ort", "unbekannt")

#: Ja/Nein-Angaben ("ist die Stelle remote?"), wie sie aus einem Browserlauf kommen.
_JA = frozenset({"true", "ja", "yes", "y", "1", "wahr"})
_NEIN = frozenset({"false", "nein", "no", "n", "0", "falsch"})
#: Ausdruecklich vor Ort.
_VOR_ORT = frozenset({"vor ort", "vor-ort", "vorort", "vor_ort", "onsite", "on-site", "on site",
                      "praesenz", "präsenz", "im buero", "im büro", "buero", "büro", "office"})
#: "nicht remote", "kein Homeoffice" — eine verneinte Angabe ist kein Remote-Signal.
_VERNEINT = re.compile(r"\b(?:nicht|kein(?:e|en)?|no|not)\s+(?:remote|homeoffice|home[- ]office)\b")
_LEER = re.compile(r"[\s   ]+")


def normalisieren(wert) -> tuple[str, str | None]:
    """Eine Remote-Angabe von aussen auf das Vokabular abbilden (#1298).

    Rueckgabe `(stufe, hinweis)`. `hinweis` ist None, wenn die Angabe verstanden wurde; sonst steht
    `stufe` auf `unbekannt` und der Hinweis sagt, was nicht verstanden wurde — er gehoert in die
    Antwort an Claude. Unbekanntes wird NIE still gespeichert (Lehre L7: unbekannt ist ein eigener
    Zustand, kein Ersatzwert).

    * `True`, "true", "ja", "100 % remote", "voll remote", "fully remote" -> `remote`
    * `False`, "false", "nein", "vor Ort", "nicht remote"                 -> `vor_ort`
    * "hybrid", "teilweise remote", "2 Tage Homeoffice"                    -> `hybrid`
    * None, "" -> `unbekannt` ohne Hinweis (keine Angabe ist keine falsche Angabe)
    """
    if wert is None:
        return "unbekannt", None
    if isinstance(wert, bool):
        return ("remote" if wert else "vor_ort"), None
    if isinstance(wert, (int, float)) and wert in (0, 1):
        return ("remote" if wert else "vor_ort"), None
    text = _LEER.sub(" ", str(wert)).strip().lower()
    if not text:
        return "unbekannt", None
    if text in STUFEN:
        return text, None
    if text in _JA:
        return "remote", None
    if text in _NEIN or text in _VOR_ORT or _VERNEINT.search(text):
        return "vor_ort", None
    from ..job_scraper import detect_remote_level
    stufe = detect_remote_level(text)
    if stufe != "unbekannt":
        return stufe, None
    return "unbekannt", (
        f"Die Remote-Angabe „{str(wert)[:60]}“ ist nicht verständlich und wurde als „unbekannt“ "
        "gespeichert. Gültig sind: remote, hybrid, vor_ort, unbekannt (auch true/false).")


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
        f"WHERE source IN ({platz}) AND remote_level IN ('remote', 'vor_ort') "
        "AND COALESCE(remote_quelle, '') != 'mensch'",
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


def ungueltige_bereinigen(db) -> dict:
    """Altbestand: `remote_level` ausserhalb des Vokabulars auf eine Stufe abbilden (#1298 AK 5).

    Die Browser-Uebernahme speicherte bis #1298 `str(remote)`, aus `remote: true` wurde "True". Der
    Rahmen prueft auf genau "remote" — die Stelle lief gegen die 40-km-Grenze. Beim Start gerufen
    (`Database.initialize`), idempotent ueber die Bedingung selbst: nach dem ersten Lauf findet die
    Abfrage nichts mehr, ein Merker ist nicht noetig, und ein spaeter auftauchender Altwert (Sicherung
    zurueckgespielt) wird beim naechsten Start ebenso gefangen.

    Reihenfolge: zuerst die Angabe selbst (`normalisieren`: "True" -> remote, "False" -> vor_ort), und
    nur wenn sie nichts sagt, der Text der Anzeige (`bestimmen`). Danach Punkte und Rahmenzahl der
    geaenderten Stellen neu (`stelle_aendern.neu_bewerten`).
    """
    conn = db.connect()
    platz = ",".join("?" * len(STUFEN))
    zeilen = conn.execute(
        "SELECT hash, title, location, description, remote_level FROM jobs "
        f"WHERE remote_level IS NOT NULL AND remote_level NOT IN ({platz})",
        STUFEN).fetchall()
    if not zeilen:
        return {"status": "nichts_zu_tun", "geaendert": {}}
    geaendert: dict = {}
    hashes = []
    for r in zeilen:
        stufe, hinweis = normalisieren(r["remote_level"])
        if hinweis:
            stufe = bestimmen(r["title"], r["location"], r["description"])
        conn.execute("UPDATE jobs SET remote_level=? WHERE hash=?", (stufe, r["hash"]))
        schluessel = f"{r['remote_level']}->{stufe}"
        geaendert[schluessel] = geaendert.get(schluessel, 0) + 1
        hashes.append(r["hash"])
    conn.commit()
    neu_bewertet = 0
    try:
        from .stelle_aendern import neu_bewerten
        neu_bewertet = neu_bewerten(db, hashes)
    except Exception as exc:  # noqa: BLE001 - die Bereinigung steht, die Punkte zieht scores_neu_berechnen nach
        logger.warning("Remote-Bereinigung (#1298): Punkte nicht neu berechnet: %s", exc)
    logger.info("Remote-Grad von %d Stellen auf das Vokabular gebracht (#1298): %s",
                len(hashes), geaendert)
    return {"status": "bereinigt", "geaendert": geaendert, "neu_bewertet": neu_bewertet}
