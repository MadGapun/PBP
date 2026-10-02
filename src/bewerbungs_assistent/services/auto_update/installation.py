"""Der ganze Lauf: laden, pruefen, entpacken, testen, umschalten (#1093).

Reihenfolge, und warum:

    1  Vorbedingungen         nie Linienwechsel, nie zurueck, nie eine schon gescheiterte Fassung
    2  Sperre                 hoechstens ein Update zugleich
    3  Pruefsummenliste+Signatur  ZUERST und klein: eine ungueltige Signatur bricht ab, bevor 20 MB geladen sind
    4  Archiv laden, Summe    in `update/<name>.part`, erst bei vollstaendigem Empfang umbenannt
    5  Entpacken              nach `update/entpackt`, jede Datei selbst geschrieben (siehe `entpacken`)
    6  Manifest               passt die Fassung zu Linie, Python, Startbaustein?
    7  Pakete                 Fehlendes nach `entpackt/site`
    8  Selbsttest             die NEUE Fassung muss mit der Laufzeit dieses Rechners starten koennen
    9  Einsetzen              `entpackt` -> `versions/<fassung>.neu` -> `versions/<fassung>` -> Marke `.fertig`
    10 Umschalten             Statusdatei, dann `aktuell.txt` — atomar, ALS LETZTES

Bricht irgendein Schritt ab, ist `aktuell.txt` unberuehrt und der Arbeitsordner leer: PBP laeuft
wie vorher. Kein Prozess wird beendet, nichts startet neu (Akzeptanzkriterium 3); die Datenbank
wird nicht angefasst, ihre Migration geschieht wie bisher beim naechsten Start nach der
Sicherung durch `Database.initialize()`.

Alles Aeussere ist austauschbar (Netz, pip, Selbsttest), damit kein Test das Netz oder den
echten Programmordner braucht.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import abhaengigkeiten, aufraeumen, entpacken, layout, manifest as _manifest, pruefung, quelle, zustand
from . import fassung as _fassung
from . import schluessel as _schl
from .fehler import UpdateFehler

logger = logging.getLogger("bewerbungs_assistent.auto_update")

SELBSTTEST_TIMEOUT_S = 240
#: Mindestens so viel Platz auf dem Laufwerk, zusaetzlich zum Dreifachen des Archivs (laden, entpacken, einsetzen).
PLATZ_RESERVE = 150 * 1024 * 1024


@dataclass
class Ergebnis:
    ok: bool
    version: str
    code: str = ""
    text: str = ""
    sha256: str = ""
    signiert: bool = False
    schluessel: str = ""
    neustart_noetig: bool = False
    schon_vorhanden: bool = False
    aufgeraeumt: dict = field(default_factory=dict)


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _melden(fortschritt, phase: str, anteil: float, text: str) -> None:
    if fortschritt is not None:
        try:
            fortschritt(phase, max(0.0, min(1.0, anteil)), text)
        except Exception:  # eine kaputte Anzeige darf das Update nicht kippen
            logger.debug("Fortschrittsmeldung fehlgeschlagen", exc_info=True)


def _pruefen_abbruch(abbruch) -> None:
    if abbruch is not None and abbruch():
        raise UpdateFehler("abgebrochen")


def selbsttest_starten(ordner: Path, *, python=None, runner=None) -> None:
    """Die neue Fassung muss mit DIESER Laufzeit starten: `_selftest.py` importiert alles und liest/schreibt eine Wegwerf-Datenbank."""
    skript = Path(ordner) / "_selftest.py"
    if not skript.is_file():
        raise UpdateFehler("selbsttest", detail="_selftest.py fehlt im Update")
    umgebung = {k: v for k, v in os.environ.items() if k not in ("BA_DATA_DIR", "PBP_APP_DIR", "PBP_FASSUNG", "PYTHONPATH")}
    umgebung["PYTHONDONTWRITEBYTECODE"] = "1"
    run = runner or subprocess.run
    try:
        r = run([python or sys.executable, str(skript)], capture_output=True, text=True, timeout=SELBSTTEST_TIMEOUT_S,
                env=umgebung, cwd=str(ordner), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise UpdateFehler("selbsttest", detail="Zeitgrenze") from exc
    except Exception as exc:
        raise UpdateFehler("selbsttest", detail=f"{type(exc).__name__}: {exc}") from exc
    # Gezaehlt wird die letzte Zeile der STANDARDAUSGABE: das Protokoll der Datenbank geht auf die Fehlerausgabe und
    # steht sonst nach dem "OK" (so scheiterte die erste echte Probe an einem erfolgreichen Selbsttest).
    stdout = (getattr(r, "stdout", "") or "").strip()
    letzte = stdout.splitlines()[-1].strip() if stdout else ""
    if getattr(r, "returncode", 1) != 0 or letzte != "OK":
        ausgabe = (stdout + "\n" + (getattr(r, "stderr", "") or "")).strip()
        raise UpdateFehler("selbsttest", detail=ausgabe[-400:])


def _umbenennen(quelle_: Path, ziel: Path, versuche: int = 5) -> None:
    """`os.replace` fuer Ordner, mit Wiederholung: Virenscanner halten frisch entpackte Ordner kurz fest (Windows)."""
    for i in range(versuche):
        try:
            os.replace(quelle_, ziel)
            return
        except PermissionError as exc:
            if i == versuche - 1:
                raise UpdateFehler("unerwartet", detail=f"Umbenennen nicht moeglich: {exc}") from exc
            time.sleep(1.0)


def _platz_pruefen(app: Path, archiv_groesse: int) -> None:
    bedarf = 3 * min(archiv_groesse or quelle.MAX_ARCHIV_BYTES, quelle.MAX_ARCHIV_BYTES) + PLATZ_RESERVE
    frei = shutil.disk_usage(app).free
    if frei < bedarf:
        raise UpdateFehler("platz", detail=f"{frei // (1024 * 1024)} MB frei, gebraucht {bedarf // (1024 * 1024)} MB")


def _vorbedingungen(version: str, app: Path, laufend: str) -> str:
    """Gibt die aktuelle Fassung zurueck, wirft sonst. Nie Linienwechsel, nie zurueck, nie Gescheitertes."""
    if not _fassung.ist_stabil(version):
        raise UpdateFehler("quelle_nicht_erlaubt", "Vorabversionen werden nie automatisch installiert.",
                           detail=f"{version!r}")
    if _fassung.linie(version) != _fassung.linie(laufend):
        raise UpdateFehler("braucht_installer", "Ein Wechsel der Linie geschieht nie automatisch. Lade die neue "
                           "Version von der Release-Seite und starte INSTALLIEREN.bat.", detail=f"{laufend} -> {version}")
    aktuell = layout.aktuelle_fassung(app) or laufend
    neuere = aktuell if _fassung.ist_neuer(aktuell, laufend) else laufend
    if not _fassung.ist_neuer(version, neuere):
        raise UpdateFehler("schon_aktuell")
    if version in zustand.gescheiterte_fassungen(app):
        raise UpdateFehler("gescheitert", detail=f"{version} steht unter 'gescheitert'")
    return aktuell


def umschalten(app: Path, version: str, vorherige) -> None:
    """Statusdatei, dann `aktuell.txt` — das Letzte, was ein Update tut. Der naechste Start nimmt die neue Fassung.

    Rueckweg ist die zuletzt BESTAETIGT gelaufene Fassung, nicht einfach die bisherige `aktuell.txt`:
    eine Fassung, die installiert, aber nie gestartet wurde, ist kein verlaesslicher Rueckweg.
    """
    status = layout.lese_status(app)
    bestaetigt = status.get("bestaetigt")
    if bestaetigt and bestaetigt != version and layout.fassung_gueltig(app, bestaetigt):
        vorherige = bestaetigt
    if vorherige and vorherige != version:
        status["vorherige"] = vorherige
    status["letzte_installation"] = {"version": version, "zeit": _jetzt()}
    layout.schreibe_status(app, status)
    layout.schreibe_atomar(layout.pfade(app).aktuell, version + "\n")


def installiere(version: str, *, app=None, db=None, oeffner=None, fortschritt=None, abbruch=None,
                laufende_fassung=None, schluessel=None, python=None, pip_runner=None, selbsttest_runner=None,
                version_von=None, ausloeser: str = "automatisch", freigabe=None) -> Ergebnis:
    """Installiert `version` in einen neuen Fassungsordner und schaltet `aktuell.txt` um. Wirft nie: Fehler stehen im Ergebnis."""
    app = Path(app) if app is not None else layout.programmordner()
    ergebnis = Ergebnis(ok=False, version=version)
    try:
        if app is None:
            raise UpdateFehler("nicht_verfuegbar")
        laufend = laufende_fassung or layout.laufende_fassung()
        if not laufend:
            raise UpdateFehler("nicht_verfuegbar")
        aktuell = _vorbedingungen(version, app, laufend)
        pfade = layout.pfade(app)
        with aufraeumen.sperre(app):
            try:
                _lauf(version, app, pfade, aktuell, laufend, ergebnis, db, oeffner, fortschritt, abbruch, schluessel,
                      python, pip_runner, selbsttest_runner, version_von, freigabe)
            finally:
                aufraeumen.arbeit_leeren(app, eigene_sperre=True)
        ergebnis.ok = True
        ergebnis.neustart_noetig = True
        ergebnis.text = f"Version {version} ist installiert und gilt nach dem nächsten Neustart."
    except UpdateFehler as fehler:
        ergebnis.ok = False
        ergebnis.code, ergebnis.text = fehler.code, fehler.text
        logger.warning("Auto-Update %s abgebrochen: %s", version, fehler)
    except Exception as exc:  # nie nach oben: der Aufrufer ist ein Hintergrund-Thread
        ergebnis.ok = False
        ergebnis.code, ergebnis.text = "unerwartet", "Beim Update ist etwas Unerwartetes passiert. Es wurde nichts verändert."
        logger.exception("Auto-Update %s: unerwarteter Fehler", version)
    _verlauf(db, ergebnis, ausloeser)
    if ergebnis.ok and app is not None and db is not None:
        try:
            ergebnis.aufgeraeumt = aufraeumen.fassungen_aufraeumen(app, zustand.vorgaenger_behalten(db))
        except Exception:
            logger.warning("Aufraeumen nach dem Update fehlgeschlagen", exc_info=True)
    return ergebnis


def _verlauf(db, e: Ergebnis, ausloeser: str) -> None:
    if db is None:
        return
    try:
        zustand.verlauf_anhaengen(
            db, version=e.version, ergebnis="installiert" if e.ok else "fehler", code=e.code, grund=e.text,
            quelle="github", sha256=e.sha256, signiert=e.signiert, schluessel=e.schluessel, ausloeser=ausloeser)
    except Exception:
        logger.warning("Verlauf konnte nicht geschrieben werden", exc_info=True)


def _lauf(version, app, pfade, aktuell, laufend, ergebnis, db, oeffner, fortschritt, abbruch, schluessel, python,
          pip_runner, selbsttest_runner, version_von, freigabe) -> None:
    ziel = pfade.fassung(version)
    if (ziel / layout.FERTIG).is_file():
        # Schon installiert, nur nicht umgeschaltet (Strom weg zwischen Schritt 9 und 10): jetzt umschalten.
        _melden(fortschritt, "umschalten", 0.97, "Die Version ist schon geladen, wird jetzt vorgemerkt …")
        umschalten(app, version, aktuell)
        ergebnis.schon_vorhanden = True
        _melden(fortschritt, "fertig", 1.0, f"Version {version} ist installiert.")
        return

    aufraeumen.arbeit_leeren(app, eigene_sperre=True)
    pfade.arbeit.mkdir(parents=True, exist_ok=True)
    groesse = (freigabe.dateien.get(quelle.ARCHIV_NAME.format(version=version), 0) if freigabe is not None else 0)
    _platz_pruefen(app, groesse)
    archiv_name = quelle.ARCHIV_NAME.format(version=version)

    # 3. Pruefsummenliste und Signatur
    _melden(fortschritt, "pruefen", 0.02, "Prüfsummen holen …")
    summen_pfad = pfade.arbeit / quelle.SUMMEN_NAME
    quelle.laden(quelle.asset_url(version, quelle.SUMMEN_NAME), summen_pfad, max_bytes=quelle.MAX_SUMMEN_BYTES,
                 oeffner=oeffner, abbruch=abbruch)
    summen_bytes = summen_pfad.read_bytes()
    signatur_text = None
    if _schl.signatur_erforderlich(schluessel):
        sig_pfad = pfade.arbeit / quelle.SIGNATUR_NAME
        quelle.laden(quelle.asset_url(version, quelle.SIGNATUR_NAME), sig_pfad, max_bytes=quelle.MAX_SIGNATUR_BYTES,
                     oeffner=oeffner, abbruch=abbruch)
        signatur_text = sig_pfad.read_text(encoding="ascii", errors="replace")
    signiert_von = pruefung.signatur_pruefen(summen_bytes, signatur_text, schluessel=schluessel)
    ergebnis.signiert, ergebnis.schluessel = bool(signiert_von), signiert_von
    _pruefen_abbruch(abbruch)

    # 4. Archiv
    archiv = pfade.arbeit / archiv_name

    def _geladen(bytes_, gesamt):
        anteil = (bytes_ / gesamt) if gesamt else 0.5
        _melden(fortschritt, "laden", 0.05 + 0.65 * anteil, f"Lade {archiv_name} … {bytes_ // (1024 * 1024)} MB")

    _melden(fortschritt, "laden", 0.05, f"Lade {archiv_name} …")
    quelle.laden(quelle.asset_url(version, archiv_name), archiv, max_bytes=quelle.MAX_ARCHIV_BYTES, oeffner=oeffner,
                 fortschritt=_geladen, abbruch=abbruch)
    pr = pruefung.archiv_pruefen(archiv, archiv_name, summen_bytes, signiert_von=signiert_von)
    ergebnis.sha256 = pr.sha256
    _pruefen_abbruch(abbruch)

    # 5. Entpacken
    _melden(fortschritt, "entpacken", 0.72, "Entpacke …")
    entpackt = pfade.arbeit / "entpackt"
    entpacken.entpacken(archiv, entpackt)
    archiv.unlink(missing_ok=True)  # das Archiv wird nicht mehr gebraucht: sofort frei (Akzeptanzkriterium 12)
    _pruefen_abbruch(abbruch)

    # 6. Manifest
    m = _manifest.lesen(entpackt / "manifest.json", erwartete_version=version)
    _manifest.fuer_diesen_rechner_pruefen(m, laufende_fassung=laufend)

    # 7. Pakete
    fehlend = abhaengigkeiten.fehlende(m.requirements, m.requirements_optional, version_von=version_von)
    if fehlend:
        _melden(fortschritt, "pakete", 0.78, f"Richte {len(fehlend)} zusätzliche(s) Paket(e) ein …")
        abhaengigkeiten.bereitstellen(fehlend, entpackt / "site", python=python, runner=pip_runner)
    _pruefen_abbruch(abbruch)

    # 8. Selbsttest
    _melden(fortschritt, "test", 0.88, "Teste die neue Version …")
    selbsttest_starten(entpackt, python=python, runner=selbsttest_runner)
    _pruefen_abbruch(abbruch)

    # 9. Einsetzen
    _melden(fortschritt, "umschalten", 0.96, "Setze die neue Version ein …")
    pfade.versionen.mkdir(parents=True, exist_ok=True)
    neu = pfade.versionen / f"{version}.neu"
    aufraeumen.ordner_loeschen(neu)
    if ziel.exists():  # ein unfertiger Rest ohne Marke
        aufraeumen.ordner_loeschen(ziel)
    _umbenennen(entpackt, neu)
    _umbenennen(neu, ziel)
    (ziel / layout.FERTIG).write_text(json.dumps({"version": version, "sha256": ergebnis.sha256, "zeit": _jetzt()}),
                                     encoding="utf-8")

    # 10. Umschalten — als Letztes
    umschalten(app, version, aktuell)
    _melden(fortschritt, "fertig", 1.0, f"Version {version} ist installiert und gilt nach dem nächsten Neustart.")
