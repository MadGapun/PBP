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
    CLASSIFY_EMAIL = "classify_email"  # v1.7.0-beta.24
    ANALYZE_USER_PATTERNS = "analyze_user_patterns"  # v1.7.0-beta.28 (#594 Stufe 3)
    EXTRACT_CONTACTS = "extract_contacts"  # v1.7.0-beta.39 (#606)
    VALIDATE_JOB_QUALITY = "validate_job_quality"  # v1.7.0-beta.73 (#645)

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
    TaskKind.CLASSIFY_EMAIL:       [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.ANALYZE_USER_PATTERNS:[Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.EXTRACT_CONTACTS:     [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
    TaskKind.VALIDATE_JOB_QUALITY: [Backend.LOCAL, Backend.CLAUDE, Backend.MANUAL],
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

    models_detail: list[dict] = field(default_factory=list)
    """v1.7.0-beta.25: Liste von {name, size_bytes, modified_at, family,
    parameter_size} fuer UI-Anzeige (#591/#592)."""

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
        """HTTP-Check ob Ollama laeuft. Aktualisiert self._status.

        v1.7.0-beta.25 (#591/#592):
        - models_detail wird gepflegt mit name + size + modified_at fuer UI
        - Auto-Select: wenn nur 1 Modell installiert und kein selected_model,
          wird das einzige Modell automatisch zum Default
        """
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
                    self._status.models_detail = []
                    self._status.error = f"HTTP {resp.status}"
                    return
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", []) or []
                names = [m.get("name", "") for m in models if m.get("name")]
                self._status.ollama_available = True
                self._status.available_models = names
                self._status.models_detail = [
                    {
                        "name": m.get("name", ""),
                        "size_bytes": m.get("size", 0),
                        "modified_at": m.get("modified_at", ""),
                        "family": (m.get("details") or {}).get("family", ""),
                        "parameter_size": (m.get("details") or {}).get("parameter_size", ""),
                    }
                    for m in models if m.get("name")
                ]
                self._status.error = None
                # Auto-Select wenn genau 1 Modell + nichts selected
                if not self._status.selected_model and len(names) == 1:
                    self._status.selected_model = names[0]
                    if self.db is not None:
                        try:
                            self.db.set_profile_setting("llm_local_model", names[0])
                        except Exception:
                            pass
        except Exception as e:
            self._status.ollama_available = False
            self._status.available_models = []
            self._status.models_detail = []
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

        # v1.7.0-beta.96: Ollama kennt sein Trainings-Datum, nicht HEUTE.
        # Ohne expliziten Zeitbezug rechnet das Modell z.B. 'X Jahre
        # Erfahrung' gegen ein falsches Jahr oder haelt alte Stellen fuer
        # aktuell. Darum vor jeden lokalen Prompt den echten Zeitkontext.
        prompt = _datums_kontext() + builder(payload)
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

        v1.7.0-beta.62 (#638): keep_alive=60m schickt Ollama den Hint dass
        das Modell 60 Minuten lang im RAM gehalten werden soll. Sonst
        entlaedt Ollama nach 5 Min Inaktivitaet und der naechste Aufruf
        zahlt 50-60s Cold-Load — was MCP-Timeouts ausloest.
        """
        import json
        import urllib.request
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.2},
            "keep_alive": "60m",  # #638: Modell warm halten
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

    def warmup(self, model: str | None = None) -> dict:
        """v1.7.0-beta.62 (#638): Modell vorab laden um Cold-Load-Latenz zu vermeiden.

        Sendet einen Dummy-Request mit num_predict=1 + keep_alive=60m,
        damit das Modell sofort verfuegbar ist und 60 Minuten warm bleibt.
        Idempotent — wenn Modell schon warm, kostet das Millisekunden.

        Aufruf vor Bulk-Operationen (stellen_auto_aussortieren etc) oder
        regelmaessig aus dem Heartbeat.
        """
        import json
        import time as _t
        import urllib.request
        s = self.get_status(force_refresh=False)
        if not s.ollama_available:
            return {"status": "no_ollama", "error": s.error or "Ollama nicht erreichbar"}
        m = model or s.selected_model
        if not m:
            return {"status": "no_model"}
        t0 = _t.time()
        body = json.dumps({
            "model": m,
            "prompt": "ready",
            "stream": False,
            "options": {"num_predict": 1, "temperature": 0.0},
            "keep_alive": "60m",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{s.ollama_endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                resp.read()
        except Exception as exc:
            return {
                "status": "error",
                "model": m,
                "error": f"{type(exc).__name__}: {exc}"[:200],
                "duration_sec": round(_t.time() - t0, 2),
            }
        return {
            "status": "warm",
            "model": m,
            "duration_sec": round(_t.time() - t0, 2),
        }

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

def _datums_kontext() -> str:
    """Aktueller Zeitbezug fuer lokale LLM-Prompts (#679-Folgefix, beta.96).

    Ollama-Modelle haben kein eingebautes 'heute' — ohne diesen Hinweis
    rechnen sie Zeitraeume ('X Jahre Erfahrung', 'seit JJJJ') gegen ihr
    Trainings-Datum oder halten alte Stellen fuer aktuell. Locale-
    unabhaengig: numerisches Datum, Jahr explizit.
    """
    from datetime import datetime
    now = datetime.now()
    return (
        f"WICHTIG — aktueller Zeitbezug: Heute ist der {now.strftime('%d.%m.%Y')} "
        f"(Jahr {now.year}), aktuelle Uhrzeit {now.strftime('%H:%M')}. Verwende "
        f"AUSSCHLIESSLICH dieses Datum fuer alle zeitbezogenen Angaben "
        f"(Jahres-Zeitraeume aus 'X Jahre Erfahrung' oder 'seit JJJJ', "
        f"Aktualitaet, Fristen). Nimm NICHT dein Trainings-Datum an.\n\n"
    )


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


# v1.7.0-beta.24 (#586): match_job_to_skills — profil-basiertes Aussortieren
# ohne Filter-Listen. Lokale AI bekommt das Profil + die Stelle und entscheidet
# binaer "passt"/"passt_nicht"/"unsicher" mit kurzer Begruendung.

def _build_match_job_to_skills_prompt(payload: dict) -> str:
    profile_skills = payload.get("profile_skills") or []
    profile_position = (payload.get("profile_position") or "").strip()
    profile_seniority = (payload.get("profile_seniority") or "").strip()
    job_title = (payload.get("job_title") or "").strip()
    job_company = (payload.get("job_company") or "").strip()
    job_description = (payload.get("job_description") or "")[:1500]

    # v1.7.0-beta.28 (#594 Stufe 3): adaptive Anreicherung. Wenn der User
    # immer aus den gleichen Gruenden aussortiert (z.B. "falsches_fachgebiet"
    # in 80% der Faelle), dann sieht die LLM diese Top-3 jetzt im Prompt
    # und kann das Muster anwenden statt jede Stelle isoliert zu betrachten.
    dismiss_reasons_top = payload.get("dismiss_reasons_top") or []
    learned_block = ""
    if dismiss_reasons_top:
        formatted = "\n".join(
            f"  - {r.get('reason')} ({r.get('count')} Mal aussortiert)"
            for r in dismiss_reasons_top[:3] if r.get("reason")
        )
        if formatted:
            learned_block = (
                "\nGELERNT: Dieser Bewerber sortiert typischerweise aus wegen:\n"
                f"{formatted}\n"
                "Wenn die Stelle eines dieser Muster trifft, eher PASST_NICHT.\n"
            )

    # v1.7.0-beta.63 (#638 Stufe 3): KONKRETE Few-Shot-Beispiele.
    # Aggregat-Reasons (oben) zeigen das Muster, hier kommen die echten
    # Stellen-Titel + Firmen-Namen + Grund — das laesst die LLM
    # "warum diese und nicht jene" verstehen. Max 5 Beispiele um den
    # Prompt nicht zu sprengen.
    recent_dismissals = payload.get("recent_dismissals") or []
    fewshot_block = ""
    if recent_dismissals:
        examples = []
        for d in recent_dismissals[:5]:
            t = (d.get("title") or "").strip()
            c = (d.get("company") or "").strip()
            r = (d.get("dismiss_reason") or "").strip()
            if t or c:
                examples.append(
                    f"  - '{t}' bei '{c}' → PASST_NICHT (Grund: {r or 'unbekannt'})"
                )
        if examples:
            fewshot_block = (
                "\nBEISPIELE — diese Stellen hat der Bewerber zuletzt selbst abgelehnt:\n"
                + "\n".join(examples) + "\n"
                "Nutze diese Muster fuer die Bewertung der neuen Stelle.\n"
            )

    skills_str = ", ".join(profile_skills[:15]) if profile_skills else "keine erfasst"
    return (
        "Du bewertest ob eine Stelle zu einem Bewerber-Profil passt.\n\n"
        "PROFIL DES BEWERBERS:\n"
        f"  Aktuelle/letzte Position: {profile_position or 'keine erfasst'}\n"
        f"  Karriere-Stufe: {profile_seniority or 'unbekannt'}\n"
        f"  Top-Skills: {skills_str}\n"
        f"{learned_block}{fewshot_block}\n"
        "STELLE:\n"
        f"  Titel: {job_title}\n"
        f"  Firma: {job_company}\n"
        f"  Beschreibung (Auszug): {job_description}\n\n"
        "FRAGE: Wuerde es Sinn machen wenn diese Person sich auf diese Stelle "
        "bewirbt?\n\n"
        "Antworte AUSSCHLIESSLICH im Format (genau eine Zeile):\n"
        "ENTSCHEIDUNG | KURZBEGRUENDUNG\n\n"
        "ENTSCHEIDUNG ist eines von:\n"
        "  PASST           — Skills + Karriere-Stufe + Branche stimmen\n"
        "  PASST_NICHT     — falsche Branche, falsche Stufe (Junior bei "
        "Senior-Profil), oder Skills haben nichts gemeinsam\n"
        "  UNSICHER        — koennte passen, je nach Detail\n\n"
        "Beispiele:\n"
        "  PASST | Senior PLM-Architect-Profil + Stelle 'PLM Solution Architect' "
        "passt thematisch und auf Stufe.\n"
        "  PASST_NICHT | Senior-Profil mit 20J Erfahrung passt nicht zu einer "
        "Junior/Werkstudenten-Stelle als Technischer Zeichner.\n"
        "  UNSICHER | SAP-Bezug ist im Profil schwach, koennte mit Lerneffort gehen.\n\n"
        "DEINE ANTWORT:"
    )


def _clean_match_reason(reason: str) -> str:
    """Bereinigt die KURZBEGRUENDUNG aus der match_job_to_skills-Antwort.

    #691: Das 7B-Modell laesst gelegentlich den Prompt-Platzhalter
    'KURZBEGRUENDUNG' (oder eine Variante) woertlich stehen oder liefert eine
    leere Begruendung. Solche Faelle werden zu '' normalisiert, damit nie ein
    Platzhalter als echte Begruendung in research_notes / UI landet.
    """
    r = (reason or "").strip().strip(".,;:'\"`").strip()
    if not r:
        return ""
    if r.lower() in {
        "kurzbegruendung", "kurzbegrundung", "kurzbegründung",
        "begruendung", "begründung", "begrundung", "reason",
    }:
        return ""
    return r[:200]


def _parse_match_job_to_skills(raw: str) -> dict:
    raw_clean = (raw or "").strip()
    if not raw_clean:
        return {"decision": "UNSICHER", "reason": "Keine LLM-Antwort", "raw": raw}
    # Erste nicht-leere Zeile + entlang | splitten
    line = next((l.strip() for l in raw_clean.split("\n") if l.strip()), "")
    parts = [p.strip() for p in line.split("|", 1)]
    decision = parts[0].upper().strip(".,;:'\"`")
    reason = _clean_match_reason(parts[1] if len(parts) > 1 else "")
    if decision not in ("PASST", "PASST_NICHT", "UNSICHER"):
        # Versuche Auto-Heuristik aus dem Roh-Text
        lower = raw_clean.lower()
        if "passt nicht" in lower or "not match" in lower:
            decision = "PASST_NICHT"
        elif "passt" in lower:
            decision = "PASST"
        else:
            decision = "UNSICHER"
    return {
        "decision": decision,
        "reason": reason,
        "raw": raw,
    }


# v1.7.0-beta.28 (#594 Stufe 3): analyze_user_patterns — bekommt das
# Aggregat aus Stufe 2 und liefert max 3 verstaendliche Insights mit
# Empfehlung. Format ist strikt parseable.

def _build_analyze_user_patterns_prompt(payload: dict) -> str:
    import json as _json
    aggregate = payload.get("aggregate") or {}
    return (
        "Du analysierst das Nutzungs-Verhalten eines PBP-Nutzers und "
        "lieferst maximal 3 nachvollziehbare Insights mit Empfehlung.\n\n"
        "Merke: Klicks und Scroll sind Anti-Patterns (User sucht), lange "
        "Verweildauer ist gut (User liest).\n\n"
        f"Daten der letzten {aggregate.get('window_days', 30)} Tage:\n"
        f"{_json.dumps(aggregate, ensure_ascii=False, indent=2)[:3000]}\n\n"
        "Antworte AUSSCHLIESSLICH im Format (genau ein Insight pro Zeile, "
        "max 3 Zeilen):\n\n"
        "TYP|TITEL|EMPFEHLUNG\n\n"
        "TYP ist eines von:\n"
        "  filter_recommendation — wiederkehrender Filter koennte Default werden\n"
        "  ux_friction          — Anti-Pattern (viele Klicks, hoher Abort)\n"
        "  workflow_optimization — Workflow ist auffaellig haeufig/abgebrochen\n"
        "  dismiss_pattern      — Aussortier-Muster zeigt etwas Besonderes\n"
        "  positive_signal      — User-Verhalten zeigt Mastery, kein Eingriff noetig\n\n"
        "Beispiele:\n"
        "filter_recommendation|Score-Filter ueber 70 als Default|Du wendest filter_score>=70 fast jedes Mal an. PBP koennte das als Default setzen.\n"
        "ux_friction|Stellen-Seite hat 12 Klicks pro Besuch|Vermutlich findest du nicht direkt was du suchst — engere Filter koennten helfen.\n"
        "dismiss_pattern|85% deiner Aussortierungen sind 'falsches_fachgebiet'|PBP koennte Stellen mit dem Begriff im Titel automatisch vorfiltern.\n\n"
        "Wenn KEIN Pattern interessant genug ist: gib nur eine leere Zeile zurueck.\n\n"
        "DEINE ANTWORT:"
    )


def _parse_analyze_user_patterns(raw: str) -> dict:
    valid_types = {
        "filter_recommendation", "ux_friction", "workflow_optimization",
        "dismiss_pattern", "positive_signal",
    }
    insights = []
    for line in (raw or "").split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) < 3:
            continue
        t, title, recommendation = parts
        t = t.lower().strip(".,;:'\"`")
        if t not in valid_types:
            continue
        if not title or not recommendation:
            continue
        insights.append({
            "kind": t,
            "title": title[:120],
            "recommendation": recommendation[:300],
            # v1.7.0-beta.29 (#594 Stufe 4): Heuristische Page-Zuordnung
            # damit AdaptiveHintBanner weiss, wo das Insight gehoert.
            "scope": _heuristic_scope_for_insight(t, title, recommendation),
        })
        if len(insights) >= 3:
            break
    return {"insights": insights, "count": len(insights), "raw": raw}


def _heuristic_scope_for_insight(kind: str, title: str, recommendation: str) -> str:
    """Heuristik: Aus Titel + Empfehlung + Kind die wahrscheinliche Seite
    ableiten, fuer die das Insight relevant ist. Wird vom Frontend
    fuer den AdaptiveHintBanner genutzt.

    Rueckgabewerte: "page:dashboard" | "page:stellen" | "page:bewerbungen"
                    | "page:profil" | "page:einstellungen" | "page:kontakte"
                    | "global" (kein klares Match)
    """
    text = f"{title} {recommendation}".lower()
    # Reihenfolge: spezifischer zuerst
    if any(k in text for k in ("stelle", "job", "score", "filter", "aussortier", "dismiss")):
        return "page:stellen"
    if any(k in text for k in ("bewerbung", "anschreiben", "follow-up", "follow up")):
        return "page:bewerbungen"
    if any(k in text for k in ("profil", "skill", "lebenslauf")):
        return "page:profil"
    if any(k in text for k in ("kontakt", "recruiter", "linkedin")):
        return "page:kontakte"
    if any(k in text for k in ("einstellung", "lokale ai", "modell", "ollama")):
        return "page:einstellungen"
    if kind == "ux_friction":
        return "page:dashboard"
    return "global"


# v1.7.0-beta.24 (NEU): classify_email — eingehende Mails zu Bewerbungs-
# Mails klassifizieren (Antwort, Eingangsbestaetigung, Absage, Spam, etc.)

def _build_classify_email_prompt(payload: dict) -> str:
    sender = (payload.get("sender") or "").strip()[:100]
    subject = (payload.get("subject") or "").strip()[:200]
    body = (payload.get("body") or "")[:2000]
    return (
        "Du klassifizierst eine eingehende Bewerbungs-E-Mail.\n\n"
        f"Absender: {sender}\n"
        f"Betreff: {subject}\n\n"
        f"Body (Auszug):\n{body}\n\n"
        "Antworte AUSSCHLIESSLICH mit einer Kategorie aus:\n"
        "  eingangsbestaetigung — automatischer Empfangsbestaetigung\n"
        "  einladung_interview  — Interview/Kennenlerngespraech-Einladung\n"
        "  absage              — Bewerbung abgelehnt\n"
        "  rueckfrage          — Recruiter fragt nach Unterlagen oder Termin\n"
        "  angebot             — Vertragsangebot\n"
        "  newsletter          — Job-Newsletter / Marketing\n"
        "  spam                — Phishing oder Werbung\n"
        "  sonstiges           — sonstige Mail im Bewerbungs-Kontext\n\n"
        "Kategorie:"
    )


def _parse_classify_email(raw: str) -> dict:
    valid = {
        "eingangsbestaetigung", "einladung_interview", "absage",
        "rueckfrage", "angebot", "newsletter", "spam", "sonstiges",
    }
    cleaned = (raw or "").strip().lower().split()[0] if raw else ""
    cleaned = cleaned.strip(".,;:'\"`")
    if cleaned not in valid:
        return {"category": "sonstiges", "confidence": 0.3, "raw": raw}
    return {"category": cleaned, "confidence": 0.85, "raw": raw}


# v1.7.0-beta.39 (#606): extract_contacts — extrahiert Personen aus
# Bewerbungs-/Mail-/Dokument-Texten. Format: PIPE-getrennt, eine Person
# pro Zeile. Kategorie wird aus Kontext abgeleitet, Confidence pro Zeile.

def _build_extract_contacts_prompt(payload: dict) -> str:
    """Baut Prompt fuer Kontakt-Extraktion aus Text + Kontext.

    payload = {
        text: str,                         # Bewerbung/Mail/Dokument
        context_company: str,              # bekannte Firma (falls schon)
        bekannte_kategorien: list[str],    # Slugs der vorhandenen Kategorien
    }
    """
    text = (payload.get("text") or "")[:3000]
    company = payload.get("context_company") or ""
    cats = payload.get("bekannte_kategorien") or [
        "recruiter", "hr", "ansprechpartner", "endkunde",
        "vermittler", "referenz", "sonstiges",
    ]
    return (
        "Du extrahierst Personen-Kontakte aus Bewerbungs-Mails, "
        "Anschreiben oder Recherche-Texten.\n\n"
        f"FIRMA-KONTEXT: {company or 'unbekannt'}\n\n"
        f"TEXT:\n{text}\n\n"
        "FRAGE: Welche realen Personen werden genannt?\n\n"
        "Antworte AUSSCHLIESSLICH eine Person pro Zeile, max 5 Personen, "
        "im Format:\n"
        "NAME | EMAIL | KATEGORIE | ROLLE | CONFIDENCE\n\n"
        "Wo:\n"
        "- NAME: Vor- und Nachname (Pflicht)\n"
        "- EMAIL: leer wenn nicht im Text genannt\n"
        f"- KATEGORIE: eines von {', '.join(cats)}\n"
        "- ROLLE: kurze Beschreibung (max 30 Zeichen)\n"
        "- CONFIDENCE: 0.1-1.0 (wie sicher bist du)\n\n"
        "Beispiele:\n"
        "Anna Mueller | a.mueller@acme.de | hr | Recruiterin ACME | 0.95\n"
        "Stefan Klein |  | ansprechpartner | Fachbereichs-Lead | 0.7\n\n"
        "Wenn KEINE Personen im Text: gib eine leere Zeile zurueck.\n"
        "DEINE ANTWORT:"
    )


def _parse_extract_contacts(raw: str) -> dict:
    valid_kategorien = {
        "recruiter", "hr", "ansprechpartner", "endkunde",
        "vermittler", "referenz", "sonstiges",
    }
    contacts: list[dict] = []
    for line in (raw or "").split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        # Padding mit leeren Strings falls Zeile kuerzer
        while len(parts) < 5:
            parts.append("")
        name, email, kategorie, rolle, conf_raw = parts[:5]
        if not name or len(name) < 3:
            continue
        kategorie = kategorie.lower().strip(".,;:'\"`")
        # Erlaubt auch Custom-Kategorien (User kann eigene definieren).
        # Defaults werden gegen die feste Liste geprueft.
        try:
            confidence = float(conf_raw) if conf_raw else 0.5
            confidence = max(0.0, min(1.0, confidence))
        except ValueError:
            confidence = 0.5
        contacts.append({
            "name": name[:120],
            "email": email if "@" in email else "",
            "kategorie": kategorie or "sonstiges",
            "rolle": rolle[:60],
            "confidence": confidence,
        })
        if len(contacts) >= 5:
            break
    return {"contacts": contacts, "count": len(contacts), "raw": raw}


def _build_validate_job_quality_prompt(payload: dict) -> str:
    """Prompt fuer Stellenbeschreibungs-Qualitaets-Check (#645).

    Input: {title, company, location, description, url, source}
    Erwartete Antwort (JSON):
      {
        "vollstaendig": true|false,
        "score": 0-10,
        "vorhanden": ["aufgaben", "anforderungen", "gehalt", "standort", "remote", "kontakt", "benefits"],
        "fehlt": ["..."],
        "begruendung": "kurz, 1-2 Saetze",
        "claude_action": "nachladen"|"manuell_ergaenzen"|"keine"
      }
    """
    title = (payload.get("title") or "")[:200]
    company = (payload.get("company") or "")[:120]
    location = (payload.get("location") or "")[:120]
    source = (payload.get("source") or "")[:40]
    url = (payload.get("url") or "")[:300]
    desc = (payload.get("description") or "")[:2500]
    return f"""Du bist ein Qualitaets-Validator fuer Stellenanzeigen-Daten.
Pruefe ob diese Stellenanzeige vollstaendig genug ist um eine Bewerbung zu erstellen.

STELLE:
Titel: {title}
Firma: {company}
Ort: {location}
Quelle: {source}
URL: {url}
Beschreibung:
{desc}

Pruefe ob folgende Inhalte erkennbar sind:
- aufgaben: Was sind die taeglichen Aufgaben?
- anforderungen: Welche Skills/Erfahrung wird verlangt?
- gehalt: Gehaltsangabe oder Range vorhanden?
- standort: Konkreter Ort genannt?
- remote: Remote/Hybrid/vor-Ort-Angabe vorhanden?
- kontakt: Ansprechperson oder Kontakt-Email/Telefon?
- benefits: Benefits oder Goodies erwaehnt?

Bewerte einen Vollstaendigkeits-Score von 0 (leer) bis 10 (perfekt).
Bewerte "vollstaendig": True ab Score 6.
Setze "claude_action":
  - "nachladen" wenn URL existiert und Beschreibung leer/zu kurz ist
    (Claude soll stellenbeschreibung_nachladen ausfuehren)
  - "manuell_ergaenzen" wenn URL fehlt oder dauerhaft nicht erreichbar
    (Claude soll User fragen oder via Websuche ergaenzen)
  - "keine" wenn alles fein

Antworte NUR mit einem JSON-Objekt. Kein Vorspann, keine Markdown-Codefence.
Beispiel:
{{"vollstaendig":true,"score":8,"vorhanden":["aufgaben","anforderungen","standort","remote"],"fehlt":["gehalt","kontakt","benefits"],"begruendung":"Klare Aufgabenbeschreibung und Anforderungen, Gehalt fehlt aber ueblich.","claude_action":"keine"}}
"""


def _parse_validate_job_quality(raw: str) -> dict:
    """Parse Ollama-Antwort fuer VALIDATE_JOB_QUALITY.

    Robust gegen Markdown-Codefences und Vor-/Nachspann.
    """
    import json
    import re as _re
    text = (raw or "").strip()
    # Codefence entfernen
    if text.startswith("```"):
        text = _re.sub(r"^```[a-z]*\s*", "", text)
        text = _re.sub(r"\s*```\s*$", "", text)
    # JSON-Block extrahieren (greedy match auf ersten { ... })
    m = _re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {
            "vollstaendig": False,
            "score": 0,
            "vorhanden": [],
            "fehlt": [],
            "begruendung": "LLM-Antwort nicht parsebar",
            "claude_action": "manuell_ergaenzen",
            "raw": raw[:300],
        }
    # Normalisierung
    out = {
        "vollstaendig": bool(data.get("vollstaendig")),
        "score": int(data.get("score") or 0),
        "vorhanden": list(data.get("vorhanden") or []),
        "fehlt": list(data.get("fehlt") or []),
        "begruendung": str(data.get("begruendung") or "")[:300],
        "claude_action": str(data.get("claude_action") or "keine"),
    }
    if out["claude_action"] not in ("nachladen", "manuell_ergaenzen", "keine"):
        out["claude_action"] = "keine"
    return out


_PROMPT_BUILDERS = {
    TaskKind.CLASSIFY_DOCUMENT: _build_classify_document_prompt,
    TaskKind.EXTRACT_SKILLS: _build_extract_skills_prompt,
    TaskKind.MATCH_JOB_TO_SKILLS: _build_match_job_to_skills_prompt,
    TaskKind.CLASSIFY_EMAIL: _build_classify_email_prompt,
    TaskKind.ANALYZE_USER_PATTERNS: _build_analyze_user_patterns_prompt,
    TaskKind.EXTRACT_CONTACTS: _build_extract_contacts_prompt,
    TaskKind.VALIDATE_JOB_QUALITY: _build_validate_job_quality_prompt,
}

_RESPONSE_PARSERS = {
    TaskKind.CLASSIFY_DOCUMENT: _parse_classify_document,
    TaskKind.EXTRACT_SKILLS: _parse_extract_skills,
    TaskKind.MATCH_JOB_TO_SKILLS: _parse_match_job_to_skills,
    TaskKind.CLASSIFY_EMAIL: _parse_classify_email,
    TaskKind.ANALYZE_USER_PATTERNS: _parse_analyze_user_patterns,
    TaskKind.EXTRACT_CONTACTS: _parse_extract_contacts,
    TaskKind.VALIDATE_JOB_QUALITY: _parse_validate_job_quality,
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
