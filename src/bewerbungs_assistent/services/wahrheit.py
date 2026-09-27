"""Woher ein Wert an einer Stelle kommt — belegt, geschaetzt, unbekannt (#954).

Die Bausteine lagen verstreut: `entfernung.befund` kennt Luftlinie und
Fahrstrecke (#950), `salary_estimated` kennzeichnet ein geschaetztes
Gehalt (#827), `anzeigenalter.einordnung` kennt "unbekannt" (#949),
`textgrenzen` erkennt eine Kappung (#952). Jeder sprach seine eigene
Sprache, keiner nannte einen Zeitpunkt, und eine von Hand gesetzte
Entfernung stand als "Luftlinie" da (#1077).

Dieses Modul beantwortet fuer sechs Felder dieselbe Frage in derselben
Form: ``{"guete", "methode", "erhoben_am", "text"}``.

Abgrenzung zu `datenguete` (#989): dort geht es darum, ob ein KRITERIUM
erfuellt ist (geprueft / verletzt / ungeprueft). Hier geht es darum,
woher der WERT kommt. Eine geschaetzte Entfernung kann ein Kriterium
erfuellen; sie bleibt trotzdem geschaetzt.

**Aus den gespeicherten Spalten abgeleitet, nicht zusaetzlich
gespeichert.** Eine zweite Ablage fuer dieselbe Auskunft liefe
auseinander (#963). Bestandsdaten tragen damit sofort die Kennzeichnung,
die ihrer Entstehung entspricht — ohne Migration (AK 6/7). Nur die
Zeitpunkte von Entfernung und Score und die Score-Grundlage sind neue
Spalten, weil sie sich aus nichts ableiten lassen.

In der Oberflaeche erscheinen nur die drei Alltagswoerter (P3 aus #953);
kein Schalter, keine Prozentzahl.
"""
from __future__ import annotations

from datetime import date

BELEGT = "belegt"
GESCHAETZT = "geschaetzt"
UNBEKANNT = "unbekannt"
STUFEN = (BELEGT, GESCHAETZT, UNBEKANNT)

#: Anzeigewort je Stufe — die einzigen Woerter, die ein Mensch sieht.
WORT = {BELEGT: "belegt", GESCHAETZT: "geschätzt", UNBEKANNT: "unbekannt"}

#: Die sechs Felder der ersten Ausbaustufe, in Anzeige-Reihenfolge.
FELDER = ("beschreibung", "anforderungen", "entfernung", "gehalt",
          "veroeffentlicht", "score")

NAMEN = {
    "beschreibung": "Anzeigentext",
    "anforderungen": "Anforderungen",
    "entfernung": "Entfernung",
    "gehalt": "Gehalt",
    "veroeffentlicht": "Veröffentlicht",
    "score": "Punkte",
}


def _eintrag(guete, methode, erhoben_am=None, text="") -> dict:
    return {"guete": guete, "methode": methode,
            "erhoben_am": (str(erhoben_am)[:19] if erhoben_am else None),
            "text": text}


# -- Score-Grundlage --------------------------------------------------

def score_stand(beschreibung, kriterien) -> str:
    """Worauf ein Score beruht: Anzeigentext und Suchkriterien.

    Dieselben Fingerabdruecke wie beim Urteil (#1051) — ohne Profil, weil
    der Score den Lebenslauf nicht liest (#1003)."""
    from .passung import kriterien_stand, text_stand
    return f"t={text_stand(beschreibung)}|k={kriterien_stand(kriterien)}"


def _stand_teile(stand) -> dict:
    teile = {}
    for stueck in str(stand or "").split("|"):
        k, trenner, v = stueck.partition("=")
        if trenner:
            teile[k] = v
    return teile


def score_ueberholt(job: dict, kriterien=None) -> list:
    """Was sich seit der Berechnung geaendert hat: ["anzeigentext",
    "suchkriterien"]. Leer, wenn nichts oder wenn keine Grundlage
    bekannt ist — ohne Grundlage wird nichts behauptet."""
    stand = job.get("score_stand")
    if not stand or stand == "mensch":
        return []
    from .passung import kriterien_stand, text_stand
    alt = _stand_teile(stand)
    geaendert = []
    if "t" in alt and alt["t"] != text_stand(job.get("description")):
        geaendert.append("anzeigentext")
    if kriterien is not None and "k" in alt and alt["k"] != kriterien_stand(kriterien):
        geaendert.append("suchkriterien")
    return geaendert


# -- Die sechs Felder -------------------------------------------------

def _beschreibung(job: dict) -> dict:
    from ..job_scraper.textgrenzen import ist_gekappt
    from .datenguete import MIN_BESCHREIBUNG
    text = (job.get("description") or "").strip()
    am = job.get("snapshot_at") or job.get("found_at")
    if len(text) < MIN_BESCHREIBUNG:
        return _eintrag(UNBEKANNT, "fehlt", None,
                        f"Nur {len(text)} Zeichen Anzeigentext.")
    if ist_gekappt(text, job.get("source")):
        return _eintrag(UNBEKANNT, "gekappt", am,
                        "Der Text ist abgeschnitten — was danach kam, "
                        "kennt PBP nicht. Nachladen holt den ganzen Text.")
    return _eintrag(BELEGT, "anzeige", am, "")


def _anforderungen(job: dict, beschreibung: dict) -> dict:
    """Dreiwertig: was nicht im Text steht, ist bei unvollstaendigem Text
    NICHT "nicht gefordert", sondern unbekannt (#952)."""
    if beschreibung["guete"] == UNBEKANNT:
        return _eintrag(UNBEKANNT, beschreibung["methode"], None,
                        "Ob eine Anforderung fehlt oder nur nicht mitkam, "
                        "lässt sich ohne vollständigen Text nicht sagen.")
    return _eintrag(BELEGT, "anzeigentext", beschreibung["erhoben_am"], "")


def _entfernung(job: dict) -> dict:
    from . import entfernung
    am = job.get("entfernung_am")
    km = job.get("distance_km")
    if job.get("entfernung_quelle") == "mensch" and km is not None:
        return _eintrag(BELEGT, "von_hand", am, f"{float(km):g} km, von dir eingetragen.")
    b = entfernung.befund(job)
    if not b:
        return _eintrag(UNBEKANNT, "keine", None,
                        "Ohne Ort oder ohne Standort gibt es keine Entfernung.")
    if b.get("entfernung_art") == entfernung.ART_FAHRSTRECKE:
        return _eintrag(BELEGT, "routing", am, b.get("entfernung_text", ""))
    return _eintrag(GESCHAETZT, "luftlinie", am, b.get("entfernung_text", ""))


def _gehalt(job: dict) -> dict:
    if not job.get("salary_min") and not job.get("salary_max"):
        return _eintrag(UNBEKANNT, "keine", None, "Die Anzeige nennt kein Gehalt.")
    am = job.get("found_at")
    if job.get("salary_quelle") == "mensch":
        return _eintrag(BELEGT, "von_hand", job.get("updated_at"), "Von dir eingetragen.")
    if job.get("salary_estimated"):
        # #827: unveraendert — eine Schaetzung zaehlt im Score nicht.
        return _eintrag(GESCHAETZT, "schaetzung_titel_ort", am,
                        "Geschätzt nach Titel und Ort; zählt nicht in die Punkte.")
    return _eintrag(BELEGT, "anzeige", am, "")


def _veroeffentlicht(job: dict, heute: date | None) -> dict:
    from . import anzeigenalter
    e = anzeigenalter.einordnung(job, heute)
    if e["guete"] == "unbekannt":
        return _eintrag(UNBEKANNT, "keine", None,
                        "Die Quelle nennt kein Datum; das Funddatum ist ein anderes.")
    return _eintrag(BELEGT, "quelle", job.get("found_at"), e.get("hinweis", ""))


def _score(job: dict, kriterien) -> dict:
    am = job.get("score_am")
    stand = job.get("score_stand")
    if stand == "mensch":
        return _eintrag(BELEGT, "von_hand", am, "Von dir gesetzt.")
    if not stand:
        return _eintrag(UNBEKANNT, "keine", None,
                        "Nicht bekannt, auf welchem Stand die Punkte gerechnet wurden.")
    geaendert = score_ueberholt(job, kriterien)
    if geaendert:
        was = " und ".join({"anzeigentext": "der Anzeigentext",
                            "suchkriterien": "deine Suchkriterien"}[g] for g in geaendert)
        return _eintrag(GESCHAETZT, "ueberholt", am,
                        f"Seit der Berechnung haben sich {was} geändert — "
                        "„Punkte neu berechnen“ bringt sie auf den Stand.")
    return _eintrag(BELEGT, "berechnet", am, "")


def felder(job: dict, kriterien=None, heute: date | None = None) -> dict:
    """Je Feld: Guete, Methode, Erhebungszeitpunkt, Satz."""
    job = job or {}
    b = _beschreibung(job)
    return {
        "beschreibung": b,
        "anforderungen": _anforderungen(job, b),
        "entfernung": _entfernung(job),
        "gehalt": _gehalt(job),
        "veroeffentlicht": _veroeffentlicht(job, heute),
        "score": _score(job, kriterien),
    }


def kurz(felder_: dict) -> str:
    """Eine Zeile fuer Claude: "Entfernung geschätzt (luftlinie), ...".
    Nennt nur, was nicht belegt ist — belegt ist der Normalfall."""
    teile = [f"{NAMEN[f]} {WORT[e['guete']]} ({e['methode']})"
             for f, e in felder_.items() if e["guete"] != BELEGT]
    return ", ".join(teile) if teile else "alle Angaben belegt"
