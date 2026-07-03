/**
 * OnboardingHintBanner — v1.7.5 (#652, G11)
 *
 * Zeigt Onboarding-Hints fuer ungenutzte Features direkt auf dem Tab,
 * fuer den sie relevant sind. Das Backend (services/onboarding_hints.py)
 * existierte seit beta.76 — diese Komponente macht die Hints erstmals
 * sichtbar. Leitlinie: der User soll immer den naechsten logischen
 * Schritt sehen (Hover-Titel erklaeren jede Aktion).
 *
 * Usage:
 *   <OnboardingHintBanner tab="dashboard" />
 *   <OnboardingHintBanner tab="stellen" />
 *
 * Verhalten:
 * - Holt /api/onboarding/hints?tab=<tab> beim Mount
 * - "Nicht mehr anzeigen" dismisst PERSISTENT (DELETE /api/onboarding/hints/{id},
 *   gleicher Speicher wie das MCP-Tool onboarding_hint_dismiss)
 * - X-Button blendet nur fuer die Sitzung aus (localStorage)
 * - Keine Hints -> nichts rendern
 * - Abgrenzung zum AdaptiveHintBanner (#594): dort KI-gelernte Insights,
 *   hier kuratierte Feature-Führung. Bewusst eigene, waermere Optik.
 */
import { useEffect, useState } from "react";
import { Compass, X } from "lucide-react";

const STORAGE_KEY = "pbp_session_hidden_onboarding_hints_v1";

function readHidden() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function persistHidden(set) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  } catch {}
}

export default function OnboardingHintBanner({ tab, limit = 2 }) {
  const [hints, setHints] = useState([]);
  const [hidden, setHidden] = useState(() => readHidden());

  useEffect(() => {
    let cancelled = false;
    if (!tab) return;
    fetch(`/api/onboarding/hints?tab=${encodeURIComponent(tab)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d) return;
        setHints((d.hints || []).slice(0, limit));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [tab, limit]);

  function hideForSession(id) {
    setHidden((cur) => {
      const next = new Set(cur);
      next.add(id);
      persistHidden(next);
      return next;
    });
  }

  async function dismissPermanent(id) {
    try {
      await fetch(`/api/onboarding/hints/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    } catch {}
    hideForSession(id);
  }

  const visible = hints.filter((h) => !hidden.has(h.id));
  if (visible.length === 0) return null;

  return (
    <div className="space-y-1.5 mb-3">
      {visible.map((h) => (
        <div
          key={h.id}
          className="flex items-start gap-2 p-2.5 rounded-lg border border-amber-400/25 bg-amber-400/[0.06] text-[12px]"
        >
          <Compass className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="font-medium text-ink">{h.title}</span>
            <p className="text-[11px] text-muted/80 mt-0.5">{h.body}</p>
            <div className="flex items-center gap-3 mt-1.5">
              <span
                className="text-[11px] text-amber-600"
                title={`Einfach in Claude Desktop tippen — Claude nutzt dann ${h.cta_tool || "das passende Werkzeug"}.`}
              >
                💬 Sag Claude: „{h.cta_label}"
              </span>
              <button
                type="button"
                onClick={() => dismissPermanent(h.id)}
                className="text-[11px] text-muted/40 hover:text-coral"
                title="Diesen Tipp dauerhaft ausblenden"
              >
                Nicht mehr anzeigen
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={() => hideForSession(h.id)}
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
