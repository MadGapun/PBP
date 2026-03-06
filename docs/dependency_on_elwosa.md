# PBP Abhaengigkeit von ELWOSA

## Zusammenfassung

PBP ist ein **eigenstaendiges Projekt** ohne Code-Abhaengigkeit von ELWOSA.
Die Verbindung ist rein infrastrukturell.

---

## Art der Abhaengigkeit

### Was PBP von ELWOSA nutzt

1. **Hosting**: PBP wurde auf dem ELWOSA-Server (192.168.178.200) entwickelt.
   Der Quellcode liegt unter `/home/chatgpt/pbp/bewerbungs-assistent/`.

2. **Release-Distribution**: PBP-Release-ZIPs werden ueber den ELWOSA
   Voice-Backend Static-Server ausgeliefert:
   `https://192.168.178.200:8100/static/PBP-Bewerbungs-Assistent-v*.zip`

3. **GitHub**: PBP hat ein eigenes Repository: https://github.com/MadGapun/PBP

### Was PBP NICHT von ELWOSA nutzt

- **Kein gemeinsamer Code**: PBP importiert nichts aus ELWOSA.
- **Keine gemeinsame Datenbank**: PBP nutzt lokale SQLite, ELWOSA nutzt PostgreSQL.
- **Kein gemeinsames Backend**: PBP ist ein eigenstaendiger MCP-Server.
- **Kein gemeinsames Frontend**: PBP hat ein eigenes Web-Dashboard.

---

## Kann PBP ohne ELWOSA laufen?

**Ja, vollstaendig.**

PBP ist als Windows-Anwendung konzipiert (MCP-Server fuer Claude Desktop).
Es kann auf jedem Rechner mit Python 3.11+ installiert und betrieben werden.
Der ELWOSA-Server wird nur fuer die Entwicklung und Release-Distribution benoetigt.

### PBP standalone installieren

```bash
# Von GitHub klonen
git clone https://github.com/MadGapun/PBP.git
cd PBP

# Installieren
pip install -e ".[all]"

# Starten
bewerbungs-assistent
```

Oder unter Windows: `INSTALLIEREN.bat` ausfuehren.

---

## Gemeinsame Geschichte

PBP entstand als Nebenprojekt waehrend der ELWOSA-Entwicklung.
Markus brauchte ein Tool fuer die Jobsuche und hat es als MCP-Server
fuer Claude Desktop gebaut. Die Entwicklungsumgebung war der ELWOSA-Server,
aber PBP wurde von Anfang an als eigenstaendiges Projekt konzipiert.

### Timeline
- **Feb 2026**: Erste Version (v0.1.0) auf ELWOSA-Server entwickelt
- **Feb-Maerz 2026**: Iterative Entwicklung bis v0.11.0
- **Maerz 2026**: Alle Features und Optimierungen abgeschlossen
- **GitHub**: 15 Releases von v1.0.0 bis v0.11.0

---

## Fuer Codex/KI-Assistenten

Wenn du an PBP arbeitest, brauchst du keinen Zugriff auf ELWOSA.
Das PBP-Repository ist in sich geschlossen.

Wenn du an ELWOSA arbeitest, musst du PBP nicht kennen.
Die PBP-ZIPs unter `voice_backend/static/` sind nur statische Dateien.

---

*Stand: 06.03.2026*
