"""Google-Jobs-Benachrichtigungen aus dem Postfach lesen (#1068, #1120).

Google schickt zu einer gefolgten Stellensuche taeglich eine Mail. Der
Newsletter-Ingest (#525) konnte sie nicht verwerten, und zwar aus einem
Grund, den keine Portal-Regel loest: **alle Links der Mail zeigen auf
`notifications.googleapis.com/email/redirect?...`**, nicht auf ein
Portal. `extract_job_links` findet dort nichts.

Die Stellen stehen in einem festen Block je Treffer:

    <Initiale oder "Logo">
    <Titel>
    <Firma>
    <Ort>, Deutschland
    ueber <Ursprungsportal>
    Time icon <Datum> Work icon <Vertragsart>

**Gemessen an neun echten Mails (21.–29.09.2026, 25 Treffer, #1120).**
Die erste Fassung (#1068) war nach einer Beschreibung gebaut und las
davon null — ihr Test-Fixture war nie gegen eine echte Mail geprueft.
Was die echten Mails anders machen:

* Der Betreff lautet bei genau einem Treffer `1 neuer Job für ...`
  (sechs von neun Mails), sonst `<N> neue Jobs für ...`.
* Im Textteil (base64, `format=flowed; delsp=yes`) stehen Leerzeilen
  zwischen den Feldern, lange Titel sind weich umgebrochen (die Zeile
  endet mit einem Leerzeichen), und Datum und Vertragsart tragen die
  Alt-Texte der Symbole als Praefix.
* Orte kommen auch als `<PLZ>, <Stadtteil>, Deutschland` oder als volle
  Adresse mit Strasse.

**Welcher Teil der Mail?** Beide gemessen: nach dem Zusammenfuegen der
Umbrueche liefern Text und HTML dieselben 25 Treffer mit gleichem Titel,
Firma, Ort und Portal. Gelesen wird zuerst das HTML, der Text ist der
Rueckfall. Im HTML steht jedes Feld in einem eigenen Element, es gibt
keine weichen Umbrueche, und nur dort haengt der Link an der Karte. Der
Textteil braucht zwei Umformungen mehr (Umbrueche, Symbol-Praefixe), und
an genau solchen Umformungen ist die erste Fassung gescheitert. Beide
Wege laufen durch DIESELBE Blockauswertung (`_bloecke`), damit sie nicht
auseinanderlaufen.

**Die Links** sind offline dekodierbar: der Parameter `r` ist zlib plus
base64url. Alle 25 Ziele waren `google.de/search?...ibp=htl;jobs...` —
das alte Google-Jobs-Format, das in der Praxis oft nur die Trefferliste
oeffnet. Der Link wird deshalb nie als Stellen-URL gespeichert, sondern
hoechstens als Google-Link im Vermerk.

Weitere gemessene Eigenheiten:

* Manche Titel tragen Python-Listentext aus Googles Quelle
  (``- ['Vollzeit', 'Homeoffice']``).
* Die Treffer sind nur fuer DIESEN Alert neu: beim ersten Versand lagen
  die Anzeigen zwischen 16. Januar und 12. September. Ohne
  `veroeffentlicht_am` (#949) saehen sie alle taufrisch aus — ausser bei
  Weiterverbreitern (`services/weiterverbreiter.py`), deren Datum das
  Kopierdatum ist.
"""
from __future__ import annotations

import base64
import re
import zlib
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from .weiterverbreiter import ist_weiterverbreiter

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

#: `10 neue Jobs für "PLM Hamburg" - 21. Sept.` und, bei genau einem
#: Treffer, `1 neuer Job für "PLM Hamburg" - 29. Sept.` (#1120).
BETREFF = re.compile(r"\bneue[rs]?\s+jobs?\s+f(?:ü|ue)r\b", re.I)
_SUCHANFRAGE = re.compile(r"[\"„»](.+?)[\"“«]")

_MONATE = {
    "jan": 1, "feb": 2, "mär": 3, "mae": 3, "mar": 3, "apr": 4, "mai": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}
#: Die Alt-Texte der Symbole vor Datum und Vertragsart im Textteil (#1120).
_SYMBOL = re.compile(r"\b(?:time|work)\s+icon\b", re.I)
#: "23. Apr.", "24. März", "3. Juli" — dahinter die Vertragsart. Sie kann
#: ohne Trenner kleben: "23. Apr.Vollzeit" (Form aus #1068) und im HTML
#: "31. MaiVollzeit", weil Datum und Vertragsart in zwei spans stehen.
#: Deshalb die Monatsnamen selbst und nicht "Buchstaben, so viele es
#: gibt" — das las "MaiVollze" als Monat (#1120, gemessen).
_DATUM = re.compile(
    r"^(\d{1,2})\.\s*(Jan(?:uar)?|Feb(?:ruar)?|M(?:ä|ae)rz|Mär|Apr(?:il)?|Mai|"
    r"Juni?|Juli?|Aug(?:ust)?|Sept(?:ember)?|Sep|Okt(?:ober)?|"
    r"Nov(?:ember)?|Dez(?:ember)?)\.?(.*)$", re.I)
#: `- ['Vollzeit', 'Homeoffice']` am Titelende.
_LISTENTEXT = re.compile(r"\s*[-–]\s*\[[^\]]*\]\s*$")
_UEBER = re.compile(r"^(?:ü|ue)ber\s+(.+)$", re.I)
_LAENDER = {"deutschland", "germany", "österreich", "oesterreich",
            "austria", "schweiz", "switzerland"}
_PLZ = re.compile(r"^\d{4,5}(?:\s+|$)")


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


def google_link(href: str) -> str:
    """Das Ziel eines Google-Redirects, offline dekodiert — sonst leer.

    `r` ist zlib plus base64url. Geliefert wird nur ein Ziel auf einer
    Google-Suche: das ist der Link, der zur Karte gehoert. Er oeffnet oft
    nur die Trefferliste und ist deshalb KEINE Stellen-URL.
    """
    try:
        r = parse_qs(urlparse(href or "").query).get("r", [""])[0]
        if not r:
            return ""
        ziel = zlib.decompress(
            base64.urlsafe_b64decode(r + "=" * (-len(r) % 4))).decode("utf-8")
    except Exception:
        return ""
    teile = urlparse(ziel)
    if (teile.scheme == "https" and teile.path == "/search"
            and re.fullmatch(r"www\.google\.(?:[a-z]{2,3}|co(?:m)?\.[a-z]{2})",
                             teile.netloc)):
        return ziel
    return ""


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


def _ort(zeile: str) -> str:
    """`Hamburg, Deutschland` -> Hamburg; auch mit PLZ oder Strasse davor.

    Gemessen: `<PLZ>, <Stadtteil>, Deutschland` und
    `<Standort>, <Strasse>, <Stadt>, Deutschland`. Die Stadt steht jeweils
    zuletzt vor dem Land. Steht NUR das Land da, bleibt es stehen — das
    sagt die Quelle, und die Entfernungsrechnung behandelt es als Zusatz.
    """
    teile = [t.strip() for t in (zeile or "").split(",") if t.strip()]
    land = teile.pop() if teile and teile[-1].lower() in _LAENDER else ""
    teile = [_PLZ.sub("", t).strip() for t in teile]
    teile = [t for t in teile if t]
    return teile[-1] if teile else land


def _titel(roh: str, portal: str) -> str:
    """Listentext und das Anhaengsel eines Weiterverbreiters entfernen.

    Gemessen (#1120): die Kopie haengt `. Job in <Ort> <Portal>` an den
    Titel. Entfernt wird das nur, wenn der Titel wirklich auf das Portal
    endet — ein Titel wie `... (m/w/d) in Hamburg` bleibt, wie er ist.
    """
    titel = _LISTENTEXT.sub("", roh).strip()
    if portal:
        m = re.match(r"^(.*?)\.?\s+Job\s+in\s+.+?\s+" + re.escape(portal) + r"$",
                     titel, re.I)
        if m and m.group(1).strip():
            titel = m.group(1).strip()
    return titel


# ── Zwei Zugaenge, eine Auswertung ─────────────────────────────────────

def _zeilen_aus_text(text: str) -> list[tuple[str, str]]:
    """Der Textteil als Zeilenliste, weiche Umbrueche zusammengefuegt.

    `format=flowed; delsp=yes` (RFC 3676): eine Zeile, die mit einem
    Leerzeichen endet, geht in der naechsten weiter; das letzte
    Leerzeichen ist nur die Markierung und faellt weg. Leerzeilen fallen
    ganz weg. Links hat der Textteil nicht.
    """
    zeilen: list[tuple[str, str]] = []
    rest = ""
    for zeile in re.split(r"\r\n|\r|\n", text or ""):
        zeile = rest + zeile
        rest = ""
        if zeile.endswith(" ") and zeile.strip():
            rest = zeile[:-1]
            continue
        if zeile.strip():
            zeilen.append((re.sub(r"\s+", " ", zeile).strip(), ""))
    if rest.strip():
        zeilen.append((re.sub(r"\s+", " ", rest).strip(), ""))
    return zeilen


class _HtmlZeilen(HTMLParser):
    """HTML -> eine Zeile je Block, mit dem Link, in dem sie steht.

    Inline-Elemente (span) bleiben in der Zeile: Datum und Vertragsart
    stehen in zwei spans desselben Blocks und ergeben "28. Sept. Vollzeit".
    Die Symbole davor sind Bilder und tragen nichts bei.
    """

    _BLOCK = {"a", "br", "div", "li", "p", "table", "td", "th", "tr"}
    _STUMM = {"head", "script", "style", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.zeilen: list[tuple[str, str]] = []
        self._puffer: list[str] = []
        self._href = ""
        self._stumm = 0

    def _abschliessen(self):
        zeile = re.sub(r"\s+", " ", "".join(self._puffer)).strip()
        if zeile:
            self.zeilen.append((zeile, self._href))
        self._puffer = []

    def handle_starttag(self, tag, attrs):
        if tag in self._STUMM:
            self._stumm += 1
        if tag in self._BLOCK:
            self._abschliessen()
        if tag == "a":
            self._href = dict(attrs).get("href") or ""

    def handle_endtag(self, tag):
        if tag in self._STUMM and self._stumm:
            self._stumm -= 1
        if tag in self._BLOCK:
            self._abschliessen()
        if tag == "a":
            self._href = ""

    def handle_data(self, data):
        if not self._stumm:
            self._puffer.append(data)


def _zeilen_aus_html(html: str) -> list[tuple[str, str]]:
    if not (html or "").strip():
        return []
    leser = _HtmlZeilen()
    try:
        leser.feed(html)
        leser.close()
    except Exception:
        return []
    leser._abschliessen()
    return leser.zeilen


def _bloecke(zeilen: list[tuple[str, str]], heute: date) -> list[dict]:
    """Die Treffer aus einer Zeilenliste, verankert an `ueber <Portal>`.

    Die Zeile steht in jedem Block und ist das verlaessliche Merkmal.
    Titel, Firma und Ort stehen in den drei Zeilen davor, Datum und
    Vertragsart in der Zeile danach.
    """
    treffer: list[dict] = []
    for i, (zeile, _href) in enumerate(zeilen):
        m = _UEBER.match(zeile)
        if not m or i < 3:
            continue
        titel_roh, href = zeilen[i - 3]
        firma = zeilen[i - 2][0]
        if not titel_roh or not firma:
            continue
        portal = m.group(1).strip()
        weiter = ist_weiterverbreiter(portal)
        eintrag = {
            "titel": _titel(titel_roh, portal),
            "firma": firma,
            "ort": _ort(zeilen[i - 1][0]),
            # Das Ursprungsportal — dieselbe Angabe wie bei der
            # Browser-Auswertung (#1067). Sie sagt, ueber welche Quelle
            # PBP die Stelle womoeglich schon hat.
            "portal": portal,
            "weiterverbreiter": weiter,
            "veroeffentlicht_am": "",
            # Das Datum auf der Karte. Bei einem Weiterverbreiter ist es
            # das Kopierdatum und wird NICHT zu `veroeffentlicht_am`.
            "kartendatum": "",
            "vertragsart": "",
            "google_link": google_link(href),
        }
        if i + 1 < len(zeilen):
            danach = zeilen[i + 1][0]
            ohne_symbol = _SYMBOL.sub(" ", danach).strip()
            d = _DATUM.match(ohne_symbol)
            if d:
                eintrag["kartendatum"] = _datum(int(d.group(1)), d.group(2), heute)
                eintrag["vertragsart"] = d.group(3).strip()
        if not weiter:
            eintrag["veroeffentlicht_am"] = eintrag["kartendatum"]
        treffer.append(eintrag)
    return treffer


def parse_alert(text: str, heute: date | None = None, html: str = "") -> list[dict]:
    """Die Treffer einer Google-Jobs-Mail — erst aus dem HTML, sonst aus dem Text.

    Jeder Treffer nennt in `gelesen_aus`, woher er stammt.
    """
    heute = heute or datetime.now().date()
    for quelle, zeilen in (("html", _zeilen_aus_html(html)),
                           ("text", _zeilen_aus_text(text))):
        treffer = _bloecke(zeilen, heute)
        if treffer:
            for t in treffer:
                t["gelesen_aus"] = quelle
            return treffer
    return []
