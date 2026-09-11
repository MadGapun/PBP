"""Konsequenz fuer erkannte Wiedergaenger (#941, v1.7.22).

Die Erkennung aus #671 arbeitete korrekt und hatte trotzdem keine
Wirkung: die Stelle wurde erkannt, als NICHT_EMPFOHLEN markiert — und
dann als aktive Stelle angelegt. Aus Nutzersicht sah das aus, als
funktioniere die Erkennung nicht.

Der Grund war ein fehlender Zustand. Eine Stelle kannte nur `aktiv`
(voll sichtbar, gleichrangig) und `aussortiert` (weg). Jede Erkennung
musste zwischen nichts tun und ungefragt loeschen waehlen, und beide
haben sich fuer nichts tun entschieden.

Jetzt drei Ausgaenge:

* **anlegen** — der Normalfall.
* **aussortieren** — erstmalig als Wiedergaenger erkannt: wird angelegt,
  aber sofort inaktiv gesetzt, mit Belegkette. Bleibt zurueckholbar.
* **ignorieren** — dieselbe Firma-Domaenen-Kombination wurde schon
  einmal aussortiert: gar nicht erst anlegen. Das ist der Kern der
  Nutzer-Vorgabe. Es geht nicht darum, dieselbe Entscheidung noch
  einmal bestaetigen zu duerfen, sondern darum, sie nicht erneut
  vorgelegt zu bekommen.

**Reposts bleiben ausgenommen.** Die Trennlinie: "Du hast diese Art
Stelle mehrfach verworfen" rechtfertigt automatisches Handeln, "Du hast
dich hier beworben" nicht — ein Repost kann eine echte zweite Chance
sein.
"""
from __future__ import annotations

from typing import Optional

from .ablehnungsgruende import ist_konform
from .wiedergaenger import (
    _domain_tokens,
    _reasons_of,
    find_wiedergaenger_pattern,
    normalize_company,
)


# Nur diese Gruende rechtfertigen eine Entscheidung OHNE Rueckfrage.
# Es sind die echten Eignungs-Urteile des Nutzers. Bewusst NICHT dabei:
#
# * `bewerbung_erstellt`, `profil_match_negativ`, `firma_blacklisted`
#   und die uebrigen System-Gruende — sie sind Buchhaltung, kein Urteil.
#   `bewerbung_erstellt` ist sogar das GEGENTEIL: die Stelle wurde
#   geschlossen, WEIL sich der Nutzer beworben hat. Live gemessen kam
#   dieser Grund 23x zusammen und haette die aehnlichsten (also besten)
#   Stellen unterdrueckt.
# * `duplikat` und `bereits_beworben` — Buchhaltung, keine Aussage
#   ueber fachliche Passung.
# * `sonstiges` — sagt per Definition nicht, woran es lag.
AUTOMATIK_GRUENDE = frozenset({
    "zu_weit_entfernt", "gehalt_zu_niedrig", "falsches_fachgebiet",
    "falsches_system", "falsche_branche", "zu_junior", "zu_senior",
    "unpassendes_arbeitsmodell", "firma_uninteressant", "zeitarbeit",
    "befristet", "kein_hochschulabschluss",
})

# v1.7.80 (#1020): Welche Gruende sich FIRMENUEBERGREIFEND uebertragen
# lassen — also in Stufe 1b, wo nur der Titel verbindet.
#
# `zu_weit_entfernt`, `gehalt_zu_niedrig` und `firma_uninteressant`
# gehoeren nicht dazu. Sie sind Eigenschaften der EINZELNEN Anzeige,
# nicht des Berufsbilds: zwei Stellen mit identischem Titel koennen
# 5 km und 500 km entfernt liegen. Gemeldet wurde eine Stelle in 9,2 km,
# die als "zu weit entfernt" aussortiert wurde — bei einem Wunschwert
# von 20 km, und die Zahl stand in derselben Datenbankzeile wie das
# Urteil.
#
# **Dieselbe Regel steht im Projekt schon zweimal richtig**, und der
# Aussortier-Pfad ist an beiden vorbeigelaufen:
#
#   tools/jobs.py          `_FACHLICHE_KO_GRUENDE` — "Gehalt/Entfernung
#                          koennen sich aendern, taugen nicht als k.o."
#   wiedergaenger.py       `_TEXTABHAENGIGE_GRUENDE` — "firma_uninteressant
#                          und zu_weit_entfernt sind ohnehin keine
#                          Aussagen ueber den Text."
#
# Der Aussortier-Pfad ist dabei der folgenreichere von dreien: die
# Empfehlung sagt nur "nicht empfohlen", die Automatik laesst die Stelle
# verschwinden. Siebzehnter Fall desselben Musters (#963 zuerst).
#
# Am Bestand gemessen: ueber eine Stichprobe von 400 aussortierten
# Stellen greift das Titel-Muster bei 241 — **108 davon (45 %) auf einem
# Grund, der nichts ueber die Art der Stelle sagt**, 20 davon
# `zu_weit_entfernt` bei Stellen INNERHALB des Wunschwerts. Ein
# einzelner generischer Titel trug dabei 86 Belege.
#
# In Stufe 1 (GLEICHE Firma) bleiben alle drei erlaubt — dort ist der
# Bezug gegeben: derselbe Arbeitgeber am selben Ort ist beim naechsten
# Mal wieder gleich weit weg.
UEBERTRAGBARE_GRUENDE = frozenset({
    # Aussagen ueber die ART der Stelle.
    "falsches_fachgebiet", "falsches_system", "falsche_branche",
    "zu_junior", "zu_senior", "kein_hochschulabschluss",
    "unpassendes_arbeitsmodell",
    # Erkennbar an Firma und Titel, also ebenfalls uebertragbar.
    "zeitarbeit", "befristet",
})

#: Gruende, gegen die ein gemessenes Feld ANTRITT. Liegt die Zahl vor
#: und widerspricht sie dem uebertragenen Urteil, gewinnt die Zahl.
MESSBARE_GRUENDE = frozenset({"zu_weit_entfernt", "gehalt_zu_niedrig"})


def _handlungsgruende(job: dict) -> list:
    """Nur echte Eignungs-Urteile rechtfertigen eine Automatik.

    Live-Befund vom 19.08.2026, der diese Regel erzwungen hat: die
    bestbewertete Stelle im Bestand (Score 83, acht MUSS-Treffer) waere
    automatisch aussortiert worden, weil vier Alt-Eintraege den
    FREITEXT-Grund 'zu "hands-on"' trugen und ueber gemeinsame
    Fachtokens zusammenfielen.

    Freitext ist eine Notiz, keine Kategorie — er taugt fuer die
    Anzeige, aber nicht als Grundlage einer Entscheidung, die ohne
    Rueckfrage getroffen wird. Der Altbestand enthaelt allein 101
    verschiedene Freitext-Gruende (#913).
    """
    gruende = []
    for g in _reasons_of(job):
        if not ist_konform(g):
            continue
        # auto:-Praefix abstreifen, dann gegen die Positivliste pruefen.
        kern = g.split(":")[1] if g.startswith("auto:") and ":" in g[5:] + ":" else g
        kern = kern.strip().lower()
        if kern in AUTOMATIK_GRUENDE:
            gruende.append(kern)
    return gruende

# Ab wie vielen gleichgesinnten Aussortierungen die Automatik greift.
# Bewusst gleich dem Default aus #671 — die Automatik soll dieselbe
# Schwelle nutzen wie die Anzeige, sonst erklaert die Warnung etwas
# anderes als die Konsequenz.
AUTOMATIK_SCHWELLE = 2


def _domain_schluessel(company: str, title: str) -> Optional[tuple]:
    """Firma + fachliche Titel-Tokens als vergleichbarer Schluessel.

    WICHTIG fuer die Abgrenzung der beiden Stufen: hier wird die
    Token-Menge EXAKT verglichen, waehrend der Wiedergaenger-Check aus
    #671 schon bei Ueberschneidung anschlaegt. Daraus ergibt sich die
    Arbeitsteilung:

    * identische Kombination ("PDM Spezialist" nach "PDM Berater",
      dieselbe Firma) -> **ignorieren**. Genau diese Entscheidung hat
      der Nutzer schon getroffen; sie ihm erneut vorzulegen ist die
      Stoerung, um die es im Issue geht.
    * ueberlappende, aber andere Kombination ("PLM Architect
      Teamcenter" nach "PLM Berater CAD") -> **aussortieren**. Aehnlich
      genug fuer eine Automatik, verschieden genug, um sie sichtbar in
      der eingeklappten Liste zu belassen.
    """
    firma = normalize_company(company)
    tokens = _domain_tokens(title)
    if not firma or not tokens:
        return None
    return (firma, frozenset(tokens))


def bereits_aussortierte_schluessel(dismissed: list) -> set:
    """Alle Firma-Domaenen-Kombinationen, die schon einmal weg waren."""
    schluessel = set()
    for j in dismissed or []:
        if not _handlungsgruende(j):
            continue
        k = _domain_schluessel(j.get("company"), j.get("title"))
        if k:
            schluessel.add(k)
    return schluessel


# Firmenuebergreifend wird BEWUSST spaeter gehandelt als firmenbezogen.
# "Dieselbe Firma zweimal" ist ein enger Beleg; "dieselbe Fachrichtung
# irgendwo dreimal" ist eine Aussage ueber ein ganzes Feld und darf
# nicht bei zwei Zufaellen zuschlagen.
TITEL_SCHWELLE = 3


def find_titel_muster(db, title: str, dismissed: Optional[list] = None,
                      *, schwellwert: int = TITEL_SCHWELLE,
                      target_hash: Optional[str] = None) -> Optional[dict]:
    """Wiedergaenger ueber Titel und Fachgebiet, unabhaengig von der Firma.

    Der firmenbezogene Check aus #671 uebersieht den Fall, dass dieselbe
    Art Stelle bei wechselnden Anbietern auftaucht — Regressionsfall aus
    #941: ein CRM-Titel wurde dreimal aussortiert ("falsche Branche",
    "falsches_fachgebiet", "duplikat"), tauchte beim naechsten Lauf bei
    einem anderen Anbieter wieder auf und wurde nicht erkannt.

    Verlangt wird eine gemeinsame Fach-Token-Schnittmenge ueber ALLE
    Belege — ein einzelnes geteiltes Allerweltswort genuegt nicht.

    v1.7.80 (#1020): und es zaehlen nur Gruende aus
    `UEBERTRAGBARE_GRUENDE`. Eine Entfernung, ein Gehalt oder ein Urteil
    ueber die Firma sagen nichts ueber eine ANDERE Firma mit aehnlichem
    Titel.
    """
    tokens = _domain_tokens(title)
    if not tokens:
        return None
    if dismissed is None:
        dismissed = _lade(db)

    nach_grund: dict = {}
    for j in dismissed or []:
        if target_hash and j.get("hash") == target_hash:
            continue
        # #1020: firmenuebergreifend zaehlen nur Gruende, die die ART
        # der Stelle beschreiben. Die Filterung sitzt HIER und nicht
        # beim Aufrufer — sonst haette der naechste Aufrufer sie wieder
        # nicht (dieselbe Bauform, um die es in diesem Issue geht).
        gruende = [g for g in _handlungsgruende(j)
                   if g in UEBERTRAGBARE_GRUENDE]
        if not gruende:
            continue
        gemeinsam = tokens & _domain_tokens(j.get("title"))
        if not gemeinsam:
            continue
        for g in gruende:
            eintrag = nach_grund.setdefault(g, {"anzahl": 0, "tokens": None,
                                                "beispiele": []})
            eintrag["anzahl"] += 1
            eintrag["tokens"] = (gemeinsam if eintrag["tokens"] is None
                                 else eintrag["tokens"] & gemeinsam)
            if len(eintrag["beispiele"]) < 3:
                eintrag["beispiele"].append(j.get("title"))

    for grund, e in sorted(nach_grund.items(), key=lambda x: -x[1]["anzahl"]):
        # Die Schnittmenge muss ueber alle Belege bestehen bleiben,
        # sonst war es dreimal etwas anderes.
        if e["anzahl"] >= schwellwert and e["tokens"]:
            return {"top_grund": grund, "anzahl": e["anzahl"],
                    "tokens": sorted(e["tokens"]), "beispiele": e["beispiele"]}
    return None



def _zahl_widerspricht(db, job: dict, grund: str) -> str:
    """Widerspricht ein GEMESSENES Feld dem uebertragenen Urteil?

    Gibt die Begruendung zurueck, wenn ja — sonst einen leeren String.

    Der Melder hat es auf den Punkt gebracht: die Entfernung stand in
    DERSELBEN Datenbankzeile wie das Urteil "zu weit entfernt", und sie
    lag innerhalb des Wunschwerts. Ein Muster darf eine vorhandene Zahl
    nicht ueberstimmen.

    Fuer die Gehaltsseite fragt die Pruefung das Nadeloehr aus #1017
    statt die Regel ein drittes Mal zu formulieren — dort steckt auch
    schon, dass eine SCHAETZUNG nichts belegt (#827).
    """
    if grund not in MESSBARE_GRUENDE:
        return ""
    try:
        criteria = db.get_search_criteria() or {}
    except Exception:  # pragma: no cover
        return ""

    if grund == "zu_weit_entfernt":
        dist = job.get("distance_km")
        if dist is None:
            return ""
        karte = criteria.get("max_entfernung") or {}
        art = (job.get("employment_type") or "festanstellung").lower()
        grenze = None
        if isinstance(karte, dict) and karte:
            grenze = karte.get(art)
            if grenze is None:
                grenze = max((float(v) for v in karte.values() if v),
                             default=None)
        if grenze is None:
            grenze = criteria.get("max_entfernung_km")
        try:
            grenze = float(grenze) if grenze else None
            dist = float(dist)
        except (TypeError, ValueError):
            return ""
        if grenze and dist <= grenze:
            return (f"{dist:.1f} km liegt innerhalb deiner "
                    f"{grenze:.0f} km — die gemessene Entfernung schlaegt "
                    f"das Titel-Muster.")
        return ""

    # gehalt_zu_niedrig
    from . import gehalt_vergleich as _gv

    befund = _gv.vergleich(job, criteria)
    if befund["stand"] != _gv.VERGLEICHBAR:
        return ""
    if befund["erfuellt"]:
        return (f"{befund['job_text']} erreicht deinen Wunsch "
                f"({befund['wunsch_text']}) — die belegte Zahl schlaegt "
                f"das Titel-Muster.")
    return ""


def entscheide(db, job: dict, *, dismissed: Optional[list] = None,
               bekannte_schluessel: Optional[set] = None,
               ist_repost: bool = False) -> dict:
    """Was soll mit einem frischen Treffer geschehen?

    Args:
        job: Der Rohtreffer (title, company, hash).
        dismissed: Vorab geladene aussortierte Stellen — beide Pruefungen
            brauchen sie, und ohne Preload laedt jeder Treffer den
            vollen Bestand neu.
        bekannte_schluessel: Ergebnis von
            `bereits_aussortierte_schluessel`, ebenfalls vorab.
        ist_repost: Auf diese Stelle wurde bereits beworben — dann wird
            NIE automatisch gehandelt.

    Returns:
        dict mit `aktion` (anlegen|aussortieren|ignorieren), `grund`
        (Vokabular-konform, fuer den Lerneffekt) und `beleg` (Freitext
        fuer dismiss_note — nie ins Lern-Feld, siehe #913).
    """
    if ist_repost:
        return {"aktion": "anlegen", "grund": "", "beleg": "",
                "hinweis": "Repost — bewusst nur markiert, nicht aussortiert."}

    titel = job.get("title") or ""
    firma = job.get("company") or ""

    # Stufe 2: schon einmal weggeworfen -> gar nicht erst zeigen.
    if bekannte_schluessel is None:
        bekannte_schluessel = bereits_aussortierte_schluessel(
            dismissed if dismissed is not None else _lade(db))
    k = _domain_schluessel(firma, titel)
    if k and k in bekannte_schluessel:
        return {
            "aktion": "ignorieren",
            "grund": "duplikat",
            "beleg": (f"Diese Firma-Fachgebiet-Kombination wurde bereits "
                      f"aussortiert ({titel[:60]})."),
        }

    # Stufe 1: erstmalig als Wiedergaenger erkannt -> aussortieren.
    muster = find_wiedergaenger_pattern(
        db, firma, titel,
        schwellwert=AUTOMATIK_SCHWELLE,
        target_hash=job.get("hash"),
        dismissed=dismissed,
    )
    if muster:
        grund = muster.get("top_grund") or "sonstiges"
        anzahl = muster.get("anzahl") or AUTOMATIK_SCHWELLE
        # #1020: eine vorhandene Zahl schlaegt das Muster. In Stufe 1
        # bleiben `zu_weit_entfernt` und `gehalt_zu_niedrig` erlaubt —
        # derselbe Arbeitgeber am selben Ort ist beim naechsten Mal
        # wieder gleich weit weg. Hat sich die Zahl aber geaendert,
        # steht sie in derselben Zeile wie das Urteil.
        _widerspruch = _zahl_widerspricht(db, job, grund)
        if not _widerspruch:
            return {
                "aktion": "aussortieren",
                "grund": grund,
                "beleg": (f"Wiedergaenger: dieselbe Firma wurde bereits "
                          f"{anzahl}x mit Grund '{grund}' aussortiert."),
                "muster": muster,
            }
        muster = None
        _stufe1_widerspruch = _widerspruch
    else:
        _stufe1_widerspruch = ""

    # Stufe 1b: dieselbe Art Stelle, andere Firma (#941-Regressionsfall).
    titel_muster = find_titel_muster(db, titel, dismissed,
                                     target_hash=job.get("hash"))
    if titel_muster:
        grund = titel_muster.get("top_grund") or "sonstiges"
        # Doppelter Boden: nach der Filterung kann hier kein messbarer
        # Grund mehr ankommen — geprueft wird trotzdem, weil die Menge
        # sich aendern kann und die Zahl dann wieder ueberstimmt wuerde.
        _widerspruch = _zahl_widerspricht(db, job, grund)
        if _widerspruch:
            return {"aktion": "anlegen", "grund": "", "beleg": "",
                    "hinweis": _widerspruch}
        return {
            "aktion": "aussortieren",
            "grund": grund,
            "beleg": (f"Wiedergaenger nach Fachgebiet: "
                      f"{titel_muster['anzahl']}x mit Grund '{grund}' "
                      f"aussortiert (gemeinsam: "
                      f"{', '.join(titel_muster['tokens'][:4])})."),
            "muster": titel_muster,
        }

    return {"aktion": "anlegen", "grund": "", "beleg": "",
            **({"hinweis": _stufe1_widerspruch} if _stufe1_widerspruch
               else {})}


def _lade(db) -> list:
    try:
        return db.get_dismissed_jobs()
    except Exception:
        return []


def anwenden(db, jobs: list, *, beworbene_hashes: Optional[set] = None) -> dict:
    """Wendet die Automatik auf eine frische Trefferliste an.

    Gibt die zu speichernden Stellen zurueck (ignorierte fehlen, zum
    Aussortieren markierte tragen `is_active=0` samt Begruendung) sowie
    die Zaehler fuer die Abschlussmeldung.

    Die Zaehlung ist keine Kosmetik: automatisches Aussortieren ohne
    Rueckfrage hat den Preis, dass eine zu scharfe Regel niemandem
    auffaellt. Die Zahl in der Abschlussmeldung ist die Gegenmassnahme.
    """
    dismissed = _lade(db)
    schluessel = bereits_aussortierte_schluessel(dismissed)
    beworbene = beworbene_hashes or set()

    behalten: list = []
    zaehler = {"automatisch_aussortiert": 0, "ignoriert": 0}
    belege: list = []

    for job in jobs:
        e = entscheide(
            db, job, dismissed=dismissed, bekannte_schluessel=schluessel,
            ist_repost=bool(job.get("hash") in beworbene
                            or job.get("_repost_verdacht")),
        )
        if e["aktion"] == "ignorieren":
            zaehler["ignoriert"] += 1
            continue
        if e["aktion"] == "aussortieren":
            job["is_active"] = 0
            # #913: das Lern-Feld bekommt NUR Vokabular, der Freitext
            # geht nach dismiss_note.
            job["dismiss_reason"] = f"auto:{e['grund']}:wiedergaenger"
            job["dismiss_note"] = e["beleg"]
            job["_auto_aussortiert"] = True
            zaehler["automatisch_aussortiert"] += 1
            belege.append({"titel": job.get("title"), "grund": e["grund"]})
        behalten.append(job)

    return {"jobs": behalten, "zaehler": zaehler, "belege": belege}
