"""Optionaler API-Weg der KI-Schicht: Anthropic-API mit eigenem Schluessel (#1236, F52).

Nur die 1.8-Linie und spaeter, nie die 1.7-Linie.

## Wozu

Wer ein API-Guthaben bei Anthropic hat, kann gleichartige Massenaufgaben, die sonst die lokale
KI (Ollama) erledigt, ueber die API laufen lassen. Ohne Schluessel aendert sich nichts: keine
Netzverbindung, keine Karte im Dashboard, keine zusaetzlichen Werkzeuge.

## Die Leitplanken (jede hat einen Test, die Gegenprobe `api` macht jede einzeln wirkungslos)

* **Vorgabe AUS, je Aufgabe einzeln.** `api_aufgaben` ist leer, bis ein Mensch eine Aufgabe
  freigibt, und das geht nur mit Schluessel und nach der Feldliste (was die API sieht).
* **Der Schluessel steht nur in der Umgebungsvariable `PBP_ANTHROPIC_API_KEY`.** PBP speichert
  ihn nirgends (nicht in der Datenbank, nicht in Sicherung, Export, Log, Telemetrie, Fehlermeldung).
  Jeder Text, der den Weg verlaesst, geht durch `schwaerzen`.
* **KI-Schalter.** `ki_features.master=False` und der Bereich der Aufgabe sperren auch diesen Weg.
* **Budget mit harter Obergrenze.** Ohne Budget kein Aufruf. Vor jedem Aufruf wird der schlimmste
  Fall gerechnet (geschaetzte Eingabe plus volle Antwortlaenge); passt er nicht mehr unter die
  Grenze, wird nicht gesendet. Gebucht wird, was die Antwort in `usage` meldet.
* **Unbekannt ist ein eigener Zustand.** Ein Modell ohne Preis wird nicht benutzt (das Budget liesse
  sich nicht einhalten); fehlt `usage` in einer Antwort, wird der schlimmste Fall gebucht und als
  geschaetzt gezaehlt.
* **Jeder Fehler hat einen Grund und einen Rueckfall.** Hoechstens eine Wiederholung bei 429 und
  5xx, keine Schleife. Danach faellt `LLMService.run` auf die lokale KI, dann auf Claude zurueck,
  mit genanntem Grund.
* **Gleichwertiger Schutz wie bei Ollama.** Derselbe Datumskontext, eine Eingabegrenze (statt des
  Kontextfensters) und eine Antwortlaenge je Aufgabe.

## Was ausdruecklich nicht

Keine Batch-Schnittstelle, kein Agent SDK, kein Claude Code, keine Anschreiben und kein Coaching
(die bleiben bei Claude Desktop). Keine Stichwort-, Mail- oder Kontaktaufgaben: dort stehen Namen
Dritter.

## Stand der Anfrageform

Die Anfrage folgt der Dokumentation (Messages API, Preisseite und Migrationsleitfaden zu Haiku 5.5,
Stand 16.10.2026). Sie ist in der Entwicklung nie gegen die echte API gelaufen (kein echter Aufruf, kein
Schluessel in der Umsetzung). `scripts/api_probe.py --senden` und `schluessel_pruefen` sind die
ersten echten Proben; ein Fehler der API steht dort im Klartext (`anfrage_abgelehnt`).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("bewerbungs_assistent.api_backend")

ENV_SCHLUESSEL = "PBP_ANTHROPIC_API_KEY"
ADRESSE = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
ZEITLIMIT_SEK = 25.0  # der MCP-Client bricht nach 60 s ab; ein Aufruf darf nicht den ganzen Lauf kosten
MAX_ANTWORT_BYTES = 1_000_000
WARTEZEIT_SEK = 2.0
WARTEZEIT_MAX_SEK = 10.0

#: Zeichen je Token fuer die Vorabschaetzung. Die neueren Modelle zaehlen rund 30 % mehr Tokens fuer
#: denselben Text; bewusst vorsichtig, denn eine Ueberschaetzung kostet hoechstens einen Rueckfall.
ZEICHEN_JE_TOKEN = 2.5
UMSCHLAG_TOKENS = 50  # Rahmen der Anfrage um den Prompt
MAX_EINGABE_TOKENS = 12_000  # weit unter der 100.000er-Grenze, ab der die Preise steigen

MAX_BUDGET_USD = 10_000

PLATZHALTER_FIRMA = "[Firma]"

# Einstellungen
S_AUFGABEN = "api_aufgaben"  # profilgebunden: {aufgabe: {"modell": id|None, "am": iso, "in": version}}
S_BUDGET = "api_budget_mikro_usd"  # global, ganze Mikro-Dollar (1 US-Dollar = 1.000.000)
S_LETZTER = "api_letzter_aufruf"
S_PRUEFUNG = "api_pruefung"
S_SEIT = "api_verbrauch_seit"
Z_AUFRUFE = "api_verbrauch_aufrufe"
Z_EINGABE = "api_verbrauch_eingabe_tokens"
Z_AUSGABE = "api_verbrauch_ausgabe_tokens"
Z_KOSTEN = "api_verbrauch_mikro_usd"
Z_GESCHAETZT = "api_verbrauch_geschaetzt"
ZAEHLER = (Z_AUFRUFE, Z_EINGABE, Z_AUSGABE, Z_KOSTEN, Z_GESCHAETZT)

_LOCK = threading.RLock()
_IN_FLIGHT = 0  # Mikro-Dollar, die laufende Aufrufe im schlimmsten Fall noch kosten koennen
_LETZTER_ERFOLG = 0.0  # Zeitstempel, damit Erfolge nicht jedes Mal in die Datenbank schreiben

# Der Schutzschalter gegen Schleifen: nach einem Fehler der Gegenstelle ruht der Weg eine Weile, statt dass
# jede der folgenden Stellen erneut einen Fehler (oder eine Zeitueberschreitung) abholt.
PAUSE_HART_SEK = 900  # Schluessel, Guthaben, Zugriff, Modell, Anfrageform: das aendert sich nicht von selbst
PAUSE_WEICH_SEK = 120  # Limit, Ueberlastung, Netz: das kann gleich wieder gehen
_HART = frozenset({"schluessel_ungueltig", "kein_zugriff", "guthaben_leer", "modell_nicht_gefunden",
                   "anfrage_abgelehnt"})
_WEICH = frozenset({"limit_erreicht", "ueberlastet", "zeitueberschreitung", "kein_netz", "unerwartet"})
_pause: Optional[tuple] = None  # (bis [monotonic], code, text)


# ── Gruende ──────────────────────────────────────────────────────────────────────────────────────────

#: Code -> Satz fuer Menschen. Die Codes sind Werte, die zurueckgeschickt werden (Umschrift); die
#: Saetze sind Anzeige.
GRUENDE: dict[str, str] = {
    "aufgabe_nicht_vorgesehen": "Diese Aufgabe läuft nicht über die API.",
    "nicht_freigegeben": "Diese Aufgabe ist für die API nicht freigegeben.",
    "ki_schalter_aus": "Ein KI-Schalter sperrt diese Aufgabe.",
    "kein_schluessel": f"Es ist kein API-Schlüssel gesetzt (Umgebungsvariable {ENV_SCHLUESSEL}).",
    "kein_budget": "Es ist kein Budget gesetzt. Ohne Obergrenze ruft PBP die API nicht auf.",
    "budget_erreicht": "Das Budget ist aufgebraucht.",
    "modell_unbekannt": "Das gewählte Modell steht nicht in der Modellliste von PBP.",
    "preis_unbekannt": "Für das gewählte Modell ist kein Preis hinterlegt. Ohne Preis lässt sich das Budget nicht einhalten.",
    "eingabe_zu_gross": "Die Eingabe ist zu lang für den API-Weg.",
    "schluessel_ungueltig": "Die API hat den Schlüssel abgelehnt (ungültig, widerrufen oder abgelaufen).",
    "kein_zugriff": "Der Schlüssel darf dieses Modell oder diese Funktion nicht nutzen.",
    "guthaben_leer": "Das Guthaben ist aufgebraucht, oder die Zahlungsangaben des Kontos sind nicht in Ordnung.",
    "limit_erreicht": "Die API meldet ein Limit: zu viele Anfragen, oder die Ausgabengrenze des Kontos ist erreicht.",
    "ueberlastet": "Die API ist gerade überlastet oder gestört.",
    "zeitueberschreitung": "Die API hat nicht rechtzeitig geantwortet.",
    "kein_netz": "Keine Verbindung zur API (kein Netz, Firewall oder Proxy).",
    "modell_nicht_gefunden": "Die API kennt das Modell nicht (mehr).",
    "anfrage_abgelehnt": "Die API hat die Anfrage abgelehnt.",
    "antwort_unlesbar": "Die Antwort der API ließ sich nicht lesen.",
    "antwort_abgelehnt": "Das Modell hat die Antwort verweigert.",
    "antwort_leer": "Die API hat keinen Text geliefert.",
    "unerwartet": "Beim API-Aufruf ist ein unerwarteter Fehler aufgetreten.",
}


class ApiFehler(Exception):
    """Ein benannter Grund, warum der API-Weg nicht geliefert hat. Der Text enthaelt nie den Schluessel."""

    def __init__(self, code: str, text: str | None = None, *, http_status: int | None = None,
                 request_id: str | None = None, verbraucht_unbekannt: bool = False):
        self.code = code
        self.text = schwaerzen(text or GRUENDE.get(code, code))
        self.http_status = http_status
        self.request_id = request_id
        # Die API hat geantwortet, die Antwort liess sich nicht lesen: vermutlich abgerechnet, Menge unbekannt.
        self.verbraucht_unbekannt = verbraucht_unbekannt
        super().__init__(self.text)


# ── Der Schluessel ───────────────────────────────────────────────────────────────────────────────────

_SCHLUESSEL_MUSTER = re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}")


def _schluessel() -> str:
    """Der Schluessel aus der Umgebung. Leer heisst: keiner. NUR hier wird er gelesen."""
    return (os.environ.get(ENV_SCHLUESSEL) or "").strip()


def schluessel_vorhanden() -> bool:
    return bool(_schluessel())


def schwaerzen(text: Any) -> str:
    """Entfernt den Schluessel (und alles, was wie ein Anthropic-Schluessel aussieht) aus einem Text.

    Geht durch jeden Text, der den Weg verlaesst: Fehlermeldungen, Log, Antworten, Anzeige.
    """
    s = str(text)
    k = _schluessel()
    if k:
        s = s.replace(k, "***")
    return _SCHLUESSEL_MUSTER.sub("***", s)


def schluessel_kennung() -> str:
    """Ein kurzer Fingerabdruck des aktuellen Schluessels (kein Teil des Schluessels).

    Damit eine gespeicherte Pruefung nur fuer den Schluessel gilt, der geprueft wurde.
    """
    k = _schluessel()
    if not k:
        return ""
    return hashlib.sha256(("pbp-api-pruefung:" + k).encode("utf-8")).hexdigest()[:12]


# ── Modelle und Preise (Konfiguration, kein Festwert im Code) ───────────────────────────────────────────

_KATALOG_PFAD = Path(__file__).resolve().parent.parent / "content" / "api_modelle.json"


@dataclass(frozen=True)
class Modell:
    id: str
    name: str
    eingabe_usd_je_mtok: Optional[Decimal]
    ausgabe_usd_je_mtok: Optional[Decimal]
    denken: str = "adaptiv"
    empfehlung: str = ""

    @property
    def preis_bekannt(self) -> bool:
        return self.eingabe_usd_je_mtok is not None and self.ausgabe_usd_je_mtok is not None


_katalog_cache: Optional[dict] = None


def _preis(wert: Any) -> Optional[Decimal]:
    if wert is None or isinstance(wert, bool):
        return None
    try:
        p = Decimal(str(wert).strip())
    except (InvalidOperation, ValueError):
        return None
    return p if p.is_finite() and p >= 0 else None


def katalog(neu_laden: bool = False) -> dict:
    """Die Modellliste: {'stand', 'quelle', 'hinweis', 'modelle': [Modell]}. Unlesbar heisst: leer."""
    global _katalog_cache
    with _LOCK:
        if _katalog_cache is not None and not neu_laden:
            return _katalog_cache
        try:
            roh = json.loads(_KATALOG_PFAD.read_text(encoding="utf-8"))
            modelle = []
            for m in roh.get("modelle") or []:
                if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"].strip():
                    continue
                modelle.append(Modell(
                    id=m["id"].strip(), name=str(m.get("name") or m["id"]),
                    eingabe_usd_je_mtok=_preis(m.get("eingabe_usd_je_mtok")),
                    ausgabe_usd_je_mtok=_preis(m.get("ausgabe_usd_je_mtok")),
                    denken=str(m.get("denken") or "adaptiv"), empfehlung=str(m.get("empfehlung") or "")))
            _katalog_cache = {"stand": str(roh.get("stand") or ""), "quelle": str(roh.get("quelle") or ""),
                              "hinweis": str(roh.get("hinweis") or ""), "modelle": modelle}
        except Exception as exc:  # noqa: BLE001 -- eine kaputte Datei darf keinen Aufruf kippen
            logger.warning("Modellliste des API-Wegs nicht lesbar (%s): leere Liste, der Weg ruht", type(exc).__name__)
            _katalog_cache = {"stand": "", "quelle": "", "hinweis": "", "modelle": []}
        return _katalog_cache


def modell_finden(modell_id: Optional[str]) -> Optional[Modell]:
    for m in katalog()["modelle"]:
        if m.id == modell_id:
            return m
    return None


def vorgabe_modell() -> Optional[Modell]:
    """Das guenstigste Modell mit bekanntem Preis (Summe aus Eingabe und Ausgabe)."""
    kandidaten = [m for m in katalog()["modelle"] if m.preis_bekannt]
    if not kandidaten:
        return None
    return min(kandidaten, key=lambda m: m.eingabe_usd_je_mtok + m.ausgabe_usd_je_mtok)


def kosten_mikro(modell: Modell, eingabe_tokens: int, ausgabe_tokens: int) -> Optional[int]:
    """Kosten in ganzen Mikro-Dollar, aufgerundet. None heisst: Preis unbekannt.

    Ein Dollar je Million Tokens ist genau ein Mikro-Dollar je Token, deshalb ist die Rechnung
    ohne Umrechnung exakt (Decimal, kein Gleitkomma).
    """
    if not modell.preis_bekannt:
        return None
    summe = (Decimal(max(0, int(eingabe_tokens))) * modell.eingabe_usd_je_mtok
             + Decimal(max(0, int(ausgabe_tokens))) * modell.ausgabe_usd_je_mtok)
    return int(summe.to_integral_value(rounding=ROUND_CEILING))


def schaetze_tokens(text: str) -> int:
    return math.ceil(len(text or "") / ZEICHEN_JE_TOKEN)


def preis_text(preis: Decimal) -> str:
    """Ein Preis je Million Tokens mit deutschem Komma und zwei Stellen: „0,10“, „2,00“, „10,00“."""
    return f"{preis.quantize(Decimal('0.01'))}".replace(".", ",")


def usd_text(mikro: int) -> str:
    """Mikro-Dollar als Text mit deutschem Komma: „5,50 US-Dollar“, „0,0099 US-Dollar“, „0,00002 US-Dollar“.

    Ab einem Dollar zwei Stellen; darunter so viele wie noetig (mindestens zwei, hoechstens sechs), damit
    ein Aufruf zu 20 Mikro-Dollar nicht als „0,00“ dasteht.
    """
    usd = Decimal(int(mikro)) / Decimal(1_000_000)
    if usd >= 1:
        text = f"{usd:.2f}"
    else:
        ganz, _, nach = f"{usd:.6f}".rstrip("0").partition(".")
        text = f"{ganz}.{nach.ljust(2, '0')}"
    return text.replace(".", ",") + " US-Dollar"


# ── Die Aufgaben: was geht an die API ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Feld:
    schluessel: str  # Schluessel in der Nutzlast der Aufgabe
    text: str  # so steht es vor der Freigabe in der Einstellung


@dataclass(frozen=True)
class Aufgabe:
    kennung: str  # TaskKind.value
    titel: str
    beschreibung: str
    ki_bereich: str  # Schalter unter „Claude (Cloud)“, der auch diesen Weg sperrt
    max_tokens: int
    felder: tuple[Feld, ...]
    nicht_gesendet: tuple[str, ...]


AUFGABEN: dict[str, Aufgabe] = {
    "match_job_to_skills": Aufgabe(
        kennung="match_job_to_skills",
        titel="Stellen mit deinem Profil abgleichen",
        beschreibung=("Die KI sagt je Stelle: passt, passt nicht oder unsicher, mit einer Zeile Begründung. "
                      "Das ist die Aufgabe hinter „Stellen automatisch aussortieren“."),
        ki_bereich="stellenanalyse",
        max_tokens=300,
        felder=(
            Feld("profile_position", "deine letzte Berufsbezeichnung"),
            Feld("profile_seniority", "deine Karrierestufe, aus den Berufsjahren berechnet (etwa „Senior, 12 Jahre“)"),
            Feld("profile_skills", "deine wichtigsten Kompetenzen (nur die Namen, bis zu 15)"),
            Feld("job_title", "der Titel der geprüften Stelle"),
            Feld("job_company", "die Firma der geprüften Stelle"),
            Feld("job_description", "der Anzeigentext der geprüften Stelle (die ersten 1.500 Zeichen)"),
            Feld("dismiss_reasons_top", "deine häufigsten Gründe fürs Aussortieren (bis zu 3, mit Anzahl)"),
            Feld("recent_dismissals", "Titel und Grund der Stellen, die du zuletzt aussortiert hast (bis zu 5); "
                                      f"die Firmennamen werden durch „{PLATZHALTER_FIRMA}“ ersetzt"),
        ),
        nicht_gesendet=("dein Name, deine Adresse, E-Mail und Telefonnummer", "Lebenslauf, Zeugnisse und andere Dokumente",
                        "Bewerbungen, Mails und Kontakte", "Gehaltsvorstellungen"),
    ),
    "validate_job_quality": Aufgabe(
        kennung="validate_job_quality",
        titel="Anzeigentexte auf Vollständigkeit prüfen",
        beschreibung=("Die KI prüft, ob eine Stellenanzeige Aufgaben, Anforderungen, Ort und Kontakt nennt und ob "
                      "der Text vollständig geladen wurde."),
        ki_bereich="stellenanalyse",
        max_tokens=600,
        felder=(
            Feld("title", "der Titel der Stelle"),
            Feld("company", "die Firma der Stelle"),
            Feld("location", "der Ort der Stelle"),
            Feld("source", "die Quelle, aus der die Stelle stammt"),
            Feld("url", "der Link der Anzeige"),
            Feld("description", "der Anzeigentext (die ersten 2.500 Zeichen)"),
        ),
        nicht_gesendet=("alles aus deinem Profil", "Dokumente, Bewerbungen, Mails und Kontakte"),
    ),
}


def aufgabe_finden(kennung_: str) -> Optional[Aufgabe]:
    return AUFGABEN.get(str(kennung_ or "").strip())


def _beispiele_schwaerzen(eintraege: Any) -> list:
    """Firmennamen aus den Beispielen der zuletzt aussortierten Stellen entfernen (Entscheidung zu Frage 4)."""
    aus = []
    for e in (eintraege or [])[:5]:
        if not isinstance(e, dict):
            continue
        firma = str(e.get("company") or "").strip()
        titel = str(e.get("title") or "")
        if len(firma) >= 3:
            titel = re.sub(r"(?<!\w)" + re.escape(firma) + r"(?!\w)", PLATZHALTER_FIRMA, titel, flags=re.IGNORECASE)
        aus.append({"title": titel, "company": PLATZHALTER_FIRMA if firma else "",
                    "dismiss_reason": e.get("dismiss_reason")})
    return aus


def nutzlast_fuer_api(aufgabe_kennung: str, payload: dict) -> dict:
    """Nur die Felder der Feldliste, und die Beispiele ohne Firmennamen.

    Die Feldliste ist die Liste, die der Mensch vor der Freigabe sieht: was hier nicht steht, geht nicht
    hinaus, auch wenn ein Aufrufer es in die Nutzlast legt.
    """
    a = aufgabe_finden(aufgabe_kennung)
    if a is None:
        raise ApiFehler("aufgabe_nicht_vorgesehen")
    erlaubt = {f.schluessel for f in a.felder}
    sicher = {k: v for k, v in (payload or {}).items() if k in erlaubt}
    if "recent_dismissals" in sicher:
        sicher["recent_dismissals"] = _beispiele_schwaerzen(sicher["recent_dismissals"])
    return sicher


# ── Einstellungen lesen und schreiben ──────────────────────────────────────────────────────────────────

def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _version() -> str:
    from .. import __version__
    return __version__


def _global(db, schluessel: str, vorgabe: Any = None) -> Any:
    try:
        return db.get_setting(schluessel, vorgabe)
    except Exception:  # noqa: BLE001 -- eine Einstellung zu lesen kippt keinen Aufruf
        return vorgabe


def _profil(db, schluessel: str, vorgabe: Any = None) -> Any:
    try:
        return db.get_profile_setting(schluessel, vorgabe)
    except Exception:  # noqa: BLE001
        return vorgabe


def freigaben_lesen(db) -> dict:
    """{aufgabe: {'modell': id|None, 'am': iso, 'in': version}} -- nur Bekanntes und Eindeutiges.

    Im Zweifel gilt der restriktivere Zustand: was sich nicht eindeutig lesen laesst, ist nicht freigegeben.
    """
    if db is None:
        return {}
    roh = _profil(db, S_AUFGABEN, None)
    if not isinstance(roh, dict):
        return {}
    aus = {}
    for name, wert in roh.items():
        if name not in AUFGABEN or not isinstance(wert, dict):
            continue
        modell = wert.get("modell")
        aus[name] = {"modell": modell if isinstance(modell, str) and modell.strip() else None,
                     "am": str(wert.get("am") or ""), "in": str(wert.get("in") or "")}
    return aus


def _freigaben_schreiben(db, freigaben: dict) -> None:
    db.set_profile_setting(S_AUFGABEN, freigaben)


def budget_lesen(db) -> Optional[int]:
    """Das Budget in Mikro-Dollar; None, wenn keins gesetzt (oder nicht lesbar) ist."""
    roh = _global(db, S_BUDGET, None) if db is not None else None
    if isinstance(roh, bool) or not isinstance(roh, int) or roh <= 0:
        return None
    return roh


def zaehler_lesen(db) -> dict:
    if db is None:
        return {"aufrufe": 0, "eingabe_tokens": 0, "ausgabe_tokens": 0, "mikro_usd": 0, "geschaetzt": 0, "seit": None}

    def zahl(k):
        v = _global(db, k, 0)
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0

    return {"aufrufe": zahl(Z_AUFRUFE), "eingabe_tokens": zahl(Z_EINGABE), "ausgabe_tokens": zahl(Z_AUSGABE),
            "mikro_usd": zahl(Z_KOSTEN), "geschaetzt": zahl(Z_GESCHAETZT), "seit": _global(db, S_SEIT, None)}


def _addieren(db, schluessel: str, delta: int) -> None:
    """Zaehler um `delta` erhoehen -- in EINER Anweisung, damit zwei Prozesse sich nicht ueberschreiben."""
    db.connect().execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = CAST(COALESCE(CAST(value AS INTEGER), 0) + ? AS TEXT)",
        (schluessel, str(int(delta)), int(delta)))


def verbuchen(db, eingabe_tokens: int, ausgabe_tokens: int, kosten: int, *, geschaetzt: bool = False) -> None:
    """Ein Aufruf in die Summen. Nur ganze Zahlen aus der Antwort (oder der schlimmste Fall, dann `geschaetzt`)."""
    conn = db.connect()
    _addieren(db, Z_AUFRUFE, 1)
    _addieren(db, Z_EINGABE, int(eingabe_tokens))
    _addieren(db, Z_AUSGABE, int(ausgabe_tokens))
    _addieren(db, Z_KOSTEN, int(kosten))
    if geschaetzt:
        _addieren(db, Z_GESCHAETZT, 1)
    conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (S_SEIT, json.dumps(_jetzt())))
    conn.commit()


def _letzten_aufruf_merken(db, *, ok: bool, aufgabe: str, modell: str, code: str | None = None,
                           text: str | None = None) -> None:
    """Der Stand des letzten Aufrufs fuer die Anzeige. Erfolge hoechstens alle 30 Sekunden."""
    global _LETZTER_ERFOLG
    jetzt = time.monotonic()
    if ok and jetzt - _LETZTER_ERFOLG < 30:
        return
    try:
        if ok:
            _LETZTER_ERFOLG = jetzt
        db.set_setting(S_LETZTER, {"ok": ok, "zeit": _jetzt(), "aufgabe": aufgabe, "modell": modell,
                                   "code": code, "text": schwaerzen(text)[:300] if text else None})
    except Exception as exc:  # noqa: BLE001 -- Anzeige darf den Aufruf nicht kippen
        logger.debug("letzter API-Aufruf nicht gespeichert: %s", type(exc).__name__)


def letzten_aufruf_lesen(db) -> Optional[dict]:
    roh = _global(db, S_LETZTER, None) if db is not None else None
    return roh if isinstance(roh, dict) else None


# ── Der Schutzschalter ───────────────────────────────────────────────────────────────────────────────────

def pause_setzen(code: str, text: str) -> None:
    """Nach einem Fehler der Gegenstelle ruht der Weg. Fehler, die nur diese Eingabe betreffen, pausieren nicht."""
    global _pause
    sekunden = PAUSE_HART_SEK if code in _HART else PAUSE_WEICH_SEK if code in _WEICH else 0
    if sekunden:
        with _LOCK:
            _pause = (time.monotonic() + sekunden, code, text)


def pause_aktiv() -> Optional[dict]:
    """{'code', 'text', 'rest_sekunden'}, solange der Weg ruht; sonst None."""
    with _LOCK:
        if _pause is None:
            return None
        rest = _pause[0] - time.monotonic()
        if rest <= 0:
            return None
        return {"code": _pause[1], "text": _pause[2], "rest_sekunden": int(rest) + 1}


def pause_aufheben() -> None:
    global _pause
    with _LOCK:
        _pause = None


def zuruecksetzen() -> None:
    """Bringt den Zustand im Speicher auf Anfang. Fuer Tests: ein Test darf dem naechsten nichts vererben."""
    global _IN_FLIGHT, _LETZTER_ERFOLG, _katalog_cache, _transport_ersatz
    with _LOCK:
        _IN_FLIGHT = 0
        _LETZTER_ERFOLG = 0.0
        _katalog_cache = None
        _transport_ersatz = None
        pause_aufheben()


# ── Darf diese Aufgabe jetzt ueber die API? ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Zustand:
    aufgabe: str
    freigegeben: bool
    erlaubt: bool
    grund: Optional[str] = None
    text: Optional[str] = None
    modell: Optional[str] = None


def _modell_fuer(db, aufgabe_kennung: str) -> tuple[Optional[Modell], Optional[str]]:
    """(Modell, Grund): das gewaehlte oder das guenstigste Modell. Der Grund nennt, warum keins gilt."""
    gewaehlt = freigaben_lesen(db).get(aufgabe_kennung, {}).get("modell")
    if gewaehlt:
        m = modell_finden(gewaehlt)
        if m is None:
            return None, "modell_unbekannt"
    else:
        m = vorgabe_modell()
        if m is None:
            return None, "preis_unbekannt"
    if not m.preis_bekannt:
        return m, "preis_unbekannt"
    return m, None


def _ki_schalter_grund(db, a: Aufgabe) -> Optional[str]:
    try:
        if db.is_ki_feature_enabled(a.ki_bereich):
            return None
        cfg = db.get_ki_features()
    except Exception:  # noqa: BLE001
        return None
    from .menue import pfad
    if not cfg.get("master", True):
        return f"Der KI-Hauptschalter ist aus ({pfad('claude')}); er sperrt auch den API-Weg."
    return f"Der Bereich „{a.ki_bereich}“ ist gesperrt ({pfad('claude')}); er sperrt auch den API-Weg."


def zustand(db, aufgabe_kennung: str) -> Zustand:
    """Die einzige Frage, ob eine Aufgabe JETZT ueber die API laufen darf. Immer mit Grund, nie geraten.

    Die Reihenfolge ist die Reihenfolge der Bedingungen; die erste fehlende nennt den Grund. Ist die
    Aufgabe nicht freigegeben, ist das der stille Normalfall.
    """
    a = aufgabe_finden(aufgabe_kennung)
    if a is None:
        return Zustand(str(aufgabe_kennung), False, False, "aufgabe_nicht_vorgesehen", GRUENDE["aufgabe_nicht_vorgesehen"])
    if db is None or aufgabe_kennung not in freigaben_lesen(db):
        return Zustand(aufgabe_kennung, False, False, "nicht_freigegeben", GRUENDE["nicht_freigegeben"])

    def nein(code, text=None, modell=None):
        return Zustand(aufgabe_kennung, True, False, code, text or GRUENDE[code], modell)

    schalter = _ki_schalter_grund(db, a)
    if schalter:
        return nein("ki_schalter_aus", schalter)
    if not schluessel_vorhanden():
        return nein("kein_schluessel")
    modell, grund = _modell_fuer(db, aufgabe_kennung)
    if grund:
        text = GRUENDE[grund] + (f" (Modell {modell.name})" if modell else "")
        return nein(grund, text, modell.id if modell else None)
    budget = budget_lesen(db)
    if budget is None:
        return nein("kein_budget", modell=modell.id)
    verbraucht = zaehler_lesen(db)["mikro_usd"] + _IN_FLIGHT
    if verbraucht >= budget:
        return nein("budget_erreicht", f"Das Budget von {usd_text(budget)} ist aufgebraucht "
                                       f"(verbraucht {usd_text(verbraucht)}).", modell.id)
    pause = pause_aktiv()
    if pause:
        return nein(pause["code"], f"{pause['text']} Der API-Weg ruht noch etwa {pause['rest_sekunden']} Sekunden, "
                                   "damit nicht jede Stelle denselben Fehler erneut abholt.", modell.id)
    return Zustand(aufgabe_kennung, True, True, None, None, modell.id)


# ── Die Anfrage ───────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Antwort:
    text: str
    modell: str
    eingabe_tokens: int
    ausgabe_tokens: int
    kosten_mikro: int
    geschaetzt: bool = False
    stop_reason: Optional[str] = None
    request_id: Optional[str] = None
    dauer_ms: int = 0


Transport = Callable[[str, dict, bytes, float], tuple]
_transport_ersatz: Optional[Transport] = None


def transport_setzen(transport: Optional[Transport]) -> None:
    """Tauscht den Transport aus (Tests). None stellt den echten wieder her."""
    global _transport_ersatz
    _transport_ersatz = transport


def _standard_transport(url: str, kopf: dict, body: bytes, zeitlimit: float) -> tuple:
    """(Status, Kopfzeilen, Koerper). Ein HTTP-Fehlerstatus kommt als Wert zurueck, Netzfehler als Ausnahme."""
    import urllib.error
    import urllib.request
    anfrage = urllib.request.Request(url, data=body, headers=kopf, method="POST")
    try:
        with urllib.request.urlopen(anfrage, timeout=zeitlimit) as antwort:
            return antwort.status, dict(antwort.headers.items()), antwort.read(MAX_ANTWORT_BYTES)
    except urllib.error.HTTPError as exc:
        try:
            koerper = exc.read(MAX_ANTWORT_BYTES)
        except Exception:  # noqa: BLE001
            koerper = b""
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, koerper


def _schlafen(sekunden: float) -> None:
    time.sleep(sekunden)


def _kopf(schluessel: str) -> dict:
    return {"content-type": "application/json", "x-api-key": schluessel,
            "anthropic-version": API_VERSION, "user-agent": f"PBP/{_version()} (api-weg)"}


def anfrage_koerper(modell: Modell, prompt: str, max_tokens: int) -> bytes:
    """Die Anfrage. Ohne temperature, top_p und top_k: die neueren Modelle weisen jeden anderen Wert ab."""
    daten: dict = {"model": modell.id, "max_tokens": int(max_tokens),
                   "messages": [{"role": "user", "content": prompt}]}
    if modell.denken == "aus":
        daten["thinking"] = {"type": "disabled"}
    elif modell.denken == "zwischen_werkzeugen":
        daten["thinking"] = {"type": "between_tools"}
    return json.dumps(daten, ensure_ascii=False).encode("utf-8")


def _fehler_aus_antwort(status: int, kopf: dict, koerper: bytes, modell: Modell) -> ApiFehler:
    """Aus einer Fehlerantwort der API einen benannten Grund machen."""
    meldung, art = "", ""
    request_id = None
    try:
        daten = json.loads(koerper.decode("utf-8", errors="replace"))
        fehler = daten.get("error") if isinstance(daten, dict) else None
        if isinstance(fehler, dict):
            meldung = str(fehler.get("message") or "")
            art = str(fehler.get("type") or "")
        request_id = daten.get("request_id") if isinstance(daten, dict) else None
    except Exception:  # noqa: BLE001
        pass
    request_id = request_id or {k.lower(): v for k, v in (kopf or {}).items()}.get("request-id")
    kleinmeldung = meldung.lower()
    if status == 401:
        code = "schluessel_ungueltig"
    elif status == 402 or (status == 400 and ("credit balance" in kleinmeldung or "billing" in kleinmeldung
                                              or "spend limit" in kleinmeldung)):
        code = "guthaben_leer"
    elif status == 403:
        code = "kein_zugriff"
    elif status == 404:
        code = "modell_nicht_gefunden"
    elif status == 413:
        code = "eingabe_zu_gross"
    elif status == 429:
        code = "limit_erreicht"
    elif status == 504:
        code = "zeitueberschreitung"
    elif status in (500, 502, 503, 529):
        code = "ueberlastet"
    elif status == 400:
        code = "anfrage_abgelehnt"
    else:
        code = "unerwartet"
    text = GRUENDE[code]
    if code == "modell_nicht_gefunden":
        text = f"Die API kennt das Modell {modell.id} nicht (mehr)."
    if code not in ("ueberlastet", "zeitueberschreitung"):
        # Was die API selbst sagt, steht dabei: bei einer abgelehnten Anfrage ist es die einzige Spur.
        zusatz = schwaerzen(meldung)[:200] or (f"HTTP {status}" if code in ("anfrage_abgelehnt", "unerwartet") else "")
        if zusatz:
            text = f"{text} Die API sagt: {zusatz}"
    return ApiFehler(code, text, http_status=status, request_id=request_id)


def _wartezeit(kopf: dict) -> float:
    for k, v in (kopf or {}).items():
        if str(k).lower() == "retry-after":
            try:
                return max(0.0, min(float(v), WARTEZEIT_MAX_SEK))
            except (TypeError, ValueError):
                break
    return WARTEZEIT_SEK


def _lesen(modell: Modell, status: int, koerper: bytes, kopf: dict, dauer_ms: int) -> Antwort:
    """Eine 200-Antwort lesen. Wirft ApiFehler, wenn sie unlesbar, verweigert oder leer ist."""
    request_id = {k.lower(): v for k, v in (kopf or {}).items()}.get("request-id")
    try:
        daten = json.loads(koerper.decode("utf-8", errors="replace"))
        if not isinstance(daten, dict):
            raise ValueError("kein Objekt")
    except Exception:  # noqa: BLE001
        raise ApiFehler("antwort_unlesbar", http_status=status, request_id=request_id,
                        verbraucht_unbekannt=True) from None
    nutzung = daten.get("usage") if isinstance(daten.get("usage"), dict) else None
    ein = aus = None
    if nutzung is not None:
        def tokens(k):
            v = nutzung.get(k)
            return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None
        ein, aus = tokens("input_tokens"), tokens("output_tokens")
        if ein is not None:
            # Zwischenspeicher-Felder (kommen ohne Caching nicht vor) zaehlen zur Eingabe, zum vollen Preis:
            # das ueberschaetzt hoechstens.
            ein += (tokens("cache_creation_input_tokens") or 0) + (tokens("cache_read_input_tokens") or 0)
    # Auch was HEREINkommt geht durch `schwaerzen`: ein Zwischenhaendler, der den Kopf der Anfrage in die Antwort spiegelt,
    # darf den Schluessel nicht in die Ergebnisse, die Notizen der Stellen oder einen Bericht tragen.
    text = schwaerzen("".join(b.get("text", "") for b in (daten.get("content") or [])
                              if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)))
    stop = daten.get("stop_reason") if isinstance(daten.get("stop_reason"), str) else None
    kosten = kosten_mikro(modell, ein, aus) if ein is not None and aus is not None else None
    return Antwort(text=text, modell=modell.id, eingabe_tokens=ein or 0, ausgabe_tokens=aus or 0,
                   kosten_mikro=kosten or 0, geschaetzt=kosten is None, stop_reason=stop,
                   request_id=request_id, dauer_ms=dauer_ms)


def _aufruf(db, modell: Modell, prompt: str, max_tokens: int, aufgabe: str, *, budget_pflicht: bool,
            transport: Optional[Transport] = None, schlafen: Optional[Callable[[float], None]] = None) -> Antwort:
    """Pruefen, senden (hoechstens eine Wiederholung), lesen, buchen. Wirft nur ApiFehler."""
    global _IN_FLIGHT
    schluessel = _schluessel()
    if not schluessel:
        raise ApiFehler("kein_schluessel")
    geschaetzt_ein = schaetze_tokens(prompt) + UMSCHLAG_TOKENS
    if geschaetzt_ein > MAX_EINGABE_TOKENS:
        raise ApiFehler("eingabe_zu_gross", f"Die Eingabe ist mit geschätzt {geschaetzt_ein} Tokens länger als die "
                                            f"Grenze von {MAX_EINGABE_TOKENS} für den API-Weg. Nicht gesendet.")
    reserve = kosten_mikro(modell, geschaetzt_ein, max_tokens)
    if reserve is None:
        raise ApiFehler("preis_unbekannt", f"{GRUENDE['preis_unbekannt']} (Modell {modell.name})")
    with _LOCK:
        budget = budget_lesen(db)
        if budget is None and budget_pflicht:
            raise ApiFehler("kein_budget")
        if budget is not None:
            verbraucht = zaehler_lesen(db)["mikro_usd"] + _IN_FLIGHT
            if verbraucht + reserve > budget:
                raise ApiFehler("budget_erreicht", (
                    f"Das Budget von {usd_text(budget)} reicht für diesen Aufruf nicht mehr: verbraucht "
                    f"{usd_text(verbraucht)}, ein Aufruf kann im ungünstigsten Fall {usd_text(reserve)} kosten. "
                    "Nicht gesendet."))
        _IN_FLIGHT += reserve
    try:
        senden_ = transport or _transport_ersatz or _standard_transport
        warten = schlafen or _schlafen
        body = anfrage_koerper(modell, prompt, max_tokens)
        kopf = _kopf(schluessel)
        start = time.monotonic()
        versuch = 0
        while True:
            versuch += 1
            try:
                status, antwortkopf, koerper = senden_(ADRESSE, kopf, body, ZEITLIMIT_SEK)
            except ApiFehler:
                raise
            except (TimeoutError, socket.timeout):
                raise ApiFehler("zeitueberschreitung") from None
            except Exception as exc:  # noqa: BLE001 -- jede Netzstoerung ist ein benannter Grund
                reason = getattr(exc, "reason", None)
                if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(exc).lower():
                    raise ApiFehler("zeitueberschreitung") from None
                raise ApiFehler("kein_netz", f"{GRUENDE['kein_netz']} ({type(exc).__name__})") from None
            dauer_ms = int((time.monotonic() - start) * 1000)
            if status == 200:
                break
            fehler = _fehler_aus_antwort(status, antwortkopf, koerper, modell)
            if versuch == 1 and status in (429, 500, 502, 503, 529):
                warten(_wartezeit(antwortkopf))
                continue
            raise fehler
        try:
            antwort = _lesen(modell, status, koerper, antwortkopf, dauer_ms)
        except ApiFehler as exc:
            if exc.verbraucht_unbekannt:
                # Die API hat geantwortet, wir koennen es nicht lesen: vermutlich abgerechnet. Der schlimmste Fall.
                verbuchen(db, geschaetzt_ein, max_tokens, reserve, geschaetzt=True)
            raise
        if antwort.geschaetzt:
            antwort.eingabe_tokens, antwort.ausgabe_tokens, antwort.kosten_mikro = geschaetzt_ein, max_tokens, reserve
        verbuchen(db, antwort.eingabe_tokens, antwort.ausgabe_tokens, antwort.kosten_mikro,
                  geschaetzt=antwort.geschaetzt)
        if antwort.stop_reason == "refusal":
            raise ApiFehler("antwort_abgelehnt", request_id=antwort.request_id)
        if not antwort.text.strip():
            zusatz = (" Die Antwort wurde vor dem Text abgeschnitten (Längengrenze)."
                      if antwort.stop_reason == "max_tokens" else "")
            raise ApiFehler("antwort_leer", GRUENDE["antwort_leer"] + zusatz, request_id=antwort.request_id)
        logger.info("API-Weg: %s, Modell %s, %d Tokens ein, %d aus, %s, %d ms%s", aufgabe, modell.id,
                    antwort.eingabe_tokens, antwort.ausgabe_tokens, usd_text(antwort.kosten_mikro), antwort.dauer_ms,
                    " (geschaetzt)" if antwort.geschaetzt else "")
        return antwort
    finally:
        with _LOCK:
            _IN_FLIGHT = max(0, _IN_FLIGHT - reserve)


def senden(db, aufgabe_kennung: str, prompt: str, *, transport: Optional[Transport] = None,
           schlafen: Optional[Callable[[float], None]] = None) -> Antwort:
    """Ein Aufruf fuer eine freigegebene Aufgabe. Prueft vor dem Senden alles noch einmal.

    Wirft `ApiFehler` mit benanntem Grund (nie etwas anderes aus diesem Weg) und merkt sich den Ausgang
    fuer die Anzeige.
    """
    z = zustand(db, aufgabe_kennung)
    a = aufgabe_finden(aufgabe_kennung)
    if not z.erlaubt:
        raise ApiFehler(z.grund or "nicht_freigegeben", z.text)
    modell = modell_finden(z.modell)
    try:
        antwort = _aufruf(db, modell, prompt, a.max_tokens, aufgabe_kennung, budget_pflicht=True,
                          transport=transport, schlafen=schlafen)
    except ApiFehler as exc:
        _letzten_aufruf_merken(db, ok=False, aufgabe=aufgabe_kennung, modell=modell.id, code=exc.code, text=exc.text)
        if exc.code == "schluessel_ungueltig":
            _pruefung_merken(db, "ungueltig", exc.code)
        pause_setzen(exc.code, exc.text)
        logger.warning("API-Weg: %s nicht erfolgreich (%s)", aufgabe_kennung, exc.code)
        raise
    _letzten_aufruf_merken(db, ok=True, aufgabe=aufgabe_kennung, modell=modell.id)
    return antwort


# ── „Schluessel gueltig“ erst nach einer echten Probe ─────────────────────────────────────────────────────

def _pruefung_merken(db, ergebnis: str, code: str | None = None) -> None:
    try:
        db.set_setting(S_PRUEFUNG, {"ergebnis": ergebnis, "code": code, "zeit": _jetzt(),
                                    "kennung": schluessel_kennung()})
    except Exception as exc:  # noqa: BLE001
        logger.debug("Pruefung nicht gespeichert: %s", type(exc).__name__)


def pruefung_lesen(db) -> dict:
    """{'ergebnis': gueltig | ungueltig | unklar | nicht_geprueft, ...}. Gilt nur fuer den geprueften Schluessel."""
    roh = _global(db, S_PRUEFUNG, None) if db is not None else None
    if (not isinstance(roh, dict) or roh.get("ergebnis") not in ("gueltig", "ungueltig", "unklar")
            or not schluessel_kennung() or roh.get("kennung") != schluessel_kennung()):
        return {"ergebnis": "nicht_geprueft", "code": None, "zeit": None}
    return {"ergebnis": roh["ergebnis"], "code": roh.get("code"), "zeit": roh.get("zeit")}


def schluessel_pruefen(db, *, transport: Optional[Transport] = None,
                       schlafen: Optional[Callable[[float], None]] = None) -> dict:
    """Die echte Probe: eine kleinste Anfrage. Nur auf ausdruecklichen Wunsch eines Menschen.

    „gueltig“ steht erst, wenn die API die Anfrage angenommen und beantwortet hat. Alles andere ist
    „ungueltig“ (401) oder „unklar“ (Netz, Limit, Guthaben ...), mit dem Grund -- nie ein stilles „ok“.
    """
    if not schluessel_vorhanden():
        return {"ergebnis": "nicht_geprueft", "code": "kein_schluessel", "text": GRUENDE["kein_schluessel"]}
    modell = vorgabe_modell()
    if modell is None:
        return {"ergebnis": "nicht_geprueft", "code": "preis_unbekannt", "text": GRUENDE["preis_unbekannt"]}
    try:
        antwort = _aufruf(db, modell, "Antworte nur mit dem Wort: ok", 16, "pruefung", budget_pflicht=False,
                          transport=transport, schlafen=schlafen)
    except ApiFehler as exc:
        ergebnis = "ungueltig" if exc.code == "schluessel_ungueltig" else "unklar"
        _pruefung_merken(db, ergebnis, exc.code)
        _letzten_aufruf_merken(db, ok=False, aufgabe="pruefung", modell=modell.id, code=exc.code, text=exc.text)
        pause_setzen(exc.code, exc.text)
        return {"ergebnis": ergebnis, "code": exc.code, "text": exc.text}
    _pruefung_merken(db, "gueltig")
    _letzten_aufruf_merken(db, ok=True, aufgabe="pruefung", modell=modell.id)
    pause_aufheben()  # die Probe hat gerade gezeigt, dass es geht
    return {"ergebnis": "gueltig", "code": None, "modell": modell.id,
            "kosten": usd_text(antwort.kosten_mikro),
            "text": "Die API hat die Probeanfrage angenommen und beantwortet."}


# ── Einstellungen aendern ─────────────────────────────────────────────────────────────────────────────────

def _usd_in_mikro(wert: Any) -> Optional[int]:
    """„5“, „5,50“, 5.5 -> Mikro-Dollar, auf Cent gerundet. None bei allem, was kein Betrag ist."""
    if isinstance(wert, bool) or wert is None:
        return None
    try:
        d = Decimal(str(wert).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite() or d < 0 or d > MAX_BUDGET_USD:
        return None
    return int((d.quantize(Decimal("0.01")) * 1_000_000).to_integral_value())


def feldliste(aufgabe_kennung: str) -> dict:
    a = AUFGABEN[aufgabe_kennung]
    return {"id": a.kennung, "titel": a.titel, "beschreibung": a.beschreibung,
            "gesendet": [f.text for f in a.felder], "nicht_gesendet": list(a.nicht_gesendet),
            "immer": "das heutige Datum", "ki_bereich": a.ki_bereich}


def freigabe_text(aufgaben: list[str]) -> str:
    """Der Satz vor der Freigabe: wohin die Daten gehen und was gesendet wird."""
    teile = []
    for kennung_ in aufgaben:
        f = feldliste(kennung_)
        teile.append(f"„{f['titel']}“ sendet: " + "; ".join(f["gesendet"]) + ". Nicht gesendet: "
                     + "; ".join(f["nicht_gesendet"]) + ".")
    return ("Mit dieser Freigabe verlassen die genannten Angaben deinen Rechner und gehen an Anthropic "
            "(die Firma hinter Claude). Das ist eine Ausnahme von „läuft komplett lokal“. " + " ".join(teile))


def einstellungen_setzen(db, *, aufgaben: Optional[list] = None, modelle: Optional[dict] = None,
                         budget_usd: Any = None, bestaetigt: bool = False) -> dict:
    """Setzer zu `uebersicht`. Nur übergebene Werte werden geändert.

    * `aufgaben`: die vollständige Liste der freigegebenen Aufgaben. Neu hinzukommende brauchen einen Schlüssel
      und `bestaetigt=True` (ohne ihn kommt nur die Feldliste); Wegnehmen wirkt sofort.
    * `modelle`: {aufgabe: modell_id oder None für das günstigste}. Nur Modelle mit Preis aus der Liste.
    * `budget_usd`: die Obergrenze in US-Dollar; 0 heißt: nichts darf ausgegeben werden.
    """
    fehler = []
    if aufgaben is None and modelle is None and budget_usd is None:
        return {"status": "unveraendert", "text": "Nichts zu ändern: weder Aufgaben noch Modelle noch Budget angegeben."}
    if aufgaben is not None:
        if not isinstance(aufgaben, (list, tuple, set)):
            return {"status": "fehler", "text": "„aufgaben“ muss eine Liste von Aufgaben sein.",
                    "erlaubt": list(AUFGABEN)}
        gewuenscht = list(dict.fromkeys(str(a).strip() for a in aufgaben))
        unbekannt = [a for a in gewuenscht if a not in AUFGABEN]
        if unbekannt:
            return {"status": "fehler", "text": "Diese Aufgabe läuft nicht über die API: " + ", ".join(unbekannt) + ".",
                    "erlaubt": list(AUFGABEN)}
    else:
        gewuenscht = None
    if modelle is not None:
        if not isinstance(modelle, dict):
            return {"status": "fehler", "text": "„modelle“ muss eine Zuordnung Aufgabe → Modell sein."}
        for aufgabe, modell_id in modelle.items():
            if aufgabe not in AUFGABEN:
                fehler.append(f"Die Aufgabe „{aufgabe}“ läuft nicht über die API.")
            elif modell_id not in (None, ""):
                m = modell_finden(str(modell_id))
                if m is None:
                    fehler.append(f"Das Modell „{modell_id}“ steht nicht in der Modellliste: "
                                  + ", ".join(x.id for x in katalog()["modelle"]) + ".")
                elif not m.preis_bekannt:
                    fehler.append(f"Für „{modell_id}“ ist kein Preis hinterlegt; ohne Preis lässt sich das Budget nicht einhalten.")
    mikro = None
    if budget_usd is not None:
        mikro = _usd_in_mikro(budget_usd)
        if mikro is None:
            fehler.append(f"„{budget_usd}“ ist kein gültiger Betrag (erlaubt: 0 bis {MAX_BUDGET_USD} US-Dollar).")
    if fehler:
        return {"status": "fehler", "text": " ".join(fehler), "nichts_gespeichert": True}

    with _LOCK:
        aktuell = freigaben_lesen(db)
        neu = dict(aktuell) if gewuenscht is None else {a: aktuell[a] for a in gewuenscht if a in aktuell}
        dazu = [a for a in (gewuenscht or []) if a not in aktuell]
        if dazu:
            if not schluessel_vorhanden():
                return {"status": "fehler", "code": "kein_schluessel", "text": GRUENDE["kein_schluessel"] + (
                    " Eine Aufgabe lässt sich erst freigeben, wenn ein Schlüssel da ist."), "nichts_gespeichert": True}
            if not bestaetigt:
                return {"status": "bestaetigung_noetig", "aufgaben": [feldliste(a) for a in dazu],
                        "text": freigabe_text(dazu) + " Soll das so sein?"}
            for a in dazu:
                neu[a] = {"modell": None, "am": _jetzt(), "in": _version()}
        if modelle:
            for aufgabe, modell_id in modelle.items():
                if aufgabe in neu:
                    neu[aufgabe] = {**neu[aufgabe], "modell": str(modell_id) if modell_id else None}
                else:
                    return {"status": "fehler", "text": f"„{aufgabe}“ ist nicht freigegeben; zuerst freigeben, dann das Modell wählen.",
                            "nichts_gespeichert": True}
        if gewuenscht is not None or modelle:
            _freigaben_schreiben(db, neu)
        if mikro is not None:
            db.set_setting(S_BUDGET, mikro)
        pause_aufheben()  # wer etwas einstellt, will es auch ausprobieren
    ergebnis = {"status": "gespeichert"}
    if dazu:
        ergebnis["freigegeben"] = dazu
    if gewuenscht is not None and set(aktuell) - set(gewuenscht):
        ergebnis["gesperrt"] = sorted(set(aktuell) - set(gewuenscht))
    return ergebnis


# ── Auskunft ──────────────────────────────────────────────────────────────────────────────────────────────

def sichtbar(db) -> bool:
    """Gibt es etwas zu zeigen? Ein Schluessel, eine Freigabe oder bereits Verbrauch. Sonst nichts (Karte, Werkzeuge)."""
    if schluessel_vorhanden():
        return True
    if db is None:
        return False
    return bool(freigaben_lesen(db)) or zaehler_lesen(db)["aufrufe"] > 0


def uebersicht(db) -> dict:
    """Alles für Dashboard und Claude: Stand, Aufgaben mit Feldliste, Budget, Verbrauch. Nie der Schlüssel."""
    if not sichtbar(db):
        return {"sichtbar": False, "schluessel_gesetzt": False}
    freigaben = freigaben_lesen(db)
    verbrauch = zaehler_lesen(db)
    budget = budget_lesen(db)
    vorgabe = vorgabe_modell()
    aufgaben = []
    for kennung_, a in AUFGABEN.items():
        z = zustand(db, kennung_)
        modell = modell_finden(z.modell) if z.modell else (
            modell_finden(freigaben.get(kennung_, {}).get("modell")) or vorgabe)
        aufgaben.append({**feldliste(kennung_), "freigegeben": kennung_ in freigaben,
                         "modell": modell.id if modell else None, "modell_name": modell.name if modell else None,
                         "bereit": z.erlaubt, "grund": z.grund if kennung_ in freigaben else None,
                         "grund_text": z.text if kennung_ in freigaben and not z.erlaubt else None,
                         "freigegeben_am": freigaben.get(kennung_, {}).get("am") or None})
    cat = katalog()
    ausgegeben = verbrauch["mikro_usd"]
    hinweise = []
    if freigaben and not schluessel_vorhanden():
        hinweise.append(f"Es sind Aufgaben freigegeben, aber es ist kein Schlüssel gesetzt ({ENV_SCHLUESSEL}): "
                        "der API-Weg ruht, alles läuft wie ohne ihn.")
    if freigaben and budget is None:
        hinweise.append("Es ist kein Budget gesetzt: ohne Obergrenze ruft PBP die API nicht auf.")
    if verbrauch["geschaetzt"]:
        hinweise.append(f"{verbrauch['geschaetzt']} Aufruf(e) wurden mit dem ungünstigsten Fall gebucht, weil die "
                        "Antwort keine Verbrauchsangabe hatte; die Summe liegt eher zu hoch als zu niedrig.")
    return {
        "sichtbar": True,
        "schluessel_gesetzt": schluessel_vorhanden(),
        "variable": ENV_SCHLUESSEL,
        "pruefung": pruefung_lesen(db),
        "aufgaben": aufgaben,
        "budget": {"gesetzt": budget is not None, "usd": budget / 1_000_000 if budget else None,
                   "verbleibend_usd": max(0, budget - ausgegeben) / 1_000_000 if budget else None,
                   "text": usd_text(budget) if budget else None},
        "verbrauch": {"aufrufe": verbrauch["aufrufe"], "eingabe_tokens": verbrauch["eingabe_tokens"],
                      "ausgabe_tokens": verbrauch["ausgabe_tokens"], "usd": ausgegeben / 1_000_000,
                      "text": usd_text(ausgegeben), "geschaetzt_aufrufe": verbrauch["geschaetzt"],
                      "seit": verbrauch["seit"]},
        "letzter_aufruf": letzten_aufruf_lesen(db),
        "modelle": [{"id": m.id, "name": m.name, "vorgabe": bool(vorgabe and m.id == vorgabe.id),
                     "preis_bekannt": m.preis_bekannt,
                     "eingabe_usd_je_mtok": str(m.eingabe_usd_je_mtok) if m.preis_bekannt else None,
                     "ausgabe_usd_je_mtok": str(m.ausgabe_usd_je_mtok) if m.preis_bekannt else None,
                     "preis": (f"{preis_text(m.eingabe_usd_je_mtok)} / {preis_text(m.ausgabe_usd_je_mtok)} US-Dollar je "
                               "Million Tokens (Eingabe / Ausgabe)") if m.preis_bekannt else "Preis unbekannt",
                     "empfehlung": m.empfehlung} for m in cat["modelle"]],
        "preise_stand": cat["stand"], "preise_hinweis": cat["hinweis"],
        "hinweise": hinweise,
        "grenze": ("Der Zähler zählt nur Aufrufe, die über PBP laufen. Das tatsächliche Guthaben steht in der "
                   "Anthropic Console."),
    }


def datenfluss_zeilen(db) -> list[str]:
    """Für die Datenschutz-Anzeige: was PBP selbst an die API schickt. Leer, solange nichts freigegeben ist."""
    zeilen = []
    for kennung_ in freigaben_lesen(db):
        f = feldliste(kennung_)
        zeilen.append(f"Direkt an die Anthropic-API, „{f['titel']}“ (dein API-Weg): " + "; ".join(f["gesendet"]))
    return zeilen
