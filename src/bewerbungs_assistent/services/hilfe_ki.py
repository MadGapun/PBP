"""Die KI-Schicht der interaktiven Hilfe (#1233, F51): die lokale KI formuliert eine Kurzantwort aus den gefundenen Abschnitten.

Die Karten (`hilfe_suche.antwort`) stehen sofort da und kommen nie aus einem Modell. Dieses Modul legt DARUEBER eine kurze,
zusammenhaengende Antwort, wenn die lokale KI laeuft und der Mensch es nicht abgeschaltet hat. Das Modell darf nur umformulieren,
was in den drei besten Abschnitten steht - und die Antwort wird geprueft, bevor sie angezeigt wird:

* Sie muss mindestens einen der drei Abschnitte zitieren (`[1]` bis `[3]`) und darf keinen anderen nennen.
* Adressen, Befehle in Backticks und Menuepfade (`A › B`) duerfen nur vorkommen, wenn sie in den Abschnitten stehen: ein 7B/8B-Modell
  erfindet sonst gern einen Knopf oder einen Befehl, der klingt, als gaebe es ihn (#771: das war der Grund gegen ein freies Chatfenster).
* "KEINE ANTWORT" heisst: die Karten genuegen.
* Wird die Antwort verworfen, bleibt die Karte - ohne Fehlermeldung, mit dem Grund im Ergebnis.

Datenschutz (Nutzerentscheidung 16.10.2026): Frage und Antwort werden NICHT gespeichert - nicht in der Datenbank, nicht im Protokoll.
Der Auftrag lebt im Arbeitsspeicher, traegt die Frage nicht (nur das Ergebnis) und verschwindet nach zehn Minuten. Die Frage geht an die
lokale KI auf diesem Rechner und sonst nirgends hin.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from typing import Any, Callable

from .hilfe_suche import umschrift

logger = logging.getLogger("bewerbungs_assistent.hilfe_ki")

SCHLUESSEL = "hilfe_ki_formulieren"
#: Ob die Kurzantwort ohne eigene Wahl des Menschen eingeschaltet ist. AUS: Nutzerentscheidung 16.10.2026 ("reicht die Messung nicht, bleibt die
#: KI-Antwort als Beta aus, und nur die Suche kommt mit 1.8.0"). Gemessen an ungesehenen Fragen findet die Suche den richtigen Abschnitt in
#: drei von vier Faellen unter den ersten drei; ein Modell, das aus einem falschen Abschnitt eine glatte Antwort baut, waere schlimmer als eine
#: Karte, die ihre Quelle nennt. Der Schalter steht unter Einstellungen > Lokale KI.
VORGABE_AN = False

MAX_ABSCHNITTE = 3
MAX_ABSCHNITT_ZEICHEN = 900
MAX_ANTWORT_ZEICHEN = 600
MAX_TOKENS = 260
JOB_LEBENSDAUER_SEK = 600
#: Hoechstens so viele Kurzantworten gleichzeitig offen (eine laeuft, eine wartet). Die lokale KI antwortet eine nach der anderen; wer in
#: kurzer Zeit viele Fragen stellt, bekommt zu den spaeteren nur die Karten, statt dass sich Auftraege stapeln, auf die niemand mehr wartet.
MAX_OFFENE_AUFTRAEGE = 2

ANWEISUNG = (
    "Du bist die Bedienungshilfe von PBP, einem Programm fuer Menschen auf Jobsuche. "
    "Beantworte die Frage NUR mit den Abschnitten unten. Regeln:\n"
    "- Antworte auf Deutsch (mit richtigen Umlauten), per Du, in hoechstens drei kurzen Saetzen.\n"
    "- Setze hinter jeden Satz in eckigen Klammern die Nummer des Abschnitts, aus dem er stammt, zum Beispiel [2].\n"
    "- Erfinde nichts: keine Knoepfe, Menues, Adressen oder Befehle, die nicht in den Abschnitten stehen.\n"
    "- Steht die Antwort nicht in den Abschnitten, antworte genau mit: KEINE ANTWORT"
)

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_ERZEUGUNG = threading.Lock()   # eine Antwort nach der anderen: die lokale KI hat nur einen Rechner


# ── Der Schalter und der Zustand ────────────────────────────────────────────────────────────

def einstellung(db: Any) -> bool:
    """Soll die lokale KI Kurzantworten formulieren? Eine eigene Wahl des Menschen gilt, sonst `VORGABE_AN`."""
    try:
        wert = db.get_profile_setting(SCHLUESSEL, None)
    except Exception:  # noqa: BLE001
        return VORGABE_AN
    if wert in (None, ""):
        return VORGABE_AN
    return wert in (True, 1, "1", "true", "True", "an", "ja")


def einstellung_setzen(db: Any, an: bool) -> dict:
    db.set_profile_setting(SCHLUESSEL, bool(an))
    return {"formulieren": einstellung(db)}


def zustand(db: Any) -> dict:
    """Kann die lokale KI jetzt antworten? {"aktiv": bool, "grund": str, "modell": str | None}. Fragt kein Netz ausser Ollama selbst."""
    try:
        from .llm_service import get_llm_service
        s = get_llm_service(db).get_status()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Zustand der lokalen KI nicht lesbar: %s", exc)
        return {"aktiv": False, "grund": "unbekannt", "modell": None}
    if not s.ollama_available:
        return {"aktiv": False, "grund": "ollama_nicht_erreichbar", "modell": None}
    if s.user_state != "active":
        return {"aktiv": False, "grund": "ki_" + str(s.user_state), "modell": None}
    if not s.selected_model:
        return {"aktiv": False, "grund": "kein_modell", "modell": None}
    return {"aktiv": True, "grund": "", "modell": s.selected_model}


# ── Prompt und Pruefung ─────────────────────────────────────────────────────────────────────

def abschnitte_fuer(antwort: dict, wissen: Any) -> list[dict]:
    """Die (hoechstens drei) vollen Abschnitte hinter den Karten einer Antwort."""
    liste = []
    for k in (antwort.get("karten") or [])[:MAX_ABSCHNITTE]:
        a = wissen.nach_id.get(k["id"])
        if a:
            liste.append(a)
    return liste


def prompt_bauen(frage: str, abschnitte: list[dict]) -> str:
    teile = [ANWEISUNG, "", f"FRAGE: {frage}", ""]
    for n, a in enumerate(abschnitte, 1):
        text = re.sub(r"\s+", " ", a["text"]).strip()[:MAX_ABSCHNITT_ZEICHEN]
        teile.append(f"ABSCHNITT [{n}] {a['titel']}: {text}")
    teile += ["", "ANTWORT:"]
    return "\n".join(teile)


def pruefen(text: str, abschnitte: list[dict]) -> dict:
    """Prueft die Antwort des Modells. {"ok": True, "text", "quellen": [Abschnitts-Kennungen]} oder {"ok": False, "grund"}."""
    t = (text or "").strip()
    if not t:
        return {"ok": False, "grund": "leer"}
    if "KEINE ANTWORT" in t.upper():
        return {"ok": False, "grund": "keine_antwort"}
    if len(t) > MAX_ANTWORT_ZEICHEN:
        return {"ok": False, "grund": "zu_lang"}
    zitate = [int(z) for z in re.findall(r"\[(\d{1,2})\]", t)]
    if not zitate:
        return {"ok": False, "grund": "ohne_quelle"}
    if any(z < 1 or z > len(abschnitte) for z in zitate):
        return {"ok": False, "grund": "fremde_quelle"}
    beleg = umschrift(" ".join(f"{a['titel']} {a['text']}" for a in abschnitte))
    ohne_zitate = re.sub(r"\[\d{1,2}\]", "", t)
    for adresse in re.findall(r"(?:https?://|www\.|pbp://)\S+", ohne_zitate, flags=re.IGNORECASE):
        if umschrift(adresse.rstrip(".,;:)”“\"'")) not in beleg:
            return {"ok": False, "grund": "erfundene_adresse"}
    for code in re.findall(r"`([^`\n]+)`", ohne_zitate):
        if umschrift(code.strip()) not in beleg:
            return {"ok": False, "grund": "erfundener_befehl"}
    if "›" in ohne_zitate:
        for stueck in re.findall(r"[^.;\n]*›[^.;\n]*", ohne_zitate):
            for teil in stueck.split("›"):
                bereinigt = umschrift(re.sub(r"[„“\"'()]", " ", teil)).strip()
                # Nur der Name eines Menuepunkts zaehlt, nicht der Satz davor: die letzten zwei Woerter reichen als Probe.
                woerter = bereinigt.split()
                if woerter and umschrift(" ".join(woerter[-2:])) not in beleg and umschrift(woerter[-1]) not in beleg:
                    return {"ok": False, "grund": "erfundener_pfad"}
    quellen: list[str] = []
    for z in zitate:
        kennung = abschnitte[z - 1]["id"]
        if kennung not in quellen:
            quellen.append(kennung)
    sauber = re.sub(r"\s*\[\d{1,2}\]", "", t)
    sauber = re.sub(r"\s+([.,;:!?])", r"\1", sauber).strip()
    return {"ok": True, "text": sauber, "quellen": quellen}


# ── Die Auftraege (nur im Arbeitsspeicher) ──────────────────────────────────────────────────

def aufraeumen(jetzt: float | None = None) -> int:
    jetzt = time.monotonic() if jetzt is None else jetzt
    with _LOCK:
        alt = [k for k, v in _JOBS.items() if jetzt - v["angelegt"] > JOB_LEBENSDAUER_SEK]
        for k in alt:
            del _JOBS[k]
    return len(alt)


def offene_auftraege() -> int:
    """Wie viele Kurzantworten gerade laufen oder warten."""
    aufraeumen()
    with _LOCK:
        return sum(1 for v in _JOBS.values() if v["status"] == "laeuft")


def lesen(job_id: str) -> dict:
    """Der Stand eines Auftrags. Unbekannt oder abgelaufen: {"status": "unbekannt"}."""
    aufraeumen()
    with _LOCK:
        job = _JOBS.get(str(job_id or ""))
        if not job:
            return {"status": "unbekannt"}
        return {k: v for k, v in job.items() if k != "angelegt"}


def _setzen(job_id: str, **felder: Any) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(felder)


def _erzeugen(db: Any, modell: str) -> Callable[[str], str]:
    from .llm_service import get_llm_service
    svc = get_llm_service(db)
    return lambda prompt: svc._ollama_generate(modell, prompt, max_tokens=MAX_TOKENS)


def starten(db: Any, frage: str, abschnitte: list[dict], modell: str, *,
            erzeuger: Callable[[str], str] | None = None, synchron: bool = False) -> str:
    """Startet die Formulierung im Hintergrund. Rueckgabe: die Kennung des Auftrags.

    `erzeuger(prompt) -> text` ist fuer Tests austauschbar; `synchron=True` wartet auf das Ende (Tests, nie im Dashboard).
    Der Auftrag merkt sich die Frage nicht - der Prompt lebt nur in diesem Aufruf.
    """
    aufraeumen()
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {"status": "laeuft", "text": "", "quellen": [], "grund": "", "angelegt": time.monotonic()}
    prompt = prompt_bauen(frage, abschnitte)
    erzeuge = erzeuger or _erzeugen(db, modell)

    def _lauf() -> None:
        try:
            with _ERZEUGUNG:
                roh = erzeuge(prompt)
            ergebnis = pruefen(roh, abschnitte)
            if ergebnis["ok"]:
                _setzen(job_id, status="fertig", text=ergebnis["text"], quellen=ergebnis["quellen"])
            else:
                _setzen(job_id, status="verworfen", grund=ergebnis["grund"])
        except Exception as exc:  # noqa: BLE001 - die Karten stehen trotzdem da
            grund = "kontext" if exc.__class__.__name__ == "KontextZuKlein" else "fehler"
            logger.warning("Kurzantwort der Hilfe nicht erzeugt (%s): %s", grund, exc.__class__.__name__)
            _setzen(job_id, status="fehler", grund=grund)

    if synchron:
        _lauf()
    else:
        threading.Thread(target=_lauf, daemon=True, name=f"pbp-hilfe-ki-{job_id[:6]}").start()
    return job_id


def anstossen(db: Any, antwort: dict, wissen: Any, *, mit_ki: bool, erzeuger=None, synchron: bool = False) -> dict:
    """Entscheidet, ob zu dieser Antwort eine Kurzantwort entsteht, und startet sie.

    Rueckgabe fuer die Oberflaeche: {"status": "aus", "grund"} oder {"status": "laeuft", "job"}. Nur zu einer SICHEREN Antwort
    wird formuliert: bei einem unsicheren Treffer waere eine glatte Antwort ueberzeugender, als die Lage es erlaubt.
    """
    if not mit_ki:
        return {"status": "aus", "grund": "nicht_angefragt"}
    if antwort.get("status") != "gefunden":
        return {"status": "aus", "grund": "keine_sichere_antwort"}
    if not einstellung(db):
        return {"status": "aus", "grund": "schalter_aus"}
    z = zustand(db)
    if not z["aktiv"]:
        return {"status": "aus", "grund": z["grund"]}
    abschnitte = abschnitte_fuer(antwort, wissen)
    if not abschnitte:
        return {"status": "aus", "grund": "keine_abschnitte"}
    if offene_auftraege() >= MAX_OFFENE_AUFTRAEGE:
        return {"status": "aus", "grund": "beschaeftigt"}
    job = starten(db, antwort["frage"], abschnitte, z["modell"], erzeuger=erzeuger, synchron=synchron)
    return {"status": "laeuft", "job": job}
