import { Ban, BriefcaseBusiness, Check, ClipboardCopy, Download, EyeOff, ExternalLink, Filter, Pencil, Pin, PinOff, Plus, RotateCcw, Search, SlidersHorizontal, Target, X } from "lucide-react";
import { startTransition, useCallback, useDeferredValue, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";

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
import { jobLinkInfo } from "@/lib/jobLink";
import { kurzmarke as datenguetMarke, vergleicheMitGuete } from "@/lib/datenguete";
import AdaptiveHintBanner from "@/components/AdaptiveHintBanner";
import OnboardingHintBanner from "@/components/OnboardingHintBanner";
import { buildAnnualSalaryMetrics, grundlagenText } from "@/lib/gehaltsKennzahl";

const EMPTY_APPLICATION = {
  job_hash: "",
  title: "",
  company: "",
  url: "",
  // #981 (D43): Vorgabe ist "will mich bewerben". Im Stellen-Tab steht
  // man in aller Regel VOR der Bewerbung — und nur bei `beworben`
  // entsteht ein Auto-Nachfass (#522), der sonst zu frueh laeuft.
  status: "in_vorbereitung",
  applied_at: "",
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

function jobNeedsDescriptionAttention(job) {
  // v1.7.7 (#756): score-unabhaengig — gerade Score-0-Stellen ohne
  // Beschreibung sind unbewertet, nicht uninteressant. Vorher fielen
  // genau sie durchs Raster (score > 0 war Bedingung).
  return String(job?.description || "").trim().length < 50;
}

function descriptionAttentionLabel(job) {
  return Number(job?.score || 0) > 0 ? "Score unsicher" : "Unbewertet";
}

// #1007: kurze Etiketten fuer das Urteil der Detailanalyse. Die
// Kategorien selbst bleiben, wie der #662-Vertrag sie nennt — hier
// steht nur die Beschriftung fuer eine schmale Karte.
// v1.7.62 (#1008): die Filter-Vorgabe steht EINMAL. Vorher lag die
// Zuruecksetz-Form als Literal im Hinweis-Block, die Startwerte separat
// im useState — zwei Fassungen derselben Sache, und genau daraus sind
// #963, #991 und #992 entstanden. Der Hinweis ueber der Liste, der
// Zuruecksetzen-Knopf und der Startzustand lesen jetzt dasselbe Objekt.
//
// `minScore: "0"` ist die eigentliche Korrektur an #1008: der Wert kam
// bis v1.7.61 aus `search_criteria.min_score_schwelle`. Das ist laut
// eigener Beschreibung die Schwelle, ab der eine Stelle beim Suchlauf
// ueberhaupt GESPEICHERT wird — nicht ein Anzeige-Filter. Seit v1.7.50
// (#993) den toten Zugriff darauf repariert hat, wirkte sie
// tatsaechlich, und zwar ohne dass der Nutzer sie je gesetzt haette:
// sieben von acht Stellen waren unsichtbar. Die Anzeige-Schwelle heisst
// `schwellenwert/auto_ignore` und wirkt serverseitig; sie hier ein
// zweites Mal nachzubauen waere derselbe Fehler in Gruen.
export const FILTER_STANDARD = {
  query: "",
  source: "",
  minScore: "0",
  remote: "",
  salaryOnly: false,
  sort: "score_desc",
  view: "active",
  employmentType: "",
  // #1023: der Umfang als eigener Filter — zweite Dimension.
  arbeitsumfang: "",
  hideApplied: true,
  missingDescriptionOnly: false,
  // #948: EIN Filter fuer den Pruefstand, drei Werte. Vorher stand
  // hier `onlyAnalysed` als Ja/Nein — die Gegenrichtung ("zeig mir,
  // was ich noch nicht angesehen habe") war damit gar nicht
  // erreichbar, und genau die braucht man beim Sichten. Zwei
  // Schalter fuer dieselbe Frage waeren #988 gewesen, deshalb ersetzt
  // das Feld den alten Schalter, statt danebenzustehen.
  // Vorgabe LEER — ein Filter, den niemand gesetzt hat, war der ganze
  // Befund von #1008.
  pruefstand: "",
};

// Welche Filter unterdruecken gerade Eintraege — und wie macht man das
// rueckgaengig. Der Hinweis ueber der Liste und die Filterzeile
// beantworten damit dieselbe Frage aus derselben Quelle.
export function aktiveFilterBestimmen(filters) {
  const aktiv = [];
  if (filters.query) aktiv.push({ schluessel: "query", text: `Suchtext "${filters.query}"` });
  if (filters.source) aktiv.push({ schluessel: "source", text: `Quelle ${filters.source}` });
  if (Number(filters.minScore || 0) > 0) aktiv.push({ schluessel: "minScore", text: `Score ab ${filters.minScore}` });
  if (filters.remote) aktiv.push({ schluessel: "remote", text: `Remote ${filters.remote}` });
  if (filters.salaryOnly) aktiv.push({ schluessel: "salaryOnly", text: "nur mit Gehalt" });
  if (filters.employmentType) aktiv.push({ schluessel: "employmentType", text: filters.employmentType });
  if (filters.arbeitsumfang) aktiv.push({ schluessel: "arbeitsumfang", text: filters.arbeitsumfang });
  if (filters.hideApplied) aktiv.push({ schluessel: "hideApplied", text: "beworbene ausgeblendet" });
  if (filters.missingDescriptionOnly) aktiv.push({ schluessel: "missingDescriptionOnly", text: "nur ohne Beschreibung" });
  if (filters.pruefstand) {
    aktiv.push({
      schluessel: "pruefstand",
      text: filters.pruefstand === "ungeprueft" ? "nur ungeprüfte" : "nur beurteilte",
    });
  }
  return aktiv;
}

// #1010: die Herkunft kommt vom Server (`services/aussortier_protokoll.py`).
// Hier steht nur, wie sie HEISST — die Regel dahinter ist nicht trivial
// und gehoert an genau eine Stelle.
export const HERKUNFT_ETIKETT = {
  ich: "von mir",
  automatik: "Automatik",
  unbekannt: "Herkunft unbekannt",
};

export function dismissWindowGrenze(fenster) {
  if (fenster === "alle") return null;
  const jetzt = new Date();
  if (fenster === "heute") {
    return new Date(jetzt.getFullYear(), jetzt.getMonth(), jetzt.getDate()).getTime();
  }
  const tage = fenster === "30tage" ? 30 : 7;
  return jetzt.getTime() - tage * 24 * 60 * 60 * 1000;
}

// #1023: Anstellungsform und Umfang sind ZWEI Merkmale. Bis v1.7.83
// stand die Zuordnung als verschachtelter Ternaer direkt im JSX — mit
// zwei Dimensionen und sechs Formen waere daraus eine Zeile geworden,
// die niemand mehr liest. Und `zeitarbeit` und `ausbildung` fehlten
// dort, obwohl sie im Bestand vorkommen.
const ANSTELLUNGSFORM_TEXT = {
  festanstellung: "Festanstellung",
  zeitarbeit: "Zeitarbeit",
  freelance: "Freelance",
  praktikum: "Praktikum",
  werkstudent: "Werkstudent",
  ausbildung: "Ausbildung",
};

const ANSTELLUNGSFORM_TON = {
  festanstellung: "sky",
  freelance: "success",
  praktikum: "amber",
  werkstudent: "amber",
  ausbildung: "amber",
  zeitarbeit: "danger",
};

const UMFANG_TEXT = {
  vollzeit: "Vollzeit",
  teilzeit: "Teilzeit",
  // "Vollzeit / Teilzeit" ist eine ZUSAGE, keine Mehrdeutigkeit — ein
  // Etikett mit nur zwei Werten macht daraus eine Falschangabe.
  beides: "Voll- oder Teilzeit",
};

const ANALYSE_ETIKETT = {
  EMPFOHLEN: "Empfohlen",
  BEDINGT: "Bedingt",
  NICHT_EMPFOHLEN: "Nicht empfohlen",
  NICHT_BEURTEILBAR: "Nicht beurteilt",
};

// #948: der Text am Abzeichen. Was "ueberholt" BEDEUTET, entscheidet
// der Server (`services/passung.py`) — hier wird der Befund nur
// vorgelesen, samt der beiden Zahlen, die ihn belegen. Ein "veraltet"
// ohne Beleg waere eine Behauptung.
export function pruefstandTitel(job) {
  const stand = job?.pruefstand;
  if (!stand) return "";
  const teile = [stand.text];
  if (stand.am) teile.push(`am ${String(stand.am).slice(0, 10)}`);
  if (job?.analyse?.begruendung) teile.push(job.analyse.begruendung);
  const alt = stand.ueberholt;
  if (alt) {
    if (alt.grund?.includes("score")) {
      teile.push(`Score seither ${alt.score_damals} → ${alt.score_jetzt}`);
    }
    if (alt.grund?.includes("profil")) {
      teile.push("Profil hat sich seither geändert");
    }
  }
  return teile.filter(Boolean).join(" — ");
}


export default function JobsPage() {
  const { chrome, intent, clearIntent, reloadKey, refreshChrome, pushToast, copyPrompt, navigateTo, startJobsuche } = useApp();
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState([]);
  const [dismissedJobs, setDismissedJobs] = useState([]);
  // #1010: Zeitfenster fuer das Aussortier-Protokoll. Ueber 2.000
  // Eintraege ohne Einstieg sind ein Archiv, kein Rueckholweg — und
  // gesucht wird fast immer "was habe ich gerade weggeklickt".
  // #1010 hatte hier "7tage" als Vorgabe: gesucht wird "was habe ich
  // gerade weggeklickt", und eine Liste mit 2.000 Eintraegen ist ein
  // Archiv. Der Gedanke stimmt — die Vorgabe war trotzdem falsch.
  //
  // v1.7.83 (#1022 Befund 2): der Melder sah "AKTIVE STELLEN 54" ueber
  // 172 ausgeblendeten Stellen und konnte die 54 von aussen nicht
  // aufloesen. Es war dieses Fenster. **Ein Filter, den niemand gesetzt
  // hat, verbarg 118 von 172 Zeilen** — woertlich #1008, wo ein
  // ungesetzter Filter 7 von 8 Stellen verbarg.
  //
  // Die Sortierung erledigt den urspruenglichen Zweck ohnehin: das
  // Protokoll ist nach `dismissed_at` sortiert, das gerade Weggeklickte
  // steht oben. Dafuer muss nichts verborgen werden.
  const [dismissWindow, setDismissWindow] = useState("alle");
  // #941: Die zuletzt AUTOMATISCH aussortierten Stellen. Bewusst nicht
  // der ganze Aussortiert-Bestand (ueber 2.000 Eintraege) — nur das,
  // was ohne Rueckfrage entschieden wurde und der Nutzer nie gesehen
  // hat. Ohne diese Einsicht faellt eine zu scharfe Regel niemandem auf.
  const [autoDismissed, setAutoDismissed] = useState([]);
  const [autoOpen, setAutoOpen] = useState(false);
  const [autoLimit, setAutoLimit] = useState(() => {
    const gespeichert = Number(localStorage.getItem("pbp-auto-dismiss-limit"));
    return Number.isFinite(gespeichert) && gespeichert > 0 ? gespeichert : 20;
  });
  const [followUps, setFollowUps] = useState([]);
  // v1.7.62 (#1008): siehe FILTER_STANDARD oben. Die Liste startet
  // ungefiltert; wer filtern will, sagt es.
  const [filters, setFilters] = useState({ ...FILTER_STANDARD });
  const [appliedJobHashes, setAppliedJobHashes] = useState(new Set());
  const [fitDialog, setFitDialog] = useState({ open: false, title: "", analysis: null });
  const [detailDialog, setDetailDialog] = useState({ open: false, job: null, editing: false });
  const [refetchBusy, setRefetchBusy] = useState(false);
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
  // #989: Wie mit Ungepruefttem umgegangen wird. Die Liste im Browser
  // muss dieselbe Reihenfolge zeigen wie die im Chat — sonst waere die
  // Einstellung eine halbe.
  const [guetUmgang, setGuetUmgang] = useState("nachrangig");
  const [jobsTotal, setJobsTotal] = useState(0);
  // #1022: die Kennzahlen der Kopfzeile rechnen ueber den GANZEN aktiven
  // Bestand, nicht ueber die geladene Seite. Der Endpunkt gibt dafuer
  // eine schlanke Grundlage mit (Score + vier Gehaltsfelder je Stelle) —
  // die Rechnung selbst bleibt `buildAnnualSalaryMetrics`, damit es
  // keine zweite Fassung gibt.
  const [kennzahlenBasis, setKennzahlenBasis] = useState([]);
  const [aussortiertGesamt, setAussortiertGesamt] = useState(0);
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
      const [activeJobsResp, hiddenJobs, followUpsResponse, appsResponse, reasons, guete] = await Promise.all([
        api(jobsUrl),
        append ? Promise.resolve(null) : api("/api/jobs?active=false"),
        append ? Promise.resolve(null) : api("/api/follow-ups"),
        append ? Promise.resolve(null) : api("/api/applications"),
        append ? Promise.resolve(null) : optionalApi("/api/dismiss-reasons"),
        append ? Promise.resolve(null) : optionalApi("/api/datenguete/umgang"),
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
          // #1022: auch beim Nachladen mitgesetzt — die Grundlage
          // beschreibt den Bestand und aendert sich dabei nicht. Faellt
          // sie aus, bleibt der alte Stand stehen statt auf die
          // geladene Seite zurueckzufallen: eine Kennzahl ueber den
          // halben Bestand ist schlimmer als eine, die kurz veraltet.
          if (Array.isArray(activeJobsResp.kennzahlen_basis)) {
            setKennzahlenBasis(activeJobsResp.kennzahlen_basis);
          }
          if (typeof activeJobsResp.aussortiert_gesamt === "number") {
            setAussortiertGesamt(activeJobsResp.aussortiert_gesamt);
          }
        } else {
          setJobsTotal(newJobs.length);
          setJobsHasMore(false);
          // Ohne Paginierung IST die geladene Liste der Bestand.
          setKennzahlenBasis(newJobs);
        }
        if (!append) {
          if (hiddenJobs) {
            setDismissedJobs(hiddenJobs || []);
            // #1022: die Zahl im Tab-Namen. Beim Vollabruf ist sie hier
            // genauer als die des Endpunkts.
            setAussortiertGesamt((hiddenJobs || []).length);
          }
          if (followUpsResponse) setFollowUps(followUpsResponse?.follow_ups || []);
          if (appsResponse) {
            const appHashes = new Set((appsResponse?.applications || []).filter(a => a.job_hash && !["abgelehnt","zurueckgezogen","abgelaufen"].includes(a.status)).map(a => a.job_hash));
            setAppliedJobHashes(appHashes);
          }
          if (reasons) setDismissReasons(reasons);
          if (guete?.umgang) setGuetUmgang(guete.umgang);
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
      // v1.7.62 (#1008): auch der Sprung auf eine bestimmte Stelle
      // raeumt ueber dieselbe Definition ab — sonst haette ein kuenftig
      // neuer Filter die angesprungene Stelle weiter verborgen.
      setFilters((current) => ({
        ...current,
        ...FILTER_STANDARD,
        view: "active",
        sort: current.sort,
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
    filters.pruefstand,
    filters.sort,
  ]);

  async function showFitAnalysis(job) {
    try {
      const analysis = await api(`/api/jobs/${job.hash}/fit-analyse`);
      // #1009: die ganze Stelle behalten — der Dialog soll danach
      // handeln koennen, ohne dass der Mensch sie in der Liste
      // wiedersuchen muss.
      setFitDialog({ open: true, title: job.title, hash: job.hash, job, analysis });
    } catch (error) {
      pushToast(`Fit-Analyse fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  const ladeAutoAussortiert = useCallback(async (limit) => {
    const daten = await optionalApi(`/api/jobs/auto-dismissed?limit=${limit}`);
    setAutoDismissed(Array.isArray(daten?.jobs) ? daten.jobs : []);
  }, []);

  useEffect(() => {
    ladeAutoAussortiert(autoLimit);
  }, [ladeAutoAussortiert, autoLimit]);

  async function holeZurueck(job) {
    try {
      await postJson("/api/jobs/restore", { hash: job.hash });
      setAutoDismissed((cur) => cur.filter((j) => String(j.hash) !== String(job.hash)));
      setJobs((cur) => [{ ...job, status: "aktiv" }, ...cur]);
      refreshChrome({ quiet: true });
      pushToast("Stelle zurueckgeholt — die Ruecknahme ist protokolliert.", "success");
    } catch (error) {
      pushToast(`Zurueckholen fehlgeschlagen: ${error.message}`, "danger");
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
    const entwurf = applicationDialog.draft;
    try {
      const erg = await postJson("/api/applications", entwurf);
      setApplicationDialog({ open: false, draft: EMPTY_APPLICATION });
      await refreshChrome();
      // D43 (#981): wer sich erst bewerben WILL, braucht als Naechstes
      // die Unterlagen — und zwar zu genau dieser Stelle. Bisher lag der
      // Prompt nur im Dashboard-Schnellzugriff, ohne Stellenbezug, und
      // der Nutzer musste Stelle und Firma im Chat noch einmal nennen.
      if (entwurf.status === "in_vorbereitung") {
        pushToast(
          "Bewerbung angelegt. Unterlagen jetzt mit Claude erstellen?",
          "success",
          {
            duration: 12000,
            action: {
              label: "Anleitung kopieren",
              onClick: () => unterlagenAnleitungKopieren(entwurf, erg?.id || ""),
            },
          }
        );
      } else {
        pushToast("Bewerbung angelegt.", "success");
      }
      navigateTo("bewerbungen");
    } catch (error) {
      pushToast(`Bewerbung konnte nicht angelegt werden: ${error.message}`, "danger");
    }
  }

  // Vorbefuellte Anleitung fuer Lebenslauf und Anschreiben (#981, D43).
  // `nur` bleibt leer — der Prompt fragt nach dem Umfang, weil nicht
  // jede Stelle ein Anschreiben verlangt.
  async function unterlagenAnleitungKopieren(entwurf, bewerbungId) {
    try {
      const params = new URLSearchParams({
        stelle: entwurf?.title || "",
        firma: entwurf?.company || "",
        job_hash: entwurf?.job_hash || "",
        bewerbung_id: bewerbungId || "",
      });
      const resolved = await api(`/api/workflow-prompt/bewerbung_schreiben?${params}`);
      await navigator.clipboard.writeText(resolved?.prompt || "");
      pushToast(
        "Anleitung kopiert — jetzt in Claude Desktop einfuegen (Strg+V).",
        "success",
        { duration: 7000 }
      );
    } catch (error) {
      pushToast(`Anleitung konnte nicht geladen werden: ${error.message}`, "danger");
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
      // Die Stelle VOR dem Entfernen festhalten — der Rueckgaengig-Knopf
      // im Toast braucht sie noch, und aus der Liste ist sie dann weg.
      const dismissed = jobs.find((j) => String(j.hash) === String(hash));
      startTransition(() => {
        setJobs((cur) => cur.filter((j) => String(j.hash) !== String(hash)));
        if (dismissed) setDismissedJobs((cur) => [{ ...dismissed, status: "aussortiert" }, ...cur]);
      });
      refreshChrome({ quiet: true });
      // Reload dismiss reasons so custom reasons appear immediately (#302)
      try {
        const updated = await optionalApi("/api/dismiss-reasons");
        if (updated) setDismissReasons(updated);
      } catch (_) { /* ignore */ }
      // #1010: der Verklicker faellt in Sekunden auf, nicht in Tagen —
      // dort gehoert die Umkehr hin. Das Protokoll ist der zweite Weg,
      // fuer den Fall, dass der Toast schon weg ist.
      pushToast("Stelle aussortiert.", "success", {
        duration: 9000,
        action: {
          label: "Rückgängig",
          onClick: () => holeZurueck(dismissed || { hash }),
        },
      });
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

  // #1009: EIN Oeffner fuer den Bewerbungs-Dialog. Der Entwurf stand als
  // Literal direkt am Karten-Knopf; ihn im Fit-Dialog noch einmal
  // hinzuschreiben waere die zweite Fassung derselben Sache — das Muster,
  // das dieses Projekt achtmal gekostet hat (#963, #913, #976, #987,
  // #991, #992, #994, #1008).
  function openApplicationDialog(job) {
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
    });
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

  // ACHTUNG Reihenfolge: dieser Block steht VOR dem fruehen
  // `if (loading) return ...`. Ein useMemo dahinter laeuft im ersten
  // Rendern nicht mit und im zweiten schon — React verwirft die
  // Komponente dann. Gefunden hat es der Browser-Test: der
  // Vite-Build war gruen, und in der Konsole stand nichts.
  // #1010: die Ausgeblendet-Ansicht ist das Protokoll. Sortiert wird nach
  // dem Zeitpunkt der AUSSORTIERUNG — `updated_at` taugt dafuer nicht,
  // die Spalte fasst jede Score-Neuberechnung an, und nach einem Suchlauf
  // stand die eben weggeklickte Stelle nicht mehr oben.
  const protokollListe = useMemo(() => {
    const grenze = dismissWindowGrenze(dismissWindow);
    const gefiltert = grenze === null
      ? dismissedJobs
      : dismissedJobs.filter((j) => {
          const wann = Date.parse(j.dismissed_at || "");
          // Ohne Zeitpunkt (Altbestand) laesst sich nichts einordnen —
          // solche Zeilen erscheinen nur unter "alle", statt still in ein
          // Fenster gerechnet zu werden.
          return !Number.isNaN(wann) && wann >= grenze;
        });
    return [...gefiltert].sort(
      (a, b) => (Date.parse(b.dismissed_at || "") || 0) - (Date.parse(a.dismissed_at || "") || 0)
    );
  }, [dismissedJobs, dismissWindow]);

  const ohneZeitpunkt = dismissedJobs.filter((j) => !j.dismissed_at).length;

  if (loading) return <LoadingPanel label="Stellen werden geladen..." />;

  const allJobs = [...jobs, ...dismissedJobs];
  const sourceOptions = [...new Set(allJobs.map((job) => job.source).filter(Boolean))];
  const remoteOptions = [...new Set(allJobs.map((job) => job.remote_level).filter((r) => r && r !== "unbekannt"))];
  const employmentTypeOptions = [...new Set(allJobs.map((job) => job.employment_type).filter(Boolean))];
  // #1023: nur Werte, die im Bestand wirklich vorkommen — und
  // `unbekannt` gehoert nicht in eine Auswahl, die etwas einschraenken
  // soll.
  const umfangOptions = [...new Set(
    allJobs.map((job) => job.arbeitsumfang)
      .filter((u) => u && u !== "unbekannt"))];
  const currentList = filters.view === "active" ? jobs : protokollListe;
  // #1022: die vier Kennzahlen der Kopfzeile beschreiben den BESTAND.
  // Bis v1.7.82 rechneten sie ueber die geladene Seite — und weil nach
  // Score sortiert wird, waren das immer die besten: Durchschnittsscore
  // 13,82 ueber die ersten 20 gegen 3,59 ueber alle 1.110 (gemessen vom
  // Melder). Eine Kennzahl, die sich beim Blaettern aendert, misst das
  // Blaettern.
  const kennzahlenQuelle = kennzahlenBasis.length ? kennzahlenBasis : jobs;
  const scoredActiveJobs = kennzahlenQuelle.filter((job) => Number(job?.score || 0) > 0);
  const jobsWithoutDescriptionCount = jobs.filter(jobNeedsDescriptionAttention).length;
  const hiddenAppliedCount = currentList.filter((job) => appliedJobHashes.has(job.hash)).length;
  const salaryMetrics = buildAnnualSalaryMetrics(kennzahlenQuelle);
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
  // beta.32 / User-Feedback: echte Bandbreite, nicht Durchschnitt der Spannen
  const bandMin = Number(salaryMetrics.bandMin);
  const bandMax = Number(salaryMetrics.bandMax);
  const hasBandMin = Number.isFinite(bandMin);
  const hasBandMax = Number.isFinite(bandMax);
  const salaryBandText = hasBandMin && hasBandMax
    ? `${fmtNum(bandMin)} – ${fmtNum(bandMax)} EUR`
    : hasBandMin
      ? formatCurrency(bandMin)
      : hasBandMax
        ? formatCurrency(bandMax)
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
      // #1023: "beides" zaehlt als Treffer fuer BEIDE Richtungen. Eine
      // Anzeige, die Voll- UND Teilzeit anbietet, ist fuer jemanden,
      // der Teilzeit sucht, eine Teilzeitstelle — sie herauszufiltern
      // waere dieselbe Falschaussage wie ein Etikett mit zwei Werten.
      const umfangMatch = !filters.arbeitsumfang
        || job.arbeitsumfang === filters.arbeitsumfang
        || (job.arbeitsumfang === "beides"
            && (filters.arbeitsumfang === "teilzeit"
                || filters.arbeitsumfang === "vollzeit"));
      const appliedMatch = !filters.hideApplied || !appliedJobHashes.has(job.hash);
      const descriptionMatch = !filters.missingDescriptionOnly || jobNeedsDescriptionAttention(job);
      // #1007/#948: "noch nicht beurteilt" ist kein Urteil. Welcher
      // Zustand gilt, entscheidet der Server (`services/passung.py`) —
      // hier steht nur, wonach gefiltert wird. Eine zweite Fassung der
      // Einteilung im JavaScript waere #963 im Frontend.
      const stand = job.pruefstand?.art || "ungeprueft";
      const analysedMatch = !filters.pruefstand || stand === filters.pruefstand;
      return queryMatch && sourceMatch && scoreMatch && remoteMatch && salaryMatch && typeMatch && umfangMatch && appliedMatch && descriptionMatch && analysedMatch;
    })
    .sort((a, b) => {
      // Pinned jobs always come first
      const pinA = a.is_pinned ? 1 : 0;
      const pinB = b.is_pinned ? 1 : 0;
      if (pinA !== pinB) return pinB - pinA;

      // v1.7.39 (#989): Datenguete VOR dem gewaehlten Kriterium. Eine
      // Stelle ohne Anzeigentext ist nicht schlecht bewertet, sie ist
      // gar nicht bewertet — und was nichts kostet, stand bisher oben.
      // Gemessen am 07.09.2026: inhaltsleerer Titel 101 Punkte, voll
      // beschriebene passende Stelle 32. Der Score bleibt unangetastet;
      // nur die Reihenfolge zieht die Konsequenz.
      // v1.7.68 (#968) AK 4: eine Stelle ohne Pflichttreffer steht nie
      // ueber einer mit. Die Entscheidung trifft der SERVER
      // (`services/muss_tor.py`) und schickt sie als `job.muss_tor` mit
      // — hier wird nur gelesen. Eine gespiegelte Fassung der Regel
      // waere der zweite Rechenweg fuer dieselbe Frage (#765, #963).
      const torA = a.muss_tor ? 1 : 0;
      const torB = b.muss_tor ? 1 : 0;
      if (torA !== torB) return torA - torB;

      return vergleicheMitGuete(a, b, (x, y) => {
      switch (filters.sort) {
        case "score_desc": return (y.score || 0) - (x.score || 0);
        case "score_asc": return (x.score || 0) - (y.score || 0);
        case "salary_desc": return (y.salary_max || y.salary_min || 0) - (x.salary_max || x.salary_min || 0);
        case "company": return (x.company || "").localeCompare(y.company || "");
        case "title": return (x.title || "").localeCompare(y.title || "");
        default: return 0;
      }
      }, guetUmgang);
    });

  // v1.7.62 (#1008): wie viele der GELADENEN Eintraege unterdruecken die
  // Filter gerade. Bewusst gegen `currentList` gerechnet und nicht gegen
  // `jobsTotal`: bei aktivem Nachladen waeren die noch nicht geholten
  // Seiten sonst als "durch Filter verborgen" gezaehlt worden — eine
  // Zahl, die zu hoch ist, ist so irrefuehrend wie eine, die fehlt.
  const verborgeneStellen = Math.max(0, currentList.length - filteredJobs.length);
  const aktiveFilter = aktiveFilterBestimmen(filters);
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
          ...FILTER_STANDARD,
          // Sortierung und Sicht sind keine Filter — sie unterdruecken
          // nichts und bleiben deshalb stehen.
          sort: current.sort,
          view: current.view,
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
        action: () => startJobsuche(),
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
      {/* beta.35: h1 sr-only — Top-Bar zeigt Breadcrumb */}
      <h1 className="sr-only">Stellen</h1>
      {/* v1.7.0-beta.29 (#594 Stufe 4): Adaptive UI-Hints */}
      <OnboardingHintBanner tab="stellen" />
      <AdaptiveHintBanner page="stellen" />
      <div className="mb-6 flex items-baseline gap-2">
        <span className="text-[11px] text-muted/40">
          {searchJob.running
    ? `Jobsuche läuft${searchJob.progress > 0 ? ` (${Math.round(searchJob.progress)}%)` : ""}`
            : chrome.searchStatus?.last_search
            ? `Aktualisiert ${chrome.searchStatus.days_ago === 0 ? "heute" : chrome.searchStatus.days_ago === 1 ? "gestern" : `vor ${chrome.searchStatus.days_ago} Tagen`}`
            : "Noch nie gesucht"}
        </span>
      </div>

      {/* Progress bar during job search (#210, #400) */}
      {searchJob.running && (
        <div className="mb-4 rounded-lg border border-sky/20 bg-sky/5 p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 font-medium text-sky">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-sky/30 border-t-sky" />
              {(() => {
                // #400: Parse source status from message for better display
                const msg = searchJob.message || "Jobsuche läuft...";
                const parts = msg.split(" | ");
                return parts[0];
              })()}
            </span>
            <span className="text-xs text-muted/50">{Math.round(searchJob.progress)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-sky transition-all duration-500 ease-out"
              style={{ width: `${Math.max(2, searchJob.progress)}%` }}
            />
          </div>
          {/* #400: Source progress summary */}
          {searchJob.message?.includes(" | ") && (
            <p className="mt-2 text-xs text-muted/40">{searchJob.message.split(" | ").slice(1).join(" — ")}</p>
          )}
        </div>
      )}

      <div className="grid gap-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            // v1.7.62 (#1008 Befund 1): die Zahl war die LAENGE DER
            // ANGEZEIGTEN Liste. Die Ueberschrift versprach die Zahl der
            // aktiven Stellen — zwei Zeilen darunter stand dann "8 aktiv
            // gesamt, 7 durch Filter verborgen". Damals bekam die
            // Ueberschrift einen Wechsel, damit sie benennt, was die Zahl
            // zeigt.
            //
            // v1.7.83 (#1022): das war die falsche Haelfte. Der Wechsel
            // haengt an `verborgeneStellen`, und das zaehlt nur
            // FILTER-verborgene Stellen — **Paginierung loest ihn nicht
            // aus**, also genau den haeufigsten Fall nicht. Die Kachel
            // meldete "AKTIVE STELLEN 20" bei 1.110 aktiven und wurde
            // beim Blaettern zu 40, dann 60. Der Melder dazu: "ich hab
            // immer gedacht, es gibt nur zwanzig Stellen fuer mich."
            //
            // Die Kopfzeile ist eine BESTANDSANZEIGE. Sie zeigt deshalb
            // immer die Zahl der aktiven Stellen — auch im
            // Ausgeblendet-Tab, wo vorher "AKTIVE STELLEN 54" ueber
            // ausgeblendeten Stellen stand. Was gerade sichtbar ist,
            // steht in der Notiz.
            label="Aktive Stellen"
            value={jobsTotal}
            note={(() => {
              // beta.26 / User-Feedback: Differenzierung zwischen
              //   - mit Bewerbung (echte applications, appliedJobHashes)
              //   - aussortiert (dismissed via "passt nicht")
              //   - anders ausgefiltert (UI-Filter, Score, etc.)
              // statt pauschal "X mit Bewerbung" wie vorher.
              // #702: jobsTotal zaehlt nur AKTIVE Stellen — Bewerbungen und
              // aussortierte sind eigene Mengen. Die alte Klammer-Form
              // ("2 gesamt (6 mit Bewerbung, 1676 aussortiert)") las sich wie
              // Teilmengen und war damit unsinnig. Jetzt entkoppelt.
              const withApplication = appliedJobHashes.size;
              const dismissedCount = aussortiertGesamt || dismissedJobs.length;
              const durchFilterVerborgen = verborgeneStellen;
              const parts = [];
              // #1022 AK 6: bei aktivem Filter gehoert die Einschraenkung
              // in die Notiz — die Kachel selbst bleibt beim Bestand.
              if (durchFilterVerborgen > 0) parts.push(`${filteredJobs.length} sichtbar, ${durchFilterVerborgen} durch Filter verborgen`);
              if (withApplication > 0) parts.push(`${withApplication} mit Bewerbung`);
              if (dismissedCount > 0) parts.push(`${dismissedCount} aussortiert`);
              if (parts.length > 0) return parts.join(" · ");
              return jobsWithSalary > 0
                ? `${jobsWithSalary} mit Gehalt${salaryEstimated ? " (geschätzt)" : ""}`
                : "Keine Gehaltsdaten";
            })()}
            tone="success"
          />
          <MetricCard
            label={`Gehaltsdurchschnitt${salaryEstimated ? " (geschätzt)" : ""}`}
            value={salaryAverage !== null ? formatCurrency(salaryAverage) : "Keine Angabe"}
            note={grundlagenText(salaryMetrics)}
            tone="success"
          />
          <MetricCard
            label={`Gehaltsbandbreite${salaryEstimated ? " (geschätzt)" : ""}`}
            value={salaryBandText}
            note={salaryCount > 0
              ? `Niedrigster bis höchster Wert über ${salaryCount} ${salaryCount === 1 ? "Stelle" : "Stellen"}`
              : "Echte Min/Max-Spanne ueber alle Stellen"}
            tone="success"
          />
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
              {/* #1022 AK 3+4: beide Tabs nennen ihre Menge, damit VOR
                  dem Klick erkennbar ist, was dahinter liegt. Die Zahlen
                  tragen die Toene, die das Dashboard ohnehin fuehrt —
                  Tuerkis fuer den Bestand, mit dem man arbeitet, Rot fuer
                  den Stapel, der aussortiert wurde. Beide Tokens gibt es
                  bereits; der Farbklassen-Guard aus #964 laesst nur
                  vorhandene durch. */}
              {[
                ["active", "Aktive", jobsTotal, "text-teal"],
                ["dismissed", "Ausgeblendet", aussortiertGesamt || dismissedJobs.length, "text-coral"],
              ].map(([value, label, menge, tonKlasse]) => (
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
                  {label}{" "}
                  <span className={cn("tabular-nums font-semibold", tonKlasse)}>({menge})</span>
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
                <button type="button" onClick={() => setFilters(f => ({ ...f, minScore: FILTER_STANDARD.minScore }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
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

            {/* #1007/#948: nach dem Pruefstand filtern. "Noch nicht
                beurteilt" ist kein Urteil — und wer sichtet, braucht
                die Gegenrichtung: da weitermachen, wo man aufgehoert
                hat. Ein Auswahlfeld statt zweier Schalter, damit es
                nicht zwei Einstellungen fuer dieselbe Frage gibt
                (#988). */}
            <div className="group inline-flex items-center gap-1.5">
              <SelectInput
                className={cn(
                  "!h-9 !min-h-0 !w-auto !rounded-xl !pl-3 !pr-3 !py-0 !text-[13px]",
                  filters.pruefstand
                    ? "!border-teal/20 !bg-teal/8 !text-teal/80"
                    : "!border-white/5 !bg-white/[0.03] !text-muted/60"
                )}
                value={filters.pruefstand}
                onChange={(event) => setFilters((current) => ({ ...current, pruefstand: event.target.value }))}
              >
                <option value="">Prüfstand: alle</option>
                <option value="ungeprueft">Nur ungeprüfte</option>
                <option value="gesichtet">Nur angesehene ohne Urteil</option>
                <option value="beurteilt">Nur beurteilte</option>
              </SelectInput>
              {filters.pruefstand && (
                <button type="button" onClick={() => setFilters(f => ({ ...f, pruefstand: "" }))} className="text-muted/40 hover:text-ink transition-colors"><X size={14} /></button>
              )}
            </div>

            {/* Employment Type Filter (#83) */}
            {employmentTypeOptions.length > 1 && (
              <SelectInput
                className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
                value={filters.employmentType}
                onChange={(e) => setFilters((f) => ({ ...f, employmentType: e.target.value }))}
              >
                <option value="">Alle Anstellungsformen</option>
                {employmentTypeOptions.map((t) => (
                  <option key={t} value={t}>{ANSTELLUNGSFORM_TEXT[t] || t}</option>
                ))}
              </SelectInput>
            )}

            {/* #1023: der zweite Filter — der UMFANG. Kombinierbar mit
                dem darueber ("alle Festanstellungen, davon Teilzeit").
                Er filtert die ANZEIGE und sortiert nichts aus: der
                Umfang steht bei den meisten Stellen gar nicht da.
                "Voll- oder Teilzeit" erscheint deshalb auch unter
                "Teilzeit" — eine Stelle, die beides anbietet, ist eine
                Teilzeitstelle fuer jemanden, der Teilzeit sucht. */}
            {umfangOptions.length > 1 && (
              <SelectInput
                className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
                value={filters.arbeitsumfang}
                onChange={(e) => setFilters((f) => ({ ...f, arbeitsumfang: e.target.value }))}
              >
                <option value="">Jeder Umfang</option>
                {umfangOptions.map((t) => (
                  <option key={t} value={t}>{UMFANG_TEXT[t] || t}</option>
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
          {/* v1.7.62 (#1008 Befund 1, AK 2 und 3): zeigt die Liste
              weniger als der Zaehler, gehoert der Grund UEBER die Liste
              — nicht in eine Kennzahl-Notiz daneben. Der Melder hat die
              Anwendung fuer defekt gehalten und mehrfach neu geladen.
              Ein Filter, der Eintraege unterdrueckt, muss sichtbar und
              mit einem Klick aufhebbar sein. */}
          {/* #1010: der Einstieg ins Protokoll. Ohne Zeitfenster ist eine
              Liste mit ueber 2.000 Eintraegen ein Archiv, kein
              Rueckholweg — gesucht wird "was habe ich gerade
              weggeklickt". */}
          {filters.view === "dismissed" && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
              <span className="text-[13px] text-muted/60">Aussortiert</span>
              <div className="inline-flex items-center gap-1">
                {[["heute", "heute"], ["7tage", "7 Tage"], ["30tage", "30 Tage"], ["alle", "alle"]].map(([wert, label]) => (
                  <button
                    key={wert}
                    type="button"
                    onClick={() => setDismissWindow(wert)}
                    className={cn(
                      "rounded-lg border px-2 py-1 text-[12px] font-medium transition-colors",
                      dismissWindow === wert
                        ? "border-teal/20 bg-teal/8 text-teal/80"
                        : "border-white/5 bg-white/[0.03] text-muted/40 hover:text-muted/60"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <span className="text-[12px] text-muted/45">
                {protokollListe.length} von {dismissedJobs.length}
              </span>
              {dismissWindow !== "alle" && ohneZeitpunkt > 0 && (
                <span className="text-[12px] text-muted/45">
                  · {ohneZeitpunkt} ohne Zeitpunkt (vor v1.7.64 aussortiert) — nur unter „alle"
                </span>
              )}
            </div>
          )}

          {verborgeneStellen > 0 && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-amber/30 bg-amber/[0.06] px-3 py-2">
              <span className="text-[13px] text-amber/90">
                {verborgeneStellen} {verborgeneStellen === 1 ? "Eintrag ist" : "Einträge sind"} durch aktive Filter verborgen
                {aktiveFilter.length > 0 && (
                  <span className="text-amber/60"> · {aktiveFilter.map((f) => f.text).join(" · ")}</span>
                )}
              </span>
              <button
                type="button"
                className="rounded-lg border border-amber/40 px-2 py-1 text-[12px] font-medium text-amber/90 transition-colors hover:bg-amber/10"
                onClick={() => setFilters((current) => ({
                  ...current,
                  ...FILTER_STANDARD,
                  sort: current.sort,
                  view: current.view,
                }))}
              >
                Filter aufheben
              </button>
            </div>
          )}
          {filteredJobs.length ? (
            filteredJobs.map((job) => (
              <Card
                key={job.hash}
                id={jobCardElementId(job.hash)}
                className={cn(
                  "flex flex-col rounded-xl transition-[border-color,box-shadow,background-color] duration-300",
                  highlightedJobHash === String(job.hash) && "job-card-highlight",
                  job.is_pinned && "border-amber/20 bg-amber/[0.02]",
                  // beta.26 / User-Feedback: Freelance-/Selbstaendigen-
                  // Projekte sichtbar von Festanstellungen unterscheiden.
                  // Pinned hat Vorrang (amber); ansonsten lila Hauch fuer
                  // employment_type=freelance.
                  !job.is_pinned && job.employment_type === "freelance" && "border-violet-400/25 bg-violet-400/[0.02]"
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
                      <Badge tone={ANSTELLUNGSFORM_TON[job.employment_type] || "neutral"}>
                        {ANSTELLUNGSFORM_TEXT[job.employment_type] || job.employment_type}
                      </Badge>
                    ) : null}
                    {/* #1023: der UMFANG als eigenes Kennzeichen neben der
                        Anstellungsform. Der Melder: "Dann sehe ich in der
                        Liste sofort, was mich erwartet, ohne die Anzeige zu
                        oeffnen." `unbekannt` bekommt bewusst KEIN Abzeichen
                        — ein Etikett "unbekannt" an 993 von 1.110 Stellen
                        waere Rauschen, und die Luecke steht ohnehin im
                        Datenguete-Befund. */}
                    {job.arbeitsumfang && job.arbeitsumfang !== "unbekannt" ? (
                      <Badge tone={job.arbeitsumfang === "teilzeit" ? "amber" : "neutral"}>
                        {UMFANG_TEXT[job.arbeitsumfang] || job.arbeitsumfang}
                      </Badge>
                    ) : null}
                    {job.befristet ? <Badge tone="neutral">Befristet</Badge> : null}
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
                      <Badge tone="amber">{descriptionAttentionLabel(job)}</Badge>
                    ) : null}
                    {/* #989: was an dieser Stelle NICHT geprueft wurde.
                        "Ungeprueft" ist nicht dasselbe wie "erfuellt
                        nicht" — im Score sehen beide gleich aus, und
                        genau daran stand die Liste auf dem Kopf. Die
                        fehlende Beschreibung hat schon ihr eigenes
                        Etikett; hier stehen die uebrigen Dimensionen. */}
                    {(() => {
                      const marke = datenguetMarke(job);
                      const rest = (marke?.ungeprueft || []).filter((d) => d !== "beschreibung");
                      if (!rest.length) return null;
                      // `neutral` ist der einzige gedeckte Ton dafuer —
                      // ein erfundener Ton erzeugt in Tailwind keine
                      // Regel UND keinen Fehler (G24/#964). Der Titel
                      // gehoert an ein Element, das ihn auch annimmt:
                      // Badge reicht `title` nicht durch.
                      return (
                        <span title={marke.text}>
                          <Badge tone="neutral">{`Ungeprüft: ${rest.length}`}</Badge>
                        </span>
                      );
                    })()}
                    {/* v1.7.68 (#968) AK 3: warum diese Zeile unten
                        steht. Eine Stelle, die ohne erkennbaren Grund
                        hinten liegt, sieht aus wie ein Fehler. Der Text
                        kommt vom Server, nicht aus einer zweiten
                        Fassung der Regel im JavaScript. */}
                    {job.muss_tor ? (
                      <span title={job.muss_tor.erklaerung || job.muss_tor.text}>
                        <Badge tone="neutral">Kein Pflichttreffer</Badge>
                      </span>
                    ) : null}
                    {/* #1007: das Urteil der Detailanalyse — getrennt vom
                        Score, weil beide Verschiedenes sagen. Ohne
                        gelesene Analyse steht hier NICHTS: "noch nicht
                        gelesen" ist kein Urteil (#989). */}
                    {/* #948 (AK 4/5/7): drei Zustaende, und ein Klick
                        fuehrt zum Ergebnis statt nur zu einem Tooltip.
                        "Ungeprueft" traegt bewusst KEIN Abzeichen — die
                        Abwesenheit ist die ehrliche Anzeige fuer "noch
                        nicht angesehen", und wer gezielt danach sucht,
                        hat dafuer den Pruefstand-Filter. */}
                    {job.pruefstand && job.pruefstand.art !== "ungeprueft" ? (
                      <button
                        type="button"
                        className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-sky/50"
                        title={pruefstandTitel(job)}
                        onClick={(event) => { event.stopPropagation(); showFitAnalysis(job); }}
                      >
                        <Badge
                          tone={
                            job.pruefstand.art !== "beurteilt" ? "neutral"
                              : job.analyse?.urteil === "EMPFOHLEN" ? "success"
                                : job.analyse?.urteil === "BEDINGT" ? "amber"
                                : job.analyse?.urteil === "NICHT_EMPFOHLEN" ? "danger"
                                : "neutral"
                          }
                        >
                          {`${
                            job.pruefstand.art === "beurteilt"
                              ? (ANALYSE_ETIKETT[job.analyse?.urteil] || "Beurteilt")
                              : "Angesehen"
                          }${job.pruefstand.ueberholt ? " ⚠ überholt" : ""}`}
                        </Badge>
                      </button>
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
                        {Number(job?.score || 0) > 0
                          ? "Beschreibung fehlt oder ist sehr kurz. Prüfe die Originalanzeige, bevor du den Score zu ernst nimmst."
                          : "Score 0 ist kein Urteil — ohne Beschreibung wurde diese Stelle nicht bewertet. Erst Beschreibung nachladen, dann entscheiden."}
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
                  <Button onClick={() => openApplicationDialog(job)}>
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
                    <>
                      {/* #1010: Herkunft und Zeitpunkt an der Zeile. Ein
                          eigenes Urteil sieht man anders an als eines der
                          Automatik — und ohne Zeitpunkt findet man den
                          Verklicker nicht wieder. */}
                      <span className="inline-flex items-center gap-2 text-[12px] text-muted/60">
                        <span className={cn(
                          "rounded-md px-1.5 py-0.5",
                          job.herkunft === "automatik"
                            ? "bg-amber/10 text-amber/80"
                            : job.herkunft === "ich"
                              ? "bg-white/[0.06] text-muted/70"
                              : "bg-white/[0.03] text-muted/40"
                        )}>
                          {HERKUNFT_ETIKETT[job.herkunft] || HERKUNFT_ETIKETT.unbekannt}
                        </span>
                        {job.dismissed_at
                          ? formatDateTime(job.dismissed_at)
                          : "Zeitpunkt unbekannt"}
                      </span>
                      <Button variant="ghost" onClick={() => changeJobState("/api/jobs/restore", { hash: job.hash }, "Stelle wiederhergestellt")}>
                        <RotateCcw size={15} />
                        Wiederherstellen
                      </Button>
                    </>
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
                  <Button variant="secondary" onClick={() => startJobsuche()}>
                    <Search size={15} />
                    Jobsuche starten
                  </Button>
                </div>
              ) : null}
            />
          )}

          {/* #941: Eingeklappte Rueckhol-Liste. Die Automatik sortiert
              ohne Rueckfrage aus — das ist nur ertraeglich, solange
              sichtbar bleibt, WAS sie entschieden hat. Standardmaessig
              zu, damit sie den Blick auf die aktiven Stellen nicht
              stoert. */}
          {filters.view === "active" && autoDismissed.length > 0 && (
            <Card className="glass-card-soft rounded-xl">
              <button
                type="button"
                onClick={() => setAutoOpen((o) => !o)}
                className="flex w-full items-center justify-between gap-3 text-left"
              >
                <span className="flex items-center gap-2 text-sm font-medium text-ink">
                  <EyeOff size={15} className="text-muted" />
                  Automatisch aussortiert
                  <Badge tone="subtle">{autoDismissed.length}</Badge>
                </span>
                <span className="text-xs text-muted">
                  {autoOpen ? "Einklappen" : "Anzeigen"}
                </span>
              </button>

              {autoOpen && (
                <div className="mt-4 grid gap-3">
                  <p className="text-xs text-muted">
                    Diese Stellen hat PBP als Wiedergaenger erkannt und ohne
                    Rueckfrage aussortiert. Holst du eine zurueck, wird das
                    protokolliert — haeuft es sich, steht die Regel zu scharf.
                  </p>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted">Anzahl</span>
                    {[20, 40, 60].map((n) => (
                      <Button
                        key={n}
                        variant={autoLimit === n ? "secondary" : "ghost"}
                        onClick={() => {
                          setAutoLimit(n);
                          localStorage.setItem("pbp-auto-dismiss-limit", String(n));
                        }}
                      >
                        {n}
                      </Button>
                    ))}
                  </div>

                  {autoDismissed.map((job) => (
                    <div
                      key={job.hash}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm text-ink">{job.title}</p>
                        <p className="truncate text-xs text-muted">
                          {job.company}
                          {job.dismiss_note ? ` · ${job.dismiss_note}` : ""}
                        </p>
                      </div>
                      <Button variant="ghost" onClick={() => holeZurueck(job)}>
                        <RotateCcw size={15} />
                        Zurueckholen
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      </div>

      <Modal
        open={fitDialog.open}
        title={`Fit-Analyse \u2014 ${fitDialog.title}`}
        onClose={() => setFitDialog({ open: false, title: "", hash: "", analysis: null })}
        /* #948 (AK 1/2): der Einstieg zur vertieften Analyse stand am
           ENDE eines langen Dialogs — man musste an Score, Faktoren,
           Treffern, Risiken und Recherche vorbeiscrollen, um den
           teuersten Schritt zu finden. Die Fusszeile des Modals liegt
           ausserhalb des Scroll-Containers: sie ist ohne Scrollen da,
           bleibt beim Scrollen stehen und verdeckt nichts, weil der
           Inhaltsbereich ihre Hoehe schon einrechnet. Kein zweiter
           Mechanismus noetig — der richtige war bereits gebaut. */
        footer={(
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button
              variant="primary"
              onClick={() => {
                const hash = fitDialog.hash || "";
                const prompt = `Bewerte die Stelle "${fitDialog.title}" (Hash: ${hash}) detailliert fuer mich. Rufe die Stellenbeschreibung ab, vergleiche sie mit meinem Profil und gib mir eine ehrliche Einschaetzung: Staerken, Schwaechen, Risiken, und ob sich eine Bewerbung lohnt.`;
                copyPrompt(prompt);
              }}
            >
              <Search size={15} />
              Detailbewertung durch Claude anfordern
            </Button>
            <Button variant="secondary" onClick={() => setFitDialog({ open: false, title: "", hash: "", analysis: null })}>Schliessen</Button>
          </div>
        )}
      >
        <div className="grid gap-4">
          {/* #948 (AK 7): wer in der Liste auf "Beurteilt" klickt, landet
              hier — also muss das Urteil hier auch stehen, und zwar oben.
              Es kommt aus der Datenbank, nicht aus dieser Antwort: der
              Score misst die Suchbegriffe, das Urteil ist gelesen
              (#1003). */}
          {fitDialog.analysis?.analyse?.urteil ? (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">Gelesenes Urteil</p>
                <Badge
                  tone={
                    fitDialog.analysis.analyse.urteil === "EMPFOHLEN" ? "success"
                      : fitDialog.analysis.analyse.urteil === "BEDINGT" ? "amber"
                        : fitDialog.analysis.analyse.urteil === "NICHT_EMPFOHLEN" ? "danger"
                          : "neutral"
                  }
                >
                  {ANALYSE_ETIKETT[fitDialog.analysis.analyse.urteil] || fitDialog.analysis.analyse.urteil}
                </Badge>
                {fitDialog.analysis.analyse.am ? (
                  <span className="text-xs text-muted/60">vom {String(fitDialog.analysis.analyse.am).slice(0, 10)}</span>
                ) : null}
              </div>
              {fitDialog.analysis.analyse.begruendung ? (
                <p className="mt-2 text-sm text-muted/80 whitespace-pre-line">{fitDialog.analysis.analyse.begruendung}</p>
              ) : null}
              {fitDialog.analysis.pruefstand?.ueberholt ? (
                <p className="mt-2 text-xs text-amber">
                  {`Seit dem Urteil hat sich die Grundlage geändert${
                    fitDialog.analysis.pruefstand.ueberholt.grund?.includes("score")
                      ? ` — Score ${fitDialog.analysis.pruefstand.ueberholt.score_damals} → ${fitDialog.analysis.pruefstand.ueberholt.score_jetzt}`
                      : ""
                  }${
                    fitDialog.analysis.pruefstand.ueberholt.grund?.includes("profil")
                      ? " — das Profil wurde seither bearbeitet"
                      : ""
                  }.`}
                </p>
              ) : null}
            </Card>
          ) : null}
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted">Gesamtscore</p>
            <p className="mt-3 text-4xl font-semibold text-ink">{fitDialog.analysis?.total_score ?? 0}</p>
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
          {/* #948 (AK 1/2): der Knopf "Detailbewertung durch Claude
              anfordern" stand hier — hinter dem ganzen Dialog. Er sitzt
              jetzt in der Fusszeile, also ohne Scrollen erreichbar. Eine
              zweite Kopie an dieser Stelle waere derselbe Fehler wie in
              #979: dieselbe Handlung an zwei Orten. */}

          {/* #1009: Handlung direkt im Dialog. Wer die Analyse gelesen
              hat, hat GENAU JETZT sein Urteil gebildet — bisher musste er
              dafuer den Dialog schliessen und die Karte wiederfinden. Der
              teuerste Schritt endete in einer Sackgasse.
              Aufgerufen werden dieselben Funktionen wie auf der Karte
              (openDismissDialog / openApplicationDialog / togglePin),
              nicht eine zweite Fassung. */}
          {fitDialog.job && (
            <div className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-4">
              <Button
                variant="secondary"
                onClick={() => {
                  const stelle = fitDialog.job;
                  setFitDialog({ open: false, title: "", analysis: null });
                  openDismissDialog(stelle);
                }}
              >
                <Ban size={15} />
                Passt nicht
              </Button>
              <Button
                onClick={() => {
                  const stelle = fitDialog.job;
                  setFitDialog({ open: false, title: "", analysis: null });
                  openApplicationDialog(stelle);
                }}
              >
                <Plus size={15} />
                Bewerbung erfassen
              </Button>
              <Button
                variant="ghost"
                onClick={() => togglePin(fitDialog.job)}
              >
                <Pin size={15} />
                {fitDialog.job.is_pinned ? "Pin entfernen" : "Anpinnen"}
              </Button>
            </div>
          )}
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
          {/* #981 (D43): die Einstiegsfrage aus #170 statt einer
              Status-Auswahl. Hier stand "Entwurf" — ein Wert, den
              VALID_STATUSES nicht kennt; die so erzeugte Bewerbung war
              danach fuer die Statistik und die Status-Journey unsichtbar.
              G20/#896 hatte genau diesen Wert aus STATUS_OPTIONS entfernt,
              die Inline-Liste hier sah der Guard nicht. */}
          <Field label="Wo stehst du?">
            <SelectInput value={applicationDialog.draft.status} onChange={(event) => setApplicationDialog((current) => ({ ...current, draft: { ...current.draft, status: event.target.value, applied_at: event.target.value === "beworben" ? current.draft.applied_at : "" } }))}>
              <option value="in_vorbereitung">Ich will mich bewerben</option>
              <option value="beworben">Ich habe mich bereits beworben</option>
            </SelectInput>
          </Field>
          {applicationDialog.draft.status === "beworben" ? (
            <Field label="Beworben am">
              <TextInput type="date" value={applicationDialog.draft.applied_at || ""} onChange={(event) => setApplicationDialog((current) => ({ ...current, draft: { ...current.draft, applied_at: event.target.value } }))} />
            </Field>
          ) : null}
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
                {jobNeedsDescriptionAttention(detailDialog.job) ? <Badge tone="amber">{descriptionAttentionLabel(detailDialog.job)}</Badge> : null}
                {detailDialog.job.is_pinned ? <Badge tone="amber"><Pin size={12} className="inline" /> Angepinnt</Badge> : null}
              </div>
              {detailDialog.job.salary_min ? (
                <p className="text-sm text-teal font-medium">
                  Gehalt: {formatCurrency(detailDialog.job.salary_min)} - {formatCurrency(detailDialog.job.salary_max)}
                  {detailDialog.job.salary_type ? ` (${detailDialog.job.salary_type})` : ""}
                  {detailDialog.job.salary_estimated ? " (geschaetzt)" : ""}
                </p>
              ) : null}
              {/* #765: nie ein stiller toter Link und nie ein leeres Feld —
                  der Weg zur Original-Anzeige ist sichtbar oder erklaert. */}
              {(() => {
                const link = jobLinkInfo(detailDialog.job);
                if (link.art === "keine") {
                  return (
                    <p className="text-sm text-amber/80">
                      Kein Link zur Original-Anzeige hinterlegt — Bewerbung ist so nicht moeglich.
                      Die Stelle auf dem Portal suchen und die URL per <code>stelle_bearbeiten</code> nachtragen.
                    </p>
                  );
                }
                return (
                  <div>
                    <a href={link.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm text-sky hover:underline">
                      <ExternalLink size={14} /> {link.label}
                    </a>
                    {link.hinweis ? (
                      <p className="mt-1 text-xs text-amber/80">{link.hinweis}</p>
                    ) : null}
                  </div>
                );
              })()}
              {jobNeedsDescriptionAttention(detailDialog.job) ? (
                <Card className="rounded-xl border-amber/20 bg-amber/10 shadow-none">
                  <p className="text-sm font-semibold text-ink">Beschreibung zuerst nachziehen</p>
                  <p className="mt-1 text-sm text-muted">
                    Für diese Stelle fehlt eine belastbare Beschreibung. Der Score ist deshalb nur eine Vororientierung und kein sauberes Urteil.
                  </p>
                  {/* v1.7.0-beta.44 (#622): Per-Klick-Refetch via Backend (1 HTTP-GET) */}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={refetchBusy}
                      onClick={async () => {
                        if (!detailDialog.job?.hash) return;
                        setRefetchBusy(true);
                        try {
                          const res = await postJson(
                            `/api/jobs/${detailDialog.job.hash}/refetch-description`,
                            {}
                          );
                          pushToast(`Beschreibung nachgeladen (${res.chars} Zeichen)`, "success");
                          // Dialog-Job mit neuem Stand updaten + im Hintergrund Liste reloaden
                          const updated = await api(`/api/jobs/${detailDialog.job.hash}`);
                          if (updated) {
                            setDetailDialog((d) => ({ ...d, job: updated }));
                          }
                          await loadPage({ silent: true });
                        } catch (err) {
                          pushToast(`Nachladen fehlgeschlagen: ${err.message}`, "danger");
                        } finally {
                          setRefetchBusy(false);
                        }
                      }}
                    >
                      <Download size={14} />
                      {refetchBusy ? "Lade..." : "Beschreibung jetzt nachladen"}
                    </Button>
                    {detailDialog.job.url ? (
                      <a
                        href={detailDialog.job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-amber/30 px-3 py-1.5 text-xs text-amber hover:bg-amber/10"
                      >
                        <ExternalLink size={12} /> Im Browser oeffnen + manuell kopieren
                      </a>
                    ) : null}
                  </div>
                  <p className="mt-2 text-[11px] text-muted/60">
                    Tipp: Du kannst auch Claude bitten — <code className="text-amber">stellenbeschreibung_nachladen</code> als Tool. Massen-Nachzug laeuft sowieso im Hintergrund (max 8 pro Auto-Run, mit Backoff).
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
                  // #1009: dritte Fundstelle desselben Entwurfs — sie gab
                  // es schon vor diesem Issue, gefunden hat sie der neue
                  // Guard. Auch dieser Weg geht jetzt durchs Nadeloehr.
                  const stelle = detailDialog.job;
                  setDetailDialog({ open: false, job: null, editing: false });
                  openApplicationDialog(stelle);
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

