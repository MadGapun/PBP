"""Die oeffentliche LinkedIn-Stellenseite lesen (#1085).

Der allgemeine Leser (`text_aus_html`) nimmt das ERSTE Element mit
"description" in der Klasse. Auf LinkedIn war das mal der Gehaltskasten
("Base pay range ..."), mal der Beschreibungsblock samt vorangestelltem
Kasten "Direct message the job poster from <Firma>" — mit Name und
Funktion einer Person. Der Name stand danach im Anzeigentext, also dort,
wo Scoring, Fit-Analyse und jeder Export ihn lesen.

Die Kaesten werden deshalb aus dem DOM entfernt, BEVOR Text entsteht.
Mit Textmustern ueber den fertigen Text zu schneiden hiesse, den Namen
erst in einen String zu holen und dann zu hoffen, dass das Muster ihn
trifft.

Die Klassen stammen aus der bekannten Struktur der oeffentlichen Seite
(`show-more-less-html__markup`, `description__text`, `compensation`,
`message-the-recruiter`). Eine Nachmessung an echten Seiten war aus der
Entwicklungsumgebung nicht moeglich (Netz gesperrt); deshalb erkennt der
Kasten zur Ansprechperson zusaetzlich an seiner Ueberschrift, nicht nur
an der Klasse.
"""
from __future__ import annotations

import re

#: Woran eine oeffentliche LinkedIn-Stellenseite zu erkennen ist.
_MERKMALE = ("show-more-less-html", "description__text", "top-card-layout",
             "decorated-job-posting")

#: Beschreibungsblock, in dieser Reihenfolge.
_BESCHREIBUNG = (".show-more-less-html__markup", ".description__text",
                 "[class*='show-more-less-html']")

#: Ueberschriften des Kastens zur Ansprechperson (englisch und deutsch).
_ANSPRECH_KOPF = re.compile(
    r"^\s*(direct message the job poster|meet the hiring team|"
    r"direktnachricht an (den|die) (stellenanbieter|inserent)|"
    r"lernen sie das (einstellungs|recruiting)team kennen)", re.I)

_GEHALT_KLASSEN = ("compensation", "salary")
_GEHALT_WORTE = re.compile(r"pay range|base pay|gehaltsspanne|vergütungsspanne", re.I)


def ist_linkedin_seite(soup) -> bool:
    html = str(soup)[:200000]
    return "linkedin" in html.lower() and any(m in html for m in _MERKMALE)


def _klassen(el) -> str:
    return " ".join(el.get("class") or []).lower()


def _ist_oder_enthaelt_beschreibung(el) -> bool:
    """`select_one` sucht nur unter dem Element — der Beschreibungsblock
    SELBST zaehlt aber auch. Sonst wanderte die Suche nach dem Behaelter
    des Kastens bis zum Block hinauf und entfernte die ganze Anzeige."""
    k = _klassen(el)
    if "show-more-less-html" in k or "description__text" in k:
        return True
    return any(el.select_one(s) for s in _BESCHREIBUNG)


def _ansprech_kaesten(soup) -> list:
    """Die Kaesten zur Ansprechperson — per Klasse oder per Ueberschrift."""
    kaesten = [el for el in soup.find_all(True)
               if "message-the-recruiter" in _klassen(el)
               or "hiring-team" in _klassen(el)]
    for kopf in soup.find_all(["h2", "h3", "h4", "p", "span", "div"]):
        if kopf.find(True) is not None and kopf.name == "div":
            continue  # nur Blattknoten als Ueberschrift
        if not _ANSPRECH_KOPF.match(kopf.get_text(" ", strip=True) or ""):
            continue
        # der naechste Container, der NICHT den Anzeigentext umschliesst
        behaelter = kopf
        for vorfahr in kopf.parents:
            if vorfahr.name in ("body", "html", "[document]", "main"):
                break
            if _ist_oder_enthaelt_beschreibung(vorfahr):
                break
            behaelter = vorfahr
            if vorfahr.name == "section":
                break
        kaesten.append(behaelter)
    return kaesten


def _ist_gehaltskasten(el) -> bool:
    return any(w in _klassen(el) for w in _GEHALT_KLASSEN)


def _gehalt_kaesten(soup) -> list:
    """Die aeussersten Elemente mit Gehaltsklasse."""
    return [el for el in soup.find_all(True)
            if _ist_gehaltskasten(el)
            and not any(_ist_gehaltskasten(v) for v in el.parents if hasattr(v, "get"))]


def bereinigen(soup) -> dict:
    """Entfernt Ansprech- und Gehaltskasten aus dem DOM (in place).

    Rueckgabe: `gehalt_text` (Text des Gehaltskastens, fuer die eigene
    Auswertung) und `entfernt` (wie viele Kaesten)."""
    entfernt = 0
    for el in _ansprech_kaesten(soup):
        if el.parent is not None:
            el.decompose()
            entfernt += 1
    gehalt = []
    for el in _gehalt_kaesten(soup):
        if el.parent is None:
            continue
        text = el.get_text(" ", strip=True)
        if text:
            gehalt.append(text)
        el.decompose()
        entfernt += 1
    return {"gehalt_text": " ".join(gehalt), "entfernt": entfernt}


def beschreibung(soup):
    """Der Beschreibungsblock — oder None."""
    for sel in _BESCHREIBUNG:
        el = soup.select_one(sel)
        if el is not None:
            return el
    return None


def nur_gehaltskasten(text: str) -> bool:
    """Ein "Anzeigentext", der nur aus dem Gehaltskasten besteht."""
    t = (text or "").strip()
    return bool(t) and len(t) < 400 and bool(_GEHALT_WORTE.search(t))


def traegt_ansprechkasten(text: str) -> bool:
    """Ein gespeicherter Text, in dem der Kasten zur Ansprechperson steht —
    fuer die Auswahl des Bestands, nicht zum Schneiden."""
    return any(_ANSPRECH_KOPF.match(z) for z in (text or "").splitlines()[:15])


# ── Gehalt aus dem Kasten ───────────────────────────────────────────

_BETRAG = re.compile(
    r"(?P<w>[€$£]|EUR|USD|GBP)\s?(?P<z>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"\s*(?:/\s*(?P<e>yr|year|jahr|hr|hour|std|stunde|mo|month|monat))?", re.I)


def _zahl(z: str) -> float:
    # englisch "70,000.00", deutsch "70.000,00"
    if re.search(r",\d{1,2}$", z):
        z = z.replace(".", "").replace(",", ".")
    else:
        z = z.replace(",", "")
    return float(z)


def gehalt_aus_kasten(text: str) -> dict | None:
    """{"min", "max", "art", "beleg"} aus dem Gehaltskasten — nur eindeutig.

    Eindeutig heisst: zwei Betraege derselben Einheit (oder einer), und
    die Werte liegen in den Plausibilitaetsgrenzen der Gehaltserkennung."""
    from ..services.gehalt_extraktion import GRENZEN
    treffer = list(_BETRAG.finditer(text or ""))
    if not treffer or len(treffer) > 2:
        return None
    einheiten = [(t.group("e") or "yr").lower()[:2] for t in treffer]
    if len(set(einheiten)) != 1:
        return None
    einheit = einheiten[0]
    try:
        werte = [_zahl(t.group("z")) for t in treffer]
    except ValueError:
        return None
    if einheit in ("mo",):
        werte = [w * 12 for w in werte]
        art = "jaehrlich"
    elif einheit in ("hr", "ho", "st"):
        art = "stuendlich"
    else:
        art = "jaehrlich"
    unten, oben = GRENZEN[art]
    if not all(unten <= w <= oben for w in werte):
        return None
    lo, hi = min(werte), max(werte)
    return {"min": lo, "max": hi, "art": art, "beleg": (text or "").strip()[:200]}
