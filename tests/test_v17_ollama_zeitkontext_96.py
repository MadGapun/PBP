"""beta.96: lokale LLM-Prompts bekommen das echte heutige Datum.

Folgefix zu #679 (Elwosa-Zeit). Ollama kennt nur sein Trainings-Datum —
ohne expliziten Zeitbezug rechnet es z.B. 'X Jahre Erfahrung' gegen ein
falsches Jahr. `_run_local` stellt darum jedem Prompt den aktuellen
Zeitkontext voran.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from bewerbungs_assistent.services import llm_service as L


def test_datums_kontext_enthaelt_jahr_und_zeit():
    ctx = L._datums_kontext()
    now = datetime.now()
    assert str(now.year) in ctx
    assert "Heute ist" in ctx
    assert "Uhr" in ctx
    assert ctx.endswith("\n\n")


def test_run_local_stellt_datumskontext_voran(monkeypatch):
    svc = L.LLMService()

    class _Status:
        selected_model = "testmodel"
        available_models = ["testmodel"]

    monkeypatch.setattr(svc, "get_status", lambda *a, **k: _Status())

    captured = {}

    def _fake_generate(model, prompt, max_tokens=800):
        captured["prompt"] = prompt
        raise RuntimeError("stop-after-capture")

    monkeypatch.setattr(svc, "_ollama_generate", _fake_generate)

    with pytest.raises(RuntimeError):
        svc._run_local(L.TaskKind.CLASSIFY_DOCUMENT,
                       {"text": "Lebenslauf", "filename": "cv.pdf"})

    prompt = captured["prompt"]
    assert prompt.startswith("WICHTIG")           # Zeitkontext zuerst
    assert str(datetime.now().year) in prompt      # echtes Jahr
    assert "Lebenslauf" in prompt                  # eigentlicher Prompt folgt
