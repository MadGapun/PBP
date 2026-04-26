import { Briefcase, Calendar, CalendarClock, CheckCircle2, ChevronLeft, ChevronRight, ClipboardCheck, Clock, Download, Edit3, ExternalLink, FileText, Filter, List, Lock, MapPin, Palette, Plus, Send, Settings, Trash2, Video, X, XCircle } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";

import { api, apiUrl, deleteRequest, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Button,
  Card,
  CheckboxInput,
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
  const d = new Date(dateStr);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return false;
  return d < now;
}

function isToday(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

const LOG_CATEGORIES = [
  { key: "termine", label: "Termine", icon: CalendarClock, color: "sky" },
  { key: "bewerbungen", label: "Bewerbungen", icon: Send, color: "emerald" },
  { key: "followups", label: "Follow-ups", icon: ClipboardCheck, color: "amber" },
  { key: "dokumente", label: "Dokumente", icon: FileText, color: "violet" },
];

const LOG_CATEGORY_COLORS = {
  termine: "bg-sky/10 text-sky",
  bewerbungen: "bg-emerald-500/10 text-emerald-400",
  followups: "bg-amber/10 text-amber",
  dokumente: "bg-violet-500/10 text-violet-400",
};

function loadLogCategories() {
  try {
    const stored = localStorage.getItem("pbp-calendar-categories");
    if (stored) return JSON.parse(stored);
  } catch { /* ignore */ }
  return { termine: true, bewerbungen: true, followups: true, dokumente: true };
}

// #394: View period helpers
const VIEW_MODES = [
  { id: "woche", label: "Woche" },
  { id: "monat", label: "Monat" },
  { id: "quartal", label: "Quartal" },
  { id: "halbjahr", label: "Halbjahr" },
];

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTH_NAMES = ["Januar", "Februar", "Maerz", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

function getViewRange(mode, referenceDate) {
  const d = new Date(referenceDate);
  d.setHours(0, 0, 0, 0);
  let start, end;
  if (mode === "woche") {
    const dayOfWeek = d.getDay();
    const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // Monday start
    start = new Date(d);
    start.setDate(d.getDate() + diff);
    end = new Date(start);
    end.setDate(start.getDate() + 6);
  } else if (mode === "monat") {
    start = new Date(d.getFullYear(), d.getMonth(), 1);
    end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  } else if (mode === "quartal") {
    const qStart = Math.floor(d.getMonth() / 3) * 3;
    start = new Date(d.getFullYear(), qStart, 1);
    end = new Date(d.getFullYear(), qStart + 3, 0);
  } else {
    // halbjahr
    const hStart = d.getMonth() < 6 ? 0 : 6;
    start = new Date(d.getFullYear(), hStart, 1);
    end = new Date(d.getFullYear(), hStart + 6, 0);
  }
  return { start, end };
}

function navigateViewPeriod(mode, referenceDate, direction) {
  const d = new Date(referenceDate);
  if (mode === "woche") d.setDate(d.getDate() + direction * 7);
  else if (mode === "monat") d.setMonth(d.getMonth() + direction);
  else if (mode === "quartal") d.setMonth(d.getMonth() + direction * 3);
  else d.setMonth(d.getMonth() + direction * 6);
  return d;
}

function formatViewLabel(mode, range) {
  const opts = { day: "2-digit", month: "2-digit", year: "numeric" };
  const fmt = (d) => d.toLocaleDateString("de-DE", opts);
  if (mode === "woche") return `${fmt(range.start)} – ${fmt(range.end)}`;
  if (mode === "monat") return range.start.toLocaleDateString("de-DE", { month: "long", year: "numeric" });
  if (mode === "quartal") {
    const q = Math.floor(range.start.getMonth() / 3) + 1;
    return `Q${q} ${range.start.getFullYear()}`;
  }
  const h = range.start.getMonth() < 6 ? 1 : 2;
  return `H${h} ${range.start.getFullYear()}`;
}

function isInRange(dateStr, range) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  d.setHours(0, 0, 0, 0);
  return d >= range.start && d <= range.end;
}

// Empty meeting form
function emptyMeeting(dateStr) {
  const date = dateStr || new Date().toISOString().slice(0, 16);
  return {
    title: "", meeting_date: date,
    meeting_type: "sonstiges", location: "", notes: "",
    application_id: "", duration_minutes: 60, is_private: false, category_id: "",
  };
}

// Generate calendar grid days for a single month
function getMonthGrid(year, month) {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startDow = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1; // Monday=0
  const days = [];

  // Padding from previous month
  for (let i = startDow - 1; i >= 0; i--) {
    const d = new Date(year, month, -i);
    days.push({ date: d, isCurrentMonth: false });
  }
  // Current month days
  for (let i = 1; i <= lastDay.getDate(); i++) {
    days.push({ date: new Date(year, month, i), isCurrentMonth: true });
  }
  // Padding to fill last week
  while (days.length % 7 !== 0) {
    const d = new Date(year, month + 1, days.length - startDow - lastDay.getDate() + 1);
    days.push({ date: d, isCurrentMonth: false });
  }
  return days;
}

function dateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Calendar grid component for a single month
function MonthGrid({ year, month, meetingsByDate, onDayClick, onMeetingClick, compact, collisionIds }) {
  const days = getMonthGrid(year, month);
  const todayKey = dateKey(new Date());

  return (
    <div>
      {compact && (
        <h3 className="mb-2 text-xs font-semibold text-muted/50">{MONTH_NAMES[month]} {year}</h3>
      )}
      <div className="grid grid-cols-7 gap-px rounded-xl overflow-hidden border border-white/[0.06]">
        {/* Day name header */}
        {DAY_NAMES.map((name) => (
          <div key={name} className="bg-white/[0.03] px-1 py-1.5 text-center text-[10px] font-semibold text-muted/40 uppercase">
            {name}
          </div>
        ))}
        {/* Day cells */}
        {days.map((day, idx) => {
          const key = dateKey(day.date);
          const meetings = meetingsByDate[key] || [];
          const today = key === todayKey;
          const past = day.date < new Date() && !today;
          return (
            <div
              key={idx}
              className={cn(
                "relative cursor-pointer transition-colors",
                compact ? "min-h-[2rem] p-0.5" : "min-h-[5rem] p-1.5",
                day.isCurrentMonth ? "bg-white/[0.015]" : "bg-transparent",
                today && "bg-sky/5",
                !today && "hover:bg-white/[0.04]",
              )}
              onClick={() => onDayClick(day.date)}
            >
              <span className={cn(
                "text-[11px] font-medium",
                today ? "inline-flex h-5 w-5 items-center justify-center rounded-full bg-sky text-shell font-bold" : "",
                !today && day.isCurrentMonth ? (past ? "text-muted/30" : "text-ink/70") : "",
                !today && !day.isCurrentMonth ? "text-muted/15" : "",
              )}>
                {day.date.getDate()}
              </span>
              {!compact && meetings.length > 0 && (
                <div className="mt-0.5 space-y-0.5">
                  {meetings.slice(0, 3).map((m) => {
                    const hasCollision = collisionIds.has(m.id);
                    const catColor = m.category_color || (m.is_private ? "#6b7280" : m.is_follow_up ? "#f59e0b" : "#0ea5e9");
                    return (
                      <button
                        key={m.id}
                        type="button"
                        className={cn(
                          "block w-full truncate rounded px-1 py-px text-left text-[10px] font-medium transition-colors hover:brightness-125",
                          hasCollision && "ring-1 ring-amber/50"
                        )}
                        style={{ backgroundColor: `${catColor}20`, color: catColor }}
                        onClick={(e) => { e.stopPropagation(); onMeetingClick(m); }}
                        title={`${m.is_private ? "Geblockt" : m.title} — ${formatDateTime(m.meeting_date)}`}
                      >
                        {m.is_private ? "Geblockt" : m.title}
                      </button>
                    );
                  })}
                  {meetings.length > 3 && (
                    <span className="block text-[9px] text-muted/40 px-1">+{meetings.length - 3}</span>
                  )}
                </div>
              )}
              {compact && meetings.length > 0 && (
                <div className="absolute bottom-0.5 left-1/2 flex -translate-x-1/2 gap-0.5">
                  {meetings.slice(0, 3).map((m) => (
                    <span key={m.id} className="inline-block h-1 w-1 rounded-full" style={{ backgroundColor: m.category_color || (m.is_private ? "#6b7280" : "#0ea5e9") }} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const { reloadKey, pushToast, navigateTo, copyPrompt } = useApp();
  const [loading, setLoading] = useState(true);
  const [meetings, setMeetings] = useState([]);
  const [collisions, setCollisions] = useState([]);
  const [categories, setCategories] = useState([]); // meeting categories (#417)
  const [applications, setApplications] = useState([]); // for linking (#418)
  const [filter, setFilter] = useState("all"); // all | upcoming | past
  const [viewMode, setViewMode] = useState("kalender");
  const [calendarView, setCalendarView] = useState("monat"); // #394
  const [viewRef, setViewRef] = useState(new Date()); // reference date for navigation
  const [logCategories, setLogCategories] = useState(loadLogCategories);
  const [activityLog, setActivityLog] = useState([]);
  const [logDays, setLogDays] = useState(90);
  const [logLoading, setLogLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState(() => {
    try {
      const stored = localStorage.getItem("pbp-meeting-cat-filter");
      if (stored) return JSON.parse(stored);
    } catch { /* ignore */ }
    return {};
  });
  const [editMeeting, setEditMeeting] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [categoryManager, setCategoryManager] = useState(false);
  const [newCategory, setNewCategory] = useState({ name: "", color: "#3b82f6", show_in_stats: true });

  // Listen for sidebar navigation events
  useEffect(() => {
    function handleCalNav(e) {
      const { action } = e.detail || {};
      if (action === "cal-view-kalender") setViewMode("kalender");
      else if (action === "cal-view-log") setViewMode("log");
      else if (action === "cal-period-woche") { setCalendarView("woche"); setViewRef(new Date()); }
      else if (action === "cal-period-monat") { setCalendarView("monat"); setViewRef(new Date()); }
      else if (action === "cal-period-quartal") { setCalendarView("quartal"); setViewRef(new Date()); }
      else if (action === "cal-period-halbjahr") { setCalendarView("halbjahr"); setViewRef(new Date()); }
      else if (action === "cal-filter-all") setFilter("all");
      else if (action === "cal-filter-upcoming") setFilter("upcoming");
      else if (action === "cal-filter-past") setFilter("past");
    }
    document.addEventListener("cal-nav", handleCalNav);
    return () => document.removeEventListener("cal-nav", handleCalNav);
  }, []);

  // Update sidebar active states
  useEffect(() => {
    document.querySelectorAll("[data-cal-action]").forEach((btn) => {
      const action = btn.dataset.calAction;
      const isActive =
        action === `cal-view-${viewMode}` ||
        action === `cal-period-${calendarView}` ||
        action === `cal-filter-${filter}`;
      btn.classList.toggle("bg-white/[0.06]", isActive);
      btn.classList.toggle("text-ink", isActive);
      btn.classList.toggle("text-muted/60", !isActive);
    });
  }, [viewMode, calendarView, filter]);

  const loadData = useEffectEvent(async () => {
    try {
      const [calData, appsData] = await Promise.all([
        api("/api/meetings/calendar?days=365"),
        api("/api/applications"),
      ]);
      setMeetings(calData?.meetings || []);
      setCollisions(calData?.collisions || []);
      setCategories(calData?.categories || []);
      setApplications(appsData?.applications || []);
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
      const activeCats = Object.entries(logCategories).filter(([, v]) => v).map(([k]) => k).join(",");
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
  }, [viewMode, logDays, logCategories, reloadKey]);

  function toggleLogCategory(key) {
    setLogCategories((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem("pbp-calendar-categories", JSON.stringify(next));
      return next;
    });
  }

  function toggleCategoryFilter(catId) {
    setCategoryFilter((prev) => {
      const next = { ...prev, [catId]: prev[catId] === false ? true : false };
      localStorage.setItem("pbp-meeting-cat-filter", JSON.stringify(next));
      return next;
    });
  }

  async function confirmDeleteMeeting() {
    if (!deleteConfirm) return;
    try {
      await deleteRequest(`/api/meetings/${deleteConfirm.id}`);
      setMeetings((cur) => cur.filter((m) => m.id !== deleteConfirm.id));
      pushToast("Termin geloescht", "success");
      setDeleteConfirm(null);
    } catch (error) {
      pushToast(`Fehler: ${error.message}`, "danger");
    }
  }

  async function saveMeeting() {
    if (!editMeeting) return;
    const isNew = editMeeting._isNew;
    const payload = {
      title: editMeeting.title,
      meeting_date: editMeeting.meeting_date,
      meeting_type: editMeeting.meeting_type,
      location: editMeeting.location || "",
      notes: editMeeting.notes || "",
      application_id: editMeeting.application_id || null,
      is_private: editMeeting.is_private || false,
      duration_minutes: editMeeting.duration_minutes ? Number(editMeeting.duration_minutes) : null,
      category_id: editMeeting.category_id || null,
    };
    if (payload.duration_minutes && payload.meeting_date) {
      const start = new Date(payload.meeting_date);
      const end = new Date(start.getTime() + payload.duration_minutes * 60 * 1000);
      payload.meeting_end = end.toISOString().slice(0, 16);
    }
    try {
      if (isNew) {
        await postJson("/api/meetings", payload);
        pushToast("Termin angelegt", "success");
      } else {
        await putJson(`/api/meetings/${editMeeting.id}`, payload);
        pushToast("Termin aktualisiert", "success");
      }
      setEditMeeting(null);
      loadData();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    }
  }

  async function saveNewCategory() {
    if (!newCategory.name.trim()) return;
    try {
      await postJson("/api/meeting-categories", newCategory);
      pushToast(`Kategorie "${newCategory.name}" erstellt`, "success");
      setNewCategory({ name: "", color: "#3b82f6", show_in_stats: true });
      loadData();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    }
  }

  async function deleteCategory(cat) {
    if (cat.is_system) { pushToast("Systemkategorien koennen nicht geloescht werden", "danger"); return; }
    const confirmed = window.confirm(`Kategorie "${cat.name}" loeschen? Bestehende Termine werden entkoppelt.`);
    if (!confirmed) return;
    try {
      await deleteRequest(`/api/meeting-categories/${cat.id}`, {});
      pushToast(`Kategorie "${cat.name}" geloescht`, "success");
      loadData();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    }
  }

  async function updateCategory(cat, data) {
    try {
      await putJson(`/api/meeting-categories/${cat.id}`, data);
      loadData();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    }
  }

  const collisionIds = new Set(collisions.flatMap((c) => [c.meeting_1, c.meeting_2]));
  const viewRange = getViewRange(calendarView, viewRef);

  // Filter meetings for calendar grid
  const filtered = meetings.filter((m) => {
    if (m.is_follow_up && !logCategories.followups) return false;
    if (!m.is_follow_up && !logCategories.termine) return false;
    if (m.category_id && categoryFilter[m.category_id] === false) return false;
    // Apply time filter
    if (filter === "upcoming" && isPast(m.meeting_date)) return false;
    if (filter === "past" && !isPast(m.meeting_date)) return false;
    return true;
  });

  // Group meetings by date for calendar grid
  const meetingsByDate = {};
  for (const m of filtered) {
    const key = (m.meeting_date || "").slice(0, 10);
    if (!meetingsByDate[key]) meetingsByDate[key] = [];
    meetingsByDate[key].push(m);
  }

  // Filtered meetings that are in the current view range (for the list below the grid)
  const rangeFiltered = filtered.filter((m) => isInRange(m.meeting_date, viewRange));
  const grouped = {};
  for (const m of rangeFiltered) {
    const date = (m.meeting_date || "").slice(0, 10);
    if (!grouped[date]) grouped[date] = [];
    grouped[date].push(m);
  }
  const sortedDates = Object.keys(grouped).sort();

  function handleDayClick(date) {
    const isoDate = `${dateKey(date)}T09:00`;
    setEditMeeting({ ...emptyMeeting(isoDate), _isNew: true });
  }

  function handleMeetingClick(meeting) {
    if (meeting.application_id) {
      navigateTo("bewerbungen", { highlight: meeting.application_id });
    } else {
      setEditMeeting({ ...meeting, _isNew: false });
    }
  }

  // Generate months for multi-month views (quartal/halbjahr)
  function getMonthsInRange() {
    const months = [];
    const d = new Date(viewRange.start);
    while (d <= viewRange.end) {
      months.push({ year: d.getFullYear(), month: d.getMonth() });
      d.setMonth(d.getMonth() + 1);
    }
    return months;
  }

  if (loading) return <LoadingPanel />;

  return (
    <div id="page-kalender" className="page active">
      {/* Header: compact with essential controls */}
      <div className="mb-4 flex flex-wrap flex-row-reverse items-center justify-between gap-3">
        <PageHeader title="Kalender" subtitle={`${meetings.length} Termine`} />
        <div className="flex flex-wrap items-center gap-2">
          {/* Navigation arrows + label */}
          <button type="button" onClick={() => setViewRef((d) => navigateViewPeriod(calendarView, d, -1))} className="rounded-lg p-1.5 text-muted/40 hover:text-ink hover:bg-white/[0.04]">
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm font-medium text-ink min-w-[140px] text-center">
            {viewMode === "kalender" ? formatViewLabel(calendarView, viewRange) : `Letzten ${logDays} Tage`}
          </span>
          <button type="button" onClick={() => setViewRef((d) => navigateViewPeriod(calendarView, d, 1))} className="rounded-lg p-1.5 text-muted/40 hover:text-ink hover:bg-white/[0.04]">
            <ChevronRight size={16} />
          </button>
          <button type="button" onClick={() => setViewRef(new Date())} className="rounded-lg px-2 py-1 text-xs text-muted/40 hover:text-sky hover:bg-white/[0.04]">
            Heute
          </button>
          <span className="mx-1 h-4 w-px bg-white/10" />
          <Button size="sm" variant="ghost" onClick={() => setCategoryManager(true)}>
            <Settings size={12} /> Kategorien
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditMeeting({ ...emptyMeeting(), _isNew: true })}>
            <Plus size={12} /> Neuer Termin
          </Button>
          <LinkButton size="sm" href={apiUrl("/api/meetings/export.ics")} target="_blank" rel="noreferrer">
            <Download size={14} /> ICS
          </LinkButton>
        </div>
      </div>

      {/* Category filter + log toggles (inline, below header) */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {viewMode === "log" && LOG_CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const active = logCategories[cat.key];
          return (
            <button
              key={cat.key}
              type="button"
              onClick={() => toggleLogCategory(cat.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors",
                active ? LOG_CATEGORY_COLORS[cat.key] : "text-muted/30 bg-white/[0.02] line-through"
              )}
            >
              <Icon size={12} />
              {cat.label}
            </button>
          );
        })}
        {viewMode === "kalender" && categories.length > 0 && (
          <>
            {categories.map((cat) => {
              const hidden = categoryFilter[cat.id] === false;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => toggleCategoryFilter(cat.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors",
                    hidden ? "text-muted/30 bg-white/[0.02] line-through" : "bg-white/[0.05] text-ink"
                  )}
                >
                  <span className="inline-block w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: cat.color || "#3b82f6" }} />
                  {cat.name}
                </button>
              );
            })}
          </>
        )}
      </div>

      {/* Modals */}
      {editMeeting && (
        <Modal open={true} title={editMeeting._isNew ? "Neuen Termin anlegen" : "Termin bearbeiten"} onClose={() => setEditMeeting(null)}>
          <div className="grid gap-4">
            <Field label="Titel *">
              <TextInput value={editMeeting.title} onChange={(e) => setEditMeeting((p) => ({ ...p, title: e.target.value }))} placeholder="z.B. Interview bei Firma XY" />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Datum & Uhrzeit *">
                <TextInput type="datetime-local" value={editMeeting.meeting_date} onChange={(e) => setEditMeeting((p) => ({ ...p, meeting_date: e.target.value }))} />
              </Field>
              <Field label="Dauer (Minuten)">
                <TextInput type="number" min="5" step="5" value={editMeeting.duration_minutes || ""} onChange={(e) => setEditMeeting((p) => ({ ...p, duration_minutes: e.target.value }))} placeholder="60" />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Typ">
                <SelectInput value={editMeeting.meeting_type} onChange={(e) => setEditMeeting((p) => ({ ...p, meeting_type: e.target.value }))}>
                  {Object.entries(MEETING_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </SelectInput>
              </Field>
              <Field label="Kategorie">
                <SelectInput value={editMeeting.category_id || ""} onChange={(e) => setEditMeeting((p) => ({ ...p, category_id: e.target.value }))}>
                  <option value="">Keine</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </SelectInput>
              </Field>
            </div>
            <Field label="Bewerbung verknuepfen (optional)">
              <SelectInput value={editMeeting.application_id || ""} onChange={(e) => setEditMeeting((p) => ({ ...p, application_id: e.target.value }))}>
                <option value="">Keine Verknuepfung</option>
                {applications.map((app) => (
                  <option key={app.id} value={app.id}>
                    {app.company || "Unbekannt"} — {app.title || "Keine Stelle"}
                  </option>
                ))}
              </SelectInput>
            </Field>
            <Field label="Ort (optional)">
              <TextInput value={editMeeting.location || ""} onChange={(e) => setEditMeeting((p) => ({ ...p, location: e.target.value }))} placeholder="z.B. Zoom, Buero, ..." />
            </Field>
            <Field label="Notizen (optional)">
              <TextArea value={editMeeting.notes || ""} onChange={(e) => setEditMeeting((p) => ({ ...p, notes: e.target.value }))} rows={2} />
            </Field>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
                <CheckboxInput
                  checked={editMeeting.is_private || false}
                  onChange={(e) => setEditMeeting((p) => ({ ...p, is_private: e.target.checked }))}
                />
                Privater Termin (wird als &ldquo;Geblockt&rdquo; angezeigt, nicht in Statistik)
              </label>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setEditMeeting(null)}>Abbrechen</Button>
              <Button disabled={!editMeeting.title || !editMeeting.meeting_date} onClick={saveMeeting}>
                {editMeeting._isNew ? "Anlegen" : "Speichern"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {deleteConfirm && (
        <Modal open={true} title="Termin loeschen" onClose={() => setDeleteConfirm(null)}>
          <p className="text-sm text-muted mb-2">
            Soll der Termin <strong className="text-ink">&ldquo;{deleteConfirm.title}&rdquo;</strong> wirklich geloescht werden?
          </p>
          {deleteConfirm.application_id && (
            <p className="text-xs text-amber mb-4">
              Dieser Termin ist mit einer Bewerbung verknuepft. Der Timeline-Eintrag wird ebenfalls entfernt.
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteConfirm(null)}>Abbrechen</Button>
            <Button variant="danger" onClick={confirmDeleteMeeting}>Endgueltig loeschen</Button>
          </div>
        </Modal>
      )}

      {categoryManager && (
        <Modal open={true} title="Termin-Kategorien verwalten" onClose={() => setCategoryManager(false)}>
          <div className="grid gap-3">
            {categories.map((cat) => (
              <div key={cat.id} className="flex items-center gap-3 rounded-xl border border-white/[0.05] px-4 py-2.5">
                <input
                  type="color"
                  value={cat.color || "#3b82f6"}
                  onChange={(e) => updateCategory(cat, { color: e.target.value })}
                  className="h-6 w-6 rounded cursor-pointer border-0 bg-transparent"
                  disabled={cat.is_system}
                />
                <span className="flex-1 text-sm text-ink font-medium">
                  {cat.name}
                  {cat.is_system ? <Badge tone="neutral" className="ml-2">System</Badge> : null}
                </span>
                <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer">
                  <CheckboxInput
                    checked={cat.show_in_stats !== 0}
                    onChange={(e) => updateCategory(cat, { show_in_stats: e.target.checked ? 1 : 0 })}
                  />
                  Statistik
                </label>
                {!cat.is_system && (
                  <button type="button" onClick={() => deleteCategory(cat)} className="text-muted/30 hover:text-coral p-1">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
            <div className="border-t border-white/5 pt-3 mt-1">
              <p className="text-xs text-muted/50 mb-2">Neue Kategorie</p>
              <div className="flex items-center gap-2">
                <input type="color" value={newCategory.color} onChange={(e) => setNewCategory((p) => ({ ...p, color: e.target.value }))} className="h-8 w-8 rounded cursor-pointer border-0 bg-transparent" />
                <TextInput value={newCategory.name} onChange={(e) => setNewCategory((p) => ({ ...p, name: e.target.value }))} placeholder="z.B. Networking" className="flex-1" />
                <label className="flex items-center gap-1 text-xs text-muted cursor-pointer whitespace-nowrap">
                  <CheckboxInput checked={newCategory.show_in_stats} onChange={(e) => setNewCategory((p) => ({ ...p, show_in_stats: e.target.checked }))} />
                  Statistik
                </label>
                <Button size="sm" disabled={!newCategory.name.trim()} onClick={saveNewCategory}>Erstellen</Button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Main content */}
      {viewMode === "log" ? (
        /* Activity Log View */
        logLoading ? <LoadingPanel /> : activityLog.length === 0 ? (
          <EmptyState title="Keine Aktivitaeten" description={`Keine Eintraege in den letzten ${logDays} Tagen.`} />
        ) : (
          <div className="grid gap-1.5">
            {activityLog.map((entry) => {
              const catDef = LOG_CATEGORIES.find((c) => c.key === entry.category);
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
                  <div className={cn("flex h-7 w-7 items-center justify-center rounded-lg shrink-0", LOG_CATEGORY_COLORS[entry.category] || "bg-white/5 text-muted/40")}>
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
      ) : (
        <>
          {/* Calendar Grid */}
          {calendarView === "monat" && (
            <MonthGrid
              year={viewRange.start.getFullYear()}
              month={viewRange.start.getMonth()}
              meetingsByDate={meetingsByDate}
              onDayClick={handleDayClick}
              onMeetingClick={handleMeetingClick}
              compact={false}
              collisionIds={collisionIds}
            />
          )}

          {calendarView === "woche" && (
            <div className="grid grid-cols-7 gap-px rounded-xl overflow-hidden border border-white/[0.06]">
              {DAY_NAMES.map((name) => (
                <div key={name} className="bg-white/[0.03] px-1 py-1.5 text-center text-[10px] font-semibold text-muted/40 uppercase">
                  {name}
                </div>
              ))}
              {(() => {
                const days = [];
                const d = new Date(viewRange.start);
                const todayKey = dateKey(new Date());
                while (d <= viewRange.end) {
                  days.push(new Date(d));
                  d.setDate(d.getDate() + 1);
                }
                return days.map((day) => {
                  const key = dateKey(day);
                  const dayMeetings = meetingsByDate[key] || [];
                  const today = key === todayKey;
                  const past = day < new Date() && !today;
                  return (
                    <div
                      key={key}
                      className={cn(
                        "min-h-[8rem] p-2 cursor-pointer transition-colors",
                        today ? "bg-sky/5" : "bg-white/[0.015] hover:bg-white/[0.04]",
                      )}
                      onClick={() => handleDayClick(day)}
                    >
                      <span className={cn(
                        "text-xs font-medium",
                        today ? "inline-flex h-5 w-5 items-center justify-center rounded-full bg-sky text-shell font-bold" : "",
                        !today && (past ? "text-muted/30" : "text-ink/70"),
                      )}>
                        {day.getDate()}
                      </span>
                      <p className="text-[9px] text-muted/30 mt-0.5">{day.toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "short" })}</p>
                      <div className="mt-1 space-y-0.5">
                        {dayMeetings.map((m) => {
                          const catColor = m.category_color || (m.is_private ? "#6b7280" : m.is_follow_up ? "#f59e0b" : "#0ea5e9");
                          return (
                            <button
                              key={m.id}
                              type="button"
                              className="block w-full truncate rounded px-1 py-px text-left text-[10px] font-medium transition-colors hover:brightness-125"
                              style={{ backgroundColor: `${catColor}20`, color: catColor }}
                              onClick={(e) => { e.stopPropagation(); handleMeetingClick(m); }}
                              title={`${m.is_private ? "Geblockt" : m.title} — ${formatDateTime(m.meeting_date)}`}
                            >
                              {m.is_private ? "Geblockt" : m.title}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          )}

          {(calendarView === "quartal" || calendarView === "halbjahr") && (
            <div className={cn("grid gap-4", calendarView === "quartal" ? "md:grid-cols-3" : "md:grid-cols-3 lg:grid-cols-3")}>
              {getMonthsInRange().map(({ year, month }) => (
                <MonthGrid
                  key={`${year}-${month}`}
                  year={year}
                  month={month}
                  meetingsByDate={meetingsByDate}
                  onDayClick={handleDayClick}
                  onMeetingClick={handleMeetingClick}
                  compact={true}
                  collisionIds={collisionIds}
                />
              ))}
            </div>
          )}

          {/* Detail list below the grid for the current view range */}
          {sortedDates.length > 0 && (
            <div className="mt-6 grid gap-4">
              <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-muted/40">
                Termine im Zeitraum ({rangeFiltered.length})
              </h2>
              {sortedDates.map((date) => (
                <div key={date}>
                  <h3 className={cn(
                    "mb-1.5 text-sm font-semibold",
                    isToday(date) ? "text-sky" : isPast(date) ? "text-muted/40" : "text-ink"
                  )}>
                    {isToday(date) ? "Heute" : formatDate(date)}
                    {isToday(date) && <span className="ml-2 text-xs font-normal text-muted/50">({formatDate(date)})</span>}
                  </h3>
                  <div className="grid gap-1.5">
                    {grouped[date].map((meeting) => {
                      const past = isPast(meeting.meeting_date);
                      const hasCollision = collisionIds.has(meeting.id);
                      const isFollowUp = meeting.is_follow_up;
                      const isPrivate = meeting.is_private;
                      const catColor = meeting.category_color || null;
                      return (
                        <Card
                          key={meeting.id}
                          className={cn(
                            "rounded-xl cursor-pointer hover:bg-white/[0.03] transition-colors",
                            past && "opacity-50",
                            hasCollision && "border-amber/30 border",
                            isPrivate && "bg-white/[0.02] border-white/[0.05] border"
                          )}
                          onClick={() => handleMeetingClick(meeting)}
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h4 className={cn("text-sm font-medium truncate", isPrivate ? "text-muted/50" : "text-ink")}>
                                  {isPrivate ? "Geblockt" : meeting.title}
                                </h4>
                                <Badge tone={past ? "neutral" : isPrivate ? "neutral" : isFollowUp ? "amber" : "sky"}>
                                  {isPrivate ? "Privat" : meetingTypeLabel(meeting.meeting_type)}
                                </Badge>
                                {meeting.category_name && !isPrivate && (
                                  <span className="rounded-lg px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: `${catColor || '#3b82f6'}20`, color: catColor || '#3b82f6' }}>
                                    {meeting.category_name}
                                  </span>
                                )}
                                {hasCollision && <Badge tone="amber">Kollision</Badge>}
                              </div>
                              {!isPrivate && (meeting.app_company || meeting.app_title) && (
                                <p className="text-xs text-muted/50 mt-0.5 truncate">
                                  {meeting.app_title}{meeting.app_company ? ` — ${meeting.app_company}` : ""}
                                </p>
                              )}
                              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted/40">
                                <span className="flex items-center gap-1">
                                  <Clock size={11} />
                                  {formatDateTime(meeting.meeting_date)}
                                  {meeting.meeting_end && ` – ${formatDateTime(meeting.meeting_end).split(", ").pop()}`}
                                  {!meeting.meeting_end && meeting.duration_minutes && ` (${meeting.duration_minutes} Min.)`}
                                </span>
                                {!isPrivate && meeting.location && (
                                  <span className="flex items-center gap-1"><MapPin size={11} />{meeting.location}</span>
                                )}
                              </div>
                            </div>
                            <div className="flex shrink-0 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                              {!isPrivate && meeting.meeting_url && (
                                <a href={meeting.meeting_url} target="_blank" rel="noreferrer" className="rounded-lg p-1.5 text-muted/30 hover:text-sky transition-colors" title="Meeting-Link oeffnen">
                                  <ExternalLink size={14} />
                                </a>
                              )}
                              {isFollowUp ? (
                                // #453 / v1.5.7: Follow-ups erledigen / hinfaellig
                                meeting.status === "geplant" && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        const id = String(meeting.id).replace(/^followup-/, "");
                                        try {
                                          await postJson(`/api/follow-ups/${id}/complete`, {});
                                          pushToast("Nachfass erledigt.", "success");
                                          loadData();
                                        } catch (err) { pushToast(`Fehler: ${err.message}`, "danger"); }
                                      }}
                                      className="rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors"
                                      title="Als erledigt markieren"
                                    >
                                      <CheckCircle2 size={14} />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        const id = String(meeting.id).replace(/^followup-/, "");
                                        try {
                                          await postJson(`/api/follow-ups/${id}/dismiss`, {});
                                          pushToast("Nachfass hinfaellig.", "success");
                                          loadData();
                                        } catch (err) { pushToast(`Fehler: ${err.message}`, "danger"); }
                                      }}
                                      className="rounded-lg p-1.5 text-muted/30 hover:text-coral transition-colors"
                                      title="Als hinfaellig markieren"
                                    >
                                      <XCircle size={14} />
                                    </button>
                                  </>
                                )
                              ) : (
                                <>
                                  {/* #457: Termin-spezifischer Interview-Prep */}
                                  {!past && ["interview", "telefoninterview", "video", "vor_ort", "kennenlernen", "zweitgespraech"].includes(meeting.meeting_type) && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        const stelle = meeting.app_title ? ` stelle="${meeting.app_title}"` : "";
                                        const firma = meeting.app_company ? ` firma="${meeting.app_company}"` : "";
                                        copyPrompt(`/interview_vorbereitung${stelle}${firma}`);
                                      }}
                                      className="rounded-lg p-1.5 text-muted/30 hover:text-amber transition-colors"
                                      title="Auf dieses Interview vorbereiten"
                                    >
                                      <Briefcase size={14} />
                                    </button>
                                  )}
                                  {/* #453 / v1.5.7: Durchgefuehrt fuer vergangene geplante Meetings */}
                                  {past && (meeting.status === "geplant" || meeting.status === "bestaetigt") && (
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        try {
                                          await putJson(`/api/meetings/${meeting.id}`, { status: "durchgefuehrt" });
                                          pushToast("Termin als durchgef\u00fchrt markiert.", "success");
                                          loadData();
                                        } catch (err) { pushToast(`Fehler: ${err.message}`, "danger"); }
                                      }}
                                      className="rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors"
                                      title="Termin hat stattgefunden"
                                    >
                                      <CheckCircle2 size={14} />
                                    </button>
                                  )}
                                  <button type="button" onClick={() => setEditMeeting({ ...meeting, _isNew: false })} className="rounded-lg p-1.5 text-muted/30 hover:text-sky transition-colors" title="Termin bearbeiten">
                                    <Edit3 size={14} />
                                  </button>
                                  <a href={apiUrl(`/api/meetings/${meeting.id}/ics`)} className="rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors" title="ICS herunterladen">
                                    <Download size={14} />
                                  </a>
                                  <button type="button" onClick={() => setDeleteConfirm(meeting)} className="rounded-lg p-1.5 text-muted/30 hover:text-coral transition-colors" title="Termin loeschen">
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
        </>
      )}
    </div>
  );
}
