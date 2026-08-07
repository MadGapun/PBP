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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seit", default="", help="nur Issues ab ISO-Datum")
    ap.add_argument("--nur-offen", action="store_true")
    ap.add_argument("--mit-releases", action="store_true",
                    help="Release-Notes mitpruefen (langsam)")
    args = ap.parse_args()

    funde: list[tuple[str, list[str]]] = []
    geprueft = 0

    for iss in issues_laden(args.nur_offen):
        if args.seit and iss.get("createdAt", "") < args.seit:
            continue
        geprueft += 1
        n = iss["number"]
        for stelle, text in [(f"#{n} Titel", iss.get("title", "")),
                             (f"#{n} Body", iss.get("body", "") or "")]:
            treffer = find_pii(text)
            if treffer:
                funde.append((stelle, treffer))
        for i, kom in enumerate(iss.get("comments") or [], 1):
            treffer = find_pii(kom.get("body", "") or "")
            if treffer:
                funde.append((f"#{n} Kommentar {i}", treffer))

    if args.mit_releases:
        for rel in releases_laden():
            geprueft += 1
            treffer = find_pii(rel.get("body", "") or "")
            if treffer:
                funde.append((f"Release {rel['tagName']}", treffer))

    print(f"Geprueft: {geprueft} Artefakte\n")
    if not funde:
        print("Keine PII gefunden.")
        return 0

    print(f"PII GEFUNDEN in {len(funde)} Artefakten:\n")
    for stelle, treffer in funde:
        print(f"  {stelle}")
        for t in sorted(set(treffer)):
            print(f"      {t}")
    print("\nWICHTIG: Editieren reicht NICHT — GitHub zeigt die Edit-Historie.")
    print("Betroffene Issues LOESCHEN (GraphQL deleteIssue) und den Inhalt")
    print("anonymisiert neu anlegen. Siehe DoD-Punkt 9 in CLAUDE.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
