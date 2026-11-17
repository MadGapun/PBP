#!/usr/bin/env python
"""Messprobe fuer das Lernen der lokalen KI (#1396) - Trefferquote vorher/nachher.

Beantwortet: "Bewertet die lokale KI nach einem Lernlauf dieselben Stellen anders
(und besser)?" Das laesst sich nur mit der ECHTEN KI des Anwenders pruefen, deshalb
ist dies ein Messskript und kein Test.

SICHERHEIT (QA-Isolation):

* Standard ist ein TROCKENLAUF: die Datenbank wird auf eine KOPIE gebracht, die
  Marker werden dort gesetzt, der Bericht zeigt Bestand und Beispiel-Prompts.
  Es wird KEINE KI aufgerufen.
* Die Quelle (`--quelle`) wird nur gelesen (sqlite-Backup im Nur-Lese-Modus); alles
  Weitere geschieht in einem Arbeitsordner mit eigenem `BA_DATA_DIR`. Die echte
  `pbp.db` wird nie beschrieben.
* Die lokale KI (Ollama) wird NUR mit dem ausdruecklichen Schalter `--mit-ki`
  angesprochen, ueber den eingestellten Endpunkt (Vorgabe http://localhost:11434).

Ablauf mit `--mit-ki`, je `--anzahl` entschiedene Stellen (zur Haelfte "passt", zur
Haelfte "passt nicht", fester Zufall):

  A  alter Prompt:   die zehn letzten Ablehnungen als Beispiele (Stand 1.8.6)
  B  neuer Prompt:   Beispiele nach Aehnlichkeit, blind (die Stelle ist nie ihr Beispiel)
  L  Lernlauf:       jede Stelle blind bewerten, Gegenprobe speichern (Gegenbeispiele)
  C  neuer Prompt:   dieselben Stellen noch einmal, jetzt mit den Gegenbeispielen

Bericht: Trefferquote A, B, C, wie viele Stellen zwischen B und C anders bewertet
wurden und in welche Richtung. Aufruf:

    python scripts/ki_lernprobe.py --quelle "<Pfad zur pbp.db>"            # Trockenlauf
    python scripts/ki_lernprobe.py --quelle "<Pfad zur pbp.db>" --mit-ki   # echte Messung
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def kopieren(quelle: Path, ziel: Path) -> None:
    """Die Datenbank auf eine Kopie bringen (Nur-Lese-Zugriff auf die Quelle, WAL-fest)."""
    if not quelle.is_file():
        raise SystemExit(f"Quelle nicht gefunden: {quelle}")
    src = sqlite3.connect(f"file:{quelle.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(ziel))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _stichprobe(db, anzahl: int, zufall: random.Random) -> list:
    from bewerbungs_assistent.services import ki_nachlernen
    from bewerbungs_assistent.services.ki_lernen import entscheidungsklasse
    zeilen = ki_nachlernen._kandidaten_zeilen(db, 5000)  # noqa: SLF001 - Messskript
    ja = [dict(z) for z in zeilen if entscheidungsklasse(z) in ("passt", "bedingt")]
    nein = [dict(z) for z in zeilen if entscheidungsklasse(z) == "passt_nicht"]
    zufall.shuffle(ja)
    zufall.shuffle(nein)
    halb = max(1, anzahl // 2)
    return ja[:halb] + nein[:anzahl - min(halb, len(ja))]


def _payload(db, kontext, top, job, beispiele=None, alt=None) -> dict:
    p = {**kontext, "job_title": job.get("title") or "", "job_company": job.get("company") or "",
         "job_description": (job.get("description") or "")[:1500], "dismiss_reasons_top": top}
    if alt is not None:
        p["recent_dismissals"] = alt
    else:
        p["lern_beispiele"] = beispiele or []
    return p


def _frage(svc, payload) -> str:
    from bewerbungs_assistent.services.llm_service import TaskKind
    res = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, payload)
    return (res.payload or {}).get("decision", "FEHLER") if res.success else "FEHLER"


def _richtig(urteil: str, klasse: str):
    from bewerbungs_assistent.services.ki_lernen import vergleich
    return vergleich(urteil, klasse)


def _quote(werte: list):
    gueltig = [w for w in werte if w is not None]
    return round(100 * sum(gueltig) / len(gueltig), 1) if gueltig else None


def lauf(db, svc, anzahl: int = 40, seed: int = 1396) -> dict:
    """Die Messung. `svc` ist die lokale KI (oder ein Testdoppel)."""
    from bewerbungs_assistent.services import (
        auto_aussortierung as aa, ki_beispiele, ki_lernen, ki_nachlernen)
    zufall = random.Random(seed)
    stellen = _stichprobe(db, anzahl, zufall)
    kontext = aa.profil_kontext(db.get_profile() or {})
    top = aa.gruende_top(db)
    alt_liste = db.get_recent_user_dismissals(limit=10)
    klassen = {s["hash"]: ki_lernen.entscheidungsklasse(s) for s in stellen}
    ergebnis = {"stellen": len(stellen), "A": {}, "B": {}, "C": {}}

    def _messen(name, beispiel_fuer):
        urteile = {}
        for s in stellen:
            urteile[s["hash"]] = _frage(svc, beispiel_fuer(s))
        ergebnis[name] = {"quote_prozent": _quote([_richtig(u, klassen[h]) for h, u in urteile.items()]),
                          "fehler": sum(1 for u in urteile.values() if u == "FEHLER")}
        return urteile

    a = _messen("A", lambda s: _payload(db, kontext, top, s, alt=alt_liste))
    pool = ki_beispiele.pool_laden(db)
    b = _messen("B", lambda s: _payload(db, kontext, top, s,
                                        ki_beispiele.beispiele_fuer(db, s, pool=pool)))
    # Lernlauf: Gegenprobe speichern, Abweichungen werden Gegenbeispiele.
    conn = db.connect()
    for s in stellen:
        ki_lernen.ollama_gesehen(conn, s["hash"], b[s["hash"]], "", "klar")
        ki_lernen.nach_entscheidung(conn, s["hash"])
    pool = ki_beispiele.pool_laden(db)
    c = _messen("C", lambda s: _payload(db, kontext, top, s,
                                        ki_beispiele.beispiele_fuer(db, s, pool=pool)))
    gedreht = {"besser": 0, "schlechter": 0, "gleich": 0}
    for s in stellen:
        vorher, nachher = _richtig(b[s["hash"]], klassen[s["hash"]]), _richtig(c[s["hash"]], klassen[s["hash"]])
        if vorher is None or nachher is None or vorher == nachher:
            gedreht["gleich"] += 1
        elif nachher > vorher:
            gedreht["besser"] += 1
        else:
            gedreht["schlechter"] += 1
    ergebnis["B_nach_C"] = gedreht
    ergebnis["anders_bewertet"] = sum(1 for s in stellen if b[s["hash"]] != c[s["hash"]])
    ergebnis["gegenbeispiele"] = sum(1 for p in pool if p["gegenbeispiel"])
    return ergebnis


def trockenlauf(db, anzahl: int, seed: int = 1396) -> dict:
    """Ohne KI: Bestand, Marker und ein Beispiel-Prompt je Seite."""
    from bewerbungs_assistent.services import ki_beispiele
    from bewerbungs_assistent.services.llm_service import _build_match_job_to_skills_prompt
    conn = db.connect()
    marker = {str(r[0]): r[1] for r in conn.execute(
        "SELECT COALESCE(entschieden_von,'(keine Entscheidung)'), COUNT(*) FROM jobs GROUP BY 1")}
    stellen = _stichprobe(db, anzahl, random.Random(seed))
    pool = ki_beispiele.pool_laden(db)
    proben = []
    for s in stellen[:3]:
        bsp = ki_beispiele.beispiele_fuer(db, s, pool=pool)
        proben.append({"titel": s["title"], "beispiele": len(bsp), "prompt": _build_match_job_to_skills_prompt(
            {"job_title": s["title"], "lern_beispiele": bsp})[:1500]})
    return {"marker": marker, "pool": len(pool), "stichprobe": len(stellen), "proben": proben}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--quelle", required=True, help="Pfad zur pbp.db (wird nur gelesen und kopiert)")
    ap.add_argument("--anzahl", type=int, default=40)
    ap.add_argument("--mit-ki", action="store_true", help="die lokale KI wirklich ansprechen (sonst Trockenlauf)")
    ap.add_argument("--arbeitsordner", help="Ordner fuer die Kopie (Vorgabe: ein neuer Temp-Ordner)")
    ap.add_argument("--bericht", help="Bericht als JSON speichern")
    a = ap.parse_args(argv)

    arbeit = Path(a.arbeitsordner or tempfile.mkdtemp(prefix="pbp_lernprobe_"))
    arbeit.mkdir(parents=True, exist_ok=True)
    quelle = Path(a.quelle).resolve()
    ziel = arbeit / "pbp.db"
    if ziel.resolve() == quelle:
        raise SystemExit("Die Kopie darf nicht die Quelle sein.")
    # QA-Isolation: der Datenordner VOR dem ersten Import setzen.
    os.environ["BA_DATA_DIR"] = str(arbeit)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    kopieren(quelle, ziel)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=ziel)
    db.initialize()
    assert str(arbeit) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    bericht = {"zeit": datetime.now().isoformat(timespec="seconds"), "arbeitsordner": str(arbeit),
               "modus": "mit_ki" if a.mit_ki else "trockenlauf"}
    if not a.mit_ki:
        bericht["trockenlauf"] = trockenlauf(db, a.anzahl)
        bericht["hinweis"] = "Trockenlauf: keine KI aufgerufen. Mit --mit-ki wird die echte Messung gestartet."
    else:
        from bewerbungs_assistent.services.llm_service import LLMService
        db.set_profile_setting("llm_local_state", "active")  # nur in der KOPIE
        svc = LLMService(db)
        st = svc.get_status(force_refresh=True)
        if not st.ollama_available or not st.available_models:
            raise SystemExit("Die lokale KI ist nicht erreichbar (Ollama laeuft nicht oder kein Modell).")
        bericht["endpunkt"] = st.ollama_endpoint
        bericht["modell"] = st.selected_model or st.available_models[0]
        bericht["messung"] = lauf(db, svc, a.anzahl)
    text = json.dumps(bericht, ensure_ascii=False, indent=2)
    print(text)
    if a.bericht:
        Path(a.bericht).write_text(text, encoding="utf-8")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
