"""Regressionstest v1.7.18 — Budget-Pool darf den Test-Drain nicht blockieren.

Die #915-Pool-Worker hiessen zunaechst "pbp-tool-budget-N". Der A22/#759-
Drain in conftest joint JEDEN "pbp-*"-Thread mit 15 s Timeout, bevor eine
Fixture die DB schliesst — Pool-Worker sind aber Idle-Dauerlaeufer und
beenden sich nie. Folge: 15 Sekunden Teardown pro Test, in Summe ueber
eine halbe Stunde CI-Laufzeit; der main-Lauf riss sein 30-Minuten-Limit
und wurde abgebrochen (die Stable-Suite kam knapp durch — der Fehler war
also nur auf einer Linie sichtbar).
"""
import threading
import time

from bewerbungs_assistent.services import tool_budget


def test_pool_worker_tragen_kein_pbp_praefix():
    """Der Drain darf sie nicht erwischen."""
    @tool_budget.mit_budget("demo", lese_tool="demo_anzeigen")
    def schnell():
        return {"status": "ok", "thread": threading.current_thread().name}

    res = schnell()
    assert res["status"] == "ok"
    name = res["thread"]
    assert not name.startswith("pbp-"), (
        f"Pool-Worker heisst '{name}' — mit 'pbp-'-Praefix joint der "
        "conftest-Drain ihn 15 s lang pro Test (CI-Timeout)"
    )


def test_lebende_pool_threads_werden_nicht_gejoint():
    """Nach einem Aufruf leben Worker weiter — aber unter anderem Namen."""
    @tool_budget.mit_budget("demo", lese_tool="demo_anzeigen")
    def schnell():
        return 1

    schnell()
    pbp_threads = [t.name for t in threading.enumerate()
                   if t.name.startswith("pbp-") and t.is_alive()]
    assert not any("budget" in n for n in pbp_threads), pbp_threads


def test_warte_auf_leerlauf_meldet_freie_bahn():
    """Der Drain wartet auf LEERLAUF statt auf den Thread-Tod."""
    assert tool_budget.warte_auf_leerlauf(timeout=5) is True

    frei = threading.Event()
    gestartet = threading.Event()

    @tool_budget.mit_budget("demo", lese_tool="demo_anzeigen")
    def haengt():
        gestartet.set()
        frei.wait(timeout=10)
        return 1

    t = threading.Thread(target=haengt, daemon=True, name="testrunner-budget")
    t.start()
    try:
        assert gestartet.wait(timeout=5)
        # laufender Auftrag -> kein Leerlauf
        assert tool_budget.warte_auf_leerlauf(timeout=0.5) is False
    finally:
        frei.set()
        t.join(timeout=10)
    assert tool_budget.warte_auf_leerlauf(timeout=5) is True


def test_teardown_bleibt_schnell():
    """Ein Budget-Aufruf darf den Teardown nicht in den 15s-Join treiben."""
    @tool_budget.mit_budget("demo", lese_tool="demo_anzeigen")
    def schnell():
        return 1

    schnell()
    t0 = time.time()
    tool_budget.warte_auf_leerlauf(timeout=10)
    assert time.time() - t0 < 2, "Leerlauf muss sofort gemeldet werden"
