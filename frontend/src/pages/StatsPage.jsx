import { Download } from "lucide-react";
import { lokalesDatum } from "@/lib/lokaleZeit";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, apiUrl, optionalApi } from "@/api";
import { useApp } from "@/app-context";
import LearningInsightsCard from "@/components/LearningInsightsCard";
import { grundText, quelleText } from "@/lib/anzeige";
import { anteilText, farben, phasenImVerlauf, phasenSumme, prozent, rangliste, zahl } from "@/lib/diagramm";
import KostenBlock from "@/components/KostenBlock";
import MitClaude from "@/components/MitClaude";
import StatistikKern from "@/components/StatistikKern";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  LinkButton,
  LoadingPanel,
  SelectInput,
  DatumFeld,
} from "@/components/ui";
import { formatDate, formatDateTime, statusLabel } from "@/utils";

const TOOLTIP_STYLE = {
  background: "rgb(var(--color-panel) / 0.97)",
  border: "1px solid rgb(var(--color-line) / 0.6)",
  borderRadius: 12,
  fontSize: 12,
  padding: "8px 10px",
  boxShadow: "0 8px 24px rgb(0 0 0 / 0.18)",
};

// #1345 (G117): das Farbschema der Seite. Achsen und Raster sind SVG; dort
// greifen CSS-Variablen nicht verlaesslich, deshalb kommen die Farben als
// feste Werte aus lib/diagramm.js und folgen dem Umschalter.
function leseFarbschema() {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function useFarbschema() {
  const [schema, setSchema] = useState(leseFarbschema);
  useEffect(() => {
    const beobachter = new MutationObserver(() => setSchema(leseFarbschema()));
    beobachter.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => beobachter.disconnect();
  }, []);
  return schema;
}

// Wer im System "Bewegung reduzieren" eingestellt hat, bekommt stehende Diagramme.
function useOhneBewegung() {
  const [ohne, setOhne] = useState(() =>
    typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return undefined;
    const hoeren = () => setOhne(mq.matches);
    mq.addEventListener?.("change", hoeren);
    return () => mq.removeEventListener?.("change", hoeren);
  }, []);
  return ohne;
}

// Hinweisfeld der Diagramme: Text in Textfarbe, die Reihe traegt ein Farbfeld.
function DiagrammHinweis({ active, payload, label, titel, einheit }) {
  if (!active || !payload?.length) return null;
  const zeilen = payload.filter((p) => Number(p.value) > 0);
  return (
    <div style={TOOLTIP_STYLE}>
      <p className="mb-1 font-semibold text-ink">{titel ? titel(label) : label}</p>
      {zeilen.length === 0 ? <p className="text-muted">Keine Einträge</p> : null}
      {zeilen.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-ink">
          <span aria-hidden="true" className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: p.color || p.fill }} />
          <span className="text-muted">{einheit || p.name}</span>
          <span className="ml-auto pl-3 font-semibold tabular-nums">{zahl(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

// Rangliste statt Kreisdiagramm: Name, Wert und Anteil stehen als Text da,
// der Balken zeigt nur die Groessenordnung. Eine Farbe fuer alle Zeilen —
// die Zeile ist durch ihren Namen bestimmt, nicht durch einen Farbton.
function RangListe({ eintraege, farbe, restFarbe, einheit, onZeile, max = 8 }) {
  const zeilen = rangliste(eintraege, { max });
  return (
    <ul className="grid gap-3">
      {zeilen.map((z) => {
        const name = z.gefaltet ? `Sonstige (${z.gefaltet})` : z.name;
        const hinweis = `${name}: ${zahl(z.wert)} ${einheit} (${prozent(Math.round(z.anteil * 10) / 10)})`;
        const inhalt = (
          <>
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 break-words text-ink">{name}</span>
              <span className="shrink-0 tabular-nums text-muted">
                <span className="font-semibold text-ink">{zahl(z.wert)}</span>
                {" · "}
                {prozent(Math.round(z.anteil))}
              </span>
            </span>
            <span className="rangbalken-spur mt-1.5 block h-1.5 rounded-full">
              <span
                className="rangbalken block h-1.5 rounded-full"
                style={{ width: `${Math.max(z.breite, 1.5)}%`, background: z.gefaltet ? restFarbe : farbe }}
              />
            </span>
          </>
        );
        return (
          <li key={name} title={hinweis}>
            {onZeile && !z.gefaltet ? (
              <button type="button" onClick={() => onZeile(z)} className="block w-full rounded-md text-left transition hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky">
                {inhalt}
              </button>
            ) : inhalt}
          </li>
        );
      })}
    </ul>
  );
}

function resolveTimeRangeDates(range) {
  if (!range) return { from: "", to: "" };
  const now = new Date();
  const to = lokalesDatum(now);
  const start = new Date(now);
  if (range === "30d") start.setDate(start.getDate() - 30);
  else if (range === "90d") start.setDate(start.getDate() - 90);
  else if (range === "6m") start.setMonth(start.getMonth() - 6);
  else if (range === "12m") start.setMonth(start.getMonth() - 12);
  else return { from: "", to: "" };
  return { from: lokalesDatum(start), to };
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

// #798: ein Zeitraum fuer die Uebersicht und alle drei Dokumente.
function gewaehlterZeitraum(timeRange, customFrom, customTo) {
  if (customFrom || customTo) return { from: customFrom, to: customTo };
  return resolveTimeRangeDates(timeRange);
}

function dokumentUrl(art, timeRange, customFrom, customTo) {
  const { from, to } = gewaehlterZeitraum(timeRange, customFrom, customTo);
  const abfrage = new URLSearchParams();
  if (from) abfrage.set("from", from);
  if (to) abfrage.set("to", to);
  const text = abfrage.toString();
  return `/api/bericht/${art}${text ? `?${text}` : ""}`;
}

function gewaehlterZeitraumProps(timeRange, customFrom, customTo) {
  const { from, to } = gewaehlterZeitraum(timeRange, customFrom, customTo);
  return { von: from, bis: to };
}

// #1345: jede Karte sagt, welchen Zeitraum ihre Zahlen meinen.
function KartenKopf({ titel, bezug, children }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-ink">{titel}</h3>
        {bezug ? <p className="mt-0.5 text-xs text-muted">{bezug}</p> : null}
      </div>
      {children}
    </div>
  );
}

function ChartCard({ title, bezug, children }) {
  return (
    <Card className="rounded-2xl">
      <KartenKopf titel={title} bezug={bezug} />
      {children}
    </Card>
  );
}

// #1345: dieselben Zahlen als Tabelle, fuer alle, die Diagramme schlecht lesen.
function DiagrammTabelle({ kopf, zeilen }) {
  if (!zeilen.length) return null;
  return (
    <details className="mt-3 text-xs text-muted">
      <summary className="cursor-pointer select-none hover:text-ink">Als Tabelle anzeigen</summary>
      <div className="mt-2 max-h-64 overflow-auto">
        <table className="w-full text-left">
          <thead>
            <tr>
              {kopf.map((k, i) => (
                <th key={k} scope="col" className={`py-1 pr-3 font-medium ${i ? "text-right" : ""}`}>{k}</th>
              ))}
            </tr>
          </thead>
          <tbody className="text-ink">
            {zeilen.map((zeile) => (
              <tr key={zeile[0]} className="border-t border-white/5">
                {zeile.map((wert, i) => (
                  <td key={kopf[i]} className={`py-1 pr-3 ${i ? "text-right tabular-nums" : ""}`}>{i ? zahl(wert) : wert}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

const tabellenZeilen = (daten, name, schluessel) => daten.map((d) => [d[name], ...schluessel.map((s) => d[s] || 0)]);

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
    const iso = lokalesDatum(cur);
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
    "rgb(var(--surface-overlay-soft) / 0.04)",
    "rgb(var(--color-sky) / 0.25)",
    "rgb(var(--color-sky) / 0.5)",
    "rgb(var(--color-sky) / 0.75)",
    "rgb(var(--color-sky) / 1)",
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
        <div className="ml-7 flex gap-[3px] text-xs text-muted">
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
          <div className="flex flex-col justify-between pr-1 text-xs text-muted">
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
                  ? `${formatDate(cell.date)}: ${zahl(count)} Aktion${count !== 1 ? "en" : ""}`
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
        <div className="ml-7 mt-1 flex items-center gap-2 text-xs text-muted">
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
      {/* U14 (#1170): „AUSSORTIERT“ lief in „Heute“ und „Diese Woche“ in die Nachbarkachel — enge Laufweite, Umbruch erlaubt. */}
      <p className="break-words text-xs uppercase tracking-[0.06em] text-muted">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${valueClasses[tone] || "text-ink"}`}>{value}</p>
      {sub && <p className="text-xs text-muted">{sub}</p>}
    </div>
  );
}

const GESAMT = "gesamter Verlauf";

export default function StatsPage() {
  const { reloadKey, pushToast, navigateTo, copyPrompt } = useApp();
  const [loading, setLoading] = useState(true);
  const [granularity, setGranularity] = useState("month"); // day | week | month | quarter | year
  const [timeRange, setTimeRange] = useState(""); // "" (default) | 30d | 90d | 6m | 12m
  // v1.6.6 (#540): manueller Zeitraum-Picker fuer den Bericht-Export
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [timeline, setTimeline] = useState(null);
  const [scores, setScores] = useState(null);
  const [extended, setExtended] = useState(null);
  const [coreStats, setCoreStats] = useState(null); // #682: get_statistics (Quoten)
  const [quotaSegment, setQuotaSegment] = useState("seit_pbp"); // #682 default: seit PBP
  const [rejection, setRejection] = useState(null);
  const [styleStats, setStyleStats] = useState(null);
  // v1.7.0-beta.12 (#579): Activity-Heatmap
  const [heatmap, setHeatmap] = useState(null);
  const [heatmapDays, setHeatmapDays] = useState(365);

  // Combined key for "all" view: granularity=all means show everything grouped monthly
  const interval = granularity === "all" ? "all" : granularity;
  const f = farben(useFarbschema());
  const bewegt = !useOhneBewegung();
  const achse = { fontSize: 11, fill: f.text };
  const legendenText = (wert) => <span style={{ color: f.text }}>{wert}</span>;

  // #1345: die Verlaufsdiagramme zeigen denselben Zeitraum wie die Uebersicht.
  const { from: zeitVon, to: zeitBis } = gewaehlterZeitraum(timeRange, customFrom, customTo);
  const zeitraumText = zeitVon || zeitBis
    ? `${zeitVon ? formatDate(zeitVon) : "Beginn"} bis ${zeitBis ? formatDate(zeitBis) : "heute"}`
    : GESAMT;
  const anfrage = useRef(0);

  const loadData = useEffectEvent(async (g, von, bis) => {
    const nummer = ++anfrage.current;
    try {
      const params = new URLSearchParams({ interval: g });
      if (von) params.set("from", von);
      if (bis) params.set("to", bis);
      if (!von && !bis) params.set("range", "alles");
      const [timelineData, scoreData, extendedData, rejectionData, styleData, heatmapData, coreData] = await Promise.all([
        optionalApi(`/api/stats/timeline?${params}`),
        optionalApi("/api/stats/scores"),
        optionalApi("/api/stats/extended"),
        optionalApi("/api/rejection-patterns"),
        optionalApi("/api/stats/style"),
        optionalApi(`/api/stats/heatmap?days=${heatmapDays}`),
        optionalApi("/api/statistics"),  // #682: Quoten + Segmentierung
      ]);
      if (nummer !== anfrage.current) return;
      if (!timelineData && !scoreData && !extendedData) {
        pushToast("Server nicht erreichbar.", "danger");
        setLoading(false);
        return;
      }
      setTimeline(timelineData);
      setScores(scoreData);
      setExtended(extendedData);
      setCoreStats(coreData);
      setRejection(rejectionData);
      setStyleStats(styleData);
      setHeatmap(heatmapData);
      setLoading(false);
    } catch (error) {
      if (nummer !== anfrage.current) return;
      pushToast(`Statistiken konnten nicht geladen werden: ${error.message}`, "danger");
      setLoading(false);
    }
  });

  useEffect(() => {
    setLoading(true);
    loadData(granularity, zeitVon, zeitBis);
  }, [reloadKey, granularity, zeitVon, zeitBis, heatmapDays]);

  // Nur beim ersten Laden die Ladeanzeige; ein Wechsel des Zeitraums haelt
  // die vorige Ansicht, bis die neue da ist (kein Springen der Seite).
  if (loading && !timeline && !scores && !extended) {
    return <LoadingPanel label="Statistiken werden geladen …" />;
  }

  // #1423: ein manueller Zeitraum gilt statt der Vorauswahl; die Vorauswahl zeigt sich dann nicht als aktiv.
  const manuellerZeitraum = Boolean(customFrom || customTo);

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
    const qMatch = period.match(/^(\d{4})-Q(\d)$/);
    if (qMatch) return `Q${qMatch[2]} ${qMatch[1].slice(2)}`;
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

  // --- Stand der Bewerbungen je Zeitraum, gefaltet in Phasen ---
  const statusJeZeitraum = timelinePeriods.map((period) => timeline?.by_status?.[period] || {});
  const phasen = phasenImVerlauf(statusJeZeitraum);
  const phasenChartData = timelinePeriods.map((period, i) => {
    const summe = phasenSumme(statusJeZeitraum[i]);
    const entry = { name: formatPeriodLabel(period) };
    for (const phase of phasen) entry[phase.label] = summe[phase.key] || 0;
    return entry;
  });

  // --- Source distribution pie data ---
  const sources = scores?.sources || [];
  // G65 (#1087 D2): Namen statt Schluessel an Achse und Legende.
  const sourcePieData = sources.map((s) => ({
    name: quelleText(s),
    wert: s.count,
  }));
  const bewerbungsQuellen = (scores?.application_sources || []).map((s) => ({
    name: quelleText(s),
    wert: s.count,
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
      name: quelleText(s),
      "Ø Punkte": Math.round(s.avg_score * 10) / 10,
      "Max Punkte": s.max_score || 0,
    }));

  // --- Dismiss reasons chart data ---
  const dismissData = (extended?.dismiss_reasons || []).slice(0, 10).map(([reason, count]) => ({
    name: grundText(reason),
    wert: count,
  }));

  const hasData = timelineChartData.length > 0 || sourcePieData.length > 0 || scoreBarData.length > 0;
  const totals = extended?.totals || {};
  const appStats = extended?.applications || {};

  return (
    <div
      id="page-statistiken"
      className="page active"
      aria-busy={loading}
    >
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
              onClick={() => { setCustomFrom(""); setCustomTo(""); setTimeRange(preset.value); if (preset.value === "" && granularity !== "all") setGranularity("all"); if (preset.value !== "" && granularity === "all") setGranularity("month"); }}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                !manuellerZeitraum && timeRange === preset.value
                  ? "bg-sky/15 text-sky"
                  : "text-muted hover:text-ink hover:bg-white/[0.04]"
              }`}
            >
              {preset.label}
            </button>
          ))}
          <span className="mx-0.5 h-4 w-px bg-white/10" />
          {/* Gruppierung (granularity) */}
          <SelectInput
            className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
          >
            <option value="day">Täglich</option>
            <option value="week">Wöchentlich</option>
            <option value="month">Monatlich</option>
            <option value="quarter">Quartalsweise</option>
            <option value="year">Jährlich</option>
            <option value="all">Komplett</option>
          </SelectInput>
          <a
            href="#kosten"
            onClick={(e) => { e.preventDefault(); document.getElementById("kosten")?.scrollIntoView({ behavior: "smooth" }); }}
            className="text-xs text-muted underline hover:text-ink"
          >
            Kosten prüfen
          </a>
          <LinkButton
            size="sm"
            href={apiUrl(dokumentUrl("nachweis", timeRange, customFrom, customTo))}
            target="_blank"
            rel="noreferrer"
            title="Für Agentur oder Jobcenter: nur was du getan hast, ohne Punkte und Bewertungen"
          >
            <Download size={14} />
            Nachweis
          </LinkButton>
          <LinkButton
            size="sm"
            href={apiUrl(dokumentUrl("auswertung", timeRange, customFrom, customTo))}
            target="_blank"
            rel="noreferrer"
            title="Für dich: was läuft, was ansteht und was funktioniert"
          >
            <Download size={14} />
            Auswertung
          </LinkButton>
          <LinkButton
            size="sm"
            href={apiUrl(buildExportUrl("xlsx", timeRange, customFrom, customTo))}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            Rohdaten
          </LinkButton>
        </div>
      </div>

      {/* v1.6.6 (#540): manueller Zeitraum fuer den Bericht-Export */}
      <div className="mb-6 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span>Zeitraum von Hand:</span>
        <DatumFeld
          value={customFrom}
          onChange={setCustomFrom}
          className="!w-32 !py-1 text-xs"
          aria-label="Zeitraum von"
        />
        <span>bis</span>
        <DatumFeld
          value={customTo}
          onChange={setCustomTo}
          className="!w-32 !py-1 text-xs"
          aria-label="Zeitraum bis"
        />
        {(customFrom || customTo) && (
          <button
            type="button"
            onClick={() => { setCustomFrom(""); setCustomTo(""); }}
            className="text-xs text-muted hover:text-ink underline"
          >
            zurücksetzen
          </button>
        )}
        <span className="ml-2 text-xs text-muted">
          (gilt statt der Auswahl oben; leer = die Auswahl gilt)
        </span>
      </div>

      <StatistikKern {...gewaehlterZeitraumProps(timeRange, customFrom, customTo)} />

      <KostenBlock />

      {/* U8 (#1170): ohne Stellen und ohne Bewerbungen war das hier eine Wand aus Nullen („0 EUR“, „k.A.“) ohne ein erklärendes Wort. */}
      {!hasData && !(Number(totals.jobs_ever) > 0 || Number(appStats.total) > 0) ? (
        <EmptyState
          title="Noch keine Zahlen"
          description="Die Statistik füllt sich, sobald PBP Stellen gefunden hat und du Bewerbungen angelegt hast. Dann siehst du, wie viele Treffer zu Bewerbungen wurden, wie lange Antworten dauern und was bei dir funktioniert."
        />
      ) : (
        <div className="grid grid-cols-1 gap-6">
          <div className="-mb-3">
            <h2 className="mb-1 text-base font-semibold text-ink">Weitere Diagramme</h2>
            <p className="text-xs text-muted">Jede Karte nennt, welchen Zeitraum sie zeigt.</p>
          </div>
          {/* Row 1: Timeline + Status */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <ChartCard title="Bewerbungen und neue Stellen im Zeitverlauf" bezug={zeitraumText}>
              {timelineChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={timelineChartData}>
                    <CartesianGrid vertical={false} stroke={f.raster} />
                    <XAxis dataKey="name" tick={achse} axisLine={{ stroke: f.raster }} tickLine={false} />
                    <YAxis tick={achse} allowDecimals={false} axisLine={false} tickLine={false} width={36} tickFormatter={zahl} />
                    <Tooltip content={<DiagrammHinweis />} cursor={{ stroke: f.text, strokeWidth: 1 }} />
                    <Legend itemSorter={null} iconType="plainline" wrapperStyle={{ fontSize: 12 }} formatter={legendenText} />
                    <Area type="monotone" dataKey="Bewerbungen" stroke={f.paar[0]} fill={f.paar[0]} fillOpacity={0.14} strokeWidth={2} activeDot={{ r: 4, stroke: f.flaeche, strokeWidth: 2 }} isAnimationActive={bewegt} />
                    <Area type="monotone" dataKey="Neue Stellen" stroke={f.paar[1]} fill={f.paar[1]} fillOpacity={0.1} strokeWidth={2} activeDot={{ r: 4, stroke: f.flaeche, strokeWidth: 2 }} isAnimationActive={bewegt} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted">Keine Zeitraumdaten vorhanden.</p>
              )}
              <DiagrammTabelle kopf={["Zeitraum", "Bewerbungen", "Neue Stellen"]} zeilen={tabellenZeilen(timelineChartData, "name", ["Bewerbungen", "Neue Stellen"])} />
            </ChartCard>

            <ChartCard title="Heutiger Stand, nach Bewerbungsdatum" bezug={zeitraumText}>
              {phasenChartData.length > 0 && phasen.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={phasenChartData}>
                    <CartesianGrid vertical={false} stroke={f.raster} />
                    <XAxis dataKey="name" tick={achse} axisLine={{ stroke: f.raster }} tickLine={false} />
                    <YAxis tick={achse} allowDecimals={false} axisLine={false} tickLine={false} width={36} tickFormatter={zahl} />
                    <Tooltip content={<DiagrammHinweis />} cursor={{ fill: f.raster, fillOpacity: 0.5 }} />
                    <Legend itemSorter={null} iconType="square" iconSize={9} wrapperStyle={{ fontSize: 12 }} formatter={legendenText} />
                    {phasen.map((phase) => (
                      <Bar key={phase.key} dataKey={phase.label} stackId="phase" fill={f.phasen[phase.key]} stroke={f.flaeche} strokeWidth={1.5} maxBarSize={30} isAnimationActive={bewegt} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted">Keine Statusdaten vorhanden.</p>
              )}
              <DiagrammTabelle kopf={["Zeitraum", ...phasen.map((x) => x.label)]} zeilen={tabellenZeilen(phasenChartData, "name", phasen.map((x) => x.label))} />
            </ChartCard>
          </div>

          {/* v1.7.0-beta.12 (#579): Activity-Heatmap */}
          <Card className="rounded-2xl">
            <KartenKopf
              titel="An welchen Tagen du aktiv warst"
              bezug={`letzte ${zahl(heatmapDays)} Tage${heatmap?.total_active_days != null ? `, ${zahl(heatmap.total_active_days)} aktive Tage` : ""}${heatmap?.max_per_day ? `, höchstens ${zahl(heatmap.max_per_day)} am Tag` : ""}`}
            >
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
                    className={`rounded-lg px-2 py-0.5 text-xs font-medium transition-colors ${
                      heatmapDays === p.value
                        ? "bg-sky/15 text-sky"
                        : "text-muted hover:text-ink hover:bg-white/[0.04]"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </KartenKopf>
            {heatmap && heatmap.data && heatmap.data.length > 0 ? (
              <ActivityHeatmap data={heatmap.data} days={heatmapDays} />
            ) : (
              <p className="py-6 text-center text-sm text-muted">
                Noch keine Aktivitäten erfasst. Sobald du Bewerbungen, Termine oder Nachfassungen anlegst, erscheint hier ein Aktivitätsmuster.
              </p>
            )}
          </Card>

          {/* #682: Outcome-Quoten mit Segmentierung am PBP-Startdatum */}
          {coreStats?.quoten && (() => {
            const q = coreStats.quoten;
            const seg = q[quotaSegment] || { basis: 0 };
            const SEGMENTS = [
              { key: "seit_pbp", label: "Seit PBP" },
              { key: "vor_pbp", label: "Vor PBP" },
              { key: "gesamt", label: "Gesamt" },
            ];
            const segLabel = SEGMENTS.find((s) => s.key === quotaSegment)?.label;
            return (
              <Card className="rounded-2xl">
                <KartenKopf
                  titel="Was aus deinen Bewerbungen wurde"
                  bezug={`${GESAMT}${q.pbp_start_datum ? `, PBP-Start: ${formatDate(q.pbp_start_datum)}` : ""}`}
                >
                  <div className="flex gap-1">
                    {SEGMENTS.map((s) => (
                      <button
                        key={s.key}
                        type="button"
                        onClick={() => setQuotaSegment(s.key)}
                        className={`rounded-md px-2.5 py-1 text-xs transition ${
                          quotaSegment === s.key
                            ? "bg-sky/15 text-sky"
                            : "text-muted hover:text-ink"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </KartenKopf>
                {seg.basis > 0 ? (
                  <>
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                      <StatBox label="Abgelaufen" value={anteilText(seg.abgelaufen, seg.basis)} sub={seg.basis >= 10 ? `${zahl(seg.abgelaufen)} von ${zahl(seg.basis)}` : ""} tone="danger" />
                      <StatBox label="Abgelehnt" value={anteilText(seg.abgelehnt, seg.basis)} sub={seg.basis >= 10 ? `${zahl(seg.abgelehnt)} von ${zahl(seg.basis)}` : ""} tone="amber" />
                      <StatBox label="Zurückgezogen" value={anteilText(seg.zurueckgezogen, seg.basis)} sub={seg.basis >= 10 ? `${zahl(seg.zurueckgezogen)} von ${zahl(seg.basis)}` : ""} tone="neutral" />
                      <StatBox label="Gespräch erreicht" value={anteilText(seg.interview, seg.basis)} sub={seg.basis >= 10 ? `${zahl(seg.interview)} von ${zahl(seg.basis)}` : ""} tone="sky" />
                      <StatBox label="Angebot" value={anteilText(seg.angebot, seg.basis)} sub={seg.basis >= 10 ? `${zahl(seg.angebot)} von ${zahl(seg.basis)}` : ""} tone="success" />
                    </div>
                    <p className="mt-2 text-xs text-muted">
                      Grundlage: {zahl(seg.basis)} abgeschickte Bewerbungen ({segLabel}, nach
                      Bewerbungsdatum). Der Vergleich „Seit PBP“ und „Vor PBP“ zeigt,
                      ob seit der Nutzung anteilig weniger Bewerbungen versanden.
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-muted">
                    Noch keine abgeschickten Bewerbungen in diesem Zeitraum.
                  </p>
                )}
              </Card>
            );
          })()}

          {/* Row 3b: Rejection patterns (#456 / v1.5.7) */}
          {rejection && rejection.anzahl >= 3 && (
            <Card className="rounded-2xl">
              <KartenKopf titel="Was Absagen dir sagen" bezug={GESAMT}>
                <Badge tone="danger">{rejection.anzahl} Absagen</Badge>
              </KartenKopf>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted mb-2">Häufigste Gründe</p>
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
                  <p className="text-xs uppercase tracking-wide text-muted mb-2">Betroffene Firmen</p>
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
                <p className="text-xs text-muted">
                  Eine systematische Häufung weist oft auf ein konkretes Profil- oder Kommunikations-Thema hin.
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => copyPrompt("/ablehnungs_coaching")}
                >
                  <MitClaude size={14}>Absagen besprechen</MitClaude>
                </Button>
              </div>
            </Card>
          )}

          {/* Row 2: Quellen (Rangliste) + Verteilung der Punkte */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <ChartCard title="Woher die Stellen kommen" bezug={GESAMT}>
              {sourcePieData.length > 0 ? (
                <RangListe
                  eintraege={sourcePieData}
                  farbe={f.eine}
                  restFarbe={f.neutral}
                  einheit="Stellen"
                  onZeile={() => navigateTo("stellen")}
                />
              ) : (
                <p className="py-8 text-center text-sm text-muted">Keine Quellendaten vorhanden.</p>
              )}
            </ChartCard>

            <ChartCard title="Wie viele Punkte die Stellen haben" bezug={GESAMT}>
              {scoreBarData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={scoreBarData} margin={{ bottom: 14 }}>
                    <CartesianGrid vertical={false} stroke={f.raster} />
                    <XAxis dataKey="bucket" tick={achse} axisLine={{ stroke: f.raster }} tickLine={false} label={{ value: "Punkte", position: "insideBottom", offset: -8, style: achse }} />
                    <YAxis tick={achse} allowDecimals={false} axisLine={false} tickLine={false} width={36} tickFormatter={zahl} />
                    <Tooltip
                      content={<DiagrammHinweis titel={(label) => `Punkte ${label}`} einheit="Stellen" />}
                      cursor={{ fill: f.raster, fillOpacity: 0.5 }}
                    />
                    <Bar dataKey="count" fill={f.eine} radius={[4, 4, 0, 0]} maxBarSize={44} isAnimationActive={bewegt} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-sm text-muted">Noch keine Punkte vorhanden.</p>
              )}
              <DiagrammTabelle kopf={["Punkte", "Stellen"]} zeilen={tabellenZeilen(scoreBarData, "bucket", ["count"])} />
            </ChartCard>
          </div>

          {/* Row 2b: Bewerbungs-Quellen + Aussortier-Gruende (Ranglisten) */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {bewerbungsQuellen.length > 0 && (
              <ChartCard title="Woher die Bewerbungen kommen" bezug={GESAMT}>
                <RangListe eintraege={bewerbungsQuellen} farbe={f.eine} restFarbe={f.neutral} einheit="Bewerbungen" />
              </ChartCard>
            )}

            {dismissData.length > 0 && (
              <ChartCard title="Warum Stellen aussortiert wurden" bezug={GESAMT}>
                <RangListe eintraege={dismissData} farbe={f.eine} restFarbe={f.neutral} einheit="Stellen" max={10} />
              </ChartCard>
            )}
          </div>

          {/* #986: Score-Verteilung ueber die BEWORBENEN Stellen.
              Zeigt, wie weit das eigene Urteil vom Modell abweicht —
              eine Frage, die keine andere Kennzahl beantwortet. */}
          {coreStats?.score_verteilung?.beworben?.anzahl > 0 && (() => {
            const v = coreStats.score_verteilung;
            const b = v.beworben;
            const spanne = Math.max(1, b.max - b.min);
            const pos = (wert) => ((wert - b.min) / spanne) * 100;
            return (
              <Card className="rounded-2xl">
                <KartenKopf titel="Bei wie vielen Punkten du dich beworben hast" bezug={GESAMT} />
                <p className="mb-4 text-xs text-muted">
                  Die Punkte zeigen, wie gut eine Anzeige deine Suchbegriffe trifft. Ob du passt, sagen sie nicht.
                </p>
                {/* Spannenbalken mit Quartilen und Schwellenmarkierung */}
                <div className="relative mb-2 h-8 w-full rounded-lg bg-panelstrong">
                  {b.q25 != null && (
                    <div
                      className="absolute top-2 h-4 rounded bg-amber/30"
                      style={{ left: `${pos(b.q25)}%`, width: `${pos(b.q75) - pos(b.q25)}%` }}
                      title={`Mittlere Hälfte: ${zahl(b.q25)} bis ${zahl(b.q75)}`}
                    />
                  )}
                  <div
                    className="absolute top-1 h-6 w-0.5 bg-amber"
                    style={{ left: `${pos(b.median)}%` }}
                    title={`Median ${zahl(b.median)}`}
                  />
                  {v.schwelle != null && v.schwelle >= b.min && v.schwelle <= b.max && (
                    <div
                      className="absolute top-0 h-8 w-0.5 bg-muted"
                      style={{ left: `${pos(v.schwelle)}%` }}
                      title={`Deine Schwelle: ${zahl(v.schwelle)}`}
                    />
                  )}
                </div>
                <div className="mb-4 flex justify-between text-xs text-muted">
                  <span>{zahl(b.min)}</span>
                  <span>Median {zahl(b.median)}</span>
                  <span>{zahl(b.max)}</span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                  <div><span className="text-muted">Bewerbungen</span><br />{zahl(b.anzahl)}</div>
                  <div><span className="text-muted">Mittel</span><br />{zahl(b.mittel)}</div>
                  <div><span className="text-muted">Median</span><br />{zahl(b.median)}</div>
                  <div><span className="text-muted">Spanne</span><br />{zahl(b.min)} – {zahl(b.max)}</div>
                </div>
                {v.unter_schwelle?.anzahl > 0 && (
                  <p className="mt-4 text-xs text-muted">
                    <strong>{v.unter_schwelle.anzahl}</strong> Bewerbung(en) lagen
                    unter deiner Schwelle von {zahl(v.schwelle)}. Du hast dich dort
                    trotz weniger Punkte beworben.
                  </p>
                )}
                {v.score_null?.anzahl > 0 && (
                  <p className="mt-2 text-xs text-muted">
                    <strong>{v.score_null.anzahl}</strong> weitere hatten 0 Punkte.
                    Das heißt: <em>kein Pflichtbegriff getroffen</em>. Das ist
                    keine schlechte Bewertung, sondern gar keine. Sie zählen
                    deshalb nicht in die Zahlen oben.
                  </p>
                )}
                {v.ohne_verknuepfte_stelle?.anzahl > 0 && (
                  <p className="mt-2 text-xs text-muted">
                    <strong>{v.ohne_verknuepfte_stelle.anzahl}</strong> Bewerbung(en)
                    haben keine verknüpfte Stelle und damit keine Punkte. Das ist
                    eine Datenlücke, kein Nullwert.
                  </p>
                )}
              </Card>
            );
          })()}

          {/* Row 3: Source-Score comparison */}
          {sourceScoreData.length > 0 ? (
            <ChartCard title="Punkte nach Quelle" bezug={GESAMT}>
              <ResponsiveContainer width="100%" height={Math.max(180, sourceScoreData.length * 44 + 70)}>
                <BarChart data={sourceScoreData} layout="vertical" barGap={3}>
                  <CartesianGrid horizontal={false} stroke={f.raster} />
                  <XAxis type="number" tick={achse} axisLine={false} tickLine={false} tickFormatter={zahl} />
                  <YAxis type="category" dataKey="name" tick={achse} width={120} axisLine={{ stroke: f.raster }} tickLine={false} />
                  <Tooltip content={<DiagrammHinweis />} cursor={{ fill: f.raster, fillOpacity: 0.5 }} />
                  <Legend itemSorter={null} iconType="square" iconSize={9} wrapperStyle={{ fontSize: 12 }} formatter={legendenText} />
                  <Bar dataKey={"Ø Punkte"} fill={f.paar[0]} radius={[0, 4, 4, 0]} barSize={8} isAnimationActive={bewegt} />
                  <Bar dataKey="Max Punkte" fill={f.paar[1]} radius={[0, 4, 4, 0]} barSize={8} isAnimationActive={bewegt} />
                </BarChart>
              </ResponsiveContainer>
              <DiagrammTabelle kopf={["Quelle", "Ø Punkte", "Max Punkte"]} zeilen={tabellenZeilen(sourceScoreData, "name", ["Ø Punkte", "Max Punkte"])} />
            </ChartCard>
          ) : null}

          {/* Row 3c: Anschreiben-Stil-Auswertung (#454) */}
          {styleStats?.status === "ok" && Object.keys(styleStats.stile || {}).length > 0 && (
            <Card className="rounded-2xl">
              <KartenKopf titel="Anschreiben-Stile im Vergleich" bezug={GESAMT}>
                <Badge tone="neutral">{styleStats.gesamt_getrackt} erfasst</Badge>
              </KartenKopf>
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
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                          <span>Gespräche: <span className="text-ink font-medium">{prozent(bucket.interview_quote)}</span></span>
                          <span>Angebote: <span className="text-ink font-medium">{prozent(bucket.angebots_quote)}</span></span>
                          <span>Absagen: <span className="text-ink font-medium">{prozent(bucket.absage_quote)}</span></span>
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-muted">{bucket.hinweis || `Mindestens ${styleStats.min_samples_fuer_quoten} Bewerbungen pro Stil nötig.`}</p>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-xs text-muted">
                Claude hält den Stil nach jedem Anschreiben fest, das über den üblichen Weg entsteht.
              </p>
            </Card>
          )}

          {/* Row 4: Recent activity */}
          {(extended?.recent_activity || []).length > 0 && (
            <Card className="rounded-2xl">
              <KartenKopf titel="Was zuletzt passiert ist" bezug="die letzten 10 Einträge" />
              <div className="grid gap-1.5">
                {extended.recent_activity.map((event, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-white/[0.04] px-3 py-2 text-sm">
                    <span className="shrink-0 text-xs text-muted tabular-nums w-28">{formatDateTime(event.event_date)}</span>
                    <Badge tone={event.status === "notiz" ? "neutral" : event.status === "abgelehnt" ? "danger" : event.status === "interview" ? "amber" : "sky"}>
                      {event.status ? statusLabel(event.status) : "Ereignis"}
                    </Badge>
                    <span className="min-w-[12rem] flex-1 break-words font-medium text-ink">{event.title} — {event.company}</span>
                    {event.notes && <span className="basis-full break-words text-xs text-muted">{event.notes}</span>}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
      {/* v1.7.35 (#985): zugezogen vom Dashboard. Nutzerhinweis vom
          07.09.2026 — "gehoert das nicht eher in die Statistiken, ist
          keine Funktion drin". Auf dem Dashboard steht, was zu TUN ist;
          was zu SEHEN ist, gehoert hierher. */}
      <div className="mt-5">
        <LearningInsightsCard />
      </div>
    </div>
  );
}
