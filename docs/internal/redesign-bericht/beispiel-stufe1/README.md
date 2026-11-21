# Beispielbericht Stufe 1 (21.11.2026)

Erzeugt aus dem Musterprofil „Bob“ (erfundene Firmen) in einer isolierten Installation (`BA_DATA_DIR`, Pfad per `assert` geprüft), Zeitraum **01.11.2026 bis 30.11.2026**, mit dem Stand von Stufe 1 (Fehler-Paket #1337 und #1420; Aufbau des Berichts unverändert).

- `beispielbericht-2026-11.pdf` — der Bericht als PDF (6 Seiten)
- `beispielbericht-2026-11.xlsx` — dasselbe als Excel (Blätter „Bewerbungen“, „Statistik“, „Kosten“)

Was beim Lesen zu beachten ist:

1. **Musterdaten, nicht der echte Bestand.** Das Musterprofil hat 24 Bewerbungen, davon 6 im November.
2. **Die Kosten (38,40 € und 24,90 €) sind für diesen Beispielbericht ergänzt,** das Musterprofil hat keine. Sie stehen in der isolierten Installation, nicht im Seed.
3. **„Prozessdauer: noch keine Angabe möglich“** ist kein Fehler: Alle Ereignisse des Musterprofils tragen den Zeitstempel des Anlegens (Abstand 0 Tage). Das behebt Stufe 4 (Musterprofil mit glaubwürdigen Daten).
4. **Abschnitte „nur im Bericht für den gesamten Verlauf“** (Punkte-Verteilung, aussortierte Stellen, offene Stellen, Quellen-Volumen) haben im Zeitraum-Bericht keine Zahlen, weil sie an Stellen statt an Bewerbungen hängen.
5. **Der Aufbau ist noch der alte** (Abschnittsnummern, Kreisdiagramm für den Status, Schlüsselwort-Analyse mit „fiktive, musterstelle“). Er wird in Stufe 3 ersetzt.
