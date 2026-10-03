# Praxisprobe 1.8.0 — Anleitung für den Test auf einem frischen Windows 11

Beta-Exit-Kriterien 3 und 7 (Master-Plan). Ziel: zeigen, dass auf einem Rechner, auf dem PBP noch nie war, **die Installation, das Auto-Update
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
| 4 | Einstellungen › Erweitert › **Updates** | Stufe „Nur Hinweis“; die Seite nennt ehrlich, dass keine Signaturschlüssel im Programm stehen, falls das noch so ist |
| 5 | Einstellungen › Erweitert › **Speicher & Downloads** | Sieben Orte mit Größen; „Aufräumen“ zeigt erst eine Vorschau und fragt dann |
| 6 | Einstellungen › Erweitert › Quellen im Detail › **Mail-Ordner** | Schalter steht auf „aus“ |
| 7 | **Kontakte › Firmen** | Die Ansicht öffnet sich; eine Firma aus einer Bewerbung lässt sich über die Suche öffnen |

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
