"""Wo laufen Notizfeld und Timeline auseinander? (#957, Stufe 1)

`bewerbung_erstellen` schreibt denselben Text an ZWEI Orte: in
`applications.notes` (das Feld) und als `application_events`-Zeile mit
`status='notiz'` (die Timeline, seit #224). Beim Anlegen sind beide
identisch — danach nicht mehr:

* `bewerbung_bearbeiten(notes=...)` aendert **nur das Feld**. Der
  Timeline-Eintrag bleibt unveraendert stehen und ist nirgends als
  ueberholt gekennzeichnet.
* `bewerbung_notiz()` schreibt dagegen sauber nur in die Timeline.

Die Doppelung entsteht also allein beim Anlegen, die Drift bei jeder
spaeteren Korrektur.

## Warum hier NICHTS geschrieben wird

Das Issue verlangt ausdruecklich zwei Stufen: **erst messen, dann
entscheiden.** Der Grund steht darin und ist gut: bei zwei abweichenden
Fassungen derselben Notiz ist die Frage, welche gilt, eine INHALTLICHE
— die kann kein Programm beantworten. Ein Auto-Fix waere hier genau der
Fehlertyp aus #980: eine Automatik, die stillschweigend eine Bedeutung
festlegt.

Dieses Modul beantwortet nur: **wie verbreitet ist die Drift
ueberhaupt.** Erst danach laesst sich sagen, ob der Rueckbau ein
Aufraeumen ist oder ein Eingriff in gepflegte Inhalte.

## Die vier Faelle

* `identisch`   — Feld und Anlage-Eintrag wortgleich. Harmlose
                  Dublette; ein Rueckbau kostet nichts.
* `abweichend`  — beide gefuellt, aber verschieden. **Der teure Fall:**
                  hier hat jemand gepflegt, und ein Rueckbau muesste
                  sich entscheiden.
* `nur_feld`    — nur `applications.notes` gefuellt.
* `nur_timeline`— nur der Anlage-Eintrag gefuellt.

Bewerbungen ohne beides tauchen gar nicht auf: dort gibt es nichts zu
entscheiden.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

IDENTISCH = "identisch"
ABWEICHEND = "abweichend"
NUR_FELD = "nur_feld"
NUR_TIMELINE = "nur_timeline"

FAELLE = (IDENTISCH, ABWEICHEND, NUR_FELD, NUR_TIMELINE)

BEDEUTUNG = {
    IDENTISCH: ("Feld und Anlage-Eintrag sind wortgleich — harmlose "
                "Dublette, ein Rueckbau kostet nichts."),
    ABWEICHEND: ("Beide gefuellt und verschieden — hier wurde gepflegt. "
                 "Welche Fassung gilt, ist eine inhaltliche Entscheidung."),
    NUR_FELD: "Nur das Notizfeld ist gefuellt.",
    NUR_TIMELINE: "Nur der Anlage-Eintrag ist gefuellt.",
}


def _vergleichbar(text) -> str:
    """Auf das Wesentliche reduzieren — Leerraum ist keine Drift.

    Ein Zeilenumbruch mehr oder weniger stammt aus der Eingabemaske und
    nicht aus einer Pflege. Wuerde er als `abweichend` zaehlen, waere
    die Zahl, auf die sich die Entscheidung stuetzt, zu hoch — und
    genau diese Zahl ist der ganze Zweck des Laufs.
    """
    return " ".join(str(text or "").split())


def _anlage_eintrag(zeilen: list) -> str:
    """Der ERSTE `notiz`-Eintrag — nur der stammt aus dem Anlegen.

    Spaetere Notizen kommen von `bewerbung_notiz()` und sind der
    saubere Weg; sie mit dem Feld zu vergleichen wuerde eine Drift
    behaupten, wo jemand schlicht etwas ergaenzt hat.
    """
    return zeilen[0] if zeilen else ""


def einordnen(feld, timeline_zeilen: list) -> str | None:
    """Welcher der vier Faelle liegt vor — oder None (nichts gefuellt)."""
    a = _vergleichbar(feld)
    b = _vergleichbar(_anlage_eintrag(timeline_zeilen))
    if not a and not b:
        return None
    if a and not b:
        return NUR_FELD
    if b and not a:
        return NUR_TIMELINE
    return IDENTISCH if a == b else ABWEICHEND


def bericht(db, *, beispiele: int = 5) -> dict:
    """Wie verbreitet ist die Drift im Bestand? Schreibt NICHTS.

    Args:
        beispiele: wieviele abweichende Faelle beispielhaft benannt
            werden. Bewusst nur die IDs und die Laengen — der Inhalt
            einer Notiz ist das Privateste im ganzen Bestand und hat in
            einer Diagnose-Antwort nichts zu suchen.
    """
    try:
        conn = db.connect()
        # Bewusst NUR id und notes: der Bericht nennt keine Firma und
        # keinen Titel, also gibt es auch keinen Grund, sie zu laden.
        # (Der erste Entwurf holte `position` — die Spalte heisst
        # `title`. Feldnamen gehoeren nachgeschlagen, nicht geraten,
        # #949.)
        zeilen = conn.execute(
            "SELECT id, notes FROM applications"
        ).fetchall()
    except Exception as exc:  # pragma: no cover — eine Diagnose stoppt nie
        logger.debug("Bewerbungen nicht lesbar: %s", exc)
        return {"fehler": str(exc)}

    zaehler = {fall: 0 for fall in FAELLE}
    proben: list[dict] = []
    betrachtet = 0

    for zeile in zeilen:
        try:
            events = conn.execute(
                "SELECT notes FROM application_events "
                "WHERE application_id = ? AND status = 'notiz' "
                "ORDER BY event_date ASC, rowid ASC",
                (zeile["id"],),
            ).fetchall()
        except Exception:  # pragma: no cover
            continue
        notizen = [e["notes"] for e in events if (e["notes"] or "").strip()]
        fall = einordnen(zeile["notes"], notizen)
        if fall is None:
            continue
        betrachtet += 1
        zaehler[fall] += 1
        if fall == ABWEICHEND and len(proben) < beispiele:
            proben.append({
                "bewerbung_id": str(zeile["id"])[:8],
                # KEIN Notiztext — nur die Groessenordnung.
                "zeichen_feld": len(_vergleichbar(zeile["notes"])),
                "zeichen_timeline": len(
                    _vergleichbar(_anlage_eintrag(notizen))),
                "weitere_notizen": max(0, len(notizen) - 1),
            })

    return {
        "bewerbungen_gesamt": len(zeilen),
        "mit_notiz": betrachtet,
        "faelle": zaehler,
        "bedeutung": BEDEUTUNG,
        "beispiele_abweichend": proben,
        "hinweis": _hinweis(zaehler),
        "schreibt": "nichts — Stufe 1 von #957 ist ein reiner Report",
    }


def _hinweis(zaehler: dict) -> str:
    """Was die Zahlen fuer die Entscheidung bedeuten.

    Eine Kennzahl ohne Deutung ist der halbe Befund (#989) — und hier
    haengt an ihr eine Entscheidung, die der Mensch treffen soll.
    """
    abweichend = zaehler.get(ABWEICHEND, 0)
    identisch = zaehler.get(IDENTISCH, 0)
    if abweichend == 0 and identisch == 0:
        return ("Keine Doppelung im Bestand — der Anlage-Eintrag aus "
                "#224 hat hier nie gegriffen. Stufe 2 waere reine "
                "Vorsorge fuer kuenftige Anlagen.")
    if abweichend == 0:
        return (f"{identisch} Dublette(n), aber KEINE Drift: Feld und "
                "Anlage-Eintrag sind ueberall wortgleich. Ein Rueckbau "
                "verliert damit nichts — es gibt keine zweite Fassung, "
                "die jemand gepflegt haette.")
    return (f"{abweichend} Bewerbung(en) tragen ZWEI verschiedene "
            "Fassungen derselben Notiz. Fuer die ist der Rueckbau kein "
            "Aufraeumen, sondern eine inhaltliche Entscheidung — welche "
            "Fassung gilt, kann nur der Mensch sagen.")
