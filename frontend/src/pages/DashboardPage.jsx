import {
  ArrowRight,
  Calendar,
  ClipboardList,
  Mail,
  MessageSquareReply,
  Search,
  Settings2,
  Send,
  Upload,
  RefreshCw,
  X,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, optionalApi, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { berlinDayDiff, berlinTimeOfDay } from "@/lib/relativeDate";
import { readinessWirdVomBlockGetragen, zeigeProfilKpi } from "@/lib/dashboardRegeln";
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
  buildMailto,
  buildReplyMailto,
  extractEmailAddress,
  formatCurrency,
  formatDate,
  readinessTone,
} from "@/utils";
import AdaptiveHintBanner from "@/components/AdaptiveHintBanner";
import OnboardingHintBanner from "@/components/OnboardingHintBanner";
import OffenBlock from "@/components/OffenBlock";
import SchnellzugriffKarten from "@/components/SchnellzugriffKarten";
import EmailUploadButton from "@/components/EmailUploadButton";
import DashboardBereich from "@/components/DashboardBereich";
import DashboardAnpassen from "@/components/DashboardAnpassen";

function positiveSalary(value) {
  if (value === null || typeof value === "undefined") return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return numeric;
}

function buildAnnualSalaryMetrics(jobs = []) {
  // v1.6.2 Bugfix: vorher wurde bei "≥1 echte Gehaltsangabe vorhanden" der
  // gesamte Pool an geschätzten Gehältern verworfen. Bei 2 echten + 272
  // geschätzten Stellen fielen also 272 raus — die Karte zeigte nur 2
  // Datenpunkte. Jetzt: alle Zeilen kombinieren; allEstimated bleibt true
  // nur wenn KEINE echten existieren (→ "(geschätzt)"-Label).
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

  const rows = [...realRows, ...estimatedRows];
  const allEstimated = realRows.length === 0 && estimatedRows.length > 0;

  // beta.26: Plausibilitaets-Filter fuer Jahresgehaelter — Tagessaetze mit
  // faelschlich salary_type=jaehrlich raus. (v1.6.2: zur Konsistenz mit JobsPage)
  const ANNUAL_MIN_PLAUSIBLE = 20000;
  const annualRows = rows.filter(
    (row) => row.salaryType === "jaehrlich" && row.min >= ANNUAL_MIN_PLAUSIBLE
  );
  if (!annualRows.length) {
    return {
      jobsWithSalary: rows.length,
      annualBasisCount: 0,
      averageMin: null,
      averageMax: null,
      bandMin: null,
      bandMax: null,
      allEstimated,
    };
  }

  const mins = annualRows.map((row) => row.min);
  const maxs = annualRows.map((row) => row.max);
  return {
    jobsWithSalary: rows.length,
    annualBasisCount: annualRows.length,
    averageMin: Math.round(mins.reduce((sum, value) => sum + value, 0) / mins.length),
    averageMax: Math.round(maxs.reduce((sum, value) => sum + value, 0) / maxs.length),
    // v1.6.2: echte Min/Max-Spanne fuer "Bandbreite"-Kachel — gleiche
    // Semantik wie in JobsPage, damit beide Tabs konsistent sind.
    bandMin: Math.min(...mins),
    bandMax: Math.max(...maxs),
    allEstimated,
  };
}

export default function DashboardPage() {
  const { chrome, reloadKey, refreshChrome, navigateTo, copyPrompt, openHelp, pushToast, startJobsuche } = useApp();
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
  const [scraperHealth, setScraperHealth] = useState([]);
  // Wie viele Zeilen der Block "Offen" zeigt — die Readiness-Karte
  // darunter darf nicht wiederholen, was dort schon steht.
  const [offenAnzahl, setOffenAnzahl] = useState(0);
  // v1.7.35 (#985): Reihenfolge, Sichtbarkeit und Einklapp-Zustand der
  // Bloecke. Liegt beim Nutzer (profile_settings), nicht im Browser —
  // die Einstellung soll den Rechner ueberleben, nicht die Sitzung.
  const [bereiche, setBereiche] = useState([]);
  const [bereichsKatalog, setBereichsKatalog] = useState([]);
  const [anpassenOffen, setAnpassenOffen] = useState(false);
  const [publicHints, setPublicHints] = useState([]);
  const [metricPerspective, setMetricPerspective] = useState(() => Math.floor(Math.random() * 5));
  const [dismissedHints, setDismissedHints] = useState(() => {
    try { return JSON.parse(localStorage.getItem("pbp_dismissed_hints") || "[]"); } catch { return []; }
  });
  // v1.6.5 (#543): Schnellzugriff-Hilfstext minimierbar, Status persistent.
  // Default offen — User soll beim ersten Mal sehen was die Karten machen.
  const [quickAccessHelpOpen, setQuickAccessHelpOpen] = useState(() => {
    try {
      const saved = localStorage.getItem("pbp_dashboard_quickhelp_open");
      return saved === null ? true : saved === "1";
    } catch {
      return true;
    }
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

  // v1.7.35 (#985): MUSS vor dem Lade-Ausstieg direkt darunter stehen.
  // Ein Hook hinter einem `return` laeuft im ersten Durchgang nicht und
  // im zweiten schon — React bricht das mit Fehler 300 ab und der
  // ErrorBoundary zeigt die ganze Seite als kaputt. Genau so ist es
  // passiert: der Effekt stand 160 Zeilen weiter unten, direkt neben
  // den Funktionen, zu denen er inhaltlich gehoert.
  useEffect(() => {
    let aktiv = true;
    fetch("/api/dashboard/bereiche")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!aktiv || !d) return;
        setBereichsKatalog(d.katalog || []);
        setBereiche(d.bereiche || []);
      })
      .catch(() => {});
    return () => { aktiv = false; };
  }, []);

  if (loading && chrome.status?.has_profile) {
    return <LoadingPanel label="Dashboard wird vorbereitet..." />;
  }

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
  // v1.6.2: Bandbreite = echte Min/Max-Spanne (gleiche Semantik wie JobsPage).
  const bandMin = Number(salaryMetrics.bandMin);
  const bandMax = Number(salaryMetrics.bandMax);
  const hasBandMin = Number.isFinite(bandMin);
  const hasBandMax = Number.isFinite(bandMax);
  const fmtNum = (n) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 }).format(Math.round(n));
  const salaryBandText = hasBandMin && hasBandMax
    ? `${fmtNum(bandMin)} – ${fmtNum(bandMax)} EUR`
    : hasBandMin
      ? formatCurrency(bandMin)
      : hasBandMax
        ? formatCurrency(bandMax)
        : "Keine Angabe";
  const lastSearchAt = chrome.searchStatus?.last_search || "";
  const searchDaysAgo = Number(chrome.searchStatus?.days_ago);
  const hasSearchDays = Number.isFinite(searchDaysAgo);
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
      // #461: direkt Dashboard-Endpoint, kein Claude-Umweg
      action: () => startJobsuche(),
    });
  }

  // #982: die Zaehl-Empfehlung "Interview vorbereiten" entfaellt.
  // Sie entstand aus der ANZAHL der Bewerbungen im Interview-Status
  // und kannte den konkreten Termin drei Bloecke tiefer nicht. Die
  // Vorbereitungszeile kommt jetzt aus dem TERMIN und steht mit
  // Datum im Block "Offen" (services/aufgaben_sicht.py).

  // #976 Befund 3: faellige Nachfassungen stehen im Block "Offen",
  // mit Titel, Datum und Herkunft. Sie hier zusaetzlich als Zahl zu
  // nennen war die dritte Zaehlweise derselben Lage.

  if (data.zombies.length > 0) {
    todoItems.push({
      id: "zombies",
      title: "Lange keine Antwort bekommen",
      description: `${data.zombies.length} Bewerbung(en) warten seit ueber 60 Tagen auf Rueckmeldung.`,
      tone: "amber",
      actionLabel: "Bewerbungen",
      // #485: Filter auf Zombies (ueber 60 Tage ohne Antwort)
      action: () => navigateTo("bewerbungen", { filter: "zombies" }),
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
  // #683: ueberfaellige offene Aufgaben fuer die prominente Dashboard-Warnung
  // #976: die ueberfaelligen Aufgaben kommen jetzt mit allem anderen
  // Offenen aus /api/dashboard/offen (OffenBlock), nicht mehr aus der
  // Workspace-Zusammenfassung als eigene Warnkarte.
  const workspaceTodos = Array.isArray(chrome.workspace?.todos) ? chrome.workspace.todos : [];
  const profileCompleteness = Number(chrome.workspace?.profile?.completeness || 0);
  // #974: Onboarding-Fortschritt gehoert auf die Profilseite und in die
  // Onboarding-Stufen. Bei 100 % und Stufe `nachfassen` stand hier bisher
  // dauerhaft "100% Profil vollstaendig" neben einer Aufgabe, die mit dem
  // Profil nichts zu tun hat. Die Entscheidung liegt in dashboardRegeln.js,
  // damit die naechste Ansicht sie nicht erneut selbst trifft.
  const zeigeVollstaendigkeit = zeigeProfilKpi(
    chrome.workspace?.readiness?.stage,
    profileCompleteness
  );
  const jobsWithoutDescription = Number(chrome.workspace?.jobs?.ohne_beschreibung || 0);

  async function bereicheSpeichern(neu) {
    setBereiche(neu);
    try {
      await fetch("/api/dashboard/bereiche", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bereiche: neu }),
      });
    } catch {
      pushToast?.("Anordnung konnte nicht gespeichert werden.", "danger");
    }
  }

  async function bereicheZuruecksetzen() {
    try {
      const r = await fetch("/api/dashboard/bereiche", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zuruecksetzen: true }),
      });
      const d = await r.json();
      setBereiche(d.bereiche || []);
    } catch {
      pushToast?.("Zuruecksetzen fehlgeschlagen.", "danger");
    }
  }

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
                {/* G18 (#749): Erster-Start-Verbindungscheck — der frisch
                    installierte User sieht SOFORT, ob Claude Desktop mit PBP
                    verbunden ist (haeufigster Support-Stolperstein), statt
                    es erst am kleinen Sidebar-Badge zu entdecken. */}
                {(() => {
                  const st = chrome?.status?.mcp_connection?.status;
                  if (st === "connected") {
                    return (
                      <div className="flex items-center gap-2 rounded-lg border border-teal/25 bg-teal/[0.06] px-3 py-2 text-[12px] text-teal"
                        title="PBP hat in den letzten 90 Sekunden ein Lebenszeichen von Claude Desktop empfangen.">
                        <span className="h-2 w-2 rounded-full bg-teal shrink-0" />
                        Claude Desktop ist verbunden — du kannst direkt loslegen.
                      </div>
                    );
                  }
                  return (
                    <div className="rounded-lg border border-amber/30 bg-amber/[0.06] px-3 py-2 text-[12px]">
                      <p className="flex items-center gap-2 font-medium text-amber">
                        <span className="h-2 w-2 rounded-full bg-amber shrink-0" />
                        {st === "unknown"
                          ? "Verbindung zu Claude Desktop wird geprueft..."
                          : "Claude Desktop ist noch nicht mit PBP verbunden."}
                      </p>
                      <ol className="mt-1 ml-4 list-decimal space-y-0.5 text-muted/80">
                        <li>
                          Claude Desktop <strong>komplett beenden</strong>: Rechtsklick auf das
                          Claude-Symbol unten rechts in der Taskleiste → „Beenden"
                          (Fenster schliessen reicht nicht).
                        </li>
                        <li>Claude Desktop neu starten und einen Moment warten.</li>
                        <li>
                          Diese Anzeige wird von selbst gruen — oder{" "}
                          <button type="button" className="underline hover:text-ink"
                            onClick={() => refreshChrome()}>
                            jetzt pruefen
                          </button>.
                        </li>
                      </ol>
                    </div>
                  );
                })()}

                {/* G17 (#744): CV-Upload ist der schnellste Einstieg —
                    gleichwertig prominent statt versteckter Ghost-Button */}
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => navigateTo("profil", { composer: "document" })}>
                    <Upload size={15} />
                    Lebenslauf hochladen — Profil entsteht automatisch
                  </Button>
                  <Button variant="ghost" onClick={() => navigateTo("profil")}>
                    Ohne Unterlagen starten (Gespräch, ca. 10 Min.)
                    <ArrowRight size={15} />
                  </Button>
                </div>
                <p className="max-w-2xl text-xs text-muted/70">
                  In beiden Fällen gilt: Profil prüfen, Suchbegriffe bestätigen —
                  und die erste Stellensuche startet direkt im Anschluss.
                </p>
              </div>

              <div className="grid gap-4">
                {[
                  {
                    title: "Schritt 1 — Profil",
                    text: "Lebenslauf hochladen oder einfach erzählen — Claude baut daraus dein Profil.",
                  },
                  {
                    title: "Schritt 2 — Stellen finden",
                    text: "Suchbegriffe werden vorgeschlagen, die erste Suche startet direkt — du siehst sofort passende Stellen mit Bewertung.",
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

  // v1.7.35 (#985): jeder Block einmal benannt, damit die Reihenfolge
  // aus den Nutzereinstellungen kommen kann statt aus dem Quelltext.
  const bereichsInhalt = {
    impuls: (
      <>
        {/* Heute fuer dich (Impulse) */}
        {impulse?.enabled && impulse?.impulse?.text && (
          <Card className="rounded-2xl border-amber/30 bg-amber/10">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.15em] text-amber/60">
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
      </>
    ),
    offen: (
      <>
        <OffenBlock
          navigateTo={navigateTo}
          refreshChrome={refreshChrome}
          onPrompt={(prompt) => copyPrompt?.(prompt)}
          onAnzahl={setOffenAnzahl}
        />
      </>
    ),
    naechster_schritt: (
      <>
        {/* Im Fluss (Readiness Card).

            v1.7.35: Sie entfaellt, wenn der Block "Offen" ihre Aussage
            schon traegt. Nutzerhinweis vom 07.09.2026 — der Block
            listete zwei faellige Nachfassungen mit Firma und Datum,
            und direkt darunter stand "Es gibt ueberfaellige
            Nachfassaktionen". #976 verlangte, keine ZAEHLUNGEN zu
            wiederholen; das war zu eng gelesen. Eine Wiederholung
            ohne Zahl ist immer noch eine. */}
        {readinessWirdVomBlockGetragen(workspaceReadiness.stage, offenAnzahl) ? null : (
        <Card className="rounded-2xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={readinessTone(workspaceReadiness.tone)}>{workspaceReadiness.label || "Nächster Schritt"}</Badge>
                {zeigeVollstaendigkeit ? (
                  <span className="text-xs text-muted/50">{profileCompleteness}% Profil vollständig</span>
                ) : null}
                {jobsWithoutDescription > 0 ? (
                  <span className="text-xs text-amber">{jobsWithoutDescription} Treffer mit unsicherem Score</span>
                ) : null}
              </div>
              {/* #976 Befund 1 / #984: vier Etiketten fuer eine Aussage
                  (Badge, Kicker, Headline, Beschreibung). Der Kicker
                  erklaerte die Karte, das Badge wiederholte das Thema,
                  die Beschreibung sagte die Headline in anderen Worten.
                  Uebrig bleibt, was Information traegt: die Aussage und
                  die Aktion daneben. */}
              <h2 className="mt-3 text-base font-semibold text-ink">{workspaceReadiness.headline || "Weiter im Prozess"}</h2>
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
                    {/* #976 Befund 2: die Nummer war ein festes Etikett
                        je Aufgabentyp, kein Rang in der gezeigten Liste
                        — fehlte der Typ `jobsuche`, begann die Liste
                        sichtbar bei "Prioritaet 2" und der Nutzer suchte
                        nach einer 1, die es nicht gab. Die Reihenfolge
                        der Karten sagt bereits, was zuerst kommt. */}
                    <Badge tone={todo.tone}>Empfehlung</Badge>
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
        )}
      </>
    ),
    kennzahlen: (
      <>
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
            note={salaryCount > 0 ? `Auf Basis von ${salaryCount} ${salaryCount === 1 ? "Stelle" : "Stellen"} mit Jahresgehalt${salaryCount < 3 ? " — wenig Datenbasis" : ""}` : "Noch keine Gehaltsdaten"}
            tone="success"
          />
          <MetricCard
            label={`Gehaltsbandbreite${salaryEstimated ? " (geschätzt)" : ""}`}
            value={salaryBandText}
            note={salaryCount > 0 ? `Niedrigster bis höchster Wert über ${salaryCount} ${salaryCount === 1 ? "Stelle" : "Stellen"}` : "Echte Min/Max-Spanne über alle Stellen"}
            tone="success"
          />
        </div>

        {/* #450: Layout auf volle Breite — Schnellimport entfernt */}
        {/* v1.7.33: `grid-cols-1` statt nur `grid`. Ohne explizite Spalte
            bekommt ein Grid-Item `min-width: auto` und kann NICHT unter
            seine Mindestbreite schrumpfen — die drei Karten hier waren
            dadurch 1035 px breit in einem 961 px breiten Container und
            liefen rechts aus dem Bild. Sichtbar wurde das erst am neu
            erzeugten Screenshot; im Browser faellt es kaum auf, weil der
            Ueberhang abgeschnitten wird. `grid-cols-1` ist
            `repeat(1, minmax(0, 1fr))` und erlaubt das Schrumpfen. */}
      </>
    ),
    schnellzugriff: (
      <>
        <SchnellzugriffKarten
          copyPrompt={copyPrompt}
          openHelp={openHelp}
          pushToast={pushToast}
        />
      </>
    ),
    top_stellen: (
      <>
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
                  const color = off ? "bg-red-500/60" : warn ? "bg-amber/80" : ok ? "bg-emerald-400/80" : "bg-zinc-500/40";
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
            {/* v1.7.35 (#985): zwei Spalten und sechs statt drei Treffer.
                Nutzerwunsch: "unten, ggf. sogar mehr Platz einraeumen
                (zwei Spalten)". Der Block hatte die halbe Breite, weil
                rechts daneben die E-Mails standen — die ziehen in den
                Docs-Bereich um. */}
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {(() => {
                const appliedHashes = new Set(
                  (data.applications || []).map((a) => a.job_hash).filter(Boolean)
                );
                const topJobs = data.jobs
                  .filter((j) => !appliedHashes.has(j.hash))
                  .sort((a, b) => (b.score || 0) - (a.score || 0))
                  .slice(0, 6);
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
                  /* v1.7.35 (#985): "Und die Stellensuche starten etwas
                     prominenter." Vorher ein Textlink in einer grauen
                     Zeile — der einzige Weg aus dem leeren Zustand sah
                     aus wie eine Fussnote. */
                  <div className="col-span-full flex flex-col items-center gap-3 py-6">
                    <p className="text-[13px] text-muted/60">
                      Noch keine Stellen gefunden.
                    </p>
                    <Button onClick={() => startJobsuche()}>
                      <Search size={15} />
                      Jobsuche starten
                    </Button>
                  </div>
                );
              })()}
            </div>
          </Card>
      </>
    ),
    import: (
      <>
        {/* #450: Dokument-Import (saubere Version, gleiche Logik wie Docs-Seite) */}
        <DashboardDocumentImport pushToast={pushToast} refreshChrome={refreshChrome} />
      </>
    ),
    recap: (
      <>
        {/* v1.7.0 (#576): Recap-Card — was hat sich seit deinem letzten Besuch getan */}
        <RecapCard pushToast={pushToast} navigateTo={navigateTo} />
      </>
    ),
  };

  return (
    <div id="page-dashboard" className="page active">
      {/* beta.35: h1 sr-only — Top-Bar zeigt Breadcrumb */}
      <h1 className="sr-only">Dashboard</h1>
      {/* v1.7.0-beta.29 (#594 Stufe 4): Adaptive UI-Hints */}
      <OnboardingHintBanner tab="dashboard" />
      <AdaptiveHintBanner page="dashboard" />

      {publicHints.filter((h) => !dismissedHints.includes(h.id)).length > 0 && (
        <div className="mb-4 space-y-2">
          {publicHints.filter((h) => !dismissedHints.includes(h.id)).map((hint) => (
            <div
              key={hint.id}
              className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${
                hint.type === "warning"
                  ? "border-amber/20 bg-amber/5 text-amber"
                  : "border-sky/20 bg-sky/5 text-sky"
              }`}
            >
              <div>
                {hint.title && <span className="font-medium">{hint.title} </span>}
                {hint.text}
                {hint.url ? (
                  <>
                    {" "}
                    <a
                      href={hint.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium underline underline-offset-2 hover:opacity-80"
                    >
                      {hint.url_label || "Mehr erfahren"} →
                    </a>
                  </>
                ) : null}
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

      {/* Bleibt ausserhalb der Bereichs-Mechanik: ein Hinweis, der sich
          selbst ausblendet, sobald Ollama laeuft. */}
      <LocalAiAutoDetectBanner pushToast={pushToast} navigateTo={navigateTo} />

      {anpassenOffen ? (
        <DashboardAnpassen
          katalog={bereichsKatalog}
          bereiche={bereiche}
          onAendern={bereicheSpeichern}
          onZuruecksetzen={bereicheZuruecksetzen}
          onSchliessen={() => setAnpassenOffen(false)}
        />
      ) : (
        <div className="mb-3 flex justify-end">
          {/* #1013: nur noch das Symbol. Ein Meta-Bedienelement, das
              jeden Tag als Textzeile ueber dem Inhalt steht, kostet
              Platz fuer eine Funktion, die man selten braucht. */}
          <button
            type="button"
            onClick={() => setAnpassenOffen(true)}
            aria-label="Dashboard anpassen — Bereiche an- und abschalten, sortieren"
            title="Dashboard anpassen — Bereiche an- und abschalten, sortieren"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/5 bg-white/[0.03] text-muted/45 transition hover:text-sky"
          >
            <Settings2 size={15} />
          </button>
        </div>
      )}

      {/* v1.7.35 (#985): die Bloecke stehen in der Reihenfolge, die der
          Nutzer gewaehlt hat — an- und abschaltbar, einklappbar.
          Nutzerwunsch vom 07.09.2026, dieselbe Bauweise wie der
          Prompt-Katalog aus #979. */}
      <div className="grid grid-cols-1 gap-5">
        {bereiche.filter((b) => b.sichtbar).map((b) => {
          const inhalt = bereichsInhalt[b.id];
          if (!inhalt) return null;
          const meta = bereichsKatalog.find((k) => k.id === b.id) || {};
          return (
            <DashboardBereich
              key={b.id}
              titel={meta.titel || b.id}
              offen={b.offen}
              onUmschalten={() => bereicheSpeichern(
                bereiche.map((x) => (x.id === b.id ? { ...x, offen: !x.offen } : x)))}
            >
              {inhalt}
            </DashboardBereich>
          );
        })}
      </div>

    </div>
  );
}


// v1.7.0 (#576): Recap-Card — zeigt was sich seit dem letzten Besuch getan hat.
// Wenn nichts passiert ist, wird die Card komplett ausgeblendet (auto-hide).
// User kann mit dem [x] auch manuell ausblenden bis morgen (LocalStorage-Flag).
// v1.7.0-beta.24 (#585): Auto-Detect-Banner — wenn Ollama erreichbar ist
// aber PBP-Lokale-KI auf 'off' steht, freundlicher Hinweis mit Aktivieren-CTA.
// Dismiss merkt sich 7 Tage in localStorage.
function LocalAiAutoDetectBanner({ pushToast, navigateTo }) {
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Dismiss-Check
    try {
      const until = localStorage.getItem("pbp_local_ai_banner_dismissed_until");
      if (until && new Date(until) > new Date()) {
        setDismissed(true);
        return;
      }
    } catch {}
    fetch("/api/llm/status")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => setStatus(d))
      .catch(() => {});
  }, []);

  if (dismissed || !status) return null;

  // Trigger-Bedingung: Ollama erreichbar, mind. 1 Modell, aber State=off
  const trigger = status.ollama_available
    && (status.available_models?.length || 0) > 0
    && status.user_state === "off";
  if (!trigger) return null;

  function dismissForWeek() {
    try {
      const d = new Date();
      d.setDate(d.getDate() + 7);
      localStorage.setItem("pbp_local_ai_banner_dismissed_until", d.toISOString());
    } catch {}
    setDismissed(true);
  }

  async function activate() {
    try {
      await postJson("/api/llm/state", { state: "active" });
      pushToast("Lokale KI aktiviert.", "success");
      setDismissed(true);
    } catch (err) {
      pushToast(`Aktivieren fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  return (
    <Card className="rounded-2xl border-sky/30 bg-sky/[0.06]">
      <div className="flex items-start gap-3">
        <div className="text-2xl">🟡</div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-ink mb-1">
            Ollama erkannt — willst du PBP-Lokale-KI aktivieren?
          </p>
          <p className="text-[12px] text-muted/70 mb-3">
            Spart Claude-Tokens fuer Standard-Aufgaben (Doku-Klassifikation,
            Skill-Extraktion, Stellen-Vorfilterung). Daten bleiben lokal.
            Aktuell installiert: <strong className="text-ink">{(status.available_models || []).join(", ")}</strong>
          </p>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={activate}>
              Aktivieren
            </Button>
            <Button size="sm" variant="secondary" onClick={() => navigateTo("einstellungen", { tab: "ai" })}>
              In Einstellungen ansehen
            </Button>
            <button
              type="button"
              onClick={dismissForWeek}
              className="text-[11px] text-muted/60 hover:text-ink underline ml-2"
            >
              Spaeter (7 Tage)
            </button>
          </div>
        </div>
      </div>
    </Card>
  );
}



function RecapCard({ pushToast, navigateTo }) {
  const [recap, setRecap] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      const flag = localStorage.getItem("pbp_recap_dismissed_until");
      if (flag && Number(flag) > Date.now()) return true;
    } catch {}
    return false;
  });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/recap")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data && !cancelled) setRecap(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (dismissed || !recap || !recap.has_anything) return null;

  const blocks = [];
  if (recap.new_jobs > 0) {
    blocks.push({
      icon: Search, color: "text-sky", label: "Neue Stellen",
      value: recap.new_jobs,
      onClick: () => navigateTo?.("stellen"),
    });
  }
  if (recap.new_applications > 0) {
    blocks.push({
      icon: Send, color: "text-teal", label: "Neue Bewerbungen",
      value: recap.new_applications,
      onClick: () => navigateTo?.("bewerbungen"),
    });
  }
  if (recap.new_emails > 0) {
    blocks.push({
      icon: Mail, color: "text-amber", label: "Neue E-Mails",
      value: recap.new_emails,
      onClick: () => navigateTo?.("bewerbungen"),
    });
  }
  if (recap.status_changes > 0) {
    blocks.push({
      icon: MessageSquareReply, color: "text-teal/80", label: "Statuswechsel",
      value: recap.status_changes,
      onClick: () => navigateTo?.("bewerbungen"),
    });
  }
  if (recap.overdue_followups > 0) {
    blocks.push({
      icon: ClipboardList, color: "text-coral", label: "Faellige Follow-ups",
      value: recap.overdue_followups,
      onClick: () => navigateTo?.("bewerbungen"),
    });
  }
  if (recap.upcoming_meetings > 0) {
    blocks.push({
      icon: Calendar, color: "text-sky", label: "Anstehende Termine",
      value: recap.upcoming_meetings,
      onClick: () => navigateTo?.("kalender"),
    });
  }

  return (
    <Card className="rounded-2xl border-sky/15 bg-sky/[0.04]">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Was hat sich getan?</h2>
          <p className="text-[11px] text-muted/60 mt-0.5">
            Aktivitaet seit deinem letzten Besuch
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            // Bis morgen ausblenden (24h)
            try {
              localStorage.setItem(
                "pbp_recap_dismissed_until",
                String(Date.now() + 24 * 60 * 60 * 1000)
              );
            } catch {}
            setDismissed(true);
          }}
          className="text-muted/40 hover:text-ink text-xs"
          title="Bis morgen ausblenden"
        >
          ✕
        </button>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {blocks.map((b, i) => (
          <button
            key={i}
            type="button"
            onClick={b.onClick}
            className="glass-card flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-white/[0.04] transition"
          >
            <b.icon size={16} className={b.color} />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-muted/60">{b.label}</p>
              <p className="text-lg font-semibold text-ink">{b.value}</p>
            </div>
          </button>
        ))}
      </div>
      {recap.top_jobs?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-white/5">
          <p className="text-[11px] text-muted/60 mb-1.5">Top neue Stellen:</p>
          <ul className="space-y-1">
            {recap.top_jobs.slice(0, 3).map((j) => (
              <li key={j.hash} className="text-[12px] text-muted/80">
                <span className="text-teal/70 font-mono mr-1.5">[{j.score}]</span>
                <span className="text-ink/90">{j.title}</span>
                <span className="text-muted/50"> bei {j.company}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
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
          <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.doc,.txt,.csv,.json,.xml,.rtf,.pptx,.xlsx,.odt,.odp,.ods" className="hidden"
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

