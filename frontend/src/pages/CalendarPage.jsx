import { Briefcase, Calendar, CalendarClock, ChevronLeft, ChevronRight, ClipboardCheck, Clock, Download, Edit3, ExternalLink, FileText, Filter, List, Lock, MapPin, Palette, Plus, Send, Settings, Trash2, Video, X } from "lucide-react";
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

function navigateView(mode, referenceDate, direction) {
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
function emptyMeeting() {
  return {
    title: "", meeting_date: new Date().toISOString().slice(0, 16),
    meeting_type: "sonstiges", location: "", notes: "",
    application_id: "", duration_minutes: 60, is_private: false, category_id: "",
  };
}

export default function CalendarPage() {
  const { reloadKey, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [meetings, setMeetings] = useState([]);
  const [collisions, setCollisions] = useState([]);
  const [categories, setCategories] = useState([]); // meeting categories (#417)
  const [applications, setApplications] = useState([]); // for linking (#418)
  const [filter, setFilter] = useState("upcoming");
  const [viewMode, setViewMode] = useState("kalender");
  const [calendarView, setCalendarView] = useState("monat"); // #394
  const [viewRef, setViewRef] = useState(new Date()); // reference date for navigation
  const [logCategories, setLogCategories] = useState(loadLogCategories);
  const [activityLog, setActivityLog] = useState([]);
  const [logDays, setLogDays] = useState(90);
  const [logLoading, setLogLoading] = useState(false);
  // Category filter: which meeting categories to show (#417)
  const [categoryFilter, setCategoryFilter] = useState(() => {
    try {
      const stored = localStorage.getItem("pbp-meeting-cat-filter");
      if (stored) return JSON.parse(stored);
    } catch { /* ignore */ }
    return {}; // empty = all visible
  });
  const [editMeeting, setEditMeeting] = useState(null); // null | { ...meeting data, _isNew: true/false }
  const [deleteConfirm, setDeleteConfirm] = useState(null); // meeting to delete
  const [categoryManager, setCategoryManager] = useState(false);
  const [newCategory, setNewCategory] = useState({ name: "", color: "#3b82f6", show_in_stats: true });

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

  // #417: Toggle meeting category filter
  function toggleCategoryFilter(catId) {
    setCategoryFilter((prev) => {
      const next = { ...prev, [catId]: prev[catId] === false ? true : false };
      // If all are true/undefined, remove all keys (= show all)
      localStorage.setItem("pbp-meeting-cat-filter", JSON.stringify(next));
      return next;
    });
  }

  // #419: Delete meeting with confirmation
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

  // #418/#419: Save meeting (create or update)
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
    // Calculate meeting_end from duration
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

  // #417: Category CRUD
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

  // #394: View range for calendar views
  const viewRange = getViewRange(calendarView, viewRef);

  // Filter meetings
  const filtered = meetings.filter((m) => {
    // Follow-up filter
    if (m.is_follow_up && !logCategories.followups) return false;
    if (!m.is_follow_up && !logCategories.termine) return false;
    // #417: Meeting category filter
    if (m.category_id && categoryFilter[m.category_id] === false) return false;
    // #394: Calendar view date range filter (in kalender mode)
    if (viewMode === "kalender") {
      if (!isInRange(m.meeting_date, viewRange)) return false;
    } else {
      // Time filter for non-view mode
      if (filter === "upcoming") return !isPast(m.meeting_date);
      if (filter === "past") return isPast(m.meeting_date);
    }
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
              {/* #394: Calendar view modes */}
              {VIEW_MODES.map((vm) => (
                <button
                  key={vm.id}
                  type="button"
                  onClick={() => { setCalendarView(vm.id); setViewRef(new Date()); }}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                    calendarView === vm.id
                      ? "bg-sky/15 text-sky"
                      : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
                  }`}
                >
                  {vm.label}
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

      {/* #394: View navigation + Category toggles + New meeting button */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {viewMode === "kalender" && (
          <>
            <button type="button" onClick={() => setViewRef((d) => navigateView(calendarView, d, -1))} className="rounded-lg p-1.5 text-muted/40 hover:text-ink hover:bg-white/[0.04]">
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm font-medium text-ink min-w-[140px] text-center">
              {formatViewLabel(calendarView, viewRange)}
            </span>
            <button type="button" onClick={() => setViewRef((d) => navigateView(calendarView, d, 1))} className="rounded-lg p-1.5 text-muted/40 hover:text-ink hover:bg-white/[0.04]">
              <ChevronRight size={16} />
            </button>
            <button type="button" onClick={() => setViewRef(new Date())} className="rounded-lg px-2 py-1 text-xs text-muted/40 hover:text-sky hover:bg-white/[0.04]">
              Heute
            </button>
            <span className="mx-1 h-4 w-px bg-white/10" />
          </>
        )}

        {/* Activity log category toggles */}
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

        {/* #417: Meeting category filter toggles */}
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
            <span className="mx-1 h-4 w-px bg-white/10" />
          </>
        )}

        {/* Category management button (#417) */}
        <Button size="sm" variant="ghost" onClick={() => setCategoryManager(true)}>
          <Settings size={12} /> Kategorien
        </Button>

        {/* New meeting button (#418) */}
        <Button size="sm" variant="ghost" onClick={() => setEditMeeting({ ...emptyMeeting(), _isNew: true })}>
          <Plus size={12} /> Neuer Termin
        </Button>
      </div>

      {/* #418/#419: Meeting create/edit modal */}
      {editMeeting && (
        <Modal title={editMeeting._isNew ? "Neuen Termin anlegen" : "Termin bearbeiten"} onClose={() => setEditMeeting(null)}>
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

      {/* #419: Delete confirmation modal */}
      {deleteConfirm && (
        <Modal title="Termin loeschen" onClose={() => setDeleteConfirm(null)}>
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

      {/* #417: Category manager modal */}
      {categoryManager && (
        <Modal title="Termin-Kategorien verwalten" onClose={() => setCategoryManager(false)}>
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
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Keine Termine"
          description="Keine Termine im gewaehlten Zeitraum."
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
                  const isPrivate = meeting.is_private;
                  const IconComp = isPrivate ? Lock : isFollowUp ? ClipboardCheck : CalendarClock;
                  const accent = isPrivate ? "neutral" : isFollowUp ? "amber" : "sky";
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
                      onClick={() => {
                        // #395: Click opens application dossier or edit dialog
                        if (isPrivate) {
                          // Private → open edit dialog
                          setEditMeeting({ ...meeting, _isNew: false });
                        } else if (meeting.application_id && !isFollowUp) {
                          navigateTo("bewerbungen", { highlight: meeting.application_id });
                        } else if (!isFollowUp) {
                          // No application link → open edit dialog
                          setEditMeeting({ ...meeting, _isNew: false });
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className={cn(
                          "mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg shrink-0",
                          past ? "bg-white/[0.03]" : isPrivate ? "bg-white/[0.04]" : isFollowUp ? "bg-amber/10" : "bg-sky/10"
                        )} style={catColor && !isPrivate ? { backgroundColor: `${catColor}20` } : undefined}>
                          <IconComp size={18} className={past ? "text-muted/30" : isPrivate ? "text-muted/40" : `text-${accent}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            {isPrivate ? (
                              <h3 className="font-medium text-muted/50">Geblockt</h3>
                            ) : (
                              <h3 className="font-medium text-ink truncate">{meeting.title}</h3>
                            )}
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
                            <p className="text-sm text-muted/50 mt-0.5 truncate">
                              {meeting.app_title}{meeting.app_company ? ` — ${meeting.app_company}` : ""}
                            </p>
                          )}
                          <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-muted/40">
                            <span className="flex items-center gap-1">
                              <Clock size={11} />
                              {formatDateTime(meeting.meeting_date)}
                              {meeting.meeting_end && ` – ${formatDateTime(meeting.meeting_end).split(", ").pop()}`}
                              {!meeting.meeting_end && meeting.duration_minutes && ` (${meeting.duration_minutes} Min.)`}
                            </span>
                            {!isPrivate && meeting.location && (
                              <span className="flex items-center gap-1">
                                <MapPin size={11} />
                                {meeting.location}
                              </span>
                            )}
                            {!isPrivate && meeting.platform && (
                              <span className="flex items-center gap-1">
                                <Video size={11} />
                                {meeting.platform}
                              </span>
                            )}
                          </div>
                          {!isPrivate && meeting.notes && (
                            <p className="mt-1.5 text-xs text-muted/40 line-clamp-2">{meeting.notes}</p>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          {!isPrivate && meeting.meeting_url && (
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
                              {/* #419: Edit button */}
                              <button
                                type="button"
                                onClick={() => setEditMeeting({ ...meeting, _isNew: false })}
                                className="rounded-lg p-1.5 text-muted/30 hover:text-sky transition-colors"
                                title="Termin bearbeiten"
                              >
                                <Edit3 size={14} />
                              </button>
                              <a
                                href={apiUrl(`/api/meetings/${meeting.id}/ics`)}
                                className="rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors"
                                title="ICS herunterladen"
                              >
                                <Download size={14} />
                              </a>
                              {/* #419: Delete with confirmation */}
                              <button
                                type="button"
                                onClick={() => setDeleteConfirm(meeting)}
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
