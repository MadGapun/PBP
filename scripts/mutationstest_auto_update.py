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
`suche` (ein Klick auf einen Treffer der Suche oeffnet das Objekt: Adressen, Zuordnung, Lesestellen der Seiten; #1177) und
`browser` (Browser-Suchlauf: die Regel "im Zweifel eintragen" steht in jeder Anleitung, die Vorschau prueft wie die Anlage
und schreibt nichts; #1187) und
`jobtic` (Quelle mit Auflagen: PBP ruft nichts selbst ab, uebernimmt keine Kontaktdaten, die Karte sagt "Konto nötig"; #1189).

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

# ── Angaben aus Google Jobs und Aussortiertes beim Anlegen (#1184, B76) ──
T_GA = ["tests/test_v18_google_angaben_1184.py"]
GA = "src/bewerbungs_assistent/services/google_angaben.py"
SAE = "src/bewerbungs_assistent/services/stelle_aendern.py"

M_GOOGLE = [
    ("gj01", "Google-Karten: die Quelle google_jobs steht nicht mehr unter Vorbehalt", GA,
     'GOOGLE_QUELLEN = ("google_jobs", "jobspy_google")', 'GOOGLE_QUELLEN = ("jobspy_google",)', T_GA),
    ("gj02", "Google-Adresse: jeder Host mit „google.“ im Namen gilt als Google", GA,
     r'_GOOGLE_HOST = re.compile(r"(?:^|\.)google\.[a-z.]{2,}$")', r'_GOOGLE_HOST = re.compile(r"google\.[a-z.]{2,}")', T_GA),
    ("gj03", "Original gelesen: eine Google-Adresse, die keine Suche ist, gilt als Original", GA,
     '    if ist_google_adresse(u) or is_search_result_url(u):\n        return False\n',
     '    if is_search_result_url(u):\n        return False\n', T_GA),
    ("gj04", "Original gelesen: der Anzeigentext ist keine Bedingung mehr", GA,
     '    return len(str(beschreibung or "").strip()) >= MIN_BESCHREIBUNG\n', '    return True\n', T_GA),
    ("gj05", "Original gelesen: ein Text ohne http-Adresse gilt als Adresse", GA,
     '    if not u.lower().startswith(("http://", "https://")):\n        return False\n',
     '    if not u:\n        return False\n', T_GA),
    ("gj06", "Vorbehalt: gilt fuer jede Quelle, nicht nur fuer Google", GA,
     '    return ist_google_quelle(quelle) and not original_gelesen(url, beschreibung)\n',
     '    return not original_gelesen(url, beschreibung)\n', T_GA),
    ("gj07", "Remote aus dem Text: der Text entscheidet nichts mehr, es bleibt unbekannt", GA,
     '    return remote_jobspy.bestimmen(str(titel or ""), "", str(beschreibung or ""))\n', '    return "unbekannt"\n', T_GA),
    ("gj08", "Hinweis: auch ein unbekanntes Arbeitsmodell wird dem Anzeigentext zugeschrieben", GA,
     '"bestimmt_aus": "Anzeigentext" if gespeichert_remote != "unbekannt" else "nichts (der Text sagt dazu nichts)",',
     '"bestimmt_aus": "Anzeigentext",', T_GA),
    ("gj09", "Hinweis: die Entfernung gilt als gerechnet, obwohl sie es nicht ist", GA,
     '"entfernung": "nicht gerechnet"}', '"entfernung": "gerechnet"}', T_GA),
    ("gj10", "Anlegen: der Vorbehalt wird nie angewendet", JOBS,
     '        if _gangaben.unter_vorbehalt(quelle, url, beschreibung):\n', '        if False:\n', T_GA),
    ("gj11", "Anlegen: der Aufrufer-Wert fuer remote bleibt trotz Vorbehalt stehen", JOBS,
     '            google_vorbehalt = _gangaben.hinweis(remote, _remote_text, ort)\n            remote = _remote_text\n',
     '            google_vorbehalt = _gangaben.hinweis(remote, _remote_text, ort)\n', T_GA),
    ("gj12", "Anlegen: die Entfernung wird auch aus Googles Ort gerechnet", JOBS,
     '        if ort and not google_vorbehalt:\n', '        if ort:\n', T_GA),
    ("gj13", "Anlegen: die Warnung google_nur_kopfdaten fehlt", JOBS,
     '                ergebnis.setdefault("warnung", "google_nur_kopfdaten")\n', '                pass\n', T_GA),
    ("gj14", "Anlegen: der Block google_vorbehalt fehlt im Ergebnis", JOBS,
     '                ergebnis["google_vorbehalt"] = google_vorbehalt\n', '                pass\n', T_GA),
    ("gj15", "Anlegen: die Aussortierten werden gar nicht angesehen", JOBS,
     'firma, titel, ort, url, aussortierte_laden(db), kanon=kanon, own_hash=job_hash)',
     'firma, titel, ort, url, [], kanon=kanon, own_hash=job_hash)', T_GA),
    ("gj16", "Anlegen: aussortierte_dublette fehlt im Ergebnis", JOBS,
     '                ergebnis["aussortierte_dublette"] = aussortierte_dublette\n', '                pass\n', T_GA),
    ("gj17", "Hinweis auf Aussortiertes: die Aussortier-Gruende fehlen", JOBS,
     '                    "aussortiert_wegen": _gruende,\n', '                    "aussortiert_wegen": [],\n', T_GA),
    ("gj18", "Hinweis auf Aussortiertes: das Datum der Aussortierung fehlt", JOBS,
     '                    "aussortiert_am": str(_alt.get("dismissed_at") or "")[:10] or None,\n',
     '                    "aussortiert_am": None,\n', T_GA),
    ("gj19", "Datenbank: set_job_remote_level nimmt jeden Wert", DBF,
     '        if remote_level not in ("remote", "hybrid", "vor_ort", "unbekannt"):\n            return False\n',
     '        if not remote_level:\n            return False\n', T_GA),
    ("gj20", "Aussortiertes: ein gemeinsames Titelwort genuegt", DD,
     '_TITEL_ORT_MIN_GEMEINSAM = 2', '_TITEL_ORT_MIN_GEMEINSAM = 1', T_GA),
    ("gj21", "Aussortiertes: die Schwelle fuer die Titel-Aehnlichkeit entfaellt", DD,
     '_TITEL_ORT_SCHWELLE = 0.8', '_TITEL_ORT_SCHWELLE = 0.0', T_GA),
    ("gj22", "Aussortiertes: der Ort muss nicht passen", DD,
     '        if ort_schluessel(cand.get("location")) != mein_ort:\n            continue\n', '        pass\n', T_GA),
    ("gj23", "Aussortiertes: ohne Ort wird trotzdem verglichen (leer gleich leer)", DD,
     '    mein_ort = ort_schluessel(ort)\n    if not mein_ort:\n        return None\n', '    mein_ort = ort_schluessel(ort)\n', T_GA),
    ("gj24", "Ort-Schluessel: nach dem Komma folgt kein Abschneiden mehr", DD,
     r'    t = re.split(r"[,;/|]|\s[-–—]\s", t)[0]', '    t = t', T_GA),
    ("gj25", "Ort-Schluessel: „Remote“ gilt als Ort", DD,
     '    "remote", "homeoffice", "home office", "hybrid", "deutschland", "germany", "bundesweit", "deutschlandweit",\n',
     '    "homeoffice", "home office", "hybrid", "deutschland", "germany", "bundesweit", "deutschlandweit",\n', T_GA),
    ("gj26", "Aussortiertes: auch eine Suchadresse zaehlt als gleiche Anzeige", DD,
     '    vergleichs_url = str(url) if url and _stellen_url(str(url)) else ""\n', '    vergleichs_url = str(url) if url else ""\n', T_GA),
    ("gj27", "Aussortiertes: gleiche Firma und gleicher Titel werden nicht mehr gesucht", DD,
     '    treffer = find_duplicate_job(firma, titel, vergleichs_url, kandidaten, kanon=kanon)\n', '    treffer = None\n', T_GA),
    ("gj28", "Nachholen: auch eine Stelle ohne Vorbehalt wird neu bestimmt", SAE,
     '    if not google_angaben.unter_vorbehalt(vorher.get("source"), vorher.get("url"), vorher.get("description")):\n        return None\n',
     '    if not google_angaben.unter_vorbehalt(vorher.get("source"), vorher.get("url"), vorher.get("description")):\n        pass\n', T_GA),
    ("gj29", "Nachholen: schon die URL allein hebt den Vorbehalt auf", SAE,
     '    if google_angaben.unter_vorbehalt(jetzt.get("source"), jetzt.get("url"), jetzt.get("description")):\n        return None\n',
     '    if google_angaben.unter_vorbehalt(jetzt.get("source"), jetzt.get("url"), jetzt.get("description")):\n        pass\n', T_GA),
    ("gj30", "Nachholen: das Arbeitsmodell wird bestimmt, aber nicht gespeichert", SAE,
     '    if stufe != "unbekannt" and stufe != bisher and db.set_job_remote_level(job_hash, stufe):\n',
     '    if stufe != "unbekannt" and stufe != bisher and True:\n', T_GA),
    ("gj31", "Nachholen: eine vorhandene Entfernung wird ueberschrieben", SAE,
     '    if jetzt.get("distance_km") is None and str(jetzt.get("location") or "").strip():\n',
     '    if str(jetzt.get("location") or "").strip():\n', T_GA),
    ("gj32", "Nachholen: wird gar nicht aufgerufen", SAE,
     '    nachgeholt = _vorbehalt_aufheben(db, resolved, job) if updates else None\n', '    nachgeholt = None\n', T_GA),
    ("gj33", "Nachholen: der Score wird bei neuem Arbeitsmodell nicht neu gerechnet", SAE,
     '    if "description" in updates or "title" in updates or entfernung_geaendert or nachgeholt:\n',
     '    if "description" in updates or "title" in updates or entfernung_geaendert:\n', T_GA),
]

# ── Browser-Suchlauf: im Zweifel eintragen, Vorschau prueft wie die Anlage (#1187, B77) ──
T_BR = ["tests/test_v18_browser_im_zweifel_1187.py"]
BH = "src/bewerbungs_assistent/services/browser_handoff.py"
HO = "src/bewerbungs_assistent/job_scraper/handoff.py"
PRM = "src/bewerbungs_assistent/prompts.py"
LVO = "src/bewerbungs_assistent/job_scraper/linkedin_voyager.py"
WK = "src/bewerbungs_assistent/services/werkzeug_katalog.py"

M_BROWSER = [
    ("bw01", "Regel: eine Stelle zu viel ist nicht mehr besser als eine zu wenig", BH,
     'ist besser als eine zu wenig; ob sie taugt', 'ist schlechter als eine zu wenig; ob sie taugt', T_BR),
    ("bw02", "Regel: ob eine Stelle taugt, entscheidet nicht mehr der Mensch in PBP", BH,
     '"nicht du im Chat. Lege jede Stelle an,', '"und du im Chat. Lege jede Stelle an,', T_BR),
    ("bw03", "Regel: das Urteil geht nicht mehr an die Stelle, sondern in den Chat", BH,
     '"Stelle (stelle_urteil_speichern); in die Begründung', '"Stelle (im Chat); in die Begründung', T_BR),
    ("bw04", "Regel: der Vermerk, ob die Anzeige noch offen ist, faellt weg", BH,
     'Anzeige offen: ja, nein oder unklar', 'Anzeige offen', T_BR),
    ("bw05", "Regel: Aussortiertes wird nicht mehr zurueckgeholt, nur erwaehnt", BH,
     'hole sie mit stelle_reaktivieren zurück, statt sie nur im ', 'erwähne sie nur im Chat, statt sie nur im ', T_BR),
    ("bw06", "Regel: aussortiert wird, was dem Bearbeiter nicht gefaellt", BH,
     'Sortiere nur aus (stelle_einordnen), was offensichtlich fachfremd oder geschlossen ist, und nenne ',
     'Sortiere aus (stelle_einordnen), was dir nicht gefällt, und nenne ', T_BR),
    ("bw07", "Regel: der Bericht im Chat ersetzt die Eintraege wieder", BH,
     'den Grund. Der Bericht im Chat ersetzt die Einträge in PBP nicht.")', 'den Grund.")', T_BR),
    ("bw08", "Auftrag je Quelle: statt der Regel steht wieder 'passende Stellen'", BH,
     'f"- {REGEL_IM_ZWEIFEL}",', '"- Übernimm passende Stellen mit stelle_manuell_anlegen().",', T_BR),
    ("bw09", "Auftrag je Quelle: der Bericht nennt wieder 'verworfen' statt aussortiert und bekannt", BH,
     'bekannt, aussortiert mit Grund. Der Bericht ersetzt die Einträge nicht.",', 'bekannt, verworfen mit Grund.",', T_BR),
    ("bw10", "Auftrag je Quelle: der Volltext ist wieder nur eine Empfehlung", BH,
     'Der Titel allein sagt zu wenig über Systeme und ', 'Der Titel allein reicht meist, auch bei Systemen und ', T_BR),
    ("bw11", "Handoff einer einzelnen Quelle: ohne die Regel", HO,
     '"Duplikat-Erkennung laufen automatisch. " + REGEL_IM_ZWEIFEL', '"Duplikat-Erkennung laufen automatisch."', T_BR),
    ("bw12", "Handoff einer einzelnen Quelle: wieder 'passende Stellen'", HO,
     '"3. Alle Treffer, die fachlich passen oder nahezu passen, mit "', '"3. Passende Stellen mit "', T_BR),
    ("bw13", "Workflow-Prompt der Jobsuche: ohne die Regel", PRM,
     'stelle_manuell_anlegen() erfassen. {REGEL_IM_ZWEIFEL}', 'stelle_manuell_anlegen() erfassen.', T_BR),
    ("bw14", "Workflow-Prompt der Jobsuche: wieder 'passende Treffer'", PRM,
     'suchprofil_lesen(), alle Treffer, die fachlich passen oder nahezu passen, mit', 'suchprofil_lesen(), passende Treffer mit', T_BR),
    ("bw15", "Google-Jobs-Hinweis: ohne die Regel", JOBS,
     '"des Arbeitgebers und Anzeigentext) vorliegt. " + REGEL_IM_ZWEIFEL', '"des Arbeitgebers und Anzeigentext) vorliegt."', T_BR),
    ("bw16", "LinkedIn-Plan: das Feld regel ist leer", JOBS,
     '"regel": REGEL_IM_ZWEIFEL,', '"regel": "",', T_BR),
    ("bw17", "LinkedIn-Plan: der Vorfilter urteilt wieder mit", JOBS,
     '"urteilt nicht: im Zweifel holen.",', '"urteilt: was nicht passt, fällt weg.",', T_BR),
    ("bw18", "LinkedIn-Plan: die Vorschau (dry_run=True) kommt im Ablauf nicht mehr vor", JOBS,
     '"als Vorschau (dry_run=True, dieselben Prüfungen wie der "', '"als Vorschau (dieselben Prüfungen wie der "', T_BR),
    ("bw19", "Katalogtext von stelle_manuell_anlegen: wieder 'nicht fuer Treffer aus einer Jobboerse'", WK,
     '"Auch für Treffer aus dem Browserlauf: im Zweifel eintragen. Was "', '"Nicht für Treffer aus einer Jobbörse; die legt die Suche selbst an. Was "', T_BR),
    ("bw20", "Hinweis zur aussortierten Dublette: das Urteil geht in den Chat", JOBS,
     'an die Stelle (stelle_urteil_speichern): ob sie taugt, "', 'an die Stelle (im Chat): ob sie taugt, "', T_BR),
    ("bw21", "Vorschau: die Blacklist-Abweisung wird auch in der Vorschau protokolliert", JOBS,
     '            if not trocken:     # #1187: die Vorschau schreibt auch kein Protokoll\n', '            if True:\n', T_BR),
    ("bw22", "Vorschau: die Anlage laeuft trotz Vorschau weiter (sie schreibt)", JOBS,
     '        if trocken:\n            # #1187: die Vorschau fragt dasselbe wie die Anlage', '        if False:\n            # #1187: die Vorschau fragt dasselbe wie die Anlage', T_BR),
    ("bw23", "Vorschau: die Sammeluebernahme ruft nie trocken auf", JOBS,
     '                trocken=dry_run)   # #1187: die Vorschau prueft wie der echte Lauf\n', '                trocken=False)\n', T_BR),
    ("bw24", "Vorschau: 'wuerde_angelegt' zaehlt nicht als angelegt", JOBS,
     'if res.get("status") in ("angelegt", "wuerde_angelegt") or (', 'if res.get("status") == "angelegt" or (', T_BR),
    ("bw25", "Vorschau: dieselbe Stelle zweimal im Aufruf zaehlt zweimal", JOBS,
     '                if res["hash"] in vorschau_hashes:\n', '                if False:\n', T_BR),
    ("bw26", "Vorschau: die Laenge des Volltexts fehlt", JOBS,
     '                    _eintrag["beschreibung_zeichen"] = len(beschreibung)\n', '                    pass\n', T_BR),
    ("bw27", "Vorschau: die Hinweise der Pruefungen fehlen", JOBS,
     '            _befunde_anfuegen(vorschau)\n', '            pass\n', T_BR),
    ("bw28", "Vorschau: der Hash der Stelle fehlt", JOBS,
     '                "id": _kurz(job_hash), "hash": job_hash,\n                "nachricht": f"Vorschau:',
     '                "id": _kurz(job_hash), "hash": "",\n                "nachricht": f"Vorschau:', T_BR),
    ("bw29", "Sammeluebernahme: die aussortierte Dublette erscheint nicht im Eintrag", JOBS,
     '                        ("aussortierte_dublette", "aussortierte_dublette"),\n', '', T_BR),
    ("bw30", "Trichter-Zeile: 'schon aussortiert' fehlt", LVO,
     '        ("aussortierte_dublette", "schon aussortiert"),\n', '', T_BR),
]

# ── jobtic: Quelle mit Auflagen - PBP ruft nichts selbst ab, keine Kontaktdaten, "Konto nötig" (#1189, B78) ──
T_JT = ["tests/test_v18_jobtic_1189.py"]
REG_JT = "src/bewerbungs_assistent/job_scraper/__init__.py"
AUF_JT = "src/bewerbungs_assistent/services/quellen_auflagen.py"
NACH_JT = "src/bewerbungs_assistent/services/nachladen.py"
UH_JT = "src/bewerbungs_assistent/services/url_health.py"
TN_JT = "src/bewerbungs_assistent/services/text_nachzug.py"
UTS_JT = "src/bewerbungs_assistent/services/url_to_source.py"
SS_JT = "src/bewerbungs_assistent/services/search_service.py"
JS_JT = "src/bewerbungs_assistent/job_scraper/jobtic_extraction.js"
T_JTP = ["tests/test_v18_jobtic_pruefung_1189.py"]
TOOLS_JT = "src/bewerbungs_assistent/tools/jobs.py"
HANDOFF_JT = "src/bewerbungs_assistent/job_scraper/handoff.py"
JSTART_JT = "src/bewerbungs_assistent/services/jobsuche_start.py"
DD_JT = "src/bewerbungs_assistent/duplicate_detection.py"
DASH_JT = "src/bewerbungs_assistent/dashboard.py"

M_JOBTIC = [
    ("jt01", "Verzeichnis: die Quelle traegt kein Kennzeichen 'Konto noetig' mehr", REG_JT,
     '        "konto_noetig": True,\n', '        "konto_noetig": False,\n', T_JT),
    ("jt02", "Verzeichnis: jobtic verlangt den Login-Knopf des alten Weges", REG_JT,
     '        "login_erforderlich": False,\n        "konto_noetig": True,\n',
     '        "login_erforderlich": True,\n        "konto_noetig": True,\n', T_JT),
    ("jt03", "Verzeichnis: der automatische Abruf ist erlaubt", REG_JT,
     '            "kein_automatischer_abruf": True,\n', '            "kein_automatischer_abruf": False,\n', T_JT),
    ("jt04", "Verzeichnis: Kontaktdaten aus dem Lauf werden uebernommen", REG_JT,
     '            "keine_kontaktdaten": True,\n', '            "keine_kontaktdaten": False,\n', T_JT),
    ("jt05", "Verzeichnis: die Stellenart ist keine Vorgabe mehr (Freelance)", REG_JT,
     '            "stellenart": "freelance",\n', '            "stellenart": "festanstellung",\n', T_JT),
    ("jt06", "Verzeichnis: die Adresse zum Konto zeigt auf die Startseite", REG_JT,
     '        "konto_url": "https://jobtic.com/register",\n', '        "konto_url": "https://jobtic.com/",\n', T_JT),
    ("jt07", "Verzeichnis: jobtic gilt als automatische Quelle", REG_JT,
     '        "konto_noetig": True,\n        "zugriffsart": "browser_login",\n',
     '        "konto_noetig": True,\n        "zugriffsart": "api",\n', T_JT),
    ("jt08", "Auflagen: die Adresse entscheidet nicht mit", AUF_JT,
     '    if url:\n        from .url_to_source import detect_source_from_url\n',
     '    if False:\n        from .url_to_source import detect_source_from_url\n', T_JT),
    ("jt09", "Auflagen: die genannte Quelle zaehlt nicht", AUF_JT,
     '    schluessel = [str(quelle or "").strip().lower()]\n', '    schluessel = []\n', T_JT),
    ("jt10", "Auflagen: die SQL-Bedingung kennt keinen Host", AUF_JT,
     '            muster.extend(hosts_von(key))\n', '            pass\n', T_JT),
    ("jt11", "Auflagen: keine Quelle hat je eine", AUF_JT,
     '        if isinstance(gefunden, dict) and gefunden:\n            return gefunden\n',
     '        if False:\n            return gefunden\n', T_JT),
    ("jt12", "Nachladen: die Sperre greift nicht, PBP ruft die Seite ab", NACH_JT,
     '    if kein_automatischer_abruf(url=url):\n        return Befund(status=NICHT_AUTOMATISCH, quelle="auflage",\n',
     '    if False:\n        return Befund(status=NICHT_AUTOMATISCH, quelle="auflage",\n', T_JT),
    ("jt13", "Nachladen: der Befund 'nicht automatisch' fehlt in der Bilanz", NACH_JT,
     'BEFUNDE = (GELESEN, WEG, GEBLOCKT, LEBT_UNLESBAR, FEHLER, NICHT_AUTOMATISCH)\n',
     'BEFUNDE = (GELESEN, WEG, GEBLOCKT, LEBT_UNLESBAR, FEHLER)\n', T_JT),
    ("jt14", "URL-Check: die Sperre greift nicht, PBP ruft die Seite ab", UH_JT,
     '    if kein_automatischer_abruf(url=url):\n        return HealthResult(status=HealthStatus.NICHT_GEPRUEFT,\n',
     '    if False:\n        return HealthResult(status=HealthStatus.NICHT_GEPRUEFT,\n', T_JT),
    ("jt15", "URL-Check: 'nicht geprueft' gilt als abgelaufen und sortiert die Stelle aus", UH_JT,
     '        return HealthResult(status=HealthStatus.NICHT_GEPRUEFT,\n',
     '        return HealthResult(status=HealthStatus.EXPIRED,\n', T_JT),
    ("jt16", "Bestands-Nachzug: eine jobtic-Stelle bleibt Kandidat und zaehlt Fehlversuche", TN_JT,
     '            if kein_automatischer_abruf(url=z["url"]):\n                continue\n',
     '            if False:\n                continue\n', T_JT),
    ("jt17", "Auto-Nachladen: die Auswahl kennt die Auflage nicht", DASH,
     '    _ohne, _ohne_params = sql_ohne_abruf("url")\n    rows = conn.execute(\n        "SELECT hash FROM jobs "\n',
     '    _ohne, _ohne_params = "", []\n    rows = conn.execute(\n        "SELECT hash FROM jobs "\n', T_JT),
    ("jt18", "Aging-Check: die Auswahl kennt die Auflage nicht", DASH,
     '    _ohne, _ohne_params = sql_ohne_abruf("url")\n    rows = conn.execute(\n        "SELECT hash, url, title FROM jobs "\n',
     '    _ohne, _ohne_params = "", []\n    rows = conn.execute(\n        "SELECT hash, url, title FROM jobs "\n', T_JT),
    ("jt19", "Anlage: Ansprechpartner aus jobtic werden uebernommen", JOBS,
     '        if _aufl.get("keine_kontaktdaten") and (kontakt_name or kontakt_email or kontakt_telefon):\n',
     '        if False and (kontakt_name or kontakt_email or kontakt_telefon):\n', T_JT),
    ("jt20", "Anlage: die Stellenart ist keine Vorgabe der Quelle", JOBS,
     '        if _aufl.get("stellenart") and stellenart == "festanstellung":\n', '        if False:\n', T_JT),
    ("jt21", "Anlage: das Ergebnis verschweigt, dass der Kontakt fehlt", JOBS,
     '                ergebnis["kontakt_nicht_uebernommen"] = kontakt_verworfen\n', '                pass\n', T_JT),
    ("jt22", "Anlage: die Adresse zaehlt bei der Auflage nicht (falsch gesetzte Quelle)", JOBS,
     '        _aufl = _auflagen.auflagen(quelle, url)\n', '        _aufl = _auflagen.auflagen(quelle, "")\n', T_JT),
    ("jt23", "Qualitaetspruefung: eine nicht gepruefte Adresse zaehlt als in Ordnung", JOBS,
     '                        kategorie.append("url_nicht_geprueft")\n', '                        pass\n', T_JT),
    ("jt24", "Handoff: die Such-URL filtert nicht nach dem Begriff", HO,
     '    "jobtic": "https://jobtic.com/search?type=projects&q={keyword}",\n',
     '    "jobtic": "https://jobtic.com/search?type=projects",\n', T_JT),
    ("jt25", "Handoff: jobtic bekommt das generische statt des eigenen Skripts", HO,
     '    "jobtic": "jobtic_extraction.js",\n', '    "jobtic": "",\n', T_JT),
    ("jt26", "Handoff: die Auflagen fehlen in der Anleitung", HO,
     '        "anleitung": anleitung + (" " + auflagen if auflagen else ""),\n', '        "anleitung": anleitung,\n', T_JT),
    ("jt27", "Handoff: die Anleitung spricht wieder vom 'Umgehen von Bot-Blockern'", HO,
     '    schritt_1 = ("1. URL im eigenen, angemeldeten Chrome mit Claude-in-Chrome öffnen. " if auflagen\n',
     '    schritt_1 = ("1. URL im eigenen, angemeldeten Chrome mit Claude-in-Chrome öffnen. " if False\n', T_JT),
    ("jt28", "Auftrag je Quelle: die Auflagen werden nicht in den Eintrag gelesen", BH,
     '            "auflagen": str((info.get("auflagen") or {}).get("hinweis") or ""),\n', '            "auflagen": "",\n', T_JT),
    ("jt29", "Auftrag je Quelle: die Auflagen stehen nicht im Text", BH,
     '        if e.get("auflagen"):\n            zeilen.append(f"   {e[\'auflagen\']}")\n',
     '        if False:\n            zeilen.append(f"   {e[\'auflagen\']}")\n', T_JT),
    ("jt30", "Adresse: jobtic.com wird keiner Quelle zugeordnet", UTS_JT,
     '    ("jobtic.com", "jobtic"),\n', '', T_JT),
    ("jt31", "Dashboard-Zeile: das Kennzeichen 'Konto noetig' kommt nicht an", SS_JT,
     '            "konto_noetig": bool(info.get("konto_noetig", False)),\n', '            "konto_noetig": False,\n', T_JT),
    ("jt32", "Skript: E-Mail-Adressen im Kartentext bleiben stehen", JS_JT,
     r"    .replace(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, '[Adresse entfernt]')" + "\n", '', T_JT),
    ("jt33", "Skript: der Kartentext wird ohne die Kontaktbereinigung uebernommen", JS_JT,
     "    if (href) karten[href.split('?')[0]] = ohneKontakt(text(karte)).slice(0, 600);\n",
     "    if (href) karten[href.split('?')[0]] = text(karte).slice(0, 600);\n", T_JT),
    ("jt34", "Skript: auch Profile und Navigation gelten als Projekte", JS_JT,
     r"    if (!/\/project\/[a-z0-9]+/i.test(link) || !titel) continue;" + "\n", "    if (!titel) continue;\n", T_JT),
    ("jt35", "Skript: eine leere Liste meldet keinen Fehler", JS_JT,
     "  if (!jobs.length) {\n", "  if (false) {\n", T_JT),
    # --- Funde des unabhaengigen Pruefers am Kandidaten (11.10.2026) ---
    ("jt36", "Anlage: Mailadressen und Rufnummern bleiben im Text", TOOLS_JT,
     "            beschreibung, _gestrichen = _auflagen.kontaktdaten_entfernen(beschreibung)\n",
     "            _gestrichen = 0\n", T_JTP),
    ("jt37", "Bearbeiten: Mailadressen und Rufnummern bleiben im Text", TOOLS_JT,
     "                beschreibung, kontakt_aus_text = _auflagen_sb.kontaktdaten_entfernen(beschreibung)\n",
     "                kontakt_aus_text = 0\n", T_JTP),
    ("jt38", "Handoff: eine eigene Quelle auf einer jobtic-Adresse gilt nicht wie jobtic", HANDOFF_JT,
     '        if erkannt != "manuell":\n            wirksam = erkannt\n', '        if False:\n            wirksam = erkannt\n', T_JTP),
    ("jt39", "Gesundheitslauf: die eigene jobtic-Quelle wird angefragt", TOOLS_JT,
     '                    if _kein_abruf(url=c["url"]):\n', "                    if False:\n", T_JTP),
    ("jt40", "Suchstart: nur_auf_wunsch wird nicht genannt", JSTART_JT,
     "    auf_wunsch = [q for q in manuelle if _nur_auf_wunsch(q)]\n", "    auf_wunsch = []\n", T_JTP),
    ("jt41", "Dublettenerkennung: ein Platzhalter gilt auf beiden Seiten als dieselbe Firma", DD_JT,
     '    return normalize_company_name(name) if benennt_arbeitgeber(name) else ""\n',
     "    return normalize_company_name(name)\n", T_JTP),
    ("jt42", "Stellen-Schluessel: ohne Adresse, wenn die Firma ein Platzhalter ist", TOOLS_JT,
     "        if url and not _benennt(firma):\n", "        if False:\n", T_JTP),
    ("jt43", "Bestandsnachzug: Stellen ohne erlaubten Abruf kommen in die Auswahl", TOOLS_JT,
     "        fehlend = [j for j in aktive_abrufbar if _fehlt(j)]\n", "        fehlend = [j for j in aktive if _fehlt(j)]\n", T_JTP),
    ("jt44", "Dashboard-Knopf: das Abrufverbot zaehlt als Fehlversuch", DASH_JT,
     "    if befund.status == nachladen.NICHT_AUTOMATISCH:\n", "    if False:\n", T_JTP),
    ("jt45", "Zuordnung: Port und Zugangsdaten gehoeren nicht zum Host", UTS_JT,
     '        host = (parsed.hostname or "").lower().rstrip(".")\n', '        host = (parsed.netloc or "").lower()\n', T_JTP),
    ("jt46", "Hilfe: Mailadressen werden nicht erkannt", AUF_JT,
     "    bereinigt = _MAILADRESSE.sub(_ersetzen, text)\n", "    bereinigt = text\n", T_JTP),
    ("jt47", "Hilfe: Rufnummern werden nicht erkannt", AUF_JT,
     "    bereinigt = _RUFNUMMER.sub(_ersetzen, bereinigt)\n", "", T_JTP),
    ("jt48", "Hilfe: jede Zahlenfolge mit Trennzeichen gilt als Rufnummer", AUF_JT,
     r'    r"|(?<![\w.])0\d{2,5}[\s/-]+\d[\d\s/-]{3,}\d(?![\w])"' + "\n",
     r'    r"|(?<![\w.])\d{2,5}[\s/-]+\d[\d\s/-]{3,}\d(?![\w])"' + "\n", T_JTP),
    ("jt49", "Hilfe: ein Platzhalter benennt einen Arbeitgeber", "src/bewerbungs_assistent/duplicate_detection.py",
     "        return bool(normalize_company(str(name)))\n", "        return True\n", T_JTP),
]

# ── Skill-Stand in der Profil-Zusammenfassung (#1190, H39) ──
T_SK = ["tests/test_v18_skill_stand_1190.py"]
PS = "src/bewerbungs_assistent/services/profile_service.py"
TP = "src/bewerbungs_assistent/tools/profil.py"

M_SKILL = [
    ("sk01", "Das heutige Niveau (level_current) wird nicht gelesen", PS,
     '    aktuell = _jahr_oder_stufe(s.get("level_current"))\n', '    aktuell = None\n', T_SK),
    ("sk02", "Ruht ohne eingetragenes Niveau: die Spitze gilt als Stand von heute", PS,
     '    if aktuell is None and ende is None:\n        aktuell = spitze', '    if aktuell is None:\n        aktuell = spitze', T_SK),
    ("sk03", "ruht: ein gesetztes Ende zaehlt nicht", PS,
     '    ruht = ende is not None or (aktuell is not None and spitze is not None and aktuell < spitze)\n',
     '    ruht = aktuell is not None and spitze is not None and aktuell < spitze\n', T_SK),
    ("sk04", "ruht: ein abgesenktes Niveau ohne Ende gilt nicht als ruhend", PS,
     '    ruht = ende is not None or (aktuell is not None and spitze is not None and aktuell < spitze)\n',
     '    ruht = ende is not None\n', T_SK),
    ("sk05", "Zeitraum: das Ende fehlt in der Antwort", PS, '        "bis": ende,\n', '        "bis": None,\n', T_SK),
    ("sk06", "Stand-Text: nennt nur die Spitze, nicht den aktuellen Stand", PS,
     '        teile.append(f"aktuell Lv.{aktuell}")\n        teile.append(f"Spitze Lv.{spitze}")\n',
     '        teile.append(f"Lv.{spitze}")\n', T_SK),
    ("sk07", "Liste: das mehrdeutige Feld level steht wieder darin", TP,
     '"kategorie": s.get("category"), **skill_stand(s)}', '"kategorie": s.get("category"), "level": s.get("level"), **skill_stand(s)}', T_SK),
    ("sk08", "Text der Zusammenfassung: wieder nur die Spitze", TP,
     "f\"{s['name']} ({skill_stand(s)['stand'] or 'Lv.?'}) [{s.get('id', '?')}]\"",
     "f\"{s['name']} (Lv.{s.get('level', '?')}) [{s.get('id', '?')}]\"", T_SK),
    ("sk09", "bereits vorhanden: nennt wieder nur die Spitze als level", TP,
     '                      **skill_stand(vorhanden)},\n', '                      "level": vorhanden.get("level")},\n', T_SK),
    ("sk10", "Zahlen: ein Wahrheitswert gilt als Stufe", PS,
     '    if isinstance(wert, bool):\n        return None\n', '', T_SK),
    ("sk11", "Zahlen: eine Null gilt als Jahr oder Stufe", PS,
     '    return zahl if zahl is not None and zahl > 0 else None\n', '    return zahl\n', T_SK),
]

# ── Installer-Reste: leerer Ordner, altes Dashboard-Fenster, Temp-Dateien (#1170 PP20, PP21, PP23) ──
T_IN = ["tests/test_v18_installer_reste_1170.py"]
T_IPP = ["tests/test_v18_installer_reste_pp24_pp25.py"]

M_INSTALLER = [
    ("in01", "Der Installer beendet das alte Dashboard-Fenster nicht mit", "INSTALLIEREN.bat",
     " -or ($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'Dashboard starten\\.bat') }", " }", T_IN),
    ("in02", "Der Prozessfilter trifft jedes cmd-Fenster", "INSTALLIEREN.bat",
     "$_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'Dashboard starten\\.bat'", "$_.Name -eq 'cmd.exe'", T_IN),
    ("in03", "Das Dashboard-Fenster erbt wieder den Arbeitsordner des Installers", "INSTALLIEREN.bat",
     'start "PBP-Dashboard" /MIN /D "%APP_DIR%" "%APP_DIR%\\Dashboard starten.bat"', 'start "PBP-Dashboard" /MIN "%APP_DIR%\\Dashboard starten.bat"', T_IN),
    ("in04", "Der Selbsttest laesst sein Datenverzeichnis liegen", "_selftest.py",
     "    if os.path.isdir(d):\n", "    if False:\n", T_IN),
    ("in05", "Die Kopie des Aufraeum-Helfers bleibt liegen", "_installer_aufraeumen.py",
     '        if Path(__file__).name == "pbp_installer_aufraeumen.py":\n', "        if False:\n", T_IN),
    ("in06", "Der Aufraeum-Helfer des Selbsttests erbt den Arbeitsordner und haelt den entpackten Ordner fest", "_selftest.py",
     "close_fds=True, cwd=tempfile.gettempdir(),\n", "close_fds=True,\n", T_IN),
    # PP24 (Testlauf 11.10.2026): der Helfer starb am ersten PermissionError beim gehaltenen Ordner
    ("in07", "Der Durchgang laesst den Fehler eines gehaltenen Ordners durchschlagen", "_installer_aufraeumen.py",
     "        try:\n            shutil.rmtree(ordner, onerror=_freigeben)\n        except OSError:\n            pass\n",
     "        shutil.rmtree(ordner, onerror=_freigeben)\n", T_IPP),
    ("in08", "Die Rueckruffunktion faengt den zweiten Fehlschlag nicht", "_installer_aufraeumen.py",
     "    except Exception:  # noqa: BLE001 -- ein Fehlschlag hier ist ein Grund zu warten, kein Grund zu sterben\n",
     "    except KeyboardInterrupt:\n", T_IPP),
    ("in14", "Die Rueckruffunktion nimmt einem Ordner unter POSIX das Lesen (chmod 0o200)", "_installer_aufraeumen.py",
     "        os.chmod(pfad, stat.S_IRWXU if os.path.isdir(pfad) else stat.S_IREAD | stat.S_IWRITE)\n",
     "        os.chmod(pfad, stat.S_IWRITE)\n", T_IPP),
    # PP25: get-pip.py liess pip.zip im gemeinsamen Temp-Ordner liegen
    ("in09", "get-pip arbeitet wieder im gemeinsamen Temp-Ordner", "INSTALLIEREN.bat",
     'set "TEMP=!PIP_TMP!"\nset "TMP=!PIP_TMP!"\n', "", T_IPP),
    ("in10", "Der eigene Temp-Ordner von get-pip wird nach dem Lauf nicht geloescht", "INSTALLIEREN.bat",
     'set "TMP=!PIP_TMP_VORHER!"\nrmdir /s /q "!PIP_TMP!" >nul 2>&1\nexit /b !PIP_RC!\n',
     'set "TMP=!PIP_TMP_VORHER!"\nexit /b !PIP_RC!\n', T_IPP),
    ("in11", "TEMP und TMP bleiben nach get-pip umgebogen", "INSTALLIEREN.bat",
     'set "TEMP=!PIP_TEMP_VORHER!"\nset "TMP=!PIP_TMP_VORHER!"\n', "", T_IPP),
    ("in12", "Der Exitcode von get-pip geht verloren", "INSTALLIEREN.bat",
     "exit /b !PIP_RC!\n", "exit /b 0\n", T_IPP),
    ("in13", ":fix_pip ruft get-pip wieder direkt auf", "INSTALLIEREN.bat",
     'curl.exe -sL -o "!GETPIP_PATH!" "%GETPIP_URL%" 2>> "%LOGFILE%"\ncall :pip_beschaffen\ngoto :eof\n',
     'curl.exe -sL -o "!GETPIP_PATH!" "%GETPIP_URL%" 2>> "%LOGFILE%"\n"%PYTHON%" "!GETPIP_PATH!" --no-warn-script-location -q >> "%LOGFILE%" 2>&1\ngoto :eof\n',
     T_IPP),
]

# ── Erste Schritte: was ein Mensch ohne Profil sieht und anklickt (#1170 U5-U9, U13, U14, U18; G83) ──
T_ES = ["tests/test_v18_erste_schritte_1170.py"]
FE = "frontend/src/"
LB = "src/bewerbungs_assistent/services/loeschbereiche.py"

M_ERSTE = [
    ("es01", "Stellen ohne Profil: die Seite zeigt wieder Kennzahlen, Filter und Quellenkarte", FE + "pages/JobsPage.jsx",
     '  // U6 (#1170): ohne Profil EINE Karte mit EINEM Knopf — keine Kennzahlen aus Nullen, keine Filter, keine Quellenkarte.\n  if (!chrome.status?.has_profile) {',
     '  // U6 (#1170): ohne Profil EINE Karte mit EINEM Knopf — keine Kennzahlen aus Nullen, keine Filter, keine Quellenkarte.\n  if (false) {', T_ES),
    ("es02", "Bewerbungen ohne Profil: die Seite zeigt wieder Kennzahlen, Filter und Knöpfe ohne Wirkung", FE + "pages/ApplicationsPage.jsx",
     '  // U6 (#1170): ohne Profil EINE Karte mit EINEM Knopf — nicht zweimal "Zuerst dein Profil" zwischen Kennzahlen, Filtern und\n'
     '  // Knöpfen („CV als DOCX“, „Bewerbung anlegen“), die ohne Profil nichts tun können.\n  if (!chrome.status?.has_profile) {',
     '  // U6 (#1170): ohne Profil EINE Karte mit EINEM Knopf — nicht zweimal "Zuerst dein Profil" zwischen Kennzahlen, Filtern und\n'
     '  // Knöpfen („CV als DOCX“, „Bewerbung anlegen“), die ohne Profil nichts tun können.\n  if (false) {', T_ES),
    ("es03", "Suche & Bewertung ohne Profil heißt wieder „Profil“", FE + "pages/ProfilePage.jsx",
     'title={zeigeSuche ? "Suche & Bewertung" : "Profil"}', 'title="Profil"', T_ES),
    ("es04", "Der Knopf der Karte öffnet nichts", FE + "components/ZuerstProfil.jsx",
     '            <Button onClick={openCreateProfileModal}>\n', '            <Button onClick={() => {}}>\n', T_ES),
    ("es05", "Der erste Dialog heißt immer „Neues Profil anlegen“", FE + "App.jsx",
     'title={chrome.status?.has_profile ? "Neues Profil anlegen" : "Dein Profil anlegen"}', 'title="Neues Profil anlegen"', T_ES),
    ("es06", "Der erste Dialog fragt wieder nach einem „Profilname“", FE + "App.jsx",
     '<Field label={chrome.status?.has_profile ? "Profilname" : "Dein Name"}>', '<Field label="Profilname">', T_ES),
    ("es07", "Dashboard: der Knopf führt wieder auf die Profilseite", FE + "pages/DashboardPage.jsx",
     '                    <Button onClick={openCreateProfileModal}>\n                      <Upload size={15} />',
     '                    <Button onClick={() => navigateTo("profil", { composer: "document" })}>\n                      <Upload size={15} />', T_ES),
    ("es08", "Aufgaben: die leere Seite erklärt wieder nichts", FE + "pages/TasksPage.jsx",
     'Aufgaben entstehen aus deinen Bewerbungen (etwa die Nachfassung', 'Entweder ist alles erledigt (etwa die Nachfassung', T_ES),
    ("es09", "Aufgaben: „Neue Aufgabe“ ist wieder blass", FE + "pages/TasksPage.jsx",
     '<Button size="sm" onClick={() => setNeuOffen((v) => !v)}>', '<Button size="sm" className="bg-teal/20" onClick={() => setNeuOffen((v) => !v)}>', T_ES),
    ("es10", "Statistiken: ohne Daten kommt wieder die Wand aus Nullen", FE + "pages/StatsPage.jsx",
     '{!hasData && !(Number(totals.jobs_ever) > 0 || Number(appStats.total) > 0) ? (', '{!hasData && !extended ? (', T_ES),
    ("es11", "Statistiken: die Beschriftung ist wieder zu weit gesetzt", FE + "pages/StatsPage.jsx",
     'className="break-words text-xs uppercase tracking-[0.06em] text-muted">{label}</p>',
     'className="text-xs uppercase tracking-[0.12em] text-muted">{label}</p>', T_ES),
    ("es12", "Statistiken: drei Kacheln nebeneinander schon ab xl", FE + "pages/StatsPage.jsx",
     'className="grid gap-6 lg:grid-cols-2 2xl:grid-cols-3"', 'className="grid gap-6 xl:grid-cols-3"', T_ES),
    ("es13", "Gefahrenzone: mitgelieferte Vorgaben werden nie erkannt", LB,
     '    if not eintrag or eintrag[0] not in _spalten(db, tabelle):\n        return None\n', '    return None\n', T_ES),
    ("es14", "Leeren: das Ergebnis zählt die Vorgaben wieder mit", LB,
     '                if cur.rowcount - vorgaben_n:\n                    geloescht[t] = cur.rowcount - vorgaben_n\n',
     '                if cur.rowcount:\n                    geloescht[t] = cur.rowcount\n', T_ES),
    ("es15", "Gefahrenzone: die Regler zählen wieder als Daten", LB,
     '"scoring_config": ("set_by_user", "COALESCE(set_by_user, 0) = 0"),', '"scoring_config": ("set_by_user", "1 = 0"),', T_ES),
    ("es16", "Prüfer: Text neben einem Ausdruck wird nicht gelesen", "scripts/ui_texte_pruefen.py",
     '    for m in _TEXTKNOTEN_AUSDRUCK.finditer(code):\n', '    for m in []:\n', T_ES),
    ("es17", "Prüfer: Zeichenketten werden wieder über die ganze Datei gepaart", "scripts/ui_texte_pruefen.py",
     '    for nr, zeile in enumerate(code.split("\\n"), 1):\n        for m in _LITERAL_ZEILE.finditer(zeile):',
     '    for nr, zeile in enumerate([], 1):\n        for m in _LITERAL_ZEILE.finditer(zeile):', T_ES),
    ("es18", "Gefahrenzone: der Hinweis auf mitgelieferte Vorgaben fehlt", FE + "pages/SettingsPage.jsx",
     'ohne {info.vorgaben} mitgelieferte Vorgaben', 'ohne {info.vorgaben} Eintraege', T_ES),
    ("es19", "Gefahrenzone: „Datensaetze“ ohne Umlaut", FE + "pages/SettingsPage.jsx",
     '{info.zeilen_gesamt ?? 0} Datensätze', '{info.zeilen_gesamt ?? 0} Datensaetze', T_ES),
    ("es20", "Kontakte: die Knöpfe der Kontaktliste stehen auch im Reiter Firmen", FE + "pages/ContactsPage.jsx",
     '        {ansicht === "kontakte" ? (\n        <div className="flex items-center gap-2">', '        {true ? (\n        <div className="flex items-center gap-2">', T_ES),
    ("es21", "Speicher: Aufräumen ist auch dort klickbar, wo nichts liegt", FE + "components/SpeicherTab.jsx",
     'Boolean(daten.laufende_arbeit?.length) || nichtsDa}', 'Boolean(daten.laufende_arbeit?.length)}', T_ES),
    ("es22", "Prüfer: jedes Textstück steht doppelt da (die Suchläufe überlappen)", "scripts/ui_texte_pruefen.py",
     "        if eintrag not in gesehen:\n", "        if True:\n", T_ES),
    ("es23", "Stellen: während der Status lädt, steht „Zuerst dein Profil“ da", FE + "pages/JobsPage.jsx",
     '  if (chrome.loading) return <LoadingPanel label="Stellen werden geladen..." />;\n', '', T_ES),
    ("es24", "Bewerbungen: während der Status lädt, steht „Zuerst dein Profil“ da", FE + "pages/ApplicationsPage.jsx",
     '  if (chrome.loading) return <LoadingPanel label="Bewerbungen werden geladen..." />;\n', '', T_ES),
    ("es25", "Profil und Suche: während der Status lädt, steht „Zuerst dein Profil“ da", FE + "pages/ProfilePage.jsx",
     '  if (loading || chrome.loading) return <LoadingPanel label="Profil wird geladen..." />;\n',
     '  if (loading) return <LoadingPanel label="Profil wird geladen..." />;\n', T_ES),
]

# ── Texterkennung ohne Administratorrechte (PP26, Testlauf 11.10.2026; Beta-Exit 3) ──
T_TE = ["tests/test_v18_texterkennung_ohne_admin_pp26.py"]
COMP_TE = "src/bewerbungs_assistent/services/components.py"

M_TESSERACT = [
    ("te01", "Das Setup startet wieder ohne die Umgebung RunAsInvoker", COMP_TE,
     "                    env=_setup_umgebung(), **_SUBPROCESS_FLAGS,\n", "                    **_SUBPROCESS_FLAGS,\n", T_TE),
    ("te02", "RunAsInvoker wird nie gesetzt", COMP_TE,
     '        if "RunAsInvoker" not in schichten:\n            schichten.append("RunAsInvoker")\n', "        pass\n", T_TE),
    ("te03", "WinError 740 wird als roher Text durchgereicht", COMP_TE,
     '                if getattr(exc, "winerror", None) == 740:\n', "                if False:\n", T_TE),
    ("te04", "Der Ort 'nur fuer mich' wird nach dem Setup nicht gesucht", COMP_TE,
     "            gefunden = find_component_binary(db, name)\n            if gefunden and Path(gefunden).is_file():\n                binary = Path(gefunden)\n",
     "            pass\n", T_TE),
    ("te05", "Der Marker einer Installation ausserhalb wird nicht geschrieben", COMP_TE,
     "        if not _liegt_in(binary, target_dir):\n            _eigene_installation_merken(target_dir, binary, version, definition)\n",
     "        pass\n", T_TE),
    ("te06", "Entfernen ignoriert den Marker", COMP_TE,
     "    marker = eigene_installation(name)\n    nicht_mehr_pbp = marker is None and eigene_installation(name, pruefen=False) is not None\n    if marker is not None:\n",
     "    marker = None\n    nicht_mehr_pbp = False\n    if marker is not None:\n", T_TE),
    ("te18", "Eine spaeter von Hand neu angelegte Installation am selben Ort gilt als die von PBP", COMP_TE,
     "        return all(marker.get(k) == jetzt[k] for k in (\"binary_groesse\", \"binary_erstellt\"))\n",
     "        return True\n", T_TE),
    ("te07", "Entfernen nimmt jeden Pfad, den der Marker nennt", COMP_TE,
     "    if erlaubt is None or not str(verzeichnis) or not _liegt_in(verzeichnis, erlaubt) or not _liegt_in(erlaubt, verzeichnis):\n",
     "    if False:\n", T_TE),
    ("te08", "Das Deinstallationsprogramm wird ohne die Umgebung RunAsInvoker gestartet", COMP_TE,
     '                    [str(deinstaller), "/S"], env=_setup_umgebung(), timeout=180, capture_output=True,\n',
     '                    [str(deinstaller), "/S"], timeout=180, capture_output=True,\n', T_TE),
    ("te09", "Entfernen laesst den Ordner mit den Resten stehen", COMP_TE,
     "        shutil.rmtree(verzeichnis, ignore_errors=True)\n", "        pass\n", T_TE),
    ("te10", "Eine vorhandene Installation 'nur fuer mich' wird nicht erkannt", COMP_TE,
     '        pfade.append(str(ordner / definition["binary_name"]))\n', "        pass\n", T_TE),
    ("te11", "Der Sprachhinweis nennt wieder Werkzeugnamen", "src/bewerbungs_assistent/services/ocr_service.py",
     '            "Das deutsche Sprachpaket fehlt, die Erkennung lief nur auf Englisch. Für deutsche Dokumente: die Datei "\n',
     '            "deu-Sprachpaket fehlt — Erkennung lief nur mit \'eng\'. Für deutsche Dokumente: ensure_language(\'deu\'). Die Datei "\n', T_TE),
    ("te12", "Die Speicheruebersicht nennt den echten Ort der Texterkennung nicht", "src/bewerbungs_assistent/services/speicher.py",
     '            if marker:\n                ziel = Path(str(marker["verzeichnis"]))\n', '            if False:\n                ziel = Path(str(marker["verzeichnis"]))\n', T_TE),
    ("te13", "Deinstaller: ohne Marker wird trotzdem entfernt", "DEINSTALLIEREN.bat",
     'if not exist "%BASE_INSTALL%\\components\\tesseract\\pbp-installation.json" exit /b 9\n', "", T_TE),
    ("te14", "Deinstaller: wartet nicht, bis das Programm weg ist", "DEINSTALLIEREN.bat",
     "for ($i = 0; $i -lt $max -and (Test-Path -LiteralPath $b); $i++) { Start-Sleep -Seconds 1 }; ", "", T_TE),
    ("te19", "Deinstaller: ohne Vergleich mit dem Vermerk wird jede Installation am Ort entfernt", "DEINSTALLIEREN.bat",
     "if (-not $gleich) { Write-Host '[INFO] Texterkennung: stammt nicht mehr von PBP oder ist schon entfernt, bleibt'; exit 8 }; ",
     "", T_TE),
    ("te15", "Deinstaller: die Texterkennung wird in Schritt 5 nicht aufgerufen", "DEINSTALLIEREN.bat",
     'call :texterkennung_entfernen\nset "TESS_RESULT=!errorlevel!"\n', 'set "TESS_RESULT=9"\n', T_TE),
    ("te16", "Deinstaller: jedes Verzeichnis statt nur dem einen Ort", "DEINSTALLIEREN.bat",
     "$d = Join-Path $env:LOCALAPPDATA 'Programs\\Tesseract-OCR'; ", "$d = $env:LOCALAPPDATA; ", T_TE),
    ("te20", "Entfernen: die Wartezeit auf das Deinstallationsprogramm entfaellt", COMP_TE,
     "            for _ in range(60):\n", "            for _ in range(0):\n", T_TE),
    ("te21", "Das Angebot an Claude nennt wieder den PBP-Ordner als Ziel", "src/bewerbungs_assistent/tools/komponenten.py",
     '                    "ziel": ziel,\n',
     '                    "ziel": "AppData/BewerbungsAssistent/components/ (kein Admin nötig)",\n', T_TE),
    ("te22", "Die Karte 'Zusatzprogramme' zaehlt den Programmordner nicht zur Summe", "src/bewerbungs_assistent/services/speicher.py",
     '           "summe_aus_eintraegen": True}\n', '           "summe_aus_eintraegen": False}\n', T_TE),
    ("te17", "Entfernen: das Warten auf das Deinstallationsprogramm blockiert den Ereignis-Thread des Dashboards",
     "src/bewerbungs_assistent/dashboard.py",
     "    result = await run_in_threadpool(comp.uninstall_component, _db, name)\n", "    result = comp.uninstall_component(_db, name)\n", T_TE),
]

KATALOGE = {"auto_update": M, "speicher": M_SPEICHER, "komponenten": M_KOMPONENTEN, "mail": M_MAIL, "firmen": M_FIRMEN, "wege": M_WEGE, "suche": M_SUCHE, "vorab": M_VORAB, "konsole": M_KONSOLE, "google": M_GOOGLE, "browser": M_BROWSER, "jobtic": M_JOBTIC, "skillstand": M_SKILL, "installer": M_INSTALLER, "erste": M_ERSTE, "texterkennung": M_TESSERACT}
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
    "google": (("T_GA", T_GA),),
    "browser": (("T_BR", T_BR),),
    "jobtic": (("T_JT", T_JT), ("T_JTP", T_JTP)),
    "skillstand": (("T_SK", T_SK),),
    "installer": (("T_IN", T_IN), ("T_IPP", T_IPP)),
    "erste": (("T_ES", T_ES),),
    "texterkennung": (("T_TE", T_TE),),
}

# ── Sprachdaten der Texterkennung: feste Fassung und Pruefsumme (#1165, I24) ──
# Ab hier ergaenzt jeder Katalog KATALOGE und GRUNDLAEUFE selbst (die Auswahl im Aufruf folgt KATALOGE).
T_SD = ["tests/test_v18_sprachdaten_pruefsumme_1165.py"]

M_SPRACHDATEN = [
    ("sd01", "Die Sprachdaten kommen wieder vom wandernden Zweig main", COMP_TE,
     '    "https://github.com/tesseract-ocr/tessdata_fast/raw/" + _TESSDATA_FAST_COMMIT + "/{lang}.traineddata"\n',
     '    "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"\n', T_SD),
    ("sd02", "_download prueft die angekommene Datei nicht", COMP_TE,
     "        if sha256 is not None and not _sha256_ok(teil, sha256):\n", "        if False:\n", T_SD),
    ("sd03", "ensure_language lehnt eine Sprache ohne Summe nicht vor dem Laden ab", COMP_TE,
     '    if not _pruefsumme_gueltig(TESSDATA_SPRACHEN.get(lang, "")):\n', "    if False:\n", T_SD),
    ("sd04", "Die Sprachdatei wird ohne Summe geladen", COMP_TE,
     ", lo, hi, sha256=TESSDATA_SPRACHEN[lang])\n", ", lo, hi)\n", T_SD),
    ("sd05", "Scheitert eine von mehreren Dateien, bleiben die abgelegten liegen", COMP_TE,
     "        for datei in abgelegt:\n            _entfernen(datei)\n", "        pass\n", T_SD),
    ("sd06", "Abgelegte Dateien werden nicht vermerkt (das Zurueckrollen findet nichts)", COMP_TE,
     "            abgelegt.append(target)\n", "", T_SD),
    ("sd07", "Fuer osd steht keine Summe in der Registry", COMP_TE,
     '    "osd": "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff",\n', '    "osd": "",\n', T_SD),
    ("sd08", "Der Installationsjob verschweigt das fehlende deutsche Sprachpaket", COMP_TE,
     '                    if lang.get("status") == "fehler":\n', "                    if False:\n", T_SD),
    ("sd09", "Die Meldung nennt die verworfene Datei nicht", COMP_TE,
     'f"Die Prüfsumme von {target.name} stimmt nicht — die Datei wurde verworfen und nicht benutzt. "',
     '"Die Prüfsumme stimmt nicht — die Datei wurde verworfen und nicht benutzt. "', T_SD),
    ("sd10", "Wird eng verlangt, wird es zweimal geladen", COMP_TE,
     '            if base != lang and not (_tessdata_dir() / f"{base}.traineddata").is_file()\n',
     '            if not (_tessdata_dir() / f"{base}.traineddata").is_file()\n', T_SD),
]
KATALOGE["sprachdaten"] = M_SPRACHDATEN
GRUNDLAEUFE["sprachdaten"] = (("T_SD", T_SD),)

# ── Google Jobs ueber JobSpy ist defekt, die Browser-Schwester bleibt (#1159, B75) ──
T_JG = ["tests/test_v18_jobspy_google_defekt_1159.py"]
REG_JG = "src/bewerbungs_assistent/job_scraper/__init__.py"
HO_JG = "src/bewerbungs_assistent/services/browser_handoff.py"

M_JOBSPY_GOOGLE = [
    ("jg01", "jobspy_google gilt wieder als funktionierend", REG_JG,
     '        "defekt": True,\n        "ersatz_quelle": "google_jobs",\n', '        "ersatz_quelle": "google_jobs",\n', T_JG),
    ("jg02", "Die defekte Quelle nennt keine Browser-Schwester", REG_JG,
     '        "ersatz_quelle": "google_jobs",\n', "", T_JG),
    ("jg03", "Die Browser-Liste nennt die defekte Schwester trotz Ersatzquelle noch einmal", HO_JG,
     ' and _nur_im_browser(info) and not info.get("ersatz_quelle"):\n', ' and _nur_im_browser(info):\n', T_JG),
    ("jg04", "Die Browser-Schwester behauptet wieder, die automatische deckte Google ab", REG_JG,
     '        # #1159: kein "doppelt_mit" mehr -- die automatische Schwester jobspy_google liefert nichts (defekt); der Satz\n',
     '        "doppelt_mit": "jobspy_google",\n', T_JG),
    ("jg05", "Der Grund nennt den Weg ueber den Browser nicht mehr", REG_JG,
     "Im Browser funktioniert die Suche: die Quelle „Google Jobs (im Browser)“ über die Claude-Erweiterung.",
     "Bitte später erneut versuchen.", T_JG),
    ("jg06", "Der Ersatzweg der Karte ist kein Link mehr", REG_JG,
     '"manueller_fallback": "https://www.google.com/search?udm=8&q=Jobs im Browser oder',
     '"manueller_fallback": "im Browser oder', T_JG),
]
KATALOGE["jobspy_google"] = M_JOBSPY_GOOGLE
GRUNDLAEUFE["jobspy_google"] = (("T_JG", T_JG),)

# ── Tester-Schalter fuer Vorabversionen (#1179, G89) ──
T_VS = ["tests/test_v18_vorab_schalter_1179.py"]
T_VSB = ["tests/test_v18_vorab_schalter_1179_browser.py",
         "tests/test_v18_update_vorabversion_1179.py::test_die_regeln_gelten_auch_im_node_test"]
AUZ = "src/bewerbungs_assistent/services/auto_update/zustand.py"
AUQ = "src/bewerbungs_assistent/services/auto_update/quelle.py"
AUM = "src/bewerbungs_assistent/services/auto_update/manifest.py"
AUI = "src/bewerbungs_assistent/services/auto_update/installation.py"
AUL_PY = "src/bewerbungs_assistent/services/auto_update/lauf.py"
UQ_PY = "src/bewerbungs_assistent/services/update_quelle.py"
DASH = "src/bewerbungs_assistent/dashboard.py"
TOOL_UPD = "src/bewerbungs_assistent/tools/update.py"
AUJS = "frontend/src/lib/autoUpdate.js"
UTAB = "frontend/src/components/UpdatesTab.jsx"
APPJ = "frontend/src/App.jsx"

M_VORABSCHALTER = [
    # Zustand
    ("vs01", "Jeder wahre Wert schaltet den Schalter ein (auch der Text 'ja')", AUZ,
     "        return db.get_setting(K_VORAB, False) is True\n", "        return bool(db.get_setting(K_VORAB, False))\n", T_VS),
    ("vs02", "Die Vorgabe des Schalters ist ein", AUZ,
     "        return db.get_setting(K_VORAB, False) is True\n", "        return db.get_setting(K_VORAB, True) is True\n", T_VS),
    ("vs03", "Setzen nimmt jeden Wert, nicht nur ein echtes ja/nein", AUZ,
     '    if not isinstance(wert, bool):\n        raise ValueError("Vorabversionen: erwartet ja oder nein.")\n', "", T_VS),
    # Quelle und Manifest
    ("vs04", "Eine von GitHub als Vorabversion markierte Nummer ohne Beta-Zusatz gilt als fertige Version", AUQ,
     "        vorab = markiert or not _fassung.ist_stabil(version)\n",
     "        vorab = not _fassung.ist_stabil(version)\n", T_VS),
    ("vs05", "Die Liste nimmt Beta-Nummern auch ohne Schalter", AUQ,
     "        if vorab and not mit_vorab:\n", "        if False:\n", T_VS),
    ("vs06", "asset_url erlaubt jede gueltige Nummer ohne die Erlaubnis des Aufrufs", AUQ,
     "    if not (_fassung.ist_stabil(version) or (vorab_erlaubt and _fassung.gueltig(version))):\n        raise UpdateFehler(\"quelle_nicht_erlaubt\", detail=f\"keine stabile Fassung: {version!r}\")\n",
     "    if not (_fassung.ist_stabil(version) or _fassung.gueltig(version)):\n        raise UpdateFehler(\"quelle_nicht_erlaubt\", detail=f\"keine stabile Fassung: {version!r}\")\n", T_VS),
    ("vs07", "asset_url prueft die Nummer einer Vorabversion nicht streng", AUQ,
     "    if not (_fassung.ist_stabil(version) or (vorab_erlaubt and _fassung.gueltig(version))):\n        raise UpdateFehler(\"quelle_nicht_erlaubt\", detail=f\"keine stabile Fassung: {version!r}\")\n",
     "    if not (_fassung.ist_stabil(version) or vorab_erlaubt):\n        raise UpdateFehler(\"quelle_nicht_erlaubt\", detail=f\"keine stabile Fassung: {version!r}\")\n", T_VS),
    ("vs08", "Das Manifest einer Vorabversion wird immer angenommen", AUM,
     "    if not (_fassung.ist_stabil(version) or (vorab_erlaubt and _fassung.gueltig(version))):\n",
     "    if not (_fassung.ist_stabil(version) or _fassung.gueltig(version)):\n", T_VS),
    # Installation
    ("vs09", "Die Vorbedingungen lassen eine Vorabversion ohne Erlaubnis durch", AUI,
     "    if not (_fassung.ist_stabil(version) or (vorab_erlaubt and _fassung.gueltig(version))):\n",
     "    if not (_fassung.ist_stabil(version) or _fassung.gueltig(version)):\n", T_VS),
    ("vs10", "Der Ausloeser 'automatisch' darf eine Vorabversion installieren (installiere)", AUI,
     '        if vorab_erlaubt and ausloeser == "automatisch":\n            raise UpdateFehler("quelle_nicht_erlaubt", "Eine Vorabversion installiert PBP nie von selbst.",\n                               detail=f"{version!r} mit Ausloeser automatisch")\n',
     "", T_VS),
    ("vs11", "Der Lauf gibt die Erlaubnis nicht an die Installation weiter", AUL_PY,
     '                      **kw, **({"vorab_erlaubt": True} if vorab else {}))\n', "                      **kw)\n", T_VS),
    # Lauf
    ("vs12", "Der Start verlangt die Zusage des Aufrufs nicht", AUL_PY,
     '        if not vorab_erlaubt or ausloeser == "automatisch" or not _fassung.gueltig(version):\n',
     '        if ausloeser == "automatisch" or not _fassung.gueltig(version):\n', T_VS),
    ("vs13", "Der Start erlaubt den Ausloeser 'automatisch'", AUL_PY,
     '        if not vorab_erlaubt or ausloeser == "automatisch" or not _fassung.gueltig(version):\n',
     '        if not vorab_erlaubt or not _fassung.gueltig(version):\n', T_VS),
    ("vs14", "Der Start prueft den Schalter nicht", AUL_PY,
     "        if not zustand.vorabversionen(db):\n", "        if False:\n", T_VS),
    ("vs15", "Der Start prueft die Nummer nicht streng", AUL_PY,
     '        if not vorab_erlaubt or ausloeser == "automatisch" or not _fassung.gueltig(version):\n',
     '        if not vorab_erlaubt or ausloeser == "automatisch":\n', T_VS),
    ("vs16", "Die Pruefung stellt die Vorabversion an die Stelle der fertigen", AUL_PY,
     "    neu = quelle.neueste_fuer_linie([f for f in freigaben if not f.vorab], bezug)\n",
     "    neu = quelle.neueste_fuer_linie(freigaben, bezug)\n", T_VS),
    ("vs17", "Die Pruefung liest die Vorabversionen auch ohne Schalter", AUL_PY,
     "    freigaben = quelle.freigaben_lesen(daten, mit_vorab=mit_vorab)\n",
     "    freigaben = quelle.freigaben_lesen(daten, mit_vorab=True)\n", T_VS),
    ("vs18", "Eine gemerkte Antwort gilt auch nach dem Umschalten des Schalters", AUL_PY,
     '        if _PRUEFUNG["ergebnis"].get("laufende") == laufende and bool(_PRUEFUNG["ergebnis"].get("mit_vorab")) == mit_vorab:\n',
     '        if _PRUEFUNG["ergebnis"].get("laufende") == laufende:\n', T_VS),
    ("vs19", "Die Uebersicht zeigt eine gemerkte Vorabversion auch bei ausgeschaltetem Schalter", AUL_PY,
     '    if antwort["vorabversionen"] and p and isinstance(p.get("vorab"), dict):\n',
     '    if p and isinstance(p.get("vorab"), dict):\n', T_VS),
    ("vs20", "Die Pruefung nennt die Vorabversion ohne den Vergleich mit der fertigen", AUL_PY,
     '        if kandidat is not None and (neu is None or _fassung.ist_neuer(kandidat.version, neu.version)):\n',
     "        if kandidat is not None:\n", T_VS),
    # allgemeine Pruefung
    ("vs21", "Die allgemeine Pruefung ignoriert den Schalter", UQ_PY,
     "    mit_vorab = bool(mit_vorab) or _ist_vorabversion(aktuell)\n", "    mit_vorab = _ist_vorabversion(aktuell)\n", T_VS),
    ("vs22", "auswerten reicht den Schalter nicht weiter", UQ_PY,
     "        return auswerten_liste(daten, aktuell, linie, mit_vorab=mit_vorab)\n", "        return auswerten_liste(daten, aktuell, linie)\n", T_VS),
    # Dashboard
    ("vs23", "Das Dashboard gibt den Schalter nicht an die allgemeine Pruefung", DASH,
     '            befund = _uq.auswerten(quelle["art"], daten, __version__, linie, mit_vorab=mit_vorab)\n',
     '            befund = _uq.auswerten(quelle["art"], daten, __version__, linie)\n', T_VS),
    ("vs24", "Der Installationsweg sendet die Zusage immer mit", DASH,
     '    zusatz = {"vorab_erlaubt": True} if payload.get("vorabversion") is True else {}\n',
     '    zusatz = {"vorab_erlaubt": True}\n', T_VS),
    ("vs25", "Der Installationsweg nimmt jeden wahren Wert als Zusage", DASH,
     '    zusatz = {"vorab_erlaubt": True} if payload.get("vorabversion") is True else {}\n',
     '    zusatz = {"vorab_erlaubt": True} if payload.get("vorabversion") else {}\n', T_VS),
    ("vs26", "Das Umschalten verwirft die gemerkte allgemeine Pruefung nicht", DASH,
     '            _update_cache["data"] = None\n    except ValueError as exc:\n        return JSONResponse({"error": str(exc)}, status_code=400)\n    return lauf.uebersicht(_db)\n',
     '    except ValueError as exc:\n        return JSONResponse({"error": str(exc)}, status_code=400)\n    return lauf.uebersicht(_db)\n', T_VS),
    # Werkzeuge
    ("vs27", "Das Werkzeug schaltet ohne Bestaetigung ein", TOOL_UPD,
     '                if wunsch == "ja" and not bestaetigt:\n', "                if False:\n", T_VS),
    ("vs28", "Das Werkzeug waehlt eine Vorabversion von selbst, wenn keine fertige da ist", TOOL_UPD,
     "            if not version and isinstance(letzte.get(\"vorab\"), dict):\n",
     "            if False:\n", T_VS),
    ("vs29", "Das Werkzeug sendet die Zusage nicht, auch wenn der Mensch die Vorabversion nannte", TOOL_UPD,
     '        zusatz = {} if _fassung_ist_stabil(version) else {"vorab_erlaubt": True}\n', "        zusatz = {}\n", T_VS),
    # Oberflaeche
    ("vf01", "Der Klick-Weg ignoriert den Schalter", AUJS,
     "  if (!au?.verfuegbar || !au.vorabversionen || !au.vorab || !au.vorab.bereit) return null;\n",
     "  if (!au?.verfuegbar || !au.vorab || !au.vorab.bereit) return null;\n", T_VSB),
    ("vf02", "Der Klick-Weg bietet eine Vorabversion ohne Update-Paket an", AUJS,
     "  if (!au?.verfuegbar || !au.vorabversionen || !au.vorab || !au.vorab.bereit) return null;\n",
     "  if (!au?.verfuegbar || !au.vorabversionen || !au.vorab) return null;\n", T_VSB),
    ("vf03", "Die Hinweiszone kennt den Klick-Weg nicht", AUJS,
     "    const klick = vorabKlick(au);\n    if (klick) return vorabKlickHinweis(klick);\n", "", T_VSB),
    ("vf04", "Der Knopf der Hinweiszone traegt die Zusage nicht (vorab: true)", AUJS,
     'label: "Vorabversion installieren", version: vorab.version, vorab: true },\n',
     'label: "Vorabversion installieren", version: vorab.version },\n', T_VSB),
    ("vf05", "Der Hinweis der Hinweiszone drueckt sich vor (dringend)", AUJS,
     '    id: "update-vorab-klick", ton: "neutral", dringend: false,\n',
     '    id: "update-vorab-klick", ton: "neutral", dringend: true,\n', T_VSB),
    ("vf06", "Erneut versuchen nach einem Fehler verliert die Zusage", AUJS,
     "version: job.version, ...(vorabLauf ? { vorab: true } : {}) },\n", "version: job.version },\n", T_VSB),
    ("vf07", "Neben dem Klick-Weg steht dieselbe Version noch einmal als ZIP-Karte", AUJS,
     "    if (k.bereit) return null;\n", "", T_VSB),
    ("vf08", "Die Installation einer Vorabversion geschieht ohne Rueckfrage", APPJ,
     "          if (!ja) return;\n          await postJson(\"/api/auto-update/installieren\", { version: a.version, vorabversion: true });\n",
     "          await postJson(\"/api/auto-update/installieren\", { version: a.version, vorabversion: true });\n", T_VSB),
    ("vf09", "Die Installation einer Vorabversion sendet die Zusage nicht", APPJ,
     "{ version: a.version, vorabversion: true }", "{ version: a.version }", T_VSB),
    ("vf10", "Das Einschalten geschieht ohne Rueckfrage", UTAB,
     '    if (an && !(await bestaetigen({ titel: "Vorabversionen anzeigen?", text: VORAB_EINSCHALTEN_FRAGE, ja: "Einschalten", gefahr: false }))) return;\n',
     "", T_VSB),
    ("vf11", "Der Schalter sendet immer 'ein'", UTAB,
     '{ vorabversionen: an },', '{ vorabversionen: true },', T_VSB),
    ("vf12", "Die Karte mit dem Installieren-Knopf wird nie gezeigt", UTAB,
     '        {klick ? (\n          <div className="mt-4 rounded-xl border border-amber/30 bg-amber/10 p-4" data-updates-vorab-klick>\n',
     '        {false ? (\n          <div className="mt-4 rounded-xl border border-amber/30 bg-amber/10 p-4" data-updates-vorab-klick>\n', T_VSB),
    ("vf13", "Die Karte nennt die Vorgabe des Schalters nicht", UTAB,
     '{au.vorabversionen ? "" : " (Vorgabe: aus)"}', '{""}', T_VSB),
    ("vf14", "Die Hilfe nennt den Schalter nicht", "frontend/src/lib/hilfe.js",
     "Für Tester gibt es unter Einstellungen › Erweitert › Updates den Schalter „Vorabversionen anbieten“: ",
     "", T_VSB),
]
KATALOGE["vorabschalter"] = M_VORABSCHALTER
GRUNDLAEUFE["vorabschalter"] = (("T_VS", T_VS), ("T_VSB", T_VSB))

# ── Der Typ eines einzelnen Dokuments von Hand (#1162, E32) ──
T_DT = ["tests/test_v18_dokument_typ_1162.py"]
T_DTB = ["tests/test_v18_dokument_typ_1162_browser.py"]
DH_PY = "src/bewerbungs_assistent/services/document_handlers.py"
DOK_TOOL = "src/bewerbungs_assistent/tools/dokumente.py"
DOCP = "frontend/src/pages/DocumentsPage.jsx"

M_DOKUMENTTYP = [
    ("dt01", "Der Dienst prueft den Typ nicht gegen die erlaubten", DH_PY,
     "    if typ not in erlaubte_typen():\n", "    if False:\n", T_DT),
    ("dt02", "Der Dienst sucht das Dokument ohne das Profil", DH_PY,
     "    doc = db.get_document(dokument_id, profile_id=profile_id)\n", "    doc = db.get_document(dokument_id)\n", T_DT),
    ("dt03", "Der Dienst schreibt ohne das Profil", DH_PY,
     "    if not db.update_document_type(dokument_id, typ, profile_id=profile_id):\n",
     "    if not db.update_document_type(dokument_id, typ):\n", T_DT),
    ("dt04", "Derselbe Typ gilt als Aenderung", DH_PY,
     "    if alt == typ:\n", "    if False:\n", T_DT),
    ("dt05", "Die erlaubten Typen kennen die Vorlagen nicht", DH_PY,
     "    return list(KNOWN_TYPES) + [t for t in VORLAGEN_TYPEN if t not in KNOWN_TYPES]\n",
     "    return list(KNOWN_TYPES)\n", T_DT),
    ("dt06", "Ein bekannter Typ hat keinen deutschen Namen", DH_PY,
     '    "absage": "Absage",\n', "", T_DT),
    ("dt07", "Der Endpunkt nimmt einen unbekannten Typ an", DASH,
     '    if erg["status"] == "unbekannter_typ":\n', "    if False:\n", T_DT),
    ("dt08", "Das Werkzeug gibt bei einem Fehler zusaetzlich einen Status zurueck", DOK_TOOL,
     '        if erg["status"] in ("nicht_gefunden", "unbekannter_typ"):\n', "        if False:\n", T_DT),
    ("dt09", "Die Typen-Uebersicht verneint die Aenderung von Hand wieder", DOK_TOOL,
     '"Den Typ eines einzelnen Dokuments stellt dokument_typ_setzen() "', '"Den Typ eines einzelnen Dokuments kann man derzeit nicht "', T_DT),
    ("df01", "Die Ansicht schickt die Aenderung nicht", DOCP,
     "      await putJson(`/api/document/${doc.id}/doc-type`, { doc_type: neuerTyp });\n", "", T_DTB),
    ("df02", "Die Ansicht schickt den alten Typ statt des neuen", DOCP,
     "{ doc_type: neuerTyp }", "{ doc_type: doc.doc_type }", T_DTB),
    ("df03", "Die Ansicht sagt nach dem Aendern nicht, was geworden ist", DOCP,
     "      pushToast(`Typ geändert: ${typName(neuerTyp)}`, \"success\");\n", "", T_DTB),
    ("df04", "Die Namen kommen nicht vom Server", DOCP,
     "    return typen.find((t) => t.typ === typ)?.name || docTypeLabel(typ);\n", "    return docTypeLabel(typ);\n", T_DTB),
    ("df05", "Ein Typ ausserhalb der Liste verschwindet aus der Auswahl", DOCP,
     "                                {typen.length === 0 || !typen.some((t) => t.typ === doc.doc_type) ? (\n",
     "                                {false ? (\n", T_DTB),
    ("df06", "Die Ansicht laedt die Typen nicht", DOCP,
     '    api("/api/document-types")\n      .then((r) => setTypen(r.typen || []))\n',
     '    Promise.resolve({ typen: [] })\n      .then((r) => setTypen(r.typen || []))\n', T_DTB),
]
KATALOGE["dokumenttyp"] = M_DOKUMENTTYP
GRUNDLAEUFE["dokumenttyp"] = (("T_DT", T_DT), ("T_DTB", T_DTB))

# ── Voreinstellung der Filter in der Stellenliste (#1158 Punkt 5, G82) ──
T_FV = ["tests/test_v18_stellen_filter_standard_1158.py"]
SFS_PY = "src/bewerbungs_assistent/services/stellen_filter_standard.py"
JOBSP = "frontend/src/pages/JobsPage.jsx"
SFJS = "frontend/src/lib/stellenFilter.js"

M_FILTERVOREINSTELLUNG = [
    ("fv01", "Die Voreinstellung nimmt einen unbekannten Filter an", SFS_PY,
     '        if schluessel not in SCHLUESSEL:\n            raise ValueError(f"Unbekannter Filter: {schluessel!r}.")\n', "", T_FV),
    ("fv02", "Die Voreinstellung prueft die Typen nicht", SFS_PY,
     "        if not isinstance(wert, erwartet) or (erwartet is str and isinstance(wert, bool)):\n", "        if False:\n", T_FV),
    ("fv03", "Mindestpunkte duerfen jeder Text sein", SFS_PY,
     '            if schluessel == "minScore" and wert.strip() and not _ZAHL.fullmatch(wert.strip()):\n', "            if False:\n", T_FV),
    ("fv04", "Ein kaputter gespeicherter Eintrag wirft statt „keine Voreinstellung“ zu sein", SFS_PY,
     "    except ValueError:\n        return None\n", "    except ValueError:\n        raise\n", T_FV),
    ("fv05", "Der Endpunkt antwortet auf eine ungueltige Voreinstellung mit 200", DASH,
     '        return JSONResponse({"error": str(exc)}, status_code=400)\n    return {"standard": gesetzt}\n',
     '        return JSONResponse({"error": str(exc)}, status_code=200)\n    return {"standard": gesetzt}\n', T_FV),
    ("fv06", "Aufheben loescht nichts auf dem Server", DASH,
     "    stellen_filter_standard.loeschen(_db)\n    return {\"standard\": None}\n", "    return {\"standard\": None}\n", T_FV),
    ("ff01", "Die Voreinstellung gilt bei jedem Betreten der Seite, nicht nur beim Oeffnen", JOBSP,
     "        if (gefunden && !voreinstellungSchonAngewendet) {\n", "        if (gefunden) {\n", T_FV),
    ("ff02", "Die erste Liste wird geholt, bevor die Voreinstellung da ist", JOBSP,
     "    if (!voreinstellungBereit) return;\n    setLoading(true);\n", "    setLoading(true);\n", T_FV),
    ("ff03", "„Filter zuruecksetzen“ stellt die Voreinstellung her statt die Einschraenkung aufzuheben", JOBSP,
     "                  ...FILTER_STANDARD,\n                  sort: current.sort,\n                  view: current.view,\n",
     "                  ...filterAusVoreinstellung(voreinstellung || {}, FILTER_STANDARD, current),\n                  sort: current.sort,\n                  view: current.view,\n", T_FV),
    ("ff04", "„Aufheben“ ruft den Server nicht", JOBSP,
     '      await deleteRequest("/api/stellen-filter-standard");\n', "", T_FV),
    ("ff05", "„Als Voreinstellung speichern“ ruft den Server nicht", JOBSP,
     '      const antwort = await putJson("/api/stellen-filter-standard", { standard: filterFuerVoreinstellung(filters) });\n',
     "      const antwort = { standard: filterFuerVoreinstellung(filters) };\n", T_FV),
    ("ff06", "Der Weg zurueck zur Voreinstellung fehlt", JOBSP,
     "              {voreinstellung && !voreinstellungGilt(filters, voreinstellung, FILTER_STANDARD) ? (\n", "              {false ? (\n", T_FV),
    ("ff07", "Die Karte sagt nicht, was beim Oeffnen gilt", JOBSP,
     '                  : "Ohne Voreinstellung gilt beim Öffnen, wie du die Liste verlassen hast."}\n', '                  : ""}\n', T_FV),
    ("ff08", "Die Voreinstellung nimmt den Suchtext mit", SFJS,
     'const NICHT_GEMERKT = ["query", "view"];\n', 'const NICHT_GEMERKT = ["view"];\n', T_FV),
    ("ff09", "Die Voreinstellung traegt den Suchtext des Moments in die Liste", SFJS,
     "  return { ...gelesen, query: aktuell.query ?? standard.query, view: aktuell.view ?? standard.view };\n",
     "  return { ...gelesen, query: standard.query, view: standard.view };\n", T_FV),
]
KATALOGE["filtervoreinstellung"] = M_FILTERVOREINSTELLUNG
GRUNDLAEUFE["filtervoreinstellung"] = (("T_FV", T_FV),)

# ── MCP-Werkzeuge: Sammelposten, Rest (#1148, H38): Parameter-Aliase, Inventar, Zaehlerstaende ──
T_WS = ["tests/test_v18_parameter_aliase_1148.py", "tests/test_v18_werkzeug_zahlen_1148.py"]
PARAL = "src/bewerbungs_assistent/services/parameter_aliase.py"
INVSK = "scripts/werkzeug_inventar.py"
SERVER_PY = "src/bewerbungs_assistent/server.py"

M_WERKZEUGSAMMEL = [
    ("pa01", "Die Uebersetzung ueberschreibt einen Namen, den das Werkzeug selbst kennt", PARAL,
     "        if name in bekannte or name not in _ANDERE:\n", "        if name not in _ANDERE:\n", T_WS),
    ("pa02", "Die Uebersetzung ueberschreibt einen schon uebergebenen Zielnamen", PARAL,
     "        kandidaten = [a for a in _ANDERE[name] if a in bekannte and a not in arguments]\n",
     "        kandidaten = [a for a in _ANDERE[name] if a in bekannte]\n", T_WS),
    ("pa03", "Die Tabelle kennt firma/company nicht", PARAL,
     '    ("firma", "company"),\n', "", T_WS),
    ("pa04", "Die Middleware wendet die Uebersetzung nicht an", SERVER_PY,
     '                context = context.copy(message=context.message.model_copy(update={"arguments": _aliase}))\n',
     "                pass\n", T_WS),
    ("iv01", "Das Ergaenzen zaehlt auch, was nur im erzeugten Abschnitt steht", INVSK,
     "    aussen = text if a < 0 or e < 0 else text[:a] + text[e + len(MARKE_ENDE):]\n", "    aussen = text\n", T_WS),
    ("iv02", "Die Wiki-Pruefung uebersieht eine falsche Zahl", INVSK,
     '    falsch = sorted(z for z in zahlen if z != inv["gesamt"])\n', "    falsch = []\n", T_WS),
    ("iv03", "Die Wiki-Pruefung uebersieht fehlende Werkzeuge", INVSK,
     '    fehlt = sorted(n for n in inv["namen"] if n not in genannt)\n    if fehlt:\n        befunde.append(',
     '    fehlt = []\n    if fehlt:\n        befunde.append(', T_WS),
]
KATALOGE["werkzeugsammel"] = M_WERKZEUGSAMMEL
GRUNDLAEUFE["werkzeugsammel"] = (("T_WS", T_WS),)

# ── Installer Teil 2, Rest (#1149): Ordnername, Deinstaller im TEMP, Mac/Linux, Zahlen und Texte ──
# Bewusst NICHT im Katalog: die Zeile mit PBP_DESKTOP (ohne sie schriebe der Test auf den ECHTEN Desktop), und die Unix-Faelle,
# deren Tests nur unter Linux laufen (SIGTERM-Semantik, echtes pgrep) - die prueft die CI auf ubuntu.
T_I2 = ["tests/test_v18_installer_rest_1149.py"]
T_I2B = T_I2 + ["tests/test_v17145_deinstaller.py"]
IB = "INSTALLIEREN.bat"
DB = "DEINSTALLIEREN.bat"
ISH = "installer/install.sh"
ICM = "INSTALLIEREN.command"
DSH = "installer/deinstallieren.sh"
PS_PTH = "-Command \"(Get-Content -LiteralPath $env:PTH_FILE) -replace"

M_INSTALLER2 = [
    ("i201", "Das Ausrufezeichen im Ordnernamen wird nicht mehr geprueft", IB,
     'if "%PBP_START_ORT:!=%"=="%PBP_START_ORT%" goto :ort_ohne_ausrufezeichen\n', "goto :ort_ohne_ausrufezeichen\n", T_I2),
    ("i202", "Die Pruefung laeuft unter verzoegerter Expansion (das Zeichen ist dann schon weg)", IB,
     'setlocal DisableDelayedExpansion\nset "PBP_START_ORT=%~dp0"\n', 'setlocal EnableDelayedExpansion\nset "PBP_START_ORT=%~dp0"\n', T_I2),
    ("i203", "Nach der Pruefung bleibt die verzoegerte Expansion aus", IB,
     ":ort_ohne_ausrufezeichen\nendlocal\nsetlocal EnableDelayedExpansion\n", ":ort_ohne_ausrufezeichen\nendlocal\nsetlocal DisableDelayedExpansion\n", T_I2),
    ("i204", "Expand-Archive nimmt den Pfad wieder eingebettet (Apostroph bricht ihn)", IB,
     'Expand-Archive -LiteralPath $env:PY_ZIP_PATH -DestinationPath $env:PYTHON_DIR -Force"',
     "Expand-Archive -Path '%PY_ZIP_PATH%' -DestinationPath '%PYTHON_DIR%' -Force\"", T_I2),
    ("i205", "_pth (frisches Python): Pfad wieder eingebettet", IB,
     ':: import site entkommentieren\npowershell -ExecutionPolicy Bypass -NoProfile ' + PS_PTH,
     ":: import site entkommentieren\npowershell -ExecutionPolicy Bypass -NoProfile -Command \"(Get-Content '!PTH_FILE!') -replace", T_I2),
    ("i206", "_pth (vorhandenes Python): Pfad wieder eingebettet", IB,
     'echo import site>> "!PTH_FILE!"\npowershell -ExecutionPolicy Bypass -NoProfile ' + PS_PTH,
     "echo import site>> \"!PTH_FILE!\"\npowershell -ExecutionPolicy Bypass -NoProfile -Command \"(Get-Content '!PTH_FILE!') -replace", T_I2),
    ("i207", "Python-Download: Zielpfad wieder eingebettet", IB,
     '-OutFile $env:PY_ZIP_PATH"', "-OutFile '%PY_ZIP_PATH%'\"", T_I2),
    ("i208", "get-pip-Download: Zielpfad wieder eingebettet", IB,
     '-OutFile $env:GETPIP_PATH"', "-OutFile '%GETPIP_PATH%'\"", T_I2),
    ("i209", "Unblock-File (frisches Python): Ordner wieder eingebettet", IB,
     'echo [DEBUG] Unblock-File... >> "%LOGFILE%"\npowershell -ExecutionPolicy Bypass -NoProfile -Command "Get-ChildItem -LiteralPath $env:BASEDIR',
     'echo [DEBUG] Unblock-File... >> "%LOGFILE%"\npowershell -ExecutionPolicy Bypass -NoProfile -Command "Get-ChildItem -Path \'%BASEDIR%\'', T_I2),
    ("i210", "Unblock-File (vorhandenes Python): Ordner wieder eingebettet", IB,
     'echo [DEBUG] Python existiert bereits >> "%LOGFILE%"\npowershell -ExecutionPolicy Bypass -NoProfile -Command "Get-ChildItem -LiteralPath $env:BASEDIR',
     'echo [DEBUG] Python existiert bereits >> "%LOGFILE%"\npowershell -ExecutionPolicy Bypass -NoProfile -Command "Get-ChildItem -Path \'%BASEDIR%\'', T_I2),
    ("i211", "Verknuepfung: Ziel wieder eingebettet", IB,
     "$s.TargetPath=(Join-Path $env:APP_DIR 'Dashboard starten.bat')", "$s.TargetPath='%APP_DIR%\\Dashboard starten.bat'", T_I2),
    ("i212", "err_pip: kein naechster Schritt", IB,
     "echo  ein Virenscanner den Download unterbrochen hat.\necho.\necho  SO GEHT ES WEITER:\necho    1. Internetverbindung pruefen ^(oeffne google.de^)\n"
     "echo    2. INSTALLIEREN.bat nochmal starten - das ist gefahrlos,\necho       deine Daten bleiben erhalten\n",
     "echo  ein Virenscanner den Download unterbrochen hat.\n", T_I2),
    ("i213", "err_packages: kein naechster Schritt", IB,
     "echo  eine Firewall oder ein Virenscanner den Download blockiert.\necho.\necho  SO GEHT ES WEITER:\necho    1. Internetverbindung pruefen ^(oeffne google.de^)\n"
     "echo    2. INSTALLIEREN.bat nochmal starten - das ist gefahrlos,\necho       deine Daten bleiben erhalten\n",
     "echo  eine Firewall oder ein Virenscanner den Download blockiert.\n", T_I2),
    ("i214", "Block: das Protokoll steht wieder als %LOGFILE% im Klammerblock", IB,
     "    echo             Details im Log: !LOGFILE!\n", "    echo             Details im Log: %LOGFILE%\n", T_I2),
    ("i215", "Block: der alte Python-Ordner steht wieder als %APP_DIR% im Klammerblock", IB,
     "gefunden: !APP_DIR!\\python >>", "gefunden: %APP_DIR%\\python >>", T_I2),
    ("i216", "Startskript: der Python-Pfad steht wieder als %PYTHON% im Klammerblock", "Dashboard starten.bat",
     "    echo    !PYTHON!\n", "    echo    %PYTHON%\n", T_I2),
    ("i220", "remove_path: Beschriftung wieder als %TARGET_LABEL% im Block (Klammer im Ordnernamen)", DB,
     "    echo         [OK] !TARGET_LABEL! entfernt\n", "    echo         [OK] %TARGET_LABEL% entfernt\n", T_I2),
    ("i221", "remove_path: 'nicht gefunden' wieder mit %TARGET_LABEL%", DB,
     "    echo         [--] !TARGET_LABEL! nicht gefunden\n", "    echo         [--] %TARGET_LABEL% nicht gefunden\n", T_I2),
    ("i222", "Deinstaller: die Umzugsmarke schuetzt den Ordner neben dem Skript nicht", DB,
     'if "%PBP_DEINST_RELOCATED%"=="1" set "BASEDIR_FREMD=1"\n', "", T_I2),
    ("i223", "Deinstaller: ein Skript in %TEMP% raeumt %TEMP% aus", DB,
     'if /i "%BASEDIR%"=="%TEMP%" set "BASEDIR_FREMD=1"\n', "", T_I2),
    ("i224", "Deinstaller: ein Skript in %TMP% raeumt %TMP% aus", DB,
     'if /i "%BASEDIR%"=="%TMP%" set "BASEDIR_FREMD=1"\n', "", T_I2),
    ("i225", "Deinstaller: trotz Schutz wird aufgeraeumt", DB,
     'bleiben unberuehrt >> "%LOGFILE%"\n    exit /b 0\n', 'bleiben unberuehrt >> "%LOGFILE%"\n', T_I2),
    ("i226", "Deinstaller: Schritt [5/7] ruft die Aufraeumzeilen gar nicht auf", DB,
     "call :ordner_neben_dem_skript\n", "rem\n", T_I2),
    ("i227", "Backup: Exit 2 ist kein Fehlschlag mehr", DB,
     '    if !BACKUP_RC! geq 2 set "BACKUP_FEHLER=1"\n', '    if !BACKUP_RC! geq 3 set "BACKUP_FEHLER=1"\n', T_I2),
    ("i228", "Backup: Zielpfad wieder eingebettet", DB,
     "-DestinationPath $env:BACKUP_ZIP -Force;", "-DestinationPath '!BACKUP_ZIP!' -Force;", T_I2B),
    ("i229", "Backup: das Protokoll sagt immer 'erstellt'", DB,
     '    if "!BACKUP_RC!"=="0" echo [INFO] Desktop-Backup erstellt >> "%LOGFILE%"\n',
     '    echo [INFO] Desktop-Backup erstellt >> "%LOGFILE%"\n', T_I2),
    ("i240", "Mac/Linux (install.sh): die Prozesssuche trifft jede Datei mit diesem Namen", ISH,
     "DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]].*start_dashboard\\.py'", "DASH_MUSTER='start_dashboard\\.py'", T_I2),
    ("i241", "Mac (.command): die Prozesssuche weicht von install.sh ab", ICM,
     "DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]].*start_dashboard\\.py'", "DASH_MUSTER='start_dashboard\\.py'", T_I2),
    ("i242", "Mac/Linux: eine andere Fassung auf dem Port gilt als 'ok'", ISH,
     '    elif [ -n "$NEUE_FASSUNG" ] && [ "$stand" != "$NEUE_FASSUNG" ]; then\n', "    elif false; then\n", T_I2),
    ("i243", "Mac (.command): eine andere Fassung auf dem Port gilt als 'ok'", ICM,
     '    elif [ -n "$NEUE_FASSUNG" ] && [ "$stand" != "$NEUE_FASSUNG" ]; then\n', "    elif false; then\n", T_I2),
    ("i244", "Mac/Linux: jedes HTTP 200 gilt als PBP", ISH,
     "        | grep -o '\"pbp_version\"[[:space:]]*:[[:space:]]*\"[^\"]*\"' | head -n 1 \\\n", "        | head -n 1 \\\n", T_I2),
    ("i245", "Mac/Linux: das alte Dashboard wird vor dem Start nicht beendet", ISH,
     "# Zuerst das alte Dashboard (Update), dann im Hintergrund starten\nalte_dashboards_beenden\n",
     "# Zuerst das alte Dashboard (Update), dann im Hintergrund starten\n", T_I2),
    ("i246", "Mac (.command): das alte Dashboard wird vor dem Start nicht beendet", ICM,
     "# Zuerst das alte Dashboard (Update), dann im Hintergrund starten\nalte_dashboards_beenden\n",
     "# Zuerst das alte Dashboard (Update), dann im Hintergrund starten\n", T_I2),
    ("i250", "deinstallieren.sh: eine kaputte JSON-Datei heisst wieder 'kein Eintrag'", DSH,
     'except (OSError, ValueError):\n    print("unreadable")', 'except (OSError, ValueError):\n    print("not_found")', T_I2),
    ("i251", "deinstallieren.sh: keine Sicherungskopie vor dem Schreiben", DSH,
     '    shutil.copy2(pfad, pfad + ".pbp-backup")\n', "", T_I2),
    ("i252", "deinstallieren.sh: 'entfernt' gemeldet, geschrieben wird nichts", DSH,
     "    os.replace(neu, pfad)\n", "    pass\n", T_I2),
    ("i253", "deinstallieren.sh: 'nicht lesbar' wird als 'nicht vorhanden' gemeldet", DSH,
     '            warn "Claude-Konfiguration nicht lesbar (kein gueltiges JSON): $CLAUDE_CONFIG"\n',
     '            info "MCP-Eintrag war nicht vorhanden"\n', T_I2),
    ("i260", "Release-Tor: server.json steht ausserhalb", "release_check.py",
     '    for rel in ("frontend/package.json", "server.json"):\n', '    for rel in ("frontend/package.json",):\n', T_I2),
    ("i261", "Release-Tor: package.json-Version wird nicht gelesen", "release_check.py",
     '        weitere[rel] = daten.get("version") or "(fehlt)"\n', "        weitere[rel] = init_version\n", T_I2),
    ("i262", "Release-Tor: eine vorhandene uv.lock steht ausserhalb", "release_check.py",
     "    if lockdatei.is_file():\n", "    if False:\n", T_I2),
    ("i263", "Release-Tor: --fix merkt sich die korrigierte Datei nicht", "release_check.py",
     "                korrigiert.add(datei_rel)\n", "", T_I2),
    ("i270", "server.json steht wieder auf 1.7.0", "server.json",
     '  "version": "1.8.0",\n  "websiteUrl"', '  "version": "1.7.0",\n  "websiteUrl"', T_I2),
    ("i271", "install.ps1 endet wieder mit Erfolg", "installer/install.ps1",
     'Write-Host ""\nexit 1\n', 'Write-Host ""\nexit 0\n', T_I2),
    ("i272", "LIESMICH verspricht wieder, nichts selber installieren zu muessen", "docs/LIESMICH.txt",
     "  -> Windows: Du brauchst vorab nichts zu installieren.\n", "  -> Du brauchst NICHTS selber installieren.\n", T_I2),
    ("i273", "README nennt die Windows-Warnung nicht mehr", "README.md",
     "> **„Ausführen“** klicken, bei Letzterem **„Weitere Informationen“ → „Trotzdem ausführen“**. PBP ist nicht mit einem bezahlten\n",
     "> **„Ausführen“** klicken. PBP ist nicht mit einem bezahlten\n", T_I2),
]
KATALOGE["installer2"] = M_INSTALLER2
GRUNDLAEUFE["installer2"] = (("T_I2", T_I2),)

# ── Die Aufraeum-Runde laeuft einmal am Tag von selbst (#1139, Variante A) ──
T_AR = ["tests/test_v18_aufraeum_runde_1139.py"]
T_ARB = ["tests/test_v18_aufraeum_runde_1139_browser.py", "tests/test_v18_erste_schritte_1170.py"]
ARQ = "src/bewerbungs_assistent/services/aufraeum_runde.py"
ASCH = "src/bewerbungs_assistent/services/automatik_scheduler.py"
TNZ = "src/bewerbungs_assistent/services/text_nachzug.py"
DSH_PY = "src/bewerbungs_assistent/dashboard.py"
DBP = "src/bewerbungs_assistent/database.py"
ANA = "src/bewerbungs_assistent/tools/analyse.py"
SET_JSX = "frontend/src/pages/SettingsPage.jsx"

M_AUFRAEUMRUNDE = [
    ("ar01", "Der automatische Lauf schliesst immer ab (der Schalter gilt nicht)", ARQ,
     '    if ausloeser == "automatik":\n        return expire_automatisch(db)\n    return True\n', "    return True\n", T_AR),
    ("ar02", "Der Knopf schliesst nur mit Schalter ab", ARQ,
     '    if ausloeser == "automatik":\n        return expire_automatisch(db)\n    return True\n', "    return expire_automatisch(db)\n", T_AR),
    ("ar03", "Das Abschliessen von selbst ist vorgabemaessig an", ARQ,
     "        return db.get_setting(EXPIRE_SCHALTER, False) in _WAHR\n", "        return db.get_setting(EXPIRE_SCHALTER, True) in _WAHR\n", T_AR),
    ("ar04", "Das Intervall der Runde ist vorgabemaessig aus", DBP,
     '_iv("automatik_aufraeumen_intervall_tage", 1)', '_iv("automatik_aufraeumen_intervall_tage", 0)', T_AR),
    ("ar05", "Ein ausdruecklich gesetztes Aus (0) gilt als nicht gesetzt", DBP,
     '            if raw is None or raw == "":\n                return vorgabe\n', "            if not raw:\n                return vorgabe\n", T_AR),
    ("ar06", "Der Lauf der Runde laesst sich nicht vermerken", DBP,
     'if kind not in ("jobsuche", "lernen", "aufraeumen"):', 'if kind not in ("jobsuche", "lernen"):', T_AR),
    ("ar10", "Der Takt startet die Runde nie", ASCH,
     '    if _is_due(s["aufraeumen_intervall_tage"], s["aufraeumen_last_at"], now):\n', "    if False:\n", T_AR),
    ("ar11", "'laeuft bereits' gilt als gelaufen", ASCH,
     '        if res.get("status") == "gestartet":\n            db.mark_automatik_run("aufraeumen")\n',
     '        if True:\n            db.mark_automatik_run("aufraeumen")\n', T_AR),
    ("ar12", "Eine zweite Runde startet, waehrend eine laeuft", ASCH,
     '    if db.get_running_background_job("aufraeumen"):\n        return {"status": "laeuft_bereits"}\n', "", T_AR),
    ("ar13", "Ein Fehler der Runde bleibt still (Job 'fertig')", ASCH,
     '                db.update_background_job(job_id, "fehler", message=f"Aufräum-Runde abgebrochen: {exc}")\n',
     '                db.update_background_job(job_id, "fertig", message="ok")\n', T_AR),
    ("ar14", "Der Planer sagt der Runde nicht, wer sie ausloest", ASCH,
     "            ergebnis = run_auto_actions(ausloeser)\n", "            ergebnis = run_auto_actions()\n", T_AR),
    ("ar20", "Knopf und Planer teilen keine Sperre", DSH_PY,
     '    if not _auto_actions_sperre.acquire(blocking=False):\n        return {"status": "laeuft_bereits"}\n    try:\n        now = datetime.now().isoformat()\n',
     '    _auto_actions_sperre.acquire(blocking=False)\n    try:\n        now = datetime.now().isoformat()\n', T_AR),
    ("ar21", "Die Sperre wird nach der Runde nicht freigegeben", DSH_PY,
     "    finally:\n        _auto_actions_sperre.release()\n", "    finally:\n        pass\n", T_AR),
    ("ar22", "Der automatische Lauf holt nicht mehr Anzeigentexte als der Knopf", DSH_PY,
     "max_jobs=16 if gross else 8", "max_jobs=8", T_AR),
    ("ar23", "Der automatische Lauf prueft nicht mehr Adressen als der Knopf", DSH_PY,
     "max_jobs=25 if gross else 10", "max_jobs=10", T_AR),
    ("ar24", "Der letzte Lauf nennt den Ausloeser nicht", DSH_PY,
     "    _db.set_setting(aufraeum_runde.LETZTER_AUSLOESER, ausloeser)\n", "", T_AR),
    ("ar25", "Der Planer sieht einen Lauf per Knopf nicht", DSH_PY,
     '        _db.mark_automatik_run("aufraeumen", now)\n', "        pass\n", T_AR),
    ("ar26", "Die URL-Pruefung bleibt bei den ersten Stellen nach Zeilennummer", DSH_PY,
     '" ORDER BY (k.value IS NOT NULL), k.value, j.hash LIMIT ?"', '" ORDER BY j.hash LIMIT ?"', T_AR),
    ("ar27", "Eine URL-Pruefung ohne Ergebnis wird nicht vermerkt (die Stelle bleibt vorn)", DSH_PY,
     '                    _db.set_setting(f"url_aging_lastcheck:{h}", now_dt.isoformat())\n', "                    pass\n", T_AR),
    ("ar28", "Der Status nennt den Schalter nicht wahrheitsgemaess", DSH_PY,
     '        "expire_automatisch": aufraeum_runde.expire_automatisch(_db),\n', '        "expire_automatisch": False,\n', T_AR),
    ("ar29", "Der Schalter nimmt jeden Wert an", DSH_PY,
     '        if not isinstance(data["expire_automatisch"], bool):\n            return JSONResponse({"error": "expire_automatisch muss wahr oder falsch sein"}, status_code=400)\n', "", T_AR),
    ("ar40", "Das Nachladen waehlt Stellen im Backoff wieder mit aus", TNZ,
     '        if _gilt(_zaehler(_roh(z["fehler"])), _roh(z["zuletzt"]), jetzt) >= MAX_FEHLVERSUCHE:\n            im_backoff += 1\n            continue\n',
     '        if False:\n            im_backoff += 1\n            continue\n', T_AR),
    ("ar41", "Das Nachladen waehlt ohne feste Reihenfolge", TNZ,
     '" ORDER BY (l.value IS NOT NULL), l.value, j.hash",', '" ORDER BY j.hash",', T_AR),
    ("ar42", "Der Fehlzaehler verfaellt nie", TNZ,
     "    if zeit is None or jetzt - zeit >= timedelta(days=FEHLZAEHLER_VERFALL_TAGE):\n        return 0\n    return zaehler\n",
     "    if zeit is None:\n        return 0\n    return zaehler\n", T_AR),
    ("ar43", "Ein Zaehler ohne Zeitstempel (Altbestand) gilt unbegrenzt", TNZ,
     "    if zeit is None or jetzt - zeit >= timedelta(days=FEHLZAEHLER_VERFALL_TAGE):\n        return 0\n    return zaehler\n",
     "    if zeit is not None and jetzt - zeit >= timedelta(days=FEHLZAEHLER_VERFALL_TAGE):\n        return 0\n    return zaehler\n", T_AR),
    ("ar44", "Ein Netzfehler zaehlt gegen die Stelle", TNZ,
     "            if status == nachladen.FEHLER or http == 429:\n", "            if False:\n", T_AR),
    ("ar45", "'Zu viele Anfragen' zaehlt gegen die Stelle", TNZ,
     "            if status == nachladen.FEHLER or http == 429:\n", "            if status == nachladen.FEHLER:\n", T_AR),
    ("ar46", "Mehrere Netzfehler hintereinander beenden die Schleife nicht", TNZ,
     '                if in_folge >= MAX_NETZFEHLER_IN_FOLGE:\n                    abgebrochen = "netz"\n                    break\n',
     '                if False:\n                    abgebrochen = "netz"\n                    break\n', T_AR),
    ("ar47", "Ein Erfolg unterbricht die Folge der Netzfehler nicht", TNZ,
     "                geholt += 1\n                in_folge = 0\n                continue\n", "                geholt += 1\n                continue\n", T_AR),
    ("ar48", "Ein Versuch wird nicht vermerkt", TNZ,
     '            versuch_vermerken(db, z["hash"])\n            if text and', "            if text and", T_AR),
    ("ar49", "Nach dem Verfall zaehlt der alte Stand weiter hoch", TNZ,
     '        db.set_setting(f"refetch_fail:{job_hash}", str(_fehlversuche(db, job_hash) + 1))\n',
     '        db.set_setting(f"refetch_fail:{job_hash}", str(_zaehler(db.get_setting(f"refetch_fail:{job_hash}", "0")) + 1))\n', T_AR),
    ("ar50", "Das Werkzeug setzt den Schalter nicht", ANA,
     "            aufraeum_runde.expire_automatisch_setzen(db, bewerbungen_abschliessen)\n", "            pass\n", T_AR),
    ("ar51", "Das Werkzeug gibt das Intervall nicht weiter", ANA,
     "                    aufraeumen_intervall_tage=aufraeumen_intervall_tage,\n", "", T_AR),
    ("ar60", "Die Karte verspricht keinen taeglichen Lauf mehr", SET_JSX,
     "PBP prüft das auf Wunsch einmal am Tag von selbst", "PBP prüft das auf Knopfdruck", T_ARB),
    ("ar61", "Der Schalter speichert nichts", SET_JSX,
     'await putJson("/api/auto-actions/settings", { expire_automatisch: wert });', "await Promise.resolve(wert);", T_ARB),
    ("ar62", "Das Intervall speichert nichts", SET_JSX,
     'await putJson("/api/automatik/settings", { aufraeumen_intervall_tage: Number(value) });', "await Promise.resolve(value);", T_ARB),
    ("ar63", "Der letzte Lauf nennt den Ausloeser nicht", SET_JSX,
     'const von = { automatik: " (von selbst)", knopf: " (per Knopf)", claude: " (durch Claude)" }[status.last_run_by] || "";', 'const von = "";', T_ARB),
]
KATALOGE["aufraeumrunde"] = M_AUFRAEUMRUNDE
GRUNDLAEUFE["aufraeumrunde"] = (("T_AR", T_AR), ("T_ARB", T_ARB))

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
    p.add_argument("--katalog", choices=tuple(KATALOGE), default="auto_update", help="welche Schutzpruefungen (Vorgabe: auto_update)")
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
