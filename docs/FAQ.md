# PBP - Haeufig gestellte Fragen (FAQ)

## Was ist PBP?

**PBP (Persoenliches Bewerbungs-Portal)** ist ein KI-gestuetztes Bewerbungsmanagement-Tool,
das den gesamten Bewerbungsprozess von der Stellensuche bis zum Angebot strukturiert
und automatisiert. Es laeuft als MCP-Server fuer Claude Desktop.

GitHub: https://github.com/MadGapun/PBP

---

## Erste Schritte

### 1. Profil erstellen
Starte mit der Ersterfassung deines Profils. PBP fragt dich Schritt fuer Schritt
nach deinen persoenlichen Daten, Berufserfahrung, Skills und Ausbildung.

**Tipp:** Lade vorhandene Lebenslaeufe und Zeugnisse hoch — PBP extrahiert
die Daten automatisch und fuellt dein Profil vor.

### 2. Suchkriterien setzen
Definiere deine Jobsuche-Keywords:
- **MUSS-Keywords**: Stellen muessen mindestens eins davon enthalten
- **PLUS-Keywords**: Erhoehen den Score (bessere Sortierung)
- **AUSSCHLUSS-Keywords**: Stellen werden komplett ignoriert

**Tipp:** Nutze `profil_zusammenfassung()` als Basis fuer die Keywords.

### 3. Jobsuche starten
Aktiviere Quellen im Dashboard und starte eine Suche. Die Ergebnisse werden
automatisch bewertet und sortiert.

### 4. Stellen bewerten und bewerben
Gehe die gefundenen Stellen durch, bewerte sie mit `stelle_bewerten()`,
und erstelle Bewerbungsunterlagen fuer die passenden Stellen.

### 5. Bewerbungen verfolgen
Nutze den gefuehrten Bewerbungs-Workflow (#170): PBP zeigt dir bei jeder
Bewerbung genau die naechsten Schritte an — von der Vorbereitung bis zum Angebot.

---

## Wichtige Hinweise

### Token-/Kontextlimits bei grossen Datenmengen

**WICHTIG:** Wenn dein Profil sehr umfangreich ist (viele Positionen, Projekte,
Skills, Dokumente), kann selbst ein Claude Pro Abo an seine Grenzen kommen.
Claude analysiert bei jeder Interaktion das gesamte Profil.

**Empfehlungen:**
- Arbeite schrittweise, nicht alles auf einmal laden
- Bei sehr grossen Profilen: Batch-Verarbeitung nutzen
- Skill-Listen regelmaessig bereinigen (Duplikate, Junk-Eintraege entfernen)
- Nicht alle Dokumente gleichzeitig extrahieren lassen

### Blacklist richtig nutzen

Die Blacklist ist NUR fuer harte Ausschluesse gedacht:
- **Firmen**: Unternehmen die IMMER ignoriert werden sollen
- **Keywords**: Begriffe die IMMER ignoriert werden sollen

Individuelle Ablehnungsgruende (zu_weit, zu_junior, etc.) werden automatisch
bei `stelle_bewerten()` gespeichert — sie gehoeren NICHT in die Blacklist!

### Scoring-Regler-System

Ab v0.32.0 gibt es ein konfigurierbares Scoring-System. Jede Dimension
(Stellentyp, Entfernung, Remote, Gehalt) hat einen Regler der den
Fit-Score beeinflusst. Nutze `scoring_konfigurieren()` um die Regler
an deine Beduerfnisse anzupassen.

---

## Verfuegbare Workflows

| Workflow | Beschreibung | Wann nutzen? |
|---|---|---|
| `ersterfassung` | Gefuehrte Profil-Erstellung | Beim allerersten Start |
| `bewerbung_vorbereitung` | Komplette Vorbereitung | Neue Bewerbung von A-Z |
| `bewerbung_schreiben` | Anschreiben erstellen | Wenn du dich bewerben willst |
| `interview_vorbereitung` | Interview-Prep | Vor einem Vorstellungsgespraech |
| `interview_simulation` | Uebungsgespraech | Zum Ueben vor dem Interview |
| `gehaltsverhandlung` | Gehalt verhandeln | Bei Gehaltsgespraech/Angebot |
| `profil_erweiterung` | Dokumente analysieren | Nach Dokument-Upload |

## Entscheidungsbaum: Was soll ich tun?

```
Oeffne PBP und frage dich:

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
    │       │       │       │       │   └── Nein → Neue Jobsuche starten!
    │       │       │       └── Habe ich ein Interview?
    │       │       │           └── Ja → workflow_starten("interview_vorbereitung")
    │       └── Habe ich neue Dokumente?
    │           └── Ja → workflow_starten("profil_erweiterung")
    └── Brauche ich einen Bericht?
        └── Ja → bewerbungsbericht_exportieren()
```

**Tipp:** Im Zweifel einfach `statistiken_abrufen()` aufrufen — das gibt dir
einen Ueberblick ueber deinen aktuellen Stand und zeigt die Pipeline.

---

## Troubleshooting

### "Token-Limit erreicht"
- Schliesse die aktuelle Konversation und starte eine neue
- Reduziere die Datenmenge (weniger Skills, kuerze Beschreibungen)
- Arbeite in kleineren Schritten

### "Skill-Import erzeugt Junk-Eintraege"
- Nutze `profil_bearbeiten()` um einzelne Skills zu loeschen
- Oder bereinige ueber die Profil-Seite im Dashboard

### "Stellensuche findet nichts"
- Pruefe ob Quellen aktiviert sind (Dashboard -> Einstellungen)
- Pruefe die MUSS-Keywords — zu spezifische Keywords = keine Treffer
- Erweitere die Regionen

### "Lebenslauf-Export sieht komisch aus"
- Ab v0.32.0: ATS-konformer Stil ohne Tabellen
- Nutze DOCX-Format fuer manuelle Nachbearbeitung
- Pruefe ob alle Profildaten vollstaendig sind

---

## Voraussetzungen

- **Claude Pro Abo** (oder Claude Max fuer grosse Profile)
- **Claude Desktop** mit MCP-Unterstuetzung
- **Python 3.11+** (fuer den MCP-Server)
- Optional: Playwright (fuer automatische Jobsuche)

---

*Erstellt fuer PBP v0.32.0 | https://github.com/MadGapun/PBP*
