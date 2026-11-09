"""Eigene Filter, benannt und gespeichert: als Ansicht oder als Regel (#1307).

Gemeldet aus 1.8.1: Dauerhaft gab es nur feste Mechanismen (Ausschluss- und
Minus-Begriffe, Blacklist, Scoring-Regler, Suchprofile). Die freie Logik von
`stellen_bulk_bewerten` (Titel und Beschreibung enthalten / enthalten nicht,
Quelle, Punkte, Alter) liess sich weder speichern noch auf neue Treffer
anwenden. Dazu #1308: englische Anzeigen sollen auch kuenftig von selbst
verschwinden.

## Zwei Arten, dieselben Bedingungen

* **Ansicht** (`ansicht`) - filtert nur. `stellen_anzeigen(ansicht=...)` und
  die Auswahl im Stellen-Tab zeigen die passenden aktiven Stellen.
* **Regel** (`regel`) - sortiert passende NEUE Treffer nach jeder Suche aus,
  mit Gruenden aus der erlaubten Liste (Standard plus eigene, nie erfundene).

Die Bedingungen prueft `stellen_filter.passt` - dieselbe Funktion wie
`stellen_bulk_bewerten` (#1307 AK: eine Frage, eine Funktion).

## Was eine Regel nie tut

* **Beim Anlegen aussortieren.** `anlegen` zeigt, was sie heute treffen
  wuerde; den Bestand nimmt erst `anwenden` mit `dry_run=False`.
* **Eine geschuetzte Stelle aussortieren.** Vom Menschen zurueckgeholte
  Stellen und solche mit gelesenem Urteil EMPFOHLEN/BEDINGT bleiben
  (`aussortier_schutz`, doppelter Boden in `Database.dismiss_job`), Stellen
  mit Bewerbung ebenso.
* **Unbekanntes als Treffer werten.** Eine Sprach-Regel trifft keine Stelle
  ohne erkennbare Sprache (`sprache.erkennen` -> ``unbekannt``).
* **Den Lerneffekt treiben.** Aussortiert wird mit Herkunft `automatik` und
  dem Namen der Regel in der Notiz (Aussortier-Protokoll, Reiter
  Aussortiert); die Zaehler, aus denen PBP Regler lernt, zaehlen nur Urteile
  des Menschen (#1239).

## Wann Regeln laufen

`nach_treffern(db, hashes)` - nach jedem internen Suchlauf
(`jobsuche_start._lauf`, nach dem Text-Nachzug und vor der Auto-Aussortierung
der lokalen KI) und nach `browser_treffer_uebernehmen` /
`linkedin_treffer_uebernehmen` (echter Lauf). Ohne aktive Regel geschieht
nichts.

Abgrenzung: `stellen_filter_standard.py` ist die Voreinstellung der Schalter
im Stellen-Tab, `stellen_filter.py` die Pruefung einer Stelle, hier stehen
Speicher, Vorschau und Lauf. Antworten fuer Claude-Werkzeug und Dashboard
entstehen hier (`als_eintrag`, `vorschau`, `anwenden`), damit beide dasselbe
sagen.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import stellen_filter as _sf

logger = logging.getLogger(__name__)

ARTEN = ("ansicht", "regel")
TABELLE = "stellen_filter"
MAX_NAME = 80
#: So viele Beispiele zeigt eine Vorschau.
BEISPIELE = 10
#: Die Herkunft, die eine Regel an der Stelle hinterlaesst (Aussortier-Protokoll).
HERKUNFT = "automatik"


class FilterFehler(ValueError):
    """Eine Anfrage, die nicht ausgefuehrt werden kann - mit Grund fuer den Menschen."""

    def __init__(self, text: str, **zusatz):
        super().__init__(text)
        self.zusatz = zusatz


def tabelle_anlegen(conn) -> None:
    """Safety-Net in `Database.initialize()` statt Schema-Bump (additiv, #1307)."""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABELLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            art TEXT NOT NULL,
            bedingungen TEXT NOT NULL DEFAULT '{{}}',
            gruende TEXT NOT NULL DEFAULT '[]',
            aktiv INTEGER NOT NULL DEFAULT 1,
            erstellt_am TEXT,
            geaendert_am TEXT,
            zuletzt_angewendet TEXT,
            treffer_gesamt INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{TABELLE}_name "
                 f"ON {TABELLE}(profile_id, name COLLATE NOCASE)")
    conn.commit()


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _profil(db) -> str:
    return db.get_active_profile_id() or ""


def _zeile(r) -> dict:
    d = dict(r)
    try:
        d["bedingungen"] = json.loads(d.get("bedingungen") or "{}")
    except (TypeError, ValueError):
        d["bedingungen"] = {}
    try:
        d["gruende"] = json.loads(d.get("gruende") or "[]")
    except (TypeError, ValueError):
        d["gruende"] = []
    d["aktiv"] = bool(d.get("aktiv"))
    return d


def alle(db, art: str = "") -> list[dict]:
    """Die gespeicherten Filter des aktiven Profils, nach Anlage geordnet."""
    sql = f"SELECT * FROM {TABELLE} WHERE profile_id=?"
    params: list = [_profil(db)]
    if art:
        sql += " AND art=?"
        params.append(art)
    sql += " ORDER BY id"
    return [_zeile(r) for r in db.connect().execute(sql, params).fetchall()]


def holen(db, name_oder_id) -> dict | None:
    """Ein Filter nach Name (ohne Gross/Klein) oder Kennung - nur im aktiven Profil."""
    wert = str(name_oder_id or "").strip()
    if not wert:
        return None
    conn = db.connect()
    pid = _profil(db)
    r = conn.execute(f"SELECT * FROM {TABELLE} WHERE profile_id=? AND name=? COLLATE NOCASE",
                     (pid, wert)).fetchone()
    if r is None and wert.isdigit():
        r = conn.execute(f"SELECT * FROM {TABELLE} WHERE profile_id=? AND id=?",
                         (pid, int(wert))).fetchone()
    return _zeile(r) if r else None


def erlaubte_gruende(db) -> list[str]:
    """Die Gruende, die eine Regel tragen darf: dieselbe Liste wie beim Aussortieren (#1297)."""
    from .ablehnungsgruende import waehlbare_gruende
    return waehlbare_gruende(db)


def gruende_pruefen(db, gruende) -> list[str]:
    """Nur Gruende aus der Liste - ein unbekannter wird ABGELEHNT, nie umgedeutet (#663)."""
    if isinstance(gruende, str):
        gruende = [gruende]
    werte = [str(g or "").strip() for g in (gruende or []) if str(g or "").strip()]
    erlaubt = erlaubte_gruende(db)
    nach_klein = {g.lower(): g for g in erlaubt}
    ergebnis, falsch = [], []
    for g in werte:
        treffer = nach_klein.get(g.lower())
        if treffer is None:
            falsch.append(g)
        else:
            ergebnis.append(treffer.lower())
    if falsch:
        raise FilterFehler(
            f"Diese Gründe gibt es nicht: {', '.join(falsch)}. Eine Regel nimmt nur Gründe aus der Liste.",
            verfuegbare_gruende=erlaubt,
            naechster_schritt=(
                "Passt keiner, lege einen eigenen Grund an (ablehnungsgrund_anlegen, z. B. "
                "'englischsprachig'; im Dashboard unter Einstellungen › Ablehnungsgründe) oder nimm 'sonstiges'."))
    if not ergebnis:
        raise FilterFehler(
            "Eine Regel braucht mindestens einen Grund aus der Liste.",
            verfuegbare_gruende=erlaubt,
            naechster_schritt=(
                "Für englische Anzeigen bietet sich ein eigener Grund an "
                "(ablehnungsgrund_anlegen, z. B. 'englischsprachig') — oder 'sonstiges'."))
    return list(dict.fromkeys(ergebnis))


def anlegen(db, name: str, art: str, bedingungen: dict, gruende=None) -> dict:
    """Legt einen Filter an. Eine Regel sortiert dabei NICHTS aus."""
    name = str(name or "").strip()
    if not name:
        raise FilterFehler("Der Filter braucht einen Namen.")
    if len(name) > MAX_NAME or any(ord(c) < 32 for c in name):
        raise FilterFehler(f"Der Name ist zu lang oder enthält Steuerzeichen (höchstens {MAX_NAME} Zeichen).")
    art = str(art or "").strip().lower()
    if art not in ARTEN:
        raise FilterFehler(f"Unbekannte Art '{art}'. Möglich: ansicht (nur filtern), regel (neue Treffer aussortieren).")
    try:
        b = _sf.bedingungen_lesen(bedingungen)
    except _sf.UngueltigeBedingung as fehler:
        raise FilterFehler(str(fehler)) from None
    if not b:
        raise FilterFehler("Ohne Bedingung würde der Filter jede Stelle treffen. Nenne mindestens eine Bedingung.",
                           moegliche_bedingungen=list(_sf.BEDINGUNGEN))
    g = gruende_pruefen(db, gruende) if art == "regel" else []
    if holen(db, name):
        raise FilterFehler(f"Einen Filter „{name}“ gibt es schon. Anderen Namen wählen oder den alten löschen.")
    jetzt = _jetzt()
    conn = db.connect()
    cur = conn.execute(
        f"INSERT INTO {TABELLE} (profile_id, name, art, bedingungen, gruende, aktiv, erstellt_am, geaendert_am) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
        (_profil(db), name, art, json.dumps(b, ensure_ascii=False), json.dumps(g, ensure_ascii=False),
         jetzt, jetzt))
    conn.commit()
    return holen(db, str(cur.lastrowid)) or {}


def aktiv_setzen(db, name_oder_id, aktiv: bool) -> dict:
    f = holen(db, name_oder_id)
    if not f:
        raise FilterFehler(f"Keinen Filter „{name_oder_id}“ gefunden.", vorhandene=[x["name"] for x in alle(db)])
    if f["art"] != "regel":
        raise FilterFehler("Eine Ansicht wirkt nur, wenn du sie auswählst — an- und ausschalten gibt es für Regeln.")
    conn = db.connect()
    conn.execute(f"UPDATE {TABELLE} SET aktiv=?, geaendert_am=? WHERE id=?", (1 if aktiv else 0, _jetzt(), f["id"]))
    conn.commit()
    return holen(db, str(f["id"])) or {}


def loeschen(db, name_oder_id) -> dict:
    """Loescht den Filter. Aussortiertes bleibt aussortiert (und laesst sich zurueckholen)."""
    f = holen(db, name_oder_id)
    if not f:
        raise FilterFehler(f"Keinen Filter „{name_oder_id}“ gefunden.", vorhandene=[x["name"] for x in alle(db)])
    conn = db.connect()
    conn.execute(f"DELETE FROM {TABELLE} WHERE id=? AND profile_id=?", (f["id"], _profil(db)))
    conn.commit()
    return f


def als_eintrag(f: dict) -> dict:
    """Ein Filter, wie Claude und das Dashboard ihn zeigen."""
    eintrag = {
        "id": f["id"],
        "name": f["name"],
        "art": f["art"],
        "bedingungen": f["bedingungen"],
        "beschreibung": _sf.klartext(f["bedingungen"]),
        "erstellt_am": f.get("erstellt_am"),
    }
    if f["art"] == "regel":
        eintrag.update({
            "aktiv": f["aktiv"],
            "gruende": f["gruende"],
            "zuletzt_angewendet": f.get("zuletzt_angewendet"),
            "treffer_gesamt": int(f.get("treffer_gesamt") or 0),
        })
    return eintrag


def _stelle_kurz(j: dict, sprache_von) -> dict:
    eintrag = {"hash": j.get("hash"), "titel": j.get("title"), "firma": j.get("company"),
               "quelle": j.get("source"), "score": j.get("score")}
    from . import sprache as _spr
    eintrag.update(_spr.merkmal(j, sprache_von(j)))
    return eintrag


def _hindernis(job: dict, gruende: list[str], beworbene: set) -> str:
    """Warum eine Regel diese Stelle nicht aussortieren darf: '' = darf."""
    if (job.get("hash") or "") in beworbene:
        return "bewerbung"
    from . import aussortier_schutz
    return aussortier_schutz.automatik_gesperrt(job, gruende[0] if gruende else "")


def treffer(db, f: dict, jobs: list | None = None) -> dict:
    """Welche aktiven Stellen der Filter trifft - und (bei einer Regel) welche er
    davon wirklich aussortieren duerfte. Schreibt nichts."""
    if jobs is None:
        jobs = db.get_active_jobs(exclude_blacklisted=True)
    sv = _sf.sprach_speicher()
    getroffen = _sf.filtern(jobs, f["bedingungen"], sprache_von=sv)
    ergebnis = {"getroffen": getroffen, "sprache_von": sv,
                "geschuetzt": [], "mit_bewerbung": [], "aussortierbar": getroffen}
    if f["art"] == "regel":
        beworbene = db.get_applied_job_hashes()
        aussortierbar = []
        for j in getroffen:
            grund = _hindernis(j, f["gruende"], beworbene)
            if grund == "bewerbung":
                ergebnis["mit_bewerbung"].append(j)
            elif grund:
                ergebnis["geschuetzt"].append(j)
            else:
                aussortierbar.append(j)
        ergebnis["aussortierbar"] = aussortierbar
    if "sprache" in f["bedingungen"] and "unbekannt" not in f["bedingungen"]["sprache"]:
        ergebnis["sprache_unbekannt"] = sum(1 for j in jobs if sv(j) == "unbekannt")
    return ergebnis


def vorschau(db, f: dict) -> dict:
    """Was der Filter HEUTE trifft (Testen, Antwort auf Anlegen). Schreibt nichts."""
    t = treffer(db, f)
    sv = t["sprache_von"]
    antwort = {"filter": als_eintrag(f), "anzahl_treffer": len(t["getroffen"])}
    if f["art"] == "regel":
        antwort["wuerde_aussortieren"] = len(t["aussortierbar"])
        antwort["beispiele"] = [_stelle_kurz(j, sv) for j in t["aussortierbar"][:BEISPIELE]]
        if t["geschuetzt"]:
            antwort["geschuetzt"] = len(t["geschuetzt"])
            antwort["geschuetzt_hinweis"] = (
                "Zurückgeholte Stellen und Stellen mit gelesenem Urteil (empfohlen/bedingt) "
                "sortiert eine Regel nie aus.")
        if t["mit_bewerbung"]:
            antwort["mit_bewerbung"] = len(t["mit_bewerbung"])
    else:
        antwort["beispiele"] = [_stelle_kurz(j, sv) for j in t["getroffen"][:BEISPIELE]]
    if "sprache_unbekannt" in t:
        antwort["sprache_unbekannt"] = t["sprache_unbekannt"]
        antwort["sprache_unbekannt_hinweis"] = (
            f"{t['sprache_unbekannt']} aktive Stelle(n) haben keinen oder einen zu kurzen Anzeigentext — "
            "ihre Sprache ist unbekannt, und dieser Filter trifft sie nicht.")
    return antwort


def _aussortieren(db, f: dict, jobs: list) -> int:
    """Sortiert die Stellen mit den Gruenden der Regel aus; zaehlt, was wirklich geschah."""
    # #1297: ein Grund, den der Mensch inzwischen abgeschaltet hat, traegt keine
    # Regel mehr. Bleibt keiner uebrig, sortiert die Regel nichts aus.
    aktiv = {x.lower() for x in erlaubte_gruende(db)}
    g = [x for x in f["gruende"] if str(x).lower() in aktiv]
    if not g:
        logger.info("Regel %s: alle Gruende abgeschaltet, nichts aussortiert", f["name"])
        return 0
    grund = json.dumps(g, ensure_ascii=False) if len(g) > 1 else g[0]
    notiz = f"Regel „{f['name']}“"
    n = 0
    for j in jobs:
        try:
            # Rueckgabewert auswerten (L11): das Nadeloehr weist geschuetzte Stellen ab.
            if db.dismiss_job(j["hash"], grund, herkunft=HERKUNFT, notiz=notiz):
                n += 1
        except Exception as exc:  # noqa: BLE001 - eine Stelle kippt keinen Lauf
            logger.warning("Regel %s: %s nicht aussortiert: %s", f["name"], j.get("hash"), exc)
    if n:
        conn = db.connect()
        conn.execute(f"UPDATE {TABELLE} SET treffer_gesamt=treffer_gesamt+?, zuletzt_angewendet=? WHERE id=?",
                     (n, _jetzt(), f["id"]))
        conn.commit()
    return n


def anwenden(db, f: dict, dry_run: bool = True) -> dict:
    """Wendet eine Regel auf den BESTAND an. Vorgabe: nur Vorschau."""
    if f["art"] != "regel":
        raise FilterFehler("Eine Ansicht sortiert nichts aus. Zum Ansehen: stellen_anzeigen(ansicht=...).")
    if dry_run:
        antwort = vorschau(db, f)
        antwort["dry_run"] = True
        antwort["naechster_schritt"] = (
            f"Mit dry_run=False sortiert die Regel {antwort.get('wuerde_aussortieren', 0)} Stelle(n) aus "
            "(zurückholen geht unter Stellen › Aussortiert).")
        return antwort
    t = treffer(db, f)
    n = _aussortieren(db, f, t["aussortierbar"])
    return {"dry_run": False, "filter": als_eintrag(holen(db, str(f["id"])) or f), "aussortiert": n,
            "geschuetzt": len(t["geschuetzt"]), "mit_bewerbung": len(t["mit_bewerbung"]),
            "naechster_schritt": ("Aussortiertes steht unter Stellen › Aussortiert (Herkunft Automatik, "
                                  f"Notiz „Regel {f['name']}“) und lässt sich dort zurückholen.")}


def nach_treffern(db, hashes, anlass: str = "") -> dict | None:
    """Aktive Regeln auf NEUE Treffer anwenden (nach Suche oder Uebernahme).

    `hashes`: die Kennungen der eben angelegten Stellen. Ohne aktive Regel oder
    ohne Treffer: None. Jede Regel nimmt nur Stellen, die noch aktiv sind; die
    erste passende Regel sortiert aus."""
    regeln = [f for f in alle(db, "regel") if f["aktiv"]]
    kennungen = [h for h in dict.fromkeys(hashes or []) if h]
    if not regeln or not kennungen:
        return None
    jobs = []
    for h in kennungen:
        j = db.get_job(h)
        if j and j.get("is_active"):
            jobs.append(j)
    if not jobs:
        return None
    je_regel: dict = {}
    geschuetzt = 0
    offen = jobs
    for f in regeln:
        t = treffer(db, f, offen)
        geschuetzt += len(t["geschuetzt"]) + len(t["mit_bewerbung"])
        n = _aussortieren(db, f, t["aussortierbar"]) if t["aussortierbar"] else 0
        if n:
            je_regel[f["name"]] = n
        weg = {j.get("hash") for j in t["getroffen"]}
        offen = [j for j in offen if j.get("hash") not in weg]
    gesamt = sum(je_regel.values())
    if gesamt:
        logger.info("Eigene Regeln (%s): %d neue Stelle(n) aussortiert %s", anlass, gesamt, je_regel)
    return {"geprueft": len(jobs), "aussortiert": gesamt, "je_regel": je_regel, "geschuetzt": geschuetzt}


def nach_suche(db, such_job_id: str) -> dict | None:
    """Nach einem fertigen internen Suchlauf: Regeln auf dessen neue Treffer.
    Das Ergebnis steht danach im Suchlauf unter `eigene_regeln`."""
    such = db.get_background_job(such_job_id)
    if not such or such.get("status") not in ("fertig", "erledigt"):
        return None
    ergebnis = such.get("result") if isinstance(such.get("result"), dict) else {}
    erg = nach_treffern(db, ergebnis.get("neue_treffer") or [], anlass="suche")
    if erg and erg["aussortiert"]:
        try:
            such = db.get_background_job(such_job_id) or {}
            res = such.get("result") if isinstance(such.get("result"), dict) else {}
            res["eigene_regeln"] = {"aussortiert": erg["aussortiert"], "je_regel": erg["je_regel"]}
            db.update_background_job(such_job_id, such.get("status", "fertig"),
                                     progress=such.get("progress", 100),
                                     message=such.get("message", ""), result=res)
        except Exception as exc:  # pragma: no cover
            logger.warning("Regel-Ergebnis nicht am Suchlauf vermerkt: %s", exc)
    return erg


def nach_uebernahme(db, ergebnis: dict, hashes) -> None:
    """Nach `browser_treffer_uebernehmen` / `linkedin_treffer_uebernehmen` (echter
    Lauf): Regeln auf die angelegten Stellen, Ergebnis in die Antwort. Nie fatal."""
    try:
        erg = nach_treffern(db, hashes, anlass="uebernahme")
    except Exception as exc:  # noqa: BLE001 - die Uebernahme war gut
        logger.warning("Eigene Regeln nach der Übernahme: %s", exc)
        return
    if erg and erg["aussortiert"]:
        ergebnis["eigene_regeln"] = {
            "aussortiert": erg["aussortiert"], "je_regel": erg["je_regel"],
            "hinweis": ("Deine eigenen Regeln haben davon "
                        f"{erg['aussortiert']} Stelle(n) aussortiert; sie stehen unter Stellen › Aussortiert."),
        }


AKTIONEN = ("anzeigen", "anlegen", "testen", "anwenden", "aktivieren", "deaktivieren", "loeschen")


def verwalten(db, aktion: str, name: str = "", art: str = "", bedingungen: dict | None = None,
              gruende=None, dry_run: bool = True) -> dict:
    """Die eine Antwort fuer das Claude-Werkzeug `stellen_filter_verwalten` und
    die Endpunkte des Dashboards. Fehler kommen als `fehler` mit naechstem Schritt."""
    aktion = str(aktion or "anzeigen").strip().lower()
    try:
        if aktion == "anzeigen":
            filter_ = alle(db)
            return {
                "status": "ok",
                "anzahl": len(filter_),
                "ansichten": [als_eintrag(f) for f in filter_ if f["art"] == "ansicht"],
                "regeln": [als_eintrag(f) for f in filter_ if f["art"] == "regel"],
                "naechster_schritt": (
                    "Eine Ansicht zeigt stellen_anzeigen(ansicht='<Name>'); eine Regel prüft "
                    "aktion='testen', den Bestand nimmt aktion='anwenden'. Neu: aktion='anlegen'."
                    if filter_ else
                    "Noch kein eigener Filter. Anlegen mit aktion='anlegen', art='ansicht' (nur filtern) oder "
                    "art='regel' (neue Treffer aussortieren, mit Grund)."),
            }
        if aktion == "anlegen":
            f = anlegen(db, name, art, bedingungen or {}, gruende)
            antwort = vorschau(db, f)
            antwort["status"] = "angelegt"
            if f["art"] == "regel":
                antwort["hinweis"] = (
                    "Die Regel ist angelegt und aktiv. Sie sortiert ab jetzt passende NEUE Treffer nach jeder Suche "
                    "aus. Am Bestand hat sie noch nichts geändert — oben steht, was sie heute treffen würde.")
                antwort["naechster_schritt"] = (
                    f"Bestand jetzt bereinigen: stellen_filter_verwalten(aktion='anwenden', name='{f['name']}', "
                    "dry_run=False). Zurückholen geht unter Stellen › Aussortiert.")
            else:
                antwort["naechster_schritt"] = (
                    f"Ansehen: stellen_anzeigen(ansicht='{f['name']}') oder im Dashboard unter Stellen › Ansicht.")
            return antwort
        if aktion in ("testen", "anwenden", "aktivieren", "deaktivieren", "loeschen"):
            if not str(name or "").strip():
                raise FilterFehler("name fehlt (Name oder Kennung aus aktion='anzeigen').")
            if aktion in ("aktivieren", "deaktivieren"):
                f = aktiv_setzen(db, name, aktion == "aktivieren")
                return {"status": "ok", "filter": als_eintrag(f),
                        "hinweis": ("Die Regel wirkt wieder auf neue Treffer." if f["aktiv"] else
                                    "Die Regel ruht: neue Treffer bleiben stehen. Bereits Aussortiertes bleibt aussortiert.")}
            f = holen(db, name)
            if not f:
                raise FilterFehler(f"Keinen Filter „{name}“ gefunden.", vorhandene=[x["name"] for x in alle(db)])
            if aktion == "testen":
                antwort = vorschau(db, f)
                antwort["status"] = "vorschau"
                antwort["hinweis"] = "Nur ein Test — nichts wurde verändert."
                return antwort
            if aktion == "anwenden":
                antwort = anwenden(db, f, dry_run=dry_run)
                antwort["status"] = "vorschau" if dry_run else "angewendet"
                return antwort
            if dry_run:
                return {"status": "vorschau", "dry_run": True, "filter": als_eintrag(f),
                        "hinweis": ("Löschen entfernt nur den Filter. Was eine Regel aussortiert hat, bleibt aussortiert "
                                    "und lässt sich unter Stellen › Aussortiert zurückholen."),
                        "naechster_schritt": f"Löschen: aktion='loeschen', name='{f['name']}', dry_run=False."}
            loeschen(db, f["id"])
            return {"status": "geloescht", "filter": als_eintrag(f)}
        raise FilterFehler(f"Unbekannte Aktion '{aktion}'. Möglich: {', '.join(AKTIONEN)}.")
    except FilterFehler as fehler:
        antwort = {"fehler": str(fehler)}
        antwort.update(fehler.zusatz)
        return antwort
