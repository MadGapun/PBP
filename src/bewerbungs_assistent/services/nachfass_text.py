"""Inhalt fuer Nachfassungen (#945, v1.7.23).

Beobachtung, die dahinter steht: *"ich merke, dass ich schon wieder
suche, obwohl ich doch im Dashboard auf Oeffnen beim Nachfassen
geklickt habe."*

Von sieben offenen Nachfassungen hatten fuenf ein leeres
Beschreibungsfeld. Wer sie oeffnete, sah einen Firmennamen und ein
Datum — und musste sich den Rest selbst zusammensuchen: in welche
Bewerbung gehoert das, wer war der Ansprechpartner, ueber welchen Kanal
lief die Bewerbung, was war der letzte Stand.

Der Unterschied zu den Todos im selben Bestand, die durchweg
handlungsfaehig beschrieben sind, liegt nicht am Aufgabentyp, sondern
an der Herkunft: Todos werden mit Kontext angelegt, Nachfassungen
entstehen automatisch beim Statuswechsel und blieben leer.

Die Textbausteine dafuer gab es seit #816 bereits — sie wurden nur an
zwei von vier Anlagestellen benutzt, und der Bestand wurde nie
nachgezogen. Deshalb liegt der Baustein jetzt hier, gemeinsam nutzbar,
und wird zusaetzlich beim LESEN erzeugt, wenn er fehlt.
"""
from __future__ import annotations

from typing import Optional

# Ab diesen Staenden ist eine Routine-Nachfassung gegenstandslos: es
# laeuft bereits ein Gespraech. Weiter anzumahnen erzeugt genau die
# Sorte Rauschen, die dazu fuehrt, dass auch die wichtigen Eintraege
# uebersehen werden.
UEBERHOLTE_STATUS = frozenset({
    "interview", "zweitgespraech", "angebot", "zugesagt", "abgelehnt",
    "zurueckgezogen", "arbeitgeber_ausgefallen",
})

# Wie dringend ist eine Nachfassung, unabhaengig vom Faelligkeitsdatum?
# Eine Nachfrage nach einem abgeschlossenen Gespraech ist dringender als
# eine Routinenachfrage nach zwanzig Tagen Stille.
_DRINGLICHKEIT = {
    "interview_abgeschlossen": 3,
    "zweitgespraech_abgeschlossen": 3,
    "in_pruefung": 2,
    "beworben": 1,
}


def nachfass_text(app: dict, anlass: str = "") -> str:
    """Ein Text, der sagt, was zu tun ist — nicht nur, dass etwas ansteht.

    Alles hier steht bereits im Datensatz; es wurde nur nie
    zusammengefuehrt.
    """
    app = app or {}
    kopf = (f"Nachfassen zur Bewerbung als {app.get('title') or '?'} "
            f"bei {app.get('company') or '?'}")
    if app.get("applied_at"):
        kopf += f" (beworben am {str(app['applied_at'])[:10]})"
    teile = [kopf]

    ansprech = (app.get("ansprechpartner") or "").strip()
    mail = (app.get("kontakt_email") or "").strip()
    if ansprech and mail:
        teile.append(f"Ansprechpartner: {ansprech} ({mail})")
    elif ansprech:
        teile.append(f"Ansprechpartner: {ansprech}")
    elif mail:
        teile.append(f"Kontakt: {mail}")

    art = (app.get("bewerbungsart") or "").strip()
    if art:
        teile.append(f"Beworben per: {art}")

    status = (app.get("status") or "").strip()
    if status:
        teile.append(f"Stand: {status}")

    if anlass:
        teile.append(anlass)
    else:
        teile.append(_handlungsvorschlag(status))
    return " — ".join(teile)


def _handlungsvorschlag(status: str) -> str:
    if status == "interview_abgeschlossen":
        return ("Nach dem Ergebnis des Gespraechs fragen und Interesse "
                "bekraeftigen.")
    if status == "in_pruefung":
        return "Freundlich nach dem Stand der Pruefung fragen."
    return ("Kurz freundlich nach dem Stand fragen und auf die Bewerbung "
            "Bezug nehmen.")


def claude_prompt(app: dict) -> str:
    """Fertiger Auftrag fuer Claude — ein Klick von der Aufgabe zur Mail.

    Bewusst ohne Mailadresse: der Prompt landet in der Zwischenablage
    und geht damit potenziell durch fremde Haende. Der Name genuegt fuer
    die Anrede, die Adresse steht ohnehin im Beschreibungstext.
    """
    app = app or {}
    titel = app.get("title") or "die ausgeschriebene Position"
    firma = app.get("company") or "das Unternehmen"
    teile = [f"Formuliere eine kurze, freundliche Nachfass-Mail zur "
             f"Bewerbung als {titel} bei {firma}"]
    if app.get("applied_at"):
        teile.append(f"beworben am {str(app['applied_at'])[:10]}")
    ansprech = (app.get("ansprechpartner") or "").strip()
    if ansprech:
        teile.append(f"Ansprechpartner ist {ansprech}")
    status = (app.get("status") or "").strip()
    if status == "interview_abgeschlossen":
        teile.append("das Gespraech hat bereits stattgefunden, frage nach "
                     "dem Ergebnis")
    else:
        teile.append("seither kam keine Rueckmeldung")
    return (", ".join(teile) +
            ". Halte sie kurz, hoeflich und ohne Druck; nimm Bezug auf "
            "die Bewerbung und biete an, offene Fragen zu beantworten.")


def ist_ueberholt(follow_up: dict, app: dict,
                  meetings: Optional[list] = None) -> tuple[bool, str]:
    """Hat sich die Nachfassung durch den Verfahrensstand erledigt?

    Belegter Fall: eine Nachfassung war seit Tagen ueberfaellig, waehrend
    der Bewerbungsstatus laengst `zweitgespraech` war und ein
    bestaetigter Termin acht Tage spaeter vorlag. Die Aufgabe war
    gegenstandslos und wurde trotzdem angemahnt.

    Bewusst auf `hinfaellig` setzen statt loeschen — die Historie
    bleibt erhalten.
    """
    status = (app or {}).get("status") or ""
    if status in UEBERHOLTE_STATUS:
        return True, (f"Der Bewerbungsstand ist inzwischen '{status}' — "
                      "eine Routine-Nachfrage eruebrigt sich.")

    geplant_am = str((follow_up or {}).get("created_at") or "")[:10]
    for m in meetings or []:
        wann = str(m.get("scheduled_at") or m.get("datum") or "")[:10]
        if not wann:
            continue
        # Ein Termin, der NACH dem Anlegen der Nachfassung vereinbart
        # wurde, beantwortet sie.
        if not geplant_am or wann >= geplant_am:
            return True, (f"Es ist ein Termin am {wann} vereinbart — die "
                          "Nachfrage hat sich damit erledigt.")
    return False, ""


def dringlichkeit(app: dict, tage_ueberfaellig: int = 0) -> int:
    """Rang fuer die Sortierung. Hoeher = dringender.

    Nach Verfahrensstand gewichten, nicht allein nach Faelligkeit: sonst
    geht die Nachfrage zu einem abgeschlossenen Gespraech zwischen
    Routine-Eintraegen unter, nur weil deren Datum aelter ist.
    """
    grund = _DRINGLICHKEIT.get((app or {}).get("status") or "", 1)
    # Ueberfaelligkeit zaehlt mit, aber schwaecher als der Stand.
    return grund * 100 + min(int(tage_ueberfaellig or 0), 99)
