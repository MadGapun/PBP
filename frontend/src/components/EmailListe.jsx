/**
 * Importierte E-Mails — v1.7.35 (#985)
 *
 * Nutzerhinweis vom 07.09.2026: *"E-Mails gehoert eher in den Bereich
 * Docs."*
 *
 * Stimmt. Eine importierte Mail IST ein Dokument, und der Docs-Bereich
 * ist der Ort, an dem man Dokumente sucht. Auf dem Dashboard nahm die
 * Liste die halbe Breite neben den Top-Stellen ein, ohne dass sie dort
 * eine Frage beantwortet haette, die man auf dem Dashboard stellt.
 *
 * Die Komponente holt ihre Daten selbst, statt sie sich durchreichen zu
 * lassen — sonst muesste jede Seite, die sie zeigt, dieselbe Ladelogik
 * mitschleppen.
 */
import { useCallback, useEffect, useState } from "react";
import { Mail } from "lucide-react";

import { api } from "@/api";
import { Badge, Card } from "@/components/ui";
import { formatDate } from "@/utils";
import EmailDetailModal from "@/components/EmailDetailModal";
import EmailUploadButton from "@/components/EmailUploadButton";

export default function EmailListe({ pushToast, applications = [], anzahl = 8 }) {
  const [emails, setEmails] = useState([]);
  const [detail, setDetail] = useState(null);

  const laden = useCallback(() => {
    api("/api/emails")
      .then((d) => setEmails(Array.isArray(d) ? d : (d?.emails || [])))
      .catch(() => {});
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  const offen = emails.filter((e) => !e.application_id).length;

  return (
    <>
      <Card className="overflow-hidden rounded-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">
            <Mail size={14} className="mr-1.5 inline-block text-teal/60" />
            E-Mails
            {offen > 0 && (
              <span className="ml-1.5 rounded-full bg-amber/20 px-1.5 py-px text-[10px] font-bold text-amber">
                {offen} offen
              </span>
            )}
          </h2>
          <EmailUploadButton pushToast={pushToast} />
        </div>
        <div className="mt-3 grid gap-1.5">
          {emails.length > 0 ? (
            emails.slice(0, anzahl).map((em) => (
              <button
                key={em.id}
                type="button"
                className="flex w-full min-w-0 items-center gap-2 rounded-lg border border-white/[0.04] px-3 py-2 text-left transition hover:bg-white/[0.04]"
                onClick={async () => {
                  try {
                    setDetail(await api(`/api/emails/${em.id}`));
                  } catch {
                    setDetail(em);
                  }
                }}
              >
                <span className={`shrink-0 text-sm ${em.direction === "ausgang" ? "text-sky" : "text-amber"}`}>
                  {em.direction === "ausgang" ? "↗" : "↙"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] text-ink">{em.subject || "Ohne Betreff"}</p>
                  <p className="truncate text-[11px] text-muted/50">
                    {em.sender || em.recipients}
                    {em.sent_date && <span className="ml-1.5">{formatDate(em.sent_date)}</span>}
                  </p>
                </div>
                {!em.application_id && <Badge tone="amber">Offen</Badge>}
                {em.detected_status && <Badge tone="sky">{em.detected_status}</Badge>}
              </button>
            ))
          ) : (
            <p className="py-4 text-center text-[13px] text-muted/50">
              Keine E-Mails importiert. Drag &amp; Drop oder Button nutzen.
            </p>
          )}
        </div>
      </Card>

      {detail && (
        <EmailDetailModal
          email={detail}
          applications={applications}
          onClose={() => setDetail(null)}
          pushToast={pushToast}
          onUpdate={() => { setDetail(null); laden(); }}
        />
      )}
    </>
  );
}
