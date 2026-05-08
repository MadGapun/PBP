import {
  Briefcase,
  ChevronRight,
  Download,
  ExternalLink,
  Mail,
  Phone,
  Plus,
  Search,
  Trash2,
  UsersRound,
  X,
} from "lucide-react";
import { startTransition, useEffect, useState } from "react";
import { useApp } from "@/app-context";
import { api, postJson, putJson, deleteRequest } from "@/api";
import { Button, Card, Field, Modal, TextInput, LoadingPanel } from "@/components/ui";

// v1.7.0-beta.10 (#563): Kontaktdatenbank-Frontend.
// Designprinzip: End-User wird gut gefuehrt — Empty States erklaeren, was
// Kontakte sind. Erst-Aktion-Buttons. Tags als vordefinierte + freie Eingabe.

const ROLE_OPTIONS = [
  { value: "recruiter", label: "Recruiter" },
  { value: "headhunter", label: "Headhunter" },
  { value: "hiring_manager", label: "Hiring Manager" },
  { value: "interviewer", label: "Interviewer" },
  { value: "hr", label: "HR" },
  { value: "kollege", label: "Kollege" },
  { value: "mentor", label: "Mentor" },
  { value: "sonstiges", label: "Sonstiges" },
];

const ROLE_LABELS = Object.fromEntries(ROLE_OPTIONS.map((o) => [o.value, o.label]));

// v1.7.0-beta.39 (#608): Categories-Cache als Modul-State (1x pro Session
// nachgeladen, refreshen bei Aenderungen via window-Event).
let _categoriesCache = null;
const CATEGORIES_EVENT = "pbp-contact-categories-changed";

async function loadCategories() {
  if (_categoriesCache !== null) return _categoriesCache;
  try {
    const r = await api("/api/contacts/categories");
    _categoriesCache = r?.categories || [];
  } catch {
    _categoriesCache = [];
  }
  return _categoriesCache;
}

function invalidateCategoriesCache() {
  _categoriesCache = null;
  window.dispatchEvent(new CustomEvent(CATEGORIES_EVENT));
}

function useCategories() {
  const [cats, setCats] = useState(_categoriesCache || []);
  useEffect(() => {
    let cancelled = false;
    if (_categoriesCache === null) {
      loadCategories().then((c) => { if (!cancelled) setCats(c); });
    }
    const handler = () => {
      loadCategories().then((c) => { if (!cancelled) setCats(c); });
    };
    window.addEventListener(CATEGORIES_EVENT, handler);
    return () => {
      cancelled = true;
      window.removeEventListener(CATEGORIES_EVENT, handler);
    };
  }, []);
  return cats;
}

function RoleChip({ role }) {
  const cats = useCategories();
  const cat = cats.find((c) => c.slug === role);
  const label = cat?.name || ROLE_LABELS[role] || role;
  // v1.7.0-beta.39 (#608): Farbe aus Kategorie statt fest sky
  const color = cat?.color;
  if (color) {
    return (
      <span
        className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
        style={{
          backgroundColor: color + "26",  // 15% Alpha
          color: color,
        }}
      >
        {label}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-sky/15 text-sky px-2 py-0.5 text-[10px] font-medium">
      {label}
    </span>
  );
}

function ContactCard({ contact, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="glass-card text-left rounded-xl px-4 py-3 hover:bg-white/[0.04] transition-colors w-full"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-[15px] font-semibold text-ink truncate">{contact.full_name}</p>
          {contact.position && contact.company && (
            <p className="text-[12px] text-muted/60 truncate">
              {contact.position} · {contact.company}
            </p>
          )}
          {!contact.position && contact.company && (
            <p className="text-[12px] text-muted/60 truncate">{contact.company}</p>
          )}
          <div className="mt-1.5 flex flex-wrap gap-1">
            {(contact.tags || []).slice(0, 3).map((tag) => (
              <RoleChip key={tag} role={tag} />
            ))}
            {(contact.tags || []).length > 3 && (
              <span className="text-[10px] text-muted/40">+{contact.tags.length - 3}</span>
            )}
          </div>
        </div>
        <ChevronRight size={16} className="text-muted/30 shrink-0 mt-0.5" />
      </div>
    </button>
  );
}

function ContactDialog({ contact, onClose, onSaved, onDeleted, pushToast }) {
  const isEdit = Boolean(contact?.id);
  const [form, setForm] = useState(() => ({
    full_name: contact?.full_name || "",
    email: contact?.email || "",
    phone: contact?.phone || "",
    company: contact?.company || "",
    position: contact?.position || "",
    linkedin_url: contact?.linkedin_url || "",
    tags: contact?.tags || [],
    notes: contact?.notes || "",
  }));
  const [linkedItems, setLinkedItems] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isEdit) return;
    api(`/api/contacts/${contact.id}/links`).catch(() => null).then((data) => {
      if (data?.links) setLinkedItems(data.links);
    });
  }, [contact?.id]);

  function toggleTag(value) {
    setForm((f) => ({
      ...f,
      tags: f.tags.includes(value)
        ? f.tags.filter((t) => t !== value)
        : [...f.tags, value],
    }));
  }

  async function handleSave() {
    if (!form.full_name.trim()) {
      pushToast("Name ist Pflicht.", "danger");
      return;
    }
    setSaving(true);
    try {
      if (isEdit) {
        await putJson(`/api/contacts/${contact.id}`, form);
      } else {
        await postJson("/api/contacts", form);
      }
      pushToast(isEdit ? "Kontakt aktualisiert" : "Kontakt angelegt", "success");
      onSaved?.();
      onClose();
    } catch (err) {
      pushToast(`Speichern fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Kontakt „${contact.full_name}" wirklich loeschen?`)) return;
    try {
      await deleteRequest(`/api/contacts/${contact.id}`);
      pushToast("Kontakt geloescht", "success");
      onDeleted?.();
      onClose();
    } catch (err) {
      pushToast(`Loeschen fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  return (
    <Modal
      open
      title={isEdit ? "Kontakt bearbeiten" : "Neuer Kontakt"}
      onClose={onClose}
    >
      <div className="space-y-3">
        <Field label="Name" required>
          <TextInput
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="z.B. Maria Mustermann"
          />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="E-Mail">
            <TextInput
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="maria@firma.de"
            />
          </Field>
          <Field label="Telefon">
            <TextInput
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+49 ..."
            />
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Firma">
            <TextInput
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
              placeholder="z.B. TestCorp GmbH"
            />
          </Field>
          <Field label="Position">
            <TextInput
              value={form.position}
              onChange={(e) => setForm({ ...form, position: e.target.value })}
              placeholder="z.B. Talent Acquisition Lead"
            />
          </Field>
        </div>
        <Field label="LinkedIn">
          <div className="flex items-stretch gap-2">
            <TextInput
              className="flex-1"
              value={form.linkedin_url}
              onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
              placeholder="https://linkedin.com/in/..."
            />
            {/* v1.7.0-beta.21: Wenn LinkedIn-URL gesetzt → Daten via
                Claude-in-Chrome holen. LinkedIn blockt direkten Scraping;
                der Prompt-Block muss in Claude eingefuegt werden. */}
            {form.linkedin_url && form.linkedin_url.includes("linkedin.com/in/") && (
              <button
                type="button"
                onClick={async () => {
                  try {
                    const res = await postJson("/api/contacts/enrich-from-linkedin", {
                      contact_id: contact?.id || "",
                      linkedin_url: form.linkedin_url,
                    });
                    if (res?.prompt) {
                      try {
                        await navigator.clipboard.writeText(res.prompt);
                        pushToast(
                          "Prompt in Zwischenablage. In Claude einfuegen — der eingeloggte Chrome-Tab holt die LinkedIn-Daten.",
                          "success",
                          { duration: 8000 }
                        );
                      } catch {
                        pushToast("Prompt erzeugt. Bitte aus dem Backend-Response kopieren.", "info");
                      }
                    }
                  } catch (err) {
                    pushToast(`Anreichern fehlgeschlagen: ${err.message}`, "danger");
                  }
                }}
                className="rounded-lg border border-sky/20 bg-sky/[0.08] px-3 text-[12px] text-sky hover:bg-sky/[0.15] whitespace-nowrap"
                title="LinkedIn-Daten via Claude-in-Chrome holen"
              >
                Daten holen
              </button>
            )}
          </div>
          {form.linkedin_url && form.linkedin_url.includes("linkedin.com/in/") && (
            <p className="mt-1 text-[11px] text-muted/50">
              <span className="text-sky">„Daten holen"</span> erzeugt einen Claude-Prompt.
              Claude oeffnet das Profil im eingeloggten Chrome-Tab und liest Name/Position/Firma.
            </p>
          )}
        </Field>

        <div>
          <p className="text-[11px] font-semibold text-muted/60 mb-1.5 uppercase tracking-[0.1em]">
            Rollen / Tags
          </p>
          <p className="text-[11px] text-muted/50 mb-2">
            Was diese Person fuer dich ist. Mehrere moeglich — z.B. „Recruiter" + „HR".
          </p>
          <div className="flex flex-wrap gap-1.5">
            {ROLE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleTag(opt.value)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  form.tags.includes(opt.value)
                    ? "bg-sky/20 text-sky"
                    : "bg-white/[0.03] text-muted/60 hover:bg-white/[0.07]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <Field label="Notizen">
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={3}
            className="w-full rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-sm text-ink placeholder-muted/40 focus:border-sky/40 focus:outline-none"
            placeholder="Wie habt ihr euch kennengelernt, was ist wichtig zu wissen..."
          />
        </Field>

        {isEdit && linkedItems.length > 0 && (
          <div className="border-t border-white/5 pt-3">
            <p className="text-[11px] font-semibold text-muted/60 mb-2 uppercase tracking-[0.1em]">
              Verknuepfungen ({linkedItems.length})
            </p>
            <ul className="space-y-1 text-[12px] text-muted/70">
              {linkedItems.slice(0, 8).map((l) => (
                <li key={l.id}>
                  <span className="text-muted/40">{l.target_kind}</span>
                  {" · "}
                  {l.role && <RoleChip role={l.role} />}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex justify-between pt-3 border-t border-white/5">
          {isEdit ? (
            <button
              type="button"
              onClick={handleDelete}
              className="text-[12px] text-coral/70 hover:text-coral inline-flex items-center gap-1"
            >
              <Trash2 size={12} /> Loeschen
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Abbrechen
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? "Speichere..." : isEdit ? "Speichern" : "Anlegen"}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// v1.7.0-beta.39 (#606): Banner mit Pending-Kontakten (von LLM extrahiert,
// warten auf User-Genehmigung). Nicht angezeigt wenn keine pending da.
function PendingContactsBanner({ pushToast, onChange }) {
  const [pending, setPending] = useState([]);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const r = await api("/api/contacts/pending");
      setPending(r?.pending || []);
    } catch {}
  }

  useEffect(() => { reload(); }, []);

  async function approve(id) {
    setBusy(true);
    try {
      await postJson(`/api/contacts/pending/${id}/approve`, {});
      pushToast("Kontakt genehmigt", "success");
      await reload();
      onChange?.();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function reject(id) {
    setBusy(true);
    try {
      await deleteRequest(`/api/contacts/pending/${id}`);
      pushToast("Kontakt verworfen", "success");
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  if (pending.length === 0) return null;

  return (
    <Card className="rounded-2xl mb-4 border-amber/30 bg-amber/[0.04]">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber/80">
            Vorschlaege von der lokalen AI
          </p>
          <p className="text-sm text-ink mt-1">
            {pending.length} Kontakt{pending.length === 1 ? "" : "e"} aus
            Bewerbungen/Mails extrahiert — warten auf deine Genehmigung
          </p>
        </div>
      </div>
      <div className="space-y-2 mt-3">
        {pending.slice(0, 10).map((c) => (
          <div key={c.id} className="glass-card p-2 flex items-center justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium text-ink">{c.full_name}</p>
              <p className="text-[11px] text-muted/60">
                {c.position && <>{c.position}</>}
                {c.position && c.company && " · "}
                {c.company}
                {c.email && (
                  <span className="ml-2 text-muted/40">{c.email}</span>
                )}
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {(c.tags || []).map((t) => <RoleChip key={t} role={t} />)}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Button size="xs" onClick={() => approve(c.id)} disabled={busy}>
                Akzeptieren
              </Button>
              <Button size="xs" variant="secondary" onClick={() => reject(c.id)} disabled={busy}>
                Verwerfen
              </Button>
            </div>
          </div>
        ))}
      </div>
      {pending.length > 10 && (
        <p className="text-[11px] text-muted/50 mt-2">
          +{pending.length - 10} weitere — genehmige diese erst, dann kommen die naechsten.
        </p>
      )}
    </Card>
  );
}


// v1.7.0-beta.39 (#608): Kategorien-Verwaltung als ausklappbare Card.
// Zeigt Liste mit Farb-Swatch + Name + Anzahl Kontakte. Inline-Edit
// (Klick auf Farbe oeffnet color-Input). Loesch-Schutz fuer is_system + zugewiesene.
function CategoryManagementSection({ pushToast }) {
  const [cats, setCats] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");

  async function reload() {
    try {
      const r = await api("/api/contacts/categories");
      setCats(r?.categories || []);
      invalidateCategoriesCache();
    } catch {}
  }

  useEffect(() => { reload(); }, []);

  async function addNew() {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      await postJson("/api/contacts/categories", { name: newName.trim() });
      pushToast(`Kategorie "${newName.trim()}" angelegt`, "success");
      setNewName("");
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function updateColor(id, color) {
    try {
      await putJson(`/api/contacts/categories/${id}`, { color });
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    }
  }

  async function updateName(id, name) {
    if (!name.trim()) return;
    try {
      await putJson(`/api/contacts/categories/${id}`, { name: name.trim() });
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    }
  }

  async function removeCat(id, name) {
    if (!confirm(`Kategorie "${name}" wirklich loeschen?`)) return;
    setBusy(true);
    try {
      const r = await fetch(`/api/contacts/categories/${id}`, { method: "DELETE" });
      const data = await r.json();
      if (!r.ok || data.fehler) {
        pushToast(data.fehler || "Loeschen fehlgeschlagen", "danger");
        return;
      }
      pushToast(`"${name}" geloescht`, "success");
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="rounded-2xl mb-4">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between"
      >
        <div className="text-left">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
            Kategorien verwalten
          </p>
          <p className="text-sm text-ink mt-1">
            {cats.length} Kategorie{cats.length === 1 ? "" : "n"} mit Farben
          </p>
        </div>
        <span className="text-muted/40 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-2">
          {cats.map((c) => (
            <div key={c.id} className="flex items-center gap-3 p-2 rounded-md hover:bg-white/[0.03]">
              <input
                type="color"
                value={c.color}
                onChange={(e) => updateColor(c.id, e.target.value)}
                className="h-7 w-10 rounded cursor-pointer border border-white/10"
                title="Farbe aendern"
              />
              <input
                type="text"
                defaultValue={c.name}
                onBlur={(e) => {
                  if (e.target.value !== c.name) updateName(c.id, e.target.value);
                }}
                className="flex-1 bg-transparent text-[13px] text-ink focus:outline-none focus:bg-white/[0.04] px-2 py-1 rounded"
              />
              <span className="text-[10px] text-muted/40 font-mono shrink-0">
                {c.contact_count} Kontakt{c.contact_count === 1 ? "" : "e"}
              </span>
              {c.is_system ? (
                <span className="text-[10px] text-muted/40 italic shrink-0">System</span>
              ) : (
                <button
                  type="button"
                  onClick={() => removeCat(c.id, c.name)}
                  disabled={busy}
                  className="text-muted/40 hover:text-coral shrink-0"
                  title="Kategorie loeschen"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}

          <div className="flex items-center gap-2 pt-3 border-t border-white/5">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addNew()}
              placeholder="Neue Kategorie (z.B. Headhunter)"
              className="flex-1 bg-white/[0.03] border border-white/10 rounded-md px-2 py-1.5 text-[12px] text-ink placeholder-muted/40 focus:border-teal/40 focus:outline-none"
            />
            <Button size="xs" onClick={addNew} disabled={busy || !newName.trim()}>
              <Plus size={12} /> Anlegen
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}


export default function ContactsPage() {
  const { reloadKey, pushToast } = useApp();
  const [loading, setLoading] = useState(true);
  const [contacts, setContacts] = useState([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [dialogContact, setDialogContact] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  // v1.7.0-beta.19: Kontakt-Import aus Bewerbungen + Mails
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (roleFilter) params.set("role", roleFilter);
      const data = await api(`/api/contacts?${params}`);
      startTransition(() => setContacts(data?.contacts || []));
    } catch (err) {
      pushToast(`Laden fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, [reloadKey, search, roleFilter]);

  function handleNew() {
    setDialogContact(null);
    setDialogOpen(true);
  }

  function handleEdit(c) {
    setDialogContact(c);
    setDialogOpen(true);
  }

  if (loading && contacts.length === 0) return <LoadingPanel label="Kontakte werden geladen..." />;

  const isEmpty = contacts.length === 0 && !search && !roleFilter;

  return (
    <div id="page-kontakte" className="page active">
      <h1 className="sr-only">Kontakte</h1>

      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-base font-semibold text-ink">Kontakte</h2>
          <p className="text-xs text-muted/60 mt-0.5">
            Personen mit Rollen und Historie ueber Bewerbungen, Stellen und Termine
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* v1.7.0-beta.19: Kontakt-Import aus Bewerbungen + Mails */}
          <Button size="sm" variant="secondary" onClick={() => setImportDialogOpen(true)}>
            <Download size={14} className="mr-1" /> Importieren
          </Button>
          <Button size="sm" onClick={handleNew}>
            <Plus size={14} className="mr-1" /> Neuer Kontakt
          </Button>
        </div>
      </div>

      {/* v1.7.0-beta.39 (#606): Pending-Banner */}
      <PendingContactsBanner pushToast={pushToast} onChange={reload} />

      {/* v1.7.0-beta.39 (#608): Kategorien-Verwaltung (collapsible) */}
      <CategoryManagementSection pushToast={pushToast} />

      {!isEmpty && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <div className="flex-1 min-w-[200px] relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/40" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Name, E-Mail, Firma..."
              className="w-full rounded-lg border border-white/8 bg-white/[0.03] pl-9 pr-3 py-2 text-[13px] text-ink placeholder-muted/40 focus:border-sky/40 focus:outline-none"
            />
          </div>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-[13px] text-ink"
          >
            <option value="">Alle Rollen</option>
            {ROLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {(search || roleFilter) && (
            <button
              type="button"
              onClick={() => { setSearch(""); setRoleFilter(""); }}
              className="text-[11px] text-muted/50 hover:text-ink underline"
            >
              zuruecksetzen
            </button>
          )}
        </div>
      )}

      {isEmpty ? (
        <Card className="rounded-2xl">
          <div className="text-center py-12">
            <UsersRound size={48} className="mx-auto text-muted/20 mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">Noch keine Kontakte</h3>
            <p className="text-sm text-muted/70 max-w-md mx-auto mb-1.5">
              Kontakte sind <strong className="text-ink/90">Personen, die mit deiner Jobsuche zu tun haben</strong> —
              Recruiter, Hiring Manager, Interviewer, Mentoren, Kollegen.
            </p>
            <p className="text-sm text-muted/70 max-w-md mx-auto mb-6">
              Du kannst sie spaeter mit Bewerbungen oder Terminen verknuepfen, um die
              Historie pro Person zu sehen.
            </p>
            <Button onClick={handleNew}>
              <Plus size={14} className="mr-1.5" />
              Ersten Kontakt anlegen
            </Button>
          </div>
        </Card>
      ) : contacts.length === 0 ? (
        <Card className="rounded-2xl">
          <div className="py-8 text-center text-muted/60">
            <p className="text-sm">Keine Kontakte mit diesen Filtern.</p>
            <button
              type="button"
              onClick={() => { setSearch(""); setRoleFilter(""); }}
              className="text-[12px] text-sky hover:underline mt-2"
            >
              Filter zuruecksetzen
            </button>
          </div>
        </Card>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {contacts.map((c) => (
            <ContactCard key={c.id} contact={c} onClick={() => handleEdit(c)} />
          ))}
        </div>
      )}

      {dialogOpen && (
        <ContactDialog
          contact={dialogContact}
          onClose={() => setDialogOpen(false)}
          onSaved={reload}
          onDeleted={reload}
          pushToast={pushToast}
        />
      )}

      {importDialogOpen && (
        <ImportDiscoverDialog
          onClose={() => setImportDialogOpen(false)}
          onImported={(n) => {
            pushToast(`${n} Kontakte importiert.`, "success");
            reload();
            setImportDialogOpen(false);
          }}
          pushToast={pushToast}
        />
      )}
    </div>
  );
}


// v1.7.0-beta.19: Kontakt-Import-Wizard
// Liefert eine Vorschau aller Kandidaten aus Bewerbungen + Mail-Dokumenten,
// User waehlt aus, dann Import. Kein Auto-Import — immer User-bestaetigt.
function ImportDiscoverDialog({ onClose, onImported, pushToast }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api("/api/contacts/discover")
      .then((d) => {
        if (cancelled) return;
        setData(d);
        // Default: alle aus Bewerbungen vor-selektiert (hochwertige Quelle),
        // Mails NICHT vorausgewaehlt (Heuristik, kann Muell enthalten).
        const initial = new Set();
        (d?.from_applications || []).forEach((c, i) => initial.add(`app-${i}`));
        setSelected(initial);
      })
      .catch((err) => pushToast(`Laden fehlgeschlagen: ${err.message}`, "danger"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, []);

  function toggle(key) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAll(prefix, list) {
    setSelected((prev) => {
      const next = new Set(prev);
      const allSelected = list.every((_, i) => next.has(`${prefix}-${i}`));
      list.forEach((_, i) => {
        if (allSelected) next.delete(`${prefix}-${i}`);
        else next.add(`${prefix}-${i}`);
      });
      return next;
    });
  }

  async function handleImport() {
    if (!data) return;
    const candidates = [];
    (data.from_applications || []).forEach((c, i) => {
      if (selected.has(`app-${i}`)) candidates.push(c);
    });
    (data.from_emails || []).forEach((c, i) => {
      if (selected.has(`mail-${i}`)) candidates.push(c);
    });
    if (candidates.length === 0) {
      pushToast("Keine Kontakte ausgewaehlt.", "warning");
      return;
    }
    setImporting(true);
    try {
      const res = await postJson("/api/contacts/import-discovered", { candidates });
      onImported(res?.created || 0);
    } catch (err) {
      pushToast(`Import fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setImporting(false);
    }
  }

  if (loading) {
    return (
      <Modal open onClose={onClose} title="Kontakte importieren">
        <p className="text-sm text-muted/60">Suche Kandidaten in Bewerbungen und Mails...</p>
      </Modal>
    );
  }

  const apps = data?.from_applications || [];
  const mails = data?.from_emails || [];
  const totalSelected = selected.size;

  if (apps.length === 0 && mails.length === 0) {
    return (
      <Modal open onClose={onClose} title="Kontakte importieren">
        <div className="text-sm text-muted/70 space-y-3">
          <p>
            Keine neuen Kontakt-Kandidaten gefunden. Entweder hast du noch keine
            Bewerbungen mit Ansprechpartner erfasst, oder alle gefundenen Personen
            sind bereits als Kontakt angelegt.
          </p>
          <p className="text-[12px] text-muted/50">
            Tipp: Bewerbungen mit gefuelltem Feld <em>Ansprechpartner</em> oder
            <em> Kontakt-E-Mail</em> sind die beste Quelle.
          </p>
          <div className="flex justify-end pt-2">
            <Button variant="secondary" size="sm" onClick={onClose}>Schliessen</Button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal open onClose={onClose} title="Kontakte importieren">
      <div className="space-y-4">
        <p className="text-[12px] text-muted/60">
          Aus deinen Bewerbungen und E-Mail-Dokumenten konnten {apps.length + mails.length} potenzielle Kontakte gefunden werden.
          Waehle aus, welche du als Kontakt anlegen moechtest. Bestehende Kontakte sind ausgefiltert.
        </p>

        {apps.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-ink">
                Aus Bewerbungen ({apps.length})
              </h3>
              <button
                type="button"
                onClick={() => toggleAll("app", apps)}
                className="text-[11px] text-sky hover:underline"
              >
                Alle umschalten
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1.5">
              {apps.map((c, i) => (
                <label key={`app-${i}`} className="flex items-start gap-2 p-2 rounded-md hover:bg-white/[0.03] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.has(`app-${i}`)}
                    onChange={() => toggle(`app-${i}`)}
                    className="mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-ink truncate">{c.full_name}</p>
                    <p className="text-[11px] text-muted/60 truncate">
                      {c.email && <span>{c.email}</span>}
                      {c.email && c.company && " · "}
                      {c.company && <span>{c.company}</span>}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {mails.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-ink">
                Aus Mail-Dokumenten ({mails.length})
                <span className="ml-2 text-[10px] uppercase tracking-wide text-amber/80">
                  Heuristik — pruefe sorgfaeltig
                </span>
              </h3>
              <button
                type="button"
                onClick={() => toggleAll("mail", mails)}
                className="text-[11px] text-sky hover:underline"
              >
                Alle umschalten
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1.5">
              {mails.map((c, i) => (
                <label key={`mail-${i}`} className="flex items-start gap-2 p-2 rounded-md hover:bg-white/[0.03] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.has(`mail-${i}`)}
                    onChange={() => toggle(`mail-${i}`)}
                    className="mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-ink truncate">{c.full_name}</p>
                    <p className="text-[11px] text-muted/60 truncate">
                      {c.email}
                      {c.found_in?.length > 0 && (
                        <span className="ml-2 text-muted/40">
                          aus {c.found_in.length} {c.found_in.length === 1 ? "Mail" : "Mails"}
                        </span>
                      )}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-3 border-t border-white/5">
          <p className="text-[12px] text-muted/60">
            {totalSelected} ausgewaehlt
          </p>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onClose} disabled={importing}>
              Abbrechen
            </Button>
            <Button size="sm" onClick={handleImport} disabled={importing || totalSelected === 0}>
              {importing ? "Importiere..." : `${totalSelected} importieren`}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
