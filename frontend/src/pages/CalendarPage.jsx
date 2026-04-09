import { Briefcase, Calendar, CalendarClock, ClipboardCheck, Clock, Download, ExternalLink, FileText, List, MapPin, Send, Trash2, Video } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";

import { api, apiUrl, deleteRequest, postJson } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  LinkButton,
  LoadingPanel,
  Modal,
  PageHeader,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/ui";
import { cn, formatDate, formatDateTime } from "@/utils";

const MEETING_TYPE_LABELS = {
  interview: "Interview",
  zweitgespraech: "2. Gespraech",
  telefoninterview: "Telefoninterview",
  assessment: "Assessment",
  kennenlernen: "Kennenlernen",
  followup: "Follow-up",
  sonstiges: "Termin",
};

function meetingTypeLabel(type) {
  return MEETING_TYPE_LABELS[type] || type || "Termin";
}

function isPast(dateStr) {
  if (!dateStr) return false;
  // A meeting is "past" only if its DATE is before today (not just its time) (#364)
  const d = new Date(dateStr);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return false; // today is never "past"
  return d < now;
}

function isToday(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

const CATEGORIES = [
  { key: "termine", label: "Termine", icon: CalendarClock, color: "sky" },
  { key: "bewerbungen", label: "Bewerbungen", icon: Send, color: "emerald" },
  { key: "followups", label: "Follow-ups", icon: ClipboardCheck, color: "amber" },
  { key: "dokumente", label: "Dokumente", icon: FileText, color: "violet" },
];

const CATEGORY_COLORS = {
  termine: "bg-sky/10 text-sky",
  bewerbungen: "bg-emerald-500/10 text-emerald-400",
  followups: "bg-amber/10 text-amber",
  dokumente: "bg-violet-500/10 text-violet-400",
};

function loadCategories() {
  try {
    const stored = localStorage.getItem("pbp-calendar-categories");
    if (stored) return JSON.parse(stored);
  } catch { /* ignore */ }
  return { termine: true, bewerbungen: true, followups: true, dokumente: true };
}

export default function CalendarPage() {
  const { reloadKey, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [meetings, setMeetings] = useState([]);
  const [collisions, setCollisions] = useState([]);
  const [filter, setFilter] = useState("upcoming"); // upcoming | past | all
  const [viewMode, setViewMode] = useState("kalender"); // kalender | log
  const [categories, setCategories] = useState(loadCategories);
  const [activityLog, setActivityLog] = useState([]);
  const [logDays, setLogDays] = useState(90);
  const [logLoading, setLogLoading] = useState(false);
  const [monthFilter, setMonthFilter] = useState(""); // #394: "" = alle, "2026-04" = April 2026
  const [manualTermin, setManualTermin] = useState(null); // #394: manual meeting creation form

  const loadData = useEffectEvent(async () => {
    try {
      const data = await api("/api/meetings/calendar?days=365");
      setMeetings(data?.meetings || []);
      setCollisions(data?.collisions || []);
    } catch (error) {
      pushToast(`Termine konnten nicht geladen werden: ${error.message}`, "danger");
    } finally {
      setLoading(false);
    }
  });

  useEffect(() => { loadData(); }, [reloadKey]);

  const loadActivityLog = useEffectEvent(async () => {
    setLogLoading(true);
    try {
      const activeCats = Object.entries(categories).filter(([, v]) => v).map(([k]) => k).join(",");
      const data = await api(`/api/activity-log?days=${logDays}&categories=${activeCats}`);
      setActivityLog(data?.entries || []);
    } catch (error) {
      pushToast(`Aktivitaetslog konnte nicht geladen werden: ${error.message}`, "danger");
    } finally {
      setLogLoading(false);
    }
  });

  useEffect(() => {
    if (viewMode === "log") loadActivityLog();
  }, [viewMode, logDays, categories, reloadKey]);

  function toggleCategory(key) {
    setCategories((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem("pbp-calendar-categories", JSON.stringify(next));
      return next;
    });
  }

  async function deleteMeeting(id) {
    try {
      await deleteRequest(`/api/meetings/${id}`);
      setMeetings((cur) => cur.filter((m) => m.id !== id));
      pushToast("Termin geloescht", "success");
    } catch (error) {
      pushToast(`Fehler: ${error.message}`, "danger");
    }
  }

  const collisionIds = new Set(collisions.flatMap((c) => [c.meeting_1, c.meeting_2]));

  const filtered = meetings.filter((m) => {
    // Category filter (#373)
    if (m.is_follow_up && !categories.followups) return false;
    if (!m.is_follow_up && !categories.termine) return false;
    // #394: Month filter
    if (monthFilter && m.meeting_date) {
      const mMonth = m.meeting_date.slice(0, 7);
      if (mMonth !== monthFilter) return false;
    }
    // Time filter
    if (filter === "upcoming") return !isPast(m.meeting_date);
    if (filter === "past") return isPast(m.meeting_date);
    return true;
  });

  // #394: Available months for filter
  const availableMonths = [...new Set(meetings.map((m) => (m.meeting_date || "").slice(0, 7)).filter(Boolean))].sort();

  const grouped = {};
  for (const m of filtered) {
    const date = (m.meeting_date || "").slice(0, 10);
    if (!grouped[date]) grouped[date] = [];
    grouped[date].push(m);
  }
  const sortedDates = Object.keys(grouped).sort();

  if (loading) return <LoadingPanel />;

  return (
    <div id="page-kalender" className="page active">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
        <PageHeader title="Kalender" subtitle={`${meetings.length} Termine`} />
        <div className="flex flex-wrap items-center gap-2">
          {/* View mode toggle */}
          <button type="button" onClick={() => setViewMode("kalender")} className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${viewMode === "kalender" ? "bg-sky/15 text-sky" : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"}`}>
            <Calendar size={12} className="inline mr-1" />Kalender
          </button>
          <button type="button" onClick={() => setViewMode("log")} className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${viewMode === "log" ? "bg-sky/15 text-sky" : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"}`}>
            <List size={12} className="inline mr-1" />Aktivitaetslog
          </button>
          <span className="mx-1 h-4 w-px bg-white/10" />
          {viewMode === "kalender" ? (
            <>
              {[
                { label: "Kommende", value: "upcoming" },
                { label: "Vergangene", value: "past" },
                { label: "Alle", value: "all" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setFilter(opt.value)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                    filter === opt.value
                      ? "bg-sky/15 text-sky"
                      : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </>
          ) : (
            <>
              {[7, 30, 90, 365].map((d) => (
                <button key={d} type="button" onClick={() => setLogDays(d)} className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${logDays === d ? "bg-sky/15 text-sky" : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"}`}>
                  {d}d
                </button>
              ))}
            </>
          )}
          <LinkButton
            size="sm"
            href={apiUrl("/api/meetings/export.ics")}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            ICS
          </LinkButton>
        </div>
      </div>

      {/* Category toggles (#373) + Month filter (#394) */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const active = categories[cat.key];
          return (
            <button
              key={cat.key}
              type="button"
              onClick={() => toggleCategory(cat.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors",
                active ? CATEGORY_COLORS[cat.key] : "text-muted/30 bg-white/[0.02] line-through"
              )}
            >
              <Icon size={12} />
              {cat.label}
            </button>
          );
        })}
        {/* #394: Month filter */}
        {viewMode === "kalender" && availableMonths.length > 1 && (
          <>
            <span className="mx-1 h-4 w-px bg-white/10" />
            <select
              value={monthFilter}
              onChange={(e) => setMonthFilter(e.target.value)}
              className="rounded-lg bg-white/[0.03] border border-white/5 px-2 py-1 text-xs text-muted/60"
            >
              <option value="">Alle Monate</option>
              {availableMonths.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </>
        )}
        <span className="mx-1 h-4 w-px bg-white/10" />
        {/* #394: Manual meeting creation */}
        <Button size="sm" variant="ghost" onClick={() => setManualTermin({
          title: "", meeting_date: new Date().toISOString().slice(0, 16),
          meeting_type: "sonstiges", location: "", notes: "",
        })}>
          + Neuer Termin
        </Button>
      </div>

      {/* #394: Manual meeting creation modal */}
      {manualTermin && (
        <Modal title="Neuen Termin anlegen" onClose={() => setManualTermin(null)}>
          <div className="grid gap-4">
            <Field label="Titel">
              <TextInput value={manualTermin.title} onChange={(e) => setManualTermin((p) => ({ ...p, title: e.target.value }))} placeholder="z.B. Interview bei Firma XY" />
            </Field>
            <Field label="Datum & Uhrzeit">
              <TextInput type="datetime-local" value={manualTermin.meeting_date} onChange={(e) => setManualTermin((p) => ({ ...p, meeting_date: e.target.value }))} />
            </Field>
            <Field label="Typ">
              <SelectInput value={manualTermin.meeting_type} onChange={(e) => setManualTermin((p) => ({ ...p, meeting_type: e.target.value }))}>
                {Object.entries(MEETING_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </SelectInput>
            </Field>
            <Field label="Ort (optional)">
              <TextInput value={manualTermin.location} onChange={(e) => setManualTermin((p) => ({ ...p, location: e.target.value }))} placeholder="z.B. Zoom, Buero, ..." />
            </Field>
            <Field label="Notizen (optional)">
              <TextArea value={manualTermin.notes} onChange={(e) => setManualTermin((p) => ({ ...p, notes: e.target.value }))} rows={2} />
            </Field>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setManualTermin(null)}>Abbrechen</Button>
              <Button disabled={!manualTermin.title} onClick={async () => {
                try {
                  await postJson("/api/meetings", manualTermin);
                  pushToast("Termin angelegt", "success");
                  setManualTermin(null);
                  loadData();
                } catch (err) {
                  pushToast(`Fehler: ${err.message}`, "danger");
                }
              }}>Anlegen</Button>
            </div>
          </div>
        </Modal>
      )}

      {viewMode === "log" ? (
        /* Activity Log View (#373) */
        logLoading ? <LoadingPanel /> : activityLog.length === 0 ? (
          <EmptyState title="Keine Aktivitaeten" description={`Keine Eintraege in den letzten ${logDays} Tagen.`} />
        ) : (
          <div className="grid gap-1.5">
            {activityLog.map((entry) => {
              const catDef = CATEGORIES.find((c) => c.key === entry.category);
              const Icon = catDef?.icon || Calendar;
              return (
                <button
                  key={`${entry.category}-${entry.id}`}
                  type="button"
                  className="flex items-center gap-3 rounded-xl bg-white/[0.02] px-4 py-2.5 text-left transition-colors hover:bg-white/[0.05]"
                  onClick={() => {
                    if (entry.link_type === "bewerbung" && entry.link_id) navigateTo("bewerbungen", { highlight: entry.link_id });
                    else if (entry.link_type === "dokument") navigateTo("dokumente");
                  }}
                >
                  <div className={cn("flex h-7 w-7 items-center justify-center rounded-lg shrink-0", CATEGORY_COLORS[entry.category] || "bg-white/5 text-muted/40")}>
                    <Icon size={14} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-ink truncate">{entry.title}</p>
                    {entry.subtitle && <p className="text-xs text-muted/40 truncate">{entry.subtitle}</p>}
                  </div>
                  <span className="shrink-0 text-xs text-muted/30">{formatDate(entry.event_date)}</span>
                  {entry.is_imported && <Badge tone="neutral" className="shrink-0">Import</Badge>}
                </button>
              );
            })}
          </div>
        )
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Keine Termine"
          description={filter === "upcoming"
            ? "Keine kommenden Termine. Termine werden automatisch aus E-Mails und Bewerbungen erkannt."
            : "Keine Termine im gewaehlten Zeitraum."
          }
        />
      ) : (
        <div className="grid gap-4">
          {sortedDates.map((date) => (
            <div key={date}>
              <h2 className={cn(
                "mb-2 text-sm font-semibold",
                isToday(date) ? "text-sky" : isPast(date) ? "text-muted/40" : "text-ink"
              )}>
                {isToday(date) ? "Heute" : formatDate(date)}
                {isToday(date) && <span className="ml-2 text-xs font-normal text-muted/50">({formatDate(date)})</span>}
              </h2>
              <div className="grid gap-2">
                {grouped[date].map((meeting) => {
                  const past = isPast(meeting.meeting_date);
                  const hasCollision = collisionIds.has(meeting.id);
                  const isFollowUp = meeting.is_follow_up;
                  const IconComp = isFollowUp ? ClipboardCheck : CalendarClock;
                  const accent = isFollowUp ? "amber" : "sky";
                  return (
                    <Card
                      key={meeting.id}
                      className={cn(
                        "rounded-xl cursor-pointer hover:bg-white/[0.03] transition-colors",
                        past && "opacity-50",
                        hasCollision && "border-amber/30 border"
                      )}
                      onClick={() => {
                        // #395: Click opens application dossier
                        if (meeting.application_id) {
                          navigateTo("bewerbungen", { highlight: meeting.application_id });
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className={cn(
                          "mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg shrink-0",
                          past ? "bg-white/[0.03]" : isFollowUp ? "bg-amber/10" : "bg-sky/10"
                        )}>
                          <IconComp size={18} className={past ? "text-muted/30" : `text-${accent}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-medium text-ink truncate">{meeting.title}</h3>
                            <Badge tone={past ? "neutral" : isFollowUp ? "amber" : "sky"}>{meetingTypeLabel(meeting.meeting_type)}</Badge>
                            {hasCollision && <Badge tone="amber">Kollision</Badge>}
                          </div>
                          {(meeting.app_company || meeting.app_title) && (
                            <p className="text-sm text-muted/50 mt-0.5 truncate">
                              {meeting.app_title}{meeting.app_company ? ` \u2014 ${meeting.app_company}` : ""}
                            </p>
                          )}
                          <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-muted/40">
                            <span className="flex items-center gap-1">
                              <Clock size={11} />
                              {formatDateTime(meeting.meeting_date)}
                              {meeting.meeting_end && ` \u2013 ${formatDateTime(meeting.meeting_end).split(", ").pop()}`}
                            </span>
                            {meeting.location && (
                              <span className="flex items-center gap-1">
                                <MapPin size={11} />
                                {meeting.location}
                              </span>
                            )}
                            {meeting.platform && (
                              <span className="flex items-center gap-1">
                                <Video size={11} />
                                {meeting.platform}
                              </span>
                            )}
                          </div>
                          {meeting.notes && (
                            <p className="mt-1.5 text-xs text-muted/40 line-clamp-2">{meeting.notes}</p>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          {meeting.meeting_url && (
                            <a
                              href={meeting.meeting_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-lg p-1.5 text-muted/30 hover:text-sky transition-colors"
                              title="Meeting-Link oeffnen"
                            >
                              <ExternalLink size={14} />
                            </a>
                          )}
                          {!isFollowUp && (
                            <>
                              <a
                                href={apiUrl(`/api/meetings/${meeting.id}/ics`)}
                                className="rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors"
                                title="ICS herunterladen"
                              >
                                <Download size={14} />
                              </a>
                              <button
                                type="button"
                                onClick={() => deleteMeeting(meeting.id)}
                                className="rounded-lg p-1.5 text-muted/30 hover:text-coral transition-colors"
                                title="Termin loeschen"
                              >
                                <Trash2 size={14} />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
