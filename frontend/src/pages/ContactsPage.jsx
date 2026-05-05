import {
  Briefcase,
  ChevronRight,
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

function RoleChip({ role }) {
  const label = ROLE_LABELS[role] || role;
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
          <TextInput
            value={form.linkedin_url}
            onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
            placeholder="https://linkedin.com/in/..."
          />
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

export default function ContactsPage() {
  const { reloadKey, pushToast } = useApp();
  const [loading, setLoading] = useState(true);
  const [contacts, setContacts] = useState([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [dialogContact, setDialogContact] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

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
        <Button size="sm" onClick={handleNew}>
          <Plus size={14} className="mr-1" /> Neuer Kontakt
        </Button>
      </div>

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
    </div>
  );
}
