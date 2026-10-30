"""Wer haelt das Dashboard — und damit den Planer? (#1155)

Das Dashboard liegt auf EINEM Port (8200). Zwei PBP-Prozesse koennen ihn nicht
teilen: der MCP-Prozess, den Claude Desktop startet, und das eigenstaendige
Dashboard (Desktop-Verknuepfung). Wer zuerst da ist, hat das Dashboard — und
den Planer (taegliche Sicherung, geplante Suche, Lernen). Der zweite startet
beides nicht, damit nichts doppelt laeuft.

Bis v1.7.147 blieb es dabei: schloss man das andere Fenster, gab es bis zum
Neustart von Claude Desktop weder Dashboard noch Sicherung noch geplante Suche,
und die Karte "Sicherungen" versprach weiter "PBP sichert einmal am Tag von
selbst". Jetzt sieht der Prozess, der den Port nicht bekam, in Abstaenden
nach (`server.dashboard_nachholen_starten`) und uebernimmt, sobald er frei ist.

Dieses Modul haelt nur den Stand, damit `pbp_diagnose` ihn nennen kann, ohne
`server` zu importieren (das oeffnet beim Import eine Datenbank).
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

EIGENER = "eigener_prozess"
ANDERER = "anderer_prozess"
#: Der Port ist belegt, aber nicht von einem PBP (#1149): ein anderes Programm.
FREMDES = "fremdes_programm"
#: Der Port ist belegt, das Programm dort nimmt Verbindungen an, antwortet aber nicht (#1290):
#: unbekannt, nicht fremd (Lehre 2). Meist ein haengender PBP-Prozess.
HAENGT = "dashboard_haengt"
KEINER = "keiner"

#: Auskunft ueber einen belegten Port (`port_auskunft`).
ANTWORT_PBP = "pbp"
ANTWORT_FREMD = "fremd"
ANTWORT_KEINE = "keine_antwort"
#: Zeitgrenze und Versuche fuer die Frage "antwortet dort ein PBP?" (#1290). Ein beschaeftigtes PBP
#: (Suchlauf, Sicherung) braucht gemessen auch mal laenger als 2 s; ein Timeout ist kein "fremd".
ANTWORT_ZEIT_S = 5.0
ANTWORT_VERSUCHE = 2

_lock = threading.Lock()
_zustand: dict = {}


def zuruecksetzen() -> None:
    """Zurueck auf "noch nicht entschieden" (Start und Tests)."""
    with _lock:
        _zustand.clear()
        _zustand.update({
            "halter": KEINER, "port": None, "seit": None, "server": None,
            "fehler": "", "entschieden": False, "pruefintervall_s": None,
            "nachhol_versuche": 0, "besitzer": None,
        })


zuruecksetzen()


def setzen(halter: str, port: int | None = None, server=None, fehler: str = "",
           besitzer: dict | None = None) -> None:
    """Haelt fest, wer das Dashboard in diesem Prozess hat (`besitzer`: wer sonst den Port haelt, falls bekannt)."""
    with _lock:
        _zustand.update({
            "halter": halter, "port": port, "server": server, "fehler": fehler,
            "besitzer": dict(besitzer) if isinstance(besitzer, dict) else None,
            "entschieden": True,
            "seit": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })


def port_belegt(port: int, host: str = "127.0.0.1", timeout: float = 4.0) -> bool:
    """Lauscht auf dem Port etwas? (#1290) Genau dann "frei", wenn ein Server dort binden koennte.

    `connect_ex(...) == 0` las jeden Fehlschlag als "frei". Ein haengender Prozess nimmt aber Verbindungen an, ohne sie zu
    bearbeiten; ist seine Warteschlange voll, laeuft der naechste Verbindungsversuch in die Zeitgrenze (oder wird nach einigen
    Sekunden abgelehnt), und ein zweiter Server rannte gegen den belegten Port. Darum zaehlt zuerst, ob ein Binden gelingt
    (gelingt es, ist der Port frei; schlaegt es mit "Adresse in Benutzung" fehl, ist er belegt). Nur bei einem anderen
    Bindefehler (zum Beispiel ein von Windows reservierter Bereich) entscheidet ein Verbindungsversuch, und dort gilt nur eine
    abgelehnte Verbindung als frei; Zeitueberschreitung und jeder andere Fehler gelten als belegt (im Zweifel nicht anfassen).
    """
    import errno
    import socket
    import sys
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if sys.platform != "win32":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # wie uvicorn: TIME_WAIT blockiert nicht
            s.bind((host, int(port)))
        return False
    except OSError as exc:
        if exc.errno in (errno.EADDRINUSE, 10048) or getattr(exc, "winerror", None) == 10048:
            return True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            fehler = s.connect_ex((host, int(port)))
    except OSError:
        return True
    return fehler == 0 or fehler not in (errno.ECONNREFUSED, 10061)


def _probe(port: int, timeout: float, host: str, urlopen=None) -> str:
    """Eine einzelne Frage an `/api/health`: `ANTWORT_PBP`, `ANTWORT_FREMD` oder `ANTWORT_KEINE`."""
    import json
    import urllib.error
    import urllib.request
    oeffne = urlopen or urllib.request.urlopen
    try:
        # urlopen wirft bei 4xx/5xx (HTTPError) und folgt Weiterleitungen: was hier
        # ankommt, ist eine erfolgreiche Antwort.
        with oeffne(f"http://{host}:{int(port)}/api/health", timeout=timeout) as antwort:
            roh = antwort.read(65536)
    except urllib.error.HTTPError:
        return ANTWORT_FREMD                      # der Port antwortet, nur nicht mit einer Gesundheitsauskunft
    except Exception as exc:  # noqa: BLE001
        grund = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        if isinstance(grund, TimeoutError):       # Verbindung steht, Antwort bleibt aus (socket.timeout ist TimeoutError)
            return ANTWORT_KEINE
        return ANTWORT_FREMD                      # abgelehnt, getrennt, kein HTTP: dort spricht etwas anderes
    try:
        daten = json.loads(roh.decode("utf-8", errors="replace"))
    except ValueError:
        return ANTWORT_FREMD
    return ANTWORT_PBP if isinstance(daten, dict) and "pbp_version" in daten else ANTWORT_FREMD


def port_auskunft(port: int, timeout: float = ANTWORT_ZEIT_S, versuche: int = ANTWORT_VERSUCHE,
                  host: str = "127.0.0.1", urlopen=None) -> str:
    """Was antwortet auf diesem Port? Drei Ausgaenge statt Ja/Nein (#1290).

    * `ANTWORT_PBP`   — `/api/health` liefert JSON mit `pbp_version`.
    * `ANTWORT_FREMD` — der Port antwortet, aber nicht wie PBP (HTTP-Fehler, kein JSON, JSON ohne `pbp_version`,
      sofort abgelehnt oder getrennt).
    * `ANTWORT_KEINE` — die Zeit lief ab: die Verbindung steht, aber es kommt nichts. Das ist UNBEKANNT, nicht fremd:
      am 30.10.2026 hielt ein haengender PBP-Prozess den Port, und `ist_pbp` machte daraus "kein PBP".

    Nur bei einer Zeitueberschreitung gibt es einen weiteren Versuch (ein beschaeftigter Prozess antwortet beim zweiten
    Mal oft); alles andere ist sofort eindeutig. Nur die Standardbibliothek. `urlopen` ist fuer Tests austauschbar.
    """
    ergebnis = ANTWORT_KEINE
    for _ in range(max(1, int(versuche))):
        ergebnis = _probe(port, timeout, host, urlopen)
        if ergebnis != ANTWORT_KEINE:
            return ergebnis
    return ergebnis


def ist_pbp(port: int, timeout: float = 2.0, host: str = "127.0.0.1") -> bool:
    """Antwortet auf diesem Port ein PBP? (#1149) Ein Versuch, kurze Zeitgrenze.

    Ein belegter Port heisst noch nicht, dass dort ein PBP laeuft: bis v1.7.148
    schrieb `start_dashboard.py` "PBP laeuft bereits ... Das Dashboard ist schon
    erreichbar!" und oeffnete den Browser, auch wenn ein fremdes Programm den
    Port hielt (gemessen mit einem Programm auf einem Testport). Erkannt wird PBP
    an `/api/health` (seit v1.4.0): eine JSON-Antwort mit `pbp_version`.

    Nur fuer Aufrufer, die bloss warten (`browser_oeffnen`): sie brauchen kein Urteil ueber den Besitzer.
    Wer wissen muss, WARUM nichts antwortet, ruft `port_auskunft`.
    """
    return port_auskunft(port, timeout=timeout, versuche=1, host=host) == ANTWORT_PBP


def kennung_text(besitzer: dict | None) -> str:
    """"(Kennung 14552, seit 29.10. 19:23)" oder "": was ueber den Besitzer eines Ports bekannt ist."""
    if not isinstance(besitzer, dict) or not besitzer.get("pid"):
        return ""
    teile = [f"Kennung {besitzer['pid']}"]
    if besitzer.get("seit_text"):
        teile.append(f"seit {besitzer['seit_text']}")
    return ", ".join(teile)


def besitzer_zusatz(besitzer: dict | None) -> str:
    """", Name, Kennung N, seit ..." (mit fuehrendem Komma) oder "": Anhang fuer die Meldung ueber ein fremdes Programm."""
    name = (besitzer or {}).get("name") or ""
    teile = [t for t in (name, kennung_text(besitzer)) if t]
    return (", " + ", ".join(teile)) if teile else ""


def beenden_befehl(pid) -> str:
    """Der Befehl, mit dem man einen Prozess von Hand beendet (fuer Meldungen ohne Terminal)."""
    import sys
    return f"taskkill /PID {int(pid)} /F" if sys.platform == "win32" else f"kill {int(pid)}"


def belegt_text(port: int, auskunft: str, besitzer: dict | None = None) -> str:
    """Der ehrliche Satz, wenn ein Port belegt ist und dort kein PBP antwortet. Nie "kein PBP" bei ausbleibender Antwort."""
    kennung = kennung_text(besitzer)
    name = (besitzer or {}).get("name") or ""
    wer = f"{name}, {kennung}" if name and kennung else (name or kennung)
    if auskunft == ANTWORT_KEINE:
        if (besitzer or {}).get("ist_eigener_pbp"):
            return (f"Port {port} ist belegt, das Programm dort antwortet aber nicht. Es ist ein PBP-Prozess "
                    f"({kennung}), der vermutlich hängt.")
        if wer:
            return (f"Port {port} ist belegt, das Programm dort ({wer}) antwortet aber nicht. "
                    f"Ob es ein PBP ist, lässt sich nicht sicher sagen.")
        return (f"Port {port} ist belegt, das Programm dort antwortet aber nicht. "
                f"Wer den Port hält, konnte PBP nicht feststellen.")
    return (f"Port {port} wird von einem ANDEREN Programm benutzt" + (f" ({wer})" if wer else "")
            + ". Es antwortet nicht wie PBP.")


def pruefintervall_merken(sekunden: float | None) -> None:
    with _lock:
        _zustand["pruefintervall_s"] = sekunden


def versuch_zaehlen() -> None:
    with _lock:
        _zustand["nachhol_versuche"] = _zustand.get("nachhol_versuche", 0) + 1


def server():
    """Der uvicorn-Server dieses Prozesses (zum sauberen Beenden) oder None."""
    with _lock:
        return _zustand.get("server")


def lesen() -> dict:
    """Der Stand ohne das Server-Objekt."""
    with _lock:
        return {k: v for k, v in _zustand.items() if k != "server"}


def beschreiben() -> dict | None:
    """Eine Auskunft fuer `pbp_diagnose`, oder None, solange nichts entschieden ist.

    Rueckgabe: {"art": "info"|"warnung", "meldung": str}
    """
    z = lesen()
    if not z["entschieden"]:
        return None
    port = z["port"]
    if z["halter"] == EIGENER:
        return {"art": "info",
                "meldung": (f"Dashboard und Planer (tägliche Sicherung, geplante Suche) "
                            f"laufen in diesem Prozess (Port {port}).")}
    if z["halter"] == ANDERER:
        intervall = z.get("pruefintervall_s")
        minuten = max(1, round(intervall / 60)) if intervall else None
        wann = (f" Schließt du es, übernimmt dieser Prozess innerhalb von etwa "
                f"{minuten} {'Minute' if minuten == 1 else 'Minuten'}."
                if minuten else "")
        return {"art": "info",
                "meldung": (f"Port {port} gehört einem anderen PBP-Fenster: dort laufen "
                            f"das Dashboard und der Planer (tägliche Sicherung, geplante "
                            f"Suche).{wann}")}
    if z["halter"] == FREMDES:
        intervall = z.get("pruefintervall_s")
        minuten = max(1, round(intervall / 60)) if intervall else None
        wann = (f" Dieser Prozess prüft alle {minuten} {'Minute' if minuten == 1 else 'Minuten'}, "
                f"ob der Port frei wird, und übernimmt dann." if minuten else "")
        return {"art": "warnung",
                "meldung": (f"Port {port} wird von einem anderen Programm benutzt "
                            f"(kein PBP{besitzer_zusatz(z.get('besitzer'))}). "
                            f"Deshalb laufen Dashboard und Planer (tägliche Sicherung, geplante "
                            f"Suche) nicht. Beende das Programm, das den Port belegt, oder starte "
                            f"den Rechner neu und öffne PBP zuerst.{wann}")}
    if z["halter"] == HAENGT:
        intervall = z.get("pruefintervall_s")
        minuten = max(1, round(intervall / 60)) if intervall else None
        wann = (f" Dieser Prozess prüft alle {minuten} {'Minute' if minuten == 1 else 'Minuten'}, "
                f"ob der Port frei wird, und übernimmt dann." if minuten else "")
        besitzer = z.get("besitzer")
        beenden = ""
        if isinstance(besitzer, dict) and besitzer.get("pid"):
            beenden = (f" Beenden lässt sich der Prozess so: {beenden_befehl(besitzer['pid'])}"
                       + (" (Claude Desktop verliert dann die Verbindung zu PBP, bis es neu gestartet wird)."
                          if besitzer.get("unter_claude") else "."))
        return {"art": "warnung",
                "meldung": (belegt_text(port, ANTWORT_KEINE, besitzer) + " Deshalb laufen Dashboard und Planer "
                            f"(tägliche Sicherung, geplante Suche) in diesem Prozess nicht.{wann}"),
                "loesung": ("Claude Desktop vollständig beenden und neu starten. Oder den hängenden Prozess "
                            "beenden und PBP über die Desktop-Verknüpfung öffnen." + beenden)}
    return {"art": "warnung",
            "meldung": ("Das Dashboard läuft in keinem Prozess"
                        + (f": {z['fehler']}" if z.get("fehler") else "")
                        + ". Die tägliche Sicherung und die geplante Suche laufen so nicht.")}
