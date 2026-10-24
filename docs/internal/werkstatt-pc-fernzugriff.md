# Werkstatt-PC: Testen per Fernzugriff (für alle Claude-Instanzen)

Stand 23.10.2026, aus fünf PBP-Testläufen (05.10. bis 23.10.2026). Gilt für jede Instanz, die den Werkstatt-PC über die
Remotedesktop-Verbindung steuert: PBP (Claude Code), CAMWOSA (Claude-Chat) und künftige.

## 1. Warum es eine Absprache braucht

- **Eine Maus, eine Tastatur.** Jede Instanz steuert per Computer Use den Hauptrechner des Nutzers, auf dem das
  Remotedesktop-Fenster läuft. Zwei Instanzen gleichzeitig klicken sich gegenseitig in die Arbeit, auch wenn eine nur
  Bildschirmfotos macht.
- **Eine Sitzung am Werkstatt-PC.** Windows 11 Pro erlaubt je Benutzer nur eine Remotedesktop-Sitzung. Verbindet sich eine
  zweite, fliegt die erste raus; ein Klick auf das falsche Feld der Titelleiste schließt die Verbindung ebenfalls.
- **Der Werkstatt-PC arbeitet.** Dort laufen Slicer, Laser- und Fräsprogramme, oft mit einem Auftrag an einer echten Maschine.

## 2. Die Absprache über ELWOSA (Pinnwand des Projekts „Werkstatt“, P-GZ3N)

Alle Instanzen schreiben unter demselben Konto. Darum steht in jeder Notiz, **wer** sie schreibt und **wann**.

1. **Vorher lesen:** `list_notes(slug="werkstatt")`. Steht die letzte Notiz zum Werkstatt-PC auf `BELEGT` ohne ein
   späteres `FREI`, wird **nicht** verbunden. Der Nutzer wird gefragt, nicht die andere Instanz übergangen.
2. **Belegen**, erst nach dem Wort des Nutzers:
   `post_note(slug="werkstatt", text="WERKSTATT-PC BELEGT | von: <Instanz> | seit: <JJJJ-MM-TT hh:mm> | bis ca.: <hh:mm> | Zweck: <ein Satz> | Nutzerwort: „<Wortlaut>“")`
3. **Gegenprobe:** gleich danach noch einmal `list_notes`. Steht eine fremde `BELEGT`-Notiz mit derselben Zeit oder jünger
   als die eigene da, zieht die **spätere** zurück (`WERKSTATT-PC FREI | von: <Instanz> | zurückgezogen, weil <Instanz> zuerst`).
4. **Freigeben**, sobald der Rechner zurückgesetzt und die Steuerung abgegeben ist:
   `WERKSTATT-PC FREI | von: <Instanz> | seit: <Zeit> | Zustand: zurückgesetzt, Remotedesktop offen | Funde: <kurz oder „keine“>`
5. **Verwaist:** Eine `BELEGT`-Notiz, deren „bis ca.“ mehr als eine Stunde vorbei ist, wird **nicht** übernommen. Der Nutzer
   entscheidet.
6. Die Pinnwand ist Austausch, keine Arbeit: Funde gehören zusätzlich in das Issue- oder Story-System des eigenen Projekts.

## 3. Sicherheit (hart)

- **Keine Bewegung einer Maschine ohne den Nutzer davor.** Kein G-Code senden, keinen Job starten, kein Jog, kein Laser an,
  keine Referenzfahrt, auch nicht „nur zum Testen“. Ein Programm, das eine Maschine steuert, wird nur angesehen.
- **Laufende Aufträge nicht anfassen:** Fenster von Slicer, Laser- oder Fräsprogrammen nicht schließen, nicht minimieren,
  nicht in ihnen klicken.
- **Nie ein Passwort eingeben.** Fragt Windows beim Verbinden danach, meldet sich der Nutzer selbst an.
- **Keine System- oder Energieeinstellungen ändern;** die Seite dafür öffnen und dem Nutzer sagen, wo er klickt, ist erlaubt.
- **Nur eigene Spuren beseitigen:** Prozesse nur nach Name und Befehlszeile beenden und nur die, die man selbst gestartet hat
  (nie nach Nummern aus einem Bildschirmfoto). Dateien nur löschen, wenn sie aus dem eigenen Lauf stammen (Erstellungszeit prüfen).
- **Daten anderer Programme nicht lesen.** Claude Desktop auf dem Werkstatt-PC zeigt die Gespräche des Nutzers; dort nur
  bedienen, was der Test braucht.

## 4. Ablauf eines Laufs

1. **Ankündigen:** dem Nutzer sagen, was, wie lange, und dass er den Werkstatt-PC so lange nicht anfasst. Erst nach seinem
   Wort weiter (Absprache aus Abschnitt 2).
2. **Verbinden:** `mstsc.exe /v:192.168.178.119` (nie die gespeicherte `.rdp`-Datei). Vorher prüfen, ob schon ein Fenster
   „192.168.178.119 - Remotedesktopverbindung“ offen ist; dann dieses nutzen, keine zweite Verbindung.
3. **Ausgangszustand festhalten** (nur lesend): Ordner, Konfigurationsdateien mit Prüfsumme, laufende Prozesse, belegte Ports,
   freier Platz. Kopien der Dateien, die der Test verändern kann, in einen eigenen Ordner (`D:\Downloads\<projekt>_probe`).
4. **Testen** wie ein Nutzer: Doppelklick, Taskleiste, Startmenü, Symbol im Infobereich.
5. **Zurücksetzen:** veränderte Dateien aus den Kopien zurück (Prüfsumme vergleichen), eigene Dateien, Ordner, Fenster und
   Browser-Tabs weg, Programme, die man beendet hat, wieder starten.
6. **Übergabe:** Remotedesktop **offen lassen**; `Start-Process ms-settings:powersleep` öffnen; dem Nutzer sagen, dass die
   Steuerung abgegeben ist und der Rahmen über Einstellungen › Desktop-App › Computer Use abgeschaltet wird; danach keine
   Computer-Use-Aufrufe mehr. Pinnwand auf `FREI`.

## 5. Bedienung: was sich bewährt hat

- **PowerShell öffnen:** Suchfeld der Remote-Taskleiste anklicken, `powershell` tippen, Enter. Es läuft Windows PowerShell 5.1
  ohne Administratorrechte; prüfen mit `([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')`.
- **Längere Befehle nie tippen lassen:** In die Zwischenablage schreiben, 3 Sekunden warten, im Fenster `Strg+V`, dann Enter
  einzeln. Der Remote-Rechner fügt sonst gelegentlich den alten Inhalt ein. Kurze Texte (unter 15 Zeichen) gehen direkt.
- **PowerShell 5.1:** `Set-Location` ändert nicht das Arbeitsverzeichnis des Prozesses; vorher
  `[Environment]::CurrentDirectory = 'D:\Downloads'`, sonst blockiert das Fenster das Löschen des Ordners. Ein offenes
  Konsolenfenster, das in einem Ordner gestartet wurde, sperrt ihn ebenso, bis es geschlossen ist.
- `Get-PSDrive` hängt rund 60 Sekunden (Netzlaufwerk Z:); `Get-PSDrive -Name C` und `-Name D` gezielt nehmen.
- Gesperrte Dateien (Datenbank, Protokoll) mit `[IO.FileStream]` und Freigabe `ReadWrite` lesen.
- **Infobereich:** Pfeil links neben der Uhr öffnet die versteckten Symbole; Rechtsklick auf ein Symbol, Menü per Zoom lesen.
- **Kleines Fenster:** Das Remotedesktop-Fenster ist auf dem Hauptrechner klein; für Text immer zoomen, für Klicks nur
  Koordinaten aus dem letzten ganzen Bildschirmfoto nehmen. Symbole der Taskleiste rücken nach, wenn ein Fenster verschwindet.
- **Titelleiste des Remotedesktop-Fensters meiden:** Minimieren, Maximieren und Schließen liegen eng beieinander; ein Klick
  daneben trennt die Verbindung (die Sitzung dort läuft weiter, `mstsc.exe /v:…` verbindet wieder).
- **Wecken:** Der Werkstatt-PC wacht auf Magic Packets nicht zuverlässig auf. Ist Port 3389 zu, den Nutzer fragen, statt
  es lange zu versuchen.
