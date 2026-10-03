# Entwurf: CHANGELOG-Eintrag für 1.8.0

> **Kein Teil des CHANGELOG.** Der Eintrag kommt GANZ OBEN in `CHANGELOG.md`, sobald die Version angehoben wird (`release_check.py`
> verlangt den Kopf auf der aktuellen Version). Zahlen (Tests, Datum) beim Release einsetzen, danach diese Datei löschen.
> Stand des Entwurfs: 02.10.2026, Arbeitszweige `feature/v18-auto-update-1093` → `-speicher-1131` → `-mail-zugang-947` → `-firmen-1080`.

---

## [1.8.0] - TT.MM.2026 — Updates, die sich selbst installieren

PBP kann sich jetzt selbst aktualisieren — **wenn du es willst**. Ohne deine Wahl installiert PBP nichts. Dazu kommen die Übersicht
„Speicher & Downloads“, die Prüfsumme für Zusatzprogramme, die Zugangsschicht für Jobmails aus Ordnern und der Firmen-Eintrag. Die Version
sammelt außerdem alles, was die 1.8.0-Betas (beta.0 bis beta.15) und die Hotfixes bis v1.7.150 geliefert haben; die Einzelheiten stehen in den
Einträgen darunter.

**Wichtig zu wissen:**

- **Updates (Einstellungen › Erweitert › Updates).** Vier Stufen: *Nur Hinweis* (Vorgabe), *Mit einem Klick*, *Automatisch, mit Meldung*,
  *Automatisch, still*. Neue Versionen landen in einem eigenen Ordner neben der laufenden; startet die neue nicht, fällt PBP **von selbst auf die
  vorige zurück** und sagt es. Geladen wird nur von der festen GitHub-Adresse, nur stabile Versionen der eigenen Linie, mit Prüfsumme **und Signatur**
  (Ed25519; ohne gültige Signatur wird nichts installiert). Die Automatik startet nie neben anderer Arbeit.
- **Einmalig von Hand:** Die erste Version mit dieser Funktion ist 1.8.0 selbst. Wer von 1.7.x kommt, installiert sie wie gewohnt (ZIP,
  `INSTALLIEREN.bat`); ab dann kann PBP den Rest selbst. **Das automatische Aktualisieren gibt es zurzeit nur unter Windows.**
- **Speicher & Downloads (Einstellungen › Erweitert).** Wohin PBP schreibt und lädt, wie viel dort liegt, und Aufräumen in zwei Schritten — nie
  ohne dein Ja, nie bei laufender Arbeit. Was anderen Programmen gehört (Browser der Jobsuche, KI-Modelle), wird nur gezeigt.
- **Mail-Ordner (Einstellungen › Erweitert › Quellen im Detail).** Der Ordner-Scan ist **standardmäßig aus**; gelesen werden nur Ordner, die du
  ausdrücklich freigibst. PBP öffnet nie selbst ein Postfach. Ein Add-on, das Ordner von sich aus liest, gibt es noch nicht — das Thunderbird-Add-on
  schickt weiter nur, was du markierst.
- **Firmen (Kontakte › Firmen).** Alles, was PBP zu einer Firma weiß, als eine Zeitleiste; ein Firmen-Eintrag fasst Schreibweisen zusammen
  („Alt AG“ heißt heute „Neu GmbH“) und kennt die Mutterfirma. Bewerbungen, Stellen und Kontakte behalten ihren Firmennamen als Text.

### Added

- **Auto-Update** (#1093): `services/auto_update/` (feste Quelle, Prüfsumme, Ed25519-Signatur in reinem Python, sicheres Entpacken, Manifest,
  Selbsttest vor dem Umschalten, Stufen, Verlauf), der **Startbaustein** `bewerbungs_assistent_boot` (eingefroren, nur Standardbibliothek,
  Rückfall im selben Prozess und nach zwei unbestätigten Starts), der **Schema-Schutz** (`services/schema_schutz.py`: ist die Datenbank neuer als
  das Programm, schreibt der alte Prozess nicht weiter), der Hinweis, wenn Claude und Dashboard mit verschiedenen Fassungen laufen, der
  Installer-Umbau (Versionsordner, Selbstaufräumen, Deinstaller), `scripts/build_update_archive.py` und ein Schritt im Release-Tor. Werkzeuge
  `update_status`, `update_einstellungen_setzen`, `update_jetzt_installieren`, `update_zurueckschalten`.
- **Speicher & Downloads** (#1131): sieben Orte, sieben Aufräum-Aktionen, Werkzeuge `speicher_anzeigen` und `speicher_bereinigen`.
- **Prüfsumme der Komponenten** (#1152): kein Installer ohne SHA-256; die Ablehnung kommt vor dem Download.
- **Mail-Zugangsschicht** (#947): Schalter, genaue Liste freigegebener Ordner, Prüfung im Mail-Eingang für jedes Add-on
  (`GET /api/v1/ingest/mail-policy`, `modus=scan` bei `POST /api/v1/ingest/email`), Zahlen je Ordner; Werkzeuge `mail_quelle_anzeigen` und
  `mail_quelle_einstellen`. Die Ingest-API v1 bleibt kompatibel: die Erweiterung ist rein additiv.
- **Firmen-Eintrag, Stufe 2** (#1080): Tabellen `companies`, `company_aliases`, `company_contacts` (additiv, ohne Versionssprung); die
  Duplikat- und Repost-Erkennung kennt die Einträge (`firmen_kanon`); Kontakte gehören mehreren Firmen mit Rolle und Zeitraum; Dokumente an einer
  Bewerbung stehen auch in der Historie der Firma; Dashboard-Ansicht mit Zeitleiste, Bearbeiten und Vorschlägen; Firmenname als Link in Stellen,
  Bewerbungen und Kontakten; Werkzeuge `firmen_stamm_anzeigen`, `firmen_vorschlaege_anzeigen`, `firmen_stamm_bearbeiten`; `firma_oeffnen` in
  `fit_analyse`, `bewerbung_details` und `kontakt_anzeigen`; `dashboard_link` in `firma_kontext`.
- Wiki: Seiten **Updates**, **Speicher & Downloads**, **Mail-Ordner**, **Firmen**; Abschnitt „Erweiterungen“ in den Einstellungen.
- Gegenprobe (`scripts/mutationstest_auto_update.py`): fünf Kataloge, 229 absichtlich eingebaute Fehler (Auto-Update 93, Speicher 24,
  Komponenten 6, Mail 20, Firmen 86); die Tests erkennen alle bis auf einen begründet gleichwertigen und zwei, die Symlink-Recht brauchen.

### Changed

- `kontakt_verknuepfen(ziel_typ='firma')` ordnet jetzt wirklich einer Firma zu (bisher ein Eintrag ins Leere ohne Leser) und nimmt `von` und `bis`.
- `firma_kontext` liest über die Firmen-Einträge (Schreibweisen, Mutter- und Tochterfirma, jeder Treffer nennt `via`) und liefert die Daten über
  dieselbe Funktion wie die Dashboard-Ansicht.
- Die Warnung bei einer nur in den Notizen genannten Firma beginnt mit „Prüfen:“ (statt „Pruefen:“).
- Ein zweiter Klick auf „Firmen“ (Reiter oder Seitenleiste) führt aus einer geöffneten Firma zurück in die Liste.

### Fixed

- Die Tesseract-Komponente wurde ohne Prüfsumme gestartet (#1152).
- Benutzernamen mit einem Zeichen außerhalb der Windows-Zeichentabelle (ł, ş, ř, griechisch, kyrillisch; Umlaute waren nie betroffen) ließen
  mehrere Schritte scheitern (#1163): die Claude-Konfiguration und die Sicherung vor dem Update im Installer, den Selbsttest des Auto-Updates
  und die Texterkennung (Tesseract liest Pfade in der ANSI-Tabelle). Behoben: die Ausgabe wird als UTF-8 gelesen und abgesichert, das
  Seitenbild geht über die Standardeingabe, die Sprachdaten über den Kurzpfad. Mit Tests; die Praxisprobe auf einem solchen Rechner steht aus.
- Eine Absage an der Bewerbung beim Vermittler fehlte in der Historie des Endkunden (#1080).

### Known Issues

- Die Sprachdaten der Texterkennung (tessdata) werden weiterhin ohne Prüfsumme nachgeladen (#1165).
- Verlorener Schlüssel: Geht der Hauptschlüssel zum Signieren verloren, kann ein mit dem Notfallschlüssel signiertes Update einen neuen eintragen; geht auch der Notfallschlüssel verloren, braucht es eine Installation von Hand.
- Auto-Update nur unter Windows.
- Ein Add-on für den Ordner-Scan fehlt noch (Outlook-Add-In #480 offen).

*Schema v52 (unverändert), 281 MCP-Werkzeuge, NNNN Tests.*

[Pflicht-Block „Wie installiere oder aktualisiere ich PBP?“ mit Version 1.8.0 — Vorlage in CLAUDE.md, Abschnitt „GitHub-Release-Notes“.]
