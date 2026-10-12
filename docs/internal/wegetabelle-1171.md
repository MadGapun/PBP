# Wegetabelle 1.8.0 — Ist und Soll (#1171, G85)

Der Auftrag des Nutzers (06.10.2026): *„Wenn du testest, dann alle Abläufe von A nach B — eine Stelle ansehen, bewerten lassen, eine
Bewerbung dazu schreiben; bei einer Bewerbung nachfassen, die Timeline ansehen, wer der Ansprechpartner ist, wie die Stelle beschrieben
war, wie der Lebenslauf aussah. Jeder Schritt höchstens einen Mausklick vom nächsten entfernt, mit Links und Querverbindungen, und ohne
zum Klicken scrollen zu müssen.“*

Diese Tabelle ist die Prüfliste dazu: **jede Zeile ist ein Test**. Ein Klick heißt: ein Mausklick, ohne vorher zu scrollen. „Fall, dann
Eintrag“ heißt zwei Klicks (die Leiste nennt die Zahl; bei mehreren Einträgen steht eine kurze Auswahl). Gemessen wird bei
**1366 × 768** (ein Laptop) und **1920 × 1080**.

## 1. Die Fälle und was zu ihnen gehört

| Fall | Ansicht | Gehört dazu |
|---|---|---|
| Stelle | Fenster „Stellendetails“ | Firma · Bewerbung · Personen |
| Bewerbung | Fenster „Timeline“ | Stelle · Firma · Personen · Dokumente · Termine |
| Kontakt | Fenster „Kontakt bearbeiten“ | Bewerbungen · Stellen · Firma |
| Firma | Seite Kontakte › Firmen | Bewerbungen · Stellen · Personen · Dokumente |

## 2. Die feste Weg-Leiste

Jede Ansicht eines Falls trägt oben dieselbe Leiste, am selben Ort und mit denselben Wörtern. Sie bleibt beim Scrollen stehen (in einem
Fenster liegt sie über dem scrollenden Inhalt, bei der Firma im festen Kopf der App).

```
‹ Zurück zu …   |   Stelle · Firma · Kontakte 2 · Dokumente · Termine   |   ▸ nächster Schritt ▾
```

- **Links** der Rückweg: dorthin, woher man kam („Zurück zu Bewerbung: …“); sonst die Liste.
- **Mitte** die anderen Ansichten desselben Falls — nur, was es gibt, mit Anzahl. Ein Klick öffnet das Objekt, bei mehreren eine Auswahl.
- **Rechts** der wahrscheinlichste nächste Schritt (der Hauptknopf) und dahinter die anderen Wege.

Die Wörter sind überall dieselben: „Zur Stelle“, „Zur Bewerbung“, „Zur Firma“, „Zum Kontakt“.

### Der Hauptknopf nach Zustand

| Ansicht und Zustand | Hauptknopf | dahinter |
|---|---|---|
| Stelle, ohne Bewerbung, nicht beurteilt | Stelle bewerten (mit Claude) | Bewerbung anlegen · Anzeige öffnen |
| Stelle, beurteilt, ohne Bewerbung | Bewerbung anlegen | Anzeige öffnen |
| Stelle mit Bewerbung | Zur Bewerbung | Anzeige öffnen |
| Bewerbung in Vorbereitung, ohne Lebenslauf | Lebenslauf (mit Claude) | Anschreiben |
| Bewerbung in Vorbereitung, Lebenslauf da | Anschreiben (mit Claude) | |
| Bewerbung in Vorbereitung, beides da | Als beworben eintragen | |
| beworben · Eingangsbestätigung · Gespräch abgeschlossen | Nachfassen (mit Claude) | |
| Interview · Zweitgespräch | Gespräch vorbereiten (mit Claude) | |
| Angebot | Angebot prüfen (mit Claude) | |
| abgelehnt | Aus der Absage lernen (mit Claude) | |
| angenommen · zurückgezogen · abgelaufen · Arbeitgeber ausgefallen | *keiner* — die Leiste erfindet keinen Schritt | |
| Kontakt mit laufender Bewerbung | Nachfassen bei <Name> (mit Claude) | |
| Firma | *keiner* — Pflege steht im Kopf der Ansicht („Bearbeiten“, „Als Firma anlegen“) | |

Test: `tests/test_v18_weg_leiste_1171.py::test_der_hauptknopf_folgt_dem_status`, Rechnung: `frontend/src/lib/wegleiste.js`
(Knoten-Test `wegleiste.test.mjs`, läuft in der CI).

## 3. Die Wege von A nach B

| Von | Nach | Klicks | Vorher | Test |
|---|---|---|---|---|
| Dashboard „Offen“, eine Nachfassung | ihre Bewerbung (Timeline) | 1 | nur die Aufgabenliste | `test_v18_wege_1171::test_dashboard_nachfassen_oeffnet_die_bewerbung` |
| Dashboard, Top-Stelle | die Stelle | 1 | nur die Stellenliste | `…::test_dashboard_top_stelle_oeffnet_die_stelle` |
| Dashboard, Bewerbungskarte | ihre Stelle | 1 | — | `…::test_bewerbungskarte_fuehrt_zur_stelle` |
| Aufgabe | ihre Bewerbung | 1 | zwei (Zeile, dann Dialog) | `…::test_aufgabe_fuehrt_in_einem_klick_zur_bewerbung` |
| Globale Suche, Treffer | das Objekt | 1 | der Klick tat nichts (#1177) | `test_v18_suche_treffer_oeffnen_1177` |
| Link aus Claude (`#<seite>/<kennung>`) | die Stelle, die Bewerbung, … | 0 | die Seite, nicht das Objekt | `test_v18_wege_1171::test_link_aus_claude_oeffnet_die_stelle` (auch hinter der ersten Seite) |
| Bewerbung speichern | die neue Bewerbung, mit den Unterlagen als Schritt | 0 | — | `…::test_nach_bewerbung_speichern_liegt_die_neue_bewerbung_offen_da` |
| Bewerbung (Timeline) | Stelle | 1 | — | `test_v18_weg_leiste_1171::test_ein_klick_von_der_bewerbung_zur_stelle_und_zurueck` |
| Bewerbung (Timeline) | Person | 1 · bei mehreren 2 | roher Verweis „application“ | `…::test_mit_mehreren_personen_steht_eine_auswahl_und_ein_klick_oeffnet_die_person` |
| Bewerbung (Timeline) | Firma · Dokument · Termin | 1 · bei mehreren 2 | Firma ohne Sprung | `…::test_die_leiste_nennt_rueckweg_faelle_und_den_naechsten_schritt` (Stelle, Firma, Personen); Dokumente und Termine: Rechnung im Knoten-Test `wegleiste.test.mjs` |
| Person | ihre Bewerbung · Stelle · Firma | 1 · bei mehreren 2 | die Verknüpfung stand unten im Formular | `test_v18_wege_1171::test_person_in_der_bewerbung_fuehrt_zur_karte_und_die_karte_zurueck` |
| Stelle | ihre Bewerbung | 1 (Hauptknopf) | — | `test_v18_weg_leiste_1171::test_von_der_stelle_fuehrt_ein_klick_zur_bewerbung` |
| Stelle | Firma | 1 | — | `…::test_von_der_stelle_zur_firma_und_zurueck` |
| Firma | Bewerbung · Stelle · Person · Dokument | 1 · bei mehreren 2 | nur die Liste öffnete sich | `…::test_ein_klick_von_der_firma_zur_bewerbung_und_zurueck`, `test_v18_wege_1171::test_firma_oeffnet_stelle_und_person_selbst` |
| jede Ansicht | zurück dorthin, woher man kam | 1 | die Liste | `test_v18_weg_leiste_1171::test_ein_klick_von_der_bewerbung_zur_stelle_und_zurueck` |
| Zurück-Taste des Browsers (Alt + ←) | oberster Dialog schließt, die Seite bleibt | 1 | verließ die Seite | `…::test_die_zurueck_taste_schliesst_den_dialog_statt_die_seite_zu_verlassen` |
| Timeline, Abschnitt | Abschnitt unter der festen Leiste | 1 | — | `test_v18_wege_1171::test_sprungleiste_legt_den_abschnitt_unter_die_stehende_leiste` |

## 4. Listen zuerst: die erste Zeile samt Hauptknopf im ersten Bildschirm

Vor der ersten Stelle lagen rund 900 Pixel (vier Kennzahlkacheln, Hinweiskasten, Suchstand, Filter, „Zuletzt aktualisiert“), vor der
ersten Bewerbung rund 600. Jetzt ist der Kopf EINE Zeile (`ListenUebersicht`): die Zahlen in einem Satz, der eine Hinweis mit seinem
Knopf, der Suchstand — und ein Schalter, der die Kennzahlen und die Erklärung aufklappt (Vorgabe zu, die Wahl wird je Liste im Browser
gemerkt). Die Filterkarten sind niedriger.

Gemessen mit einer Demo (acht Stellen, vier bis fünf Bewerbungen, drei Kontakte, drei Dokumente, eine Aufgabe), **mit** dem Hinweisbanner „Neu: …“
(96 px); je nach Daten schwanken die Werte um rund zehn Pixel:

| Liste | erste Zeile bei 1366 × 768 (oben bis unten) | bei 1920 × 1080 | davor (bis zur ersten Zeile) |
|---|---|---|---|
| Stellen | y 404 bis 717, Knöpfe bis 696 | 388 bis 681, Knöpfe bis 660 | rund 900 px (Ist-Aufnahme), mit #1170 U16 rund 730 |
| Bewerbungen | 483 bis 691, „Timeline“ bis 667 | 483 bis 691 | rund 600 px |
| Kontakte | 348 bis 441 | 348 bis 441 | 348 |
| Dokumente | 459 bis 601, Knöpfe bis 506 | 442 bis 570, Knöpfe bis 489 | 479 (mit einer leeren Zeile davor) |
| Aufgaben | 180 bis 196 („Zur Bewerbung“) | 180 bis 196 | 180 |

Test: `tests/test_v18_listen_zuerst_1171.py` (bei beiden Größen; dazu: keine Liste scrollt seitwärts, der Kopf ist zu, klappt auf, merkt
sich die Wahl, der eine Hinweis bleibt mit seinem Knopf in der Zeile).

**Was bewusst im Weg bleibt:** hat die Bewerbungen-Seite offene Aktionen (Termine, Nachfassungen), steht die Karte „Offene Aktionen“
vor der Liste — sie IST die Arbeit des Tages, ihre erste Zeile liegt im ersten Bildschirm, und „Fällige anzeigen“ springt dorthin.

## 5. Bewusst nicht umgebaut (Antworten an #1171)

- **Kontakt:** erst Ansicht, dann Formular (Frage 7) — die Leiste und die Verknüpfungen stehen oben im vorhandenen Fenster; ein neuer
  Dialogtyp wäre ein eigener Umbau.
- **„Timeline“ → „Verlauf“** (Frage 8): nicht umbenannt; die Wörter der Leiste sind einheitlich, der Name der Ansicht bleibt.
- **Rückweg:** merkt die Ansicht, woher man kam — nicht die Folge davor (kein Verlauf mit mehr als einem Schritt, keine Adresse je
  Dialog).

## 6. Wie die Tabelle geprüft wird

- Browser-Wächter (gebautes Bundle): `test_v18_wege_1171.py`, `test_v18_weg_leiste_1171.py`, `test_v18_listen_zuerst_1171.py`,
  `test_v18_leerlauf_alle_seiten_1171.py`.
- Knoten-Tests in der CI: `wege.test.mjs`, `wegleiste.test.mjs`.
- Gegenprobe: Kataloge `wege` (33 Fehler) und `weg_leiste` im Mutationstest-Lauf (`scripts/mutationstest_auto_update.py`); jeder Fehler
  muss von mindestens einem Test erkannt werden.
