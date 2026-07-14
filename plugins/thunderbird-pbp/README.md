# „An PBP senden" — Thunderbird-Add-on (J2/#478)

Markierte E-Mails (auch ganze Threads) per **Rechtsklick → „An PBP
senden"** an das Persoenliche Bewerbungs-Portal uebergeben. PBP macht den
Rest: Duplikat-Erkennung, Bewerbungs-Zuordnung, Termine, Timeline.
Alles laeuft lokal (127.0.0.1) — das Add-on ist ein externes Plugin an
der [Ingest-API v1](https://github.com/MadGapun/PBP/wiki/Plugins), ohne
Zugriff auf die PBP-Datenbank.

## Installation (3 Minuten, Thunderbird 115+)

1. **XPI bauen:** Den INHALT dieses Ordners (nicht den Ordner selbst) in
   eine ZIP packen und die Endung auf `.xpi` aendern:
   - Windows: alle Dateien markieren → Rechtsklick → *Senden an → ZIP-komprimierter Ordner* → umbenennen in `pbp-sender.xpi`
   - oder per Kommandozeile: `cd plugins/thunderbird-pbp && zip -r ../pbp-sender.xpi . -x README.md`
2. **In Thunderbird installieren:** ☰ → Add-ons und Themes → Zahnrad ⚙ →
   *Add-on aus Datei installieren...* → die `.xpi` waehlen. Die Warnung
   „nicht verifiziert" ist bei selbstgebauten Add-ons normal — Thunderbird
   erlaubt die Installation.
3. **Mit PBP koppeln:** PBP-Dashboard → Einstellungen → **Erweiterungen**
   → Gekoppelte Plugins → *Plugin koppeln* → Inhalt von
   [`pbp-plugin.json`](pbp-plugin.json) einfuegen → **API-Key kopieren**
   (wird genau einmal angezeigt).
4. **Key eintragen:** Thunderbird → Add-ons → „An PBP senden" →
   Einstellungen → API-Key einfuegen → *Verbindung testen* → Speichern.

## Nutzung

- **Eine Mail:** Rechtsklick auf die Nachricht in der Liste → „An PBP senden".
- **Ganzer Thread (J2.2):** Alle Nachrichten des Threads markieren
  (erste anklicken, letzte mit Umschalt+Klick — oder im Thread-Modus den
  Thread aufklappen und mit Strg/Cmd+A im Thread alle waehlen) →
  Rechtsklick → „An PBP senden". Jede Nachricht wird einzeln uebergeben;
  PBP haengt sie an dieselbe Bewerbung (Matching + Duplikat-Erkennung).
- Ergebnis kommt als Benachrichtigung („3 uebergeben, 1 schon vorhanden").

## Fehlerbilder

| Meldung | Ursache / Loesung |
|---|---|
| „Kopplung fehlt" | Schritt 3+4 oben durchfuehren |
| „Key ungueltig" | Key wurde in PBP widerrufen → neu koppeln, Key aktualisieren |
| „PBP nicht erreichbar" | Dashboard laeuft nicht → PBP-Verknuepfung auf dem Desktop starten |

## Alternativen ohne Add-on

Der [Watch-Folder](../watch-folder/) tut dasselbe ohne Installation im
Mail-Programm: Mails per Drag&Drop aus Thunderbird in einen Ordner ziehen.
