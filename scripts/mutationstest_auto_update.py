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

Vier Kataloge: `auto_update` (Pruefsumme, Signatur, Quelle, Entpacken, Startbaustein, Schema-Schutz, Stufen; #1093),
`speicher` (Loeschen nur unter der Wurzel, zwei Schritte, nie bei laufender Arbeit, Fremdes nur zeigen; #1131) und
`komponenten` (kein Installer ohne Pruefsumme; #1152) und `mail` (Mail-Ordner: Vorgabe aus, genaue Liste; #947).

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




# ── Zweiter Katalog: Speicher & Downloads (#1131) ──
SP = "src/bewerbungs_assistent/services/speicher.py"
T_SP = ["tests/test_v18_speicher_1131.py"]

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

KATALOGE = {"auto_update": M, "speicher": M_SPEICHER, "komponenten": M_KOMPONENTEN, "mail": M_MAIL}
GRUNDLAEUFE = {
    "auto_update": (("T_PR", T_PR), ("T_Q", T_Q), ("T_I", T_I), ("T_B", T_B), ("T_L", T_L), ("T_S", T_S), ("T_E", T_E)),
    "speicher": (("T_SP", T_SP),),
    "komponenten": (("T_KP", T_KP),),
    "mail": (("T_MQ", T_MQ),),
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
    p.add_argument("--katalog", choices=("auto_update", "speicher", "komponenten", "mail"), default="auto_update", help="welche Schutzpruefungen (Vorgabe: auto_update)")
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
