import { Calendar, CalendarClock, Check, Download, ExternalLink, FileText, Link2, Mail, MessageSquareReply, Pencil, Plus, Search, Send, Trash2, Upload, Video, Workflow, X } from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useEffectEvent, useRef, useState } from "react";
import { Archive } from "lucide-react";

import { api, apiUrl, deleteRequest, postJson, putJson } from "@/api";
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
import {
  STATUS_OPTIONS,
  cn,
  formatCurrency,
  formatDate,
  formatDateTime,
  statusTone,
  textExcerpt,
} from "@/utils";

const EMPTY_APPLICATION = {
  title: "",
  company: "",
  url: "",
  status: "beworben",
  applied_at: new Date().toISOString().slice(0, 10),
  notes: "",
};
const ARCHIVE_STATUSES = ["abgelehnt", "zurueckgezogen", "abgelaufen"];
const INTERVIEW_STATUSES = ["interview", "zweitgespraech", "interview_abgeschlossen"];

function EmailUploadButton({ pushToast, onImported }) {
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
      const statusInfo = data.detected_status?.status ? ` | Status: ${data.detected_status.status}` : "";
      const meetingInfo = data.meetings?.length ? ` | ${data.meetings.length} Termin(e)` : "";
      const docInfo = data.imported_documents ? ` | ${data.imported_documents} Dokument(e)` : "";
      pushToast(`E-Mail importiert${matchInfo}${statusInfo}${meetingInfo}${docInfo}`, "success");
      onImported?.();
    } catch (err) {
      pushToast(`Upload fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <>
      <input ref={fileRef} type="file" accept=".msg,.eml" className="hidden" onChange={handleUpload} />
      <Button size="sm" variant="ghost" onClick={() => fileRef.current?.click()} disabled={uploading}>
        <Mail size={14} className="mr-1" />
        {uploading ? "Importiere..." : "E-Mail importieren"}
      </Button>
    </>
  );
}

export default function ApplicationsPage() {
  const { chrome, reloadKey, refreshChrome, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [applications, setApplications] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [applicationMeta, setApplicationMeta] = useState({ total: 0, filteredTotal: 0, archivedCount: 0 });
  const [filters, setFilters] = useState({
    query: "",
    status: "",
    fromDate: "",
    toDate: "",
    stellenart: "",
    showArchived: false,
  });
  const [sortMode, setSortMode] = useState("neueste"); // neueste | status | firma
  const [createDialog, setCreateDialog] = useState({ open: false, draft: EMPTY_APPLICATION });
  const [timelineDialog, setTimelineDialog] = useState({ open: false, entry: null });
  const [newNoteText, setNewNoteText] = useState("");
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [docSearchQuery, setDocSearchQuery] = useState("");
  const [replyingToId, setReplyingToId] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [documents, setDocuments] = useState([]);
  const [timelineStatusDraft, setTimelineStatusDraft] = useState(EMPTY_APPLICATION.status);
  const [timelineMeetings, setTimelineMeetings] = useState([]);
  const [timelineEmails, setTimelineEmails] = useState([]);

  const deferredQuery = useDeferredValue(filters.query);
  const includeArchivedDataset = filters.showArchived || ARCHIVE_STATUSES.includes(filters.status);

  const loadPage = useEffectEvent(async () => {
    try {
      const [applicationData, followUpData] = await Promise.all([
        api(`/api/applications?limit=500&include_archived=${includeArchivedDataset ? "true" : "false"}`),
        api("/api/follow-ups"),
      ]);
      startTransition(() => {
        setApplications(applicationData?.applications || []);
        setApplicationMeta({
          total: Number(applicationData?.total || 0),
          filteredTotal: Number(applicationData?.filtered_total || 0),
          archivedCount: Number(applicationData?.archived_count || 0),
        });
        setFollowUps(followUpData?.follow_ups || []);
        setLoading(false);
      });
    } catch (error) {
      pushToast(`Bewerbungen konnten nicht geladen werden: ${error.message}`, "danger");
      startTransition(() => setLoading(false));
    }
  });

  useEffect(() => {
    setLoading(true);
    loadPage();
  }, [reloadKey, includeArchivedDataset]);

  async function updateStatus(applicationId, status, options = {}) {
    try {
      await putJson(`/api/applications/${applicationId}/status`, { status });
      setApplications((current) =>
        current.map((app) => (app.id === applicationId ? { ...app, status } : app))
      );
      if (options.reloadTimeline) {
        await reloadTimeline(applicationId);
      }
      await refreshChrome({ quiet: true, forceReload: true });
      pushToast("Status aktualisiert.", "success");
    } catch (error) {
      if (options.rollbackStatus) {
        setTimelineStatusDraft(options.rollbackStatus);
      }
      pushToast(`Status konnte nicht aktualisiert werden: ${error.message}`, "danger");
    }
  }

  async function saveApplication() {
    try {
      await postJson("/api/applications", createDialog.draft);
      setCreateDialog({ open: false, draft: EMPTY_APPLICATION });
      await refreshChrome();
      pushToast("Bewerbung angelegt.", "success");
    } catch (error) {
      pushToast(`Bewerbung konnte nicht angelegt werden: ${error.message}`, "danger");
    }
  }

  async function openTimeline(application) {
    try {
      const [timeline, docs, meetings, emails] = await Promise.all([
        api(`/api/application/${application.id}/timeline`),
        api("/api/documents"),
        api(`/api/applications/${application.id}/meetings`).catch(() => ({ meetings: [] })),
        api(`/api/applications/${application.id}/emails`).catch(() => ({ emails: [] })),
      ]);
      setTimelineDialog({ open: true, entry: timeline });
      setTimelineStatusDraft(timeline?.application?.status || EMPTY_APPLICATION.status);
      setDocuments(docs?.documents || []);
      setTimelineMeetings(meetings?.meetings || []);
      setTimelineEmails(emails?.emails || []);
      setNewNoteText("");
      setEditingNoteId(null);
      setDocSearchQuery("");
    } catch (error) {
      pushToast(`Timeline konnte nicht geladen werden: ${error.message}`, "danger");
    }
  }

  async function reloadTimeline(appId) {
    try {
      const timeline = await api(`/api/application/${appId}/timeline`);
      setTimelineDialog((current) => ({ ...current, entry: timeline }));
      setTimelineStatusDraft(timeline?.application?.status || EMPTY_APPLICATION.status);
    } catch { /* silent */ }
  }

  async function updateTimelineStatus(status) {
    const appId = timelineDialog.entry?.application?.id;
    const currentStatus = timelineDialog.entry?.application?.status || EMPTY_APPLICATION.status;
    if (!appId || !status || status === currentStatus) return;
    setTimelineStatusDraft(status);
    await updateStatus(appId, status, { reloadTimeline: true, rollbackStatus: currentStatus });
  }

  async function addNote(parentEventId = null) {
    const text = parentEventId ? replyText.trim() : newNoteText.trim();
    if (!text) return;
    const appId = timelineDialog.entry?.application?.id;
    if (!appId) return;
    try {
      await postJson(`/api/applications/${appId}/notes`, { text, parent_event_id: parentEventId });
      if (parentEventId) { setReplyText(""); setReplyingToId(null); }
      else setNewNoteText("");
      await reloadTimeline(appId);
      pushToast("Notiz hinzugefügt.", "success");
    } catch (error) {
      pushToast(`Notiz konnte nicht gespeichert werden: ${error.message}`, "danger");
    }
  }

  async function updateNote(eventId) {
    const text = editingNoteText.trim();
    if (!text) return;
    const appId = timelineDialog.entry?.application?.id;
    if (!appId) return;
    try {
      await putJson(`/api/applications/${appId}/notes/${eventId}`, { text });
      setEditingNoteId(null);
      setEditingNoteText("");
      await reloadTimeline(appId);
      pushToast("Notiz aktualisiert.", "success");
    } catch (error) {
      pushToast(`Notiz konnte nicht aktualisiert werden: ${error.message}`, "danger");
    }
  }

  async function deleteNote(eventId) {
    const appId = timelineDialog.entry?.application?.id;
    if (!appId) return;
    try {
      await deleteRequest(`/api/applications/${appId}/notes/${eventId}`);
      await reloadTimeline(appId);
      pushToast("Notiz gelöscht.", "success");
    } catch (error) {
      pushToast(`Notiz konnte nicht gelöscht werden: ${error.message}`, "danger");
    }
  }

  async function linkDocument(docId) {
    const appId = timelineDialog.entry?.application?.id;
    if (!appId) return;
    try {
      await postJson(`/api/applications/${appId}/link-document`, { document_id: docId });
      await reloadTimeline(appId);
      pushToast("Dokument verknüpft.", "success");
    } catch (error) {
      pushToast(`Verknüpfung fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  if (loading) return <LoadingPanel label="Bewerbungen werden geladen..." />;

  const filteredApplications = applications.filter((application) => {
    const haystack = `${application.title || ""} ${application.company || ""} ${application.notes || ""}`.toLowerCase();
    const queryMatch = !deferredQuery || haystack.includes(deferredQuery.toLowerCase());
    const statusMatch = !filters.status ||
      (filters.status === "interview"
        ? INTERVIEW_STATUSES.includes(application.status)
        : application.status === filters.status);
    const dateMatch = (!filters.fromDate || (application.applied_at || "") >= filters.fromDate) &&
                      (!filters.toDate || (application.applied_at || "") <= filters.toDate + "T23:59:59");
    const artMatch = !filters.stellenart ||
      (filters.stellenart === "freelance" ? (application.job_employment_type && application.job_employment_type !== "festanstellung") : application.job_employment_type === "festanstellung" || !application.job_employment_type);
    return queryMatch && statusMatch && dateMatch && artMatch;
  });

  // #245: Sortierung
  const STATUS_PRIORITY = {
    angebot: 0, interview_abgeschlossen: 1, zweitgespraech: 2, interview: 3,
    warte_auf_rueckmeldung: 4, eingangsbestaetigung: 5, beworben: 6,
    in_vorbereitung: 7, entwurf: 8,
    angenommen: 9, abgelehnt: 10, zurueckgezogen: 11, abgelaufen: 12,
  };
  const sortedApplications = [...filteredApplications].sort((a, b) => {
    if (sortMode === "firma") return (a.company || "").localeCompare(b.company || "", "de");
    if (sortMode === "status") {
      const pa = STATUS_PRIORITY[a.status] ?? 99;
      const pb = STATUS_PRIORITY[b.status] ?? 99;
      return pa !== pb ? pa - pb : (b.applied_at || "").localeCompare(a.applied_at || "");
    }
    // neueste (default)
    return (b.applied_at || b.created_at || "").localeCompare(a.applied_at || a.created_at || "");
  });

  const dueFollowUps = followUps.filter((item) => item.faellig);
  const archivedCount = Number(applicationMeta.archivedCount || 0);
  const activeApplications = applications.filter((item) => !ARCHIVE_STATUSES.includes(item.status));
  const activeApplicationsCount = activeApplications.length;
  const visibleArchivedCount = applications.filter((item) => ARCHIVE_STATUSES.includes(item.status)).length;
  const interviewApplicationsCount = applications.filter((item) => INTERVIEW_STATUSES.includes(item.status)).length;
  const draftApplicationsCount = applications.filter((item) => ["in_vorbereitung", "entwurf"].includes(item.status)).length;
  const activeJobsCount = Number(chrome.workspace?.jobs?.active || 0);
  const applicationTimestamps = applications
    .map((item) => Date.parse(item?.applied_at || item?.created_at || item?.updated_at || ""))
    .filter((timestamp) => Number.isFinite(timestamp));
  const applicationsPerWeekRaw = (() => {
    if (!applications.length) return 0;
    if (!applicationTimestamps.length) return applications.length;
    const earliest = Math.min(...applicationTimestamps);
    const elapsedDays = Math.max(1, Math.ceil((Date.now() - earliest) / (1000 * 60 * 60 * 24)) + 1);
    return applications.length / (elapsedDays / 7);
  })();
  const applicationsPerWeek = new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: applicationsPerWeekRaw > 0 && applicationsPerWeekRaw < 10 ? 1 : 0,
    maximumFractionDigits: applicationsPerWeekRaw > 0 && applicationsPerWeekRaw < 10 ? 1 : 0,
  }).format(applicationsPerWeekRaw);
  const nextStep = (() => {
    if (dueFollowUps.length > 0) {
      return {
        badge: "Priorität 1",
        tone: "danger",
        title: "Fällige Nachfassaktionen zuerst schließen",
        description: `${dueFollowUps.length} Follow-up(s) sind fällig oder überfällig. Aktualisiere Status und Notizen, bevor neue Fälle liegen bleiben.`,
      };
    }
    if (draftApplicationsCount > 0) {
      const draftStatus = applications.some((item) => item.status === "in_vorbereitung") ? "in_vorbereitung" : "entwurf";
      return {
        badge: "Entwürfe",
        tone: "amber",
        title: "Fast fertige Bewerbungen abschließen",
        description: `${draftApplicationsCount} Bewerbung(en) stehen noch auf Entwurf oder Vorbereitung. Zieh zuerst die halbfertigen Fälle über die Ziellinie.`,
        actionLabel: "Entwürfe filtern",
        action: () => setFilters((current) => ({ ...current, status: draftStatus, showArchived: false })),
      };
    }
    if (!activeApplicationsCount && activeJobsCount > 0) {
      return {
        badge: "Start",
        tone: "sky",
        title: "Aus vorhandenen Stellen die erste Bewerbung machen",
        description: `${activeJobsCount} aktive Stellen sind da, aber noch keine aktive Bewerbung. Nutze eine Stelle als Startpunkt oder lege manuell eine Bewerbung an.`,
        actionLabel: "Bewerbung anlegen",
        action: () => setCreateDialog({ open: true, draft: EMPTY_APPLICATION }),
      };
    }
    if (interviewApplicationsCount > 0) {
      return {
        badge: "Interview",
        tone: "amber",
        title: "Interview-Phase eng begleiten",
        description: `${interviewApplicationsCount} Bewerbung(en) stehen im Interview oder Zweitgespräch. Halte Status, Termine und Notizen bewusst zusammen.`,
        actionLabel: "Interview filtern",
        action: () => setFilters((current) => ({ ...current, status: "interview", showArchived: false })),
      };
    }
    if (archivedCount > 0 && !filters.showArchived && !ARCHIVE_STATUSES.includes(filters.status)) {
      return {
        badge: "Archiv",
        tone: "neutral",
        title: "Archivierte Bewerbungen bleiben bewusst aus dem Weg",
        description: `${archivedCount} ältere Fälle liegen im Archiv. Blende sie nur ein, wenn du Gründe, Quellen oder alte Kontakte prüfen willst.`,
        actionLabel: "Archiv einblenden",
        action: () => setFilters((current) => ({ ...current, showArchived: true })),
      };
    }
    return {
      badge: "Auf Kurs",
      tone: "success",
      title: "Bewerbungsboard ist gerade sauber",
      description: "Im Moment ist nichts akut liegen geblieben. Nutze die Liste für klare Statuspflege statt nur zum Sammeln.",
    };
  })();

  return (
    <div id="page-bewerbungen" className="page active">
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Bewerbungen</h1>
        <div className="flex gap-2">
          <LinkButton size="sm" href={apiUrl("/api/cv/export/docx")} target="_blank" rel="noreferrer">
            <Download size={14} />
            CV als DOCX
          </LinkButton>
          <Button size="sm" onClick={() => setCreateDialog({ open: true, draft: EMPTY_APPLICATION })}>
            <Plus size={14} />
            Bewerbung
          </Button>
        </div>
      </div>

      <div className="grid gap-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label={filters.showArchived || ARCHIVE_STATUSES.includes(filters.status) ? "Sichtbare Bewerbungen" : "Aktive Bewerbungen"}
            value={filters.showArchived || ARCHIVE_STATUSES.includes(filters.status) ? applications.length : activeApplicationsCount}
            note={
              archivedCount > 0
                ? `${activeApplicationsCount} aktiv · ${archivedCount} archiviert`
                : `${activeJobsCount} aktive Stellen im Board`
            }
            tone="sky"
          />
          <MetricCard label="Bewerbungen pro Woche" value={applicationsPerWeek} note="Ø seit erster Bewerbung" tone="sky" />
          <MetricCard label="Follow-ups" value={dueFollowUps.length} note="Offene Nachfassaktionen" tone={dueFollowUps.length ? "danger" : "neutral"} />
          <MetricCard label="Interviews" value={interviewApplicationsCount} note="Aktive Interview-Phase" tone="amber" />
        </div>

        <Card className="rounded-2xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={nextStep.tone}>{nextStep.badge}</Badge>
                {archivedCount > 0 && !filters.showArchived && !ARCHIVE_STATUSES.includes(filters.status) ? (
                  <span className="text-xs text-muted/50">{archivedCount} archivierte Fälle sind aktuell ausgeblendet.</span>
                ) : null}
              </div>
              <h2 className="mt-3 text-base font-semibold text-ink">{nextStep.title}</h2>
              <p className="mt-1 max-w-3xl text-sm text-muted">{nextStep.description}</p>
            </div>
            {nextStep.actionLabel ? (
              <Button size="sm" variant="secondary" onClick={nextStep.action}>
                {nextStep.actionLabel}
              </Button>
            ) : null}
          </div>
        </Card>

        <Card className="rounded-2xl">
          <SectionHeading title="Filter" description="Schneller Blick auf einzelne Status-Cluster." />
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant={filters.showArchived ? "secondary" : "ghost"}
              onClick={() => setFilters((current) => ({ ...current, showArchived: !current.showArchived }))}
            >
              <Archive size={14} />
              {filters.showArchived ? "Archiv eingeblendet" : "Archivierte anzeigen"}
            </Button>
            {archivedCount > 0 ? (
              <span className="text-xs text-muted/50">
                {archivedCount} archivierte Bewerbung(en){visibleArchivedCount > 0 ? `, davon ${visibleArchivedCount} sichtbar` : ""}.
              </span>
            ) : (
              <span className="text-xs text-muted/50">Zurzeit keine archivierten Bewerbungen.</span>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_14rem_10rem_10rem_10rem]">
            <Field label="Suche">
              <TextInput value={filters.query} onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Titel, Firma oder Notizen" />
            </Field>
            <Field label="Status">
              <SelectInput value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
                <option value="">Alle</option>
                <option value="in_vorbereitung">In Vorbereitung</option>
                <option value="entwurf">Entwurf</option>
                <option value="beworben">Beworben</option>
                <option value="interview">Interview</option>
                <option value="zweitgespraech">Zweitgespräch</option>
                <option value="interview_abgeschlossen">Interview abgeschlossen</option>
                <option value="angebot">Angebot</option>
                <option value="abgelehnt">Abgelehnt</option>
                <option value="zurueckgezogen">Zurückgezogen</option>
                <option value="abgelaufen">Abgelaufen</option>
              </SelectInput>
            </Field>
            <Field label="Stellenart">
              <SelectInput value={filters.stellenart} onChange={(event) => setFilters((current) => ({ ...current, stellenart: event.target.value }))}>
                <option value="">Alle</option>
                <option value="festanstellung">Festanstellung</option>
                <option value="freelance">Freelance</option>
              </SelectInput>
            </Field>
            <Field label="Von">
              <TextInput type="date" value={filters.fromDate} onChange={(event) => setFilters((current) => ({ ...current, fromDate: event.target.value }))} />
            </Field>
            <Field label="Bis">
              <TextInput type="date" value={filters.toDate} onChange={(event) => setFilters((current) => ({ ...current, toDate: event.target.value }))} />
            </Field>
          </div>
        </Card>

        {/* #423: Follow-ups + Schnell-Import ABOVE the application list (2/3 + 1/3) */}
        {followUps.length > 0 && (
          <div className="mb-6 grid gap-4 xl:grid-cols-[2fr_1fr]">
            <Card className="rounded-2xl">
              <div className="flex items-center justify-between">
                <SectionHeading title={`Follow-ups (${followUps.length})`} />
                <Button size="sm" variant="ghost" onClick={() => navigateTo("kalender", { filter: "followups" })}>
                  Alle im Kalender
                </Button>
              </div>
              <div className="grid gap-1.5">
                {followUps.slice(0, 5).map((followUp) => (
                  <div
                    key={followUp.id}
                    title={`${followUp.title} — ${followUp.company}`}
                    onClick={() => openTimeline({ id: followUp.application_id })}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors min-w-0",
                      followUp.faellig
                        ? "bg-coral/8 border border-coral/15 hover:bg-coral/15"
                        : "bg-white/[0.03] border border-white/5 hover:bg-white/[0.07]"
                    )}
                  >
                    <CalendarClock size={14} className={cn("shrink-0", followUp.faellig ? "text-coral" : "text-muted/40")} />
                    <span className="flex-1 min-w-0 truncate text-ink font-medium">{followUp.title} — {followUp.company}</span>
                    <span className="shrink-0 text-xs text-muted/50">{formatDate(followUp.scheduled_date)}</span>
                    <Badge tone={followUp.faellig ? "danger" : "sky"}>{followUp.faellig ? "Fällig" : "Geplant"}</Badge>
                  </div>
                ))}
                {followUps.length > 5 && (
                  <p className="text-xs text-muted/40 px-3 pt-1">+{followUps.length - 5} weitere im Kalender</p>
                )}
              </div>
            </Card>
            <Card className="rounded-2xl xl:self-start">
              <h2 className="text-sm font-semibold text-ink">
                <Upload size={14} className="mr-1.5 inline-block text-teal/60" />
                Schnell-Import
              </h2>
              <p className="mt-1 text-[11px] text-muted/50">
                Dokumente oder E-Mails hier ablegen.
              </p>
              <div className="mt-3 grid gap-2">
                <EmailUploadButton pushToast={pushToast} onImported={() => loadData()} />
              </div>
              <div className="mt-3 rounded-lg border border-dashed border-white/10 p-4 text-center text-xs text-muted/40">
                Dateien per Drag &amp; Drop auf die Seite ziehen
              </div>
            </Card>
          </div>
        )}

        <div>
          <Card className="rounded-2xl">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <SectionHeading title="Bewerbungen" description="Statuswechsel werden direkt in der Historie vermerkt." />
              <div className="flex gap-1.5">
                {[["neueste", "Neueste"], ["status", "Status"], ["firma", "Firma A-Z"]].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-xs font-medium transition",
                      sortMode === key ? "bg-sky/20 text-sky" : "text-muted hover:text-ink hover:bg-white/5"
                    )}
                    onClick={() => setSortMode(key)}
                  >{label}</button>
                ))}
              </div>
            </div>
            <div className="grid gap-4">
              {sortedApplications.length ? (
                sortedApplications.map((application) => (
                  <Card key={application.id} className={cn("flex flex-col rounded-xl shadow-none", application.job_employment_type && application.job_employment_type !== "festanstellung" ? "border border-emerald-600/40 bg-emerald-950/20" : "glass-card-soft")}>
                    <div className="flex-1 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={statusTone(application.status)}>{application.status || "offen"}</Badge>
                        {/* #171: Klickbare ID */}
                        <button
                          className="font-mono text-[10px] text-muted/40 hover:text-sky cursor-pointer transition-colors"
                          title={`ID: ${application.id} — Klicken zum Kopieren`}
                          onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(application.id); pushToast(`ID ${application.id.slice(0,8)} kopiert`, "success"); }}
                        >{application.id?.slice(0, 8)}</button>
                        <span className="text-xs font-medium text-muted">{formatDate(application.applied_at)}</span>
                        {application.applied_at && (() => {
                          const days = Math.floor((Date.now() - Date.parse(application.applied_at)) / 86400000);
                          return days > 0 ? <span className="text-xs text-muted/40">vor {days}d</span> : null;
                        })()}
                        {application.document_count > 0 && (
                          <span className="inline-flex items-center gap-1 text-xs text-muted/50">
                            <FileText size={12} /> {application.document_count}
                          </span>
                        )}
                        {application.is_imported ? <Badge tone="neutral">Import</Badge> : null}
                        {application.bewerbungsart && application.bewerbungsart !== "mit_dokumenten" && (
                          <Badge tone="neutral">{application.bewerbungsart === "ueber_portal" ? "Portal" : application.bewerbungsart === "elektronisch" ? "E-Mail" : application.bewerbungsart}</Badge>
                        )}
                        {application.job_employment_type && application.job_employment_type !== "festanstellung" && (
                          <Badge tone="success">Freelance</Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-xl font-semibold text-ink cursor-pointer hover:text-sky transition-colors" onClick={() => openTimeline(application)}>{application.title}</h3>
                        {application.url ? (
                          <a href={application.url} target="_blank" rel="noreferrer" className="text-muted/40 hover:text-sky transition-colors" title="Stellenanzeige öffnen">
                            <ExternalLink size={14} />
                          </a>
                        ) : null}
                      </div>
                      <p className="text-sm text-muted">{application.company}{application.ansprechpartner ? ` — ${application.ansprechpartner}` : ""}</p>
                      {application.notes ? <p className="text-sm text-muted">{textExcerpt(application.notes, 150)}</p> : null}
                      {application.last_note ? <p className="text-xs text-muted/40 truncate">Letzte Notiz: {textExcerpt(application.last_note, 100)}</p> : null}
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/[0.06] pt-4">
                      <SelectInput value={application.status || "beworben"} onChange={(event) => updateStatus(application.id, event.target.value)}>
                        {STATUS_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </SelectInput>
                      <Button variant="secondary" onClick={() => openTimeline(application)}>
                        <Workflow size={15} />
                        Timeline
                      </Button>
                      {application.url && (
                        <a href={application.url} target="_blank" rel="noopener noreferrer">
                          <Button variant="secondary" type="button" onClick={(e) => e.stopPropagation()}>
                            <ExternalLink size={15} />
                            Stellenanzeige
                          </Button>
                        </a>
                      )}
                    </div>
                  </Card>
                ))
              ) : (
                <EmptyState
                  title={archivedCount > 0 && !filters.showArchived ? "Keine aktiven Bewerbungen im Filter" : "Noch keine Bewerbungen"}
                  description={
                    archivedCount > 0 && !filters.showArchived
                      ? "Aktive Bewerbungen passen gerade nicht zum Filter. Archivierte Fälle kannst du oben gezielt einblenden."
                      : "Lege eine neue Bewerbung an oder übernimm sie direkt aus einer Stelle."
                  }
                  action={<Button onClick={() => setCreateDialog({ open: true, draft: EMPTY_APPLICATION })}>Bewerbung anlegen</Button>}
                />
              )}
            </div>
          </Card>

        </div>
      </div>

      <Modal
        open={createDialog.open}
        title="Neue Bewerbung"
        onClose={() => setCreateDialog({ open: false, draft: EMPTY_APPLICATION })}
        footer={<div className="flex justify-end gap-3"><Button variant="ghost" onClick={() => setCreateDialog({ open: false, draft: EMPTY_APPLICATION })}>Abbrechen</Button><Button onClick={saveApplication}>Bewerbung speichern</Button></div>}
      >
        <div className="grid gap-4">
          {["title", "company", "url", "applied_at"].map((key) => (
            <Field key={key} label={key}>
              <TextInput value={createDialog.draft[key] || ""} onChange={(event) => setCreateDialog((current) => ({ ...current, draft: { ...current.draft, [key]: event.target.value } }))} />
            </Field>
          ))}
          <Field label="Status">
            <SelectInput value={createDialog.draft.status} onChange={(event) => setCreateDialog((current) => ({ ...current, draft: { ...current.draft, status: event.target.value } }))}>
              {STATUS_OPTIONS.filter((option) => !["abgelehnt", "zurueckgezogen", "abgelaufen"].includes(option.value)).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          </Field>
          <Field label="Notizen">
            <TextArea rows={4} value={createDialog.draft.notes} onChange={(event) => setCreateDialog((current) => ({ ...current, draft: { ...current.draft, notes: event.target.value } }))} />
          </Field>
        </div>
      </Modal>

      <Modal
        open={timelineDialog.open}
        title={`Timeline - ${timelineDialog.entry?.application?.title || ""}`}
        onClose={() => setTimelineDialog({ open: false, entry: null })}
        size="xl"
        footer={<div className="flex justify-between"><LinkButton size="sm" href={`/api/application/${timelineDialog.entry?.application?.id}/timeline/print`} target="_blank" rel="noreferrer"><Download size={14} /> Protokoll drucken</LinkButton><Button onClick={() => setTimelineDialog({ open: false, entry: null })}>Schlie&szlig;en</Button></div>}
      >
        <div className="grid gap-5">
          {/* Application details & contact (#134 editable) */}
          {timelineDialog.entry?.application && (() => {
            const app = timelineDialog.entry.application;
            return (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Bewerbung</p>
                    {/* #171: Klickbare IDs */}
                    <button
                      className="font-mono text-[10px] text-muted/30 hover:text-sky cursor-pointer"
                      title={`Bewerbung-ID: ${app.id}`}
                      onClick={() => { navigator.clipboard.writeText(app.id); pushToast(`ID ${app.id?.slice(0,8)} kopiert`, "success"); }}
                    >{app.id?.slice(0, 8)}</button>
                    {app.job_hash && (
                      <button
                        className="font-mono text-[10px] text-muted/30 hover:text-sky cursor-pointer"
                        title="Zur Stelle wechseln"
                        onClick={() => { window.location.hash = "stellen"; }}
                      ><ExternalLink size={8} className="mr-0.5 inline" />Stelle: {app.job_hash?.slice(0, 8)}</button>
                    )}
                  </div>
                  <h3 className="mt-1 text-base font-semibold text-ink">{app.title}</h3>
                  <p className="text-sm text-muted">{app.company}</p>
                  {(app.vermittler || app.endkunde) && (
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted/60">
                      {app.vermittler && <span>Vermittler: {app.vermittler}</span>}
                      {app.endkunde && <span>Endkunde: {app.endkunde}</span>}
                    </div>
                  )}
                </div>
                <Badge tone={statusTone(app.status)}>{app.status}</Badge>
              </div>
              {(app.ansprechpartner || app.kontakt_email) && (
                <div className="mt-2 flex flex-wrap gap-3 text-sm text-muted/70">
                  {app.ansprechpartner && <span>Kontakt: {app.ansprechpartner}</span>}
                  {app.kontakt_email && <a href={`mailto:${app.kontakt_email}`} className="text-sky hover:underline">{app.kontakt_email}</a>}
                </div>
              )}
              <div className="mt-1 flex flex-wrap items-center gap-3">
                {app.portal_name && (
                  <span className="text-xs text-muted/50">Portal: {app.portal_name}</span>
                )}
                {(app.url || timelineDialog.entry.job?.url) && (
                  <a href={app.url || timelineDialog.entry.job?.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-sky hover:underline">
                    <ExternalLink size={12} />
                    Stellenanzeige öffnen
                  </a>
                )}
              </div>
              <div className="mt-1 flex items-center gap-2">
                {app.applied_at && (
                  <span className="text-xs text-muted/40">Beworben am: {formatDate(app.applied_at)}</span>
                )}
                {app.is_imported ? <Badge tone="neutral">Importiert</Badge> : null}
              </div>

              {/* Inline edit section (#134) */}
              <details className="mt-3 border-t border-white/[0.06] pt-3">
                <summary className="cursor-pointer text-sm font-medium text-muted/60 hover:text-ink flex items-center gap-1.5">
                  <Pencil size={13} />
                  Bewerbung bearbeiten
                </summary>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {[
                    { key: "title", label: "Stellentitel" },
                    { key: "company", label: "Firma (Endkunde)" },
                    { key: "vermittler", label: "Vermittler" },
                    { key: "endkunde", label: "Endkunde" },
                    { key: "ansprechpartner", label: "Ansprechpartner" },
                    { key: "kontakt_email", label: "Kontakt-E-Mail" },
                    { key: "gehaltsvorstellung", label: "Gehaltsvorstellung", placeholder: "z.B. 65.000\u20ac/Jahr, 850\u20ac/Tag" },
                    { key: "portal_name", label: "Portal" },
                    { key: "url", label: "URL" },
                  ].map(({ key, label, placeholder }) => (
                    <Field key={key} label={label}>
                      <TextInput
                        defaultValue={app[key] || ""}
                        placeholder={placeholder || ""}
                        onBlur={async (e) => {
                          const newVal = e.target.value;
                          if (newVal === (app[key] || "")) return;
                          try {
                            await putJson(`/api/applications/${app.id}`, { [key]: newVal });
                            await reloadTimeline(app.id);
                            pushToast(`${label} aktualisiert.`, "success");
                          } catch (err) {
                            pushToast(`Fehler: ${err.message}`, "danger");
                          }
                        }}
                      />
                    </Field>
                  ))}
                  <Field label="Stellenart">
                    <SelectInput
                      value={app.job_employment_type || "festanstellung"}
                      onChange={async (e) => {
                        const newVal = e.target.value;
                        try {
                          await putJson(`/api/applications/${app.id}`, { employment_type: newVal });
                          await reloadTimeline(app.id);
                          pushToast("Stellenart aktualisiert.", "success");
                        } catch (err) {
                          pushToast(`Fehler: ${err.message}`, "danger");
                        }
                      }}
                    >
                      <option value="festanstellung">Festanstellung</option>
                      <option value="freelance">Freelance</option>
                      <option value="praktikum">Praktikum</option>
                      <option value="werkstudent">Werkstudent</option>
                    </SelectInput>
                  </Field>
                  <Field label="Bewerbungsdatum">
                    <TextInput
                      type="date"
                      defaultValue={(app.applied_at || "").slice(0, 10)}
                      onBlur={async (e) => {
                        const newVal = e.target.value;
                        if (newVal === (app.applied_at || "").slice(0, 10)) return;
                        try {
                          await putJson(`/api/applications/${app.id}`, { applied_at: newVal });
                          await reloadTimeline(app.id);
                          pushToast("Bewerbungsdatum aktualisiert.", "success");
                        } catch (err) {
                          pushToast(`Fehler: ${err.message}`, "danger");
                        }
                      }}
                    />
                  </Field>
                  <Field label="Importiert">
                    <label className="flex items-center gap-2 cursor-pointer mt-2">
                      <input
                        type="checkbox"
                        defaultChecked={!!app.is_imported}
                        onChange={async (e) => {
                          try {
                            await putJson(`/api/applications/${app.id}`, { is_imported: e.target.checked ? 1 : 0 });
                            await reloadTimeline(app.id);
                            pushToast(e.target.checked ? "Als importiert markiert." : "Import-Markierung entfernt.", "success");
                          } catch (err) {
                            pushToast(`Fehler: ${err.message}`, "danger");
                          }
                        }}
                        className="rounded border-white/20 bg-white/5 text-sky focus:ring-sky/30"
                      />
                      <span className="text-sm text-muted/60">Bewerbung existierte vor PBP</span>
                    </label>
                  </Field>
                </div>
              </details>

              <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-white/[0.06] pt-4">
                <Field className="min-w-[14rem] flex-1" label="Status direkt ändern">
                  <SelectInput
                    value={timelineStatusDraft}
                    onChange={(event) => updateTimelineStatus(event.target.value)}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </SelectInput>
                </Field>
                <p className="pb-2 text-xs text-muted/50">
                  Der Status wird sofort gespeichert und als Timeline-Eintrag protokolliert.
                </p>
              </div>
            </Card>
            );
          })()}

          {/* Job details with full description */}
          {timelineDialog.entry?.job ? (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Stellendetails</p>
              <h3 className="mt-2 text-base font-semibold text-ink">{timelineDialog.entry.job.title}</h3>
              <p className="text-sm text-muted">{timelineDialog.entry.job.company}{timelineDialog.entry.job.location ? ` — ${timelineDialog.entry.job.location}` : ""}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge tone="sky">{timelineDialog.entry.job.source || "Quelle"}</Badge>
                <Badge tone="amber">Score {timelineDialog.entry.job.score || 0}</Badge>
                {timelineDialog.entry.job.remote_level && timelineDialog.entry.job.remote_level !== "unbekannt" ? <Badge tone="success">{timelineDialog.entry.job.remote_level}</Badge> : null}
              </div>
              {timelineDialog.entry.job.salary_min ? (
                <p className="mt-2 text-sm text-ink">
                  Gehalt: {formatCurrency(timelineDialog.entry.job.salary_min)}{timelineDialog.entry.job.salary_max ? ` bis ${formatCurrency(timelineDialog.entry.job.salary_max)}` : ""}{timelineDialog.entry.job.salary_estimated ? " (geschätzt)" : ""}
                </p>
              ) : null}
              {timelineDialog.entry.job.url && (
                <a href={timelineDialog.entry.job.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm text-sky hover:underline">
                  Stellenanzeige öffnen
                </a>
              )}
              {timelineDialog.entry.job.description && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-sm font-medium text-muted/60 hover:text-ink">Stellenbeschreibung anzeigen</summary>
                  <div className="mt-2 max-h-60 overflow-y-auto rounded-lg bg-white/[0.02] p-3 text-sm text-muted/70 whitespace-pre-wrap">
                    {timelineDialog.entry.job.description}
                  </div>
                </details>
              )}
            </Card>
          ) : null}

          {/* Fit-Analyse (#84) */}
          {timelineDialog.entry?.application?.fit_analyse ? (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Fit-Analyse</p>
              <div className="mt-2 space-y-1 text-sm">
                {timelineDialog.entry.application.fit_analyse.total_score != null && (
                  <p className="text-ink font-medium">Fit-Score: {timelineDialog.entry.application.fit_analyse.total_score}/10</p>
                )}
                {timelineDialog.entry.application.fit_analyse.summary && (
                  <p className="text-muted/70">{timelineDialog.entry.application.fit_analyse.summary}</p>
                )}
                {(timelineDialog.entry.application.fit_analyse.muss_hits || []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {timelineDialog.entry.application.fit_analyse.muss_hits.map((k, i) => (
                      <Badge key={i} tone="success">{k}</Badge>
                    ))}
                  </div>
                )}
                {(timelineDialog.entry.application.fit_analyse.risks || []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {timelineDialog.entry.application.fit_analyse.risks.map((r, i) => (
                      <Badge key={i} tone="danger">{r}</Badge>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          ) : null}

          {/* Linked documents + Upload zone (#176) */}
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Dokumente</p>
            {(timelineDialog.entry?.documents || []).length > 0 && (
              <div className="mt-2 grid gap-1.5">
                {timelineDialog.entry.documents.map((doc) => (
                  <a
                    key={doc.id}
                    href={`/api/documents/${doc.id}/download`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-ink hover:text-sky transition-colors cursor-pointer rounded-lg px-2 py-1.5 -mx-2 hover:bg-white/[0.04]"
                  >
                    <FileText size={14} className="shrink-0 text-muted/50" />
                    <span className="truncate">{doc.filename}</span>
                    {doc.doc_type ? <Badge tone="sky">{doc.doc_type}</Badge> : null}
                    <ExternalLink size={12} className="shrink-0 ml-auto text-muted/30" />
                  </a>
                ))}
              </div>
            )}

            {/* Drag & Drop Upload Zone (#176) */}
            <div
              className="mt-3 border-2 border-dashed border-white/10 rounded-lg p-4 text-center hover:border-sky/30 hover:bg-sky/[0.02] transition-all cursor-pointer"
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-sky/40", "bg-sky/[0.05]"); }}
              onDragLeave={(e) => { e.currentTarget.classList.remove("border-sky/40", "bg-sky/[0.05]"); }}
              onDrop={async (e) => {
                e.preventDefault();
                e.currentTarget.classList.remove("border-sky/40", "bg-sky/[0.05]");
                const { extractDroppedFiles } = await import("@/file-drop.js");
                const { uploadDocumentFile } = await import("@/document-upload.js");
                const files = await extractDroppedFiles(e.dataTransfer);
                const appId = timelineDialog.entry?.application?.id;
                for (const file of files) {
                  try {
                    const result = await uploadDocumentFile(file);
                    if (result?.document_id && appId) {
                      await postJson(`/api/applications/${appId}/link-document`, { document_id: result.document_id });
                    }
                    pushToast(`'${file.name}' hochgeladen und verknüpft.`, "success");
                  } catch (err) {
                    pushToast(`Upload fehlgeschlagen: ${err.message}`, "danger");
                  }
                }
                if (appId) await reloadTimeline(appId);
              }}
              onClick={() => {
                const input = document.createElement("input");
                input.type = "file";
                input.multiple = true;
                input.accept = ".pdf,.docx,.doc,.txt,.msg,.eml";
                input.onchange = async (ev) => {
                  const { uploadDocumentFile } = await import("@/document-upload.js");
                  const appId = timelineDialog.entry?.application?.id;
                  for (const file of ev.target.files) {
                    try {
                      const result = await uploadDocumentFile(file);
                      if (result?.document_id && appId) {
                        await postJson(`/api/applications/${appId}/link-document`, { document_id: result.document_id });
                      }
                      pushToast(`'${file.name}' hochgeladen und verknüpft.`, "success");
                    } catch (err) {
                      pushToast(`Upload fehlgeschlagen: ${err.message}`, "danger");
                    }
                  }
                  if (appId) await reloadTimeline(appId);
                };
                input.click();
              }}
            >
              <Upload size={20} className="mx-auto text-muted/30" />
              <p className="mt-1 text-xs text-muted/50">Datei hierher ziehen oder klicken zum Upload</p>
            </div>

            {/* Link existing document button */}
            {documents.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-muted/50 hover:text-sky flex items-center gap-1">
                  <Link2 size={12} /> Vorhandenes Dokument verknüpfen
                </summary>
                <div className="mt-2 grid gap-1 max-h-40 overflow-y-auto">
                  {documents
                    .filter((d) => !d.linked_application_id)
                    .slice(0, 20)
                    .map((doc) => (
                    <button
                      key={doc.id}
                      className="flex items-center gap-2 text-xs text-ink hover:text-sky rounded px-2 py-1 hover:bg-white/[0.04] text-left w-full"
                      onClick={() => linkDocument(doc.id)}
                    >
                      <FileText size={12} className="shrink-0 text-muted/40" />
                      <span className="truncate">{doc.filename}</span>
                    </button>
                  ))}
                </div>
              </details>
            )}
          </Card>

          {/* Meetings for this application (#136) */}
          {timelineMeetings.length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
                <Calendar size={12} className="mr-1 inline" />
                Termine ({timelineMeetings.length})
              </p>
              <div className="mt-2 grid gap-1.5">
                {timelineMeetings.map((m) => {
                  const dt = new Date(m.meeting_date);
                  const isPast = dt < new Date();
                  return (
                    <div key={m.id} className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 ${isPast ? "opacity-50" : "bg-teal/5 border border-teal/15"}`}>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">{m.title || "Termin"}</p>
                        <p className="text-xs text-muted/60">
                          {formatDate(m.meeting_date)} {dt.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr
                          {m.platform && <span className="ml-1 rounded bg-sky/15 px-1 py-px text-[10px] font-bold text-sky">{m.platform}</span>}
                          {m.location && <span className="ml-1">— {m.location}</span>}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        {/* .ics Export (#261, #263) */}
                        <a href={`/api/meetings/${m.id}/ics`} download
                          className="inline-flex items-center gap-1 rounded bg-white/5 px-2 py-1 text-[10px] font-semibold text-muted/60 hover:bg-white/10 hover:text-ink"
                          title="Als .ics exportieren">
                          <Download size={10} /> .ics
                        </a>
                        {/* Delete meeting (#266) */}
                        <button
                          onClick={async () => {
                            if (!confirm("Termin wirklich löschen?")) return;
                            await deleteRequest(`/api/meetings/${m.id}`);
                            pushToast("Termin gelöscht.", "success");
                            loadTimeline();
                          }}
                          className="inline-flex items-center rounded bg-white/5 px-1.5 py-1 text-[10px] text-muted/40 hover:bg-danger/15 hover:text-danger"
                          title="Termin löschen">
                          <Trash2 size={10} />
                        </button>
                        {m.meeting_url && !isPast && (
                          <a href={m.meeting_url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded bg-teal/15 px-2 py-1 text-[11px] font-semibold text-teal hover:bg-teal/25">
                            <Video size={12} /> Beitreten
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {/* Emails for this application (#136) */}
          {timelineEmails.length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
                <Mail size={12} className="mr-1 inline" />
                E-Mails ({timelineEmails.length})
              </p>
              <div className="mt-2 grid gap-1.5">
                {timelineEmails.map((em) => (
                  <a
                    key={em.id}
                    href={`/api/emails/${em.id}/download`}
                    download={em.filename || true}
                    className="flex items-center gap-2 rounded-lg px-3 py-2 border border-white/[0.04] hover:bg-white/[0.06] transition-colors cursor-pointer no-underline"
                  >
                    <span className={`shrink-0 text-xs ${em.direction === "ausgang" ? "text-sky" : "text-amber"}`}>
                      {em.direction === "ausgang" ? "↗" : "↙"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink">{em.subject || "Ohne Betreff"}</p>
                      <p className="text-xs text-muted/50">
                        {em.direction === "ausgang" ? "An" : "Von"}: {em.direction === "ausgang" ? em.recipients : em.sender}
                        {em.sent_date && <span className="ml-2">{formatDate(em.sent_date)}</span>}
                      </p>
                    </div>
                    {em.detected_status && (
                      <Badge tone={statusTone(em.detected_status)}>{em.detected_status}</Badge>
                    )}
                    <Download size={14} className="shrink-0 text-muted/30 hover:text-sky transition-colors" />
                  </a>
                ))}
              </div>
            </Card>
          )}

          {/* Create meeting manually (#136) */}
          {timelineDialog.entry?.application && (
            <MeetingCreator
              applicationId={timelineDialog.entry.application.id}
              pushToast={pushToast}
              onCreated={async () => {
                const appId = timelineDialog.entry.application.id;
                await reloadTimeline(appId);
                const meetings = await api(`/api/applications/${appId}/meetings`).catch(() => ({ meetings: [] }));
                setTimelineMeetings(meetings?.meetings || []);
              }}
            />
          )}

          {/* Document linking search */}
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Dokument verknüpfen</p>
            <div className="mt-2 relative">
              <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted/50" />
              <TextInput
                className="!pl-9"
                placeholder="Dokument suchen..."
                value={docSearchQuery}
                onChange={(e) => setDocSearchQuery(e.target.value)}
              />
            </div>
            {docSearchQuery.trim() && (
              <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-white/5 bg-white/[0.02]">
                {documents
                  .filter((doc) => {
                    const q = docSearchQuery.toLowerCase();
                    return (doc.filename || "").toLowerCase().includes(q) || (doc.doc_type || "").toLowerCase().includes(q);
                  })
                  .slice(0, 8)
                  .map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink transition-colors hover:bg-white/[0.06]"
                      onClick={() => { linkDocument(doc.id); setDocSearchQuery(""); }}
                    >
                      <Link2 size={14} className="shrink-0 text-teal/60" />
                      <span className="truncate">{doc.filename}</span>
                      {doc.doc_type ? <span className="ml-auto shrink-0 text-[11px] text-muted/50">{doc.doc_type}</span> : null}
                    </button>
                  ))}
                {documents.filter((doc) => {
                  const q = docSearchQuery.toLowerCase();
                  return (doc.filename || "").toLowerCase().includes(q) || (doc.doc_type || "").toLowerCase().includes(q);
                }).length === 0 ? (
                  <p className="px-3 py-2 text-sm text-muted/50">Kein Dokument gefunden.</p>
                ) : null}
              </div>
            )}
          </Card>

          {/* Add note */}
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Neue Notiz</p>
            <div className="mt-2 flex gap-2">
              <TextArea
                rows={2}
                className="flex-1"
                placeholder="Notiz hinzufügen..."
                value={newNoteText}
                onChange={(e) => setNewNoteText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) addNote(); }}
              />
              <Button className="shrink-0 self-end" onClick={() => addNote()} disabled={!newNoteText.trim()}>
                <Plus size={14} />
                Hinzufügen
              </Button>
            </div>
          </Card>

          {/* E-Mail & Termin-Einträge aus unified_timeline (#313) */}
          {(timelineDialog.entry?.unified_timeline || []).filter(e => e._source === "email" || e._source === "meeting").length > 0 && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60 mb-2">
                Automatische Eintr&auml;ge
              </p>
              <div className="grid gap-1.5">
                {(timelineDialog.entry?.unified_timeline || [])
                  .filter(e => e._source === "email" || e._source === "meeting")
                  .map((entry) => (
                    <div key={entry.id} className="flex items-center gap-2 text-sm">
                      <Badge tone={entry._source === "email" ? "sky" : "success"}>
                        {entry._source === "email" ? "E-Mail" : "Termin"}
                      </Badge>
                      <span className="text-xs text-muted/40 shrink-0">{formatDate(entry.event_date)}</span>
                      <span className="text-ink truncate">{entry.description}</span>
                    </div>
                  ))
                }
              </div>
            </Card>
          )}

          {/* Timeline events */}
          {(timelineDialog.entry?.events || []).length ? (
            timelineDialog.entry.events.filter(e => !e.parent_event_id).map((event) => (
              <Card key={`${event.id}-${event.event_date}`} className="glass-card-soft rounded-xl shadow-none">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <Badge tone={statusTone(event.status || event.event_type)}>{event.status || event.event_type || "notiz"}</Badge>
                    <p className="text-[12px] text-muted/50">{formatDateTime(event.event_date)}</p>
                  </div>
                  <div className="flex-1 min-w-0">
                    {editingNoteId === event.id ? (
                      <div className="flex gap-2">
                        <TextArea
                          rows={2}
                          className="flex-1"
                          value={editingNoteText}
                          onChange={(e) => setEditingNoteText(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) updateNote(event.id); }}
                          autoFocus
                        />
                        <div className="flex flex-col gap-1 shrink-0">
                          <button type="button" className="text-teal hover:text-teal/80" onClick={() => updateNote(event.id)}><Check size={16} /></button>
                          <button type="button" className="text-muted hover:text-ink" onClick={() => setEditingNoteId(null)}><X size={16} /></button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-ink">{event.notes || event.text || "Keine Notiz"}</p>
                    )}
                  </div>
                  {(event.event_type === "notiz" || event.status === "notiz") && editingNoteId !== event.id ? (
                    <div className="flex gap-1.5 shrink-0">
                      <button type="button" className="text-muted/40 hover:text-sky transition-colors" onClick={() => { setReplyingToId(event.id); setReplyText(""); }} title="Antworten"><MessageSquareReply size={14} /></button>
                      <button type="button" className="text-muted/40 hover:text-ink transition-colors" onClick={() => { setEditingNoteId(event.id); setEditingNoteText(event.notes || event.text || ""); }} title="Bearbeiten"><Pencil size={14} /></button>
                      <button type="button" className="text-muted/40 hover:text-coral transition-colors" onClick={() => deleteNote(event.id)} title="Löschen"><Trash2 size={14} /></button>
                    </div>
                  ) : null}
                </div>
                {/* Reply form (#85) */}
                {replyingToId === event.id && (
                  <div className="ml-8 mt-2 flex gap-2">
                    <TextInput
                      className="flex-1"
                      placeholder="Antwort schreiben..."
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) addNote(event.id); }}
                    />
                    <Button size="sm" onClick={() => addNote(event.id)} disabled={!replyText.trim()}>Antworten</Button>
                    <Button size="sm" variant="ghost" onClick={() => setReplyingToId(null)}><X size={14} /></Button>
                  </div>
                )}
                {/* Replies to this note */}
                {(timelineDialog.entry?.events || []).filter(r => r.parent_event_id === event.id).map((reply) => (
                  <Card key={reply.id} className="ml-8 mt-2 glass-card-soft rounded-lg shadow-none border-l-2 border-sky/20">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted/40">{formatDateTime(reply.event_date)}</span>
                      <Badge tone="sky">Antwort</Badge>
                    </div>
                    <p className="text-sm text-ink mt-1">{reply.notes || reply.text}</p>
                  </Card>
                ))}
              </Card>
            ))
          ) : (
            <EmptyState title="Keine Timeline-Einträge" description="Für diese Bewerbung liegt noch keine Historie vor." />
          )}
        </div>
      </Modal>
    </div>
  );
}


function MeetingCreator({ applicationId, pushToast, onCreated }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("Vorstellungsgespräch");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("10:00");
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);

  async function createMeeting() {
    if (!date) {
      pushToast("Bitte ein Datum angeben.", "danger");
      return;
    }
    setSaving(true);
    try {
      const meetingDate = `${date}T${time || "10:00"}:00`;
      await postJson("/api/meetings", {
        application_id: applicationId,
        title,
        meeting_date: meetingDate,
        meeting_url: url || undefined,
        platform: url.includes("teams") ? "teams" : url.includes("zoom") ? "zoom" : url.includes("meet.google") ? "google_meet" : undefined,
      });
      pushToast("Termin erstellt.", "success");
      setOpen(false);
      setTitle("Vorstellungsgespräch");
      setDate("");
      setTime("10:00");
      setUrl("");
      onCreated();
    } catch (err) {
      pushToast(`Termin konnte nicht erstellt werden: ${err.message}`, "danger");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-white/10 px-3 py-2.5 text-[13px] text-muted/50 transition hover:border-teal/30 hover:text-teal/70"
        onClick={() => setOpen(true)}
      >
        <Calendar size={14} />
        Termin hinzufügen
      </button>
    );
  }

  return (
    <Card className="glass-card-soft rounded-xl shadow-none">
      <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
        <Calendar size={12} className="mr-1 inline" />
        Neuer Termin
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <div>
          <label className="text-xs text-muted/60">Titel</label>
          <input
            type="text"
            className="mt-0.5 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm text-ink"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs text-muted/60">Datum</label>
          <input
            type="date"
            className="mt-0.5 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm text-ink"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs text-muted/60">Uhrzeit</label>
          <input
            type="time"
            className="mt-0.5 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm text-ink"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs text-muted/60">Meeting-Link (optional)</label>
          <input
            type="url"
            className="mt-0.5 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm text-ink"
            placeholder="https://teams..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" onClick={createMeeting} disabled={saving || !date}>
          <Plus size={14} />
          Erstellen
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Abbrechen</Button>
      </div>
    </Card>
  );
}

