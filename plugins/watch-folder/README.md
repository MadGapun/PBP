# PBP Watch-Folder-Plugin (Referenz fuer die Ingest-API v1)

Beobachtet einen Ordner und uebergibt neue **.eml/.msg**-Dateien an PBP.
Der einfachste Mail-Zubringer: Mails aus Thunderbird/Outlook per
Drag&Drop in den Ordner ziehen — PBP macht den Rest (Duplikat-Erkennung,
Bewerbungs-Matching, Termine, Timeline).

Zugleich ist dieses Skript die **Referenz-Implementierung** fuer eigene
Plugins: ~150 Zeilen, nur Python-Standardbibliothek.

## Einrichtung (2 Minuten)

1. **Koppeln:** PBP-Dashboard → Einstellungen → **Erweiterungen** →
   Gekoppelte Plugins → *Plugin koppeln* → Inhalt von
   [`pbp-plugin.json`](pbp-plugin.json) einfuegen → **API-Key kopieren**
   (wird genau einmal angezeigt).
2. **Starten:**

   ```bash
   python watch_folder.py --ordner "C:/PBP-Eingang" --api-key pbp_DEIN_KEY
   ```

   Optionen: `--url http://127.0.0.1:8200` · `--intervall 15` · `--einmalig`

Verarbeitete Dateien wandern nach `verarbeitet/`, fehlgeschlagene nach
`fehler/` (mit Fehlertext daneben). Widerruf jederzeit in den
Einstellungen — der Key ist sofort tot.

## Die Ingest-API v1 in Kuerze (fuer eigene Plugins)

> Beta-Hinweis: Die API v1 wird mit dem 1.8-Stable eingefroren; bis dahin
> sind additive Aenderungen moeglich. Alles laeuft lokal (127.0.0.1),
> nichts verlaesst den Rechner.

**Pairing:** Der User erzeugt den API-Key in den PBP-Einstellungen aus
deinem Manifest (`pbp-plugin.json`):

```json
{
  "name": "Mein-Plugin",
  "version": "1.0.0",
  "ingest_api": "^1",
  "capabilities": ["ingest:email", "ingest:job"],
  "beschreibung": "Was das Plugin tut."
}
```

**Auth:** Jeder Call traegt den Header `X-PBP-API-Key: pbp_...`.
Antworten bei Problemen: `401` (Key fehlt/unbekannt/widerrufen),
`403` (Capability nicht im Manifest deklariert).

| Endpoint | Zweck |
|---|---|
| `GET /api/v1/ingest/ping` | Setup-Check: Key gueltig? Liefert Plugin-Name, Capabilities, PBP-Version. |
| `POST /api/v1/ingest/email` | `multipart/form-data`, Feld `file` (.eml/.msg). Volle Upload-Pipeline: Duplikat-Erkennung, Bewerbungs-Matching, Termine. |
| `POST /api/v1/ingest/job` | JSON: `{titel, firma, url?, ort?, beschreibung?, remote?, stellenart?}`. Laeuft durch Scoring + Duplikat-Erkennung; Quelle wird `plugin:<name>`. `409` bei Blacklist-Firma oder laufender Bewerbung mit sehr aehnlichem Titel. |

Beispiel `ingest/job`:

```bash
curl -X POST http://127.0.0.1:8200/api/v1/ingest/job \
  -H "X-PBP-API-Key: pbp_DEIN_KEY" -H "Content-Type: application/json" \
  -d '{"titel": "PLM Consultant", "firma": "Acme Solutions GmbH", "url": "https://example.com/job/1", "beschreibung": "..."}'
```

Antwort: `{"status": "angelegt", "job_hash": "...", "score": 42, ...}` —
bei Inhalts-Duplikaten (gleicher Titel+Firma schon aktiv) wird die Stelle
als Duplikat markiert statt doppelt zu erscheinen.
