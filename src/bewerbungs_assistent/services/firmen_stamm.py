"""Der Firmen-Stammsatz: bestätigte Schreibweisen, Mutterfirma, Zuordnung nur nach Bestätigung (#1080, Stufe 2).

Stufe 1 (`firmen_bezuege.py`) findet eine Firma in allen Quellen und gleicht Namen über ihre Form ab (Rechtsform,
Umlaut, Wortfolge). Was sie nicht kann, weiß nur der Mensch:

* ein **früherer Name** („Alt AG“ heißt heute „Neu GmbH“),
* eine **Kurzform** oder ein **Geschäftsbereich**, der nicht wie die Firma klingt,
* die **Mutterfirma**: Tochter und Konzern sollen zusammen gefunden werden, ohne zu verschmelzen.

Dafür gibt es zwei Tabellen: `companies` (Name, Mutterfirma, Branche, Standorte, Notizen) und `company_aliases` (jede bestätigte
Schreibweise). **Bestand und Textfelder bleiben, wie sie sind**: Bewerbungen, Stellen, Kontakte und Lebenslauf tragen weiter
ihren Firmennamen als Text. Der Stammsatz wird erst beim Lesen aufgelöst (`aufloesen`, `formen_der_gruppe`); das ist rückbaubar
und berührt keine laufende Schreibstelle. Jeder Name ist je Profil genau EINER Firma zugeordnet (Namen und Schreibweisen sind
zusammen eindeutig).

Zugeordnet wird nie auf Verdacht: `vorschlaege` leitet aus dem Bestandsbericht ab, welche Schreibweisen vermutlich dieselbe Firma sind;
angelegt wird erst mit Bestätigung des Menschen (`vorschlaege_anwenden(bestaetigt=True)`).

Ein Name, der zu mehreren Firmen passen könnte („Muster“ bei „Muster Energie“ und „Muster Medizin“), wird NICHT geraten:
`aufloesen` meldet ihn als mehrdeutig, und die Suche fällt auf den Namensabgleich der Stufe 1 zurück.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import firmen_bezuege as _fb

logger = logging.getLogger("bewerbungs_assistent.firmen_stamm")

ARTEN = {
    "schreibweise": "Andere Schreibweise",
    "frueherer_name": "Früherer Name",
    "kurzform": "Kurzform",
    "bereich": "Geschäftsbereich",
}
MAX_ALIASE = 60
MAX_NAME = 200
MAX_TIEFE = 8          # so tief darf eine Konzernkette höchstens sein (und so tief wird nach Zyklen gesucht)

_LOCK = threading.RLock()


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pid(db) -> str:
    try:
        return db.get_active_profile_id() or ""
    except Exception:  # noqa: BLE001
        return ""


def _form(name) -> str:
    return _fb.namensform(name)


def _sauber(text, maximal: int = MAX_NAME) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))).strip()[:maximal]


# ── Lesen ────────────────────────────────────────────────────────────────────────────────────────────

def _firma_zeile(r) -> dict:
    return {"id": r["id"], "name": r["name"], "mutterfirma_id": r["parent_id"] or "", "branche": r["branche"] or "",
            "standorte": r["standorte"] or "", "notizen": r["notizen"] or "", "angelegt": r["created_at"]}


def firma_laden(db, firma_id: str) -> Optional[dict]:
    """Eine Firma mit Schreibweisen, Mutterfirma und Tochterfirmen — oder None."""
    conn, pid = db.connect(), _pid(db)
    r = conn.execute("SELECT * FROM companies WHERE id=? AND profile_id=?", (str(firma_id), pid)).fetchone()
    if r is None:
        return None
    f = _firma_zeile(r)
    f["aliase"] = [{"id": a["id"], "alias": a["alias"], "art": a["art"], "art_text": ARTEN.get(a["art"], a["art"])}
                   for a in conn.execute("SELECT id, alias, art FROM company_aliases WHERE company_id=? AND profile_id=? "
                                         "ORDER BY alias COLLATE NOCASE", (f["id"], pid))]
    f["mutterfirma"] = None
    if f["mutterfirma_id"]:
        m = conn.execute("SELECT id, name FROM companies WHERE id=? AND profile_id=?", (f["mutterfirma_id"], pid)).fetchone()
        f["mutterfirma"] = {"id": m["id"], "name": m["name"]} if m else None
    f["tochterfirmen"] = [{"id": k["id"], "name": k["name"]} for k in conn.execute(
        "SELECT id, name FROM companies WHERE parent_id=? AND profile_id=? ORDER BY name COLLATE NOCASE", (f["id"], pid))]
    return f


def firmen_liste(db, suche: str = "") -> list:
    """Alle Firmen des Profils, kompakt: Name, Schreibweisen (Namen), Mutterfirma, Zahl der Tochterfirmen."""
    conn, pid = db.connect(), _pid(db)
    firmen = conn.execute("SELECT * FROM companies WHERE profile_id=? ORDER BY name COLLATE NOCASE", (pid,)).fetchall()
    aliase: dict = {}
    for a in conn.execute("SELECT company_id, alias FROM company_aliases WHERE profile_id=? ORDER BY alias COLLATE NOCASE", (pid,)):
        aliase.setdefault(a["company_id"], []).append(a["alias"])
    namen = {f["id"]: f["name"] for f in firmen}
    kinder: dict = {}
    for f in firmen:
        if f["parent_id"]:
            kinder[f["parent_id"]] = kinder.get(f["parent_id"], 0) + 1
    gesucht = _form(suche) if suche else ""
    erg = []
    for f in firmen:
        alle = [f["name"], *aliase.get(f["id"], [])]
        if gesucht and not any(_fb.abgleich(gesucht, _form(n)) in ("gleich", "teil") for n in alle):
            continue
        erg.append({"id": f["id"], "name": f["name"], "aliase": aliase.get(f["id"], []),
                    "mutterfirma": namen.get(f["parent_id"], "") if f["parent_id"] else "",
                    "tochterfirmen": kinder.get(f["id"], 0), "branche": f["branche"] or ""})
    return erg


# ── Auflösen: welcher Firma gehört dieser Name? ───────────────────────────────────────────────────────────

def _alle_formen(db) -> list:
    """[(Form, Firma-ID, Name der Firma, 'name'|<art>)] für alle Namen und Schreibweisen des Profils."""
    conn, pid = db.connect(), _pid(db)
    erg = [(r["name_form"], r["id"], r["name"], "name") for r in conn.execute(
        "SELECT id, name, name_form FROM companies WHERE profile_id=?", (pid,))]
    erg += [(a["alias_form"], a["company_id"], a["firma"], a["art"]) for a in conn.execute(
        "SELECT a.alias_form, a.company_id, a.art, c.name AS firma FROM company_aliases a "
        "JOIN companies c ON c.id = a.company_id WHERE a.profile_id=?", (pid,))]
    return erg


def aufloesen(db, name) -> dict:
    """Welche Firma ist gemeint? `{'firma': dict|None, 'mehrdeutig': [Namen], 'art': 'exakt'|'abgleich'|''}`.

    Zuerst gilt die ganze Namensform genau (Name oder bestätigte Schreibweise). Findet sich nichts, wird wie in Stufe 1
    abgeglichen (gleiche Wortfolge, 'Acme' in 'Acme Solutions'); passt der Name dann zu GENAU einer Firma, ist es diese,
    sonst steht er in `mehrdeutig` und wird nicht geraten.
    """
    leer = {"firma": None, "mehrdeutig": [], "art": ""}
    form = _form(name)
    if not form:
        return leer
    formen = _alle_formen(db)
    if not formen:
        return leer
    exakt = {fid for f, fid, _, _ in formen if f == form or f.replace(" ", "") == form.replace(" ", "")}
    if len(exakt) == 1:
        return {"firma": firma_laden(db, next(iter(exakt))), "mehrdeutig": [], "art": "exakt"}
    if len(exakt) > 1:      # darf es nach den Regeln nicht geben (Namen sind eindeutig), wird aber nie geraten
        return {"firma": None, "mehrdeutig": sorted({n for f, fid, n, _ in formen if fid in exakt}), "art": ""}
    treffer = {fid for f, fid, _, _ in formen if _fb.abgleich(form, f) in ("gleich", "teil")}
    if len(treffer) == 1:
        return {"firma": firma_laden(db, next(iter(treffer))), "mehrdeutig": [], "art": "abgleich"}
    if len(treffer) > 1:
        return {"firma": None, "mehrdeutig": sorted({n for f, fid, n, _ in formen if fid in treffer}), "art": ""}
    return leer


def formen_der_gruppe(db, firma_id: str) -> list:
    """Alle Namensformen, unter denen diese Firma im Bestand stehen kann: [(Form, via, Anzeigename)].

    `via`: `schreibweise` (Name und bestätigte Schreibweisen der Firma selbst), `mutterfirma`, `tochterfirma` (eine Ebene in
    jede Richtung). Konzernbeziehungen werden gefunden, aber nie als dieselbe Firma behandelt.
    """
    f = firma_laden(db, firma_id)
    if f is None:
        return []
    erg = [(_form(f["name"]), "schreibweise", f["name"])]
    erg += [(_form(a["alias"]), "schreibweise", a["alias"]) for a in f["aliase"]]
    nachbarn = ([("mutterfirma", f["mutterfirma"]["id"])] if f["mutterfirma"] else []) + [("tochterfirma", k["id"]) for k in f["tochterfirmen"]]
    for via, nid in nachbarn:
        n = firma_laden(db, nid)
        if n is None:
            continue
        erg.append((_form(n["name"]), via, n["name"]))
        erg += [(_form(a["alias"]), via, a["alias"]) for a in n["aliase"]]
    gesehen, aus = set(), []
    for form, via, anzeige in erg:
        if form and (form, via) not in gesehen:
            gesehen.add((form, via))
            aus.append((form, via, anzeige))
    return aus


def gleiche_firma(db, a, b) -> bool:
    """Sind `a` und `b` dieselbe Firma — nach der Namensform ODER nach dem Stammsatz? (Konzern zählt nicht.)"""
    fa, fb = _form(a), _form(b)
    if not fa or not fb:
        return False
    if fa == fb or fa.replace(" ", "") == fb.replace(" ", ""):
        return True
    try:
        ra, rb = aufloesen(db, a), aufloesen(db, b)
    except Exception:  # noqa: BLE001 — ein Fehler hier darf eine Duplikat-Erkennung nie kosten
        return False
    return bool(ra["firma"] and rb["firma"] and ra["firma"]["id"] == rb["firma"]["id"])


# ── Nachschlagen für den Duplikat-Abgleich ───────────────────────────────────────────────────────────────

def _wortfolge_in(form: str, text: str) -> bool:
    """Steht `form` als ganze Wortfolge in `text`? (Beide sind schon normalisiert: klein, einfache Leerzeichen.)"""
    return f" {form} " in f" {text} "


class FirmenKanon:
    """Welche Namen sind laut Firmen-Stammsatz dieselbe Firma? Einmal gebaut, danach nur Nachschlagen (#1080).

    Der Duplikat-Abgleich fragt denselben Namen hundertfach (Stelle × Bewerbung); ein Datenbankzugriff je Frage wäre zu teuer.
    Die Schlüssel sind die Formen von `normalize_company_name` — dieselbe Normalisierung, mit der der Abgleich selbst arbeitet —,
    nicht die Namensformen der Stufe 1.

    Der Kanon FÜGT Treffer hinzu und nimmt nie einen weg: Zwei verschiedene Firmen im Stammsatz verhindern keinen Treffer des
    Namensabgleichs (Recall vor Präzision, #951 — eine übersehene Doppelung ist teurer als ein Hinweis zu viel). Mutter- und
    Tochterfirma gelten hier NICHT als dieselbe Firma; eine Form, die zwei Firmen gehört, ordnet er niemandem zu.
    """

    #: Ein Name unter dieser Länge steckt zu oft zufällig in einem anderen, um ihn in einem längeren Namen zu suchen.
    MIN_TEILNAME = 4

    def __init__(self, firmen: dict):
        """`firmen`: {Firma-ID: [normalisierte Namensformen: Name und bestätigte Schreibweisen]}."""
        self._formen_je_firma: dict = {}
        self._firma_je_form: dict = {}
        doppelt = set()
        for fid, formen in firmen.items():
            eigene = []
            for f in formen:
                if not f or f in eigene:
                    continue
                eigene.append(f)
                if self._firma_je_form.get(f, fid) != fid:
                    doppelt.add(f)
                self._firma_je_form[f] = fid
            self._formen_je_firma[fid] = eigene
        for f in doppelt:
            self._firma_je_form.pop(f, None)
        self._gemerkt: dict = {}

    def __bool__(self) -> bool:
        return bool(self._firma_je_form)

    def firma_von(self, norm: str) -> str:
        """Die Kennung der Firma, zu der dieser (normalisierte) Name gehört — oder ''.

        Zuerst gilt die ganze Form genau; findet sich nichts, zählt eine bestätigte Schreibweise, die als ganze Wortfolge im
        Namen steckt („Acme“ in „Acme Deutschland“) — aber nur, wenn es GENAU eine Firma ist. Mehrdeutiges wird nicht geraten.
        """
        if not norm:
            return ""
        if norm in self._gemerkt:
            return self._gemerkt[norm]
        fid = self._firma_je_form.get(norm, "")
        if not fid:
            treffer = {k for form, k in self._firma_je_form.items()
                       if len(form) >= self.MIN_TEILNAME and _wortfolge_in(form, norm)}
            fid = next(iter(treffer)) if len(treffer) == 1 else ""
        self._gemerkt[norm] = fid
        return fid

    def gleich(self, a: str, b: str) -> bool:
        """Sind beide (normalisierten) Namen laut Stammsatz dieselbe Firma?"""
        fa = self.firma_von(a)
        return bool(fa) and fa == self.firma_von(b)

    def formen_von(self, norm: str) -> list:
        """Alle (normalisierten) Namen der Firma, zu der `norm` gehört; leer, wenn der Stammsatz sie nicht kennt."""
        fid = self.firma_von(norm)
        return [f for f in self._formen_je_firma.get(fid, ()) if f in self._firma_je_form] if fid else []


def kanon(db, profile_id: Optional[str] = None) -> Optional[FirmenKanon]:
    """Der Stammsatz als Nachschlagetabelle für den Duplikat-Abgleich — oder None (kein Stammsatz, nicht lesbar).

    None heißt „so abgleichen wie bisher“: ein Fehler hier darf eine Duplikat-Erkennung nie kosten. Mit `profile_id` gilt der
    Stammsatz dieses Profils (der Import schreibt je Profil), sonst der des aktiven.
    """
    try:
        from ..duplicate_detection import normalize_company_name as _norm
        conn = db.connect()
        pid = _pid(db) if profile_id is None else profile_id
        firmen: dict = {}
        for r in conn.execute("SELECT id, name FROM companies WHERE profile_id=?", (pid,)):
            firmen.setdefault(r["id"], []).append(_norm(r["name"]))
        if not firmen:
            return None
        for a in conn.execute("SELECT company_id, alias FROM company_aliases WHERE profile_id=?", (pid,)):
            if a["company_id"] in firmen:
                firmen[a["company_id"]].append(_norm(a["alias"]))
        k = FirmenKanon(firmen)
        return k if k else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Firmen-Stammsatz für den Abgleich nicht lesbar (#1080): %s", exc)
        return None


# ── Schreiben ────────────────────────────────────────────────────────────────────────────────────────

def _form_vergeben(db, form: str, ausser_firma: str = "") -> Optional[dict]:
    """Wem gehört diese Namensform schon? `{'firma_id', 'firma', 'als'}` oder None."""
    for f, fid, name, als in _alle_formen(db):
        if (f == form or f.replace(" ", "") == form.replace(" ", "")) and fid != ausser_firma:
            return {"firma_id": fid, "firma": name, "als": als}
    return None


def _kette_enthaelt(db, start_id: str, gesucht_id: str) -> bool:
    """Liegt `gesucht_id` über `start_id` in der Mutterkette (oder ist es selbst)?"""
    conn, pid = db.connect(), _pid(db)
    aktuell, schritte = start_id, 0
    while aktuell and schritte <= MAX_TIEFE:
        if aktuell == gesucht_id:
            return True
        r = conn.execute("SELECT parent_id FROM companies WHERE id=? AND profile_id=?", (aktuell, pid)).fetchone()
        aktuell = (r["parent_id"] if r else "") or ""
        schritte += 1
    return False


def firma_anlegen(db, name: str, *, mutterfirma_id: str = "", branche: str = "", standorte: str = "", notizen: str = "",
                  aliase=()) -> dict:
    """Legt eine Firma an. Ein Name, der schon einer Firma gehört, wird abgewiesen (statt eine zweite zu bauen)."""
    sauber = _sauber(name)
    form = _form(sauber)
    if not form:
        return {"status": "fehler", "text": "Der Firmenname fehlt oder besteht nur aus einer Rechtsform."}
    with _LOCK:
        gehoert = _form_vergeben(db, form)
        if gehoert:
            return {"status": "schon_da", "text": f"Dieser Name gehört schon zur Firma „{gehoert['firma']}“ (als {ARTEN.get(gehoert['als'], 'Name')}).",
                    "firma_id": gehoert["firma_id"]}
        if mutterfirma_id and firma_laden(db, mutterfirma_id) is None:
            return {"status": "fehler", "text": "Die Mutterfirma gibt es nicht."}
        conn, pid = db.connect(), _pid(db)
        fid = "fi_" + uuid.uuid4().hex[:10]
        conn.execute("INSERT INTO companies (id, profile_id, name, name_form, parent_id, branche, standorte, notizen, created_at, updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (fid, pid, sauber, form, mutterfirma_id or None, _sauber(branche), _sauber(standorte, 400), _sauber(notizen, 4000), _jetzt(), _jetzt()))
        conn.commit()
        hinweise = []
        for a in aliase or ():
            erg = alias_hinzufuegen(db, fid, a)
            if erg["status"] not in ("hinzugefuegt",):
                hinweise.append(erg["text"])
    f = firma_laden(db, fid)
    return {"status": "angelegt", "firma": f, "hinweise": hinweise, "text": f"Die Firma „{sauber}“ ist angelegt."}


def alias_hinzufuegen(db, firma_id: str, alias: str, art: str = "schreibweise") -> dict:
    """Eine weitere Schreibweise. Gehört sie schon einer anderen Firma, wird das gesagt und nichts geändert."""
    art = (art or "schreibweise").strip().casefold()
    if art not in ARTEN:
        return {"status": "fehler", "text": f"Unbekannte Art „{art}“.", "erlaubt": list(ARTEN)}
    sauber = _sauber(alias)
    form = _form(sauber)
    if not form:
        return {"status": "fehler", "text": "Die Schreibweise fehlt oder besteht nur aus einer Rechtsform."}
    with _LOCK:
        f = firma_laden(db, firma_id)
        if f is None:
            return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr)."}
        gehoert = _form_vergeben(db, form)
        if gehoert and gehoert["firma_id"] == f["id"]:
            return {"status": "schon_da", "text": "Diese Schreibweise gehört schon zu dieser Firma."}
        if gehoert:
            return {"status": "gehoert_anderer_firma", "firma_id": gehoert["firma_id"],
                    "text": (f"Diese Schreibweise gehört schon zur Firma „{gehoert['firma']}“. Sind das dieselbe Firma, führe die beiden "
                             "zusammen (aktion='zusammenfuehren'); sonst bleibt sie dort.")}
        if len(f["aliase"]) >= MAX_ALIASE:
            return {"status": "fehler", "text": f"Mehr als {MAX_ALIASE} Schreibweisen je Firma sind nicht vorgesehen."}
        conn = db.connect()
        conn.execute("INSERT INTO company_aliases (company_id, profile_id, alias, alias_form, art, created_at) VALUES (?,?,?,?,?,?)",
                     (f["id"], _pid(db), sauber, form, art, _jetzt()))
        conn.commit()
    return {"status": "hinzugefuegt", "text": f"„{sauber}“ zählt jetzt zu „{f['name']}“.", "firma": firma_laden(db, f["id"])}


def alias_entfernen(db, firma_id: str, alias_id) -> dict:
    with _LOCK:
        conn, pid = db.connect(), _pid(db)
        try:
            aid = int(alias_id)
        except (TypeError, ValueError):
            return {"status": "fehler", "text": "Die Kennung der Schreibweise fehlt."}
        r = conn.execute("SELECT alias FROM company_aliases WHERE id=? AND company_id=? AND profile_id=?", (aid, str(firma_id), pid)).fetchone()
        if r is None:
            return {"status": "nicht_gefunden", "text": "Diese Schreibweise gibt es nicht (mehr)."}
        conn.execute("DELETE FROM company_aliases WHERE id=?", (aid,))
        conn.commit()
    return {"status": "entfernt", "text": f"„{r['alias']}“ gehört nicht mehr zu dieser Firma. Bewerbungen und Stellen bleiben unverändert."}


def firma_bearbeiten(db, firma_id: str, **felder) -> dict:
    """Branche, Standorte, Notizen. Name und Mutterfirma haben eigene Funktionen (sie prüfen mehr)."""
    erlaubt = {"branche": 200, "standorte": 400, "notizen": 4000}
    unbekannt = [k for k in felder if k not in erlaubt]
    if unbekannt:
        return {"status": "fehler", "text": f"Unbekannte Felder: {unbekannt}", "erlaubt": list(erlaubt)}
    with _LOCK:
        if firma_laden(db, firma_id) is None:
            return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr)."}
        conn, pid = db.connect(), _pid(db)
        for k, v in felder.items():
            conn.execute(f"UPDATE companies SET {k}=?, updated_at=? WHERE id=? AND profile_id=?", (_sauber(v, erlaubt[k]), _jetzt(), str(firma_id), pid))
        conn.commit()
    return {"status": "gespeichert", "firma": firma_laden(db, firma_id)}


def umbenennen(db, firma_id: str, neuer_name: str, *, alten_namen_merken: bool = True) -> dict:
    sauber = _sauber(neuer_name)
    form = _form(sauber)
    if not form:
        return {"status": "fehler", "text": "Der neue Name fehlt oder besteht nur aus einer Rechtsform."}
    with _LOCK:
        f = firma_laden(db, firma_id)
        if f is None:
            return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr)."}
        gehoert = _form_vergeben(db, form, ausser_firma=f["id"])
        if gehoert:
            return {"status": "schon_da", "text": f"Dieser Name gehört schon zur Firma „{gehoert['firma']}“.", "firma_id": gehoert["firma_id"]}
        conn, pid = db.connect(), _pid(db)
        # War der neue Name bisher eine Schreibweise dieser Firma, wird er zum Namen und ist keine Schreibweise mehr.
        conn.execute("DELETE FROM company_aliases WHERE company_id=? AND profile_id=? AND alias_form=?", (f["id"], pid, form))
        conn.execute("UPDATE companies SET name=?, name_form=?, updated_at=? WHERE id=? AND profile_id=?", (sauber, form, _jetzt(), f["id"], pid))
        conn.commit()
    if alten_namen_merken and _form(f["name"]) != form:
        alias_hinzufuegen(db, f["id"], f["name"], "frueherer_name")
    return {"status": "umbenannt", "firma": firma_laden(db, f["id"]), "text": f"Die Firma heißt jetzt „{sauber}“."}


def mutterfirma_setzen(db, firma_id: str, mutterfirma_id: str = "") -> dict:
    """Setzt oder löst (leer) die Mutterfirma. Eine Kette im Kreis wird abgewiesen."""
    with _LOCK:
        f = firma_laden(db, firma_id)
        if f is None:
            return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr)."}
        if mutterfirma_id:
            if firma_laden(db, mutterfirma_id) is None:
                return {"status": "fehler", "text": "Die Mutterfirma gibt es nicht."}
            if _kette_enthaelt(db, mutterfirma_id, f["id"]):
                return {"status": "fehler", "text": "Das ergäbe einen Kreis: eine Firma kann nicht ihre eigene Mutter oder Enkelin sein."}
        conn, pid = db.connect(), _pid(db)
        conn.execute("UPDATE companies SET parent_id=?, updated_at=? WHERE id=? AND profile_id=?", (mutterfirma_id or None, _jetzt(), f["id"], pid))
        conn.commit()
    return {"status": "gesetzt", "firma": firma_laden(db, f["id"]),
            "text": ("Die Mutterfirma ist gesetzt. Konzern und Tochter werden zusammen gefunden, aber nicht als dieselbe Firma behandelt."
                     if mutterfirma_id else "Die Mutterfirma ist gelöst.")}


def zusammenfuehren(db, ziel_id: str, quelle_id: str) -> dict:
    """Zwei Einträge sind dieselbe Firma: Namen und Schreibweisen der Quelle gehen an das Ziel, die Quelle verschwindet."""
    if str(ziel_id) == str(quelle_id):
        return {"status": "fehler", "text": "Ziel und Quelle sind dieselbe Firma."}
    with _LOCK:
        ziel, quelle = firma_laden(db, ziel_id), firma_laden(db, quelle_id)
        if ziel is None or quelle is None:
            return {"status": "nicht_gefunden", "text": "Eine der beiden Firmen gibt es nicht (mehr)."}
        conn, pid = db.connect(), _pid(db)
        try:
            conn.execute("UPDATE company_aliases SET company_id=? WHERE company_id=? AND profile_id=?", (ziel["id"], quelle["id"], pid))
            conn.execute("UPDATE company_contacts SET company_id=? WHERE company_id=? AND profile_id=?", (ziel["id"], quelle["id"], pid))
            conn.execute("DELETE FROM companies WHERE id=? AND profile_id=?", (quelle["id"], pid))
            conn.execute("UPDATE companies SET parent_id=? WHERE parent_id=? AND profile_id=?", (ziel["id"], quelle["id"], pid))
            conn.execute("UPDATE companies SET parent_id=NULL WHERE id=? AND parent_id=?", (ziel["id"], ziel["id"]))   # Kind der Quelle war das Ziel
            if quelle["mutterfirma_id"] and not ziel["mutterfirma_id"] and quelle["mutterfirma_id"] != ziel["id"]:
                conn.execute("UPDATE companies SET parent_id=? WHERE id=? AND profile_id=?", (quelle["mutterfirma_id"], ziel["id"], pid))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        alias_hinzufuegen(db, ziel["id"], quelle["name"], "schreibweise")
    return {"status": "zusammengefuehrt", "firma": firma_laden(db, ziel["id"]),
            "text": f"„{quelle['name']}“ und „{ziel['name']}“ sind jetzt eine Firma. Bewerbungen und Stellen bleiben unverändert."}


def firma_loeschen(db, firma_id: str) -> dict:
    """Entfernt den Stammsatz samt Schreibweisen. Bewerbungen, Stellen, Kontakte und Lebenslauf bleiben unberührt."""
    with _LOCK:
        f = firma_laden(db, firma_id)
        if f is None:
            return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr)."}
        conn, pid = db.connect(), _pid(db)
        conn.execute("DELETE FROM company_aliases WHERE company_id=? AND profile_id=?", (f["id"], pid))
        conn.execute("DELETE FROM company_contacts WHERE company_id=? AND profile_id=?", (f["id"], pid))
        conn.execute("UPDATE companies SET parent_id=NULL WHERE parent_id=? AND profile_id=?", (f["id"], pid))
        conn.execute("DELETE FROM companies WHERE id=? AND profile_id=?", (f["id"], pid))
        conn.commit()
    return {"status": "geloescht", "text": (f"Der Stammsatz „{f['name']}“ ist gelöscht ({len(f['aliase'])} Schreibweisen). "
                                            "Bewerbungen, Stellen, Kontakte und Lebenslauf sind unverändert.")}


# ── Kontakte einer Firma: Rolle und Zeitraum ────────────────────────────────────────────────────────────

_ZEIT = re.compile(r"^(?:(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?|(?:(\d{1,2})\.)?(\d{1,2})\.(\d{4}))$")


def _zeit(wert) -> tuple:
    """Eine Zeitangabe als 'JJJJ', 'JJJJ-MM' oder 'JJJJ-MM-TT' — `(Wert, Fehler)`. Erlaubt sind auch 'MM.JJJJ' und 'TT.MM.JJJJ'. Leer ist erlaubt."""
    s = str(wert or "").strip()
    if not s:
        return "", ""
    m = _ZEIT.match(s)
    if not m:
        return "", f"„{s}“ ist keine Zeitangabe. Erlaubt: 2021, 2021-03 oder 03.2021 (auch mit Tag)."
    if m.group(1):
        jahr, monat, tag = m.group(1), m.group(2), m.group(3)
    else:
        jahr, monat, tag = m.group(6), m.group(5), m.group(4)
    try:
        if monat and not 1 <= int(monat) <= 12:
            raise ValueError
        if tag:
            datetime(int(jahr), int(monat), int(tag))
    except ValueError:
        return "", f"„{s}“ ist kein gültiges Datum."
    ergebnis = jahr
    if monat:
        ergebnis += f"-{int(monat):02d}"
    if tag:
        ergebnis += f"-{int(tag):02d}"
    return ergebnis, ""


def _zeit_sortierbar(wert: str) -> tuple:
    teile = [int(x) for x in (wert or "").split("-") if x.isdigit()]
    return tuple(teile) + (0,) * (3 - len(teile))


def zeitraum_text(von: str, bis: str, aktuell: bool) -> str:
    """Der Zeitraum für Menschen: 'seit 2021', '2018 bis 2021', 'bis 2021', 'früher' oder 'aktuell'."""
    if von and bis:
        return f"{von} bis {bis}"
    if von:
        return f"seit {von}" if aktuell else f"ab {von}, nicht mehr dort"
    if bis:
        return f"bis {bis}"
    return "aktuell" if aktuell else "früher"


def _kontakt_aufloesen(db, kontakt_id) -> Optional[dict]:
    """Der Kontakt des aktiven Profils zu dieser (auch gekürzten oder typisierten) Kennung — oder None."""
    from .typed_ids import strip_prefix
    roh = strip_prefix(str(kontakt_id or "")).strip()
    if not roh:
        return None
    conn, pid = db.connect(), _pid(db)
    r = conn.execute("SELECT id, full_name, company, position FROM contacts WHERE id=? AND (profile_id=? OR profile_id IS NULL)", (roh, pid)).fetchone()
    if r is None and len(roh) <= 8:
        r = conn.execute("SELECT id, full_name, company, position FROM contacts WHERE id LIKE ? AND (profile_id=? OR profile_id IS NULL) LIMIT 2",
                         (roh + "%", pid)).fetchall()
        r = r[0] if len(r) == 1 else None          # mehrdeutig: nicht raten
    return dict(r) if r is not None else None


kontakt_aufloesen = _kontakt_aufloesen      # öffentlich: das Werkzeug prüft den Kontakt vor der Firma


def _zuordnung_zeile(z) -> dict:
    von, bis, aktuell = z["von"] or "", z["bis"] or "", bool(z["aktuell"])
    return {"id": z["id"], "firma_id": z["company_id"], "firma": z["firma"], "kontakt_id": z["contact_id"], "kontakt": z["kontakt"],
            "kontakt_firma_text": z["kontakt_firma"] or "", "funktion": z["funktion"] or "", "rolle": z["rolle"] or "",
            "von": von, "bis": bis, "aktuell": aktuell, "zeitraum": zeitraum_text(von, bis, aktuell), "notizen": z["notizen"] or ""}


_ZUORDNUNG_SQL = ("SELECT cc.*, co.name AS firma, c.full_name AS kontakt, c.company AS kontakt_firma, c.position AS funktion "
                  "FROM company_contacts cc JOIN companies co ON co.id = cc.company_id JOIN contacts c ON c.id = cc.contact_id "
                  "WHERE cc.profile_id=? ")


def kontakte_der_firma(db, firma_id: str) -> list:
    """Die Kontakte, die einer Firma zugeordnet sind: aktuelle zuerst, dann nach Beginn."""
    conn, pid = db.connect(), _pid(db)
    zeilen = [_zuordnung_zeile(z) for z in conn.execute(_ZUORDNUNG_SQL + "AND cc.company_id=?", (pid, str(firma_id)))]
    return sorted(zeilen, key=lambda z: (not z["aktuell"], tuple(-x for x in _zeit_sortierbar(z["von"] or z["bis"])), z["kontakt"].casefold()))


def firmen_des_kontakts(db, kontakt_id: str) -> list:
    """Die Firmen, denen ein Kontakt zugeordnet ist (aktuelle zuerst)."""
    k = _kontakt_aufloesen(db, kontakt_id)
    if k is None:
        return []
    conn, pid = db.connect(), _pid(db)
    zeilen = [_zuordnung_zeile(z) for z in conn.execute(_ZUORDNUNG_SQL + "AND cc.contact_id=?", (pid, k["id"]))]
    return sorted(zeilen, key=lambda z: (not z["aktuell"], tuple(-x for x in _zeit_sortierbar(z["von"] or z["bis"])), z["firma"].casefold()))


def kontakt_zuordnen(db, firma_id: str, kontakt_id: str, *, rolle: str = "", von: str = "", bis: str = "", aktuell=None, notizen: str = "") -> dict:
    """Ordnet einen Kontakt einer Firma zu — mit Rolle und Zeitraum. Dieselbe Person kann mehreren Firmen angehören (aktuell, früher).

    Ohne Angabe gilt der Kontakt dort als aktuell; mit `bis` ist er es nicht mehr. Das Textfeld „Firma“ am Kontakt bleibt unverändert.
    """
    f = firma_laden(db, firma_id)
    if f is None:
        return {"status": "nicht_gefunden", "text": "Diese Firma gibt es nicht (mehr). Lege sie zuerst an (firmen_stamm_bearbeiten, aktion='anlegen')."}
    k = _kontakt_aufloesen(db, kontakt_id)
    if k is None:
        return {"status": "nicht_gefunden", "text": "Diesen Kontakt gibt es nicht. Die Kennung steht in kontakte_auflisten()."}
    von_n, fehler = _zeit(von)
    bis_n, fehler2 = _zeit(bis)
    if fehler or fehler2:
        return {"status": "fehler", "text": fehler or fehler2}
    if von_n and bis_n and _zeit_sortierbar(von_n) > _zeit_sortierbar(bis_n):
        return {"status": "fehler", "text": f"Der Beginn ({von_n}) liegt nach dem Ende ({bis_n})."}
    if aktuell is None:
        aktuell = not bis_n
    if bis_n and aktuell:
        return {"status": "fehler", "text": "Ein Zeitraum mit Ende ist nicht aktuell: entweder das Ende weglassen oder aktuell=False."}
    rolle = _sauber(rolle, 120)
    with _LOCK:
        conn, pid = db.connect(), _pid(db)
        gleich = conn.execute("SELECT id FROM company_contacts WHERE company_id=? AND contact_id=? AND profile_id=? AND rolle=? AND von=? AND bis=?",
                              (f["id"], k["id"], pid, rolle, von_n, bis_n)).fetchone()
        if gleich:
            return {"status": "schon_da", "zuordnung_id": gleich["id"], "text": f"{k['full_name']} gehört schon so zu „{f['name']}“."}
        zid = "cc_" + uuid.uuid4().hex[:10]
        conn.execute("INSERT INTO company_contacts (id, company_id, contact_id, profile_id, rolle, von, bis, aktuell, notizen, created_at, updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (zid, f["id"], k["id"], pid, rolle, von_n, bis_n, 1 if aktuell else 0, _sauber(notizen, 1000), _jetzt(), _jetzt()))
        conn.commit()
    zeile = next(z for z in kontakte_der_firma(db, f["id"]) if z["id"] == zid)
    return {"status": "zugeordnet", "zuordnung": zeile,
            "text": f"{k['full_name']} gehört jetzt zu „{f['name']}“ ({zeile['zeitraum']}). Das Textfeld Firma am Kontakt ist unverändert."}


def zuordnung_aendern(db, zuordnung_id: str, **felder) -> dict:
    """Ändert Rolle, Zeitraum, aktuell oder Notizen einer Zuordnung. Nur die genannten Felder."""
    erlaubt = {"rolle", "von", "bis", "aktuell", "notizen"}
    unbekannt = [k for k in felder if k not in erlaubt]
    if unbekannt:
        return {"status": "fehler", "text": f"Unbekannte Felder: {unbekannt}", "erlaubt": sorted(erlaubt)}
    with _LOCK:
        conn, pid = db.connect(), _pid(db)
        z = conn.execute("SELECT * FROM company_contacts WHERE id=? AND profile_id=?", (str(zuordnung_id), pid)).fetchone()
        if z is None:
            return {"status": "nicht_gefunden", "text": "Diese Zuordnung gibt es nicht (mehr)."}
        von_n, bis_n, aktuell = z["von"] or "", z["bis"] or "", bool(z["aktuell"])
        if "von" in felder:
            von_n, fehler = _zeit(felder["von"])
            if fehler:
                return {"status": "fehler", "text": fehler}
        if "bis" in felder:
            bis_n, fehler = _zeit(felder["bis"])
            if fehler:
                return {"status": "fehler", "text": fehler}
            if bis_n and "aktuell" not in felder:
                aktuell = False
        if "aktuell" in felder and felder["aktuell"] is not None:
            aktuell = bool(felder["aktuell"])
        if bis_n and aktuell:
            return {"status": "fehler", "text": "Ein Zeitraum mit Ende ist nicht aktuell: entweder das Ende entfernen oder aktuell=False."}
        if von_n and bis_n and _zeit_sortierbar(von_n) > _zeit_sortierbar(bis_n):
            return {"status": "fehler", "text": f"Der Beginn ({von_n}) liegt nach dem Ende ({bis_n})."}
        rolle = _sauber(felder["rolle"], 120) if "rolle" in felder else (z["rolle"] or "")
        notizen = _sauber(felder["notizen"], 1000) if "notizen" in felder else (z["notizen"] or "")
        conn.execute("UPDATE company_contacts SET rolle=?, von=?, bis=?, aktuell=?, notizen=?, updated_at=? WHERE id=? AND profile_id=?",
                     (rolle, von_n, bis_n, 1 if aktuell else 0, notizen, _jetzt(), z["id"], pid))
        conn.commit()
        zeile = next(x for x in kontakte_der_firma(db, z["company_id"]) if x["id"] == z["id"])
    return {"status": "geaendert", "zuordnung": zeile, "text": f"Gespeichert: {zeile['kontakt']} bei „{zeile['firma']}“ ({zeile['zeitraum']})."}


def zuordnung_entfernen(db, zuordnung_id: str) -> dict:
    """Nimmt einen Kontakt aus der Firma. Der Kontakt selbst und sein Textfeld Firma bleiben."""
    with _LOCK:
        conn, pid = db.connect(), _pid(db)
        z = conn.execute(_ZUORDNUNG_SQL + "AND cc.id=?", (pid, str(zuordnung_id))).fetchone()
        if z is None:
            return {"status": "nicht_gefunden", "text": "Diese Zuordnung gibt es nicht (mehr)."}
        conn.execute("DELETE FROM company_contacts WHERE id=? AND profile_id=?", (z["id"], pid))
        conn.commit()
    return {"status": "entfernt", "text": f"{z['kontakt']} gehört nicht mehr zu „{z['firma']}“. Der Kontakt bleibt unverändert."}


# ── Vorschläge aus dem Bestand ─────────────────────────────────────────────────────────────────────────

#: Bis zu so vielen verschiedenen Namensformen vergleicht `vorschlaege` Paare (n² Vergleiche); darüber nur die gleiche Form.
MAX_PAARVERGLEICH = 3000
#: Ein Name unter dieser Länge steckt zu oft zufällig in einem anderen, um ihn als Kurzform vorzuschlagen.
MIN_TEILNAME = 4


def _vorschlag_id(formen) -> str:
    return "v_" + hashlib.sha1("|".join(sorted(formen)).encode("utf-8")).hexdigest()[:8]


def _gruppen_im_bestand(db) -> dict:
    """Namen des Bestands nach ihrer Namensform ohne Leerzeichen: {Schlüssel: {'form', 'namen': {Schreibweise: Anzahl}, 'herkunft'}}."""
    gruppen: dict = {}
    for name, her in _fb.namen_im_bestand(db):
        k = _form(name)
        if not k:
            continue
        g = gruppen.setdefault(k.replace(" ", ""), {"form": k, "namen": {}, "herkunft": set()})
        g["namen"][name] = g["namen"].get(name, 0) + 1
        g["herkunft"].add(her)
    return gruppen


def _cluster(gruppen: dict) -> list:
    """Gruppen, die vermutlich dieselbe Firma sind: eine Gruppe mit EINDEUTIGEM längerem Namen, in dem ihr Name als Wortfolge steht.

    „Acme“ wird mit „Acme Solutions GmbH“ verbunden — aber nicht, wenn es zugleich in „Acme Energie“ steht (dann würde PBP raten).
    Rückgabe: Listen von Gruppen-Schlüsseln, jede Liste = ein Cluster (auch einzelne Gruppen).
    """
    schluessel = list(gruppen)
    ziel: dict = {}
    if len(schluessel) <= MAX_PAARVERGLEICH:
        for a in schluessel:
            fa = gruppen[a]["form"]
            if len(fa) < MIN_TEILNAME:
                continue
            laenger = [b for b in schluessel if b != a and len(gruppen[b]["form"].split()) > len(fa.split())
                       and _fb.abgleich(fa, gruppen[b]["form"]) == "teil"]
            if len(laenger) == 1:
                ziel[a] = laenger[0]
    eltern = {k: k for k in schluessel}

    def wurzel(k):
        while eltern[k] != k:
            eltern[k] = eltern[eltern[k]]
            k = eltern[k]
        return k

    for a, b in ziel.items():
        eltern[wurzel(a)] = wurzel(b)
    cluster: dict = {}
    for k in schluessel:
        cluster.setdefault(wurzel(k), []).append(k)
    return list(cluster.values())


def vorschlaege(db, *, maximal: int = 100) -> dict:
    """Welche Namen im Bestand vermutlich dieselbe Firma sind — und noch keinem Stammsatz gehören. Liest nur.

    Zwei Gründe, ein Vorschlag zu sein: derselbe Name in mehreren Schreibweisen (`gleiche_namensform`: Rechtsform, Umlaut,
    Bindestrich) oder ein kürzerer Name, der als Wortfolge in genau einem längeren steckt (`teilname`: „Acme“ in „Acme Solutions GmbH“).
    Der zweite Grund ist unsicherer und steht als `sicherheit: mittel` dabei. Frühere Namen und Geschäftsbereiche kann nur der Mensch
    kennen; er trägt sie mit `alias_hinzufuegen` ein.

    Jeder Vorschlag hat eine stabile Kennung (aus den Namensformen), den Namen zum Anlegen (die häufigste Schreibweise des längsten Namens)
    und nur die Schreibweisen, die der Stammsatz speichern muss (andere Namensformen; gleiche findet er ohnehin). Gehört ein Teil schon
    einer Firma, lautet der Vorschlag, die übrigen dort zu ergänzen (`ergaenzt_firma`).
    """
    gruppen = _gruppen_im_bestand(db)
    erg = []
    for mitglieder in _cluster(gruppen):
        spelungen: dict = {}
        formen = set()
        herkunft = set()
        for k in mitglieder:
            g = gruppen[k]
            formen.add(g["form"])
            herkunft |= g["herkunft"]
            for n, c in g["namen"].items():
                spelungen[n] = spelungen.get(n, 0) + c
        mehrere_schreibweisen = any(len(gruppen[k]["namen"]) >= 2 for k in mitglieder)
        if not mehrere_schreibweisen and len(mitglieder) < 2:
            continue                                                  # ein Name in einer Schreibweise: nichts zusammenzufassen
        # Zuordnung prüfen: wem gehört davon schon etwas?
        besitzer, offen = set(), []
        for n in spelungen:
            r = aufloesen(db, n)
            if r["firma"] and r["art"] == "exakt":
                besitzer.add(r["firma"]["id"])
            else:
                offen.append(n)
        if not offen or len(besitzer) > 1:
            continue                                                  # alles zugeordnet, oder es widerspricht sich: nicht raten
        laengste = max(mitglieder, key=lambda k: (len(gruppen[k]["form"].split()), sum(gruppen[k]["namen"].values())))
        name = max(gruppen[laengste]["namen"], key=lambda n: (gruppen[laengste]["namen"][n], len(n), n))
        speichern, gesehen = [], {_form(name)}
        for n in sorted(spelungen, key=lambda s: (-spelungen[s], s)):
            fm = _form(n)
            if fm not in gesehen and not any(fm.replace(" ", "") == g.replace(" ", "") for g in gesehen):
                gesehen.add(fm)
                speichern.append(n)
        eintrag = {
            "vorschlag_id": _vorschlag_id(formen), "name": name, "schreibweisen": sorted(spelungen),
            "vorkommen": sum(spelungen.values()), "herkunft": sorted(herkunft),
            "grund": "teilname" if len(mitglieder) > 1 else "gleiche_namensform",
            "sicherheit": "mittel" if len(mitglieder) > 1 else "hoch",
        }
        if besitzer:
            f = firma_laden(db, next(iter(besitzer)))
            bekannt = {x[0].replace(" ", "") for x in _alle_formen(db)}
            neue = [n for n in [name, *speichern] if _form(n).replace(" ", "") not in bekannt]
            if not neue:
                continue
            eintrag.update(art="ergaenzung", ergaenzt_firma={"id": f["id"], "name": f["name"]}, neue_schreibweisen=neue)
        else:
            eintrag.update(art="neu", aliase=speichern)
        erg.append(eintrag)
    erg.sort(key=lambda e: (e["sicherheit"] != "hoch", -e["vorkommen"], e["name"].casefold()))
    return {"anzahl": len(erg), "vorschlaege": erg[:max(1, int(maximal))],
            "hinweis": ("Nur Vorschläge: PBP ändert nichts, bevor du bestätigst. Bewerbungen, Stellen und Kontakte behalten ihren Text; "
                        "der Stammsatz sorgt dafür, dass alle Schreibweisen zusammen gefunden werden. Frühere Namen und "
                        "Geschäftsbereiche kann PBP nicht erkennen: die trägst du selbst ein.")}


def vorschlaege_anwenden(db, auswahl, *, bestaetigt: bool = False) -> dict:
    """Legt die gewählten Vorschläge an (oder ergänzt die genannte Firma). Ohne `bestaetigt` nur die Vorschau."""
    if not isinstance(auswahl, (list, tuple, set)) or not auswahl:
        return {"status": "fehler", "text": "Es ist kein Vorschlag gewählt. Nenne die Kennungen aus der Vorschlagsliste."}
    alle = {v["vorschlag_id"]: v for v in vorschlaege(db, maximal=100000)["vorschlaege"]}
    gewaehlt = list(dict.fromkeys(str(a) for a in auswahl))
    unbekannt = [a for a in gewaehlt if a not in alle]
    if unbekannt:
        return {"status": "fehler", "text": f"Unbekannte oder schon angewendete Vorschläge: {unbekannt}", "unbekannt": unbekannt}
    plan = [alle[a] for a in gewaehlt]
    if not bestaetigt:
        return {"status": "vorschau", "anzahl": len(plan), "vorschlaege": plan,
                "text": (f"{len(plan)} {'Eintrag würde' if len(plan) == 1 else 'Einträge würden'} angelegt oder ergänzt. Bewerbungen, Stellen und Kontakte bleiben unverändert. "
                         "Bestätige, um sie anzulegen.")}
    angelegt, ergaenzt, probleme = [], [], []
    for v in plan:
        if v["art"] == "ergaenzung":
            for n in v["neue_schreibweisen"]:
                r = alias_hinzufuegen(db, v["ergaenzt_firma"]["id"], n)
                if r["status"] == "hinzugefuegt":
                    ergaenzt.append(n)
                elif r["status"] != "schon_da":
                    probleme.append(f"{n}: {r['text']}")
        else:
            r = firma_anlegen(db, v["name"], aliase=v.get("aliase", []))
            if r["status"] == "angelegt":
                angelegt.append(v["name"])
                probleme += r.get("hinweise", [])
            elif r["status"] != "schon_da":
                probleme.append(f"{v['name']}: {r['text']}")
    return {"status": "angewendet" if not probleme else "teilweise", "angelegt": angelegt, "ergaenzt": ergaenzt, "probleme": probleme,
            "text": (f"{len(angelegt)} {'Firma' if len(angelegt) == 1 else 'Firmen'} angelegt, "
                     f"{len(ergaenzt)} {'Schreibweise' if len(ergaenzt) == 1 else 'Schreibweisen'} ergänzt.")
                    + (f" {len(probleme)} {'Hinweis' if len(probleme) == 1 else 'Hinweise'}." if probleme else "")}
