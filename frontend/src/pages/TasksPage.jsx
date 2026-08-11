/**
 * Aufgaben-Bereich (#814/#815, D35, v1.7.12).
 *
 * PBP hatte Aufgaben, aber keinen Ort, an dem sie leben: kein Menue,
 * keine Gesamtsicht, kein Anlegen ohne Bewerbung. 5 Aufgaben auf 94
 * Bewerbungen war kein Nutzungsmuster, sondern ein Zugangsproblem —
 * und die beiden am laengsten festhaengenden Bewerbungen waren exakt
 * die mit den aeltesten unsichtbaren Nachfassungen.
 *
 * Eine Liste ueber alle drei Toepfe (Todos, Nachfassungen, Termine),
 * gruppiert nach Faelligkeit, bedienbar aus der Zeile.
 */
import { useCallback, useContext, useEffect, useState } from "react";
import { Check, Clock3, Plus, RotateCcw, Trash2, X } from "lucide-react";
import { api, deleteRequest, postJson } from "@/api";
import { AppContext } from "@/app-context";

const GRUPPEN = [
  ["ueberfaellig", "Überfällig", "text-coral"],
  ["heute", "Heute", "text-amber-400"],
  ["diese_woche", "Diese Woche", "text-sky"],
  ["spaeter", "Später", "text-muted/70"],
  ["ohne_faelligkeit", "Ohne Fälligkeit", "text-muted/50"],
];

const HERKUNFT_BADGE = {
  todo: ["Aufgabe", "bg-teal/15 text-teal"],
  nachfass: ["Nachfass", "bg-amber-400/15 text-amber-400"],
  termin: ["Termin", "bg-sky/15 text-sky"],
};

async function patchJson(url, body) {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export default function TasksPage() {
  const { navigateTo } = useContext(AppContext) || {};
  const [daten, setDaten] = useState(null);
  const [statusFilter, setStatusFilter] = useState("offen");
  const [neuOffen, setNeuOffen] = useState(false);
  const [neuTitel, setNeuTitel] = useState("");
  const [neuBeschreibung, setNeuBeschreibung] = useState("");
  const [neuFaellig, setNeuFaellig] = useState("");
  const [neuBewerbung, setNeuBewerbung] = useState("");
  const [bewerbungen, setBewerbungen] = useState([]);
  const [detail, setDetail] = useState(null);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(async () => {
    try {
      const res = await api(`/api/aufgaben?status=${statusFilter}`);
      setDaten(res);
      setFehler("");
    } catch (e) {
      setFehler(`Aufgaben konnten nicht geladen werden: ${e.message}`);
    }
  }, [statusFilter]);

  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    api("/api/applications").then((r) => {
      const liste = Array.isArray(r) ? r : (r?.applications || []);
      setBewerbungen(liste.filter((a) =>
        !["abgelehnt", "abgelaufen", "zurueckgezogen", "angenommen"]
          .includes(a.status)));
    }).catch(() => {});
  }, []);

  async function anlegen() {
    if (!neuTitel.trim()) return;
    try {
      await postJson("/api/tasks", {
        titel: neuTitel.trim(),
        beschreibung: neuBeschreibung,
        faellig_am: neuFaellig || null,
        application_id: neuBewerbung || null,
      });
      setNeuTitel(""); setNeuBeschreibung(""); setNeuFaellig("");
      setNeuBewerbung(""); setNeuOffen(false);
      await laden();
    } catch (e) {
      setFehler(`Anlegen fehlgeschlagen: ${e.message}`);
    }
  }

  async function aktion(eintrag, was) {
    try {
      if (eintrag.herkunft === "todo") {
        if (was === "erledigt") await postJson(`/api/tasks/${eintrag.id}/complete`, {});
        else if (was === "hinfaellig") await postJson(`/api/tasks/${eintrag.id}/hinfaellig`, {});
        else if (was === "reopen") await postJson(`/api/tasks/${eintrag.id}/reopen`, {});
        else if (was === "loeschen") await deleteRequest(`/api/tasks/${eintrag.id}`);
      } else if (eintrag.herkunft === "nachfass") {
        if (was === "erledigt") await postJson(`/api/follow-ups/${eintrag.id}/complete`, {});
        else if (was === "hinfaellig") await postJson(`/api/follow-ups/${eintrag.id}/obsolete`, {}).catch(async () => {
          await postJson(`/api/follow-ups/${eintrag.id}/complete`, {});
        });
      }
      await laden();
    } catch (e) {
      setFehler(`Aktion fehlgeschlagen: ${e.message}`);
    }
  }

  async function verschieben(eintrag, datum) {
    if (!datum) return;
    try {
      if (eintrag.herkunft === "todo") {
        await patchJson(`/api/tasks/${eintrag.id}`, { faellig_am: datum });
      } else if (eintrag.herkunft === "nachfass") {
        await postJson(`/api/follow-ups/${eintrag.id}/reschedule`,
          { scheduled_date: datum });
      }
      await laden();
    } catch (e) {
      setFehler(`Verschieben fehlgeschlagen: ${e.message}`);
    }
  }

  function springeZurBewerbung(eintrag) {
    if (!eintrag.bewerbung_id || !navigateTo) return;
    // #815: Sprung in den Kontext — Bewerbungen-Tab + Timeline oeffnen
    navigateTo("bewerbungen", { applicationId: eintrag.bewerbung_id });
  }

  const zeile = (e) => {
    const [label, badgeCls] = HERKUNFT_BADGE[e.herkunft] || ["?", ""];
    return (
      <div key={`${e.herkunft}-${e.id}`}
        className="group flex items-start gap-2 rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 hover:bg-white/[0.05]">
        {e.herkunft !== "termin" && e.status !== "erledigt" && (
          <button
            onClick={() => aktion(e, "erledigt")}
            title="Erledigt"
            className="mt-0.5 shrink-0 rounded-md border border-teal/30 bg-teal/10 p-1 text-teal hover:bg-teal/25">
            <Check size={13} />
          </button>
        )}
        {e.status === "erledigt" && (
          <button
            onClick={() => aktion(e, "reopen")}
            title="Wieder öffnen"
            className="mt-0.5 shrink-0 rounded-md border border-white/10 p-1 text-muted/50 hover:text-ink">
            <RotateCcw size={13} />
          </button>
        )}
        <div className="min-w-0 flex-1 cursor-pointer" onClick={() => setDetail(e)}>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded px-1.5 py-px text-[10px] font-bold ${badgeCls}`}>{label}</span>
            <span className={`truncate text-sm ${e.status === "erledigt" ? "text-muted/40 line-through" : "text-ink"}`}>{e.titel}</span>
          </div>
          <p className="mt-0.5 text-xs text-muted/60">
            {e.firma ? <span className="mr-2">{e.firma}</span> : null}
            {e.faellig_am ? (
              <span className={e.ueberfaellig_seit_tagen ? "font-semibold text-coral" : ""}>
                {e.ueberfaellig_seit_tagen
                  ? `überfällig seit ${e.ueberfaellig_seit_tagen} Tagen`
                  : `fällig ${e.faellig_am}`}
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          {e.herkunft !== "termin" && e.status !== "erledigt" && (
            <>
              <input
                type="date"
                title="Verschieben"
                className="w-[7.5rem] rounded border border-white/10 bg-bg/60 px-1 py-0.5 text-[11px] text-muted/70"
                onChange={(ev) => verschieben(e, ev.target.value)}
              />
              <button
                onClick={() => aktion(e, "hinfaellig")}
                title="Hinfällig (gegenstandslos geworden)"
                className="rounded p-1 text-muted/40 hover:bg-white/10 hover:text-ink">
                <X size={13} />
              </button>
            </>
          )}
          {e.herkunft === "todo" && (
            <button
              onClick={() => { if (confirm("Aufgabe wirklich löschen?")) aktion(e, "loeschen"); }}
              title="Löschen"
              className="rounded p-1 text-muted/30 hover:bg-danger/15 hover:text-danger">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="mx-auto grid max-w-4xl gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Clock3 size={18} className="text-teal" />
          <h2 className="text-lg font-semibold text-ink">Aufgaben</h2>
          {daten?.ueberfaellig_anzahl > 0 && (
            <span className="rounded-full bg-coral/15 px-2 py-px text-xs font-bold text-coral">
              {daten.ueberfaellig_anzahl} überfällig
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-white/10 bg-bg/60 px-2 py-1 text-sm text-ink">
            <option value="offen">Offene</option>
            <option value="erledigt">Erledigte</option>
            <option value="alle">Alle</option>
          </select>
          <button
            onClick={() => setNeuOffen((v) => !v)}
            className="inline-flex items-center gap-1 rounded-lg bg-teal/20 px-3 py-1.5 text-sm font-semibold text-teal hover:bg-teal/30">
            <Plus size={14} /> Neue Aufgabe
          </button>
        </div>
      </div>

      {fehler && <p className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{fehler}</p>}

      {neuOffen && (
        <div className="grid gap-2 rounded-xl border border-teal/20 bg-teal/5 p-4">
          <input
            autoFocus
            placeholder="Was ist zu tun?"
            value={neuTitel}
            onChange={(e) => setNeuTitel(e.target.value)}
            className="rounded-lg border border-white/10 bg-bg/60 px-3 py-2 text-sm text-ink outline-none focus:border-teal/40"
          />
          <textarea
            rows={2}
            placeholder="Details (optional) — an wen, worauf bezogen, welcher Kanal"
            value={neuBeschreibung}
            onChange={(e) => setNeuBeschreibung(e.target.value)}
            className="rounded-lg border border-white/10 bg-bg/60 px-3 py-2 text-sm text-ink outline-none focus:border-teal/40"
          />
          <div className="flex flex-wrap items-center gap-2">
            <input type="date" value={neuFaellig}
              onChange={(e) => setNeuFaellig(e.target.value)}
              className="rounded-lg border border-white/10 bg-bg/60 px-2 py-1.5 text-sm text-ink" />
            <select value={neuBewerbung}
              onChange={(e) => setNeuBewerbung(e.target.value)}
              className="min-w-0 flex-1 truncate rounded-lg border border-white/10 bg-bg/60 px-2 py-1.5 text-sm text-ink">
              <option value="">Ohne Bewerbungsbezug (freie Aufgabe)</option>
              {bewerbungen.map((a) => (
                <option key={a.id} value={a.id}>{a.company} — {a.title}</option>
              ))}
            </select>
            <button onClick={anlegen}
              className="rounded-lg bg-teal/25 px-4 py-1.5 text-sm font-semibold text-teal hover:bg-teal/35">
              Anlegen
            </button>
          </div>
        </div>
      )}

      {!daten && !fehler && <p className="text-sm text-muted/60">Lade…</p>}

      {daten && GRUPPEN.map(([key, label, cls]) => {
        const liste = daten.gruppen?.[key] || [];
        if (!liste.length) return null;
        return (
          <section key={key} className="grid gap-1.5">
            <h3 className={`text-[11px] font-bold uppercase tracking-[0.2em] ${cls}`}>
              {label} ({liste.length})
            </h3>
            {liste.map(zeile)}
          </section>
        );
      })}

      {daten && daten.anzahl === 0 && (
        <p className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-6 text-center text-sm text-muted/60">
          Nichts offen. Entweder ist wirklich alles erledigt — oder es fehlt der Plan für den nächsten Schritt.
        </p>
      )}

      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setDetail(null)}>
          <div className="w-full max-w-lg rounded-xl border border-white/10 bg-bg p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-base font-semibold text-ink">{detail.titel}</h3>
              <button onClick={() => setDetail(null)}
                className="rounded p-1 text-muted/50 hover:text-ink"><X size={16} /></button>
            </div>
            <p className="mt-1 text-xs text-muted/60">
              {(HERKUNFT_BADGE[detail.herkunft] || ["?"])[0]}
              {detail.firma ? ` · ${detail.firma}` : ""}
              {detail.faellig_am ? ` · fällig ${detail.faellig_am}` : ""}
              {` · Status: ${detail.status}`}
            </p>
            {detail.beschreibung ? (
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink/90">{detail.beschreibung}</p>
            ) : (
              <p className="mt-3 text-sm italic text-muted/50">
                Keine Details hinterlegt — genau das macht Aufgaben schwer erledigbar.
              </p>
            )}
            {detail.notiz && (
              <p className="mt-2 text-xs text-muted/60">Notiz: {detail.notiz}</p>
            )}
            {detail.bewerbung_id && (
              <button
                onClick={() => { springeZurBewerbung(detail); setDetail(null); }}
                className="mt-4 rounded-lg bg-sky/15 px-3 py-1.5 text-sm font-semibold text-sky hover:bg-sky/25">
                Zur Bewerbung
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
