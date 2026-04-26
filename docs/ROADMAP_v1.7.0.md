# Roadmap v1.7.0 — Local LLM Foundation

**Status:** Planning (Stand 2026-04-25)

v1.7.0 wird der **erste tiefe Eingriff** seit der Adapter-v2-Architektur in
v1.6.0 (#499). Das zentrale Thema ist die Einfuehrung einer **lokalen LLM
ueber Ollama als optionalen Sidecar-Prozess** — und der schrittweise
Umbau einzelner Funktionen, die heute Claude-Token verbrauchen oder
heuristisch arbeiten, auf den lokalen Pfad.

Dieses Dokument fasst die strategische Richtung zusammen. Alle
detaillierten Anwendungsfaelle und Phasen sind in **[#512 — Lokale LLM
(Ollama Sidecar): Anwendungsfaelle und
Roadmap](https://github.com/MadGapun/PBP/issues/512)** dokumentiert.

---

## Warum

Drei Schmerzpunkte fuhren zu dieser Architektur-Entscheidung:

1. **Claude-Token-Belastung**. Heute laufen alle KI-Operationen ueber das
   Claude-Konto des Users — auch triviale wie "Skill-Liste aus Lebenslauf
   extrahieren" oder "Welche Keywords unterscheiden meine Bewerbungen
   von meinen Ablehnungen?". Das ist Ressourcen-Verschwendung.

2. **Heuristik-Grenze erreicht**. Beispiel: Die in v1.6.0-beta.29
   ueberarbeiteten Keyword-Vorschlaege sind besser geworden (Stop-Words,
   TF-IDF-Spezifitaet, Bewerbungs-vs-Ablehnungs-Vergleich), aber sie
   verstehen den **inhaltlichen** Unterschied nicht. Dass "Windchill"
   vs. "Teamcenter" der entscheidende Punkt sein koennte, sieht ein
   lokales Sprachmodell besser als jede statistische Heuristik.

3. **Datenschutz / lokale Souveraenitaet**. Lebenslauf-Inhalte,
   Stellenbeschreibungen mit Firmenkontakten, Gespraechs-Notizen sind
   sensibel. Eine lokale LLM verlaesst die eigene Maschine nicht.

---

## Architektur

### Sidecar-Modell

```
┌──────────────────────────┐         ┌──────────────────┐
│ PBP MCP Server (Python)  │ ──────> │ Ollama (lokal)   │
│ - feature_flag local_llm │  HTTP   │ llama3.1:8b      │
│ - pbp.local_llm.client   │   :11434│ qwen2.5:7b       │
└──────────────────────────┘         └──────────────────┘
              │
              ├─ wenn local_llm AUS:
              │  Heuristik / Claude-Fallback wie heute
              │
              └─ wenn local_llm AN + Sidecar erreichbar:
                 lokale Inferenz, Claude bleibt fuer komplexe Multi-
                 Step-Aufgaben zustaendig
```

### Konstraints

- **Ollama bleibt optional**. Ohne Sidecar laeuft v1.7.0 wie v1.6.0.
  Der `feature_flag local_llm` ist Default OFF.
- **Keine zusaetzliche Pflicht-Dependency**. Installer pruefen ob Ollama
  laeuft, installieren es nicht. User entscheidet ueber Komponente.
- **Modell-Auswahl im UI** (siehe #425 Granulare KI-Steuerung).
  Empfohlen werden 7-8B-Modelle, die auf 16GB RAM laufen.
- **Claude bleibt erste Instanz fuer komplexe Aufgaben** —
  Anschreiben-Generierung, Bewerbungs-Strategie, Profil-Analyse.

---

## Phasen

### Phase A — niedrige Komplexitaet, hoher Nutzen (Sub-Issues an v1.7.0)

| Use-Case | Issue | Heute | Mit Ollama |
|---|---|---|---|
| Smartere Keyword-Vorschlaege | (aus #512) | TF-IDF-Heuristik (beta.29) | Inhaltliche Unterscheidung "Windchill vs. Teamcenter" |
| Stellen-Embeddings fuer Aehnlichkeit | #465 absorbed | nur Hash-Dedup | semantische Aehnlichkeit |
| Stelle-zu-Profil-Match-Erklaerung | (aus #512) | Score-Zahl | "Score 7 weil PLM passt, fehlt aber S/4HANA" (lokal); Claude nur bei "tiefer" |

### Phase B — mittlere Komplexitaet (v1.7.0)

| Use-Case | Issue | Heute | Mit Ollama |
|---|---|---|---|
| Skill-Extraktion aus Dokumenten | (aus #512) | Regex/Liste, viele Garbage-Skills (#43, #129) | Strukturierte Extraktion + Validierung |
| Anschreiben-Vorab-Check | (aus #512) | nur Claude | Lokal: "Klingt natuerlich? MUSS-Keywords vorhanden?" — reduziert Claude-Iterationen |
| Lange Stellen-Beschreibungen kuerzen | (aus #512) | UI zeigt nur Anfang | Lokale Extraktion der Kernpunkte |

### Phase C+D — hoehere Komplexitaet (verschoben auf v1.8.0)

| Use-Case | Issue | Beschreibung |
|---|---|---|
| User-Lernen via Few-Shot-DB | (v1.8.0) | Aus User-Feedback ("dieses Anschreiben gut", "diese Stelle ablehnen weil X") lokale Datenbank fuer Claude-Calls |
| Interview-Training-Arc | #452 | Frage-Antwort lokal vorbereiten, dann Claude verfeinern |

---

## Begleitende v1.7.0-Issues

Neben dem Local-LLM-Kern stehen weitere Sub-Themen auf v1.7.0:

| # | Titel |
|---|---|
| [#425](https://github.com/MadGapun/PBP/issues/425) | Granulare KI-Steuerung in Einstellungen |
| [#429](https://github.com/MadGapun/PBP/issues/429) | PyPI-Paket + MCP Registry |
| [#464](https://github.com/MadGapun/PBP/issues/464) | Post-Interview-Reflexion |
| [#469](https://github.com/MadGapun/PBP/issues/469) | Thunderbird-Integration (Roadmap) |
| [#472](https://github.com/MadGapun/PBP/issues/472) | n:m Bewerbung-zu-Stelle-Relation |
| [#478](https://github.com/MadGapun/PBP/issues/478) | Thunderbird-Add-On "An PBP senden" |
| [#480](https://github.com/MadGapun/PBP/issues/480) | Outlook-Integration (Office-Add-In) |
| [#481](https://github.com/MadGapun/PBP/issues/481) | Termine an Thunderbird/Outlook senden |
| [#504](https://github.com/MadGapun/PBP/issues/504) | Plugin-Plattform: Sub-Add-Ins ueber Ingest-API |
| [#505](https://github.com/MadGapun/PBP/issues/505) | ID-Typisierung (Praefixe) |

---

## Risiken

1. **Performance-Erwartung**. Ein 7-8B-Modell auf CPU ist langsam.
   GPU-Nutzung empfohlen aber nicht garantiert. Klare Warnungen im
   UI: "Ollama-Inferenz braucht ~5-15s ohne GPU".

2. **Modell-Qualitaets-Variabilitaet**. Eine lokale LLM ist
   schwaecher als Claude. Wir muessen pro Use-Case validieren ob die
   Qualitaet ausreicht (z.B. Skill-Extraktion: false-positive-Rate).

3. **Ollama-Verfuegbarkeit am User-System**. Installation auf Windows
   nicht trivial. Wir liefern Setup-Hilfe, aber keine Auto-Installation.

4. **Migrations-Pfad fuer Embeddings**. Wenn wir Stellen-Embeddings in
   die DB schreiben, muss das Schema das aushalten (BLOB-Spalten oder
   separate Tabelle). Schema-Bump.

5. **Bestehende Heuristiken werden nicht entfernt** — sie bleiben als
   Fallback wenn `local_llm`-Flag aus ist oder Ollama nicht erreichbar.

---

## Nicht-Ziele

- Ollama als **Pflicht-Komponente** machen.
- Den **Claude-Workflow ersetzen**. Claude bleibt fuer Multi-Step-
  Aufgaben (Anschreiben, Strategie) zustaendig.
- **Lokale Modelle als Plattform anbieten** — wir nutzen Ollama,
  schreiben kein eigenes LLM-Backend.
- **Cloud-LLM-Provider unterstuetzen** (OpenAI, Anthropic API direkt).
  Wer ein anderes Modell will, nutzt Claude Desktop wie heute.

---

## Wann

Tagging ergibt sich aus dem **v1.6.0-Final-Release** (vermutlich
Anfang Mai 2026). Danach beginnt die v1.7.0-Beta-Phase mit
**Phase A** (Quick Wins). Phase B folgt im selben Release-Cycle.
Phase C+D wandert auf **v1.8.0**.

---

**Naechster Schritt nach v1.6.0-final:** Sub-Issues fuer Phase A aus
#512 ableiten und priorisieren (Embedding-Layer als Foundation,
weil 3 von 5 Use-Cases darauf aufbauen).
