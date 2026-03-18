import { CalendarClock, Check, Download, FileText, Link2, Pencil, Plus, Search, Send, Trash2, Workflow, X } from "lucide-react";
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
import { cn, formatCurrency, formatDate, formatDateTime, statusTone } from "@/utils";

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
  const [filters, setFilters] = useState({ query: "", status: "" });
  const [createDialog, setCreateDialog] = useState({ open: false, draft: EMPTY_APPLICATION });
  const [timelineDialog, setTimelineDialog] = useState({ open: false, entry: null });
  const [newNoteText, setNewNoteText] = useState("");
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [docSearchQuery, setDocSearchQuery] = useState("");
  const [documents, setDocuments] = useState([]);

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

  async function updateStatus(applicationId, status) {
    try {
      await putJson(`/api/applications/${applicationId}/status`, { status });
      await refreshChrome();
      pushToast("Status aktualisiert.", "success");
    } catch (error) {
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
    } catch { /* silent */ }
  }

  async function addNote() {
    const text = newNoteText.trim();
    if (!text) return;
    const appId = timelineDialog.entry?.application?.id;
    if (!appId) return;
    try {
      await postJson(`/api/applications/${appId}/notes`, { text });
      setNewNoteText("");
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
    const haystack = `${application.title || ""} ${application.company || ""}`.toLowerCase();
    const queryMatch = !deferredQuery || haystack.includes(deferredQuery.toLowerCase());
    const statusMatch = !filters.status || application.status === filters.status;
    return queryMatch && statusMatch;
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
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_14rem]">
            <Field label="Suche">
              <TextInput value={filters.query} onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))} placeholder="Titel oder Firma" />
            </Field>
            <Field label="Status">
              <SelectInput value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
                <option value="">Alle</option>
                <option value="entwurf">Entwurf</option>
                <option value="beworben">Beworben</option>
                <option value="interview">Interview</option>
                <option value="angebot">Angebot</option>
                <option value="abgelehnt">Abgelehnt</option>
              </SelectInput>
            </Field>
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)]">
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
                      </div>
                      <h3 className="text-xl font-semibold text-ink">{application.title}</h3>
                      <p className="text-sm text-muted">{application.company}</p>
                      {application.notes ? <p className="text-sm text-muted">{application.notes}</p> : null}
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/[0.06] pt-4">
                      <SelectInput value={application.status || "beworben"} onChange={(event) => updateStatus(application.id, event.target.value)}>
                        <option value="entwurf">Entwurf</option>
                        <option value="beworben">Beworben</option>
                        <option value="interview">Interview</option>
                        <option value="angebot">Angebot</option>
                        <option value="abgelehnt">Abgelehnt</option>
                        <option value="zurueckgezogen">Zurückgezogen</option>
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

          <Card className="rounded-2xl">
            <SectionHeading title="Follow-ups" description="Fällige Nachfassaktionen werden vom Backend berechnet." />
            <div className="grid gap-4">
              {followUps.length ? (
                followUps.map((followUp) => (
                  <Card key={followUp.id} className="glass-card-soft rounded-xl shadow-none">
                    <div className="flex items-start gap-3">
                      <div className="glass-icon glass-icon-danger h-12 w-12">
                        <CalendarClock size={16} />
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-ink">{followUp.title} - {followUp.company}</p>
                        <p className="text-sm text-muted">Fällig am {formatDate(followUp.scheduled_date)}</p>
                        <Badge tone={followUp.faellig ? "danger" : "sky"}>{followUp.faellig ? "Fällig" : "Geplant"}</Badge>
                      </div>
                    </div>
                  </Card>
                ))
              ) : (
                <EmptyState title="Keine Follow-ups" description="Sobald Nachfassaktionen geplant sind, erscheinen sie hier." />
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
              <option value="entwurf">Entwurf</option>
              <option value="beworben">Beworben</option>
              <option value="interview">Interview</option>
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
          {/* Job details */}
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
            </Card>
          ) : null}

          {/* Linked documents */}
          {(timelineDialog.entry?.documents || []).length > 0 ? (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Verknüpfte Dokumente</p>
              <div className="mt-2 grid gap-1.5">
                {timelineDialog.entry.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center gap-2 text-sm text-ink">
                    <FileText size={14} className="shrink-0 text-muted/50" />
                    <span className="truncate">{doc.filename}</span>
                    {doc.doc_type ? <Badge tone="sky">{doc.doc_type}</Badge> : null}
                  </div>
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
              <Button className="shrink-0 self-end" onClick={addNote} disabled={!newNoteText.trim()}>
                <Plus size={14} />
                Hinzufügen
              </Button>
            </div>
          </Card>

          {/* Timeline events */}
          {(timelineDialog.entry?.events || []).length ? (
            timelineDialog.entry.events.map((event) => (
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
                      <button type="button" className="text-muted/40 hover:text-ink transition-colors" onClick={() => { setEditingNoteId(event.id); setEditingNoteText(event.notes || event.text || ""); }} title="Bearbeiten"><Pencil size={14} /></button>
                      <button type="button" className="text-muted/40 hover:text-coral transition-colors" onClick={() => deleteNote(event.id)} title="Löschen"><Trash2 size={14} /></button>
                    </div>
                  ) : null}
                </div>
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

