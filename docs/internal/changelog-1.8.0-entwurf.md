# Entwurf: CHANGELOG-Eintrag für 1.8.0

> **Kein Teil des CHANGELOG.** Der Eintrag kommt GANZ OBEN in `CHANGELOG.md`, sobald die Version angehoben wird (`release_check.py`
> verlangt den Kopf auf der aktuellen Version). Zahlen (Tests, Datum) beim Release einsetzen, danach diese Datei löschen.
> Stand des Entwurfs: 02.10.2026, Arbeitszweige `feature/v18-auto-update-1093` → `-speicher-1131` → `-mail-zugang-947` → `-firmen-1080`.

---

## [1.8.0] - TT.MM.2026 — Updates, die sich selbst installieren

<!-- anwender -->
PBP kann sich jetzt selbst aktualisieren — wenn du es willst (Einstellungen › Erweitert › Updates). Ohne deine Wahl installiert PBP nichts.
Neu sind außerdem die Übersicht „Speicher & Downloads“ (dort änderst du auch den Ordner für deine Lebensläufe und Anschreiben), der Firmen-Eintrag und ein Mail-Ordner-Zugang, der standardmäßig aus ist.
Die Wege durch PBP sind kürzer: von der Nachfassung zur Bewerbung, von der Person zur Bewerbung und zurück, von der Stelle zur neuen Bewerbung — je ein Klick. Die Seite „Stellen“ läuft im Leerlauf wieder ruhig.
<!-- /anwender -->

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
  ohne dein Ja, nie bei laufender Arbeit. Was anderen Programmen gehört (Browser der Jobsuche, KI-Modelle), wird nur gezeigt. Die Karte „Deine
  eigenen Ordner“ trägt die Eingabefelder für den Ordner, in den PBP deine Lebensläufe, Anschreiben und Berichte legt, und für den Ordner mit
  deinen Vorlagen — du änderst sie dort, wo du siehst, wie viel darin liegt (#1173). Die anderen Orte sind durch die Installation bedingt und bleiben ohne Eingabe.
- **Mail-Ordner (Einstellungen › Erweitert › Quellen im Detail).** Der Ordner-Scan ist **standardmäßig aus**; gelesen werden nur Ordner, die du
  ausdrücklich freigibst. PBP öffnet nie selbst ein Postfach. Ein Add-on, das Ordner von sich aus liest, gibt es noch nicht — das Thunderbird-Add-on
  schickt weiter nur, was du markierst.
- **Firmen (Kontakte › Firmen).** Alles, was PBP zu einer Firma weiß, als eine Zeitleiste; ein Firmen-Eintrag fasst Schreibweisen zusammen
  („Alt AG“ heißt heute „Neu GmbH“) und kennt die Mutterfirma. Bewerbungen, Stellen und Kontakte behalten ihren Firmennamen als Text.
- **Ein Klick zum Nächsten (#1171).** Die Zeile „Nachfassen“ im Dashboard öffnet die Bewerbung; nach „Bewerbung speichern“ liegt die neue
  Bewerbung offen da (mit „Lebenslauf mit Claude“ und „Anschreiben mit Claude“ im Fuß); in der Timeline führt der Name der Person zu ihrer Karte,
  und die Karte nennt oben „Bewerbung: Titel bei Firma“ und führt zurück; „Zur Stelle“ auf der Bewerbungskarte, „Zur Bewerbung“ in der
  Aufgabenzeile, die Top-Stelle im Dashboard öffnet die Stelle. Die Timeline hat oben eine Sprungleiste (Status · Stelle · Dokumente · Personen ·
  Aufgaben · Termine · Verlauf), die beim Scrollen stehen bleibt. Der Link aus Claude (`#stellen/<Kennung>`) öffnet die Stelle selbst.
- **Neu im Dashboard-Fenster:** Schreibt Claude, während du eine Stelle oder die Timeline einer Bewerbung offen hast (ein Urteil zur Stelle, eine Notiz, ein Termin, eine
  Mail zur Bewerbung), erscheint das dort nach ein bis drei Sekunden; die Leseposition bleibt, nichts flackert.

### Added

- **Auto-Update** (#1093): `services/auto_update/` (feste Quelle, Prüfsumme, Ed25519-Signatur in reinem Python, sicheres Entpacken, Manifest,
  Selbsttest vor dem Umschalten, Stufen, Verlauf), der **Startbaustein** `bewerbungs_assistent_boot` (eingefroren, nur Standardbibliothek,
  Rückfall im selben Prozess und nach zwei unbestätigten Starts), der **Schema-Schutz** (`services/schema_schutz.py`: ist die Datenbank neuer als
  das Programm, schreibt der alte Prozess nicht weiter), der Hinweis, wenn Claude und Dashboard mit verschiedenen Fassungen laufen, der
  Installer-Umbau (Versionsordner, Selbstaufräumen, Deinstaller), `scripts/build_update_archive.py` und ein Schritt im Release-Tor. Werkzeuge
  `update_status`, `update_einstellungen_setzen`, `update_jetzt_installieren`, `update_zurueckschalten`.
- **Speicher & Downloads** (#1131): sieben Orte, sieben Aufräum-Aktionen, Werkzeuge `speicher_anzeigen` und `speicher_bereinigen`. Die Karte
  „Deine eigenen Ordner“ steht immer da und enthält die Eingabefelder für Ausgabe- und Vorlagen-Ordner (#1173; dieselbe Komponente und dieselbe
  Prüfung wie unter Einstellungen › Ordner, die Seite misst nach dem Speichern neu).
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
- Gegenprobe (`scripts/mutationstest_auto_update.py`): sechs Kataloge, 288 absichtlich eingebaute Fehler (Auto-Update 101, Speicher 37,
  Komponenten 6, Mail 20, Firmen 86, Wege 38); die Tests erkennen alle bis auf einen begründet gleichwertigen und zwei, die Symlink-Recht brauchen.
  Im Katalog „Wege“ überlebte beim ersten Lauf ein Fehler (die Marke der Sprungleiste wurde nur direkt nach dem Klick geprüft, nicht nach dem
  Scrollen); der Test wurde gehärtet, danach wird er erkannt.

### Changed

- `kontakt_verknuepfen(ziel_typ='firma')` ordnet jetzt wirklich einer Firma zu (bisher ein Eintrag ins Leere ohne Leser) und nimmt `von` und `bis`.
- `firma_kontext` liest über die Firmen-Einträge (Schreibweisen, Mutter- und Tochterfirma, jeder Treffer nennt `via`) und liefert die Daten über
  dieselbe Funktion wie die Dashboard-Ansicht.
- Die Warnung bei einer nur in den Notizen genannten Firma beginnt mit „Prüfen:“ (statt „Pruefen:“).
- Ein zweiter Klick auf „Firmen“ (Reiter oder Seitenleiste) führt aus einer geöffneten Firma zurück in die Liste.

### Fixed

- Die Tesseract-Komponente wurde ohne Prüfsumme gestartet (#1152).
- **Die Seite „Stellen“ lief im Leerlauf auf Hochtouren** (#1171): sie fragte pausenlos, ob gerade eine Suche läuft — gemessen 270 bis 470 Anfragen
  pro Sekunde und ein zu zwei Dritteln beschäftigter Hauptthread des Browsers, während niemand etwas tat (alle anderen Seiten: 0,0 %). Ursache war
  eine Funktion in der Abhängigkeitsliste des Abfrage-Effekts (`useEffectEvent` ist bei jedem Zeichnen eine neue Funktion; jede Antwort setzt den
  Zustand neu, der Effekt startete sich nach jeder Antwort selbst neu). Die Zeile steht seit März 2026 (v0.23.0) im Code, auch in der Stable-Version
  v1.7.153. Nachher: 0,2 % und 0,6 Anfragen pro Sekunde. Zwei Wächter-Tests halten es fern: einer sieht jede der elf Seiten im Leerlauf an (gesund sind 1 bis 2 Anfragen in drei Sekunden), einer lässt keine neuen
  Effekt-Ereignisse in Abhängigkeitslisten zu (`test_kein_effekt_ereignis_in_einer_abhaengigkeitsliste`); acht ältere Stellen (App, Ablegen von Dokumenten, Einrichtungsassistent) sind als Bestand benannt, bei ihnen wurde nichts Auffälliges gemessen.
- Jede Seite lud beim Start zweimal und blendete dabei kurz die schon gezeichnete Liste aus (ein offenes Fenster ging mit, die Leseposition sprang an
  den Anfang). In „Stellen“ und „Bewerbungen“ erscheint die Ladeanzeige nur noch beim ersten Laden; „Kalender“, „Profil“, „Statistik“ und
  „Einstellungen“ folgen. Der Welle-4-Test `test_g62_karte_eine_kernaussage_und_ein_menue`, der an diesem Flackern scheiterte, ist wieder stabil.
- Was Claude schreibt, kam im offenen Fenster nicht an: das Urteil zu einer Stelle und eine Notiz in der Timeline erschienen erst nach Schließen und Öffnen.
- Benutzernamen mit einem Zeichen außerhalb der Windows-Zeichentabelle (ł, ş, ř, griechisch, kyrillisch; Umlaute waren nie betroffen) ließen
  mehrere Schritte scheitern (#1163): die Claude-Konfiguration und die Sicherung vor dem Update im Installer, den Selbsttest des Auto-Updates
  und die Texterkennung (Tesseract liest Pfade in der ANSI-Tabelle). Behoben: die Ausgabe wird als UTF-8 gelesen und abgesichert, das
  Seitenbild geht über die Standardeingabe, die Sprachdaten über den Kurzpfad. Mit Tests; die Praxisprobe auf einem solchen Rechner steht aus.
- Eine Absage an der Bewerbung beim Vermittler fehlte in der Historie des Endkunden (#1080).
- **Aus der Praxisprobe auf einem frischen Windows 11 (05.10.2026):**
  - Der Reiter „Erweiterungen“ stürzte auf jedem Rechner ab, auf dem die Texterkennung noch fehlt (ein Variablenname war beim
    Umlaut-Austausch an einer Stelle geändert worden). Ein Absturz in einem Reiter der Einstellungen lässt die anderen Reiter jetzt in Ruhe.
  - Der Knopf „Deinstaller starten“ (Einstellungen › Gefahrenzone) öffnete unter Windows nie ein Fenster, sondern meldete „Kein Terminal
    gefunden“ — die Flags des Prozessstarts schließen sich aus. Behoben, mit einem Test, der das Betriebssystem wirklich fragt.
  - Der Deinstaller räumt jetzt auch die Konfiguration von Claude aus dem Microsoft Store auf (der Eintrag blieb stehen, Claude meldete danach
    bei jedem Start einen Server ohne Programm) und schließt das Dashboard-Fenster.
  - Der Deinstaller ließ unter Windows rund 830 MB liegen, die der Installer außerhalb von PBP geladen hat: den Browser für Quellen (Playwright, `%LOCALAPPDATA%\ms-playwright`,
    rund 700 MB) und den Zwischenspeicher von pip (rund 125 MB) — ohne es zu erwähnen (macOS und Linux fragen). Er fragt jetzt zum Schluss, mit Ort und Größe;
    die Vorgabe ist **Behalten**, und nur ein einzelnes „j“ löscht. Der Browser-Ordner geht ganz, von pip nur der Unterordner `Cache` (die Einstellungsdatei
    eines anderen Programms bleibt). Dieselben Ordner nutzen andere Programme mit, deshalb im Zweifel behalten.
  - Die Fehlermarke `[!!]` erschien in Installer und Deinstaller als `[]`: unter `EnableDelayedExpansion` verschluckt `cmd` das Paar `!!`. Betroffen waren zehn
    Meldungen („… konnte nicht entfernt werden“, „Datei in Benutzung?“ u. a.); wer einen Fehler hatte, sah nur leere Klammern vor dem Text. Maskiert; ein Test
    verbietet die ungeschützte Schreibweise.
  - Der Deinstaller ließ nach dem Start über den Knopf einen leeren Ordner `%LOCALAPPDATA%\BewerbungsAssistent\app` liegen (Schritt [5/7] meldete „konnte nicht
    entfernt werden“): das neue Fenster hatte diesen Ordner als Arbeitsordner, und ein Prozess hält seinen Arbeitsordner fest. Gefunden bei der
    Gegenprobe der Reparaturen auf demselben Rechner; das Fenster öffnet jetzt im Temp-Ordner, und die Datei verlässt den Ordner, bevor sie sich verschiebt.
  - Weitere Funde derselben Gegenprobe, behoben:
    - Die verschobene Kopie des Deinstallers (`PBP-Deinstaller-<Zahl>.bat`, rund 15 KB) blieb in `%TEMP%` liegen; sie räumt sich jetzt selbst weg.
    - Der Deinstaller schrieb die Konfiguration von Claude in der Formatierung von Windows PowerShell neu (rund siebenmal so groß) und ließ
      `"mcpServers": {}` stehen. Jetzt nimmt er nur den PBP-Eintrag aus dem Text, der Rest bleibt Byte für Byte; das Ergebnis wird geprüft,
      und wo der Text-Weg nicht passt, gilt der bisherige.
    - Das Dashboard-Fenster zeigt nur noch Warnungen und Fehler (die Log-Datei bekommt weiter alles; `BA_CONSOLE_LEVEL=INFO` zeigt alles). Vorher
      schoben sich Protokollzeilen in die Frage „Claude jetzt neu starten?“ und füllten den ersten Start mit Dutzenden Zeilen.
    - Der Browser öffnet sich erst, wenn das Dashboard antwortet (auf einem frischen Rechner zeigte Chrome „Verbindung verweigert“), und nur einmal:
      der Installer unterdrückt das Öffnen im von ihm gestarteten Fenster und öffnet selbst, nach seiner Prüfung.
    - Am Ende jeder gelungenen Installation stand „Die Syntax für den Dateinamen, Verzeichnisnamen oder die Datenträgerbezeichnung ist falsch.“, und die
      Einstellung zum Aufräumen des Installationsordners (nie, fragen, immer) wurde nie gelesen. `cmd` schneidet bei einem Befehl in `for /f` mit mehr als
      zwei Anführungszeichen das erste und das letzte ab; ein zusätzliches Paar um den ganzen Befehl behebt das.
  - Das Dashboard startete nicht, solange die Frage „Claude jetzt neu starten?“ unbeantwortet blieb; der Installer wartete umsonst und öffnete
    „Verbindung verweigert“. Die Frage kommt jetzt erst, wenn das Dashboard läuft.
  - Der Installer startet Claude aus dem Store am Ende (statt „nicht gefunden“); die Ausgabe enthält keine Sonderzeichen mehr, die die
    Konsole verstümmelt.
  - Auf den Karten der Erweiterungen und Quellen standen Kennungen aus der Planung („…(E19)“); entfernt.
  - Das Titelbild des Wikis zeigte seit v1.7.137 eine Fehlerkarte („Dieser Bereich ist abgestürzt“); der Screenshot-Generator prüft jetzt
    jede Aufnahme.
- **Die Ordner für Lebensläufe, Anschreiben und Vorlagen: drei Fehler, alle seit v1.7.59** (#1173). (1) Die Karte „Deine eigenen Ordner“ und der
  Hinweis beim Löschen („bleibt liegen“) nannten den Ordner des Nutzers nie: gespeichert wird je Profil, gelesen wurde ohne Profil, die Liste war
  immer leer — ein Test blieb dabei grün, weil er die Einstellung auf dem anderen Weg schrieb. (2) „Zurücksetzen“ (das Feld leeren) endete im
  Dashboard mit „HTTP 400“, nur das Werkzeug für Claude kannte den Platzhalter „-“; die Regel steht jetzt an einer Stelle (`ablage.ordner_setzen`).
  (3) Bei einem ungültigen Pfad stand am Feld ebenfalls nur „HTTP 400“ statt der Begründung („Diesen Ordner gibt es nicht …“); die Antwort nennt den
  Grund jetzt als `error`, und die Oberfläche liest ihn. Eingebettet steht der Satz zum verschwundenen Ordner nur noch einmal da.

### Known Issues

- Die Sprachdaten der Texterkennung (tessdata) werden weiterhin ohne Prüfsumme nachgeladen (#1165).
- Verlorener Schlüssel: Geht der Hauptschlüssel zum Signieren verloren, kann ein mit dem Notfallschlüssel signiertes Update einen neuen eintragen; geht auch der Notfallschlüssel verloren, braucht es eine Installation von Hand.
- Auto-Update nur unter Windows.
- Ein Add-on für den Ordner-Scan fehlt noch (Outlook-Add-In #480 offen).

*Schema v52 (unverändert), 281 MCP-Werkzeuge, NNNN Tests.*

[Pflicht-Block „Wie installiere oder aktualisiere ich PBP?“ mit Version 1.8.0 — Vorlage in CLAUDE.md, Abschnitt „GitHub-Release-Notes“.]
