"""Die Kriterien, mit denen gerechnet wird — an EINER Stelle gebaut.

Belegt in #987 (07.09.2026): von 86 Stellen eines Suchlaufs waren 86
falsch bewertet, im Schnitt um 47 Punkte zu hoch, im Maximum um 105.
`fit_analyse` auf die Spitzenstelle ergab mit denselben Kriterien 0.

Der Rechenweg war nicht schuld — `calculate_score` lief in beiden
Faellen. Verschieden waren die KRITERIEN. Der Suchlauf reicherte sie an
(`_applied_titles`, `_muss_synonyme`), `scores_neu_berechnen` und
`fit_analyse` nahmen sie roh aus der Datenbank. Damit war der
gespeicherte Score von keinem anderen Werkzeug reproduzierbar, und die
Trefferliste stand auf dem Kopf, ohne dass irgendwo ein Fehler auftrat.

Das ist zum vierten Mal dasselbe Muster (#963 fit_analyse gegen
calculate_score, #913 dismiss_job, #976 aufgaben_uebersicht) — nur eine
Ebene tiefer: **nicht die Rechnung lag doppelt, sondern ihre
Eingabe.** Ein Nadeloehr fuer die Logik nuetzt nichts, wenn jeder
Aufrufer ihr etwas anderes hineinreicht.

**Warum die Synonyme gespeichert werden und nicht live geholt.** Sie
kommen aus einer Netzabfrage (#969). Ein Score, der davon abhaengt, ob
das Netz gerade da ist, ist nicht reproduzierbar — dieselbe Stelle
haette online einen anderen Wert als offline. Also: einmal je Suchlauf
holen, in `profile_settings` ablegen, und ab da lesen ALLE Wege
dieselbe Liste. Faellt das Netz aus, bleibt die letzte bekannte Liste
gueltig; das ist ehrlicher als ein stillschweigend anderer Score.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EINSTELLUNG = "muss_synonyme"

# Status ohne Bewerbung: deren Titel sollen kein Signal mehr geben (#68).
ARCHIV_STATUS = ("abgelehnt", "zurueckgezogen")


def _beworbene_titel(db) -> list[str]:
    """Titel laufender Bewerbungen — Signal aus dem eigenen Verhalten (#68)."""
    try:
        return [
            (a.get("title") or "").lower()
            for a in db.get_applications()
            if a.get("title") and a.get("status") not in ARCHIV_STATUS
        ]
    except Exception as exc:  # pragma: no cover — darf nie eine Suche stoppen
        logger.debug("Beworbene Titel nicht lesbar: %s", exc)
        return []


def _gespeicherte_synonyme(db) -> dict[str, list[str]]:
    roh = None
    try:
        roh = db.get_profile_setting(EINSTELLUNG, None)
    except Exception as exc:  # pragma: no cover
        logger.debug("Synonyme nicht lesbar: %s", exc)
    if not isinstance(roh, dict):
        return {}
    sauber: dict[str, list[str]] = {}
    for begriff, formen in roh.items():
        if isinstance(formen, list):
            sauber[str(begriff)] = [str(f) for f in formen if str(f).strip()]
    return sauber


def synonyme_auffrischen(db, *, client=None) -> dict[str, list[str]]:
    """Alternativbezeichnungen neu holen und ablegen.

    Gehoert an den Anfang eines Suchlaufs und hinter jede Aenderung der
    MUSS-Begriffe. Bewusst NICHT in `fuer_scoring`: ein Lesevorgang darf
    keine Netzabfrage ausloesen, und ein Score darf sich nicht dadurch
    aendern, dass jemand hinsieht (#963).
    """
    from . import berufsbezeichnungen

    try:
        kriterien = db.get_search_criteria() or {}
        begriffe = [k for k in (kriterien.get("keywords_muss") or [])
                    if str(k).strip()]
        if not begriffe:
            neu: dict[str, list[str]] = {}
        else:
            neu = berufsbezeichnungen.erweitere(begriffe, client=client)

        # Ein leeres Ergebnis hat zwei Ursachen, die von aussen gleich
        # aussehen: "nichts zu finden" und "nicht erreichbar" — die
        # Abfrage schluckt ihren Ausfall bewusst, damit eine fehlende
        # Auskunft keine Suche stoppt (#969). Deshalb wird ein leeres
        # Ergebnis NICHT ueber einen vorhandenen Stand geschrieben: im
        # ersten Fall aendert das nichts, im zweiten rettet es die
        # Reproduzierbarkeit. Preis ist ein moeglicher Altbestand, wenn
        # der Markt eine Bezeichnung fallen laesst — gegen einen Score,
        # der davon abhaengt, ob das Netz gerade da ist, ist das der
        # kleinere Schaden.
        if not neu and _gespeicherte_synonyme(db):
            logger.debug("Leere Auskunft — bisheriger Stand bleibt stehen.")
            return _gespeicherte_synonyme(db)

        db.set_profile_setting(EINSTELLUNG, neu)
        return neu
    except Exception as exc:  # pragma: no cover — Ausfall darf nie stoeren
        logger.debug("Synonyme nicht auffrischbar: %s", exc)
        return _gespeicherte_synonyme(db)


def fuer_scoring(db, kriterien: dict | None = None) -> dict:
    """Die Kriterien fuer JEDE Score-Berechnung.

    Suchlauf, `scores_neu_berechnen`, `fit_analyse`, Newsletter-Import
    und die manuelle Anlage rufen ausschliesslich das hier. Wer eine
    eigene Anreicherung braucht, setzt sie OBENDRAUF — aber niemand
    baut die Basis noch einmal selbst.

    `kriterien` erlaubt es, eine bereits geladene Fassung
    weiterzureichen, statt sie ein zweites Mal aus der Datenbank zu
    holen.
    """
    krit = dict(kriterien if kriterien is not None
                else (db.get_search_criteria() or {}))
    krit["_applied_titles"] = _beworbene_titel(db)

    # Nur Synonyme zu Begriffen, die noch in den Kriterien stehen. Wer
    # ein MUSS-Keyword entfernt, soll seine Alternativbezeichnungen
    # nicht als Altlast weiterschleppen.
    aktuelle = {str(k) for k in (krit.get("keywords_muss") or []) if str(k).strip()}
    gespeichert = _gespeicherte_synonyme(db)
    krit["_muss_synonyme"] = {k: v for k, v in gespeichert.items() if k in aktuelle}

    # v1.7.39 (#989): der strenge Umgang mit Unbekanntem wirkt im Score
    # und gehoert damit in die Kriterien — sonst rechnete der Suchlauf
    # wieder anders als die Neuberechnung. Genau der Fehler aus #987.
    try:
        from . import datenguete
        if datenguete.umgang(db) == datenguete.STRENG:
            krit["_unbekannt_streng"] = True
    except Exception as exc:  # pragma: no cover — nie eine Suche stoppen
        logger.debug("Umgang mit Unbekanntem nicht lesbar: %s", exc)
    return krit
