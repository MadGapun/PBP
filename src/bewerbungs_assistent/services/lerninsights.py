"""learned_insights — Fundament der Ollama-Lernschleife (#784, F28, v1.7.10).

Verdichtet, was in PBP tatsaechlich passiert (Aussortier-Gruende,
Bewerbungs-Outcomes, Kanal-Quoten), zu Kandidaten-Aussagen mit EVIDENZ
und KONFIDENZ. Eine Erkenntnis aus zwei Faellen ist eine Vermutung, eine
aus dreissig ein Muster — die Konfidenz macht den Unterschied sichtbar.

⛔ GRUNDSATZ (User-Vorgabe): Keine Erkenntnis wird ohne Nutzerbestaetigung
wirksam. Dieser Service LEITET AB und ZEIGT AN — er wendet nichts an.
Die Anbindung an stellen_auto_aussortieren/Scoring ist der v1.8-Teil und
setzt bestaetigt_vom_user=1 voraus.

Widersprochene Erkenntnisse (bestaetigt_vom_user=-1) werden NIE erneut
vorgeschlagen — dieselbe Fehlableitung darf nicht in drei Wochen
wiederkommen (Anti-Echoraum).

v1.7 bewusst REGELBASIERT (deterministisch, testbar). LLM-gestuetzte
Ableitung ist v1.8.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _konfidenz(n: int) -> float:
    """Konfidenz aus Fallzahl: 5 Faelle ~0.33, 10 ~0.5, 30 ~0.75, 90 ~0.9."""
    return round(min(0.95, n / (n + 10)), 2)


def _kandidat(kategorie: str, aussage: str, evidenz: dict, n: int) -> dict:
    return {
        "kategorie": kategorie,
        "aussage": aussage,
        "evidenz": evidenz,
        "belegt_durch_n": n,
        "konfidenz": _konfidenz(n),
    }


def kandidaten_ableiten(db: Any) -> list:
    """Regelbasierte Kandidaten-Aussagen aus dem Bestand."""
    conn = db.connect()
    pid = db.get_active_profile_id()
    kandidaten: list = []

    # --- Regel 1: dominante Aussortier-Gruende (Verhalten) ---
    gruende = conn.execute(
        "SELECT dismiss_reason, COUNT(*) AS n FROM jobs "
        "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
        "AND COALESCE(dismiss_reason,'') NOT IN ('', 'bewerbung_erstellt') "
        "GROUP BY dismiss_reason ORDER BY n DESC", (pid,)
    ).fetchall()
    gesamt_dismissed = sum(r["n"] for r in gruende)
    for r in gruende[:3]:
        if r["n"] < 10:
            continue
        anteil = round(r["n"] / gesamt_dismissed * 100, 1)
        kandidaten.append(_kandidat(
            "verhalten",
            f"Aussortier-Grund '{r['dismiss_reason']}' dominiert mit "
            f"{anteil} % ({r['n']} von {gesamt_dismissed}) — Suchkriterien "
            "filtern diese Faelle nicht vorab heraus.",
            {"grund": r["dismiss_reason"], "anzahl": r["n"],
             "gesamt_aussortiert": gesamt_dismissed}, r["n"]))

    # --- Regel 2: Zeitarbeit/ANUE-Muster (Stellentyp) ---
    zeitarbeit = next((r["n"] for r in gruende
                       if r["dismiss_reason"] == "zeitarbeit"), 0)
    if zeitarbeit >= 5:
        kandidaten.append(_kandidat(
            "stellentyp",
            f"Arbeitnehmerueberlassung wird konsequent abgelehnt "
            f"({zeitarbeit} Faelle mit Grund 'zeitarbeit').",
            {"grund": "zeitarbeit", "anzahl": zeitarbeit}, zeitarbeit))

    # --- Regel 3: hoher Score schuetzt nicht vor Aussortierung (Scoring) ---
    schwelle_row = conn.execute(
        "SELECT AVG(score) AS avg_s FROM jobs "
        "WHERE (profile_id=? OR profile_id IS NULL) AND score > 0", (pid,)
    ).fetchone()
    avg_s = schwelle_row["avg_s"] or 0
    if avg_s > 0:
        hoch_aussortiert = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs "
            "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
            "AND score >= ? "
            "AND COALESCE(dismiss_reason,'') NOT IN ('', 'bewerbung_erstellt')",
            (pid, avg_s * 2),
        ).fetchone()["n"]
        if hoch_aussortiert >= 5:
            kandidaten.append(_kandidat(
                "rolle",
                f"Hohe Keyword-Scores garantieren keine Passung: "
                f"{hoch_aussortiert} Stellen mit mindestens doppeltem "
                f"Durchschnitts-Score (>= {round(avg_s * 2)}) wurden "
                "trotzdem aussortiert. Score misst Begriffe, nicht Substanz.",
                {"schwelle": round(avg_s * 2), "anzahl": hoch_aussortiert},
                hoch_aussortiert))

    # --- Regel 4: Kanal-Unterschiede (Kanal) ---
    try:
        from .statistik_erweitert import kanal_auswertung
        ka = kanal_auswertung(db)
        kanaele = ka.get("kanaele") or {}
        relevante = {k: v for k, v in kanaele.items()
                     if v.get("bewerbungen", 0) >= 5
                     and k != "unklassifiziert"}
        if len(relevante) >= 2:
            beste = max(relevante, key=lambda k: relevante[k]["interview_quote"])
            schlechteste = min(relevante,
                               key=lambda k: relevante[k]["interview_quote"])
            if (relevante[beste]["interview_quote"]
                    >= relevante[schlechteste]["interview_quote"] * 1.5
                    and relevante[beste]["interview_quote"] > 0):
                n = relevante[beste]["bewerbungen"]
                kandidaten.append(_kandidat(
                    "kanal",
                    f"Kanal '{beste}' konvertiert deutlich besser zu "
                    f"Interviews ({relevante[beste]['interview_quote']} %) "
                    f"als '{schlechteste}' "
                    f"({relevante[schlechteste]['interview_quote']} %).",
                    {"kanaele": {k: v["interview_quote"]
                                 for k, v in relevante.items()}}, n))
    except Exception:
        pass

    return kandidaten


def speichern(db: Any, kandidaten: list) -> dict:
    """Legt neue Kandidaten als unbestaetigt ab (bestaetigt_vom_user=0).

    - Existiert dieselbe Aussage bereits WIDERSPROCHEN (-1): ueberspringen.
    - Existiert sie unbestaetigt/bestaetigt: Evidenz und Fallzahl auffrischen.
    """
    from ..database import _gen_id
    conn = db.connect()
    pid = db.get_active_profile_id() or ""

    def _basis(aussage: str) -> str:
        # Zahlen raus — die aendern sich mit jedem Lauf, die Aussage nicht.
        return "".join(c for c in aussage[:80].lower() if not c.isdigit())

    bestehende = {}
    for r in conn.execute(
        "SELECT id, kategorie, aussage, bestaetigt_vom_user "
        "FROM learned_insights WHERE (profile_id=? OR profile_id='')",
        (pid,),
    ).fetchall():
        bestehende[(r["kategorie"], _basis(r["aussage"]))] = r

    neu, aufgefrischt, uebersprungen = 0, 0, 0
    for k in kandidaten:
        row = bestehende.get((k["kategorie"], _basis(k["aussage"])))
        now = datetime.now().isoformat()
        if row:
            if row["bestaetigt_vom_user"] == -1:
                uebersprungen += 1
                continue
            conn.execute(
                "UPDATE learned_insights SET aussage=?, evidenz_json=?, "
                "konfidenz=?, belegt_durch_n=?, aktualisiert_am=? WHERE id=?",
                (k["aussage"], json.dumps(k["evidenz"], ensure_ascii=False),
                 k["konfidenz"], k["belegt_durch_n"], now, row["id"]))
            aufgefrischt += 1
        else:
            conn.execute(
                "INSERT INTO learned_insights (id, profile_id, kategorie, "
                "aussage, evidenz_json, konfidenz, belegt_durch_n, "
                "erstellt_am, aktualisiert_am, bestaetigt_vom_user) "
                "VALUES (?,?,?,?,?,?,?,?,?,0)",
                (_gen_id(), pid, k["kategorie"], k["aussage"],
                 json.dumps(k["evidenz"], ensure_ascii=False),
                 k["konfidenz"], k["belegt_durch_n"], now, now))
            neu += 1
    conn.commit()
    return {"neu": neu, "aufgefrischt": aufgefrischt,
            "uebersprungen_widersprochen": uebersprungen}


def bestaetigte_fuer_kontext(db: Any, min_konfidenz: float = 0.5) -> list:
    """Vom User BESTAETIGTE Erkenntnisse fuer den Ollama-Systemkontext.

    Nur bestaetigt_vom_user=1 und Konfidenz >= Schwelle — schwach belegte
    Aussagen werden nie als Fakten ausgespielt (Anti-Echoraum).
    """
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    rows = conn.execute(
        "SELECT kategorie, aussage, konfidenz, belegt_durch_n "
        "FROM learned_insights WHERE (profile_id=? OR profile_id='') "
        "AND bestaetigt_vom_user=1 AND konfidenz >= ? "
        "ORDER BY konfidenz DESC", (pid, min_konfidenz),
    ).fetchall()
    return [dict(r) for r in rows]
