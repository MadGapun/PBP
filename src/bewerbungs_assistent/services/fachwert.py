"""Der Fachwert und sein Daumen (#1052 Schritt 2, AK 2/3).

Der Score mischte zwei Dinge, die nichts miteinander zu tun haben: wie
gut eine Anzeige fachlich trifft, und ob die Rahmenbedingungen ueberhaupt
in Frage kommen. Belegter Fall vom 15.09.2026: Fachscore 21,0 — der
hoechste im aktiven Bestand — stand in der Liste bei 0, weil der
Entfernungsregler 40 Punkte abzog. Umgekehrt stand eine Stelle mit
Fachscore 0 bei 10, allein aus dem Remote-Regler.

Hier wohnt die eine Haelfte: der FACHWERT. Er kommt nur aus MUSS, PLUS
und MINUS und ist nie von Entfernung, Gehalt, Arbeitsmodell oder
Vertragsform beeinflusst.

Zwei Entscheidungen des Nutzers vom 15.09.2026 stecken darin:

**Prozent statt Punkte.** Eine Punktsumme sagt nichts, solange niemand
den Hoechstwert kennt — das war #999, und es ist derselbe Fehler wie
"Score 15.0/100" bei einer Skala ohne 100. Der Anteil bezieht sich auf
`fach_maximum`, also auf das, was MIT DIESEN Kriterien erreichbar ist.

**Die Schwellen kommen aus dem eigenen Bestand, nicht aus dem Code.**
Feste Prozentwerte waeren an einem Profil kalibriert und fuer jedes
andere falsch (v1.7.69). Grundlage ist die Verteilung der Fachwerte der
eigenen Bewerbungen. Reicht sie nicht, bleibt der Daumen GRAU und sagt
warum — eine Ersatzschwelle waere eine erfundene Angabe (#989).
"""
from __future__ import annotations

# Ab wie vielen bewertbaren Bewerbungen die Verteilung eine Schwelle
# tragen kann. Nutzervorschlag vom 15.09.2026. Darunter waere ein
# Quartil die Verkleidung einer Handvoll Einzelfaelle — und eine
# Schwelle, die aus vier Bewerbungen entsteht, sortiert den ganzen
# Bestand.
MIN_BEWERBUNGEN = 20

HOCH = "hoch"
MITTEL = "mittel"
RUNTER = "runter"

BELEGT = "belegt"
GRAU = "grau"


def anteil(punkte, maximum) -> float | None:
    """Der Fachwert in Prozent des Erreichbaren — oder None.

    None heisst "nicht bestimmbar", nicht "null Prozent". Ohne
    Hoechstwert gibt es keine Skala, und eine Zahl ohne Skala ist genau
    die Auskunft, die #999 abgeschafft hat.
    """
    try:
        obergrenze = float(maximum)
        wert = float(punkte)
    except (TypeError, ValueError):
        return None
    if obergrenze <= 0:
        return None
    # Nach oben gedeckelt: mehr als alles gibt es nicht. Nach unten auf
    # 0 — ein negativer Anteil waere keine Passungsaussage, sondern ein
    # Rechenrest aus den Abzuegen.
    return round(max(0.0, min(100.0, wert / obergrenze * 100.0)), 1)


def schwellen(db, criteria=None) -> dict:
    """Wo liegt "hoch" und wo "runter" — gemessen am eigenen Bestand.

    Grundlage sind die Fachwerte der Stellen, auf die sich der Mensch
    beworben hat. Das ist die einzige Stichprobe, in der eine Entscheidung
    steckt; alles andere waere eine Annahme ueber ihn.

    Returns:
        {"q25": .., "q75": .., "anzahl": ..} — oder
        {"grundlage_fehlt": "<Grund>", "anzahl": ..}, und dann bleibt
        der Daumen grau.
    """
    werte = _fachwerte_der_bewerbungen(db, criteria)
    if len(werte) < MIN_BEWERBUNGEN:
        return {
            "anzahl": len(werte),
            "grundlage_fehlt": (
                f"Nur {len(werte)} bewertbare Bewerbungen — unter "
                f"{MIN_BEWERBUNGEN} traegt die Verteilung keine Schwelle. "
                "Der Fachdaumen bleibt deshalb grau; eine Ersatzschwelle "
                "waere geraten."),
        }
    # Dieselbe Quantil-Rechnung wie in der Score-Verteilung (#986) —
    # eine zweite Fassung waere das Muster, das dieses Projekt vierzehnmal
    # gekostet hat (#963).
    from .score_verteilung import kennzahlen
    kenn = kennzahlen(werte)
    return {
        "anzahl": kenn.get("anzahl", len(werte)),
        "q25": kenn.get("q25"),
        "q75": kenn.get("q75"),
        "median": kenn.get("median"),
    }


def _fachwerte_der_bewerbungen(db, criteria=None) -> list:
    """Die Fachwerte der beworbenen Stellen, in Prozent.

    `applications.job_hash` traegt den OEFFENTLICHEN Hash, `jobs.hash`
    den profil-praefixierten — ein rohes `WHERE hash=?` findet deshalb
    nichts (v1.7.56 MERKE 4). `get_job` loest beide Formen auf.
    """
    try:
        bewerbungen = db.get_applications() or []
    except Exception:
        return []
    if criteria is None:
        try:
            from .scoring_kriterien import fuer_scoring
            criteria = fuer_scoring(db)
        except Exception:
            criteria = {}
    try:
        from ..job_scraper import fach_maximum
        maximum = fach_maximum(criteria or {})
    except Exception:
        return []
    if maximum <= 0:
        return []

    werte = []
    for bew in bewerbungen:
        hash_ = bew.get("job_hash")
        if not hash_:
            continue
        try:
            stelle = db.get_job(hash_)
        except Exception:
            continue
        if not stelle:
            continue
        punkte = stelle.get("fachscore")
        if punkte is None:
            continue
        prozent = anteil(punkte, maximum)
        # 0 heisst "kein Pflichttreffer" und ist keine Bewertung (#989);
        # solche Zeilen wuerden die Verteilung nach unten ziehen, ohne
        # etwas ueber die Passung zu sagen.
        if prozent is None or prozent <= 0:
            continue
        werte.append(prozent)
    return werte


def daumen(prozent, schwellen_werte: dict, belegt: bool = True) -> dict:
    """Richtung und Farbe des Fachdaumens — zwei getrennte Kanaele.

    Die RICHTUNG ergibt sich aus den vorhandenen Angaben, die FARBE sagt,
    wie belegt diese Angaben sind. Ein grauer Daumen nach unten heisst:
    sieht schlecht aus, aber ungeprueft. Damit ist der Indikator nie
    nutzlos und nie erfunden (Nutzervorgabe 15.09.2026).
    """
    if prozent is None:
        return {"richtung": MITTEL, "farbe": GRAU,
                "grund": "Kein erreichbares Fachmaximum — ohne Skala keine "
                         "Einordnung. Pflege Pflichtbegriffe, dann traegt "
                         "der Wert etwas."}
    fehlt = (schwellen_werte or {}).get("grundlage_fehlt")
    if fehlt:
        return {"richtung": MITTEL, "farbe": GRAU, "grund": fehlt}
    q25 = (schwellen_werte or {}).get("q25")
    q75 = (schwellen_werte or {}).get("q75")
    if q25 is None or q75 is None:
        return {"richtung": MITTEL, "farbe": GRAU,
                "grund": "Die Verteilung deiner Bewerbungen liefert keine "
                         "Quartile — der Daumen bleibt ohne Grundlage."}
    if prozent >= q75:
        richtung, grund = HOCH, (
            f"{prozent:.0f} % — im oberen Viertel deiner Bewerbungen "
            f"(ab {q75:.0f} %).")
    elif prozent < q25:
        richtung, grund = RUNTER, (
            f"{prozent:.0f} % — unter dem unteren Viertel deiner "
            f"Bewerbungen ({q25:.0f} %).")
    else:
        richtung, grund = MITTEL, (
            f"{prozent:.0f} % — zwischen unterem und oberem Viertel deiner "
            f"Bewerbungen ({q25:.0f} bis {q75:.0f} %).")
    return {"richtung": richtung,
            "farbe": BELEGT if belegt else GRAU,
            "grund": grund}
