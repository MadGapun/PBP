"""PII-Scrubber fuer GitHub-Issue-Bodies und -Comments.

Hintergrund: am 2026-05-10 wurde festgestellt, dass historische Issues
echte Personen-Namen, Firmen-Namen und Mail-Adressen enthielten — DSGVO-
relevant fuer den User UND die Dritten. Sweep hat 68 Bodies + 2 Comments
nachtraeglich anonymisiert. CLAUDE.md hat jetzt die Pflicht: vor jedem
`gh issue create` durch diesen Scrubber laufen lassen.

## Verwendung

### CLI

```bash
# Check-Mode: exit 0 wenn sauber, exit 1 wenn PII gefunden
python scripts/scrub_pii.py --check < text.md

# Scrub-Mode: anonymisiert + schreibt nach stdout
python scripts/scrub_pii.py --scrub < text.md > clean.md

# Datei in-place bearbeiten
python scripts/scrub_pii.py --scrub-file text.md
```

### Programmatisch

```python
from scripts.scrub_pii import scrub_text, find_pii
body = "Bewerbung bei <FIRMA> als Senior PLM."
hits = find_pii(body)
if hits:
    body = scrub_text(body)
```

## Replace-Konvention

| Klasse | Pattern | Ersatz |
|---|---|---|
| User-Name | `Markus Birzite`, `Birzite` | `<USER>` |
| Firmen | konkrete Firmennamen aus Bewerbungs-Kontext | `<FIRMA>` |
| Email | echte externe Adressen | `<email-anonymisiert>` |
| Telefon | DE-Telefonmuster | `<telefon>` |

## Was NICHT scrubt

- GitHub-Username `MadGapun` (oeffentlicher Repo-Owner — nicht private PII)
- Test-Mails wie `bewerbung@firma.de`, `test@example.com`
- Generische Branchen ("Maschinenbau", "Tech-Senior")

## Erweitern

Neue Firma im PII-Scope? In `_FIRMA_PATTERNS` ergaenzen. Neue Mail-Domain
die safe ist? In `SAFE_EMAIL_DOMAINS`. Pull-Request mit Begruendung.
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable


# === User-Identifizierung ========================================
_USER_PATTERNS = [
    re.compile(r"\bMarkus\s+Birzite\b"),
    re.compile(r"\bBirzite\b"),
]

# === Konkrete Firmennamen aus Bewerbungs-Kontext =================
_FIRMA_PATTERNS = [
    # DAX-Konzerne / bekannte Marken
    re.compile(r"\bAudi\b"),
    re.compile(r"\bBMW(?:\s+Group)?\b"),
    re.compile(r"\bBosch\b"),
    re.compile(r"\bMercedes(?:-Benz)?\b"),
    re.compile(r"\bRheinmetall\b"),
    re.compile(r"\bSiemens(?:\s+Energy)?\b"),
    re.compile(r"\bThyssenkrupp\b", re.IGNORECASE),
    re.compile(r"\bVolkswagen\b"),
    # Mittelstand / spezifische Firmen
    re.compile(r"\bPhoenix Contact\b"),
    re.compile(r"\bhagebau\b"),
    re.compile(r"\bEdeka\b"),
    re.compile(r"\bH(ä|ae|�)rtling(?:\s+Hamburg)?\b"),
    re.compile(r"\bGerman LNG(?:\s+Terminal)?\b"),
    # Recruiter / Personaldienstleister
    re.compile(r"\bAPRIORI\b"),
    re.compile(r"\bAS Innovative(?:\s+IT)?\b"),
    re.compile(r"\bDxP Services\b"),
    re.compile(r"\bECS Engineering\b"),
    re.compile(r"\bFERCHAU(?:\s+GmbH)?\b"),
    re.compile(r"\bHays\b"),
    re.compile(r"\bHiSimply(?:\s+GmbH)?\b"),
    re.compile(r"\bIQ(?:\s+Engineering)?\b"),
    re.compile(r"\bITC Infotech\b"),
    re.compile(r"\bProgressive Recruitment\b"),
    re.compile(r"\bRandstad(?:\s+Professional)?\b"),
    re.compile(r"\bSoorce\b"),
    re.compile(r"\bTC Thomas Consulting\b"),
    re.compile(r"\bThomas Consulting\b"),
    re.compile(r"\bYER(?:\s+Staffing)?\b"),
]

# === Mail-Adressen ===============================================
_EMAIL_RE = re.compile(r"[\w\.\-+]+@[\w\.\-]+\.[a-zA-Z]{2,}")
SAFE_EMAIL_DOMAINS = (
    "anthropic.com",        # Co-Author Footer
    "github.com",           # GitHub-Bots
    "example.com",          # RFC-2606 Test-Domain
    "example.org",
    "example.net",
    "elwosa.de",            # interne Test-Mail
    "firma.de",             # generischer Platzhalter
    "test.de",              # generischer Platzhalter
)

# === Telefon (DE) =================================================
_PHONE_RE = re.compile(
    r"(?:\+49|0049|0)\s?[1-9]\d{1,4}[\s\-/]?\d{3,}[\s\-/]?\d{0,}"
)


def _is_safe_email(addr: str) -> bool:
    domain = addr.split("@", 1)[-1].lower()
    return any(domain.endswith(d) for d in SAFE_EMAIL_DOMAINS)


def find_pii(text: str) -> list[str]:
    """Liefert eine Liste der gefundenen PII-Treffer (zur Anzeige)."""
    if not text:
        return []
    hits: list[str] = []
    for p in _USER_PATTERNS:
        for m in set(p.findall(text)):
            hits.append(f"USER: {m}")
    for p in _FIRMA_PATTERNS:
        for m in set(p.findall(text)):
            label = m if isinstance(m, str) else " ".join(filter(None, m))
            hits.append(f"FIRMA: {label}")
    for m in set(_EMAIL_RE.findall(text)):
        if not _is_safe_email(m):
            hits.append(f"EMAIL: {m}")
    for m in set(_PHONE_RE.findall(text)):
        if len(m.replace(" ", "").replace("-", "")) >= 7:
            hits.append(f"PHONE: {m}")
    return hits


def scrub_text(text: str) -> str:
    """Wendet alle Anonymisierungs-Regeln an. Idempotent."""
    if not text:
        return text
    for p in _USER_PATTERNS:
        text = p.sub("<USER>", text)
    for p in _FIRMA_PATTERNS:
        text = p.sub("<FIRMA>", text)
    text = _EMAIL_RE.sub(
        lambda m: m.group() if _is_safe_email(m.group()) else "<email-anonymisiert>",
        text,
    )
    text = _PHONE_RE.sub("<telefon>", text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 wenn PII gefunden (kein Output ausser auf stderr)")
    ap.add_argument("--scrub", action="store_true",
                    help="Anonymisierten Text auf stdout schreiben")
    ap.add_argument("--scrub-file", metavar="PATH",
                    help="Datei in-place anonymisieren")
    args = ap.parse_args()

    if args.scrub_file:
        with open(args.scrub_file, "r", encoding="utf-8") as f:
            text = f.read()
        cleaned = scrub_text(text)
        with open(args.scrub_file, "w", encoding="utf-8") as f:
            f.write(cleaned)
        diff = sum(1 for a, b in zip(text, cleaned) if a != b)
        print(f"Anonymisiert: {args.scrub_file} (Diff: {diff} Zeichen)",
              file=sys.stderr)
        return 0

    text = sys.stdin.read()
    hits = find_pii(text)

    if args.check:
        if hits:
            print("PII GEFUNDEN — Issue NICHT erstellen:", file=sys.stderr)
            for h in hits:
                print(f"  - {h}", file=sys.stderr)
            print("Tipp: python scripts/scrub_pii.py --scrub < input > clean",
                  file=sys.stderr)
            return 1
        return 0

    if args.scrub:
        sys.stdout.write(scrub_text(text))
        if hits:
            print(f"\n[scrubbed {len(hits)} PII-Treffer]", file=sys.stderr)
        return 0

    # Default: zeige Treffer
    if hits:
        for h in hits:
            print(h)
        return 1
    print("(keine PII-Treffer)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
