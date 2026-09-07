/**
 * "Was PBP gelernt hat" — v1.7.35 (#985)
 *
 * Stand bis v1.7.34 auf dem Dashboard. Nutzerhinweis vom 07.09.2026:
 *
 *   "Was PBP gelernt hat... gehoert das nicht eher in die Statistiken,
 *   ist keine Funktion drin."
 *
 * Stimmt: der Block zeigt eine Auswertung und bietet keine Handlung an,
 * die man von hier aus ausloest. Auf dem Dashboard steht, was zu TUN
 * ist; was zu SEHEN ist, gehoert zu den Statistiken.
 */
import { useEffect, useState } from "react";

import { api } from "@/api";
import { Card } from "@/components/ui";

// v1.7.0-beta.27 (#594 Stufe 2): „Was PBP ueber dich gelernt hat"
// Zeigt Aggregat aus user_activity_events der letzten 30 Tage:
// Top-Pages mit Klicks/Verweildauer, Workflow-Stats, Top-Filter,
// Top-Dismiss-Reasons. Plus Anti-Pattern-Hinweise wenn erkannt.
// Card wird ausgeblendet bei < 50 Events (zu wenig Daten fuer Insights).
export default function LearningInsightsCard({ pushToast, navigateTo }) {
  const [data, setData] = useState(null);
  const [llmInsights, setLlmInsights] = useState([]);
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/activity/aggregate?days=30")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {});
    // v1.7.0-beta.28 (#594 Stufe 3): LLM-Insights nachladen wenn vorhanden
    fetch("/api/learning/insights?only_active=1&limit=10")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (!cancelled && d?.insights) setLlmInsights(d.insights); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const dismissInsight = async (id) => {
    try {
      const r = await fetch(`/api/learning/insights/${id}`, { method: "DELETE" });
      if (r.ok) {
        setLlmInsights((cur) => cur.filter((x) => x.id !== id));
      }
    } catch {}
  };

  if (!data) return null;
  // Mindestens 50 Events oder ein Anti-Pattern oder ein LLM-Insight,
  // sonst kein Mehrwert.
  if (
    data.total_events < 50
    && (data.anti_patterns || []).length === 0
    && llmInsights.length === 0
  ) {
    return null;
  }

  return (
    <Card className="rounded-2xl">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between"
      >
        <div className="text-left">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
            Was PBP gelernt hat
          </p>
          <p className="text-sm text-ink mt-1">
            {data.total_events} Events in {data.window_days} Tagen
            {data.anti_patterns?.length > 0 && (
              <span className="ml-2 text-amber">
                · {data.anti_patterns.length} Hinweis{data.anti_patterns.length === 1 ? "" : "e"}
              </span>
            )}
            {llmInsights.length > 0 && (
              <span className="ml-2 text-teal">
                · {llmInsights.length} KI-Insight{llmInsights.length === 1 ? "" : "s"}
              </span>
            )}
          </p>
        </div>
        <span className="text-muted/40 text-xs">{collapsed ? "▼" : "▲"}</span>
      </button>

      {!collapsed && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {/* Top-Pages */}
          {data.top_pages?.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-muted/70 uppercase mb-2">Top-Seiten</p>
              <div className="space-y-1.5">
                {data.top_pages.map((p) => (
                  <div key={p.page} className="glass-card p-2 text-[12px]">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink">{p.page}</span>
                      <span className="text-muted/50">{p.views}× besucht</span>
                    </div>
                    <p className="text-[11px] text-muted/60 mt-0.5">
                      {p.dwell_minutes} min Verweildauer · {p.clicks_per_view} Klicks/Besuch
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top-Dismiss-Reasons */}
          {data.dismiss_reasons_top?.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-muted/70 uppercase mb-2">
                Top-Aussortier-Gruende
              </p>
              <div className="space-y-1.5">
                {data.dismiss_reasons_top.map((r) => (
                  <div key={r.reason} className="glass-card p-2 text-[12px] flex items-center justify-between">
                    <span className="font-medium text-ink">{r.reason}</span>
                    <span className="text-muted/50">{r.count}×</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top-Filters */}
          {data.top_filters?.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-muted/70 uppercase mb-2">Haeufige Filter</p>
              <div className="space-y-1.5">
                {data.top_filters.map((f) => (
                  <div key={f.filter} className="glass-card p-2 text-[12px] flex items-center justify-between">
                    <span className="font-mono text-ink">{f.filter}</span>
                    <span className="text-muted/50">{f.count}×</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Workflow-Stats */}
          {Object.keys(data.workflow_stats || {}).length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-muted/70 uppercase mb-2">Workflows</p>
              <div className="space-y-1.5">
                {Object.entries(data.workflow_stats).map(([wf, stats]) => {
                  const total = stats.start || 0;
                  const completed = stats.complete || 0;
                  const aborted = stats.abort || 0;
                  const rate = total > 0 ? Math.round((completed / total) * 100) : 0;
                  return (
                    <div key={wf} className="glass-card p-2 text-[12px]">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink">{wf}</span>
                        <span className={
                          rate >= 70 ? "text-teal" :
                          rate >= 40 ? "text-amber" : "text-coral"
                        }>{rate}%</span>
                      </div>
                      <p className="text-[11px] text-muted/50 mt-0.5">
                        {total} gestartet · {completed} abgeschlossen · {aborted} abgebrochen
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* LLM-Insights (v1.7.0-beta.28 / #594 Stufe 3) */}
          {llmInsights.length > 0 && (
            <div className="lg:col-span-2">
              <p className="text-[11px] font-semibold text-teal/80 uppercase mb-2">
                KI-Erkenntnisse aus deinem Verhalten
              </p>
              <div className="space-y-1.5">
                {llmInsights.map((ins) => (
                  <div
                    key={ins.id}
                    className="glass-card p-3 text-[12px] border-teal/20 bg-teal/[0.03]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-teal/10 text-teal">
                            {ins.kind?.replace(/_/g, " ")}
                          </span>
                          <span className="font-medium text-ink">{ins.title}</span>
                        </div>
                        {ins.recommendation && (
                          <p className="text-[11px] text-muted/70 mt-1.5">
                            {ins.recommendation}
                          </p>
                        )}
                        <p className="text-[10px] text-muted/40 mt-1">
                          {ins.observed_count}× beobachtet
                          {ins.app_version_at_creation && ` · seit v${ins.app_version_at_creation}`}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => dismissInsight(ins.id)}
                        className="text-[10px] text-muted/40 hover:text-coral"
                        title="Nicht mehr anzeigen"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Anti-Patterns */}
          {data.anti_patterns?.length > 0 && (
            <div className="lg:col-span-2">
              <p className="text-[11px] font-semibold text-amber/80 uppercase mb-2">
                Beobachtungen
              </p>
              <div className="space-y-1.5">
                {data.anti_patterns.map((ap, i) => (
                  <div key={i} className="glass-card p-3 text-[12px] border-amber/20 bg-amber/[0.03]">
                    <p className="text-muted/80">{ap.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
