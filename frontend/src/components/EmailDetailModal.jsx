/**
 * E-Mail-Detailansicht — v1.7.35 (#985), zugezogen vom Dashboard.
 *
 * Nutzerhinweis vom 07.09.2026: *"E-Mails gehoert eher in den Bereich
 * Docs."* Stimmt — eine importierte Mail ist ein Dokument, und der
 * Docs-Bereich ist der Ort, an dem man Dokumente sucht.
 */
import { useState } from "react";
import { MessageSquareReply } from "lucide-react";

import { api, postJson } from "@/api";
import { Badge, Button, Card, Modal, SelectInput } from "@/components/ui";
import { formatDate } from "@/utils";

export default function EmailDetailModal({ email, applications, onClose, pushToast, onUpdate }) {
  const [assignApp, setAssignApp] = useState(email.application_id || "");
  const [applying, setApplying] = useState(false);

  async function confirmMatch() {
    if (!assignApp) return;
    try {
      await postJson(`/api/emails/${email.id}/confirm-match`, { application_id: assignApp });
      pushToast("E-Mail zugeordnet.", "success");
      onUpdate();
    } catch (err) {
      pushToast(`Zuordnung fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  async function createApplicationFromEmail() {
    try {
      const result = await postJson(`/api/emails/${email.id}/create-application`, {});
      pushToast(`Bewerbung "${result.title}" @ ${result.company} angelegt.`, "success");
      onUpdate();
    } catch (err) {
      pushToast(`Bewerbung konnte nicht angelegt werden: ${err.message}`, "danger");
    }
  }

  async function applyStatus(status) {
    setApplying(true);
    try {
      await postJson(`/api/emails/${email.id}/apply-status`, { status });
      pushToast(`Status '${status}' angewendet.`, "success");
      onUpdate();
    } catch (err) {
      pushToast(`Status konnte nicht angewendet werden: ${err.message}`, "danger");
    } finally {
      setApplying(false);
    }
  }

  async function deleteEmail() {
    try {
      await api(`/api/emails/${email.id}`, { method: "DELETE" });
      pushToast("E-Mail gelöscht.", "success");
      onUpdate();
    } catch (err) {
      pushToast(`Löschen fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  const replyTo = email.direction === "ausgang" ? email.recipients : email.sender;
  const replyMailto = buildReplyMailto(replyTo, email.subject);
  const senderMailto = buildMailto({ to: email.sender });
  const recipientsMailto = buildMailto({ to: email.recipients });

  return (
    <Modal
      open={true}
      title={email.subject || "E-Mail"}
      onClose={onClose}
      footer={
        <div className="flex justify-between">
          <Button variant="ghost" className="text-coral" onClick={deleteEmail}>Löschen</Button>
          <div className="flex gap-2">
            {replyMailto && (
              <a
                href={replyMailto}
                className="inline-flex items-center gap-1 rounded-lg bg-sky/15 px-3 py-1.5 text-sm font-semibold text-sky hover:bg-sky/25 transition-colors"
                title={`Im Mail-Client antworten an ${extractEmailAddress(replyTo)}`}
              >
                <MessageSquareReply size={14} /> Antworten
              </a>
            )}
            <Button onClick={onClose}>Schließen</Button>
          </div>
        </div>
      }
    >
      <div className="grid gap-4">
        <Card className="glass-card-soft rounded-xl shadow-none">
          <div className="grid gap-1.5 text-sm">
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">Von:</span>
              {senderMailto ? (
                <a href={senderMailto} className="text-sky hover:underline">{email.sender}</a>
              ) : (
                <span className="text-ink">{email.sender}</span>
              )}
            </div>
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">An:</span>
              {recipientsMailto ? (
                <a href={recipientsMailto} className="text-sky hover:underline">{email.recipients}</a>
              ) : (
                <span className="text-ink">{email.recipients}</span>
              )}
            </div>
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">Datum:</span>
              <span className="text-ink">{formatDate(email.sent_date)}</span>
            </div>
            <div className="flex gap-2">
              <span className="w-16 shrink-0 text-muted/50">Richtung:</span>
              <Badge tone={email.direction === "ausgang" ? "sky" : "amber"}>
                {email.direction === "ausgang" ? "Ausgehend" : "Eingehend"}
              </Badge>
            </div>
          </div>
        </Card>

        {/* Body text */}
        {email.body_text && (
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Inhalt</p>
            <div className="mt-2 max-h-60 overflow-y-auto rounded-lg bg-white/[0.02] p-3 text-sm text-muted/70 whitespace-pre-wrap">
              {email.body_text}
            </div>
          </Card>
        )}

        {/* Detected status */}
        {email.detected_status && (
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Erkannter Status</p>
            <div className="mt-2 flex items-center gap-3">
              <Badge tone="sky">{email.detected_status}</Badge>
              <span className="text-xs text-muted/50">
                Konfidenz: {Math.round((email.detected_status_confidence || 0) * 100)}%
              </span>
              {email.application_id && (
                <Button size="sm" onClick={() => applyStatus(email.detected_status)} disabled={applying}>
                  Status übernehmen
                </Button>
              )}
            </div>
          </Card>
        )}

        {/* Attachments */}
        {(email.attachments_meta || []).length > 0 && (
          <Card className="glass-card-soft rounded-xl shadow-none">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
              Anhänge ({email.attachments_meta.length})
            </p>
            <div className="mt-2 grid gap-1">
              {email.attachments_meta.map((att, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-ink">
                  <span className="text-muted/50">📎</span>
                  <span>{att.filename}</span>
                  {att.imported && <Badge tone="success">Importiert</Badge>}
                  {att.duplicate_of && <Badge tone="neutral">Duplikat</Badge>}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Assign to application */}
        <Card className="glass-card-soft rounded-xl shadow-none">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">Bewerbung zuordnen</p>
          <div className="mt-2 flex gap-2">
            <SelectInput
              className="flex-1"
              value={assignApp}
              onChange={(e) => setAssignApp(e.target.value)}
            >
              <option value="">— Nicht zugeordnet —</option>
              {(applications || []).map((app) => (
                <option key={app.id} value={app.id}>
                  {app.title} @ {app.company}
                </option>
              ))}
            </SelectInput>
            <Button size="sm" onClick={confirmMatch} disabled={!assignApp}>
              Zuordnen
            </Button>
          </div>
          {email.match_confidence > 0 && email.match_confidence < 1 && (
            <p className="mt-1 text-xs text-muted/50">
              Auto-Match Konfidenz: {Math.round(email.match_confidence * 100)}%
            </p>
          )}
          {/* #459: Bewerbung neu erstellen, wenn keine passt */}
          {!email.application_id && (
            <div className="mt-3 border-t border-white/[0.04] pt-3">
              <p className="text-xs text-muted/50 mb-2">
                Keine passende Bewerbung? Lege eine neue aus dieser E-Mail an — Subject als Titel, Absender-Domain als Firma.
              </p>
              <Button size="sm" variant="secondary" onClick={createApplicationFromEmail}>
                Neue Bewerbung daraus erstellen
              </Button>
            </div>
          )}
        </Card>
      </div>
    </Modal>
  );
}
