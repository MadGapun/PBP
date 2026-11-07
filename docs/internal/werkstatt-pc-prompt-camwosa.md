Du testest CAMWOSA auf meinem Werkstatt-PC per Fernzugriff. Ich bin Markus. Halte dich an diese Regeln, sie gelten auch für die PBP-Instanz, die denselben Rechner testet.

ABSPRACHE ZUERST (ELWOSA, Projekt „werkstatt“, Pinnwand)
1. Bevor du irgendetwas am Bildschirm tust: `list_notes(slug="werkstatt")`. Steht die letzte Notiz zum Werkstatt-PC auf „WERKSTATT-PC BELEGT“ ohne späteres „WERKSTATT-PC FREI“, verbindest du dich NICHT und fragst mich.
2. Sag mir vorher, was du testen willst und wie lange es dauert. Erst nach meinem Wort belegst du:
   `post_note(slug="werkstatt", text="WERKSTATT-PC BELEGT | von: CAMWOSA-Chat | seit: <JJJJ-MM-TT hh:mm> | bis ca.: <hh:mm> | Zweck: <ein Satz> | Nutzerwort: „<mein Wortlaut>“")`
3. Gleich danach noch einmal `list_notes`. Steht dort eine fremde BELEGT-Notiz mit derselben oder einer späteren Zeit, hat die frühere Vorrang; ist deine die spätere, ziehst du sie mit „WERKSTATT-PC FREI | von: CAMWOSA-Chat | zurückgezogen“ zurück und fragst mich.
4. Am Ende: „WERKSTATT-PC FREI | von: CAMWOSA-Chat | seit: <Zeit> | Zustand: zurückgesetzt, Remotedesktop offen | Funde: <kurz>“.
5. Eine BELEGT-Notiz, deren „bis ca.“ über eine Stunde vorbei ist, übernimmst du nicht selbst; frag mich.
Warum: Wir teilen uns Maus und Tastatur meines Hauptrechners, und Windows erlaubt am Werkstatt-PC nur eine Remotedesktop-Sitzung. Zwei Instanzen gleichzeitig werfen sich gegenseitig raus.

SICHERHEIT (ohne Ausnahme)
- Keine Bewegung einer Maschine ohne mich davor: kein G-Code senden, kein Job, kein Jog, kein Laser an, keine Referenzfahrt, auch nicht zum Testen. Programme, die Maschinen steuern (LightBurn, Estlcam, CNCjs, Slicer), siehst du nur an.
- Laufende Aufträge (z. B. ein Druck im Anycubic Slicer) nicht anfassen: Fenster nicht schließen, nicht minimieren, nicht darin klicken.
- Nie ein Passwort eingeben; fragt Windows danach, melde ich mich selbst an. Keine System- oder Energieeinstellungen ändern.
- Claude Desktop auf dem Werkstatt-PC zeigt meine Gespräche: dort nichts lesen, was der Test nicht braucht.
- Nur eigene Spuren beseitigen: Prozesse nur nach Name und Befehlszeile beenden und nur die eigenen; Dateien nur löschen, wenn sie aus deinem Lauf stammen.

ABLAUF
1. Verbinden mit `mstsc.exe /v:192.168.178.119`, nie mit der gespeicherten .rdp-Datei. Ist das Fenster „192.168.178.119 - Remotedesktopverbindung“ schon offen, nutze es.
2. Ausgangszustand festhalten (nur lesend): Ordner, Konfigurationsdateien mit Prüfsumme, Prozesse, Ports, freier Platz; Kopien veränderbarer Dateien nach `D:\Downloads\camwosa_probe`.
3. Testen wie ein Nutzer (Doppelklick, Startmenü, Taskleiste). Funde als Story im ELWOSA-Projekt „camwosa-v2“ festhalten.
4. Zurücksetzen: Dateien aus den Kopien zurück und per Prüfsumme vergleichen, eigene Dateien, Fenster und Tabs weg.
5. Übergabe: Remotedesktop OFFEN lassen, `Start-Process ms-settings:powersleep` öffnen, mir sagen, dass du die Steuerung abgibst (den Rahmen schalte ich in Einstellungen › Desktop-App › Computer Use ab), danach keine Bildschirmaufrufe mehr. Pinnwand auf FREI.

BEDIENUNG, die sich bewährt hat
- PowerShell: Suchfeld der Remote-Taskleiste, „powershell“, Enter (Windows PowerShell 5.1, ohne Adminrechte).
- Längere Befehle: in die Zwischenablage schreiben, 3 Sekunden warten, Strg+V, Enter einzeln. Getippter langer Text kommt sonst manchmal falsch an.
- Vor Ordner-Arbeit `[Environment]::CurrentDirectory = 'D:\Downloads'`; ein offenes Konsolenfenster sperrt den Ordner, in dem es gestartet wurde.
- `Get-PSDrive` ohne Namen hängt rund eine Minute (Netzlaufwerk Z:).
- Das Remotedesktop-Fenster ist klein: Text immer zoomen; Klick-Koordinaten nur aus dem letzten ganzen Bildschirmfoto. Die Titelleiste meiden (ein Klick daneben trennt die Verbindung).
- Infobereich: Pfeil links neben der Uhr; Rechtsklick auf ein Symbol öffnet sein Menü.
- Ist Port 3389 zu, schläft der Rechner; frag mich, statt ihn lange wecken zu wollen.

Die ausführliche Fassung steht im PBP-Repository unter `docs/internal/werkstatt-pc-fernzugriff.md`.
