"""Die eine Stelle, an der entschieden wird: blockt die Blacklist das? (#992)

Befund vom 07.09.2026. Eine Stelle mit dem MUSS-Begriff zweimal im Titel
wurde beim Anlegen abgewiesen — mit einer Begruendung, die keine Firma
beschreibt, sondern eine Gattung ("Zeitarbeit/Consulting, kein Fit").
Fuer genau diesen Fall gibt es seit C31/#790 die Titel-Ausnahme
(`ausser_wenn_titel_enthaelt`): die Firma bleibt geblockt, die fachlich
passenden Rollen kommen durch.

**Der eigentliche Befund war, dass die Ausnahme nur an zwei von vier
Stellen ueberhaupt gelesen wurde.** Die Frage "blockt die Blacklist
diese Stelle" stand viermal im Code:

* `database.is_company_blacklisted` — Substring-Match, MIT Ausnahme
* `blacklist_anwenden` (tools/suche.py) — Substring-Match, MIT Ausnahme
* `job_scraper._post_search_cleanup` — Substring, OHNE Ausnahme
* `database.get_active_jobs(exclude_blacklisted=True)` — GLEICHHEIT
  statt Substring, OHNE Ausnahme

Die beiden letzten sind die, die zaehlen: der Suchlauf und die Liste,
die der Mensch ansieht. Wer die Ausnahme setzte, bekam die Stelle beim
manuellen Anlegen durch — und der naechste Suchlauf warf sie wieder weg,
ohne dass irgendwo etwas davon stand.

Das ist zum siebten Mal dasselbe Muster (#963, #913, #976, #987, #991,
#994): **wo zwei Wege denselben Wert erzeugen, gehoert ein Aufruf hin,
kein Hinweis.** Hier ist der Aufruf.

Dieses Modul ist bewusst DB-frei — es bekommt die Eintraege gereicht und
gibt ein Urteil zurueck. So kann `database.py` es benutzen, ohne dass
ein Zyklus entsteht.
"""
from __future__ import annotations

from datetime import datetime, timezone

# v1.7.12 (#828, C33): Woerter, die auf ein Gattungsurteil statt einer
# konkreten Erfahrung hindeuten. Belegter Fall 11.08.: ein Blacklist-Grund
# "bewusste Entscheidung gegen Beratungshaus" (tatsaechlicher Anlass: nie
# Rueckmeldung von genau EINER Firma) wurde bei spaeteren Bewertungen als
# generelle Haltung gelesen und verzerrte zwei unbeteiligte Stellen.
# v1.7.41 (#992): hierher verschoben, weil jetzt drei Aufrufer die Liste
# brauchen — der Hinweis beim Anlegen, die Bestandspruefung und die
# Blockade-Auskunft. Am alten Ort waere sie ein viertes Mal getippt worden.
KATEGORIEN_WOERTER = (
    "beratungshaus", "beratungshaeuser", "consulting", "zeitarbeit",
    "personaldienstleister", "vermittler", "branche", "generell",
    "grundsaetzlich", "alle ", "solche firmen", "diese art",
)

# Ab wann ein Gattungsurteil zur Ueberpruefung vorgeschlagen wird. Ein
# Urteil aus neun aussortierten Stellen von vor Monaten ist keine
# Tatsache mehr, sondern eine Vermutung mit Datum (#992 Vorschlag 5).
PRUEF_INTERVALL_TAGE = 180

# Kappung des Blockade-Protokolls. Ein Protokoll ohne Grenze ist auch
# eine Datenmenge (#991 MERKE 5) — die letzten Blockaden beantworten die
# Frage "was wirft mein Filter gerade weg" vollstaendig.
PROTOKOLL_MAX = 500


def _lc(wert) -> str:
    return (wert or "").strip().lower()


def firmen_eintraege(eintraege) -> list:
    return [e for e in (eintraege or []) if e.get("type") == "firma"]


def keyword_eintraege(eintraege) -> list:
    return [e for e in (eintraege or []) if e.get("type") == "keyword"]


def ausnahme_treffer(eintrag, titel: str):
    """Welcher Ausnahme-Begriff hebelt diesen Firmen-Block aus? (#790)"""
    t = _lc(titel)
    if not t:
        return None
    for a in (eintrag.get("ausser_wenn_titel_enthaelt") or []):
        if a and a.lower() in t:
            return a
    return None


def treffer(eintraege, firma: str, titel: str = "",
            typen=("firma", "keyword")) -> dict | None:
    """Blockt die Blacklist diese Stelle? Die EINE Antwort.

    Firmen matchen beidseitig als Substring ("Musterfirma" matcht
    "Musterfirma Software GmbH" und umgekehrt), Keywords in Titel ODER
    Firma. Steht ein Ausnahme-Begriff im Titel, greift der Firmen-Block
    nicht — und zwar ueberall, nicht nur dort, wo jemand daran gedacht
    hat.

    Returns:
        None, wenn nichts blockt. Sonst ein dict mit `typ` (firma/
        keyword), `wert`, `grund`, `eintrag_id` und `eintrag`.

    Args:
        typen: welche Eintragsarten zaehlen. `("firma",)` fuer die Frage
            "steht diese FIRMA auf der Blacklist" — beim Anlegen einer
            einzelnen Stelle soll ein Keyword-Eintrag nicht stillschweigend
            mitblocken, dort entscheidet der Mensch.
    """
    f_lc, t_lc = _lc(firma), _lc(titel)

    for e in (firmen_eintraege(eintraege) if "firma" in typen else []):
        v = _lc(e.get("value"))
        if not v or not f_lc:
            continue
        if not (v in f_lc or f_lc in v):
            continue
        if ausnahme_treffer(e, titel):
            # Ausnahme greift — und zwar fuer die GANZE Blacklist-Frage:
            # ein zweiter Firmen-Eintrag darf dieselbe Stelle nicht doch
            # noch wegwerfen, sonst haengt das Ergebnis an der Reihenfolge.
            return None
        return {"typ": "firma", "wert": e.get("value"),
                "grund": e.get("reason") or "", "eintrag_id": e.get("id"),
                "eintrag": e}

    for e in (keyword_eintraege(eintraege) if "keyword" in typen else []):
        v = _lc(e.get("value"))
        if not v:
            continue
        if v in t_lc or v in f_lc:
            return {"typ": "keyword", "wert": e.get("value"),
                    "grund": e.get("reason") or "", "eintrag_id": e.get("id"),
                    "eintrag": e}
    return None


def verschont(eintraege, firma: str, titel: str) -> dict | None:
    """Wurde die Stelle NUR durch eine Ausnahme gerettet? Fuer die Anzeige.

    Der Mensch soll sehen, WARUM eine Stelle trotz Blacklist da ist —
    sonst wirkt die Ausnahme wie ein Fehler des Filters.
    """
    f_lc = _lc(firma)
    if not f_lc or not titel:
        return None
    for e in firmen_eintraege(eintraege):
        v = _lc(e.get("value"))
        if not v or not (v in f_lc or f_lc in v):
            continue
        a = ausnahme_treffer(e, titel)
        if a:
            return {"eintrag": e.get("value"), "begriff": a,
                    "eintrag_id": e.get("id")}
    return None


def gattungswoerter(grund: str) -> list:
    """Welche Gattungsmerkmale stehen in dieser Begruendung?"""
    g = _lc(grund)
    if not g:
        return []
    return [w.strip() for w in KATEGORIEN_WOERTER if w in g]


def alter_tage(eintrag, heute=None):
    """Alter des Eintrags in Tagen, oder None wenn kein Datum da ist."""
    roh = eintrag.get("created_at")
    if not roh:
        return None
    try:
        d = datetime.fromisoformat(str(roh).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    jetzt = heute or datetime.now(timezone.utc)
    if jetzt.tzinfo is None:
        jetzt = jetzt.replace(tzinfo=timezone.utc)
    return max(0, (jetzt - d).days)


def muss_treffer(titel: str, kriterien) -> list:
    """MUSS-Begriffe im Stellentitel — der maschinell erkennbare Widerspruch.

    Ein Eintrag, der Titel mit den eigenen MUSS-Begriffen wegwirft, sagt
    zwei Dinge gleichzeitig: "das suche ich" und "das will ich nicht".
    Eines von beiden ist falsch, und der Mensch muss entscheiden welches.
    """
    t = _lc(titel)
    if not t:
        return []
    muss = (kriterien or {}).get("keywords_muss") or []
    return [k for k in muss if k and k.lower() in t]


def _empfehlung(eintrag, woerter, kollisionen, alter):
    if kollisionen:
        return ("Dieser Eintrag wirft Stellen weg, deren Titel deine "
                "MUSS-Begriffe enthaelt. Setz eine Ausnahme statt den "
                "Eintrag zu loeschen: blacklist_verwalten('aendern', "
                f"entry_id={eintrag.get('id')}, "
                "ausser_wenn_titel_enthaelt=[...]).")
    if woerter and not (eintrag.get("ausser_wenn_titel_enthaelt") or []):
        return ("Die Begruendung beschreibt eine Gattung, keine Firma. "
                "Bei Personaldienstleistern und Beratungen ist eine "
                "Titel-Ausnahme fast immer richtiger als ein pauschaler "
                "Block: blacklist_verwalten('aendern', "
                f"entry_id={eintrag.get('id')}, "
                "ausser_wenn_titel_enthaelt=[...]).")
    if not (eintrag.get("reason") or "").strip():
        return ("Ohne Begruendung laesst sich der Eintrag spaeter nicht "
                "mehr pruefen — auch nicht von dir selbst. Nachtragen: "
                f"blacklist_verwalten('aendern', entry_id={eintrag.get('id')}, "
                "grund='...').")
    if woerter and alter is not None and alter >= PRUEF_INTERVALL_TAGE:
        return (f"Gattungsurteil, {alter} Tage alt — lohnt eine "
                "Gegenprobe, ob die Firma inzwischen anderes ausschreibt.")
    return None


def befund(eintraege, kriterien=None, blockaden=None, heute=None) -> list:
    """Bestandspruefung: was tut jeder Eintrag, und ist das noch richtig?

    Args:
        eintraege: die Blacklist (db.get_blacklist()).
        kriterien: Suchkriterien — fuer die MUSS-Kollisionen.
        blockaden: Protokollzeilen (db.get_blacklist_blocks()), je Eintrag
            zugeordnet ueber `eintrag_wert`.
        heute: fuer Tests.
    """
    je_wert = {}
    for b in (blockaden or []):
        je_wert.setdefault(_lc(b.get("eintrag_wert")), []).append(b)

    out = []
    for e in (eintraege or []):
        woerter = gattungswoerter(e.get("reason") or "")
        alter = alter_tage(e, heute)
        meine = je_wert.get(_lc(e.get("value")), [])
        kollisionen, behoben = [], 0
        for b in meine:
            k = muss_treffer(b.get("titel") or "", kriterien)
            if not k:
                continue
            # Das Protokoll ist Vergangenheit, das Urteil ist Gegenwart:
            # wer inzwischen eine Ausnahme gesetzt hat, soll nicht weiter
            # ermahnt werden. Also gegen die HEUTIGE Regel nachrechnen.
            if not treffer(eintraege, b.get("firma") or "",
                           b.get("titel") or ""):
                behoben += 1
                continue
            kollisionen.append({"titel": b.get("titel"),
                                "firma": b.get("firma"),
                                "muss_begriffe": k,
                                "blockiert_am": b.get("blockiert_am")})
        eintrag = {
            "entry_id": e.get("id"),
            "typ": e.get("type"),
            "wert": e.get("value"),
            "grund": e.get("reason") or "",
            "alter_tage": alter,
            "gattungswoerter": woerter,
            "ausser_wenn_titel_enthaelt": e.get("ausser_wenn_titel_enthaelt") or [],
            "geblockt_protokolliert": len(meine),
            "muss_kollisionen": kollisionen,
        }
        if behoben:
            eintrag["muss_kollisionen_behoben"] = behoben
        rat = _empfehlung(e, woerter, kollisionen, alter)
        if rat:
            eintrag["empfehlung"] = rat
        out.append(eintrag)

    # Das Dringendste zuerst: echter Widerspruch, dann Gattungsurteil,
    # dann fehlende Begruendung.
    def _rang(x):
        return (0 if x["muss_kollisionen"] else
                1 if x["gattungswoerter"] and not x["ausser_wenn_titel_enthaelt"] else
                2 if not x["grund"].strip() else 3,
                -x["geblockt_protokolliert"])
    out.sort(key=_rang)
    return out
