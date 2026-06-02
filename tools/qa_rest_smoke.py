"""QA: REST-Endpoint-Smoke-Test gegen migrierte Real-DB-Kopie (#QA-B).

Nutzt FastAPI TestClient (kein Port-Binding -> kein Konflikt mit dem
laufenden User-Server). Testet die in beta.85/90 neu hinzugekommenen
Endpoints end-to-end gegen echte Daten.

READ-mostly: legt nur Test-Tasks/Reasons in der KOPIE an, nicht im Original.
"""
import os
# Migrierte KOPIE der Real-DB (nie das Original unter AppData!).
# Pfad ueber QA_DATA_DIR ueberschreibbar; Default ist der lokale QA-Ordner.
os.environ["BA_DATA_DIR"] = os.environ.get("QA_DATA_DIR", r"C:\Temp\claude\qa")

import sys
sys.path.insert(0, "src")

from starlette.testclient import TestClient  # noqa: E402
import bewerbungs_assistent.dashboard as dash  # noqa: E402
from bewerbungs_assistent.database import Database  # noqa: E402

db = Database()
db.initialize()
dash._db = db

client = TestClient(dash.app)
ok = 0
fail = 0


def check(name, resp, want=200):
    global ok, fail
    status = resp.status_code
    if status == want:
        ok += 1
        print(f"  OK   {name}: {status}")
        return True
    fail += 1
    body = ""
    try:
        body = str(resp.json())[:120]
    except Exception:
        body = resp.text[:120]
    print(f"  FAIL {name}: {status} (want {want}) {body}")
    return False


print("=== Dismiss-Reasons (#663 C20) ===")
r = client.get("/api/dismiss-reasons")
check("GET /api/dismiss-reasons", r)
reasons_before = len(r.json()) if r.status_code == 200 else 0
print(f"       {reasons_before} Gruende")

r = client.post("/api/dismiss-reasons", json={"label": "qa_testgrund"})
check("POST /api/dismiss-reasons", r)
new_id = (r.json() or {}).get("id") if r.status_code == 200 else None

if new_id:
    r = client.patch(f"/api/dismiss-reasons/{new_id}", json={"is_active": 0})
    check(f"PATCH /api/dismiss-reasons/{new_id} (deactivate)", r)
    r = client.patch(f"/api/dismiss-reasons/{new_id}", json={"label": "qa_testgrund_neu"})
    check(f"PATCH /api/dismiss-reasons/{new_id} (rename)", r)

print("=== Tasks (#666 D19) ===")
# Eine echte application_id holen
conn = db.connect()
app_row = conn.execute("SELECT id FROM applications LIMIT 1").fetchone()
app_id = app_row["id"] if app_row else None
print(f"       Test-Bewerbung: {app_id}")

if app_id:
    r = client.get(f"/api/applications/{app_id}/tasks")
    check(f"GET /api/applications/{app_id}/tasks", r)

    r = client.post(f"/api/applications/{app_id}/tasks", json={"titel": "QA-Test-Todo"})
    check("POST .../tasks", r)
    task_id = (r.json() or {}).get("id") if r.status_code == 200 else None

    if task_id:
        r = client.post(f"/api/tasks/{task_id}/complete", json={"notiz": "qa"})
        check(f"POST /api/tasks/{task_id}/complete", r)
        r = client.post(f"/api/tasks/{task_id}/reopen")
        check(f"POST /api/tasks/{task_id}/reopen", r)
        r = client.delete(f"/api/tasks/{task_id}")
        check(f"DELETE /api/tasks/{task_id}", r)

    r = client.get("/api/tasks")
    check("GET /api/tasks", r)

print("=== Follow-ups complete (#665 D18) ===")
fu_row = conn.execute("SELECT id FROM follow_ups WHERE status='geplant' LIMIT 1").fetchone()
if fu_row:
    # NICHT abschliessen (Kopie, aber wir wollen das Verhalten nicht aendern) —
    # nur pruefen dass der Endpoint existiert/antwortet via einer ungueltigen ID
    r = client.post("/api/follow-ups/nichtvorhanden/complete", json={})
    # erwartet 404 (Endpoint existiert, ID nicht) -> beweist Routing
    print(f"  INFO POST /api/follow-ups/<bad>/complete: {r.status_code} (404 = Endpoint da)")
else:
    print("       kein offener Follow-up in der Kopie")

print(f"\n=== Ergebnis: {ok} OK, {fail} FAIL ===")
db.close()
sys.exit(1 if fail else 0)
