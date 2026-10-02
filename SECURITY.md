# Sicherheitsrichtlinie

## Unterstützte Versionen

| Version | Unterstützt |
|---------|-------------|
| 1.7.x (Stable) — jeweils die neueste | ✅ Ja |
| 1.8.0-beta.x (Vorabversion) | ⚠️ Fehlerbehebungen kommen in die nächste Vorabversion |
| < 1.7 | ❌ Nein |

## Sicherheitslücke melden

**Bitte erstelle KEIN öffentliches Issue für Sicherheitslücken.**

Schicke stattdessen eine E-Mail an: **pbp-security@elwosa.de**

Beschreibe bitte:
- Was du gefunden hast
- Schritte zum Reproduzieren (wenn möglich)
- Mögliche Auswirkungen

Wir melden uns innerhalb von 7 Tagen und arbeiten mit dir an einer Lösung, bevor wir das Problem öffentlich machen.

## Architektur-Hinweise

- **Lokale Anwendung:** Gespeichert wird lokal auf deinem Rechner; was du mit Claude bearbeitest, geht an Anthropic. PBP hat keinen eigenen Server und kein eigenes Konto.
- **Datenbank:** SQLite-Datei auf deiner Festplatte. Löschen = Daten weg.
- **Claude Desktop:** Wenn du mit Claude sprichst, werden die relevanten Daten an Anthropics API gesendet — wie bei jeder normalen Claude-Nutzung. Das schließt Profil (auch Adresse und Geburtsdatum), den Text deiner Dokumente, Anzeigentexte und Notizen ein, sobald Claude sie über PBP liest. Einzelne Bereiche kannst du in den Einstellungen für Claude sperren.
- **Anfragen, die PBP selbst stellt:** Jobbörsen (nur bei einer Suche; LinkedIn und XING verlangen eine Anmeldung), JobSpy (läuft lokal und fragt Indeed und LinkedIn ab), OpenStreetMap Nominatim (dein Wohnort und die Orte der Stellen, als Koordinaten für die Entfernung), OpenRouteService (Fahrstrecken, nur mit eigenem Schlüssel), GitHub und elwosa.de (Update-Prüfung und Tipps, anonym).
- **Keine API-Keys im Code:** Alle Konfiguration läuft über Umgebungsvariablen.
- **Jobportal-Scraping:** PBP ruft Stellenportale ab. Dabei gehen nur Suchbegriffe und Region an die Portale — keine Profil- oder Bewerbungsdaten. Für LinkedIn und XING ist eine eigene Anmeldung nötig; PBP speichert dafür keine Zugangsdaten (Claude arbeitet in deinem bereits angemeldeten Browser).
