// #1184 (d): Hinweise aus Google-Benachrichtigungen — Treffer, die noch KEINE Stelle sind.
//
// Eine Benachrichtigungs-Mail von Google Jobs nennt nur Titel, Firma, Ort und Portal; jeder Link fuehrt auf eine Google-Suche, und
// derselbe Treffer kommt mit verschiedenen Orten. Daraus legt PBP seit 1.8.0 keine Stelle an (sie stand bis dahin ohne Text und
// Anker mitten in der Trefferliste), sondern einen Hinweis. Hier stehen sie, eingeklappt, mit der vorbereiteten Suche nach dem
// Original beim Arbeitgeber. Die Liste und die Suche kommen vom Server (`services/stellen_hinweise`, `services/google_angaben`).

import { useEffect, useState } from "react";
import { ChevronDown, ExternalLink, Lightbulb } from "lucide-react";

import { api, postJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card } from "@/components/ui";
import { sichereAdresse } from "@/lib/webAdresse";

export default function StellenHinweise({ anlass = 0 }) {
  const { pushToast } = useApp();
  const [daten, setDaten] = useState(null);
  const [offen, setOffen] = useState(false);
  const [beschaeftigt, setBeschaeftigt] = useState("");

  async function laden() {
    try {
      setDaten(await api("/api/stellen-hinweise?status=offen"));
    } catch {
      setDaten(null);
    }
  }

  useEffect(() => { laden(); }, [anlass]);

  async function verwerfen(h) {
    setBeschaeftigt(h.id);
    try {
      await postJson(`/api/stellen-hinweise/${h.id}/verwerfen`, {});
      pushToast("Hinweis verworfen.", "success", { duration: 2500 });
      await laden();
    } catch (err) {
      pushToast(`Verwerfen fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setBeschaeftigt("");
    }
  }

  const hinweise = Array.isArray(daten?.hinweise) ? daten.hinweise : [];
  if (!hinweise.length) return null;

  return (
    <Card className="glass-card-soft mb-4 rounded-xl" data-stellen-hinweise>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 text-left"
        aria-expanded={offen}
        onClick={() => setOffen(!offen)}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-ink">
          <Lightbulb size={15} />
          {hinweise.length === 1
            ? "1 Hinweis aus einer Google-Benachrichtigung — noch keine Stelle"
            : `${hinweise.length} Hinweise aus Google-Benachrichtigungen — noch keine Stellen`}
        </span>
        <ChevronDown size={15} className={offen ? "rotate-180 transition-transform" : "transition-transform"} aria-hidden="true" />
      </button>
      {offen && (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-muted">
            Die Mail nennt nur Titel, Firma, Ort und Portal; ihre Links führen auf eine Google-Suche, und derselbe Treffer
            kommt mit verschiedenen Orten. Darum ist daraus keine Stelle geworden. Was dich interessiert: such das Original
            beim Arbeitgeber und leg es mit Adresse und Text an — oder sag Claude: „Such mir das Original zu …“.
          </p>
          <ul className="grid gap-2">
            {hinweise.map((h) => (
              <li key={h.id} className="rounded-lg border border-white/8 p-3" data-hinweis={h.id}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">{h.titel}</p>
                    <p className="text-xs text-muted">
                      {[h.firma, h.ort, h.portal ? `über ${h.portal}` : ""].filter(Boolean).join(" · ")}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {h.anzahl_mails > 1 && <Badge>in {h.anzahl_mails} Mails</Badge>}
                      {String(h.ort || "").includes(";") && <Badge tone="amber">Orte widersprechen sich</Badge>}
                      {h.weiterverbreiter && <Badge tone="amber">Kopie einer Sammelseite</Badge>}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {h.suche?.[0]?.url && (
                      <a
                        className="inline-flex items-center gap-1 text-xs text-sky underline"
                        href={sichereAdresse(h.suche[0].url)}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Original suchen <ExternalLink size={12} aria-hidden="true" />
                      </a>
                    )}
                    <Button variant="secondary" size="sm" disabled={beschaeftigt === h.id} onClick={() => verwerfen(h)}>
                      Verwerfen
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
