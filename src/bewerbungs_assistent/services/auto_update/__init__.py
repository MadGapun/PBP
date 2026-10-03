"""Auto-Update (#1093, v1.8): Updates im Hintergrund vorbereiten, beim naechsten Start umschalten.

Die Bauform in einem Satz: neue Fassungen landen in einem eigenen Ordner
(`app/versions/<version>`), ein kleiner Startbaustein (`bewerbungs_assistent_boot`)
waehlt beim Start die aktuelle, und nichts wird je ueber laufende Dateien kopiert.

Module (jedes beantwortet eine Frage):

* `layout`        — wo liegt was (Programmordner, Fassungen, Statusdatei)
* `fassung`       — was ist eine gueltige Versionsnummer und welche ist neuer
* `schluessel`    — welchen oeffentlichen Schluesseln vertraut diese Fassung
* `ed25519`       — Signaturen pruefen und erzeugen (RFC 8032)
* `manifest`      — was steht im Update-Archiv und passt es zu diesem Rechner
* `quelle`        — woher darf installiert werden (fest im Code, nie eine Einstellung)
* `pruefung`      — Pruefsumme und Signatur
* `entpacken`     — sicher entpacken
* `abhaengigkeiten` — fehlende Pakete erkennen und in die neue Fassung legen
* `installation`  — der ganze Lauf: laden, pruefen, entpacken, umschalten
* `zustand`       — Statusdatei (Start bestaetigt, Rueckfall) und Verlauf
* `aufraeumen`    — alte Fassungen, Reste, Belegung durch laufende Prozesse
* `lauf`          — Hintergrund-Job, Stufen und Zeitpunkt

Die Quelle der Installation ist eine Konstante im Code. Die Einstellung
`update_quellen` darf die PRUEFUNG umlenken (wo PBP nachsieht, ob es etwas
Neues gibt), nie die INSTALLATION: sonst genuegte ein geaenderter Wert in der
Datenbank fuer eine Codeausfuehrung (Akzeptanzkriterium 6 in #1093).
"""
