"""Der Rahmendaumen (#1052 Schritt 2, AK 3/4/5/6).

Die zweite Haelfte neben `fachwert`: kommt die Stelle physisch und
wirtschaftlich in Frage? Entfernung, Gehalt, Arbeitsmodell,
Vertragsform — und ausdruecklich NICHT die fachliche Passung.

**Indikator, kein Tor.** Die Formulierung "Rahmen als Tor" stammt aus
dem ersten Entwurf und hat zwei Dinge vermischt; der Nutzer hat sie am
15.09.2026 zurueckgezogen. Der Score ordnet und entscheidet nicht. Die
Entfernungsgrenze dagegen ist eine physische Tatsache — woertlich:
"ein zu weit weg ist zu weit weg, da macht auch eine 100-prozentige
fachliche Passung es fuer mich unmoeglich, den Job anzunehmen".

Beides gilt gleichzeitig, und daraus folgt gerade NICHT: automatisches
Aussortieren, Umsortieren ans Listenende oder Ausblenden ohne Hinweis.
Dieses Modul faellt deshalb kein Urteil ueber die Stelle — es liefert
eine Richtung und eine Farbe. Was damit geschieht, entscheidet der
Filter, den der Mensch bedient.

**Richtung und Farbe sind zwei getrennte Kanaele.** Die Richtung ergibt
sich aus den vorhandenen Angaben, die Farbe sagt, wie belegt sie sind.
Ein grauer Daumen nach unten heisst: sieht schlecht aus, aber
ungeprueft. Ohne diese Trennung waere der Indikator im eigenen Bestand
fast wertlos — die Mehrzahl der Gehaelter ist geschaetzt (#827).

Gelesen wird ausschliesslich aus `criteria`, nie direkt aus der
Datenbank: alle Kriterien kommen durch das Nadeloehr aus #987, sonst
rechnet dieselbe Stelle je nach Aufrufer anders.
"""
from __future__ import annotations

HOCH = "hoch"
MITTEL = "mittel"
RUNTER = "runter"

BELEGT = "belegt"
GRAU = "grau"

# Messtoleranz, KEIN Bewertungsband (Nutzerantwort 15.09.2026, Punkt 6).
# Gemessen wird von Ortsgrenze zu Ortsgrenze, und diese Messung ist
# ungenau. Innerhalb des Bandes bleibt die Richtung, die der Messwert
# hergibt — der Daumen wird nur grau.
VORGABE_TOLERANZ_KM = 10.0

# Die Groessen der Zweitwohnsitz-Formel stehen LEER. Keine Vorgabewerte,
# und das ist eine Entscheidung: die Zahlen aus dem Entwurfsgespraech
# (110.000 EUR, 15 Prozent) sind die EINES Profils, und eine an einem
# Bestand kalibrierte Voreinstellung gilt nur fuer diesen Bestand
# (v1.7.69). Leer heisst: es gibt keinen Ausweg.
ZWEITWOHNSITZ_FELDER = (
    "zweitwohnsitz_aufschlag_prozent",
    "zweitwohnsitz_kosten_pro_monat",
    "heimfahrten_pro_monat",
    "kosten_je_km",
)


def _zahl(wert):
    try:
        if wert is None or wert == "":
            return None
        return float(wert)
    except (TypeError, ValueError):
        return None


def toleranz_km(criteria: dict) -> float:
    """Die Messtoleranz um die Entfernungsgrenze, in km."""
    wert = _zahl((criteria or {}).get("entfernung_toleranz_km"))
    if wert is None or wert < 0:
        return VORGABE_TOLERANZ_KM
    return wert


def ist_freiberuflich(job: dict) -> bool:
    """Freiberuflich gelten die bestehenden Regler, sonst nichts.

    Begruendung des Nutzers: als Freiberufler gehen Reisekosten und
    Reisezeit in den Satz ein, der Kunde entscheidet darueber. Auf die
    Frage nach einer Zeitgrenze ausdruecklich: "Nein, dann reise ich
    eben einen Tag vorher an."
    """
    art = str((job or {}).get("employment_type") or "").strip().lower()
    return art in ("freelance", "freiberuflich", "freelancer")


def gehalt_belegt(job: dict) -> bool:
    """Steht das Gehalt in der Anzeige — oder ist es geschaetzt? (#827)"""
    if (job or {}).get("salary_estimated"):
        return False
    return bool(_zahl((job or {}).get("salary_min")))


def zweitwohnsitz_schwelle(criteria: dict, entfernung_km):
    """Ab welchem Jahresgehalt traegt ein Zweitwohnsitz? (#1052 AK 5)

        schwelle = min_gehalt * (1 + aufschlag_prozent)
                 + zweitwohnsitz_kosten_pro_monat * 12
                 + heimfahrten_pro_monat * 12 * 2 * entfernung_km * kosten_je_km

    Der Faktor 2 steht fuer Hin- und Rueckfahrt; die Heimfahrtkosten
    wachsen damit mit der Entfernung, statt als Konstante dazustehen.

    Returns:
        None, sobald eine der Groessen fehlt. **Leer heisst: es gibt
        keinen Ausweg** — nicht "Ausweg zum Nulltarif" (#989).
    """
    basis = _zahl((criteria or {}).get("min_gehalt"))
    if not basis:
        return None
    werte = {feld: _zahl((criteria or {}).get(feld))
             for feld in ZWEITWOHNSITZ_FELDER}
    if any(w is None for w in werte.values()):
        return None
    km = _zahl(entfernung_km)
    if km is None:
        return None
    aufschlag = werte["zweitwohnsitz_aufschlag_prozent"]
    # Der Aufschlag darf als 15 ODER als 0.15 dastehen. Wer "15" meint
    # und 1500 Prozent bekommt, merkt es erst an einer Schwelle, die nie
    # erreicht wird — und haelt den Ausweg dann fuer kaputt.
    teil = aufschlag / 100.0 if aufschlag > 1 else aufschlag
    return round(
        basis * (1 + teil)
        + werte["zweitwohnsitz_kosten_pro_monat"] * 12
        + werte["heimfahrten_pro_monat"] * 12 * 2 * km * werte["kosten_je_km"],
        2)


def _entfernungs_befund(job: dict, criteria: dict) -> dict:
    """Entfernung: Ausschluss, Toleranzband oder in Ordnung.

    Die Reihenfolge ist Absicht und nicht beliebig.

    **Erst der Rechtsraum.** Eine Stelle ausserhalb des DACH-Raums ist
    nicht weit weg, sondern gar nicht bewerbbar (#996) — auch dann,
    wenn sie remote ist. Das schlaegt alles andere.

    **Dann Remote.** Hier reicht `entfernungs_guete` nicht: sie
    beantwortet, wie belastbar die ZAHL ist, und meldet bei bekannter
    Entfernung sofort "belegt" — der Remote-Zweig kommt dann nie dran.
    Fuer den Rahmendaumen zaehlt aber die andere Frage: ob die
    Entfernung ueberhaupt gilt. Eine vollstaendig remote ausgeschriebene
    Stelle mit gemessenen 120 km waere sonst ein Ausschluss, obwohl
    niemand die 120 km faehrt. Hybrid loest die Grenze NICHT — ein
    Buerotag in der Woche ist ein Buerotag.
    """
    from .entfernung import grenze_km, preis_km
    from . import arbeitsregion

    fremd, belege = arbeitsregion.ausserhalb(job)
    if fremd:
        return {"stufe": RUNTER, "belegt": True,
                "grund": arbeitsregion.hinweis(belege),
                "ausschluss": "entfernung"}
    if str(job.get("remote_level") or "").strip().lower() == "remote":
        return {"stufe": HOCH, "belegt": True,
                "grund": "Vollständig remote — die Entfernung fällt weg."}

    km = preis_km(job, criteria)
    if km is None:
        return {"stufe": MITTEL, "belegt": False,
                "grund": "Kein Ort in der Anzeige — die Entfernung ist "
                         "unbekannt, nicht gleich null (#989)."}

    art = str(job.get("employment_type") or "festanstellung").strip().lower()
    grenze = grenze_km(criteria, art)
    band = toleranz_km(criteria)

    if km > grenze + band:
        return {"stufe": RUNTER, "belegt": True,
                "grund": f"{km:.0f} km liegt über deiner Grenze von "
                         f"{grenze:.0f} km fuer {art}.",
                "ausschluss": "entfernung", "entfernung_km": km,
                "grenze_km": grenze}
    if km >= grenze - band:
        # Im Band. Die Richtung kommt aus dem Messwert, die Farbe sagt,
        # dass die Messung sie nicht traegt (Nutzerantwort Punkt 6).
        # Deshalb gibt das Band nie ein "hoch": nah an der Grenze heisst
        # nicht "innerhalb der Wunschwerte".
        ueber = km > grenze
        return {
            "stufe": RUNTER if ueber else MITTEL,
            "belegt": False,
            "grund": (f"{km:.0f} km liegt im Toleranzband um deine Grenze "
                      f"von {grenze:.0f} km (plus minus {band:.0f} km). "
                      "Gemessen wird von Ortsgrenze zu Ortsgrenze — ein "
                      "Indikator, kein Navigationssystem."),
            "ausschluss": "entfernung" if ueber else None,
            "entfernung_km": km, "grenze_km": grenze,
        }
    return {"stufe": HOCH, "belegt": True,
            "grund": f"{km:.0f} km liegt innerhalb deiner Grenze von "
                     f"{grenze:.0f} km.",
            "entfernung_km": km, "grenze_km": grenze}


def _gehalts_befund(job: dict, criteria: dict) -> dict:
    """Gehalt: unter Minimum, zwischen Minimum und Wunsch, oder darueber."""
    minimum = _zahl((criteria or {}).get("min_gehalt"))
    wunsch = _zahl((criteria or {}).get("wunsch_gehalt"))
    if not minimum:
        return {"stufe": HOCH, "belegt": True,
                "grund": "Du hast kein Mindestgehalt hinterlegt."}
    if not gehalt_belegt(job):
        # #827: eine Schaetzung ist keine Angabe. Sie zaehlt im Score
        # gar nicht — und darf hier keinen Ausschluss tragen.
        return {"stufe": MITTEL, "belegt": False,
                "grund": "Das Gehalt ist geschätzt oder fehlt — daraus "
                         "folgt kein Urteil (#827)."}
    betrag = _zahl(job.get("salary_min"))
    if str(job.get("salary_type") or "jaehrlich") != "jaehrlich":
        return {"stufe": MITTEL, "belegt": False,
                "grund": "Die Anzeige nennt keinen Jahreswert — nicht "
                         "vergleichbar mit deinem Mindestgehalt."}
    if betrag < minimum:
        return {"stufe": RUNTER, "belegt": True,
                "grund": f"{int(betrag)} EUR liegt unter deinem Minimum von "
                         f"{int(minimum)} EUR.",
                "ausschluss": "gehalt", "gehalt": betrag}
    if wunsch and betrag < wunsch:
        return {"stufe": MITTEL, "belegt": True,
                "grund": f"{int(betrag)} EUR liegt zwischen deinem Minimum "
                         f"({int(minimum)}) und deinem Wunsch "
                         f"({int(wunsch)}).",
                "gehalt": betrag}
    return {"stufe": HOCH, "belegt": True,
            "grund": f"{int(betrag)} EUR liegt auf oder über deinem Wunsch.",
            "gehalt": betrag}


def _vertrags_befund(job: dict, criteria: dict) -> dict:
    """Vertragsform: steht sie in den gewaehlten Stellentypen?"""
    art = str(job.get("employment_type") or "").strip().lower()
    gewuenscht = [str(t).strip().lower()
                  for t in ((criteria or {}).get("stellentypen") or [])]
    if not gewuenscht:
        return {"stufe": HOCH, "belegt": True,
                "grund": "Du hast keine Stellentypen eingegrenzt."}
    if not art or art == "unbekannt":
        return {"stufe": MITTEL, "belegt": False,
                "grund": "Die Anzeige sagt nichts zur Vertragsform."}
    if art not in gewuenscht:
        return {"stufe": RUNTER, "belegt": True,
                "grund": f"Die Vertragsform {art} steht nicht in deinen "
                         "Stellentypen.",
                "ausschluss": "vertragsform"}
    return {"stufe": HOCH, "belegt": True, "grund": ""}


def _zweitwohnsitz_ausweg(job: dict, criteria: dict, entfernung: dict) -> dict:
    """Traegt ein Zweitwohnsitz die Entfernung? (#1052 AK 5)

    Zwei Bedingungen, beide vom Nutzer:

    - Der Ausweg zaehlt **nur bei belegtem Gehalt**, nie bei einer
      Schaetzung. Sonst entsteht aus einer erfundenen Zahl eine
      Umzugsempfehlung.
    - Er macht aus "runter" ein "mittel", nie ein "hoch".
    """
    schwelle = zweitwohnsitz_schwelle(criteria,
                                      entfernung.get("entfernung_km"))
    if schwelle is None:
        return {"greift": False,
                "grund": "Kein Zweitwohnsitz-Ausweg hinterlegt."}
    if not gehalt_belegt(job):
        return {"greift": False, "schwelle": schwelle,
                "grund": "Der Zweitwohnsitz-Ausweg zählt nur bei belegtem "
                         "Gehalt — aus einer Schätzung wird keine "
                         "Umzugsempfehlung."}
    betrag = _zahl(job.get("salary_min"))
    if str(job.get("salary_type") or "jaehrlich") != "jaehrlich":
        return {"greift": False, "schwelle": schwelle,
                "grund": "Kein vergleichbarer Jahreswert in der Anzeige."}
    if betrag is None or betrag < schwelle:
        return {"greift": False, "schwelle": schwelle,
                "grund": f"Für einen Zweitwohnsitz bräuchte es rund "
                         f"{int(schwelle)} EUR im Jahr."}
    return {"greift": True, "schwelle": schwelle,
            "grund": f"{int(betrag)} EUR trägt einen Zweitwohnsitz (ab rund "
                     f"{int(schwelle)} EUR) — das bleibt ein Preis, kein "
                     "Wunschwert."}


def daumen(job: dict, criteria: dict | None = None) -> dict:
    """Richtung und Farbe des Rahmendaumens.

    - **runter**: mindestens ein Ausschlusskriterium ist verletzt.
    - **mittel**: kein Ausschluss, aber ein Wert liegt zwischen Minimum
      und Wunsch — oder die Entfernung liegt im Toleranzband.
    - **hoch**: alles innerhalb der Wunschwerte.
    - **grau**, sobald ein Wert, der in die Richtung eingeht, geschaetzt
      ist oder fehlt.

    Der Zweitwohnsitz-Ausweg macht aus "runter" ein "mittel" — **nie ein
    "hoch"**. Ein Zweitwohnsitz bleibt ein Preis.
    """
    krit = criteria or {}
    teile = {
        "entfernung": _entfernungs_befund(job, krit),
        "gehalt": _gehalts_befund(job, krit),
        "vertragsform": _vertrags_befund(job, krit),
    }
    freiberuflich = ist_freiberuflich(job)

    ausschluesse = [name for name, t in teile.items() if t.get("ausschluss")]
    ausweg = None
    if "entfernung" in ausschluesse and not freiberuflich:
        befund = _zweitwohnsitz_ausweg(job, krit, teile["entfernung"])
        if befund.get("greift"):
            ausschluesse.remove("entfernung")
            teile["entfernung"]["ausweg"] = befund
            ausweg = befund

    if ausschluesse:
        richtung = RUNTER
    elif ausweg or any(t["stufe"] == MITTEL for t in teile.values()):
        # Der Ausweg hebt nach "mittel" und nie weiter: ein Zweitwohnsitz
        # bleibt ein Preis, auch wenn das Gehalt ihn traegt.
        richtung = MITTEL
    else:
        richtung = HOCH

    # Grau, sobald irgendein Teil, das in die Richtung eingeht, nicht
    # belegt ist. Ein einzelner ungeprueter Wert reicht — der Daumen
    # behauptet sonst eine Sicherheit, die die Angaben nicht hergeben.
    belegt = all(t.get("belegt", True) for t in teile.values())

    gruende = [t["grund"] for t in teile.values() if t.get("grund")]
    if ausweg:
        gruende.append(ausweg["grund"])
    marke = {
        "richtung": richtung,
        "farbe": BELEGT if belegt else GRAU,
        "ausschluesse": ausschluesse,
        "freiberuflich": freiberuflich,
        "teile": teile,
        "grund": " ".join(gruende).strip(),
    }
    # C97 (#1087 C8): welche Angabe fehlt, in wenigen Worten.
    if not belegt:
        fehlend = [_UNGEPRUEFT_TEXT.get(n, n) for n, t in teile.items()
                   if not t.get("belegt", True)]
        marke["ungeprueft_weil"] = ", ".join(fehlend)
    return marke


_UNGEPRUEFT_TEXT = {
    "entfernung": "Entfernung unbekannt",
    "gehalt": "Gehalt geschätzt oder unbekannt",
    "vertragsform": "Vertragsform unbekannt",
}
