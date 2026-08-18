"""JSON-LD aus SSR-Hydration-Payloads extrahieren (#925, v1.7.18).

Moderne SPA-Karriereseiten liefern ihre `JobPosting`-Daten haeufig NICHT
als `<script type="application/ld+json">` im DOM aus, sondern escaped
innerhalb der Hydration-Daten:

    {"tag":"script","attributes":{"id":"metaOfferSchema",...},
     "content":"{\"@context\":\"https:\\/\\/schema.org\",
                 \"@type\":\"JobPosting\",...}"}

BeautifulSoup findet dort nichts — der Block ist kein Element, sondern
ein String. Belegter Fall: eine Quelle stand monatelang als tot
markiert und lieferte 0 Stellen, obwohl 25 JobPosting-Objekte pro Seite
ausgeliefert wurden (#925).

Bewusst ein SCANNER statt Regex: das Escaping ist mehrstufig
(`\\/` fuer `/`, `\"` fuer `"`), und ein Regex, der das zuverlaessig
abdeckt, ist weder lesbar noch robust gegen Verschachtelung.
"""
import json
import logging

logger = logging.getLogger("bewerbungs_assistent.scraper.hydration")


def _json_string_ab(text: str, quote_pos: int) -> str | None:
    """Liest ein JSON-String-Literal ab dem oeffnenden Quote."""
    i = quote_pos + 1
    out = []
    while i < len(text):
        c = text[i]
        if c == "\\":
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == '"':
            return "".join(out)
        out.append(c)
        i += 1
    return None


def jsonld_aus_hydration(html: str, typ: str = "JobPosting",
                         marke: str = '"content":"') -> list[dict]:
    """Alle JSON-LD-Objekte vom Typ `typ` aus dem Hydration-Payload.

    Liefert eine leere Liste, wenn nichts gefunden wird — der Aufrufer
    faellt dann auf seinen bisherigen DOM-Pfad zurueck.
    """
    if not html:
        return []
    gefunden: list[dict] = []
    pos = 0
    while True:
        p = html.find(marke, pos)
        if p < 0:
            break
        pos = p + len(marke)
        roh = _json_string_ab(html, p + len(marke) - 1)
        if not roh or "@type" not in roh:
            continue
        try:
            daten = json.loads(json.loads('"' + roh + '"'))
        except (ValueError, TypeError):
            continue
        eintraege = daten if isinstance(daten, list) else [daten]
        for d in eintraege:
            if isinstance(d, dict) and d.get("@type") == typ:
                gefunden.append(d)
    if gefunden:
        logger.debug("Hydration-Payload: %d %s-Objekte", len(gefunden), typ)
    return gefunden


def _json_array_ab(text: str, start: int):
    """Liest ein JSON-Array ab der oeffnenden Klammer (klammer-balanciert)."""
    tiefe = 0
    in_str = False
    i = start
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                tiefe += 1
            elif c == "]":
                tiefe -= 1
                if tiefe == 0:
                    return text[start:i + 1]
        i += 1
    return None


def liste_aus_hydration(html: str, schluessel: str) -> list:
    """Ein JSON-Array aus dem Hydration-Payload (z.B. "Offers").

    Reichhaltiger als der JSON-LD-Block: die Plattform-eigenen Objekte
    tragen Detail-Slug, echte Gehaltsspanne und Arbeitsort-Felder, die
    im schema.org-Auszug fehlen (#925).
    """
    if not html:
        return []
    marke = '"' + schluessel + '":['
    p = html.find(marke)
    if p < 0:
        return []
    roh = _json_array_ab(html, p + len(marke) - 1)
    if not roh:
        return []
    try:
        daten = json.loads(roh)
    except (ValueError, TypeError):
        return []
    return daten if isinstance(daten, list) else []


def entweiche_trennzeichen(text: str) -> str:
    """Entfernt Soft-Hyphens und Zero-Width-Zeichen (#925).

    Die Plattform setzt Trennhinweise MITTEN in die Woerter
    ("Syste\u00adm\u00adadmi\u00adnis\u00adtrator"). Ohne Bereinigung
    matcht kein einziges Keyword — der Titel sieht nur fuer das Auge
    normal aus. Belegt: von 25 Stellen passierten so nur 7 den Filter.
    """
    if not text:
        return ""
    for zeichen in ("\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"):
        text = text.replace(zeichen, "")
    return text
