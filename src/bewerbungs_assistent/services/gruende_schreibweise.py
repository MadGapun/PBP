"""Ein Grund, eine Schreibweise (#663 C66).

Ablehnungsgruende sind im Bestand ueber die Schreibweise gespalten, und
zwar an ZWEI Orten gleichzeitig. Gemessen am 10.09.2026:

| Gruppe | Grund-Eintraege | in `jobs.dismiss_reason` |
|---|---|---|
| Branche | `Falsche Branche` (50), `falsche_branche` (1) | `falsche branche` (49), `falsche_branche` (1) |
| System | `Falsches System` (50), `falsches_system` (5) | `falsches system` (50), `falsches_system` (5) |
| Duplikat | `Dublikat` (27), `duplikat` (1) | `dublikat` (18), `duplikat` (14) |

**Der Knackpunkt: Label und gespeicherter Wert sind zwei verschiedene
Zeichenketten.** In den Stellen steht `falsches system` — mit
Leerzeichen und klein, also weder wie das eine noch wie das andere
Label. `ablehnungsgrund_umbenennen` vergleicht gegen das alte LABEL und
traefe damit nur die fuenf Zeilen mit Unterstrich; die fuenfzig mit
Leerzeichen blieben stehen. Die Spaltung waere danach nicht behoben,
sondern verschoben.

Deshalb gruppiert dieser Lauf ueber einen **normalisierten Schluessel**
(Kleinschreibung; Leerzeichen, Unterstrich und Bindestrich gelten
gleich) und schreibt BEIDE Orte um.

## Welche Schreibweise gewinnt

1. **Die Whitelist-Form**, wenn die Gruppe eine enthaelt. `duplikat`
   steht in der Liste, die `stelle_bewerten` akzeptiert (#663 Teil 2) —
   jede andere Schreibweise wird dort still auf `sonstiges`
   normalisiert und verfaelscht Statistik und Lerneffekt.
2. **Sonst die haeufigste** unter den gespeicherten Werten. Sie ist
   das, was der Bestand tatsaechlich benutzt, und sie kostet am
   wenigsten Umschreibungen.

Die Wahl steht in der Vorschau, BEVOR etwas passiert, und laesst sich je
Gruppe ueberschreiben. Es sind die Daten des Nutzers — eine
Schreibweise, die PBP sich aussucht und stillschweigend durchsetzt,
waere dieselbe Bevormundung wie ein erfundener Ablehnungsgrund.

## Was als Spaltung gilt — und was nicht

Ein Grund heisst im Editor `Veraltet` und steht in den Stellen als
`veraltet`: das ist **keine** Spaltung, sondern die normale Ablage —
`stelle_bewerten` schreibt klein. Waere das ein Fall, wuerde der Lauf
saemtliche Custom-Label kleinschreiben, also Anzeige umbauen statt
Daten aufraeumen. (Genau das tat die erste Fassung; aufgefallen ist es
erst am echten Bestand.)

Als Spaltung zaehlt deshalb nur, wo es **zwei Grund-Eintraege** gibt
oder **zwei verschiedene gespeicherte Schreibweisen**.

## Was der Lauf NICHT tut

Er fasst nur zusammen, was sich in der Schreibweise unterscheidet.
`falsches_fachgebiet` und `falsches_system` bleiben getrennt — das
sind zwei Sachverhalte, und sie zusammenzuziehen waere kein Aufraeumen,
sondern Datenverlust. Aehnlichkeit entscheidet hier nichts: gruppiert
wird ausschliesslich, was nach der Normalisierung IDENTISCH ist.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# Die Gruende, die `stelle_bewerten` ohne Normalisierung akzeptiert
# (#663 Teil 2, CLAUDE.md). Eine Gruppe, die eine davon enthaelt, wird
# darauf vereinheitlicht — jede andere Schreibweise landet sonst still
# auf `sonstiges`.
WHITELIST = frozenset({
    "zu_weit_entfernt", "gehalt_zu_niedrig", "falsches_fachgebiet",
    "zu_junior", "zu_senior", "unpassendes_arbeitsmodell",
    "firma_uninteressant", "zeitarbeit", "befristet", "bereits_beworben",
    "duplikat", "kein_hochschulabschluss", "sonstiges",
})


def schluessel(wert) -> str:
    """Der Vergleichsschluessel: was nur anders geschrieben ist, ist gleich.

    Bewusst grob — Kleinschreibung und alle Trennzeichen weg. Feiner zu
    vergleichen (Aehnlichkeit, Wortstamm) wuerde SCHAETZEN, und ein
    falsch zusammengezogener Grund kostet eine Unterscheidung, die ein
    Mensch gemeint hat (dieselbe Ueberlegung wie bei der
    Anforderungs-Gruppierung in #1012).
    """
    return re.sub(r"[^a-z0-9]+", "", str(wert or "").lower())


def _einzelwerte(roh) -> tuple[list, bool]:
    """Ein `dismiss_reason` als Liste — und ob er als Liste gespeichert war.

    Seit #913 steht dort normalerweise eine JSON-Liste, weil eine Stelle
    mehrere Gruende tragen kann. Ein Vergleich auf den nackten String
    sieht davon nichts.
    """
    text = str(roh or "").strip()
    if text.startswith("["):
        try:
            geparst = json.loads(text)
            if isinstance(geparst, list):
                return [str(w) for w in geparst], True
        except Exception:
            pass
    return ([text] if text else []), False


def _gruppen(db) -> dict:
    """Alle Schreibweisen je Schluessel — aus BEIDEN Orten."""
    gruppen: dict = {}

    def merken(k, wert, art, anzahl=0, grund_id=None):
        eintrag = gruppen.setdefault(k, {"label": {}, "gespeichert": {}})
        if art == "label":
            # LISTE je Schreibweise: es kann zwei Eintraege mit exakt
            # demselben Label geben — eine frische Datenbank bringt
            # `falsches_system` als Standardgrund mit, und wer ihn von
            # Hand anlegt, bekommt einen zweiten. Ein dict nach
            # Label-Text haette den einen still verschluckt, und der
            # Lauf haette drei Durchgaenge gebraucht statt einem.
            eintrag["label"].setdefault(wert, []).append(
                {"id": grund_id, "usage": anzahl})
        else:
            eintrag["gespeichert"][wert] = (
                eintrag["gespeichert"].get(wert, 0) + anzahl)

    try:
        for g in db.get_dismiss_reasons() or []:
            k = schluessel(g.get("label"))
            if k:
                merken(k, g.get("label"), "label",
                       g.get("usage_count") or 0, g.get("id"))
    except Exception as exc:  # pragma: no cover
        logger.debug("Gruende nicht lesbar: %s", exc)

    try:
        zeilen = db.connect().execute(
            "SELECT dismiss_reason FROM jobs WHERE dismiss_reason IS NOT NULL "
            "AND TRIM(dismiss_reason) != ''").fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Stellen nicht lesbar: %s", exc)
        zeilen = []
    for z in zeilen:
        for wert in _einzelwerte(z[0])[0]:
            k = schluessel(wert)
            if k:
                merken(k, wert, "gespeichert", 1)
    return gruppen


def _ist_spaltung(eintrag: dict) -> bool:
    """Liegt hier wirklich eine Spaltung vor?

    NUR wenn es zwei Grund-Eintraege gibt oder zwei verschiedene
    gespeicherte Schreibweisen. Dass das Label `Veraltet` heisst und in
    den Stellen `veraltet` steht, ist die normale Ablage und kein Fall
    — sonst schriebe der Lauf saemtliche Custom-Label klein.

    Gezaehlt werden EINTRAEGE, nicht Schreibweisen: zwei Zeilen mit
    exakt demselben Label sind ebenfalls eine Dublette.
    """
    eintraege = sum(len(v) for v in eintrag["label"].values())
    return eintraege > 1 or len(eintrag["gespeichert"]) > 1


def _ziel(k: str, eintrag: dict) -> str:
    """Die Zielschreibweise einer Gruppe — nach der Regel im Modulkopf."""
    alle = list(eintrag["label"]) + list(eintrag["gespeichert"])
    for wert in alle:
        if wert in WHITELIST:
            return wert
    # Sonst die haeufigste unter den GESPEICHERTEN Werten: sie ist das,
    # was der Bestand benutzt, und kostet am wenigsten Umschreibungen.
    if eintrag["gespeichert"]:
        return max(eintrag["gespeichert"].items(), key=lambda p: p[1])[0]
    if eintrag["label"]:
        return max(eintrag["label"].items(),
                   key=lambda p: sum(d["usage"] for d in p[1]))[0]
    return k


def bericht(db) -> dict:
    """Welche Gruende sind nur ueber die Schreibweise gespalten?

    Schreibt nichts.
    """
    gefunden = []
    for k, eintrag in sorted(_gruppen(db).items()):
        if not _ist_spaltung(eintrag):
            continue
        schreibweisen = set(eintrag["label"]) | set(eintrag["gespeichert"])
        ziel = _ziel(k, eintrag)
        gefunden.append({
            "schluessel": k,
            "ziel": ziel,
            "aus_whitelist": ziel in WHITELIST,
            "label": [{"schreibweise": w, "id": d["id"], "usage": d["usage"]}
                      for w, liste in sorted(
                          eintrag["label"].items(),
                          key=lambda p: -sum(d["usage"] for d in p[1]))
                      for d in liste],
            "gespeichert": [{"schreibweise": w, "stellen": c}
                            for w, c in sorted(eintrag["gespeichert"].items(),
                                               key=lambda p: -p[1])],
        })
    return {
        "gruppen": gefunden,
        "anzahl": len(gefunden),
        "regel": ("Die Whitelist-Schreibweise gewinnt, wenn die Gruppe "
                  "eine enthaelt — sonst die haeufigste unter den "
                  "gespeicherten Werten."),
        "schreibt": "nichts",
    }


def vereinheitlichen(db, *, dry_run: bool = True,
                     ziele: dict | None = None) -> dict:
    """Fuehrt Schreibweisen desselben Grunds zusammen (#663 C66).

    Args:
        dry_run: Vorgabe True. Es wird NICHTS geschrieben.
        ziele: je Schluessel eine abweichende Zielschreibweise, z.B.
            ``{"falschessystem": "falsches_system"}``. Es sind die
            Daten des Nutzers — die Vorgabe ist ein Vorschlag.

    Returns:
        dict mit den Zahlen je Gruppe. Idempotent: nach einem Lauf
        gibt es je Schluessel nur noch eine Schreibweise, also nichts
        mehr zu tun.
    """
    ziele = {schluessel(k): v for k, v in (ziele or {}).items()}
    gruppen = _gruppen(db)
    conn = db.connect()

    ergebnisse = []
    stellen_gesamt = gruende_gesamt = 0

    for k, eintrag in sorted(gruppen.items()):
        if not _ist_spaltung(eintrag):
            continue
        schreibweisen = set(eintrag["label"]) | set(eintrag["gespeichert"])
        ziel = ziele.get(k) or _ziel(k, eintrag)

        stellen = _stellen_umschreiben(conn, k, ziel, nur_zaehlen=dry_run)
        gruende = _gruende_zusammenfuehren(
            db, conn, eintrag, ziel, nur_zaehlen=dry_run)

        stellen_gesamt += stellen
        gruende_gesamt += gruende
        ergebnisse.append({
            "schluessel": k,
            "ziel": ziel,
            "aus_whitelist": ziel in WHITELIST,
            "schreibweisen_vorher": sorted(schreibweisen),
            "stellen_umgeschrieben": stellen,
            "grund_eintraege_zusammengefuehrt": gruende,
        })

    if not dry_run:
        conn.commit()

    return {
        "status": "vorschau" if dry_run else "vereinheitlicht",
        "gruppen": ergebnisse,
        "stellen_umgeschrieben": stellen_gesamt,
        "grund_eintraege_zusammengefuehrt": gruende_gesamt,
        "hinweis": (
            "Vorschau — es wurde nichts geschrieben. Die Zielschreibweise "
            "je Gruppe steht oben; mit `ziele={...}` laesst sie sich "
            "ueberschreiben, mit dry_run=False wird geschrieben."
            if dry_run else
            "Je Grund gibt es jetzt eine Schreibweise — in der "
            "Grundliste UND in den Stellen. Ein zweiter Lauf findet "
            "nichts mehr."),
    }


def _stellen_umschreiben(conn, k: str, ziel: str, *,
                         nur_zaehlen: bool) -> int:
    """Alle Schreibweisen der Gruppe in `jobs.dismiss_reason` auf `ziel`."""
    try:
        zeilen = conn.execute(
            "SELECT hash, dismiss_reason FROM jobs "
            "WHERE dismiss_reason IS NOT NULL AND TRIM(dismiss_reason) != ''"
        ).fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Stellen nicht lesbar: %s", exc)
        return 0

    geaendert = 0
    for zeile in zeilen:
        werte, war_liste = _einzelwerte(zeile["dismiss_reason"])
        if not any(schluessel(w) == k and w != ziel for w in werte):
            continue
        neu: list = []
        for w in werte:
            ersetzt = ziel if schluessel(w) == k else w
            # Entdoppeln: eine Stelle mit zwei Schreibweisen desselben
            # Grunds behaelt danach eine, nicht zweimal dieselbe.
            if ersetzt not in neu:
                neu.append(ersetzt)
        geaendert += 1
        if nur_zaehlen:
            continue
        conn.execute(
            "UPDATE jobs SET dismiss_reason=? WHERE hash=?",
            (json.dumps(neu, ensure_ascii=False) if war_liste else neu[0],
             zeile["hash"]))
    return geaendert


def _gruende_zusammenfuehren(db, conn, eintrag: dict, ziel: str, *,
                             nur_zaehlen: bool) -> int:
    """Die Grund-Eintraege der Gruppe auf einen mit dem Ziel-Label."""
    labels = eintrag["label"]
    # Alle Eintraege, die NICHT schon der eine Ziel-Eintrag sind — auch
    # ein zweiter mit identischem Label zaehlt dazu.
    ziel_liste = labels.get(ziel) or []
    ziel_id = ziel_liste[0]["id"] if ziel_liste else None
    ueberzaehlig = [(w, d) for w, liste in labels.items() for d in liste
                    if d["id"] != ziel_id]
    if not ueberzaehlig:
        return 0
    if nur_zaehlen:
        return len(ueberzaehlig)
    geaendert = 0
    for wert, daten in ueberzaehlig:
        try:
            if ziel_id is None:
                # Kein Eintrag traegt schon das Ziel-Label — den ersten
                # umbenennen statt einen neuen anzulegen.
                conn.execute("UPDATE dismiss_reasons SET label=? WHERE id=?",
                             (ziel, daten["id"]))
                ziel_id = daten["id"]
            else:
                conn.execute(
                    "UPDATE dismiss_reasons SET usage_count=usage_count+? "
                    "WHERE id=?", (daten.get("usage") or 0, ziel_id))
                conn.execute("DELETE FROM dismiss_reasons WHERE id=?",
                             (daten["id"],))
            geaendert += 1
        except Exception as exc:  # pragma: no cover
            logger.debug("Grund %s nicht zusammenfuehrbar: %s", wert, exc)
    return geaendert
