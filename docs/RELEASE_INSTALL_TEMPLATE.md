# Release-Install-Template

Standard-Installations-Sektion fuer **jeden** zukuenftigen Release. Ans
Ende des CHANGELOG-Eintrags + in die GitHub-Release-Notes (via
`gh release create --notes-file` ODER `gh release edit --notes-file`).

User-Wunsch v1.6.4: „Viele normale User wissen nicht was Source code
bedeutet" — daher ZIP-Pfad zuerst, klare Schritt-fuer-Schritt-Anleitung,
Doppelklick als primaere Aktion.

**Anpassen pro Release:** nur die Versionsnummer im ZIP-Link
(`refs/tags/vX.Y.Z.zip`).

---

```markdown
### 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

#### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-X.Y.Z.zip](https://github.com/MadGapun/PBP/archive/refs/tags/vX.Y.Z.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

#### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

#### Linux

```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
```

#### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

#### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)
```
