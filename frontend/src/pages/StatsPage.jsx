import { Activity, BarChart3, Calendar, Clock, Download, PenLine, TrendingUp } from "lucide-react";
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

function resolveTimeRangeDates(range) {
  if (!range) return { from: "", to: "" };
  const now = new Date();
  const to = now.toISOString().slice(0, 10);
  const start = new Date(now);
  if (range === "30d") start.setDate(start.getDate() - 30);
  else if (range === "90d") start.setDate(start.getDate() - 90);
  else if (range === "6m") start.setMonth(start.getMonth() - 6);
  else if (range === "12m") start.setMonth(start.getMonth() - 12);
  else return { from: "", to: "" };
  return { from: start.toISOString().slice(0, 10), to };
}

function buildExportUrl(format, timeRange, customFrom, customTo) {
  const params = new URLSearchParams({ format });
  // v1.6.6: explizites von-bis hat Vorrang vor dem Preset-Range
  if (customFrom || customTo) {
    if (customFrom) params.set("from", customFrom);
    if (customTo) params.set("to", customTo);
  } else {
    const { from, to } = resolveTimeRangeDates(timeRange);
    if (from) params.set("from", from);
    if (to) params.set("to", to);
  }
  return `/api/applications/export?${params.toString()}`;
}

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

// v1.7.0-beta.12 (#579): GitHub-Style Activity Heatmap
function ActivityHeatmap({ data, days }) {
  const dataByDate = new Map((data || []).map((d) => [d.date, d]));
  const today = new Date();
  // Wochenraster aufbauen — letzte X Tage, ausgerichtet auf Montag-Sonntag
  const cells = [];
  const start = new Date(today);
  start.setDate(start.getDate() - (days - 1));
  // Auf Montag der Startwoche zurueckspringen
  const startDow = (start.getDay() + 6) % 7; // 0=Mo .. 6=So
  start.setDate(start.getDate() - startDow);
  const cur = new Date(start);
  while (cur <= today) {
    const iso = cur.toISOString().slice(0, 10);
    const inRange = (today - cur) / 86400000 <= days;
    cells.push({ date: iso, entry: inRange ? dataByDate.get(iso) : null, inRange });
    cur.setDate(cur.getDate() + 1);
  }
  // In Wochen-Spalten (7 Zeilen) gruppieren
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const max = Math.max(1, ...((data || []).map((d) => d.count || 0)));
  function bucket(count) {
    if (!count) return 0;
    const ratio = count / max;
    if (ratio < 0.25) return 1;
    if (ratio < 0.5) return 2;
    if (ratio < 0.75) return 3;
    return 4;
  }
  const colors = [
    "rgba(255,255,255,0.04)",
    "rgba(56,189,248,0.25)",
    "rgba(56,189,248,0.5)",
    "rgba(56,189,248,0.75)",
    "rgba(56,189,248,1)",
  ];

  // Monatslabels: Index der ersten Woche pro Monat
  const monthLabels = [];
  let lastMonth = -1;
  weeks.forEach((week, i) => {
    const firstInRange = week.find((c) => c.inRange);
    if (!firstInRange) return;
    const m = new Date(firstInRange.date).getMonth();
    if (m !== lastMonth) {
      monthLabels.push({ index: i, label: ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"][m] });
      lastMonth = m;
    }
  });

  return (
    <div className="overflow-x-auto">
      <div className="inline-flex flex-col gap-1">
        <div className="ml-7 flex gap-[3px] text-[9px] text-muted/40">
          {weeks.map((_, i) => {
            const lbl = monthLabels.find((m) => m.index === i);
            return (
              <div key={i} className="w-[11px] text-left">
                {lbl ? lbl.label : ""}
              </div>
            );
          })}
        </div>
        <div className="flex gap-[3px]">
          <div className="flex flex-col justify-between pr-1 text-[9px] text-muted/40">
            <span>Mo</span>
            <span>Mi</span>
            <span>Fr</span>
            <span>So</span>
          </div>
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[3px]">
              {week.map((cell, di) => {
                const count = cell.entry?.count || 0;
                const b = cell.inRange ? bucket(count) : 0;
                const tip = cell.inRange
                  ? `${cell.date}: ${count} Aktion${count !== 1 ? "en" : ""}`
                  : "";
                return (
                  <div
                    key={di}
                    title={tip}
                    className="h-[11px] w-[11px] rounded-[2px]"
                    style={{
                      background: colors[b],
                      opacity: cell.inRange ? 1 : 0.3,
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
        <div className="ml-7 mt-1 flex items-center gap-2 text-[10px] text-muted/40">
          <span>weniger</span>
          {colors.map((c, i) => (
            <div key={i} className="h-[10px] w-[10px] rounded-[2px]" style={{ background: c }} />
          ))}
          <span>mehr</span>
        </div>
      </div>
    </div>
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
  const [granularity, setGranularity] = useState("month"); // day | week | month | quarter | year
  const [timeRange, setTimeRange] = useState(""); // "" (default) | 30d | 90d | 6m | 12m
  // v1.6.6 (#540): manueller Zeitraum-Picker fuer den Bericht-Export
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [timeline, setTimeline] = useState(null);
  const [scores, setScores] = useState(null);
  const [extended, setExtended] = useState(null);
  const [rejection, setRejection] = useState(null);
  const [styleStats, setStyleStats] = useState(null);
  // v1.7.0-beta.12 (#579): Activity-Heatmap
  const [heatmap, setHeatmap] = useState(null);
  const [heatmapDays, setHeatmapDays] = useState(365);

  // Combined key for "all" view: granularity=all means show everything grouped monthly
  const interval = granularity === "all" ? "all" : granularity;

  const loadData = useEffectEvent(async (g, r) => {
    try {
      const params = new URLSearchParams({ interval: g });
      if (r) params.set("range", r);
      const [timelineData, scoreData, extendedData, rejectionData, styleData, heatmapData] = await Promise.all([
        optionalApi(`/api/stats/timeline?${params}`),
        optionalApi("/api/stats/scores"),
        optionalApi("/api/stats/extended"),
        optionalApi("/api/rejection-patterns"),
        optionalApi("/api/stats/style"),
        optionalApi(`/api/stats/heatmap?days=${heatmapDays}`),
      ]);
      if (!timelineData && !scoreData && !extendedData) {
        pushToast("Server nicht erreichbar.", "danger");
        setLoading(false);
        return;
      }
      setTimeline(timelineData);
      setScores(scoreData);
      setExtended(extendedData);
      setRejection(rejectionData);
      setStyleStats(styleData);
      setHeatmap(heatmapData);
      setLoading(false);
    } catch (error) {
      pushToast(`Statistiken konnten nicht geladen werden: ${error.message}`, "danger");
      setLoading(false);
    }
  });

  useEffect(() => {
    setLoading(true);
    loadData(granularity, timeRange);
  }, [reloadKey, granularity, timeRange, heatmapDays]);

  if (loading) return <LoadingPanel label="Statistiken werden geladen..." />;

  // --- Timeline chart data ---
  // beta.33 / User-Feedback: laufende Periode NICHT mehr wegfiltern
  // (User: "wir sind schon KW 17, Statistik geht aber nur bis KW 15").
  // Die laufende Periode wird stattdessen visuell als "(unvollst.)"
  // markiert — siehe formatPeriodLabel weiter unten.
  const currentPeriod = timeline?.current_period;
  const allPeriods = timeline?.periods || [];
  const timelinePeriods = allPeriods;

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
      {/* beta.35: h1 sr-only — Top-Bar zeigt Breadcrumb */}
      <h1 className="sr-only">Statistiken</h1>
      <div className="mb-6 flex flex-wrap items-baseline justify-end gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {/* Zeitraum (time range) */}
          {[
            { label: "30 Tage", value: "30d" },
            { label: "90 Tage", value: "90d" },
            { label: "6 Monate", value: "6m" },
            { label: "12 Monate", value: "12m" },
            { label: "Alles", value: "" },
          ].map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => { setTimeRange(preset.value); if (preset.value === "" && granularity !== "all") setGranularity("all"); if (preset.value !== "" && granularity === "all") setGranularity("month"); }}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                timeRange === preset.value
                  ? "bg-sky/15 text-sky"
                  : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
              }`}
            >
              {preset.label}
            </button>
          ))}
          <span className="mx-0.5 h-4 w-px bg-white/10" />
          {/* Gruppierung (granularity) */}
          <SelectInput
            className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
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
            href={apiUrl(buildExportUrl("pdf", timeRange, customFrom, customTo))}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            PDF
          </LinkButton>
          <LinkButton
            size="sm"
            href={apiUrl(buildExportUrl("xlsx", timeRange, customFrom, customTo))}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            Excel
          </LinkButton>
        </div>
      </div>

      {/* v1.6.6 (#540): manueller Zeitraum fuer den Bericht-Export */}
      <div className="mb-6 flex flex-wrap items-center gap-3 text-xs text-muted/70">
        <span>Bericht-Zeitraum manuell:</span>
        <input
          type="date"
          value={customFrom}
          onChange={(e) => setCustomFrom(e.target.value)}
          className="rounded-lg border border-white/5 bg-white/[0.03] px-2 py-1 text-ink"
          aria-label="Zeitraum von"
        />
        <span>bis</span>
        <input
          type="date"
          value={customTo}
          onChange={(e) => setCustomTo(e.target.value)}
          className="rounded-lg border border-white/5 bg-white/[0.03] px-2 py-1 text-ink"
          aria-label="Zeitraum bis"
        />
        {(customFrom || customTo) && (
          <button
            type="button"
            onClick={() => { setCustomFrom(""); setCustomTo(""); }}
            className="text-[11px] text-muted/60 hover:text-ink underline"
          >
            zuruecksetzen
          </button>
        )}
        <span className="ml-2 text-[11px] text-muted/50">
          (ueberschreibt die Preset-Auswahl oben — leer = Preset gilt)
        </span>
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

          {/* v1.7.0-beta.12 (#579): Activity-Heatmap */}
          <Card className="rounded-2xl">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Activity size={14} className="text-sky" />
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
                  Aktivitaets-Heatmap
                </p>
                {heatmap?.total_active_days != null && (
                  <span className="ml-2 text-[11px] text-muted/50">
                    {heatmap.total_active_days} aktive Tage
                    {heatmap.max_per_day ? ` · max. ${heatmap.max_per_day}/Tag` : ""}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {[
                  { label: "90 T", value: 90 },
                  { label: "180 T", value: 180 },
                  { label: "365 T", value: 365 },
                  { label: "730 T", value: 730 },
                ].map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setHeatmapDays(p.value)}
                    className={`rounded-lg px-2 py-0.5 text-[11px] font-medium transition-colors ${
                      heatmapDays === p.value
                        ? "bg-sky/15 text-sky"
                        : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            {heatmap && heatmap.data && heatmap.data.length > 0 ? (
              <ActivityHeatmap data={heatmap.data} days={heatmapDays} />
            ) : (
              <p className="py-6 text-center text-sm text-muted/40">
                Noch keine Aktivitaeten erfasst. Sobald du Bewerbungen, Termine oder Follow-ups anlegst, erscheint hier ein Aktivitaetsmuster.
              </p>
            )}
          </Card>

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

          {/* Row 3b: Rejection patterns (#456 / v1.5.7) */}
          {rejection && rejection.anzahl >= 3 && (
            <Card className="rounded-2xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <TrendingUp size={14} className="text-coral" />
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Was Absagen dir sagen</p>
                </div>
                <Badge tone="danger">{rejection.anzahl} Absagen</Badge>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted/50 mb-2">Haeufigste Gruende</p>
                  <div className="grid gap-1.5">
                    {Object.entries(rejection.nach_grund || {}).slice(0, 6).map(([grund, count]) => (
                      // v1.6.5: items-start statt items-center + break-words statt truncate,
                      // damit lange Begruendungen umbrechen statt zu ueberlaufen.
                      <div key={grund} className="flex items-start justify-between gap-3 rounded-lg border border-white/[0.04] px-3 py-1.5 text-sm">
                        <span className="flex-1 min-w-0 break-words text-ink leading-snug">{grund}</span>
                        <Badge tone="neutral" className="shrink-0 mt-0.5">{count}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted/50 mb-2">Betroffene Firmen</p>
                  <div className="grid gap-1.5">
                    {Object.entries(rejection.nach_firma || {}).slice(0, 6).map(([firma, count]) => (
                      <div key={firma} className="flex items-start justify-between gap-3 rounded-lg border border-white/[0.04] px-3 py-1.5 text-sm">
                        <span className="flex-1 min-w-0 break-words text-ink leading-snug">{firma}</span>
                        <Badge tone="neutral" className="shrink-0 mt-0.5">{count === 1 ? "1 Absage" : `${count} Absagen`}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3">
                <p className="text-xs text-muted/50">
                  Eine systematische Haeufung weist oft auf ein konkretes Profil- oder Kommunikations-Thema hin.
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    navigator.clipboard?.writeText("/ablehnungs_coaching").catch(() => {});
                    pushToast("Prompt /ablehnungs_coaching kopiert — in Claude Desktop einfuegen.", "success");
                  }}
                >
                  Vertieft mit Claude besprechen
                </Button>
              </div>
            </Card>
          )}

          {/* Row 3c: Anschreiben-Stil-Auswertung (#454) */}
          {styleStats?.status === "ok" && Object.keys(styleStats.stile || {}).length > 0 && (
            <Card className="rounded-2xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <PenLine size={14} className="text-sky" />
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Anschreiben-Stile im Vergleich</p>
                </div>
                <Badge tone="neutral">{styleStats.gesamt_getrackt} getrackt</Badge>
              </div>
              <div className="grid gap-1.5">
                {Object.entries(styleStats.stile).map(([stil, bucket]) => {
                  const hasQuoten = typeof bucket.interview_quote === "number";
                  return (
                    <div key={stil} className="rounded-lg border border-white/[0.04] px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-ink capitalize">{stil}</span>
                        <Badge tone="neutral">{bucket.anzahl} {bucket.anzahl === 1 ? "Bewerbung" : "Bewerbungen"}</Badge>
                      </div>
                      {hasQuoten ? (
                        <div className="mt-1.5 flex items-center gap-3 text-xs text-muted/70">
                          <span>Interview-Quote: <span className="text-ink font-medium">{bucket.interview_quote}%</span></span>
                          <span>Angebote: <span className="text-ink font-medium">{bucket.angebots_quote}%</span></span>
                          <span>Absagen: <span className="text-ink font-medium">{bucket.absage_quote}%</span></span>
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-muted/50">{bucket.hinweis || `Mindestens ${styleStats.min_samples_fuer_quoten} Bewerbungen pro Stil noetig.`}</p>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-xs text-muted/50">
                Stil per <code className="text-ink/70">bewerbung_stil_tracken()</code> nach jedem Anschreiben festhalten — Claude macht das nach dem Standard-Workflow automatisch.
              </p>
            </Card>
          )}

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
