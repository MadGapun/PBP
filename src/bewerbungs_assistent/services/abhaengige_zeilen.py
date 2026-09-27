"""Wer zeigt auf diese Zeile — und was geschieht mit ihm beim Loeschen (#1100)?

`delete_application` loeschte bis v1.7.139 Timeline, Nachfassungen und
die Bewerbung. Ueber Fremdschluessel fielen Aufgaben, Termine und
Reflexionen mit. Stehen blieben alle Bezuege OHNE Fremdschluessel:
`application_jobs` (die Stelle galt weiter als beworben),
`application_costs` (die Kosten zaehlten im Aufwand weiter),
`research_notes`, `document_versions`, `contact_references` und die
polymorphen `contact_links`. Beim Loeschen eines Termins ebenso.

Das Wissen, welche Tabellen an einer Zeile haengen, steht schon in den
Loeschbereichen (#1025): Fremdschluessel aus dem Schema plus
`_ZUSATZ_BEZUG`. Dieses Modul nimmt genau das und ergaenzt, was dort
fehlt — eine zweite Liste in `delete_application` waere #963 an einer
neuen Stelle.

Zwei Aktionen, mehr nicht:

* ``loeschen`` — die Zeile ergibt ohne ihr Elternteil keinen Sinn
  (Timeline-Eintrag, Kosten, Verknuepfung, Recherche zu DIESER Bewerbung).
* ``loesen`` — die Zeile hat einen eigenen Wert und verliert nur den
  Verweis (Dokument, Mail, Dokumentversion, Referenz). Das folgt dem
  `ON DELETE SET NULL` des Schemas, wo es eins gibt.

Vorschau und Ausfuehrung laufen durch dieselbe Funktion, damit die Zahl
vorher dieselbe ist wie nachher (die Lehre aus #1025: eine Vorschau, die
anders rechnet als die Loeschung, verspricht etwas anderes, als sie tut).
"""
from __future__ import annotations

import logging

from . import loeschbereiche as _lb

logger = logging.getLogger("bewerbungs_assistent.abhaengige_zeilen")

LOESCHEN = "loeschen"
LOESEN = "loesen"

#: Bezuege ohne Fremdschluessel, die `_ZUSATZ_BEZUG` nicht traegt.
#: Sie stehen hier und nicht dort, weil `_ZUSATZ_BEZUG` auch die
#: Profil-Zuordnung der Loeschbereiche steuert (`_eltern`) — eine Recherche
#: ohne Bewerbung gehoert trotzdem zum Profil.
#: (Tabelle, Spalte, Elterntabelle, Aktion)
WEITERE_BEZUEGE = (
    ("application_costs", "application_id", "applications", LOESCHEN),
    ("research_notes", "bewerbung_id", "applications", LOESCHEN),
    ("document_versions", "application_id", "applications", LOESEN),
    ("contact_references", "application_id", "applications", LOESEN),
    ("interview_reflections", "meeting_id", "application_meetings", LOESEN),
)

#: Polymorphe Verweise (#1077): keine Schema-Suche findet sie.
#: (Tabelle, Art-Spalte, Id-Spalte, {Elterntabelle: Art-Wert})
POLYMORPH = (
    ("contact_links", "target_kind", "target_id",
     {"applications": "application", "application_meetings": "meeting",
      "jobs": "job"}),
)

#: Klartext je Tabelle fuer Vorschau und Antwort.
NAMEN = {
    "applications": "Bewerbung",
    "application_events": "Timeline-Einträge",
    "follow_ups": "Nachfassungen",
    "tasks": "Aufgaben",
    "application_meetings": "Termine",
    "interview_reflections": "Interview-Reflexionen",
    "application_costs": "Kosten",
    "research_notes": "Recherchen",
    "application_jobs": "Stellen-Verknüpfungen",
    "contact_links": "Kontakt-Verknüpfungen",
    "documents": "Dokumente",
    "document_versions": "Dokumentversionen",
    "application_emails": "Mails",
    "contact_references": "Referenzen",
}


def bezuege_auf(db, eltern: str) -> list:
    """Alle Bezuege auf `eltern` — aus Schema, `_ZUSATZ_BEZUG`,
    `WEITERE_BEZUEGE` und `POLYMORPH`. Je Eintrag: tabelle, spalte,
    aktion und optional eine Zusatzbedingung (polymorph)."""
    vorhanden = set(_lb.tabellen(db))
    con = db.connect()
    gefunden: dict = {}
    for t in sorted(vorhanden):
        if t == eltern:
            continue  # Selbstbezug (Antwort-Ketten) — die Zeile geht mit
        try:
            for r in con.execute(f"PRAGMA foreign_key_list({t})"):
                # (id, seq, table, from, to, on_update, on_delete, match)
                if r[2] != eltern:
                    continue
                aktion = LOESEN if (r[6] or "").upper() == "SET NULL" else LOESCHEN
                gefunden[(t, r[3])] = {"tabelle": t, "spalte": r[3],
                                       "aktion": aktion, "bedingung": ""}
        except Exception as exc:  # pragma: no cover
            logger.debug("Fremdschluessel von %s nicht lesbar: %s", t, exc)
    for t, (e, spalte, _deren) in _lb._ZUSATZ_BEZUG.items():
        if e == eltern and t in vorhanden:
            gefunden.setdefault((t, spalte), {"tabelle": t, "spalte": spalte,
                                              "aktion": LOESCHEN, "bedingung": ""})
    for t, spalte, e, aktion in WEITERE_BEZUEGE:
        if e == eltern and t in vorhanden and spalte in _lb._spalten(db, t):
            gefunden.setdefault((t, spalte), {"tabelle": t, "spalte": spalte,
                                              "aktion": aktion, "bedingung": ""})
    for t, art_spalte, id_spalte, arten in POLYMORPH:
        if eltern in arten and t in vorhanden:
            gefunden[(t, id_spalte, arten[eltern])] = {
                "tabelle": t, "spalte": id_spalte, "aktion": LOESCHEN,
                "bedingung": f" AND {art_spalte}='{arten[eltern]}'"}
    return list(gefunden.values())


def _ids(con, tabelle, spalte, wert, bedingung) -> list:
    try:
        return [r[0] for r in con.execute(
            f"SELECT id FROM {tabelle} WHERE {spalte}=?{bedingung}", (wert,))]
    except Exception:
        # Tabelle ohne `id`-Spalte: nur zaehlen.
        n = con.execute(
            f"SELECT COUNT(*) FROM {tabelle} WHERE {spalte}=?{bedingung}",
            (wert,)).fetchone()[0]
        return [None] * n


def mit_bezuegen_loeschen(db, eltern: str, schluessel,
                          dry_run: bool = True) -> dict:
    """Loescht eine Zeile aus `eltern` samt allem, was an ihr haengt —
    oder zaehlt das nur (`dry_run`).

    Rueckgabe: {"geloescht": {Tabelle: n}, "geloest": {Tabelle: n}}.
    Zeilen, die mitgeloescht werden und selbst Elternteil sind (Termine
    einer Bewerbung), nehmen ihre eigenen Bezuege mit — ein Termin, der
    mit der Bewerbung geht, darf keine Kontakt-Verknuepfung auf sich
    hinterlassen. Zeilen, die schon die Wurzel loescht, zaehlen dabei
    nicht ein zweites Mal (eine Reflexion haengt an Bewerbung UND
    Termin). Verglichen wird je ZEILE, nicht je Tabelle: `contact_links`
    verliert fuer die Bewerbung andere Zeilen als fuer den Termin.
    """
    zaehler = {"geloescht": {}, "geloest": {}}
    con = db.connect()
    wurzel = bezuege_auf(db, eltern)
    weg: dict = {}   # Tabelle -> Zeilen-IDs, die die Wurzel loescht
    for b in wurzel:
        ids = _ids(con, b["tabelle"], b["spalte"], schluessel, b["bedingung"])
        _zaehlen(zaehler, b, len(ids))
        if b["aktion"] == LOESCHEN:
            weg.setdefault(b["tabelle"], set()).update(i for i in ids if i is not None)
    # Kinder, die mitgehen, raeumen ihre eigenen Bezuege ab — vor dem
    # Loeschen der Kinder selbst, sonst sind die IDs nicht mehr lesbar.
    for b in wurzel:
        if b["aktion"] != LOESCHEN:
            continue
        for kind_id in _ids(con, b["tabelle"], b["spalte"], schluessel, b["bedingung"]):
            if kind_id is None:
                continue
            for kb in bezuege_auf(db, b["tabelle"]):
                if kb["tabelle"] == eltern:
                    continue
                ids = [i for i in _ids(con, kb["tabelle"], kb["spalte"], kind_id,
                                       kb["bedingung"])
                       if i is None or i not in weg.get(kb["tabelle"], set())]
                if not ids:
                    continue
                _zaehlen(zaehler, kb, len(ids))
                if not dry_run:
                    _anwenden(con, kb, kind_id)
    if not dry_run:
        for b in wurzel:
            _anwenden(con, b, schluessel)
        con.execute(f"DELETE FROM {eltern} WHERE id=?", (schluessel,))
        con.commit()
    zaehler["geloescht"][eltern] = zaehler["geloescht"].get(eltern, 0) + 1
    return zaehler


def _zaehlen(zaehler, b, n) -> None:
    if n:
        ziel = "geloest" if b["aktion"] == LOESEN else "geloescht"
        zaehler[ziel][b["tabelle"]] = zaehler[ziel].get(b["tabelle"], 0) + n


def _anwenden(con, b, wert) -> None:
    t, s, bed = b["tabelle"], b["spalte"], b["bedingung"]
    if b["aktion"] == LOESEN:
        con.execute(f"UPDATE {t} SET {s}=NULL WHERE {s}=?{bed}", (wert,))
    else:
        con.execute(f"DELETE FROM {t} WHERE {s}=?{bed}", (wert,))


def klartext(zaehler: dict) -> str:
    """"Löscht 1 Bewerbung, 7 Timeline-Einträge; löst 3 Dokumente." """
    def teil(d):
        return ", ".join(f"{n} {NAMEN.get(t, t)}"
                         for t, n in sorted(d.items(), key=lambda p: -p[1]) if n)
    geloescht, geloest = teil(zaehler["geloescht"]), teil(zaehler["geloest"])
    satz = f"Löscht {geloescht}" if geloescht else "Löscht nichts"
    if geloest:
        satz += f"; löst {geloest} (sie bleiben erhalten)"
    return satz + "."
