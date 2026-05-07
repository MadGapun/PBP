/**
 * InlineJobDetailModal — v1.7.0-beta.31 (#595)
 *
 * Read-only Stellen-Detail-Ansicht, die aus jeder Page heraus geoeffnet
 * werden kann. Holt /api/jobs/<hash> (kein is_active-Filter), zeigt
 * Title/Company/Location/Salary/Description/URL.
 *
 * Hintergrund: Wenn aus einer Bewerbung auf die verknuepfte Stelle
 * geklickt wird, ist diese Stelle typischerweise auf is_active=0 mit
 * dismiss_reason='bewerbung_erstellt' gesetzt. Die normale Stellen-Liste
 * filtert nach is_active=1, dadurch war die Detail-Ansicht leer.
 */
import { useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";

import { api } from "@/api";
import { Button, Modal } from "@/components/ui";
import { formatCurrency, formatDateTime, textExcerpt } from "@/utils";

export default function InlineJobDetailModal({ jobHash, onClose }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobHash) return;
    let cancelled = false;
    setLoading(true);
    api(`/api/jobs/${jobHash}`)
      .then((data) => { if (!cancelled) { setJob(data); setLoading(false); } })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || "Konnte Stelle nicht laden");
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [jobHash]);

  if (!jobHash) return null;

  return (
    <Modal open={true} title="Stellendetails" onClose={onClose}>
      {loading && <p className="text-sm text-muted/70">Lade...</p>}
      {error && (
        <div className="rounded-lg border border-coral/20 bg-coral/[0.05] p-3 text-sm text-coral">
          {error}
        </div>
      )}
      {job && (
        <div className="space-y-3">
          <div>
            <h3 className="text-xl font-semibold text-ink">{job.title}</h3>
            <p className="text-sm text-muted">
              {job.company || "Unbekannt"}
              {job.location ? ` — ${job.location}` : ""}
            </p>
          </div>

          {!job.is_active && job.dismiss_reason && (
            <div className="rounded-lg border border-amber/20 bg-amber/[0.04] p-2 text-[11px] text-amber/80">
              Diese Stelle ist aussortiert
              {` (${job.dismiss_reason})`}
              {" — Read-Only-Ansicht."}
            </div>
          )}

          {(job.salary_min || job.salary_max) && (
            <p className="text-sm text-muted/70">
              <strong className="text-ink">Gehalt:</strong>{" "}
              {job.salary_min ? formatCurrency(job.salary_min) : "?"}
              {job.salary_max ? ` — ${formatCurrency(job.salary_max)}` : ""}
              {job.salary_period ? ` / ${job.salary_period}` : ""}
            </p>
          )}

          {job.score !== null && job.score !== undefined && (
            <p className="text-sm text-muted/70">
              <strong className="text-ink">Score:</strong> {job.score}
            </p>
          )}

          {job.source && (
            <p className="text-[11px] text-muted/50">
              Quelle: <span className="font-mono">{job.source}</span>
              {job.found_at && ` · gefunden ${formatDateTime(job.found_at)}`}
            </p>
          )}

          {job.description && (
            <details open>
              <summary className="cursor-pointer text-[11px] uppercase tracking-wider text-muted/60">
                Beschreibung
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted/80">
                {textExcerpt(job.description, 2000)}
              </p>
            </details>
          )}

          {job.research_notes && (
            <details>
              <summary className="cursor-pointer text-[11px] uppercase tracking-wider text-muted/60">
                Notizen
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted/80">
                {job.research_notes}
              </p>
            </details>
          )}

          <div className="flex gap-2 pt-2">
            {job.url && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => window.open(job.url, "_blank", "noopener")}
              >
                <ExternalLink size={14} />
                Original-URL
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              <X size={14} />
              Schliessen
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
