import { Activity, BarChart3, Calendar, Clock, Download, TrendingUp } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, apiUrl, optionalApi } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  LinkButton,
  LoadingPanel,
  MetricCard,
  SelectInput,
} from "@/components/ui";
import { formatDate, formatDateTime, statusLabel } from "@/utils";

const STATUS_COLORS = {
  beworben: "#38bdf8",
  eingangsbestaetigung: "#38bdf8",
  interview: "#fbbf24",
  zweitgespraech: "#fbbf24",
  interview_abgeschlossen: "#14b8a6",
  angebot: "#34d399",
  abgelehnt: "#f87171",
  entwurf: "#94a3b8",
  zurueckgezogen: "#a78bfa",
  abgelaufen: "#94a3b8",
};

const SOURCE_COLORS = [
  "#38bdf8", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#60a5fa", "#facc15",
];

const DISMISS_COLORS = [
  "#f87171", "#fb923c", "#fbbf24", "#a78bfa", "#38bdf8",
  "#34d399", "#e879f9", "#94a3b8", "#2dd4bf", "#60a5fa",
];

const CHART_STYLE = {
  fontSize: 11,
  fill: "rgba(255,255,255,0.45)",
};

const TOOLTIP_STYLE = {
  background: "rgba(30,34,52,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12,
  fontSize: 12,
};

function ChartCard({ title, children }) {
  return (
    <Card className="rounded-2xl">
      <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
        {title}
      </p>
      {children}
    </Card>
  );
}

function StatBox({ label, value, sub, tone = "neutral" }) {
  const toneClasses = {
    sky: "border-sky/15 bg-sky/[0.06]",
    success: "border-teal/15 bg-teal/[0.06]",
    amber: "border-amber/15 bg-amber/[0.06]",
    danger: "border-coral/15 bg-coral/[0.06]",
    neutral: "border-white/[0.05] bg-white/[0.02]",
  };
  const valueClasses = {
    sky: "text-sky", success: "text-teal", amber: "text-amber",
    danger: "text-coral", neutral: "text-ink",
  };
  return (
    <div className={`rounded-lg border px-3 py-2.5 ${toneClasses[tone] || toneClasses.neutral}`}>
      <p className="text-[10px] uppercase tracking-[0.12em] text-muted/50">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${valueClasses[tone] || "text-ink"}`}>{value}</p>
      {sub && <p className="text-[10px] text-muted/40">{sub}</p>}
    </div>
  );
}

export default function StatsPage() {
  const { reloadKey, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [interval, setInterval_] = useState("all");
  const [timeline, setTimeline] = useState(null);
  const [scores, setScores] = useState(null);
  const [extended, setExtended] = useState(null);

  const loadData = useEffectEvent(async (selectedInterval) => {
    try {
      const [timelineData, scoreData, extendedData] = await Promise.all([
        optionalApi(`/api/stats/timeline?interval=${selectedInterval}`),
        optionalApi("/api/stats/scores"),
        optionalApi("/api/stats/extended"),
      ]);
      if (!timelineData && !scoreData && !extendedData) {
        pushToast("Server nicht erreichbar.", "danger");
        setLoading(false);
        return;
      }
      setTimeline(timelineData);
      setScores(scoreData);
      setExtended(extendedData);
      setLoading(false);
    } catch (error) {
      pushToast(`Statistiken konnten nicht geladen werden: ${error.message}`, "danger");
      setLoading(false);
    }
  });

  useEffect(() => {
    setLoading(true);
    loadData(interval);
  }, [reloadKey, interval]);

  if (loading) return <LoadingPanel label="Statistiken werden geladen..." />;

  // --- Timeline chart data ---
  // #358: Exclude incomplete current period to avoid misleading downward trend
  // #396: But keep it when it's the ONLY period, so charts aren't empty
  const currentPeriod = timeline?.current_period;
  const allPeriods = timeline?.periods || [];
  const timelinePeriods = allPeriods.length <= 1
    ? allPeriods
    : allPeriods.filter((p) => interval === "all" || p !== currentPeriod);

  // #396: Format period labels for readability (2026-W14 → KW 14, 2026-04-09 → 09.04.)
  function formatPeriodLabel(period) {
    const wMatch = period.match(/^\d{4}-W(\d+)$/);
    if (wMatch) return `KW ${parseInt(wMatch[1], 10)}`;
    const dMatch = period.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dMatch) return `${dMatch[3]}.${dMatch[2]}.`;
    const mMatch = period.match(/^(\d{4})-(\d{2})$/);
    if (mMatch) {
      const months = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
      return months[parseInt(mMatch[2], 10) - 1] + " " + mMatch[1].slice(2);
    }
    return period;
  }

  const timelineChartData = timelinePeriods.map((period) => ({
    name: formatPeriodLabel(period),
    Bewerbungen: timeline?.applications?.[period] || 0,
    "Neue Stellen": timeline?.jobs_found?.[period] || 0,
  }));

  // --- Status breakdown chart data ---
  const allStatuses = new Set();
  for (const period of timelinePeriods) {
    for (const status of Object.keys(timeline?.by_status?.[period] || {})) {
      allStatuses.add(status);
    }
  }
  const statusKeys = [...allStatuses];
  const statusLabels = statusKeys.map((s) => statusLabel(s));
  const statusChartData = timelinePeriods.map((period) => {
    const entry = { name: formatPeriodLabel(period) };
    for (let i = 0; i < statusKeys.length; i++) {
      entry[statusLabels[i]] = timeline?.by_status?.[period]?.[statusKeys[i]] || 0;
    }
    return entry;
  });

  // --- Source distribution pie data ---
  const sources = scores?.sources || [];
  const sourcePieData = sources.map((s) => ({
    name: s.name,
    value: s.count,
  }));

  // --- Score distribution bar data ---
  const scoreDistribution = scores?.score_distribution || {};
  const SCORE_BRACKET_ORDER = ["0", "1-3", "4-6", "7-9", "10+"];
  const scoreBarData = SCORE_BRACKET_ORDER
    .filter((bracket) => scoreDistribution[bracket] != null)
    .map((bracket) => ({ bucket: bracket, count: scoreDistribution[bracket] || 0 }));

  // --- Source-Score comparison bar data ---
  const sourceScoreData = sources
    .filter((s) => s.avg_score > 0)
    .map((s) => ({
      name: s.name,
      "Ø Score": Math.round(s.avg_score * 10) / 10,
      "Max Score": s.max_score || 0,
    }));

  // --- Dismiss reasons chart data ---
  const dismissData = (extended?.dismiss_reasons || []).slice(0, 10).map(([reason, count]) => ({
    name: reason,
    count,
  }));

  const hasData = timelineChartData.length > 0 || sourcePieData.length > 0 || scoreBarData.length > 0;
  const today = extended?.today || {};
  const week = extended?.this_week || {};
  const totals = extended?.totals || {};
  const appStats = extended?.applications || {};
  const response = extended?.response_times || {};

  return (
    <div id="page-statistiken" className="page active">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Statistiken</h1>
        <div className="flex flex-wrap items-center gap-2">
          {/* Quick-select Presets (#307) */}
          {[
            { label: "30 Tage", value: "day" },
            { label: "12 Wochen", value: "week" },
            { label: "12 Monate", value: "month" },
            { label: "Alles", value: "all" },
          ].map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => setInterval_(preset.value)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                interval === preset.value
                  ? "bg-sky/15 text-sky"
                  : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
              }`}
            >
              {preset.label}
            </button>
          ))}
          <SelectInput
            className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
            value={interval}
            onChange={(e) => setInterval_(e.target.value)}
          >
            <option value="day">Taeglich</option>
            <option value="week">Woechentlich</option>
            <option value="month">Monatlich</option>
            <option value="quarter">Quartalsweise</option>
            <option value="year">Jaehrlich</option>
            <option value="all">Komplett</option>
          </SelectInput>
          <LinkButton
            size="sm"
            href={apiUrl("/api/applications/export?format=pdf")}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            PDF
          </LinkButton>
          <LinkButton
            size="sm"
            href={apiUrl("/api/applications/export?format=xlsx")}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            Excel
          </LinkButton>
        </div>
      </div>

      {!hasData && !extended ? (
        <EmptyState
          title="Noch keine Daten"
          description="Sobald Bewerbungen und Stellen vorhanden sind, erscheinen hier Auswertungen."
        />
      ) : (
        <div className="grid gap-6">
          {/* Row 0: Activity overview — Today + Week + Totals */}
          {extended && (
            <div className="grid gap-6 xl:grid-cols-3">
              <Card className="rounded-2xl">
                <div className="flex items-center gap-2 mb-3">
                  <Calendar size={14} className="text-sky" />
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Heute</p>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <StatBox label="Gefunden" value={today.jobs_found || 0} tone="success" />
                  <StatBox label="Aussortiert" value={today.dismissed || 0} tone="danger" />
                  <StatBox label="Beworben" value={today.applied || 0} tone="sky" />
                </div>
              </Card>

              <Card className="rounded-2xl">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp size={14} className="text-teal" />
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Diese Woche</p>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <StatBox label="Gefunden" value={week.jobs_found || 0} tone="success" />
                  <StatBox label="Aussortiert" value={week.dismissed || 0} tone="danger" />
                  <StatBox label="Beworben" value={week.applied || 0} tone="sky" />
                </div>
              </Card>

              <Card className="rounded-2xl">
                <div className="flex items-center gap-2 mb-3">
                  <BarChart3 size={14} className="text-amber" />
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
                    Gesamt{extended.start_date ? ` (seit ${formatDate(extended.start_date)})` : ""}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <StatBox label="Stellen gesamt" value={totals.jobs_ever || 0} tone="neutral" />
                  <StatBox label="Aktiv" value={totals.jobs_active || 0} tone="success" />
                  <StatBox label="Beworben" value={totals.jobs_applied || 0} sub={totals.hit_rate ? `${totals.hit_rate}% Trefferquote` : ""} tone="sky" />
                  <StatBox label="Aussortiert" value={totals.jobs_dismissed || 0} sub={totals.dismiss_rate ? `${totals.dismiss_rate}%` : ""} tone="danger" />
                  <StatBox label="Gepinnt" value={totals.jobs_pinned || 0} tone="amber" />
                </div>
              </Card>
            </div>
          )}

          {/* Row 0b: Applications + Response times */}
          {extended && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <MetricCard label="Bewerbungen gesamt" value={appStats.total || 0} note={appStats.imported ? `${appStats.imported} importiert, ${appStats.new || 0} neu` : "Alle im Tool erstellt"} tone="sky" />
              <MetricCard label="Importiert" value={appStats.imported || 0} note="Vor Tool-Nutzung" tone="neutral" />
              <MetricCard label="Neu erstellt" value={appStats.new || 0} note="Seit Tool-Nutzung" tone="success" />
              <MetricCard
                label={"Ø Antwortzeit"}
                value={response.average_days != null ? `${response.average_days} Tage` : "k.A."}
                note={response.sample_size ? `Basierend auf ${response.sample_size} Rueckmeldungen` : "Noch keine Daten"}
                tone="amber"
              />
              <MetricCard
                label="Schnellste Antwort"
                value={response.fastest_days != null ? `${response.fastest_days} Tage` : "k.A."}
                note={response.slowest_days != null ? `Langsamste: ${response.slowest_days} Tage` : ""}
                tone="success"
              />
            </div>
          )}

          {/* Row 1: Timeline + Status */}
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard title="Bewerbungen & Stellen im Zeitverlauf">
              {timelineChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={timelineChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" tick={CHART_STYLE} />
                    <YAxis tick={CHART_STYLE} allowDecimals={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "rgba(255,255,255,0.7)" }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Area type="monotone" dataKey="Bewerbungen" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.15} strokeWidth={2} />
                    <Area type="monotone" dataKey="Neue Stellen" stroke="#34d399" fill="#34d399" fillOpacity={0.1} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted/40">Keine Zeitraumdaten vorhanden.</p>
              )}
            </ChartCard>

            <ChartCard title="Status-Verteilung im Zeitverlauf">
              {statusChartData.length > 0 && statusKeys.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={statusChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" tick={CHART_STYLE} />
                    <YAxis tick={CHART_STYLE} allowDecimals={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "rgba(255,255,255,0.7)" }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {statusKeys.map((status, i) => (
                      <Bar key={status} dataKey={statusLabels[i]} stackId="status" fill={STATUS_COLORS[status] || "#94a3b8"} radius={[2, 2, 0, 0]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted/40">Keine Statusdaten vorhanden.</p>
              )}
            </ChartCard>
          </div>

          {/* Row 2: Sources pie + Score distribution */}
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard title="Quellen-Verteilung">
              {sourcePieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={sourcePieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      innerRadius={50}
                      paddingAngle={2}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                      labelLine={{ stroke: "rgba(255,255,255,0.2)" }}
                    >
                      {sourcePieData.map((entry, i) => (
                        <Cell key={i} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} cursor="pointer" onClick={() => navigateTo("stellen")} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted/40">Keine Quellendaten vorhanden.</p>
              )}
            </ChartCard>

            <ChartCard title="Score-Verteilung">
              {scoreBarData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={scoreBarData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="bucket" tick={CHART_STYLE} label={{ value: "Score", position: "insideBottom", offset: -2, style: CHART_STYLE }} />
                    <YAxis tick={CHART_STYLE} allowDecimals={false} />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      labelStyle={{ color: "rgba(255,255,255,0.7)" }}
                      formatter={(value) => [value, "Stellen"]}
                      labelFormatter={(label) => `Score-Bereich ${label}`}
                    />
                    <Bar dataKey="count" fill="#fbbf24" radius={[4, 4, 0, 0]}>
                      {scoreBarData.map((_, i) => (
                        <Cell key={i} fill={`hsl(${40 + i * 8}, 90%, 60%)`} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted/40">Keine Score-Daten vorhanden.</p>
              )}
            </ChartCard>
          </div>

          {/* Row 2b: Application Sources + Dismiss Reasons */}
          <div className="grid gap-6 xl:grid-cols-2">
            {(scores?.application_sources || []).length > 0 && (
              <ChartCard title="Bewerbungs-Quellen">
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={scores.application_sources.map((s) => ({ name: s.name, value: s.count }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      innerRadius={50}
                      paddingAngle={2}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                      labelLine={{ stroke: "rgba(255,255,255,0.2)" }}
                    >
                      {scores.application_sources.map((_, i) => (
                        <Cell key={i} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
            )}

            {dismissData.length > 0 && (
              <ChartCard title="Ablehnungsgruende (Top 10)">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={dismissData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis type="number" tick={CHART_STYLE} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" tick={CHART_STYLE} width={140} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "rgba(255,255,255,0.7)" }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {dismissData.map((_, i) => (
                        <Cell key={i} fill={DISMISS_COLORS[i % DISMISS_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
          </div>

          {/* Row 3: Source-Score comparison */}
          {sourceScoreData.length > 0 ? (
            <ChartCard title="Durchschnittsscore nach Quelle">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={sourceScoreData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis type="number" tick={CHART_STYLE} />
                  <YAxis type="category" dataKey="name" tick={CHART_STYLE} width={100} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "rgba(255,255,255,0.7)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey={"Ø Score"} fill="#38bdf8" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="Max Score" fill="#34d399" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          ) : null}

          {/* Row 4: Recent activity */}
          {(extended?.recent_activity || []).length > 0 && (
            <Card className="rounded-2xl">
              <div className="flex items-center gap-2 mb-3">
                <Activity size={14} className="text-sky" />
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Letzte Aktivitaet</p>
              </div>
              <div className="grid gap-1.5">
                {extended.recent_activity.map((event, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-white/[0.04] px-3 py-2 text-sm">
                    <span className="shrink-0 text-[11px] text-muted/40 tabular-nums w-28">{formatDateTime(event.event_date)}</span>
                    <Badge tone={event.status === "notiz" ? "neutral" : event.status === "abgelehnt" ? "danger" : event.status === "interview" ? "amber" : "sky"}>
                      {event.status || "Event"}
                    </Badge>
                    <span className="flex-1 truncate text-ink font-medium">{event.title} — {event.company}</span>
                    {event.notes && <span className="shrink-0 max-w-48 truncate text-xs text-muted/50">{event.notes}</span>}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
