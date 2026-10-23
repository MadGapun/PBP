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
`jobtic` (Quelle mit Auflagen: PBP ruft nichts selbst ab, uebernimmt keine Kontaktdaten, die Karte sagt "Konto nötig"; #1189) und
`elwosa_strom1256` (Elwosa-Strom in der Seitenleiste: die Marke "N neu" zaehlt nach Kennung, der Bereich haelt das Ende bei Hoehenaenderung und
beim Eintreffen der Daten; #1256 — baut das Bundle bei Frontend-Eintraegen neu).

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
T_V = ["tests/test_v18_vorab_auto_update_1199.py"]  # #1199: Vorab-Auto-Update (opt-in)
T_VI = ["tests/test_v18_vorab_installation_1222.py"]  # #1222: ... und seine Installation

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
    ("qu07", "asset_url: ungueltige Fassung erlaubt", AU + "quelle.py", "    if not _fassung.gueltig(version):", "    if False:", T_Q + T_V),
    ("qu08", "asset_url: beliebiger Dateiname erlaubt", AU + "quelle.py", "    if name not in erlaubt:", "    if False:", T_Q),
    ("qu09", "json_holen: andere Adresse erlaubt", AU + "quelle.py", "    if url != API_FREIGABEN:", "    if False:", T_Q),
    ("qu10", "Freigaben: Vorabversionen (Flag) ohne Schalter zugelassen", AU + "quelle.py", '        if eintrag.get("prerelease") and not vorab:', "        if False:", T_Q + T_L + T_V),
    ("qu11", "Freigaben: Entwuerfe zugelassen", AU + "quelle.py", ' or eintrag.get("draft")', "", T_Q + T_L + T_V),
    ("qu12", "Freigaben: Beta-Tag ohne Flag zugelassen", AU + "quelle.py", "        if not vorab and not _fassung.ist_stabil(version):", "        if False:", T_Q + T_V),
    ("qu13", "neueste_fuer_linie: andere Linie erlaubt", AU + "quelle.py", "                  if _fassung.linie(f.version) == linie", "                  if True", T_Q + T_L + T_V),
    ("qu14", "neueste_fuer_linie: aeltere Fassung erlaubt", AU + "quelle.py", "                  and _fassung.ist_neuer(f.version, laufende_fassung)\n", "", T_Q + T_L + T_V),
    ("qu15", "neueste_fuer_linie: nimmt die aelteste statt der neuesten", AU + "quelle.py", "    return max(kandidaten, key=lambda f: _fassung.schluessel(f.version))", "    return min(kandidaten, key=lambda f: _fassung.schluessel(f.version))", T_Q + T_L),
    ("qu21", "kandidat_erlaubt: stabile Installation auf eine Vorab gezogen", AU + "quelle.py", "    return bool(vorab) and not _fassung.ist_stabil(laufende_fassung)", "    return True", T_Q + T_V),
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
    ('in04', "Lauf: Vorabversion erlaubt", AU + "installation.py",
     '    if not quelle.kandidat_erlaubt(version, laufend, vorab):', '    if False:', T_I + T_VI),
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
    ('wg05', 'Stellen-Seite liest die Absicht `oeffnen` nicht', 'frontend/src/pages/JobsPage.jsx',
     '      if (intent.oeffnen) {\n        detailVonRef.current = intent.von || null;\n        setPendingOpenJobHash(String(intent.jobHash));\n      }\n', '', T_WG),
    ('wg06', 'Stellen-Seite oeffnet die gemerkte Stelle nie', 'frontend/src/pages/JobsPage.jsx', '    if (loading || !pendingOpenJobHash) return undefined;\n    const hash = pendingOpenJobHash;', '    return undefined;\n    const hash = pendingOpenJobHash;', T_WG),
    ('wg07', 'Stelle ausserhalb der geladenen Seite: die Einzelantwort wird verworfen', 'frontend/src/pages/JobsPage.jsx', '.then((einzeln) => { if (einzeln) openDetailDialog(einzeln); })', '.then(() => {})', T_WG),
    ('wg08', 'Kontakte-Seite liest die Absicht `kontaktId` nicht', 'frontend/src/pages/ContactsPage.jsx', '      if (intent.kontaktId) {\n', '      if (false) {\n', T_WG),
    ('wg09', 'Kontakt-Dialog: die Verknuepfung ist wieder nur Text', 'frontend/src/pages/ContactsPage.jsx', '{z.ziel ? (', '{false ? (', T_WG),
    ('wg10', 'Bewerbung: der Name der Person fuehrt nirgends hin', 'frontend/src/pages/ApplicationsPage.jsx', 'onClick={() => { const z = zuKontakt(c.id); if (z) navigateTo(z.seite, z.intent); }}', 'onClick={() => {}}', T_WG),
    ('wg11', 'Bewerbungskarte: „Zur Stelle“ tut nichts', 'frontend/src/pages/ApplicationsPage.jsx', '<Button variant="secondary" onClick={() => setJobDetail({ hash: application.job_hash, bewerbungId: application.id })} data-karte-zur-stelle', '<Button variant="secondary" onClick={() => {}} data-karte-zur-stelle', T_WG),
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
    ('vo01', "Update-Seite: statt der Vorabversion steht wieder „Aktuell“", UT,
     '            : vorab ? <Badge tone="amber">Neue Vorabversion: v{vorab.version}</Badge>\n              : zeigeAktuell(au)', '            : zeigeAktuell(au)', T_VO),
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
    ('vo14', "Regel: updateHinweis kennt keine Vorabversion", AUL,
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
    ('bw11', "Handoff einer einzelnen Quelle: ohne die Regel", HO,
     '"Duplikat-Erkennung laufen automatisch, und der Lauf wird verbucht. " + REGEL_IM_ZWEIFEL', '"Duplikat-Erkennung laufen automatisch, und der Lauf wird verbucht."', T_BR),
    ("bw12", "Handoff einer einzelnen Quelle: wieder 'passende Stellen'", HO,
     '"3. Alle Treffer, die fachlich passen oder nahezu passen, mit "', '"3. Passende Stellen mit "', T_BR),
    ('bw13', "Workflow-Prompt der Jobsuche: ohne die Regel", PRM,
     '(einzelne Stellen: stelle_manuell_anlegen()). {REGEL_IM_ZWEIFEL}', '(einzelne Stellen: stelle_manuell_anlegen()).', T_BR),
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
    ('bw19', "Katalogtext von stelle_manuell_anlegen: wieder 'nicht fuer Treffer aus einer Jobboerse'", WK,
     'Browserlauf: im Zweifel eintragen, viele auf einmal mit "\n        "browser_treffer_uebernehmen. Was PBPs eigene Suche schon angelegt "', 'Browserlauf: nicht für Treffer aus einer Jobbörse; die legt die Suche selbst an. Was PBPs eigene Suche schon angelegt "', T_BR),
    ("bw20", "Hinweis zur aussortierten Dublette: das Urteil geht in den Chat", JOBS,
     'an die Stelle (stelle_urteil_speichern): ob sie taugt, "', 'an die Stelle (im Chat): ob sie taugt, "', T_BR),
    ("bw21", "Vorschau: die Blacklist-Abweisung wird auch in der Vorschau protokolliert", JOBS,
     '            if not trocken:     # #1187: die Vorschau schreibt auch kein Protokoll\n', '            if True:\n', T_BR),
    ("bw22", "Vorschau: die Anlage laeuft trotz Vorschau weiter (sie schreibt)", JOBS,
     '        if trocken:\n            # #1187: die Vorschau fragt dasselbe wie die Anlage', '        if False:\n            # #1187: die Vorschau fragt dasselbe wie die Anlage', T_BR),
    ("bw23", "Vorschau: die Sammeluebernahme ruft nie trocken auf", JOBS,
     '                trocken=dry_run)   # #1187: die Vorschau prueft wie der echte Lauf\n', '                trocken=False)\n', T_BR),
    ('bw24', "Vorschau: 'wuerde_angelegt' zaehlt nicht als angelegt", JOBS,
     'if res.get("status") in ("angelegt", "wuerde_angelegt") or (\n', 'if res.get("status") == "angelegt" or (\n', T_BR),
    ('bw25', "Vorschau: dieselbe Stelle zweimal im Aufruf zaehlt zweimal", JOBS,
     '                if res["hash"] in vorschau_hashes:\n                    _skip(e, "duplikat_aktiv",\n', '                if False:\n                    _skip(e, "duplikat_aktiv",\n', T_BR),
    ("bw26", "Vorschau: die Laenge des Volltexts fehlt", JOBS,
     '                    _eintrag["beschreibung_zeichen"] = len(beschreibung)\n', '                    pass\n', T_BR),
    ("bw27", "Vorschau: die Hinweise der Pruefungen fehlen", JOBS,
     '            _befunde_anfuegen(vorschau)\n', '            pass\n', T_BR),
    ("bw28", "Vorschau: der Hash der Stelle fehlt", JOBS,
     '                "id": _kurz(job_hash), "hash": job_hash,\n                "nachricht": f"Vorschau:',
     '                "id": _kurz(job_hash), "hash": "",\n                "nachricht": f"Vorschau:', T_BR),
    ('bw29', "Sammeluebernahme: die aussortierte Dublette erscheint nicht im Eintrag", JOBS,
     '                         "laufende_bewerbung_verdacht"),\n                        ("aussortierte_dublette", "aussortierte_dublette"),\n', '                         "laufende_bewerbung_verdacht"),\n', T_BR),
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
    ('jt17', "Auto-Nachladen: die Auswahl kennt die Auflage nicht", "src/bewerbungs_assistent/services/text_nachzug.py",
     '    ohne, ohne_params = sql_ohne_abruf("url")\n    zeilen = db.connect().execute(\n', '    ohne, ohne_params = "", []\n    zeilen = db.connect().execute(\n', T_JT),
    ('jt18', "Aging-Check: die Auswahl kennt die Auflage nicht", DASH,
     '    _ohne, _ohne_params = sql_ohne_abruf("url")\n    # #1139: feste Reihenfolge', '    _ohne, _ohne_params = "", []\n    # #1139: feste Reihenfolge', T_JT),
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


def _server_json_version() -> str:
    """Die Version, die `server.json` in diesem Baum oben traegt. Der Eintrag i270 sucht genau diese Zeile: stuende die Fassung fest im
    Muster, bricht jeder Release-Kandidat (1.8.0-rc.4) den Katalog, ohne dass sich an der Pruefung etwas geaendert haette."""
    try:
        text = (WURZEL / "server.json").read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except OSError:
        return "1.8.0"
    ende = text.find('",\n  "websiteUrl"')
    anfang = text.rfind('"version": "', 0, ende) + len('"version": "') if ende >= 0 else -1
    return text[anfang:ende] if ende >= 0 and anfang > 0 else "1.8.0"


M_INSTALLER2 = [
    ("i201", "Das Ausrufezeichen im Ordnernamen wird nicht mehr geprueft", IB,
     'if "%PBP_START_ORT:!=%"=="%PBP_START_ORT%" goto :ort_ohne_ausrufezeichen\n', "goto :ort_ohne_ausrufezeichen\n", T_I2),
    ("i202", "Die Pruefung laeuft unter verzoegerter Expansion (das Zeichen ist dann schon weg)", IB,
     'setlocal DisableDelayedExpansion\nset "PBP_START_ORT=%~dp0"\n', 'setlocal EnableDelayedExpansion\nset "PBP_START_ORT=%~dp0"\n', T_I2),
    ("i203", "Nach der Pruefung bleibt die verzoegerte Expansion aus", IB,
     ":profil_ohne_ausrufezeichen\nendlocal\nsetlocal EnableDelayedExpansion\n", ":profil_ohne_ausrufezeichen\nendlocal\nsetlocal DisableDelayedExpansion\n", T_I2),
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
     "DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]](.*[[:space:]/])?start_dashboard\\.py'", "DASH_MUSTER='start_dashboard\\.py'", T_I2),
    ("i241", "Mac (.command): die Prozesssuche weicht von install.sh ab", ICM,
     "DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]](.*[[:space:]/])?start_dashboard\\.py'", "DASH_MUSTER='start_dashboard\\.py'", T_I2),
    ("i242", "Mac/Linux: eine andere Fassung auf dem Port gilt als 'ok'", ISH,
     '    elif [ "$stand" != "$NEUE_FASSUNG" ]; then\n', "    elif false; then\n", T_I2),
    ("i243", "Mac (.command): eine andere Fassung auf dem Port gilt als 'ok'", ICM,
     '    elif [ "$stand" != "$NEUE_FASSUNG" ]; then\n', "    elif false; then\n", T_I2),
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
     f'  "version": "{_server_json_version()}",\n  "websiteUrl"', '  "version": "1.7.0",\n  "websiteUrl"', T_I2),
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
    # CI 16.10.2026 (Exit 139): die Runde lief unter einem Namen, den weder "Daten loeschen" noch der Abbau der Suite sah
    ("ar70", "Die Runde laeuft wieder unter einem Namen ohne pbp- (laufende_arbeit und der Abbau der Suite sehen sie nicht)",
     "src/bewerbungs_assistent/services/automatik_scheduler.py",
     'name="pbp-automatik-aufraeumen"', 'name="automatik-aufraeumen"', T_AR),
    ("ar71", "Die laufende Runde hat keinen Klartext (es erschiene der Thread-Name)", "src/bewerbungs_assistent/services/datenordner.py",
     '        elif n.startswith("pbp-automatik-aufraeumen"):\n            teile.append("die Aufräum-Runde")\n', "", T_AR),
    ("ar72", "Der Takt eines gewoehnlichen Tests startet wieder die echte Runde", "tests/conftest.py",
     '    monkeypatch.setattr(automatik_scheduler, "run_aufraeumen_now",\n                        lambda *a, **k: {"status": "gestartet", "job_id": 0})\n',
     "    pass\n", ["tests/test_v18_keine_echte_aufraeum_runde_im_test.py"]),
]
KATALOGE["aufraeumrunde"] = M_AUFRAEUMRUNDE
GRUNDLAEUFE["aufraeumrunde"] = (("T_AR", T_AR), ("T_ARB", T_ARB))

# ── KI-Schalter: auch die lesenden Werkzeuge fuer Dokument- und Mailtexte (#1147 Punkt 3, Variante B) ──
T_KS = ["tests/test_v18_ki_schalter_lesen_1147.py"]
T_KSB = T_KS + ["tests/test_v18_erste_schritte_1170.py"]
KIZ = "src/bewerbungs_assistent/services/ki_zuordnung.py"

M_KISCHALTER = [
    ("kl01", "dokument_lesen faellt aus der Zuordnung (Volltext geht trotz Schalter weiter)", KIZ,
     '    "dokument_lesen": ("dokumentenanalyse", (\n', '    "dokument_lesen_x": ("dokumentenanalyse", (\n', T_KS),
    ("kl02", "emails_anzeigen faellt aus der Zuordnung (Mailtext geht trotz Schalter weiter)", KIZ,
     '    "emails_anzeigen": ("dokumentenanalyse", (\n', '    "emails_anzeigen_x": ("dokumentenanalyse", (\n', T_KS),
    ("kl03", "dokumente_zur_analyse faellt aus der Zuordnung", KIZ,
     '    "dokumente_zur_analyse": ("dokumentenanalyse", (\n', '    "dokumente_zur_analyse_x": ("dokumentenanalyse", (\n', T_KS),
    ("kl04", "dokument_lesen haengt am falschen Schalter", KIZ,
     '    "dokument_lesen": ("dokumentenanalyse", (\n', '    "dokument_lesen": ("stellenanalyse", (\n', T_KS),
    ("kl05", "emails_anzeigen haengt am falschen Schalter", KIZ,
     '    "emails_anzeigen": ("dokumentenanalyse", (\n', '    "emails_anzeigen": ("coaching", (\n', T_KS),
    ("kl06", "dokument_lesen nennt keine Alternative", KIZ,
     "        f\"Das Dokument bleibt im Dashboard lesbar ({pfad('dokumente')}). Soll Claude es lesen, \"\n"
     "        f\"schalte \\\"Dokumentenanalyse\\\" unter {pfad('claude')} ein.\")),\n",
     "        None)),\n", T_KS),
    ("kl07", "Das Profil wird mitgesperrt (die Grenze verschiebt sich unbemerkt)", KIZ,
     '    "dokumente_batch_analysieren": ("dokumentenanalyse", None),\n',
     '    "dokumente_batch_analysieren": ("dokumentenanalyse", None),\n    "profil_zusammenfassung": ("dokumentenanalyse", None),\n', T_KS),
    ("kl08", "Die Bewerbungsdetails werden mitgesperrt", KIZ,
     '    "dokumente_batch_analysieren": ("dokumentenanalyse", None),\n',
     '    "dokumente_batch_analysieren": ("dokumentenanalyse", None),\n    "bewerbung_details": ("dokumentenanalyse", None),\n', T_KS),
    ("kl10", "Der Satz in den Einstellungen sagt nicht, dass Dokumente und Mails gesperrt sind", "frontend/src/pages/SettingsPage.jsx",
     "Bei „Dokumentenanalyse“ liest Claude dann auch keine Dokumente und Mails mehr. ", "", T_KSB),
    ("kl11", "Der Satz verspricht wieder, Claude lese weiter alles", "frontend/src/pages/SettingsPage.jsx",
     "Dein Profil, deine Bewerbungen und die Stellen kann Claude weiterhin lesen, sonst arbeitet fast nichts mehr; wer gar nichts weitergeben will, trennt PBP in Claude Desktop.",
     "Claude kann Daten dennoch lesen, solange PBP in Claude Desktop eingetragen ist; wer gar nichts weitergeben will, trennt PBP dort.", T_KSB),
]
KATALOGE["kischalter"] = M_KISCHALTER
GRUNDLAEUFE["kischalter"] = (("T_KS", T_KS), ("T_KSB", T_KSB))

# ── Google Jobs: Sperre ohne Original, Hinweise statt Stellen, vorbereitete Suche (#1184 a, d, e) ──
T_GO = ["tests/test_v18_google_original_1184.py"]
T_GOA = T_GO + ["tests/test_1120_google_alert_echte_mails.py", "tests/test_v17124_google_alert_1068.py"]
T_GOB = ["tests/test_v18_google_original_1184_browser.py"]
GAN = "src/bewerbungs_assistent/services/google_angaben.py"
JOBS_PY = "src/bewerbungs_assistent/tools/jobs.py"
SHW = "src/bewerbungs_assistent/services/stellen_hinweise.py"
NLS = "src/bewerbungs_assistent/services/newsletter_service.py"
LBR = "src/bewerbungs_assistent/services/loeschbereiche.py"

M_GOOGLEORIGINAL = [
    ("go01", "Ein Google-Treffer ohne Beleg gilt nie als ohne Beleg", GAN,
     "    return not hat_adresse and not hat_text\n", "    return False\n", T_GO),
    ("go02", "Adresse ODER Text fehlt genuegt fuer die Sperre (statt: beides)", GAN,
     "    return not hat_adresse and not hat_text\n", "    return not hat_adresse or not hat_text\n", T_GO),
    ("go03", "Eine Suchadresse gilt als Anker", GAN,
     '    hat_adresse = (u.lower().startswith(("http://", "https://")) and not ist_google_adresse(u)\n                   and not is_search_result_url(u))\n',
     '    hat_adresse = (u.lower().startswith(("http://", "https://")) and not ist_google_adresse(u))\n', T_GO),
    ("go04", "Eine Google-Adresse gilt als Anker", GAN,
     '    hat_adresse = (u.lower().startswith(("http://", "https://")) and not ist_google_adresse(u)\n                   and not is_search_result_url(u))\n',
     '    hat_adresse = (u.lower().startswith(("http://", "https://")) and not is_search_result_url(u))\n', T_GO),
    ("go05", "Die Suche nennt Firma und Titel nicht als feste Wendung", GAN,
     "    frage = \" \".join(x for x in (f'\"{f}\"' if f else \"\", f'\"{t}\"' if t else \"\", \"Karriere\") if x)\n",
     "    frage = \" \".join(x for x in (f if f else \"\", t if t else \"\", \"Karriere\") if x)\n", T_GO),
    ("go06", "Der Ort fehlt in den Portal-Suchen", GAN,
     '            ort=quote_plus(o)).rstrip("?&")})\n', '            ort="").rstrip("?&")})\n', T_GO),
    ("go07", "Die Websuche ist nicht kodiert", GAN,
     '"https://www.google.com/search?q=" + quote_plus(frage)', '"https://www.google.com/search?q=" + frage', T_GO),
    ("go10", "Die Sperre greift nie", JOBS_PY,
     "        if _gangaben.ohne_beleg(quelle, url, beschreibung) and not force:\n", "        if False:\n", T_GO),
    ("go11", "force hebt die Sperre nicht auf", JOBS_PY,
     "        if _gangaben.ohne_beleg(quelle, url, beschreibung) and not force:\n",
     "        if _gangaben.ohne_beleg(quelle, url, beschreibung):\n", T_GO),
    ("go12", "Die Abweisung nennt die Suche nach dem Original nicht", JOBS_PY,
     '                "original_suchen": _gangaben.original_suchen(titel, firma, ort),\n', "", T_GO),
    ("go13", "Die Abweisung meldet 'angelegt'", JOBS_PY,
     '                "status": "nicht_angelegt",\n', '                "status": "angelegt",\n', T_GO),
    ("go14", "Ein angelegtes Original erledigt den Hinweis nicht", JOBS_PY,
     "            _hinweise.als_angelegt(db, firma, titel, job_hash)\n", "            pass\n", T_GO),
    ("go15", "Das Werkzeug verwirft nichts", JOBS_PY,
     '            ok = (_hinweise.verwerfen(db, hinweis_id) if aktion == "verwerfen"\n                  else _hinweise.wiederherstellen(db, hinweis_id))\n',
     "            ok = True\n", T_GO),
    ("go16", "Die Anleitung an Claude nennt die Ausnahme nicht", JOBS_PY,
     'Ausnahme (#1184): Einen Treffer aus Google OHNE Detail-URL des "', 'Hinweis: Einen Treffer aus Google OHNE Detail-URL des "', T_GO),
    ("go20", "Derselbe Treffer wird vervielfacht", SHW,
     '        if zeile:\n            conn.execute(\n                "UPDATE stellen_hinweise SET ort=?', '        if False:\n            conn.execute(\n                "UPDATE stellen_hinweise SET ort=?', T_GO),
    ("go21", "Die Orte werden ueberschrieben statt nebeneinandergestellt", SHW,
     '                (_orte(zeile["ort"], e.get("ort")), jetzt, hid))', '                (str(e.get("ort") or ""), jetzt, hid))', T_GO),
    ("go22", "Was schon eine Stelle ist, steht als offen da", SHW,
     '             "angelegt" if stelle else "offen", stelle, 1, jetzt, jetzt))', '             "offen", stelle, 1, jetzt, jetzt))', T_GO),
    ("go23", "Die Zahl der Mails zaehlt nicht mit", SHW,
     "COALESCE(anzahl_mails,1)+1", "COALESCE(anzahl_mails,1)", T_GO),
    ("go24", "Ein anderes Profil sieht die Hinweise", SHW,
     '    sql = "SELECT * FROM stellen_hinweise WHERE (profile_id=? OR profile_id IS NULL)"\n',
     '    sql = "SELECT * FROM stellen_hinweise WHERE (? IS NOT NULL OR profile_id IS NULL)"\n', T_GO),
    ("go25", "Auch Erledigtes laesst sich verwerfen", SHW,
     "UPDATE stellen_hinweise SET status='verworfen', aktualisiert_am=? WHERE id=? AND status='offen'",
     "UPDATE stellen_hinweise SET status='verworfen', aktualisiert_am=? WHERE id=?", T_GO),
    ("go26", "Gross-/Kleinschreibung macht einen zweiten Hinweis", SHW,
     '    return re.sub(r"\\s+", " ", str(text or "").strip().lower())\n', '    return re.sub(r"\\s+", " ", str(text or "").strip())\n', T_GO),
    ("go30", "Aus einer Alert-Mail entsteht wieder eine Stelle", NLS,
     "    erg = stellen_hinweise.merken(db, treffer, suchanfrage=anfrage)\n",
     "    erg = stellen_hinweise.merken(db, treffer, suchanfrage=anfrage)\n"
     "    from ..job_scraper import stelle_hash\n"
     "    db.save_jobs([{\"hash\": stelle_hash(\"n\", e[\"titel\"]), \"title\": e[\"titel\"], \"company\": e[\"firma\"], \"location\": e[\"ort\"],\n"
     "                   \"url\": \"\", \"source\": \"newsletter:x\", \"description\": \"\", \"score\": 0, \"_manual_entry\": True} for e in treffer])\n", T_GOA),
    ("go31", "Die Alert-Mail meldet weiter 'uebernommen'", NLS,
     '        "status": "hinweise_notiert",\n        "label": label,\n', '        "status": "uebernommen",\n        "label": label,\n', T_GOA),
    ("go40", "Die Mail wird nach den Hinweisen nicht archiviert (Upload)", "src/bewerbungs_assistent/dashboard.py",
     'newsletter_result.get("status") in ("uebernommen", "hinweise_notiert")', 'newsletter_result.get("status") == "uebernommen"', T_GO),
    ("go41", "Verwerfen eines unbekannten Hinweises meldet Erfolg", "src/bewerbungs_assistent/dashboard.py",
     '        return JSONResponse({"error": "Hinweis nicht gefunden oder nicht mehr offen."}, status_code=404)\n', "        return {\"status\": \"ok\"}\n", T_GO),
    ("go50", "Die Hinweise gehoeren keinem Loeschbereich", LBR,
     '        "stellen_hinweise",\n    ),\n', "    ),\n", T_GO),
    ("go60", "Die Hinweise sind nicht eingeklappt", "frontend/src/components/StellenHinweise.jsx",
     "  const [offen, setOffen] = useState(false);\n", "  const [offen, setOffen] = useState(true);\n", T_GOB),
    ("go61", "Verwerfen speichert nichts", "frontend/src/components/StellenHinweise.jsx",
     "await postJson(`/api/stellen-hinweise/${h.id}/verwerfen`, {});", "await Promise.resolve();", T_GOB),
    ("go62", "Die Suche nach dem Original fehlt", "frontend/src/components/StellenHinweise.jsx",
     "{h.suche?.[0]?.url && (", "{false && (", T_GOB),
    ("go63", "Der Block steht nicht auf der Stellen-Seite", "frontend/src/pages/JobsPage.jsx",
     "      <StellenHinweise anlass={reloadKey} />\n", "", T_GOB),
]
KATALOGE["googleoriginal"] = M_GOOGLEORIGINAL
GRUNDLAEUFE["googleoriginal"] = (("T_GO", T_GO), ("T_GOB", T_GOB))

# ── Browser-Ernte: ein Sammelweg fuer alle Quellen, Lauf verbuchen, "Stellen zu pruefen" (#1187 Stufe 2/3) ──
T_BU = ["tests/test_v18_browser_uebernahme_1187.py"]
T_BUB = ["tests/test_v18_browser_uebernahme_1187_browser.py"]
BU_SZP = "src/bewerbungs_assistent/services/stellen_zu_pruefen.py"
BU_BUE = "src/bewerbungs_assistent/services/browser_uebernahme.py"
BU_DB = "src/bewerbungs_assistent/database.py"
BU_APR = "src/bewerbungs_assistent/services/aussortier_protokoll.py"
BU_AUS = "src/bewerbungs_assistent/services/aussortieren.py"
BU_DASH = "src/bewerbungs_assistent/dashboard.py"
BU_JP = "frontend/src/pages/JobsPage.jsx"
BU_SZPJ = "frontend/src/components/StellenZuPruefen.jsx"
BU_DP = "frontend/src/pages/DashboardPage.jsx"
BU_WEGE = "frontend/src/lib/wege.js"

M_BROWSERUEBERNAHME = [
    ("bu01", "Die Vorschau verbucht den Lauf", JOBS_PY,
     '        if not dry_run:\n            db.record_browser_run(quelle_n, rohtreffer=trichter["rohtreffer"], neu=trichter["angelegt"],\n',
     '        if True:\n            db.record_browser_run(quelle_n, rohtreffer=trichter["rohtreffer"], neu=trichter["angelegt"],\n', T_BU),
    ("bu02", "Ein Lauf ohne Anlage wird nicht verbucht", JOBS_PY,
     '            db.record_browser_run(quelle_n, rohtreffer=trichter["rohtreffer"], neu=trichter["angelegt"],\n',
     '            (db.record_browser_run if trichter["angelegt"] else (lambda *a, **k: None))(quelle_n, rohtreffer=trichter["rohtreffer"], neu=trichter["angelegt"],\n', T_BU),
    ("bu03", "Eine leere Uebergabe wird nicht verbucht", JOBS_PY,
     '                db.record_browser_run(quelle_n, rohtreffer=trichter["rohtreffer"], neu=0,\n',
     '                (lambda *a, **k: None)(quelle_n, rohtreffer=trichter["rohtreffer"], neu=0,\n', T_BU),
    ("bu04", "Ein Urteil wird auch ohne gelesenen Volltext gespeichert", JOBS_PY,
     '                    elif len(beschreibung) < MIN_BESCHREIBUNG and urteil != "NICHT_BEURTEILBAR":\n',
     '                    elif False:\n', T_BU),
    ("bu05", "Ein Urteil ausserhalb der Kategorien wird nicht abgewiesen", JOBS_PY,
     '                    if urteil not in _bu.URTEILE:\n', '                    if False:\n', T_BU),
    ("bu06", "Nach dem Lesen aussortiert mit der Herkunft ich", JOBS_PY,
     'collect_hints=False, herkunft="claude")', 'collect_hints=False, herkunft="ich")', T_BU),
    ("bu07", "Die Vorschau sortiert aus", JOBS_PY,
     '                if grund_roh and not dry_run:\n', '                if grund_roh:\n', T_BU),
    ("bu08", "Die Vorschau speichert das Urteil", JOBS_PY,
     '                if urteil and not dry_run:\n', '                if urteil:\n', T_BU),
    ("bu09", "Ein erfundener Grund wird nicht normalisiert", JOBS_PY,
     '                    gruende = _normalize_reason_list(grund_roh)\n', '                    gruende = [grund_roh]\n', T_BU),
    ("bu10", "Google ohne Original nennt die Suche nicht", JOBS_PY,
     '                if _gangaben.ist_google_quelle(quelle_n):\n', '                if False:\n', T_BU),
    ("bu11", "Eine Anlage ohne Volltext wird nicht gezaehlt", JOBS_PY,
     '                    trichter["ohne_volltext"] += 1\n', '                    pass\n', T_BU),
    ("bu12", "Die Anker-Warnung der Anlage geht verloren", JOBS_PY,
     '                    eintrag["anker_warnung"] = res["anker_warnung"]\n', '                    pass\n', T_BU),
    ("bu13", "Ein fehlender Login verbucht einen Lauf", JOBS_PY,
     '        if login_fehlt:\n            return {\n                "status": "wartet_auf_login", "quelle": quelle_n,\n',
     '        if login_fehlt:\n            db.record_browser_run(quelle_n, rohtreffer=0)\n            return {\n                "status": "wartet_auf_login", "quelle": quelle_n,\n', T_BU),
    ("bu14", "Die Quelle wird nicht auf Kleinschreibung gebracht", JOBS_PY,
     '        quelle_n = _gangaben.quelle_normalisiert(quelle)         # #1201: "Google Jobs" wird gespeichert als google_jobs\n        if not quelle_n:\n            return {"fehler": "quelle fehlt (z.B. \'stepstone\'',
     '        quelle_n = str(quelle or "").strip()\n        if not quelle_n:\n            return {"fehler": "quelle fehlt (z.B. \'stepstone\'', T_BU),
    ("bu15", "Die Vorgabe ist der echte Lauf statt der Vorschau", JOBS_PY,
     '                                    dry_run: bool = True,\n                                    rohtreffer: int = 0,\n',
     '                                    dry_run: bool = False,\n                                    rohtreffer: int = 0,\n', T_BU),
    ("bu20", "Ein Lauf ohne Rohtreffer gilt als ok", BU_DB,
     '"ok" if int(rohtreffer or 0) > 0 else "silent"', '"ok"', T_BU),
    ("bu21", "Die angelegten Stellen des Laufs werden nicht mitgeschrieben", BU_DB,
     '                 int(neu or 0), 0.0, "", ("Browserlauf: "', '                 0, 0.0, "", ("Browserlauf: "', T_BU),
    ("bu23", "Die Datenbank kennt die Herkunft claude nicht", BU_DB,
     '        wer = herkunft if herkunft in ("automatik", "claude") else "ich"\n',
     '        wer = herkunft if herkunft in ("automatik",) else "ich"\n', T_BU),
    ("bu24", "Das Protokoll liest die Herkunft claude als unbekannt", BU_APR,
     '    if gespeichert in ("ich", "automatik", "claude"):\n', '    if gespeichert in ("ich", "automatik"):\n', T_BU),
    ("bu25", "Das Protokoll laesst sich nicht nach claude filtern", BU_APR,
     'HERKUENFTE = ("ich", "automatik", "claude", "unbekannt")\n', 'HERKUENFTE = ("ich", "automatik", "unbekannt")\n', T_BU),
    ("bu26", "Das Aussortieren reicht die Herkunft nicht weiter", BU_AUS,
     '    db.dismiss_job(job_hash, reason_str, herkunft=herkunft)\n', '    db.dismiss_job(job_hash, reason_str)\n', T_BU),
    ("bu30", "Stellen mit laufender Bewerbung warten mit", BU_SZP,
     '        if db._public_job_hash(z["hash"], z["profile_id"]) in beworbene:\n            continue\n',
     '        if False:\n            continue\n', T_BU),
    ("bu31", "Beworbene werden mit der Speicher-Kennung verglichen statt mit der oeffentlichen", BU_SZP,
     '        if db._public_job_hash(z["hash"], z["profile_id"]) in beworbene:\n',
     '        if z["hash"] in beworbene:\n', T_BU),
    ("bu32", "Stellen einer Firma auf der Blacklist warten mit", BU_SZP,
     '        if sperren and blacklist_regel.treffer(sperren, z["company"] or "", z["title"] or ""):\n', '        if False:\n', T_BU),
    ("bu33", "Beurteilte Stellen zaehlen als ungeprueft", BU_SZP,
     '        if (z["analyse_urteil"] or "").strip() or (z["gesichtet_am"] or "").strip():\n',
     '        if (z["gesichtet_am"] or "").strip():\n', T_BU),
    ("bu34", "Angesehene Stellen zaehlen als ungeprueft", BU_SZP,
     '        if (z["analyse_urteil"] or "").strip() or (z["gesichtet_am"] or "").strip():\n',
     '        if (z["analyse_urteil"] or "").strip():\n', T_BU),
    ("bu35", "Auch Altes zaehlt als neu", BU_SZP,
     '        if str(z["found_at"] or "")[:10] >= tag_grenze:\n', '        if True:\n', T_BU),
    ("bu36", "Jede aussortierte Stelle zaehlt als von Claude aussortiert", BU_SZP,
     "        \"WHERE is_active=0 AND dismissed_by='claude' AND (profile_id=? OR profile_id IS NULL) \"\n",
     "        \"WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) \"\n", T_BU),
    ("bu37", "Die Liste der Karte ist unbegrenzt", BU_SZP,
     '    for z in zeilen[:MAX_LISTE]:\n', '    for z in zeilen:\n', T_BU),
    ("bu38", "Ein anderes Profil sieht die wartenden Stellen", BU_SZP,
     '            "WHERE is_active=1 AND (profile_id=? OR profile_id IS NULL)", (pid,)):\n',
     '            "WHERE is_active=1 AND (? IS NOT NULL OR profile_id IS NULL)", (pid,)):\n', T_BU),
    ("bu39", "Die Karte nennt den Grund nicht", BU_SZP,
     '            "grund": gruende[0] if gruende else "",\n', '            "grund": "",\n', T_BU),
    ("bu40", "Ein Anzeigentext allein ist kein Anker", BU_BUE,
     '    return u.startswith(("http://", "https://")) or len(str(beschreibung or "").strip()) >= min_beschreibung\n',
     '    return u.startswith(("http://", "https://"))\n', T_BU),
    ("bu41", "Eine Adresse allein ist kein Anker", BU_BUE,
     '    return u.startswith(("http://", "https://")) or len(str(beschreibung or "").strip()) >= min_beschreibung\n',
     '    return len(str(beschreibung or "").strip()) >= min_beschreibung\n', T_BU),
    ("bu50", "Die Schnittstelle nennt nichts", BU_DASH,
     '    return stellen_zu_pruefen.uebersicht(_db)\n',
     '    return {"ungeprueft": 0, "neu": 0, "tage": 14, "von_claude_aussortiert": 0, "aussortiert": []}\n', T_BU + T_BUB),
    ("bf01", "Der Sprung setzt den Pruefstand nicht", BU_JP,
     '        pruefstand: intent.pruefstand || "",\n', '        pruefstand: "",\n', T_BUB),
    ("bf02", "Der Sprung in Ausgeblendet bleibt in der aktiven Ansicht", BU_JP,
     '        view: intent.view === "dismissed" ? "dismissed" : "active",\n', '        view: "active",\n', T_BUB),
    ("bf03", "Die Herkunft claude hat kein Etikett", BU_JP,
     '  claude: "von Claude gelesen und aussortiert",\n', '', T_BU + T_BUB),
    ("bf04", "Zurueckholen speichert nichts", BU_SZPJ,
     '      await postJson("/api/jobs/restore", { hash });\n', '      await Promise.resolve();\n', T_BUB),
    ("bf05", "Die Karte verschwindet, wenn nichts Neues wartet", BU_SZPJ,
     '  if (!neu && !claude) return null;\n', '  if (!neu) return null;\n', T_BUB),
    ("bf06", "Die Liste der aussortierten Stellen ist aufgeklappt", BU_SZPJ,
     '  const [offen, setOffen] = useState(false);\n', '  const [offen, setOffen] = useState(true);\n', T_BUB),
    ("bf07", "Der Grund steht roh da", BU_SZPJ,
     '{stelle.grund ? <span className="text-muted"> — {grundText(stelle.grund)}</span> : null}',
     '{stelle.grund ? <span className="text-muted"> — {stelle.grund}</span> : null}', T_BUB),
    ("bf08", "Der Weg zu den ungeprueften Stellen setzt keinen Filter", BU_WEGE,
     '  return { seite: "stellen", intent: { pruefstand: "ungeprueft" } };\n',
     '  return { seite: "stellen", intent: { pruefstand: "" } };\n', T_BUB),
    ("bf09", "Die Karte steht nicht auf dem Dashboard", BU_DP,
     '        <StellenZuPruefen navigateTo={navigateTo} anlass={reloadKey} />\n', '', T_BUB),
    ("bf10", "Die Karte zaehlt nach dem Zurueckholen nicht neu", BU_SZPJ,
     '      setDaten(await laden());\n', '      await laden();\n', T_BUB),
]
KATALOGE["browseruebernahme"] = M_BROWSERUEBERNAHME
GRUNDLAEUFE["browseruebernahme"] = (("T_BU", T_BU), ("T_BUB", T_BUB))

# ── Bedienungspruefung 1.8: schmale Fenster, Vorspann, eine Navigation, Kopierknoepfe, Erklaertexte, Texterkennung (#1170 U10-U17) ──
T_B15 = ["tests/test_v18_seitenleiste_schmal_1170.py"]
T_B16 = ["tests/test_v18_stellen_vorspann_1170.py"]
T_B17 = ["tests/test_v18_navigation_zahlen_1170.py"]
T_B10 = ["tests/test_v18_bedienung_1170_u10_u12.py"]
B_SL = "frontend/src/lib/seitenleiste.js"
B_APP = "frontend/src/App.jsx"
B_BH = "frontend/src/components/BrowserHandoffKarte.jsx"
B_JP = "frontend/src/pages/JobsPage.jsx"
B_SP = "frontend/src/pages/SettingsPage.jsx"
B_WS = "src/bewerbungs_assistent/services/workspace_service.py"
B_SB = "frontend/src/components/Sidebar.jsx"
B_DP = "frontend/src/pages/DashboardPage.jsx"
B_PO = "frontend/src/components/ProfileOnboarding.jsx"
B_UT = "frontend/src/components/UpdatesTab.jsx"
B_ET = "frontend/src/components/ErklaerText.jsx"
B_EL = "frontend/src/lib/erklaertexte.js"
B_UH = "frontend/src/lib/uploadHinweis.js"
B_DOC = "frontend/src/pages/DocumentsPage.jsx"

M_BEDIENUNG = [
    ("bd01", "U15: schmal gilt nie", B_SL,
     "export const SCHMAL_BIS_PX = 900;\n", "export const SCHMAL_BIS_PX = 1;\n", T_B15),
    ("bd03", "U15: im schmalen Fenster ist die Leiste ohne Wahl ausgeklappt", B_SL,
     "  if (schmal) return wahlSchmal === null || wahlSchmal === undefined ? true : Boolean(wahlSchmal);\n",
     "  if (schmal) return wahlSchmal === null || wahlSchmal === undefined ? false : Boolean(wahlSchmal);\n", T_B15),
    ("bd04", "U15: die Wahl im schmalen Fenster landet beim breiten Schluessel", B_APP,
     "    if (fensterSchmal) {\n      setWahlSchmal(next);\n", "    if (false) {\n      setWahlSchmal(next);\n", T_B15),
    ("bd05", "U15: die Leiste hoert nicht auf die Fensterbreite", B_APP,
     "    const aendern = () => setFensterSchmal(istSchmal(window.innerWidth));\n", "    const aendern = () => {};\n", T_B15),
    ("bd10", "U16: die Browser-Karte steht auch nur mit den optionalen Quellen", B_BH,
     "  if (!daten?.prompt || !uebersprungen.length) return null;\n",
     "  if (!daten?.prompt || (!uebersprungen.length && !optional.length)) return null;\n", T_B16),
    ("bd11", "U16: die Kennzahlen stehen erst ab 1280 px in einer Zeile", B_JP,
     '<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-stellen-kennzahlen>',
     '<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-stellen-kennzahlen>', T_B16),
    ("bd20", "U17: die Seitenleiste fuehrt die Unterpunkte der Einstellungen wieder", B_APP,
     '    sidebarSubNavigation = null;\n  } else if (page === "kontakte") {\n',
     '    sidebarSubNavigation = { items: SETTINGS_REITER.map((r) => ({ id: r.id, label: r.label })), onSelect: () => {} };\n  } else if (page === "kontakte") {\n', T_B17),
    ("bd21", "U17: der Pfad oben nennt den Reiter nicht", B_SP,
     '    setSubPath?.(SETTINGS_REITER.find((r) => r.id === settingsTab)?.label || "");\n',
     '    setSubPath?.("");\n', T_B17),
    ("bd22", "U17: die Zahl der Stellen hat kein Wort", B_WS,
     '        kurz["stellen"] = "aktiv"\n', '        kurz["stellen"] = ""\n', T_B17),
    ("bd23", "U17: die Seitenleiste zeigt das Wort nicht", B_SB,
     "                          {badgeWords[tab.id] ? (\n", "                          {false ? (\n", T_B17),
    ("bd24", "U17: eine Zahl ohne Bedeutung bekommt trotzdem ein Wort", B_WS,
     '    if faellig:\n        kurz["bewerbungen"] = "fällig"\n', '    if True:\n        kurz["bewerbungen"] = "fällig"\n', T_B17),
    ("bd30", "U10: Gespraech starten kopiert wieder die lange Anleitung", B_DP,
     "                      onClick={() => copyPrompt(STARTSATZ, {\n", '                      onClick={() => copyPrompt("/ersterfassung", {\n', T_B10),
    ("bd31", "U10: im Onboarding-Panel kopiert der Knopf die lange Anleitung", B_PO,
     "        <Button variant=\"secondary\" onClick={copyStartsatz}>\n", "        <Button variant=\"secondary\" onClick={copyConversationCommand}>\n", T_B10),
    ("bd32", "U10: die Updates-Seite hat keinen Mit-Claude-Knopf", B_UT,
     "              <MitClaude>Updates erklären</MitClaude>\n", "              Updates erklären\n", T_B10),
    ("bd40", "U11: ein Erklaertext steht immer aufgeklappt", B_ET,
     "  const offen = aufgeklappt(alle, einzeln);\n", "  const offen = true;\n", T_B10),
    ("bd41", "U11: der Schalter laesst die Einzelwahlen stehen", B_EL,
     "      weg.forEach((k) => s.removeItem(k));\n", "", T_B10),
    ("bd42", "U11: ohne gemerkte Wahl ist alles eingeklappt", B_EL,
     '  return text !== "0";\n', '  return text === "1";\n', T_B10),
    ("bd43", "U11: die Wahl je Erklaertext wird nicht gemerkt", B_ET,
     "          schreibeEinzeln(id, !offen);\n", "", T_B10),
    ("bd50", "U12: ein Scan ohne Komponente bekommt keinen Hinweis", B_UH,
     '  if (ocr.ocr === "erforderlich") {\n', "  if (false) {\n", T_B10),
    ("bd51", "U12: die Dokumente-Seite zeigt den Hinweis nicht", B_DOC,
     "      for (const hinweis of ocrHinweise(antworten)) {\n", "      for (const hinweis of []) {\n", T_B10),
    ("bd52", "U12: der Knopf fuehrt auf den falschen Reiter", B_DOC,
     'navigateTo("einstellungen", { tab: "erweiterungen" })', 'navigateTo("einstellungen", { tab: "updates" })', T_B10),
]
KATALOGE["bedienung1170"] = M_BEDIENUNG
GRUNDLAEUFE["bedienung1170"] = (("T_B15", T_B15), ("T_B16", T_B16), ("T_B17", T_B17), ("T_B10", T_B10))

# ── Wege durch PBP, Baustein 3-5: Weg-Leiste, Rueckweg, Listenkoepfe, die Leiste der Firma (#1171, G85) ──
T_LK = ["tests/test_v18_listen_zuerst_1171.py"]
T_WL = ["tests/test_v18_weg_leiste_1171.py"]
T_KN = ["tests/test_v18_knoten_tests_1171.py"]
L_LU = "frontend/src/components/ListenUebersicht.jsx"
L_AP = "frontend/src/pages/ApplicationsPage.jsx"
L_JP = "frontend/src/pages/JobsPage.jsx"
L_FA = "frontend/src/components/FirmenAnsicht.jsx"
L_CP = "frontend/src/pages/ContactsPage.jsx"
L_WG = "frontend/src/lib/wegleiste.js"
L_WL = "frontend/src/components/WegLeiste.jsx"
L_APP = "frontend/src/App.jsx"
L_UI = "frontend/src/components/ui.jsx"

M_LEISTE = [
    # Baustein 5: der Listenkopf
    ("lk01", "Listenkopf: ohne gemerkte Wahl ist er aufgeklappt", L_LU,
     '    return window.localStorage.getItem(PRAEFIX + id) === "auf";\n',
     '    return window.localStorage.getItem(PRAEFIX + id) !== "zu";\n', T_LK),
    ("lk02", "Listenkopf: die Wahl wird nicht gemerkt", L_LU,
     "onClick={() => { setOffen(!offen); schreiben(id, !offen); }}",
     "onClick={() => { setOffen(!offen); }}", T_LK),
    ("lk03", "Listenkopf: der Hinweis-Knopf fehlt in der Zeile", L_LU,
     "        {aktion}\n      </div>\n", "      </div>\n", T_LK),
    ("lk04", "Listenkopf: der Suchstand fehlt in der Zeile", L_LU,
     '        {status ? <span className="text-[12px] text-muted" data-listen-uebersicht-status>{status}</span> : null}\n', "", T_LK),
    ("lk05", "Listenkopf: die Kennzahlen stehen immer da", L_LU,
     '      {offen ? <div className="mt-4 grid gap-4" data-listen-uebersicht-inhalt>{children}</div> : null}\n',
     '      {true ? <div className="mt-4 grid gap-4" data-listen-uebersicht-inhalt>{children}</div> : null}\n', T_LK),
    ("lk07", "Bewerbungen: der Hinweis-Knopf fehlt", L_AP,
     "          aktion={nextStep.actionLabel ? (\n", "          aktion={false ? (\n", T_LK),
    ("lk08", "Bewerbungen: die Karten tragen keinen Haken", L_AP,
     "data-bewerbungskarte={application.id} ", "", T_LK),
    ("lk09", "Stellen: „Zuletzt aktualisiert“ steht nicht in der Filterkarte", L_JP,
     "data-stellen-zuletzt>", "data-stellen-zuletzt-weg>", T_LK),
    ("lk10", "Stellen: der Suchstand steht nicht in der Zeile des Kopfs", L_JP,
     "          status={suchStatusText}\n", "", T_LK),
    ("lk11", "Kontakte: die Karten tragen keinen Haken", L_CP,
     "      data-kontaktkarte={contact.id}\n", "", T_LK),
    # Baustein 3: die Leiste (Rechnung und Zeichnung)
    ("wl01", "Leiste: bei einem Gespraech steht „Nachfassen“", L_WG,
     '    haupt = { aktion: "gespraech_vorbereiten", label: "Gespräch vorbereiten", mitClaude: true };\n',
     '    haupt = { aktion: "nachfassen", label: "Nachfassen", mitClaude: true };\n', T_KN + T_WL),
    ("wl02", "Leiste: eine beendete Bewerbung bekommt trotzdem einen Schritt", L_WG,
     "  } else if (NACHFASSEN.has(s) || (nachfassenFaellig && !ENDE.has(s))) {\n",
     "  } else if (NACHFASSEN.has(s) || nachfassenFaellig) {\n", T_KN),
    ("wl03", "Leiste: die Zahl der Personen steht nicht dabei", L_WL,
     '                {f.anzahl > 1 ? <span className="text-xs text-muted">{f.anzahl}</span> : null}\n', "", T_WL),
    ("wl04", "Leiste: ein Fall mit mehreren Eintraegen oeffnet blind den ersten", L_WL,
     'onClick={() => (einzeln ? oeffnen(f.eintraege[0].ziel) : setOffen(istOffen ? "" : f.id))}',
     "onClick={() => oeffnen(f.eintraege[0].ziel)}", T_WL),
    # Baustein 4: der Rueckweg und die Zurueck-Taste
    ("wl05", "Rueckweg: nennt nicht, woher man kam", L_WL,
     '  const rueckLabel = von?.label ? `Zurück zu ${von.label}` : leiste.zurueck?.label || "Zurück";\n',
     '  const rueckLabel = leiste.zurueck?.label || "Zurück";\n', T_WL),
    ("wl06", "Rueckweg: fuehrt nicht dorthin, woher man kam", L_WL,
     "    if (von?.seite) {\n      navigateTo(von.seite, { ...(von.intent || {}), zurueckVon: true });\n    } else {\n      onZurueck?.();\n    }\n",
     "    onZurueck?.();\n", T_WL),
    ("zt01", "Zurueck-Taste: der Dialog meldet sich nicht im Stapel an", L_UI,
     "    dialogStapel.push(eintrag);\n    return () => {\n      const i = dialogStapel.indexOf(eintrag);\n",
     "    return () => {\n      const i = dialogStapel.indexOf(eintrag);\n", T_WL),
    ("zt02", "Zurueck-Taste: das Schliessen von Hand laesst einen toten Schritt im Verlauf", L_UI,
     "          if (window.history.state?.pbpDialog === id) window.history.back();\n", "", T_WL),
    ("zt03", "Zurueck-Taste: schliesst alle Dialoge statt nur den obersten", L_UI,
     "    if (oben.id === aktuell) break;       // sein Eintrag liegt noch im Verlauf: er bleibt offen\n", "", T_WL),
    # Baustein 3 (Rest): die Leiste der Firma
    ("fl01", "Firma: dieselbe Bewerbung zaehlt doppelt", L_WG,
     "      if (gesehen.has(schluessel)) continue;\n", "", T_KN),
    ("fl02", "Firma: der Rueckweg kennt die Herkunft nicht", L_FA,
     "          von={von}\n          onZurueck={zurueck}\n", "          von={null}\n          onZurueck={zurueck}\n", T_WL),
    ("fl03", "Firma: die Herkunft kommt bei der Ansicht nicht an", L_CP,
     "nonce: intent.nonce, von: intent.von || null });\n", "nonce: intent.nonce, von: null });\n", T_WL),
    ("fl04", "Firma: die Leiste steht nicht im festen Kopf", L_FA,
     "  return slot ? createPortal(children, slot) : children;\n", "  return children;\n", T_WL),
    ("fl05", "Firma: die Stellen fehlen unter den Faellen", L_WG,
     '    gruppe("stelle", "stellen", "Stellen"),\n', "", T_WL + T_KN),
    ("fl06", "Firma: die Leiste erfindet einen Hauptknopf", L_WG,
     '  return leiste({ art: "firma", zurueckLabel, faelle, schritt: { haupt: null, weitere: [] } });\n',
     '  return leiste({ art: "firma", zurueckLabel, faelle, schritt: { haupt: { aktion: "firma_anlegen", label: "Als Firma anlegen", mitClaude: false }, weitere: [] } });\n',
     T_WL + T_KN),
    ("fl07", "Firma: der Rueckweg fuehrt nicht in die Liste", L_FA,
     "          onZurueck={zurueck}\n          className=", "          onZurueck={() => {}}\n          className=", T_WL),
    ("fl08", "App: der Platz fuer die Leiste im Kopf fehlt", L_APP,
     '          <div id="weg-leiste-slot" className="px-5 empty:hidden sm:px-8" />\n', "", T_WL),
]
KATALOGE["wegleiste1171"] = M_LEISTE
GRUNDLAEUFE["wegleiste1171"] = (("T_LK", T_LK), ("T_WL", T_WL), ("T_KN", T_KN))

# ── Funde der unabhaengigen Pruefung des Release-Zweigs (14.10.2026, #1201-#1220) ──
T_PB = ["tests/test_v18_pruefung_backend_1201_1206.py"]
T_PF = ["tests/test_v18_pruefung_frontend_1210_1215.py"]
T_PI = ["tests/test_v18_installer_pruefung_1216_1220.py"]
T_BA = ["tests/test_v18_bat_bloecke_1224.py"]  # #1224: keine Klammer in Kommentaren eines Klammerblocks
T_OL = ["tests/test_v18_ollama_probe_1227.py"]  # #1227: kurze Verbindungsprobe statt 2 x 2 s Zeitablauf
T_VS = ["tests/test_v18_vorab_schalter_1226.py"]  # #1226: der Schalter aendert die Frage, die Antwort wird neu geholt
T_RG = ["tests/test_v18_windows_liste_1228.py"]  # #1228: DisplayVersion nennt die laufende Fassung
T_UM = ["tests/test_v18_umschalten_richtung_1229.py"]  # #1229: Umschalten nach vorn heisst nicht „zurueckgeschaltet“
T_VM = ["tests/test_v18_vermittler_endkunde_1198.py", "tests/test_v17126_dubletten_1076.py",
        "tests/test_v17143_schon_beworben_1126.py", "tests/test_v17143_schon_beworben_anschluesse_1126.py"]  # #1198
DD_PY = "src/bewerbungs_assistent/duplicate_detection.py"
HINWEIS_PY = "src/bewerbungs_assistent/services/bewerbungs_hinweis.py"
UPD_JSX = "frontend/src/components/UpdatesTab.jsx"
WL_PY = "src/bewerbungs_assistent/services/auto_update/windows_liste.py"
AUJS = "frontend/src/lib/autoUpdate.js"
TOOL_UPDATE = "src/bewerbungs_assistent/tools/update.py"
LLM_PY = "src/bewerbungs_assistent/services/llm_service.py"
T_PW = ["tests/test_v18_installer_rest_1149.py", "tests/test_v18_auto_update_installer_bat.py",
        "tests/test_v18_auto_update_installer_aufraeumen.py"]
T_PD = ["tests/test_v18_aufraeum_runde_1139.py", "tests/test_v18_google_original_1184.py"]
GA_PY = "src/bewerbungs_assistent/services/google_angaben.py"
TN_PY = "src/bewerbungs_assistent/services/text_nachzug.py"
SH_PY = "src/bewerbungs_assistent/services/stellen_hinweise.py"
JOBS_TOOL = "src/bewerbungs_assistent/tools/jobs.py"
UI_JSX = "frontend/src/components/ui.jsx"
APP_JSX = "frontend/src/App.jsx"
WL_JSX = "frontend/src/components/WegLeiste.jsx"
IJ_JSX = "frontend/src/components/InlineJobDetailModal.jsx"
AP_JSX = "frontend/src/pages/ApplicationsPage.jsx"
JP_JSX = "frontend/src/pages/JobsPage.jsx"
INST_SH = "installer/install.sh"
INST_CMD = "INSTALLIEREN.command"
DEINST_SH = "installer/deinstallieren.sh"

M_PRUEFUNG = [
    # ── #1201: eine Schreibweise fuer die Google-Quelle ──
    ("pb01", "Google-Quelle: nur noch der exakte Schluessel zaehlt", GA_PY,
     "    return bool(google_schluessel(quelle))\n", "    return str(quelle or \"\").strip().lower() in GOOGLE_QUELLEN\n", T_PB),
    ("pb02", "Google-Quelle: „Google“ allein ist keine Google-Quelle mehr", GA_PY,
     "\"googleforjobs\": \"google_jobs\", \"google\": \"google_jobs\",\n", "\"googleforjobs\": \"google_jobs\",\n", T_PB),
    ("pb03", "Anlage von Hand: der Schluessel wird nicht normalisiert", JOBS_TOOL,
     "        quelle = _g1201.google_schluessel(quelle) or quelle\n", "        quelle = quelle\n", T_PB),
    ("pb04", "Browser-Uebernahme: der Schluessel wird nur kleingeschrieben", JOBS_TOOL,
     "        quelle_n = _gangaben.quelle_normalisiert(quelle)         # #1201: \"Google Jobs\" wird gespeichert als google_jobs\n",
     "        quelle_n = str(quelle or \"\").strip().lower()\n", T_PB),
    # ── #1202: der verfallene Fehlzaehler ──
    ("pb05", "Nachladen: der verfallene Zaehler wird vor dem Zeitstempel nicht gestrichen", TN_PY,
     "            verfallenen_zaehler_loeschen(db, z[\"hash\"])\n", "            pass\n", T_PB),
    ("pb06", "Nachladen: ein verfallener Zaehler gilt nie als zu streichen", TN_PY,
     "        if roh > 0 and _fehlversuche(db, job_hash) == 0:\n", "        if False:\n", T_PB),
    # ── #1203/#1205: die Hinweise aus Alert-Mails ──
    ("pb07", "Hinweise: das Anlegen vergleicht wieder mit SQL-LOWER (nur ASCII)", SH_PY,
     "            \"AND norm_hinweis(firma)=? AND norm_hinweis(titel)=?\",\n",
     "            \"AND LOWER(TRIM(firma))=? AND LOWER(TRIM(titel))=?\",\n", T_PB),
    ("pb08", "Hinweise: der Vergleich kuerzt den Leerraum innen nicht", SH_PY,
     "    return re.sub(r\"\\s+\", \" \", str(text or \"\").strip().lower())\n",
     "    return str(text or \"\").strip().lower()\n", T_PB),
    ("pb09", "Hinweise: der Bestand wird je Hinweis neu gelesen", SH_PY,
     "        if index is None:\n            index = _bestand_index(db)\n        stelle = _bereits_stelle(db, firma, titel, index)\n",
     "        stelle = _bereits_stelle(db, firma, titel)\n", T_PB),
    ("pb10", "Hinweise: die Liste ignoriert den Offset", SH_PY,
     "    params.append(max(0, int(offset or 0)))\n", "    params.append(0)\n", T_PB),
    ("pb11", "Hinweise: die Suche liest wieder die auf 500 begrenzte Liste", JOBS_TOOL,
     "                z = _hinweise.holen(db, hinweis_id)        # #1205: die Zeile direkt, nicht über eine auf 500 begrenzte Liste\n",
     "                z = next((e for e in _hinweise.liste(db, status=\"alle\", limit=500) if e[\"id\"] == hinweis_id), None)\n", T_PB),
    ("pb12", "Hinweise: das Werkzeug blaettert nicht", JOBS_TOOL,
     "            eintraege = _hinweise.liste(db, status=_st, limit=limit, offset=_offset)\n",
     "            eintraege = _hinweise.liste(db, status=_st, limit=limit, offset=0)\n", T_PB),
    ("pb13", "Hinweise: der Endpunkt blaettert nicht", DASH,
     "    eintraege = stellen_hinweise.liste(_db, status=st, limit=limit, offset=start)\n",
     "    eintraege = stellen_hinweise.liste(_db, status=st, limit=limit, offset=0)\n", T_PB),
    # ── #1204: die Vorschau sieht die Eintraege derselben Uebergabe ──
    ("pb14", "Vorschau: aehnliche Titel derselben Uebergabe zaehlen als angelegt", JOBS_TOOL,
     "                if _aehnlich:\n                    _skip(e, \"duplikat_aktiv\",\n",
     "                if False:\n                    _skip(e, \"duplikat_aktiv\",\n", T_PB),
    ("pb15", "Vorschau: die gezaehlten Eintraege werden nicht gemerkt", JOBS_TOOL,
     "                vorschau_jobs.append({\"hash\": res[\"hash\"], \"title\": titel, \"company\": firma, \"url\": url})\n",
     "                pass\n", T_PB),
    # ── #1206: ein Nicht-Text als Dokumenttyp ──
    ("pb16", "Dokumenttyp: ein Nicht-Text wird nicht abgelehnt", DH_PY,
     "    if not isinstance(typ, str):\n", "    if False:\n", T_PB),
    ("pb17", "Dokumenttyp: ein Nicht-Objekt als Koerper wird nicht abgelehnt", DASH,
     "    if not isinstance(data, dict):           # #1206: ein Nicht-Objekt (Liste, Zahl) war ein AttributeError und HTTP 500\n",
     "    if False:\n", T_PB),
    # ── #1208-#1215: Oberflaeche (baut das Bundle neu) ──
    ("pf01", "Zurueck-Taste: der Dialog schliesst mitten in der Schleife (Endlosschleife bei Eingaben)", UI_JSX,
     "    dialogStapel.pop();\n    abgetragen.push(oben);\n", "    dialogStapel.pop();\n    oben.zurueck();\n", T_PF),
    ("pf02", "Pfad: jeder Klick setzt den Unterpfad zurueck, auch auf derselben Seite", APP_JSX,
     "    if (nextPage !== page) setCurrentSubPath(\"\");\n", "    setCurrentSubPath(\"\");\n", T_PF),
    ("pf03", "Verlauf: der Sprung aus einem Dialog legt den Eintrag obenauf", APP_JSX,
     "      if (window.history.state?.pbpDialog != null) {\n", "      if (false) {\n", T_PF),
    ("pf04", "Leiste: Escape erreicht den Dialog trotz offenem Menue", WL_JSX,
     "    document.addEventListener(\"keydown\", taste, true);\n", "", T_PF),
    ("pf05", "Stelle aus der Bewerbung: die Leiste kennt die Bewerbung nicht", IJ_JSX,
     "            bewerbungId,\n            beurteilt: true,\n", "            beurteilt: true,\n", T_PF),
    ("pf06", "Bewerbungen: der Dialog bekommt die Kennung der Bewerbung nicht", AP_JSX,
     "          bewerbungId={jobDetail.bewerbungId}\n", "", T_PF),
    ("pf07", "Stellen: nur die 30 juengsten Bewerbungen sind bekannt", JP_JSX,
     "append ? Promise.resolve(null) : api(\"/api/applications?limit=0\"),\n",
     "append ? Promise.resolve(null) : api(\"/api/applications\"),\n", T_PF),
    ("pf08", "Stellen: der Pruefstand einer ausgeblendeten Stelle wird nicht nachgeholt", JP_JSX,
     "    if (!detailDialog.open || !stelle?.hash || stelle.pruefstand) return undefined;\n", "    return undefined;\n", T_WL),
    # ── #1207/#1219 (Windows) ──
    ("pw01", "Installer: das Ausrufezeichen im Profil wird nicht geprueft", "INSTALLIEREN.bat",
     "if \"%PBP_PROFIL_ORTE:!=%\"==\"%PBP_PROFIL_ORTE%\" goto :profil_ohne_ausrufezeichen\n", "goto :profil_ohne_ausrufezeichen\n", T_PI + T_PW),
    ("pw02", "Deinstaller: das Ausrufezeichen im Profil wird nicht geprueft", "DEINSTALLIEREN.bat",
     "if \"%PBP_PROFIL_ORTE:!=%\"==\"%PBP_PROFIL_ORTE%\" goto :pbp_profil_ok\n", "goto :pbp_profil_ok\n", T_PW),
    ("pw03", "Installer: das Aufraeumen verspricht das Loeschen ohne den Exit-Code zu lesen", "INSTALLIEREN.bat",
     "if not errorlevel 1 goto :aufraeumen_gestartet\n", "goto :aufraeumen_gestartet\n", T_PW),
    ("pw04", "Aufraeum-Helfer: ein Fehler beim Starten ist wieder ein Traceback", "_installer_aufraeumen.py",
     "        except OSError as exc:\n            # #1219: die Bat sagt", "        except ZeroDivisionError as exc:\n            # #1219: die Bat sagt", T_PW),
    # ── #1216-#1220 (Unix) ──
    ("pu01", "Installer: pip-Update ohne Anfuehrungszeichen um den Python-Aufruf", INST_SH,
     "\"$PYTHON\" -m pip install --upgrade pip -q 2>/dev/null || warn", "$PYTHON -m pip install --upgrade pip -q 2>/dev/null || warn", T_PI),
    ("pu02", "Installer (macOS): Python-Aufruf fuer die Pakete ohne Anfuehrungszeichen", INST_CMD,
     "\"$PYTHON\" -m pip install -e \"$PROJECT_DIR\" -q\n", "$PYTHON -m pip install -e \"$PROJECT_DIR\" -q\n", T_PI),
    ("pu03", "Installer: der Funktionstest laeuft auf dem echten Datenordner", INST_SH,
     "if ! BA_DATA_DIR=\"$TEST_DIR\" \"$PYTHON\" -c", "if ! \"$PYTHON\" -c", T_PI),
    ("pu04", "Installer: ein gescheitertes pip-Update beendet den Installer", INST_SH,
     "\"$PYTHON\" -m pip install --upgrade pip -q 2>/dev/null || warn \"pip liess sich nicht aktualisieren - kein Problem\"\n",
     "\"$PYTHON\" -m pip install --upgrade pip -q 2>/dev/null\n", T_PI),
    ("pu05", "Installer: die Prozesssuche beendet auch ein fremdes start_dashboard.py", INST_SH,
     "        if skript_ist_fremd \"$zeile\"; then\n            continue\n        fi\n", "", T_PI),
    ("pu06", "Installer: das Muster trifft wieder jeden Testlauf mit dem Namen als Argument", INST_SH,
     "DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]](.*[[:space:]/])?start_dashboard\\.py'\n",
     "DASH_MUSTER='(^|/)[Pp]ython[0-9.]*[[:space:]].*start_dashboard\\.py'\n", T_PI),
    ("pu07", "Installer: ohne lesbare Fassung gilt jede antwortende Fassung als ok", INST_SH,
     "    elif [ -z \"$NEUE_FASSUNG\" ]; then\n        echo unbekannt\n", "    elif false; then\n        echo unbekannt\n", T_PI),
    ("pu08", "Installer: der Fehlschlag von _setup_claude.py beendet das Skript unter set -e", INST_SH,
     "    if SETUP_AUSGABE=\"$(\"$PYTHON\" \"$PROJECT_DIR/_setup_claude.py\" 2>&1)\"; then\n",
     "    SETUP_AUSGABE=\"$(\"$PYTHON\" \"$PROJECT_DIR/_setup_claude.py\" 2>&1)\"\n    if [ $? -eq 0 ]; then\n", T_PI),
    ("pu09", "Installer (macOS): ein Fehlschlag von _setup_claude.py setzt den Merker nicht", INST_CMD,
     "        CLAUDE_FEHLER=1\n", "        :\n", T_PI),
    ("pu10", "Deinstaller: ein nicht lesbarer Eintrag bleibt ohne Merker", DEINST_SH,
     "        unreadable)\n            MCP_BLIEB=1\n", "        unreadable)\n", T_PI),
    ("pu11", "Deinstaller: der Schluss ist auch bei stehengebliebenem Eintrag gruen", DEINST_SH,
     "if [ \"$MCP_BLIEB\" = \"1\" ]; then\n", "if false; then\n", T_PI),
    ("pu12", "Deinstaller: nur j gilt als Ja", DEINST_SH,
     "        j|J|ja|Ja|JA|y|Y|yes|Yes|YES) return 0 ;;\n", "        j|J) return 0 ;;\n", T_PI),
    ("pu13", "Doppelklick-Deinstaller: der Exit-Code geht verloren", "DEINSTALLIEREN.command",
     "bash \"$SKRIPT\" || ERGEBNIS=$?\n", "bash \"$SKRIPT\"\n", T_PI),
    ("pu14", "Installer: die Sicherungskopie der Claude-Konfiguration kommt nicht in den Schluss", INST_SH,
     "if [ -n \"${CLAUDE_KOPIE:-}\" ]; then\n", "if false; then\n", T_PI),
    # ── #1222: die Installation einer Vorabversion (Schalter aus #1199) ──
    ("vi01", "Installation: eine ungueltige Fassung wird nicht abgewiesen", AU + "installation.py",
     "    if not _fassung.gueltig(version):\n        raise UpdateFehler(\"quelle_nicht_erlaubt\"",
     "    if False:\n        raise UpdateFehler(\"quelle_nicht_erlaubt\"", T_VI),
    ("vi02", "Installation: der Schalter wird nicht aus der Datenbank gelesen (immer an)", AU + "installation.py",
     "        vorab = zustand.vorab(db) if db is not None else False        # #1222: der Schalter, wie die Auswahl ihn las\n",
     "        vorab = True\n", T_VI),
    ("vi03", "Start: eine Vorabversion wird ohne Schalter gestartet", AU + "lauf.py",
     "        if not quelle.kandidat_erlaubt(version, laufend, zustand.vorab(db)):\n", "        if False:\n", T_VI),
    ("vi04", "Start: eine ungueltige Fassung wird nicht abgewiesen", AU + "lauf.py",
     "    if not _fassung.gueltig(version):\n"
     "        return {\"status\": \"abgelehnt\", \"text\": \"Das ist keine gültige Versionsnummer.\"}\n", "", T_VI),
    ("vi05", "Manifest: eine ungueltige Fassung wird akzeptiert", AU + "manifest.py",
     "    if not _fassung.gueltig(version):\n"
     "        raise UpdateFehler(\"manifest\", detail=f\"version {version!r} ist keine gültige Fassung\")\n", "", T_PR + T_VI),
    # ── #1224: Kommentare mit Klammern in einem Klammerblock beendeten den Stapel (dritter Werkstatt-PC-Lauf) ──
    ("ba01", "Deinstaller: Kommentarzeilen mit Klammern stehen wieder im Backup-Block", DB,
     "    echo         Erstelle Backup...\n    powershell ",
     "    echo         Erstelle Backup...\n"
     ":: v1.8.0 (#1149 Punkt 8): die Pfade (DATA_DIR, BACKUP_ZIP), nicht eingebettet. Ein Apostroph\n"
     ":: im Benutzernamen (O'Brien) machte aus dem Befehl einen Syntaxfehler\n"
     "    powershell ", T_BA),
    ("au01", "Updates-Seite: „Aktuell“ steht auch, wenn die Prüfung keine Antwort bekam", "frontend/src/lib/autoUpdate.js",
     "  return Boolean(au) && !au.neu && !au.neustart_noetig && !standUnbekannt(au);\n",
     "  return Boolean(au) && !au.neu && !au.neustart_noetig;\n", T_VO),
    ("ba02", "Installer: ein Kommentar mit Klammer im Migrationsblock", IB,
     "    :: dokumente/ und export/ Inhalte migrieren, nur wenn im alten Pfad vorhanden\n",
     "    :: dokumente/ und export/ Inhalte migrieren (nur wenn im alten Pfad vorhanden)\n", T_BA),
    # ── #1227: die Ollama-Abfrage kostete ohne Ollama unter Windows 4 s (dritter Werkstatt-PC-Lauf) ──
    ("ol01", "Ollama-Probe: der Zeitablauf der Schleifenprobe ist wieder 2,0 s", LLM_PY,
     "OLLAMA_PROBE_TIMEOUT_S = 0.5\n", "OLLAMA_PROBE_TIMEOUT_S = 2.0\n", T_OL),
    ("ol02", "Ollama-Abfrage: ohne Probe, die Abfrage geht wieder blind an localhost", LLM_PY,
     "            basis = self._ollama_basis()\n", "            basis = self._status.ollama_endpoint\n", T_OL),
    ("ol03", "Ollama-Probe: ::1 wird nicht probiert", LLM_PY,
     "        for adresse in (\"127.0.0.1\", \"::1\"):\n", "        for adresse in (\"127.0.0.1\",):\n", T_OL),
    ("ol04", "Ollama-Abfrage: sie geht nicht an die annehmende Adresse, sondern wieder an localhost", LLM_PY,
     "            return f\"{teile.scheme or 'http'}://{host}:{port}\"\n", "            return endpunkt\n", T_OL),
    ("ol05", "Ollama-Probe: auch ein fremder Endpunkt bekommt die Schleifenprobe", LLM_PY,
     "        if (teile.hostname or \"\").lower() != \"localhost\":\n", "        if False:\n", T_OL),
    ("ol06", "Erweiterungen: der Handler ist wieder ein async-Handler und haelt den Server an", DASH,
     "@app.get(\"/api/components\")\ndef api_components_overview():\n",
     "@app.get(\"/api/components\")\nasync def api_components_overview():\n", T_OL),
    # ── #1226: der Schalter „Vorabversionen automatisch“ aendert die Frage (Block E5, dritter Lauf) ──
    ("vs01", "Pruefung: der Zwischenspeicher gilt auch bei anderem Stand des Schalters", AU + "lauf.py",
     "        if gemerkt.get(\"laufende\") == laufende and bool(gemerkt.get(\"vorab\")) == vorab:\n",
     "        if gemerkt.get(\"laufende\") == laufende:\n", T_VS),
    ("vs02", "Pruefung: das Ergebnis merkt den Stand des Schalters nicht", AU + "lauf.py",
     "\"laufende\": laufende, \"vorab\": bool(vorab)}\n", "\"laufende\": laufende}\n", T_VS),
    ("vs03", "Umschalten: es wird nie neu geprueft", AU + "lauf.py",
     "    geaendert = vorher != bool(an)\n    if geaendert:\n", "    geaendert = vorher != bool(an)\n    if False:\n", T_VS),
    ("vs04", "Umschalten: es wird auch bei gleichem Stand neu geprueft", AU + "lauf.py",
     "    geaendert = vorher != bool(an)\n    if geaendert:\n", "    geaendert = vorher != bool(an)\n    if True:\n", T_VS),
    ("vs05", "Endpunkt: die Einstellung setzt den Schalter ohne neue Pruefung", DASH,
     "        await asyncio.to_thread(lauf.vorab_einstellen, _db, bool(payload[\"vorab\"]))\n",
     "        zustand.vorab_setzen(_db, bool(payload[\"vorab\"]))\n", T_VS),
    ("vs06", "Werkzeug: die Einstellung setzt den Schalter ohne neue Pruefung", TOOL_UPDATE,
     "                lauf.vorab_einstellen(db, bool(vorab))      # #1226: stellt die Frage neu (prueft gleich)\n",
     "                zustand.vorab_setzen(db, bool(vorab))\n", T_VS),
    ("vs07", "Uebersicht: eine Vorabversion bleibt nach dem Ausschalten als neu stehen", AU + "lauf.py",
     "    if p and p.get(\"version\") and not _fassung.ist_stabil(p[\"version\"]) and bool(p.get(\"vorab\")) and not antwort[\"vorab\"]:\n"
     "        p = None\n", "    if False:\n        p = None\n", T_VS),
    ("vs08", "Karte: nach dem Einschalten steht wieder immer der Satz zur Versionslinie", AUJS,
     "  return vorab.pruefungVeraltet ? VORAB_ERKLAERUNG_PRUEFEN : VORAB_ERKLAERUNG_ANDERE_LINIE;\n",
     "  return VORAB_ERKLAERUNG_ANDERE_LINIE;\n", T_VS + T_VO),
    ("vs09", "Hinweiszone: nach dem Einschalten steht wieder der Satz zur Versionslinie", AUJS,
     "    return vorab.pruefungVeraltet\n      ? \"Ob sie automatisch kommt", "    return false\n      ? \"Ob sie automatisch kommt", T_VO),
    ("vs10", "Oberflaeche: die Pruefung gilt auch ohne den Vermerk des Schalters als belegt", AUJS,
     "    pruefungVeraltet: schalterAn && !(au?.pruefung?.status === \"aktuell\" && au.pruefung.vorab === true),\n",
     "    pruefungVeraltet: false,\n", T_VO),
    # ── #1228: die Windows-Liste („Apps & Features“) nennt die laufende Fassung (Block E5, dritter Lauf) ──
    ("rg01", "Windows-Liste: der Ort des Eintrags wird nicht verglichen (fremde Installation wird veraendert)", WL_PY,
     "            if not _gleicher_ort(ort, programmordner):\n                return \"anderer_ort\"\n",
     "            if False:\n                return \"anderer_ort\"\n", T_RG),
    ("rg02", "Windows-Liste: ein fehlender Eintrag gilt als Fehler statt als nicht vorhanden", WL_PY,
     "        except FileNotFoundError:\n            return \"kein_eintrag\"\n",
     "        except FileNotFoundError:\n            raise RuntimeError(\"kein Eintrag\")\n", T_RG),
    ("rg03", "Windows-Liste: ein gleicher Eintrag wird trotzdem geschrieben", WL_PY,
     "            if aktuell == str(version):\n                return \"gleich\"\n",
     "            if False:\n                return \"gleich\"\n", T_RG),
    ("rg04", "Windows-Liste: ein Schreibfehler wird nicht abgefangen", WL_PY,
     "    except Exception:  # noqa: BLE001 — eine Anzeige darf den Start nie aufhalten\n",
     "    except ZeroDivisionError:  # noqa: BLE001 — eine Anzeige darf den Start nie aufhalten\n", T_RG),
    ("rg05", "Windows-Liste: unter Linux und macOS wird trotzdem gelesen", WL_PY,
     "    if (plattform or sys.platform) != \"win32\":\n        return \"nicht_windows\"\n",
     "    if False:\n        return \"nicht_windows\"\n", T_RG),
    ("rg06", "Start: der Abgleich der Windows-Liste fehlt", AU + "lauf.py",
     "        ergebnis[\"windows_liste\"] = windows_liste.abgleichen(layout.laufende_fassung(), app)\n",
     "        ergebnis[\"windows_liste\"] = \"nichts_zu_tun\"\n", T_RG),
    ("rg07", "Start: ein Fehler des Abgleichs bricht den Start ab", AU + "lauf.py",
     "    except Exception:  # noqa: BLE001\n        logger.debug(\"Windows-Liste nicht abgeglichen\", exc_info=True)\n",
     "    except ZeroDivisionError:  # noqa: BLE001\n        logger.debug(\"Windows-Liste nicht abgeglichen\", exc_info=True)\n", T_RG),
    ("rg08", "Windows-Liste: der Ort wird wieder als Zeichenfolge verglichen (Junction und 8.3-Name gelten als fremd)", WL_PY,
     "    return os.path.normcase(os.path.realpath(str(pfad)))\n",
     "    return os.path.normcase(os.path.normpath(str(pfad)))\n", T_RG),
    # ── #1229: „Beim naechsten Start nutzen“ kennt zwei Richtungen (Block E5, dritter Lauf) ──
    ("um01", "Verlauf: ein Schritt nach vorn heisst wieder „zurueckgeschaltet“", AU + "lauf.py",
     "    if nach_vorn:\n        zustand.verlauf_anhaengen(db, version=ziel, ergebnis=\"umgeschaltet\"",
     "    if False:\n        zustand.verlauf_anhaengen(db, version=ziel, ergebnis=\"umgeschaltet\"", T_UM),
    ("um02", "Verlauf: auch der Rueckweg heisst „umgeschaltet“", AU + "lauf.py",
     "    nach_vorn = bool(aktuell) and _fassung.ist_neuer(ziel, aktuell)\n", "    nach_vorn = True\n", T_UM),
    ("um03", "Umschalten: das gewaehlte Ziel bleibt zurueckgenommen", AU + "lauf.py",
     "    gemerkt = (set(abgelehnt(db)) | set(neuere)) - {ziel}\n", "    gemerkt = (set(abgelehnt(db)) | set(neuere))\n", T_UM),
    ("um04", "Frage: der Schritt nach vorn bekommt den Satz des Rueckwegs", AUJS,
     "  if (istNeuer(version, aktuell)) {\n    return `Beim nächsten Start läuft Version",
     "  if (false) {\n    return `Beim nächsten Start läuft Version", T_UM + T_VO),
    ("um05", "Anzeige: die Marke „Umgeschaltet“ fehlt (der Verlauf zeigt den rohen Wert)", UPD_JSX,
     "  umgeschaltet: { label: \"Umgeschaltet\", tone: \"amber\" },\n", "", T_UM + T_VO),
    ("um06", "Oberflaeche: die Frage nimmt wieder immer den Satz des Rueckwegs", UPD_JSX,
     "    const ok = await bestaetigen({ text: umschaltText(v, au.aktuell) });\n",
     "    const ok = await bestaetigen({ text: umschaltText(v, null) });\n", T_UM + T_VO),
    # ── #1198: Repost-Warnung Art „vermittler“ (Fremdbeitrag PR #1230, in 1.8.0 uebernommen) ──
    ("vm01", "Vermittler: ein eingetragener Endkunde ist nicht mehr massgeblich (Notizen ueberstimmen ihn)", DD_PY,
     "        roh = endkunde or \" \".join(str(app.get(k) or \"\")\n                                   for k in (\"company\", \"notes\"))\n",
     "        roh = \" \".join(str(app.get(k) or \"\")\n                       for k in (\"company\", \"notes\", \"endkunde\"))\n", T_VM),
    ("vm02", "Vermittler: ein Freitexttreffer gilt wieder als eingetragener Endkunde", HINWEIS_PY,
     "    if str(bewerbung.get(\"endkunde\") or \"\").strip():\n        return f\"{firma} ist als Endkunde in der Bewerbung eingetragen.\"\n",
     "    if True:\n        return f\"{firma} ist als Endkunde in der Bewerbung eingetragen.\"\n", T_VM),
    ("vm03", "Vermittler: der Hinweis nennt wieder die Firma der Bewerbung statt des eingetragenen Vermittlers", HINWEIS_PY,
     "    name = str(bewerbung.get(\"vermittler\") or \"\").strip()\n    return name or str(bewerbung.get(\"company\") or \"\").strip()\n",
     "    return str(bewerbung.get(\"company\") or \"\").strip()\n", T_VM),
    ("vm04", "Vermittler: ohne Endkunde im Feld wird der Treffer nie als offen eingeordnet", HINWEIS_PY,
     "        f\"{firma} wird in den Notizen oder Firmenangaben erwähnt; \"\n        \"ob es der Endkunde ist, bleibt offen.\")\n",
     "        f\"{firma} nennt diese Bewerbung als Endkunden.\")\n", T_VM),
    ("vm05", "Anlage von Hand: der Hinweis nennt wieder den Vermittler aus der Firma der Bewerbung", JOBS_TOOL,
     "                        f\"'{vermittler_name(_vb)}'. \"\n",
     "                        f\"'{_vb.get('company')}'. \"\n", T_VM),
    ("vm06", "Anlage von Hand: der Hinweis behauptet den Endkunden wieder als Tatsache", JOBS_TOOL,
     "                        f\"{vermittler_einordnung(firma, _vb)} \"\n",
     "                        f\"nennt {firma} als Endkunden. \"\n", T_VM),
]
KATALOGE["pruefung1214"] = M_PRUEFUNG
GRUNDLAEUFE["pruefung1214"] = (("T_PB", T_PB), ("T_PD", T_PD), ("T_PW", T_PW), ("T_PI", T_PI), ("T_PF", T_PF),
                                ("T_VI", T_VI), ("T_BA", T_BA), ("T_OL", T_OL), ("T_VS", T_VS), ("T_RG", T_RG), ("T_UM", T_UM), ("T_VM", T_VM))

# ── #1231: der PII-Pruefer kennt einen Platzhalter in jeder Schreibweise ──
T_PU = ["tests/test_v18_pii_umlaut_1231.py", "tests/test_scrub_pii_erkennung.py"]
SCRUB_PY = "scripts/scrub_pii.py"
M_PII = [
    ("pu01", "PII-Pruefer: der Text wird nicht mehr in Umschrift gebracht (Süd im Text gegen sued in der Liste)", SCRUB_PY,
     "    klein = _umschrift(label)\n    return any(_umschrift(f) in klein for f in FIKTIVE_FIRMEN)\n",
     "    klein = label.lower()\n    return any(_umschrift(f) in klein for f in FIKTIVE_FIRMEN)\n", T_PU),
    ("pu02", "PII-Pruefer: die Liste wird nicht mehr in Umschrift gebracht (Eintrag mit Umlaut gegen Text in Umschrift)", SCRUB_PY,
     "    return any(_umschrift(f) in klein for f in FIKTIVE_FIRMEN)\n",
     "    return any(f in klein for f in FIKTIVE_FIRMEN)\n", T_PU),
    ("pu03", "PII-Pruefer: das ß bleibt unbehandelt (Weisswerk gegen Weißwerk)", SCRUB_PY,
     '(("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))',
     '(("ä", "ae"), ("ö", "oe"), ("ü", "ue"))', T_PU),
    ("pu04", "PII-Pruefer: ein zerlegtes Trema (u plus Punkte) wird nicht zusammengesetzt", SCRUB_PY,
     '    klein = unicodedata.normalize("NFC", text).lower()\n',
     '    klein = text.lower()\n', T_PU),
    ("pu05", "PII-Pruefer: nur noch die ganze Angabe gilt als Platzhalter, nicht mehr ein Teil davon", SCRUB_PY,
     "    return any(_umschrift(f) in klein for f in FIKTIVE_FIRMEN)\n",
     "    return any(_umschrift(f) == klein for f in FIKTIVE_FIRMEN)\n", T_PU),
    ("pu06", "PII-Pruefer: jede Firma gilt als Platzhalter", SCRUB_PY,
     "    return any(_umschrift(f) in klein for f in FIKTIVE_FIRMEN)\n",
     "    return True\n", T_PU),
]
KATALOGE["pii1231"] = M_PII
GRUNDLAEUFE["pii1231"] = (("T_PU", T_PU),)

# ── #1232: eine interne Notiz schliesst den automatischen Nachfass nicht mehr ──
T_NF = ["tests/test_v17158_nachfass_notiz_1232.py", "tests/test_v17142_termin_folgen_1123.py",
        "tests/test_v18_nachfass_notiz_anleitung_1232.py"]
NF_TOOL = "src/bewerbungs_assistent/tools/bewerbungen.py"
NF_DIENST = "src/bewerbungs_assistent/services/nachfass_abgleich.py"
NF_TERMIN = "src/bewerbungs_assistent/services/termin_folgen.py"
NF_PROMPTS = "src/bewerbungs_assistent/prompts.py"
NF_HANDLER = "src/bewerbungs_assistent/services/document_handlers.py"
NF_RUECK = "src/bewerbungs_assistent/document_analysis_prompts.py"
M_NACHFASS = [
    ("nf01", "bewerbung_notiz: die Vorgabe ist wieder Kontakt statt intern", NF_TOOL,
     'def bewerbung_notiz(bewerbung_id: str, notiz: str, art: str = "intern") -> dict:',
     'def bewerbung_notiz(bewerbung_id: str, notiz: str, art: str = "kontakt") -> dict:', T_NF),
    ("nf02", "bewerbung_notiz: art=kontakt schliesst die Erinnerung nicht mehr", NF_TOOL,
     '            hinfaellig = nachfass_abgleich.kontakt_gemeldet(\n                db, bewerbung_id, "Gesprächsnotiz")\n',
     '            hinfaellig = []\n', T_NF),
    ("nf03", "bewerbung_notiz: art=nachfrage setzt hinfaellig statt erledigt", NF_TOOL,
     '            erledigt = nachfass_abgleich.nachfrage_gesendet(db, bewerbung_id)\n',
     '            erledigt = nachfass_abgleich.kontakt_gemeldet(db, bewerbung_id, "Nachfrage")\n', T_NF),
    ("nf04", "bewerbung_notiz: das Feld heisst wieder erledigt, obwohl hinfaellig gespeichert wird", NF_TOOL,
     '                ergebnis["nachfassung_hinfaellig"] = hinfaellig\n',
     '                ergebnis["nachfassung_erledigt"] = hinfaellig\n', T_NF),
    ("nf05", "bewerbung_notiz: eine unbekannte Art wird still wie intern behandelt", NF_TOOL,
     '        if art_norm not in nachfass_abgleich.NOTIZ_ARTEN:\n',
     '        if False:\n', T_NF),
    ("nf06", "Dienst: schliessen ignoriert den gewuenschten Zustand", NF_DIENST,
     '            (status, _jetzt(), fu["id"]))\n',
     '            ("hinfaellig", _jetzt(), fu["id"]))\n', T_NF),
    ("nf07", "Dienst: ein unbekannter Zustand wird angenommen", NF_DIENST,
     '    if status not in SCHLIESS_STATUS:\n',
     '    if False:\n', T_NF),
    ("nf08", "Termin: das Feld heisst wieder erledigt, obwohl hinfaellig gespeichert wird", NF_TERMIN,
     '            ergebnis["nachfassung_hinfaellig"] = hinfaellig\n',
     '            ergebnis["nachfassung_erledigt"] = hinfaellig\n', T_NF),
    ("nf09", "Werkzeugschema: der Parameter art hat keinen Text mehr", NF_TOOL,
     '            art: `intern` (Vorgabe), `kontakt` oder `nachfrage`. Nur `kontakt`\n'
     '                und `nachfrage` schließen die offene Nachfass-Erinnerung.\n',
     '', T_NF),
    ("nf10", "Anleitung: die Mail des Arbeitgebers nennt art=kontakt nicht mehr", NF_PROMPTS,
     'art="kontakt") — eine Mail des Arbeitgebers ist Kontakt',
     ') — eine Mail des Arbeitgebers ist Kontakt', T_NF),
    ("nf11", "Anleitung: das Projekt-Update nennt art=kontakt nicht mehr", NF_HANDLER,
     "\"claude_action\": \"bewerbung_notiz(bewerbung_id, '...', art='kontakt') mit dem Update-Inhalt + ggf. nachfass_planen\",",
     "\"claude_action\": \"bewerbung_notiz(bewerbung_id, '...') mit dem Update-Inhalt + ggf. nachfass_planen\",", T_NF),
    ("nf12", "Rueckfuehrung: das Gespraechsprotokoll nennt art=kontakt nicht mehr", NF_RUECK,
     "bewerbung_notiz(bewerbung_id, '...', \"\n        \"art='kontakt') an die Bewerbung schreiben",
     "bewerbung_notiz(bewerbung_id, '...') \"\n        \"an die Bewerbung schreiben", T_NF),
]
KATALOGE["nachfass1232"] = M_NACHFASS
GRUNDLAEUFE["nachfass1232"] = (("T_NF", T_NF),)

# ── #1234: ein Wiedergaenger-k.o. nur aus Gruenden, die ein Urteil sind ──
T_WG = ["tests/test_v18_wiedergaenger_urteil_1234.py"]
WG_DIENST = "src/bewerbungs_assistent/services/wiedergaenger.py"
WG_GRUENDE = "src/bewerbungs_assistent/services/ablehnungsgruende.py"
WG_TOOL = "src/bewerbungs_assistent/tools/jobs.py"
WG_LISTE = '    "bewerbung_erstellt", "bereits_beworben", "duplikat", "veraltet_url",\n'
WG_STOPS = '    "head", "chief", "director", "direktor", "vorstand",\n'
WG_KO = ('    return (muster.get("anzahl", 0) >= 2\n'
         '            and muster.get("top_grund") in FACHLICHE_KO_GRUENDE)\n')
M_WIEDERGAENGER = [
    ("wg01", "Nicht-Urteile: die Liste ist leer", WG_GRUENDE,
     'KEIN_URTEIL_GRUENDE = frozenset({\n' + WG_LISTE + '})\n', 'KEIN_URTEIL_GRUENDE = frozenset()\n', T_WG),
    ("wg02", "Nicht-Urteile: bewerbung_erstellt zaehlt wieder", WG_GRUENDE,
     WG_LISTE, '    "bereits_beworben", "duplikat", "veraltet_url",\n', T_WG),
    ("wg03", "Nicht-Urteile: bereits_beworben zaehlt wieder", WG_GRUENDE,
     WG_LISTE, '    "bewerbung_erstellt", "duplikat", "veraltet_url",\n', T_WG),
    ("wg04", "Nicht-Urteile: duplikat zaehlt wieder", WG_GRUENDE,
     WG_LISTE, '    "bewerbung_erstellt", "bereits_beworben", "veraltet_url",\n', T_WG),
    ("wg05", "Nicht-Urteile: veraltet_url zaehlt wieder", WG_GRUENDE,
     WG_LISTE, '    "bewerbung_erstellt", "bereits_beworben", "duplikat",\n', T_WG),
    ("wg06", "urteilsgruende gibt jeden Grund zurueck", WG_DIENST,
     '    return [r for r in _reasons_of(job) if ist_urteil(r)]\n', '    return list(_reasons_of(job))\n', T_WG),
    ("wg07", "die Zaehlung im Wiedergaenger nimmt wieder jeden Grund", WG_DIENST,
     '        for r in sorted(set(urteilsgruende(j))):\n            reason_counter[r] += 1\n',
     '        for r in sorted(set(_reasons_of(j))):\n            reason_counter[r] += 1\n', T_WG),
    ("wg08", "die Firmen-Historie nennt wieder jeden Grund", WG_DIENST,
     '        reasons = sorted(set(urteilsgruende(j)))  # #966: je Stelle einmal; #1234: nur Urteile\n',
     '        reasons = sorted(set(_reasons_of(j)))  # #966: je Stelle einmal\n', T_WG),
    ("wg09", "ist_urteil erkennt das auto:-Praefix nicht", WG_GRUENDE,
     '    if kern.startswith("auto:"):\n        kern = kern[len("auto:"):].split(":", 1)[0]\n', '', T_WG),
    ("wg10", "ist_urteil unterscheidet Gross und Klein", WG_GRUENDE,
     '    kern = str(grund or "").strip().lower()\n    if kern.startswith("auto:"):',
     '    kern = str(grund or "").strip()\n    if kern.startswith("auto:"):', T_WG),
    ("wg11", "head ist wieder ein Fachwort", WG_DIENST,
     WG_STOPS, '    "chief", "director", "direktor", "vorstand",\n', T_WG),
    ("wg12", "chief ist wieder ein Fachwort", WG_DIENST,
     WG_STOPS, '    "head", "director", "direktor", "vorstand",\n', T_WG),
    ("wg13", "director ist wieder ein Fachwort", WG_DIENST,
     WG_STOPS, '    "head", "chief", "direktor", "vorstand",\n', T_WG),
    ("wg14", "direktor ist wieder ein Fachwort", WG_DIENST,
     WG_STOPS, '    "head", "chief", "director", "vorstand",\n', T_WG),
    ("wg15", "ein Muster mit einem Beleg ist schon ein k.o.", WG_DIENST,
     WG_KO, WG_KO.replace(">= 2", ">= 1"), T_WG),
    ("wg16", "jedes Muster mit zwei Belegen ist ein k.o., egal welcher Grund", WG_DIENST,
     WG_KO, '    return muster.get("anzahl", 0) >= 2\n', T_WG),
    ("wg17", "Gehalt ist ein fachlicher k.o.-Grund", WG_DIENST,
     '    "kein_hochschulabschluss", "unpassendes_arbeitsmodell",\n})\n\n\ndef ist_fachlicher_ko',
     '    "kein_hochschulabschluss", "unpassendes_arbeitsmodell", "gehalt_zu_niedrig",\n})\n\n\ndef ist_fachlicher_ko', T_WG),
    ("wg18", "die Liste macht wieder aus jedem Muster ein k.o.", WG_TOOL,
     '                    if ist_fachlicher_ko(muster):\n                        j["_ko_muster"] = muster\n'
     '                    elif muster:\n                        j["_wg_hinweis"] = muster\n',
     '                    if muster:\n                        j["_ko_muster"] = muster\n', T_WG),
    ("wg19", "die Analyse hat wieder ihre eigene k.o.-Frage", WG_TOOL,
     '    if ist_fachlicher_ko(wiedergaenger):\n        ko_gruende.append(',
     '    if wiedergaenger:\n        ko_gruende.append(', T_WG),
    ("wg20", "das gelesene Urteil steht nicht neben dem k.o.", WG_TOOL,
     '                if _gelesen and _gelesen != "NICHT_EMPFOHLEN":\n', '                if False:\n', T_WG),
    ("wg21", "ein Muster ohne k.o. bleibt ohne Hinweis", WG_TOOL,
     '            elif j.get("_wg_hinweis"):\n', '            elif False:\n', T_WG),
]
KATALOGE["wiedergaenger1234"] = M_WIEDERGAENGER
GRUNDLAEUFE["wiedergaenger1234"] = (("T_WG", T_WG),)

# ── #1235: ein mehrdeutiger Ortsname bekommt keinen geratenen Treffer ──
T_OD = ["tests/test_v18_ortsdienst_mehrdeutig_1235.py"]
OD_GEO = "src/bewerbungs_assistent/services/geocoding_service.py"
OD_STANDORT = "src/bewerbungs_assistent/services/eigener_standort.py"
OD_WAHRHEIT = "src/bewerbungs_assistent/services/wahrheit.py"
OD_SUCHE = "src/bewerbungs_assistent/job_scraper/__init__.py"
OD_TOOL = "src/bewerbungs_assistent/tools/jobs.py"
OD_HEILUNG = "src/bewerbungs_assistent/services/karten_heilung.py"
OD_NACHLADEN = "src/bewerbungs_assistent/services/nachladen.py"
OD_AENDERN = "src/bewerbungs_assistent/services/stelle_aendern.py"
OD_DB = "src/bewerbungs_assistent/database.py"
M_ORTSDIENST = [
    ("od01", "Mehrdeutig braucht keinen Abstand mehr (50 km -> 5000 km)", OD_GEO,
     'MEHRDEUTIG_AB_KM = 50.0\n', 'MEHRDEUTIG_AB_KM = 5000.0\n', T_OD),
    ("od02", "Mehrdeutig gibt es nie (Gewichtsabstand 0)", OD_GEO,
     'MEHRDEUTIG_GEWICHT = 0.10\n', 'MEHRDEUTIG_GEWICHT = 0.0\n', T_OD),
    ("od03", "Mehrdeutig gilt immer, auch bei klarem Spitzenreiter (Gewichtsabstand 1)", OD_GEO,
     'MEHRDEUTIG_GEWICHT = 0.10\n', 'MEHRDEUTIG_GEWICHT = 1.0\n', T_OD),
    ("od04", "jeder Treffer zaehlt als Ort, auch ein Park", OD_GEO,
     '    return raw.get("class") in ("boundary", "place") and raw.get("type") != "postal_code"\n',
     '    return True\n', T_OD),
    ("od05", "dieselbe Gemeinde als Ortsteil wird doppelt genannt", OD_GEO,
     '        if any(calculate_distance_km(punkt, (k["lat"], k["lon"])) < 10.0 for k in kandidaten):\n            continue\n',
     '        if False:\n            continue\n', T_OD),
    ("od06", "der Dienst wird wieder nach EINEM Treffer gefragt", OD_GEO,
     '        antwort = geolocator.geocode(anfrage, exactly_one=False, limit=MAX_TREFFER)\n',
     '        antwort = geolocator.geocode(anfrage, exactly_one=True, limit=MAX_TREFFER)\n', T_OD),
    ("od07", "die Kandidaten werden nicht im Arbeitsspeicher gemerkt", OD_GEO,
     '                _mehrdeutig_orte[loc_key] = fund["kandidaten"]\n', '                pass\n', T_OD),
    ("od08", "die Kandidaten werden nicht in der Datenbank gemerkt", OD_GEO,
     '             json.dumps(kandidaten, ensure_ascii=False) if kandidaten else None))\n', '             None))\n', T_OD),
    ("od09", "Zeilen ohne Stand gelten wieder als geprueft", OD_GEO,
     '        if (row[3] or 0) < SPEICHER_STAND:\n', '        if False:\n', T_OD),
    ("od10", "zwei verschiedene PLZ im Text geben eine zufaellige", OD_GEO,
     '    if len(plz) == 1:\n', '    if plz:\n', T_OD),
    ("od11", "das Bundesland aus dem Text wird nicht gelesen", OD_GEO,
     '    if len(gefunden) == 1:\n        return f"{name}, {next(iter(gefunden))}"\n    return ""\n', '    return ""\n', T_OD),
    ("od12", "die Anzeige klaert einen mehrdeutigen Ort nicht", OD_GEO,
     '    genauer = ort_aus_anzeige(ort_fuer_abfrage(location), anzeige)\n    if not genauer:\n        return fund\n',
     '    return fund\n', T_OD),
    ("od13", "die Herkunft nennt den mehrdeutigen Ort nicht", OD_WAHRHEIT,
     '        kandidaten = _mehrdeutige_kandidaten(job)\n        if kandidaten:\n',
     '        kandidaten = []\n        if kandidaten:\n', T_OD),
    ("od14", "der Befund nennt die Kandidaten des Wohnorts nicht", OD_STANDORT,
     '        if kandidaten:\n            erg["mehrdeutig"] = [k_["name"] for k_ in kandidaten]\n',
     '        if False:\n            erg["mehrdeutig"] = [k_["name"] for k_ in kandidaten]\n', T_OD),
    ("od15", "ein mehrdeutiger eigener Ort heisst wieder nur 'nicht aufgeloest'", OD_STANDORT,
     '        if kandidaten:\n            namen = [k_["name"] for k_ in kandidaten]\n',
     '        if False:\n            namen = [k_["name"] for k_ in kandidaten]\n', T_OD),
    ("od16", "die Pruefung des Bestands leert die geratene Entfernung nicht", OD_STANDORT,
     '                "WHERE hash=? AND distance_km IS NOT NULL", (am, kennung))\n',
     '                "WHERE hash=? AND 0", (am, kennung))\n', T_OD),
    ("od17", "die Pruefung fragt auch grosse Staedte und Orte mit PLZ", OD_STANDORT,
     '    offen = [o for o in nach_ort if o not in _MEHRDEUTIG_VERSUCHT and mehrdeutigkeit_offen(o)]\n',
     '    offen = [o for o in nach_ort if o not in _MEHRDEUTIG_VERSUCHT]\n', T_OD),
    ("od18", "die Pruefung ist je Lauf nicht begrenzt", OD_STANDORT,
     'mehrdeutigkeit_offen(o)]\n    if max_orte:\n        offen = offen[:max_orte]\n', 'mehrdeutigkeit_offen(o)]\n', T_OD),
    ("od19", "nach einem Suchlauf wird der Bestand nicht auf mehrdeutige Orte geprueft", OD_STANDORT,
     '        mehrdeutig = entfernungen_mehrdeutige_pruefen(db)\n', '        mehrdeutig = {}\n', T_OD),
    ("od20", "neu rechnen klaert oder leert mehrdeutige Orte nicht", OD_STANDORT,
     '        if not ziel and ort in klaerung:\n', '        if False:\n', T_OD),
    ("od21", "die Pruefung ueberschreibt von Hand gesetzte Entfernungen", OD_STANDORT,
     '''"AND COALESCE(entfernung_quelle, '') != 'mensch'")\n    nach_ort: dict = {}\n'''
     '    for kennung, ort in con.execute(sql, (pid,)).fetchall():\n        if ort_schluessel(ort):\n',
     '"")\n    nach_ort: dict = {}\n'
     '    for kennung, ort in con.execute(sql, (pid,)).fetchall():\n        if ort_schluessel(ort):\n', T_OD),
    ("od22", "Ort aendern klaert einen mehrdeutigen Ort nicht mit der Anzeige", OD_AENDERN,
     '    if start and not ziel:\n', '    if False:\n', T_OD),
    ("od23", "die Anlage von Hand fragt bei einem mehrdeutigen Ort nicht mit der Anzeige nach", OD_TOOL,
     '                        _genau = entfernung_aus_anzeige(\n                            ort, user_coords[0], user_coords[1], beschreibung or "")\n',
     '                        _genau = None\n', T_OD),
    ("od24", "der Suchlauf fragt bei einem mehrdeutigen Ort nicht mit der Anzeige nach", OD_SUCHE,
     '                        _genau = entfernung_aus_anzeige(\n                            loc, user_coords[0], user_coords[1], job.get("description") or "")\n',
     '                        _genau = None\n', T_OD),
    ("od25", "die Heilung der Karten fragt bei einem mehrdeutigen Ort nicht mit der Anzeige nach", OD_HEILUNG,
     '                    genau = entfernung_aus_anzeige(\n                        reihe["location"], koordinaten[0], koordinaten[1], reihe["description"] or "")\n',
     '                    genau = None\n', T_OD),
    ("od26", "das Nachladen fragt bei einem mehrdeutigen Ort nicht mit der Anzeige nach", OD_NACHLADEN,
     '                genau = _geo.entfernung_aus_anzeige(\n                    _geo.normalisiere_ort(kopf["ort"]), heim[0], heim[1], job.get("description") or "")\n',
     '                genau = None\n', T_OD),
    ("od27", "die Spalten der Geo-Tabelle kommen nicht in eine alte Datenbank", OD_DB,
     '            for _sp, _typ in (("stand", "INTEGER"), ("kandidaten", "TEXT")):\n', '            for _sp, _typ in ():\n', T_OD),
]
KATALOGE["ortsdienst1235"] = M_ORTSDIENST
GRUNDLAEUFE["ortsdienst1235"] = (("T_OD", T_OD),)

# ── #1247 (F56): der Hilfe-Dialog fragt nach einer getippten Frage nicht nach "ungespeicherten Eingaben" ──
T_HS = ["tests/test_v18_hilfe_frage_browser_1233.py::test_1247_eine_getippte_frage_loest_beim_schliessen_keine_rueckfrage_aus",
        "tests/test_v18_hilfe_frage_browser_1233.py::test_1247_auch_escape_schliesst_nach_einer_frage_ohne_rueckfrage",
        "tests/test_v18_hilfe_frage_browser_1233.py::test_1247_das_filterfeld_der_prompts_loest_keine_rueckfrage_aus"]
T_HSG = ["tests/test_g1087_welle6_oberflaeche.py::test_g67_dialog_fragt_vor_dem_verwerfen"]  # die Gegenseite: ein Dialog mit Formular fragt weiter
M_HILFE_SCHUTZ = [
    ("hs01", "Der Hilfe-Dialog fragt nach einer getippten Frage wieder nach ungespeicherten Eingaben", "frontend/src/App.jsx",
     " onClose={() => setHelpOpen(false)} schutz={false}>", " onClose={() => setHelpOpen(false)}>", T_HS),
    ("hs02", "Kein Dialog fragt mehr vor dem Verwerfen (der Schutz ist von Haus aus aus)", "frontend/src/components/ui.jsx",
     'size = "lg", schutz = true }) {', 'size = "lg", schutz = false }) {', T_HSG),
]
KATALOGE["hilfeschutz1247"] = M_HILFE_SCHUTZ
GRUNDLAEUFE["hilfeschutz1247"] = (("T_HS", T_HS), ("T_HSG", T_HSG))

# ── #1252 (B83): python-jobspy bleibt unter 1.4 (die Bibliothek wurde am 19.10.2026 umgebaut) ──
T_JS = ["tests/test_v17150_jobspy_120_1159.py::test_1252_python_jobspy_ist_nach_oben_begrenzt_und_ueberall_gleich"]
M_JOBSPY_GRENZE = [
    ("js01", "pyproject: die Kern-Abhaengigkeit hat keine Obergrenze mehr", "pyproject.toml",
     '    "python-jobspy>=1.2,<1.4",\n]\n\n[project.optional-dependencies]', '    "python-jobspy>=1.2",\n]\n\n[project.optional-dependencies]', T_JS),
    ("js02", "pyproject: das Extra scraper hat keine Obergrenze mehr", "pyproject.toml",
     '    "python-jobspy>=1.2,<1.4",\n]\ndocs = [', '    "python-jobspy>=1.2",\n]\ndocs = [', T_JS),
    ("js03", "Installer: die pip-Zeile hat keine Obergrenze mehr", "INSTALLIEREN.bat",
     '"python-jobspy>=1.2,<1.4" --no-warn-script-location', '"python-jobspy>=1.2" --no-warn-script-location', T_JS),
    ("js04", "pyproject: die Obergrenze steht auf 1.5 und laesst 1.4.0 durch", "pyproject.toml",
     '    "python-jobspy>=1.2,<1.4",\n]\n\n[project.optional-dependencies]', '    "python-jobspy>=1.2,<1.5",\n]\n\n[project.optional-dependencies]', T_JS),
]
KATALOGE["jobspy1252"] = M_JOBSPY_GRENZE
GRUNDLAEUFE["jobspy1252"] = (("T_JS", T_JS),)

# ── #1233 (F51): die interaktive Hilfe - nachschlagen, nicht raten ──
T_HI = ["tests/test_v18_hilfe_suche_1233.py", "tests/test_v18_hilfe_ki_1233.py"]
T_HI_BROWSER = ["tests/test_v18_hilfe_frage_browser_1233.py"]
# Die Faelle zu #1254 (Seitenleiste: EIN Bereich zum Scrollen, Nachrichten und Antworten nach der Zeit): die Eintraege hi37 bis hi51 laufen nur gegen sie.
T_HI_1254 = [
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_nach_einer_frage_gibt_es_in_der_seitenleiste_einen_einzigen_scrollbereich",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_der_elwosa_verlauf_behaelt_seine_hoehe_wenn_antworten_dazukommen",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_die_antwort_steht_im_verlauf_und_die_eingabe_bleibt_sichtbar_daneben",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_die_neue_antwort_ist_mit_ihrem_anfang_im_blick",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_zwei_fragen_stehen_der_reihe_nach_und_die_neueste_ist_im_blick",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_eine_neue_nachricht_elwosas_kommt_unter_die_antwort_und_ist_zu_sehen",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_die_sechste_frage_verdraengt_die_aelteste_und_ist_im_blick",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_eine_lange_frage_ohne_leerzeichen_macht_keine_waagerechte_leiste",
    "tests/test_v18_hilfe_frage_browser_1233.py::test_1254_der_hilfe_dialog_zeigt_die_neueste_antwort_oben",
]
HI_SUCHE = "src/bewerbungs_assistent/services/hilfe_suche.py"
HI_KI = "src/bewerbungs_assistent/services/hilfe_ki.py"
HI_DASH = "src/bewerbungs_assistent/dashboard.py"
HI_LEISTE = "frontend/src/components/ElwosaSidebarChat.jsx"
HI_APP = "frontend/src/App.jsx"
HI_FRAGE = "frontend/src/components/HilfeFrage.jsx"
HI_KARTE = "frontend/src/components/HilfeKiKarte.jsx"
HI_SCHEMA = "src/bewerbungs_assistent/services/schema_schutz.py"
M_HILFE = [
    # die Suche
    ("hi01", "Eine Nachfrage erbt das Thema der vorigen Frage nicht", HI_SUCHE,
     "    if not konzepte and vorherige:\n", "    if False and not konzepte and vorherige:\n", T_HI),
    ("hi02", "'aktualisiert' und 'aktualisieren' haben wieder verschiedene Staemme", HI_SUCHE,
     '        return _PARTIZIP_IER.sub("ier", wort)\n', "        pass\n", T_HI),
    ("hi03", "Jede Frage gilt als gefunden (Schwelle der Abdeckung 0)", HI_SUCHE,
     "ABDECKUNG_GEFUNDEN = 0.55\n", "ABDECKUNG_GEFUNDEN = 0.0\n", T_HI),
    ("hi04", "Unbekannte Woerter verhindern keine sichere Antwort mehr", HI_SUCHE,
     "UNBEKANNT_GEFUNDEN = 0.34\n", "UNBEKANNT_GEFUNDEN = 9.0\n", T_HI),
    ("hi05", "Der Wiki-Link zeigt nicht mehr ins Wiki des Projekts", HI_SUCHE,
     'WIKI_BASIS = "https://github.com/MadGapun/PBP/wiki/"\n', 'WIKI_BASIS = "https://example.invalid/wiki/"\n', T_HI),
    ("hi06", "Eine lange Frage wird nicht mehr gekuerzt", HI_SUCHE,
     "    return t[:MAX_FRAGE]\n", "    return t\n", T_HI),
    ("hi07", "Gleiche Titel erscheinen mehrfach", HI_SUCHE,
     "        if schluessel in gesehen:\n", "        if False and schluessel in gesehen:\n", T_HI),
    ("hi08", "Ein Sprung auf eine Seite wird auch fuer eine unbekannte Seite angeboten", HI_SUCHE,
     '    if ziel.get("art") == "seite" and ziel.get("id") in w.seiten:\n', '    if ziel.get("art") == "seite":\n', T_HI),
    # die KI-Schicht
    ("hi09", "Die Kurzantwort ist wieder von Anfang an eingeschaltet", HI_KI,
     "VORGABE_AN = False\n", "VORGABE_AN = True\n", T_HI),
    ("hi10", "Eine Kurzantwort ohne genannte Quelle wird angezeigt", HI_KI,
     "    if not zitate:\n", "    if False:\n", T_HI),
    ("hi11", "Eine Kurzantwort darf einen Abschnitt zitieren, der nicht vorliegt", HI_KI,
     "    if any(z < 1 or z > len(abschnitte) for z in zitate):\n", "    if False:\n", T_HI),
    ("hi12", "Eine erfundene Adresse in der Kurzantwort wird nicht erkannt", HI_KI,
     "        if umschrift(adresse.rstrip(", "        if False and umschrift(adresse.rstrip(", T_HI),
    ("hi13", "Ein erfundener Befehl in der Kurzantwort wird nicht erkannt", HI_KI,
     "        if umschrift(code.strip()) not in beleg:\n", "        if False and umschrift(code.strip()) not in beleg:\n", T_HI),
    ("hi14", "Ein erfundener Menuepfad in der Kurzantwort wird nicht erkannt", HI_KI,
     '    if "›" in ohne_zitate:\n', '    if False and "›" in ohne_zitate:\n', T_HI),
    ("hi15", "'KEINE ANTWORT' des Modells wird als Antwort gezeigt", HI_KI,
     '    if "KEINE ANTWORT" in t.upper():\n', '    if False and "KEINE ANTWORT" in t.upper():\n', T_HI),
    ("hi16", "Eine zu lange Kurzantwort wird angezeigt", HI_KI,
     "    if len(t) > MAX_ANTWORT_ZEICHEN:\n", "    if False and len(t) > MAX_ANTWORT_ZEICHEN:\n", T_HI),
    ("hi17", "Auch zu einem unsicheren Treffer wird formuliert", HI_KI,
     '    if antwort.get("status") != "gefunden":\n', '    if False and antwort.get("status") != "gefunden":\n', T_HI),
    ("hi18", "Der Schalter der Kurzantwort wirkt nicht", HI_KI,
     "    if not einstellung(db):\n", "    if False and not einstellung(db):\n", T_HI),
    ("hi19", "Die Kurzantwort entsteht auch bei nicht bereiter lokaler KI", HI_KI,
     '    if not z["aktiv"]:\n', '    if False and not z["aktiv"]:\n', T_HI),
    ("hi20", "Der Auftrag der Kurzantwort traegt die Frage", HI_KI,
     '"grund": "", "angelegt": time.monotonic()}', '"grund": "", "angelegt": time.monotonic(), "frage": frage}', T_HI),
    ("hi21", "Auftraege der Kurzantwort verschwinden nie", HI_KI,
     "> JOB_LEBENSDAUER_SEK]", "> 10 ** 9]", T_HI),
    ("hi22", "Die Quellenmarken [1] bleiben im Text der Kurzantwort", HI_KI,
     '    sauber = re.sub(r"\\s*\\[\\d{1,2}\\]", "", t)\n', "    sauber = t\n", T_HI),
    # die Endpunkte
    ("hi23", "Der Endpunkt formuliert immer, auch ohne Anfrage", HI_DASH,
     'mit_ki=bool(data.get("mit_ki"))', "mit_ki=True", T_HI),
    ("hi24", "Der Endpunkt nimmt auch eine Frage, die kein Text ist", HI_DASH,
     '    if not isinstance(data, dict) or not isinstance(data.get("frage", ""), str):\n', "    if False:\n", T_HI),
    ("hi25", "Fehlen die Daten der Hilfe, meldet der Endpunkt keinen Fehler", HI_DASH,
     "    if not hilfe_suche.verfuegbar():\n", "    if False and not hilfe_suche.verfuegbar():\n", T_HI),
    ("hi26", "Der Schalter nimmt auch einen Wert, der kein Ja oder Nein ist", HI_DASH,
     '    if not isinstance(data, dict) or not isinstance(data.get("formulieren"), bool):\n', "    if False:\n", T_HI),
    # die Oberflaeche (das gebaute Bundle)
    ("hi27", "Die Eingabe erscheint in der Seitenleiste auch ohne laufende lokale KI", HI_LEISTE,
     "  const fragenAktiv = seitenleisteFragt(status);\n", "  const fragenAktiv = true;\n", T_HI_BROWSER),
    ("hi28", "Das Oeffnen aus dem Dialog laesst den Dialog stehen", HI_APP,
     "onOeffnen={(seite, absicht) => { setHelpOpen(false); navigateTo(seite, absicht); }}", "onOeffnen={(seite, absicht) => { navigateTo(seite, absicht); }}", T_HI_BROWSER),
    ("hi29", "Der Wiki-Link oeffnet im selben Tab, ohne noopener", HI_FRAGE,
     'target="_blank" rel="noopener noreferrer" data-hilfe-aktion="wiki"', 'data-hilfe-aktion="wiki"', T_HI_BROWSER),
    ("hi30", "Der Schalter der Kurzantwort speichert nichts", HI_KARTE,
     "onChange={(e) => umschalten(e.target.checked)}", "onChange={() => {}}", T_HI_BROWSER),
    # der Schema-Schutz
    ("hi31", "Bei zu neuer Datenbank antwortet die Hilfe nicht mehr (die Frage gilt als schreibender Aufruf)", HI_SCHEMA,
     ', "/api/hilfe/frage")\n', ")\n", T_HI),
    # Nachtrag zur KI-Schicht
    ("hi32", "Auftraege der Kurzantwort stapeln sich ohne Grenze", HI_KI,
     "    if offene_auftraege() >= MAX_OFFENE_AUFTRAEGE:\n", "    if False and offene_auftraege() >= MAX_OFFENE_AUFTRAEGE:\n", T_HI),
    # die Beispielfragen
    ("hi33", "Die Beispielfragen stehen auch nach der ersten Frage da", HI_FRAGE,
     "{!kompakt && verlauf.length === 0 && (", "{!kompakt && (", T_HI_BROWSER),
    ("hi34", "Die schmale Seitenleiste zeigt Beispielfragen", HI_FRAGE,
     "{!kompakt && verlauf.length === 0 && (", "{verlauf.length === 0 && (", T_HI_BROWSER),
    ("hi35", "Ein Klick auf eine Beispielfrage stellt keine Frage", HI_FRAGE,
     "onClick={() => fragen(null, beispiel)}", "onClick={() => {}}", T_HI_BROWSER),
    ("hi36", "Eine Beispielfrage fuehrt in eine Sackgasse", "frontend/src/lib/hilfeFrage.js",
     '  "Wie melde ich einen Fehler?",\n', '  "Wie wird das Wetter morgen?",\n', T_HI),
    # #1254 (F57): Elwosas Nachrichten und die Antworten der Hilfe stehen in EINEM Bereich zum Scrollen, nach der Zeit wie in einem Chat.
    # Die Eintraege laufen nur gegen die Faelle zu #1254 (T_HI_1254): der erste rote Test ist dann einer von ihnen und nicht ein aelterer der Datei.
    ("hi37", "Die Antworten der Hilfe bekommen wieder einen eigenen Scroller", HI_FRAGE,
     '<div className="space-y-1.5" data-hilfe-antwort={antwort.status} data-hilfe-eintrag={eintrag.id}>',
     '<div className="max-h-[38vh] space-y-1.5 overflow-y-auto" data-hilfe-antwort={antwort.status} data-hilfe-eintrag={eintrag.id}>', T_HI_1254),
    ("hi38", "Die Antworten stehen wieder im Block des Feldes und nehmen dem Verlauf die Hoehe", HI_LEISTE,
     "          <HilfeEingabe hilfe={hilfe} kompakt />\n",
     "          <HilfeEingabe hilfe={hilfe} kompakt />\n"
     "          {hilfe.verlauf.map((e) => <HilfeAntwort key={e.id} eintrag={e} kompakt onOeffnen={onOeffnen} copyPrompt={onCopyPrompt} />)}\n", T_HI_1254),
    ("hi39", "Die Antworten stehen nicht im Strom", HI_LEISTE,
     "const strom = stromMit(messages, fragenAktiv ? hilfe.verlauf : []);", "const strom = stromMit(messages, []);", T_HI_1254),
    ("hi40", "Nach einer Frage bleibt der Bereich stehen, die Antwort liegt unter dem Bild", HI_LEISTE,
     "    liste.scrollTop += eintrag.getBoundingClientRect().top - liste.getBoundingClientRect().top - 4;\n",
     "    liste.scrollTop += 0;\n", T_HI_1254),
    ("hi41", "Nach einer Frage scrollt der Bereich ans Ende statt an den Anfang der Antwort", HI_LEISTE,
     "    liste.scrollTop += eintrag.getBoundingClientRect().top - liste.getBoundingClientRect().top - 4;\n",
     "    liste.scrollTop = liste.scrollHeight;\n", T_HI_1254),
    ("hi42", "Die Zeile 'Fragen zur Bedienung' fehlt", HI_LEISTE,
     'if (letzteArt !== "hilfe") groupedByDay.push({ type: "hilfe-kopf" });', 'if (false) groupedByDay.push({ type: "hilfe-kopf" });', T_HI_1254),
    ("hi43", "Die Zeile 'Fragen zur Bedienung' steht vor jeder Antwort statt vor jeder Reihe von Antworten", HI_LEISTE,
     'if (letzteArt !== "hilfe") groupedByDay.push({ type: "hilfe-kopf" });', 'if (true) groupedByDay.push({ type: "hilfe-kopf" });', T_HI_1254),
    ("hi44", "Alle Antworten stehen hinter allen Nachrichten: eine neue Nachricht Elwosas kommt UEBER die Antworten", "frontend/src/lib/hilfeFrage.js",
     "(i < msgs.length && !(msgs[i].t > fragen[j].t))", "(i < msgs.length)", T_HI_1254),
    ("hi45", "Die Antworten stehen vor den Nachrichten statt nach der Zeit", "frontend/src/lib/hilfeFrage.js",
     "(i < msgs.length && !(msgs[i].t > fragen[j].t))", "(i < msgs.length && msgs[i].t > fragen[j].t)", T_HI_1254),
    ("hi46", "Eine Antwort traegt keine Zeit, sie steht darum am Ende der Reihe", HI_FRAGE,
     "kiStand: null, zeit: Date.now() };", "kiStand: null };", T_HI_1254),
    ("hi47", "Im Hilfe-Dialog steht die neueste Antwort nicht mehr oben", HI_FRAGE,
     "{[...verlauf].reverse().map((e) => (", "{verlauf.map((e) => (", T_HI_1254),
    ("hi48", "Der Rahmen fuer die Meldung einer neuen Antwort meldet nichts", HI_LEISTE,
     '<div className="sr-only" aria-live="polite" data-hilfe-ansage>', '<div className="sr-only" data-hilfe-ansage>', T_HI_1254),
    ("hi49", "Der Rahmen fuer die Meldung einer neuen Antwort bleibt leer", HI_LEISTE,
     'const ansage = fragenAktiv && hilfe.verlauf.length > 0 ? ansageText(hilfe.verlauf[hilfe.verlauf.length - 1]) : "";', 'const ansage = "";', T_HI_1254),
    ("hi50", "Eine lange Frage ohne Leerzeichen macht eine waagerechte Leiste", HI_FRAGE,
     '<p className="break-words text-xs text-ink/80" data-hilfe-frage-text>', '<p className="text-xs text-ink/80" data-hilfe-frage-text>', T_HI_1254),
    ("hi51", "Der Verlauf waechst ohne Grenze statt bei fuenf Fragen zu enden", "frontend/src/lib/hilfeFrage.js",
     "return [...(verlauf || []), eintrag].slice(-MAX_VERLAUF);", "return [...(verlauf || []), eintrag];", T_HI_1254),
]
KATALOGE["hilfe1233"] = M_HILFE
GRUNDLAEUFE["hilfe1233"] = (("T_HI", T_HI), ("T_HI_BROWSER", T_HI_BROWSER))

# ── #1256 (F58): der Elwosa-Strom - die Marke "N neu" zaehlt nach Kennung, der Bereich haelt das Ende bei Hoehenaenderung ──
# Die Browser-Faelle stehen in der Datei zu #1233/#1254 (`test_1256_*`); jeder Eintrag zielt auf EINEN Handgriff der Behebung. Eintraege unter
# frontend/ bauen das Bundle neu.
STROM_BROWSER = "tests/test_v18_hilfe_frage_browser_1233.py::"
T_STROM_MARKE = [STROM_BROWSER + n for n in (
    "test_1256_die_marke_neu_erscheint_auch_bei_voller_liste",
    "test_1256_die_marke_zaehlt_mit_und_beginnt_am_ende_von_vorn",
    "test_1256_das_ausblenden_einer_nachricht_macht_keine_marke",
    "test_1256_bei_kurzer_liste_zeigt_die_marke_weiter_die_neuen",
)]
T_STROM_ENDE = [STROM_BROWSER + n for n in (
    "test_1256_wird_der_bereich_niedriger_bleibt_das_ende_im_bild",
    "test_1256_eine_meldung_nach_sprung_und_hoehenaenderung_bleibt_nicht_verdeckt",
    "test_1256_wird_der_bereich_hoeher_und_liegt_das_ende_im_bild_verschwindet_die_marke",
    "test_1256_auch_die_zweite_hoehenaenderung_rechnet_mit_der_neuen_hoehe",
    "test_1256_wer_oben_liest_wird_bei_hoehenaenderung_und_neuer_meldung_nicht_nach_unten_gezogen",
)]
T_STROM_SPRUNG = [STROM_BROWSER + "test_1256_eine_meldung_direkt_nach_einem_sprung_ans_ende_ist_zu_sehen",
                  STROM_BROWSER + "test_1254_eine_neue_nachricht_elwosas_kommt_unter_die_antwort_und_ist_zu_sehen"]
T_STROM_NEU = [STROM_BROWSER + "test_1256_nach_dem_wiedereinblenden_steht_der_verlauf_am_ende"]
T_STROM_AUSBLENDEN = [STROM_BROWSER + "test_1256_was_waehrend_des_ausblendens_kam_steht_beim_wiedereinblenden_unten_und_ist_nicht_neu"]
T_STROM_FRAGE = [STROM_BROWSER + "test_1256_wer_nach_einer_frage_den_anfang_der_antwort_liest_wird_von_einer_meldung_nicht_ans_ende_gezogen"]
T_STROM_PROFIL = [STROM_BROWSER + "test_1256_nach_einem_profilwechsel_beginnt_die_zaehlung_neu"]
# die Knoten-Tests laufen als Ganzes (die Kennung einer parametrierten Funktion kennt der Waechter des Katalogs nicht); der Eingriff in die Bibliothek
# macht den Fall elwosaStrom rot
T_STROM_NODE = ["tests/test_v18_knoten_tests_1171.py"]
T_STROM_QUELLTEXT = ["tests/test_v1717_sidebar_907.py::test_1256_der_strom_zaehlt_nach_kennung_und_beobachtet_seine_hoehe"]
STROM_LEISTE = "frontend/src/components/ElwosaSidebarChat.jsx"
STROM_LIB = "frontend/src/lib/elwosaStrom.js"
STROM_APP = "frontend/src/App.jsx"
STROM_RO_ZEILE = "      if (Math.min(abstandVorher, abstandJetzt) >= AM_ENDE_TOLERANZ) return; // wer oben liest, bleibt stehen\n"
M_STROM = [
    # die Marke "N neu": neu ist, was eine groessere Kennung traegt
    ("ev01", "Die Marke zaehlt wieder die Nachrichten der Liste statt der neuen Kennungen", STROM_LEISTE,
     "    const { anzahl: neue, hoechste } = neueNachrichten(letzteKennung.current, messages);\n    letzteKennung.current = hoechste;\n",
     "    const neue = Math.max(0, messages.length - (letzteKennung.current ?? 0));\n    letzteKennung.current = messages.length;\n",
     T_STROM_MARKE + T_STROM_QUELLTEXT),
    ("ev02", "Die Marke zaehlt nicht weiter, jede neue Meldung setzt sie auf die eigene Zahl", STROM_LEISTE,
     "      setUnreadBelow((u) => u + neue);\n", "      setUnreadBelow(neue);\n", T_STROM_MARKE),
    ("ev03", "Die Marke wird nie gezeigt", STROM_LEISTE,
     "      setShowJumpToBottom(true);\n    }\n  }, [messages]);\n", "    }\n  }, [messages]);\n", T_STROM_MARKE),
    ("ev04", "Beim ersten Laden zaehlt alles als neu", STROM_LIB,
     "  if (gesehen === null || gesehen === undefined) return { anzahl: 0, hoechste };\n", "", T_STROM_NODE),
    ("ev05", "Die groesste gesehene Kennung sinkt, wenn die neueste Nachricht ausgeblendet wird", STROM_LIB,
     "  return { anzahl, hoechste: Math.max(gesehen, hoechste) };\n", "  return { anzahl, hoechste };\n", T_STROM_NODE),
    ("ev06", "Die zuletzt gesehene Nachricht zaehlt noch einmal als neu", STROM_LIB,
     "    if (kennung(nachricht) > gesehen) anzahl += 1;\n", "    if (kennung(nachricht) >= gesehen) anzahl += 1;\n", T_STROM_NODE + T_STROM_MARKE),
    ("ev07", "Eine Zeile ohne gueltige Kennung zaehlt als neu", STROM_LIB,
     "  return Number.isFinite(n) && n > 0 ? n : 0;\n", "  return Number.isFinite(n) && n > 0 ? n : Number.MAX_SAFE_INTEGER;\n", T_STROM_NODE),
    # das Ende halten, wenn sich die Hoehe aendert
    ("ev08", "Der Beobachter haelt das Ende nicht", STROM_LEISTE,
     "      liste.scrollTop = liste.scrollHeight;\n", "      liste.scrollTop += 0;\n", T_STROM_ENDE),
    ("ev09", "Der Beobachter rechnet nur mit der Hoehe von jetzt (das Ende rutscht bei einem niedrigeren Bereich)", STROM_LEISTE,
     STROM_RO_ZEILE, "      if (abstandJetzt >= AM_ENDE_TOLERANZ) return; // wer oben liest, bleibt stehen\n", T_STROM_ENDE),
    ("ev10", "Der Beobachter rechnet nur mit der Hoehe von vorher (ein hoeherer Bereich bringt das Ende nicht zurueck)", STROM_LEISTE,
     STROM_RO_ZEILE, "      if (abstandVorher >= AM_ENDE_TOLERANZ) return; // wer oben liest, bleibt stehen\n", T_STROM_ENDE),
    ("ev11", "Der Beobachter zieht auch den nach unten, der oben liest", STROM_LEISTE, STROM_RO_ZEILE, "", T_STROM_ENDE),
    ("ev12", "Der Beobachter wird nie angelegt", STROM_LEISTE,
     "    groessenBeobachter.current.observe(el);\n", "", T_STROM_ENDE),
    ("ev13", "Die Hoehe von vorher wird nicht fortgeschrieben (die zweite Aenderung rechnet mit der Hoehe vom Anfang)", STROM_LEISTE,
     "      sichtHoehe.current = liste.clientHeight;\n", "", T_STROM_ENDE),
    ("ev14", "Ein neuer Bereich beginnt nicht unten (nach dem Wiedereinblenden steht er oben)", STROM_LEISTE,
     "    el.scrollTop = el.scrollHeight;\n    sichtHoehe.current = el.clientHeight;\n", "    sichtHoehe.current = el.clientHeight;\n", T_STROM_NEU),
    # ob der Mensch am Ende steht: die Geometrie beim Eintreffen der Daten, nicht ein ausstehendes Ereignis
    ("ev15", "Beim Eintreffen der Daten wird nicht gemessen, ob der Mensch am Ende steht", STROM_LEISTE,
     "        warAmEnde.current = scrollRef.current ? stehtAmEnde(scrollRef.current) : null;\n", "", T_STROM_SPRUNG + T_STROM_QUELLTEXT),
    ("ev16", "Die Toleranz ist 0: der Mensch gilt nie als am Ende", STROM_LEISTE,
     'const AM_ENDE_TOLERANZ = 30; // px: so nah am Ende gilt der Mensch noch als "am Ende"\n',
     'const AM_ENDE_TOLERANZ = 0; // px: so nah am Ende gilt der Mensch noch als "am Ende"\n', T_STROM_ENDE + T_STROM_SPRUNG),
    ("ev17", "Die Kennung wird nur nachgefuehrt, solange es den Bereich gibt (was beim Ausblenden kommt, gilt spaeter als neu)", STROM_LEISTE,
     "    letzteKennung.current = hoechste;\n", "    if (scrollRef.current) letzteKennung.current = hoechste;\n", T_STROM_AUSBLENDEN),
    ("ev18", "Wer den Anfang einer Antwort liest, wird von einer neuen Meldung ans Ende gezogen (jede Meldung gilt als gefolgt)", STROM_LEISTE,
     "    const folgt = warAmEnde.current === true;\n", "    const folgt = true;\n", T_STROM_FRAGE + T_STROM_MARKE),
    ("ev19", "Eine Liste ohne Messung (Ausblenden, gelesen) zieht den Menschen ans Ende", STROM_LEISTE,
     "    const folgt = warAmEnde.current === true;\n", "    const folgt = warAmEnde.current !== false;\n", T_STROM_MARKE + T_STROM_FRAGE),
    ("ev20", "Nach einem Profilwechsel beginnt die Seitenleiste nicht neu (die Liste des anderen Profils gilt als neu)", STROM_APP,
     '                key={activeProfileId || "kein-profil"}\n', "", T_STROM_PROFIL + T_STROM_QUELLTEXT),
]
KATALOGE["elwosa_strom1256"] = M_STROM
GRUNDLAEUFE["elwosa_strom1256"] = (("T_STROM_MARKE", T_STROM_MARKE), ("T_STROM_ENDE", T_STROM_ENDE), ("T_STROM_SPRUNG", T_STROM_SPRUNG),
                                   ("T_STROM_NEU", T_STROM_NEU), ("T_STROM_AUSBLENDEN", T_STROM_AUSBLENDEN), ("T_STROM_FRAGE", T_STROM_FRAGE),
                                   ("T_STROM_PROFIL", T_STROM_PROFIL), ("T_STROM_NODE", T_STROM_NODE), ("T_STROM_QUELLTEXT", T_STROM_QUELLTEXT))

# ── Installer und Claude-Konfiguration: was der Mensch unter env eingetragen hat, bleibt (#1238, I38) ──
# Das Wort der Konfiguration steht hier NICHT als Literal: der Waechter in test_1238 sucht es in scripts/ und wuerde
# dieses Skript sonst als unbekannten Schreiber melden. install.ps1 ist in dieser Linie ein Stub (#1149): die Eingriffe in
# die PowerShell-Funktion gibt es nur in der Stable-Linie.
MCP_WORT = "mcp" + "Servers"
T_CK = ["tests/test_1238_installer_env_erhalten.py"]
GUI = "installer/setup_gui.py"
UNIX_AUFRUF_ZEILE = '    if SETUP_AUSGABE="$("$PYTHON" "$PROJECT_DIR/_setup_claude.py" 2>&1)"; then\n'

M_CLAUDEKONFIG = [
    # setup_gui.py
    ("ck01", "setup_gui: die Datei wird nicht BOM-fest gelesen (PowerShell 5.1 schreibt ein BOM)", GUI,
     "encoding='utf-8-sig') as f:", "encoding='utf-8') as f:", T_CK),
    ("ck02", "setup_gui: das env wird wieder neu gebaut", GUI,
     "                'env': env\n", "                'env': {'BA_DATA_DIR': data_dir}\n", T_CK),
    ("ck03", "setup_gui: ein verlegter Datenordner wird ueberschrieben", GUI,
     "env.setdefault('BA_DATA_DIR', data_dir)", "env['BA_DATA_DIR'] = data_dir", T_CK),
    ("ck04", "setup_gui: ein alter PYTHONPATH bleibt und laedt den alten Programmstand", GUI,
     "env.pop('PYTHONPATH', None)", "pass", T_CK),
    # switch_mode.py
    ("ck05", "switch_mode: der bisherige Eintrag wird nicht mehr gelesen, das env geht verloren", "switch_mode.py",
     "server.get(MCP_KEY))", "None)", T_CK),
    ("ck06", "switch_mode: die Datei wird nicht BOM-fest gelesen", "switch_mode.py",
     'encoding="utf-8-sig")', 'encoding="utf-8")', T_CK),
    # _setup_claude.py (der Weg von INSTALLIEREN.bat, INSTALLIEREN.command und install.sh; seit v1.7.145)
    ("ck07", "_setup_claude: das env des bisherigen Eintrags wird nicht uebernommen", "_setup_claude.py",
     'env.update(alter_eintrag["env"])', "pass", T_CK),
    ("ck08", "_setup_claude: ein verlegter Datenordner wird ueberschrieben", "_setup_claude.py",
     'env.setdefault("BA_DATA_DIR", data_dir)', 'env["BA_DATA_DIR"] = data_dir', T_CK),
    # die Aufrufer und die Liste der Schreiber
    ("ck09", "INSTALLIEREN.command ruft _setup_claude.py nicht mehr auf", "INSTALLIEREN.command",
     UNIX_AUFRUF_ZEILE, '    if SETUP_AUSGABE="$(true 2>&1)"; then\n', T_CK),
    ("ck10", "install.sh ruft _setup_claude.py nicht mehr auf", "installer/install.sh",
     UNIX_AUFRUF_ZEILE, '    if SETUP_AUSGABE="$(true 2>&1)"; then\n', T_CK),
    ("ck11", "INSTALLIEREN.bat ruft _setup_claude.py nicht mehr auf", "INSTALLIEREN.bat",
     '"%PYTHON%" "%BASEDIR%\\_setup_claude.py" >> "%LOGFILE%" 2>&1', 'rem entfaellt >> "%LOGFILE%" 2>&1', T_CK),
    ("ck12", "install.sh baut den Eintrag selbst (die Datei nennt die Konfiguration)", "installer/install.sh",
     "# ── FERTIG", "# " + MCP_WORT + " ── FERTIG", T_CK),
    ("ck13", "ein Programmteil beruehrt die Konfiguration von Claude Desktop", "src/bewerbungs_assistent/__init__.py",
     '"""Entry point for the package."""', '"""Entry point for the package."""  # ' + MCP_WORT, T_CK),
    ("ck14", "ein neues Skript in scripts/ schreibt die Konfiguration, ohne in der Liste zu stehen", "scripts/ui_texte_pruefen.py",
     '"""Sichtbare Texte der Oberflaeche pruefen', '"""' + MCP_WORT + ' Sichtbare Texte der Oberflaeche pruefen', T_CK),
]
KATALOGE["claude_konfig"] = M_CLAUDEKONFIG
GRUNDLAEUFE["claude_konfig"] = (("T_CK", T_CK),)

# ── #1237: "bis heute" rechnet mit der Uhr, nie mit einer Jahreszahl im Code ──
# Zeitabhaengige Fehler zeigt kein Test mit dem Datum von heute: bis zum 31.12.2026 ist die feste 2026 "richtig".
# Darum stellen die Tests die Uhr auf Tage vor, in und nach 2026; "an der Naht vorbei" (datetime.now statt
# uhr.heute) und "feste Zahl" sind zwei verschiedene Eingriffe, die verschieden erkannt werden muessen.
T_BJ = ["tests/test_berufsjahre_laufendes_jahr_1237.py"]
BJ_UHR = "src/bewerbungs_assistent/services/uhr.py"
BJ_BF = "src/bewerbungs_assistent/services/berufsfeld.py"
BJ_AA = "src/bewerbungs_assistent/services/auto_aussortierung.py"
BJ_EX = "src/bewerbungs_assistent/export.py"
BJ_T = T_BJ[0]
#: Die Rechnung der Auto-Aussortierung bis v1.7.158: eigene Schleife, feste 2026 fuer ein offenes Ende.
BJ_ALTE_SCHLEIFE = (
    'years = 0\n'
    '    for p in positions:\n'
    '        try:\n'
    '            start = int((p.get("start_date") or "0000")[:4])\n'
    '            end_raw = (p.get("end_date") or "")[:4]\n'
    '            end = int(end_raw) if end_raw.isdigit() else 2026\n'
    '            if start > 1900:\n'
    '                years += max(0, end - start)\n'
    '        except Exception:\n'
    '            pass\n')
M_BERUFSJAHRE = [
    ("bj01", "Die Uhr liefert einen festen Tag statt des heutigen", BJ_UHR,
     "    return date.today()\n", "    return date(1999, 1, 1)\n", T_BJ),
    ("bj02", "berufsjahre liest die Uhr an der Naht vorbei (datetime.now)", BJ_BF,
     "    this_year = uhr.heute().year\n", "    from datetime import datetime\n    this_year = datetime.now().year\n", T_BJ),
    ("bj03", "berufsjahre rechnet wieder mit einer festen 2026", BJ_BF,
     "    this_year = uhr.heute().year\n", "    this_year = 2026\n", T_BJ),
    ("bj04", "ein offenes Ende zaehlt nicht mehr bis heute", BJ_BF,
     "        end = int(end_raw) if end_raw.isdigit() else this_year\n",
     "        end = int(end_raw) if end_raw.isdigit() else start\n", T_BJ),
    ("bj05", "eine Station, die spaeter beginnt, zaehlt negativ", BJ_BF,
     "        total += max(0, end - start)\n", "        total += end - start\n", T_BJ),
    ("bj06", "die Auto-Aussortierung nimmt die Berufsjahre nicht mehr", BJ_AA,
     "years = berufsjahre(positions)\n", "years = 0\n", T_BJ),
    ("bj07", "die Auto-Aussortierung hat wieder ihre eigene Schleife mit fester 2026", BJ_AA,
     "years = berufsjahre(positions)\n", BJ_ALTE_SCHLEIFE, T_BJ),
    ("bj08", "die Recruiter-Wertung liest die Uhr an der Naht vorbei", BJ_EX,
     "end_year = uhr.heute().year", "end_year = datetime.now().year", T_BJ),
    ("bj09", "die Recruiter-Wertung rechnet wieder mit einer festen 2026", BJ_EX,
     "end_year = uhr.heute().year", "end_year = 2026", T_BJ),
    ("bj10", "die Luecken-Erkennung liest die Uhr an der Naht vorbei", BJ_EX,
     "heute = uhr.heute()", "heute = datetime.now()", T_BJ),
    ("bj11", "die Luecken-Erkennung rechnet wieder mit 2026-03", BJ_EX,
     "e_year, e_month = heute.year, heute.month", "e_year, e_month = 2026, 3", T_BJ),
    ("bj12", "die Luecken-Erkennung ignoriert den Monat von heute", BJ_EX,
     "e_year, e_month = heute.year, heute.month", "e_year, e_month = heute.year, 12", T_BJ),
    # der Waechter selbst (die Mutationen sitzen in der Testdatei)
    ("bj13", "Waechter: das Fenster beginnt erst 2030", BJ_T,
     "JAHR_VON, JAHR_BIS = 2020, 2039", "JAHR_VON, JAHR_BIS = 2030, 2039", T_BJ),
    ("bj14", "Waechter: das Fenster endet schon 2025", BJ_T,
     "JAHR_VON, JAHR_BIS = 2020, 2039", "JAHR_VON, JAHR_BIS = 2020, 2025", T_BJ),
    ("bj15", "Waechter: die Raender des Fensters zaehlen nicht", BJ_T,
     "        return JAHR_VON <= wert <= JAHR_BIS\n", "        return JAHR_VON < wert < JAHR_BIS\n", T_BJ),
    ("bj16", "Waechter: reine Jahres-Zeichenketten zaehlen nicht", BJ_T,
     "        return len(wert) == 4 and wert.isdigit() and JAHR_VON <= int(wert) <= JAHR_BIS\n", "        return False\n", T_BJ),
    ("bj17", "Waechter: eine Marke ohne Grund genuegt", BJ_T,
     "        if MARKE in kommentar and kommentar.partition(MARKE)[2].strip():\n", "        if MARKE in kommentar:\n", T_BJ),
    ("bj18", "Waechter: der Ordner services wird nicht gelesen", BJ_T,
     '    return sorted(p for p in SRC.rglob("*.py") if "static" not in p.parts)\n',
     '    return sorted(p for p in SRC.rglob("*.py") if "static" not in p.parts and "services" not in p.parts)\n', T_BJ),
    ("bj19", "Waechter: der Syntaxbaum wird nur eine Ebene tief gelesen", BJ_T,
     "    for knoten in ast.walk(ast.parse(quelltext)):\n", "    for knoten in ast.iter_child_nodes(ast.parse(quelltext)):\n", T_BJ),
]
KATALOGE["berufsjahre1237"] = M_BERUFSJAHRE
GRUNDLAEUFE["berufsjahre1237"] = (("T_BJ", T_BJ),)

# ── #1245 (I39): Installer und Deinstaller kennen den Datenordner der neueren Store-Fassung von Claude ──
T_CO = ["tests/test_v17159_claude_konfig_ort_1245.py"]
T_COD = ["tests/test_v18_praxisprobe_deinstaller.py::test_pp37b_die_datei_der_neuen_store_fassung_wird_bereinigt",
         "tests/test_v18_praxisprobe_deinstaller.py::test_pp37b_alle_drei_orte_in_einem_lauf",
         "tests/test_v18_praxisprobe_deinstaller.py::test_pp37b_der_hinweis_fuer_den_handgriff_nennt_den_neuen_ort"]
CO_SETUP = "_setup_claude.py"
# Das Wort der Konfiguration steht hier NICHT als Literal: der Waechter in test_1238 sucht es in scripts/ und wuerde dieses Skript
# sonst als unbekannten Schreiber melden.
CO_MCP = "mcp" + "Servers"
CO_DEIN = "DEINSTALLIEREN.bat"
CO_PS_ZEILE = ("if ($env:LOCALAPPDATA) { foreach ($d in @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Claude-Data') -Directory "
               "-Filter 'claude*' -ErrorAction SilentlyContinue)) { $pfade += Join-Path $d.FullName 'claude_desktop_config.json' } }; ")
M_CLAUDE_ORT = [
    # der Installer
    ("co01", "Installer: der Datenordner der neueren Store-Fassung fehlt in der Pfadliste", CO_SETUP,
     "            paths.extend(_claude_data_pfade(local_app))\n", "            pass\n", T_CO),
    ("co02", "Installer: jeder Eintrag unter Claude-Data zaehlt als Konfigurationsort", CO_SETUP,
     '        if (klein == "claude" or klein.startswith("claude_")) and os.path.isdir(os.path.join(wurzel, name)):\n',
     "        if True:\n", T_CO),
    ("co03", "Installer: auch eine Datei namens claude_x zaehlt als Ordner", CO_SETUP,
     ' and os.path.isdir(os.path.join(wurzel, name)):\n', ":\n", T_CO),
    ("co04", "Installer: das Zuruecklesen nach dem Schreiben entfaellt", CO_SETUP,
     '    if zurueck is None or zurueck.get("' + CO_MCP + '", {}).get("bewerbungs-assistent") != eintrag:\n',
     "    if False:\n", T_CO),
    ("co05", "Installer: ein Schreibfehler einer Datei bricht den ganzen Lauf ab", CO_SETUP,
     "    except OSError as e:\n        # Eine Datei, die sich nicht schreiben laesst",
     "    except KeyError as e:\n        # Eine Datei, die sich nicht schreiben laesst", T_CO),
    ("co06", "Installer: auch eine nicht geschriebene Datei zaehlt als geschrieben", CO_SETUP,
     "        if config_schreiben(cp, python_exe, src_dir, data_dir):\n            written += 1\n",
     "        config_schreiben(cp, python_exe, src_dir, data_dir)\n        written += 1\n", T_CO),
    ("co07", "Installer: ohne geschriebene Datei endet der Lauf trotzdem mit Erfolg", CO_SETUP,
     "    if written == 0:\n", "    if False:\n", T_CO),
    # der Deinstaller
    ("co08", "Deinstaller: der Datenordner der neueren Store-Fassung wird nicht durchsucht", CO_DEIN,
     CO_PS_ZEILE, "", T_COD),
    ("co09", "Deinstaller: der Filter findet die Ordner unter Claude-Data nicht", CO_DEIN,
     "-Directory -Filter 'claude*' -ErrorAction", "-Directory -Filter 'zzz*' -ErrorAction", T_COD),
    ("co10", "Deinstaller: er sucht im Datenordner eine andere Datei", CO_DEIN,
     "$pfade += Join-Path $d.FullName 'claude_desktop_config.json' } }; ", "$pfade += Join-Path $d.FullName 'config.json' } }; ", T_COD),
    ("co11", "Deinstaller: der Hinweis fuer den Handgriff nennt den neuen Ort nicht", CO_DEIN,
     "\\Claude-Data\\claude_...\\claude_desktop_config.json^)\n", "\\Zzz\\claude_desktop_config.json^)\n", T_COD),
    # die Probe des Werkstatt-PCs
    ("co12", "Probe: sie sucht den Datenordner von Claude nicht", "docs/internal/testlauf/pbp_probe.ps1",
     "  $cd = Join-Path $LA 'Claude-Data'\n", "  $cd = Join-Path $LA 'Zzz'\n", T_CO),
]
KATALOGE["claude_ort1245"] = M_CLAUDE_ORT
GRUNDLAEUFE["claude_ort1245"] = (("T_CO", T_CO), ("T_COD", T_COD))

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
