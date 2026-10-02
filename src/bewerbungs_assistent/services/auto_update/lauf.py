"""Der Hintergrund-Job: nachsehen, ob es ein Update gibt, und je nach Stufe installieren (#1093).

Wer ruft das auf?

* der **Zeitgeber** (`zeitgeber_starten`): erste Pruefung kurz nach dem Start, danach alle sechs
  Stunden. Er installiert nur in den Stufen `auto_meldung` und `auto_still` — und nur, wenn gerade
  nichts anderes arbeitet (Suchlauf, Extraktion, Lernlauf): das Herunterladen konkurriert sonst um
  Leitung und Platte;
* das **Dashboard** und die **Werkzeuge** (`pruefen`, `starte_installation`, `uebersicht`): der Knopf
  „Jetzt aktualisieren“ der Stufe `hinweis` und die Anzeige. Ein Klick des Menschen laeuft immer, auch
  wenn der Computer gerade arbeitet.

Die Installation selbst steht in `installation.py`; hier nur: wann, mit welchem Eintrag in
`background_jobs` (F35/#799 — nie synchron, sonst gibt es nicht einmal eine Spur) und was der Mensch
davon sieht. Ein Fehler bleibt pro Fassung gemerkt (`K_BLOCKIERT`): was an der Datei selbst liegt
(Pruefsumme, Signatur, unerlaubter Inhalt, Funktionstest, braucht den Installer), wird nicht noch
einmal automatisch versucht; was am Netz liegt, wird nach einer Stunde wieder versucht.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from . import aufraeumen, installation, layout, quelle, zustand
from . import fassung as _fassung
from . import schluessel as _schl
from .fehler import UpdateFehler

logger = logging.getLogger("bewerbungs_assistent.auto_update")

JOB_TYP = "auto_update"
START_VERZOEGERUNG_S = 90
#: So lange laeuft ein Start, bevor er als gelungen gilt: ein Absturz in den ersten Sekunden soll zum Rueckfall fuehren.
BESTAETIGUNG_NACH_S = 20
PRUEF_INTERVALL_S = 6 * 3600
MIN_ABSTAND_FRISCH_S = 15
#: Wie lange eine Antwort der Quelle gilt. Ein Fehlschlag gilt nur kurz (wie #1134): ein einziger Netzfehler beim
#: Start darf der Anzeige nicht zehn Minuten lang jede Auskunft nehmen.
ERFOLG_GILT_S = 600
FEHLSCHLAG_GILT_S = 100
WIEDERHOLUNG_NACH_NETZFEHLER_S = 3600

#: Fehler, die an der Datei selbst liegen: derselbe Versuch ginge gleich aus. Nicht von selbst wiederholen.
DAUERHAFTE_CODES = frozenset({
    "pruefsumme", "signatur", "archiv_unsicher", "manifest", "braucht_installer", "selbsttest", "gescheitert",
    "quelle_nicht_erlaubt",
})
#: Hintergrundarbeit, die ein automatisches Update NICHT aufhaelt.
LEICHTE_JOBS = frozenset({JOB_TYP, "sicherung"})

K_BLOCKIERT = "auto_update_blockiert"
K_ABGELEHNT = "auto_update_abgelehnt"
K_LETZTE_PRUEFUNG = "auto_update_letzte_pruefung"

_PRUEFUNG = {"zeit": 0.0, "gilt_s": ERFOLG_GILT_S, "ergebnis": None}
_JOB = {"id": None, "status": None, "phase": "", "anteil": 0.0, "text": "", "version": None, "ausloeser": ""}
_JOB_SPERRE = threading.Lock()


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


# ── Nachsehen ───────────────────────────────────────────────────────────────────────────

def auszug_aus_notizen(text: str, maximal: int = 3) -> list:
    """Zwei, drei Saetze aus den Release-Notizen fuer den Hinweis („neu starten“ braucht einen Grund)."""
    if not text:
        return []
    kopf = re.split(r"\n\s*---\s*\n|\n##\s*📦", text, maxsplit=1)[0]
    saetze = []
    for zeile in kopf.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith(("#", "|", "```", ">")):
            continue
        zeile = re.sub(r"^[-*]\s+", "", zeile)
        zeile = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", zeile)
        zeile = re.sub(r"[*_`]", "", zeile).strip()
        if len(zeile) < 12:
            continue
        saetze.append(zeile[:240])
        if len(saetze) >= maximal:
            break
    return saetze


def _bezugsfassung(app, laufende: str) -> str:
    """Die neueste Fassung, die schon da ist (laufend oder vorgemerkt): alles darunter ist kein Update."""
    vorgemerkt = layout.aktuelle_fassung(app) if app is not None else None
    if vorgemerkt and _fassung.ist_neuer(vorgemerkt, laufende):
        return vorgemerkt
    return laufende


def pruefen(db=None, *, oeffner=None, laufende=None, app=None, frisch: bool = False) -> dict:
    """Fragt die FESTE Quelle nach der neuesten stabilen Fassung der eigenen Linie.

    Antwort: `status` ist `neu`, `aktuell`, `unvollstaendig` (Freigabe da, Update-Dateien noch nicht),
    `keine_antwort` oder `nicht_verfuegbar`. Eine Antwort wird kurz behalten; „frisch“ umgeht das, aber
    nicht dichter als `MIN_ABSTAND_FRISCH_S` (GitHub erlaubt ohne Anmeldung 60 Anfragen je Stunde).
    """
    laufende = laufende or layout.laufende_fassung()
    app = app if app is not None else layout.programmordner()
    if not laufende:
        return {"status": "nicht_verfuegbar", "text": layout.verfuegbarkeit()[1] or "Keine laufende Fassung bekannt."}
    jetzt = time.monotonic()
    alter = jetzt - _PRUEFUNG["zeit"]
    if _PRUEFUNG["ergebnis"] is not None and (alter < MIN_ABSTAND_FRISCH_S or (not frisch and alter < _PRUEFUNG["gilt_s"])):
        if _PRUEFUNG["ergebnis"].get("laufende") == laufende:
            return _PRUEFUNG["ergebnis"]
    try:
        daten = quelle.json_holen(oeffner=oeffner, version_pbp=laufende)
    except UpdateFehler as fehler:
        erg = {"status": "keine_antwort", "text": fehler.text, "code": fehler.code}
        return _pruefung_merken(db, erg, laufende, jetzt, behalten=False)
    freigaben = quelle.freigaben_lesen(daten)
    bezug = _bezugsfassung(app, laufende)
    neu = quelle.neueste_fuer_linie(freigaben, bezug)
    if neu is None:
        erg = {"status": "aktuell", "text": "Du hast die neueste Version."}
    elif not quelle.vollstaendig(neu, _schl.signatur_erforderlich()):
        erg = {"status": "unvollstaendig", "version": neu.version, "titel": neu.titel,
               "text": f"Version {neu.version} ist erschienen. Das automatische Update dafür ist noch nicht bereit; "
                       "du kannst sie von Hand installieren."}
    else:
        erg = {"status": "neu", "version": neu.version, "titel": neu.titel, "veroeffentlicht": neu.veroeffentlicht,
               "auszug": auszug_aus_notizen(neu.notizen),
               "groesse": neu.dateien.get(quelle.ARCHIV_NAME.format(version=neu.version), 0),
               "text": f"Version {neu.version} ist verfügbar."}
    return _pruefung_merken(db, erg, laufende, jetzt, behalten=True)


def _pruefung_merken(db, erg: dict, laufende: str, monoton: float, *, behalten: bool) -> dict:
    erg = {**erg, "zeit": _jetzt().isoformat(timespec="seconds"), "laufende": laufende}
    _PRUEFUNG.update(zeit=monoton, gilt_s=ERFOLG_GILT_S if behalten else FEHLSCHLAG_GILT_S, ergebnis=erg)
    if db is not None:
        try:
            db.set_setting(K_LETZTE_PRUEFUNG, {k: v for k, v in erg.items() if k != "laufende"})
        except Exception:
            logger.debug("letzte Pruefung nicht gemerkt", exc_info=True)
    return erg


def letzte_pruefung(db) -> dict | None:
    wert = db.get_setting(K_LETZTE_PRUEFUNG, None) if db is not None else None
    return wert if isinstance(wert, dict) else None


# ── Sperre pro Fassung ──────────────────────────────────────────────────────────────────

def blockiert(db, version: str) -> dict | None:
    """Ist fuer diese Fassung ein Versuch gescheitert, der nicht von selbst wiederholt wird?"""
    b = db.get_setting(K_BLOCKIERT, None)
    if not isinstance(b, dict) or b.get("version") != version:
        return None
    bis = b.get("bis")
    if bis:
        try:
            if _jetzt() >= datetime.fromisoformat(bis):
                return None
        except ValueError:
            return None
    return b


def _blockade_merken(db, version: str, code: str, text: str) -> None:
    dauerhaft = code in DAUERHAFTE_CODES
    bis = None if dauerhaft else (_jetzt() + timedelta(seconds=WIEDERHOLUNG_NACH_NETZFEHLER_S)).isoformat(timespec="seconds")
    db.set_setting(K_BLOCKIERT, {"version": version, "code": code, "text": text, "dauerhaft": dauerhaft, "bis": bis,
                                 "zeit": _jetzt().isoformat(timespec="seconds")})


def blockade_loeschen(db) -> None:
    db.set_setting(K_BLOCKIERT, None)


def abgelehnt(db) -> list:
    """Fassungen, die der Mensch zurueckgenommen hat: der Automatismus schaltet nie wieder von selbst auf sie."""
    wert = db.get_setting(K_ABGELEHNT, [])
    return [v for v in wert if _fassung.gueltig(v)] if isinstance(wert, list) else []


def zurueckschalten(db, ziel: str, *, app=None) -> dict:
    """Beim naechsten Start soll eine aeltere, noch installierte Fassung laufen (Rueckweg auf Wunsch).

    Nichts wird beendet, nichts geloescht. Die Fassungen, die NEUER sind als `ziel`, merkt sich PBP als
    zurueckgenommen: weder der Zeitgeber noch ein spaeterer Lauf schaltet von selbst wieder auf sie.
    Wer sie doch will, installiert sie ausdruecklich (Knopf oder Werkzeug).
    """
    if app is None:
        ok, grund = layout.verfuegbarkeit()
        if not ok:
            return {"status": "nicht_verfuegbar", "text": grund}
        app = layout.programmordner()
    if not _fassung.gueltig(ziel) or not layout.fassung_gueltig(app, ziel):
        return {"status": "nicht_moeglich", "text": f"Version {ziel} ist nicht (mehr) installiert."}
    aktuell = layout.aktuelle_fassung(app)
    if ziel == aktuell:
        return {"status": "nichts_zu_tun", "text": f"Beim nächsten Start läuft ohnehin Version {ziel}."}
    neuere = [v for v in layout.installierte_fassungen(app) if _fassung.ist_neuer(v, ziel)]
    layout.schreibe_atomar(layout.pfade(app).aktuell, ziel + "\n")
    status = layout.lese_status(app)
    status.pop("vorherige", None)
    status.pop("rueckgang", None)
    layout.schreibe_status(app, status)
    db.set_setting(K_ABGELEHNT, sorted(set(abgelehnt(db)) | set(neuere), key=_fassung.schluessel))
    zustand.verlauf_anhaengen(db, version=ziel, ergebnis="zurueckgeschaltet", ausloeser="klick",
                              grund=f"Auf Wunsch zurück von {aktuell} auf {ziel}.")
    return {"status": "ok", "nach": ziel,
            "text": f"Beim nächsten Start läuft Version {ziel}. Starte PBP und Claude Desktop neu."}


# ── Ruhe ────────────────────────────────────────────────────────────────────────────────

def ruhig(db) -> tuple:
    """(True, "") wenn kein anderer Hintergrundjob laeuft, sonst (False, Art der Arbeit)."""
    try:
        job = db.get_running_background_job()
    except Exception:
        return True, ""
    if job and job.get("job_type") not in LEICHTE_JOBS:
        return False, str(job.get("job_type"))
    return True, ""


# ── Installieren im Hintergrund ─────────────────────────────────────────────────────────

def job_stand() -> dict:
    """Was der laufende (oder zuletzt beendete) Lauf meldet — fuer die Anzeige."""
    return dict(_JOB)


def starte_installation(db, version: str, *, ausloeser: str = "klick", oeffner=None, installieren=None, freigabe=None,
                        synchron: bool = False, **kw) -> dict:
    """Startet die Installation im Hintergrund (eigener Thread, Eintrag in `background_jobs`).

    `installieren` ist austauschbar (Tests). Gibt sofort zurueck: {status: gestartet|laeuft_bereits|nicht_verfuegbar, job_id}.
    """
    ok, grund = layout.verfuegbarkeit()
    if not ok and installieren is None and kw.get("app") is None:
        return {"status": "nicht_verfuegbar", "text": grund}
    if not _fassung.ist_stabil(version):
        return {"status": "abgelehnt", "text": "Vorabversionen werden nie automatisch installiert."}
    if not _JOB_SPERRE.acquire(blocking=False):
        return {"status": "laeuft_bereits", "text": "Ein Update läuft gerade."}
    try:
        job_id = db.create_background_job(JOB_TYP, {"version": version, "ausloeser": ausloeser})
    except Exception:
        _JOB_SPERRE.release()
        raise
    if ausloeser != "automatisch":
        try:
            blockade_loeschen(db)          # ein ausdruecklicher Klick darf es noch einmal versuchen
            rest = [v for v in abgelehnt(db) if v != version]
            db.set_setting(K_ABGELEHNT, rest)     # und eine zurueckgenommene Fassung ausdruecklich wieder wollen
        except Exception:
            pass
    _JOB.update(id=job_id, status="laeuft", phase="start", anteil=0.0, text="Update wird vorbereitet …",
                version=version, ausloeser=ausloeser)
    run = installieren or installation.installiere

    def fortschritt(phase, anteil, text):
        _JOB.update(phase=phase, anteil=anteil, text=text)
        try:
            db.update_background_job(job_id, "running", progress=int(anteil * 100), message=text)
        except Exception:
            logger.debug("Job-Fortschritt nicht gespeichert", exc_info=True)

    def _lauf():
        try:
            erg = run(version, db=db, oeffner=oeffner, fortschritt=fortschritt, ausloeser=ausloeser, freigabe=freigabe, **kw)
            if erg.ok:
                _JOB.update(status="fertig", phase="fertig", anteil=1.0, text=erg.text)
                db.update_background_job(job_id, "fertig", progress=100, message=erg.text,
                                         result={"version": version, "sha256": erg.sha256, "signiert": erg.signiert})
                _PRUEFUNG["ergebnis"] = None
            else:
                _JOB.update(status="fehler", phase="fehler", text=erg.text)
                db.update_background_job(job_id, "fehler", progress=100, message=erg.text, result={"code": erg.code})
                _blockade_merken(db, version, erg.code, erg.text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Auto-Update-Job abgestuerzt")
            _JOB.update(status="fehler", phase="fehler", text="Beim Update ist etwas Unerwartetes passiert.")
            try:
                db.update_background_job(job_id, "fehler", message=str(exc))
            except Exception:
                pass
        finally:
            _JOB_SPERRE.release()

    if synchron:
        _lauf()
    else:
        threading.Thread(target=_lauf, daemon=True, name=f"pbp-update-{job_id[:8]}").start()
    return {"status": "gestartet", "job_id": job_id}


# ── Der Zeitgeber ───────────────────────────────────────────────────────────────────────

def automatik_schritt(db, *, oeffner=None, **kw) -> dict:
    """Ein Durchgang: pruefen, und in den automatischen Stufen — wenn es ruhig ist — installieren."""
    ok, grund = layout.verfuegbarkeit()
    if not ok:
        return {"status": "nicht_verfuegbar", "text": grund}
    p = pruefen(db, oeffner=oeffner)
    stufe = zustand.stufe(db)
    if p["status"] != "neu" or stufe not in zustand.AUTOMATISCHE_STUFEN:
        return {"status": p["status"], "stufe": stufe, "installiert": False}
    version = p["version"]
    if blockiert(db, version):
        return {"status": "blockiert", "version": version, "installiert": False}
    if version in abgelehnt(db):
        return {"status": "zurueckgenommen", "version": version, "installiert": False}
    frei, art = ruhig(db)
    if not frei:
        return {"status": "wartet", "version": version, "grund": f"{art} läuft", "installiert": False}
    start = starte_installation(db, version, ausloeser="automatisch", oeffner=oeffner, **kw)
    return {**start, "version": version, "installiert": start["status"] == "gestartet"}


def zeitgeber_starten(db, *, warte=None, intervall: float = PRUEF_INTERVALL_S, verzoegerung: float = START_VERZOEGERUNG_S,
                      oeffner=None):
    """Startet den Zeitgeber-Thread (einmal je Prozess). Der Name beginnt bewusst NICHT mit „pbp-“:
    ein Dauerlaeufer darf das Aufraeumen der Tests nicht aufhalten (siehe tests/conftest.py)."""
    ok, _ = layout.verfuegbarkeit()
    if not ok:
        return None
    for t in threading.enumerate():
        if t.name == "autoupdate-zeitgeber" and t.is_alive():
            return t
    stop = threading.Event()
    warten = warte or stop.wait

    def _schleife():
        if warten(verzoegerung):
            return
        while not stop.is_set():
            try:
                aufraeumen.reste_entfernen(layout.programmordner())
                automatik_schritt(db, oeffner=oeffner)
            except Exception:  # noqa: BLE001 — der Zeitgeber darf nie sterben
                logger.warning("Auto-Update-Zeitgeber: Durchgang fehlgeschlagen", exc_info=True)
            if warten(intervall):
                return

    t = threading.Thread(target=_schleife, daemon=True, name="autoupdate-zeitgeber")
    t.stop_ereignis = stop  # type: ignore[attr-defined]
    t.start()
    return t


def beim_start(db, *, bestaetigung_nach: float = BESTAETIGUNG_NACH_S) -> dict:
    """Von Server und Dashboard beim Start gerufen: Reste wegraeumen, „bereit“ melden, Zeitgeber starten.

    Zwei Schritte, zwei Fragen an den Startbaustein:

    * **bereit** (sofort): mein Startcode ist durch. Eine Ausnahme DAVOR fuehrt zum Rueckfall auf die
      vorige Fassung, eine DANACH nicht mehr (Akzeptanzkriterium 5).
    * **bestaetigt** (nach `bestaetigung_nach` Sekunden): ich laufe noch. Ein Prozess, der vorher stirbt,
      zaehlt als nicht gelungener Start; zwei davon hintereinander schalten zurueck.
    """
    ergebnis = {"verfuegbar": False}
    ok, _ = layout.verfuegbarkeit()
    if not ok:
        return ergebnis
    app = layout.programmordner()
    try:
        aufraeumen.reste_entfernen(app)
        aufraeumen.arbeit_leeren(app)
        aufraeumen.fassungen_aufraeumen(app, zustand.vorgaenger_behalten(db))
    except Exception:  # noqa: BLE001 — Aufraeumen darf nie den Start verhindern
        logger.warning("Auto-Update: Aufraeumen beim Start fehlgeschlagen", exc_info=True)
    ergebnis["verfuegbar"] = True
    try:
        import bewerbungs_assistent_boot as _boot
        _boot.bereit_melden()
    except Exception:  # noqa: BLE001
        logger.debug("bereit_melden nicht moeglich", exc_info=True)
    if bestaetigung_nach <= 0:
        ergebnis["bestaetigt"] = zustand.start_bestaetigen()
    else:
        t = threading.Timer(bestaetigung_nach, zustand.start_bestaetigen)
        t.daemon = True
        t.name = "autoupdate-bestaetigung"
        t.start()
        ergebnis["bestaetigt"] = False
    zeitgeber_starten(db)
    return ergebnis


# ── Was die Oberflaeche und die Werkzeuge sehen ─────────────────────────────────────────

def uebersicht(db) -> dict:
    """Alles, was die Anzeige braucht — eine Antwort fuer Dashboard und Werkzeug."""
    ok, grund = layout.verfuegbarkeit()
    app = layout.programmordner()
    laufend = layout.laufende_fassung()
    stufe = zustand.stufe(db)
    antwort = {
        "verfuegbar": ok, "grund": grund, "laufend": laufend, "stufe": stufe, "stufen": list(zustand.STUFEN),
        "vorgaenger_behalten": zustand.vorgaenger_behalten(db), "installer_aufraeumen": zustand.installer_aufraeumen(db),
        "gefragt": zustand.gefragt(db), "verlauf": zustand.verlauf(db)[-10:][::-1],
        "signatur": {"erforderlich": _schl.signatur_erforderlich(), "schluessel": sorted(_schl.schluessel_bytes())},
        "pruefung": letzte_pruefung(db), "job": job_stand() if _JOB["id"] else None,
        "aktuell": None, "installiert": [], "neustart_noetig": False, "neu": None, "blockiert": None, "rueckgang": None,
    }
    if not ok or app is None:
        return antwort
    aktuell = layout.aktuelle_fassung(app)
    antwort["aktuell"] = aktuell
    antwort["installiert"] = layout.installierte_fassungen(app)
    antwort["neustart_noetig"] = bool(aktuell and laufend and aktuell != laufend)
    antwort["rueckgang"] = zustand.rueckgang_offen(app)
    p = antwort["pruefung"]
    if p and p.get("status") in ("neu", "unvollstaendig") and p.get("version") and _fassung.ist_neuer(p["version"], _bezugsfassung(app, laufend or "0.0.0")):
        antwort["neu"] = {**p, "frage_faellig": zustand.frage_faellig(db, p["version"]),
                          "zurueckgenommen": p["version"] in abgelehnt(db)}
        antwort["blockiert"] = blockiert(db, p["version"])
    return antwort
