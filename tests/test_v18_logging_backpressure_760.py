# -*- coding: utf-8 -*-
"""#760 / A23: stderr-Backpressure darf den MCP-Server nie einfrieren.

Praxis-Fall 2026-07-16: jobsuche_starten mit ~32 aktiven Quellen fuellte
den stderr-Pipe-Puffer (Claude Desktop liest stderr nicht kontinuierlich).
Der Such-Thread blockierte im StreamHandler-write und hielt dabei den
Handler-Lock — der naechste logger.info() in der Tool-Middleware (im
Event-Loop-Thread!) wartete ewig auf den Lock: kein Tool antwortete mehr,
der Heartbeat fror ein, waehrend Dashboard und DB im selben Prozess
weiterliefen. Fix: Console-Logging laeuft ueber eine Drop-on-full-Queue
(logging_config.DropOnFullQueueHandler + QueueListener); die Middleware
schreibt den Heartbeat VOR dem Log-Aufruf.
"""
import asyncio
import logging
import queue
import threading
import time
from logging.handlers import QueueListener

import pytest

from bewerbungs_assistent.logging_config import (
    DropOnFullQueueHandler,
    setup_logging,
)


class TestDropOnFullQueueHandler:
    def test_volle_queue_verwirft_statt_zu_blockieren(self):
        lq = queue.Queue(maxsize=2)
        qh = DropOnFullQueueHandler(lq)
        rec = logging.LogRecord(
            "x", logging.INFO, __file__, 1, "msg", (), None)
        t0 = time.monotonic()
        for _ in range(10):
            qh.enqueue(qh.prepare(rec))
        assert time.monotonic() - t0 < 1.0, "enqueue hat blockiert"
        assert lq.qsize() == 2

    def test_logger_lebt_trotz_blockiertem_stream(self):
        """Kern von #760: Ziel-Stream haengt (voller Pipe-Puffer) —
        logger-Aufrufe muessen trotzdem sofort zurueckkehren."""
        gate = threading.Event()

        class BlockierenderStream:
            def write(self, s):
                gate.wait(timeout=30)

            def flush(self):
                pass

        sh = logging.StreamHandler(BlockierenderStream())
        lq = queue.Queue(maxsize=5)
        qh = DropOnFullQueueHandler(lq)
        listener = QueueListener(lq, sh)
        listener.start()
        lg = logging.getLogger("test760_blockierter_stream")
        lg.addHandler(qh)
        lg.setLevel(logging.INFO)
        lg.propagate = False
        try:
            t0 = time.monotonic()
            for i in range(50):  # weit mehr als Queue + Pipe fassen
                lg.info("suchlauf quelle %d liefert treffer", i)
            dauer = time.monotonic() - t0
            assert dauer < 2.0, f"Logging blockierte {dauer:.1f}s (#760)"
        finally:
            gate.set()
            # Listener erst stoppen wenn die Queue geleert ist — stop()
            # legt einen Sentinel per put_nowait und wuerde an der noch
            # vollen Queue selbst mit queue.Full scheitern.
            for _ in range(200):
                if lq.empty():
                    break
                time.sleep(0.05)
            listener.stop()
            lg.removeHandler(qh)

    def test_setup_logging_haengt_keinen_direkten_stream_handler_an(self):
        lg = setup_logging()  # idempotent; Suite hat i.d.R. schon initialisiert
        direkte = [
            h for h in lg.handlers
            if type(h) is logging.StreamHandler  # exakt, nicht Subklassen
        ]
        assert not direkte, (
            "direkter StreamHandler am Logger — genau der #760-Blocker")
        assert any(isinstance(h, DropOnFullQueueHandler) for h in lg.handlers)


class TestMiddlewareHeartbeatReihenfolge:
    def test_heartbeat_wird_vor_dem_log_geschrieben(self, monkeypatch):
        """Friert Logging ein, muss der Heartbeat den Call trotzdem
        dokumentiert haben (write_heartbeat VOR logger.info)."""
        from bewerbungs_assistent import server as srv

        beats = []
        monkeypatch.setattr(srv, "write_heartbeat", beats.append)

        def eingefroren(*a, **k):
            raise RuntimeError("logging eingefroren (#760-Simulation)")

        monkeypatch.setattr(srv.logger, "info", eingefroren)

        mw = srv.HeartbeatMiddleware()

        class Msg:
            name = "pbp_mcp_diagnose"

        class Ctx:
            message = Msg()

        async def call_next(ctx):
            return "ok"

        with pytest.raises(RuntimeError):
            asyncio.run(mw.on_call_tool(Ctx(), call_next))
        assert beats == ["pbp_mcp_diagnose"]
