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
PR des Kandidaten. Beta-Exit-Punkte 4, 5 und 7 sind belegt, Punkt 3 war offen (PP26) und ist in `1.8.0-rc.2` behoben; der Beleg mit dem echten Setup kam im
zweiten, kurzen Lauf (Blöcke B, D, G, H; rund eine Stunde; vorher angekündigt).

**Zweiter Lauf (11.10.2026, spät abends):** gelaufen, alle vier Blöcke in Ordnung (Ergebnis in `praxisprobe-1.8.0.md`, Abschnitt „Zweiter Lauf des Kandidaten
`1.8.0-rc.2`“). PP24, PP25 und PP26 sind mit dem echten Setup belegt, ohne dass irgendwo eine Abfrage nach Administratorrechten kam; neu ist nur PP29 (kosmetisch,
nicht geändert). Beta-Exit-Punkte 3, 4, 5 und 7 sind belegt; offen ist das Wort des Nutzers (Punkt 6).

## Zweiter Lauf (nach `1.8.0-rc.2`): nur das, was sich geändert hat

Blöcke B, D, G, H; rund eine Stunde; der Werkstatt-PC steht nach dem ersten Lauf im Ausgangszustand (Claude-Konfiguration byte-gleich). Das Probe-Skript wird neu
geladen (`iwr https://raw.githubusercontent.com/MadGapun/PBP/release/v1.8.0-rc/docs/internal/testlauf/pbp_probe.ps1`). Was jeweils zu sehen sein muss:

- **B (PP24, PP25):** Installer endet grün; das Fenster wird mit einer Taste geschlossen; **innerhalb von zehn Minuten** ist der entpackte Ordner samt ZIP weg
  (der Helfer versucht es alle drei Sekunden und gibt erst nach zehn Minuten auf), danach liegen weder `pbp_installer_aufraeumen.py` noch ein `tmp…\pip.zip` im
  Temp-Ordner (`check` zeigt beides).
- **D (PP26):** *Einstellungen › Erweitert › Erweiterungen › Texterkennung › Herunterladen & installieren* **ohne** eine Abfrage nach Administratorrechten;
  Fortschritt, dann „Installiert · v5.4.0“. `komp` zeigt den Vermerk (`pbp-installation.json`), den Ordner `%LOCALAPPDATA%\Programs\Tesseract-OCR` mit
  `tesseract.exe`, `tesseract-uninstall.exe` und im `tessdata` **`deu.traineddata`**. *Speicher & Downloads* nennt den Programmordner mit Größe. Das Scan-PDF
  hochladen: `ocr` zeigt `sprachen: deu+eng`, keinen Sprachhinweis. Danach *Entfernen*: Ordner und Startmenü-Eintrag weg, Karte wieder „Nicht installiert“.
- **G (PP26):** Texterkennung noch einmal installieren, dann der Deinstaller (Knopf in der Gefahrenzone): Schritt 5 meldet „[OK] Texterkennung (Tesseract)
  entfernt“, danach ist `%LOCALAPPDATA%\Programs\Tesseract-OCR` samt Startmenü-Eintrag weg (`check`), `components\` ebenfalls.
- **H:** wie zuvor; `orig_config2.json` zurückkopieren, `%APPDATA%\Claude` entfernen, wenn es erst durch den Lauf entstand.

## Dritter Lauf (vor der Veröffentlichung von 1.8.0): der Kandidat `1.8.0`, alle Blöcke

Nutzerwort 12.10.2026: „vorher wieder ausführlich testen“. Alle Blöcke A bis H, rund drei Stunden, mit dem Kandidaten **`1.8.0`** (Zweig `release/v1.8.0`, ZIP des
Zweigs) statt `1.8.0-rc.1`. Die Vorbereitung ist dieselbe wie im ersten Lauf (Liste oben, „Was du vorher tust“): der Werkstatt-PC läuft ohne Ruhezustand, die
Remotedesktop-Verbindung ist offen, du fasst ihn nicht an. Was anders ist:

- **Stable ist jetzt 1.7.157** (Block F: das ZIP des Tags `v1.7.157`; Schema 48 → 52, Abdruck gleich).
- **Alle Funde PP20 bis PP26 in einem Durchgang** (B, D, G, H): kein leerer Ordner, keine alten Fenster, keine Temp-Reste, Texterkennung ohne Abfrage nach
  Administratorrechten, Deinstaller mit Schritt „[OK] Texterkennung (Tesseract) entfernt“.
- **E2 bis E4 brauchen neue Probe-Veröffentlichungen** über 1.8.0 im Probe-Repository (mit dem echten Schlüssel signiert, der den Rechner nie verlässt):
  zuerst `v1.8.3` (gut, `probe_archiv_bauen.py 1.8.3 <Ordner>`) für E2 und E3, danach `v1.8.4` (falsche Prüfsumme) und `v1.8.5` (fremde Signatur) für E4
  (`probe_e4_bauen.py <Archiv> 1.8.4 1.8.5 <Ordner>`, liest beide Pakete mit den Prüfungen des Programms gegen); die älteren bleiben liegen.
- **F2 (neu): „Neue Linie“ auf einer 1.7-Installation.** Auf der installierten Stable 1.7.157 wird die Einstellung `update_quellen` auf das Probe-Repository
  gestellt (`pbp_probe.ps1 linie MadGapun/PBP-update-probe`; dort liegt eine stabile 1.8-Veröffentlichung). Erwartet: Einstellungen › Updates und die Seitenleiste nennen die Version 1.8.x samt Weg dorthin
  (ZIP, `INSTALLIEREN.bat`); angeboten oder installiert wird sie nie (Linie 1.7 → 1.8 geht einmal von Hand). So wird die Meldung, die am Tag der
  Veröffentlichung jede 1.7-Installation trifft, gegen echte GitHub-Antworten gesehen, bevor sie wirklich gilt.
- **E5 (neu): Vorabversion von selbst** (#1199, #1222). Das echte `1.8.0-rc.3` kann eine Vorabversion NICHT installieren (#1222: Start,
  Vorbedingung und Manifest kannten nur stabile Fassungen); der Beweis braucht deshalb eine Installation MIT dem Fix.
  `probe_vorab_bauen.py 1.9.0-rc.1 1.9.0-rc.2 <Ordner>` baut aus dem Kandidaten das ZIP `PBP-1.9.0-rc.1.zip` (Installation von Hand) und die
  Probe-Veröffentlichung `v1.9.0-rc.2` (Archiv, Summenliste, Signatur mit dem echten Schlüssel; im Probe-Repository als **Vorabversion** gekennzeichnet).
  Bewusst die Linie **1.9**: die stabilen Probe-Veröffentlichungen aus E2 bis E4 (`v1.8.x`) liegen in einer anderen Linie und kommen nicht
  dazwischen (ein Linienwechsel geschieht nie von selbst). Ablauf auf einem sauberen Stand: (1) `1.9.0-rc.1` installieren wie in Block B;
  (2) die feste Quelle der Kopie auf das Probe-Repository stellen wie in E2; (3) *Einstellungen › Erweitert › Updates*: der Abschnitt
  **„Vorabversionen automatisch“** steht da (nur auf einer Vorab-Installation), Schalter **aus**: „Jetzt prüfen“ nennt die Vorabversion, es gibt
  keinen Installieren-Knopf, die Karte sagt „nur, wenn du es einschaltest“; (4) Schalter **ein**, „Jetzt prüfen“: *Neu: v1.9.0-rc.2* mit
  „Jetzt installieren“; (5) installieren: Fortschritt, Verlauf „1.9.0-rc.2“, „Ab dem nächsten Neustart“; (6) PBP und Claude Desktop neu starten:
  die Seitenleiste zeigt `1.9.0-rc.2`, „Zurückschalten“ auf `1.9.0-rc.1` geht; (7) Gegenprobe: auf der stabilen Installation aus Block B/F fehlt
  der Abschnitt ganz, und die Meldung einer Vorabversion sagt dort „nie von selbst“.
- **Block I (neu): Wege und Listen** (#1170, #1171; rund 15 Minuten, nur Klicken und Ansehen, auf dem echten Bildschirm). Erwartet ist überall: **ein Klick je
  Schritt, nichts scrollen, um zu klicken.** (1) Stellen und Bewerbungen: der Kopf ist eine Zeile, die erste Zeile samt Knöpfen steht im Bild; ein Klick auf die Zeile
  klappt die Kennzahlen auf, nach dem Neuladen bleibt es so. (2) Eine Stelle öffnen › „Bewerbung anlegen“ › speichern: die neue Bewerbung liegt offen da; in der
  Leiste „Zur Stelle“ (ein Klick), dort „‹ Zurück zu Bewerbung: …“ (ein Klick). (3) In der Timeline „Firma“: die Firmen-Ansicht mit der Leiste im festen Kopf —
  die Historie scrollen, die Leiste bleibt; „‹ Zurück zu Bewerbung: …“. (4) Alt + ← (oder die Zurück-Taste der Maus) schließt den obersten Dialog, die Seite bleibt.
  (5) Das Dashboard-Fenster auf halbe Bildschirmbreite ziehen (neben Claude Desktop): die Seitenleiste ist eingeklappt, nichts ist abgeschnitten. (6) Einstellungen:
  die Reiter sind die einzige Navigation; die Zahlen in der Seitenleiste tragen ein Wort. Die Tabelle aller Wege: `docs/internal/wegetabelle-1171.md`.
- **Ergebnis** wie zuvor: je Block ein Satz im PR des Kandidaten und im Issue #1170; Funde werden ab PP30 nummeriert. Ein Befund, der ein Ergebnis ändert,
  hält die Veröffentlichung an.

**Dritter Lauf (14.10.2026):** gelaufen, alle Blöcke A bis I und E5 in Ordnung; Ergebnis je Block und die Funde PP30 bis PP36 stehen in `praxisprobe-1.8.0.md`
(Abschnitt „Dritter Lauf des Kandidaten `1.8.0`“), im PR des Kandidaten und im Issue #1170. Alle Funde sind im Kandidaten behoben (#1224 bis #1229, Probe-Skript).
Der Rechner steht wieder auf der Ausgangsprüfung; die Store-Konfiguration von Claude weicht nur in Schlüsseln ab, die Claude Desktop selbst geändert hat.

## Vierter Lauf (nach `1.8.0-rc.4`): die interaktive Hilfe (#1233), Block J

Neu seit dem dritten Lauf ist nur die Hilfe, die Fragen zur Bedienung beantwortet. Block J, rund 20 Minuten, auf dem echten Bildschirm, nach einer frischen
Installation (Block B) und vor dem Zurücksetzen (Block H); alle anderen Blöcke gelten als belegt, solange kein Fund sie berührt. Erwartet:

- **J1 — Eine Frage, eine Karte, ein Sprung.** Hilfe & Support (Fragezeichen neben dem Profilwechsler) › *Frag mich*: vor der ersten Frage stehen vier
  Beispielfragen zum Anklicken da (ein Klick stellt die Frage; nach der ersten Frage verschwinden sie). Dann „Wo stelle ich ein, dass sich PBP selbst
  aktualisiert?“. Es erscheinen Karten mit Titel, Kurztext und Quelle; jede führt mit *Öffnen: Einstellungen › Updates* in den Reiter (der Dialog schließt
  sich), *Mehr im Wiki* öffnet eine Seite von `github.com/MadGapun/PBP/wiki` in einem neuen Tab. Eine Nachfrage („und wo finde ich das?“) bleibt beim Thema.
- **J2 — Ehrlich, wenn nichts passt.** „Wie wird das Wetter morgen?“ → „Dazu kann ich nur zur Bedienung von PBP etwas sagen“; „Kann ich meine Stellen nach
  Excel exportieren?“ → keine sichere Antwort. Beide zeigen den Satz für Claude; ein Klick kopiert ihn, in Claude Desktop eingefügt ist er verständlich.
- **J3 — Die Seitenleiste.** Ohne laufende lokale KI steht unter dem Elwosa-Strom **keine** Eingabe. Mit laufender lokaler KI (Ollama, ein Modell gewählt)
  erscheint „Frag zur Bedienung …“ fest unter dem Strom; Frage und Antwort stehen IM Strom nach der Zeit (ein einziger Bereich zum Scrollen, kein zweiter
  Scrollbalken), vor der Reihe die Zeile „Fragen zur Bedienung“; der Bereich springt an den Anfang der Antwort, eine zweite Frage steht darunter, und eine Meldung
  Elwosas nach der Antwort steht UNTER ihr und ist zu sehen, wenn du unten liest (#1254). Die Antwort ist kompakt (der beste Treffer, die weiteren auf Klick). Elwosa
  selbst spricht dazu nicht.
- **J4 — Die Kurzantwort (Beta).** *Einstellungen › Lokale KI*: die Karte „Fragen zur Bedienung: Kurzantwort“ trägt *Beta*, der Schalter ist **aus**. Eingeschaltet
  und mit laufender lokaler KI erscheint über den Karten nach einigen Sekunden eine kurze Antwort mit Quelle (oder nur die Karten, wenn die Antwort verworfen
  wird); ausgeschaltet bleiben die Karten. Die Zeile unter dem Schalter nennt den Zustand der lokalen KI.
- **J5 — Nichts wird gespeichert.** Nach den Fragen steht ihr Wortlaut weder in *Einstellungen › Logs* noch in einem Elwosa-Eintrag; ein Neuladen des Dashboards
  zeigt den Verlauf der Hilfe nicht mehr.
- **J6 — Das Mitscrollen des Elwosa-Stroms (#1256).** Scrolle im Verlauf nach oben und warte, bis Elwosa etwas Neues sagt: unten im Bereich erscheint „N neu“ mit der
  richtigen Zahl, auch wenn zehn Nachrichten im Verlauf stehen; ein Klick darauf oder das Scrollen ans Ende lässt den Knopf verschwinden. Eine Nachricht auszublenden
  (das X an der Nachricht) lässt keinen Knopf erscheinen. Wer unten liest, bleibt unten, wenn sich die Höhe des Bereichs ändert (Fenster kleiner und wieder größer
  ziehen; die Zeile „Update-Stand unbekannt“ erscheint nach etwa einer Sekunde und nimmt 38 Pixel), und eine neue Meldung ist dann zu sehen. Elwosa mit dem Auge
  aus- und wieder einblenden: der Verlauf steht danach wieder unten, nicht bei den ältesten Nachrichten.
- **Ergebnis** wie zuvor: ein Satz je Punkt im PR des Kandidaten und im Issue #1233; Funde werden ab PP37 nummeriert.
