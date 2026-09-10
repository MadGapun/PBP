"""Woraus eine Empfehlung entsteht — und woraus nicht (#1003, #1007).

Nutzer-Korrektur vom 09.09.2026, und sie trifft die Wurzel:

    "Ob es eine Empfehlung gibt, hat nichts mit den Punkten, nichts mit
    dem Score zu tun — das ist nur ein Indikator fuer die Suchbegriffe.
    Ob es eine Empfehlung gibt oder nicht, entsteht erst durch die
    Fit-Analyse bzw. durch die Detailanalyse, die den Lebenslauf mit der
    Stelle vergleicht — und nicht irgendwelche Punkte."

## Was vorher geschah

`_build_empfehlung` bildete den Verdict aus `total_score /
total_score_max`. In diese Zahl gehen ein: Keyword-Treffer in Titel und
Anzeigentext, Gehalt, Entfernung, Remote-Grad. **Der Lebenslauf geht
nicht ein.** `fit_analyse` reicht zwar Profil-Kompetenzen in die
Kriterien hinein — aber als zusaetzliches KEYWORD-Material fuer dieselbe
Summe, nicht als Vergleich von Werdegang und Rolle.

Der Score beantwortet: *"Steht in dieser Anzeige, wonach ich gesucht
habe?"* Der Verdict behauptete: *"Passt dieser Mensch auf diese
Stelle?"* Zwei verschiedene Fragen, und die zweite wurde aus der Antwort
auf die erste abgeleitet.

## Warum hier keine Schwelle steht

Der naheliegende Ausweg waere ein besserer MASSSTAB gewesen — gegen den
hoechsten bisher erreichten Wert, gegen die Verteilung des Bestands. Ich
hatte die Verteilung selbst vorgeschlagen. Beides haette denselben
Fehler nur sauberer gemacht: der Verdict kaeme weiter aus dem
Suchbegriff-Score.

Deshalb rechnet dieses Modul **gar nicht**. Es entscheidet nach
Sachverhalten:

* Es gibt ein k.o.-Kriterium → `NICHT_EMPFOHLEN`. Das ist eine Aussage
  ueber die Stelle und ueber dokumentierte Entscheidungen, keine
  Punkterechnung.
* Es liegt eine gelesene Detailanalyse vor → deren Urteil.
* Sonst → `NICHT_BEURTEILBAR`, mit dem Grund und dem naechsten Schritt.

Die vierte Kategorie aus #999 war bis hierher ein Notausgang fuer einen
fehlenden Hoechstwert. Jetzt sagt sie, was sie sagt: **niemand hat diese
Stelle gegen dein Profil gelesen.** Das ist etwas anderes als "passt
nicht" — und genau die Verwechslung, die #989 abgeschafft hat.

## Die Herkunft steht dabei

Ein maschinelles Urteil und ein gelesenes Urteil duerfen in der Liste
nicht gleich aussehen. `grundlage` ist deshalb Pflichtfeld und kein
Zierrat.
"""
from __future__ import annotations

KATEGORIEN = ("EMPFOHLEN", "BEDINGT", "NICHT_EMPFOHLEN", "NICHT_BEURTEILBAR")

# Woraus ein Urteil stammt. Kein Wert bedeutet "irgendwie berechnet" —
# das war der Zustand vor #1003.
GRUNDLAGEN = ("detailanalyse", "ko_kriterium", "keine_grundlage")

# Warum nicht beurteilt werden konnte. Drei verschiedene Sachverhalte
# mit drei verschiedenen naechsten Schritten (#989).
OHNE_URTEIL = {
    "keine_beschreibung": (
        "Die Anzeige liegt nur als Titel vor. Ohne Text gibt es nichts "
        "zu vergleichen — hole zuerst die Beschreibung nach "
        "(stellenbeschreibung_nachladen)."),
    "kein_profil": (
        "PBP kennt deine Kompetenzen nicht. Ohne Profil laesst sich "
        "keine Passung beurteilen — leg zuerst dein Profil an."),
    "nicht_gelesen": (
        "Diese Stelle wurde noch nicht gegen dein Profil gelesen. Der "
        "Score sagt nur, wie gut sie deine SUCHBEGRIFFE trifft — das ist "
        "keine Aussage darueber, ob du passt. Lass Claude die "
        "Detailanalyse machen; das Ergebnis bleibt danach an der Stelle."),
}


def _ist_kategorie(wert) -> bool:
    return isinstance(wert, str) and wert.upper() in KATEGORIEN


def urteil(ko_gruende=None, beschreibung_vorhanden: bool = True,
           profil_kompetenzen: int = 0, gespeicherte_analyse=None) -> dict:
    """Der Verdict — ohne eine einzige Punkterechnung.

    Args:
        ko_gruende: harte Ausschluesse (Wiedergaenger mit fachlichem
            Grund, ausserhalb des Rechtsraums, kein MUSS-Treffer).
        beschreibung_vorhanden: hat die Anzeige ueberhaupt Text?
        profil_kompetenzen: wie viele Kompetenzen im Profil stehen.
        gespeicherte_analyse: der an der Stelle abgelegte Befund einer
            gelesenen Detailanalyse (siehe `analyse_lesen`).

    Reihenfolge mit Absicht: ein k.o. schlaegt eine gute Analyse. Wer
    eine Firma dreimal aus fachlichem Grund aussortiert hat, will nicht
    beim vierten Mal eine Empfehlung lesen (#671).
    """
    gruende = [g for g in (ko_gruende or []) if g]
    if gruende:
        return {
            "kategorie": "NICHT_EMPFOHLEN",
            "grundlage": "ko_kriterium",
            "begruendung": gruende[0],
            "ko_gruende": gruende,
            "kurz": "Nicht empfohlen: " + gruende[0],
        }

    if gespeicherte_analyse and _ist_kategorie(
            gespeicherte_analyse.get("urteil")):
        kategorie = gespeicherte_analyse["urteil"].upper()
        begruendung = (gespeicherte_analyse.get("begruendung") or "").strip()
        antwort = {
            "kategorie": kategorie,
            "grundlage": "detailanalyse",
            "begruendung": begruendung or "Aus der Detailanalyse.",
            "kurz": f"{kategorie} (Detailanalyse)",
            "analyse_am": gespeicherte_analyse.get("am", ""),
            "analyse_quelle": gespeicherte_analyse.get("grundlage", ""),
        }
        if gespeicherte_analyse.get("veraltet"):
            # Nicht verwerfen, sondern kennzeichnen: das Urteil war zu
            # seiner Zeit richtig, und ein stilles Wegwerfen verlöre die
            # teuerste Auskunft im System.
            antwort["veraltet"] = True
            antwort["hinweis"] = (
                "Dein Profil hat sich seit dieser Analyse geaendert — das "
                "Urteil kann ueberholt sein.")
        return antwort

    if not beschreibung_vorhanden:
        grund = "keine_beschreibung"
    elif profil_kompetenzen <= 0:
        grund = "kein_profil"
    else:
        grund = "nicht_gelesen"
    return {
        "kategorie": "NICHT_BEURTEILBAR",
        "grundlage": "keine_grundlage",
        "warum": grund,
        "begruendung": OHNE_URTEIL[grund],
        "kurz": "Noch nicht beurteilt",
    }


# -- Der Befund an der Stelle -----------------------------------------

def profil_stand(profil) -> str:
    """Ein kurzer Fingerabdruck des Profils.

    Er beantwortet genau eine Frage: hat sich seit der Analyse etwas
    geaendert? Deshalb reichen Zahl der Kompetenzen und Zeitpunkt — ein
    Inhalts-Hash waere genauer und wuerde bei jeder Kleinigkeit
    "veraltet" melden. Ein Hinweis, der zu oft kommt, wird ignoriert
    (#929).
    """
    if not profil:
        return ""
    # Kompetenzen UND Stationen: beide gehen in einen Profil-Abgleich
    # ein. Der Zeitstempel allein traegt nicht — er aendert sich beim
    # Anlegen einer Kompetenz nicht zuverlaessig, weil die in einer
    # eigenen Tabelle liegt.
    kompetenzen = len(profil.get("skills") or [])
    stationen = len(profil.get("positions") or [])
    stand = str(profil.get("updated_at") or "")[:19]
    return f"{kompetenzen}/{stationen}@{stand}"


# -- Die drei Zustaende einer Stelle (#948) ---------------------------
#
# Das Issue verlangt, dass die Trefferliste drei Zustaende unterscheidet:
# nie geprueft, geprueft und aktuell, geprueft aber ueberholt. Sie
# entstehen HIER und nur hier — im Frontend und im MCP eine zweite
# Fassung derselben Einteilung zu halten waere das Muster, das dieses
# Projekt inzwischen dreizehnmal gekostet hat (#963 zuerst).

UNGEPRUEFT = "ungeprueft"
GESICHTET = "gesichtet"
BEURTEILT = "beurteilt"

ZUSTAND_TEXT = {
    UNGEPRUEFT: "Noch nicht angesehen",
    GESICHTET: "Angesehen, kein Urteil hinterlegt",
    BEURTEILT: "Beurteilt",
}

# Warum "gesichtet" ueberhaupt ein eigener Zustand ist:
#
# `fit_analyse` hinterliess bis v1.7.71 GAR KEINE Spur. Wer eine Stelle
# vertieft ansah und danach kein Urteil zurueckschrieb, fand sie beim
# naechsten Sichten wieder vor, als sei nie etwas geschehen — das ist
# der gemeldete Schaden aus #948.
#
# Die Spur trotzdem als "beurteilt" zu zaehlen waere falsch: dass ein
# Werkzeug gelaufen ist, sagt nichts darueber, ob jemand das Ergebnis
# gelesen und entschieden hat. Genau diese Gleichsetzung ist #989 —
# eine fehlende Information sieht aus wie eine vorhandene. Also drei
# Zustaende statt zwei.


def ueberholt(job: dict, profil=None) -> dict | None:
    """Hat sich seit der Pruefung die Grundlage geaendert?

    Der Score ist das INTEGRIERENDE Signal, und deshalb genuegt er:
    eine nachgeladene Beschreibung, geaenderte Suchkriterien und
    verstellte Scoring-Regler wirken alle drei ueber ihn. Drei einzelne
    Vergleiche zu bauen haette dieselbe Frage dreimal beantwortet —
    und zwei davon ungenauer.

    **Keine Toleranzschwelle, und das ist gemessen.** Ueber 600 Stellen
    mit Anzeigentext (Kopie des Bestands, 10.09.2026) gegen die
    heutigen Kriterien nachgerechnet: 381 unveraendert, 219 abweichend
    — und die kleinste beobachtete Abweichung betraegt bereits 0,5
    Punkte, der Median 10,5. Es gibt kein Rauschband, das eine Schwelle
    wegfiltern muesste. Eine Schwelle waere hier also kein Schutz vor
    Fehlalarmen (#929), sondern eine Grenze, die echte Aenderungen
    verschweigt.

    Returns:
        dict mit `grund` ('score' | 'profil' | 'score+profil') und den
        beiden Score-Werten, oder None wenn nichts veraltet ist.
    """
    if not job:
        return None
    gruende = []
    damals = job.get("analyse_score")
    if damals is None:
        damals = job.get("gesichtet_score")
    jetzt_score = job.get("score")
    if damals is not None and jetzt_score is not None:
        try:
            if abs(float(jetzt_score) - float(damals)) >= 0.01:
                gruende.append("score")
        except (TypeError, ValueError):  # pragma: no cover
            pass
    gespeichert = job.get("analyse_profil_stand") or ""
    jetzt_profil = profil_stand(profil)
    if gespeichert and jetzt_profil and gespeichert != jetzt_profil:
        gruende.append("profil")
    if not gruende:
        return None
    befund = {"grund": "+".join(gruende)}
    if "score" in gruende:
        befund["score_damals"] = round(float(damals), 1)
        befund["score_jetzt"] = round(float(jetzt_score), 1)
    return befund


def zustand(job: dict, profil=None) -> dict:
    """In welchem der drei Zustaende steht diese Stelle (#948)?

    Immer ein dict, nie None — "noch nicht angesehen" ist eine Antwort
    und keine fehlende Auskunft.
    """
    job = job or {}
    urteil_wert = (job.get("analyse_urteil") or "").strip()
    gesichtet = (job.get("gesichtet_am") or "").strip()
    if urteil_wert:
        art = BEURTEILT
    elif gesichtet:
        art = GESICHTET
    else:
        art = UNGEPRUEFT
    antwort = {"art": art, "text": ZUSTAND_TEXT[art]}
    if art == UNGEPRUEFT:
        return antwort
    antwort["am"] = (job.get("analyse_am") or gesichtet or "")
    alt = ueberholt(job, profil)
    if alt:
        antwort["ueberholt"] = alt
    return antwort


def analyse_lesen(job: dict, profil=None) -> dict | None:
    """Der gespeicherte Befund einer Stelle, oder None."""
    if not job:
        return None
    urteil_wert = (job.get("analyse_urteil") or "").strip()
    if not urteil_wert:
        return None
    befund = {
        "urteil": urteil_wert.upper(),
        "begruendung": job.get("analyse_begruendung") or "",
        "grundlage": job.get("analyse_grundlage") or "",
        "am": job.get("analyse_am") or "",
    }
    # #948: der Score zum Zeitpunkt des Urteils steht dabei — ohne ihn
    # laesst sich "ueberholt" nur behaupten, nicht belegen.
    if job.get("analyse_score") is not None:
        befund["score_damals"] = round(float(job["analyse_score"]), 1)
    alt = ueberholt(job, profil)
    if alt:
        befund["veraltet"] = True
        befund["veraltet_grund"] = alt["grund"]
        if "score_jetzt" in alt:
            befund["score_jetzt"] = alt["score_jetzt"]
    return befund
