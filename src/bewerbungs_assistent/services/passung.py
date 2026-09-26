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

from .punkte import SCORE_BEDEUTUNG as _SCORE_BEDEUTUNG

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
        "PBP kennt deine Kompetenzen nicht. Ohne Profil lässt sich "
        "keine Passung beurteilen — leg zuerst dein Profil an."),
    # H24 (#1087 G4): die Score-Deutung kommt aus EINER Konstante.
    "nicht_gelesen": (
        "Diese Stelle wurde noch nicht gegen dein Profil gelesen. "
        + _SCORE_BEDEUTUNG + " Lass Claude die "
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
            # v1.7.112 (#1051): den tatsaechlichen Grund nennen. Der alte
            # Satz sagte immer "Profil", auch wenn der Score der Grund war.
            gruende = gespeicherte_analyse.get("veraltet_text") or [
                "Dein Profil hat sich seither geändert"]
            antwort["hinweis"] = (
                "; ".join(gruende) + " — das Urteil kann überholt sein.")
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


# -- Worauf eine Pruefung beruht (#1051) ------------------------------
#
# Bis v1.7.111 hing "ueberholt" am Score: gespeichert wurde der Score
# zum Zeitpunkt der Pruefung, verglichen mit dem Score der Liste. Das
# waren ZWEI Rechenwege — gespeichert der rohe Wert, in der Liste der
# Wert mit den Scoring-Reglern. Bei jeder Stelle, an der ein Regler
# greift, stand ein Urteil deshalb im Moment seiner Entstehung als
# veraltet da (gemeldet: gespeichert 0, Liste 10). Ein Hinweis, der
# immer kommt, wird nach dem zweiten Mal ignoriert — und dann auch der,
# der wirklich auf eine veraltete Analyse zeigt (#929).
#
# Die Nutzereinordnung dazu: der Score ist nur ein Anhaltspunkt. Eine
# Detailanalyse liest ihn nicht einmal (#1003), sie vergleicht Profil
# und Anzeige. "Ueberholt" haengt deshalb jetzt an den EINGABEN statt
# an einer Zahl, die mehrere Wege verschieden berechnen: Profil,
# Anzeigentext und Suchkriterien. Ein Fingerabdruck ist kein
# Rechenergebnis und kann nicht auf zwei Wegen verschieden herauskommen.

GRUND_TEXT = {
    "profil": "Profil hat sich seither geändert",
    "anzeigentext": "Anzeigentext hat sich seither geändert",
    "kriterien": "Suchkriterien haben sich seither geändert",
}


def _kurz_hash(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def text_stand(beschreibung) -> str:
    """Fingerabdruck des Anzeigentexts, unempfindlich gegen Formatierung.

    Leerraum faellt vor dem Vergleich weg: v1.7.110 (#1047) hat
    Anzeigentexte neu gegliedert, ohne ein Wort zu aendern. Ein Urteil
    darf dadurch nicht ueberholt heissen — es hat denselben Text gelesen.
    """
    rein = "".join(str(beschreibung or "").split())
    return _kurz_hash(rein) if rein else ""


def kriterien_stand(kriterien) -> str:
    """Fingerabdruck der Suchkriterien, ohne das, was nicht zaehlt.

    Heraus fallen die Eintraege mit Unterstrich — PBP reichert sie zur
    Laufzeit an, die beworbenen Titel etwa aendern sich mit jeder
    Bewerbung und saegten sonst jedes Urteil ab — und die Nennwerte
    fuers Gespraech (#931), die in keine Pruefung eingehen.
    """
    if not kriterien:
        return ""
    import json

    from .nennwerte import WUNSCH_FELDER
    kern = {k: v for k, v in dict(kriterien).items()
            if not str(k).startswith("_") and k not in WUNSCH_FELDER}
    if not kern:
        return ""
    return _kurz_hash(json.dumps(kern, sort_keys=True, ensure_ascii=False,
                                 default=str))


def grundlage_stand(profil, job, kriterien) -> str:
    """Worauf eine Pruefung beruht, in einer Zeile: `p=...|t=...|k=...`."""
    return (f"p={profil_stand(profil)}"
            f"|t={text_stand((job or {}).get('description'))}"
            f"|k={kriterien_stand(kriterien)}")


def _teile(stand) -> dict:
    teile = {}
    for stueck in str(stand or "").split("|"):
        schluessel, trenner, wert = stueck.partition("=")
        if trenner and schluessel in ("p", "t", "k"):
            teile[schluessel] = wert
    return teile


def ueberholt(job: dict, profil=None, kriterien=None) -> dict | None:
    """Hat sich seit der Pruefung ihre GRUNDLAGE geaendert (#948, #1051)?

    Verglichen werden Profil, Anzeigentext und Suchkriterien zum
    Zeitpunkt der Pruefung mit dem heutigen Stand. Der Score gehoert
    nicht mehr dazu — warum, steht im Block darueber.

    Eine Seite ohne Angabe entscheidet nichts. Fehlt der gespeicherte
    Stand (Pruefung von vor v1.7.112) oder reicht der Aufrufer weder
    Profil noch Kriterien herein, wird diese Grundlage nicht verglichen:
    ein fehlender Beleg ist kein Befund (#989). Ein Urteil von vor
    v1.7.112 kennt nur seinen Profil-Stand und wird nur daran gemessen.

    Ein Urteil ist der juengere Stand und geht der Sichtung vor.

    Returns:
        dict mit `grund` (etwa 'profil' oder 'anzeigentext+kriterien')
        und `gruende_text`, oder None wenn nichts ueberholt ist.
    """
    if not job:
        return None
    if (job.get("analyse_urteil") or "").strip():
        gespeichert = _teile(job.get("analyse_stand"))
        if not gespeichert and job.get("analyse_profil_stand"):
            gespeichert = {"p": job["analyse_profil_stand"]}
    elif (job.get("gesichtet_am") or "").strip():
        gespeichert = _teile(job.get("gesichtet_stand"))
    else:
        return None

    gruende = []
    jetzt_profil = profil_stand(profil)
    if gespeichert.get("p") and jetzt_profil and gespeichert["p"] != jetzt_profil:
        gruende.append("profil")
    # Nur ein VORHANDENER Text zaehlt als Aenderung: ein Text, der beim
    # Nachladen weggebrochen ist, macht ein Urteil nicht falsch — es hat
    # gelesen, was damals dastand (dafuer gibt es den Snapshot, C23).
    jetzt_text = text_stand(job.get("description"))
    if "t" in gespeichert and jetzt_text and gespeichert["t"] != jetzt_text:
        gruende.append("anzeigentext")
    if kriterien is not None and "k" in gespeichert:
        if gespeichert["k"] != kriterien_stand(kriterien):
            gruende.append("kriterien")
    if not gruende:
        return None
    return {"grund": "+".join(gruende),
            "gruende_text": [GRUND_TEXT[g] for g in gruende]}


def zustand(job: dict, profil=None, kriterien=None) -> dict:
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
    alt = ueberholt(job, profil, kriterien)
    if alt:
        antwort["ueberholt"] = alt
    return antwort


def analyse_lesen(job: dict, profil=None, kriterien=None) -> dict | None:
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
    # #948: der Score zum Zeitpunkt des Urteils bleibt als Auskunft
    # stehen. Ob das Urteil ueberholt ist, entscheidet er seit v1.7.112
    # nicht mehr (#1051) — er entsteht auf mehreren Wegen.
    if job.get("analyse_score") is not None:
        befund["score_damals"] = round(float(job["analyse_score"]), 1)
    alt = ueberholt(job, profil, kriterien)
    if alt:
        befund["veraltet"] = True
        befund["veraltet_grund"] = alt["grund"]
        befund["veraltet_text"] = alt["gruende_text"]
    return befund
