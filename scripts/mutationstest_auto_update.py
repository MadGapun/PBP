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
    python scripts/mutationstest_auto_update.py --arbeitsbaum C:/Temp/pbp_mutation [--katalog speicher] [Kennung ...]

Sieben Kataloge: `auto_update` (Pruefsumme, Signatur, Quelle, Entpacken, Startbaustein, Schema-Schutz, Stufen; #1093),
`speicher` (Loeschen nur unter der Wurzel, zwei Schritte, nie bei laufender Arbeit, Fremdes nur zeigen; #1131),
`komponenten` (kein Installer ohne Pruefsumme; #1152), `mail` (Mail-Ordner: Vorgabe aus, genaue Liste; #947) und
`firmen` (Firmen-Stammsatz: nie raten, nie verschmelzen, der Kanon fuegt nur hinzu; #1080) und
`wege` (Wege durch PBP: jeder Sprung, jede Verknuepfung, die Sprungleiste; #1171 — baut das Bundle bei Frontend-Eintraegen neu) und
`suche` (ein Klick auf einen Treffer der Suche oeffnet das Objekt: Adressen, Zuordnung, Lesestellen der Seiten; #1177).

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

#: Diese Mutationen lassen sich nur mit Symlink-Recht pruefen (Linux, macOS, Windows im Entwicklermodus). Ohne das Recht
#: laufen die zugehoerigen Tests ueber eine Junction, und die Mutation bleibt unbemerkt, ohne dass etwas fehlt.
BRAUCHT_SYMLINKS = {"sp06", "sp14"}

# (Kennung, Beschreibung, Datei, alt, neu, Tests)
T_PR = ["tests/test_v18_auto_update_pruefen_entpacken.py"]
T_Q = ["tests/test_v18_auto_update_quelle.py"]
T_I = ["tests/test_v18_auto_update_installation.py"]
T_B = ["tests/test_v18_auto_update_boot.py"]
T_L = ["tests/test_v18_auto_update_lauf.py", "tests/test_v18_auto_update_aufraeumen_zustand.py"]
T_S = ["tests/test_v18_auto_update_schnittstellen.py"]
T_E = ["tests/test_v18_auto_update_ed25519.py"]
T_SA = ["tests/test_v18_auto_update_schluessel_ausgeliefert.py"]
T_SAB = ["tests/test_v18_auto_update_schluessel_ablage.py"]

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
    ("pr11", "Ausgelieferte Schluessel: die Liste der vertrauten Schluessel ist leer", AU + "schluessel.py", "VERTRAUTE_SCHLUESSEL: dict = {\n", "VERTRAUTE_SCHLUESSEL: dict = {}\n_UNBENUTZT: dict = {\n", T_SA),
    ("sa01", "Archivbauer: der Schluessel am festen Ort wird nicht gesucht", "scripts/build_update_archive.py", "or os.environ.get(SCHLUESSEL_ENV) or standard_schluessel()", "or os.environ.get(SCHLUESSEL_ENV)", T_SAB),
    ("sa02", "Archivbauer: ohne Schluessel entsteht trotzdem ein Archiv", "scripts/build_update_archive.py", "    if not schluessel_datei and schluessel.signatur_erforderlich() and not ohne_signatur:", "    if False:", T_SAB),
    ("sa03", "Release-Tor: das Probe-Archiv wird nie signiert", "release_check.py", "    signieren = bool(erforderlich and haupt and not im_ci)", "    signieren = False", T_SAB),
    ("sa04", "Release-Tor: ein fehlender Schluessel ist nur eine Warnung", "release_check.py", "        (error if fassung.ist_stabil(version) else warn)(meldung)", "        warn(meldung)", T_SAB),
    ("sa05", "Release-Tor: die fehlende Sicherung wird nicht angemahnt", "release_check.py", "    if stand[\"sicherung_vollstaendig\"]:", "    if True:", T_SAB),
    ("sa06", "Sichern ueberschreibt einen anderen Schluessel", "scripts/update_schluessel.py", "        if kopie.exists() and kopie.read_bytes().strip() != quelle.read_bytes().strip():", "        if False:", T_SAB),
    ("sa07", "Sichern in ein Git-Arbeitsverzeichnis", "scripts/update_schluessel.py", "    if _im_git_arbeitsbaum(ziel):", "    if False:", T_SAB),
    ("sa08", "Tests sehen den echten Schluesselordner", "tests/conftest.py", "    monkeypatch.setenv(\"PBP_SIGNATUR_ORDNER\", str(basis / \"kein-signatur-ordner\"))", "    pass", T_SAB),
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




# ── Zweiter Katalog: Speicher & Downloads (#1131) ──
SP = "src/bewerbungs_assistent/services/speicher.py"
T_SP = ["tests/test_v18_speicher_1131.py"]
# #1173 (eigene Ordner auf der Speicher-Seite)
DO = "src/bewerbungs_assistent/services/datenordner.py"
AB = "src/bewerbungs_assistent/services/ablage.py"
DA = "src/bewerbungs_assistent/dashboard.py"
SPS = "frontend/src/pages/SettingsPage.jsx"
T_EO = ["tests/test_v18_speicher_eigene_ordner_1173.py"]
T_DO = ["tests/test_1097_datenordner.py"]

M_SPEICHER = [
    ("sp01", "Sicherungen: die neueste steht zur Auswahl", SP, "                  for e in alle[1:]]", "                  for e in alle]", T_SP),
    ("sp02", "Sicherungen: die neueste laesst sich entfernen", "src/bewerbungs_assistent/services/sicherung.py",
     "        if name == neueste:", "        if False:", T_SP),
    ("sp03", "Sicherungen: unbekannte Namen werden nicht abgewiesen", "src/bewerbungs_assistent/services/sicherung.py",
     "        if name not in bekannt:", "        if False:", T_SP),
    ("sp04", "Loeschen: Wurzelpruefung entfaellt", SP, "    if echt == w or not echt.is_relative_to(w) or pfad.is_symlink():", "    if False:", T_SP),
    ("sp05", "Loeschen: die Wurzel selbst ist loeschbar", SP, "    if echt == w or not echt.is_relative_to(w) or pfad.is_symlink():",
     "    if not echt.is_relative_to(w) or pfad.is_symlink():", T_SP),
    ("sp06", "Loeschen: Verknuepfungen werden verfolgt", SP, "    if echt == w or not echt.is_relative_to(w) or pfad.is_symlink():",
     "    if echt == w or not echt.is_relative_to(w):", T_SP),
    ("sp07", "Bereinigen laeuft trotz Hintergrundarbeit", SP, "    if laufend:\n        return f\"Gerade läuft", "    if False:\n        return f\"Gerade läuft", T_SP),
    ("sp08", "Bestaetigung wird nicht verlangt (Vorschau loescht)", SP, "    if not bestaetigt:\n        if not kandidaten:", "    if False:\n        if not kandidaten:", T_SP),
    ("sp09", "Bestaetigung ohne Auswahl loescht trotzdem", SP,
     '    if a["braucht_auswahl"] and not auswahl:\n        return {**basis, "status": "fehler"', '    if False:\n        return {**basis, "status": "fehler"', T_SP),
    ("sp10", "Downloads: jedes ZIP namens PBP-* gilt als Installationspaket", SP,
     '            return any(n == "INSTALLIEREN.bat" or n.endswith("/INSTALLIEREN.bat") for n in zf.namelist()[:5000])', "            return True", T_SP),
    ("sp11", "Downloads: der Name wird nicht geprueft", SP, '                if not (n.startswith("pbp-") and n.endswith(".zip")):', "                if False:", T_SP),
    ("sp12", "Ordner oeffnen: beliebiger Ort aus der Anfrage", SP, "    if ort_id not in ORT_IDS:", "    if False:", T_SP),
    ("sp13", "Fremdes: Playwright bekommt eine Aufraeum-Aktion", SP,
     'und wird auch von anderen Programmen benutzt; PBP löscht ihn nie."),\n            "aktionen": [], "eintraege": []}',
     'und wird auch von anderen Programmen benutzt; PBP löscht ihn nie."),\n            "aktionen": ["export"], "eintraege": []}', T_SP),
    ("sp14", "Messen: symbolische Links werden verfolgt", SP,
     '                        if eintrag.is_symlink() or getattr(eintrag, "is_junction", lambda: False)():',
     '                        if getattr(eintrag, "is_junction", lambda: False)():', T_SP),
    ("sp24", "Messen: Junctions werden verfolgt", SP,
     '                        if eintrag.is_symlink() or getattr(eintrag, "is_junction", lambda: False)():',
     "                        if eintrag.is_symlink():", T_SP),
    ("sp15", "Messen: keine Frist", SP, "                    if zaehler > MAX_EINTRAEGE_MESSUNG or time.monotonic() > ende:", "                    if False:", T_SP),
    ("sp16", "Update laeuft: Versions-Aktionen nicht gesperrt", SP, '    if aktion in ("alte_fassungen", "update_arbeitsordner") and _update_laeuft():', "    if False:", T_SP),
    ("sp17", "Komponenteninstallation laeuft: Reste nicht gesperrt", SP, "            if components._installation_laeuft(db):", "            if False:", T_SP),
    ("sp18", "Protokolle: das offene wird mitgeloescht", SP, "        if not f.is_file() or os.path.normcase(str(f.resolve())) in offen:",
     "        if not f.is_file():", T_SP),
    ("sp19", "Werkzeug: der eigene Aufruf zaehlt auch fuer das Dashboard nicht", SP,
     "    laufend = [n for n in datenordner.laufende_arbeit() if not (als_werkzeug and n == EIGENER_AUFRUF)]",
     "    laufend = [n for n in datenordner.laufende_arbeit() if not (n == EIGENER_AUFRUF)]", T_SP),
    ("sp20", "Versionen: die Vorschau loescht wirklich", "src/bewerbungs_assistent/services/auto_update/aufraeumen.py",
     "        if nur_vorschau:\n            bericht[\"geloescht\"].append(v)", "        if False:\n            bericht[\"geloescht\"].append(v)", T_SP),
    ("sp21", "Update-Reste: die Vorschau loescht wirklich", "src/bewerbungs_assistent/services/auto_update/aufraeumen.py",
     "        if (rest or unfertig) and (nur_vorschau or ordner_loeschen(kind)):", "        if (rest or unfertig) and ordner_loeschen(kind):", T_SP),
    ("sp22", "Ordner oeffnen: fehlender Ordner wird nicht erkannt", SP, '    if not ort.get("pfad") or not pfad.exists():', "    if False:", T_SP),
    ("sp23", "Fremdes zaehlt zur eigenen Summe", SP, '"gesamt_bytes": sum(o["bytes"] for o in orte if o["urheber"] != "fremd"),',
     '"gesamt_bytes": sum(o["bytes"] for o in orte),', T_SP),
    # ── #1173: der eigene Ordner (Lebenslaeufe, Anschreiben, Berichte) laesst sich auf der Speicher-Seite aendern ──
    ("sp25", "Eigene Ordner: gelesen wird ohne Profil (die Liste bleibt leer)", DO,
     "ablage.ordner_lesen(db, art) if db else None", '(db.get_setting(ablage._schluessel(art), "") or None) if db else None', T_EO + T_DO),
    ("sp26", "Eigene Ordner: die Karte nennt den Ausgabe-Ordner nicht (kein Pfad, kein Oeffnen)", SP,
     '            ort["pfad"] = befund["ordner"]', '            ort["pfad"] = ""', T_EO),
    ("sp27", "Eigene Ordner: ohne Wahl fehlt der Hinweis auf den Datenordner", SP, "        elif befund:\n", "        elif False:\n", T_EO),
    ("sp28", "Eigene Ordner: ein verschwundener Ordner wird nicht benannt", SP,
     '        elif befund and befund["befund"] == "ausweich":', "        elif False:", T_EO),
    ("sp29", "Eigene Ordner: Vorlagen-Ordner fehlt in der Liste", DO,
     '(("ausgabe", "Ablageordner"), ("vorlagen", "Vorlagenordner"))', '(("ausgabe", "Ablageordner"),)', T_EO + T_DO),
    ("sp30", "Zuruecksetzen: „-“ wird als Pfad geprueft und abgewiesen", AB, '    if str(pfad or "").strip() == "-":', "    if False:", T_EO),
    ("sp31", "REST: der Grund der Abweisung kommt nicht als `error` (am Feld steht „HTTP 400“)", DA,
     '        return JSONResponse({**ergebnis, "error": ergebnis.get("hinweis") or "Der Pfad wurde nicht gespeichert."}, status_code=400)',
     "        return JSONResponse(ergebnis, status_code=400)", T_EO),
    ("sp32", "Oberflaeche: der Grund des Servers wird nicht gelesen", SPS,
     "const text = String(err?.payload?.hinweis || err?.message || err);", "const text = String(err?.message || err);", T_EO),
    ("sp33", "Oberflaeche: leer wird als Platzhalter „-“ geschickt", SPS, "{ art, pfad: pfad.trim() }", '{ art, pfad: pfad.trim() || "-" }', T_EO),
    ("sp34", "Oberflaeche: nach dem Speichern misst die Speicher-Seite nicht neu", SPS, "      onGespeichert?.();\n", "", T_EO),
    ("sp35", "Speicher-Seite: der Editor steht an jeder Karte", "frontend/src/components/SpeicherTab.jsx",
     '{ort.id === "eigene" && ordnerEditor ?', "{ordnerEditor ?", T_EO),
    ("sp36", "Eingebettet: die Zeile mit dem Ort steht doppelt", SPS,
     '{(!eingebettet || stand.ausgabe_befund === "ausweich") && (', "{true && (", T_EO),
    ("sp37", "Eingebettet: der Hinweis zum verschwundenen Ordner steht doppelt", SPS,
     '{stand.ausgabe_befund === "ausweich" && !eingebettet && (', '{stand.ausgabe_befund === "ausweich" && (', T_EO),
]

# ── Dritter Katalog: Pruefsumme der Komponenten (#1152) ──
KP = "src/bewerbungs_assistent/services/components.py"
T_KP = ["tests/test_v18_komponenten_pruefsumme_1152.py", "tests/test_v18_komponenten_aufraeumen_1130.py"]

M_KOMPONENTEN = [
    ("kp01", "_sha256_ok: ohne Sollwert gilt die Pruefung als bestanden", KP, "        return False\n    import hashlib", "        return True\n    import hashlib", T_KP),
    ("kp02", "install_component: ohne Summe wird trotzdem geladen", KP, '    if not _pruefsumme_gueltig(dl.get("sha256", "")):', "    if False:", T_KP),
    ("kp03", "_pruefsumme_gueltig: jeder nichtleere Text genuegt", KP,
     '    return isinstance(wert, str) and re.fullmatch(r"[0-9a-fA-F]{64}", wert) is not None', "    return isinstance(wert, str) and len(wert) > 0", T_KP),
    ("kp04", "install_component: die Summe des Downloads wird nicht verglichen", KP, '        if not _sha256_ok(setup_path, dl.get("sha256", "")):', "        if False:", T_KP),
    ("kp05", "Registry: Tesseract ohne Pruefsumme", KP, '"sha256": "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9",', '"sha256": "",', T_KP),
    ("kp06", "_sha256_ok: Gross-/Kleinschreibung zaehlt", KP, "    return h.hexdigest().lower() == expected.lower()", "    return h.hexdigest() == expected", T_KP),
]

# ── Vierter Katalog: Mail-Ordner als Quelle (#947) ──
MQ = "src/bewerbungs_assistent/services/mail_quelle.py"
DASH = "src/bewerbungs_assistent/dashboard.py"
T_MQ = ["tests/test_v18_mail_quelle_947.py"]
_GLEICH = '_schluessel(f["anbieter"], f["konto"], f["ordner"]) == gesucht'

M_MAIL = [
    ("mq01", "Vorgabe: der Ordner-Scan ist an", MQ, '    return {"format": FORMAT, "scan_aktiv": False,', '    return {"format": FORMAT, "scan_aktiv": True,', T_MQ),
    ("mq02", "Scan aus: Mails kommen trotzdem herein", MQ, '    if not z["scan_aktiv"]:\n        return _nein("scan_aus"', '    if False:\n        return _nein("scan_aus"', T_MQ),
    ("mq03", "Leere Liste: es wird trotzdem gelesen", MQ, '    if not z["freigaben"]:\n        return _nein("whitelist_leer"', '    if False:\n        return _nein("whitelist_leer"', T_MQ),
    ("mq04", "Unterordner gelten als freigegeben", MQ, '        if ' + _GLEICH + ':',
     '        if (_schluessel(f["anbieter"], f["konto"], f["ordner"])[0] == gesucht[0] and gesucht[2].startswith(_schluessel(f["anbieter"], f["konto"], f["ordner"])[2])):', T_MQ),
    ("mq05", "Das Konto wird nicht verglichen", MQ, '        if ' + _GLEICH + ':',
     '        if (_schluessel(f["anbieter"], f["konto"], f["ordner"])[0], _schluessel(f["anbieter"], f["konto"], f["ordner"])[2]) == (gesucht[0], gesucht[2]):', T_MQ),
    ("mq06", "Der Anbieter wird nicht verglichen", MQ, '        if ' + _GLEICH + ':',
     '        if (_schluessel(f["anbieter"], f["konto"], f["ordner"])[1], _schluessel(f["anbieter"], f["konto"], f["ordner"])[2]) == (gesucht[1], gesucht[2]):', T_MQ),
    ("mq07", "Der Posteingang braucht keine Bestaetigung", MQ, '    if inbox and not posteingang_bestaetigt:', '    if False:', T_MQ),
    ("mq08", "Platzhalter und Steuerzeichen erlaubt", MQ, '    if _UNERLAUBT.search(roh) or _UNERLAUBT.search(konto):', '    if False:', T_MQ),
    ("mq09", "Einschalten ohne Bestaetigung", MQ, '    if not bestaetigt:\n        return {"status": "bestaetigung_noetig"', '    if False:\n        return {"status": "bestaetigung_noetig"', T_MQ),
    ("mq10", "Beta-Einstellung gilt in stabil still weiter", MQ,
     '    return bool(zustand.get("scan_aktiv") and zustand.get("aktiviert_in")\n                and _vorabversion(zustand["aktiviert_in"]) and not _vorabversion(_version()))',
     '    return False', T_MQ),
    ("mq11", "Unlesbare Einstellung ohne Hinweis", MQ, '        return {**_leer(), "unlesbar": True}', '        return {**_leer(), "unlesbar": False}', T_MQ),
    ("mq12", "Die Richtlinie nennt Ordner auch bei ausgeschaltetem Scan", MQ,
     '"ordner": f["ordner"]} for f in z["freigaben"]] if ok else []', '"ordner": f["ordner"]} for f in z["freigaben"]] if True else []', T_MQ),
    ("mq13", "Ausschalten schaltet nicht aus", MQ, '        z.update(scan_aktiv=False)', '        z.update(scan_aktiv=True)', T_MQ),
    ("mq14", "Dieselbe Freigabe doppelt moeglich", MQ,
     '        if any(_schluessel(f["anbieter"], f["konto"], f["ordner"]) == _schluessel(anbieter, konto, norm) for f in z["freigaben"]):',
     '        if False:', T_MQ),
    ("mq15", "Eingang prueft den Scan-Modus nicht", DASH, '    if modus == "scan":\n        from .services import mail_quelle\n        urteil', '    if False:\n        from .services import mail_quelle\n        urteil', T_MQ),
    ("mq16", "Unbekannter Modus wird hingenommen", DASH, '    if modus not in ("push", "scan"):', '    if False:', T_MQ),
    ("mq17", "Die Zahlen je Ordner werden nicht gefuehrt", DASH, '        mail_quelle.lauf_verbuchen(_db, freigabe_id, mails=1, stellen=int(neu))', '        pass', T_MQ),
    ("mq18", "Abschalten verschweigt die importierten Daten", MQ, '    return {"status": "aus", "importiert": {"mails": mails, "stellen": stellen}, "text": (', '    return {"status": "aus", "importiert": {"mails": 0, "stellen": 0}, "text": (', T_MQ),
    ("mq19", "Zuruecksetzen laesst die Liste stehen", MQ, '        _speichern(db, _leer())\n    return {"status": "zurueckgesetzt"', '        pass\n    return {"status": "zurueckgesetzt"', T_MQ),
    ("mq20", "Freigabe zurueckzunehmen wirkt nicht", MQ, '        z["freigaben"] = rest\n        _speichern(db, z)\n    return {"status": "entfernt"', '        pass\n    return {"status": "entfernt"', T_MQ),
]

# ── Fuenfter Katalog: Firmen-Stammsatz und seine Wirkung auf die Erkennung (#1080) ──
DD = "src/bewerbungs_assistent/duplicate_detection.py"
FS = "src/bewerbungs_assistent/services/firmen_stamm.py"
FB = "src/bewerbungs_assistent/services/firmen_bezuege.py"
FT = "src/bewerbungs_assistent/tools/firmen_stamm.py"
BEW = "src/bewerbungs_assistent/tools/bewerbungen.py"
JOBS = "src/bewerbungs_assistent/tools/jobs.py"
KON = "src/bewerbungs_assistent/tools/kontakte.py"
FA = "src/bewerbungs_assistent/services/firmen_ansicht.py"
DBF = "src/bewerbungs_assistent/database.py"
SDU = "src/bewerbungs_assistent/services/stellen_dublette.py"
AUS = "src/bewerbungs_assistent/services/aussortieren.py"
HIN = "src/bewerbungs_assistent/services/bewerbungs_hinweis.py"
AUT = "src/bewerbungs_assistent/services/stellen_automatik.py"
ELW = "src/bewerbungs_assistent/services/elwosa_provider.py"
T_FI = ["tests/test_v18_firmen_dubletten_1080.py", "tests/test_v18_firmen_stamm_1080.py", "tests/test_v18_firmen_kontakte_1080.py",
        "tests/test_v18_firmen_ansicht_1080.py"]

M_FIRMEN = [
    # ── Der Kanon: nur nachschlagen, nie raten ──
    ("fk01", "Kanon: mehrere passende Firmen im Namen - es wird eine geraten", FS, '            fid = next(iter(treffer)) if len(treffer) == 1 else ""', '            fid = next(iter(treffer)) if treffer else ""', T_FI),
    ("fk02", "Kanon: eine Schreibweise gilt auch als Teil eines Wortes", FS, '    return f" {form} " in f" {text} "', '    return form in text', T_FI),
    ("fk03", "Kanon: auch ein Kuerzel steckt in einem laengeren Namen", FS, "    MIN_TEILNAME = 4\n\n    def __init__(self, firmen: dict):", "    MIN_TEILNAME = 1\n\n    def __init__(self, firmen: dict):", T_FI),
    ("fk04", "Kanon: eine Form, die zwei Firmen gehoert, ordnet eine zu", FS, "        for f in doppelt:\n            self._firma_je_form.pop(f, None)", "        for f in doppelt:\n            pass", T_FI),
    ("fk05", "Kanon: gilt immer fuer das aktive Profil", FS, "        pid = _pid(db) if profile_id is None else profile_id", "        pid = _pid(db)", T_FI),
    ("fk06", "Kanon: Schreibweisen werden nicht normalisiert", FS, '                firmen[a["company_id"]].append(_norm(a["alias"]))', '                firmen[a["company_id"]].append(a["alias"])', T_FI),
    ("fk07", "Kanon: ein Lesefehler stoppt die Erkennung", FS, '        logger.debug("Firmen-Stammsatz für den Abgleich nicht lesbar (#1080): %s", exc)\n        return None', '        raise', T_FI),
    ("fk08", "Kanon: formen_von nennt auch mehrdeutige Formen", FS, "        return [f for f in self._formen_je_firma.get(fid, ()) if f in self._firma_je_form] if fid else []", "        return list(self._formen_je_firma.get(fid, ())) if fid else []", T_FI),
    ("fk09", "Kanon: zwei unbekannte Namen sind dieselbe Firma", FS, "        return bool(fa) and fa == self.firma_von(b)", "        return fa == self.firma_von(b)", T_FI),
    # ── Die Erkennung nimmt den Kanon ──
    ("fm01", "find_duplicate_job: der Kanon wird nicht gefragt", DD, "        if not firma_match and _gleiche_firma(norm_firma, cand_firma, kanon):", "        if False:", T_FI),
    ("fm02", "_gleiche_firma: nie dieselbe Firma", DD, "    return bool(kanon is not None and a and b and kanon.gleich(a, b))", "    return False", T_FI),
    ("fm03", "find_duplicate_job: der Treffer sagt nicht, dass er aus dem Kanon kommt", DD,
     '                "hours_ago": round(hours_ago, 1) if hours_ago is not None else None,\n                **({"firma_via": "stammsatz"} if via_stamm else {}),', '                "hours_ago": round(hours_ago, 1) if hours_ago is not None else None,', T_FI),
    ("fm04", "Wiederholung: der Kanon wird nicht weitergegeben", DD, '            job.get("company") or "", job.get("title") or "", "", kandidaten,\n            kanon=kanon)', '            job.get("company") or "", job.get("title") or "", "", kandidaten)', T_FI),
    ("fm05", "Wiederholung: ohne Kanon wird nichts aus der Datenbank gebaut", DD, "    if kanon is None and db is not None:\n        kanon = firmen_kanon(db)\n    hit = _url_treffer", "    if False:\n        kanon = firmen_kanon(db)\n    hit = _url_treffer", T_FI),
    ("fm06", "Wiederholung: die Warnung sagt nicht, warum zwei Namen zusammengehoeren", DD, "    if via_stamm:\n        # Der Leser sieht zwei verschiedene Namen", "    if False:\n        # Der Leser sieht zwei verschiedene Namen", T_FI),
    ("fm07", "Wiederholung: das Ergebnis traegt kein firma_via", DD, '        **({"firma_via": "stammsatz"} if via_stamm else {}),\n        "kurz": kurz,', '        "kurz": kurz,', T_FI),
    ("fm08", "Textvergleich: der Kanon wird nicht gefragt", DD, "                   or _gleiche_firma(norm, cf, kanon)):", "                   ):", T_FI),
    ("fm09", "Textvergleich: ein bestaetigtes Kuerzel ist zu kurz", DD, "    if not norm or (len(norm) < 4 and not _gleiche_firma(norm, norm, kanon)):", "    if not norm or len(norm) < 4:", T_FI),
    ("fm10", "Vermittler: die anderen Schreibweisen werden nicht gesucht", DD, "        namen += [f for f in kanon.formen_von(norm) if len(f) >= 3 and f not in namen]", "        pass", T_FI),
    ("fm11", "Vermittler: die Bewerbung bei der Firma selbst gilt als Vermittler", DD, "        if app_firma == norm or _gleiche_firma(app_firma, norm, kanon):\n            continue  # das ist Stufe A", "        if app_firma == norm:\n            continue  # das ist Stufe A", T_FI),
    ("fm12", "Vermittler: ein Kuerzel zaehlt auch als Wortteil", DD, "        if any(_wortgrenze(n, text) for n in namen):", "        if any(n in text for n in namen):", T_FI),
    # ── Aufrufer: einmal bauen und weitergeben ──
    ("fi01", "Import: der Kanon wird nicht weitergegeben", DBF, "                    kanon=kanon_je_profil[job_pid])", "                    kanon=None)", T_FI),
    ("fi02", "Import: der Kanon wird je Stelle neu gelesen", DBF, "                if job_pid not in kanon_je_profil:\n                    from .duplicate_detection import firmen_kanon", "                if True:\n                    from .duplicate_detection import firmen_kanon", T_FI),
    ("fi03", "Stellen-Dublette: der Kanon wird nicht weitergegeben", SDU, "            liste,\n            kanon=kanon,\n        )", "            liste,\n        )", T_FI),
    ("fi04", "Stellen-Dublette: ein Treffer ueber den Kanon gilt als sicher", SDU, '    return {"stelle": treffer["job"], "sicherheit": VERDACHT,', '    return {"stelle": treffer["job"], "sicherheit": SICHER,', T_FI),
    ("fi05", "Handanlage: laufende Bewerbung ohne Kanon", JOBS, "        app_hit = find_duplicate_job(firma, titel, url, running_apps,\n                                     kanon=kanon)", "        app_hit = find_duplicate_job(firma, titel, url, running_apps)", T_FI),
    ("fi06", "Handanlage: aktive Stelle ohne Kanon", JOBS, "        active_hit = find_duplicate_job(firma, titel, url, active_jobs,\n                                        kanon=kanon)", "        active_hit = find_duplicate_job(firma, titel, url, active_jobs)", T_FI),
    ("fi07", "Handanlage: Anzeigen unter anderen Namen der Firma werden nicht geholt", JOBS, "            if kanon is not None:\n                # #1080: dieselbe Firma steht auch unter ihrem frueheren", "            if False:\n                # #1080: dieselbe Firma steht auch unter ihrem frueheren", T_FI),
    ("fi08", "Handanlage: Textvergleich ohne Kanon", JOBS, "                own_hash=job_hash, kanon=kanon)", "                own_hash=job_hash)", T_FI),
    ("fi09", "Handanlage: Hinweis auf aehnliche Bewerbung ohne Kanon", JOBS, '                _lb = find_duplicate_job(firma, titel, "", running_apps,\n                                         kanon=kanon)', '                _lb = find_duplicate_job(firma, titel, "", running_apps)', T_FI),
    ("fi10", "Handanlage: Vermittler-Suche ohne Kanon", JOBS, "            _vb = find_vermittler_bewerbung(firma, running_apps, kanon=kanon)", "            _vb = find_vermittler_bewerbung(firma, running_apps)", T_FI),
    ("fi11", "Aussortieren: Bewerbungen ohne Kanon", AUS, "    treffer = find_duplicate_job(firma, titel, url, db.get_applications(),\n                                 kanon=kanon)", "    treffer = find_duplicate_job(firma, titel, url, db.get_applications())", T_FI),
    ("fi12", "Aussortieren: aussortierte Stellen ohne Kanon", AUS, '         if (d.get("hash") or "") != eigener],\n        kanon=kanon)', '         if (d.get("hash") or "") != eigener])', T_FI),
    ("fi13", "Trefferliste: der Kanon wird je Stelle neu gebaut", HIN, "            hinweis = fuer_stelle(job, bewerbungen, db=db, kanon=kanon)", "            hinweis = fuer_stelle(job, bewerbungen, db=db)", T_FI),
    ("fi14", "Stellen-Hinweis: Vermittler-Suche ohne Kanon", HIN, '    bewerbung = find_vermittler_bewerbung(job.get("company") or "", laufende,\n                                          kanon=kanon)', '    bewerbung = find_vermittler_bewerbung(job.get("company") or "", laufende)', T_FI),
    ("fi15", "Stellen-Hinweis: ohne Kanon wird keiner gebaut", HIN, "    if kanon is None and db is not None:\n        kanon = firmen_kanon(db)\n    treffer = find_repost_of_application(job, bewerbungen, db=db, kanon=kanon)", "    if False:\n        kanon = firmen_kanon(db)\n    treffer = find_repost_of_application(job, bewerbungen, db=db, kanon=kanon)", T_FI),
    ("fi16", "Automatik: Wiederholung ohne Kanon", AUT, "            if bewerbungs_hinweis.ist_wiederholung(job, bewerbungen, kanon=kanon):", "            if bewerbungs_hinweis.ist_wiederholung(job, bewerbungen):", T_FI),
    ("fi17", "Elwosa: Repost ohne Kanon", ELW, "            rep = find_repost_of_application(j, bewerbungen, kanon=kanon)", "            rep = find_repost_of_application(j, bewerbungen)", T_FI),
    ("fi18", "Plugin-Ingest: laufende Bewerbung ohne Kanon", DASH, "        dup = find_duplicate_job(firma, titel, url, apps,\n                                 kanon=firmen_kanon(_db))", "        dup = find_duplicate_job(firma, titel, url, apps)", T_FI),
    # ── Der Stammsatz selbst ──
    ("fs01", "Ein Name darf mehreren Firmen gehoeren", FS, '        if (f == form or f.replace(" ", "") == form.replace(" ", "")) and fid != ausser_firma:', "        if False:", T_FI),
    ("fs02", "Mutterfirma: Kreise werden nicht abgewiesen", FS, '            if _kette_enthaelt(db, mutterfirma_id, f["id"]):', "            if False:", T_FI),
    ("fs03", "Aufloesen: mehrere passende Firmen - es wird eine geraten", FS, '    if len(treffer) == 1:\n        return {"firma": firma_laden(db, next(iter(treffer))), "mehrdeutig": [], "art": "abgleich"}', '    if len(treffer) >= 1:\n        return {"firma": firma_laden(db, next(iter(treffer))), "mehrdeutig": [], "art": "abgleich"}', T_FI),
    ("fs04", "Vorschlaege werden ohne Bestaetigung angelegt", FS, '    if not bestaetigt:\n        return {"status": "vorschau", "anzahl": len(plan)', '    if False:\n        return {"status": "vorschau", "anzahl": len(plan)', T_FI),
    ("fs05", "Zusammenfuehren mit sich selbst", FS, "    if str(ziel_id) == str(quelle_id):", "    if False:", T_FI),
    ("fs06", "Loeschen laesst die Schreibweisen stehen", FS, '        conn.execute("DELETE FROM company_aliases WHERE company_id=? AND profile_id=?", (f["id"], pid))\n        conn.execute("DELETE FROM company_contacts', '        conn.execute("DELETE FROM company_contacts', T_FI),
    ("fs07", "Umbenennen vergisst den alten Namen", FS, '    if alten_namen_merken and _form(f["name"]) != form:', "    if False:", T_FI),
    ("ft01", "Werkzeug: Zusammenfuehren ohne Bestaetigung", FT, '                if bestaetigung is not True:\n                    return {"status": "bestaetigung_noetig", "ziel": ziel["name"]', '                if False:\n                    return {"status": "bestaetigung_noetig", "ziel": ziel["name"]', T_FI),
    ("ft02", "Werkzeug: Loeschen ohne Bestaetigung", FT, '            if bestaetigung is not True:\n                return {"status": "bestaetigung_noetig", "firma": f["name"]', '            if False:\n                return {"status": "bestaetigung_noetig", "firma": f["name"]', T_FI),
    ("ft03", "Werkzeug: Vorschlaege anwenden gilt immer als bestaetigt", FT, "bestaetigt=bestaetigung is True", "bestaetigt=True", T_FI),
    # ── firma_kontext liest ueber den Stammsatz ──
    ("fb01", "Bezuege: Treffer ueber Schreibweisen sagen nicht woher", FB, '        if via != "direkt":\n            eintrag["via"] = via', '        if False:\n            eintrag["via"] = via', T_FI),
    ("fb02", "Bezuege: der Stammsatz erweitert die Suche nicht", FB, '        if r["firma"]:\n            stamm["formen"] =', '        if False:\n            stamm["formen"] =', T_FI),
    ("fb03", "Konzern: laufende Bewerbung bei Mutter/Tochter bleibt ohne Warnung", FB, '        if o.get("via") in ("mutterfirma", "tochterfirma"):', "        if False:", T_FI),
    ("fb04", "Konzern: Bewerbungen bei Mutter/Tochter zaehlen als dieselbe Firma", FB, '    offene = [o for o in offene if o.get("via") not in ("mutterfirma", "tochterfirma")]', "    offene = offene", T_FI),
    ("fb05", "Kompakt: die Herkunft eines Treffers geht verloren", FB, '    if e.get("via"):\n        aus["via"] = e["via"]', '    if False:\n        aus["via"] = e["via"]', T_FI),
    ("fb06", "firma_kontext: Treffer ueber Schreibweisen sagen nicht woher", BEW, '        if via != "direkt":\n            eintrag["via"] = via', '        if False:\n            eintrag["via"] = via', T_FI),
    ("fb07", "firma_kontext: mehrdeutige Firmen werden verschwiegen", BEW, '    elif stamm_aufloesung["mehrdeutig"]:', "    elif False:", T_FI),
    ("fb08", "Dokumente an einer gefundenen Bewerbung bleiben aus der Historie", FB, '        an_bewerbung = (d["linked_application_id"] or "") in app_ids', "        an_bewerbung = False", T_FI),
    # ── Kontakte: Rolle und Zeitraum je Firma ──
    ("fc01", "Zuordnung: ein Ende macht den Kontakt nicht zum fruehen", FS, "    if aktuell is None:\n        aktuell = not bis_n", "    if aktuell is None:\n        aktuell = True", T_FI),
    ("fc02", "Zuordnung: Ende und aktuell zugleich werden hingenommen", FS, '    if bis_n and aktuell:\n        return {"status": "fehler", "text": "Ein Zeitraum mit Ende ist nicht aktuell: entweder das Ende weglassen oder aktuell=False."}', "    if False:\n        pass", T_FI),
    ("fc03", "Zuordnung: der Beginn darf nach dem Ende liegen", FS, '        return {"status": "fehler", "text": fehler or fehler2}\n    if von_n and bis_n and _zeit_sortierbar(von_n) > _zeit_sortierbar(bis_n):', '        return {"status": "fehler", "text": fehler or fehler2}\n    if False:', T_FI),
    ("fc04", "Zuordnung: dieselbe Zuordnung entsteht doppelt", FS, '        if gleich:\n            return {"status": "schon_da", "zuordnung_id": gleich["id"]', '        if False:\n            return {"status": "schon_da", "zuordnung_id": gleich["id"]', T_FI),
    ("fc05", "Kontakt: eine mehrdeutige kurze Kennung wird geraten", FS, "        r = r[0] if len(r) == 1 else None          # mehrdeutig: nicht raten", "        r = r[0] if r else None", T_FI),
    ("fc06", "Kontakt: auch Kontakte anderer Profile lassen sich zuordnen", FS, '    r = conn.execute("SELECT id, full_name, company, position FROM contacts WHERE id=? AND (profile_id=? OR profile_id IS NULL)", (roh, pid)).fetchone()', '    r = conn.execute("SELECT id, full_name, company, position FROM contacts WHERE id=? AND ?=?", (roh, pid, pid)).fetchone()', T_FI),
    ("fc07", "Aendern: ein neues Ende macht den Kontakt nicht zum fruehen", FS, '            if bis_n and "aktuell" not in felder:\n                aktuell = False', '            if bis_n and "aktuell" not in felder:\n                pass', T_FI),
    ("fc08", "Zusammenfuehren laesst die Zuordnungen der Quelle zurueck", FS, '            conn.execute("UPDATE company_contacts SET company_id=? WHERE company_id=? AND profile_id=?", (ziel["id"], quelle["id"], pid))\n', "", T_FI),
    ("fc09", "Loeschen der Firma laesst die Zuordnungen stehen", FS, '        conn.execute("DELETE FROM company_contacts WHERE company_id=? AND profile_id=?", (f["id"], pid))\n', "", T_FI),
    ("fc10", "firma_kontext: der Kontakt erscheint doppelt (Zuordnung und Textfeld)", FB, '        if k["id"] in zugeordnet:\n            continue', '        if False:\n            continue', T_FI),
    ("fc11", "firma_kontext: der Zeitraum fehlt in der Kurzzeile", FB, '        return ", ".join(x for x in (e.get("person"), e.get("funktion"), e.get("zeitraum")) if x)', '        return ", ".join(x for x in (e.get("person"), e.get("funktion")) if x)', T_FI),
    ("fc12", "firma_kontext: der Firmentext eines Kontakts wird zur Schreibweise", FB, '                            if t.get("abgleich") not in ("text", "bewerbung", "zuordnung")', '                            if t.get("abgleich") not in ("text", "bewerbung")', T_FI),
    ("fo01", "Verweis: oeffnen_aufrufe nennt eine Firma mehrfach", FB, "        if roh and schluessel and schluessel not in gesehen:", "        if roh and schluessel:", T_FI),
    ("fo02", "Verweis: Apostroph im Namen bricht den Aufruf", FB, "roh.replace(\"'\", \"\\\\'\")", "roh", T_FI),
    ("fo03", "Bewerbung: nur der Arbeitgeber fuehrt zur Firma", BEW, '                app.get("company"), app.get("vermittler"), app.get("endkunde"))', '                app.get("company"))', T_FI),
    ("fo04", "Stelle: kein Weg zur Firma", JOBS, '            result["firma_oeffnen"] = _fb_oeffnen.oeffnen_aufrufe(job_dict.get("company"))', "            pass", T_FI),
    ("fo05", "Kontakt: das Textfeld Firma fuehrt nicht zur Firma", KON, '                *[z["firma"] for z in firmen], contact.get("company"))', '                *[z["firma"] for z in firmen])', T_FI),
    ("fv01", "kontakt_verknuepfen: firma geht ins Leere statt zur Firma", KON, '        if (ziel_typ or "").strip().lower() == "firma":', "        if False:", T_FI),
    ("fv02", "kontakt_verknuepfen: ein mehrdeutiger Name wird geraten", KON, '                if erg["mehrdeutig"]:\n                    return {"fehler": "Der Name passt zu mehreren Firmen:', '                if False:\n                    return {"fehler": "Der Name passt zu mehreren Firmen:', T_FI),
    ("ft04", "Werkzeug: Zuordnung aendern ohne etwas zu aendern gilt als erfolgreich", FT, '                if not felder:\n                    return {"status": "fehler", "text": "Nichts zu ändern: nenne rolle, von, bis, aktuell oder notizen."}', "                if False:\n                    pass", T_FI),
    # ── Die Firmen-Ansicht und ihre Endpunkte ──
    ("fa01", "Ansicht: die Bewerbungen fehlen in der Zeitleiste", FA, '    eintraege = [_aus_bewerbung(b) for b in daten.get("bewerbungen", [])]', "    eintraege = []", T_FI),
    ("fa02", "Ansicht: die aktiven Stellen fehlen in der Zeitleiste", FA, '    eintraege += [_aus_stelle(s) for s in daten.get("aktive_stellen", [])]', "    eintraege += []", T_FI),
    ("fa03", "Ansicht: das Aelteste steht oben", FA, "    mit = sorted((e for e in eintraege if e[\"datum\"]), key=lambda e: e[\"datum\"], reverse=True)", "    mit = sorted((e for e in eintraege if e[\"datum\"]), key=lambda e: e[\"datum\"])", T_FI),
    ("fa04", "Ansicht: Eintraege ohne Datum stehen oben", FA, '    return mit + [e for e in eintraege if not e["datum"]]', '    return [e for e in eintraege if not e["datum"]] + mit', T_FI),
    ("fa05", "Ansicht: eine Erwaehnung in den Notizen faellt weg", FA, '    if rolle == "in_notizen_erwaehnt":', "    if False:", T_FI),
    ("fr01", "Endpunkt: Zusammenfuehren ohne Bestaetigung", DASH, '    if data.get("bestaetigt") is not True:\n        return JSONResponse({"error": "Bestätigung fehlt.", "status": "bestaetigung_noetig", "ziel"', '    if False:\n        return JSONResponse({"error": "Bestätigung fehlt.", "status": "bestaetigung_noetig", "ziel"', T_FI),
    ("fr02", "Endpunkt: Loeschen ohne Bestaetigung", DASH, '    if not bestaetigt:\n        return JSONResponse({"error": "Bestätigung fehlt.", "status": "bestaetigung_noetig"}, status_code=400)', '    if False:\n        return JSONResponse({"error": "Bestätigung fehlt.", "status": "bestaetigung_noetig"}, status_code=400)', T_FI),
    ("fr03", "Endpunkt: Vorschlaege gelten immer als bestaetigt", DASH, 'bestaetigt=data.get("bestaetigt") is True))', "bestaetigt=True))", T_FI),
    ("fr04", "Endpunkt: Fehler kommen als 200 zurueck", DASH, '    code = _FIRMEN_FEHLER.get(erg.get("status"))', "    code = None", T_FI),
]

# ── Suche: ein Klick auf einen Treffer oeffnet das Objekt (#1177, G88) ──
DASH_S = "src/bewerbungs_assistent/dashboard.py"
T_SU = ["tests/test_v18_suche_treffer_oeffnen_1177.py"]

M_SUCHE = [
    ("su01", "Suche: Bewerbungs-Treffer tragen wieder die fruehere Adresse (?id=)", DASH_S,
     '            "url": _hash_ziel("bewerbungen", a["id"]),\n', '            "url": f"#bewerbungen?id={a[\'id\']}",\n', T_SU),
    ("su02", "Suche: Stellen-Treffer tragen den gespeicherten Hash mit Profil-Praefix", DASH_S,
     '            "id": _db._public_job_hash(j["hash"]),\n', '            "id": j["hash"],\n', T_SU),
    ("su03", "Suche: ein Termin ohne Bewerbung zeigt auf den Kalender ohne Kennung", DASH_S,
     '_hash_ziel("kalender", m["id"])', '_hash_ziel("kalender")', T_SU),
    ("su04", "Suche: ein Termin traegt seine Bewerbung nicht mit", DASH_S,
     '                "application_id": m["app_id"] or "",\n', '                "application_id": "",\n', T_SU),
    ("su05", "Dokumente: die Liste kennt die Kennung (doc_id) nicht", DASH_S,
     '    if doc_id:\n        base += " AND d.id = ?"', '    if False:\n        base += " AND d.id = ?"', T_SU),
    ("su06", "Link: hash_ziel behaelt das Profil-Praefix der Stelle", "src/bewerbungs_assistent/services/dashboard_link.py",
     '        kennung = str(kennung).split(":", 1)[-1]\n', '        kennung = str(kennung)\n', T_SU),
    ("su07", "Klick: der Treffer setzt nur noch den Hash, ohne Sprungziel", "frontend/src/App.jsx",
     '    navigateTo(ziel.seite, ziel.intent);\n  }', '    window.location.hash = ziel.seite;\n  }', T_SU),
    ("su08", "wege.js: ein Stellen-Treffer blaettert nur, statt die Stelle zu oeffnen", "frontend/src/lib/wege.js",
     '  else if (art === "job") ziel = zuStelle(treffer.id);', '  else if (art === "job") ziel = { seite: "stellen", intent: { jobHash: treffer.id } };', T_SU),
    ("su09", "wege.js: ein Termin mit Bewerbung landet oben in der Timeline", "frontend/src/lib/wege.js",
     '    if (ziel?.seite === "bewerbungen") ziel = {', '    if (false) ziel = {', T_SU),
    ("su10", "wege.js: ein Mail-Treffer fuehrt nirgends hin", "frontend/src/lib/wege.js",
     '  } else if (art === "email") ziel = zuMail(treffer.id);', '  } else if (art === "email") ziel = null;', T_SU),
    ("su11", "wege.js: ein Skill-Treffer kennt den Namen nicht", "frontend/src/lib/wege.js",
     'ziel = zuProfil("skills", treffer.title);', 'ziel = zuProfil("skills");', T_SU),
    ("su12", "Dokumente-Seite: die Kennung des Sprungs wird nicht gelesen", "frontend/src/pages/DocumentsPage.jsx",
     '    if (!intent.dokumentId) return;\n', '    return;\n', T_SU),
    ("su13", "Dokumente-Seite: das Dokument wird nicht aufgeklappt", "frontend/src/pages/DocumentsPage.jsx",
     '        setExpandedDoc(doc.id);\n        setDokumentZiel(doc.id);', '        setDokumentZiel(doc.id);', T_SU),
    ("su14", "Dokumente-Seite: ein aktiver Typ-Filter verbirgt das Dokument weiter", "frontend/src/pages/DocumentsPage.jsx",
     '        setDocType("");\n        setAppFilter("");', '        setAppFilter("");', T_SU),
    ("su15", "Dokumente-Seite: die Mail-Kennung des Sprungs wird nicht weitergegeben", "frontend/src/pages/DocumentsPage.jsx",
     '      setMailZiel(String(intent.mailId));\n', '      setMailZiel("");\n', T_SU),
    ("su16", "Mail-Liste: das Fenster der Mail geht nicht auf", "frontend/src/components/EmailListe.jsx",
     '      .then((mail) => setDetail(mail))', '      .then((mail) => mail)', T_SU),
    ("su17", "Kalender-Seite: die Termin-Kennung des Sprungs wird nicht gelesen", "frontend/src/pages/CalendarPage.jsx",
     '    if (intent?.page !== "kalender" || !intent.terminId) return;\n', '    return;\n', T_SU),
    ("su18", "Profil-Seite: der Abschnitt des Sprungs wird nicht gemerkt", "frontend/src/pages/ProfilePage.jsx",
     '    if (intent.abschnitt) setAbschnittZiel(', '    if (false) setAbschnittZiel(', T_SU),
    ("su19", "Profil-Seite: der Name filtert die Skill-Liste nicht", "frontend/src/pages/ProfilePage.jsx",
     '(profile?.skills?.length || 0) > 6) setSkillFilter(suche);', '(profile?.skills?.length || 0) > 6) { /* nichts */ }', T_SU),
    ("su20", "Timeline: der Sprung in den Abschnitt beim Oeffnen fehlt", "frontend/src/components/Sprungleiste.jsx",
     '    springe(anfang.kennung, true);\n', '', T_SU),
    ("su21", "Link: #dokumente/<Kennung> fuehrt nirgends hin", "frontend/src/utils.js",
     '  if (ziel.page === "dokumente") return { dokumentId: ziel.kennung };\n', '', T_SU),
    ("su22", "Link: #kalender/<Kennung> fuehrt nirgends hin", "frontend/src/utils.js",
     '  if (ziel.page === "kalender") return { terminId: ziel.kennung };\n', '', T_SU),
    ("su23", "Bewerbungen: ein Termin ohne Bewerbung fuehrt nur in den Kalender, ohne sich zu oeffnen", "frontend/src/pages/ApplicationsPage.jsx",
     'navigateTo("kalender", { terminId: meeting.id })', 'navigateTo("kalender")', T_SU),
]

T_WG = ["tests/test_v18_wege_1171.py"]
T_WGF = T_WG + ["tests/test_v18_firmen_ansicht_1080.py"]
T_WGO = ["tests/test_v18_offen_nur_ueberfaelliges_rot_1174.py"]

# Wege durch PBP (#1171, G85): jeder Weg einzeln unterbrochen. Die Frontend-Eintraege (frontend/...) bauen das Bundle vor dem Test neu,
# denn die Browser-Tests pruefen das gebaute Bundle. Der Arbeitsbaum braucht dafuer `frontend/node_modules` (Junction oder Link).
M_WEGE = [
    ('wg01', 'Dashboard: die Nachfass-Zeile fuehrt wieder nur auf die Aufgaben-Seite', 'frontend/src/components/OffenBlock.jsx', '    const ziel = offenZeileZiel(eintrag);\n    if (ziel) return navigateTo?.(ziel.seite, ziel.intent || undefined);\n', '    return navigateTo?.("aufgaben");\n', T_WG),
    ('wg02', 'wege.js: eine Zeile mit Bewerbung kennt ihre Bewerbung nicht', 'frontend/src/lib/wege.js', '  const bew = zuBewerbung(eintrag.bewerbung_id);\n  return bew || { seite: "aufgaben", intent: null };\n', '  return { seite: "aufgaben", intent: null };\n', T_WG),
    ('wg03', 'wege.js: eine Stelle wird angescrollt, nicht geoeffnet', 'frontend/src/lib/wege.js', 'intent: { focus: "job", jobHash: h, oeffnen: true }', 'intent: { focus: "job", jobHash: h }', T_WG),
    ('wg04', 'Nach dem Speichern bleibt die neue Bewerbung unter der Liste', 'frontend/src/pages/JobsPage.jsx', '      if (neu) navigateTo(neu.seite, neu.intent);\n      else navigateTo("bewerbungen");\n', '      navigateTo("bewerbungen");\n', T_WG),
    ('wg05', 'Stellen-Seite liest die Absicht `oeffnen` nicht', 'frontend/src/pages/JobsPage.jsx', '      if (intent.oeffnen) setPendingOpenJobHash(String(intent.jobHash));\n', '', T_WG),
    ('wg06', 'Stellen-Seite oeffnet die gemerkte Stelle nie', 'frontend/src/pages/JobsPage.jsx', '    if (loading || !pendingOpenJobHash) return undefined;\n    const hash = pendingOpenJobHash;', '    return undefined;\n    const hash = pendingOpenJobHash;', T_WG),
    ('wg07', 'Stelle ausserhalb der geladenen Seite: die Einzelantwort wird verworfen', 'frontend/src/pages/JobsPage.jsx', '.then((einzeln) => { if (einzeln) openDetailDialog(einzeln); })', '.then(() => {})', T_WG),
    ('wg08', 'Kontakte-Seite liest die Absicht `kontaktId` nicht', 'frontend/src/pages/ContactsPage.jsx', '      if (intent.kontaktId) {\n', '      if (false) {\n', T_WG),
    ('wg09', 'Kontakt-Dialog: die Verknuepfung ist wieder nur Text', 'frontend/src/pages/ContactsPage.jsx', '{z.ziel ? (', '{false ? (', T_WG),
    ('wg10', 'Bewerbung: der Name der Person fuehrt nirgends hin', 'frontend/src/pages/ApplicationsPage.jsx', 'onClick={() => { const z = zuKontakt(c.id); if (z) navigateTo(z.seite, z.intent); }}', 'onClick={() => {}}', T_WG),
    ('wg11', 'Bewerbungskarte: „Zur Stelle“ tut nichts', 'frontend/src/pages/ApplicationsPage.jsx', '<Button variant="secondary" onClick={() => setJobDetailHash(application.job_hash)} data-karte-zur-stelle', '<Button variant="secondary" onClick={() => {}} data-karte-zur-stelle', T_WG),
    ('wg12', 'Timeline: kein naechster Schritt fuer die Unterlagen', 'frontend/src/pages/ApplicationsPage.jsx', '{timelineDialog.entry?.application?.status === "in_vorbereitung" && !timelineDialog.entry?.application?.cv_path && (', '{false && (', T_WG),
    ('wg13', 'Aufgabe: „Zur Bewerbung“ tut nichts', 'frontend/src/pages/TasksPage.jsx', 'onClick={(ev) => { ev.stopPropagation(); springeZurBewerbung(e); }}', 'onClick={(ev) => { ev.stopPropagation(); }}', T_WG),
    ('wg14', 'Dashboard: die Top-Stelle scrollt nur noch', 'frontend/src/pages/DashboardPage.jsx', 'onClick={() => { const z = zuStelle(job.hash); if (z) navigateTo(z.seite, z.intent); }}', 'onClick={() => navigateTo("stellen", { focus: "job", jobHash: job.hash })}', T_WG),
    ('wg15', 'Sprungleiste: steht 20 px unter dem Rand, darueber scrollt Inhalt vorbei', 'frontend/src/components/Sprungleiste.jsx', 'sticky -top-5 z-20', 'sticky top-0 z-20', T_WG),
    ('wg16', 'Sprungleiste: der letzte Abschnitt wird am Ende nicht als aktuell markiert', 'frontend/src/components/Sprungleiste.jsx', '      if (alle.length && koerper.scrollTop + koerper.clientHeight >= koerper.scrollHeight - 2) {', '      if (false) {', T_WG),
    ('wg17', 'Sprungleiste: der Abschnitt landet hinter der Leiste', 'frontend/src/components/Sprungleiste.jsx', 'koerper.scrollTop - leiste - 8;', 'koerper.scrollTop - 8;', T_WG),
    ('wg18', 'Dialog: der scrollende Inhalt traegt keine Kennung mehr', 'frontend/src/components/ui.jsx', '<div data-modal-koerper className="soft-scrollbar', '<div className="soft-scrollbar', T_WG),
    ('wg19', 'Timeline: der Abschnitt Personen ist nicht mehr anspringbar', 'frontend/src/pages/ApplicationsPage.jsx', '<Card data-abschnitt="personen" className=', '<Card className=', T_WG),
    ('wg20', 'Kontakt: die Verknuepfung nennt ihr Ziel nicht', 'src/bewerbungs_assistent/database.py', 'link.update(ziel_titel=row["title"] or "", ziel_firma=row["company"] or "", ziel_status=row["status"] or "", ziel_gefunden=True)', 'link.update(ziel_gefunden=True)', T_WG),
    ('wg21', 'Route: eine Kennung verschluckt die festen Pfade (export.csv)', 'src/bewerbungs_assistent/dashboard.py', '@app.get("/api/contacts/export.csv")', '@app.get("/api/contacts/export-csv")', T_WG),
    ('wg22', 'Firma: der Kontakt-Eintrag traegt keine Kennung der Person', 'src/bewerbungs_assistent/services/firmen_ansicht.py', ', "kontakt_id": b.get("kontakt_id") or ""},', '},', T_WGF),
    ('wg23', 'firmen.js: ein Kontakt-Sprung kennt die Person nicht', 'frontend/src/lib/firmen.js', '      const z = zuKontakt(ziel.kontakt_id);', '      const z = null;', T_WG),
    ('wg24', 'wege.js: die Verknuepfung nennt ihren Titel nicht', 'frontend/src/lib/wege.js', '  if (titel) text += `: ${titel}`;\n', '', T_WG),
    ('wg25', 'wege.js: die Abschnitte der Sprungleiste stehen in falscher Reihenfolge', 'frontend/src/lib/wege.js', '  { kennung: "dokumente", label: "Dokumente" },\n  { kennung: "personen", label: "Personen" },\n', '  { kennung: "personen", label: "Personen" },\n  { kennung: "dokumente", label: "Dokumente" },\n', T_WG),
    ('wg26', 'Einzelne Stelle: ohne Anreicherung (roher Wert, keine Daumen)', 'src/bewerbungs_assistent/dashboard.py', '        _db._mit_scoring_reglern([job], sortieren=False)\n        _guete_anreichern([job])\n', '        pass\n', T_WG),
    ('wg27', 'Bewerbungen: jedes Nachladen ersetzt die Seite samt Dialog durch die Ladeanzeige', 'frontend/src/pages/ApplicationsPage.jsx', 'if (loading && applications.length === 0 && !timelineDialog.open) return', 'if (loading) return', T_WG),
    ('wg28', 'Link aus Claude: `#stellen/<Kennung>` blaettert nur in der Liste', 'frontend/src/utils.js', 'return { jobHash: ziel.kennung, oeffnen: true };', 'return { jobHash: ziel.kennung };', T_WG),
    ('wg29', 'Stellen: der Abruf „laeuft eine Suche?“ startet nach jeder Antwort neu (Effekt-Ereignis in der Liste)', 'frontend/src/pages/JobsPage.jsx', '  }, [reloadKey]);\n\n  useEffect(() => {\n    if (intent?.page !== "stellen") return;', '  }, [reloadKey, syncRunningSearch]);\n\n  useEffect(() => {\n    if (intent?.page !== "stellen") return;', T_WG),
    ('wg30', 'Stellen: jedes Nachladen ersetzt Liste und Dialog durch die Ladeanzeige', 'frontend/src/pages/JobsPage.jsx', 'if (loading && !einmalGeladen) return <LoadingPanel label="Stellen werden geladen..." />;', 'if (loading) return <LoadingPanel label="Stellen werden geladen..." />;', T_WG),
    ('wg31', 'Stellen: der offene Dialog zeigt weiter den Stand vom Oeffnen', 'frontend/src/pages/JobsPage.jsx', '    if (!frisch || frisch === detailDialog.job) return;\n', '    return;\n', T_WG),
    ('wg32', 'Bewerbungen: die offene Timeline wird nach dem Nachladen nicht aufgefrischt', 'frontend/src/pages/ApplicationsPage.jsx', '    loadPage();\n    offeneTimelineAuffrischen();\n', '    loadPage();\n', T_WG),    ('wg33', 'Stellen: eine von Claude gestartete Suche erscheint erst nach bis zu 30 Sekunden', 'frontend/src/pages/JobsPage.jsx', 'const SUCHE_ABFRAGE_MS = 5000;', 'const SUCHE_ABFRAGE_MS = 30000;', T_WG),
    ('wg34', 'Offen: die ganze Karte wird rot, sobald etwas ueberfaellig ist', 'frontend/src/components/OffenBlock.jsx', '<Card className="rounded-2xl" data-offen-karte>', '<Card className={block.ueberfaellig_anzahl > 0 ? "rounded-2xl border border-coral/40 bg-coral/[0.06]" : "rounded-2xl"} data-offen-karte>', T_WGO),
    ('wg35', 'Offen: das Wecker-Symbol wird rot, sobald etwas ueberfaellig ist', 'frontend/src/components/OffenBlock.jsx', '<AlarmClock size={16} className="text-muted" data-offen-symbol />', '<AlarmClock size={16} className={block.ueberfaellig_anzahl > 0 ? "text-coral" : "text-muted"} data-offen-symbol />', T_WGO),
    ('wg36', 'Offen: das Datum der ueberfaelligen Zeilen ist nicht mehr rot', 'frontend/src/components/OffenBlock.jsx', '${key === "ueberfaellig" ? "text-coral" : "text-muted"}', 'text-muted', T_WGO),
    ('wg37', 'Offen: auch die Daten der anderen Zeilen sind rot', 'frontend/src/components/OffenBlock.jsx', '${key === "ueberfaellig" ? "text-coral" : "text-muted"}', 'text-coral', T_WGO),
    ('wg38', 'Offen: die Ueberschrift Ueberfaellig ist nicht mehr rot', 'frontend/src/components/OffenBlock.jsx', '{ key: "ueberfaellig", label: "Überfällig", ton: "text-coral" }', '{ key: "ueberfaellig", label: "Überfällig", ton: "text-muted" }', T_WGO),
]

# ── Update-Hinweis fuer Vorabversionen (#1179, G89) und Elwosa nennt eine neue Version (#1180, F49) ──
T_VO = ["tests/test_v18_update_vorabversion_1179.py"]
T_EW = ["tests/test_v18_elwosa_update_1180.py"]
AUL = "frontend/src/lib/autoUpdate.js"
UT = "frontend/src/components/UpdatesTab.jsx"
SBL = "frontend/src/components/Sidebar.jsx"
HZ = "frontend/src/lib/hinweisZone.js"
EWP = "src/bewerbungs_assistent/services/elwosa_provider.py"
EWE = "src/bewerbungs_assistent/services/elwosa.py"

M_VORAB = [
    ("vo01", "Update-Seite: statt der Vorabversion steht wieder „Aktuell“", UT,
     '            : vorab ? <Badge tone="amber">Neue Vorabversion: v{vorab.version}</Badge>\n              : zeigeAktuell(au)',
     '            : zeigeAktuell(au)', T_VO),
    ("vo02", "Update-Seite: die Karte mit Erklaerung und Weg fehlt", UT,
     '        {vorab ? (\n          <div className="mt-4 rounded-xl border border-amber/30 bg-amber/10 p-4" data-updates-vorab>',
     '        {false ? (\n          <div className="mt-4 rounded-xl border border-amber/30 bg-amber/10 p-4" data-updates-vorab>', T_VO),
    ("vo03", "Update-Seite: „Jetzt pruefen“ fragt die allgemeine Pruefung nicht mit", UT,
     '      if (pfad === "/api/auto-update/pruefen") refreshUpdateInfo?.();\n', '', T_VO),
    ("vo04", "Update-Seite: „ZIP herunterladen“ oeffnet die Veroeffentlichung statt des ZIP", UT,
     '<Button size="sm" onClick={() => oeffneAdresse(vorab.zip)}', '<Button size="sm" onClick={() => oeffneAdresse(vorab.url)}', T_VO),
    ("vo05", "Regel: eine von Hand installierte Vorabversion gilt weiter als neu", AUL,
     '  if (istSchonInstalliert(au, version)) return null;\n', '', T_VO),
    ("vo06", "Regel: eine fertige neue Version verdraengt die Vorabversion nicht mehr", AUL,
     '  if (au?.neu) return null;\n', '', T_VO),
    ("vo07", "Regel: die Adresse des ZIP zeigt auf einen Zweig statt auf den Tag", AUL,
     'const ARCHIV_ADRESSE = "https://github.com/MadGapun/PBP/archive/refs/tags/";',
     'const ARCHIV_ADRESSE = "https://github.com/MadGapun/PBP/archive/refs/heads/";', T_VO),
    ("vo08", "Regel: auch eine fertige Version gilt als Vorabversion", AUL,
     '  return Boolean(k) && k[3] !== 9;\n', '  return Boolean(k);\n', T_VO),
    ("vo09", "Seitenleiste: der Knopf nennt eine Vorabversion „Neue Version“", SBL,
     '                  {istVorabversion(brand.updateVersion) ? "Neue Vorabversion verfügbar" : "Neue Version verfügbar"}: v{brand.updateVersion}\n                </button>',
     '                  Neue Version verfügbar: v{brand.updateVersion}\n                </button>', T_VO),
    ("vo10", "Seitenleiste: der Link nennt eine Vorabversion „Neue Version“", SBL,
     '                  {istVorabversion(brand.updateVersion) ? "Neue Vorabversion verfügbar" : "Neue Version verfügbar"}: v{brand.updateVersion}\n                </a>',
     '                  Neue Version verfügbar: v{brand.updateVersion}\n                </a>', T_VO),
    ("vo11", "Dashboard: die Vorabversion kommt nicht in die Hinweiszone", "frontend/src/pages/DashboardPage.jsx",
     '    vorab: vorabNeu(autoUpdate, updateInfo),\n', '', T_VO),
    ("vo12", "Hinweiszone: updateHinweis bekommt die Vorabversion nicht", HZ,
     'mcp: lage.mcp, vorab: lage.vorab });', 'mcp: lage.mcp });', T_VO),
    ("vo13", "Hinweiszone: ohne Auto-Update gilt wieder der alte Hinweis fuer die Vorabversion", HZ,
     '    if (lage.vorab) return vorabHinweis(lage.vorab);\n', '', T_VO),
    ("vo14", "Regel: updateHinweis kennt keine Vorabversion", AUL,
     '  if (!neu) return extra.vorab ? vorabHinweis(extra.vorab) : null;\n', '  if (!neu) return null;\n', T_VO),
    ("vo15", "Kontext: die Update-Seite kann die allgemeine Pruefung nicht anstossen", "frontend/src/App.jsx",
     '    refreshUpdateInfo: () => setUpdateFrageNr((n) => n + 1),\n', '', T_VO),
    ("vo16", "Hilfe: die FAQ nennt Vorabversionen nicht", "frontend/src/lib/hilfe.js",
     'Eine neuere Vorabversion (Beta) nennt PBP', 'Eine neuere Fassung nennt PBP', T_VO),
    ("ew01", "Elwosa: eine unbrauchbare Version wird trotzdem gesagt", EWP,
     '    if not _FASSUNG.fullmatch(version):\n        return []\n', '    if False:\n        return []\n', T_EW),
    ("ew02", "Elwosa: dieselbe Version wird immer wieder gesagt", EWP,
     '    if (db.get_profile_setting("elwosa_update_version", "") or "") == version:\n        return []                         # diese Version ist schon gesagt\n',
     '', T_EW),
    ("ew03", "Elwosa: eine von Hand installierte Version wird noch gesagt", EWP,
     '    if _fassung_schon_da(version):\n        return []                         # von Hand installiert, wartet nur auf den Neustart\n',
     '', T_EW),
    ("ew04", "Elwosa: nach dem Posten wird die Version nicht vermerkt", EWE,
     '    if msg_id and cand.trigger_kind == "update_neu":', '    if False and cand.trigger_kind == "update_neu":', T_EW),
    ("ew05", "Elwosa: ein Titel gegen die Sprach-DNA laesst die Linie stumm statt ohne Titel", EWP,
     '        except TonfallError:\n            continue                      # ein Titel gegen die Sprach-DNA: dann ohne Titel, nicht stumm\n',
     '        except TonfallError:\n            pass\n', T_EW),
    ("ew06", "Elwosa: eine Vorabversion wird nicht als solche genannt", EWP,
     '    if "-" in version:\n', '    if False:\n', T_EW),
    ("ew07", "Elwosa: der Kanal steht vor der Betriebslage", EWP,
     '    for provider in (betriebslage_kandidaten, update_kandidaten, changelog_kandidaten):',
     '    for provider in (update_kandidaten, betriebslage_kandidaten, changelog_kandidaten):', T_EW),
    ("ew08", "Elwosa: die Linie traegt keinen Link", EWP,
     '        link_url=befund.get("release_url") or f"https://github.com/MadGapun/PBP/releases/tag/v{version}",\n', '        link_url="",\n', T_EW),
    ("ew09", "Elwosa: die Pruefung merkt ihren Befund nicht", "src/bewerbungs_assistent/dashboard.py",
     '    _uq.befund_merken(result)   # #1180: Elwosa nennt eine neue Version, ohne selbst zu fragen\n', '', T_EW),
    ("ew10", "Elwosa: der Kanal fehlt in der Liste der Kanaele", EWP,
     '    for provider in (betriebslage_kandidaten, update_kandidaten, changelog_kandidaten):',
     '    for provider in (betriebslage_kandidaten, changelog_kandidaten):', T_EW),
    ("ew11", "Elwosa: „schon installiert“ vergleicht verkehrt herum", EWP,
     '        return bool(aktuell) and not fassung.ist_neuer(version, aktuell)\n',
     '        return bool(aktuell) and fassung.ist_neuer(version, aktuell)\n', T_EW),
    ("ew12", "Elwosa: ein langer Titel wird nicht gekuerzt", EWP,
     '    return t[:UPDATE_TITEL_MAX].strip()\n', '    return t.strip()\n', T_EW),
]

# ── Konsolenausgaben nie mit der falschen Kodierung lesen (#1182, I26) ──
T_KO = ["tests/test_v18_konsole_ausgabe_1182.py"]
CN = "src/bewerbungs_assistent/services/claude_neustart.py"
KO = "src/bewerbungs_assistent/services/konsole.py"
OS_ = "src/bewerbungs_assistent/services/ollama_start.py"

M_KONSOLE = [
    ("ko01", "Claude-Pruefung: tasklist wird wieder im Textmodus gelesen", CN,
     '        r = run(["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],\n                capture_output=True, timeout=5, creationflags=_OHNE_FENSTER)\n',
     '        r = run(["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],\n                capture_output=True, text=True, timeout=5, creationflags=_OHNE_FENSTER)\n', T_KO),
    ("ko02", "Claude-Pruefung: der Prozessname zaehlt wieder mit Gross- und Kleinschreibung", CN,
     '        return "claude.exe" in text_lesen(r.stdout).lower()\n', '        return "Claude.exe" in text_lesen(r.stdout)\n', T_KO),
    ("ko03", "Store-Start: die Ausgabe von PowerShell wird nicht mehr in Text verwandelt", CN,
     '            if "ok" in text_lesen(r.stdout):', '            if "ok" in (r.stdout or ""):', T_KO),
    ("ko04", "Helfer: nichts (None) wird nicht mehr zu leerem Text", KO,
     '    if roh is None:\n        return ""\n', '    if roh is None:\n        return None\n', T_KO),
    ("ko05", "Helfer: unlesbare Zeichen brechen das Lesen wieder ab", KO,
     '        return bytes(roh).decode(kodierung or konsole_kodierung(), errors="replace")', '        return bytes(roh).decode(kodierung or konsole_kodierung())', T_KO),
    ("ko06", "Helfer: unter Windows gilt die Kodierung des Systems statt der der Konsole", KO,
     '    return "oem" if sys.platform == "win32" else "utf-8"', '    return "cp1252" if sys.platform == "win32" else "utf-8"', T_KO),
    ("ko07", "Desktop-Pfad: PowerShell wird wieder im Textmodus ohne Kodierung gelesen", OS_,
     'capture_output=True, encoding=konsole_kodierung(), errors="replace", timeout=20,', 'capture_output=True, text=True, timeout=20,', T_KO),
    ("ko08", "Verknuepfung Ollama beenden: PowerShell wird wieder im Textmodus ohne Kodierung gelesen", OS_,
     'capture_output=True, encoding=konsole_kodierung(), errors="replace", timeout=30,', 'capture_output=True, text=True, timeout=30,', T_KO),
    ("ko09", "systemctl-Abfrage: wieder Textmodus ohne Kodierung", OS_,
     'capture_output=True, encoding="utf-8", errors="replace", timeout=5)', 'capture_output=True, text=True, timeout=5)', T_KO),
    ("ko10", ".doc-Auslesen (antiword): wieder Textmodus ohne Kodierung", "src/bewerbungs_assistent/dashboard.py",
     'capture_output=True, encoding="utf-8", errors="replace", timeout=30', 'capture_output=True, text=True, timeout=30', T_KO),
    ("ko11", "Alter Installer mit Fenster: der venv-Aufruf liest wieder ohne Ersatzzeichen", "installer/setup_gui.py",
     'capture_output=True, text=True, errors="replace", timeout=120', 'capture_output=True, text=True, timeout=120', T_KO),
]

KATALOGE = {"auto_update": M, "speicher": M_SPEICHER, "komponenten": M_KOMPONENTEN, "mail": M_MAIL, "firmen": M_FIRMEN, "wege": M_WEGE, "suche": M_SUCHE, "vorab": M_VORAB, "konsole": M_KONSOLE}
GRUNDLAEUFE = {
    "auto_update": (("T_PR", T_PR), ("T_Q", T_Q), ("T_I", T_I), ("T_B", T_B), ("T_L", T_L), ("T_S", T_S), ("T_E", T_E)),
    "speicher": (("T_SP", T_SP), ("T_EO", T_EO)),
    "komponenten": (("T_KP", T_KP),),
    "mail": (("T_MQ", T_MQ),),
    "firmen": (("T_FI", T_FI),),
    "wege": (("T_WG", T_WG),),
    "suche": (("T_SU", T_SU),),
    "vorab": (("T_VO", T_VO), ("T_EW", T_EW)),
    "konsole": (("T_KO", T_KO),),
}

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
    # ein neu gebautes Bundle liegt als unversionierte Datei daneben: weg damit, das eingecheckte steht dann wieder
    subprocess.run(["git", "clean", "-fdq", "--", "src/bewerbungs_assistent/static/dashboard"], cwd=str(WT), capture_output=True, text=True)


def bundle_bauen() -> bool:
    """Baut das Frontend im Arbeitsbaum neu (Eintraege unter frontend/ — die Browser-Tests lesen das GEBAUTE Bundle)."""
    import shutil
    pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if not pnpm:
        return False
    r = subprocess.run([pnpm, "exec", "vite", "build"], cwd=str(WT / "frontend"), capture_output=True, text=True, timeout=900,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0


def _symlinks_moeglich() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        try:
            os.symlink(Path(t), Path(t) / "l", target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            return False


def main(argv=None) -> int:
    global WT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arbeitsbaum", required=True, help="ein eigener, sauberer git-Arbeitsbaum (nie der Arbeitsordner)")
    p.add_argument("--ergebnis", help="JSON-Datei fuer das Ergebnis (Vorgabe: neben dem Arbeitsbaum)")
    p.add_argument("--katalog", choices=("auto_update", "speicher", "komponenten", "mail", "firmen", "wege", "suche", "vorab", "konsole"), default="auto_update", help="welche Schutzpruefungen (Vorgabe: auto_update)")
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
        for name, tests in GRUNDLAEUFE[a.katalog]:
            code, fehl, sek, rest = pytest(tests)
            print(f"GRUNDLAUF {name}: {'gruen' if code == 0 else 'ROT'} ({sek}s) {fehl}", flush=True)
            if code != 0:
                print("Abbruch: der Grundlauf ist nicht gruen, ein roter Test sagt dann nichts.", rest)
                return 2
    for mid, text, datei, alt, neu, tests in KATALOGE[a.katalog]:
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
            if datei.startswith("frontend/") and not bundle_bauen():
                code, fehl, sek, rest = 2, [], 0, "Bundle liess sich nicht bauen (pnpm oder frontend/node_modules fehlt)"
            else:
                code, fehl, sek, rest = pytest(tests)
        finally:
            zuruecksetzen()
        urteil = "ERKANNT" if code == 1 else ("UEBERLEBT" if code == 0 else "FEHLERHAFT")
        ergebnisse[mid] = {"text": text, "urteil": urteil, "erster_roter_test": fehl[0][:200] if fehl else "", "sek": sek}
        print(f"{mid} [{urteil}] {text}  -> {fehl[0][7:120] if fehl else rest[:120]}  ({sek}s)", flush=True)
        ziel_json.write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1), encoding="utf-8")
    kein_symlink = set() if _symlinks_moeglich() else BRAUCHT_SYMLINKS
    offen = [k for k, v in ergebnisse.items() if v["urteil"] != "ERKANNT" and k not in AEQUIVALENT and k not in kein_symlink]
    gleichwertig = [k for k, v in ergebnisse.items() if v["urteil"] != "ERKANNT" and k in AEQUIVALENT]
    nicht_pruefbar = [k for k, v in ergebnisse.items() if v["urteil"] != "ERKANNT" and k in kein_symlink and k not in AEQUIVALENT]
    print(f"\nFERTIG: {len(ergebnisse)} Mutationen, {len(ergebnisse) - len(offen) - len(gleichwertig) - len(nicht_pruefbar)} erkannt, "
          f"gleichwertig begruendet: {gleichwertig}, hier nicht pruefbar (kein Symlink-Recht): {nicht_pruefbar}, OFFEN: {offen}", flush=True)
    return 1 if offen else 0


if __name__ == "__main__":
    sys.exit(main())
