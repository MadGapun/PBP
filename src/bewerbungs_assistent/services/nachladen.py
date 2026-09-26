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
          "ausdrücklich als entfernt). Die Stelle wird aussortiert."),
    GEBLOCKT: ("Der Server verweigert den Zugriff. Im eingeloggten "
               "Browser öffnen und den Text von Hand einsetzen."),
    LEBT_UNLESBAR: ("Die Anzeige lebt, aber im ausgelieferten Text steht "
                    "nichts Brauchbares — möglich sind eine Login-Wall, "
                    "ein Bot-Block oder eine Seite, die ihren Inhalt erst "
                    "per JavaScript nachlädt."),
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
    # v1.7.128 (#1040, #1041, #1042): Firma und Ort aus dem JobPosting der
    # Detailseite. Die Seite war schon geholt — beides lag vor und wurde
    # weggeworfen, waehrend die Stelle "Unbekannt" ohne Ort blieb.
    kopf: dict = field(default_factory=dict)

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
            "Detail-API lieferte keinen Text — HTML-Weg als Rückfall.")

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
    roh = getattr(antwort, "text", "") or ""
    text = text_aus_html(roh, max_chars=max_chars) or ""
    kopf = kopf_aus_html(roh)
    if text.strip():
        return Befund(status=GELESEN, text=text, http_status=200, quelle="html",
                      kopf=kopf)
    return Befund(status=LEBT_UNLESBAR, http_status=200, quelle="html",
                  kopf=kopf)


def _sauber(wert) -> str:
    import html as _html
    import re as _re
    return _re.sub(r"\s+", " ", _html.unescape(str(wert or ""))).strip(" ,;-")


def kopf_aus_html(html_text: str) -> dict:
    """Firma und Ort aus dem `JobPosting`-JSON-LD einer Detailseite.

    Nur was dort ausdruecklich steht: `hiringOrganization.name` und
    `jobLocation.address.addressLocality` (bei mehreren Orten der
    erste). Ein Platzhalter ("Unbekannt") zaehlt nicht als Firma.
    """
    try:
        from ..job_scraper import extract_jobposting_jsonld
        daten = extract_jobposting_jsonld(html_text or "") or {}
    except Exception:  # pragma: no cover — nie das Nachladen kippen
        return {}
    kopf: dict = {}
    org = daten.get("hiringOrganization")
    name = org.get("name") if isinstance(org, dict) else org
    name = _sauber(name)
    if name:
        from .wiedergaenger import normalize_company
        if normalize_company(name):
            kopf["firma"] = name
    orte = daten.get("jobLocation")
    if isinstance(orte, dict):
        orte = [orte]
    for eintrag in orte if isinstance(orte, list) else []:
        adresse = eintrag.get("address") if isinstance(eintrag, dict) else None
        if isinstance(adresse, dict):
            ort = _sauber(adresse.get("addressLocality"))
        else:
            ort = _sauber(adresse)
        if ort:
            kopf["ort"] = ort
            break
    return kopf


def fehlender_kopf(job: dict) -> list[str]:
    """Welche Kopfangaben einer Stelle fehlen: 'firma', 'ort' oder beide.

    "Unbekannt" und "Nicht angegeben" sind fehlende Namen, die wie
    vorhandene aussehen (#1028).
    """
    from .wiedergaenger import normalize_company
    fehlt = []
    if not normalize_company(job.get("company") or ""):
        fehlt.append("firma")
    if not (job.get("location") or "").strip():
        fehlt.append("ort")
    return fehlt


def kopf_ergaenzen(db, job_hash: str, kopf: dict | None) -> list[str]:
    """Fuellt fehlende Firma und fehlenden Ort — ueberschreibt nie.

    Kommt ein Ort hinzu, wird er geocodet und die Entfernung gesetzt,
    sonst bliebe die Stelle genau so ohne Entfernung wie vorher (#1040:
    "Ohne Ort gibt es keine Entfernung"). Das ist eine Netzabfrage — sie
    gehoert hierher, weil das Nachladen ohnehin eine ist; der Score
    danach rechnet wieder ohne Netz.
    """
    if not kopf:
        return []
    job = db.get_job(job_hash) or {}
    if not job:
        return []
    fehlt = fehlender_kopf(job)
    spalten: dict = {}
    if "firma" in fehlt and kopf.get("firma"):
        spalten["company"] = kopf["firma"]
    if "ort" in fehlt and kopf.get("ort"):
        spalten["location"] = kopf["ort"]
        try:
            from . import geocoding_service as _geo
            koord = _geo.geocode_location(_geo.normalisiere_ort(kopf["ort"]))
            heim = _geo.get_user_coordinates(db)
            if koord:
                spalten["lat"], spalten["lon"] = koord
                if heim:
                    spalten["distance_km"] = _geo.calculate_distance_km(heim, koord)
        except Exception as exc:  # pragma: no cover — Ort bleibt trotzdem
            logger.debug("Geocoding nach Nachladen (%s): %s", job_hash, exc)
    if not spalten:
        return []
    ziel = db.resolve_job_hash(job_hash) or job_hash
    conn = db.connect()
    conn.execute(
        f"UPDATE jobs SET {', '.join(f'{k}=?' for k in spalten)} WHERE hash=?",
        (*spalten.values(), ziel))
    conn.commit()
    return sorted(k for k in ("company", "location", "distance_km") if k in spalten)


def kopf_nachziehen(db, job_hash: str, kopf: dict | None) -> dict:
    """Nur Firma und Ort ergaenzen und neu bewerten — der Text bleibt.

    Fuer den Mengenweg: der Text einer Stelle kann laengst vollstaendig
    sein, waehrend Firma und Ort fehlen.
    """
    ergaenzt = kopf_ergaenzen(db, job_hash, kopf)
    if not ergaenzt:
        return {"kopf": []}
    ergebnis = neu_auswerten(db, job_hash)
    ergebnis["kopf"] = ergaenzt
    return ergebnis


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


#: v1.7.122 (#1064 Angrenzend 2): Schluessel, die Quellen-Adapter dem
#: Anzeigentext voranstellen. Beim Nachladen kommt der Text von der
#: Detailseite und traegt sie nicht mehr — gemeldet am Beispiel
#: "Standort / Einstiegslevel / Eintrittsdatum", die nach dem Nachladen
#: fehlten. Einstiegslevel ist ein Senioritaets-Signal und entscheidet
#: ueber `zu_junior` / `zu_senior` mit.
#:
#: Bewusst eine GESCHLOSSENE Liste statt einer Regel ueber
#: "Wort: Wert". Gemessen an einer Bestandskopie (1.578 Anzeigen mit
#: Text): nur 47 tragen ueberhaupt Kopfzeilen, und die generische Form
#: fing dabei schon Fliesstext mit ("Die VESCON Aqua ..."). Eine Regel,
#: die bei 3 % Nutzen Fehltreffer erzeugt, ist die falsche Bauform
#: (#1004/#1005: eine kuratierte Liste traegt ihr Aufnahmekriterium).
KOPFDATEN_SCHLUESSEL = {
    "start", "starttermin", "eintrittsdatum", "einsatzort", "ort",
    "standort", "bereich", "projektdauer", "projekttitel", "stellentyp",
    "beschaeftigungsart", "beschäftigungsart", "einstiegslevel",
    "befristung", "requisition id", "req id", "jobnummer", "nummer",
    "referenznummer",
}


def kopfdaten_bewahren(alt: str, neu: str) -> str:
    """Kopfzeilen des alten Textes, die im neuen fehlen — als Praefix.

    Ergaenzt, statt umzudeuten (#1048): uebernommen wird eine Zeile nur,
    wenn ihr Schluessel in der Liste steht UND ihr Wert im neuen Text
    nicht vorkommt. Damit entsteht keine Dublette, wenn die Detailseite
    dieselbe Angabe in anderer Form liefert.
    """
    if not alt or not neu:
        return neu or ""
    bewahrt = []
    for zeile in str(alt).split("\n")[:6]:
        z = zeile.strip()
        if not z or ":" not in z or len(z) > 120:
            break
        schluessel, _, wert = z.partition(":")
        if schluessel.strip().lower() not in KOPFDATEN_SCHLUESSEL:
            break
        wert = wert.strip()
        if wert and wert not in neu:
            bewahrt.append(f"{schluessel.strip()}: {wert}")
    if not bewahrt:
        return neu
    return "\n".join(bewahrt) + "\n\n" + neu


def text_uebernehmen(db, job_hash: str, text: str,
                     herkunft: str = "nachladen", kopf: dict | None = None) -> dict:
    """Schreibt einen nachgeladenen Anzeigentext — und was an ihm haengt.

    v1.7.109 (#1048): Bis hierher schrieben vier Aufrufer den Text selbst
    (MCP-Einzelweg, MCP-Mengenweg, Knopf im Dashboard, Auto-Nachzug), und
    keiner bewertete danach neu. Der Mengenweg sagte es wenigstens
    ("sollten neu bewertet werden"), die anderen drei nicht. Bei einer
    Stelle der Quelle `hays`, deren Text von 500 auf 2.300 Zeichen waechst, stand
    danach der volle Text neben einem Score, einem Gehalt und einem
    Umfang aus den ersten 500 Zeichen — also genau das, was der Melder
    als Folge beschreibt, nur eine Stufe spaeter.

    Ein Weg statt vier, sonst bekommt der naechste Aufrufer die Regel
    wieder nicht (#963).

    v1.7.122 (#1064): Kopfdaten des alten Textes, die der neue nicht
    traegt, bleiben erhalten — siehe `kopfdaten_bewahren`.
    """
    _alt = (db.get_job(job_hash) or {}).get("description") or ""
    text = kopfdaten_bewahren(_alt, text)
    db.update_job(job_hash, {"description": text})
    # C23 (#687): erster brauchbarer Volltext -> unveraenderlicher
    # Snapshot. Die 1.7-Linie hat keine Snapshot-Spalte; dort fehlt die
    # Methode, und der Schritt entfaellt.
    snapshot = getattr(db, "set_description_snapshot_if_empty", None)
    if snapshot is not None:
        snapshot(job_hash, text, herkunft)
    # v1.7.128 (#1040 Punkt 2): fehlende Firma und fehlender Ort aus der
    # Detailseite, BEVOR neu bewertet wird — der Score liest die Entfernung.
    ergaenzt = kopf_ergaenzen(db, job_hash, kopf)
    ergebnis = neu_auswerten(db, job_hash)
    ergebnis["kopf"] = ergaenzt
    return ergebnis


def neu_auswerten(db, job_hash: str) -> dict:
    """Gehalt, Umfang, Befristung und Score aus dem GESPEICHERTEN Text.

    Ein laengerer Text bringt nur zusaetzliche Belege, deshalb wird
    ergaenzt und nicht umgedeutet:

    * **Gehalt** nur, wenn der Text jetzt eines belegt. Eine Schaetzung
      wird dadurch ersetzt, ein vorhandener Wert ohne neuen Beleg nicht
      geloescht — dieselbe Regel wie `gehaelter_neu_auswerten` (#1018).
      Ein von Hand gesetztes Gehalt weist `save_salary_data` ab (#1026).
    * **Umfang** nur, wenn noch keiner gespeichert ist; eine Angabe der
      Quelle hat Vorrang vor dem Fliesstext (#1023), und ein gespeicherter
      Wert, der sich selbst bestaetigt, war schon einmal der Fehler
      (#1031).
    * **Befristet** nur von nein auf ja.
    * **Score** mit denselben Kriterien wie der Suchlauf (#987), ohne
      Netzabfrage — ein Nachladen ist keine Neuberechnung des Bestands.
    """
    ergebnis: dict = {"gehalt": False, "merkmale": [], "score": None}
    job = db.get_job(job_hash)
    if not job:
        return ergebnis
    text = job.get("description") or ""
    score_vorher = round(float(job.get("score") or 0), 1)

    try:
        from . import gehalt_extraktion
        neu = gehalt_extraktion.extrahieren(text)
        if neu.get("art"):
            gleich = (job.get("salary_type") == neu["art"]
                      and (job.get("salary_min") or 0) == (neu["min"] or 0)
                      and (job.get("salary_max") or 0) == (neu["max"] or 0)
                      and not job.get("salary_estimated"))
            if not gleich and db.save_salary_data(
                    job_hash, neu["min"], neu["max"], neu["art"],
                    salary_estimated=0):
                ergebnis["gehalt"] = True
    except Exception as exc:  # pragma: no cover — nie den Text verlieren
        logger.debug("Gehalt nach Nachladen (%s): %s", job_hash, exc)

    try:
        from . import stellenart
        m = stellenart.merkmale(job)
        spalten: dict = {}
        umfang_alt = (job.get("arbeitsumfang") or "").strip().lower()
        if (umfang_alt in ("", stellenart.UNBEKANNT)
                and m["umfang"] and m["umfang"] != stellenart.UNBEKANNT):
            spalten["arbeitsumfang"] = m["umfang"]
        if m["befristet"] and not job.get("befristet"):
            spalten["befristet"] = 1
        if spalten:
            ziel = db.resolve_job_hash(job_hash) or job_hash
            conn = db.connect()
            conn.execute(
                f"UPDATE jobs SET {', '.join(f'{k}=?' for k in spalten)} "
                "WHERE hash=?", (*spalten.values(), ziel))
            conn.commit()
            ergebnis["merkmale"] = sorted(spalten)
    except Exception as exc:  # pragma: no cover
        logger.debug("Merkmale nach Nachladen (%s): %s", job_hash, exc)

    try:
        from ..job_scraper import calculate_score
        from . import scoring_kriterien
        job = db.get_job(job_hash) or job
        score_neu = round(float(calculate_score(
            job, scoring_kriterien.fuer_scoring(db))), 1)
        felder = {"score": score_neu}
        if job.get("_fachscore") is not None:
            felder["fachscore"] = job.get("_fachscore")
            felder["rahmenscore"] = job.get("_rahmenscore")
        db.update_job(job_hash, felder)
        ergebnis["score"] = {"vorher": score_vorher, "nachher": score_neu}
    except Exception as exc:  # pragma: no cover
        logger.debug("Score nach Nachladen (%s): %s", job_hash, exc)
    return ergebnis
