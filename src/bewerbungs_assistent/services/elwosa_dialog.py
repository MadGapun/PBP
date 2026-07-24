"""Elwosa ueber Claude ansprechbar (#774, F29, v1.7.10).

Claude ist der Vermittler: der User fragt, PBP reicht die Frage mit
relevantem Kontext an die lokale KI durch, Claude ordnet die Antwort ein.
Kein eigenes Chat-Fenster (#771, verworfen) — ein 7B/8B-Modell antwortet
plausibel auch dort, wo es falsch liegt; der Umweg ueber Claude ist das
Fehlerkorrektiv.

Grundregeln:
- Elwosa ist AUSKUNFTSFAEHIG, NICHT URTEILSFAEHIG. Antworten sind eine
  Position ("Elwosa sagt dazu: ..."), kein Fakt.
- Ohne Kontext ist die Antwort wertlos — jede Frage bekommt Profil-
  Kurztext (ohne PII-Details), Kern-Statistiken und die vom User
  BESTAETIGTEN learned_insights (#784) mit.
- Lokale KI nicht erreichbar -> ehrliche Meldung. KEIN stiller Fallback
  auf Claude.
- Dialoge landen in elwosa_messages (trigger_kind='dialog') und sind
  damit nachvollziehbar.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

SPRACH_DNA = (
    "Antworte auf Deutsch, per Du, lakonisch und knapp. Keine "
    "Ausrufezeichen, keine Emojis. Wenn die Datenlage duenn ist, sag das "
    "offen statt zu raten."
)


def baue_kontext(db: Any) -> tuple[str, list, int]:
    """Kontextblock fuer die lokale KI. Liefert (text, quellen, datenpunkte)."""
    quellen: list = []
    datenpunkte = 0
    teile: list = []

    try:
        from .llm_service import build_profil_kurztext
        profil = db.get_profile()
        kurz = build_profil_kurztext(profil) if profil else ""
        if kurz:
            teile.append("PROFIL (Kurzfassung):\n" + kurz)
            quellen.append("profil_kurztext")
    except Exception:
        pass

    try:
        stats = db.get_statistics()
        q = (stats.get("quoten") or {}).get("gesamt") or {}
        if q.get("basis"):
            teile.append(
                "BEWERBUNGS-STATISTIK: "
                f"{q['basis']} abgeschickte Bewerbungen, "
                f"Interview-Quote {q.get('interview_rate', 0)} %, "
                f"Angebots-Quote {q.get('offer_rate', 0)} %, "
                f"Absage-Quote {q.get('rejection_rate', 0)} %, "
                f"ohne Rueckmeldung {q.get('expired_rate', 0)} %."
            )
            quellen.append("statistik_quoten")
            datenpunkte += q["basis"]
        aktiv = stats.get("active_jobs")
        if aktiv is not None:
            teile.append(f"STELLEN: {aktiv} aktiv, "
                         f"{stats.get('dismissed_jobs', 0)} aussortiert.")
            datenpunkte += (aktiv or 0) + (stats.get("dismissed_jobs") or 0)
            quellen.append("stellen_zaehler")
    except Exception:
        pass

    try:
        from .lerninsights import bestaetigte_fuer_kontext
        insights = bestaetigte_fuer_kontext(db)
        if insights:
            zeilen = [
                f"- [{i['kategorie']}, Konfidenz {i['konfidenz']}, "
                f"n={i['belegt_durch_n']}] {i['aussage']}"
                for i in insights[:10]
            ]
            teile.append(
                "VOM NUTZER BESTAETIGTE ERKENNTNISSE (nur diese als "
                "gesichert behandeln):\n" + "\n".join(zeilen))
            quellen.append(f"learned_insights ({len(insights)} bestaetigt)")
            datenpunkte += sum(i["belegt_durch_n"] for i in insights)
    except Exception:
        pass

    return "\n\n".join(teile), quellen, datenpunkte


def baue_prompt(db: Any, frage: str) -> tuple[str, list, int]:
    kontext, quellen, datenpunkte = baue_kontext(db)
    prompt = (
        f"Du bist Elwosa, die lokale Assistenz-KI des Bewerbungsportals PBP. "
        f"{SPRACH_DNA}\n"
        f"Heute ist {datetime.now().strftime('%d.%m.%Y')}.\n\n"
        f"{kontext}\n\n"
        f"FRAGE DES NUTZERS:\n{frage}\n\n"
        "Antworte nur auf Basis des obigen Kontexts. Was du nicht weisst, "
        "benennst du als unbekannt."
    )
    return prompt, quellen, datenpunkte


def _log_dialog(db: Any, frage: str, antwort: str) -> None:
    """Dialog in elwosa_messages ablegen — bewusst OHNE Tonfall-Validator:
    das ist ein Protokoll fremder Aussagen, keine kuratierte Elwosa-Linie."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id() or ""
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO elwosa_messages (profile_id, content, trigger_kind, "
            "cluster, created_at) VALUES (?,?,?,?,?)",
            (pid, f"Frage: {frage[:400]}", "dialog_frage", "dialog", now))
        conn.execute(
            "INSERT INTO elwosa_messages (profile_id, content, trigger_kind, "
            "cluster, created_at) VALUES (?,?,?,?,?)",
            (pid, f"Antwort: {antwort[:2000]}", "dialog_antwort", "dialog", now))
        conn.commit()
    except Exception:
        pass


def frage_stellen(db: Any, frage: str, roh: bool = False) -> dict:
    """Frage an die lokale KI durchreichen. Ehrlicher Fehler statt Fallback."""
    from .llm_service import LLMService
    service = LLMService(db)
    status = service.get_status()
    if not getattr(status, "ollama_available", False):
        return {
            "status": "nicht_erreichbar",
            "fehler": (
                "Die lokale KI (Ollama) ist nicht erreichbar — Elwosa kann "
                "nicht antworten. Claude darf diese Frage NICHT stillschweigend "
                "selbst beantworten, sondern soll den Ausfall benennen."
            ),
            "details": getattr(status, "error", "") or "",
        }
    model = getattr(status, "selected_model", None) or (
        (getattr(status, "available_models", None) or [None])[0])
    if not model:
        return {"status": "kein_modell",
                "fehler": "Ollama laeuft, aber es ist kein Modell installiert."}

    prompt, quellen, datenpunkte = baue_prompt(db, frage)
    start = time.time()
    try:
        antwort = service._ollama_generate(model, prompt, max_tokens=600)
    except Exception as e:
        return {
            "status": "fehler",
            "fehler": f"Lokale KI hat nicht geantwortet: {e}. "
                      "Kein Fallback auf Claude — Ausfall bitte benennen.",
        }
    dauer_ms = int((time.time() - start) * 1000)
    antwort = (antwort or "").strip()
    _log_dialog(db, frage, antwort)
    result = {
        "status": "ok",
        "antwort": antwort,
        "modell": model,
        "kontext_verwendet": quellen,
        "dauer_ms": dauer_ms,
        "konfidenz_hinweis": (
            f"Antwort basiert auf {datenpunkte} Datenpunkten aus PBP. "
            "Elwosa ist auskunftsfaehig, nicht urteilsfaehig."
        ),
    }
    if not roh:
        result["einordnung_pflicht"] = (
            "Diese Antwort als Position kennzeichnen ('Elwosa sagt dazu: "
            "...'), bei Widerspruch zur eigenen Einschaetzung beides zeigen "
            "und den Unterschied benennen. Nicht fuer Stellenbewertungen "
            "oder Handlungsempfehlungen verwenden."
        )
    return result
