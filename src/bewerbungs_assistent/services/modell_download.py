"""Modell-Download in Ollama als Hintergrund-Job mit Fortschritt (#1154 Punkt 1).

Bis v1.7.149 wartete `POST /api/llm/pull` in einem einzigen Aufruf auf das Ende des Downloads
(`stream: false`, Zeitgrenze 600 s). Zwei Folgen:

* Die Oberfläche zeigte nur „Laedt…“ — keinen Stand, keine Größe, kein Ende in Sicht.
* Bei einem großen Modell oder einer langsamen Leitung brach die Anfrage nach zehn Minuten ab,
  und die Oberfläche meldete „Download fehlgeschlagen“, obwohl Ollama weiterlud.

Jetzt startet der Aufruf einen Hintergrund-Job (`background_jobs`, Art `modell_download`) und
antwortet sofort mit dessen Kennung. Der Job liest Ollamas Stream (`stream: true`, eine JSON-Zeile
je Schritt mit `total` und `completed` je Datei-Teil), rechnet daraus Prozent und einen Satz auf
Deutsch aus und schreibt beides in den Job; die Oberfläche fragt ihn ab. Es gibt keine Gesamt-
Zeitgrenze mehr, nur noch eine Stillstandsgrenze: kommt `STILLSTAND_S` Sekunden lang keine Zeile,
gilt der Download als hängend.

Alles, was die Außenwelt berührt (das Öffnen der Verbindung), lässt sich hereinreichen.
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger("bewerbungs_assistent.modell_download")

#: Art des Hintergrund-Jobs in der Tabelle `background_jobs`.
JOB_TYP = "modell_download"

#: So lange darf Ollama keine Zeile schicken, bevor der Download als hängend gilt (Sekunden).
STILLSTAND_S = 180.0

#: Frühestens so oft wird der Stand in die Datenbank geschrieben (Sekunden), außer bei einer neuen Prozentzahl.
SCHREIB_ABSTAND_S = 0.7

_GB = 1024 ** 3

_sperre = threading.Lock()
_threads: list = []


class Fortschritt:
    """Rechnet aus Ollamas Zeilen eine Prozentzahl und einen Satz auf Deutsch aus."""

    def __init__(self):
        self.teile: dict = {}      # digest -> [total, completed]
        self.prozent = 0
        self.text = "Starte den Download ..."

    def zeile(self, daten: dict) -> None:
        status = str(daten.get("status") or "")
        digest = daten.get("digest")
        total, fertig = daten.get("total"), daten.get("completed")
        if digest and isinstance(total, (int, float)) and total > 0:
            self.teile[digest] = [float(total), float(fertig or 0)]
        gesamt = sum(t for t, _ in self.teile.values())
        geladen = sum(min(c, t) for t, c in self.teile.values())
        if gesamt > 0:
            # Nie rückwärts, und 100 erst bei „success“: danach folgen noch Prüfen und Schreiben.
            self.prozent = max(self.prozent, min(99, int(100 * geladen / gesamt)))
        if status == "success":
            self.prozent, self.text = 100, "Fertig."
        elif status.startswith("pulling manifest"):
            self.text = "Hole die Liste der Teile ..."
        elif status.startswith("verifying"):
            self.text = "Prüfe die geladenen Daten ..."
        elif status.startswith("writing manifest"):
            self.text = "Schreibe das Modell ..."
        elif status.startswith("removing"):
            self.text = "Räume auf ..."
        elif gesamt > 0:
            self.text = f"Lade {geladen / _GB:.1f} von {gesamt / _GB:.1f} GB ({self.prozent} %)"
        elif status:
            self.text = status


def _fehlertext(exc: BaseException, stillstand_s: float) -> str:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return (f"Seit {int(stillstand_s)} Sekunden kamen keine Daten mehr von Ollama; der Download steht. "
                "Prüfe die Internetverbindung und starte ihn noch einmal (bereits geladene Teile bleiben erhalten).")
    if isinstance(exc, urllib.error.HTTPError):
        return f"Ollama hat den Download abgelehnt (Antwort {exc.code})."
    if isinstance(exc, (urllib.error.URLError, ConnectionRefusedError)):
        return "Ollama ist nicht erreichbar. Läuft es? Starte es und versuche es noch einmal."
    if isinstance(exc, ConnectionError):
        return "Die Verbindung zu Ollama ist abgebrochen. Läuft es noch? Versuche es noch einmal."
    return f"Der Download ist abgebrochen: {str(exc)[:160]}"


def _ollama_fehler(text: str) -> str:
    text = str(text).strip()
    if "file does not exist" in text or "not found" in text.lower():
        return f"Ollama kennt dieses Modell unter diesem Namen nicht ({text[:120]}). Prüfe den Namen."
    return f"Ollama meldet: {text[:200]}"


def lauf(db, job_id: str, endpoint: str, modell: str, nach_erfolg=None,
         stillstand_s: float | None = None, oeffnen=None) -> None:
    """Der Hintergrund-Thread: liest Ollamas Stream und schreibt den Stand in den Job.

    `oeffnen` ist `urllib.request.urlopen`, wird aber erst HIER nachgeschlagen (nicht als
    Vorgabewert gebunden), damit ein Test, der `urlopen` ersetzt, wirklich greift und nie
    ein Ollama auf dem Rechner des Entwicklers anspricht."""
    stillstand_s = STILLSTAND_S if stillstand_s is None else stillstand_s
    oeffnen = oeffnen or urllib.request.urlopen
    f = Fortschritt()
    letzter = {"zeit": 0.0, "prozent": -1, "text": ""}
    ergebnis = {"model": modell}

    def schreiben() -> None:
        """Eine neue Prozentzahl wird sofort geschrieben; wechselt nur der Text (die GB-Zahl),
        höchstens alle `SCHREIB_ABSTAND_S` Sekunden — die Datenbank ist keine Anzeigetafel."""
        jetzt = time.monotonic()
        if f.prozent == letzter["prozent"] and (f.text == letzter["text"]
                                                  or jetzt - letzter["zeit"] < SCHREIB_ABSTAND_S):
            return
        letzter.update(zeit=jetzt, prozent=f.prozent, text=f.text)
        db.update_background_job(job_id, "running", progress=f.prozent, message=f.text)

    try:
        req = urllib.request.Request(
            f"{endpoint}/api/pull",
            data=json.dumps({"name": modell, "stream": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        erfolg = False
        with oeffnen(req, timeout=stillstand_s) as antwort:
            for roh in antwort:
                roh = roh.strip()
                if not roh:
                    continue
                try:
                    daten = json.loads(roh.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if not isinstance(daten, dict):
                    continue
                if daten.get("error"):
                    ergebnis["error"] = _ollama_fehler(daten["error"])
                    db.update_background_job(job_id, "fehler", progress=f.prozent, message=ergebnis["error"],
                                             result=ergebnis)
                    return
                f.zeile(daten)
                if daten.get("status") == "success":
                    erfolg = True
                    break
                schreiben()
        if not erfolg:
            ergebnis["error"] = "Ollama hat den Download beendet, ohne Erfolg zu melden. Versuche es noch einmal."
            db.update_background_job(job_id, "fehler", progress=f.prozent, message=ergebnis["error"], result=ergebnis)
            return
        db.update_background_job(job_id, "fertig", progress=100, message="Fertig.", result=ergebnis)
        if nach_erfolg is not None:
            try:
                nach_erfolg()
            except Exception as exc:  # noqa: BLE001 — der Download selbst ist gelungen
                logger.debug("Nach dem Download: %s", exc)
    except Exception as exc:  # noqa: BLE001 — jeder Fehler muss im Job landen, nicht im Thread verpuffen
        logger.warning("Modell-Download %s fehlgeschlagen: %s", modell, exc)
        ergebnis["error"] = _fehlertext(exc, stillstand_s)
        try:
            db.update_background_job(job_id, "fehler", progress=f.prozent, message=ergebnis["error"], result=ergebnis)
        except Exception:  # noqa: BLE001
            logger.exception("Job %s liess sich nicht als fehlgeschlagen markieren", job_id)


def starten(db, endpoint: str, modell: str, nach_erfolg=None, stillstand_s: float | None = None,
            oeffnen=None) -> dict:
    """Startet den Download im Hintergrund; antwortet sofort mit der Kennung des Jobs.

    Läuft schon ein Download, wird kein zweiter gestartet: die Antwort nennt den laufenden Job.
    """
    with _sperre:
        laufend = db.get_running_background_job(JOB_TYP)
        if laufend:
            name = (laufend.get("params") or {}).get("model")
            return {"job_id": laufend["id"], "model": name, "status": "laeuft_schon",
                    "gleiches_modell": name == modell}
        job_id = db.create_background_job(JOB_TYP, {"model": modell})
        thread = threading.Thread(
            target=lauf, args=(db, job_id, endpoint, modell, nach_erfolg, stillstand_s, oeffnen),
            name="modell-download", daemon=True)
        _threads.append(thread)
        thread.start()
    return {"job_id": job_id, "model": modell, "status": "gestartet"}


def job_beschreiben(job: dict | None) -> dict | None:
    """Der Job in der Form, die die Oberfläche braucht."""
    if not job:
        return None
    ergebnis = job.get("result") or {}
    return {
        "job_id": job.get("id"),
        "model": (job.get("params") or {}).get("model"),
        "status": job.get("status"),
        "progress": int(job.get("progress") or 0),
        "message": job.get("message") or "",
        "error": ergebnis.get("error") if isinstance(ergebnis, dict) else None,
    }


def warten(timeout: float = 30.0) -> None:
    """Wartet auf alle gestarteten Downloads (für Tests: vor dem Schließen der Datenbank)."""
    ende = time.monotonic() + timeout
    while _threads and time.monotonic() < ende:
        t = _threads[0]
        t.join(max(0.0, ende - time.monotonic()))
        if t.is_alive():
            break
        _threads.pop(0)
