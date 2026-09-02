**Deutsch** | [English](README.en.md)

# <img src="docs/pbp.png" alt="PBP Logo" width="36" align="absmiddle" /> PBP — Persönliches Bewerbungs-Portal

<sup><a href="https://www.elwosa.de">An <b>ELWOSA</b> Project</a></sup>

<!-- Einstieg: Variante D (Originalsprache) + Schlusszeile aus Variante A, gewaehlt in #834. -->
**PBP ist ein Bewerbungs-Helfer — mit einem entscheidenden Unterschied: die Werkzeuge reden miteinander.**

Wer schon mal mehr als zehn Bewerbungen gleichzeitig laufen hatte, kennt das Gefühl: zehn offene Tabs, drei Excel-Listen, ein Kalender voller Termine ohne Kontext, und am Ende der Woche weiß man nicht mehr, wem man eigentlich was geschrieben hat.

PBP ist mehr als eine Excel-Liste, in der drei Monate später niemand mehr weiß, was eigentlich passiert ist. Mehr als ein Kalender, der an das Interview morgen erinnert, aber nicht weiß, mit wem man vor zwei Wochen telefoniert hat. Mehr als ein Coach, der Tipps gibt, ohne Lebenslauf, Stelle und bisherige Korrespondenz zu kennen.

![PBP-Dashboard — Bewerbungen, Termine und der nächste sinnvolle Schritt auf einen Blick](docs/screenshots/01_dashboard.png)

Aktuelle Version **v1.7.24** · letztes Release am 2. September 2026 · 2631 automatische Tests · wöchentliche Releases

Es ist gemacht für den deutschsprachigen Raum. Wer gerade keine Bewerbung schreiben muss, braucht es nicht. Wer eine schreibt, wird es vermutlich mögen.

**So fängst du an:** [ZIP herunterladen und `INSTALLIEREN.bat` doppelklicken](#schnellstart) — nach rund fünf Minuten läuft PBP. Du brauchst dazu [Claude Desktop](https://claude.ai/download) (kostenlos); als reines Verwaltungs-Tool funktioniert PBP auch ganz ohne KI.

> **🌍 Note for international users:** PBP currently supports the **German-speaking job market (DACH region)** only. All tools, workflows, job portals, and UI are in German — see the [English overview](README.en.md). Interested in support for your country? [Open an issue!](https://github.com/MadGapun/PBP/issues)

[![Stable](https://img.shields.io/badge/Stable-v1.7.24-brightgreen.svg)](https://github.com/MadGapun/PBP/releases/latest)
[![Tests](https://img.shields.io/badge/Tests-2631-brightgreen.svg)](https://github.com/MadGapun/PBP/actions)
[![MCP](https://img.shields.io/badge/MCP-Claude_Desktop-orange.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Plattformen](https://img.shields.io/badge/Plattformen-Windows_%7C_macOS_%7C_Linux-blue.svg)](#schnellstart)

---

## So funktioniert PBP

**PBP führt dich Schritt für Schritt durch deine Bewerbungen — auch wenn du lange keine geschrieben hast.**

| Schritt | Was passiert |
|---------|-------------|
| **1. Du erzählst kurz von dir** | Claude führt dich durch ein Kennenlerngespräch und baut dein Profil auf. Du musst nichts vorbereiten. |
| **2. PBP findet passende Stellen** | PBP durchsucht Stellenanzeigen automatisch auf den wichtigsten Jobbörsen. Du bekommst eine bewertete Liste. |
| **3. Du bewirbst dich — mit Unterstützung** | Anschreiben, Lebenslauf, Interview-Vorbereitung — PBP begleitet dich bei jedem Schritt. |

> 💡 **Wichtig:** PBP arbeitet zusammen mit [Claude Desktop](https://claude.ai/download). Du wirst an bestimmten Stellen automatisch dorthin weitergeleitet — das ist Teil des Ablaufs. Claude ist dein Gesprächspartner, das Dashboard deine Übersicht.

---

## PBP in Bildern

| ![Stellen mit Scoring](docs/screenshots/03_stellen.png) | ![Bewerbungs-Pipeline](docs/screenshots/04_bewerbungen.png) |
|:--:|:--:|
| *Stellenanzeigen automatisch durchsuchen und mit Score bewerten* | *Bewerbungen verwalten: Pipeline, Status und Nachfassen* |
| ![Kalender](docs/screenshots/06_kalender.png) | ![Statistiken](docs/screenshots/07_statistiken.png) |
| *Termine und Vorstellungsgespräche im Kalender* | *Absagen auswerten: Quoten, Antwortzeiten, Muster* |

<details>
<summary><b>Weitere Ansichten anzeigen</b> — Aufgaben, Profil, Dokumente, Kontakte, Dossier, erster Start, Einstellungen</summary>

<br>

*Aufgaben — Nachfassen, Termine und Todos nach Fälligkeit gruppiert (neu in v1.7.12)*
![Aufgaben](docs/screenshots/05b_aufgaben.png)

*Profil — Berufserfahrung, Skills mit Zeiträumen, Ausbildung*
![Profil](docs/screenshots/02_profil.png)

*Bewerbungs-Dossier — Timeline, Stellendetails und Firmen-Recherche an einem Ort*
![Dossier](docs/screenshots/04b_dossier.png)

*Kontakte — Recruiter, HR und Referenzen mit farbigen Kategorien*
![Kontakte](docs/screenshots/04c_kontakte.png)

*Dokumente — Upload, Verknüpfung und Analyse*
![Dokumente](docs/screenshots/05_dokumente.png)

*Erster Start — So begrüßt dich PBP*
![Willkommen](docs/screenshots/00_willkommen.png)

*Unvollständiges Profil — PBP zeigt dir den nächsten Schritt*
![Profil unvollständig](docs/screenshots/00b_profil_unvollstaendig.png)

*Alles eingerichtet — Dashboard im Normalbetrieb*
![Dashboard vollständig](docs/screenshots/00c_dashboard_vollstaendig.png)

*Einstellungen — Quellen, Erweiterungen, Export & Backup*
![Einstellungen](docs/screenshots/08_einstellungen.png)

*Datenschutz — wo deine Daten liegen und was wohin geht*
![Datenschutz](docs/screenshots/08b_datenschutz.png)

</details>

---

## Warum PBP?

Mal ehrlich: Weißt du, wie dein Lebenslauf auf einen Recruiter wirkt? Auf ein ATS-System? Auf einen Personalberater?

Die meisten Bewerber wissen es nicht. Sie schreiben ihren CV einmal, kopieren das Anschreiben mit minimalen Änderungen und wundern sich über Absagen. Nicht weil sie schlecht sind — sondern weil niemand ihnen ehrlich sagt, was sie besser machen könnten.

**PBP ist dieser ehrliche Sparringspartner.**

Und zugleich ein kostenloser Bewerbungsmanager: Bewerbungen verwalten, den Bewerbungsstatus verfolgen, Absagen auswerten — alles an einem Ort statt in einer wachsenden Excel-Liste. Wer nur eine übersichtliche Alternative zur Bewerbungsübersicht in Excel sucht, kann PBP auch komplett ohne KI nutzen.

### Was PBP anders macht

PBP ist kein Tool, das alles für dich erledigt und du drückst nur auf "Absenden". PBP gibt dir **Perspektive, Struktur und ehrliches Feedback** — die Entscheidungen triffst du.

| Du fragst dich... | PBP hilft dir so |
|-------------------|-----------------|
| *"Ist mein Lebenslauf gut genug?"* | **3-Perspektiven-Analyse** — lass deinen Lebenslauf prüfen: Wie wirkt er auf einen Personalberater, ein ATS-System und einen Recruiter? |
| *"Passe ich überhaupt auf die Stelle?"* | **Fit-Analyse** — Punkt-für-Punkt-Vergleich Profil vs. Stelle. Ehrlich, nicht schöngerechnet. |
| *"Was fehlt mir noch?"* | **Skill-Gap-Analyse** — Welche Fähigkeiten verlangt die Stelle, die du (noch) nicht hast? |
| *"Was soll ich im Interview sagen?"* | **Interview-Simulation** — so kannst du jedes Vorstellungsgespräch vorbereiten: Claude spielt den Interviewer auf Basis der echten Stelle. |
| *"Wie verhandle ich das Gehalt?"* | **Gehaltsverhandlung** — Markdaten, Strategie, konkrete Argumente. |

### Und wenn du mehr willst

- **35 Jobportale konfiguriert** (~8 davon liefern aktuell zuverlaessig) — die grosse oeffentliche Jobboerse, mehrere Stellenmaerkte und Bewerbermanagement-Systeme, dazu Projektboersen fuer Freelancer; die uebrigen laufen ueber die Chrome-Extension oder sind sichtbar als defekt markiert, damit kein falscher Eindruck von Abdeckung entsteht ([welche genau, steht im Wiki](https://github.com/MadGapun/PBP/wiki/Jobportale))
- **Angepasste Lebensläufe** — Für jede Stelle ein CV, in dem Skills nach Relevanz sortiert sind
- **E-Mail-Import** — Drag & Drop deine Firmen-Mails rein. Status und Termine werden automatisch erkannt
- **Kalender** — Grafisches Grid mit Kategorien, Kollisionserkennung und .ics-Export
- **Bewerbungsstatus verfolgen** — Pipeline mit Timeline, Notizen, Follow-ups und Statistiken
- **Aufgaben-Übersicht** — Nachfassen, Termine und Todos nach Fälligkeit an einem Ort (v1.7.12)
- **Scoring-Regler** — Konfiguriere, was dir wichtig ist. PBP sortiert automatisch

> 📖 **Alle Features im Detail:** [Wiki → Dashboard](https://github.com/MadGapun/PBP/wiki/Dashboard) · [Workflows](https://github.com/MadGapun/PBP/wiki/Workflows) · [MCP-Tools](https://github.com/MadGapun/PBP/wiki/MCP-Tools) · [Jobportale](https://github.com/MadGapun/PBP/wiki/Jobportale)

### Einfach reden — keine Befehle nötig

Du musst keine Kommandos kennen. **Du redest einfach mit Claude, wie mit einem Menschen.**

> *"Schau mal über meinen Lebenslauf"*
> *"Ich hab ne Absage bekommen, was mach ich falsch?"*
> *"Bereite mich auf das Interview morgen vor"*
> *"Suche was mit Python in Hamburg"*

**🎙️ Oder einfach sprechen:** Drück aufs Mikrofon in Claude Desktop und rede. Interview-Training, Profilerstellung, Feedback — alles geht auch per Sprache.

---

## Voraussetzungen

PBP läuft über [Claude Desktop](https://claude.ai/download) — die kostenlose App von Anthropic für Windows und macOS. Unter Linux funktioniert alternativ [Claude Code](https://claude.com/claude-code) (CLI) mit MCP-Support.

| | **Free** | **Pro** ⭐ empfohlen | **Max** |
|---|----------|---------------------|---------|
| **Preis** | $0 | **$20/Monat** | $100–200/Monat |
| **Was geht mit PBP** | Reinschnuppern, CV analysieren lassen, einzelne Fragen stellen | **Alles.** Tägliche Nutzung: Jobsuche, Bewerbungen, Interview-Training, Coaching | Für Power-User mit stundenlangen Sessions |
| **Nachrichten** | ~20 pro Tag | ~45 pro 5 Stunden (5× mehr) | 5×–20× mehr als Pro |
| **MCP-Tools (PBP)** | ✅ Funktioniert | ✅ Funktioniert | ✅ Funktioniert |
| **Mikrofon/Sprache** | ✅ Ja | ✅ Ja | ✅ Ja |

> **Vorab, ganz offen:** Wir — die Macher von PBP — haben keinen Vertrag, keine Kooperation und keinen Verdienst durch Anthropic (die Firma hinter Claude). Wir verdienen nichts an diesem Tool. PBP ist ein Herzensprojekt, Open Source, kostenlos.
>
> Trotzdem wollen wir ehrlich sein: Die KI dahinter (Claude) ist ein Service von Anthropic, und der hat Grenzen.
>
> Stell dir PBP vor wie ein Auto mit eingebautem Navi, das du geschenkt bekommst. **Fahren kannst du sofort** — kostenlos. Alles funktioniert, keine Begrenzung von unserer Seite. Aber nach ein paar Kilometern musst du an die Tankstelle, warten bis der Tank wieder voll ist, und dann weiterfahren. So funktioniert der Free-Plan: Du kommst vorwärts, aber in Etappen. Claude wird fürs Denken bezahlt — nicht von uns, sondern von Anthropic.
>
> **Mit Claude Pro ($20/Monat) tankst du voll** — und fährst den ganzen Tag ohne Pause. Jobsuche, Bewerbungen schreiben, Interview-Training, Coaching — alles in einer Session, so viel du willst.
>
> Zum Vergleich: Ein einziger professioneller Bewerbungscheck kostet oft 50–150 €. Mit PBP + Claude Pro hast du einen persönlichen Bewerbungs-Coach für 20 Dollar im Monat — so oft du willst, so lange du willst.
>
> **Unser Rat:** Fang kostenlos an. Installieren, Lebenslauf hochladen, analysieren lassen. Wenn du merkst, dass es dir was bringt — und das wirst du — dann lohnt sich der Volltank.

### Das Besondere

- **Einfach reden — oder sprechen.** Kein Formular, keine Befehle. Tippen oder Mikrofon drücken — Claude versteht beides.

> **&#9888;&#65039; Deine Daten bleiben auf deinem Rechner.** PBP speichert alles in einer einzigen lokalen Datenbankdatei auf deiner Festplatte (`pbp.db`). **Kein Server, kein Account, kein Cloud-Speicher.** Wenn du die Datei löschst, ist alles weg. Wenn du sie kopierst, hast du ein komplettes Backup. So einfach. **Deine Bewerbungsdaten verlassen niemals deinen Computer.**

- **Festanstellung & Freelance.** Egal ob fester Job oder Projektaufträge — PBP unterstützt beides.
- **Multi-Profil.** Mehrere Benutzer auf einem Rechner? Kein Problem — jedes Profil hat eigene Daten.
- **Open Source & kostenlos.** PBP selbst kostet nichts. Du brauchst nur Claude Desktop (Free oder Pro).
- **Tagesimpulse mit Glueckskeks-Charakter.** 169 kuratierte Sprueche, einer pro Tag, kontextbezogen. Manche sind klar, andere lesen sich beim ersten Mal wie billig uebersetzte Bambusstaebchen-Weisheiten — da brauchst du zwei Schluck Kaffee, dann ergibt's Sinn. Oder auch nicht. *It's not a bug, it's a feature.*

---

## Schnellstart

### Windows (Empfohlen)

1. **Lade die [neueste Version](https://github.com/MadGapun/PBP/releases/latest) herunter** — auf der Release-Seite unter *Assets* → **„Source code (zip)"**
2. **Entpacke** das ZIP in einen Ordner (z.B. `C:\PBP`). Darin liegt ein Unterordner `PBP-...` — dort hinein wechseln.
3. **Doppelklicke `INSTALLIEREN.bat`** — fertig!

> **Voraussetzungen:** Windows 10/11 (64-Bit), Internetverbindung, [Claude Desktop](https://claude.ai/download)

### macOS

1. **Einmalig vorab: Python 3.11+ installieren** — am einfachsten mit dem [Installer von python.org](https://www.python.org/downloads/) (Doppelklick), alternativ `brew install python@3.12`
2. **Lade die [neueste Version](https://github.com/MadGapun/PBP/releases/latest) herunter** (*Assets* → „Source code (zip)") und **entpacke** sie (im ZIP liegt ein Unterordner `PBP-...`)
3. **Doppelklicke `INSTALLIEREN.command`**

> Falls macOS warnt („kann nicht geoeffnet werden"): **Rechtsklick** auf `INSTALLIEREN.command` → *„Oeffnen"* → nochmal *„Oeffnen"*.
> **Voraussetzungen:** macOS 12+, Python 3.11+, [Claude Desktop](https://claude.ai/download)

### Linux

```bash
git clone https://github.com/MadGapun/PBP.git && cd PBP && bash installer/install.sh
```

> 📖 **Detaillierte Anleitungen, Claude Desktop Config und Fehlerbehebung:** [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation)

### Erste Schritte

Öffne Claude Desktop und sage:

> **"Starte die Ersterfassung"**

Claude führt dich durch ein lockeres Gespräch (ca. 10-15 Minuten) und baut dein Profil auf.
**Schneller geht's mit Dokumenten:** Lade deinen Lebenslauf als PDF oder DOCX hoch — PBP extrahiert die Daten automatisch.

> 📖 **Schritt-für-Schritt-Anleitung:** [Wiki → Erste Schritte](https://github.com/MadGapun/PBP/wiki/Erste-Schritte)

---

## Auf einen Blick

| | |
|---|---|
| **Plattformen** | Windows, macOS, Linux |
| **MCP-Tools** | 218 Tools in 11 Modulen (Stable: 205) |
| **Workflows** | 25 gefuehrte Workflows (Prompts) |
| **Jobportale** | 35 Quellen konfiguriert, ~8 aktuell zuverlaessig liefernd (Festanstellung und Freelance); defekte sichtbar markiert, mit Chrome-Workaround |
| **Dashboard** | 10 Tabs: Dashboard, Profil, Stellen, Bewerbungen, Kontakte, Dokumente, Aufgaben, Kalender, Statistiken, Einstellungen |
| **Datenbank** | SQLite (WAL), Schema v48 (Stable) · v52 (Beta) |
| **Tests** | 2199 bestanden |

### Typed IDs (v1.7.0, #505)

PBP-IDs haben ab v1.7.0 sichtbare Praefixe — du erkennst auf einen Blick,
um was fuer eine Entitaet es geht:

| Praefix | Entitaet | Beispiel |
|---|---|---|
| `APP-` | Bewerbung (Application) | `APP-42061e46` |
| `JOB-` | Stelle (Job) | `JOB-2b19d4c6` |
| `DOC-` | Dokument | `DOC-d60ac54b` |
| `MTG-` | Termin/Meeting | `MTG-7f33ac90` |
| `CON-` | Kontakt (v1.7.0 #563) | `CON-5b8a2d11` |

**Nicht-breaking:** Tools akzeptieren weiterhin nackte 8-Hex-IDs ohne
Praefix (`42061e46`). Die Praefixe erscheinen in Listen-/Detail-Antworten
und in der UI; intern bleibt die ID gleich.

> 📖 **Technische Details:** [Wiki → Architektur](https://github.com/MadGapun/PBP/wiki/Architektur) · [MCP-Tools](https://github.com/MadGapun/PBP/wiki/MCP-Tools) · [Jobportale](https://github.com/MadGapun/PBP/wiki/Jobportale)

---

## Roadmap

> **v1.7 ist Stable** — aktuell **v1.7.12** (11. August 2026), mit wöchentlichen Pflege-Releases seit Juni.
> **Nächster Zyklus: v1.8** — die Beta-Reihe läuft (aktuell v1.8.0-beta.11): Plugin-Plattform ([#504](https://github.com/MadGapun/PBP/issues/504)), Thunderbird-Add-on, Newsletter-Ingest, Komponenten-Framework mit Auto-OCR. Strategische Übersicht im [Master-Plan](https://github.com/MadGapun/PBP/wiki/Master-Plan).

## Changelog

Die letzten drei Stable-Releases — vollständige Historie im [CHANGELOG.md](CHANGELOG.md) und auf der [Releases-Seite](https://github.com/MadGapun/PBP/releases):

- **v1.7.12** (11.08.2026) — Große Pflege-Welle: Aufgaben-Bereich vollwertig bedienbar, Interview-Nachbereitung, Scoring-Fairness (Firmen-Werbeabsätze zählen weniger), WAL-Hygiene, Elwosa-Feinschliff. 15 Issues in einer Welle.
- **v1.7.11** (06.08.2026) — Stille Ausfälle behoben: tote Bundesagentur-API (v4→v6), blockierter Lernmodus, still verunglückte Dokument-Verknüpfungen. Fehler, die sich als Erfolg tarnten.
- **v1.7.10** (24.07.2026) — Stabilisierungswelle: Kalibrierungs-Backtest, ehrliche Statistik (Quote roh + bereinigt), Kontakt- und Vermittler-Historie, Lern-Fundament mit Nutzerbestätigung.

---

## FAQ

**Brauche ich ueberhaupt eine KI?**
Nein! PBP ist ein eigenstaendiges Verwaltungstool. Ohne Claude kannst du: Bewerbungen verwalten, Dokumente organisieren, Termine planen, Statistiken auswerten, E-Mails importieren und Follow-ups tracken. Claude ist ein optionaler Sparringspartner — er kann dir Feedback geben, Anschreiben formulieren oder Interviews simulieren. Aber die Kernfunktionen laufen komplett ohne KI.

**Brauche ich einen Claude Pro Account?**
Nein — PBP funktioniert mit jedem Claude Desktop Account, auch dem kostenlosen. Ein Pro-Account hat hoehere Nutzungslimits, was bei vielen Jobsuchen hilfreich sein kann.

**Werden meine Daten in die Cloud geschickt?**
Deine Profildaten, Bewerbungen und Dokumente bleiben lokal auf deinem Rechner (SQLite). Wenn du Claude nutzt (Gespraech, Anschreiben, Fit-Analyse), werden die relevanten Daten an Claude gesendet — wie bei jeder normalen Claude-Konversation.

**Kann ich PBP ohne Jobportale nutzen?**
Ja! Du kannst PBP auch nur fuer Profilerstellung, Lebenslauf-Export und Bewerbungstracking nutzen, ganz ohne Stellensuche.

### Browser nicht gefunden / Chrome nicht verbunden?

1. Microsoft Edge schliessen (auch im System-Tray pruefen)
2. Google Chrome manuell oeffnen falls nicht offen
3. PBP-Suche erneut starten

Hintergrund: PBP versucht den Standard-Browser zu steuern. Wenn Edge geoeffnet ist, kann PBP sich mit Edge statt Chrome verbinden und scheitert dann.

> 📖 **Weitere Fragen und Troubleshooting:** [Wiki → FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)

---

## Lizenz

[MIT License](LICENSE) — Markus Birzite

---

## Credits

**Markus Birzite** — Idee, Konzept, Architektur & Projektleitung
> Hat PBP erdacht, die Vision definiert und das Projekt von Anfang an geleitet. Treibt Richtung, Priorisierung und Qualität.

**Claude** (Anthropic) — Entwicklung, Code, Dokumentation, Tests
> Hauptentwickler seit v0.1.0. Hat den Großteil des Codes geschrieben — Backend, Frontend-Integration, Scraper, Tests, Installer, Dashboard, E-Mail-Service. Jeder Commit trägt seinen Namen. Intern: "der Onkel".

**ChatGPT** (OpenAI) — Bewertung, Analyse & Qualitätssicherung
> Die neutrale Instanz im Team. Bewertet Ergebnisse von Claude und Codex, liest jede Analyse quer, hinterfragt Annahmen und stellt sicher, dass nichts schöngeredet wird. Intern: "die Mama".

**Codex** (OpenAI) — Code-Analyse, Recovery & Bugfixes
> Kommt ins Spiel wenn größere Code-Analysen, Refactorings oder Recovery-Aufgaben anstehen. Hat u.a. das Frontend-Recovery (v0.25.2) durchgeführt und liefert zuverlässig Fixes für komplexe Bugs. Intern: "die Tante".

**Toms ([@Koala280](https://github.com/Koala280))** — React-Frontend, Testing & Sparringspartner
> Hat das React 19 + Vite + Tailwind Frontend beigesteuert (v0.23.0, 7.877 Zeilen), das System ausgiebig getestet und als Diskussionspartner die UX mitgeformt. AI & Data Science Student.

**ELWOSA** — Fundament, Projektmanagement & Dateninfrastruktur
> Die allererste PBP-Version lief direkt auf der ELWOSA-Datenbank — dort wurde der Prototyp entwickelt und erprobt, bevor er zur eigenständigen Anwendung umgebaut wurde. ELWOSA liefert bis heute Projektmanagement, Server-Infrastruktur, CI/CD-Prozesse und Entwicklungsmethodik.

### Third-Party-Bibliotheken

- **[python-jobspy](https://github.com/speedyapply/JobSpy)** (MIT) — seit v1.6.0-beta.3 als optionale Scraper-Bibliothek fuer mehrere grosse Jobportale eingebunden (#490). Kein API-Key, keine Kosten.

---

## PBP und ELWOSA

PBP entsteht auf [ELWOSA](https://www.elwosa.de), der Arbeitsplattform für Menschen und KI. Dort liegen Plan, Stories und Wiki nach demselben Definition-of-Done-Prinzip, das auch dieses Repository führt: Eine Position gilt erst als fertig, wenn Code, Tests und Dokumentation zusammen abgeschlossen sind. Was hinter der Plattform steckt und warum es sie gibt, steht unter [elwosa.de/idee](https://www.elwosa.de/idee).

---

<p align="center">
<a href="https://paypal.me/birzite"><img src="https://img.shields.io/badge/☕_Kaffee_spendieren-PayPal-blue?style=for-the-badge" alt="Kaffee spendieren"></a>
<br><sub><a href="https://www.elwosa.de">An <b>ELWOSA</b> Project</a></sub>
<br><sub><b>Deutsch</b> | <a href="README.en.md">English</a></sub>
</p>
