"""Der Fachwert und sein Daumen (#1052 Schritt 2).

Der Score mischte zwei Dinge, die nichts miteinander zu tun haben: wie
gut eine Anzeige fachlich trifft, und ob die Rahmenbedingungen ueberhaupt
in Frage kommen. Belegter Fall vom 15.09.2026: Fachscore 21,0 — der
hoechste im aktiven Bestand — stand in der Liste bei 0, weil der
Entfernungsregler 40 Punkte abzog. Umgekehrt stand eine Stelle mit
Fachscore 0 bei 10, allein aus dem Remote-Regler.

Hier wohnt die eine Haelfte: der FACHWERT. Er kommt nur aus MUSS, PLUS
und MINUS und ist nie von Entfernung, Gehalt, Arbeitsmodell oder
Vertragsform beeinflusst.

## Rohe Punkte, keine Skala

Die erste Fassung zeigte den Fachwert als Prozent des erreichbaren
Maximums. Das Akzeptanzkriterium dazu hat der Nutzer am 16.09.2026
**zurueckgezogen**, mit einer Begruendung, die tiefer geht als die
Darstellungsfrage:

    "es gibt keine ober oder untergrenze, denn je nachdem wieviele
    PLUS oder MINUS werte man mit gibt oder man diese gewichtet kann
    das fuer jede Person sehr individuell sein. ja es kann sogar sein
    ... das die besten stellen sogar einen Minus score haben."

Ein Prozentwert setzt eine Obergrenze voraus, und die gibt es nicht.
Der urspruengliche Einwand ("28.5 sagt nichts") galt fuer eine Welt
ohne Daumen — die Einordnung leistet jetzt der Daumen, und zwar aus dem
eigenen Bestand heraus. Damit darf die Zahl roh bleiben.

**Nicht gekappt, in keine Richtung.** Eine Stelle bei -8 und eine bei 0
duerfen nicht gleich aussehen. Genau das war der Fehler, der #1052
ausgeloest hat: eine Zahl, die etwas anderes bedeutet als sie sagt.

## Die Schwellen kommen aus dem eigenen Bestand

Feste Prozentwerte waeren an einem Profil kalibriert und fuer jedes
andere falsch (v1.7.69). Zwei Zahlen, zwei verschiedene Aussagen
(Nutzerantwort 16.09.2026, Variante c):

* **Trennschwelle** — ab wo sich das Hinsehen ueberhaupt lohnt.
  Dieselbe Rechnung wie der Schwellenvorschlag im Backtest: unteres
  Viertel der Bewerbungen mal 0,8 (die 20 % Toleranz nach unten sind
  Nutzervorgabe aus #778).
* **Oberes Viertel der Bewerbungen** — ab wo es sich besonders lohnt.

Reicht die Grundlage nicht, bleibt der Daumen GRAU und sagt warum —
eine Ersatzschwelle waere eine erfundene Angabe (#989).

Gelesen werden die GESPEICHERTEN Fachwerte, nicht frisch gerechnete.
Das ist Absicht: die Schwelle wird gegen dieselben Zahlen gehalten, die
in der Liste stehen. Eine frisch gerechnete Schwelle gegen gespeicherte
Werte waere wieder der Vergleich zweier Rechenwege (#1051).
"""
from __future__ import annotations

# Ab wie vielen bewertbaren Bewerbungen die Verteilung eine Schwelle
# tragen kann. Nutzervorschlag vom 15.09.2026. Darunter waere ein
# Quartil die Verkleidung einer Handvoll Einzelfaelle — und eine
# Schwelle, die aus vier Bewerbungen entsteht, sortiert den ganzen
# Bestand.
MIN_BEWERBUNGEN = 20

# Toleranz nach unten auf das untere Viertel, Nutzervorgabe aus #778.
# Dieselbe Zahl wie im Backtest — die Trennschwelle soll dort und hier
# dieselbe sein, sonst schlaegt der Backtest einen Wert vor, den der
# Daumen nicht benutzt.
TRENN_TOLERANZ = 0.8

HOCH = "hoch"
MITTEL = "mittel"
RUNTER = "runter"

BELEGT = "belegt"
GRAU = "grau"


def _quantil(sortiert: list, anteil: float) -> float:
    """Dasselbe Quantil wie in der Score-Verteilung (#986).

    Bewusst importiert statt nachgebaut: zwei Fassungen derselben
    Rechnung sind das Muster, das dieses Projekt vierzehnmal gekostet
    hat (#963).
    """
    from .score_verteilung import _quantil as _q
    return _q(sortiert, anteil)


def schwellen(db, criteria=None) -> dict:
    """Wo liegt "hoch" und wo "runter" — gemessen am eigenen Bestand.

    Returns:
        {"trennschwelle": .., "oberes_viertel": .., "anzahl": ..,
         "aussortierte_darueber": ..} — oder
        {"grundlage_fehlt": "<Grund>", "anzahl": ..}, und dann bleibt
        der Daumen grau.
    """
    beworben = _fachwerte(db, beworben=True)
    if len(beworben) < MIN_BEWERBUNGEN:
        return {
            "anzahl": len(beworben),
            "grundlage_fehlt": (
                f"Nur {len(beworben)} bewertbare Bewerbungen — unter "
                f"{MIN_BEWERBUNGEN} traegt die Verteilung keine Schwelle. "
                "Der Fachdaumen bleibt deshalb grau; eine Ersatzschwelle "
                "waere geraten."),
        }
    sortiert = sorted(beworben)
    q25 = _quantil(sortiert, 0.25)
    q75 = _quantil(sortiert, 0.75)
    trenn = round(q25 * TRENN_TOLERANZ, 1)

    ergebnis = {
        "anzahl": len(sortiert),
        "trennschwelle": trenn,
        "oberes_viertel": q75,
        "median": _quantil(sortiert, 0.5),
        "formel": (
            f"Unteres Viertel deiner Bewerbungen ({q25}) mal "
            f"{TRENN_TOLERANZ} = {trenn}. Darunter lohnt das Hinsehen "
            f"erfahrungsgemaess nicht; ab {q75} liegst du im oberen "
            "Viertel dessen, worauf du dich beworben hast."),
    }
    # Wieviele aussortierte Stellen laegen ueber der Trennschwelle? Die
    # Zahl macht die Schwelle pruefbar: trennt sie wirklich, oder steht
    # der halbe Bestand darueber? Sie entscheidet nichts — sie steht da.
    aussortiert = _fachwerte(db, beworben=False)
    if aussortiert:
        darueber = sum(1 for w in aussortiert if w >= trenn)
        ergebnis["aussortierte"] = len(aussortiert)
        ergebnis["aussortierte_darueber"] = darueber
        ergebnis["aussortierte_darueber_quote"] = round(
            darueber / len(aussortiert), 3)
    return ergebnis


def _fachwerte(db, beworben: bool) -> list:
    """Die gespeicherten Fachwerte — der Bewerbungen oder der Aussortierten.

    `applications.job_hash` traegt den OEFFENTLICHEN Hash, `jobs.hash`
    den profil-praefixierten — ein rohes `WHERE hash=?` findet deshalb
    nichts (v1.7.56 MERKE 4). `get_job` loest beide Formen auf.
    """
    werte = []
    if beworben:
        try:
            bewerbungen = db.get_applications() or []
        except Exception:
            return []
        for bew in bewerbungen:
            hash_ = bew.get("job_hash")
            if not hash_:
                continue
            try:
                stelle = db.get_job(hash_)
            except Exception:
                continue
            if stelle and stelle.get("score") is not None:
                werte.append(float(stelle["score"]))
        return werte

    try:
        aussortiert = db.get_dismissed_jobs() or []
    except Exception:
        return []
    for stelle in aussortiert:
        # Wer sich beworben hat, hat die Stelle nicht abgelehnt — der
        # Grund `bewerbung_erstellt` ist das Gegenteil einer Ablehnung
        # (#941). Er gehoert nicht in die Negativ-Menge.
        if "bewerbung_erstellt" in str(stelle.get("dismiss_reason") or ""):
            continue
        if stelle.get("score") is not None:
            werte.append(float(stelle["score"]))
    return werte


def daumen(punkte, schwellen_werte: dict, belegt: bool = True) -> dict:
    """Richtung und Farbe des Fachdaumens — zwei getrennte Kanaele.

    Die RICHTUNG ergibt sich aus den vorhandenen Angaben, die FARBE sagt,
    wie belegt diese Angaben sind. Ein grauer Daumen nach unten heisst:
    sieht schlecht aus, aber ungeprueft. Damit ist der Indikator nie
    nutzlos und nie erfunden (Nutzervorgabe 15.09.2026).
    """
    # C97 (#1087 C8): "ungeprueft" nennt einen kurzen Grund auf der Karte,
    # nicht erst im Tooltip.
    if punkte is None:
        return {"richtung": MITTEL, "farbe": GRAU,
                "ungeprueft_weil": "ohne Punkte",
                "grund": "Diese Stelle traegt keinen Fachwert."}
    fehlt = (schwellen_werte or {}).get("grundlage_fehlt")
    if fehlt:
        return {"richtung": MITTEL, "farbe": GRAU, "grund": fehlt,
                "ungeprueft_weil": "zu wenige Bewerbungen zum Vergleich"}
    trenn = (schwellen_werte or {}).get("trennschwelle")
    oben = (schwellen_werte or {}).get("oberes_viertel")
    if trenn is None or oben is None:
        return {"richtung": MITTEL, "farbe": GRAU,
                "ungeprueft_weil": "zu wenige Bewerbungen zum Vergleich",
                "grund": "Die Verteilung deiner Bewerbungen liefert keine "
                         "Schwellen — der Daumen bleibt ohne Grundlage."}
    wert = float(punkte)
    if wert >= oben:
        richtung, grund = HOCH, (
            f"{wert:g} Punkte — im oberen Viertel deiner Bewerbungen "
            f"(ab {oben:g}).")
    elif wert < trenn:
        richtung, grund = RUNTER, (
            f"{wert:g} Punkte — unter der Schwelle, ab der sich das "
            f"Hinsehen erfahrungsgemaess lohnt ({trenn:g}).")
    else:
        richtung, grund = MITTEL, (
            f"{wert:g} Punkte — ueber der Schwelle ({trenn:g}), aber "
            f"unter deinem oberen Viertel ({oben:g}).")
    marke = {"richtung": richtung,
             "farbe": BELEGT if belegt else GRAU,
             "grund": grund}
    if not belegt:
        marke["ungeprueft_weil"] = "ohne Anzeigentext"
    return marke
