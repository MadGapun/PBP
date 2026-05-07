// v1.7.0-beta.26 (#594 Stufe 1): Activity-Tracking-Hook
//
// Sammelt UI-Events lokal in einer Buffer-Queue und schickt sie alle 10s
// als Batch an das Backend. Wird beim App-Mount initialisiert.
//
// Designprinzipien (User-Vorgabe):
// - Default On, aber jederzeit ausschaltbar via Setting
// - Tracking TIEF: Klicks, Tab-Wechsel, Filter, Verweildauer, Scroll
// - Anti-Pattern-Logik: viele Klicks/Scroll + kurze Verweildauer = User sucht
// - Performance < 50ms Impact pro UI-Interaktion
// - Alles lokal, keine externen Calls

const FLUSH_INTERVAL_MS = 10_000;
const MAX_BUFFER_SIZE = 200;

let _buffer = [];
let _sessionId = null;
let _appVersion = "unknown";
let _enabled = null; // null = noch nicht initialisiert
let _flushTimerId = null;
let _initialized = false;

function _now() {
  return new Date().toISOString();
}

function _getSessionId() {
  if (_sessionId) return _sessionId;
  try {
    const stored = sessionStorage.getItem("pbp_activity_session");
    if (stored) {
      _sessionId = stored;
      return _sessionId;
    }
  } catch {}
  _sessionId = "s-" + Math.random().toString(36).slice(2, 14) + "-" + Date.now();
  try { sessionStorage.setItem("pbp_activity_session", _sessionId); } catch {}
  return _sessionId;
}

async function _flush() {
  if (!_buffer.length) return;
  const events = _buffer.splice(0, _buffer.length);
  try {
    const r = await fetch("/api/activity/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events }),
    });
    if (!r.ok) {
      // Bei 4xx/5xx Buffer nicht weiter aufblähen — verwerfen
      return;
    }
    const j = await r.json();
    if (j?.status === "disabled") {
      // Tracking serverseitig deaktiviert → Hook schaltet sich aus
      _enabled = false;
      _stopFlushTimer();
    }
  } catch {
    // Server nicht erreichbar — Events verworfen, beim naechsten Flush neue
  }
}

function _startFlushTimer() {
  if (_flushTimerId) return;
  _flushTimerId = window.setInterval(_flush, FLUSH_INTERVAL_MS);
}

function _stopFlushTimer() {
  if (_flushTimerId) {
    window.clearInterval(_flushTimerId);
    _flushTimerId = null;
  }
}

export function initActivityTracking(appVersion) {
  if (_initialized) return;
  _initialized = true;
  _appVersion = appVersion || "unknown";

  // Init: Setting laden
  fetch("/api/settings/learning")
    .then((r) => r.ok ? r.json() : null)
    .then((d) => {
      _enabled = d?.learning_enabled !== false;
      if (_enabled) _startFlushTimer();
    })
    .catch(() => { _enabled = false; });

  // Beim Tab-Schließen letzten Buffer flushen via beacon
  window.addEventListener("beforeunload", () => {
    if (!_enabled || !_buffer.length) return;
    try {
      const events = _buffer.splice(0, _buffer.length);
      const blob = new Blob(
        [JSON.stringify({ events })],
        { type: "application/json" }
      );
      navigator.sendBeacon("/api/activity/track", blob);
    } catch {}
  });
}

export function setLearningEnabled(enabled) {
  _enabled = !!enabled;
  if (_enabled) {
    _startFlushTimer();
  } else {
    _stopFlushTimer();
    _buffer = []; // Buffer leeren bei Deaktivierung
  }
}

export function trackEvent(eventType, options = {}) {
  if (_enabled === false) return;  // explizit deaktiviert
  // Wenn _enabled noch null (Setting noch nicht geladen): trotzdem buffern,
  // wird beim Init entweder ge-flushed oder verworfen
  if (_buffer.length >= MAX_BUFFER_SIZE) {
    // Buffer voll — aelteste Events verwerfen (FIFO)
    _buffer.splice(0, 50);
  }
  _buffer.push({
    event_type: eventType,
    entity_type: options.entityType || null,
    entity_id: options.entityId || null,
    page: options.page || null,
    action: options.action || null,
    metadata: options.metadata || null,
    session_id: _getSessionId(),
    app_version: _appVersion,
    timestamp: _now(),
  });
}

// Pre-baked Helpers fuer haeufige Events
export const track = {
  pageView: (page) => trackEvent("page_view", { page }),
  click: (page, action, metadata) =>
    trackEvent("click", { page, action, metadata }),
  filterApply: (page, filterName, filterValue) =>
    trackEvent("filter_apply", {
      page,
      action: "filter_apply",
      metadata: { filter: filterName, value: String(filterValue).slice(0, 100) },
    }),
  workflowStart: (workflowId) =>
    trackEvent("workflow_start", { action: workflowId }),
  workflowAbort: (workflowId, reason) =>
    trackEvent("workflow_abort", {
      action: workflowId,
      metadata: { reason: reason || "" },
    }),
  workflowComplete: (workflowId) =>
    trackEvent("workflow_complete", { action: workflowId }),
  // Scroll (gedrosselt — alle 1s max)
  scroll: (() => {
    let lastTs = 0;
    return (page, scrollY, maxScrollY) => {
      const now = Date.now();
      if (now - lastTs < 1000) return;
      lastTs = now;
      trackEvent("scroll", {
        page,
        metadata: {
          y: scrollY,
          y_pct: maxScrollY > 0 ? Math.round((scrollY / maxScrollY) * 100) : 0,
        },
      });
    };
  })(),
  // Verweildauer (beim Tab-Wechsel automatisch)
  dwell: (page, durationMs) =>
    trackEvent("dwell", {
      page,
      metadata: { duration_ms: Math.round(durationMs) },
    }),
  // LLM-User-Korrektur (z.B. wenn User stelle_bewerten('passt') nach
  // Auto-Aussortierung als 'passt_nicht' macht)
  llmCorrection: (taskKind, originalDecision, userDecision, entityId) =>
    trackEvent("llm_correction", {
      entity_type: "job",
      entity_id: entityId,
      action: "llm_correction",
      metadata: {
        task: taskKind,
        original: originalDecision,
        corrected_to: userDecision,
      },
    }),
};

export function getEnabledStatus() {
  return _enabled;
}

// Manueller Flush (z.B. von Tests oder beim Logout)
export async function flushNow() {
  await _flush();
}
