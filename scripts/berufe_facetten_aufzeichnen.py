"""Zeichnet echte Antworten des Berufe-Registers als Test-Fixture auf.

Hintergrund (#968, v1.7.69): die Betriebsart des MUSS-Tors leitet sich
daraus ab, ob ein Pflichtbegriff einen BERUF oder eine TECHNIK nennt.
Diese Ableitung wurde gegen das echte Register gemessen — die Messung
lag danach aber nur in einem Sitzungsprotokoll, also **behauptet statt
belegt**.

Dieses Skript holt die Antworten einmal und legt sie unter
`tests/fixtures/berufe_facetten.json` ab. Ab da prueft
`test_v1769_begriffsart_beleg_968.py` die Ableitung gegen ECHTE Daten,
ohne Netz — dasselbe Muster wie die aufgezeichneten LinkedIn- und
Ferchau-Antworten (#919, #925).

Aufruf (selten noetig, nur wenn das Register sich aendert):

    python scripts/berufe_facetten_aufzeichnen.py

Bewusst KEIN Testlauf: ein Test darf keine fremde API anrufen — sonst
haengt die CI an einer Netzsperre oder misst fremde Latenz.

Die Begriffe sind generische Berufs- und Technikbezeichnungen; es
werden keine Firmen, Personen oder Bestandsdaten beruehrt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

ZIEL = REPO / "tests" / "fixtures" / "berufe_facetten.json"

# Bewusst quer durch den Arbeitsmarkt und NICHT nach einem einzelnen
# Lebenslauf ausgewaehlt — genau das war der Einwand, der diese Arbeit
# ausgeloest hat.
BERUFE = [
    "Pflegefachkraft",
    "Erzieherin",
    "Elektroniker",
    "Finanzbuchhalter",
    "Koch",
    "Physiotherapeut",
]

TECHNIKEN = [
    "PLM",
    "PDM",
    "Python",
    "Kubernetes",
    "Materialstammdaten",
]


def main() -> int:
    from bewerbungs_assistent.services import berufsbezeichnungen as bb

    aufzeichnung: dict[str, dict] = {}
    for begriff, erwartet in (
        [(b, bb.BERUF) for b in BERUFE] + [(t, bb.TECHNIK) for t in TECHNIKEN]
    ):
        bb.cache_leeren()
        daten = bb._daten(begriff)
        if daten is None:
            print(f"  {begriff:<20} KEINE ANTWORT — uebersprungen")
            continue
        facette = ((daten or {}).get("facetten") or {}).get("beruf") or {}
        counts = facette.get("counts") if isinstance(facette, dict) else None
        if not isinstance(counts, dict) or not counts:
            print(f"  {begriff:<20} LEERE FACETTE — uebersprungen")
            continue
        gesamt = sum(counts.values()) or 1
        anteil = max(counts.values()) / gesamt
        aufzeichnung[begriff] = {
            "erwartet": erwartet,
            "spitzenanteil": round(anteil, 4),
            # Nur die Facette, nicht die ganze Antwort: die Stellenliste
            # traegt Firmennamen, und die haben in einem oeffentlichen
            # Repo nichts zu suchen (DoD 9).
            "counts": counts,
        }
        print(f"  {begriff:<20} {anteil:6.1%}  -> {erwartet}")

    if not aufzeichnung:
        print("Nichts aufgezeichnet — Register nicht erreichbar?")
        return 1

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(
        json.dumps(aufzeichnung, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"\n{len(aufzeichnung)} Begriffe -> {ZIEL.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
