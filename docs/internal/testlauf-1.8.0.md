# Testlauf 1.8.0 (Release-Kandidat) auf dem Werkstatt-PC

Stand 11.10.2026, Plan I27 im Master-Plan. Der Plan ist fertig; **ausgeführt wird erst, wenn der Nutzer das Signal gibt**. Er löst die
Praxisprobe (`praxisprobe-1.8.0.md`) ab: dort stehen die Protokolle der ersten drei Durchläufe (05./06.10.2026), hier der letzte, vollständige.

## Was der Lauf belegen soll

| Beta-Exit-Punkt | Frage | Block |
|---|---|---|
| 3 | Zusatzprogramm (Texterkennung) installiert, liest ein Scan-PDF, wird mit PBP wieder entfernt — auf einem frischen Windows 11, ohne Administratorrechte | D, G |
| 4 | Von der letzten stabilen Version (1.7.156, Schema 48) auf den Kandidaten (Schema 52): Daten bleiben, Sicherung entsteht | F |
| 5 | Ein Mensch ohne Vorwissen kommt vom ersten Start bis zum Profil, ohne in eine Sackgasse zu laufen | C |
| 7 | Auto-Update gegen echte GitHub-Infrastruktur: laden, Prüfsumme, Signatur, entpacken, Selbsttest, umschalten, Rückfall | E |
| — | Reste der Praxisprobe: PP10 (Frage nach den rund 830 MB mit echtem Playwright), PP20, PP21, PP23 | B, G |

## Was du vorher tust (rund 10 Minuten)

1. Der Werkstatt-PC läuft, ist an dein Windows-Konto angemeldet (kein Sperrbildschirm) und geht **nicht** in den Ruhezustand
   (Einstellungen › System › Netzbetrieb und Akku › „Nie“ — das änderst nur du).
2. Claude Desktop (Microsoft-Store-Fassung) ist installiert und einmal gestartet. **PBP ist nicht installiert** (sonst vorher den Deinstaller laufen
   lassen); Port 8200 ist frei.
3. Auf deinem Rechner ist die Remotedesktop-Verbindung zum Werkstatt-PC offen (`mstsc /v:192.168.178.119`). Du meldest dich dort selbst an; ich gebe
   nie ein Passwort ein. Das Fenster bleibt offen, ich steuere nur darin.
4. Mindestens 3 GB frei auf dem Laufwerk des Benutzerprofils.
5. Während des Laufs fasst du den Werkstatt-PC nicht an (rund drei Stunden, in zwei Teilen möglich: B bis E, dann F bis H).
6. **Nur für E2** (Auto-Update gegen echtes GitHub): ein leeres öffentliches Repository `MadGapun/PBP-update-probe` darf entstehen (siehe unten). Ohne
   es läuft E1; E2 bis E4 bleiben dann für nach der Veröffentlichung.

## Was ich auf dem Rechner tue — und was du siehst

Alle Daten sind erfunden („Erika Beispiel“). Es werden keine echten Konten, Passwörter oder Systemeinstellungen berührt; deine eigenen Browser-Tabs
bleiben unangetastet. Ein kleines Skript (`docs/internal/testlauf/pbp_probe.ps1`, nur ASCII) hält Ausgangszustand, Zwischenstände und Endzustand
fest; Prüfsummen der Claude-Konfiguration vorher und nachher.

### A — Ausgangszustand (5 Minuten, nur lesend)
Ordner, Registry, Verknüpfung, Konfiguration von Claude (Prüfsumme), Prozesse, Port, freier Platz. Erwartet: kein PBP, nichts unter
`%LOCALAPPDATA%\BewerbungsAssistent`, `ms-playwright` und `pip`-Ordner nur, wenn andere Programme sie angelegt haben.

### B — Frische Installation des Kandidaten (15 Minuten)
ZIP des Release-Zweigs laden, entpacken, `INSTALLIEREN.bat` doppelklicken. Erwartet:
- das Fenster endet grün; **ein** neuer Browser-Tab, ruhiges Dashboard-Fenster (PP14, PP15),
- am Ende **kein** leerer Ordner des Installers (PP20) und **kein** Fenster „Dashboard ist mit Fehlercode -1 beendet“ (PP21),
- im Temp-Ordner keine Reste von Selbsttest und Helfer (PP23),
- Verknüpfung auf dem Desktop; Claude-Konfiguration trägt den Eintrag, fremde Server unverändert; der Server antwortet, wie Claude ihn startet
  (`initialize`, `tools/list`),
- Version `1.8.0-rc.1` unter Einstellungen › Erweitert › Updates.

### C — Erstkontakt (15 Minuten, der eigentliche Prüfstein für Punkt 5)
Auf der leeren Installation, mit Bildschirmfotos:
- Dashboard: der eine Hauptweg „Lebenslauf hochladen“; Stellen, Bewerbungen und Suche & Bewertung zeigen **eine** Karte mit **einem** Knopf (U5, U6),
- Klick → „Dein Profil anlegen“ / „Dein Name“ / „Weiter zum Lebenslauf“ (U7); danach der Willkommens-Assistent mit dem Upload,
- Aufgaben und Statistiken erklären sich (U8); Gefahrenzone zählt 0 Datensätze und nennt die mitgelieferten Vorgaben (U9),
- Hilfe-Fenster (Updates, Speicher & Downloads, Mail-Ordner, Firmen, Erweiterungen),
- Kontakte › Firmen, Speicher & Downloads, Mail-Ordner (Schalter „aus“, Liste leer).
- Beim ersten Öffnen und nach jedem Neuladen (Strg+F5) steht auf Stellen, Bewerbungen und Suche kurz „… werden geladen“, nie „Zuerst dein Profil“, wenn ein
  Profil da ist (Fund des zweiten Prüfers, 11.10.2026; der Browser-Test verzögert dafür die Statusabfrage um 1,8 Sekunden).

### D — Texterkennung (10 Minuten; lädt rund 55 MB und die Sprachdaten)
Einstellungen › Erweitert › Erweiterungen › Texterkennung: Größe und Lizenz stehen vor dem Klick da; „Herunterladen & installieren“; Prüfsumme wird
verlangt, Fortschritt, „installiert“ (ohne Administratorrechte). Danach ein **eingescanntes** PDF (fiktives Arbeitszeugnis, eine Seite, nur Bild) bei
Dokumente hochladen: der Text wird erkannt und trägt den Vermerk der Texterkennung. Speicher & Downloads nennt die Komponente mit Größe.

### E — Auto-Update (30 bis 50 Minuten)
- **E1** (ohne Probe-Repository): Updates-Seite — vier Stufen, Vorgabe „Nur Hinweis“, Sicherheitsabsatz mit Prüfsumme und Signatur, „Jetzt prüfen“
  sagt ehrlich „aktuell“ (die 1.7-Linie wird nicht angeboten), Stufe wechseln und zurück.
- **E2** (mit Probe-Repository): in der installierten Kopie wird **eine Zeile** geändert — die Konstante `REPO` in
  `services/auto_update/quelle.py` zeigt auf das Probe-Repository; alles andere ist der ausgelieferte Code. Dort liegt ein Release `v1.8.0`: das
  Archiv des Kandidaten mit der Versionsnummer 1.8.0, **mit dem echten Schlüssel signiert**, dazu `SHA256SUMS` und `SHA256SUMS.sig`. „Jetzt prüfen“
  → „Neue Version 1.8.0“; Stufe „Mit einem Klick“ → Fortschritt (Prüfen, Laden, Entpacken, Test, Umschalten) → „Neustart nötig“ → PBP und Claude
  komplett beenden, neu starten → es läuft 1.8.0, Daten unverändert, Verlauf nennt Prüfsumme und Signatur.
- **E3** Rückfall: in `versions\1.8.0\...\dashboard.py` wird eine Zeile eingefügt, die einen Fehler wirft; Neustart → PBP schaltet von selbst auf
  `1.8.0-rc.1` zurück und sagt es; die defekte Fassung wird nicht noch einmal angeboten.
- **E4** (optional, wenn Zeit): ein Release mit falscher Prüfsumme und eines mit fremder Signatur — beide müssen abgelehnt werden, nichts bleibt liegen.

### F — Von Stable 1.7.156 auf den Kandidaten (30 Minuten)
Stable-ZIP laden, installieren, über die Schnittstelle erfundene Daten anlegen (Profil, 6 Bewerbungen, 7 Kontakte, 2 Aufgaben), Abdruck merken; dann
den Kandidaten **darüber** installieren. Erwartet: Daten gleich (Abdruck), Schema 48 → 52, Sicherung vor dem Update und vor der Migration gültig,
Versionsordner `versions\1.8.0-rc.1`, Claude-Konfiguration auf den Startbaustein, kein altes `src`.

### G — Deinstallation (15 Minuten)
Knopf „Deinstaller starten“ (Einstellungen › Gefahrenzone): sieben Schritte; die Frage nach den rund 830 MB (PP10) mit **echtem** Playwright und
pip-Zwischenspeicher, Vorgabe „Behalten“, ein einzelnes „j“ löscht; Texterkennung (`components`) geht mit; Bewerbungsdaten erst nach Eingabe von
`LOESCHEN`; kein Rest-Fenster, keine Kopie des Deinstallers in `%TEMP%`.

### H — Zurücksetzen und Übergabe
Konfiguration von Claude **Byte für Byte** gegen die Prüfsumme von Block A; alle Hilfsdateien, ZIPs, entpackten Ordner, Temp-Reste weg; von mir
geöffnete Tabs und Fenster zu. Die Remotedesktop-Verbindung bleibt **offen**, die Seite `ms-settings:powersleep` ist geöffnet (du stellst den
Ruhezustand selbst ab). Danach gebe ich die Steuerung ab.

## Was geladen wird (damit nichts überrascht)

| Datei | Woher | Größe (ungefähr) | Block |
|---|---|---|---|
| ZIP des Release-Kandidaten | github.com/MadGapun/PBP (Zweig `release/v1.8.0-rc`) | 15 MB | B |
| Python-Laufzeit, Pakete, Chromium für die Quellen | vom Installer (python.org, PyPI, Playwright) | 700 MB bis 1 GB | B, F |
| Texterkennung (Tesseract-Setup) und Sprachdaten | GitHub (UB Mannheim) und tessdata_fast | 55 MB + wenige MB | D |
| ZIP von Stable v1.7.156 | github.com/MadGapun/PBP (Tag) | 12 MB | F |
| Probe-Release (Archiv, Prüfsummen, Signatur) | github.com/MadGapun/PBP-update-probe | 3 MB | E2 |
| fiktives Scan-PDF | von diesem Rechner (Remotesitzung, Zwischenablage oder Freigabe) | < 1 MB | D |

## Das Probe-Repository (nur Block E2)

PBP lädt Updates nur von einer festen GitHub-Adresse und nur stabile Versionen. Bis 1.8.0 selbst veröffentlicht ist, gibt es dort kein Paket, das ein
Update sein könnte. Für den Beweis gegen echte Infrastruktur (Programmierschnittstelle, Weiterleitung auf die Datei-Server von GitHub, Download,
Prüfsumme, Signatur) braucht es also eine **zweite** Adresse mit einer stabilen Veröffentlichung. Das Repository enthält keinen Code, nur die drei
Dateien einer Veröffentlichung, und kann nach dem Lauf gelöscht werden. Die Konstante wird nur in der Kopie auf dem Werkstatt-PC geändert; im
ausgelieferten Code bleibt die feste Quelle.

Der Schlüssel zum Signieren verlässt diesen Rechner nie; signiert wird hier, hochgeladen werden nur Archiv, Summenliste und Signatur.

## Ergebnis

Je Block ein Satz („in Ordnung“ oder Abweichung mit Bildschirmfoto) im Issue #1170 und im PR des Kandidaten; Funde werden wie PP1 bis PP23 nummeriert
(PP24 ff.). Ein Befund, der ein Ergebnis ändert, hält die Veröffentlichung an.

## Stand nach dem Lauf (11.10.2026)

Gelaufen. Ergebnis je Block und die Funde PP24 bis PP28 stehen in `praxisprobe-1.8.0.md` (Abschnitt „Testlauf des Release-Kandidaten“), im Issue #1170 und im
PR des Kandidaten. Beta-Exit-Punkte 4, 5 und 7 sind belegt, Punkt 3 war offen (PP26) und ist in `1.8.0-rc.2` behoben; der Beleg mit dem echten Setup ist ein
zweiter, kurzer Lauf (Blöcke B, D, G, H; rund eine Stunde; vorher ankündigen).
