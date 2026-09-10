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
# v1.7.76 (#957 Stufe 2): das Feld ENTHAELT den Anlage-Eintrag und mehr.
#
# Ohne diesen Fall haette der Report nach der Zusammenfuehrung weiter
# `abweichend` gemeldet — technisch richtig (die Texte sind verschieden),
# in der Sache falsch: beide Fassungen liegen dann ja an einem Ort. Ein
# Pruefer, der bei korrektem Zustand Alarm gibt, wird nach dem zweiten
# Mal ignoriert (#929). Beim Messen aufgefallen, nicht beim Nachdenken.
ZUSAMMENGEFUEHRT = "zusammengefuehrt"

FAELLE = (IDENTISCH, ABWEICHEND, ZUSAMMENGEFUEHRT, NUR_FELD, NUR_TIMELINE)

BEDEUTUNG = {
    IDENTISCH: ("Feld und Anlage-Eintrag sind wortgleich — harmlose "
                "Dublette, ein Rueckbau kostet nichts."),
    ABWEICHEND: ("Beide gefuellt und verschieden — hier wurde gepflegt. "
                 "Welche Fassung gilt, ist eine inhaltliche Entscheidung."),
    ZUSAMMENGEFUEHRT: ("Das Notizfeld enthaelt beide Fassungen. Nichts "
                       "ist verloren, nichts mehr zu tun."),
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
    if a == b:
        return IDENTISCH
    # Steht der Anlage-Eintrag VOLLSTAENDIG im Feld, ist die Drift
    # aufgeloest — genau das erzeugt `zusammenfuehren()`.
    if b in a:
        return ZUSAMMENGEFUEHRT
    return ABWEICHEND


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


# ---------------------------------------------------------------------
# Stufe 2 (#957) — die Nutzerentscheidung vom 10.09.2026
# ---------------------------------------------------------------------
#
# Die Messung aus Stufe 1 hat die Entscheidung erzwungen: **23 von 97
# Bewerbungen** tragen zwei verschiedene Fassungen derselben Notiz, und
# die Abweichung geht in BEIDE Richtungen — mal ist das Feld laenger,
# mal der Timeline-Eintrag. Es gibt also keine ableitbare Regel.
#
# Drei Wege standen zur Wahl:
#
# 1. *Die neuere gewinnt* — braucht einen verlaesslichen Zeitstempel auf
#    beiden Seiten. Den hat das Feld nicht.
# 2. *Die laengere gewinnt* — eine Vermutung, kein Beleg. Eine gekuerzte
#    Korrektur waere damit verloren.
# 3. *Beide behalten, verkettet* — verliert nichts.
#
# **Der Nutzer hat 3 gewaehlt.** Das ist auch der einzige Weg, der zu
# der Linie passt, die dieses Projekt sonst faehrt: eine Luecke gehoert
# benannt, nicht gefuellt, und eine Information, die ein Mensch
# geschrieben hat, wird nicht auf Verdacht weggeworfen (#989, #1010).

TRENNZEILE = "--- frueherer Stand (aus dem Anlage-Eintrag) ---"


def _verketten(feld: str, timeline: str) -> str:
    """Beide Fassungen, durch eine benannte Zeile getrennt.

    Das FELD steht oben: es ist die Fassung, die zuletzt gepflegt wurde
    (`bewerbung_bearbeiten` schreibt nur dorthin). Der Anlage-Eintrag
    kommt darunter — er ist der aeltere Stand und wird als solcher
    bezeichnet, statt kommentarlos angehaengt zu werden.
    """
    oben = str(feld or "").rstrip()
    unten = str(timeline or "").strip()
    if not unten:
        return oben
    if not oben:
        return unten
    return f"{oben}\n\n{TRENNZEILE}\n{unten}"


def zusammenfuehren(db, *, dry_run: bool = True, max_bewerbungen: int = 0) -> dict:
    """Fuehrt abweichende Notiz-Fassungen zusammen (#957, Stufe 2).

    **Nichts wird weggeworfen.** Bei einer Abweichung stehen danach
    beide Fassungen im Feld, getrennt durch eine benannte Zeile. Der
    Timeline-Eintrag bleibt unangetastet — er ist die Herkunft des
    unteren Teils und damit der Beleg dafuer, dass nichts erfunden
    wurde.

    Angefasst wird ausschliesslich der Fall `abweichend`. `identisch`
    braucht nichts, `nur_feld` und `nur_timeline` sind keine Drift,
    sondern schlicht ein Ort, an dem etwas steht.

    Idempotent: eine bereits verkettete Notiz ENTHAELT den
    Timeline-Eintrag und faellt damit nicht mehr unter `abweichend` —
    der zweite Lauf findet sie nicht wieder.

    Args:
        dry_run: Vorgabe True. Es wird NICHTS geschrieben, nur gezaehlt.
        max_bewerbungen: 0 = alle.

    Returns:
        dict mit den Zahlen und einer Stichprobe OHNE Notiztexte — der
        Inhalt einer Notiz ist das Privateste im ganzen Bestand.
    """
    try:
        conn = db.connect()
        zeilen = conn.execute("SELECT id, notes FROM applications").fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Bewerbungen nicht lesbar: %s", exc)
        return {"status": "fehler", "fehler": str(exc)[:200]}

    if max_bewerbungen > 0:
        zeilen = zeilen[:max_bewerbungen]

    zusammengefuehrt = uebersprungen = fehler = 0
    nur_timeline = 0
    proben: list[dict] = []

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
        # Der Lauf ist idempotent, ohne eine Merkliste zu fuehren: eine
        # bereits verkettete Notiz faellt unter `zusammengefuehrt` und
        # nicht mehr unter `abweichend`. Dieselbe Einordnung wie im
        # Report — zwei Fassungen davon waeren #963 in diesem Modul.
        if fall == ZUSAMMENGEFUEHRT:
            uebersprungen += 1
            continue
        if fall == NUR_TIMELINE:
            # BEWUSST unangetastet: hier gibt es keine zwei Fassungen,
            # sondern eine — sie steht nur am anderen Ort. Sie ins Feld
            # zu schieben waere kein Zusammenfuehren, sondern ein Umzug,
            # und damit eine zweite Entscheidung. Sie wird deshalb
            # gezaehlt und benannt, nicht ausgefuehrt.
            nur_timeline += 1
            continue
        if fall != ABWEICHEND:
            continue

        anlage = _anlage_eintrag(notizen)
        neu = _verketten(zeile["notes"], anlage)
        if len(proben) < 10:
            proben.append({
                "bewerbung_id": str(zeile["id"])[:8],
                # KEINE Notiztexte — nur die Groessenordnung.
                "zeichen_vorher": len(_vergleichbar(zeile["notes"])),
                "zeichen_nachher": len(_vergleichbar(neu)),
            })

        if dry_run:
            zusammengefuehrt += 1
            continue

        try:
            conn.execute("UPDATE applications SET notes=? WHERE id=?",
                         (neu, zeile["id"]))
            conn.commit()
            zusammengefuehrt += 1
        except Exception as exc:  # pragma: no cover
            logger.debug("Zusammenfuehren fehlgeschlagen (%s): %s",
                         zeile["id"], exc)
            fehler += 1

    return {
        "status": "vorschau" if dry_run else "zusammengefuehrt",
        "betrachtet": len(zeilen),
        "zusammengefuehrt": zusammengefuehrt,
        "bereits_zusammengefuehrt": uebersprungen,
        "fehler": fehler,
        "nur_im_timeline_eintrag": {
            "anzahl": nur_timeline,
            "bedeutung": (
                "Hier steht die Notiz NUR im Anlage-Eintrag, das Feld "
                "ist leer. Es gibt also nichts zusammenzufuehren — "
                "diese Faelle bleiben unangetastet. Sie ins Feld zu "
                "schieben waere ein Umzug und damit eine eigene "
                "Entscheidung."),
        },
        "stichprobe": proben,
        "trennzeile": TRENNZEILE,
        "hinweis": (
            "Vorschau — es wurde nichts geschrieben. Mit dry_run=False "
            "stehen danach beide Fassungen im Notizfeld, getrennt durch "
            "eine benannte Zeile. Der Timeline-Eintrag bleibt "
            "unangetastet."
            if dry_run else
            "Beide Fassungen stehen jetzt im Notizfeld. Nichts wurde "
            "geloescht; der Timeline-Eintrag belegt weiterhin die "
            "Herkunft des unteren Teils."),
    }
