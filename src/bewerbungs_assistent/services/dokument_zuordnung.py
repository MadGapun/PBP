"""Lose und falsch verknuepfte Dokumente auffindbar machen (#797/E20, v1.7.12).

Belegter Fall 25.07.: 48 von 223 Dokumenten ohne Verknuepfung — neun
davon gehoerten nachweislich zu einer vorhandenen Bewerbung, und die
Antwort war nur per Direkt-SQL zu bekommen (genau der #514-Verstoss).
Dazu drei FALSCH verknuepfte Dokumente: eine falsche Zuordnung ist
unsichtbarer als eine fehlende — sie wird nie gesucht, weil sie
scheinbar richtig liegt.

Grundsaetze: KEIN auto_fix (Zuordnung ist eine inhaltliche
Entscheidung); jeder Treffer traegt seine Begruendung; Vorschlaege
kommen mit Konfidenz-Einordnung, der Mensch bestaetigt.
"""
from __future__ import annotations

import re
from typing import Any

from .wiedergaenger import normalize_company

# Dokumenttypen, die fast immer zu einem konkreten Vorgang gehoeren —
# lose sind sie verdaechtig, nicht nur unvollstaendig.
_VORGANGS_TYPEN = ("bewerbungsantwort", "angebot", "absage",
                   "recruiter_anfrage", "interview_transkript",
                   "einladung", "korrespondenz")


def _betreff_stamm(filename: str) -> str:
    """Betreff-/Dateinamen-Stamm: Re:/AW:/Fwd:-Praefixe und Endung weg."""
    s = (filename or "").rsplit(".", 1)[0]
    s = re.sub(r"^(re|aw|fwd|wg)[_\-: ]+", "", s.strip(), flags=re.I)
    while True:
        neu = re.sub(r"^(re|aw|fwd|wg)[_\-: ]+", "", s, flags=re.I)
        if neu == s:
            break
        s = neu
    return s.strip().lower()


def finde_lose_dokumente(db, nur_verdaechtige: bool = True) -> dict[str, Any]:
    """Unverknuepfte Dokumente, sortiert nach Verdachtsstaerke."""
    conn = db.connect()
    pid = db.get_active_profile_id()
    docs = [dict(r) for r in conn.execute(
        "SELECT id, filename, doc_type, linked_application_id, lifecycle "
        "FROM documents WHERE (profile_id=? OR profile_id IS NULL) "
        "AND COALESCE(lifecycle, 'aktiv') = 'aktiv'",
        (pid,)).fetchall()]
    apps = db.get_applications()
    firmen = {}
    for a in apps:
        norm = normalize_company(a.get("company"))
        if norm and len(norm) >= 4:
            firmen.setdefault(norm, a)

    # Thread-Signal vorbereiten: Stamm -> verknuepfte Bewerbung(en)
    stamm_zu_app: dict[str, set] = {}
    for d in docs:
        if d.get("linked_application_id"):
            stamm = _betreff_stamm(d.get("filename") or "")
            if len(stamm) >= 8:
                stamm_zu_app.setdefault(stamm, set()).add(
                    d["linked_application_id"])

    lose = [d for d in docs if not d.get("linked_application_id")]
    treffer = []
    for d in lose:
        gruende = []
        vorschlag = None
        # Separatoren normalisieren: "Firma_Nord_Antwort.pdf" muss den
        # Bewerbungs-Eintrag "Firma Nord" treffen.
        fname_lc = re.sub(r"[_\-.]+", " ", (d.get("filename") or "").lower())

        if (d.get("doc_type") or "") in _VORGANGS_TYPEN:
            gruende.append(
                f"Typ '{d['doc_type']}' gehoert fast immer zu einem "
                "konkreten Vorgang")

        norm_treffer = next((n for n in firmen if n in fname_lc), None)
        if norm_treffer:
            app = firmen[norm_treffer]
            gruende.append(
                f"Dateiname enthaelt die Firma einer vorhandenen Bewerbung")
            vorschlag = {"bewerbung_id": app.get("id"),
                         "firma": app.get("company"),
                         "stelle": app.get("title"),
                         "konfidenz": "mittel",
                         "beleg": "Firmenname im Dateinamen"}

        # Staerkstes Signal (#797): das Geschwister-Dokument desselben
        # Threads haengt bereits an einer Bewerbung.
        stamm = _betreff_stamm(d.get("filename") or "")
        if len(stamm) >= 8 and stamm in stamm_zu_app:
            ziele = stamm_zu_app[stamm]
            if len(ziele) == 1:
                ziel = next(iter(ziele))
                app = next((a for a in apps if a.get("id") == ziel), {})
                gruende.append(
                    "Ein Dokument mit demselben Betreff-Stamm haengt "
                    "bereits an einer Bewerbung (Thread-Signal)")
                vorschlag = {"bewerbung_id": ziel,
                             "firma": app.get("company"),
                             "stelle": app.get("title"),
                             "konfidenz": "hoch",
                             "beleg": f"Thread-Geschwister: '{stamm[:50]}'"}

        if gruende or not nur_verdaechtige:
            treffer.append({
                "dokument_id": d["id"],
                "dateiname": d.get("filename"),
                "typ": d.get("doc_type"),
                "verdacht": gruende or ["ohne Verdachtsmoment (nur bei "
                                        "nur_verdaechtige=False gelistet)"],
                "zuordnungs_vorschlag": vorschlag,
            })

    # Nach Signalstaerke: Vorschlag mit hoher Konfidenz zuerst
    def _rang(t):
        k = (t.get("zuordnungs_vorschlag") or {}).get("konfidenz")
        return {"hoch": 0, "mittel": 1}.get(k, 2)
    treffer.sort(key=_rang)

    return {
        "dokumente_gesamt": len(docs),
        "ohne_verknuepfung": len(lose),
        "verdaechtige": len([t for t in treffer
                             if t["verdacht"] and "ohne Verdachtsmoment"
                             not in t["verdacht"][0]]),
        "treffer": treffer,
    }


def pruefe_verknuepfungs_integritaet(db) -> list[dict]:
    """#797/4 + #796-Anschluss: Verknuepfungen auf Nicht-Existentes."""
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT d.id, d.filename, d.linked_application_id "
        "FROM documents d LEFT JOIN applications a "
        "ON a.id = d.linked_application_id "
        "WHERE d.linked_application_id IS NOT NULL AND a.id IS NULL "
        "AND (d.profile_id=? OR d.profile_id IS NULL)",
        (pid,)).fetchall()
    return [{"dokument_id": r["id"], "dateiname": r["filename"],
             "zeigt_auf": r["linked_application_id"],
             "befund": "Verknuepfung zeigt auf keine existierende Bewerbung"}
            for r in rows]
