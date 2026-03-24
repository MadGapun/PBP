# PBP - Häufig gestellte Fragen (FAQ)

## Was ist PBP?

**PBP (Persönliches Bewerbungs-Portal)** ist ein KI-gestütztes Bewerbungsmanagement-Tool,
das den gesamten Bewerbungsprozess von der Stellensuche bis zum Angebot strukturiert
und automatisiert. Es läuft als MCP-Server für Claude Desktop.

GitHub: https://github.com/MadGapun/PBP

---

## Erste Schritte

### 1. Profil erstellen
Starte mit der Ersterfassung deines Profils. PBP fragt dich Schritt für Schritt
nach deinen persönlichen Daten, Berufserfahrung, Skills und Ausbildung.

**Tipp:** Lade vorhandene Lebensläufe und Zeugnisse hoch. PBP extrahiert
die Daten automatisch und füllt dein Profil vor.

### 2. Suchkriterien setzen
Definiere deine Jobsuche-Keywords:

- **MUSS-Keywords**: Stellen müssen mindestens eins davon enthalten
- **PLUS-Keywords**: Erhöhen den Score und verbessern die Sortierung
- **AUSSCHLUSS-Keywords**: Stellen werden komplett ignoriert

**Tipp:** Nutze `profil_zusammenfassung()` als Basis für deine Keywords.

### 3. Jobsuche starten
Aktiviere Quellen im Dashboard und starte eine Suche. Die Ergebnisse werden
automatisch bewertet und sortiert.

### 4. Stellen bewerten und bewerben
Gehe die gefundenen Stellen durch, bewerte sie mit `stelle_bewerten()`
und erstelle Bewerbungsunterlagen für die passenden Stellen.

### 5. Bewerbungen verfolgen
Nutze den geführten Bewerbungs-Workflow: PBP zeigt dir bei jeder Bewerbung
die nächsten sinnvollen Schritte an, statt dich mit Optionen zu überladen.

---

## Wichtige Hinweise

### Token- und Kontextlimits bei großen Profilen

Wenn dein Profil sehr umfangreich ist, kann selbst ein starkes Claude-Abo
an Grenzen stoßen. Claude analysiert bei jeder Interaktion dein Profil,
deine Suchkriterien und oft auch die aktuelle Stelle.

**Empfehlungen:**

- Arbeite schrittweise statt alles auf einmal zu laden.
- Nutze Uploads und Analysen in kleineren Blöcken.
- Bereinige Skill-Listen regelmäßig.
- Extrahiere nicht alle Dokumente gleichzeitig.

### Blacklist richtig nutzen

Die Blacklist ist nur für harte Ausschlüsse gedacht:

- **Firmen**: Unternehmen, die immer ignoriert werden sollen
- **Keywords**: Begriffe, die immer ignoriert werden sollen

Individuelle Ablehnungsgründe wie `zu_weit` oder `zu_junior` gehören nicht
in die Blacklist. Diese Informationen werden über die Stellen- und
Bewerbungslogik ohnehin sinnvoller ausgewertet.

### Scoring-Regler-System

Ab `v0.32.0` gibt es ein konfigurierbares Scoring-System. Jede Dimension
wie Stellentyp, Entfernung, Remote und Gehalt kann gewichtet werden.
Nutze `scoring_konfigurieren()`, um PBP an deine Prioritäten anzupassen.

---

## Verfügbare Workflows

| Workflow | Beschreibung | Wann nutzen? |
|---|---|---|
| `ersterfassung` | Geführte Profil-Erstellung | Beim allerersten Start |
| `bewerbung_vorbereitung` | Komplette Vorbereitung | Für eine neue Bewerbung |
| `bewerbung_schreiben` | Anschreiben erstellen | Wenn du dich konkret bewerben willst |
| `interview_vorbereitung` | Interview-Prep | Vor einem Gespräch |
| `interview_simulation` | Übungsgespräch | Zum Üben mit Claude |
| `gehaltsverhandlung` | Gehalt verhandeln | Bei Angebot oder Verhandlung |
| `profil_erweiterung` | Dokumente analysieren | Nach Upload neuer Unterlagen |

## Entscheidungsbaum: Was soll ich jetzt tun?

```text
Öffne PBP und frage dich:

Habe ich ein Profil?
├── Nein → workflow_starten("ersterfassung")
└── Ja
    ├── Habe ich Suchkriterien?
    │   ├── Nein → suchkriterien_setzen(...)
    │   └── Ja
    │       ├── Habe ich aktuelle Stellen?
    │       │   ├── Nein → jobsuche_starten()
    │       │   └── Ja
    │       │       ├── Habe ich unbearbeitete Stellen?
    │       │       │   ├── Ja → stellen_anzeigen() + stelle_bewerten()
    │       │       │   └── Nein
    │       │       │       ├── Habe ich Bewerbungen in Vorbereitung?
    │       │       │       │   ├── Ja → workflow_starten("bewerbung_vorbereitung")
    │       │       │       │   └── Nein
    │       │       │       │       ├── Warte ich auf Antworten?
    │       │       │       │       │   ├── Ja → nachfass_anzeigen() / bewerbungen_anzeigen()
    │       │       │       │       │   └── Nein → neue Jobsuche starten
    │       │       │       └── Habe ich ein Interview?
    │       │       │           └── Ja → workflow_starten("interview_vorbereitung")
    │       └── Habe ich neue Dokumente?
    │           └── Ja → workflow_starten("profil_erweiterung")
    └── Brauche ich einen Bericht?
        └── Ja → bewerbungsbericht_exportieren()
```

**Tipp:** Im Zweifel hilft `statistiken_abrufen()`. Das gibt dir einen
kompakten Überblick über deinen aktuellen Stand und die Pipeline.

---

## Troubleshooting

### "Token-Limit erreicht"

- Schließe die aktuelle Konversation und starte eine neue.
- Reduziere die Datenmenge.
- Arbeite in kleineren Schritten.

### "Skill-Import erzeugt Junk-Einträge"

- Nutze `profil_bearbeiten()`, um einzelne Skills zu löschen.
- Oder bereinige sie über die Profil-Seite im Dashboard.

### "Stellensuche findet nichts"

- Prüfe, ob Quellen aktiviert sind.
- Prüfe die MUSS-Keywords.
- Erweitere Regionen oder lockere Kriterien.

### "Lebenslauf-Export sieht komisch aus"

- Ab `v0.32.0` ist der ATS-konforme Stil ohne Tabellen aktiv.
- Nutze DOCX für manuelle Nachbearbeitung.
- Prüfe, ob alle Profildaten vollständig sind.

---

## Voraussetzungen

- **Claude Pro** oder **Claude Max** für größere Profile
- **Claude Desktop** mit MCP-Unterstützung
- **Python 3.11+**
- Optional: **Playwright** für automatische Jobsuche

---

*Erstellt für PBP v0.32.4 | https://github.com/MadGapun/PBP*
