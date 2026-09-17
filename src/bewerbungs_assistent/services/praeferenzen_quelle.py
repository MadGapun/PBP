"""Gehalt und Saetze stehen an EINER Stelle: den Suchkriterien (#1055).

## Der Befund

Dieselbe Angabe wurde an zwei Orten gefuehrt:

* **Suchkriterien** — die Einstellungsseite, die der Mensch sieht und
  pflegt, und die Quelle, die das Scoring liest.
* **Job-Praeferenzen am Profil** — aus der Ersterfassung im Gespraech,
  ohne Eingabefeld in irgendeiner Oberflaeche, also nie nachgezogen.

Am 17.09.2026 in einem Bestand gemessen: Mindestgehalt 75.000 gegen
80.000, Tagessatz 800 gegen 900, Ziel-Tagessatz 1.350 gegen 1.200.

**Der teuerste Leser war `fit_analyse`.** Es holte die Kriterien durch
das Nadeloehr aus #987 und ueberschrieb `min_gehalt` danach mit dem Wert
aus den Praeferenzen. Dieselbe Stelle bekam damit in der Liste einen
anderen Rahmenwert als in der Detailansicht — #963 an einer Stelle, an
der beide Zahlen "dein Minimum" heissen.

## Die Entscheidung

Nutzervorgabe vom 17.09.2026, woertlich: *"Nur die Werte, die auf der
Einstellungsseite stehen, gelten. Wenn woanders Gehaltsangaben oder
Wuensche stehen, sind die dort falsch und muessen weg."*

Kein Abgleich, keine Uebernahme, kein "der neuere gewinnt" — die
Praeferenzen verlieren diese Felder. Was dort stand, wird beim
Entfernen AUFGESCHRIEBEN und einmal genannt: ein gesetzter Wert darf
nicht still verschwinden (#1053).

## Was bleibt

Entfernt werden nur Felder, die auf der Einstellungsseite ein
Gegenstueck haben. `arbeitsmodell`, `reisebereitschaft`,
`remote_anteil`, `max_vor_ort_tage` und `umzug_moeglich` haben keines —
sie bleiben, auch wenn sie heute nur die Profil-Zusammenfassung liest.
Sie zu loeschen waere kein Aufraeumen, sondern ein Datenverlust (#989:
eine Luecke gehoert benannt, nicht gefuellt — und eine Angabe ohne
zweiten Ort gehoert nicht entfernt).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Die Marke haelt fest, WAS entfernt wurde — nicht, DASS aufgeraeumt
# wurde. Ohne die Werte koennte niemand mehr nachsehen, was im Profil
# stand, und der Hinweis waere eine Behauptung.
MARKE = "praeferenzen_gehalt_entfernt_1055"

# Praeferenz-Feld -> Schluessel in den Suchkriterien.
#
# Die Namen unterscheiden sich, und genau das hat die Doppelung so lange
# unsichtbar gemacht: "ziel_gehalt" und "wunsch_gehalt" sehen aus wie
# zwei Angaben und sind eine (#931 hat den Nennwert vom Minimum
# getrennt — hier kommt er aus den Kriterien).
DOPPELTE_FELDER: dict[str, str] = {
    "min_gehalt": "min_gehalt",
    "ziel_gehalt": "wunsch_gehalt",
    "min_tagessatz": "min_tagessatz",
    "ziel_tagessatz": "wunsch_tagessatz",
    "min_stundensatz": "min_stundensatz",
    "ziel_stundensatz": "wunsch_stundensatz",
    # #1000 hat den Altwert in den Kriterien benannt statt umgedeutet;
    # die dritte Fassung im Profil hat ohnehin keinen Leser.
    "max_entfernung_km": "max_entfernung_km",
}


def _zahl(wert):
    if wert in (None, "", 0, "0"):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def wunschwerte(db) -> dict:
    """Gehalt und Saetze — aus den Suchkriterien, und nur von dort.

    Das ist das Nadeloehr fuer alle Wege, die bisher die Praeferenzen
    gelesen haben (`gehalt_extrahieren`, `gehalt_marktanalyse`,
    `/api/salary-stats`, `fit_analyse`). Vier Leser mit vier eigenen
    `prefs.get(...)`-Zeilen waren vier Gelegenheiten, die Umstellung an
    einer davon zu vergessen.

    Returns:
        Ein dict mit den Praeferenz-NAMEN als Schluessel (`min_gehalt`,
        `ziel_gehalt`, ...), damit die Aufrufer ihre Antwortform
        behalten — die Werte kommen aus den Kriterien.
    """
    try:
        krit = db.get_search_criteria() or {}
    except Exception as exc:  # pragma: no cover — nie eine Auskunft stoppen
        logger.debug("Suchkriterien nicht lesbar (#1055): %s", exc)
        return {}
    werte = {}
    for pref_feld, krit_feld in DOPPELTE_FELDER.items():
        wert = _zahl(krit.get(krit_feld))
        if wert is not None:
            werte[pref_feld] = wert
    return werte


def gefundene_doppelung(db) -> dict:
    """Welche Praeferenz-Felder stehen noch im Profil — und was sagen die
    Kriterien dazu?

    Reine Auskunft, sie schreibt nichts. `bereinigen` benutzt sie, und
    die Diagnose kann sie zeigen, ohne etwas zu veraendern.
    """
    try:
        profil = db.get_profile() or {}
    except Exception as exc:  # pragma: no cover
        logger.debug("Profil nicht lesbar (#1055): %s", exc)
        return {}
    from .profile_service import get_profile_preferences

    prefs = get_profile_preferences(profil)
    krit_werte = wunschwerte(db)
    befund = {}
    for feld in DOPPELTE_FELDER:
        wert = prefs.get(feld)
        if wert in (None, "", 0, "0"):
            continue
        befund[feld] = {
            "im_profil": wert,
            "in_den_suchkriterien": krit_werte.get(feld),
            "gilt": krit_werte.get(feld),
        }
    return befund


def bereinigen(db) -> dict:
    """Entfernt die doppelt gefuehrten Felder aus den Praeferenzen.

    Idempotent: beim zweiten Lauf gibt es nichts mehr zu entfernen, und
    die Marke bleibt unveraendert stehen — sie ist der Beleg dafuer, was
    einmal dastand, nicht ein Zaehler fuer Laeufe.

    Geschrieben wird ueber `save_profile`, also denselben Weg, den auch
    `profil_bearbeiten` nimmt. Ein eigenes UPDATE auf die Spalte waere
    der vierte Schreiber an derselben Tabelle (#1053 MERKE 2).
    """
    befund = gefundene_doppelung(db)
    try:
        profil = db.get_profile() or {}
        from .profile_service import get_profile_preferences

        prefs = dict(get_profile_preferences(profil))
    except Exception as exc:  # pragma: no cover
        logger.debug("Profil nicht lesbar (#1055): %s", exc)
        return {"entfernt": 0}

    # Auf der Bestandskopie standen zwei der Felder mit `null` da
    # (`max_entfernung_km`, `min_stundensatz`). Sie tragen keinen Wert,
    # also gibt es nichts zu belegen — aber der SCHLUESSEL bleibt sonst
    # in den Praeferenzen liegen, und `profil_bearbeiten` weist ihn seit
    # diesem Release ab: ein Feld, das dasteht und das niemand mehr
    # setzen kann. Es wird still entfernt und getrennt gezaehlt.
    leere = [f for f in DOPPELTE_FELDER
             if f in prefs and f not in befund]
    if not befund and not leere:
        return {"entfernt": 0}

    # Was DIESER Lauf entfernt — der Beleg unten waechst ueber alle
    # Laeufe, die Zahl im Ergebnis darf das nicht tun.
    jetzt_entfernt = len(befund)

    try:
        for feld in list(befund) + leere:
            prefs.pop(feld, None)
        db.save_profile({
            "name": profil.get("name"), "email": profil.get("email"),
            "phone": profil.get("phone"), "address": profil.get("address"),
            "city": profil.get("city"), "plz": profil.get("plz"),
            "country": profil.get("country"), "birthday": profil.get("birthday"),
            "nationality": profil.get("nationality"),
            "summary": profil.get("summary"),
            "informal_notes": profil.get("informal_notes"),
            "preferences": prefs,
        })
        # Der Beleg wandert in die Einstellungen, BEVOR jemand danach
        # fragt. Ohne ihn waere der Hinweis eine Behauptung ueber Werte,
        # die niemand mehr nachlesen kann (#1053).
        if befund:
            vorher = db.get_profile_setting(MARKE) or {}
            if isinstance(vorher, dict) and vorher.get("felder"):
                befund = {**befund, **vorher["felder"]}
            db.set_profile_setting(MARKE, {"felder": befund})
    except Exception as exc:  # pragma: no cover — nie einen Start stoppen
        logger.warning("Praeferenzen-Bereinigung (#1055) fehlgeschlagen: %s", exc)
        return {"entfernt": 0, "fehler": str(exc)}

    logger.info("Praeferenzen bereinigt (#1055): %d Gehaltsfeld(er) mit Wert "
                "und %d leere entfernt, es gelten die Suchkriterien",
                jetzt_entfernt, len(leere))
    return {"entfernt": jetzt_entfernt, "felder": befund,
            "leere_entfernt": len(leere)}


def entfernte_werte(db) -> dict:
    """Was wurde entfernt — fuer den einmaligen Hinweis.

    Solange der Mensch den Hinweis nicht weggeklickt hat, steht hier,
    was im Profil stand und was stattdessen gilt.
    """
    try:
        beleg = db.get_profile_setting(MARKE) or {}
    except Exception as exc:  # pragma: no cover
        logger.debug("Beleg nicht lesbar (#1055): %s", exc)
        return {}
    if not isinstance(beleg, dict):
        return {}
    return beleg.get("felder") or {}
