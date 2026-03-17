import { CalendarClock, Download, Plus, Send, Workflow } from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useEffectEvent, useState } from "react";

import { api, apiUrl, postJson, putJson } from "@/api";
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
import { formatDate, formatDateTime, statusTone } from "@/utils";

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
      const timeline = await api(`/api/application/${application.id}/timeline`);
      setTimelineDialog({ open: true, entry: timeline });
    } catch (error) {
      pushToast(`Timeline konnte nicht geladen werden: ${error.message}`, "danger");
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
                  <Card key={application.id} className="glass-card-soft rounded-xl shadow-none">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={statusTone(application.status)}>{application.status || "offen"}</Badge>
                          <span className="text-xs font-medium text-muted">{formatDate(application.applied_at)}</span>
                        </div>
                        <h3 className="text-xl font-semibold text-ink">{application.title}</h3>
                        <p className="text-sm text-muted">{application.company}</p>
                        {application.notes ? <p className="text-sm text-muted">{application.notes}</p> : null}
                      </div>
                      <div className="flex flex-wrap gap-3">
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
        <div className="grid gap-4">
          {(timelineDialog.entry?.events || []).length ? (
            timelineDialog.entry.events.map((event) => (
              <Card key={`${event.id}-${event.event_date}`} className="glass-card-soft rounded-xl shadow-none">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Badge tone={statusTone(event.status)}>{event.status}</Badge>
                    <p className="mt-3 text-sm text-muted">{formatDateTime(event.event_date)}</p>
                  </div>
                  <p className="max-w-xl text-sm text-ink">{event.notes || "Keine Notiz"}</p>
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

