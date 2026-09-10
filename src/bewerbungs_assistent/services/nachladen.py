"""Beschreibung nachladen — mit Befund statt Vermutung (#1014).

Gemeldet von einem fremden Anwender am 10.09.2026, mit Messungen:
**360 von 473 aktiven Stellen der Bundesagentur (76 %) hatten keinen
Anzeigentext**, und "Beschreibung jetzt nachladen" schlug bei jeder
davon fehl — mit der Meldung *"evtl. Login-Wall oder Bot-Block"*.

## Zwei Ursachen, und die zweite ist die teurere

**(1) Der Nachlade-Pfad fragte die falsche Adresse.**
`fetch_description_from_detail` scrapt HTML. arbeitsagentur.de ist eine
Angular-Anwendung: der Anzeigentext wird per JavaScript nachgeladen und
steht im ausgelieferten HTML nicht drin. Gegenprobe des Melders an
derselben Stelle, in derselben Sekunde:

    HTML-Scrape   ->     0 Zeichen
    Detail-API    ->  3.460 Zeichen

Den API-Weg gibt es seit #489 (`_fetch_ba_detail`). Der Nachlade-Pfad
hat ihn nur nie gerufen. **Das Werkzeug war da, der Weg dorthin
fehlte** — dieselbe Bauform wie #994.

**(2) Der HTTP-Status wurde verworfen.** `if status != 200: return ""`
macht aus 404, 410, 403 und 500 dieselbe leere Zeichenkette, und der
Aufrufer formuliert daraus eine Vermutung. Belegter Fall: eine Stelle
antwortet mit **410 Gone**, die Detail-API zusaetzlich mit
`STELLENANGEBOT_NICHT_GEFUNDEN` — PBP meldete "Login-Wall oder
Bot-Block?".

**410 Gone ist die eindeutigste Antwort, die ein Server auf diese Frage
geben kann.** Sie wegzuwerfen und stattdessen zu raten ist derselbe
Fehler wie #989: eine vorhandene Auskunft wird zu einer fehlenden
gemacht. Und PBP kann es an anderer Stelle laengst richtig —
`services/url_health.py` behandelt 404/410 als "Anzeige existiert
nicht mehr". Zwei Funktionen, dieselbe URL, zwei Antworten (#963,
#987, #991, #992).

## Warum das sich selbst festfaehrt

Die BA-Suche legt ab Treffer 21 je Suchbegriff Stellen ohne Volltext an
(`_DETAIL_FETCH_LIMIT_PER_KW`, #500 — als Tempo-Entscheidung
nachvollziehbar). Sie setzt voraus, dass Nachladen funktioniert. Tut es
das nicht, greift nach drei Fehlversuchen der `refetch_fail`-Backoff,
die Stelle wird nicht mehr angefasst — und der Aging-Check sortiert sie
auch nicht aus, weil die Anzeige ja mit HTTP 200 antwortet. Ergebnis:
eine Aufgabe im Dashboard, die sich nicht abarbeiten laesst, mit einer
Begruendung, die nicht stimmt.

## Die vier Befunde

Der Melder nennt drei Faelle, die bisher in einer Meldung zusammenfielen.
Es sind vier, wenn man das Lesen selbst mitzaehlt:

* `GELESEN`        — Text da.
* `WEG`            — 404/410. Die Anzeige existiert nicht mehr; die
                     Stelle gehoert aussortiert, nicht nachgeladen.
* `GEBLOCKT`       — 401/403/429. Zugriff verweigert; ein Mensch mit
                     Browser kaeme vermutlich durch.
* `LEBT_UNLESBAR`  — HTTP 200, aber kein Text zu finden. Genau hier ist
                     "Login-Wall oder Bot-Block" eine zulaessige
                     Vermutung — und nur hier.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

GELESEN = "gelesen"
WEG = "weg"
GEBLOCKT = "geblockt"
LEBT_UNLESBAR = "lebt_unlesbar"
FEHLER = "fehler"

BEFUNDE = (GELESEN, WEG, GEBLOCKT, LEBT_UNLESBAR, FEHLER)

# Was der Mensch zu jedem Befund lesen soll. Bewusst je ein Satz, der
# den NAECHSTEN Schritt nennt — eine Meldung ohne Ausweg ist eine
# Sackgasse (#927).
KLARTEXT = {
    GELESEN: "Anzeigentext geladen.",
    WEG: ("Die Anzeige existiert nicht mehr (der Server meldet sie "
          "ausdruecklich als entfernt). Die Stelle wird aussortiert."),
    GEBLOCKT: ("Der Server verweigert den Zugriff. Im eingeloggten "
               "Browser oeffnen und den Text von Hand einsetzen."),
    LEBT_UNLESBAR: ("Die Anzeige lebt, aber im ausgelieferten Text steht "
                    "nichts Brauchbares — moeglich sind eine Login-Wall, "
                    "ein Bot-Block oder eine Seite, die ihren Inhalt erst "
                    "per JavaScript nachlaedt."),
    FEHLER: "Die Seite war nicht erreichbar.",
}

# Wer 404/410 sagt, sagt es. Dieselbe Liste wie in `url_health` — nicht
# eine zweite daneben.
STATUS_WEG = (404, 410)
STATUS_GEBLOCKT = (401, 403, 429)


@dataclass
class Befund:
    """Was beim Nachladen herauskam — Text UND Begruendung.

    Der Text allein war das Problem: er ist bei "weg", "geblockt" und
    "lebt aber unlesbar" derselbe leere String.
    """

    status: str = FEHLER
    text: str = ""
    http_status: int | None = None
    quelle: str = ""          # 'detail_api' oder 'html'
    hinweise: list = field(default_factory=list)

    @property
    def erfolg(self) -> bool:
        return self.status == GELESEN and bool(self.text)

    @property
    def soll_aussortiert_werden(self) -> bool:
        """Nur bei einer AUSDRUECKLICHEN Absage des Servers.

        Ein Timeout oder ein 500er sagt nichts ueber die Anzeige — nur
        etwas ueber diesen Moment. Daraus eine Aussortierung abzuleiten
        waere geraten (#989).
        """
        return self.status == WEG

    def klartext(self) -> str:
        satz = KLARTEXT.get(self.status, KLARTEXT[FEHLER])
        if self.http_status:
            satz += f" (HTTP {self.http_status})"
        return satz

    def als_dict(self) -> dict:
        return {
            "befund": self.status,
            "erklaerung": self.klartext(),
            "http_status": self.http_status,
            "quelle": self.quelle or None,
            "zeichen": len(self.text),
            "hinweise": self.hinweise,
        }


def ist_bundesagentur(url: str) -> bool:
    """Zeigt diese URL auf eine Detailseite der Bundesagentur?"""
    try:
        teile = urlparse(str(url or ""))
    except Exception:
        return False
    return (teile.netloc.lower().endswith("arbeitsagentur.de")
            and "/jobsuche/jobdetail/" in teile.path)


def referenznummer(url: str) -> str:
    """Die Referenznummer aus einer BA-Detail-URL.

    Der Adapter baut die URL als `.../jobdetail/{refnr}` (#526), das
    letzte Pfadsegment IST also die Nummer. Die Detail-API will sie
    base64-kodiert (#489) — das erledigt `_fetch_ba_detail` selbst.
    """
    if not ist_bundesagentur(url):
        return ""
    pfad = urlparse(str(url)).path.rstrip("/")
    return pfad.rsplit("/", 1)[-1] if "/" in pfad else ""


def _status_zu_befund(code: int) -> str:
    if code in STATUS_WEG:
        return WEG
    if code in STATUS_GEBLOCKT:
        return GEBLOCKT
    return FEHLER


def beschreibung_holen(url: str, client, *, timeout: float = 15,
                       max_chars: int | None = None) -> Befund:
    """Holt den Anzeigentext — und sagt, was der Server geantwortet hat.

    Der EINE Weg fuer alle vier Aufrufer (Knopf in der Stellenansicht,
    Auto-Nachzug, MCP-Werkzeug, Bestands-Nachzug). Vier eigene Fassungen
    waeren derselbe Fehler in vier Gestalten — genau das schreibt der
    Melder in sein Issue.
    """
    from ..job_scraper import text_aus_html

    if ist_bundesagentur(url):
        befund = _ueber_detail_api(url, client)
        if befund.status != LEBT_UNLESBAR:
            return befund
        # Die API hat geantwortet, aber ohne Text — dann darf der
        # HTML-Weg es noch versuchen. Umgekehrt waere es sinnlos: bei
        # einer SPA liefert HTML grundsaetzlich nichts.
        befund.hinweise.append(
            "Detail-API lieferte keinen Text — HTML-Weg als Rueckfall.")

    try:
        antwort = client.get(url, timeout=timeout)
    except Exception as exc:
        logger.debug("Nachladen fehlgeschlagen (%s): %s", url, exc)
        return Befund(status=FEHLER, quelle="html",
                      hinweise=[str(exc)[:200]])

    code = getattr(antwort, "status_code", None)
    if code != 200:
        return Befund(status=_status_zu_befund(code or 0), http_status=code,
                      quelle="html")

    # Die Seite ist schon geholt — ein zweiter Abruf fuer denselben
    # Text waere die Haelfte aller Anfragen umsonst.
    text = text_aus_html(getattr(antwort, "text", "") or "",
                         max_chars=max_chars) or ""
    if text.strip():
        return Befund(status=GELESEN, text=text, http_status=200, quelle="html")
    return Befund(status=LEBT_UNLESBAR, http_status=200, quelle="html")


def _ueber_detail_api(url: str, client) -> Befund:
    """Der Weg, den es seit #489 gibt und den niemand gerufen hat.

    Gemessen vom Melder an derselben Stelle: HTML 0 Zeichen, API 3.460.
    """
    ref = referenznummer(url)
    if not ref:
        return Befund(status=LEBT_UNLESBAR, quelle="detail_api",
                      hinweise=["Keine Referenznummer in der URL."])
    try:
        from ..job_scraper.bundesagentur import _fetch_ba_detail, api_session
    except Exception as exc:  # pragma: no cover
        logger.debug("BA-Detailweg nicht verfuegbar: %s", exc)
        return Befund(status=LEBT_UNLESBAR, quelle="detail_api")

    status: list = []
    # Die Detail-API braucht ihren eigenen Schluessel und User-Agent
    # (#489/#624) — der Client des Aufrufers hat die nicht. Ein
    # gemeinsamer Client haette hier still 403 geliefert, und das waere
    # als "geblockt" gemeldet worden, obwohl nur der Header fehlt.
    try:
        with api_session() as ba_client:
            text = _fetch_ba_detail(ba_client, ref, status_raus=status) or ""
    except Exception as exc:
        logger.debug("BA-Detailabruf fehlgeschlagen (%s): %s", ref, exc)
        return Befund(status=FEHLER, quelle="detail_api",
                      hinweise=[str(exc)[:200]])

    code = status[-1] if status else None
    if text.strip():
        return Befund(status=GELESEN, text=text, http_status=code or 200,
                      quelle="detail_api")
    if code in STATUS_WEG:
        # Die API sagt es maschinenlesbar: STELLENANGEBOT_NICHT_GEFUNDEN.
        return Befund(status=WEG, http_status=code, quelle="detail_api")
    if code in STATUS_GEBLOCKT:
        return Befund(status=GEBLOCKT, http_status=code, quelle="detail_api")
    return Befund(status=LEBT_UNLESBAR, http_status=code, quelle="detail_api")
