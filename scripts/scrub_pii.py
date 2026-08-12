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
    re.compile(r"\bMarkus\s+Birzite\b", re.IGNORECASE),
    re.compile(r"\bBirzite\b", re.IGNORECASE),
    re.compile(r"\bMarkus['’]s?\b"),  # Possessiv: Markus' / Markus's
]

# === Personennamen (Recruiter, HR-Kontakte) ======================
_PERSON_LITERAL = [
    r"Sheirry\s+Singh",
    r"Kiani\s+Webb",
    r"Saskia\s+van\s+Wijk",
    r"R\.\s+Molnar",
    r"Sebastian\s+Hentzelt",
]
_PERSON_PATTERNS = [re.compile(rf"\b{p}\b") for p in _PERSON_LITERAL]

# === Konkrete Firmennamen — case-insensitive =====================
# Reihenfolge: spezifischere Patterns zuerst (z.B. "Lürssen Werft" vor "Lürssen")
_FIRMA_LITERAL = [
    # Bewerbungs-Targets / Endkunden
    r"L(?:ü|ue|�)rssen(?:[\s\-]+Werft)?(?:\s+Bremen)?",
    r"L(?:ue)rssen",
    r"TKMS(?:\s+GmbH)?",
    r"Intelligentes\s+Ingenieur(?:\s+Management)?(?:\s+GmbH)?",
    r"PBCN",
    r"Rheinmetall",
    r"Siemens(?:\s+Energy)?",
    r"BMW(?:\s+Group)?",
    r"Bosch",
    r"Mercedes(?:-Benz)?",
    r"Audi",
    r"Volkswagen",
    r"Phoenix\s+Contact",
    r"hagebau",
    r"Edeka",
    r"Thyssenkrupp",
    r"H(?:ä|ae|�)rtling(?:\s+Hamburg)?",
    r"German\s+LNG(?:\s+Terminal)?",
    # Recruiter / Personaldienstleister
    r"APRIORI",
    r"AS\s+Innovative(?:\s+IT)?",
    r"DxP\s+Services",
    r"ECS\s+(?:Engineering|GmbH)",
    r"FERCHAU(?:\s+GmbH)?",
    r"Hays",
    r"HiSimply(?:\s+GmbH)?",
    r"\bIQ\b(?!\.\w)",  # IQ aber nicht IQ.something
    r"ITC\s+Infotech",
    r"Progressive\s+Recruitment",
    r"Randstad(?:\s+Professional)?",
    r"Soorce",
    r"TC\s+Thomas\s+Consulting",
    r"Thomas\s+Consulting",
    r"YER(?:\s+Staffing)?",
    # Tech-/Engineering-Firmen
    r"Bechtle(?:\s+PLM(?:\s+Deutschland)?)?(?:\s+GmbH)?",
    r"CIDEON(?:\s+Software(?:\s*&\s*Services)?)?(?:\s+GmbH)?",
    r"PartSpace(?:\s+GmbH)?",
    r"Teccon(?:\s+GmbH)?",
    r"Kaiser\s+Personalberatung(?:\s+GmbH)?",
    r"BHD(?:\s+GmbH)?",
    r"Rite-Hite(?:\s+GmbH)?",
    r"TOMRA(?:\s+Sorting)?(?:\s+GmbH)?",
    r"CENIT(?:\s+AG)?",
    r"Questax(?:\s+Experts)?(?:\s+GmbH)?",
    r"Leuchtmehr(?:\s+GmbH)?",
    r"CONTACT\s+Software(?:\s+GmbH)?",
    r"Masa\s+GmbH",
    r"NVL(?:\s+B\.V\.\s*&\s*Co\.\s*KG)?",
    # Nachtrag 11.08.2026: standen in #821 (Blacklist-/Bewerbungshistorie)
    # und rutschten am Sweep vorbei — Markennamen ohne Rechtsform-Suffix
    # faengt der Corp-Catch-all nicht.
    r"Atos",
    r"valantic",
    r"adesso(?:\s+SE)?",
    r"Akkodis(?:\s+Germany)?(?:\s+Tech\s+Experts)?(?:\s+GmbH)?",
]
_FIRMA_PATTERNS = [re.compile(rf"\b{p}\b", re.IGNORECASE) for p in _FIRMA_LITERAL]

# Fiktive Firmen, die als ANONYMISIERUNG dienen (CLAUDE.md, DoD-9).
# Ohne diese Liste schlaegt der Catch-all bei genau den Platzhaltern an, die
# die Regel vorschreibt — ein Pruefer, der bei korrektem Ergebnis Alarm gibt,
# wird nach dem zweiten Mal ignoriert. Neue Platzhalter hier eintragen.
FIKTIVE_FIRMEN = (
    "musterfirma",
    "halbleiterwerk nord",
    "systemhaus nord",
    "anlagenbau sued",
    "chemiewerk mitte",
    "engineering-partner",
    "konsumgueter",
    "ingenieurvermittlung mitte",
    "werft nord",
    "vermittler nord",
    "vermittler ost",
    "vermittler sued",
    "vermittler west",
    "beispiel",
    "acme",
    # Der generische Platzhalter selbst ("Firma GmbH" als Beispieltext in
    # Doku/Kommentaren) — exakte Phrase, kein realer Firmenname.
    "firma gmbh",
    # Musterprofile Bob & Anna (docs/screenshots/musterprofile.py, #840) —
    # alle frei erfunden, dienen als Demo-/Screenshot-Daten.
    "weserstahl",
    "leinetal",
    "hansa verfahrenstechnik",
    "bergwind getriebebau",
    "alpenland anlagenmontage",
    "nordlicht antriebstechnik",
    "steinfeld hydraulik",
    "calenberg maschinenfabrik",
    "windrose energietechnik",
    "teutoburg stanztechnik",
    "aller metallbau",
    "harzland pumpen",
    "borgfeld automotive",
    "leibniz schaltanlagen",
    "okertal getriebe",
    "muehlenberg werkzeugbau",
    "mühlenberg werkzeugbau",
    "deistervilla",
    "steinhuder foerdertechnik",
    "steinhuder fördertechnik",
    "parkhotel auenblick",
    "grandhotel firnlicht",
    "stadthotel elsterblick",
    "kontor 44",
    "pflegewerk saale",
    "auwald klinikgruppe",
    "lindenhof seniorenresidenzen",
    "quartier m immobilien",
    "elbaue logistik",
    "salzgold therme",
    "mitteldeutsches bildungswerk",
    "wetterfeld",
    "pleisse medien",
    "pleiße medien",
    "rosental kosmetikwerk",
    "cospudener reisen",
    "hafenkontor halle",
)

# Catch-all: "<Wort> GmbH/AG/KG/SE/UG" — fängt unbekannte deutsche Firmen
_GERMAN_CORP_RE = re.compile(
    r"\b[A-ZÄÖÜ][\wÄÖÜäöüß\.\-/&]+(?:\s+[A-ZÄÖÜ&][\wÄÖÜäöüß\.\-/&]*){0,4}"
    r"\s+(?:GmbH|AG|KG|SE|UG|e\.V\.|gGmbH|mbH|GbR)"
    r"(?:\s*&\s*Co\.?(?:\s*KG)?)?\b"
)

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
#
# Zwei Fehler der ersten Fassung, gefunden beim Sweep am 07.08.2026:
#   1. `\s` matchte auch ZEILENUMBRUECHE — "0160\n127" wurde als Nummer
#      gemeldet, obwohl die Ziffern aus zwei verschiedenen Zeilen kamen.
#   2. Kein Lookbehind — die Jahresspanne "2020-2024" wurde ab Position 1
#      als "020-2024" gelesen und als Telefonnummer gemeldet.
# Beides erzeugte so viele Fehlalarme, dass der Report unbrauchbar war —
# und ein Pruefer, dem man nicht glaubt, verhindert nichts.
_PHONE_RE = re.compile(
    r"(?<![\d/.\-])"                      # nicht mitten in einer Zahl beginnen
    r"(?:\+49|0049|0)[ ]?"                # DE-Vorwahl, nur echte Leerzeichen
    r"[1-9]\d{1,4}[ \-/]?"                # Ortsnetz/Mobilfunk
    r"\d{3,}(?:[ \-/]?\d+)*"              # Rufnummer, optional gruppiert
    r"(?![\d\-]*\s*(?:Zeichen|Stellen|px|EUR|€))"  # keine Mengenangaben
)


# Inline-Code in Backticks. Dort stehen Commit-Hashes, IDs und Codeschnipsel
# — nie die Telefonnummer eines Menschen. Gefunden beim Sweep am 07.08.2026:
# `0462449` (ein Git-Commit) wurde als Rufnummer gemeldet, weil sieben Ziffern
# mit fuehrender Null exakt wie eine aussehen. Bewusst NUR ueber den
# Backtick-Kontext und nicht ueber ein Hex-Muster: ein reines Ziffernmuster
# wuerde auch echte Rufnummern verschlucken.
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _in_inline_code(text: str, start: int, ende: int) -> bool:
    """True, wenn der Treffer vollstaendig in einem Backtick-Block liegt."""
    return any(m.start() <= start and ende <= m.end()
               for m in _INLINE_CODE_RE.finditer(text))


def _ist_fiktiv(label: str) -> bool:
    """True fuer Platzhalter-Firmen aus FIKTIVE_FIRMEN (DoD-9-Konvention)."""
    klein = label.lower()
    return any(f in klein for f in FIKTIVE_FIRMEN)


# Automaten-Absender. Hinter `noreply@` oder `mailrobot@` steht kein Mensch,
# den man erreichen kann — das sind keine Kontaktdaten, sondern technische
# Kennungen. PBP dokumentiert sie bewusst (Absender-Erkennung fuer
# Newsletter und Portal-Benachrichtigungen, #643/#657). Bewusst ueber den
# LOKALTEIL und nicht ueber die Domain: `noreply@firma.de` ist harmlos,
# `vorname.name@firma.de` auf derselben Domain waere es nicht.
_SYSTEM_LOKALTEILE = (
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailrobot", "notifications-noreply", "messaging-digest-noreply",
    "notification", "automailer", "bounce", "postmaster",
)

# Reine Roboter-DOMAINS der Portale: dahinter ist unabhaengig vom Lokalteil
# kein Mensch erreichbar (Absender-Erkennung ist Produktfunktion, #643).
# Fund aus der PII-Triage 12.08.2026: `info@bot.xing.com` wurde gemeldet,
# obwohl der Lokalteil "info" nur an einem Benachrichtigungs-Roboter haengt.
_AUTOMAT_DOMAINS = (
    "bot.xing.com",
)


def _is_safe_email(addr: str) -> bool:
    lokal, _, domain = addr.rpartition("@")
    domain = domain.lower()
    # Exakt oder echte Subdomain — NICHT per endswith. Sonst galt jede
    # Domain als sicher, die zufaellig auf einen Platzhalter endet:
    # `grossfirma.de` endet auf `firma.de`, `bestetest.de` auf `test.de`.
    # Das war ein Fehler in der gefaehrlichen Richtung (echte Adressen
    # rutschten durch), gefunden am 07.08.2026.
    if any(domain == d or domain.endswith("." + d) for d in SAFE_EMAIL_DOMAINS):
        return True
    if any(domain == d or domain.endswith("." + d) for d in _AUTOMAT_DOMAINS):
        return True
    return lokal.lower() in _SYSTEM_LOKALTEILE


def find_pii(text: str) -> list[str]:
    """Liefert eine Liste der gefundenen PII-Treffer (zur Anzeige)."""
    if not text:
        return []
    hits: list[str] = []
    for p in _USER_PATTERNS:
        for m in set(p.findall(text)):
            hits.append(f"USER: {m}")
    for p in _PERSON_PATTERNS:
        for m in set(p.findall(text)):
            hits.append(f"PERSON: {m}")
    for p in _FIRMA_PATTERNS:
        for m in set(p.findall(text)):
            label = m if isinstance(m, str) else " ".join(filter(None, m))
            hits.append(f"FIRMA: {label}")
    for m in set(_GERMAN_CORP_RE.findall(text)):
        label = m if isinstance(m, str) else " ".join(filter(None, m))
        if "<" not in label and not _ist_fiktiv(label):
            hits.append(f"CORP: {label}")
    for m in set(_EMAIL_RE.findall(text)):
        if not _is_safe_email(m):
            hits.append(f"EMAIL: {m}")
    gesehen_tel: set[str] = set()
    for m in _PHONE_RE.finditer(text):
        wert = m.group(0)
        if wert in gesehen_tel:
            continue
        if len(wert.replace(" ", "").replace("-", "")) < 7:
            continue
        # Commit-Hashes, IDs und Codeschnipsel stehen in Backticks
        if _in_inline_code(text, m.start(), m.end()):
            continue
        gesehen_tel.add(wert)
        hits.append(f"PHONE: {wert}")
    return hits


def scrub_text(text: str) -> str:
    """Wendet alle Anonymisierungs-Regeln an. Idempotent."""
    if not text:
        return text
    for p in _USER_PATTERNS:
        text = p.sub("<USER>", text)
    for p in _PERSON_PATTERNS:
        text = p.sub("<PERSON>", text)
    for p in _FIRMA_PATTERNS:
        text = p.sub("<FIRMA>", text)
    text = _GERMAN_CORP_RE.sub("<FIRMA>", text)
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
