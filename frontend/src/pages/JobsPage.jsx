import { Ban, BriefcaseBusiness, Check, ClipboardCopy, EyeOff, ExternalLink, Filter, Pencil, Pin, PinOff, Plus, RotateCcw, Search, SlidersHorizontal, Target, X } from "lucide-react";
import { startTransition, useCallback, useDeferredValue, useEffect, useEffectEvent, useRef, useState } from "react";

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
const EMPTY_DISMISS_DIALOG = {
  open: false,
  job: null,
  selectedReasons: [],
  customReason: "",
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

function jobNeedsDescriptionAttention(job) {
  return Number(job?.score || 0) > 0 && String(job?.description || "").trim().length < 50;
}

export default function JobsPage() {
  const { chrome, intent, clearIntent, reloadKey, refreshChrome, pushToast, copyPrompt, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState([]);
  const [dismissedJobs, setDismissedJobs] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [filters, setFilters] = useState({
    query: "",
    source: "",
    minScore: "0",
    remote: "",
    salaryOnly: false,
    sort: "score_desc",
    view: "active",
    employmentType: "",
    hideApplied: true,
    missingDescriptionOnly: false,
  });
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
  const [dismissDialog, setDismissDialog] = useState(EMPTY_DISMISS_DIALOG);
  const [dismissReasons, setDismissReasons] = useState([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsHasMore, setJobsHasMore] = useState(false);
  const [jobsPageSize, setJobsPageSize] = useState(() => {
    const saved = localStorage.getItem("pbp_jobs_page_size");
    return saved ? Number(saved) : 20;
  });
  const [loadingMore, setLoadingMore] = useState(false);

  const wasSearchRunningRef = useRef(false);
  const searchPollErrorShownRef = useRef(false);

  const deferredQuery = useDeferredValue(filters.query);

  const openDetailDialog = useCallback((job) => {
    setDetailDialog({ open: true, job, editing: false });
  }, []);

  const loadPage = useEffectEvent(async (options = {}) => {
    const silent = Boolean(options?.silent);
    const append = Boolean(options?.append);
    const pageSize = options?.pageSize || jobsPageSize;
    const currentOffset = append ? jobs.length : 0;
    try {
      const jobsUrl = pageSize > 0
        ? `/api/jobs?active=true&exclude_blacklisted=true&limit=${pageSize}&offset=${currentOffset}`
        : "/api/jobs?active=true&exclude_blacklisted=true";
      const [activeJobsResp, hiddenJobs, followUpsResponse, appsResponse, reasons] = await Promise.all([
        api(jobsUrl),
        append ? Promise.resolve(null) : api("/api/jobs?active=false"),
        append ? Promise.resolve(null) : api("/api/follow-ups"),
        append ? Promise.resolve(null) : api("/api/applications"),
        append ? Promise.resolve(null) : optionalApi("/api/dismiss-reasons"),
      ]);
      startTransition(() => {
        // Handle paginated response (object with jobs array) or plain array (no limit)
        const isPaginated = activeJobsResp && !Array.isArray(activeJobsResp) && activeJobsResp.jobs;
        const newJobs = isPaginated ? activeJobsResp.jobs : (activeJobsResp || []);
        if (append) {
          setJobs((prev) => [...prev, ...newJobs]);
        } else {
          setJobs(newJobs);
        }
        if (isPaginated) {
          setJobsTotal(activeJobsResp.total || 0);
          setJobsHasMore(Boolean(activeJobsResp.has_more));
        } else {
          setJobsTotal(newJobs.length);
          setJobsHasMore(false);
        }
        if (!append) {
          if (hiddenJobs) setDismissedJobs(hiddenJobs || []);
          if (followUpsResponse) setFollowUps(followUpsResponse?.follow_ups || []);
          if (appsResponse) {
            const appHashes = new Set((appsResponse?.applications || []).filter(a => a.job_hash && !["abgelehnt","zurueckgezogen","abgelaufen"].includes(a.status)).map(a => a.job_hash));
            setAppliedJobHashes(appHashes);
          }
          if (reasons) setDismissReasons(reasons);
        }
        setLoading(false);
        setLoadingMore(false);
      });
    } catch (error) {
      if (!silent) {
        pushToast(`Stellen konnten nicht geladen werden: ${error.message}`, "danger");
      }
      startTransition(() => { setLoading(false); setLoadingMore(false); });
    }
  });

  const syncRunningSearch = useEffectEvent(async () => {
    try {
      const status = await optionalApi("/api/jobsuche/running");
      if (!status) {
        searchPollErrorShownRef.current = false;
        // #221: Nur bei Status-Wechsel (running→done) neu laden
        if (wasSearchRunningRef.current) {
          wasSearchRunningRef.current = false;
          await loadPage({ silent: true });
          await refreshChrome({ quiet: true });
        }
        startTransition(() => setSearchJob({ running: false, progress: 0, message: "" }));
        return;
      }
      const running = Boolean(status?.running);
      const progress = Math.max(0, Math.min(100, Number(status?.progress || 0)));
      const message = String(status?.message || "");

      searchPollErrorShownRef.current = false;
      startTransition(() => setSearchJob({ running, progress, message }));

      if (running) {
        wasSearchRunningRef.current = true;
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
      const delay = wasSearchRunningRef.current ? 5000 : 30000;
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
        missingDescriptionOnly: false,
      }));
      setPendingFocusJobHash(String(intent.jobHash));
    }
    if (intent.missingDescriptionOnly) {
      setFilters((current) => ({
        ...current,
        view: "active",
        missingDescriptionOnly: true,
      }));
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
    filters.missingDescriptionOnly,
    filters.sort,
  ]);

  async function showFitAnalysis(job) {
    try {
      const analysis = await api(`/api/jobs/${job.hash}/fit-analyse`);
      setFitDialog({ open: true, title: job.title, hash: job.hash, analysis });
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

  function openDismissDialog(job) {
    setDismissDialog({ open: true, job, selectedReasons: [], customReason: "" });
  }

  async function saveDismiss() {
    const reasons = [...dismissDialog.selectedReasons];
    if (dismissDialog.customReason.trim()) {
      reasons.push(dismissDialog.customReason.trim());
    }
    if (!reasons.length) {
      pushToast("Bitte mindestens einen Ablehnungsgrund auswählen.", "danger");
      return;
    }
    const hash = dismissDialog.job?.hash;
    if (!hash) return;
    try {
      await postJson("/api/jobs/dismiss", { hash, reasons });
      startTransition(() => {
        setJobs((cur) => cur.filter((j) => String(j.hash) !== String(hash)));
        const dismissed = jobs.find((j) => String(j.hash) === String(hash));
        if (dismissed) setDismissedJobs((cur) => [{ ...dismissed, status: "aussortiert" }, ...cur]);
      });
      refreshChrome({ quiet: true });
      // Reload dismiss reasons so custom reasons appear immediately (#302)
      try {
        const updated = await optionalApi("/api/dismiss-reasons");
        if (updated) setDismissReasons(updated);
      } catch (_) { /* ignore */ }
      pushToast("Stelle aussortiert.", "success");
      setDismissDialog(EMPTY_DISMISS_DIALOG);
    } catch (error) {
      pushToast(`Stelle konnte nicht aussortiert werden: ${error.message}`, "danger");
    }
  }

  function toggleDismissReason(label) {
    setDismissDialog((cur) => {
      const selected = cur.selectedReasons.includes(label)
        ? cur.selectedReasons.filter((r) => r !== label)
        : [...cur.selectedReasons, label];
      return { ...cur, selectedReasons: selected };
    });
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
  const jobsWithoutDescriptionCount = jobs.filter(jobNeedsDescriptionAttention).length;
  const hiddenAppliedCount = currentList.filter((job) => appliedJobHashes.has(job.hash)).length;
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
      const descriptionMatch = !filters.missingDescriptionOnly || jobNeedsDescriptionAttention(job);
      return queryMatch && sourceMatch && scoreMatch && remoteMatch && salaryMatch && typeMatch && appliedMatch && descriptionMatch;
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
  const visibleDescriptionGaps = filteredJobs.filter(jobNeedsDescriptionAttention).length;
  const searchNeedsRefresh = !chrome.searchStatus?.last_search || Number(chrome.searchStatus?.days_ago || 0) > 0;
  const jobsGuidance = (() => {
    if (searchJob.running) {
      return {
        badge: "Läuft",
        tone: "sky",
        title: "Jobsuche wird gerade aktualisiert",
        description: searchJob.message || "Neue Treffer kommen laufend rein. Prüfe die Liste erst, wenn die Suche durch ist.",
      };
    }
    if (filters.view === "active" && jobsWithoutDescriptionCount > 0) {
      return {
        badge: "Score prüfen",
        tone: "amber",
        title: "Ein Teil der Scores ist noch nicht belastbar",
        description: `${jobsWithoutDescriptionCount} aktive Stelle(n) haben keine oder nur eine sehr kurze Beschreibung. Prüfe diese Treffer vor einer Entscheidung direkt gegen die Originalanzeige.`,
        actionLabel: filters.missingDescriptionOnly ? "Alle Stellen zeigen" : "Nur diese Stellen zeigen",
        action: () => setFilters((current) => ({ ...current, view: "active", missingDescriptionOnly: !current.missingDescriptionOnly })),
      };
    }
    if (filters.view === "active" && filteredJobs.length === 0 && currentList.length > 0 && filters.hideApplied && hiddenAppliedCount === currentList.length) {
      return {
        badge: "Filter",
        tone: "sky",
        title: "Alle sichtbaren Treffer sind nur wegen \"Beworbene ausblenden\" weg",
        description: "Für einen Vollcheck lohnt sich ein kurzer Blick auf bereits bearbeitete Stellen, bevor du unnötig neu suchst.",
        actionLabel: "Beworbene einblenden",
        action: () => setFilters((current) => ({ ...current, hideApplied: false })),
      };
    }
    if (filters.view === "active" && filteredJobs.length === 0 && currentList.length > 0) {
      return {
        badge: "Filter",
        tone: "neutral",
        title: "Die aktuelle Filterkombination ist strenger als nötig",
        description: "Gerade passt kein Treffer mehr durch die Filter. Lockere zuerst die Auswahl, bevor du annimmst, dass nichts Passendes da ist.",
        actionLabel: "Filter zurücksetzen",
        action: () => setFilters((current) => ({
          ...current,
          query: "",
          source: "",
          minScore: "0",
          remote: "",
          salaryOnly: false,
          employmentType: "",
          hideApplied: true,
          missingDescriptionOnly: false,
        })),
      };
    }
    if (filters.view === "active" && filteredJobs.length === 0 && searchNeedsRefresh) {
      return {
        badge: "Suche",
        tone: "danger",
        title: "Erst die Jobsuche erneuern, dann wieder aussortieren",
        description: "Die Suche ist veraltet oder noch nie gelaufen. Neue Treffer bringen jetzt mehr als noch feinere Filter.",
        actionLabel: "Jobsuche starten",
        action: () => copyPrompt("/jobsuche_workflow"),
      };
    }
    if (filters.view === "dismissed" && dismissedJobs.length > 0) {
      return {
        badge: "Review",
        tone: "neutral",
        title: "Ausgeblendete Stellen sind dein späteres Prüfregal",
        description: "Hier solltest du nur bewusst wiederherstellen, nicht wahllos zurückholen. Nutze die Gründe als Lernsignal für bessere Filter.",
      };
    }
    return {
      badge: "Auf Kurs",
      tone: "success",
      title: "Die Stellenliste ist arbeitsfähig",
      description: "Prüfe jetzt die besten Treffer, bevor du neue Suchrunden startest. Erst sichten, dann bewerben, dann nachschärfen.",
    };
  })();

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

      {/* Progress bar during job search (#210) */}
      {searchJob.running && (
        <div className="mb-4 rounded-lg border border-sky-500/20 bg-sky-500/5 p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 font-medium text-sky-300">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-sky-500/30 border-t-sky-400" />
              {searchJob.message || "Jobsuche läuft..."}
            </span>
            <span className="text-xs text-muted/50">{Math.round(searchJob.progress)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-sky-500 transition-all duration-500 ease-out"
              style={{ width: `${Math.max(2, searchJob.progress)}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid gap-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Aktive Stellen" value={jobsTotal || filteredJobs.length} note={filteredJobs.length !== (jobsTotal || filteredJobs.length) ? `${filteredJobs.length} angezeigt (Filter aktiv)` : jobsWithSalary > 0 ? `${jobsWithSalary} mit Gehalt${salaryEstimated ? " (geschätzt)" : ""}` : "Keine Gehaltsdaten"} tone="success" />
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
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={jobsGuidance.tone}>{jobsGuidance.badge}</Badge>
                {visibleDescriptionGaps > 0 ? (
                  <span className="text-xs text-muted/50">{visibleDescriptionGaps} Treffer im aktuellen Blick brauchen erst mehr Beschreibung.</span>
                ) : null}
              </div>
              <h2 className="mt-3 text-base font-semibold text-ink">{jobsGuidance.title}</h2>
              <p className="mt-1 max-w-3xl text-sm text-muted">{jobsGuidance.description}</p>
            </div>
            {jobsGuidance.actionLabel ? (
              <Button size="sm" variant="secondary" onClick={jobsGuidance.action}>
                {jobsGuidance.actionLabel}
              </Button>
            ) : null}
          </div>
        </Card>

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
              {filteredJobs.length}{jobsTotal > jobs.length ? ` / ${jobsTotal}` : ` / ${currentList.length}`}
            </span>
            <SelectInput
              className="!min-h-0 !w-auto !rounded-lg !px-2 !py-1 text-[11px] !border-white/5 !bg-white/[0.03]"
              value={jobsPageSize}
              onChange={async (e) => {
                const newSize = Number(e.target.value);
                setJobsPageSize(newSize);
                localStorage.setItem("pbp_jobs_page_size", String(newSize));
                setLoading(true);
                await loadPage({ pageSize: newSize });
              }}
            >
              <option value="20">20 pro Seite</option>
              <option value="50">50 pro Seite</option>
              <option value="100">100 pro Seite</option>
              <option value="0">Alle</option>
            </SelectInput>
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

            <div className="group inline-flex items-center gap-1.5">
              <button
                type="button"
                className={cn(
                  "flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[13px] font-medium transition-colors",
                  filters.missingDescriptionOnly
                    ? "border-amber/20 bg-amber/8 text-amber"
                    : "border-white/5 bg-white/[0.03] text-muted/40 hover:bg-white/[0.05] hover:text-muted/60"
                )}
                onClick={() => setFilters((current) => ({ ...current, missingDescriptionOnly: !current.missingDescriptionOnly }))}
              >
                Nur ohne Beschreibung
              </button>
              {filters.missingDescriptionOnly && (
                <button type="button" onClick={() => setFilters((current) => ({ ...current, missingDescriptionOnly: false }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
              )}
            </div>

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
                    <button
                      type="button"
                      className="font-mono text-[10px] text-muted/30 hover:text-sky transition-colors"
                      title="ID kopieren"
                      onClick={async () => { try { await navigator.clipboard.writeText(job.hash); pushToast("ID kopiert.", "success", { duration: 2000 }); } catch {} }}
                    >#{String(job.hash).slice(0, 12)}</button>
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
                    {job.employment_type ? (
                      <Badge tone={job.employment_type === "freelance" ? "success" : job.employment_type === "festanstellung" ? "sky" : job.employment_type === "praktikum" ? "amber" : "neutral"}>
                        {job.employment_type === "freelance" ? "Freelance" : job.employment_type === "festanstellung" ? "Festanstellung" : job.employment_type === "praktikum" ? "Praktikum" : job.employment_type === "werkstudent" ? "Werkstudent" : job.employment_type}
                      </Badge>
                    ) : null}
                    {/* #154: Bereits-beworben-Badge aus matched applications */}
                    {appliedJobHashes.has(job.hash) ? (
                      <button
                        className="cursor-pointer"
                        onClick={(e) => { e.stopPropagation(); window.location.hash = "bewerbungen"; }}
                        title="Zur Bewerbung wechseln"
                      >
                        <Badge tone="success">Bereits beworben</Badge>
                      </button>
                    ) : null}
                    {jobNeedsDescriptionAttention(job) ? (
                      <Badge tone="amber">Score unsicher</Badge>
                    ) : null}
                  </div>
                  <div
                    role="button"
                    tabIndex={0}
                    className="cursor-pointer group rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-sky/50 focus-visible:ring-offset-2 focus-visible:ring-offset-night"
                    onClick={() => openDetailDialog(job)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openDetailDialog(job);
                      }
                    }}
                    title="Details anzeigen"
                  >
                    <h2 className="text-2xl font-semibold text-ink group-hover:text-sky transition-colors">{job.title}</h2>
                    <p className="text-sm text-muted">{job.company || "Unbekannte Firma"}{job.location ? ` - ${job.location}` : ""}</p>
                    <p className="text-sm text-muted">{textExcerpt(job.description, 220)}</p>
                    {jobNeedsDescriptionAttention(job) ? (
                      <p className="text-xs text-amber">
                        Beschreibung fehlt oder ist sehr kurz. Prüfe die Originalanzeige, bevor du den Score zu ernst nimmst.
                      </p>
                    ) : null}
                    {job.salary_min ? (
                      <p className="text-sm text-ink">
                        Gehalt: {formatCurrency(job.salary_min)}{job.salary_max ? ` bis ${formatCurrency(job.salary_max)}` : ""}{job.salary_estimated ? " (geschätzt)" : ""}
                      </p>
                    ) : null}
                  </div>
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
                    <Button variant="danger" onClick={() => openDismissDialog(job)}>
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
          ) : null}

          {/* Load more + page size (#145) */}
          {filteredJobs.length > 0 && jobsHasMore && filters.view === "active" && (
            <div className="flex items-center justify-center gap-4 py-4">
              <Button
                variant="secondary"
                disabled={loadingMore}
                onClick={async () => {
                  setLoadingMore(true);
                  await loadPage({ append: true, silent: true });
                }}
              >
                {loadingMore ? "Laden..." : `Mehr laden (${jobs.length} von ${jobsTotal})`}
              </Button>
              <Button
                variant="ghost"
                onClick={async () => {
                  setJobsPageSize(0);
                  localStorage.setItem("pbp_jobs_page_size", "0");
                  setLoading(true);
                  await loadPage({ pageSize: 0 });
                }}
              >
                Alle laden
              </Button>
            </div>
          )}

          {filteredJobs.length === 0 && (
            <EmptyState
              title={filters.view === "active" ? "Keine aktiven Stellen" : "Keine ausgeblendeten Stellen"}
              description={filters.view === "active" ? "Starte eine Jobsuche oder öffne das Suchprofil, um neue Stellen zu finden." : "Ausgeblendete Jobs können hier später wieder aktiviert werden."}
              action={filters.view === "active" ? (
                <div className="flex gap-3">
                  <Button onClick={() => navigateTo("einstellungen")}>Suchprofil öffnen</Button>
                  <Button variant="secondary" onClick={() => copyPrompt("/jobsuche_workflow")}>
                    <Search size={15} />
                    Jobsuche starten
                  </Button>
                </div>
              ) : null}
            />
          )}
        </div>
      </div>

      <Modal
        open={fitDialog.open}
        title={`Fit-Analyse \u2014 ${fitDialog.title}`}
        onClose={() => setFitDialog({ open: false, title: "", hash: "", analysis: null })}
        footer={<div className="flex justify-end"><Button onClick={() => setFitDialog({ open: false, title: "", hash: "", analysis: null })}>Schliessen</Button></div>}
      >
        <div className="grid gap-4">
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">Gesamtscore</p>
            <p className="mt-3 text-4xl font-semibold text-ink">{fitDialog.analysis?.total_score ?? 0}</p>
            {fitDialog.analysis?.hochschulabschluss_gefordert && (
              <p className="mt-1 text-xs text-coral font-medium">Hochschulabschluss gefordert</p>
            )}
          </Card>
          {/* Scoring-Faktoren Aufschlüsselung (#306) */}
          {fitDialog.analysis?.factors && Object.keys(fitDialog.analysis.factors).length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-sm font-semibold text-ink mb-2">Score-Faktoren</p>
              <div className="grid gap-1">
                {Object.entries(fitDialog.analysis.factors).map(([label, pts]) => (
                  <div key={label} className="flex justify-between text-sm">
                    <span className="text-muted/70">{label}</span>
                    <span className={`font-medium ${pts >= 0 ? "text-teal" : "text-coral"}`}>{pts >= 0 ? "+" : ""}{pts}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-sm font-semibold text-ink">MUSS-Treffer</p>
            <p className="mt-2 text-sm text-muted">{(fitDialog.analysis?.muss_hits || []).join(", ") || "Keine"}</p>
          </Card>
          {(fitDialog.analysis?.missing_muss || []).length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-sm font-semibold text-ink">Fehlende MUSS-Kriterien</p>
              <p className="mt-2 text-sm text-coral/80">{fitDialog.analysis.missing_muss.join(", ")}</p>
            </Card>
          )}
          {(fitDialog.analysis?.plus_hits || []).length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-sm font-semibold text-ink">PLUS-Treffer</p>
              <p className="mt-2 text-sm text-teal/80">{fitDialog.analysis.plus_hits.join(", ")}</p>
            </Card>
          )}
          {(fitDialog.analysis?.risks || []).length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-sm font-semibold text-ink">Risiken</p>
              <div className="mt-2 grid gap-2 text-sm text-coral/70">
                {fitDialog.analysis.risks.map((risk) => <p key={risk}>{risk}</p>)}
              </div>
            </Card>
          )}
          {/* Claude-Analyse / Research Notes (#306) */}
          {fitDialog.analysis?.research_notes && (
            <Card className="glass-card-soft rounded-xl shadow-none border border-sky/15">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-semibold text-sky">Claude-Analyse</p>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(fitDialog.analysis.research_notes).then(
                      () => pushToast("Analyse in Zwischenablage kopiert", "success"),
                      () => pushToast("Kopieren fehlgeschlagen", "danger")
                    );
                  }}
                  className="text-muted/40 hover:text-sky transition-colors"
                  title="In Zwischenablage kopieren"
                >
                  <ClipboardCopy size={14} />
                </button>
              </div>
              <p className="text-sm text-muted/70 whitespace-pre-line">{fitDialog.analysis.research_notes}</p>
            </Card>
          )}
          <Button
            variant="secondary"
            className="w-full"
            onClick={() => {
              const hash = fitDialog.hash || "";
              const prompt = `Bewerte die Stelle "${fitDialog.title}" (Hash: ${hash}) detailliert fuer mich. Rufe die Stellenbeschreibung ab, vergleiche sie mit meinem Profil und gib mir eine ehrliche Einschaetzung: Staerken, Schwaechen, Risiken, und ob sich eine Bewerbung lohnt.`;
              copyPrompt(prompt);
            }}
          >
            <Search size={15} />
            Detailbewertung durch Claude anfordern
          </Button>
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

      {/* Dismiss Dialog with reason selection (#108, #120) */}
      <Modal
        open={dismissDialog.open}
        title={`Stelle aussortieren — ${dismissDialog.job?.title || ""}`}
        onClose={() => setDismissDialog(EMPTY_DISMISS_DIALOG)}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setDismissDialog(EMPTY_DISMISS_DIALOG)}>Abbrechen</Button>
            <Button variant="danger" onClick={saveDismiss}>
              <EyeOff size={15} />
              Aussortieren
            </Button>
          </div>
        }
      >
        <div className="grid gap-4">
          <p className="text-sm text-muted">Warum passt diese Stelle nicht? (Mehrfachauswahl möglich)</p>
          <div className="flex flex-wrap gap-2">
            {(dismissReasons.length ? dismissReasons : [
              { label: "zu_weit_entfernt" }, { label: "gehalt_zu_niedrig" }, { label: "falsches_fachgebiet" },
              { label: "zu_junior" }, { label: "zu_senior" }, { label: "unpassendes_arbeitsmodell" },
              { label: "firma_uninteressant" }, { label: "zeitarbeit" }, { label: "befristet" }, { label: "sonstiges" },
            ]).map((reason) => {
              const selected = dismissDialog.selectedReasons.includes(reason.label);
              const displayLabel = reason.label.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
              return (
                <button
                  key={reason.label}
                  type="button"
                  className={cn(
                    "rounded-lg border px-3 py-1.5 text-[13px] font-medium transition-colors",
                    selected
                      ? "border-coral/30 bg-coral/15 text-coral"
                      : "border-white/10 bg-white/[0.04] text-muted/60 hover:bg-white/[0.08] hover:text-muted/80"
                  )}
                  onClick={() => toggleDismissReason(reason.label)}
                >
                  {selected ? <Check size={12} className="mr-1 inline -mt-0.5" /> : null}
                  {displayLabel}
                  {reason.usage_count > 0 ? <span className="ml-1 text-[11px] opacity-50">({reason.usage_count})</span> : null}
                </button>
              );
            })}
          </div>
          <Field label="Eigener Grund (optional)">
            <TextInput
              placeholder="z.B. kein Home-Office möglich"
              value={dismissDialog.customReason}
              onChange={(e) => setDismissDialog((cur) => ({ ...cur, customReason: e.target.value }))}
            />
          </Field>
        </div>
      </Modal>

      {/* Job Detail Modal (#90) */}
      {detailDialog.open && detailDialog.job && (
        <Modal
          open={detailDialog.open}
          title={detailDialog.editing ? "Stelle bearbeiten" : "Stellendetails"}
          onClose={() => setDetailDialog({ open: false, job: null, editing: false })}
          size="xl"
        >
          {detailDialog.editing ? (
            <div className="space-y-4">
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
                  <h3 className="text-xl font-semibold text-ink">{detailDialog.job.title}</h3>
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
                <button
                  type="button"
                  className="font-mono text-[10px] text-muted/40 hover:text-sky transition-colors"
                  title="ID kopieren"
                  onClick={async () => { try { await navigator.clipboard.writeText(detailDialog.job.hash); pushToast("ID kopiert.", "success", { duration: 2000 }); } catch {} }}
                >#{String(detailDialog.job.hash).slice(0, 12)}</button>
                <Badge tone="sky">{detailDialog.job.source || "Quelle"}</Badge>
                {detailDialog.job.employment_type ? <Badge tone={detailDialog.job.employment_type === "freelance" ? "success" : "neutral"}>{detailDialog.job.employment_type}</Badge> : null}
                {detailDialog.job.remote_level && detailDialog.job.remote_level !== "unbekannt" ? <Badge tone="success">{detailDialog.job.remote_level}</Badge> : null}
                <Badge tone="amber">Score {detailDialog.job.score || 0}</Badge>
                {jobNeedsDescriptionAttention(detailDialog.job) ? <Badge tone="amber">Score unsicher</Badge> : null}
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
              {jobNeedsDescriptionAttention(detailDialog.job) ? (
                <Card className="rounded-xl border-amber/20 bg-amber/10 shadow-none">
                  <p className="text-sm font-semibold text-ink">Beschreibung zuerst nachziehen</p>
                  <p className="mt-1 text-sm text-muted">
                    Für diese Stelle fehlt eine belastbare Beschreibung. Der Score ist deshalb nur eine Vororientierung und kein sauberes Urteil.
                  </p>
                </Card>
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

