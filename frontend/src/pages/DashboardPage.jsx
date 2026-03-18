import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Briefcase,
  ClipboardList,
  FolderOpen,
  HandCoins,
  Mic,
  Network,
  PlayCircle,
  PlusCircle,
  Search,
  Send,
  UserCheck,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, optionalApi } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Button,
  Card,
  LoadingPanel,
  MetricCard,
  PageHeader,
} from "@/components/ui";
import {
  formatCurrency,
  formatDate,
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
  const { chrome, reloadKey, navigateTo, copyPrompt, pushToast } = useApp();
  const lastLoadErrorRef = useRef({ message: "", at: 0 });
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({
    jobs: [],
    applications: [],
    followUps: [],
    statistics: {},
  });

  const loadData = useEffectEvent(async () => {
    if (!chrome.status?.has_profile) {
      startTransition(() => {
        setData({
          jobs: [],
          applications: [],
          followUps: [],
          statistics: {},
        });
        setLoading(false);
      });
      return;
    }

    try {
      const [jobs, applications, followUps, statistics] = await Promise.all([
        api("/api/jobs?active=true"),
        optionalApi("/api/applications"),
        api("/api/follow-ups"),
        api("/api/statistics"),
      ]);

      startTransition(() => {
        setData({
          jobs: jobs || [],
          applications: applications?.applications || [],
          followUps: followUps?.follow_ups || [],
          statistics: statistics || {},
        });
        setLoading(false);
      });
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
  const applicationsCount = Number(data.applications?.length || data.statistics?.total_applications || 0);
  const applicationTimestamps = (data.applications || [])
    .map((item) => Date.parse(item?.applied_at || item?.created_at || item?.updated_at || ""))
    .filter((timestamp) => Number.isFinite(timestamp));
  const applicationsPerWeekRaw = (() => {
    if (!applicationsCount) return 0;
    if (!applicationTimestamps.length) return applicationsCount;
    const earliest = Math.min(...applicationTimestamps);
    const elapsedDays = Math.max(1, Math.ceil((Date.now() - earliest) / (1000 * 60 * 60 * 24)) + 1);
    return applicationsCount / (elapsedDays / 7);
  })();
  const applicationsPerWeek = new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: applicationsPerWeekRaw > 0 && applicationsPerWeekRaw < 10 ? 1 : 0,
    maximumFractionDigits: applicationsPerWeekRaw > 0 && applicationsPerWeekRaw < 10 ? 1 : 0,
  }).format(applicationsPerWeekRaw);
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
  const needsMoreSourcesTodo = activeJobsCount >= 3 && appliedCoverage >= 0.6;
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

  if (upcomingInterviewTodos.length > 0 || activeInterviewCount > 0) {
    const nextInterviewDate = upcomingInterviewTodos[0]?.scheduled_date || "";
    todoItems.push({
      id: "interviews",
      title: "Interview vorbereiten",
      description:
        upcomingInterviewTodos.length > 0
          ? `${upcomingInterviewTodos.length} Interview-Termin(e) in den nächsten 7 Tagen, nächster am ${formatDate(nextInterviewDate)}.`
          : `${activeInterviewCount} Bewerbung(en) sind im Interview-Status.`,
      tone: "amber",
      actionLabel: "Vorbereiten",
      action: () => copyPrompt("/interview_vorbereitung"),
    });
  }

  if (dueFollowUps.length > 0) {
    todoItems.push({
      id: "followups",
      title: "Follow-ups bearbeiten",
      description: `${dueFollowUps.length} Follow-up(s) sind heute oder früher fällig.`,
      tone: "sky",
      actionLabel: "Öffnen",
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

  if (!chrome.status?.has_profile) {
    return (
      <div id="page-dashboard" className="page active">
        <PageHeader
          title="Dashboard"
          description="Alle Funktionalität bleibt erhalten, aber der Einstieg ist jetzt fokussierter und klarer strukturiert."
          eyebrow="Übersicht"
        />

        <div id="welcome-screen" className="grid gap-6">
          <Card className="glass-hero rounded-2xl p-8">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.9fr)]">
              <div className="space-y-5">
                <Badge tone="sky">Neuer UI-Layer auf bestehendem Backend</Badge>
                <h2 className="font-display text-4xl font-semibold tracking-tight text-ink">
                  Willkommen beim Bewerbungs-Assistenten
                </h2>
                <p className="max-w-2xl text-base text-muted">
                  Diese React-Oberfläche nutzt dieselben FastAPI-Endpunkte wie zuvor, bringt aber
                  mehr Ordnung, klarere Hierarchien und deutlich bessere Lesbarkeit.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => navigateTo("profil")}>
                    Profil starten
                    <ArrowRight size={15} />
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => navigateTo("profil", { composer: "document" })}
                  >
                    <FolderOpen size={15} />
                    Ordner importieren
                  </Button>
                  <Button variant="ghost" onClick={() => navigateTo("einstellungen")}>
                    Einstellungen Öffnen
                  </Button>
                </div>
              </div>

              <div className="grid gap-4">
                {[
                  {
                    title: "Profil",
                    text: "Persönliche Daten, Positionen, Skills und Dokumente zentral pflegen.",
                  },
                  {
                    title: "Stellen",
                    text: "Gefundene Jobs mit Filtern, Fit-Analyse und schneller Übernahme in Bewerbungen.",
                  },
                  {
                    title: "Bewerbungen",
                    text: "TODOs, Statuswechsel, Timeline und Exportfunktionen auf einen Blick.",
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

      <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Bewerbungen" value={`${applicationsCount} / ${activeJobsCount}`} note="Bewerbungen / aktive Stellen" tone="sky" />
        <MetricCard label="Bewerbungen pro Woche" value={applicationsPerWeek} note="Ø seit erster Bewerbung" tone="sky" />
        <MetricCard
          label={`Gehaltsdurchschnitt${salaryEstimated ? " (geschätzt)" : ""}`}
          value={salaryAverage !== null ? formatCurrency(salaryAverage) : "Keine Angabe"}
          note={salaryCount > 0 ? `Auf Basis von ${salaryCount} Stellen mit Jahresgehalt` : "Noch keine Gehaltsdaten"}
          tone="success"
        />
        <MetricCard label={`Gehaltsbandbreite${salaryEstimated ? " (geschätzt)" : ""}`} value={salaryBandText} note="Durchschnittliche Min/Max-Spanne" tone="success" />
      </div>

      <div id="dashboard-content" className="grid gap-5">
        <div className="grid gap-3 xl:grid-cols-2">
            <Card className="col-span-full rounded-2xl">
              <h2 className="text-sm font-semibold text-ink">Schnellzugriff</h2>
              {[
                {
                  title: "Erste Schritte",
                  items: [
                    { prompt: "/ersterfassung", label: "Ersterfassung", desc: "Profil im Gespräch erstellen", icon: PlayCircle },
                    { prompt: "/willkommen", label: "Willkommen", desc: "Status-Übersicht", icon: BookOpen },
                    { prompt: "/profil_erweiterung", label: "Profil erweitern", desc: "Dokumente analysieren", icon: PlusCircle, isNew: true },
                  ],
                },
                {
                  title: "Jobsuche & Bewerbung",
                  items: [
                    { prompt: "/jobsuche_workflow", label: "Jobsuche", desc: "Geführter 5-Schritte Suchprozess", icon: Search },
                    { prompt: "/bewerbung_schreiben", label: "Bewerbung schreiben", desc: "Anschreiben erstellen + Export", icon: Send },
                    { prompt: "/bewerbungs_uebersicht", label: "Übersicht", desc: "Alle Aktivitäten", icon: ClipboardList },
                  ],
                },
                {
                  title: "Interview & Verhandlung",
                  items: [
                    { prompt: "/interview_vorbereitung", label: "Interview-Prep", desc: "Fragen, STAR-Antworten", icon: Briefcase },
                    { prompt: "/interview_simulation", label: "Simulation", desc: "Übungsgespräch mit Claude", icon: Mic, isNew: true },
                    { prompt: "/gehaltsverhandlung", label: "Gehalt", desc: "Verhandlungsstrategie", icon: HandCoins, isNew: true },
                  ],
                },
                {
                  title: "Analyse & Strategie",
                  items: [
                    { prompt: "/profil_analyse", label: "Profil-Analyse", desc: "Stärken & Potenziale", icon: BarChart3 },
                    { prompt: "/profil_ueberpruefen", label: "Profil prüfen", desc: "Fehler finden + korrigieren", icon: UserCheck },
                    { prompt: "/netzwerk_strategie", label: "Netzwerk", desc: "Networking-Plan", icon: Network, isNew: true },
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
        </div>

        <div className="grid gap-3 xl:grid-cols-2">
          <Card className="rounded-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">TODOs</h2>
              <Button size="sm" variant="ghost" onClick={() => navigateTo("bewerbungen")}>
                Alle
              </Button>
            </div>
            <div className="mt-3 grid gap-2">
              {todoItems.length ? (
                todoItems.map((todo) => (
                  <div
                    key={todo.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.04] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge tone={todo.tone}>
                          {todo.id === "jobsuche" ? "Priorität 1" : todo.id === "interviews" ? "Priorität 2" : todo.id === "followups" ? "Priorität 3" : "Empfehlung"}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[13px] font-semibold text-ink">{todo.title}</p>
                      <p className="mt-0.5 text-[12px] text-muted/60">{todo.description}</p>
                    </div>
                    <Button size="sm" variant="ghost" onClick={todo.action}>
                      {todo.actionLabel}
                    </Button>
                  </div>
                ))
              ) : (
                <p className="py-4 text-center text-[13px] text-muted/50">Keine TODOs offen</p>
              )}
            </div>
          </Card>

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
            <div className="mt-3 grid gap-2">
              {data.jobs.slice(0, 3).length ? (
                data.jobs.slice(0, 3).map((job) => (
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
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}


