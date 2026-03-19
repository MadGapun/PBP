import { Ban, BriefcaseBusiness, Check, EyeOff, ExternalLink, Filter, Pencil, Pin, PinOff, Plus, RotateCcw, Search, SlidersHorizontal, Target, X } from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, optionalApi, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  LinkButton,
  LoadingPanel,
  MetricCard,
  Modal,
  PageHeader,
  SectionHeading,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/ui";
import { cn, formatCurrency, formatDateTime, textExcerpt } from "@/utils";

const EMPTY_APPLICATION = {
  job_hash: "",
  title: "",
  company: "",
  url: "",
  status: "beworben",
  notes: "",
};

const EMPTY_BLACKLIST_DIALOG = {
  open: false,
  job: null,
  type: "firma",
  value: "",
};
const JOB_HIGHLIGHT_DURATION_MS = 1800;

function blacklistValueForType(job, type) {
  if (!job) return "";
  if (type === "firma") return String(job.company || "").trim();
  if (type === "ort") return String(job.location || "").trim();
  return String(job.title || "").trim();
}

function jobCardElementId(jobHash) {
  return `job-card-${encodeURIComponent(String(jobHash || ""))}`;
}

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

  // Prefer real data; fall back to estimated
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

export default function JobsPage() {
  const { chrome, intent, clearIntent, reloadKey, refreshChrome, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState([]);
  const [dismissedJobs, setDismissedJobs] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [filters, setFilters] = useState({ query: "", source: "", minScore: "0", remote: "", salaryOnly: false, sort: "score_desc", view: "active", employmentType: "", hideApplied: true });
  const [appliedJobHashes, setAppliedJobHashes] = useState(new Set());
  const [fitDialog, setFitDialog] = useState({ open: false, title: "", analysis: null });
  const [detailDialog, setDetailDialog] = useState({ open: false, job: null, editing: false });
  const [editForm, setEditForm] = useState({});
  const [applicationDialog, setApplicationDialog] = useState({ open: false, draft: EMPTY_APPLICATION });
  const [blacklistDialog, setBlacklistDialog] = useState(EMPTY_BLACKLIST_DIALOG);
  const [searchJob, setSearchJob] = useState({ running: false, progress: 0, message: "" });
  const [pendingFocusJobHash, setPendingFocusJobHash] = useState("");
  const [highlightedJobHash, setHighlightedJobHash] = useState("");
  const [editingScoreHash, setEditingScoreHash] = useState("");
  const [editingScoreValue, setEditingScoreValue] = useState("");

  const wasSearchRunningRef = useRef(false);
  const searchPollErrorShownRef = useRef(false);

  const deferredQuery = useDeferredValue(filters.query);

  const loadPage = useEffectEvent(async (options = {}) => {
    const silent = Boolean(options?.silent);
    try {
      const [activeJobs, hiddenJobs, followUpsResponse, appsResponse] = await Promise.all([
        api("/api/jobs?active=true"),
        api("/api/jobs?active=false"),
        api("/api/follow-ups"),
        api("/api/applications"),
      ]);
      startTransition(() => {
        setJobs(activeJobs || []);
        setDismissedJobs(hiddenJobs || []);
        setFollowUps(followUpsResponse?.follow_ups || []);
        const appHashes = new Set((appsResponse?.applications || []).filter(a => a.job_hash && !["abgelehnt","zurueckgezogen","abgelaufen"].includes(a.status)).map(a => a.job_hash));
        setAppliedJobHashes(appHashes);
        setLoading(false);
      });
    } catch (error) {
      if (!silent) {
        pushToast(`Stellen konnten nicht geladen werden: ${error.message}`, "danger");
      }
      startTransition(() => setLoading(false));
    }
  });

  const syncRunningSearch = useEffectEvent(async () => {
    try {
      const status = await optionalApi("/api/jobsuche/running");
      if (!status) {
        searchPollErrorShownRef.current = false;
        wasSearchRunningRef.current = false;
        startTransition(() => setSearchJob({ running: false, progress: 0, message: "" }));
        await loadPage({ silent: true });
        return;
      }
      const running = Boolean(status?.running);
      const progress = Math.max(0, Math.min(100, Number(status?.progress || 0)));
      const message = String(status?.message || "");

      searchPollErrorShownRef.current = false;
      startTransition(() => setSearchJob({ running, progress, message }));

      if (running) {
        wasSearchRunningRef.current = true;
        await loadPage({ silent: true });
        return;
      }

      if (wasSearchRunningRef.current) {
        wasSearchRunningRef.current = false;
        await loadPage({ silent: true });
        await refreshChrome({ quiet: true });
      }
    } catch (error) {
      if (!searchPollErrorShownRef.current) {
        searchPollErrorShownRef.current = true;
        pushToast(`Live-Aktualisierung fehlgeschlagen: ${error.message}`, "danger");
      }
    }
  });

  useEffect(() => {
    setLoading(true);
    loadPage();
  }, [reloadKey]);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      if (cancelled) return;
      await syncRunningSearch();
      if (cancelled) return;
      const delay = wasSearchRunningRef.current ? 2000 : 5000;
      timer = window.setTimeout(tick, delay);
    };

    tick();

    return () => {
      cancelled = true;
      wasSearchRunningRef.current = false;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [reloadKey, syncRunningSearch]);

  useEffect(() => {
    if (intent?.page !== "stellen") return;
    if (intent.focus === "job" && intent.jobHash) {
      setFilters((current) => ({
        ...current,
        view: "active",
        query: "",
        source: "",
        minScore: "0",
        remote: "",
        salaryOnly: false,
      }));
      setPendingFocusJobHash(String(intent.jobHash));
    }
    clearIntent();
  }, [intent]);

  useEffect(() => {
    if (loading || !pendingFocusJobHash) return undefined;
    const element = document.getElementById(jobCardElementId(pendingFocusJobHash));
    if (!element) return undefined;

    element.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightedJobHash(pendingFocusJobHash);
    setPendingFocusJobHash("");

    const timer = window.setTimeout(() => {
      setHighlightedJobHash((current) => (current === pendingFocusJobHash ? "" : current));
    }, JOB_HIGHLIGHT_DURATION_MS);

    return () => window.clearTimeout(timer);
  }, [
    loading,
    pendingFocusJobHash,
    jobs,
    dismissedJobs,
    filters.view,
    filters.query,
    filters.source,
    filters.minScore,
    filters.remote,
    filters.salaryOnly,
    filters.sort,
  ]);

  async function showFitAnalysis(job) {
    try {
      const analysis = await api(`/api/jobs/${job.hash}/fit-analyse`);
      setFitDialog({ open: true, title: job.title, analysis });
    } catch (error) {
      pushToast(`Fit-Analyse fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function changeJobState(path, payload, successText) {
    try {
      await postJson(path, payload);
      const hash = payload.hash;
      if (path.includes("/dismiss")) {
        startTransition(() => {
          setJobs((cur) => cur.filter((j) => String(j.hash) !== String(hash)));
          const dismissed = jobs.find((j) => String(j.hash) === String(hash));
          if (dismissed) setDismissedJobs((cur) => [{ ...dismissed, status: "aussortiert" }, ...cur]);
        });
      } else if (path.includes("/restore")) {
        startTransition(() => {
          setDismissedJobs((cur) => cur.filter((j) => String(j.hash) !== String(hash)));
          const restored = dismissedJobs.find((j) => String(j.hash) === String(hash));
          if (restored) setJobs((cur) => [{ ...restored, status: "aktiv" }, ...cur]);
        });
      }
      refreshChrome({ quiet: true });
      pushToast(successText, "success");
    } catch (error) {
      pushToast(`${successText} fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function saveApplication() {
    try {
      await postJson("/api/applications", applicationDialog.draft);
      setApplicationDialog({ open: false, draft: EMPTY_APPLICATION });
      await refreshChrome();
      pushToast("Bewerbung angelegt.", "success");
      navigateTo("bewerbungen");
    } catch (error) {
      pushToast(`Bewerbung konnte nicht angelegt werden: ${error.message}`, "danger");
    }
  }

  function openBlacklistDialog(job) {
    const preferredType = job?.company ? "firma" : job?.location ? "ort" : "keyword";
    setBlacklistDialog({
      open: true,
      job,
      type: preferredType,
      value: blacklistValueForType(job, preferredType),
    });
  }

  async function saveBlacklistEntry() {
    const value = (blacklistDialog.value || "").trim();
    if (!value) {
      pushToast("Bitte einen Wert für die Blacklist eingeben.", "danger");
      return;
    }
    try {
      await postJson("/api/blacklist", {
        type: blacklistDialog.type,
        value,
      });
      const jobHash = blacklistDialog.job?.hash;
      if (jobHash) {
        startTransition(() => {
          setJobs((cur) => cur.filter((j) => String(j.hash) !== String(jobHash)));
        });
      }
      refreshChrome({ quiet: true });
      pushToast(`Blacklist-Eintrag gespeichert: ${value}`, "success");
      setBlacklistDialog(EMPTY_BLACKLIST_DIALOG);
    } catch (error) {
      pushToast(`Blacklist-Eintrag fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function togglePin(job) {
    try {
      const result = await putJson(`/api/jobs/${job.hash}/pin`, {});
      const newPinned = result.is_pinned;
      startTransition(() => {
        setJobs((cur) => cur.map((j) => String(j.hash) === String(job.hash) ? { ...j, is_pinned: newPinned ? 1 : 0 } : j));
      });
      refreshChrome({ quiet: true });
      pushToast(newPinned ? "Stelle angepinnt." : "Pin entfernt.", "success");
    } catch (error) {
      pushToast(`Pin-Aktion fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function saveScore(job) {
    const score = Math.max(0, Math.min(100, Math.round(Number(editingScoreValue) || 0)));
    try {
      await putJson(`/api/jobs/${job.hash}/score`, { score });
      setEditingScoreHash("");
      setEditingScoreValue("");
      startTransition(() => {
        setJobs((cur) => cur.map((j) => String(j.hash) === String(job.hash) ? { ...j, score } : j));
      });
      refreshChrome({ quiet: true });
      pushToast(`Score auf ${score} gesetzt.`, "success");
    } catch (error) {
      pushToast(`Score konnte nicht gespeichert werden: ${error.message}`, "danger");
    }
  }

  if (loading) return <LoadingPanel label="Stellen werden geladen..." />;

  const allJobs = [...jobs, ...dismissedJobs];
  const sourceOptions = [...new Set(allJobs.map((job) => job.source).filter(Boolean))];
  const remoteOptions = [...new Set(allJobs.map((job) => job.remote_level).filter((r) => r && r !== "unbekannt"))];
  const employmentTypeOptions = [...new Set(allJobs.map((job) => job.employment_type).filter(Boolean))];
  const currentList = filters.view === "active" ? jobs : dismissedJobs;
  const scoredActiveJobs = jobs.filter((job) => Number(job?.score || 0) > 0);
  const salaryMetrics = buildAnnualSalaryMetrics(jobs);
  const jobsWithSalary = Number(salaryMetrics.jobsWithSalary || 0);
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
  const latestJobUpdate = (currentList.length ? currentList : allJobs).reduce(
    (latest, job) => {
      const raw = job.updated_at || job.found_at || "";
      const timestamp = Date.parse(raw);
      if (Number.isNaN(timestamp)) return latest;
      if (timestamp > latest.timestamp) return { raw, timestamp };
      return latest;
    },
    { raw: "", timestamp: -Infinity }
  ).raw;
  const averageScore = scoredActiveJobs.length
    ? Math.round(scoredActiveJobs.reduce((sum, job) => sum + Number(job.score || 0), 0) / scoredActiveJobs.length)
    : 0;
  const filteredJobs = currentList
    .filter((job) => {
      const haystack = `${job.title || ""} ${job.company || ""} ${job.description || ""}`.toLowerCase();
      const queryMatch = !deferredQuery || haystack.includes(deferredQuery.toLowerCase());
      const sourceMatch = !filters.source || job.source === filters.source;
      const scoreMatch = Number(job.score || 0) >= Number(filters.minScore || 0);
      const remoteMatch = !filters.remote || job.remote_level === filters.remote;
      const salaryMatch = !filters.salaryOnly || (job.salary_min && job.salary_min > 0);
      const typeMatch = !filters.employmentType || job.employment_type === filters.employmentType;
      const appliedMatch = !filters.hideApplied || !appliedJobHashes.has(job.hash);
      return queryMatch && sourceMatch && scoreMatch && remoteMatch && salaryMatch && typeMatch && appliedMatch;
    })
    .sort((a, b) => {
      // Pinned jobs always come first
      const pinA = a.is_pinned ? 1 : 0;
      const pinB = b.is_pinned ? 1 : 0;
      if (pinA !== pinB) return pinB - pinA;

      switch (filters.sort) {
        case "score_desc": return (b.score || 0) - (a.score || 0);
        case "score_asc": return (a.score || 0) - (b.score || 0);
        case "salary_desc": return (b.salary_max || b.salary_min || 0) - (a.salary_max || a.salary_min || 0);
        case "company": return (a.company || "").localeCompare(b.company || "");
        case "title": return (a.title || "").localeCompare(b.title || "");
        default: return 0;
      }
    });

  return (
    <div id="page-stellen" className="page active">
      <div className="mb-6 flex items-baseline gap-2">
        <h1 className="font-display text-xl font-semibold text-ink">Stellen</h1>
        <span className="text-[11px] text-muted/40">
          {searchJob.running
    ? `Jobsuche läuft${searchJob.progress > 0 ? ` (${Math.round(searchJob.progress)}%)` : ""}`
            : chrome.searchStatus?.last_search
            ? `Aktualisiert ${chrome.searchStatus.days_ago === 0 ? "heute" : chrome.searchStatus.days_ago === 1 ? "gestern" : `vor ${chrome.searchStatus.days_ago} Tagen`}`
            : "Noch nie gesucht"}
        </span>
      </div>

      <div className="grid gap-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Aktive Stellen" value={jobs.length} note={jobsWithSalary > 0 ? `${jobsWithSalary} mit Gehalt${salaryEstimated ? " (geschätzt)" : ""}` : "Keine Gehaltsdaten"} tone="success" />
          <MetricCard
            label={`Gehaltsdurchschnitt${salaryEstimated ? " (geschätzt)" : ""}`}
            value={salaryAverage !== null ? formatCurrency(salaryAverage) : "Keine Angabe"}
            note={salaryCount > 0 ? `Auf Basis von ${salaryCount} Stellen mit Jahresgehalt` : "Noch keine Gehaltsdaten"}
            tone="success"
          />
          <MetricCard label={`Gehaltsbandbreite${salaryEstimated ? " (geschätzt)" : ""}`} value={salaryBandText} note="Durchschnittliche Min/Max-Spanne" tone="success" />
          <MetricCard
            label="Durchschnittsscore"
            value={averageScore}
            note={scoredActiveJobs.length > 0 ? `${scoredActiveJobs.length} bewertete Treffer` : "Noch keine bewerteten Treffer"}
            tone="sky"
          />
        </div>

        <Card className="rounded-2xl">
          {/* Row 1: Search bar + counter */}
          <div className="flex items-center gap-3">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted/50" size={16} />
              <TextInput
                className="w-full !rounded-xl !pl-11 !pr-10"
                value={filters.query}
                onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))}
                placeholder="Titel, Firma oder Schlagwort suchen..."
              />
              {filters.query && (
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted/50 hover:text-ink"
                  onClick={() => setFilters((current) => ({ ...current, query: "" }))}
                >
                  <X size={16} />
                </button>
              )}
            </div>
            <span className="shrink-0 text-[12px] tabular-nums text-muted/50">
              {filteredJobs.length} / {currentList.length}
            </span>
          </div>

          {/* Row 2: Filter chips row */}
          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            {/* View toggle */}
            <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-white/5 bg-white/[0.03]">
              {[
                ["active", "Aktive"],
                ["dismissed", "Ausgeblendet"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={cn(
                    "px-4 py-2 text-center text-[13px] font-medium outline-none transition-colors",
                    filters.view === value
                      ? "bg-white/[0.08] text-ink"
                      : "text-muted/40 hover:bg-white/[0.03] hover:text-muted/60"
                  )}
                  onClick={() => setFilters((current) => ({ ...current, view: value }))}
                >
                  {label}
                </button>
              ))}
            </div>

            <span className="mx-0.5 h-5 w-px bg-white/5" />

            {/* Inline filter selects */}
            <div className="group inline-flex items-center gap-1.5">
              <SelectInput
                className={cn(
                  "!h-9 !min-h-0 !w-auto !rounded-xl !pl-3 !pr-3 !py-0 !text-[13px]",
                  filters.source
                    ? "!border-teal/20 !bg-teal/8 !text-teal/80"
                    : "!border-white/5 !bg-white/[0.03] !text-muted/60"
                )}
                value={filters.source}
                onChange={(event) => setFilters((current) => ({ ...current, source: event.target.value }))}
              >
                <option value="">Alle Quellen</option>
                {sourceOptions.map((source) => (
                  <option key={source} value={source}>{source}</option>
                ))}
              </SelectInput>
              {filters.source && (
                <button type="button" onClick={() => setFilters(f => ({ ...f, source: "" }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
              )}
            </div>

            <div className="group inline-flex items-center gap-1.5">
              <SelectInput
                className={cn(
                  "!h-9 !min-h-0 !w-auto !rounded-xl !pl-3 !pr-3 !py-0 !text-[13px]",
                  filters.remote
                    ? "!border-teal/20 !bg-teal/8 !text-teal/80"
                    : "!border-white/5 !bg-white/[0.03] !text-muted/60"
                )}
                value={filters.remote}
                onChange={(event) => setFilters((current) => ({ ...current, remote: event.target.value }))}
              >
                <option value="">Remote: Alle</option>
                {remoteOptions.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </SelectInput>
              {filters.remote && (
                <button type="button" onClick={() => setFilters(f => ({ ...f, remote: "" }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
              )}
            </div>

            <div className="group inline-flex items-center gap-1.5">
              <div className={cn(
                "flex items-center gap-1.5 rounded-xl border px-3 py-1.5 transition-colors",
                Number(filters.minScore || 0) > 0
                  ? "border-teal/20 bg-teal/8"
                  : "border-white/5 bg-white/[0.03]"
              )}>
                <span className={cn("text-[13px]", Number(filters.minScore || 0) > 0 ? "text-teal/80" : "text-muted/40")}>Score ≥</span>
                <input
                  type="number"
                  className={cn(
                    "w-10 rounded-md border bg-white/[0.04] text-center text-[13px] font-medium outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
                    Number(filters.minScore || 0) > 0
                      ? "border-teal/30 text-teal/80 focus:border-teal/50"
                      : "border-white/10 text-muted/70 focus:border-teal/40"
                  )}
                  value={filters.minScore}
                  onChange={(event) => setFilters((current) => ({ ...current, minScore: event.target.value }))}
                />
              </div>
              {Number(filters.minScore || 0) > 0 && (
                <button type="button" onClick={() => setFilters(f => ({ ...f, minScore: "0" }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
              )}
            </div>

            <div className="group inline-flex items-center gap-1.5">
              <button
                type="button"
                className={cn(
                  "flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[13px] font-medium transition-colors",
                  filters.salaryOnly
                    ? "border-teal/20 bg-teal/8 text-teal/80"
                    : "border-white/5 bg-white/[0.03] text-muted/40 hover:bg-white/[0.05] hover:text-muted/60"
                )}
                onClick={() => setFilters((current) => ({ ...current, salaryOnly: !current.salaryOnly }))}
              >
                Nur mit Gehalt
              </button>
              {filters.salaryOnly && (
                <button type="button" onClick={() => setFilters(f => ({ ...f, salaryOnly: false }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
              )}
            </div>

            {/* Employment Type Filter (#83) */}
            {employmentTypeOptions.length > 1 && (
              <SelectInput
                className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
                value={filters.employmentType}
                onChange={(e) => setFilters((f) => ({ ...f, employmentType: e.target.value }))}
              >
                <option value="">Alle Stellenarten</option>
                {employmentTypeOptions.map((t) => (
                  <option key={t} value={t}>{t === "festanstellung" ? "Festanstellung" : t === "freelance" ? "Freelance" : t === "praktikum" ? "Praktikum" : t === "werkstudent" ? "Werkstudent" : t}</option>
                ))}
              </SelectInput>
            )}

            {/* Hide Applied Toggle (#83) */}
            <button
              type="button"
              className={cn(
                "flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[13px] font-medium transition-colors",
                filters.hideApplied
                  ? "border-sky/20 bg-sky/8 text-sky/80"
                  : "border-white/5 bg-white/[0.03] text-muted/40 hover:bg-white/[0.05] hover:text-muted/60"
              )}
              onClick={() => setFilters((f) => ({ ...f, hideApplied: !f.hideApplied }))}
            >
              <EyeOff size={14} />
              Beworbene ausblenden
            </button>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Sort */}
            <SelectInput
              className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
              value={filters.sort}
              onChange={(event) => setFilters((current) => ({ ...current, sort: event.target.value }))}
            >
              <option value="score_desc">Score abst.</option>
              <option value="score_asc">Score aufst.</option>
              <option value="salary_desc">Gehalt abst.</option>
              <option value="company">Firma A–Z</option>
              <option value="title">Titel A–Z</option>
            </SelectInput>
          </div>
        </Card>

        <div className="grid gap-4">
          <div className="flex justify-end">
            <p className="text-[12px] text-muted/45">
              Zuletzt aktualisiert: {latestJobUpdate ? formatDateTime(latestJobUpdate) : "Keine Angabe"}
            </p>
          </div>
          {filteredJobs.length ? (
            filteredJobs.map((job) => (
              <Card
                key={job.hash}
                id={jobCardElementId(job.hash)}
                className={cn(
                  "flex flex-col rounded-xl transition-[border-color,box-shadow,background-color] duration-300",
                  highlightedJobHash === String(job.hash) && "job-card-highlight",
                  job.is_pinned && "border-amber/20 bg-amber/[0.02]"
                )}
              >
                <div className="flex-1 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {job.is_pinned ? <Badge tone="amber"><Pin size={12} className="inline -mt-0.5" /> Angepinnt</Badge> : null}
                    <Badge tone="sky">{job.source || "Quelle"}</Badge>
                    {editingScoreHash === String(job.hash) ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/30 bg-amber/10 px-2.5 py-0.5">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          className="w-12 rounded border border-white/10 bg-white/[0.06] px-1.5 py-0.5 text-center text-[12px] font-medium text-ink outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                          value={editingScoreValue}
                          onChange={(e) => setEditingScoreValue(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") saveScore(job); if (e.key === "Escape") setEditingScoreHash(""); }}
                          autoFocus
                        />
                        <button type="button" className="text-teal hover:text-teal/80" onClick={() => saveScore(job)}><Check size={14} /></button>
                        <button type="button" className="text-muted hover:text-ink" onClick={() => setEditingScoreHash("")}><X size={14} /></button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-transparent bg-amber/10 px-2.5 py-0.5 text-[12px] font-semibold text-amber transition-colors hover:border-amber/30 hover:bg-amber/20"
                        onClick={() => { setEditingScoreHash(String(job.hash)); setEditingScoreValue(String(job.score || 0)); }}
                        title="Score bearbeiten"
                      >
                        Score {job.score || 0}
                        <Pencil size={11} />
                      </button>
                    )}
                    {job.remote_level && job.remote_level !== "unbekannt" ? <Badge tone="success">{job.remote_level}</Badge> : null}
                    {job.employment_type && job.employment_type !== "festanstellung" ? (
                      <Badge tone={job.employment_type === "freelance" ? "success" : job.employment_type === "praktikum" ? "amber" : "neutral"}>
                        {job.employment_type === "freelance" ? "Freelance" : job.employment_type === "praktikum" ? "Praktikum" : job.employment_type === "werkstudent" ? "Werkstudent" : job.employment_type}
                      </Badge>
                    ) : null}
                  </div>
                  <h2
                    className="text-2xl font-semibold text-ink cursor-pointer hover:text-sky transition-colors"
                    onClick={() => setDetailDialog({ open: true, job, editing: false })}
                    title="Details anzeigen"
                  >{job.title}</h2>
                  <p className="text-sm text-muted">{job.company || "Unbekannte Firma"}{job.location ? ` - ${job.location}` : ""}</p>
                  <p className="text-sm text-muted">{textExcerpt(job.description, 220)}</p>
                  {job.salary_min ? (
                    <p className="text-sm text-ink">
                      Gehalt: {formatCurrency(job.salary_min)}{job.salary_max ? ` bis ${formatCurrency(job.salary_max)}` : ""}{job.salary_estimated ? " (geschätzt)" : ""}
                    </p>
                  ) : null}
                </div>
                <div className="mt-4 flex flex-wrap gap-3 border-t border-white/[0.06] pt-4">
                  <Button variant={job.is_pinned ? "subtle" : "secondary"} onClick={() => togglePin(job)}>
                    {job.is_pinned ? <PinOff size={15} /> : <Pin size={15} />}
                    {job.is_pinned ? "Entpinnen" : "Anpinnen"}
                  </Button>
                  <Button variant="secondary" onClick={() => showFitAnalysis(job)}>
                    <Target size={15} />
                    Fit-Analyse
                  </Button>
                  <Button
                    onClick={() =>
                      setApplicationDialog({
                        open: true,
                        draft: {
                          job_hash: job.hash,
                          title: job.title || "",
                          company: job.company || "",
                          url: job.url || "",
                          status: "beworben",
                          notes: "",
                        },
                      })
                    }
                  >
                    <Plus size={15} />
                    Bewerbung erfassen
                  </Button>
                  <Button variant="ghost" onClick={() => openBlacklistDialog(job)}>
                    <Ban size={15} />
                    Zur Blacklist
                  </Button>
                  {filters.view === "active" ? (
                    <Button variant="danger" onClick={() => changeJobState("/api/jobs/dismiss", { hash: job.hash, reason: "passt_nicht" }, "Stelle aussortiert")}>
                      <EyeOff size={15} />
                      Passt nicht
                    </Button>
                  ) : (
                    <Button variant="ghost" onClick={() => changeJobState("/api/jobs/restore", { hash: job.hash }, "Stelle wiederhergestellt")}>
                      <RotateCcw size={15} />
                      Wiederherstellen
                    </Button>
                  )}
                  {job.url ? (
                    <LinkButton href={job.url} target="_blank" rel="noreferrer">
                      <ExternalLink size={15} />
                      Anzeige
                    </LinkButton>
                  ) : null}
                </div>
              </Card>
            ))
          ) : (
            <EmptyState
              title={filters.view === "active" ? "Keine aktiven Stellen" : "Keine ausgeblendeten Stellen"}
              description={filters.view === "active" ? "Sobald Jobs im System sind, erscheinen sie hier mit Fit-Analyse und Aktionsbuttons." : "Ausgeblendete Jobs können hier später wieder aktiviert werden."}
          action={filters.view === "active" ? <Button onClick={() => navigateTo("einstellungen")}>Suchprofil öffnen</Button> : null}
            />
          )}
        </div>
      </div>

      <Modal
        open={fitDialog.open}
        title={`Fit-Analyse - ${fitDialog.title}`}
        onClose={() => setFitDialog({ open: false, title: "", analysis: null })}
        footer={<div className="flex justify-end"><Button onClick={() => setFitDialog({ open: false, title: "", analysis: null })}>Schließen</Button></div>}
      >
        <div className="grid gap-4">
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">Gesamtscore</p>
            <p className="mt-3 text-4xl font-semibold text-ink">{fitDialog.analysis?.total_score ?? 0}</p>
          </Card>
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-sm font-semibold text-ink">MUSS-Treffer</p>
            <p className="mt-2 text-sm text-muted">{(fitDialog.analysis?.muss_hits || []).join(", ") || "Keine"}</p>
          </Card>
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-sm font-semibold text-ink">Fehlende MUSS-Kriterien</p>
            <p className="mt-2 text-sm text-muted">{(fitDialog.analysis?.missing_muss || []).join(", ") || "Keine"}</p>
          </Card>
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-sm font-semibold text-ink">Risiken</p>
            <div className="mt-2 grid gap-2 text-sm text-muted">
              {(fitDialog.analysis?.risks || []).length ? fitDialog.analysis.risks.map((risk) => <p key={risk}>{risk}</p>) : <p>Keine besonderen Risiken.</p>}
            </div>
          </Card>
        </div>
      </Modal>

      <Modal
        open={applicationDialog.open}
        title="Bewerbung aus Stelle anlegen"
        onClose={() => setApplicationDialog({ open: false, draft: EMPTY_APPLICATION })}
        footer={<div className="flex justify-end gap-3"><Button variant="ghost" onClick={() => setApplicationDialog({ open: false, draft: EMPTY_APPLICATION })}>Abbrechen</Button><Button onClick={saveApplication}>Bewerbung speichern</Button></div>}
      >
        <div className="grid gap-4">
          {["title", "company", "url"].map((key) => (
            <Field key={key} label={key}>
              <TextInput value={applicationDialog.draft[key] || ""} onChange={(event) => setApplicationDialog((current) => ({ ...current, draft: { ...current.draft, [key]: event.target.value } }))} />
            </Field>
          ))}
          <Field label="Status">
            <SelectInput value={applicationDialog.draft.status} onChange={(event) => setApplicationDialog((current) => ({ ...current, draft: { ...current.draft, status: event.target.value } }))}>
              <option value="beworben">Beworben</option>
              <option value="entwurf">Entwurf</option>
            </SelectInput>
          </Field>
          <Field label="Notizen">
            <TextArea rows={4} value={applicationDialog.draft.notes} onChange={(event) => setApplicationDialog((current) => ({ ...current, draft: { ...current.draft, notes: event.target.value } }))} />
          </Field>
        </div>
      </Modal>

      <Modal
        open={blacklistDialog.open}
        title="Zur Blacklist hinzufügen"
        onClose={() => setBlacklistDialog(EMPTY_BLACKLIST_DIALOG)}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setBlacklistDialog(EMPTY_BLACKLIST_DIALOG)}>
              Abbrechen
            </Button>
            <Button onClick={saveBlacklistEntry}>
              <Ban size={15} />
              Blockieren
            </Button>
          </div>
        }
      >
        <div className="grid gap-4">
          <Field label="Typ">
            <SelectInput
              value={blacklistDialog.type}
              onChange={(event) =>
                setBlacklistDialog((current) => ({
                  ...current,
                  type: event.target.value,
                  value: blacklistValueForType(current.job, event.target.value),
                }))
              }
            >
              <option value="keyword">Keyword</option>
              <option value="firma">Firma</option>
              <option value="ort">Ort</option>
            </SelectInput>
          </Field>
          <Field label="Wert, der blockiert wird">
            <TextInput
              value={blacklistDialog.value}
              onChange={(event) =>
                setBlacklistDialog((current) => ({ ...current, value: event.target.value }))
              }
            />
          </Field>
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">Vorschau</p>
            <p className="mt-2 text-sm text-ink">
              Blockiert wird:
              {" "}
              <span className="font-semibold">
                {blacklistDialog.value?.trim() || "(kein Wert)"}
              </span>
            </p>
          </Card>
        </div>
      </Modal>

      {/* Job Detail Modal (#90) */}
      {detailDialog.open && detailDialog.job && (
        <Modal onClose={() => setDetailDialog({ open: false, job: null, editing: false })}>
          {detailDialog.editing ? (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-ink">Stelle bearbeiten</h2>
              <Field label="Titel">
                <TextInput value={editForm.title || ""} onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))} />
              </Field>
              <Field label="Firma">
                <TextInput value={editForm.company || ""} onChange={(e) => setEditForm((f) => ({ ...f, company: e.target.value }))} />
              </Field>
              <Field label="Standort">
                <TextInput value={editForm.location || ""} onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))} />
              </Field>
              <Field label="Beschreibung">
                <TextArea value={editForm.description || ""} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} className="!min-h-40" />
              </Field>
              <div className="flex gap-2">
                <Button variant="primary" onClick={async () => {
                  await putJson(`/api/jobs/${detailDialog.job.hash}`, editForm);
                  pushToast("Stelle aktualisiert", "success");
                  setDetailDialog({ open: false, job: null, editing: false });
                  loadPage({ silent: true });
                }}>Speichern</Button>
                <Button variant="ghost" onClick={() => setDetailDialog((d) => ({ ...d, editing: false }))}>Abbrechen</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-ink">{detailDialog.job.title}</h2>
                  <p className="text-sm text-muted">{detailDialog.job.company || "Unbekannt"}{detailDialog.job.location ? ` — ${detailDialog.job.location}` : ""}</p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => {
                  setEditForm({
                    title: detailDialog.job.title || "",
                    company: detailDialog.job.company || "",
                    location: detailDialog.job.location || "",
                    description: detailDialog.job.description || "",
                  });
                  setDetailDialog((d) => ({ ...d, editing: true }));
                }}>
                  <Pencil size={14} /> Bearbeiten
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="sky">{detailDialog.job.source || "Quelle"}</Badge>
                {detailDialog.job.employment_type ? <Badge tone={detailDialog.job.employment_type === "freelance" ? "success" : "neutral"}>{detailDialog.job.employment_type}</Badge> : null}
                {detailDialog.job.remote_level && detailDialog.job.remote_level !== "unbekannt" ? <Badge tone="success">{detailDialog.job.remote_level}</Badge> : null}
                <Badge tone="amber">Score {detailDialog.job.score || 0}</Badge>
                {detailDialog.job.is_pinned ? <Badge tone="amber"><Pin size={12} className="inline" /> Angepinnt</Badge> : null}
              </div>
              {detailDialog.job.salary_min ? (
                <p className="text-sm text-teal font-medium">
                  Gehalt: {formatCurrency(detailDialog.job.salary_min)} - {formatCurrency(detailDialog.job.salary_max)}
                  {detailDialog.job.salary_type ? ` (${detailDialog.job.salary_type})` : ""}
                  {detailDialog.job.salary_estimated ? " (geschaetzt)" : ""}
                </p>
              ) : null}
              {detailDialog.job.url ? (
                <a href={detailDialog.job.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm text-sky hover:underline">
                  <ExternalLink size={14} /> Stellenanzeige oeffnen
                </a>
              ) : null}
              {detailDialog.job.description ? (
                <div className="glass-card p-4 rounded-xl">
                  <h3 className="text-sm font-semibold text-ink mb-2">Stellenbeschreibung</h3>
                  <p className="text-sm text-muted/70 whitespace-pre-wrap">{detailDialog.job.description}</p>
                </div>
              ) : null}
              {detailDialog.job.found_at ? (
                <p className="text-xs text-muted/40">Gefunden: {formatDateTime(detailDialog.job.found_at)}</p>
              ) : null}
              <div className="flex flex-wrap gap-2 border-t border-white/[0.06] pt-4 mt-4">
                <Button onClick={() => {
                  setDetailDialog({ open: false, job: null, editing: false });
                  setApplicationDialog({
                    open: true,
                    draft: {
                      job_hash: detailDialog.job.hash,
                      title: detailDialog.job.title || "",
                      company: detailDialog.job.company || "",
                      url: detailDialog.job.url || "",
                      status: "beworben",
                      notes: "",
                    },
                  });
                }}>
                  <Plus size={15} /> Bewerbung erfassen
                </Button>
                <Button variant="secondary" onClick={() => {
                  setDetailDialog({ open: false, job: null, editing: false });
                  showFitAnalysis(detailDialog.job);
                }}>
                  <Target size={15} /> Fit-Analyse
                </Button>
                <Button variant={detailDialog.job.is_pinned ? "subtle" : "secondary"} onClick={async () => {
                  await togglePin(detailDialog.job);
                  setDetailDialog((d) => ({ ...d, job: { ...d.job, is_pinned: d.job.is_pinned ? 0 : 1 } }));
                }}>
                  {detailDialog.job.is_pinned ? <PinOff size={15} /> : <Pin size={15} />}
                  {detailDialog.job.is_pinned ? "Entpinnen" : "Anpinnen"}
                </Button>
                <Button variant="ghost" onClick={() => {
                  setDetailDialog({ open: false, job: null, editing: false });
                  openBlacklistDialog(detailDialog.job);
                }}>
                  <Ban size={15} /> Blacklist
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

