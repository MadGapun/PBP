"""Die Ernte eines Browserlaufs nach PBP uebernehmen (#1187 Stufe 2).

## Warum es das gibt

Nach einem Lauf ueber sechs Browser-Quellen (StepStone, XING, Indeed, Google Jobs, Heise, LinkedIn) mit rund 1.300 Rohtreffern
stand keine einzige Stelle in PBP. Vier Ursachen: Die Anleitungen liessen Claude auswaehlen, was "passt" (Stufe 1 hat die Regel
gedreht: im Zweifel eintragen), die Werkzeuge widersprachen sich, **nur LinkedIn hatte einen Sammelweg**, und ein Lauf ohne
Anlage hinterliess nirgends eine Spur — er tauchte weder im Trichter noch in der Langzeit-Auswertung auf.

## Was dieses Modul haelt

Die reinen Teile des gemeinsamen Werkzeugs `browser_treffer_uebernehmen` (tools/jobs.py): der Trichter, sein Text, und die
Frage, ob ein Eintrag einen Anker traegt. Die Anlage selbst laeuft durch `_stelle_uebernehmen` — dieselben Regeln wie
`stelle_manuell_anlegen` und `linkedin_treffer_uebernehmen`; eine zweite Fassung waere das Muster aus #963.

Abgrenzung: `browser_handoff` schreibt die Anleitungen an Claude (vor dem Lauf), `job_scraper/handoff` baut die Such-URLs;
hier steht, was NACH dem Lauf mit der Ernte geschieht. `scraper_runs` (B25) bekommt den Lauf ueber
`Database.record_browser_run`, ohne den Gesundheitszustand der Quelle anzufassen: ein Browserlauf ist kein Scraper-Lauf, und
"0 neu" darf keine Quelle abschalten.
"""
from __future__ import annotations

#: Eine Anzeige ohne Volltext ist trotzdem eine Stelle (Regel "im Zweifel eintragen"); ihren Text holt
#: `stellenbeschreibung_nachladen`. Darunter gilt der Text als nicht gelesen (dieselbe Grenze wie `datenguete`).
URTEILE = ("EMPFOHLEN", "BEDINGT", "NICHT_EMPFOHLEN", "NICHT_BEURTEILBAR")

GRUND_TEXTE = {
    "titel_oder_firma_fehlt": "Titel oder Firma fehlt",
    "kein_anker": "weder Adresse noch Anzeigentext",
    "google_original_fehlt": "Google-Karte ohne Original (weder Detail-Adresse noch Text)",
    "duplikat_aktiv": "schon als aktive Stelle da",
    "duplikat_beworben": "schon eine Bewerbung",
    "blacklist": "Firma steht auf der Blacklist",
    "abgewiesen": "von der Anlage abgewiesen",
    "kein_eintrag": "kein gültiger Eintrag",
}


def trichter_leer() -> dict:
    return {
        "rohtreffer": 0,
        "uebergeben": 0,
        "volltexte_gelesen": 0,
        "angelegt": 0,
        "ohne_volltext": 0,
        "ohne_anker": 0,
        "mit_urteil": 0,
        "nach_lesen_aussortiert": 0,
        "kontakte": 0,
        "uebersprungen": 0,
        "gruende": {},
    }


def hat_anker(url, beschreibung, min_beschreibung: int) -> bool:
    """Adresse oder Anzeigentext - die Stelle muss fuer den Menschen etwas sein, in das er sich einlesen kann (#766)."""
    u = str(url or "").strip().lower()
    return u.startswith(("http://", "https://")) or len(str(beschreibung or "").strip()) >= min_beschreibung


def trichter_text(t: dict) -> str:
    """Der Trichter in einem Satz - ehrlich auch bei Null."""
    teile = [f"{t['rohtreffer']} Rohtreffer", f"{t['uebergeben']} übergeben", f"{t['angelegt']} angelegt"]
    davon = []
    if t.get("ohne_volltext"):
        davon.append(f"{t['ohne_volltext']} ohne Volltext")
    if t.get("ohne_anker"):
        davon.append(f"{t['ohne_anker']} ohne verfolgbaren Anker")
    if davon:
        teile[-1] += f" (davon {', '.join(davon)})"
    if t.get("nach_lesen_aussortiert"):
        teile.append(f"{t['nach_lesen_aussortiert']} nach dem Lesen aussortiert")
    if t.get("uebersprungen"):
        gruende = ", ".join(f"{GRUND_TEXTE.get(g, g)}: {n}" for g, n in sorted(t["gruende"].items(), key=lambda x: -x[1]))
        teile.append(f"{t['uebersprungen']} nicht übernommen ({gruende})")
    return ", ".join(teile) + "."
