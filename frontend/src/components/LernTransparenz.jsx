/**
 * Was PBP über dich lernt — #792.
 *
 * Drei Fragen, die vorher niemand beantworten konnte: welche Daten fließen
 * ein (auch ausdrücklich, welche NICHT), was haben die letzten Läufe
 * ergeben, und warum kam bei einem Lauf nichts heraus. Dazu der Export
 * zum Nachlesen. Die Zahlen rechnet der Server (`lernquellen`,
 * `lernprotokoll`) — dieselben, die Claude mit `lernprotokoll_anzeigen`
 * bekommt.
 */
import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { api, apiUrl } from "@/api";
import { formatDateTime } from "@/utils";

const AUSLOESER = { automatik: "Automatik", manuell: "von Hand" };
const STATUS = {
  fertig: "fertig",
  teilweise: "teilweise",
  lernen_aus: "Lernen aus",
};

function zeitraum(q) {
  if (!q.von && !q.bis) return "—";
  return `${q.von || "?"} bis ${q.bis || "?"}`;
}

function Lauf({ lauf }) {
  const [offen, setOffen] = useState(false);
  const kandidaten = lauf.kandidaten || [];
  const warum = lauf.warum_nichts_neues || [];
  return (
    <li className="rounded-lg border border-white/[0.04] px-2.5 py-1.5" data-lernlauf>
      <button type="button" className="flex w-full items-center justify-between gap-2 text-left"
        aria-expanded={offen} onClick={() => setOffen((o) => !o)}>
        <span className="text-[12px] text-ink">
          {formatDateTime(lauf.gestartet_am)} · {AUSLOESER[lauf.ausloeser] || lauf.ausloeser}
          {" · "}{STATUS[lauf.status] || lauf.status}
        </span>
        <span className="shrink-0 text-xs text-muted">
          {lauf.neu ? `${lauf.neu} neu` : "nichts Neues"} {offen ? "▲" : "▼"}
        </span>
      </button>
      {offen && (
        <div className="mt-1.5 space-y-1.5 text-xs text-muted">
          {kandidaten.length > 0 && (
            <ul className="space-y-1">
              {kandidaten.map((k, i) => (
                <li key={i}>
                  <span className="text-ink">{k.aussage}</span>
                  {" "}— belegt durch {k.belegt_durch_n} Fälle, Sicherheit {Math.round((k.konfidenz || 0) * 100)} %
                </li>
              ))}
            </ul>
          )}
          {lauf.aufgefrischt > 0 && <p>{lauf.aufgefrischt} schon bekannte Aussagen bestätigt.</p>}
          {lauf.verworfen > 0 && <p>{lauf.verworfen} Aussagen übergangen, weil du sie früher verworfen hast.</p>}
          {warum.length > 0 && (
            <div data-warum-nichts>
              <p className="font-semibold text-ink">Warum nichts Neues:</p>
              <ul className="list-disc pl-4">
                {warum.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}
          {lauf.lokale_ki && lauf.lokale_ki.uebersprungen === false && (
            <p>Lokale KI: {lauf.lokale_ki.erkenntnisse} Hinweise zur Bedienung.</p>
          )}
          <p>Dauer: {Math.round((lauf.dauer_ms || 0) / 100) / 10} s</p>
        </div>
      )}
    </li>
  );
}

export default function LernTransparenz() {
  const [daten, setDaten] = useState(null);
  const [offen, setOffen] = useState(false);
  useEffect(() => {
    api("/api/lernen/transparenz?limit=10").then(setDaten).catch(() => setDaten(null));
  }, []);
  if (!daten) return null;
  const quellen = daten.quellen || [];
  const laeufe = daten.laeufe || [];
  return (
    <div className="glass-card p-3 mb-4" data-lern-transparenz>
      <button type="button" className="flex w-full items-center justify-between text-left"
        aria-expanded={offen} onClick={() => setOffen((o) => !o)}>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Was PBP über dich lernt
        </p>
        <span className="text-xs text-muted">{offen ? "▲" : "▼"}</span>
      </button>
      {offen && (
        <div className="mt-2 space-y-3">
          {!daten.lernen_eingeschaltet && (
            <p className="text-xs text-amber">
              Das Lernen ist unter Datenschutz ausgeschaltet — es wird nichts ausgewertet.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted">
                <tr>
                  <th className="py-1 pr-2 font-medium">Quelle</th>
                  <th className="py-1 pr-2 font-medium">fließt ein</th>
                  <th className="py-1 pr-2 font-medium">Datensätze</th>
                  <th className="py-1 pr-2 font-medium">Zeitraum</th>
                  <th className="py-1 font-medium">wofür</th>
                </tr>
              </thead>
              <tbody>
                {quellen.map((q) => (
                  <tr key={q.key} className="border-t border-white/[0.04] align-top" data-lernquelle={q.key}>
                    <td className="py-1 pr-2 text-ink">{q.name}</td>
                    <td className="py-1 pr-2">{q.fliesst_ein ? "ja" : "nein"}</td>
                    <td className="py-1 pr-2 tabular-nums">{q.fliesst_ein ? q.anzahl : ""}</td>
                    <td className="py-1 pr-2">{q.fliesst_ein ? zeitraum(q) : ""}</td>
                    <td className="py-1 text-muted">{q.wofuer}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold text-ink">Letzte Lernläufe</p>
            {laeufe.length ? (
              <ul className="space-y-1.5">{laeufe.map((l) => <Lauf key={l.id} lauf={l} />)}</ul>
            ) : (
              <p className="text-xs text-muted">
                Noch kein Lernlauf. Er läuft mit der Automatik (Einstellungen › Automatik) oder sofort über „Jetzt lernen“.
              </p>
            )}
          </div>
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-muted">
              Der Export enthält genau diese Daten als CSV, die Erkenntnisse mit Beleg und das Protokoll. Er enthält Firmennamen — nicht unbedacht weitergeben.
            </p>
            <a href={apiUrl("/api/lernen/export")} download
              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/10 px-2.5 py-1 text-xs text-ink hover:bg-white/5"
              data-lerndaten-export>
              <Download size={13} /> Lerndaten exportieren
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
