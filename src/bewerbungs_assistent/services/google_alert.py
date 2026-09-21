"""Google-Jobs-Benachrichtigungen aus dem Postfach lesen (#1068).

Google schickt zu einer gefolgten Stellensuche taeglich eine Mail. Der
Newsletter-Ingest (#525) konnte sie nicht verwerten, und zwar aus einem
Grund, den keine Portal-Regel loest: **alle Links der Mail zeigen auf
`notifications.googleapis.com/email/redirect?...`**, nicht auf ein
Portal. `extract_job_links` findet dort nichts.

Die Stellen stehen im TEXTteil, in einem festen Block je Treffer:

    <Titel>
    <Firma>
    <Ort>, Deutschland
    ueber <Ursprungsportal>
    <Veroeffentlicht><Vertragsart>

Alles hier ist an **echten Mails gemessen** (Melder, 21.09.2026, zwei
Benachrichtigungen mit 17 Treffern) — nicht geraten. Das war die
ausdrueckliche Bedingung des Issues, und sie ist begruendet: Googles
Kontowarnungen kommen von derselben Domain, und ein zu breites Muster
wuerde sie als Stellen-Newsletter lesen.

Drei Eigenheiten, alle gemessen:

* Veroeffentlichungsdatum und Vertragsart kleben ohne Trenner
  aneinander ("23. Apr.Vollzeit").
* Manche Titel tragen Python-Listentext aus Googles Quelle
  (``- ['Vollzeit', 'Homeoffice']``).
* Die Treffer sind nur fuer DIESEN Alert neu: beim ersten Versand lagen
  die Anzeigen zwischen 16. Januar und 12. September. Ohne
  `veroeffentlicht_am` (#949) saehen sie alle taufrisch aus.
"""
from __future__ import annotations

import re
from datetime import date, datetime

#: Der Absender der Benachrichtigungen — gemessen, nicht geraten.
ABSENDER = "notify-noreply@google.com"

#: Und die, von denen er unterschieden werden MUSS. Sie kommen von
#: derselben Domain; eine Regel auf `google.com` wuerde Kontowarnungen
#: und Zahlungsmails als Job-Newsletter lesen. Genau dieses
#: Fehlalarm-Risiko nennt der Kommentar an `_SUBJECT_HINTS`.
KEINE_JOBMAIL = (
    "no-reply@accounts.google.com",
    "noreply-accounts@google.com",
    "payments-noreply@google.com",
)

#: `10 neue Jobs für "PLM Hamburg" - 21. Sept.`
BETREFF = re.compile(r"\bneue\s+jobs\s+f(?:ü|ue)r\b", re.I)
_SUCHANFRAGE = re.compile(r"[\"„»](.+?)[\"“«]")

_MONATE = {
    "jan": 1, "feb": 2, "mär": 3, "maer": 3, "mar": 3, "apr": 4, "mai": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}
#: "23. Apr." bzw. "23. Apr.Vollzeit" — Datum und Vertragsart kleben.
_DATUM = re.compile(r"^(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]{3,9})\.?(.*)$")
#: `- ['Vollzeit', 'Homeoffice']` am Titelende.
_LISTENTEXT = re.compile(r"\s*[-–]\s*\[[^\]]*\]\s*$")
_UEBER = re.compile(r"^(?:ü|ue)ber\s+(.+)$", re.I)


def ist_google_jobmail(sender: str, betreff: str) -> bool:
    """Absender UND Betreff — eines allein traegt hier nicht.

    Der Absender allein wuerde jede Benachrichtigung von Google fangen
    (auch Kalender und Drive), der Betreff allein jeden Newsletter mit
    "neue Jobs" im Titel.
    """
    s = (sender or "").lower()
    if any(k in s for k in KEINE_JOBMAIL):
        return False
    return ABSENDER in s and bool(BETREFF.search(betreff or ""))


def suchanfrage(betreff: str) -> str:
    """Die Suchanfrage aus dem Betreff — sie steht dort in Anfuehrungszeichen."""
    m = _SUCHANFRAGE.search(betreff or "")
    return m.group(1).strip() if m else ""


def _datum(tag: int, monat_wort: str, heute: date) -> str:
    """'23' + 'Apr' -> ISO-Datum. Ohne Jahr in der Mail.

    Ein Datum, das in der Zukunft laege, gehoert ins Vorjahr — die
    Alerts tragen Anzeigen bis zu acht Monate zurueck.
    """
    monat = _MONATE.get(monat_wort[:3].lower())
    if not monat or not 1 <= tag <= 31:
        return ""
    try:
        d = date(heute.year, monat, tag)
    except ValueError:
        return ""
    if d > heute:
        try:
            d = date(heute.year - 1, monat, tag)
        except ValueError:
            return ""
    return d.isoformat()


def parse_alert(text: str, heute: date | None = None) -> list[dict]:
    """Die Treffer aus dem Textteil einer Google-Jobs-Mail.

    Verankert an der Zeile `ueber <Portal>` — sie steht in jedem Block
    und ist das einzige verlaessliche Merkmal. Titel, Firma und Ort
    stehen davor, Datum und Vertragsart dahinter.
    """
    heute = heute or datetime.now().date()
    zeilen = [z.strip() for z in (text or "").split("\n")]
    treffer: list[dict] = []
    for i, zeile in enumerate(zeilen):
        m = _UEBER.match(zeile)
        if not m or i < 3:
            continue
        ort_zeile = zeilen[i - 1]
        firma = zeilen[i - 2]
        titel = zeilen[i - 3]
        if not titel or not firma:
            continue
        ort = ort_zeile.split(",")[0].strip()
        eintrag = {
            "titel": _LISTENTEXT.sub("", titel).strip(),
            "firma": firma,
            "ort": ort,
            # Das Ursprungsportal — dieselbe Angabe wie bei der
            # Browser-Auswertung (#1067). Sie sagt, ueber welche Quelle
            # PBP die Stelle womoeglich schon hat.
            "portal": m.group(1).strip(),
            "veroeffentlicht_am": "",
            "vertragsart": "",
        }
        if i + 1 < len(zeilen):
            d = _DATUM.match(zeilen[i + 1])
            if d:
                eintrag["veroeffentlicht_am"] = _datum(
                    int(d.group(1)), d.group(2), heute)
                eintrag["vertragsart"] = d.group(3).strip()
        treffer.append(eintrag)
    return treffer
