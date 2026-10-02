"""Gegenprobe (Mutationstest) der Schutzmechanismen des Auto-Updates (#1093).

Jede Mutation macht EINE Schutzpruefung wirkungslos (Pruefsumme, Signatur, feste Quelle, sicheres Entpacken,
Manifest, Installationslauf, Startbaustein, Schema-Schutz, Stufen). Die Tests muessen dann rot werden. Wird eine
Mutation nicht erkannt ("UEBERLEBT"), schuetzt kein Test diese Pruefung: das ist eine Luecke in den Tests, es sei denn,
der Eingriff ist gleichwertig und steht begruendet in AEQUIVALENT.

Warum es das gibt: gruen im Repository ist kein Beweis, dass ein Schutz greift (DoD 8c). Beim ersten Lauf (v1.8.0)
ueberlebten 10 von 92 Mutationen; sieben davon waren echte Luecken, zum Beispiel wies der Schema-Schutz nur POST ab,
und die Automatik haette eine bewusst zurueckgenommene Version wieder installiert.

Aufruf (NICHT im Arbeitsordner, sondern in einem eigenen, sauberen Arbeitsbaum):

    git worktree add --detach C:/Temp/pbp_mutation HEAD
    python scripts/mutationstest_auto_update.py --arbeitsbaum C:/Temp/pbp_mutation [Kennung ...]

Nach jeder Mutation wird mit `git checkout -- .` zurueckgesetzt. Ein Lauf dauert einige Minuten. Beim Umbau der
geprueften Dateien koennen Muster nicht mehr passen ("MUSTER"): dann den Eintrag nachziehen, nicht loeschen.
Kein Teil der CI.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PY = sys.executable
WURZEL = Path(__file__).resolve().parent.parent

AU = "src/bewerbungs_assistent/services/auto_update/"
BOOT = "src/bewerbungs_assistent_boot/__init__.py"

#: Mutationen, die sich mit der heutigen Bibliothek nicht erreichen lassen. Jede traegt ihren Grund.
AEQUIVALENT = {
    "en14": "`zipfile` liefert nie mehr Daten als im Kopf angekuendigt und prueft die CRC; die Zeile gilt einer kuenftigen Bibliothek",
}

# (Kennung, Beschreibung, Datei, alt, neu, Tests)
T_PR = ["tests/test_v18_auto_update_pruefen_entpacken.py"]
T_Q = ["tests/test_v18_auto_update_quelle.py"]
T_I = ["tests/test_v18_auto_update_installation.py"]
T_B = ["tests/test_v18_auto_update_boot.py"]
T_L = ["tests/test_v18_auto_update_lauf.py", "tests/test_v18_auto_update_aufraeumen_zustand.py"]
T_S = ["tests/test_v18_auto_update_schnittstellen.py"]
T_E = ["tests/test_v18_auto_update_ed25519.py"]

# (id, Beschreibung, Datei, alt, neu, Tests)
M = [
    # ── Pruefsumme und Signatur ──
    ("pr01", "Pruefsumme des Archivs wird nicht verglichen", AU + "pruefung.py", "    if tatsaechlich != erwartet:", "    if False:", T_PR + T_I),
    ("pr02", "Signatur wird nie verlangt, auch mit Schluessel", AU + "pruefung.py", "    if not _schl.signatur_erforderlich(schluessel):", "    if True:", T_PR + T_I),
    ("pr03", "fehlende Signaturdatei wird hingenommen", AU + "pruefung.py", '        raise UpdateFehler("signatur", detail="keine Signaturdatei")', '        return ""', T_PR + T_I),
    ("pr04", "jede Signatur gilt als gueltig", AU + "pruefung.py", "        if ed25519.pruefen(oeffentlich, bytes(summen_bytes), daten):", "        if True:", T_PR + T_I),
    ("pr05", "Signatur falscher Laenge wird nicht abgewiesen", AU + "pruefung.py", '        raise UpdateFehler("signatur", detail=f"{len(daten)} statt 64 Byte")', "        pass", T_PR + T_E),
    ("pr06", "Dateiname mit Pfadanteil in der Summenliste erlaubt", AU + "pruefung.py", r'        if "/" in name or "\\" in name or name in (".", ".."):', "        if False:", T_PR),
    ("pr07", "widerspruechliche Summen derselben Datei erlaubt", AU + "pruefung.py", "        if name in ergebnis and ergebnis[name] != summe:", "        if False:", T_PR),
    ("pr08", "Pruefsumme wird im Ablauf uebersprungen", AU + "installation.py", "    pr = pruefung.archiv_pruefen(archiv, archiv_name, summen_bytes, signiert_von=signiert_von)", '    pr = pruefung.Pruefergebnis(sha256="", signiert=False, schluessel="")', T_I),
    ("pr09", "Signatur wird im Ablauf uebersprungen", AU + "installation.py", "    signiert_von = pruefung.signatur_pruefen(summen_bytes, signatur_text, schluessel=schluessel)", '    signiert_von = ""', T_I),
    ("pr10", "Signaturdatei wird im Ablauf nicht geladen", AU + "installation.py", "    if _schl.signatur_erforderlich(schluessel):", "    if False:", T_I),
    ("ed01", "Signatur: s >= Q wird nicht abgewiesen", AU + "ed25519.py", "        if s >= _Q:", "        if False:", T_E),
    # ── feste Quelle ──
    ("qu01", "Adresse: gar keine Pruefung", AU + "quelle.py", '    if teile.scheme != "https" or host not in erlaubte_hosts or teile.username or teile.password or port not in (None, 443):', "    if False:", T_Q + T_I),
    ("qu02", "Adresse: Host nicht geprueft", AU + "quelle.py", "host not in erlaubte_hosts or ", "", T_Q + T_I),
    ("qu03", "Adresse: http erlaubt", AU + "quelle.py", 'teile.scheme != "https" or ', "", T_Q + T_I),
    ("qu04", "Adresse: Zugangsdaten in der Adresse erlaubt", AU + "quelle.py", "teile.username or teile.password or ", "", T_Q),
    ("qu05", "Adresse: Fremdport erlaubt", AU + "quelle.py", " or port not in (None, 443)", "", T_Q),
    ("qu06", "Weiterleitung wird nicht geprueft", AU + "quelle.py", "        _url_pruefen(newurl, erlaubte_hosts=WEITERLEITUNG_HOSTS)", "        pass", T_Q + T_I),
    ("qu07", "asset_url: Vorabversion erlaubt", AU + "quelle.py", "    if not _fassung.ist_stabil(version):", "    if False:", T_Q),
    ("qu08", "asset_url: beliebiger Dateiname erlaubt", AU + "quelle.py", "    if name not in erlaubt:", "    if False:", T_Q),
    ("qu09", "json_holen: andere Adresse erlaubt", AU + "quelle.py", "    if url != API_FREIGABEN:", "    if False:", T_Q),
    ("qu10", "Freigaben: Vorabversionen (Flag) zugelassen", AU + "quelle.py", ' or eintrag.get("prerelease"):', ":", T_Q + T_L),
    ("qu11", "Freigaben: Entwuerfe zugelassen", AU + "quelle.py", 'eintrag.get("draft") or ', "", T_Q + T_L),
    ("qu12", "Freigaben: Beta-Tag ohne Flag zugelassen", AU + "quelle.py", "        if version is None or not _fassung.ist_stabil(version):", "        if version is None:", T_Q),
    ("qu13", "neueste_fuer_linie: andere Linie erlaubt", AU + "quelle.py", "                  if _fassung.linie(f.version) == linie and _fassung.ist_neuer(f.version, laufende_fassung)]", "                  if _fassung.ist_neuer(f.version, laufende_fassung)]", T_Q + T_L),
    ("qu14", "neueste_fuer_linie: aeltere Fassung erlaubt", AU + "quelle.py", "                  if _fassung.linie(f.version) == linie and _fassung.ist_neuer(f.version, laufende_fassung)]", "                  if _fassung.linie(f.version) == linie]", T_Q + T_L),
    ("qu15", "neueste_fuer_linie: nimmt die aelteste statt der neuesten", AU + "quelle.py", "    return max(kandidaten, key=lambda f: _fassung.schluessel(f.version))", "    return min(kandidaten, key=lambda f: _fassung.schluessel(f.version))", T_Q + T_L),
    ("qu16", "laden: angekuendigte Groesse nicht begrenzt", AU + "quelle.py", "            if laenge is not None and laenge > max_bytes:", "            if False:", T_Q),
    ("qu17", "laden: empfangene Groesse nicht begrenzt", AU + "quelle.py", "                    if geladen > max_bytes:", "                    if False:", T_Q),
    ("qu18", "laden: unvollstaendiger Empfang wird hingenommen", AU + "quelle.py", "        if laenge is not None and geladen != laenge:", "        if False:", T_Q),
    ("qu19", "laden: .part-Datei bleibt nach Abbruch liegen", AU + "quelle.py", "            if teil.exists():", "            if False:", T_Q + T_I),
    ("qu20", "laden: Adresse wird nicht geprueft", AU + "quelle.py", "    _url_pruefen(url, erlaubte_hosts=START_HOSTS)", "    pass", T_Q),
    # ── Entpacken ──
    ("en01", "Entpacken: Pfadmuster (.., absolut, Laufwerk) nicht geprueft", AU + "entpacken.py", r'    if not name or "\x00" in name or "\\" in name or name.startswith("/") or ":" in name:', "    if False:", T_PR),
    ("en02", "Entpacken: Pfadteile (.., Leerzeichen, Punkt am Ende) nicht geprueft", AU + "entpacken.py", r'        if teil in ("", ".", "..") or teil != teil.strip() or teil.endswith("."):', "        if False:", T_PR),
    ("en03", "Entpacken: Geraetenamen erlaubt", AU + "entpacken.py", "        if stamm in GERAETENAMEN:", "        if False:", T_PR),
    ("en04", "Entpacken: Gross-/Kleinschreibungs-Doppel erlaubt", AU + "entpacken.py", "            if schluessel in gesehen:", "            if False:", T_PR),
    ("en05", "Entpacken: Verknuepfungen erlaubt", AU + "entpacken.py", "            if _ist_verknuepfung(info):", "            if False:", T_PR),
    ("en06", "Entpacken: ausfuehrbare Dateien erlaubt", AU + "entpacken.py", "                if pfad.suffix.lower() in VERBOTENE_ENDUNGEN:", "                if False:", T_PR),
    ("en07", "Entpacken: fremde Dateien an der Wurzel erlaubt", AU + "entpacken.py", "                    if wurzel not in ERLAUBTE_WURZELDATEIEN:", "                    if False:", T_PR),
    ("en08", "Entpacken: fremde Ordner an der Wurzel erlaubt", AU + "entpacken.py", "                elif wurzel != ERLAUBTER_WURZELORDNER:", "                elif False:", T_PR),
    ("en09", "Entpacken: Einzeldatei beliebig gross", AU + "entpacken.py", "                if info.file_size > MAX_EINZEL_BYTES:", "                if False:", T_PR),
    ("en10", "Entpacken: Zip-Bombe (Verhaeltnis) nicht erkannt", AU + "entpacken.py", "                if info.file_size > 1024 * 1024 and info.compress_size and info.file_size / info.compress_size > MAX_VERHAELTNIS:", "                if False:", T_PR),
    ("en11", "Entpacken: Gesamtgroesse unbegrenzt", AU + "entpacken.py", "            if gesamt > MAX_GESAMT_BYTES:", "            if False:", T_PR),
    ("en12", "Entpacken: Dateianzahl unbegrenzt", AU + "entpacken.py", "        if len(eintraege) > MAX_DATEIEN:", "        if False:", T_PR),
    ("en13", "Entpacken: Archiv ohne manifest.json erlaubt", AU + "entpacken.py", '        if "manifest.json" not in namen:', "        if False:", T_PR),
    ("en14", "Entpacken: mehr Daten als angekuendigt erlaubt", AU + "entpacken.py", "                    if bytes_ > info.file_size or bytes_ > MAX_EINZEL_BYTES:", "                    if False:", T_PR),
    ("en15", "Entpacken: nicht leerer Zielordner erlaubt", AU + "entpacken.py", "    if ziel.exists() and any(ziel.iterdir()):", "    if False:", T_PR),
    ("en16", "Entpacken: zweite Schicht (Zielpfad ausserhalb)", AU + "entpacken.py", "            if ziel != ziel_pfad and ziel not in ziel_pfad.parents:", "            if False:", T_PR),
    # ── Manifest ──
    ("ma01", "Manifest: Format nicht geprueft", AU + "manifest.py", '    if roh.get("format") != MANIFEST_FORMAT:', "    if False:", T_PR + T_I),
    ("ma02", "Manifest: andere Version als angekuendigt erlaubt", AU + "manifest.py", "    if version != erwartete_version:", "    if False:", T_PR + T_I),
    ("ma03", "Manifest: Linie nicht zur Version geprueft", AU + "manifest.py", "    if linie != _fassung.linie(version):", "    if False:", T_PR + T_I),
    ("ma04", "Manifest: fremde Linie erlaubt", AU + "manifest.py", "    if _fassung.linie(laufende_fassung) != m.linie:", "    if False:", T_PR + T_I),
    ("ma05", "Manifest: nicht neuere Fassung erlaubt", AU + "manifest.py", "    if not _fassung.ist_neuer(m.version, laufende_fassung):", "    if False:", T_PR + T_I),
    ("ma06", "Manifest: auto_update_moeglich=false ignoriert", AU + "manifest.py", "    if not m.auto_update_moeglich:", "    if False:", T_PR + T_I),
    ("ma07", "Manifest: neueres Startbaustein-Format ignoriert", AU + "manifest.py", "    if m.boot_format > boot_format:", "    if False:", T_PR + T_I),
    ("ma08", "Manifest: Python-Bereich ignoriert", AU + "manifest.py", "    if not (m.python_min <= python[:len(m.python_min)] and python[:len(m.python_unter)] < m.python_unter):", "    if False:", T_PR + T_I),
    # ── Installationslauf ──
    ("in01", "Lauf: Linienwechsel erlaubt", AU + "installation.py", "    if _fassung.linie(version) != _fassung.linie(laufend):", "    if False:", T_I),
    ("in02", "Lauf: Zurueck-/Gleichstand erlaubt", AU + "installation.py", "    if not _fassung.ist_neuer(version, neuere):", "    if False:", T_I),
    ("in03", "Lauf: gescheiterte Fassung wird erneut versucht", AU + "installation.py", "    if version in zustand.gescheiterte_fassungen(app):", "    if False:", T_I),
    ("in04", "Lauf: Vorabversion erlaubt", AU + "installation.py", "    if not _fassung.ist_stabil(version):", "    if False:", T_I),
    ("in05", "Selbsttest: Urteil ignoriert", AU + "installation.py", '    if getattr(r, "returncode", 1) != 0 or letzte != "OK":', "    if False:", T_I),
    ("in06", "Selbsttest wird uebersprungen", AU + "installation.py", "    selbsttest_starten(entpackt, python=python, runner=selbsttest_runner)", "    pass", T_I),
    ("in07", "Arbeitsordner wird nach Abbruch nicht geleert", AU + "installation.py", "                aufraeumen.arbeit_leeren(app, eigene_sperre=True)\n        ergebnis.ok = True", "                pass\n        ergebnis.ok = True", T_I),
    ("in08", "Sperre: mehrere Updates zugleich", AU + "installation.py", "        with aufraeumen.sperre(app):", "        if True:", T_I + T_L),
    ("in09", "Platzpruefung entfaellt", AU + "installation.py", "    if frei < bedarf:", "    if False:", T_I),
    ("in10", "Rueckweg: unbestaetigte Fassung als Rueckweg", AU + "installation.py", "    if bestaetigt and bestaetigt != version and layout.fassung_gueltig(app, bestaetigt):", "    if False:", T_I),
    ("in11", "aktuell.txt wird nie umgeschaltet", AU + "installation.py", r'    layout.schreibe_atomar(layout.pfade(app).aktuell, version + "\n")', "    pass", T_I),
    # ── Aufraeumen ──
    ("au01", "Aufraeumen: geschuetzte Fassungen loeschbar", AU + "aufraeumen.py", "        if v in schutz or v in zu_behalten:", "        if v in zu_behalten:", T_L),
    ("au02", "Aufraeumen: Fassung in Benutzung loeschbar", AU + "aufraeumen.py", "        if belegungen(app, v):", "        if False:", T_L),
    ("au03", "Aufraeumen: loescht auch bei unklarer aktuell.txt", AU + "aufraeumen.py", "    if not aktuell or not layout.fassung_gueltig(app, aktuell):", "    if False:", T_L),
    ("au04", "Sperre: lebende Sperre wird uebergangen", AU + "aufraeumen.py", "            if versuch == 2 or not _sperre_verwaist(p):", "            if versuch == 2:", T_L + T_I),
    # ── Startbaustein ──
    ("bo01", "Boot: keine Rueckkehr nach zwei unbestaetigten Starts", BOOT, '        elif start.get("fehler") or bisher >= MAX_UNBESTAETIGT:', '        elif start.get("fehler"):', T_B),
    ("bo02", "Boot: Nachsicht entfaellt (junger Start zaehlt als gescheitert)", BOOT, '        frisch = _alter_s(start.get("zeit")) < NACHSICHT_S', "        frisch = False", T_B),
    ("bo03", "Boot: nach 'bereit' trotzdem Rueckfall", BOOT, "        if bestaetigt or _BEREIT or not rueckfall_erlaubt:", "        if bestaetigt or not rueckfall_erlaubt:", T_B),
    ("bo04", "Boot: bestaetigter Start kann zurueckfallen", BOOT, "        if bestaetigt or _BEREIT or not rueckfall_erlaubt:", "        if _BEREIT or not rueckfall_erlaubt:", T_B),
    ("bo05", "Boot: Rueckfall nicht auf einmal begrenzt", BOOT, "        if bestaetigt or _BEREIT or not rueckfall_erlaubt:", "        if bestaetigt or _BEREIT:", T_B),
    ("bo06", "Boot: Rueckfall auf ungueltige vorherige Fassung", BOOT, "    if vorherige and vorherige != von and fassung_gueltig(app, vorherige):", "    if vorherige and vorherige != von:", T_B),
    ("bo07", "Boot: Rueckfall auf eine NEUERE Fassung", BOOT, "        if kandidat != von and (schluessel_von is None or sortschluessel(kandidat) < schluessel_von):", "        if kandidat != von:", T_B),
    ("bo08", "Boot: Rueckfall schreibt aktuell.txt nicht", BOOT, r'    schreibe_atomar(Path(app) / AKTUELL, nach + "\n")', "    pass", T_B),
    ("bo09", "Boot: unvollstaendige aktuelle Fassung wird gestartet", BOOT, "    if aktuell and not fassung_gueltig(app, aktuell):", "    if False:", T_B),
    ("bo10", "Boot: Bestaetigung gilt fuer jede Fassung", BOOT, "    if start.get(\"version\") != fassung:\n        return False", "    if False:\n        return False", T_B),
    # ── Schema-Schutz ──
    ("sc01", "Schema-Schutz: erkennt nie eine zu neue Datenbank", "src/bewerbungs_assistent/services/schema_schutz.py", "    if n is not None and n > SCHEMA_VERSION:", "    if n is not None and n > SCHEMA_VERSION + 1000:", T_S),
    ("sc02", "Schema-Schutz: Werkzeuge nie abgewiesen", "src/bewerbungs_assistent/services/schema_schutz.py", "    if werkzeug in ERLAUBTE_WERKZEUGE:", "    if True:", T_S),
    ("sc03", "Schema-Schutz: Dashboard-Schreibzugriffe nie abgewiesen", "src/bewerbungs_assistent/services/schema_schutz.py", '            if pfad.startswith("/api/") and not pfad.startswith(ERLAUBTE_PRAEFIXE):', "            if False:", T_S),
    ("sc04", "Schema-Schutz: nur POST abgewiesen", "src/bewerbungs_assistent/services/schema_schutz.py", '        if scope["type"] == "http" and scope.get("method") in SCHREIBENDE_METHODEN:', '        if scope["type"] == "http" and scope.get("method") == "POST":', T_S),
    # ── Stufen und Zustimmung ──
    ("st01", "Stufe 'aus' installiert trotzdem automatisch", AU + "lauf.py", '    if p["status"] != "neu" or stufe not in zustand.AUTOMATISCHE_STUFEN:', '    if p["status"] != "neu":', T_L),
    ("st02", "Automatik ignoriert Sperre fuer fehlgeschlagene Fassungen", AU + "lauf.py", "    if blockiert(db, version):", "    if False:", T_L),
    ("st03", "Automatik ignoriert bewusst Zurueckgeschaltetes", AU + "lauf.py", "    if version in abgelehnt(db):", "    if False:", T_L),
    ("st04", "Automatik wartet nicht auf ruhige Zeit", AU + "lauf.py", "    if not frei:", "    if False:", T_L),
    ("st05", "Automatische Stufe ohne Zustimmung setzbar", "src/bewerbungs_assistent/tools/update.py", "                if stufe in zustand.AUTOMATISCHE_STUFEN and not bestaetigt:", "                if False:", T_S),
    ("st06", "Installation ohne Zustimmung ueber Claude", "src/bewerbungs_assistent/tools/update.py", "        if not bestaetigt:", "        if False:", T_S),
    # ── Versionsnummern ──
    ("fa01", "Versionsnummer: Zeilenende/Anhang erlaubt (match statt fullmatch)", AU + "fassung.py",
     '''def schluessel(fassung):
    """Vergleichswert; None, wenn es keine gueltige Fassung ist."""
    m = _FASSUNG.fullmatch(fassung) if isinstance(fassung, str) else None''',
     '''def schluessel(fassung):
    """Vergleichswert; None, wenn es keine gueltige Fassung ist."""
    m = _FASSUNG.match(fassung) if isinstance(fassung, str) else None''', T_Q + T_I),
    ("fa02", "Versionsnummer: Nicht-ASCII-Ziffern erlaubt", AU + "fassung.py",
     r'_FASSUNG = re.compile(r"([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,4})(?:-(alpha|beta|rc)\.([0-9]{1,3}))?", re.ASCII)',
     r'_FASSUNG = re.compile(r"(\d{1,3})\.(\d{1,3})\.(\d{1,4})(?:-(alpha|beta|rc)\.(\d{1,3}))?")', T_Q + T_I),
]



WT = None


def lauf(args, timeout=900):
    return subprocess.run(args, cwd=str(WT), capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "PYTHONPATH": str(WT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def pytest(tests):
    t0 = time.time()
    r = lauf([PY, "-m", "pytest", "-x", "-q", "--tb=no", "-p", "no:cacheprovider", "-W", "ignore", "-rf", *tests])
    ersten = [z for z in r.stdout.splitlines() if z.startswith("FAILED")][:1]
    return r.returncode, ersten, round(time.time() - t0, 1), (r.stdout[-300:] if r.returncode not in (0, 1) else "")


def zuruecksetzen():
    subprocess.run(["git", "checkout", "--", "."], cwd=str(WT), capture_output=True, text=True)


def main(argv=None) -> int:
    global WT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arbeitsbaum", required=True, help="ein eigener, sauberer git-Arbeitsbaum (nie der Arbeitsordner)")
    p.add_argument("--ergebnis", help="JSON-Datei fuer das Ergebnis (Vorgabe: neben dem Arbeitsbaum)")
    p.add_argument("kennungen", nargs="*", help="nur diese Mutationen")
    a = p.parse_args(argv)
    WT = Path(a.arbeitsbaum).resolve()
    if WT == WURZEL:
        print("Abbruch: das ist der Arbeitsordner dieses Skripts. Bitte einen eigenen Arbeitsbaum nehmen (git worktree add).")
        return 2
    if not (WT / ".git").exists():
        print("Abbruch: kein git-Arbeitsbaum.")
        return 2
    sauber = subprocess.run(["git", "status", "--porcelain"], cwd=str(WT), capture_output=True, text=True).stdout.strip()
    if sauber:
        print("Abbruch: der Arbeitsbaum ist nicht sauber (es wird mit `git checkout -- .` zurueckgesetzt, das wuerde Aenderungen verwerfen).")
        return 2
    ziel_json = Path(a.ergebnis) if a.ergebnis else WT.parent / (WT.name + "_mutationen.json")
    nur = set(a.kennungen)
    ergebnisse = {}
    if not nur:
        for name, tests in (("T_PR", T_PR), ("T_Q", T_Q), ("T_I", T_I), ("T_B", T_B), ("T_L", T_L), ("T_S", T_S), ("T_E", T_E)):
            code, fehl, sek, rest = pytest(tests)
            print(f"GRUNDLAUF {name}: {'gruen' if code == 0 else 'ROT'} ({sek}s) {fehl}", flush=True)
            if code != 0:
                print("Abbruch: der Grundlauf ist nicht gruen, ein roter Test sagt dann nichts.", rest)
                return 2
    for mid, text, datei, alt, neu, tests in M:
        if nur and mid not in nur:
            continue
        pfad = WT / datei
        original = pfad.read_bytes()
        s = original.decode("utf-8-sig")
        crlf = "\r\n" in s
        s_lf = s.replace("\r\n", "\n")
        if s_lf.count(alt) != 1:
            print(f"{mid}: MUSTER {s_lf.count(alt)}x gefunden (Eintrag nachziehen): {alt[:60]!r}", flush=True)
            ergebnisse[mid] = {"text": text, "urteil": "MUSTER", "n": s_lf.count(alt)}
            continue
        mutiert = s_lf.replace(alt, neu)
        if crlf:
            mutiert = mutiert.replace("\n", "\r\n")
        pfad.write_bytes((b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b"") + mutiert.encode("utf-8"))
        try:
            code, fehl, sek, rest = pytest(tests)
        finally:
            zuruecksetzen()
        urteil = "ERKANNT" if code == 1 else ("UEBERLEBT" if code == 0 else "FEHLERHAFT")
        ergebnisse[mid] = {"text": text, "urteil": urteil, "erster_roter_test": fehl[0][:200] if fehl else "", "sek": sek}
        print(f"{mid} [{urteil}] {text}  -> {fehl[0][7:120] if fehl else rest[:120]}  ({sek}s)", flush=True)
        ziel_json.write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1), encoding="utf-8")
    offen = [k for k, v in ergebnisse.items() if v["urteil"] != "ERKANNT" and k not in AEQUIVALENT]
    gleichwertig = [k for k, v in ergebnisse.items() if v["urteil"] != "ERKANNT" and k in AEQUIVALENT]
    print(f"\nFERTIG: {len(ergebnisse)} Mutationen, {len(ergebnisse) - len(offen) - len(gleichwertig)} erkannt, "
          f"gleichwertig begruendet: {gleichwertig}, OFFEN: {offen}", flush=True)
    return 1 if offen else 0


if __name__ == "__main__":
    sys.exit(main())
