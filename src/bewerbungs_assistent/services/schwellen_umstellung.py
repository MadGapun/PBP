"""Deine Schwelle meint seit #1052 etwas anderes — und das gehoert gesagt.

Bis v1.7.116 war `score` die Summe aus Fachwert und Rahmen. Seit der
Trennung ist er der Fachwert allein, also eine kleinere Zahl: der
Remote-Bonus, die Naehe und ein Gehalt ueber Wunsch zaehlen nicht mehr
mit. Eine gespeicherte Schwelle filtert damit ab dem Umbau schaerfer,
**ohne dass jemand sie angefasst hat**.

Das ist die Lage aus #1012 und #988, und die Antwort dort war beide Male
dieselbe: benennen, nicht still umdeuten. Eine Einstellung, die
klammheimlich etwas anderes bedeutet als beim Setzen, ist schlimmer als
eine, die fehlt — man verlaesst sich auf sie.

**Der Vorschlag kommt aus dem Backtest, nicht aus einer
Umrechnungsformel** (Nutzerantwort 16.09.2026). Eine Formel wie "mal
0,7" waere geraten; der Backtest rechnet die Schwelle aus der eigenen
Bewerbungshistorie, also aus derselben Quelle wie die Schwellen des
Fachdaumens.

**Der Backtest laeuft nicht im Hinweis.** Er bewertet alle Bewerbungen
und eine Stichprobe der Aussortierten neu — das dauert und gehoert nicht
in eine Bedingung, die bei jedem Seitenaufbau geprueft wird. Der Hinweis
stellt nur fest, DASS eine Schwelle aus der alten Skala dasteht; die
Zahl holt, wer darauf klickt.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Gesetzt, sobald der Mensch die Schwelle nach der Umstellung angesehen
# hat — egal ob er sie geaendert oder bewusst gelassen hat. Danach
# schweigt der Hinweis. Ein Pruefer, der bei einem entschiedenen Zustand
# weiter meldet, wird nach dem zweiten Mal ignoriert (#929).
MARKE = "schwelle_nach_1052_geprueft"


def _zahl(wert) -> float:
    try:
        return float(wert or 0)
    except (TypeError, ValueError):
        return 0.0


def gesetzte_schwellen(db) -> dict:
    """Welche Schwellen stehen im Bestand — und was tun sie?

    Es sind zwei, und sie wirken an verschiedenen Stellen. Das war schon
    vor #1052 eine Fehlerquelle (#1008): `min_score_schwelle` entscheidet
    beim SPEICHERN, `schwellenwert/auto_ignore` blendet in der LISTE aus.
    """
    ergebnis = {}
    try:
        krit = db.get_search_criteria() or {}
        ergebnis["min_score_schwelle"] = _zahl(krit.get("min_score_schwelle"))
    except Exception as exc:  # pragma: no cover — nie einen Start stoppen
        logger.debug("Suchkriterien nicht lesbar: %s", exc)
        ergebnis["min_score_schwelle"] = 0.0
    ergebnis["auto_ignore"] = 0.0
    try:
        for zeile in db.get_scoring_config("schwellenwert") or []:
            if zeile.get("sub_key") == "auto_ignore":
                ergebnis["auto_ignore"] = _zahl(zeile.get("value"))
    except Exception as exc:  # pragma: no cover
        logger.debug("Scoring-Regler nicht lesbar: %s", exc)
    return ergebnis


def offen(db) -> dict:
    """Steht eine Schwelle aus der Zeit vor der Trennung im Bestand?

    Bewusst BILLIG: nur zwei Lesezugriffe, kein Backtest. Diese Frage
    wird bei jedem Seitenaufbau gestellt.

    Returns:
        {"betroffen": False} — oder die Fundstellen samt Erklaerung.
    """
    try:
        if db.get_profile_setting(MARKE):
            return {"betroffen": False, "grund": "bereits angesehen"}
    except Exception as exc:  # pragma: no cover
        logger.debug("Marke nicht lesbar: %s", exc)

    werte = gesetzte_schwellen(db)
    gesetzt = {k: v for k, v in werte.items() if v > 0}
    if not gesetzt:
        # Ohne gesetzte Schwelle gibt es nichts umzudeuten. Der Hinweis
        # bliebe sonst bei jedem frischen Profil stehen — genau der
        # Fehlalarm aus #1008, der jeden Anwender beim ersten Start
        # getroffen haette.
        return {"betroffen": False, "grund": "keine Schwelle gesetzt"}

    return {
        "betroffen": True,
        "schwellen": gesetzt,
        "erklaerung": (
            "Seit v1.7.117 (#1052) ist der Score der FACHWERT allein — "
            "Entfernung, Remote-Anteil und Gehalt zählen nicht mehr mit "
            "hinein, sondern stehen als eigener Rahmenwert daneben. Die "
            "Zahl ist damit kleiner als vorher, und deine Schwelle "
            "filtert schärfer, ohne dass du sie angefasst hast."),
        "naechster_schritt": (
            "Lass den Backtest einen neuen Wert vorschlagen: "
            "kalibrierung_backtest(). Er rechnet ihn aus deiner eigenen "
            "Bewerbungshistorie, nicht aus einer Umrechnungsformel."),
    }


def vorschlag(db, ergebnis: dict | None = None) -> dict:
    """Der neue Wert, aus dem Backtest.

    Teuer — er bewertet alle Bewerbungen und eine Stichprobe der
    Aussortierten neu. Deshalb nur auf Ansage, nie in einer Bedingung.

    Args:
        ergebnis: ein bereits gerechneter Backtest. `kalibrierung_backtest`
            reicht seinen eigenen Lauf herein — zweimal dieselbe Rechnung
            fuer dieselbe Zahl waere #963 mit Rechenzeit.
    """
    befund = {"alt": gesetzte_schwellen(db)}
    if ergebnis is None:
        try:
            from .kalibrierung import backtest
            ergebnis = backtest(db)
        except Exception as exc:  # pragma: no cover — nie eine Auskunft stoppen
            logger.debug("Backtest nicht moeglich: %s", exc)
            befund["hinweis"] = f"Der Backtest lief nicht durch: {exc}"
            return befund

    block = (ergebnis.get("varianten") or {}).get("aktuell") or {}
    if block.get("schwellen_vorschlag") is None:
        befund["hinweis"] = block.get("hinweis") or (
            "Ohne bewerbungsverknüpfte Stellen gibt es keine Grundlage "
            "für einen Vorschlag — und geraten wird nicht.")
        return befund

    befund["vorschlag"] = block["schwellen_vorschlag"]
    befund["formel"] = block.get("schwellen_formel")
    befund["bewerbungen_unter_vorschlag"] = block.get(
        "bewerbungen_unter_vorschlag")
    befund["aussortierte_ueber_vorschlag"] = block.get(
        "aussortierte_ueber_vorschlag")
    befund["setzen_mit"] = (
        "suchkriterien_setzen(min_score_schwelle=%s) für den Suchlauf, "
        "scoring_konfigurieren('setzen', 'schwellenwert', 'auto_ignore', %s) "
        "für die Liste." % (befund["vorschlag"], befund["vorschlag"]))
    return befund


def abhaken(db, grund: str = "") -> dict:
    """Der Mensch hat die Schwelle angesehen — der Hinweis schweigt.

    Abgehakt wird auch, wenn er sie bewusst LAESST. Das ist eine
    Entscheidung wie jede andere, und ein Hinweis, der sie nicht
    akzeptiert, wird zur Tapete.
    """
    try:
        db.set_profile_setting(MARKE, {"angesehen": True, "grund": grund})
    except Exception as exc:  # pragma: no cover
        return {"status": "fehler", "fehler": str(exc)}
    return {"status": "abgehakt", "grund": grund}
