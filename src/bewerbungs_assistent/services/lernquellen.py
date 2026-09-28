"""Was fliesst ins Lernen ein — und was nicht (#792).

Der Lernmodus lief taeglich, und von aussen war nicht zu sehen, WAS er
auswertet. Hier steht es an einem Ort, gerechnet statt beschrieben: je
Quelle die Tabellen, die Zahl der Datensaetze im aktiven Profil und der
Zeitraum. Auch das ausdrueckliche "nein" gehoert dazu — wer wissen will,
was das System ueber ihn lernt, will vor allem wissen, was es nicht
anfasst.

Abgrenzung: `lerninsights` leitet ab, `lernprotokoll` haelt jeden Lauf
fest. Diese Liste ist die Beschreibung ihrer Eingaben; ein Test haelt sie
gegen die Tabellen, die die Regeln tatsaechlich lesen.
"""
from __future__ import annotations

from typing import Any

#: Die Nutzungsereignisse wertet nur die Muster-Analyse der lokalen KI
#: aus, und zwar ueber dieses Fenster (dashboard._run_analyze_user_patterns).
FENSTER_AKTIVITAET_TAGE = 30

QUELLEN: list[dict] = [
    {"key": "aussortierungen", "name": "Aussortierte Stellen",
     "tabellen": ["jobs"], "fliesst_ein": True, "stufe": "regeln",
     "wofuer": "Häufigste Ablehnungsgründe; hohe Punkte trotz Aussortieren",
     "felder": "Titel, Firma, Punkte, Grund, Zeitpunkt"},
    {"key": "bewerbungen", "name": "Bewerbungen",
     "tabellen": ["applications"], "fliesst_ein": True, "stufe": "regeln",
     "wofuer": "Kanal (Portal, Vermittler, Kontakt, direkt), Bewerbungen je Monat",
     "felder": "Titel, Firma, Status, Datum, Quelle, Vermittler"},
    {"key": "bewerbungs_verlauf", "name": "Verlauf der Bewerbungen",
     "tabellen": ["application_events"], "fliesst_ein": True, "stufe": "regeln",
     "wofuer": "Zeit bis zur ersten Rückmeldung, Interviews je Monat",
     "felder": "Status und Datum je Ereignis"},
    {"key": "aktivitaet", "name": "Nutzung des Dashboards",
     "tabellen": ["user_activity_events"], "fliesst_ein": True, "stufe": "lokale_ki",
     "wofuer": (f"Muster in der Bedienung (nur mit lokaler KI, letzte "
                f"{FENSTER_AKTIVITAET_TAGE} Tage)"),
     "felder": "Seite, Aktion, Zeitpunkt"},
    {"key": "dokumente", "name": "Dokumente, Mails und ihr Text",
     "tabellen": ["documents", "application_emails"], "fliesst_ein": False,
     "wofuer": "Lebenslauf, Anschreiben, Mails — nicht ausgewertet"},
    {"key": "profil", "name": "Profil (Stationen, Kompetenzen, Notizen)",
     "tabellen": ["profile", "positions", "skills"], "fliesst_ein": False,
     "wofuer": "Nicht ausgewertet"},
    {"key": "kontakte", "name": "Kontakte",
     "tabellen": ["contacts"], "fliesst_ein": False,
     "wofuer": "Nicht ausgewertet"},
    {"key": "termine", "name": "Termine und Reflexionen",
     "tabellen": ["application_meetings", "interview_reflections"],
     "fliesst_ein": False, "wofuer": "Nicht ausgewertet"},
]


def _zaehlen(conn, tabelle: str, pid: str, zeitspalte: str | None,
             bedingung: str = "") -> dict:
    spalten = {r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")}
    if not spalten:
        return {"anzahl": 0, "von": None, "bis": None}
    wo, args = [], []
    if "profile_id" in spalten:
        wo.append("(profile_id=? OR profile_id IS NULL OR profile_id='')")
        args.append(pid)
    elif tabelle == "application_events":
        wo.append("application_id IN (SELECT id FROM applications "
                  "WHERE profile_id=? OR profile_id IS NULL)")
        args.append(pid)
    if bedingung:
        wo.append(bedingung)
    sql_wo = (" WHERE " + " AND ".join(wo)) if wo else ""
    zeit = zeitspalte if zeitspalte in spalten else None
    auswahl = f"COUNT(*) AS n, MIN({zeit}) AS von, MAX({zeit}) AS bis" if zeit \
        else "COUNT(*) AS n, NULL AS von, NULL AS bis"
    r = conn.execute(f"SELECT {auswahl} FROM {tabelle}{sql_wo}", args).fetchone()
    return {"anzahl": r["n"] or 0, "von": (r["von"] or "")[:10] or None,
            "bis": (r["bis"] or "")[:10] or None}


#: Wie jede Quelle gezaehlt wird: (Zeitspalte, Zusatzbedingung).
_ZAEHLUNG = {
    "aussortierungen": ("dismissed_at",
                        "is_active=0 AND COALESCE(dismiss_reason,'') "
                        "NOT IN ('', 'bewerbung_erstellt')"),
    "bewerbungen": ("applied_at", ""),
    "bewerbungs_verlauf": ("event_date", ""),
    "aktivitaet": ("timestamp",
                   f"timestamp >= datetime('now', '-{FENSTER_AKTIVITAET_TAGE} days')"),
}


def uebersicht(db: Any) -> list[dict]:
    """Je Quelle: Name, Tabellen, fliesst ein ja/nein, Zahl, Zeitraum.

    Gezaehlt wird nur, was einfliesst — fuer die "nein"-Zeilen waere eine
    Zahl eine Einladung, sie doch fuer einen Teil des Lernens zu halten."""
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    out = []
    for q in QUELLEN:
        zeile = {k: q[k] for k in ("key", "name", "tabellen", "fliesst_ein",
                                   "wofuer") if k in q}
        zeile["stufe"] = q.get("stufe")
        zeile["felder"] = q.get("felder")
        if q["fliesst_ein"]:
            zeit, bed = _ZAEHLUNG[q["key"]]
            try:
                zeile.update(_zaehlen(conn, q["tabellen"][0], pid, zeit, bed))
            except Exception:  # eine fehlende Tabelle ist "0", kein Abbruch
                zeile.update({"anzahl": 0, "von": None, "bis": None})
        out.append(zeile)
    return out


def warum_leer(lauf: dict) -> list[str]:
    """Warum ein Lauf keine neue Erkenntnis erzeugt hat — je Grund ein Satz.

    `lauf` ist der Protokolleintrag (`lernprotokoll.eintragen`). Die
    Regeln nennen ihre Mindestdaten selbst (`lerninsights.MINDESTENS`);
    hier wird nur ausgewaehlt, was fuer diesen Lauf zutrifft."""
    from .lerninsights import MINDESTENS
    gruende = []
    if lauf.get("status") == "lernen_aus":
        return ["Das Lernen ist unter Datenschutz ausgeschaltet."]
    fehler = lauf.get("regel_fehler") or {}
    ohne = [r for r in (lauf.get("regeln_gelaufen") or [])
            if r not in set(lauf.get("regeln_mit_ergebnis") or [])]
    for regel in ohne:
        gruende.append(f"Regel „{MINDESTENS[regel][0]}“ fand nichts. "
                       f"Sie braucht {MINDESTENS[regel][1]}.")
    for regel in lauf.get("regeln_uebersprungen") or []:
        gruende.append(f"Regel „{MINDESTENS.get(regel, (regel,))[0]}“ lief "
                       "nicht mehr (Zeitbudget des Laufs erschöpft).")
    for regel, text in fehler.items():
        gruende.append(f"Regel „{MINDESTENS.get(regel, (regel,))[0]}“ ist "
                       f"fehlgeschlagen: {text}")
    ki = lauf.get("lokale_ki") or {}
    if ki.get("uebersprungen"):
        gruende.append(f"Muster-Analyse der lokalen KI: {ki.get('grund')}")
    if (lauf.get("kandidaten") or []) and not lauf.get("neu"):
        gruende.append("Alle gefundenen Aussagen waren schon bekannt oder "
                       "wurden von dir früher verworfen.")
    return gruende
