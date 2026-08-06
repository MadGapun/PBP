"""Regelbasierte Erkenntnisse aus dem PBP-Bestand (#799/F35, v1.7.11).

Loest die Fehlkonstruktion aus v1.7.10/#784 ab: dort wurde eine zweite
Tabelle `learned_insights` angelegt, obwohl `learning_insights` (#594)
bereits existierte — die UI las die eine, die Logik schrieb in die andere,
und der Nutzer sah nie etwas. Jetzt schreibt alles in `learning_insights`.

Zwei Grundsaetze:

1. **Ohne lokale KI lauffaehig.** Alle Aussagen entstehen aus Zaehlwerten
   der eigenen Datenbank. Ollama kann darueber formulieren, nicht darunter:
   faellt es aus, bleiben die Erkenntnisse bestehen — nur nuechterner.
2. **Nichts wirkt ohne Bestaetigung.** `bestaetigt_vom_user`: 0 offen,
   1 bestaetigt, -1 widersprochen (wird nie erneut vorgeschlagen).

`scope` trennt die beiden Welten, die der Nutzer nicht vermischt sehen
will: `strategie` (was sagen meine Daten ueber meine Bewerbungen?) und
`bedienung` (wie benutze ich die Oberflaeche?). Wer wissen will, was
seine Absagen verbindet, will nicht im selben Atemzug lesen, dass er
viel klickt.
"""
from __future__ import annotations

import json
import time
from typing import Any

# Wall-Clock-Budget (#799 Befund 1): kein Ableitungslauf darf den Server
# blockieren. Wird zwischen den Regeln geprueft — jede Regel ist fuer sich
# kurz, aber bei wachsendem Bestand summiert sich das.
DEFAULT_BUDGET_SEKUNDEN = 20

SCOPE_STRATEGIE = "strategie"
SCOPE_BEDIENUNG = "bedienung"


def _konfidenz(n: int) -> float:
    """Konfidenz aus Fallzahl: 5 Faelle ~0.33, 10 ~0.5, 30 ~0.75, 90 ~0.9.

    Eine Erkenntnis aus zwei Faellen ist eine Vermutung, eine aus dreissig
    ein Muster — das muss sichtbar bleiben, sonst wirkt beides gleich.
    """
    return round(min(0.95, n / (n + 10)), 2)


def _unsicherheits_praefix(n: int) -> str:
    """Bei duenner Datenlage steht die Unsicherheit IN der Aussage, nicht
    in einer Fussnote (Bericht-Designprinzip v1.6.8)."""
    if n < 5:
        return "Erster Hinweis (nur wenige Faelle): "
    if n < 15:
        return "Tendenz: "
    return ""


def _kandidat(kind: str, scope: str, aussage: str, evidenz: dict,
              n: int) -> dict:
    return {
        "kind": kind,
        "scope": scope,
        "aussage": _unsicherheits_praefix(n) + aussage,
        "evidenz": evidenz,
        "belegt_durch_n": n,
        "konfidenz": _konfidenz(n),
    }


# --------------------------------------------------------------- Regeln
# Jede Regel ist eine Funktion (db) -> list[dict]. Sie darf fehlschlagen,
# ohne den Lauf zu kippen — dann fehlt eben diese eine Erkenntnis.

def _regel_aussortier_muster(db: Any) -> list:
    """Welche Ablehnungsgruende dominieren?"""
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT dismiss_reason, COUNT(*) AS n FROM jobs "
        "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
        "AND COALESCE(dismiss_reason,'') NOT IN ('', 'bewerbung_erstellt') "
        "GROUP BY dismiss_reason ORDER BY n DESC", (pid,)
    ).fetchall()
    gesamt = sum(r["n"] for r in rows)
    if not gesamt:
        return []
    out = []
    for r in rows[:2]:
        if r["n"] < 5:
            continue
        anteil = round(r["n"] / gesamt * 100, 1)
        out.append(_kandidat(
            "dismiss_pattern", SCOPE_STRATEGIE,
            f"{anteil} % deiner Aussortierungen entfallen auf "
            f"'{r['dismiss_reason']}' ({r['n']} von {gesamt}). Ein Filter, "
            "der das vorab abfaengt, spart genau diese Sichtungsarbeit.",
            {"grund": r["dismiss_reason"], "anzahl": r["n"],
             "gesamt_aussortiert": gesamt, "anteil_prozent": anteil},
            r["n"]))
    return out


def _regel_kanal(db: Any) -> list:
    """Ueber welchen Weg entstehen tatsaechlich Interviews? (Daten aus #781)"""
    from .statistik_erweitert import kanal_auswertung
    ka = kanal_auswertung(db)
    kanaele = {k: v for k, v in (ka.get("kanaele") or {}).items()
               if v.get("bewerbungen", 0) >= 3 and k != "unklassifiziert"}
    if len(kanaele) < 2:
        return []
    beste = max(kanaele, key=lambda k: kanaele[k]["interview_quote"])
    schlechteste = min(kanaele, key=lambda k: kanaele[k]["interview_quote"])
    if kanaele[beste]["interview_quote"] <= 0:
        return []
    if kanaele[beste]["interview_quote"] < kanaele[schlechteste]["interview_quote"] * 1.5:
        return []
    label = {"vermittler_recruiter": "ueber Vermittler",
             "portal": "ueber Jobportale", "netzwerk": "ueber Kontakte",
             "direktbewerbung": "als Direktbewerbung"}
    n = kanaele[beste]["bewerbungen"]
    return [_kandidat(
        "kanal_pattern", SCOPE_STRATEGIE,
        f"Bewerbungen {label.get(beste, beste)} fuehren bei dir deutlich "
        f"haeufiger zu einem Interview ({kanaele[beste]['interview_quote']} %) "
        f"als {label.get(schlechteste, schlechteste)} "
        f"({kanaele[schlechteste]['interview_quote']} %).",
        {"kanaele": {k: {"bewerbungen": v["bewerbungen"],
                         "interviews": v["interviews"],
                         "quote": v["interview_quote"]}
                     for k, v in kanaele.items()}}, n)]


def _regel_score_realitaet(db: Any) -> list:
    """Hoher Score, trotzdem aussortiert — der belegte Fehlleitungsfall."""
    conn = db.connect()
    pid = db.get_active_profile_id()
    avg = (conn.execute(
        "SELECT AVG(score) AS a FROM jobs "
        "WHERE (profile_id=? OR profile_id IS NULL) AND score > 0",
        (pid,)).fetchone()["a"]) or 0
    if avg <= 0:
        return []
    schwelle = round(avg * 2)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM jobs WHERE is_active=0 "
        "AND (profile_id=? OR profile_id IS NULL) AND score >= ? "
        "AND COALESCE(dismiss_reason,'') NOT IN ('', 'bewerbung_erstellt')",
        (pid, schwelle)).fetchone()
    n = row["n"] if row else 0
    if n < 3:
        return []
    beispiele = [
        {"titel": r["title"], "firma": r["company"], "score": r["score"],
         "grund": r["dismiss_reason"]}
        for r in conn.execute(
            "SELECT title, company, score, dismiss_reason FROM jobs "
            "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
            "AND score >= ? AND COALESCE(dismiss_reason,'') "
            "NOT IN ('', 'bewerbung_erstellt') ORDER BY score DESC LIMIT 3",
            (pid, schwelle)).fetchall()]
    return [_kandidat(
        "score_check", SCOPE_STRATEGIE,
        f"{n} Stellen mit hohem Score (ab {schwelle}) hast du trotzdem "
        "aussortiert. Der Score misst Begriffe, nicht Passung — verlass "
        "dich bei der Vorauswahl nicht allein auf ihn.",
        {"schwelle": schwelle, "anzahl": n, "beispiele": beispiele}, n)]


def _regel_reaktionszeit(db: Any) -> list:
    """Wie lange dauert eine Rueckmeldung — und wann ist ein Vorgang tot?"""
    from .statistik_erweitert import zeitliche_kennzahlen
    zk = zeitliche_kennzahlen(db)
    r = zk.get("zeit_bis_erste_reaktion") or {}
    if not r.get("anzahl") or r["anzahl"] < 5:
        return []
    median = r["median_tage"]
    # "Praktisch tot" = deutlich jenseits des ueblichen Rahmens
    tot_ab = int(max(median * 3, median + 21))
    return [_kandidat(
        "reaktionszeit", SCOPE_STRATEGIE,
        f"Eine erste Rueckmeldung kommt bei dir typischerweise nach "
        f"{median} Tagen (Median aus {r['anzahl']} Vorgaengen). Kommt nach "
        f"{tot_ab} Tagen nichts, lohnt Nachfassen mehr als Warten.",
        {"median_tage": median, "mittel_tage": r.get("mittel_tage"),
         "anzahl": r["anzahl"], "faustregel_tot_ab_tagen": tot_ab},
        r["anzahl"])]


def _regel_zeitmuster(db: Any) -> list:
    """Bewerbungen pro Monat und was dabei herauskam."""
    from .statistik_erweitert import zeitliche_kennzahlen
    zk = zeitliche_kennzahlen(db)
    pro_monat = zk.get("bewerbungen_pro_monat") or {}
    if len(pro_monat) < 3:
        return []
    werte = list(pro_monat.values())
    schnitt = round(sum(werte) / len(werte), 1)
    iv = zk.get("interviews_pro_monat") or {}
    iv_gesamt = sum(iv.values())
    b_gesamt = sum(werte)
    quote = round(iv_gesamt / b_gesamt * 100, 1) if b_gesamt else 0
    bester = max(pro_monat, key=lambda m: pro_monat[m])
    return [_kandidat(
        "zeitmuster", SCOPE_STRATEGIE,
        f"Du bewirbst dich im Schnitt {schnitt} mal pro Monat "
        f"({b_gesamt} in {len(pro_monat)} Monaten). Auf 100 Bewerbungen "
        f"kommen rechnerisch {quote} Interviews.",
        {"pro_monat": pro_monat, "schnitt": schnitt,
         "aktivster_monat": bester, "interviews_gesamt": iv_gesamt,
         "interview_quote_prozent": quote}, b_gesamt)]


_REGELN = [
    ("aussortier_muster", _regel_aussortier_muster),
    ("kanal", _regel_kanal),
    ("score_realitaet", _regel_score_realitaet),
    ("reaktionszeit", _regel_reaktionszeit),
    ("zeitmuster", _regel_zeitmuster),
]


def kandidaten_ableiten(db: Any,
                        budget_sekunden: int = DEFAULT_BUDGET_SEKUNDEN) -> dict:
    """Alle Regeln mit Wall-Clock-Budget. Liefert IMMER ein Ergebnis —
    bei Budget-Ende ein ehrlich gekennzeichnetes Teilergebnis (#799)."""
    start = time.time()
    kandidaten: list = []
    gelaufen: list = []
    uebersprungen: list = []
    fehler: dict = {}
    for name, regel in _REGELN:
        if time.time() - start > budget_sekunden:
            uebersprungen.append(name)
            continue
        try:
            kandidaten.extend(regel(db))
            gelaufen.append(name)
        except Exception as e:  # eine kaputte Regel kippt den Lauf nicht
            fehler[name] = f"{type(e).__name__}: {e}"
    return {
        "kandidaten": kandidaten,
        "regeln_gelaufen": gelaufen,
        "regeln_uebersprungen": uebersprungen,
        "regel_fehler": fehler,
        "dauer_ms": int((time.time() - start) * 1000),
        "abgebrochen": bool(uebersprungen),
    }


def speichern(db: Any, kandidaten: list, app_version: str = "") -> dict:
    """Legt Kandidaten in `learning_insights` ab (upsert mit Duplikat-Schutz).

    Widersprochene Aussagen (-1) werden von `upsert_learning_insight`
    nicht wiederbelebt — hier zaehlen wir sie nur mit.
    """
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    neu, aufgefrischt, uebersprungen = 0, 0, 0

    def _norm(s: str) -> str:
        return "".join(c for c in (s or "").lower() if not c.isdigit())

    for k in kandidaten:
        ziel = _norm(k["aussage"])
        # gleiche Schwelle wie in upsert_learning_insight: zu kurzer
        # Resttext taugt nicht als Identitaet
        if len(ziel.strip()) < 25:
            ziel = None
        vorher = None
        for r in (conn.execute(
            "SELECT id, title, bestaetigt_vom_user FROM learning_insights "
            "WHERE (profile_id=? OR profile_id='') AND kind=? AND is_active=1",
            (pid, k["kind"])
        ).fetchall() if ziel else []):
            if _norm(r["title"]) == ziel:
                vorher = r
                break
        if vorher is not None and vorher["bestaetigt_vom_user"] == -1:
            uebersprungen += 1
            continue
        db.upsert_learning_insight({
            "kind": k["kind"],
            "scope": k["scope"],
            "title": k["aussage"],
            "details": {
                "evidenz": k["evidenz"],
                "konfidenz": k["konfidenz"],
                "belegt_durch_n": k["belegt_durch_n"],
                "quelle": "regelbasiert",
            },
            "score": k["konfidenz"],
            "app_version": app_version,
        })
        if vorher is None:
            neu += 1
        else:
            aufgefrischt += 1
    return {"neu": neu, "aufgefrischt": aufgefrischt,
            "uebersprungen_widersprochen": uebersprungen}


def bestaetigte_fuer_kontext(db: Any, min_konfidenz: float = 0.5) -> list:
    """Vom User BESTAETIGTE Strategie-Erkenntnisse fuer den Ollama-Kontext.

    Nur `bestaetigt_vom_user=1`, nur Strategie (Bedienhinweise haben in
    einem Bewerbungs-Kontext nichts verloren), nur ueber der Konfidenz-
    Schwelle — schwach belegte Aussagen werden nie als Fakten ausgespielt.
    """
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    rows = conn.execute(
        "SELECT kind, scope, title, details_json, score FROM learning_insights "
        "WHERE (profile_id=? OR profile_id='') AND is_active=1 "
        "AND bestaetigt_vom_user=1 AND COALESCE(scope,'')!=? "
        "AND score >= ? ORDER BY score DESC",
        (pid, SCOPE_BEDIENUNG, min_konfidenz),
    ).fetchall()
    out = []
    for r in rows:
        try:
            details = json.loads(r["details_json"] or "{}")
        except Exception:
            details = {}
        out.append({
            "kategorie": r["kind"],
            "aussage": r["title"],
            "konfidenz": r["score"],
            "belegt_durch_n": details.get("belegt_durch_n", 0),
        })
    return out
