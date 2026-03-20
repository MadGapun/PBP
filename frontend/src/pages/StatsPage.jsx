import { BarChart3, Download, TrendingUp } from "lucide-react";
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

import { api, apiUrl } from "@/api";
import { useApp } from "@/app-context";
import {
  Button,
  Card,
  EmptyState,
  LinkButton,
  LoadingPanel,
  SelectInput,
} from "@/components/ui";

const STATUS_COLORS = {
  beworben: "#38bdf8",
  interview: "#fbbf24",
  angebot: "#34d399",
  abgelehnt: "#f87171",
  entwurf: "#94a3b8",
  zurueckgezogen: "#a78bfa",
};

const SOURCE_COLORS = [
  "#38bdf8", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#60a5fa", "#facc15",
];

const CHART_STYLE = {
  fontSize: 11,
  fill: "rgba(255,255,255,0.45)",
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

export default function StatsPage() {
  const { reloadKey, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [interval, setInterval_] = useState("month");
  const [timeline, setTimeline] = useState(null);
  const [scores, setScores] = useState(null);

  const loadData = useEffectEvent(async (selectedInterval) => {
    try {
      const [timelineData, scoreData] = await Promise.all([
        api(`/api/stats/timeline?interval=${selectedInterval}`),
        api("/api/stats/scores"),
      ]);
      setTimeline(timelineData);
      setScores(scoreData);
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
  const timelinePeriods = timeline?.periods || [];
  const timelineChartData = timelinePeriods.map((period) => ({
    name: period,
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
  const statusChartData = timelinePeriods.map((period) => {
    const entry = { name: period };
    for (const status of statusKeys) {
      entry[status] = timeline?.by_status?.[period]?.[status] || 0;
    }
    return entry;
  });

  // --- Source distribution pie data ---
  const sources = scores?.sources || [];
  const sourcePieData = sources.map((s) => ({
    name: s.name,
    value: s.count,
  }));

  // --- Score distribution bar data (brackets: 0, 1-3, 4-6, 7-9, 10+) ---
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

  const hasData = timelineChartData.length > 0 || sourcePieData.length > 0 || scoreBarData.length > 0;

  return (
    <div id="page-statistiken" className="page active">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Statistiken</h1>
        <div className="flex flex-wrap gap-2">
          <SelectInput
            className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
            value={interval}
            onChange={(e) => setInterval_(e.target.value)}
          >
            <option value="week">Wöchentlich</option>
            <option value="month">Monatlich</option>
            <option value="quarter">Quartalsweise</option>
            <option value="year">Jährlich</option>
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

      {!hasData ? (
        <EmptyState
          title="Noch keine Daten"
          description="Sobald Bewerbungen und Stellen vorhanden sind, erscheinen hier Auswertungen."
        />
      ) : (
        <div className="grid gap-6">
          {/* Row 1: Timeline + Status */}
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard title="Bewerbungen & Stellen im Zeitverlauf">
              {timelineChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={timelineChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" tick={CHART_STYLE} />
                    <YAxis tick={CHART_STYLE} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: "rgba(30,34,52,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: "rgba(255,255,255,0.7)" }}
                    />
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
                    <Tooltip
                      contentStyle={{ background: "rgba(30,34,52,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: "rgba(255,255,255,0.7)" }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {statusKeys.map((status) => (
                      <Bar key={status} dataKey={status} stackId="status" fill={STATUS_COLORS[status] || "#94a3b8"} radius={[2, 2, 0, 0]} />
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
                    <Tooltip
                      contentStyle={{ background: "rgba(30,34,52,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }}
                    />
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
                      contentStyle={{ background: "rgba(30,34,52,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }}
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

          {/* Row 2b: Application Sources (#87) */}
          {(scores?.application_sources || []).length > 0 && (
            <div className="grid gap-6 xl:grid-cols-2">
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
                    <Tooltip
                      contentStyle={{ background: "rgba(30,34,52,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
              <div />
            </div>
          )}

          {/* Row 3: Source-Score comparison */}
          {sourceScoreData.length > 0 ? (
            <ChartCard title="Durchschnittsscore nach Quelle">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={sourceScoreData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis type="number" tick={CHART_STYLE} />
                  <YAxis type="category" dataKey="name" tick={CHART_STYLE} width={100} />
                  <Tooltip
                    contentStyle={{ background: "rgba(30,34,52,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }}
                    labelStyle={{ color: "rgba(255,255,255,0.7)" }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Ø Score" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="Max Score" fill="#34d399" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          ) : null}
        </div>
      )}
    </div>
  );
}
