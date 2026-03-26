# Sicherheitsrichtlinie

## Unterstützte Versionen

| Version | Unterstützt |
|---------|-------------|
| 1.0.x   | ✅ Ja       |
| < 1.0   | ❌ Nein     |

## Sicherheitslücke melden

**Bitte erstelle KEIN öffentliches Issue für Sicherheitslücken.**

Schicke stattdessen eine E-Mail an: **pbp-security@elwosa.de**

Beschreibe bitte:
- Was du gefunden hast
- Schritte zum Reproduzieren (wenn möglich)
- Mögliche Auswirkungen

Wir melden uns innerhalb von 7 Tagen und arbeiten mit dir an einer Lösung, bevor wir das Problem öffentlich machen.

## Architektur-Hinweise

- **Lokale Anwendung:** PBP läuft vollständig auf deinem Rechner. Keine Cloud, kein Account, kein externer Server.
- **Datenbank:** SQLite-Datei auf deiner Festplatte. Löschen = Daten weg.
- **Claude Desktop:** Wenn du mit Claude sprichst, werden die relevanten Daten an Anthropics API gesendet — wie bei jeder normalen Claude-Nutzung. PBP selbst sendet keine Daten an externe Server.
- **Keine API-Keys im Code:** Alle Konfiguration läuft über Umgebungsvariablen.
- **Jobportal-Scraping:** PBP ruft öffentliche Stellenportale ab. Dabei werden keine Logins oder persönliche Daten übertragen.
