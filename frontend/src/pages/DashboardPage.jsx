import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Briefcase,
  Calendar,
  ClipboardList,
  Download,
  HandCoins,
  Mail,
  Mic,
  Network,
  PlayCircle,
  PlusCircle,
  Search,
  Send,
  Upload,
  UserCheck,
  RefreshCw,
  Video,
  X,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, optionalApi, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { createFileSignature, uploadDocumentFile } from "@/document-upload";
import { extractDroppedFiles } from "@/file-drop";
import {
  Badge,
  Button,
  Card,
  LoadingPanel,
  MetricCard,
  Modal,
  PageHeader,
  SelectInput,
} from "@/components/ui";
import {
  formatCurrency,
  formatDate,
  readinessTone,
} from "@/utils";

function positiveSalary(value) {
  if (value === null || typeof value === "undefined") return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return numeric;
}

function buildAnnualSalaryMetrics(jobs = []) {
  const realRows = [];
  const estimatedRows = [];
  for (const job of jobs) {
    let min = positiveSalary(job?.salary_min);
    let max = positiveSalary(job?.salary_max);
    if (min === null && max === null) continue;
    if (min === null) min = max;
    if (max === null) max = min;
    const entry = { min, max, salaryType: String(job?.salary_type || "").toLowerCase() };
    if (job?.salary_estimated) {
      estimatedRows.push(entry);
    } else {
      realRows.push(entry);
    }
  }

  const hasReal = realRows.length > 0;
  const rows = hasReal ? realRows : estimatedRows;
  const allEstimated = !hasReal && estimatedRows.length > 0;

  const annualRows = rows.filter((row) => row.salaryType === "jaehrlich");
  if (!annualRows.length) {
    return {
      jobsWithSalary: hasReal ? realRows.length : estimatedRows.length,
      annualBasisCount: 0,
      averageMin: null,
      averageMax: null,
      allEstimated,
    };
  }

  const mins = annualRows.map((row) => row.min);
  const maxs = annualRows.map((row) => row.max);
  return {
    jobsWithSalary: hasReal ? realRows.length : estimatedRows.length,
    annualBasisCount: annualRows.length,
    averageMin: Math.round(mins.reduce((sum, value) => sum + value, 0) / mins.length),
    averageMax: Math.round(maxs.reduce((sum, value) => sum + value, 0) / maxs.length),
    allEstimated,
  };
}

export default function DashboardPage() {
  const { chrome, reloadKey, refreshChrome, navigateTo, copyPrompt, pushToast } = useApp();
  const lastLoadErrorRef = useRef({ message: "", at: 0 });
  const [loading, setLoading] = useState(true);
  const [impulse, setImpulse] = useState(null);
  const [data, setData] = useState({
    jobs: [],
    applications: [],
    followUps: [],
    statistics: {},
    zombies: [],
    meetings: [],
    emails: [],
  });
  const [emailDetail, setEmailDetail] = useState(null);
  const [scraperHealth, setScraperHealth] = useState([]);
  const [publicHints, setPublicHints] = useState([]);
  const [metricPerspective, setMetricPerspective] = useState(() => Math.floor(Math.random() * 5));
  const [dismissedHints, setDismissedHints] = useState(() => {
    try { return JSON.parse(localStorage.getItem("pbp_dismissed_hints") || "[]"); } catch { return []; }
  });

  const loadData = useEffectEvent(async () => {
    if (!chrome.status?.has_profile) {
      startTransition(() => {
        setData({
          jobs: [],
          applications: [],
          followUps: [],
          statistics: {},
          zombies: [],
          meetings: [],
          emails: [],
        });
        setLoading(false);
      });
      return;
    }

    try {
      const [jobs, applications, followUps, statistics, zombieData, meetingsData, emailsData, impulseData] = await Promise.all([
        optionalApi("/api/jobs?active=true"),
        optionalApi("/api/applications"),
        optionalApi("/api/follow-ups"),
        optionalApi("/api/statistics"),
        optionalApi("/api/applications/zombies"),
        optionalApi("/api/meetings"),
        optionalApi("/api/emails"),
        optionalApi("/api/daily-impulse"),
      ]);

      // If ALL calls returned null, the server is unreachable (#123)
      if (!jobs && !applications && !followUps && !statistics) {
        const message = "Server nicht erreichbar — LiveUpdate pausiert.";
        const now = Date.now();
        if (
          message !== lastLoadErrorRef.current.message ||
          now - lastLoadErrorRef.current.at > 30000
        ) {
          lastLoadErrorRef.current = { message, at: now };
          pushToast(message, "danger");
        }
        startTransition(() => setLoading(false));
        return;
      }

      startTransition(() => {
        setData({
          jobs: jobs || [],
          applications: applications?.applications || [],
          followUps: followUps?.follow_ups || [],
          statistics: statistics || {},
          zombies: zombieData?.zombies || [],
          meetings: meetingsData?.meetings || [],
          emails: emailsData?.emails || [],
        });
        if (impulseData) setImpulse(impulseData);
        setLoading(false);
      });

      // #432: Scraper health (non-blocking)
      optionalApi("/api/scraper-health")
        .then((h) => { if (h?.scrapers?.length) setScraperHealth(h.scrapers); })
        .catch(() => {});

      // #233: Hints from public GitHub source (non-blocking)
      optionalApi("/api/public/hints")
        .then((h) => { if (h?.hints?.length) setPublicHints(h.hints); })
        .catch(() => {});
    } catch (error) {
      const message = `Dashboard-Daten konnten nicht geladen werden: ${error.message}`;
      const now = Date.now();
      if (
        message !== lastLoadErrorRef.current.message ||
        now - lastLoadErrorRef.current.at > 10000
      ) {
        lastLoadErrorRef.current = { message, at: now };
        pushToast(message, "danger");
      }
      startTransition(() => setLoading(false));
    }
  });

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [reloadKey, chrome.status?.has_profile]);

  if (loading && chrome.status?.has_profile) {
    return <LoadingPanel label="Dashboard wird vorbereitet..." />;
  }

  const dueFollowUps = data.followUps.filter((item) => item.faellig);
  const interviewCount = data.statistics?.applications_by_status?.interview || 0;
  const applicationsTotal = Number(data.statistics?.total_applications || data.applications?.length || 0);  // #199: use total from statistics (includes archived)
  const applicationsCount = applicationsTotal;
  const applicationTimestamps = (data.applications || [])
    .map((item) => Date.parse(item?.applied_at || item?.created_at || item?.updated_at || ""))
    .filter((timestamp) => Number.isFinite(timestamp));
  // #367: Multiple perspectives for applications per week
  const metricPerspectives = (() => {
    const fmt = (v) => new Intl.NumberFormat("de-DE", {
      minimumFractionDigits: v > 0 && v < 10 ? 1 : 0,
      maximumFractionDigits: v > 0 && v < 10 ? 1 : 0,
    }).format(v);
    const now = Date.now();
    const day = 1000 * 60 * 60 * 24;
    const perspectives = [];
    // 0: Last 30 days
    const last30 = applicationTimestamps.filter((t) => now - t <= 30 * day).length;
    const weeks30 = 30 / 7;
    perspectives.push({ value: fmt(applicationsCount ? last30 / weeks30 : 0), note: "Ø seit 1 Monat" });
    // 1: Last 365 days
    const last365 = applicationTimestamps.filter((t) => now - t <= 365 * day).length;
    const weeks365 = 365 / 7;
    perspectives.push({ value: fmt(applicationsCount ? last365 / weeks365 : 0), note: "Ø seit 1 Jahr" });
    // 2: Total (all time)
    if (applicationTimestamps.length) {
      const earliest = Math.min(...applicationTimestamps);
      const elapsedDays = Math.max(1, Math.ceil((now - earliest) / day) + 1);
      perspectives.push({ value: fmt(applicationsCount / (elapsedDays / 7)), note: "Ø gesamt" });
    } else {
      perspectives.push({ value: fmt(applicationsCount), note: "Ø gesamt" });
    }
    // 3: Since PBP usage (profile created_at)
    const profileCreated = Date.parse(data.statistics?.profile_created_at || "");
    if (Number.isFinite(profileCreated)) {
      const daysSince = Math.max(1, Math.ceil((now - profileCreated) / day) + 1);
      perspectives.push({ value: fmt(applicationsCount / (daysSince / 7)), note: "Ø seit PBP-Start" });
    } else {
      perspectives.push(perspectives[2]); // fallback to total
    }
    // 4: Per analyzed job
    const totalJobs = (data.statistics?.active_jobs || 0) + (data.statistics?.dismissed_jobs || 0);
    if (totalJobs > 0) {
      perspectives.push({ value: fmt(applicationsCount / totalJobs * 100), note: `pro 100 Stellen (${totalJobs} analysiert)` });
    } else {
      perspectives.push({ value: "—", note: "Noch keine Stellen analysiert" });
    }
    return perspectives;
  })();
  const currentMetric = metricPerspectives[metricPerspective % metricPerspectives.length];
  const applicationsPerWeek = currentMetric.value;
  const appliedJobHashes = new Set(
    (data.applications || [])
      .filter((a) => a.job_hash && !["abgelehnt", "zurueckgezogen", "abgelaufen"].includes(a.status))
      .map((a) => a.job_hash)
  );
  const unappliedJobsCount = data.jobs.filter((j) => !appliedJobHashes.has(j.hash)).length;
  const activeJobsCount = data.jobs.length;
  const salaryMetrics = buildAnnualSalaryMetrics(data.jobs);
  const salaryEstimated = Boolean(salaryMetrics.allEstimated);
  const salaryCount = Number(salaryMetrics.annualBasisCount || 0);
  const salaryMin = Number(salaryMetrics.averageMin);
  const salaryMax = Number(salaryMetrics.averageMax);
  const hasSalaryMin = Number.isFinite(salaryMin);
  const hasSalaryMax = Number.isFinite(salaryMax);
  const salaryAverage = hasSalaryMin && hasSalaryMax
    ? Math.round((salaryMin + salaryMax) / 2)
    : hasSalaryMin
      ? Math.round(salaryMin)
      : hasSalaryMax
        ? Math.round(salaryMax)
        : null;
  const fmtNum = (n) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 }).format(Math.round(n));
  const salaryBandText = hasSalaryMin && hasSalaryMax
    ? `${fmtNum(salaryMin)} – ${fmtNum(salaryMax)} EUR`
    : hasSalaryMin
      ? formatCurrency(salaryMin)
      : hasSalaryMax
        ? formatCurrency(salaryMax)
        : "Keine Angabe";
  const lastSearchAt = chrome.searchStatus?.last_search || "";
  const searchDaysAgo = Number(chrome.searchStatus?.days_ago);
  const hasSearchDays = Number.isFinite(searchDaysAgo);
  const secondInterviewCount = Number(data.statistics?.applications_by_status?.zweitgespraech || 0);
  const activeInterviewCount = interviewCount + secondInterviewCount;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const inSevenDays = new Date(today);
  inSevenDays.setDate(inSevenDays.getDate() + 7);
  const upcomingInterviewTodos = data.followUps
    .filter((item) => {
      const status = String(item?.app_status || "").toLowerCase();
      if (status !== "interview" && status !== "zweitgespraech") return false;
      const timestamp = Date.parse(item?.scheduled_date || "");
      if (Number.isNaN(timestamp)) return false;
      const eventDate = new Date(timestamp);
      return eventDate >= today && eventDate <= inSevenDays;
    })
    .sort((left, right) => String(left.scheduled_date || "").localeCompare(String(right.scheduled_date || "")));
  const needsSearchTodo = !lastSearchAt || !hasSearchDays || searchDaysAgo > 0;
  const appliedCoverage = activeJobsCount > 0 ? applicationsCount / activeJobsCount : 0;
  const activeSourceCount = Number(chrome.workspace?.sources?.active || 0);
  const needsMoreSourcesTodo = activeJobsCount >= 3 && appliedCoverage >= 0.6 && activeSourceCount < 2;
  const todoItems = [];

  if (needsSearchTodo) {
    todoItems.push({
      id: "jobsuche",
      title: "Neue Jobsuche starten",
      description:
        lastSearchAt && hasSearchDays
          ? `Die letzte Jobsuche war vor ${searchDaysAgo} ${searchDaysAgo === 1 ? "Tag" : "Tagen"}.`
          : "Heute wurde noch keine Jobsuche durchgeführt.",
      tone: "danger",
      actionLabel: "Jetzt starten",
      action: () => copyPrompt("/jobsuche_workflow"),
    });
  }

  // Interview-Termine werden jetzt im Meeting-Widget angezeigt (#140)
  // Nur wenn KEINE Follow-Ups vorhanden, aber Interviews laufen, als TODO zeigen
  if (activeInterviewCount > 0 && upcomingInterviewTodos.length === 0) {
    todoItems.push({
      id: "interviews",
      title: "Interview vorbereiten",
      description: `${activeInterviewCount} Bewerbung(en) sind im Interview-Status.`,
      tone: "amber",
      actionLabel: "Vorbereiten",
      action: () => copyPrompt("/interview_vorbereitung"),
    });
  }

  if (dueFollowUps.length > 0) {
    todoItems.push({
      id: "followups",
      title: "Nachfragen nicht vergessen",
      description: `Bei ${dueFollowUps.length} Bewerbung(en) solltest du nachhaken.`,
      tone: "sky",
      actionLabel: "Öffnen",
      action: () => navigateTo("bewerbungen"),
    });
  }

  if (data.zombies.length > 0) {
    todoItems.push({
      id: "zombies",
      title: "Lange keine Antwort bekommen",
      description: `${data.zombies.length} Bewerbung(en) warten seit ueber 60 Tagen auf Rueckmeldung.`,
      tone: "amber",
      actionLabel: "Bewerbungen",
      action: () => navigateTo("bewerbungen"),
    });
  }

  if (needsMoreSourcesTodo) {
    todoItems.push({
      id: "quellen",
      title: "Neue Quellen hinzufügen",
      description: `${applicationsCount} von ${activeJobsCount} aktiven Stellen sind bereits in Bewerbungen.`,
      tone: "success",
      actionLabel: "Quellen",
      action: () => navigateTo("einstellungen"),
    });
  }

  const workspaceReadiness = chrome.workspace?.readiness || {};
  const workspaceTodos = Array.isArray(chrome.workspace?.todos) ? chrome.workspace.todos : [];
  const profileCompleteness = Number(chrome.workspace?.profile?.completeness || 0);
  const jobsWithoutDescription = Number(chrome.workspace?.jobs?.ohne_beschreibung || 0);

  async function runWorkspaceAction(action) {
    if (!action) return;
    if (String(action.typ || "") === "beschreibung_nachladen" || String(action.aktion || "").includes("beschreibung_fehlt")) {
      navigateTo("stellen", { missingDescriptionOnly: true });
      return;
    }
    if (action.action_type === "prompt" && action.action_target) {
      await copyPrompt(action.action_target);
      return;
    }
    if (action.action_type === "page" && action.action_target) {
      navigateTo(action.action_target);
    }
  }

  if (!chrome.status?.has_profile) {
    return (
      <div id="page-dashboard" className="page active">
        <PageHeader
          title="Dashboard"
          description="Hier siehst du auf einen Blick, was als Nächstes zu tun ist."
          eyebrow="Uebersicht"
        />

        <div id="welcome-screen" className="grid gap-6">
          <Card className="glass-hero rounded-2xl p-8">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.9fr)]">
              <div className="space-y-5">
                <Badge tone="sky">Dein Bewerbungs-Begleiter</Badge>
                <h2 className="font-display text-4xl font-semibold tracking-tight text-ink">
                  Willkommen bei PBP
                </h2>
                <p className="max-w-2xl text-base text-muted">
                  PBP hilft dir Schritt für Schritt durch den Bewerbungsprozess — vom
                  Lebenslauf bis zum Vorstellungsgespräch. Alles bleibt auf deinem Rechner.
                </p>
                <p className="max-w-2xl text-sm text-muted/70">
                  Du musst nicht wissen, was du tun sollst — PBP zeigt dir bei jedem
                  Schritt, was als Nächstes sinnvoll ist.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => navigateTo("profil")}>
                    Starte dein Profil (ca. 10 Minuten)
                    <ArrowRight size={15} />
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => navigateTo("profil", { composer: "document" })}
                  >
                    <Upload size={15} />
                    Ich habe schon Unterlagen (optional)
                  </Button>
                </div>
              </div>

              <div className="grid gap-4">
                {[
                  {
                    title: "Schritt 1 — Profil",
                    text: "Erzähl Claude von dir. Deine Erfahrung, deine Stärken, deine Wünsche.",
                  },
                  {
                    title: "Schritt 2 — Stellen finden",
                    text: "PBP durchsucht Jobbörsen und zeigt dir passende Stellen mit Bewertung.",
                  },
                  {
                    title: "Schritt 3 — Bewerben",
                    text: "Anschreiben erstellen, Bewerbungen verfolgen, Termine im Blick behalten.",
                  },
                ].map((item) => (
                  <Card key={item.title} className="glass-card-soft rounded-xl shadow-none">
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">
                      {item.title}
                    </p>
                    <p className="mt-3 text-sm leading-6 text-ink">{item.text}</p>
                  </Card>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div id="page-dashboard" className="page active">
      <div className="mb-6 flex items-baseline gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Dashboard</h1>
      </div>

      {publicHints.filter((h) => !dismissedHints.includes(h.id)).length > 0 && (
        <div className="mb-4 space-y-2">
          {publicHints.filter((h) => !dismissedHints.includes(h.id)).map((hint) => (
            <div
              key={hint.id}
              className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${
                hint.type === "warning"
                  ? "border-amber-500/20 bg-amber-500/5 text-amber-200"
                  : "border-sky-500/20 bg-sky-500/5 text-sky-200"
              }`}
            >
              <div>
                {hint.title && <span className="font-medium">{hint.title} </span>}
                {hint.text}
              </div>
              <button
                type="button"
                onClick={() => {
                  const next = [...dismissedHints, hint.id];
                  setDismissedHints(next);
                  try { localStorage.setItem("pbp_dismissed_hints", JSON.stringify(next)); } catch {}
                }}
                className="shrink-0 rounded p-0.5 opacity-50 hover:opacity-100 transition-opacity"
                title="Schliessen"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Bewerbungen" value={applicationsCount} note={`${applicationsCount} geschrieben${unappliedJobsCount > 0 ? ` / ${unappliedJobsCount} unbearbeitete Stellen` : ""}`} tone="sky" />
        <MetricCard
          label={<span className="flex items-center gap-1.5">Bew. / Woche<button type="button" onClick={() => setMetricPerspective((p) => (p + 1) % metricPerspectives.length)} className="rounded p-0.5 text-muted/30 hover:text-sky transition-colors" title="Andere Perspektive"><RefreshCw size={11} /></button></span>}
          value={applicationsPerWeek}
          note={currentMetric.note}
          tone="sky"
        />
        <MetricCard
          label={`Gehaltsdurchschnitt${salaryEstimated ? " (geschätzt)" : ""}`}
          value={salaryAverage !== null ? formatCurrency(salaryAverage) : "Keine Angabe"}
          note={salaryCount > 0 ? `Auf Basis von ${salaryCount} Stellen mit Jahresgehalt` : "Noch keine Gehaltsdaten"}
          tone="success"
        />
        <MetricCard label={`Gehaltsbandbreite${salaryEstimated ? " (geschätzt)" : ""}`} value={salaryBandText} note="Durchschnittliche Min/Max-Spanne" tone="success" />
      </div>

      {/* #450: Layout auf volle Breite — Schnellimport entfernt */}
      <div className="mb-5 grid gap-4">
          {/* Im Fluss (Readiness Card) */}
          <Card className="rounded-2xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={readinessTone(workspaceReadiness.tone)}>{workspaceReadiness.label || "Nächster Schritt"}</Badge>
                  <span className="text-xs text-muted/50">{profileCompleteness}% Profil vollständig</span>
                  {jobsWithoutDescription > 0 ? (
                    <span className="text-xs text-amber">{jobsWithoutDescription} Treffer mit unsicherem Score</span>
                  ) : null}
                </div>
                <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.15em] text-muted/55">Nächster sinnvoller Schritt</p>
                <h2 className="mt-1 text-base font-semibold text-ink">{workspaceReadiness.headline || "Weiter im Prozess"}</h2>
                <p className="mt-1 max-w-3xl text-sm text-muted">
                  {workspaceReadiness.description || "PBP zeigt dir hier immer, was als Nächstes sinnvoll ist."}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                {workspaceReadiness.action_label && workspaceReadiness.action_target !== "dashboard" ? (
                  <Button size="sm" variant="secondary" onClick={() => runWorkspaceAction(workspaceReadiness)}>
                    {workspaceReadiness.action_label}
                  </Button>
                ) : null}
              </div>
            </div>

            {(todoItems.length > 0 || workspaceTodos.length > 0) && (
              <div className="mt-4 grid gap-2">
                {todoItems.map((todo) => (
                  <div
                    key={todo.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.05] px-4 py-3"
                  >
                    <div className="min-w-0 flex items-center gap-2.5">
                      <Badge tone={todo.tone}>
                        {todo.id === "jobsuche" ? "Priorität 1" : todo.id === "interviews" ? "Priorität 2" : todo.id === "followups" ? "Priorität 3" : "Empfehlung"}
                      </Badge>
                      <div>
                        <p className="text-[13px] font-semibold text-ink">{todo.title}</p>
                        <p className="mt-0.5 text-[12px] text-muted/60">{todo.description}</p>
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" onClick={todo.action}>
                      {todo.actionLabel}
                    </Button>
                  </div>
                ))}
                {workspaceTodos.slice(0, 2).map((todo) => (
                  <div
                    key={`ws-${todo.typ}-${todo.text}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.05] px-4 py-3"
                  >
                    <div className="min-w-0 flex items-center gap-2.5">
                      <Badge tone={todo.prioritaet === "hoch" ? "amber" : "blue"}>Hinweis</Badge>
                      <div>
                        <p className="text-[13px] font-semibold text-ink">{todo.text}</p>
                        <p className="mt-0.5 text-[12px] text-muted/60">
                          {todo.prioritaet === "hoch" ? "Bitte zuerst prüfen." : "Optional, aber sinnvoll für sauberere Ergebnisse."}
                        </p>
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => runWorkspaceAction(todo)}>
                      Öffnen
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Heute fuer dich (Impulse) */}
          {impulse?.enabled && impulse?.impulse?.text && (
            <Card className="rounded-2xl border-amber-600/30 bg-amber-950/10">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.15em] text-amber-400/60">
                    {impulse.impulse.title || "Heute für dich"}
                  </p>
                  <p className="text-sm italic text-muted">{impulse.impulse.text}</p>
                </div>
                <button
                  className="shrink-0 text-xs text-muted/40 hover:text-muted"
                  title="Tagesimpuls ausblenden"
                  onClick={async () => {
                    try {
                      await postJson("/api/daily-impulse/toggle");
                      setImpulse((prev) => ({ ...prev, enabled: false }));
                    } catch {}
                  }}
                >
                  ausblenden
                </button>
              </div>
            </Card>
          )}
      </div>

      {/* #421: Anstehende Termine direkt unter Im Fluss (nur wenn vorhanden, max 5) */}
      {(() => {
        const interviewPseudoMeetings = upcomingInterviewTodos
          .filter((fu) => !data.meetings.some((m) => m.application_id === fu.application_id && m.meeting_date?.startsWith(fu.scheduled_date)))
          .map((fu) => ({
            id: `interview-${fu.id}`,
            title: "Interview vorbereiten",
            meeting_date: fu.scheduled_date + "T09:00:00",
            app_company: fu.company || fu.title || "",
            app_title: fu.title || "",
            platform: null,
            meeting_url: null,
            application_id: fu.application_id,
            _isInterview: true,
          }));
        const allMeetings = [...data.meetings, ...interviewPseudoMeetings]
          .sort((a, b) => String(a.meeting_date || "").localeCompare(String(b.meeting_date || "")));
        if (allMeetings.length === 0) return null;
        return (
          <Card className="mb-5 rounded-2xl">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="text-sm font-semibold text-ink hover:text-sky transition-colors flex items-center gap-1.5"
                onClick={() => navigateTo("kalender")}
              >
                <Calendar size={14} className="text-teal/60" />
                Anstehende Termine
              </button>
            </div>
            <div className="mt-3 grid gap-2">
              {allMeetings.slice(0, 5).map((meeting) => {
                const meetingDate = new Date(meeting.meeting_date);
                const now = new Date();
                const diffMs = meetingDate - now;
                const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
                const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                const countdown =
                  diffDays > 1
                    ? `in ${diffDays} Tagen`
                    : diffDays === 1
                      ? "morgen"
                      : diffHours > 0
                        ? `in ${diffHours} Stunden`
                        : diffMs > 0
                          ? "jetzt gleich"
                          : "vergangen";
                const isMeetingToday = diffDays === 0 && diffMs > 0;
                const isPrivate = meeting.is_private;
                const platformIcon = meeting.platform === "teams" ? "Teams" :
                  meeting.platform === "zoom" ? "Zoom" :
                  meeting.platform === "google_meet" ? "Meet" : "";
                return (
                  <div
                    key={meeting.id}
                    className={`flex items-center justify-between gap-3 rounded-xl border px-4 py-3 cursor-pointer transition-colors hover:bg-white/[0.03] ${
                      isMeetingToday
                        ? "border-teal/30 bg-teal/5"
                        : "border-white/[0.04]"
                    }`}
                    onClick={() => {
                      // #395/#421: Click navigates to application or calendar
                      if (isPrivate) {
                        navigateTo("kalender");
                      } else if (meeting.application_id) {
                        navigateTo("bewerbungen", { highlight: meeting.application_id });
                      } else {
                        navigateTo("kalender");
                      }
                    }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-semibold text-ink">
                        {isPrivate ? "Geblockt" : (meeting.title || meeting.app_title || "Termin")}
                      </p>
                      {!isPrivate && (
                        <p className="text-[12px] text-muted/60">
                          {meeting.app_company && (
                            <span className="font-medium text-muted/80">{meeting.app_company} — </span>
                          )}
                          {formatDate(meeting.meeting_date)}{" "}
                          {meetingDate.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr
                          {platformIcon && (
                            <span className="ml-1.5 rounded bg-sky/15 px-1.5 py-px text-[10px] font-bold text-sky">
                              {platformIcon}
                            </span>
                          )}
                        </p>
                      )}
                      {isPrivate && (
                        <p className="text-[12px] text-muted/40">
                          {formatDate(meeting.meeting_date)}{" "}
                          {meetingDate.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr
                        </p>
                      )}
                      <p className={`mt-0.5 text-[11px] font-medium ${
                        isMeetingToday ? "text-teal" : diffDays <= 3 ? "text-amber" : "text-muted/50"
                      }`}>
                        {countdown}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {!meeting._isInterview && !meeting.is_follow_up && !isPrivate && (
                        <a href={`/api/meetings/${meeting.id}/ics`} download
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1.5 text-[11px] font-semibold text-muted/50 transition hover:bg-white/10 hover:text-ink"
                          title="Als .ics exportieren">
                          <Download size={12} /> .ics
                        </a>
                      )}
                      {meeting._isInterview ? (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); copyPrompt("/interview_vorbereitung"); }}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-amber/15 px-3 py-1.5 text-[12px] font-semibold text-amber transition hover:bg-amber/25"
                        >
                          <Calendar size={14} />
                          Vorbereiten
                        </button>
                      ) : meeting.is_follow_up ? (
                        // #453 / v1.5.7: Follow-ups abschliessen
                        <>
                          <button
                            type="button"
                            onClick={async (e) => {
                              e.stopPropagation();
                              const followId = String(meeting.id).replace(/^followup-/, "");
                              try {
                                await postJson(`/api/follow-ups/${followId}/complete`, {});
                                pushToast("Nachfass als erledigt markiert.", "success");
                                loadData();
                                refreshChrome({ quiet: true });
                              } catch (err) {
                                pushToast(`Fehler: ${err.message}`, "danger");
                              }
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-teal/15 px-3 py-1.5 text-[12px] font-semibold text-teal transition hover:bg-teal/25"
                            title="Nachfass erledigt"
                          >
                            Erledigt
                          </button>
                          <button
                            type="button"
                            onClick={async (e) => {
                              e.stopPropagation();
                              const followId = String(meeting.id).replace(/^followup-/, "");
                              try {
                                await postJson(`/api/follow-ups/${followId}/dismiss`, {});
                                pushToast("Nachfass als hinfaellig geschlossen.", "success");
                                loadData();
                                refreshChrome({ quiet: true });
                              } catch (err) {
                                pushToast(`Fehler: ${err.message}`, "danger");
                              }
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-[12px] font-semibold text-muted/70 transition hover:bg-white/10 hover:text-ink"
                            title="Nicht mehr noetig"
                          >
                            Hinf&auml;llig
                          </button>
                        </>
                      ) : !isPrivate && meeting.meeting_url ? (
                        <a
                          href={meeting.meeting_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-teal/15 px-3 py-1.5 text-[12px] font-semibold text-teal transition hover:bg-teal/25"
                        >
                          <Video size={14} />
                          Beitreten
                        </a>
                      ) : null}
                      {/* #453 / v1.5.7: Durchgefuehrt-Button fuer vergangene Meetings */}
                      {!meeting._isInterview && !meeting.is_follow_up && !isPrivate && diffMs < 0 && (meeting.status === "geplant" || meeting.status === "bestaetigt") && (
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              await putJson(`/api/meetings/${meeting.id}`, { status: "durchgefuehrt" });
                              pushToast("Termin als durchgef\u00fchrt markiert.", "success");
                              loadData();
                              refreshChrome({ quiet: true });
                            } catch (err) {
                              pushToast(`Fehler: ${err.message}`, "danger");
                            }
                          }}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-teal/15 px-3 py-1.5 text-[12px] font-semibold text-teal transition hover:bg-teal/25"
                          title="Termin hat stattgefunden"
                        >
                          Durchgef&uuml;hrt
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        );
      })()}

      {/* #450: Dokument-Import (saubere Version, gleiche Logik wie Docs-Seite) */}
      <DashboardDocumentImport pushToast={pushToast} refreshChrome={refreshChrome} />

      <div id="dashboard-content" className="grid gap-5">
        {/* Schnellzugriff (full width) */}
        <Card className="rounded-2xl">
          <h2 className="text-sm font-semibold text-ink">Schnellzugriff</h2>
          {[
            {
              title: "Erste Schritte",
              items: [
                { prompt: "/ersterfassung", label: "Kennenlernen", desc: "Profil im Gespraech erstellen", icon: PlayCircle },
                { prompt: "/willkommen", label: "Wo stehe ich?", desc: "Dein aktueller Stand", icon: BookOpen },
                { prompt: "/profil_erweiterung", label: "Profil ergaenzen", desc: "Unterlagen auswerten lassen", icon: PlusCircle, isNew: true },
              ],
            },
            {
              title: "Jobsuche & Bewerbung",
              items: [
                { prompt: "/jobsuche_workflow", label: "Jobsuche starten", desc: "Jobboersen durchsuchen lassen", icon: Search },
                { prompt: "/bewerbung_schreiben", label: "Bewerbung schreiben", desc: "Anschreiben erstellen lassen", icon: Send },
                { prompt: "/bewerbungs_uebersicht", label: "Uebersicht", desc: "Was laeuft gerade?", icon: ClipboardList },
              ],
            },
            {
              title: "Interview & Verhandlung",
              items: [
                { prompt: "/interview_vorbereitung", label: "Interview vorbereiten", desc: "Typische Fragen ueben", icon: Briefcase },
                { prompt: "/interview_simulation", label: "Uebungsgespraech", desc: "Probelauf mit Claude", icon: Mic, isNew: true },
                { prompt: "/gehaltsverhandlung", label: "Gehalt verhandeln", desc: "Strategie besprechen", icon: HandCoins, isNew: true },
              ],
            },
            {
              title: "Analyse & Strategie",
              items: [
                { prompt: "/profil_analyse", label: "Staerken erkennen", desc: "Was kann ich besonders gut?", icon: BarChart3 },
                { prompt: "/profil_ueberpruefen", label: "Profil pruefen", desc: "Fehler finden und korrigieren", icon: UserCheck },
                { prompt: "/netzwerk_strategie", label: "Netzwerk aufbauen", desc: "Kontakte gezielt nutzen", icon: Network, isNew: true },
              ],
            },
          ].map((group) => (
            <div key={group.title} className="mt-3">
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-teal/60">{group.title}</p>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
                {group.items.map(({ prompt, label, desc, icon: Icon, isNew }) => (
                  <button
                    key={prompt}
                    type="button"
                    className="glass-tab flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-left transition"
                    onClick={() => copyPrompt(prompt)}
                  >
                    <Icon size={16} className="shrink-0 text-teal/50" />
                    <div className="min-w-0">
                      <span className="flex items-center gap-1.5 text-[13px] font-semibold text-ink/90">
                        {label}
                        {isNew ? <span className="rounded bg-teal/15 px-1.5 py-px text-[10px] font-bold text-teal">NEU</span> : null}
                      </span>
                      <span className="block truncate text-[11px] text-muted/60">{desc}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </Card>

        <div className="grid gap-3 xl:grid-cols-2">
          <Card className="overflow-hidden rounded-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-baseline gap-2">
                <h2 className="text-sm font-semibold text-ink">Top-Stellen</h2>
                <span className="text-[11px] text-muted/40">
                  {chrome.searchStatus?.last_search
                    ? `Aktualisiert ${chrome.searchStatus.days_ago === 0 ? "heute" : chrome.searchStatus.days_ago === 1 ? "gestern" : `vor ${chrome.searchStatus.days_ago} Tagen`}`
                    : "Noch nie gesucht"}
                </span>
              </div>
              <Button size="sm" variant="ghost" onClick={() => navigateTo("stellen")}>
                Alle
              </Button>
            </div>
            {/* #432: Compact scraper health dots */}
            {scraperHealth.length > 0 && (
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-muted/50">
                <span>Scraper:</span>
                {scraperHealth.map((s) => {
                  const ok = s.is_active && s.consecutive_failures < 3;
                  const warn = s.is_active && s.consecutive_failures >= 3 && s.consecutive_failures < 10;
                  const off = !s.is_active;
                  const color = off ? "bg-red-500/60" : warn ? "bg-amber-400/80" : ok ? "bg-emerald-400/80" : "bg-zinc-500/40";
                  const tip = `${s.scraper_name}: ${off ? "deaktiviert" : s.consecutive_failures > 0 ? `${s.consecutive_failures} Fehler` : "OK"} (${s.total_successes}/${s.total_runs} erfolgreich)`;
                  return (
                    <span key={s.scraper_name} className="flex items-center gap-1" title={tip}>
                      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
                      {s.scraper_name}
                    </span>
                  );
                })}
              </div>
            )}
            <div className="mt-3 grid gap-2">
              {(() => {
                const appliedHashes = new Set(
                  (data.applications || []).map((a) => a.job_hash).filter(Boolean)
                );
                const topJobs = data.jobs
                  .filter((j) => !appliedHashes.has(j.hash))
                  .sort((a, b) => (b.score || 0) - (a.score || 0))
                  .slice(0, 3);
                return topJobs.length ? (
                  topJobs.map((job) => (
                    <button
                      key={job.hash}
                      type="button"
                      className="group flex min-w-0 w-full cursor-pointer items-center justify-between gap-3 rounded-xl border border-white/[0.04] px-4 py-3 text-left transition-all duration-150 hover:-translate-y-[1px] hover:border-sky/35 hover:bg-white/[0.06] hover:shadow-[0_8px_20px_rgba(14,165,233,0.12)] hover:text-ink"
                      onClick={() => navigateTo("stellen", { focus: "job", jobHash: job.hash })}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-ink">{job.title}</p>
                        <p className="truncate text-[12px] text-muted/50">
                          {job.company || "Unbekannt"}{job.location ? ` - ${job.location}` : ""}
                        </p>
                      </div>
                      <span className="shrink-0"><Badge tone="amber">Score {job.score || 0}</Badge></span>
                    </button>
                  ))
                ) : (
                  <p className="py-4 text-center text-[13px] text-muted/50">
                    Noch keine Stellen.{" "}
                    <button type="button" className="text-teal/70 hover:text-teal" onClick={() => copyPrompt("/jobsuche_workflow")}>
                      Suche starten
                    </button>
                  </p>
                );
              })()}
            </div>
          </Card>

          {/* Recent Emails (#136) */}
          <Card className="overflow-hidden rounded-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">
                <Mail size={14} className="mr-1.5 inline-block text-teal/60" />
                E-Mails
                {data.emails.filter((e) => !e.application_id).length > 0 && (
                  <span className="ml-1.5 rounded-full bg-amber/20 px-1.5 py-px text-[10px] font-bold text-amber">
                    {data.emails.filter((e) => !e.application_id).length} offen
                  </span>
                )}
              </h2>
              <EmailUploadButton pushToast={pushToast} />
            </div>
            <div className="mt-3 grid gap-1.5">
              {data.emails.length > 0 ? (
                data.emails.slice(0, 6).map((em) => (
                  <button
                    key={em.id}
                    type="button"
                    className="flex w-full min-w-0 items-center gap-2 rounded-lg border border-white/[0.04] px-3 py-2 text-left transition hover:bg-white/[0.04]"
                    onClick={async () => {
                      try {
                        const full = await api(`/api/emails/${em.id}`);
                        setEmailDetail(full);
                      } catch {
                        setEmailDetail(em);
                      }
                    }}
                  >
                    <span className={`shrink-0 text-sm ${em.direction === "ausgang" ? "text-sky" : "text-amber"}`}>
                      {em.direction === "ausgang" ? "↗" : "↙"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] text-ink">{em.subject || "Ohne Betreff"}</p>
                      <p className="truncate text-[11px] text-muted/50">
                        {em.sender || em.recipients}
                        {em.sent_date && <span className="ml-1.5">{formatDate(em.sent_date)}</span>}
                      </p>
                    </div>
                    {!em.application_id && (
                      <Badge tone="amber">Offen</Badge>
                    )}
                    {em.detected_status && (
                      <Badge tone="sky">{em.detected_status}</Badge>
                    )}
                  </button>
                ))
              ) : (
                <p className="py-4 text-center text-[13px] text-muted/50">
                  Keine E-Mails importiert. Drag &amp; Drop oder Button nutzen.
                </p>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Email Detail Modal (#136) */}
      {emailDetail && (
        <EmailDetailModal
          email={emailDetail}
          applications={data.applications}
          onClose={() => setEmailDetail(null)}
          pushToast={pushToast}
          onUpdate={() => { setEmailDetail(null); loadData(); }}
        />
      )}
    </div>
  );
}


function EmailDetailModal({ email, applications, onClose, pushToast, onUpdate }) {
  const [assignApp, setAssignApp] = useState(email.application_id || "");
  const [applying, setApplying] = useState(false);

  async function confirmMatch() {
    if (!assignApp) return;
    try {
      await postJson(`/api/emails/${email.id}/confirm-match`, { application_id: assignApp });
      pushToast("E-Mail zugeordnet.", "success");
      onUpdate();
    } catch (err) {
      pushToast(`Zuordnung fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  async function applyStatus(status) {
    setApplying(true);
    try {
      await postJson(`/api/emails/${email.id}/apply-status`, { status });
      pushToast(`Status '${status}' angewendet.`, "success");
      onUpdate();
    } catch (err) {
      pushToast(`Status konnte nicht angewendet werden: ${err.message}`, "danger");
    } finally {
      setApplying(false);
    }
  }

  async function deleteEmail() {
    try {
      await api(`/api/emails/${email.id}`, { method: "DELETE" });
      pushToast("E-Mail gelöscht.", "success");
      onUpdate();
    } catch (err) {
      pushToast(`Löschen fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  return (
    <Modal
      open={true}
      title={email.subject || "E-Mail"}
      onClose={onClose}
      footer={
        <div className="flex justify-between">
          <Button variant="ghost" className="text-coral" onClick={deleteEmail}>Löschen</Button>
          <Button onClick={onClose}>Schließen</Button>
        </div>
      }
    >
      <div className="grid gap-4">
        <Card className="glass-card-soft rounded-xl shadow-none">
          <div className="grid gap-1.5 text-sm">
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">Von:</span>
              <span className="text-ink">{email.sender}</span>
            </div>
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">An:</span>
              <span className="text-ink">{email.recipients}</span>
            </div>
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">Datum:</span>
              <span className="text-ink">{formatDate(email.sent_date)}</span>
            </div>
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">Richtung:</span>
              <Badge tone={email.direction === "ausgang" ? "sky" : "amber"}>
                {email.direction === "ausgang" ? "Ausgehend" : "Eingehend"}
              </Badge>
            </div>
          </div>
        </Card>

        {/* Body text */}
        {email.body_text && (
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Inhalt</p>
            <div className="mt-2 max-h-60 overflow-y-auto rounded-lg bg-white/[0.02] p-3 text-sm text-muted/70 whitespace-pre-wrap">
              {email.body_text}
            </div>
          </Card>
        )}

        {/* Detected status */}
        {email.detected_status && (
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Erkannter Status</p>
            <div className="mt-2 flex items-center gap-3">
              <Badge tone="sky">{email.detected_status}</Badge>
              <span className="text-xs text-muted/50">
                Konfidenz: {Math.round((email.detected_status_confidence || 0) * 100)}%
              </span>
              {email.application_id && (
                <Button size="sm" onClick={() => applyStatus(email.detected_status)} disabled={applying}>
                  Status übernehmen
                </Button>
              )}
            </div>
          </Card>
        )}

        {/* Attachments */}
        {(email.attachments_meta || []).length > 0 && (
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
              Anhänge ({email.attachments_meta.length})
            </p>
            <div className="mt-2 grid gap-1">
              {email.attachments_meta.map((att, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-ink">
                  <span className="text-muted/50">📎</span>
                  <span>{att.filename}</span>
                  {att.imported && <Badge tone="success">Importiert</Badge>}
                  {att.duplicate_of && <Badge tone="neutral">Duplikat</Badge>}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Assign to application */}
        <Card className="glass-card-soft rounded-xl shadow-none">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Bewerbung zuordnen</p>
          <div className="mt-2 flex gap-2">
            <SelectInput
              className="flex-1"
              value={assignApp}
              onChange={(e) => setAssignApp(e.target.value)}
            >
              <option value="">— Nicht zugeordnet —</option>
              {(applications || []).map((app) => (
                <option key={app.id} value={app.id}>
                  {app.title} @ {app.company}
                </option>
              ))}
            </SelectInput>
            <Button size="sm" onClick={confirmMatch} disabled={!assignApp}>
              Zuordnen
            </Button>
          </div>
          {email.match_confidence > 0 && email.match_confidence < 1 && (
            <p className="mt-1 text-xs text-muted/50">
              Auto-Match Konfidenz: {Math.round(email.match_confidence * 100)}%
            </p>
          )}
        </Card>
      </div>
    </Modal>
  );
}


function DashboardDocumentImport({ pushToast, refreshChrome }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  async function processFiles(files) {
    if (!files?.length) return;
    setUploading(true);
    let count = 0;
    try {
      const signatures = new Set();
      for (const file of files) {
        const sig = createFileSignature(file);
        if (signatures.has(sig)) continue;
        signatures.add(sig);
        await uploadDocumentFile(file);
        count++;
      }
      if (count > 0) {
        pushToast(`${count} Dokument${count > 1 ? "e" : ""} hochgeladen`, "success");
        await refreshChrome({ forceReload: true });
      }
    } catch (err) {
      pushToast(`Upload-Fehler: ${err.message}`, "danger");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card className="mb-5 rounded-2xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Upload size={14} className="text-teal/60" />
          <h2 className="text-sm font-semibold text-ink">Dokumente importieren</h2>
        </div>
        <div className="flex items-center gap-2">
          <EmailUploadButton pushToast={pushToast} />
          <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.doc,.txt,.csv,.json,.xml,.rtf" className="hidden"
            onChange={async (e) => { await processFiles(Array.from(e.target.files || [])); if (fileRef.current) fileRef.current.value = ""; }} />
          <Button size="sm" variant="ghost" onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? "Importiere..." : "Dateien auswaehlen"}
          </Button>
        </div>
      </div>
      <div
        className={`mt-3 rounded-xl border-2 border-dashed px-4 py-4 text-center text-xs transition ${
          dragActive ? "border-sky/60 bg-sky/10 text-sky" : "border-white/10 text-muted/40"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={(e) => { e.preventDefault(); if (e.currentTarget.contains(e.relatedTarget)) return; setDragActive(false); }}
        onDrop={async (e) => { e.preventDefault(); setDragActive(false); const files = await extractDroppedFiles(e.dataTransfer); await processFiles(files); }}
      >
        {dragActive ? "Loslassen zum Hochladen" : "Dokumente oder E-Mails per Drag & Drop hier ablegen"}
      </div>
    </Card>
  );
}


function EmailUploadButton({ pushToast }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/emails/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        pushToast(data.error || "E-Mail-Upload fehlgeschlagen", "danger");
        return;
      }
      const matchInfo = data.match?.application
        ? ` → ${data.match.application.company} (${Math.round(data.match.confidence * 100)}%)`
        : " (nicht zugeordnet)";
      const statusInfo = data.detected_status?.status
        ? ` | Status: ${data.detected_status.status}`
        : "";
      const meetingInfo = data.meetings?.length
        ? ` | ${data.meetings.length} Termin(e)`
        : "";
      const docInfo = data.imported_documents
        ? ` | ${data.imported_documents} Dokument(e)`
        : "";
      pushToast(`E-Mail importiert${matchInfo}${statusInfo}${meetingInfo}${docInfo}`, "success");
    } catch (err) {
      pushToast(`Upload fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept=".msg,.eml"
        className="hidden"
        onChange={handleUpload}
      />
      <Button
        size="sm"
        variant="ghost"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
      >
        <Mail size={14} className="mr-1" />
        {uploading ? "Importiere..." : "E-Mail importieren"}
      </Button>
    </>
  );
}
