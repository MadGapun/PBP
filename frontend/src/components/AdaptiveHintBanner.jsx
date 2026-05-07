/**
 * AdaptiveHintBanner — v1.7.0-beta.29 (#594 Stufe 4)
 *
 * Zeigt LLM-generierte Insights (kind=filter_recommendation, ux_friction,
 * dismiss_pattern, ...) direkt auf der Seite an, fuer die sie relevant sind.
 *
 * Usage:
 *   <AdaptiveHintBanner page="stellen" />
 *   <AdaptiveHintBanner page="bewerbungen" />
 *
 * Verhalten:
 * - Holt /api/learning/hints?page=<page>&limit=2 beim Mount
 * - Zeigt max 2 Hints, jeder dismissible mit X-Button
 * - localStorage gemerkt: pro Hint-ID nur 1× aussortiert
 * - Wenn keine Hints: nichts rendern (kein leeres Skelett)
 *
 * Privacy/UX:
 * - Hints sind nicht aufdringlich (kleine Zeile, dezente Farbe)
 * - User-Vorgabe: tief tracken, aber UI nur dann aendern wenn wirklich
 *   etwas Bedeutsames gelernt wurde — daher LLM-Threshold (50 Events,
 *   Stufe 3 in beta.28) gilt indirekt auch hier.
 */
import { useEffect, useState } from "react";
import { Lightbulb, X } from "lucide-react";

const STORAGE_KEY = "pbp_dismissed_hints_v1";

function readDismissedFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function persistDismissed(set) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  } catch {}
}

export default function AdaptiveHintBanner({ page, limit = 2, onApply }) {
  const [hints, setHints] = useState([]);
  const [dismissed, setDismissed] = useState(() => readDismissedFromStorage());

  useEffect(() => {
    let cancelled = false;
    if (!page) return;
    fetch(`/api/learning/hints?page=${encodeURIComponent(page)}&limit=${limit}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d) return;
        setHints(d.hints || []);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [page, limit]);

  function dismissLocal(id) {
    setDismissed((cur) => {
      const next = new Set(cur);
      next.add(id);
      persistDismissed(next);
      return next;
    });
  }

  async function dismissPermanent(id) {
    // Server-Dismiss: Insight wird auf is_active=0 gesetzt
    try {
      await fetch(`/api/learning/insights/${id}`, { method: "DELETE" });
    } catch {}
    dismissLocal(id);
  }

  const visible = hints.filter((h) => !dismissed.has(h.id));
  if (visible.length === 0) return null;

  return (
    <div className="space-y-1.5 mb-3">
      {visible.map((h) => (
        <div
          key={h.id}
          className="flex items-start gap-2 p-2.5 rounded-lg border border-teal/20 bg-teal/[0.04] text-[12px]"
        >
          <Lightbulb className="h-4 w-4 text-teal mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-teal/80">
                {(h.kind || "").replace(/_/g, " ")}
              </span>
              <span className="font-medium text-ink truncate">{h.title}</span>
            </div>
            {h.recommendation && (
              <p className="text-[11px] text-muted/70 mt-0.5">
                {h.recommendation}
              </p>
            )}
            <div className="flex items-center gap-3 mt-1.5">
              {onApply && h.kind === "filter_recommendation" && (
                <button
                  type="button"
                  onClick={() => onApply(h)}
                  className="text-[11px] text-teal hover:underline"
                >
                  Vorschlag anwenden
                </button>
              )}
              <button
                type="button"
                onClick={() => dismissPermanent(h.id)}
                className="text-[11px] text-muted/40 hover:text-coral"
              >
                Nicht mehr anzeigen
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={() => dismissLocal(h.id)}
            className="text-muted/40 hover:text-ink shrink-0"
            title="Fuer diese Sitzung ausblenden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
