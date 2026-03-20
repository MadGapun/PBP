import { CalendarClock, Check, Download, ExternalLink, FileText, Link2, MessageSquareReply, Pencil, Plus, Search, Send, Trash2, Workflow, X } from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useEffectEvent, useState } from "react";

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

export default function ApplicationsPage() {
  const { chrome, reloadKey, refreshChrome, pushToast } = useApp();
  const [loading, setLoading] = useState(true);
  const [applications, setApplications] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [filters, setFilters] = useState({ query: "", status: "", fromDate: "", toDate: "" });
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

  const deferredQuery = useDeferredValue(filters.query);

  const loadPage = useEffectEvent(async () => {
    try {
      const [applicationData, followUpData] = await Promise.all([
        api("/api/applications"),
        api("/api/follow-ups"),
      ]);
      startTransition(() => {
        setApplications(applicationData?.applications || []);
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
  }, [reloadKey]);

  async function updateStatus(applicationId, status, options = {}) {
    try {
      await putJson(`/api/applications/${applicationId}/status`, { status });
      setApplications((current) =>
        current.map((app) => (app.id === applicationId ? { ...app, status } : app))
      );
      if (options.reloadTimeline) {
        await reloadTimeline(applicationId);
      }
      await refreshChrome({ quiet: true });
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
      const [timeline, docs] = await Promise.all([
        api(`/api/application/${application.id}/timeline`),
        api("/api/documents"),
      ]);
      setTimelineDialog({ open: true, entry: timeline });
      setTimelineStatusDraft(timeline?.application?.status || EMPTY_APPLICATION.status);
      setDocuments(docs?.documents || []);
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
    const statusMatch = !filters.status || application.status === filters.status;
    const dateMatch = (!filters.fromDate || (application.applied_at || "") >= filters.fromDate) &&
                      (!filters.toDate || (application.applied_at || "") <= filters.toDate + "T23:59:59");
    return queryMatch && statusMatch && dateMatch;
  });

  const dueFollowUps = followUps.filter((item) => item.faellig);
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
          <MetricCard label="Bewerbungen" value={`${applications.length} / ${activeJobsCount}`} note="Bewerbungen / aktive Stellen" tone="sky" />
          <MetricCard label="Bewerbungen pro Woche" value={applicationsPerWeek} note="Ø seit erster Bewerbung" tone="sky" />
          <MetricCard label="Follow-ups" value={dueFollowUps.length} note="Offene Nachfassaktionen" tone={dueFollowUps.length ? "danger" : "neutral"} />
          <MetricCard label="Interviews" value={applications.filter((item) => item.status === "interview").length} note="Aktive Interview-Phase" tone="amber" />
        </div>

        <Card className="rounded-2xl">
          <SectionHeading title="Filter" description="Schneller Blick auf einzelne Status-Cluster." />
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_14rem_10rem_10rem]">
            <Field label="Suche">
              <TextInput value={filters.query} onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Titel, Firma oder Notizen" />
            </Field>
            <Field label="Status">
              <SelectInput value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
                <option value="">Alle</option>
                <option value="entwurf">Entwurf</option>
                <option value="beworben">Beworben</option>
                <option value="interview">Interview</option>
                <option value="zweitgespraech">Zweitgespräch</option>
                <option value="angebot">Angebot</option>
                <option value="abgelehnt">Abgelehnt</option>
                <option value="abgelaufen">Abgelaufen</option>
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

        <div className={cn("grid gap-6", followUps.length > 0 ? "xl:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)]" : "")}>
          <Card className="rounded-2xl">
            <SectionHeading title="Bewerbungen" description="Statuswechsel werden direkt in der Historie vermerkt." />
            <div className="grid gap-4">
              {filteredApplications.length ? (
                filteredApplications.map((application) => (
                  <Card key={application.id} className="flex flex-col glass-card-soft rounded-xl shadow-none">
                    <div className="flex-1 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={statusTone(application.status)}>{application.status || "offen"}</Badge>
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
                        {application.bewerbungsart && application.bewerbungsart !== "mit_dokumenten" && (
                          <Badge tone="neutral">{application.bewerbungsart === "ueber_portal" ? "Portal" : application.bewerbungsart === "elektronisch" ? "E-Mail" : application.bewerbungsart}</Badge>
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
                    </div>
                  </Card>
                ))
              ) : (
                <EmptyState
                  title="Noch keine Bewerbungen"
            description="Lege eine neue Bewerbung an oder übernimm sie direkt aus einer Stelle."
                  action={<Button onClick={() => setCreateDialog({ open: true, draft: EMPTY_APPLICATION })}>Bewerbung anlegen</Button>}
                />
              )}
            </div>
          </Card>

          {followUps.length > 0 && (
            <Card className="rounded-2xl">
              <SectionHeading title={`Follow-ups (${followUps.length})`} />
              <div className="grid gap-1.5">
                {followUps.map((followUp) => (
                  <div key={followUp.id} className={cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                    followUp.faellig ? "bg-coral/8 border border-coral/15" : "bg-white/[0.03] border border-white/5"
                  )}>
                    <CalendarClock size={14} className={followUp.faellig ? "text-coral" : "text-muted/40"} />
                    <span className="flex-1 truncate text-ink font-medium">{followUp.title} — {followUp.company}</span>
                    <span className="shrink-0 text-xs text-muted/50">{formatDate(followUp.scheduled_date)}</span>
                    <Badge tone={followUp.faellig ? "danger" : "sky"}>{followUp.faellig ? "Fällig" : "Geplant"}</Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}
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
        footer={<div className="flex justify-end"><Button onClick={() => setTimelineDialog({ open: false, entry: null })}>Schließen</Button></div>}
      >
        <div className="grid gap-5">
          {/* Application details & contact */}
          {timelineDialog.entry?.application && (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Bewerbung</p>
                  <h3 className="mt-1 text-base font-semibold text-ink">{timelineDialog.entry.application.title}</h3>
                  <p className="text-sm text-muted">{timelineDialog.entry.application.company}</p>
                </div>
                <Badge tone={statusTone(timelineDialog.entry.application.status)}>{timelineDialog.entry.application.status}</Badge>
              </div>
              {(timelineDialog.entry.application.ansprechpartner || timelineDialog.entry.application.kontakt_email) && (
                <div className="mt-2 flex flex-wrap gap-3 text-sm text-muted/70">
                  {timelineDialog.entry.application.ansprechpartner && <span>Kontakt: {timelineDialog.entry.application.ansprechpartner}</span>}
                  {timelineDialog.entry.application.kontakt_email && <a href={`mailto:${timelineDialog.entry.application.kontakt_email}`} className="text-sky hover:underline">{timelineDialog.entry.application.kontakt_email}</a>}
                </div>
              )}
              {timelineDialog.entry.application.portal_name && (
                <p className="mt-1 text-xs text-muted/50">Portal: {timelineDialog.entry.application.portal_name}</p>
              )}
              {timelineDialog.entry.application.applied_at && (
                <p className="mt-1 text-xs text-muted/40">Beworben am: {formatDate(timelineDialog.entry.application.applied_at)}</p>
              )}
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
          )}

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
                  Stellenanzeige oeffnen
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

          {/* Linked documents */}
          {(timelineDialog.entry?.documents || []).length > 0 ? (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Verknüpfte Dokumente</p>
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
            </Card>
          ) : null}

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

