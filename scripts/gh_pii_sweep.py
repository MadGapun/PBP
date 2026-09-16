"""Sweep ueber ALLE GitHub-Artefakte auf PII (DoD-Punkt 9).

Warum es dieses Skript gibt: Die Regel "vor jedem `gh issue create` den
Scrubber laufen lassen" hat zweimal versagt — am 23.07.2026 (#763/#766) und
erneut am 31.07./06.08. (drei Issues mit realen Firmen, einem Personennamen,
einer Mailadresse und zwei Telefonnummern). Eine Regel, an die man sich
erinnern muss, ist keine Kontrolle. Dieses Skript prueft den IST-Zustand,
statt sich auf Disziplin beim Anlegen zu verlassen.

Geprueft werden Issue-Bodies UND Kommentare, offene wie geschlossene, dazu
Release-Notes. Das Skript aendert nichts — es meldet nur. Die Entscheidung,
ob ein Fund geloescht wird (Edit reicht nicht, GitHub behaelt die Historie),
bleibt beim Menschen.

Aufruf:
    python scripts/gh_pii_sweep.py                 # alles
    python scripts/gh_pii_sweep.py --seit 2026-07-01
    python scripts/gh_pii_sweep.py --nur-offen

Exit-Code 1 bei Funden — damit es sich in CI oder einen Hook haengen laesst.

    python scripts/gh_pii_sweep.py --ohne-namen    # fuer CI-Logs

`--ohne-namen` (#817): nennt nur Fundstelle und Anzahl, nie den gefundenen
Text. In einem oeffentlichen Repository sind die Actions-Logs oeffentlich —
ein Sweep, der dort seine Funde ausdruckt, veroeffentlicht genau das, was
er finden soll. Die Namen sieht, wer das Skript lokal ohne den Schalter
laufen laesst.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub_pii import find_pii  # noqa: E402


# Dokumentierte Ausnahmen (DoD-9, PII-Triage 12.08.2026): Diese Artefakte
# nennen Portale/Vermittler als QUELLEN-Feature (Produktfunktion, kein
# Bewerbungsverhaeltnis) bzw. den historischen Referenzfall aus dem
# A21/#758-Sweep. Der Sweep meldet fuer sie nur ABWEICHUNGEN vom erwarteten
# Treffer-Set — so bleibt er stumm, solange nichts Neues dazukommt, und
# schlaegt an, sobald jemand echte PII ergaenzt. (Ein Pruefer, der bei
# korrektem Zustand Alarm gibt, wird ignoriert — MERKE aus DoD-9.)
# ACHTUNG: Kommentare sind positionsindiziert ("Kommentar 2") — wird vor
# einem Ausnahme-Kommentar ein neuer eingefuegt, verrutscht der Schluessel
# und der Sweep meldet scheinbar Neues. Dann hier nachziehen.
AUSNAHMEN: dict[str, set[str]] = {
    # Quellen-/Scraper-Kontext: Portale und Vermittler als Adapter/Health
    "#653 Body": {"FIRMA: ferchau"},
    "#668 Body": {"FIRMA: ferchau", "FIRMA: hays"},
    "#668 Kommentar 1": {"FIRMA: ferchau"},
    "#675 Body": {"FIRMA: ferchau", "FIRMA: hays"},  # DoD-Checkliste selbst
    "#747 Titel": {"FIRMA: ferchau"},
    "#747 Body": {"FIRMA: ferchau"},
    "#747 Kommentar 1": {"FIRMA: ferchau"},
    "#748 Body": {"FIRMA: ferchau"},
    "#758 Kommentar 2": {"FIRMA: Hays", "FIRMA: ferchau"},  # beschreibt die Ausnahme-Regel
    "#761 Body": {"FIRMA: ferchau", "FIRMA: hays"},
    "#813 Body": {"FIRMA: ferchau", "FIRMA: hays"},
    # 18.08.: Quellen-Aktivierungs-UX — Portale/Vermittler als Adapter
    "#906 Body": {"FIRMA: ferchau", "FIRMA: hays"},
    # 14.09.: Quellenliste, Lesbarkeit, Textkappung — derselbe Fall, der Name ist ein Quellen-Key
    # aus SOURCE_REGISTRY (programmatisch gegengeprueft, nicht getippt).
    "#1047 Body": {"FIRMA: hays"},
    "#1048 Titel": {"FIRMA: hays"},
    "#1048 Body": {"FIRMA: hays"},
    "#1039 Body": {"FIRMA: hays"},
    # Historischer Referenzfall aus dem A21/#758-Sweep (bewusst belassen):
    # aussortierte Fremd-Stellen, kein Bewerbungsverhaeltnis.
    "#670 Body": {"CORP: Tchibo GmbH"},
    "#671 Body": {"CORP: Konkreter Fall\n\nTchibo GmbH"},
    "#671 Kommentar 1": {"CORP: Fall\n\nTchibo GmbH", "CORP: Tchibo GmbH"},
    # #930 erklaert die Praefix-Regel der Platzhalter-Erkennung und braucht
    # dafuer ein Gegenbeispiel: "Alt GmbH" ist ein Platzhalter, ein realer
    # Name mit demselben Wortanfang bleibt ein Treffer. Der genannte Name
    # steht in KEINER Bewerbung — gegengeprueft mit issue_text_pruefen
    # (#946), das gegen den echten Bestand sucht statt gegen ein Muster.
    "#930 Kommentar 1": {"CORP: Altana AG"},
    # Release-Notes: Portale/Vermittler als Quellen-Feature (Adapter,
    # Probe-URLs, URL-Erkennung, Workday-DAX-Karriereportale) sowie der
    # Tchibo-Referenzfall (beta.86) und ein Catch-all-Fehlalarm auf die
    # Formulierung "Rechtsform-Suffixe GmbH" (beta.64).
    "Release v1.7.4": {"FIRMA: FERCHAU"},
    "Release v1.7.3": {"FIRMA: Hays"},
    "Release v1.7.0-beta.86": {"CORP: Tchibo GmbH"},
    "Release v1.7.0-beta.85": {"FIRMA: ferchau"},
    "Release v1.7.0-beta.77": {"FIRMA: ferchau"},
    "Release v1.7.0-beta.64": {"CORP: Rechtsform-Suffixe GmbH"},
    "Release v1.7.0-beta.47": {"FIRMA: Hays"},
    "Release v1.7.0-beta.36": {"FIRMA: Bosch", "FIRMA: Siemens"},
    "Release v1.7.0-beta.35": {"FIRMA: ferchau", "FIRMA: hays"},
    "Release v1.6.2": {"FIRMA: FERCHAU", "FIRMA: Hays"},
    "Release v1.6.0-beta.20": {"FIRMA: hays"},
    "Release v1.6.0-beta.18": {"FIRMA: ferchau", "FIRMA: hays"},
    "Release v1.6.0-beta.16": {"FIRMA: ferchau"},
    "Release v1.6.0-beta.14": {"FIRMA: hays"},
    "Release v1.6.0-beta.12": {"FIRMA: Hays"},
}


# Zweite Liste, und die Trennung zu AUSNAHMEN ist die eigentliche Aussage:
#
#   AUSNAHMEN        = der Treffer ist ein FEHLALARM (Portalname als
#                      Quellen-Feature, Platzhalter, Referenzfall).
#   BEWUSST_GELASSEN = der Treffer ist ECHT, und der Mensch hat
#                      entschieden, dass er stehen bleibt.
#
# Warum es die zweite Liste braucht (Nutzerwort 16.09.2026, "mich nerven
# diese Mails"): der woechentliche Lauf meldete seit Wochen denselben,
# laengst entschiedenen Stand und scheiterte jedes Mal. **Ein Pruefer,
# der bei einem akzeptierten Zustand Alarm gibt, wird nach dem zweiten
# Mal ignoriert** (#929) — und dann sieht ihn auch niemand mehr, wenn er
# einmal recht hat.
#
# Gespeichert wird NUR die Anzahl je Art, nie der Name. Ein Name in
# dieser Datei waere genau die Veroeffentlichung, die der Sweep
# verhindern soll — und ein Hash waere bei einer kurzen, erratbaren
# Zeichenkette keiner.
#
# GRENZE, ausdruecklich: ein Name, der gegen einen ANDEREN gleicher Art
# getauscht wird, faellt damit nicht auf. Ein hinzukommender schon, und
# das ist der Fall, der zaehlt. Wer es genauer braucht, laesst den Sweep
# lokal ohne --ohne-namen laufen.
BEWUSST_GELASSEN: dict[str, dict[str, int]] = {
    # 21.08.2026, Nutzerentscheidung "ignoriere diese": Bestandsbelege in
    # eigenen Fehlerberichten. Die Namen stehen weiter oeffentlich auf
    # GitHub — sie hier stummzuschalten aendert daran nichts und
    # behauptet es auch nicht. Wer sie entfernen will: Issue LOESCHEN
    # (Editieren reicht nicht, GitHub zeigt die Historie) und den Inhalt
    # anonymisiert neu anlegen.
    "#947 Body": {"FIRMA": 1},
    "#951 Body": {"FIRMA": 3},
    "#953 Body": {"FIRMA": 1},
    "#956 Body": {"FIRMA": 1},
    "#957 Body": {"FIRMA": 2},
}


def _arten(treffer: list[str]) -> dict[str, int]:
    """Zaehlt die Treffer je Art — ohne die Namen selbst."""
    gezaehlt: dict[str, int] = {}
    for t in sorted(set(treffer)):
        art = t.split(":", 1)[0]
        gezaehlt[art] = gezaehlt.get(art, 0) + 1
    return gezaehlt


def _gefiltert(stelle: str, treffer: list[str]) -> list[str]:
    """Blendet erwartete Treffer dokumentierter Ausnahmen aus.

    Verglichen wird ohne Ruecksicht auf Gross- und Kleinschreibung: in
    einem Issue steht der Quellen-Key so, wie ihn jemand getippt hat, in
    DIESER Datei darf er nur klein stehen (v1.7.109 MERKE 6, sonst
    schlaegt `scrub_pii --check` bei jedem Commit an). Ein Vergleich auf
    Gleichheit haette die Grossschreibung hier erzwungen — und am
    eigenen Pruefer vorbeizuarbeiten ist nie die Antwort.
    """
    erwartet = AUSNAHMEN.get(stelle)
    if erwartet is None:
        return treffer
    bekannt = {e.lower() for e in erwartet}
    return sorted(t for t in set(treffer) if t.lower() not in bekannt)


def _abgehakt(stelle: str, treffer: list[str]) -> bool:
    """True, wenn der Fund genau dem bewusst gelassenen Stand entspricht.

    Weicht die Zahl ab — nach oben wie nach unten —, meldet der Sweep den
    Fund wieder. Nach unten deshalb, weil dann diese Liste veraltet ist
    und nachgezogen gehoert: eine Liste, die mehr abhakt als der Bestand
    hergibt, deckt beim naechsten Mal etwas Echtes zu.
    """
    bekannt = BEWUSST_GELASSEN.get(stelle)
    return bekannt is not None and _arten(treffer) == bekannt


def _gh(args: list[str]) -> str:
    """Ruft gh auf — ohne GITHUB_TOKEN, sonst greift der Token mit zu
    engen Scopes (siehe CLAUDE.md, Token-Falle)."""
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    res = subprocess.run(["gh", *args], capture_output=True, text=True,
                         env=env, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} -> {res.stderr.strip()[:300]}")
    return res.stdout


def issues_laden(nur_offen: bool) -> list[dict]:
    state = "open" if nur_offen else "all"
    roh = _gh(["issue", "list", "--state", state, "--limit", "1000",
               "--json", "number,title,body,comments,createdAt"])
    return json.loads(roh)


def releases_laden() -> list[dict]:
    roh = _gh(["release", "list", "--limit", "200", "--json", "tagName"])
    out = []
    for r in json.loads(roh):
        try:
            d = json.loads(_gh(["release", "view", r["tagName"],
                                "--json", "tagName,body"]))
            out.append(d)
        except RuntimeError:
            continue
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seit", default="", help="nur Issues ab ISO-Datum")
    ap.add_argument("--nur-offen", action="store_true")
    ap.add_argument("--mit-releases", action="store_true",
                    help="Release-Notes mitpruefen (langsam)")
    ap.add_argument("--ohne-namen", action="store_true",
                    help="nur Fundstelle und Anzahl ausgeben (fuer CI-Logs, #817)")
    args = ap.parse_args(argv)

    funde: list[tuple[str, list[str]]] = []
    abgehakt: list[str] = []
    geprueft = 0

    for iss in issues_laden(args.nur_offen):
        if args.seit and iss.get("createdAt", "") < args.seit:
            continue
        geprueft += 1
        n = iss["number"]
        for stelle, text in [(f"#{n} Titel", iss.get("title", "")),
                             (f"#{n} Body", iss.get("body", "") or "")]:
            treffer = _gefiltert(stelle, find_pii(text))
            if treffer and _abgehakt(stelle, treffer):
                abgehakt.append(stelle)
            elif treffer:
                funde.append((stelle, treffer))
        for i, kom in enumerate(iss.get("comments") or [], 1):
            stelle = f"#{n} Kommentar {i}"
            treffer = _gefiltert(stelle, find_pii(kom.get("body", "") or ""))
            if treffer and _abgehakt(stelle, treffer):
                abgehakt.append(stelle)
            elif treffer:
                funde.append((stelle, treffer))

    if args.mit_releases:
        for rel in releases_laden():
            geprueft += 1
            stelle = f"Release {rel['tagName']}"
            treffer = _gefiltert(stelle, find_pii(rel.get("body", "") or ""))
            if treffer and _abgehakt(stelle, treffer):
                abgehakt.append(stelle)
            elif treffer:
                funde.append((stelle, treffer))

    print(f"Geprueft: {geprueft} Artefakte")
    if abgehakt:
        # Stumm heisst nicht unsichtbar: die Zeile nennt die Zahl,
        # damit niemand den Stand fuer sauber haelt.
        print(f"Bewusst gelassen, unveraendert (BEWUSST_GELASSEN): "
              f"{len(abgehakt)} Artefakte — {', '.join(abgehakt)}")
    veraltet = sorted(set(BEWUSST_GELASSEN) - set(abgehakt)
                      - {stelle for stelle, _ in funde})
    if veraltet:
        print(f"HINWEIS: hier ist nichts mehr zu finden — Eintrag aus "
              f"BEWUSST_GELASSEN entfernen: {', '.join(veraltet)}")
    print()
    if not funde:
        print("Keine neue PII gefunden.")
        return 0

    print(f"PII GEFUNDEN in {len(funde)} Artefakten:\n")
    for stelle, treffer in funde:
        if args.ohne_namen:
            # Nur die Art je Treffer ("FIRMA", "PERSON", ...), nie der Text.
            arten = sorted({t.split(":", 1)[0] for t in treffer})
            print(f"  {stelle}: {len(set(treffer))} Treffer ({', '.join(arten)})")
            continue
        print(f"  {stelle}")
        for t in sorted(set(treffer)):
            print(f"      {t}")
    if args.ohne_namen:
        print("\nDie Namen stehen bewusst nicht im Log. Lokal ohne --ohne-namen")
        print("laufen lassen, um sie zu sehen.")
    print("\nWICHTIG: Editieren reicht NICHT — GitHub zeigt die Edit-Historie.")
    print("Betroffene Issues LOESCHEN (GraphQL deleteIssue) und den Inhalt")
    print("anonymisiert neu anlegen. Siehe DoD-Punkt 9 in CLAUDE.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
