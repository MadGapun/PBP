"""PBP Smoke-Test (#498) — prueft die kritischen Flows in <1 Minute.

Ziel: Vor jedem Commit/Release laufen lassen. Wenn etwas rot ist, entweder
fixen oder revertieren — kein Release auf rotem Smoke.

Was wird geprueft (Kernflows):
  1. Paket-Imports (Database, Dashboard, Server, Feature-Flags)
  2. Datenbank: init + Profil CRUD
  3. Bewerbung CRUD (add → update_status → events lesen → delete)
  4. Dokument CRUD (add → fetch → delete)
  5. Jobs/Stellen: save_jobs → get_active_jobs
  6. Termin: add_meeting → get_upcoming_meetings
  7. Dashboard-Counts (count_applications, get_pending_follow_ups)

Hardening:
  - Laeuft gegen ein *temporaeres* Datenverzeichnis, beruehrt keine
    Nutzerdaten.
  - Deterministische Reihenfolge, keine Netzwerk-Calls (Scraper sind
    bewusst nicht Teil des Smoke — siehe #488/#499 fuer Scraper-Health).
  - Exit-Code 0 = gruen, 1 = mindestens ein Check rot.

Aufruf:
  python scripts/smoke_test.py
  python scripts/smoke_test.py --verbose
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

# Projekt-Root und src/ auf den Pfad, damit das Skript unabhaengig vom
# Aufruf-Verzeichnis laeuft.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


# Temporaeres Datenverzeichnis — vor jedem Import setzen, damit die
# Module beim Laden die Test-Umgebung sehen.
_tmpdir = tempfile.mkdtemp(prefix="pbp_smoke_")
os.environ["BA_DATA_DIR"] = _tmpdir


class Smoke:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, fn) -> None:
        try:
            fn()
            self.passed.append(name)
            print(f"[ OK ] {name}")
        except Exception as exc:
            self.failed.append((name, str(exc)))
            print(f"[FAIL] {name}: {exc}")
            if self.verbose:
                traceback.print_exc()

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print()
        print(f"Smoke-Test: {len(self.passed)}/{total} gruen")
        if self.failed:
            print("Fehlgeschlagen:")
            for name, err in self.failed:
                print(f"  - {name}: {err}")
            return 1
        return 0


def run(verbose: bool = False) -> int:
    smoke = Smoke(verbose=verbose)

    # 1. Imports
    def _imports():
        from bewerbungs_assistent import __version__  # noqa: F401
        from bewerbungs_assistent.database import Database  # noqa: F401
        from bewerbungs_assistent.dashboard import start_dashboard  # noqa: F401
        from bewerbungs_assistent.server import mcp  # noqa: F401
        from bewerbungs_assistent.feature_flags import is_enabled, enabled_flags  # noqa: F401
        from bewerbungs_assistent.job_scraper.adapters import (  # noqa: F401
            AdapterResult, AdapterStatus, JobPosting, JobSourceAdapter,
            available_adapters, get_adapter, run_adapters,
        )

    smoke.check("Paket-Imports (version, Database, Dashboard, MCP, feature_flags, adapters)", _imports)

    # 2. Datenbank init + Profil
    from bewerbungs_assistent.database import Database

    db = Database()

    def _init():
        db.initialize()

    smoke.check("Datenbank: initialize()", _init)

    def _profile():
        pid = db.save_profile({"name": "Smoke Tester", "email": "smoke@test.local"})
        assert pid, "save_profile lieferte keine ID"
        p = db.get_profile()
        assert p and p["name"] == "Smoke Tester", "get_profile liefert falsche Daten"

    smoke.check("Profil: save + read", _profile)

    # 3. Bewerbung CRUD
    state = {}

    def _app_create():
        aid = db.add_application({
            "title": "Smoke PLM Manager",
            "company": "SmokeCo",
            "url": "https://example.local/job/1",
            "status": "beworben",
        })
        assert aid, "add_application lieferte keine ID"
        state["app_id"] = aid

    smoke.check("Bewerbung: add_application", _app_create)

    def _app_update():
        ok = db.update_application_status(state["app_id"], "interview", notes="Smoke")
        assert ok, "update_application_status = False"
        apps = db.get_applications(status="interview")
        assert any(a["id"] == state["app_id"] for a in apps), \
            "Bewerbung nicht unter 'interview' gefunden"

    smoke.check("Bewerbung: update_application_status + get_applications(filter)", _app_update)

    def _app_events():
        # Initial-Event (beworben) + Status-Wechsel-Event (interview) = mindestens 2
        conn = db.connect()
        rows = conn.execute(
            "SELECT COUNT(*) FROM application_events WHERE application_id=?",
            (state["app_id"],),
        ).fetchone()
        assert rows[0] >= 2, f"erwartet >=2 Events, bekommen {rows[0]}"

    smoke.check("Bewerbung: application_events geschrieben", _app_events)

    # 4. Dokument CRUD
    def _doc_create():
        did = db.add_document({
            "filename": "smoke_cv.pdf",
            "filepath": "/tmp/smoke_cv.pdf",
            "doc_type": "lebenslauf",
            "extracted_text": "Smoke Text",
        })
        assert did, "add_document lieferte keine ID"
        state["doc_id"] = did

    smoke.check("Dokument: add_document", _doc_create)

    def _doc_read():
        d = db.get_document(state["doc_id"])
        assert d and d["filename"] == "smoke_cv.pdf", "get_document falsch"

    smoke.check("Dokument: get_document", _doc_read)

    # 5. Jobs/Stellen
    def _jobs():
        # save_jobs erwartet Liste von Dicts
        db.save_jobs([
            {
                "hash": "smoke_hash_1",
                "title": "Smoke PLM Spezialist",
                "company": "SmokeCo",
                "location": "Hamburg",
                "url": "https://example.local/job/smoke1",
                "source": "smoke",
                "description": "Smoke-Test Job",
            }
        ])
        active = db.get_active_jobs()
        # save_jobs scoped den Hash pro Profil — Endung pruefen reicht.
        assert any(str(j.get("hash", "")).endswith("smoke_hash_1") for j in active), \
            "save_jobs -> get_active_jobs nicht sichtbar"

    smoke.check("Jobs: save_jobs + get_active_jobs", _jobs)

    # 6. Termine
    def _meeting():
        mid = db.add_meeting({
            "application_id": state["app_id"],
            "title": "Smoke Interview",
            "meeting_date": "2099-01-01 10:00:00",
            "meeting_end": "2099-01-01 11:00:00",
            "meeting_type": "interview",
        })
        assert mid, "add_meeting lieferte keine ID"
        upcoming = db.get_upcoming_meetings(days=365 * 100)
        assert any(m["id"] == mid for m in upcoming), \
            "Termin nicht in get_upcoming_meetings"

    smoke.check("Termin: add_meeting + get_upcoming_meetings", _meeting)

    # 7. Dashboard-Counts
    def _counts():
        total = db.count_applications()
        assert total >= 1, f"count_applications = {total}, erwartet >=1"
        pending = db.get_pending_follow_ups()
        assert isinstance(pending, list), "get_pending_follow_ups: erwartet Liste"

    smoke.check("Dashboard: count_applications + get_pending_follow_ups", _counts)

    # Cleanup (Teil der Tests — delete muss funktionieren)
    def _cleanup():
        db.delete_application(state["app_id"])
        apps_after = db.get_applications()
        assert not any(a["id"] == state["app_id"] for a in apps_after), \
            "Bewerbung nach delete_application immer noch sichtbar"

    smoke.check("Bewerbung: delete_application", _cleanup)

    db.close()

    # 8. Adapter v2 (#499) — isolierte Smoke-Tests ohne Netz
    def _adapter_registry():
        from bewerbungs_assistent.job_scraper.adapters import (
            available_adapters, get_adapter, JobSourceAdapter,
        )
        names = available_adapters()
        assert "bundesagentur" in names and "hays" in names, \
            f"Registry unvollstaendig: {names}"
        for name in names:
            adapter = get_adapter(name)
            assert isinstance(adapter, JobSourceAdapter), \
                f"{name} ist keine JobSourceAdapter-Instanz"
            assert adapter.source_key == name, \
                f"{name}: source_key={adapter.source_key}"

    smoke.check("Adapter v2: Registry + Instanzen", _adapter_registry)

    def _adapter_posting_roundtrip():
        from bewerbungs_assistent.job_scraper.adapters import JobPosting
        sample = {
            "hash": "x", "title": "T", "company": "C", "location": "L",
            "url": "u", "source": "s", "description": "d",
            "employment_type": "festanstellung", "remote_level": "hybrid",
            "salary_min": 50000, "custom_field": "xyz",
        }
        p = JobPosting.from_job_dict(sample)
        assert p.extra.get("custom_field") == "xyz", "extra-Feld verloren"
        out = p.to_job_dict()
        for key in ("hash", "title", "company", "url", "custom_field"):
            assert out.get(key) == sample[key], f"{key} nicht round-trippable"

    smoke.check("Adapter v2: JobPosting-Roundtrip (keine Dict-Verluste)", _adapter_posting_roundtrip)

    def _adapter_fault_isolation():
        # Orchestrator muss ERROR melden, wenn Adapter wirft, und die
        # anderen Quellen trotzdem durchlaufen lassen.
        from bewerbungs_assistent.job_scraper.adapters import (
            AdapterStatus, run_adapters,
        )
        from bewerbungs_assistent.job_scraper.adapters import registry as reg
        from bewerbungs_assistent.job_scraper.adapters.base import (
            AdapterResult, JobSourceAdapter,
        )

        class _Boom(JobSourceAdapter):
            source_key = "boom"

            def search(self, params):
                raise RuntimeError("boom")

        class _OK(JobSourceAdapter):
            source_key = "ok_src"

            def search(self, params):
                return AdapterResult(status=AdapterStatus.OK, postings=[])

        saved = dict(reg._ADAPTERS)
        reg._ADAPTERS["boom"] = _Boom()
        reg._ADAPTERS["ok_src"] = _OK()
        try:
            res = run_adapters(["boom", "ok_src", "nope"], {})
            assert res["boom"].status == AdapterStatus.ERROR, "boom nicht als ERROR markiert"
            assert res["ok_src"].status == AdapterStatus.OK, "ok_src von boom beeinflusst"
            assert res["nope"].status == AdapterStatus.NOT_CONFIGURED, "nope nicht NOT_CONFIGURED"
        finally:
            reg._ADAPTERS.clear()
            reg._ADAPTERS.update(saved)

    smoke.check("Adapter v2: Fehler-Isolation im Orchestrator", _adapter_fault_isolation)

    # 9. BA-Retry-Logik (#489) — ohne Netz: httpx-Transport mocken
    def _ba_retry_logic():
        import httpx
        from bewerbungs_assistent.job_scraper import bundesagentur as ba

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            # Erste 2 Calls => 503, dritter Call => 200
            if calls["n"] < 3:
                return httpx.Response(503, json={"err": "dns"})
            return httpx.Response(200, json={"stellenangebote": []})

        transport = httpx.MockTransport(handler)
        # Backoff auf 0 setzen, damit der Smoke-Test schnell bleibt.
        orig_backoff = ba._RETRY_BACKOFF_BASE
        ba._RETRY_BACKOFF_BASE = 1.0
        try:
            with httpx.Client(transport=transport, timeout=5) as client:
                # Monkey-patch sleep: wir wollen keine Sekunden warten
                import time as _t
                orig_sleep = _t.sleep
                _t.sleep = lambda _s: None
                try:
                    resp = ba._request_with_retry(client, "http://x/ba", params={"was": "PLM"})
                finally:
                    _t.sleep = orig_sleep
            assert resp is not None and resp.status_code == 200, \
                f"Retry hat nicht auf 200 gewartet (calls={calls['n']})"
            assert calls["n"] == 3, f"erwartet 3 Calls, bekommen {calls['n']}"
        finally:
            ba._RETRY_BACKOFF_BASE = orig_backoff

    smoke.check("BA-Scraper: Retry bis 200 bei transienten 503", _ba_retry_logic)

    return smoke.summary()


def main() -> int:
    parser = argparse.ArgumentParser(description="PBP Smoke-Test (#498)")
    parser.add_argument("--verbose", action="store_true", help="Full tracebacks")
    args = parser.parse_args()
    try:
        return run(verbose=args.verbose)
    finally:
        # Windows haelt SQLite-File-Locks bis GC; gc.collect() + kurzer
        # Retry stellen sicher, dass der Tempdir wirklich verschwindet.
        import gc
        import time
        gc.collect()
        for _ in range(5):
            try:
                shutil.rmtree(_tmpdir)
                break
            except (OSError, PermissionError):
                time.sleep(0.1)
        else:
            shutil.rmtree(_tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
