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
    # Nachtrag 18.08.2026: Gespraechspartner aus Termin-Titeln — standen
    # in #830 (Merge-Datenverlust) als reale Belege und rutschten am
    # Sweep vorbei, weil der Pruefer sie nicht kannte.
    r"Felix\s+Hennings",
    r"Hennings",
    r"Christina\s+Pesold",
    r"Pesold",
    r"Schmidt-Lechler",
    r"Jan\s+Peters",
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
    # Nachtrag 18.08.2026: Interview-/Sichtungshistorie aus #830/#911/#914
    # — Markennamen ohne Rechtsform-Suffix, die der Corp-Catch-all nicht
    # faengt.
    r"ePLM(?:\s+AG)?",
    r"Dassault(?:\s+Syst(?:e|è)mes)?",
    r"HydroDyn",
    r"VirtoTech",
    r"Amplifon",
    r"BW\s+Papersystems",
    r"Cubiq(?:\s+Recruitment)?",
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
    "kontor nord",
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
    # Nachtrag 18.08.2026: Stand-ins der Welle 17.08. (#830/#909/#911/#914)
    "plm-haus sued",
    "cad-konzern west",
    "wasserkraft nord",
    "vermittler mitte",
    "messtechnik mitte",
    "hoertechnik sued",
    "sortiertechnik nord",
    "papiertechnik west",
    "recruitment-haus",
    "systemhaus sued",

)

# Catch-all: "<Wort> GmbH/AG/KG/SE/UG" — fängt unbekannte deutsche Firmen
# Woerter, die vor einer Rechtsform stehen koennen, ohne dass ein
# Firmenname gemeint ist — sonst meldet der Pruefer Saetze wie
# "Firma (Umlaute, Rechtsform-Suffixe GmbH/AG/...)" als Treffer.
# Ein Pruefer, der bei korrektem Text Alarm gibt, wird ignoriert.
_CORP_STOPWORDS = (
    "rechtsform", "rechtsformen", "firmen", "firma", "suffix", "suffixe",
    "beispiel", "beispiele", "platzhalter", "endung", "endungen",
)


def _ist_quellen_klasse(label: str, text: str) -> bool:
    """True fuer Adapter-Klassennamen wie `HaysAdapter` — das ist ein
    Quellen-Bezeichner im Code, kein Hinweis auf eine Bewerbung
    (DoD-9-Ausnahme, gleiche Logik wie fuer die kleingeschriebenen Keys).
    """
    return f"{label}Adapter" in text


# Woerter, an denen man einen TESTPLATZHALTER erkennt. Strukturell
# statt als Einzelliste: eine gepflegte Aufzaehlung ist immer nur so
# gut wie ihre letzte Pflege (#929), und Testdaten entstehen staendig
# neu. Ein Treffer, der mit einem dieser Woerter beginnt, ist keine
# reale Firma.
_PLATZHALTER_WOERTER = frozenset({
    "foo", "bar", "baz", "qux", "test", "testfirma", "testcorp", "demo",
    "beispiel", "dummy", "muster", "musterfirma", "alt", "neu", "frisch",
    "eins", "zwei", "drei", "vier", "alpha", "beta", "gamma", "delta",
    "evilcorp", "badcorp", "badfit", "bigcorp", "cloudcorp", "techcorp",
    "techstart", "mittelstandtech", "bla", "blub", "andere", "anderer",
    "anderes", "geblockt", "geheime", "phantom", "reconstruct", "bridge",
    "export", "standard", "default", "aktiv", "inaktiv", "pausiert",
    "konkret", "gattung", "spaet", "dienst", "dienstleister", "saubere",
    "leer", "offener", "geheimkunde", "voellig", "unbekannt", "nur",
    "lang", "schnell", "bericht", "netzwerk", "reflex", "refetch",
    "tech", "passt", "fehltreffer", "knapp", "regler", "gute", "laeuft",
    "belegt", "vermutet", "gewertet", "ohne", "werk", "reue", "zweite",
    "systemhaus", "medienhaus", "agentur", "verlag", "beratungshaus",
})


def _ist_platzhalter_kopf(label: str) -> bool:
    """True, wenn der Treffer wie ein Testdatensatz aussieht.

    Bewusst nur der KOPF: "Alt GmbH" ist ein Platzhalter, "Altana AG"
    waere eine reale Firma und beginnt mit einem anderen Wort.
    """
    teile = label.split()
    if not teile:
        return False
    kopf = teile[0].lower().strip("-,.:;\"'()„“")
    return kopf in _PLATZHALTER_WOERTER


# Rechtsform-Bausteine. Der KOPF eines Firmennamens ist nie selbst
# einer — steht dort trotzdem einer, zaehlt das Umfeld eine Liste von
# Rechtsformen auf statt eine Firma zu nennen.
_RECHTSFORM_WOERTER = frozenset({
    "gmbh", "ag", "kg", "se", "ug", "mbh", "gbr", "ohg", "ggmbh",
    "co", "e.v.", "ev", "ltd", "inc", "plc", "llc", "b.v.", "n.v.",
})


def _ist_stoppwort_kopf(label: str) -> bool:
    """True, wenn im Treffer ein generisches Wort steckt.

    Nicht nur das erste Wort pruefen: "Die Endungen GmbH" beginnt mit
    einem Artikel, das aussagekraeftige Wort steht dahinter. Echte
    Firmennamen enthalten diese Woerter praktisch nie.

    v1.7.24: dazu der Fall aus dem eigenen Bestand — die Aufzaehlung
    "(GmbH, AG, SE, & Co. KG, B.V., Group, Ltd.)" in #962 wurde als
    Firma "Co. KG" gemeldet. Der Regex nahm "Co." als Namen und "KG"
    als Rechtsform. Ein Firmenname faengt nie mit einer Rechtsform an.
    """
    kopf = (label.split() or [""])[0].lower().strip("-,.:;\"'()„“")
    if kopf in _RECHTSFORM_WOERTER:
        return True
    for wort in label.split():
        rein = wort.lower().strip("-,.:;\"'()„“")
        if rein in _CORP_STOPWORDS or rein.split("-")[0] in _CORP_STOPWORDS:
            return True
    return False


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


def _ist_hex_konstante(text: str, start: int) -> bool:
    """True, wenn die Ziffernfolge Teil einer 0x-Konstante ist.

    Belegt: `creationflags: 0x08000000` wurde als Rufnummer gemeldet.
    Ein Pruefer, der bei Quelltext-Konstanten Alarm gibt, wird
    ignoriert — dieselbe Lehre wie bei den Jahresspannen.
    """
    davor = text[max(0, start - 2):start].lower()
    return davor.endswith("0x") or davor.endswith("x")


def _ist_farbwert(treffer: str) -> bool:
    """True fuer RGB-Tripel wie "0 255 200" (CSS-Variablen im Frontend).

    Die Telefon-Erkennung hat schon einmal Vertrauen gekostet, weil sie
    die Jahresspanne 2020-2024 als Rufnummer las. Ein Pruefer, der bei
    korrektem Inhalt Alarm gibt, wird nach dem zweiten Mal ignoriert —
    deshalb hier die enge Ausnahme: drei Gruppen, alle im Bereich
    0..255, per Leerzeichen getrennt. Eine echte Rufnummer sieht so
    nicht aus.
    """
    teile = treffer.split()
    if len(teile) != 3:
        return False
    return all(t.isdigit() and len(t) <= 3 and int(t) <= 255 for t in teile)


# Inline-Code in Backticks. Dort stehen Commit-Hashes, IDs und Codeschnipsel
# — nie die Telefonnummer eines Menschen. Gefunden beim Sweep am 07.08.2026:
# `0462449` (ein Git-Commit) wurde als Rufnummer gemeldet, weil sieben Ziffern
# mit fuehrender Null exakt wie eine aussehen. Bewusst NUR ueber den
# Backtick-Kontext und nicht ueber ein Hex-Muster: ein reines Ziffernmuster
# wuerde auch echte Rufnummern verschlucken.
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _ist_fiktive_nummer(wert: str) -> bool:
    """Rufnummern nach der 555-Fiktionskonvention (v1.7.16).

    Musterdaten brauchen Telefonnummern, die erkennbar KEINE echten sind
    — international ueblich ist dafuer der 555-Block (Filme, Lehrbuecher).
    PBP nutzt ihn in den Musterprofilen (docs/screenshots/musterprofile.py).
    Ohne diese Regel meldet der Pruefer bei korrekten Musterdaten Alarm,
    und ein Pruefer, dem man nicht glaubt, verhindert nichts.

    Eng gefasst: der Teilnehmerteil (nach der Vorwahl) muss mit 555
    BEGINNEN. Eine echte Nummer, in der zufaellig 555 vorkommt, faellt
    nicht darunter.
    """
    ziffern = re.sub(r"\D", "", wert)
    if ziffern.startswith("0049"):
        ziffern = "0" + ziffern[4:]
    elif ziffern.startswith("49") and len(ziffern) > 10:
        ziffern = "0" + ziffern[2:]
    # Vorwahl: 0 + 2-5 Stellen, danach der Teilnehmerteil
    for vorwahl_laenge in range(3, 7):
        if len(ziffern) > vorwahl_laenge and ziffern[vorwahl_laenge:].startswith("555"):
            return True
    return False


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


# === Quellen-Keys: dokumentierte DoD-9-Ausnahme ==================
# Einige Portale und Personaldienstleister sind BEIDES: reale Vermittler
# aus der Bewerbungshistorie (dann PII) UND technische Quellen-Keys im
# SOURCE_REGISTRY (dann ein Feature, ueber das Issues, Wiki und
# Release-Notes zwangslaeufig sprechen muessen). Die DoD nennt sie
# ausdruecklich als Ausnahme — bisher musste man sie pro Artefakt von
# Hand freischalten (siehe AUSNAHMEN in gh_pii_sweep.py).
#
# Unterschieden wird ueber die SCHREIBWEISE, weil sie den Kontext
# zuverlaessig verraet:
#   `ferchau`, ferchau        -> technischer Key aus dem Registry  = erlaubt
#   FERCHAU, Ferchau GmbH     -> Firmen-Nennung, i.d.R. Historie   = PII
# Damit bleibt der Pruefer fuer den eigentlichen Schutzfall scharf.
_QUELLEN_KEYS = {
    "adzuna", "arbeitnow", "berufsstart", "bundesagentur", "ferchau",
    "freelance_de", "freelancermap", "google_jobs", "greenhouse", "gulp",
    "hays", "heise_jobs", "himalayas", "indeed", "ingenieur_de",
    "jobware", "kimeta", "linkedin", "meinestadt", "monster", "personio",
    "praktikum_de", "remoteok", "remotive", "solcom",
    "stellenanzeigen_de", "stepstone", "studentjob", "workable",
    "workday_dax", "xing",
}


def _ist_quellen_key(treffer: str) -> bool:
    """True, wenn der Treffer als technischer Quellen-Key geschrieben ist."""
    roh = (treffer or "").strip()
    return roh.islower() and roh.replace("-", "_") in _QUELLEN_KEYS


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
            if _ist_quellen_key(label) or _ist_quellen_klasse(label, text):
                continue  # technischer Quellen-Key, DoD-9-Ausnahme
            hits.append(f"FIRMA: {label}")
    for m in set(_GERMAN_CORP_RE.findall(text)):
        label = m if isinstance(m, str) else " ".join(filter(None, m))
        if ("<" not in label and not _ist_fiktiv(label)
                and not _ist_stoppwort_kopf(label)
                and not _ist_platzhalter_kopf(label)):
            hits.append(f"CORP: {label}")
    for m in set(_EMAIL_RE.findall(text)):
        if not _is_safe_email(m):
            hits.append(f"EMAIL: {m}")
    gesehen_tel: set[str] = set()
    for m in _PHONE_RE.finditer(text):
        if _ist_farbwert(m.group(0)):
            continue
        if _ist_hex_konstante(text, m.start()):
            continue
        wert = m.group(0)
        if wert in gesehen_tel:
            continue
        if len(wert.replace(" ", "").replace("-", "")) < 7:
            continue
        # Commit-Hashes, IDs und Codeschnipsel stehen in Backticks
        if _in_inline_code(text, m.start(), m.end()):
            continue
        if _ist_fiktive_nummer(wert):
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


def _stdio_utf8() -> None:
    """Meldungen enthalten Gedankenstriche und Umlaute — unter cp1252
    wuerden sie als '?' erscheinen oder die Ausgabe abbrechen."""
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def main() -> int:
    _stdio_utf8()
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

    # sys.stdin.read() nimmt unter Windows die ANSI-Codepage (cp1252).
    # UTF-8-Eingabe kommt dann verstuemmelt an: "Grün & Söhne GmbH" wird
    # zu "GrÃ¼n & SÃ¶hne GmbH" — und passt auf KEIN Erkennungsmuster mehr.
    # Der Pruefer haette solche Namen also durchgewinkt (falsch-negativ in
    # einem Schutzwerkzeug), und meldete umgekehrt Fehlalarme, weil
    # deutsche Anfuehrungszeichen zerfielen. Deshalb hart UTF-8.
    text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
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
