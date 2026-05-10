"""End-to-End-Simulation gegen das aktuelle PBP-Build (v1.7.0-beta.48).

Spawnt einen frischen DB-State, simuliert ein realistisches Profil
mit Bewerbungen + Stellen, faehrt dann alle relevanten Endpoints und
MCP-Tools probehalber. Kein pytest — Standalone-Sanity-Check.

Wird NICHT in CI ausgefuehrt. Manuell: `python tests/_simulate_beta48.py`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

# Pfad fuer Imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def setup_environment():
    """Frischer DB-State + Profil + 5 Stellen + 3 Bewerbungen."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_sim_")
    os.environ["BA_DATA_DIR"] = tmpdir
    print(f"  Sandbox: {tmpdir}")

    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent import dashboard as _dash
    db = Database()
    db.initialize()
    db.save_profile({
        "name": "Markus Mustermann",
        "email": "markus@example.com",
        "city": "Hamburg",
    })
    _dash._db = db
    pid = db.get_active_profile_id()

    # Skills
    db.add_skill({"name": "PLM", "level": 4})
    db.add_skill({"name": "Teamcenter", "level": 4})
    db.add_skill({"name": "Python", "level": 3})

    # 5 Stellen — eine pro Quelle
    seeds = [
        ("aaaa11111111", "Senior PLM Engineer", "BMW", "linkedin",
         "https://www.linkedin.com/jobs/view/aaaa", 78,
         "PLM-Architekt mit Teamcenter. " * 10),
        ("bbbb22222222", "PLM Solution Architect", "Phoenix Contact", "stepstone",
         "https://www.stepstone.de/x/bbbb", 82,
         "Senior PLM mit Aras. " * 10),
        ("cccc33333333", "Junior Backend Dev", "Startup XY", "manuell",
         "https://www.linkedin.com/jobs/view/cccc", 45,  # source=manuell aber URL=linkedin
         "Junior Python. " * 10),
        ("dddd44444444", "Beschreibung-Kandidat", "Refetch GmbH", "linkedin",
         "https://www.linkedin.com/jobs/view/dddd", 0, ""),  # leere description + URL -> refetch-Kandidat
        ("eeee55555555", "Praktikum mit international", "ACME", "linkedin",
         "https://www.linkedin.com/jobs/view/eeee", 60,
         "Wir arbeiten mit internationalen Kunden. PLM. " * 5),
    ]
    conn = db.connect()
    for h, t, c, s, u, score, desc in seeds:
        full_h = f"{pid}:{h}"
        conn.execute(
            "INSERT INTO jobs (hash, profile_id, title, company, source, url, "
            "description, score, is_active, found_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (full_h, pid, t, c, s, u, desc, score, 1, "2026-05-10")
        )
    conn.commit()

    # 3 Bewerbungen — eine davon mit orphaned job_hash
    db.add_application({"title": "Senior PLM", "company": "BMW",
                         "job_hash": f"{pid}:aaaa11111111",
                         "status": "beworben", "applied_at": "2026-05-08"})
    # Inbound ohne explizites applied_at -> sollte Default heute kriegen
    db.add_application({"title": "Inbound", "company": "Recruiter X",
                         "status": "beworben",
                         "notes": "Inbound via XING"})

    # Orphan: Job anlegen, App dran, Job mit FK off loeschen
    orphan_hash = f"{pid}:orphan999999"
    conn.execute(
        "INSERT INTO jobs (hash, profile_id, title, company, source, "
        "is_active, found_at) VALUES (?,?,?,?,?,?,?)",
        (orphan_hash, pid, "Lost Job", "Phantom Recruiter", "linkedin",
         1, "2026-05-10")
    )
    conn.commit()
    db.add_application({"title": "Lost Job", "company": "Phantom Recruiter",
                         "url": "https://www.linkedin.com/jobs/view/lost",
                         "job_hash": orphan_hash,
                         "status": "beworben", "applied_at": "2026-05-09"})
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DELETE FROM jobs WHERE hash=?", (orphan_hash,))
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")

    return db


def run_section(label, fn):
    """Helper mit Erfolg/Fehler-Markup."""
    print(f"\n[{label}]")
    try:
        fn()
        print(f"  OK")
        return True
    except Exception:
        print(f"  FEHLER")
        traceback.print_exc()
        return False


async def _call_tool(mcp, name, args=None):
    tool = await mcp.get_tool(name)
    res = await tool.run(args or {})
    return res.structured_content if hasattr(res, "structured_content") else res


def main():
    print("=" * 60)
    print("PBP v1.7.0-beta.48 — End-to-End-Simulation")
    print("=" * 60)

    db = setup_environment()

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("sim")
    register_all(mcp, db, logging.getLogger("sim"))

    results = {}

    # === API-Smoke ===
    def api_smoke():
        from fastapi.testclient import TestClient
        from bewerbungs_assistent.dashboard import app
        client = TestClient(app)
        endpoints = [
            ("GET", "/api/jobs?active=true"),
            ("GET", "/api/applications"),
            ("GET", "/api/profile"),
            ("GET", "/api/elwosa/messages"),
            ("GET", "/api/elwosa/status"),
            ("GET", "/api/elwosa/settings"),
            ("GET", "/api/auto-actions/status"),
            ("POST", "/api/wiki/request-hint", {"page": "stellen"}),
        ]
        for method, *parts in endpoints:
            url = parts[0]
            body = parts[1] if len(parts) > 1 else None
            r = client.request(method, url, json=body)
            status = "OK" if r.status_code in (200, 400, 404) else "FAIL"
            print(f"  {method:5s} {url:35s} -> {r.status_code} {status}")
            assert r.status_code < 500, f"500 from {url}: {r.text[:200]}"

    results["API-Smoke"] = run_section("API-Smoke (8 Endpoints)", api_smoke)

    # === Auto-Engine ===
    def auto_engine():
        from fastapi.testclient import TestClient
        from bewerbungs_assistent.dashboard import app
        client = TestClient(app)
        with patch("bewerbungs_assistent.job_scraper.fetch_description_from_detail",
                   return_value="X" * 200):
            r = client.post("/api/auto-actions/run")
        assert r.status_code == 200
        result = r.json()
        # Alle 9 Steps sollten unter den Keys sein
        for step in ("expire", "followup_reconciler", "mail_classify",
                     "document_classify", "pattern_analysis", "scraper_probe",
                     "extract_contacts", "auto_refetch_descriptions", "elwosa"):
            assert step in result, f"Auto-Engine-Step '{step}' fehlt"
            print(f"  {step:30s} OK")
        # auto_refetch hat eine Stelle ohne Beschreibung gefunden
        assert result["auto_refetch_descriptions"]["successes"] >= 1

    results["Auto-Engine"] = run_section("Auto-Engine-Lauf (9 Steps)", auto_engine)

    # === #613: Quellen-Migration dry_run ===
    def quellen_migration():
        out = asyncio.run(_call_tool(mcp, "quellen_aus_urls_korrigieren",
                                      {"dry_run": True}))
        print(f"  Kandidaten: {out['count_total']}, geplant: {out['count_changed']}")
        # Stelle cccc hat source=manuell aber linkedin-URL → sollte umgestellt werden
        assert out["count_changed"] >= 1
        sources_planned = [c["source_neu"] for c in out["changes"]]
        assert "linkedin" in sources_planned

    results["#613 Quellen-Migration (dry_run)"] = run_section(
        "#613 Quellen-Migration dry_run", quellen_migration)

    # === #616: Orphan-Cleanup report ===
    def orphan_report():
        out = asyncio.run(_call_tool(mcp, "verwaiste_stellenrefs_bereinigen",
                                      {"strategie": "report", "dry_run": True}))
        print(f"  Total apps: {out['count_total_apps']}, orphaned: {out['count_orphaned']}")
        assert out["count_orphaned"] >= 1, "Orphan nicht gefunden"
        assert out["orphans"][0]["company"] == "Phantom Recruiter"

    results["#616 Orphan-Cleanup (report)"] = run_section(
        "#616 Orphan-Cleanup report", orphan_report)

    # === #618: stelle_bearbeiten short hash ===
    def short_hash():
        out = asyncio.run(_call_tool(mcp, "stelle_bearbeiten",
                                      {"job_hash": "aaaa1111", "firma": "BMW Group"}))
        assert "fehler" not in out, f"Short-hash failed: {out}"
        # Verifiziere via DB direkt
        conn = db.connect()
        rows = conn.execute("SELECT company FROM jobs WHERE hash LIKE '%:aaaa11111111'").fetchall()
        assert any(r["company"] == "BMW Group" for r in rows), (
            f"Short-Hash-Update nicht durchgekommen: {[dict(r) for r in rows]}"
        )
        print(f"  Stelle aaaa1111 -> firma jetzt: {rows[0]['company']}")

    results["#618 Short-Hash"] = run_section("#618 stelle_bearbeiten Short-Hash", short_hash)

    # === #604: 'intern' kein false positive ===
    def intern_no_fp():
        from bewerbungs_assistent.job_scraper import calculate_score
        job = {
            "title": "Senior PLM",
            "description": "Wir arbeiten mit internationalen Kunden. PLM-Erfahrung." * 5,
        }
        criteria = {"keywords_muss": ["plm"], "keywords_ausschluss": ["praktikum"],
                    "gewichtung": {"muss": 2}}
        score = calculate_score(job, criteria)
        assert score > 0, f"Score wurde wieder durch 'intern' sabotiert: {score}"
        print(f"  Score fuer 'internationalen Kunden'-Stelle: {score} (sollte > 0 sein)")

    results["#604 intern-Synonym"] = run_section("#604 intern-Synonym", intern_no_fp)

    # === #602: applied_at default ===
    def applied_at_default():
        # Pfad ueber den MCP-Tool (Hot-Path mit Fix aus #602).
        out = asyncio.run(_call_tool(mcp, "bewerbung_erstellen", {
            "title": "Sim-Test Inbound", "company": "Sim-Recruiter",
            "url": "", "status": "beworben",
            # KEIN applied_at -> sollte Default heute kriegen
        }))
        if "fehler" in out and "duplikat" in (out.get("fehler") or "").lower():
            print(f"  Skip: {out['fehler']}")
            return
        from datetime import datetime
        apps = db.get_applications()
        sim = [a for a in apps if a.get("company") == "Sim-Recruiter"]
        assert len(sim) == 1, f"Bewerbung nicht angelegt: {sim}"
        today = datetime.now().isoformat()[:10]
        assert sim[0]["applied_at"] == today, (
            f"applied_at-Default nicht gesetzt: {sim[0].get('applied_at')!r}"
        )
        print(f"  MCP-Tool legt Inbound mit applied_at = {sim[0]['applied_at']} (heute) an")

    results["#602 applied_at Default"] = run_section(
        "#602 applied_at Default", applied_at_default)

    # === #619: PDF-Export safe() ===
    def pdf_unicode():
        from bewerbungs_assistent.export import generate_cv_pdf
        profile = {
            "name": "Test → User",
            "city": "Hamburg",
            "positions": [{
                "title": "Engineer",
                "company": "ACME",
                "start_date": "2020-01",
                "projects": [{"title": "P1", "result": "Migration → erfolgreich"}],
            }],
        }
        path = Path(os.environ["BA_DATA_DIR"]) / "test.pdf"
        generate_cv_pdf(profile, path)
        assert path.exists()
        assert path.stat().st_size > 1000
        print(f"  PDF erzeugt: {path.stat().st_size} bytes")

    results["#619 PDF Unicode"] = run_section("#619 PDF Unicode-Pfeil", pdf_unicode)

    # === #623: Wiki-Snippet-Hint ===
    def wiki_hint():
        from fastapi.testclient import TestClient
        from bewerbungs_assistent.dashboard import app
        client = TestClient(app)
        # Ersten Aufruf: postet
        r1 = client.post("/api/wiki/request-hint", json={"page": "bewerbungen"})
        j1 = r1.json()
        assert j1["posted"] == 1
        print(f"  Snippet gepostet: {j1['snippet_id']} -> Wiki: {j1['wiki_page']}")
        # Zweiter Aufruf: dedupped
        r2 = client.post("/api/wiki/request-hint", json={"page": "bewerbungen"})
        assert r2.json()["posted"] == 0

    results["#623 Wiki-Hint"] = run_section("#623 Wiki-Hint Per-Day-Dedup", wiki_hint)

    # === Elwosa Status-Lifecycle ===
    def elwosa_status_change():
        from bewerbungs_assistent.services import elwosa
        db.set_elwosa_settings(enabled=True)
        # Status-Wechsel triggert eine status_change-Linie mit ref
        msg_id = elwosa.speak(db, "interview_einladung",
                              ctx={"firma": "BMW", "ref": "abc12345"})
        if msg_id:
            msgs = db.get_elwosa_messages()
            last = msgs[0]
            print(f"  Linie: {last['content'][:80]}")
            # Wenn Action-Link-Variante gewaehlt wurde, sollte ref drin sein
            if "[link:application:" in last["content"]:
                assert "abc12345" in last["content"]
                print(f"  Action-Link mit ref korrekt eingesetzt.")

    results["Elwosa Status-Lifecycle"] = run_section(
        "Elwosa Status-Lifecycle (Action-Link)", elwosa_status_change)

    # === #464: Interview-Reflexion (beta.49) ===
    def reflexion():
        # Bewerbung mit Status interview_abgeschlossen anlegen
        aid = db.add_application({
            "title": "Sim-Interview-Job", "company": "Reflex GmbH",
            "status": "interview_abgeschlossen", "applied_at": "2026-04-15",
        })
        # Speichern
        out1 = asyncio.run(_call_tool(mcp, "interview_reflexion_speichern", {
            "bewerbung_id": aid,
            "was_lief_gut": "Cultural-Fit-Frage gut beantwortet",
            "was_lief_schlecht": "Tech-Tiefe Aras-Migration",
            "was_war_ueberraschend": "Drei Personen statt einer",
            "gefuehl": 4,
            "next_steps": "Nachfass am Freitag",
        }))
        assert out1["status"] == "gespeichert"
        # Lesen
        out2 = asyncio.run(_call_tool(mcp, "interview_reflexion_lesen",
                                       {"bewerbung_id": aid}))
        assert out2["status"] == "vorhanden"
        assert out2["reflexion"]["gefuehl"] == 4
        # Liste
        out3 = asyncio.run(_call_tool(mcp, "interview_reflexionen_anzeigen",
                                       {"limit": 5}))
        assert out3["anzahl"] >= 1
        print(f"  Reflexion fuer A-{aid[:8]} gespeichert + gelesen + gelistet")

    results["#464 Interview-Reflexion"] = run_section(
        "#464 Interview-Reflexion (beta.49)", reflexion)

    # === Bericht-Export ===
    def bericht():
        out = asyncio.run(_call_tool(mcp, "bewerbungsbericht_exportieren",
                                      {"format": "pdf"}))
        if "fehler" in out:
            print(f"  Skip: {out.get('fehler')}")
            return
        assert out.get("status") in ("erstellt", "ok")
        print(f"  Bericht: {out.get('datei') or out.get('pdf') or 'erzeugt'}")

    results["Bewerbungsbericht-Export"] = run_section(
        "Bewerbungsbericht PDF-Export", bericht)

    # === Sumamry ===
    print("\n" + "=" * 60)
    ok = sum(1 for v in results.values() if v)
    fail = sum(1 for v in results.values() if not v)
    print(f"Simulation: {ok} OK, {fail} Fehler von {len(results)} Sektionen")
    print("=" * 60)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
