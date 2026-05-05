"""LLM-Service-Dispatcher (v1.7.0 #512).

Zentrale Routing-Schicht zwischen drei moeglichen LLM-Backends:

- ``local``   — Ollama-Sidecar auf localhost:11434, fuer deterministische
                Routine-Aufgaben (Doku-Klassifikation, Skill-Extraktion,
                Vor-Filterung). Spart Claude-Tokens und ist kostenlos.
- ``claude``  — der Claude-Aufrufer (via MCP). Fuer kreative und Real-Time-
                Aufgaben (Anschreiben, Coaching, Web-Recherche).
- ``manual``  — kein Backend verfuegbar. Aufrufer bekommt klaren Hinweis,
                dass die Aufgabe manuell zu erledigen ist.

Designprinzipien:

1. **Lokale AI ist immer optional.** Wenn Ollama nicht laeuft oder kein
   Modell installiert ist, faellt der Service stillschweigend auf
   ``claude`` oder ``manual`` zurueck.
2. **Aufgabenteilung ist konfigurierbar** ueber ``ROUTING_TABLE`` —
   jeder Task-Typ hat eine bevorzugte und eine Fallback-Backend-Reihenfolge.
3. **Status-Caching:** Ollama-Erkennung wird 30s gecacht, damit nicht
   jeder Aufruf einen HTTP-Check macht.
4. **Mock-Modus** fuer Tests via Env-Var ``PBP_LLM_MOCK=1``.

In v1.7.0-beta.1 ist nur die Foundation drin — keine echten Ollama-
Aufrufe, nur Erkennung + Routing-Logik. Die echte Anbindung kommt in
beta.2 zusammen mit dem Setup-Wizard und dem ersten lokalen Task
(Doku-Klassifikation).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("bewerbungs_assistent.llm_service")


# ── Task-Definitionen ─────────────────────────────────────────────

class TaskKind(str, Enum):
    """Bekannte Task-Typen, die ueber den LLM-Service laufen koennen."""

    # Lokal-faehige Routine-Tasks
    CLASSIFY_DOCUMENT = "classify_document"
    EXTRACT_SKILLS = "extract_skills"
    MATCH_JOB_TO_SKILLS = "match_job_to_skills"
    EXTRACT_SALARY = "extract_salary"
    COMPARE_JOBS = "compare_jobs"
    FIND_SIMILAR_JOBS = "find_similar_jobs"

    # Claude-bevorzugte kreative Tasks
    GENERATE_COVER_LETTER = "generate_cover_letter"
    INTERVIEW_COACHING = "interview_coaching"
    SALARY_NEGOTIATION = "salary_negotiation"
    COMPANY_RESEARCH = "company_research"
    GENERATE_DAILY_IMPULSE = "generate_daily_impulse"


class Backend(str, Enum):
    """Mögliche Ausführungs-Backends."""
    LOCAL = "local"
    CLAUDE = "claude"
    MANUAL = "manual"


# Routing-Tabelle: welcher Task-Typ hat welche Backend-Praeferenz?
# Reihenfolge = Fallback-Reihenfolge. Wenn das erste Backend nicht
# verfuegbar ist, wird das naechste probiert.
ROUTING_TABLE: dict[TaskKind, list[Backend]] = {
    # Lokal bevorzugt, Claude als Fallback, manuell als letzter Ausweg
    TaskKind.CLASSIFY_DOCUMENT:    [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.EXTRACT_SKILLS:       [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.MATCH_JOB_TO_SKILLS:  [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.EXTRACT_SALARY:       [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.COMPARE_JOBS:         [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.FIND_SIMILAR_JOBS:    [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    # Claude bevorzugt — kreativ, Real-Time, Tonalität
    TaskKind.GENERATE_COVER_LETTER:  [Backend.CLAUDE, Backend.MANUAL],
    TaskKind.INTERVIEW_COACHING:     [Backend.CLAUDE, Backend.MANUAL],
    TaskKind.SALARY_NEGOTIATION:     [Backend.CLAUDE, Backend.MANUAL],
    TaskKind.COMPANY_RESEARCH:       [Backend.CLAUDE, Backend.MANUAL],
    TaskKind.GENERATE_DAILY_IMPULSE: [Backend.CLAUDE, Backend.LOCAL, Backend.MANUAL],
}


# ── Status & Result-Datentypen ────────────────────────────────────

@dataclass
class LLMStatus:
    """Status der lokalen AI-Erkennung."""

    ollama_available: bool = False
    """Ist der Ollama-Service erreichbar (HTTP 200 auf /api/tags)?"""

    ollama_endpoint: str = "http://localhost:11434"
    """URL des Ollama-Servers."""

    available_models: list[str] = field(default_factory=list)
    """Liste der lokal vorhandenen Modelle (gefuellt wenn ollama_available)."""

    selected_model: Optional[str] = None
    """Aktuell gewaehltes Default-Modell (aus profile_settings)."""

    user_state: str = "off"
    """User-Einstellung: 'off' | 'paused' | 'active'. Bei 'paused' wird
    Lokal nicht genutzt, auch wenn Ollama laeuft. Persistiert in
    profile_settings als 'llm_local_state'."""

    last_check_at: float = 0.0
    """Unix-Timestamp des letzten Erkennungs-Laufs (fuer Caching)."""

    error: Optional[str] = None
    """Letzter Fehler bei der Erkennung (wenn vorhanden)."""


@dataclass
class TaskResult:
    """Ergebnis eines LLM-Task-Aufrufs."""

    backend: Backend
    """Welches Backend hat den Task tatsaechlich erledigt."""

    success: bool
    """True wenn der Task erfolgreich war."""

    payload: Any = None
    """Das Resultat (Format taskspezifisch). None bei Misserfolg."""

    fallback_message: Optional[str] = None
    """Wenn backend == MANUAL: Hinweis-Text fuer den User."""

    metrics: dict = field(default_factory=dict)
    """Optional: Token-Verbrauch, Latenz, etc."""


# ── Service-Klasse ─────────────────────────────────────────────────

class LLMService:
    """Zentraler Dispatcher fuer alle LLM-Aufrufe in PBP.

    Lifetime: ein Singleton pro PBP-Prozess. Der Status wird gecacht,
    damit nicht jeder Aufruf einen HTTP-Check macht.
    """

    # Cache-Dauer fuer Ollama-Erkennung in Sekunden
    STATUS_CACHE_SECONDS = 30.0

    def __init__(self, db=None):
        self.db = db
        self._status: LLMStatus = LLMStatus()
        self._mock_mode = os.environ.get("PBP_LLM_MOCK") == "1"

    # ── Status & Erkennung ─────────────────────────────────────────

    def get_status(self, force_refresh: bool = False) -> LLMStatus:
        """Aktuellen Status zurueckgeben (mit Caching).

        Bei force_refresh=True wird immer neu geprueft.
        """
        now = time.time()
        cache_valid = (
            not force_refresh
            and self._status.last_check_at > 0
            and (now - self._status.last_check_at) < self.STATUS_CACHE_SECONDS
        )
        if cache_valid:
            return self._status

        # User-State aus DB laden (falls vorhanden)
        if self.db is not None:
            try:
                state = self.db.get_profile_setting("llm_local_state", "off")
                self._status.user_state = str(state) if state in ("off", "paused", "active") else "off"
                model = self.db.get_profile_setting("llm_local_model", None)
                self._status.selected_model = model or None
            except Exception as e:
                logger.debug("Failed to read llm_local_* settings: %s", e)

        # Ollama-Erkennung
        if self._mock_mode:
            # Mock: tut so als ob Ollama mit einem Modell laueft
            self._status.ollama_available = True
            self._status.available_models = ["mock-model:7b"]
            self._status.error = None
        else:
            self._check_ollama()

        self._status.last_check_at = now
        return self._status

    def _check_ollama(self) -> None:
        """HTTP-Check ob Ollama laeuft. Aktualisiert self._status."""
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                f"{self._status.ollama_endpoint}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status != 200:
                    self._status.ollama_available = False
                    self._status.available_models = []
                    self._status.error = f"HTTP {resp.status}"
                    return
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", []) or []
                self._status.ollama_available = True
                self._status.available_models = [m.get("name", "") for m in models if m.get("name")]
                self._status.error = None
        except Exception as e:
            self._status.ollama_available = False
            self._status.available_models = []
            self._status.error = str(e)[:200]

    # ── Backend-Auswahl ────────────────────────────────────────────

    def select_backend(self, task: TaskKind) -> Backend:
        """Waehlt das beste verfuegbare Backend fuer einen Task.

        Beruecksichtigt:
        - Routing-Praeferenz aus ROUTING_TABLE
        - User-State (paused/off → LOCAL nicht moeglich)
        - Ollama-Verfuegbarkeit (kein Modell installiert → LOCAL nicht moeglich)
        """
        status = self.get_status()
        chain = ROUTING_TABLE.get(task, [Backend.CLAUDE, Backend.MANUAL])
        for backend in chain:
            if backend == Backend.LOCAL:
                if (status.ollama_available
                        and status.user_state == "active"
                        and status.available_models):
                    return Backend.LOCAL
                continue
            if backend == Backend.CLAUDE:
                # Claude ist via MCP immer "verfuegbar" — der Aufrufer
                # muss aber wissen dass das Resultat asynchron ueber den
                # Claude-Tool-Call zurueckkommt.
                return Backend.CLAUDE
            return Backend.MANUAL
        return Backend.MANUAL

    # ── Task-Ausfuehrung ───────────────────────────────────────────

    def run(self, task: TaskKind, payload: dict) -> TaskResult:
        """Fuehrt einen Task auf dem besten verfuegbaren Backend aus.

        v1.7.0-beta.2: Echte Ollama-Calls fuer lokale Tasks.
        """
        backend = self.select_backend(task)

        if self._mock_mode and backend == Backend.LOCAL:
            return TaskResult(
                backend=Backend.LOCAL,
                success=True,
                payload={"mock": True, "task": task.value, "input": payload},
                metrics={"backend": "mock", "duration_ms": 0},
            )

        if backend == Backend.LOCAL:
            # v1.7.0-beta.2: Echter Ollama-Call
            try:
                return self._run_local(task, payload)
            except Exception as exc:
                logger.warning("Local LLM call failed for %s: %s — falling back to CLAUDE",
                               task, exc)
                backend = Backend.CLAUDE

        if backend == Backend.CLAUDE:
            return TaskResult(
                backend=Backend.CLAUDE,
                success=False,
                payload=None,
                fallback_message=(
                    f"Task '{task.value}' soll von Claude erledigt werden — "
                    "der MCP-Aufrufer (Claude Desktop) ist hier zustaendig."
                ),
                metrics={"backend": "claude_pending"},
            )

        return TaskResult(
            backend=Backend.MANUAL,
            success=False,
            payload=None,
            fallback_message=(
                f"Task '{task.value}' kann derzeit weder lokal noch via Claude "
                "erledigt werden — bitte manuell."
            ),
        )

    # ── Echte Ollama-Anbindung (v1.7.0-beta.2) ─────────────────────

    def _run_local(self, task: TaskKind, payload: dict) -> TaskResult:
        """Fuehrt einen Task gegen den lokalen Ollama-Server aus.

        Pro Task-Typ gibt es einen Prompt-Builder, der den Roh-Input in
        einen LLM-Prompt verwandelt und das Ergebnis zurueck-parst.
        """
        status = self.get_status()
        model = status.selected_model or (status.available_models[0] if status.available_models else None)
        if not model:
            raise RuntimeError("Kein Ollama-Modell installiert.")

        builder = _PROMPT_BUILDERS.get(task)
        if builder is None:
            raise NotImplementedError(f"Lokaler Task '{task.value}' nicht implementiert.")

        prompt = builder(payload)
        start = time.time()
        response_text = self._ollama_generate(model, prompt)
        duration_ms = int((time.time() - start) * 1000)

        parser = _RESPONSE_PARSERS.get(task, lambda s: {"raw": s})
        result_payload = parser(response_text)

        return TaskResult(
            backend=Backend.LOCAL,
            success=True,
            payload=result_payload,
            metrics={"backend": "ollama", "model": model, "duration_ms": duration_ms},
        )

    def _ollama_generate(self, model: str, prompt: str, max_tokens: int = 800) -> str:
        """Synchroner HTTP-Call an `POST /api/generate`. Stream off, JSON-Antwort.

        Liefert das `response`-Feld als String zurueck. Wirft Exception bei
        Fehler — der Aufrufer muss das fangen.
        """
        import json
        import urllib.request
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._status.ollama_endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")

    def list_models(self) -> list[dict]:
        """Liste der lokal verfuegbaren Ollama-Modelle (mit Metadaten)."""
        try:
            import json
            import urllib.request
            req = urllib.request.Request(
                f"{self._status.ollama_endpoint}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("models", []) or []
        except Exception:
            return []

    def trigger_pull(self, model_name: str) -> dict:
        """Loest einen Modell-Download in Ollama aus (asynchron via Stream).

        Aktuell: synchroner Call, wartet bis Download fertig oder Fehler.
        Fuer beta.2 reicht das. Fortschritts-Streaming kommt spaeter.
        """
        import json
        import urllib.request
        body = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{self._status.ollama_endpoint}/api/pull",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": data.get("status", "ok"), "model": model_name}
        except Exception as exc:
            return {"status": "error", "model": model_name, "error": str(exc)[:200]}


# ── Prompt-Builders & Response-Parsers ────────────────────────────

def _build_classify_document_prompt(payload: dict) -> str:
    text = (payload.get("text") or "")[:3000]
    filename = payload.get("filename") or ""
    return (
        "Du bist ein deutschsprachiger Klassifikator fuer Bewerbungs-Dokumente.\n"
        "Klassifiziere das folgende Dokument in eine dieser Kategorien:\n"
        "- lebenslauf\n"
        "- anschreiben\n"
        "- arbeitszeugnis\n"
        "- ausbildungszeugnis\n"
        "- zertifikat\n"
        "- foto\n"
        "- email\n"
        "- stellenanzeige\n"
        "- bewerbungsantwort\n"
        "- sonstiges\n\n"
        "Antworte AUSSCHLIESSLICH mit dem Kategorie-Schluessel, kein "
        "Erklaerungstext, keine Anfuehrungszeichen.\n\n"
        f"Dateiname: {filename}\n\n"
        f"Inhalt (Auszug):\n{text}"
    )


def _parse_classify_document(raw: str) -> dict:
    cleaned = (raw or "").strip().lower().split()[0] if raw else ""
    cleaned = cleaned.strip(".,;:'\"`")
    valid = {"lebenslauf", "anschreiben", "arbeitszeugnis", "ausbildungszeugnis",
             "zertifikat", "foto", "email", "stellenanzeige", "bewerbungsantwort",
             "sonstiges"}
    if cleaned not in valid:
        return {"category": "sonstiges", "confidence": 0.3, "raw": raw}
    return {"category": cleaned, "confidence": 0.85, "raw": raw}


def _build_extract_skills_prompt(payload: dict) -> str:
    text = (payload.get("text") or "")[:4000]
    return (
        "Extrahiere alle technischen und fachlichen Skills aus dem folgenden "
        "Lebenslauf. Antworte mit einer kommagetrennten Liste, KEINE "
        "Erklaerungen, KEINE Bullet-Points, KEINE Nummern.\n\n"
        f"{text}"
    )


def _parse_extract_skills(raw: str) -> dict:
    # Erst inhaltlich normalisieren, dann splitten — messy Outputs (Bullets,
    # Nummerierung, Praefix-Strich) entfernen.
    cleaned = []
    for s in (raw or "").split(","):
        token = s.strip()
        # Fuehrenden Bullet/Strich/Asterisk weg
        while token and token[0] in "-*•·–—":
            token = token[1:].strip()
        # Nachfolgenden Punkt/Komma/Kolon weg
        token = token.strip(".,;:'\"`")
        if token and len(token) <= 60:
            cleaned.append(token)
    return {"skills": cleaned, "count": len(cleaned)}


_PROMPT_BUILDERS = {
    TaskKind.CLASSIFY_DOCUMENT: _build_classify_document_prompt,
    TaskKind.EXTRACT_SKILLS: _build_extract_skills_prompt,
}

_RESPONSE_PARSERS = {
    TaskKind.CLASSIFY_DOCUMENT: _parse_classify_document,
    TaskKind.EXTRACT_SKILLS: _parse_extract_skills,
}


# ── Singleton-Helper ───────────────────────────────────────────────

_default_service: Optional[LLMService] = None


def get_llm_service(db=None) -> LLMService:
    """Singleton-Accessor. Bei mehreren Aufrufen wird derselbe Service zurueckgegeben."""
    global _default_service
    if _default_service is None:
        _default_service = LLMService(db=db)
    elif db is not None and _default_service.db is None:
        _default_service.db = db
    return _default_service


def reset_llm_service() -> None:
    """Setzt den Singleton zurueck — fuer Tests."""
    global _default_service
    _default_service = None
