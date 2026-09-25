"""Profil-Klassifikation + Quellen-Empfehlung (#590 Aufgabe B).

**Seit v1.7.125 (#1070) eine ABGELEITETE SICHT.** Die fachliche
Einordnung steht in `services/berufsfeld.py` und kennt drei Angaben
(Feld, Niveau, Form); hier wird daraus der eine Schluessel gebildet, auf
den Elwosa-Linien, Tests und die Wiki-Seite seit #590 zeigen. Der
Schluessel bleibt damit gueltig, ohne dass er weiter drei Fragen
gleichzeitig beantworten muss.

Was sich dadurch AENDERT, und zwar sichtbar: die Quellen-Empfehlung
kommt aus der Kombination statt aus dem Schluessel. Ein freiberuflicher
Senior-Entwickler heisst weiter `freelance` und bekommt jetzt die
Freelance-Boersen UND die Tech-Quellen.

User-Vorgabe: PBP wird nicht nur fuer High-Performer gebaut. Studenten,
Kassiererinnen, Pfleger, Handwerker — alle sollen sinnvolle Suchquellen
empfohlen bekommen, nicht nur LinkedIn/Workday.

Heuristik laeuft offline auf dem aktuellen Profil und gibt einen
Cluster-Schluessel zurueck. Der Schluessel mappt auf eine empfohlene
Quellen-Liste. Der User behaelt das letzte Wort — Empfehlungen sind
nicht-bindend, er kann jede Quelle einzeln zu-/abschalten.
"""

from __future__ import annotations

import re

from typing import Optional


PROFILE_TYPE_LABELS = {
    "student":            "Student / Werkstudent",
    "service":            "Service / Dienstleistung",
    "trade":              "Handwerk / Trade",
    "tech_junior":        "Tech-Einsteiger (Junior)",
    "tech_senior":        "Tech-Senior",
    "engineering_senior": "Engineering-Senior",
    "freelance":          "Freelancer",
    "executive":          "Fuehrungskraft",
    "health":             "Gesundheit / Pflege",
    "education":          "Erziehung / Bildung",
    "retail_logistics":   "Handel / Logistik",
    "hospitality":        "Gastronomie / Hotellerie",
    "creative":           "Kreativ / Medien",
    "admin_finance":      "Verwaltung / Finanzen",
    # #1070: Feld ohne Alt-Schluessel — siehe _FELD_ZU_TYP.
    "wissenschaft":       "Wissenschaft / Forschung",
    "mixed":              "Gemischt / Unbekannt",
}


#: Welches Feld auf welchen der bis v1.7.124 gebrauchten Schluessel
#: faellt. Die Zuordnung ist eine ANZEIGE-Entscheidung — die Quellen
#: kommen seit #1070 nicht mehr von hier, sondern aus der Kombination.
_FELD_ZU_TYP = {
    "gesundheit": "health",
    "bildung": "education",
    "gastgewerbe": "hospitality",
    "medien": "creative",
    "logistik": "retail_logistics",
    "handel": "retail_logistics",
    "verwaltung": "admin_finance",
    "recht": "admin_finance",
    "handwerk": "trade",
    "produktion": "trade",
    "landwirtschaft": "trade",
    "sicherheit": "service",
    "dienstleistung": "service",
    # Zwei Felder tragen ihre Stufe im alten Schluessel — genau die
    # Vermischung, die #1070 aufloest. Die Ableitung bildet sie nach,
    # damit nichts bricht, was heute darauf zeigt.
    # Der Name traegt die Stufe, obwohl es fuer das Ingenieurwesen nur
    # diesen EINEN Alt-Schluessel gibt — genau die Vermischung, die
    # #1070 aufloest. Das Feld steht daneben und ist das genauere Wort.
    "ingenieurwesen": "engineering_senior",
    "it": "tech_senior",
    # Fuer die Wissenschaft gab es nie einen Schluessel. Sie bekommt
    # einen eigenen, statt in "mixed" zu fallen — "nicht eingeordnet"
    # und "eingeordnet, aber ohne Alt-Schluessel" sind zwei
    # verschiedene Dinge (#989).
    "wissenschaft": "wissenschaft",
}


def _typ_ableiten(ein: dict) -> str:
    """Der eine Schluessel aus den drei Angaben.

    Reihenfolge ist Absicht und folgt dem alten Verhalten: Studium und
    Freiberuflichkeit ueberschreiben das Feld, danach die Fuehrungsstufe.
    Neu ist, dass dabei NICHTS mehr verlorengeht — das Feld steht in
    derselben Antwort, und die Quellen kommen aus allen drei Angaben.
    """
    formen = ein.get("formen") or []
    if "werkstudent" in formen or "praktikum" in formen:
        return "student"
    if "freiberuflich" in formen:
        return "freelance"
    if ein.get("niveau") == "experte":
        return "executive"
    feld = ein.get("feld")
    if not feld:
        return "mixed"
    typ = _FELD_ZU_TYP.get(feld, "mixed")
    if typ == "tech_senior":
        # Der Junior/Senior-Schnitt der ALTEN Schluessel lief ueber die
        # BERUFSJAHRE, und dabei bleibt es. Das `niveau` ist bewusst
        # etwas anderes: es beschreibt die Komplexitaet der Taetigkeit
        # und ist ohne Bezeichnung im Titel auf `fachkraft` gedeckelt.
        #
        # Die beiden zu vermischen war ein eigener Fehler beim Umbau:
        # ein Softwareentwickler mit zehn Jahren wurde `tech_junior`,
        # ein PLM-Berater sogar `trade`. Gefunden hat es die volle
        # Suite, nicht die gezielte Auswahl.
        if ein.get("berufsjahre", 0) >= 7:
            return "tech_senior"
        return "tech_junior"
    return typ


_NIVEAU_BELEG_TEXT = {"titel": "Bezeichnung", "ziel": "aus dem Ziel",
                      "quereinstieg": "Quereinstieg, gedeckelt"}
_FORM_BELEG_TEXT = {"praeferenz": "Job-Praeferenz",
                    "aktuelle_stationen": "aktuelle Stationen",
                    "ausbildung": "laufendes Studium", "titel": "Bezeichnung"}

#: Belege, die aus einer Aussage stammen und nicht nur aus Berufsjahren.
_BELEGT = ("titel", "ziel", "praeferenz", "aktuelle_stationen", "ausbildung")


def _konfidenz(ein: dict, typ: str) -> float:
    """Wie sicher ist der SCHLUESSEL?

    Er entsteht aus drei Angaben, und je nach Profil traegt eine andere
    davon. Ein Geschaeftsfuehrer ohne erkennbares Fachfeld ist
    trotzdem sicher eine Fuehrungskraft; eine Studentin ohne Stationen
    ist sicher Studentin. Die Konfidenz auf das FELD allein zu stuetzen
    haette beide mit 0,3 ausgewiesen, obwohl der Schluessel stimmt.

    Eine feste Zahl je Zweig — so war es bis v1.7.124 — sagte ueber den
    Einzelfall gar nichts.
    """
    # Der Schluessel kam aus der Form oder aus der Fuehrungsstufe, und
    # beide standen in einer Berufsbezeichnung.
    # #1074: seit die Form aus Praeferenz und aktuellen Stationen kommt,
    # heisst ihr Beleg nicht mehr nur "titel" — belegt ist sie trotzdem.
    form_belegt = ein.get("form_beleg") in _BELEGT
    niveau_belegt = ein.get("niveau_beleg") in _BELEGT
    aus_form = typ in ("student", "freelance") and form_belegt
    aus_niveau = typ == "executive" and niveau_belegt
    if aus_form or aus_niveau:
        wert = 0.8
        if ein.get("feld"):
            wert += 0.05  # Feld UND Form erkannt — beides stuetzt sich
        return round(min(0.9, wert), 2)

    if ein.get("unsicher"):
        return 0.3

    # Ein einzelner klarer Begriff ("Grafikdesignerin") ist ein solides
    # Signal — die Basis liegt deshalb bei 0,65 und nicht darunter.
    stark = next((f["gewicht"] for f in ein.get("alle_felder") or []), 0)
    wert = 0.65 + min(0.15, 0.05 * stark)
    if niveau_belegt:
        wert += 0.05
    if form_belegt:
        wert += 0.05
    return round(min(0.9, wert), 2)


def suchbegriffe_aus(db) -> list:
    """Die MUSS-Begriffe des aktiven Profils — das Ziel der Suche (#1074).

    Ohne sie ordnete die Einordnung nur nach dem Lebenslauf ein, und ein
    Quereinsteiger bekam die Quellen des Berufs, aus dem er heraus will.
    """
    try:
        return list((db.get_search_criteria() or {}).get("keywords_muss") or [])
    except Exception:  # pragma: no cover — die Einordnung nie blockieren
        return []


def detect_profile_type(profile: Optional[dict], suchbegriffe=None) -> dict:
    """Klassifiziert ein Profil — mit ALLEN Treffern, nicht nur dem ersten.

    Rueckgabe (abwaertskompatibel, plus die drei Dimensionen):
        {
            "type": "student" | "service" | "trade" | "tech_junior" | ...,
            "confidence": 0.0..1.0,
            "reasons": [...],
            "label": "Mensch-lesbares Label",
            # seit #1070:
            "feld": "it", "feld_name": ..., "bereich": ...,
            "alle_felder": [...],   # jeder Treffer, staerkster zuerst
            "niveau": "spezialist", "form": "freiberuflich", ...
        }
    """
    from . import berufsfeld

    ein = berufsfeld.einordnen(profile, suchbegriffe)
    if not profile:
        return {
            "type": "mixed", "confidence": 0.0,
            "reasons": ["Kein Profil"],
            "label": PROFILE_TYPE_LABELS["mixed"],
            **ein,
        }

    typ = _typ_ableiten(ein)
    reasons: list = []
    if ein["feld"]:
        stark = ein["alle_felder"][0]
        reasons.append(
            f"{stark['name']}-Indikator ({stark['gewicht']} Treffer)")
    if ein["mehrfach"]:
        weitere = ", ".join(f["name"] for f in ein["alle_felder"][1:4])
        reasons.append(f"Weitere Felder getroffen: {weitere}")
    if ein["niveau"] != "unbekannt":
        reasons.append(
            f"Niveau {ein['niveau_name']} "
            f"({_NIVEAU_BELEG_TEXT.get(ein['niveau_beleg'], str(ein['berufsjahre']) + 'J Erfahrung')})")
    if ein["formen"]:
        reasons.append("Form: " + ", ".join(ein["formen"])
                       + f" ({_FORM_BELEG_TEXT.get(ein.get('form_beleg'), '')})")
    if ein.get("quereinstieg"):
        reasons.append(
            "Quereinstieg: das Ziel (Suchbegriffe, Kurzprofil) nennt ein "
            f"anderes Feld als der Lebenslauf ({ein.get('lebenslauf_feld')})")
    if not reasons:
        reasons.append("Keine eindeutige Indikator-Gruppe")

    ergebnis = {
        "type": typ,
        "confidence": _konfidenz(ein, typ),
        "reasons": reasons,
        "label": PROFILE_TYPE_LABELS.get(typ, typ),
        **ein,
    }
    if ein["unsicher"]:
        # Nichts erkannt ist ein Achselzucken, kein Ergebnis — und es
        # wird auch so ausgewiesen (#970). Im Zweifel wird BREIT
        # gesucht statt eng, wie bei der unbekannten Entfernung (#965).
        ergebnis["unsicher"] = True
        erkannt = []
        if ein["niveau"] != "unbekannt":
            erkannt.append(ein["niveau_name"])
        if ein["formen"]:
            erkannt.append("/".join(ein["formen"]))
        zusatz = (f" Erkannt wurde: {', '.join(erkannt)}." if erkannt
                  else "")
        ergebnis["hinweis"] = (
            "PBP konnte dein BERUFSFELD nicht sicher einordnen." + zusatz
            + " Statt zu raten, empfiehlt es breit — lieber eine Quelle "
            "zu viel als die falsche. Mit suchkriterien_setzen() und "
            "einem gepflegten Profil wird die Empfehlung genauer.")
    return ergebnis


# === Quellen-Empfehlung ==================================================
#
# Bis v1.7.124 stand hier eine Liste je Schluessel (PROFILE_TYPE_CLUSTERS).
# Sie ist ersatzlos weg: mit dem Schluessel als einziger Grundlage konnte
# ein freiberuflicher Senior-Entwickler nur ENTWEDER Freelance-Boersen
# ODER Tech-Quellen bekommen (#1070). Die Quellen kommen jetzt aus der
# Kombination der drei Angaben und stehen in `berufsfeld.FELD_QUELLEN`,
# `FORM_QUELLEN` und `NIVEAU_QUELLEN`. Eine Liste hier daneben waere die
# Bauform, die dieses Projekt vierzehnmal gekostet hat (#963).


def recommend_sources(profile: Optional[dict], suchbegriffe=None) -> dict:
    """Liefert die empfohlenen Quellen fuer das Profil.

    Rueckgabe:
        {
            "type": "...", "label": "...", "confidence": 0.x,
            "reasons": [...],
            "recommended": ["bundesagentur", "kimeta", ...],
            "rationale": "Kurzer Erklaer-Text fuer das UI",
        }
    """
    from . import berufsfeld

    detection = detect_profile_type(profile, suchbegriffe)
    herkunft = berufsfeld.quellen_fuer(detection)
    # #1039: die Listen oben sind die ABSICHT; empfohlen wird nur, was
    # gerade laeuft. Jeder der 15 Typen empfahl mindestens eine defekte
    # Quelle, und der Aktivieren-Knopf legte sie in die Auswahl, obwohl
    # sich ihr Haken in der Liste gar nicht setzen laesst. Die Markierung
    # aendert sich mit Reparaturen — deshalb Filter zur Laufzeit statt
    # Streichung aus der Liste.
    from ..job_scraper import SOURCE_REGISTRY
    alle = herkunft["quellen"]
    sources = [q for q in alle if not (SOURCE_REGISTRY.get(q) or {}).get("defekt")]
    ausgelassen = [q for q in alle if q not in sources]
    # Ohne Feld gilt dieselbe Antwort wie bei "unsicher" — und die
    # Bedingung prueft BEIDES, statt sich auf das Flag zu verlassen:
    # ein Aufrufer, der nur `type` liefert (Testdoppel, Altcode), darf
    # keinen KeyError ausloesen.
    if detection.get("unsicher") or not detection.get("feld"):
        rationale = (
            f"PBP konnte das Berufsfeld nicht sicher einordnen und "
            f"empfiehlt deshalb BREIT: {len(sources)} Quellen quer durch "
            "die großen deutschen Portale. Das ist bewusst mehr, nicht "
            "weniger — im Zweifel lieber eine Quelle zu viel. Sobald das "
            "Profil Stationen und Fähigkeiten enthält, wird die "
            "Empfehlung genauer."
        )
    else:
        teile = [f"Feld {detection['feld_name']}"]
        if detection.get("niveau") != "unbekannt":
            teile.append(detection["niveau_name"])
        if detection.get("formen"):
            teile.append(", ".join(
                berufsfeld.FORMEN[f] for f in detection["formen"]))
        rationale = (
            f"Erkannt als {detection['label']} ({'; '.join(teile)}). PBP "
            f"empfiehlt diese {len(sources)} Quellen — der Empfehlung "
            "folgen oder einzelne Quellen abwählen ist jederzeit "
            "möglich."
        )
    return {
        **detection,
        "recommended": sources,
        # Woher jede Empfehlung kommt. Ohne diese Trennung ist von
        # aussen nicht zu sehen, ob eine Quelle am Feld, an der Form
        # oder am Niveau haengt — und genau das war der Befund (#1070).
        "quellen_herkunft": {
            "feld": [q for q in herkunft["aus_feld"] if q in sources],
            "form": [q for q in herkunft["aus_form"] if q in sources],
            "niveau": [q for q in herkunft["aus_niveau"] if q in sources],
        },
        # Eine ausgelassene Quelle wird benannt, nicht verschwiegen.
        "ausgelassen_defekt": ausgelassen,
        "rationale": rationale,
    }
