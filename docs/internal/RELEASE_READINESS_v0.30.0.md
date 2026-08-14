# Release Readiness v0.30.0

Stand: 2026-03-21
Basis: GitHub Release `v0.30.0` vom 2026-03-20

## Kurzurteil

PBP `v0.30.0` wirkt technisch wie ein belastbarer Release-Kandidat.

Meine Freigabe-Einschaetzung:
- `Ja, freigabefaehig`, wenn der kleine Metadaten-/Versions-PR vor dem naechsten Release mitgenommen wird.
- `Kein funktionaler Release-Blocker` aus Code, Build, Tests oder offenen GitHub-Issues sichtbar.
- `Dokumentations- und Release-Hygiene` ist der groesste Restpunkt, nicht die Produktfunktion.

## Was ich verifiziert habe

- GitHub Latest Release: `v0.30.0`, veroeffentlicht am `2026-03-20`
- Voller Testlauf lokal: `317 passed, 4 skipped`
- Frontend Production Build: erfolgreich via `pnpm run build:web`
- Offene GitHub-Issues zum Analysezeitpunkt: keine klaren offenen Bug-Blocker, hauptsaechlich Roadmap-/Feature-Themen
- Oeffentliche Kern-Dokumente gelesen: `README.md`, `CHANGELOG.md`, `AGENTS.md`, `DOKUMENTATION.md`, `ZUSTAND.md`

## Starke Seiten

### Produkt

- PBP ist inzwischen klar mehr als ein Experiment: Profilaufbau, Jobsuche, Tracking, Dokumente, E-Mail-Import und Coaching greifen sinnvoll ineinander.
- Die React-Oberflaeche fuehlt sich wie ein echtes Arbeitswerkzeug an, nicht wie ein Admin-Panel.
- Multi-Profil, lokale Datenhaltung und deutsche Nutzerfuehrung sind klare Produktstaerken.

### Technik

- Testbasis ist fuer ein lokal-first Produkt gut: `317` gruene Tests plus Browser-Smokes.
- Frontend-Build und Python-Testlauf sind reproduzierbar grün.
- Architektur ist fuer die Groesse des Projekts nachvollziehbar: MCP, Services, Dashboard, Scraper, Export.
- Der aktuelle offene GitHub-Issue-Bestand ist kein Warnsignal fuer einen instabilen Release.

### Oeffentliche Dokumentation

- `README.md` ist inhaltlich stark: klare Nutzenargumentation, Screenshots, Schnellstart, FAQ, rechtliche Einordnung.
- Die FAQ beantwortet reale Nutzerfragen statt nur Entwicklerfragen.
- Der GitHub-Auftritt wirkt in `README.md` deutlich reifer als in frueheren Staenden.

## Release-relevante Befunde

### Vor Release noch sauber mitnehmen

Diese Punkte sind klein, aber oeffentlich sichtbar oder technisch relevant:

1. Interne Paketversion war nicht synchron
   - `pyproject.toml` stand auf `0.30.0`
   - `src/bewerbungs_assistent/__init__.py` stand noch auf `0.27.0`
   - Folge: Server-Log und Installer-Versionscheck konnten falsche Versionen melden

2. Credits-Dialog im Frontend zeigte alte Version
   - `frontend/src/App.jsx` zeigte noch `v0.26.0`

3. `AGENTS.md` enthielt harte Faktenfehler
   - falscher Dashboard-Port (`5173` statt `8200`)
   - falsche Quellenzahl (`12` statt `17`)
   - Service-Layer unvollstaendig beschrieben

Diese Punkte habe ich in diesem Analyse-Branch direkt korrigiert.

### Kein Blocker, aber klar offen

1. Sekundaerdokumentation haengt deutlich hinterher
   - `DOKUMENTATION.md` steht noch auf `v0.29.0` und nennt `5173`, `9 Quellen`, `5 Tabs`
   - `ZUSTAND.md` steht noch auf `v0.16.0`
   - `docs/architecture.md` und `docs/codex_context.md` referenzieren ebenfalls alte Architektur-/Portstaende

2. Versionshistorie auf GitHub ist fuer Aussenstehende verwirrend
   - Es gibt einen veroeffentlichten Release `v1.0.0` vom `2026-03-02`
   - Gleichzeitig ist der aktuelle Hauptstrang bei `v0.30.0`
   - Ohne Erklaerung wirkt das rueckwaerts versioniert

3. Frontend-Bundle ist gross
   - aktueller Build produziert einen Chunk von rund `832 kB` vor gzip
   - kein Release-Blocker, aber ein klarer Optimierungspunkt fuer spaetere Ladezeiten

4. Einige Deprecation-Warnungen sind vorhanden
   - `fpdf2`-Warnungen in `export_report.py`
   - `websockets`-Warnungen im Testlauf
   - ebenfalls kein Blocker, aber guter Kandidat fuer einen kleinen Nachbereitungs-Sprint

## Bewertung der GitHub-/Aussenwirkung

## README

Positiv:
- sehr gute Produktpositionierung
- starker Schnellstart
- Screenshots fuer alle sichtbaren Hauptbereiche
- FAQ und rechtliche Hinweise vorhanden

Kritisch:
- die README ist fuer eine GitHub-Landing-Page sehr lang
- sie vereint Landing-Page, Handbuch, Tool-Referenz, Changelog-Auszug und Credits in einer Datei

Empfehlung:
- `README.md` als oeffentliche Hauptseite behalten
- mittelfristig aufteilen in:
  - `README.md` = Nutzen, Screenshots, Schnellstart, Kern-FAQ
  - `docs/USER_GUIDE.md` = Bedienung im Detail
  - `docs/FAQ.md` oder `docs/TROUBLESHOOTING.md`
  - `docs/architecture.md` = nur Technik

## Anleitung / FAQ / Hilfe

Positiv:
- die Hilfetexte im Produkt sind hilfreich und nah an realen Aufgaben
- die README-FAQ ist fuer Endnutzer geschrieben

Verbesserungspotenzial:
- eine explizite Troubleshooting-Sektion fehlt als eigener Einstieg
- typische Themen wie `Claude sieht PBP nicht`, `Dashboard startet nicht`, `LinkedIn/XING Login`, `Build/Update-Probleme` sollten gesammelt an einem Ort stehen

## Releases / Changelog / Repo-Hygiene

Positiv:
- GitHub Releases von `v0.22.0` bis `v0.30.0` zeigen hohe Bewegung und sichtbaren Fortschritt
- `CHANGELOG.md` ist vorhanden und aktiv gepflegt

Kritisch:
- die Release-Historie ist durch `v1.0.0` nach aussen erklaerungsbeduerftig
- einige Nebendokumente ziehen nicht mit dem Changelog mit

## GitHub-Issues, die ich dazu angelegt habe

- `#148` Dokumentationsdrift: AGENTS/DOKUMENTATION/ZUSTAND widersprechen `v0.30.0`
- `#149` Release-Historie klaeren: veroeffentlichtes `v1.0.0` vor aktuellem `v0.30.0`

## Empfehlung zur Freigabe

### Freigabe jetzt?

`Ja`, wenn der kleine Fix-PR aus diesem Analyse-Branch gemerged wird.

Warum ich das so bewerte:
- die Kernfunktion ist verifiziert
- es gibt keine sichtbaren offenen Bug-Blocker
- die groessten Probleme liegen in Metadaten und Dokumentation, nicht in der Anwendungslogik

### Was ich vor dem naechsten Release noch tun wuerde

1. Den kleinen Fix-PR mergen
   - Paketversion synchron
   - Credits-Version synchron
   - AGENTS-Hardfacts korrigiert

2. Bei Release-Notes oder Changelog einen kurzen Hinweis auf die Versionshistorie geben
   - warum `v1.0.0` existiert, obwohl jetzt `v0.30.0` aktuell ist

3. Danach einen separaten Doku-Sync-Sprint machen
   - `DOKUMENTATION.md`
   - `ZUSTAND.md`
   - `docs/architecture.md`
   - `docs/codex_context.md`

## Naechste sinnvolle Optimierungen

Nach der Freigabe wuerde ich priorisieren:

1. Doku konsolidieren und kuerzen
2. Troubleshooting/FAQ als eigene Seite auslagern
3. Frontend code-splitting pruefen
4. Deprecation-Warnungen in Export/Websocket-Stack abbauen
5. Release-Politik fuer Tags/Releases einmal schriftlich festhalten
