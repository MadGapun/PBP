# Entwurf: CHANGELOG-Eintrag für den optionalen API-Weg der KI (#1236)

> **Kein Teil des CHANGELOG.** Der Kopf von `CHANGELOG.md` gehört der Version, die gerade veröffentlicht ist: Elwosa liest ihn für „Was ist
> neu“ (`services/elwosa_provider._parse_changelog_kopf`) und `release_check.py` verlangt dort die aktuelle Version. Der Eintrag kommt GANZ
> OBEN in `CHANGELOG.md`, sobald die Version angehoben wird, die den API-Weg ausliefert (nach 1.8.0, nie in die 1.7-Linie). Zahlen und
> Datum beim Release einsetzen, danach diese Datei löschen.
> Stand des Entwurfs: 16.10.2026, Zweig `feat/api-weg-1236`.

---

## [VERSION] - TT.MM.2026 — Ein eigener API-Weg für die KI (optional)

<!-- anwender -->
Wer ein API-Guthaben bei Anthropic hat, kann PBP jetzt gleichartige Massenaufgaben über die Anthropic-API erledigen lassen statt über die lokale KI: Stellen mit dem Profil abgleichen und Anzeigentexte auf Vollständigkeit prüfen. Das ist ab Werk **aus**. Ohne eigenen Schlüssel sieht PBP genau so aus wie vorher. Mit Schlüssel erscheint unter Einstellungen › Lokale KI eine Karte: jede Aufgabe gibst du einzeln frei, **vorher steht dort, welche Angaben dann den Rechner verlassen**, und ein Budget in US-Dollar setzt eine harte Obergrenze.
<!-- /anwender -->

Der Weg ist für Fortgeschrittene gedacht, die ein befristetes oder bezahltes API-Guthaben nutzen wollen. Die lokale KI (Ollama) bleibt der Normalfall, und Claude Desktop erledigt weiter alles Kreative (Anschreiben, Coaching). **Das ist die einzige Stelle, an der PBP selbst Angaben an einen Cloud-Dienst schickt** (sonst nur Claude Desktop, wenn du mit Claude arbeitest); sie ist deshalb eine ausdrückliche, sichtbare Ausnahme von „läuft komplett lokal“.

### Added

- **Optionaler API-Weg `Backend.API` (#1236).** Nicht zu verwechseln mit `Backend.CLAUDE` (dort erledigt Claude Desktop die Aufgabe). Zwei Aufgaben laufen darüber: `match_job_to_skills` (die Aufgabe hinter „Stellen automatisch aussortieren“) und `validate_job_quality` (Qualitätsprüfung der Anzeigentexte). Mails, Kontakte und Stichwörter bewusst nicht: dort stehen Namen Dritter.
- **Vorgabe AUS, je Aufgabe einzeln, mit Feldliste.** Die Freigabe verlangt einen Schlüssel und eine Bestätigung und zeigt vorher, welche Angaben hinausgehen und welche nicht. Nur diese Felder verlassen den Rechner, auch wenn ein Aufrufer mehr in die Nutzlast legt. Die Firma früher aussortierter Stellen wird in den Beispielen durch „[Firma]“ ersetzt, auch als Wort im Titel (der Name ohne Rechtsform, ab drei Zeichen; der Name einer anderen Firma im Titel bleibt stehen). Der Grund einer Aussortierung geht nur als Kennung wie „zu_junior“ hinaus, eigener Text wird zu „sonstiges“. Dazu kommen das heutige Datum und die Uhrzeit.
- **Der Schlüssel steht nur in der Umgebungsvariable `PBP_ANTHROPIC_API_KEY`.** PBP speichert ihn nirgends (nicht in der Datenbank, nicht in Sicherung, Export, Log, Telemetrie, Fehlermeldung oder Bericht); jeder Text, der hinausgeht oder hereinkommt, geht durch eine Schwärzung. Ein Test fährt den ganzen Weg mit einem Testdoppel, das den Schlüssel in jeder Fehlermeldung wiederholt, und sucht ihn danach in sieben Kanälen, ganz und in Stücken.
- **Budget mit harter Grenze.** Ohne Budget kein Aufruf. Vor jedem Aufruf rechnet PBP den schlimmsten Fall (geschätzte Eingabe plus volle Antwortlänge) und sendet nicht, wenn er die Grenze überschritte; laufende Aufrufe zählen mit. Gebucht wird, was die Antwort in `usage` meldet; fehlt es, wird der schlimmste Fall gebucht und als „geschätzt“ gezeigt. Ein Modell ohne Preis benutzt PBP nicht. Scheitert das Speichern des Verbrauchs (Datenbank gesperrt oder voll), zählt der Betrag im Speicher weiter gegen das Budget, der Weg ruht, und der nächste Schreibvorgang holt ihn nach. Ein Zeitablauf nach dem Senden bucht den schlimmsten Fall als „geschätzt“ (die API kann trotzdem gerechnet haben). Die Grenze gilt je Prozess: laufen der Claude-Server und das Dashboard gleichzeitig, kann sie um eine Anfrage überschritten werden (Bruchteile eines Cents).
- **Modelle und Preise sind Konfiguration** (`content/api_modelle.json`, Stand 16.10.2026): Vorgabe ist das günstigste Modell (Claude Haiku 5.5), wählbar ist auch Claude Sonnet 5.5. Die Anfrage folgt der Dokumentation: kein `temperature`/`top_p`/`top_k` (die neuen Modelle weisen sie ab), das Denken wird je Modell so abgeschaltet, wie es dokumentiert ist.
- **Fehlerbild.** Ungültiger Schlüssel, Guthaben leer, Limit, Überlastung, Zeitüberschreitung, kein Netz, abgelehnte Anfrage: je ein eigener Grund in Klartext. Höchstens eine Wiederholung bei 429 und 5xx; danach ruht der Weg eine Weile (kurz bei Netz und Limit, lang bei Schlüssel und Guthaben), damit nicht jede Stelle denselben Fehler abholt. Drei bezahlte Fehlschläge in Folge (leere, unlesbare, verweigerte oder vom Parser abgelehnte Antworten) lassen den Weg ebenfalls kurz ruhen. Ein Schlüssel mit Sonderzeichen (Anführungszeichen, Zeilenumbruch) wird als solcher benannt und nie gesendet. Die Aufgabe läuft dann lokal weiter, sonst bei Claude, und der Grund steht in der Antwort.
- **Karte unter Einstellungen › Lokale KI** (nur mit Schlüssel, Freigabe oder Verbrauch): Schlüssel prüfen, Aufgaben mit Feldliste, Modell, Budget, Verbrauch, letzter Aufruf. „Gültig“ steht erst nach einer echten Probe (eine einzige kleine Anfrage, die der KI-Hauptschalter ebenfalls sperrt), und nur für den geprüften Schlüssel. Die Datenschutz-Anzeige bekommt eine vierte Zeile „Direkt an die Anthropic-API“, solange eine Aufgabe freigegeben ist.
- **Drei Werkzeuge für Claude** (nur mit Schlüssel beim Start registriert; ohne ihn ist die Werkzeugliste die von vorher): `api_weg_anzeigen`, `api_weg_einstellen`, `api_weg_pruefen`.
- **Messprobe `scripts/api_probe.py`.** Trockenlauf als Standard (zeigt den ersten Prompt genau so, wie er abgeschickt würde, dazu Tokens und Kosten; sendet nichts, braucht kein Netz). Gesendet wird nur mit `--senden` und `--budget-usd`. Arbeitet auf einer Kopie der Datenbank, vergleicht mit den Urteilen des Menschen (beworben = passt; selbst aussortiert aus einem Grund über die Art der Stelle = passt nicht; nie die Automatik, nie Systemgründe), nennt je Fehler die Stelle mit Kurzbegründung und kann dieselbe Auswertung für Ollama danebenstellen.

### Changed

- `stellen_auto_aussortieren` braucht kein Ollama, wenn der API-Weg für `match_job_to_skills` freigegeben und nutzbar ist; die Antwort nennt dann `ki_weg` und `api`. Ohne Freigabe bleibt alles, wie es war. Fällt der API-Weg mitten im Lauf aus, endet der Lauf mit dem Grund (statt für alle übrigen Stellen auf eine womöglich kalte lokale KI zurückzufallen); ein Profilwechsel mitten im Lauf beendet ihn ebenfalls.
- `stellen_qualitaet_pruefen(mit_ollama_validierung=True)`: eine Antwort aus der API steht unter `api` statt `ollama`.
- Die Karrierestufe und die häufigsten Aussortier-Gründe des Prompts kommen aus je einer Funktion (`profil_kontext`, `gruende_top`), die der Lauf und die Messprobe teilen.

### Tests und Gegenprobe

- **Netzsperre der Testsuite.** Jede Verbindung zu einem nicht-lokalen Ziel wird abgewiesen, und ein Test, der einen Versuch hinterlässt (auch einen, den der Code schluckt), scheitert. Sie hat sofort zwei Löcher gezeigt: jeder Browser-Test fragte beim Laden der Seite GitHub und elwosa.de nach einem Update, und fünf Tests sprachen das echte Ollama des Entwicklungsrechners an. Beides ist behoben (Update-Prüfung ohne Quellen, Ollama-Port gesperrt).
- **Mutationskatalog `api`:** 73 von 73 Eingriffen erkannt (Schlüssel im Log, in der Datenbank, im Fehlertext; Budget; Feldliste; Schutzschalter; Netzsperre; Messprobe). Die erste Fassung erkannte 68; für die fünf offenen kamen Tests dazu (kurzer Firmenname im Titel, Modell ohne Preis, Schwärzung im Konstruktor des Fehlers, Etikett der Systemgründe, ungleich große Klassen der Stichprobe).

*Schema vNN (unverändert, der API-Weg legt nur Einstellungen an), NNN MCP-Werkzeuge (mit Schlüssel +3), NNNN Tests. Zahlen beim Release einsetzen.*

<!-- Der Pflicht-Block "Wie installiere oder aktualisiere ich PBP?" kommt beim Release unter diesen Eintrag (Vorlage: CLAUDE.md). -->
