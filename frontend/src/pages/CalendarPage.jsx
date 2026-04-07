import { Calendar, CalendarClock, Clock, Download, ExternalLink, MapPin, Trash2, Video } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";

import { api, apiUrl, deleteRequest } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  LinkButton,
  LoadingPanel,
  PageHeader,
} from "@/components/ui";
import { cn, formatDate, formatDateTime } from "@/utils";

const MEETING_TYPE_LABELS = {
  interview: "Interview",
  zweitgespraech: "2. Gespr\u00e4ch",
  telefoninterview: "Telefoninterview",
  assessment: "Assessment",
  kennenlernen: "Kennenlernen",
  sonstiges: "Termin",
};

function meetingTypeLabel(type) {
  return MEETING_TYPE_LABELS[type] || type || "Termin";
}

function isPast(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date();
}

function isToday(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

export default function CalendarPage() {
  const { reloadKey, pushToast } = useApp();
  const [loading, setLoading] = useState(true);
  const [meetings, setMeetings] = useState([]);
  const [collisions, setCollisions] = useState([]);
  const [filter, setFilter] = useState("upcoming"); // upcoming | past | all

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

  async function deleteMeeting(id) {
    try {
      await deleteRequest(`/api/meetings/${id}`);
      setMeetings((cur) => cur.filter((m) => m.id !== id));
      pushToast("Termin gel\u00f6scht", "success");
    } catch (error) {
      pushToast(`Fehler: ${error.message}`, "danger");
    }
  }

  const collisionIds = new Set(collisions.flatMap((c) => [c.meeting_1, c.meeting_2]));

  const filtered = meetings.filter((m) => {
    if (filter === "upcoming") return !isPast(m.meeting_date);
    if (filter === "past") return isPast(m.meeting_date);
    return true;
  });

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
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <PageHeader title="Kalender" subtitle={`${meetings.length} Termine`} />
        <div className="flex flex-wrap items-center gap-2">
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
          <LinkButton
            size="sm"
            href={apiUrl("/api/meetings/export.ics")}
            target="_blank"
            rel="noreferrer"
          >
            <Download size={14} />
            ICS Export
          </LinkButton>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="Keine Termine"
          description={filter === "upcoming"
            ? "Keine kommenden Termine. Termine werden automatisch aus E-Mails und Bewerbungen erkannt."
            : "Keine Termine im gew\u00e4hlten Zeitraum."
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
                  return (
                    <Card
                      key={meeting.id}
                      className={cn(
                        "rounded-xl",
                        past && "opacity-50",
                        hasCollision && "border-amber/30 border"
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <div className={cn(
                          "mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg shrink-0",
                          past ? "bg-white/[0.03]" : "bg-sky/10"
                        )}>
                          <CalendarClock size={18} className={past ? "text-muted/30" : "text-sky"} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-medium text-ink truncate">{meeting.title}</h3>
                            <Badge tone={past ? "neutral" : "sky"}>{meetingTypeLabel(meeting.meeting_type)}</Badge>
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
                        <div className="flex shrink-0 items-center gap-1">
                          {meeting.meeting_url && (
                            <a
                              href={meeting.meeting_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-lg p-1.5 text-muted/30 hover:text-sky transition-colors"
                              title="Meeting-Link \u00f6ffnen"
                            >
                              <ExternalLink size={14} />
                            </a>
                          )}
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
                            title="Termin l\u00f6schen"
                          >
                            <Trash2 size={14} />
                          </button>
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
