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
- **Optionaler API-Weg (ab Werk aus):** Wer einen eigenen Anthropic-API-Schlüssel in die Umgebungsvariable `PBP_ANTHROPIC_API_KEY` legt und eine Aufgabe ausdrücklich freigibt, bei dem sendet PBP selbst (nicht Claude Desktop) die in der Einstellung genannten Angaben an die Anthropic-API: beim Abgleich einer Stelle mit dem Profil die Berufsbezeichnung, Karrierestufe, wichtigsten Kompetenzen, Titel, Firma und Text der geprüften Stelle, die häufigsten Aussortier-Gründe und bis zu fünf früher aussortierte Titel mit Grund (die Firmennamen ersetzt PBP vorher); beim Prüfen eines Anzeigentextes nur die Anzeige. Der Schlüssel steht nur in der Umgebung, PBP speichert, protokolliert und zeigt ihn nirgends. Ein Budget in US-Dollar setzt eine harte Obergrenze, und die KI-Schalter unter Einstellungen › Claude (Cloud) sperren auch diesen Weg.
- **Keine API-Keys im Code:** Alle Konfiguration läuft über Umgebungsvariablen.
- **Jobportal-Scraping:** PBP ruft Stellenportale ab. Dabei gehen nur Suchbegriffe und Region an die Portale — keine Profil- oder Bewerbungsdaten. Für LinkedIn und XING ist eine eigene Anmeldung nötig; PBP speichert dafür keine Zugangsdaten (Claude arbeitet in deinem bereits angemeldeten Browser).
