# Praxisprobe 1.8.0 — Anleitung für den Test auf einem frischen Windows 11

Beta-Exit-Kriterien 3 (Zusatzprogramme und Deinstallation) und 7 (Auto-Update) im Master-Plan. Ziel: zeigen, dass auf einem Rechner, auf dem PBP noch nie war, **die Installation, das Auto-Update
und der Rückfall** so funktionieren, wie es im Wiki steht. Das kann nur ein Mensch an einem echten Rechner (oder in einer frischen virtuellen
Maschine) prüfen; die automatischen Tests stellen alles mit Attrappen nach.

## Vorbereitung

- Ein Windows-11-Rechner oder eine frische virtuelle Maschine **ohne** Python, Git und PBP. [Claude Desktop](https://claude.ai/download) ist installiert
  und einmal gestartet.
- Nicht auf dem Arbeitsrechner mit den echten Daten. Wer es dort trotzdem tut: vorher eine Sicherung anlegen (Einstellungen › Export & Backup).
- **Bonus:** ein Benutzerkonto, dessen Name ein Sonderzeichen enthält (zum Beispiel `ł` oder `ş`) — das prüft #1163 zugleich.

## Ablauf

| # | Schritt | Erwartet |
|---|---|---|
| 1 | ZIP von 1.8.0 laden, entpacken, `INSTALLIEREN.bat` doppelklicken | Das Fenster endet grün, ohne gelbe Zeilen außer „Claude Desktop … neu starten“; eine Verknüpfung „PBP Bewerbungs-Portal“ liegt auf dem Desktop |
| 2 | Claude Desktop komplett beenden und neu starten, tippen: „Starte die Ersterfassung“ | Claude kennt PBP und meldet sich mit dem nächsten Schritt |
| 3 | Verknüpfung doppelklicken | Das Dashboard öffnet sich; die Version 1.8.0 steht unter Einstellungen › Erweitert › Updates |
| 4 | Einstellungen › Erweitert › **Updates** | Stufe „Nur Hinweis“; unter den Stufen steht, dass jede Datei auf ihre Prüfsumme **und auf die Signatur des Entwicklers** geprüft wird |
| 5 | Einstellungen › Erweitert › **Speicher & Downloads** | Sieben Orte mit Größen; „Aufräumen“ zeigt erst eine Vorschau und fragt dann |
| 6 | Einstellungen › Erweitert › Quellen im Detail › **Mail-Ordner** | Schalter steht auf „aus“ |
| 7 | **Kontakte › Firmen** | Die Ansicht öffnet sich; eine Firma aus einer Bewerbung lässt sich über die Suche öffnen |

## Zusatzprogramme und Deinstallation (Beta-Exit 3)

| # | Schritt | Erwartet |
|---|---|---|
| 7a | Einstellungen › Erweitert › **Erweiterungen**: bei der Texterkennung auf *Herunterladen & installieren* klicken | Vorher steht Größe (rund 55 MB) und Lizenz da; geladen wird erst nach dem Klick; danach steht die Komponente als installiert da (ohne Administratorrechte) |
| 7b | Ein **gescanntes** PDF (nur Bild, kein Text) bei Dokumente hochladen | PBP erkennt den Text und vermerkt im Text, dass er per Texterkennung entstand |
| 7c | Einstellungen › Erweitert › **Speicher & Downloads** | Die Komponente steht unter „Zusatzprogramme von PBP“ mit ihrer Größe |
| 7d | PBP deinstallieren (Windows-Einstellungen › Apps, oder `DEINSTALLIEREN.bat`) | Der Ordner `%LOCALAPPDATA%\BewerbungsAssistent\components` ist danach weg; gefragt wird, ob auch alle Bewerbungsdaten gelöscht werden sollen |

## Auto-Update (der eigentliche Beweis)

Dazu braucht es **eine zweite, später veröffentlichte Version** (zum Beispiel 1.8.1), denn ein Update gibt es erst, wenn die neuere Version samt
`pbp-update-X.Y.Z.zip` und `SHA256SUMS` an der Veröffentlichung hängt. Die Entwicklerseite veröffentlicht sie; auf dem Probe-Rechner dann:

| # | Schritt | Erwartet |
|---|---|---|
| 8 | Stufe auf „Mit einem Klick“ stellen | Mit „Jetzt prüfen“ (sonst nach spätestens sechs Stunden) erscheint oben der Hinweis auf die neue Version |
| 9 | Auf den Hinweis klicken | Fortschritt (Prüfen, Laden, Entpacken, Test, Umschalten), danach „Neustart nötig“ |
| 10 | PBP und Claude Desktop komplett beenden, neu starten | Die neue Version steht unter Updates (bis zum Neustart zeigt die Seitenleiste „läuft vX · installiert vY“); Daten sind unverändert |
| 11 | Einstellungen › Updates › Verlauf | Ein Eintrag mit Version, Ergebnis und Prüfsumme |

## Rückfall (nur lokal herbeiführen — nie über eine echte Veröffentlichung)

Eine absichtlich kaputte Version darf **nie** veröffentlicht werden: jede Installation mit Auto-Update würde sie angeboten bekommen. Stattdessen macht
die Entwicklerseite auf dem Probe-Rechner nach einem gelungenen Update eine Datei der **neuen** Version unbrauchbar (in
`versions\<neue Version>\src\bewerbungs_assistent\dashboard.py` eine Zeile ergänzen, die einen Fehler wirft) und startet PBP neu. Erwartet: PBP schaltet
**von selbst auf die vorige Version** zurück, sagt es („… ließ sich nicht starten – PBP läuft wieder mit Version …“), und bietet die defekte Version nicht
noch einmal an. Genau diesen Ablauf prüfen auch die automatischen Tests (`tests/test_v18_auto_update_e2e.py`), aber mit Attrappen statt auf einem echten Rechner.

## Was melden

Alles, was von der Spalte „Erwartet“ abweicht — mit Bildschirmfoto und dem Satz, an welchem Schritt es war. Am einfachsten Claude sagen: „Problem melden“.
Die Protokolle liegen unter `%LOCALAPPDATA%\BewerbungsAssistent\data\logs\` (und das Installer-Protokoll im entpackten Ordner).

## Protokoll der ersten Probe (05.10.2026)

Rechner: Windows 11 Pro, Claude Desktop aus dem Microsoft Store (lief ohne Fenster), Benutzername ohne Sonderzeichen. Stand: Zweig
`feature/v18-firmen-1080` (beta.15), danach ein zweiter Durchlauf mit den Reparaturen. Bedient per Remote-Desktop; danach wurde der Rechner
auf den Ausgangszustand zurückgesetzt (Konfiguration von Claude per Prüfsumme gegen die Sicherung verglichen).

| Schritt | Ergebnis |
|---|---|
| 1 Installation | Gelungen (rund 4 Minuten). Funde: **PP2** (Hinweis „Claude über das Tray-Symbol beenden“ ließ sich nicht befolgen, Claude lief ohne Fenster und ohne Symbol), **PP3** („Claude Desktop nicht gefunden“ am Ende, obwohl installiert), **PP4** (Windows-Sicherheitswarnung „Herausgeber nicht verifiziert“ steht nicht in der Anleitung) |
| 2 Dashboard starten | **PP1**: solange „Claude jetzt neu starten?“ unbeantwortet blieb, lief kein Server; der Installer öffnete nach 60 s „Verbindung verweigert“ |
| 3–5 Updates, Speicher & Downloads | in Ordnung |
| 6 Mail-Ordner | in Ordnung (Schalter „aus“, Liste leer) |
| 7 Kontakte › Firmen | in Ordnung (leerer Zustand erklärt, was ein Firmen-Eintrag ist) |
| Hilfe (U1) | in Ordnung (Updates, Speicher, Mail-Ordner, Erweiterungen, Datensicherung) |
| 7a Erweiterungen | **PP6**: Absturz „läuft is not defined“; nach der Reparatur: „Nicht installiert“ mit Knopf. Das Herunterladen der Texterkennung (55 MB) wurde **nicht** ausgeführt |
| 7b, 7c | nicht geprüft (setzen 7a voraus) |
| Drüberinstallieren (Update derselben Version) | in Ordnung: Daten blieben erhalten, vorher entstand eine Sicherung der Datenbank |
| 7d Deinstallation | **PP9** (Knopf öffnet nichts), **PP11** (Store-Konfiguration blieb), **PP12** (Fenster blieb), **PP10** (rund 830 MB Playwright und pip-Cache blieben liegen) |
| Auto-Update 8–11, Rückfall | nicht geprüft (braucht eine zweite veröffentlichte Version) |

Beim Nachsehen aufgefallen: **PP7** (das Titelbild des Wikis zeigte eine Fehlerkarte) und **PP8** (Plan-Kennungen in Karten). Alle bis auf PP2, PP4
und PP10 sind im Zweig repariert, mit Tests und Gegenprobe; Einzelheiten und Ursachen stehen in den Lehren L46 bis L50 (`lehren.md`).

## Gegenprobe der Reparaturen (05.10.2026, Hotfix 1.7.153)

Derselbe Rechner, zweimal vollständig: Installer, Dashboard, Frage zum Neustart von Claude, Knopf „Deinstaller starten“, Deinstallation,
Aufräumen. Stand: Zweig `hotfix/v1.7.153` (Stable-Linie, dieselben Commits wie im 1.8-Zweig).

| Prüfpunkt | Ergebnis |
|---|---|
| PP3 Installer startet Claude aus dem Store | in Ordnung („[OK] Claude Desktop wurde gestartet“) |
| PP1 Dashboard läuft, solange die Frage offen ist | in Ordnung; mit „n“ beantwortet: „Claude bleibt offen. Das Dashboard läuft trotzdem.“ |
| PP9 Knopf öffnet das Fenster | in Ordnung (Fenster mit den sieben Schritten) |
| PP11 Konfiguration aus dem Store | in Ordnung: Eintrag entfernt, Sicherung `.pbp-backup` angelegt |
| PP12 Dashboard-Fenster | in Ordnung: nach der Deinstallation läuft kein PBP-Prozess und kein `cmd`-Fenster mehr |
| **PP13** App-Ordner nach dem Start über den Knopf | **Fund im ersten Durchlauf:** „[!!] App-Verzeichnis … konnte nicht entfernt werden“, ein leerer Ordner blieb liegen. Ursache und Reparatur in den Lehren (L51); im zweiten Durchlauf „[OK] App-Verzeichnis … entfernt“, kein Ordner übrig |

Beim zweiten Durchlauf aufgefallen (kleine Dinge) und danach im 1.8-Zweig behoben, jeweils mit Tests und Gegenprobe (PP14 bis PP17):

- Die Frage „Claude jetzt neu starten?“ läuft im Hintergrund; Protokollzeilen des Servers können sich in dieselbe Zeile schieben.
- Der Installer öffnet das Dashboard in Chrome (sobald das Fenster steht) und danach im Standardbrowser; Chrome kann dabei ein paar Sekunden vor
  dem Server fertig sein und „Verbindung verweigert“ zeigen, bis man neu lädt.
- Die verschobene Kopie des Deinstallers (`%TEMP%` + `PBP-Deinstaller-<Zahl>.bat`) bleibt liegen: die Ursprungsdatei ist zu dem Zeitpunkt gelöscht,
  und `cmd` bricht dann vor dem `del` still ab (rund 15 KB je Deinstallation).
- Die Konfigurationsdatei von Claude wird vom Deinstaller in der Formatierung von Windows PowerShell neu geschrieben (mehr Leerraum, Inhalt
  gleich) und behält `"mcpServers": {}`.
- Behoben: PP14 (Console ruhig), PP15 (Browser erst bei Antwort, nur ein Tab), PP16 (Kopie räumt sich selbst weg), PP17 (nur der Eintrag verschwindet).
- Unverändert offen: PP2, PP4 (Wiki), PP10 (rund 830 MB Browser und pip-Zwischenspeicher bleiben liegen).

Danach war der Rechner wieder wie vorher: Ordner, Registry, Verknüpfung, Browser-Dateien, Zwischenspeicher, Downloads, Temp-Reste und die von mir
geöffneten Browser-Tabs sind weg; die Konfiguration von Claude hat keinen PBP-Eintrag mehr (die Einstellungen, die Claude selbst inzwischen
dazugeschrieben hat, blieben unberührt, der leere Eintrag `mcpServers` wurde entfernt).

## Dritter Durchlauf (05.10.2026, 1.8-Zweig, Kopf `eba13474`)

Derselbe Rechner, noch einmal vollständig (Installer bis Deinstaller-Knopf bis Aufräumen), diesmal mit dem Stand der Reparaturen PP14 bis PP17.

| Prüfpunkt | Ergebnis |
|---|---|
| PP15 Browser | in Ordnung: genau EIN neuer Tab (Standardbrowser), zu dem Zeitpunkt, an dem das Dashboard antwortet, mit geladener Seite; kein Chrome-Prozess entstand |
| PP14 Dashboard-Fenster | in Ordnung: Banner, Frage „Claude jetzt neu starten?“ in einer eigenen Zeile, keine Protokollzeilen; nach „n“ die Meldung „Claude bleibt offen“ |
| PP16 Kopie in `%TEMP%` | in Ordnung: nach der Deinstallation 0 Dateien `PBP-Deinstaller-*` |
| PP17 Konfiguration von Claude | in Ordnung: 3810 → 3393 Byte, die Sicherung ist die Datei von vorher, im Zeilenvergleich fehlen nur die Zeilen des Eintrags (und `"mcpServers": {` wurde zu `"mcpServers": {}`) |
| PP13 App-Ordner | weiter in Ordnung: kein Ordner `BewerbungsAssistent` übrig |
| **PP18** (neu) | **Fund:** am Ende der Installation erschien „Die Syntax für den Dateinamen, Verzeichnisnamen oder die Datenträgerbezeichnung ist falsch.“, danach die Frage zum Aufräumen des Installationsordners. Ursache und Reparatur in der Lehre L53 |

Danach war der Rechner wieder wie vorher: Ordner, Registry, Verknüpfung, Browser-Dateien, Zwischenspeicher, Downloads, Temp-Reste und die von mir geöffneten
Tabs sind weg; die Konfiguration von Claude ist Byte für Byte (Prüfsumme) die Datei von vor dem Durchlauf.
