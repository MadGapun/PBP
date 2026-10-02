"""Eine Firma in allen Quellen, mit der Rolle, in der sie vorkommt (#1080).

`firma_kontext` sah bis v1.7.128 nur Bewerbungen und Stellen — und bei
den Bewerbungen nur das Feld `company`. Eine Firma steht aber an viel
mehr Stellen im Bestand, und jede Stelle sagt etwas anderes:

* als **frueherer oder aktueller Arbeitgeber** im Lebenslauf,
* als **Bewerbungsziel**, direkt oder als **Endkunde hinter einem
  Vermittler**,
* selbst als **Vermittler**,
* als **Projektkunde** in einer Station,
* als Firma eines **Kontakts**,
* in einer **Anfrage** oder **Korrespondenz**,
* in einer **Recherche**,
* auf der **Blacklist**,
* in **Stellen**, aktiv oder aussortiert.

Die Frage "kenne ich die?" hat erst mit allen zusammen eine ehrliche
Antwort — und die teuerste Luecke ist der Endkunde: wer ueber einen
Vermittler bei einer Firma vorgestellt ist und sich dort ein zweites
Mal bewirbt (direkt oder ueber einen anderen Vermittler), ist doppelt
vorgestellt. Das kostet in der Praxis beide Chancen.

## Der Namensvergleich

Dieselbe Firma steht in verschiedenen Schreibweisen im Bestand
(Rechtsform, Umlaut, Bindestrich, Abkuerzung). Verglichen wird deshalb
eine Namensform: klein, Umlaute umschrieben, Satzzeichen und
Rechtsformen weg. Zwei Namen passen, wenn

* ihre Namensform gleich ist, auch ohne Leerzeichen ("gleich"),
* die kuerzere als zusammenhaengende WORTFOLGE in der laengeren steht
  ("teil" — "Acme" in "Acme Solutions GmbH", aber nicht "ki" in
  "Kita": verglichen werden Woerter, keine Buchstabenfolgen), oder
* die kuerzere ein einzelnes Wort ist, das aus den Anfangsbuchstaben
  der laengeren besteht ("abkuerzung"). Das ist der schwaechste
  Abgleich und steht deshalb an jedem Treffer dabei.

Freitext (Notizen, Dokumente, Recherchen) wird nur nach der ganzen
Namensform durchsucht, als Wortfolge, und erst ab vier Zeichen — ein
kurzer Name taucht in Fliesstext zu oft zufaellig auf.

Bewusst NICHT hier: ein Firmen-Stammsatz, der die Schreibweisen
zusammenfasst. Das ist Stufe 2 von #1080 und braucht eine
Nutzerentscheidung. Dieser Dienst schreibt nichts.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from .wiedergaenger import _COMPANY_SUFFIXES, normalize_company
from .menue import pfad

logger = logging.getLogger("bewerbungs_assistent.firmen_bezuege")

#: Woerter, die an einem Firmennamen nichts unterscheiden. Die Liste aus
#: der Wiedergaenger-Erkennung plus die deutsche "gruppe" und das deutsche
#: "und" (#1148: "Mueller & Soehne" und "Mueller und Soehne" sind dieselbe
#: Firma; das "&" verschwindet als Satzzeichen, das "und" blieb stehen —
#: das englische "and" stand schon in der Liste).
_FUELLWOERTER = set(_COMPANY_SUFFIXES) | {"gruppe", "und"}

_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

#: Status, in denen eine Bewerbung nicht mehr laeuft.
ABGESCHLOSSEN = frozenset({
    "abgelehnt", "zurueckgezogen", "angenommen", "abgelaufen",
    "abgesagt", "arbeitgeber_ausgefallen",
})

#: Dokumenttypen, die eine Anfrage oder einen Austausch mit einer Firma
#: festhalten. Lebenslauf, Zeugnis und Vorlage gehoeren nicht dazu —
#: dort steht ein Firmenname, weil er zur eigenen Laufbahn gehoert, und
#: das deckt die Rolle "arbeitgeber" schon ab.
DOKUMENT_ROLLEN = {
    "recruiter_anfrage": "anfrage",
    "vermittler_korrespondenz": "korrespondenz",
    "email": "korrespondenz",
    "absage": "korrespondenz",
    "gespraechs_feedback": "korrespondenz",
    "interview_einladung": "korrespondenz",
    "interview_bestaetigung": "korrespondenz",
    "eingangsbestaetigung": "korrespondenz",
    "bewerbungsantwort": "korrespondenz",
    "angebot": "korrespondenz",
    "stellenbeschreibung": "stellenanzeige",
    "stellenanzeige": "stellenanzeige",
}

#: Rang eines Treffers: wie er gefunden wurde (direkt oder ueber die bestaetigten Schreibweisen vor dem Konzern) und wie
#: gut der Name passt. Kleiner ist besser.
_VIA_RANG = {"direkt": 0, "schreibweise": 0, "mutterfirma": 1, "tochterfirma": 1}
_ART_RANG = {"gleich": 0, "teil": 1, "abkuerzung": 2}

#: Freitext wird erst ab dieser Laenge der Namensform durchsucht.
MIN_TEXTSUCHE = 4

#: Hoechstzahl je Rolle in einer Antwort — die Zahl daneben nennt den Rest.
MAX_JE_ROLLE = 10


def namensform(name: Optional[str]) -> str:
    """Vergleichsform eines Firmennamens; leer fuer Platzhalter (#1028)."""
    if not name or not normalize_company(name):
        return ""
    s = str(name).lower().translate(_UMSCHRIFT)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    woerter = [w for w in s.split() if w not in _FUELLWOERTER]
    return " ".join(woerter)


def _textform(text: Optional[str]) -> str:
    s = (text or "").lower().translate(_UMSCHRIFT)
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", s).split()) + " "


def abgleich(a: str, b: str) -> Optional[str]:
    """Wie zwei Namensformen zueinander passen — oder None.

    Ergebnis: "gleich", "teil" oder "abkuerzung".
    """
    if not a or not b:
        return None
    if a == b or a.replace(" ", "") == b.replace(" ", ""):
        return "gleich"
    kurz, lang = (a, b) if len(a) <= len(b) else (b, a)
    if len(kurz) >= 3 and f" {kurz} " in f" {lang} ":
        return "teil"
    kw, lw = kurz.split(), lang.split()
    if (len(kw) == 1 and 2 <= len(kurz) <= 6 and len(lw) >= 2
            and "".join(w[0] for w in lw) == kurz):
        return "abkuerzung"
    return None


#: Ab so vielen Buchstaben darf eine Suche als Wortanfang gelten (#1148).
MIN_WORTANFANG = 4


def _wortanfang(kurz_woerter: list, lang_woerter: list) -> bool:
    """Steht die kurze Wortfolge am Anfang aufeinanderfolgender langer Woerter?

    Alle Woerter der kurzen Folge ausser dem letzten muessen GANZ passen, das
    letzte darf ein Wortanfang sein: "personal" -> "personalservice",
    "mueller soe" -> "mueller soehne".
    """
    n = len(kurz_woerter)
    if not n or len(kurz_woerter[-1]) < MIN_WORTANFANG:
        return False
    for i in range(len(lang_woerter) - n + 1):
        if (all(lang_woerter[i + j] == kurz_woerter[j] for j in range(n - 1))
                and lang_woerter[i + n - 1].startswith(kurz_woerter[-1])):
            return True
    return False


def aehnliche_namen(db, firmenname: str, limit: int = 8) -> list:
    """Namen aus dem Bestand, die mit der Suche BEGINNEN, aber nicht ganz passen (#1148).

    `abgleich` vergleicht ganze Woerter — das ist richtig fuer Aussagen und
    Warnungen (ein Wortanfang waere dort ein Fehlalarm: "Personal" ist nicht
    jede Firma, deren Name so beginnt). Fuer die ERFOLGLOSE Suche ist es zu
    streng: wer "Personal" tippt und "Personalservice Beispiel" meint,
    bekam "Kein dokumentierter Kontakt". Diese Namen sind deshalb nur
    Kandidaten zum Nachfragen, nie Treffer.
    """
    schluessel = namensform(firmenname)
    if not schluessel:
        return []
    kurz = schluessel.split()
    pid = _profil(db)
    conn = db.connect()
    kandidaten = set()
    for tabelle, spalte in (("applications", "company"), ("applications", "vermittler"),
                            ("applications", "endkunde"), ("jobs", "company"),
                            ("contacts", "company"), ("positions", "company")):
        try:
            for r in conn.execute(
                    f"SELECT DISTINCT {spalte} AS n FROM {tabelle} "
                    "WHERE (profile_id=? OR profile_id IS NULL OR profile_id='') "
                    f"AND {spalte} IS NOT NULL AND TRIM({spalte}) <> ''", (pid,)):
                kandidaten.add(str(r["n"]).strip())
        except Exception:  # noqa: BLE001 — eine Tabelle darf die Suche nie kosten
            continue
    treffer = []
    for name in sorted(kandidaten):
        form = namensform(name)
        if not form or abgleich(schluessel, form) is not None:
            continue  # ein echter Treffer steht schon in der Antwort
        if _wortanfang(kurz, form.split()):
            treffer.append(name)
    return treffer[:max(1, int(limit))]


def im_text(schluessel: str, textform: str) -> bool:
    """True, wenn die Namensform als Wortfolge im Freitext steht."""
    if len(schluessel) < MIN_TEXTSUCHE:
        return False
    return f" {schluessel} " in textform


def _profil(db) -> str:
    try:
        return db.get_active_profile_id() or ""
    except Exception:
        return ""


def _datum(*werte) -> str:
    for w in werte:
        if w:
            return str(w)[:10]
    return ""


def bezuege(db, firmenname: str) -> dict:
    """Alle Stellen im Bestand, an denen die Firma vorkommt.

    Rueckgabe: `bezuege` (Liste mit `rolle`, `quelle`, `name`,
    `abgleich` und rollenabhaengigen Angaben), `rollen` (Anzahl je
    Rolle), `schreibweisen` (die gefundenen Namen), `warnungen`.
    """
    schluessel = namensform(firmenname)
    if not schluessel:
        return {"bezuege": [], "rollen": {}, "schreibweisen": [],
                "warnungen": [], "offene_vorstellungen": []}
    conn = db.connect()
    pid = _profil(db)
    treffer: list[dict] = []

    # --- Firmen-Stammsatz (#1080 Stufe 2) --------------------------------
    # Bestaetigte Schreibweisen derselben Firma sowie Mutter- und Tochterfirma erweitern die Suche; jeder Treffer, der
    # nur ueber den Stammsatz gefunden wurde, sagt es (`via`). Ohne Stammsatz bleibt es bei Stufe 1.
    stamm = {"firma": None, "mehrdeutig": [], "formen": []}
    try:
        from . import firmen_stamm
        r = firmen_stamm.aufloesen(db, firmenname)
        stamm["firma"], stamm["mehrdeutig"] = r["firma"], r["mehrdeutig"]
        if r["firma"]:
            stamm["formen"] = [(f, via) for f, via, _ in firmen_stamm.formen_der_gruppe(db, r["firma"]["id"])]
    except Exception as exc:  # noqa: BLE001 — der Stammsatz ist eine Zugabe: ein Fehler dort kostet die Suche nie
        logger.debug("Firmen-Stammsatz nicht gelesen: %s", exc)
    formen: list[tuple[str, str]] = [(schluessel, "direkt")]
    for form, via in stamm["formen"]:
        if all(form != f for f, _ in formen):
            formen.append((form, via))

    def passt_via(name) -> tuple:
        """(Art des Abgleichs, via) des besten Treffers ueber alle Formen — oder (None, 'direkt')."""
        nf = namensform(name)
        beste = None
        for form, via in formen:
            art = abgleich(form, nf)
            if art:
                rang = (_VIA_RANG.get(via, 1), _ART_RANG[art])
                if beste is None or rang < beste[0]:
                    beste = (rang, art, via)
        return (beste[1], beste[2]) if beste else (None, "direkt")

    def passt(name) -> Optional[str]:
        return passt_via(name)[0]

    def text_passt(textform: str) -> bool:
        return any(im_text(f, textform) for f, _ in formen)

    def mit_via(eintrag: dict, via: str) -> dict:
        if via != "direkt":
            eintrag["via"] = via
        return eintrag

    # --- Bewerbungen: Ziel, Vermittler, Endkunde, Notizen ---------------
    apps = conn.execute(
        "SELECT id, title, company, vermittler, endkunde, status, notes, "
        "       applied_at, created_at "
        "FROM applications WHERE (profile_id=? OR profile_id IS NULL "
        "OR profile_id='')", (pid,)).fetchall()
    app_ids: set = set()
    offene: list[dict] = []
    vermutet: list[dict] = []
    for a in apps:
        offen = (a["status"] or "") not in ABGESCHLOSSEN
        basis = {"quelle": "bewerbung", "bewerbung_id": (a["id"] or "")[:8],
                 "titel": a["title"], "status": a["status"],
                 "datum": _datum(a["applied_at"], a["created_at"])}
        gefunden = False
        for feld, rolle in (("company", "bewerbungsziel"),
                            ("vermittler", "vermittler"),
                            ("endkunde", "endkunde")):
            art, via = passt_via(a[feld])
            if not art:
                continue
            gefunden = True
            eintrag = mit_via(dict(basis, rolle=rolle, name=a[feld], abgleich=art), via)
            if rolle == "endkunde" and a["vermittler"]:
                eintrag["ueber_vermittler"] = a["vermittler"]
            if rolle == "vermittler" and a["endkunde"]:
                eintrag["fuer_endkunde"] = a["endkunde"]
            treffer.append(eintrag)
            if offen and rolle in ("bewerbungsziel", "endkunde"):
                offene.append(eintrag)
        if not gefunden and text_passt(_textform(a["notes"])):
            gefunden = True
            eintrag = dict(basis, rolle="in_notizen_erwaehnt",
                           name=a["company"], abgleich="text")
            if a["vermittler"]:
                eintrag["ueber_vermittler"] = a["vermittler"]
            treffer.append(eintrag)
            if offen and a["vermittler"] and not a["endkunde"]:
                # Moeglicherweise der Endkunde — nur benannt, nicht
                # als Vorstellung gezaehlt (#1080: nie raten).
                eintrag["moeglicher_endkunde"] = True
                vermutet.append(eintrag)
        if gefunden:
            app_ids.add(a["id"])

    # --- Lebenslauf: Stationen und Projekte -----------------------------
    try:
        stationen = conn.execute(
            "SELECT id, company, title, start_date, end_date, is_current "
            "FROM positions WHERE (profile_id=? OR profile_id IS NULL "
            "OR profile_id='')", (pid,)).fetchall()
    except Exception:
        stationen = []
    for p in stationen:
        art, via = passt_via(p["company"])
        if art:
            aktuell = bool(p["is_current"]) or not (p["end_date"] or "").strip()
            treffer.append(mit_via({
                "rolle": "arbeitgeber_aktuell" if aktuell else "arbeitgeber_frueher",
                "quelle": "lebenslauf", "name": p["company"], "abgleich": art,
                "position_id": p["id"], "titel": p["title"],
                "von": p["start_date"], "bis": p["end_date"] or ""}, via))
    try:
        projekte = conn.execute(
            "SELECT pr.id, pr.name, pr.customer_name, pr.is_confidential, "
            "       pr.position_id, "
            "       po.company AS arbeitgeber "
            "FROM projects pr JOIN positions po ON po.id = pr.position_id "
            "WHERE (po.profile_id=? OR po.profile_id IS NULL "
            "OR po.profile_id='')", (pid,)).fetchall()
    except Exception:
        projekte = []
    for pr in projekte:
        art, via = passt_via(pr["customer_name"])
        if art:
            eintrag = mit_via({"rolle": "projektkunde", "quelle": "lebenslauf",
                               "name": pr["customer_name"], "abgleich": art,
                               "projekt_id": pr["id"], "position_id": pr["position_id"],
                               "bei_arbeitgeber": pr["arbeitgeber"]}, via)
            if pr["is_confidential"]:
                eintrag["vertraulich"] = True
            else:
                eintrag["projekt"] = pr["name"]
            treffer.append(eintrag)

    # --- Kontakte ---------------------------------------------------------
    try:
        kontakte = conn.execute(
            "SELECT id, full_name, company, position FROM contacts "
            "WHERE (profile_id=? OR profile_id IS NULL OR profile_id='')",
            (pid,)).fetchall()
    except Exception:
        kontakte = []
    for k in kontakte:
        art, via = passt_via(k["company"])
        if art:
            treffer.append(mit_via({"rolle": "kontakt", "quelle": "kontakte",
                                    "name": k["company"], "abgleich": art,
                                    "kontakt_id": k["id"], "person": k["full_name"],
                                    "funktion": k["position"] or ""}, via))

    # --- Anfragen und Korrespondenz --------------------------------------
    typen = tuple(DOKUMENT_ROLLEN)
    try:
        docs = conn.execute(
            "SELECT id, filename, doc_type, extracted_text, "
            "       linked_application_id, created_at FROM documents "
            f"WHERE doc_type IN ({','.join('?' * len(typen))}) "
            "AND (profile_id=? OR profile_id IS NULL OR profile_id='')",
            (*typen, pid)).fetchall()
    except Exception:
        docs = []
    for d in docs:
        im_namen = text_passt(_textform(d["filename"]))
        if im_namen or text_passt(_textform(d["extracted_text"])):
            treffer.append({
                "rolle": DOKUMENT_ROLLEN.get(d["doc_type"], "korrespondenz"),
                "quelle": "dokument", "name": d["filename"],
                "abgleich": "text", "dokument_id": d["id"],
                "typ": d["doc_type"], "datum": _datum(d["created_at"]),
                "bewerbung_id": (d["linked_application_id"] or "")[:8]})

    # --- Recherchen -------------------------------------------------------
    try:
        notizen = conn.execute(
            "SELECT id, bewerbung_id, kategorie, text, created_at "
            "FROM research_notes WHERE (profile_id=? OR profile_id IS NULL "
            "OR profile_id='')", (pid,)).fetchall()
    except Exception:
        notizen = []
    for r in notizen:
        if r["bewerbung_id"] in app_ids or text_passt(_textform(r["text"])):
            treffer.append({"rolle": "recherche", "quelle": "recherche",
                            "name": firmenname, "abgleich": "text"
                            if r["bewerbung_id"] not in app_ids else "bewerbung",
                            "recherche_id": r["id"], "kategorie": r["kategorie"],
                            "datum": _datum(r["created_at"]),
                            "bewerbung_id": (r["bewerbung_id"] or "")[:8]})

    # --- Blacklist --------------------------------------------------------
    try:
        for b in db.get_blacklist(include_inactive=False) or []:
            if (b.get("type") or "") not in ("firma", "company"):
                continue
            art, via = passt_via(b.get("value"))
            if art:
                treffer.append(mit_via({"rolle": "blacklist", "quelle": "blacklist",
                                        "name": b.get("value"), "abgleich": art,
                                        "grund": b.get("reason") or ""}, via))
    except Exception:
        pass

    rollen: dict = {}
    for t in treffer:
        rollen[t["rolle"]] = rollen.get(t["rolle"], 0) + 1
    schreibweisen = sorted({t["name"] for t in treffer
                            if t.get("abgleich") not in ("text", "bewerbung")
                            and t.get("name")})
    return {"bezuege": treffer, "rollen": rollen,
            "schreibweisen": schreibweisen,
            "warnungen": doppelvorstellung(offene, vermutet),
            "offene_vorstellungen": offene,
            "stammsatz": stamm["firma"], "stammsatz_mehrdeutig": stamm["mehrdeutig"],
            "formen": [f for f, _ in formen]}


#: Wo ein Bezug im Dashboard steht und mit welchem Werkzeug er sich
#: oeffnen laesst. `firma_kontext` schreibt die Details nicht mit — der
#: Verweis fuehrt dorthin, wo sie stehen (Nutzerwort 25.09.2026).
def verweis(e: dict) -> dict:
    rolle, quelle = e.get("rolle"), e.get("quelle")
    if quelle == "bewerbung" or (rolle == "recherche" and e.get("bewerbung_id")):
        return {"bereich": "Bewerbungen › Timeline",
                "oeffnen": f"bewerbung_details('{e.get('bewerbung_id')}')"}
    if rolle in ("arbeitgeber_frueher", "arbeitgeber_aktuell"):
        return {"bereich": "Profil › Berufserfahrung",
                "oeffnen": f"positionen_anzeigen(nur_id='{e.get('position_id')}')"}
    if rolle == "projektkunde":
        return {"bereich": "Profil › Berufserfahrung",
                "oeffnen": f"projekte_anzeigen(position_id='{e.get('position_id')}')"}
    if rolle == "kontakt":
        return {"bereich": "Kontakte",
                "oeffnen": f"kontakt_anzeigen('{e.get('kontakt_id')}')"}
    if quelle == "dokument":
        return {"bereich": "Docs",
                "oeffnen": f"dokument_lesen('{e.get('dokument_id')}')"}
    if rolle == "blacklist":
        return {"bereich": pfad("blacklist"),
                "oeffnen": "blacklist_verwalten(aktion='anzeigen')"}
    return {"bereich": "Recherche", "oeffnen": ""}


def _kurz(e: dict) -> str:
    rolle = e.get("rolle")
    if rolle in ("arbeitgeber_frueher", "arbeitgeber_aktuell"):
        return f"{e.get('titel') or ''}, {e.get('von') or '?'} bis {e.get('bis') or 'heute'}"
    if rolle == "projektkunde":
        was = "vertrauliches Projekt" if e.get("vertraulich") else (e.get("projekt") or "Projekt")
        return f"{was} bei {e.get('bei_arbeitgeber') or '?'}"
    if rolle == "kontakt":
        return ", ".join(x for x in (e.get("person"), e.get("funktion")) if x)
    if e.get("quelle") == "dokument":
        return f"{e.get('typ')}, {e.get('datum') or 'ohne Datum'}"
    if rolle == "recherche":
        return f"{e.get('kategorie')}, {e.get('datum') or 'ohne Datum'}"
    if rolle == "blacklist":
        return e.get("grund") or "ohne Begruendung"
    teile = [e.get("titel"), e.get("status")]
    if e.get("ueber_vermittler"):
        teile.append(f"ueber {e['ueber_vermittler']}")
    return ", ".join(x for x in teile if x)


def kompakt(e: dict) -> dict:
    """Ein Bezug als Verweis: Rolle, Name, eine Zeile, wo er steht."""
    aus = {"rolle": e.get("rolle"), "name": e.get("name"), "kurz": _kurz(e)}
    if e.get("abgleich") == "abkuerzung":
        aus["abgleich"] = "abkuerzung"
    if e.get("via"):
        aus["via"] = e["via"]       # gefunden ueber eine bestaetigte Schreibweise oder die Mutter-/Tochterfirma
    if e.get("moeglicher_endkunde"):
        aus["moeglicher_endkunde"] = True
    aus.update({k: v for k, v in verweis(e).items() if v})
    return aus


def doppelvorstellung(offene: list[dict],
                      vermutet: Optional[list] = None) -> list[str]:
    """Warnung, wenn bei der Firma schon eine Vorstellung laeuft.

    Laeuft eine Bewerbung ueber einen Vermittler, ist der Mensch dort
    vorgestellt — eine direkte Bewerbung oder ein zweiter Vermittler
    waere eine Doppelvorstellung. Laufen schon zwei Kanaele, wird das
    ausdruecklich gesagt.
    """
    warnungen = []
    for v in vermutet or []:
        warnungen.append(
            f"Pruefen: eine laufende Bewerbung über {v.get('ueber_vermittler')} "
            f"({v.get('titel') or 'Bewerbung'}, {v.get('bewerbung_id')}) nennt "
            "diese Firma in den Notizen, trägt aber keinen Endkunden. Ist sie "
            "der Endkunde, bist du dort schon vorgestellt — dann mit "
            "bewerbung_bearbeiten(endkunde=...) nachtragen.")
    if not offene:
        return warnungen
    # #1080 Stufe 2: eine laufende Bewerbung bei Mutter- oder Tochterfirma ist derselbe Konzern - gemeldet, nicht verschmolzen.
    for o in offene:
        if o.get("via") in ("mutterfirma", "tochterfirma"):
            beziehung = "Mutterfirma" if o["via"] == "mutterfirma" else "Tochterfirma"
            warnungen.append(
                f"Laufende Bewerbung bei der {beziehung} {o.get('name')} ({o.get('titel') or 'Bewerbung'}, {o.get('bewerbung_id')}). "
                "Das ist derselbe Konzern: vor einer weiteren Bewerbung hier klären, ob das zusammenpasst.")
    offene = [o for o in offene if o.get("via") not in ("mutterfirma", "tochterfirma")]
    if not offene:
        return warnungen
    kanaele = sorted({(o.get("ueber_vermittler") or "direkt") for o in offene})
    ueber_vermittler = [o for o in offene if o["rolle"] == "endkunde"]
    if len(kanaele) >= 2:
        warnungen.append(
            "DOPPELVORSTELLUNG: Bei dieser Firma laufen schon Bewerbungen "
            f"über mehrere Wege ({', '.join(kanaele)}). Vor jedem weiteren "
            "Schritt klären, welcher Weg gilt.")
    elif ueber_vermittler:
        v = ueber_vermittler[0].get("ueber_vermittler") or "einen Vermittler"
        warnungen.append(
            f"Laufende Vorstellung über {v} "
            f"({ueber_vermittler[0].get('titel') or 'Bewerbung'}). Eine "
            "direkte Bewerbung oder ein zweiter Vermittler für diese Firma "
            "wäre eine Doppelvorstellung.")
    return warnungen


def namen_im_bestand(db) -> list:
    """Alle Firmennamen des Bestands mit ihrer Herkunft: [(Name, 'bewerbung'|'lebenslauf'|'kontakt'|'projekt')].

    Die eine Quelle fuer den Bestandsbericht UND die Vorschlaege des Firmen-Stammsatzes (#1080 Stufe 2)."""
    conn = db.connect()
    pid = _profil(db)
    namen: list[tuple[str, str]] = []   # (Name, Herkunft)

    def sammeln(sql: str, herkunft: str, spalten: tuple):
        try:
            for r in conn.execute(sql, (pid,)).fetchall():
                for s in spalten:
                    if r[s]:
                        namen.append((str(r[s]).strip(), herkunft))
        except Exception:
            pass

    bedingung = "(profile_id=? OR profile_id IS NULL OR profile_id='')"
    sammeln(f"SELECT company, vermittler, endkunde FROM applications WHERE {bedingung}",
            "bewerbung", ("company", "vermittler", "endkunde"))
    sammeln(f"SELECT company FROM positions WHERE {bedingung}", "lebenslauf", ("company",))
    sammeln(f"SELECT company FROM contacts WHERE {bedingung}", "kontakt", ("company",))
    sammeln("SELECT pr.customer_name FROM projects pr JOIN positions po "
            "ON po.id = pr.position_id WHERE (po.profile_id=? OR "
            "po.profile_id IS NULL OR po.profile_id='')", "projekt", ("customer_name",))
    return namen


def bestandsbericht(db, max_je_liste: int = 25) -> dict:
    """Wo die Firmennamen im Bestand auseinanderlaufen — nur lesend.

    * `schreibweisen`: Namen, die nach der Namensform dieselbe Firma
      sind, aber verschieden geschrieben stehen.
    * `endkunde_nur_in_notizen`: Bewerbungen ueber einen Vermittler ohne
      eingetragenen Endkunden, deren Notizen eine bekannte Firma nennen.
      Ohne den Eintrag kann `firma_kontext` die Doppelvorstellung nicht
      erkennen.
    """
    conn = db.connect()
    pid = _profil(db)
    bedingung = "(profile_id=? OR profile_id IS NULL OR profile_id='')"
    namen = namen_im_bestand(db)

    gruppen: dict = {}
    for name, herkunft in namen:
        k = namensform(name)
        if not k:
            continue
        g = gruppen.setdefault(k.replace(" ", ""), {"namen": {}, "herkunft": set()})
        g["namen"][name] = g["namen"].get(name, 0) + 1
        g["herkunft"].add(herkunft)
    schreibweisen = [
        {"schreibweisen": sorted(g["namen"]), "vorkommen": sum(g["namen"].values()),
         "herkunft": sorted(g["herkunft"])}
        for g in gruppen.values() if len(g["namen"]) >= 2
    ]
    schreibweisen.sort(key=lambda e: -e["vorkommen"])

    # Endkunde nur in den Notizen
    bekannte = {k for k in (namensform(n) for n, _ in namen)
                if len(k) >= MIN_TEXTSUCHE}
    vermittler_formen = set()
    offen_ohne = []
    try:
        apps = conn.execute(
            "SELECT id, title, company, vermittler, endkunde, status, notes "
            f"FROM applications WHERE {bedingung}", (pid,)).fetchall()
    except Exception:
        apps = []
    for a in apps:
        for s in ("vermittler",):
            if a[s]:
                vermittler_formen.add(namensform(a[s]))
    for a in apps:
        if (a["endkunde"] or "").strip() or not (a["vermittler"] or "").strip():
            continue
        text = _textform(a["notes"])
        eigene = {namensform(a["company"]), namensform(a["vermittler"])}
        genannt = sorted(k for k in bekannte
                         if k not in eigene and k not in vermittler_formen
                         and im_text(k, text))
        if genannt:
            offen_ohne.append({
                "bewerbung_id": (a["id"] or "")[:8], "titel": a["title"],
                "vermittler": a["vermittler"], "status": a["status"],
                "laeuft": (a["status"] or "") not in ABGESCHLOSSEN,
                "genannte_firmen": genannt})
    offen_ohne.sort(key=lambda e: not e["laeuft"])

    return {
        "schreibweisen_anzahl": len(schreibweisen),
        "schreibweisen": schreibweisen[:max_je_liste],
        "endkunde_nur_in_notizen_anzahl": len(offen_ohne),
        "endkunde_nur_in_notizen": offen_ohne[:max_je_liste],
        "hinweis": (
            "Nur ein Bericht — PBP ändert hier nichts. Einen Endkunden "
            "trägst du mit bewerbung_bearbeiten(bewerbung_id, endkunde=...) "
            "nach; erst dann erkennt firma_kontext eine laufende Vorstellung "
            "über den Vermittler. Die genannten Firmen sind Namen aus dem "
            "Bestand, die in den Notizen vorkommen — ob einer davon der "
            "Endkunde ist, weisst nur du. Verschiedene Schreibweisen "
            "findet firma_kontext bereits; zusammengeführt werden sie "
            "erst mit einem Firmen-Stammsatz (#1080 Stufe 2)."),
    }
