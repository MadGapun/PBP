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
import { Check, ClipboardCopy, Clock3, Plus, RotateCcw, Trash2, X } from "lucide-react";
import { api, deleteRequest, postJson } from "@/api";
import { AppContext } from "@/app-context";

const GRUPPEN = [
  ["ueberfaellig", "Überfällig", "text-coral"],
  ["heute", "Heute", "text-amber"],
  ["diese_woche", "Diese Woche", "text-sky"],
  ["spaeter", "Später", "text-muted/70"],
  ["ohne_faelligkeit", "Ohne Fälligkeit", "text-muted/50"],
];

const HERKUNFT_BADGE = {
  todo: ["Aufgabe", "bg-teal/15 text-teal"],
  nachfass: ["Nachfass", "bg-amber/15 text-amber"],
  termin: ["Termin", "bg-sky/15 text-sky"],
};

/**
 * Qualifizierte Kennung einer Aufgabe (#964, v1.7.24).
 *
 * Eine nackte ID reicht nicht: Aufgaben und Nachfassungen liegen in
 * getrennten Tabellen, beide IDs sind achtstellig hexadezimal und
 * damit nicht unterscheidbar. Wer nur "cf8dffcf" kopiert, kann daraus
 * nicht ableiten, ob todo_bearbeiten oder follow_up_bearbeiten
 * zustaendig ist.
 */
function kennung(e) {
  const art = (HERKUNFT_BADGE[e?.herkunft] || ["Eintrag"])[0];
  return `${art} ${e?.id || "?"}`;
}

async function putJson(url, body) {
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

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
  const [kopiert, setKopiert] = useState("");
  const [fehler, setFehler] = useState("");
  // #964 Befund 3: offene Zusage aus #814 — Titel, Beschreibung und Typ
  // sollten nachtraeglich aenderbar sein. Die MCP-Seite konnte das
  // laengst (todo_bearbeiten / follow_up_bearbeiten), nur die
  // Oberflaeche fehlte; der Endpunkt PATCH /api/tasks/{id} wird fuers
  // Verschieben schon benutzt.
  const [bearbeiten, setBearbeiten] = useState(null);
  const [speichert, setSpeichert] = useState(false);

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
          {/* #945: Die Beschreibung gehoert in die Zeile. Wer nur Firma
              und Datum sieht, faengt an zu suchen — genau das war die
              Beobachtung, die zu diesem Issue gefuehrt hat. */}
          {e.beschreibung ? (
            <p className="mt-0.5 line-clamp-2 text-xs text-muted/80">{e.beschreibung}</p>
          ) : null}
          {e.ueberholt ? (
            <p className="mt-0.5 text-xs text-amber">{e.ueberholt_grund}</p>
          ) : null}
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
                className="w-[7.5rem] rounded border border-white/10 bg-shell/60 px-1 py-0.5 text-[11px] text-muted/70"
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
          {/* #964: Der Knopf kopiert jetzt IMMER etwas. Vorher wurde er
              nur bei vorhandenem claude_prompt gerendert — und den gibt
              es im echten Bestand ausschliesslich fuer Nachfassungen.
              Auf einer frei angelegten Aufgabe gab es also gar keinen
              Kopier-Knopf, und der Nutzer konnte im Chat nicht auf sie
              zeigen. */}
          <button
            onClick={async (ev) => {
              ev.stopPropagation();
              const text = e.claude_prompt
                ? `${kennung(e)}

${e.claude_prompt}`
                : kennung(e);
              try {
                await navigator.clipboard.writeText(text);
                setKopiert(e.id);
                setTimeout(() => setKopiert(""), 2000);
              } catch { /* Zwischenablage nicht verfuegbar */ }
            }}
            title={e.claude_prompt
              ? "Kennung und fertigen Claude-Auftrag kopieren"
              : "Kennung kopieren (für den Chat)"}
            className="rounded p-1 text-muted/40 hover:bg-white/10 hover:text-teal">
            {kopiert === e.id ? <Check size={13} className="text-teal" /> : <ClipboardCopy size={13} />}
          </button>
          {e.herkunft === "todo" && (
            <button
              onClick={() => { if (confirm("Aufgabe wirklich löschen?")) aktion(e, "loeschen"); }}
              title="Löschen"
              className="rounded p-1 text-muted/30 hover:bg-coral/15 hover:text-coral">
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
            className="rounded-lg border border-white/10 bg-shell/60 px-2 py-1 text-sm text-ink">
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

      {fehler && <p className="rounded-lg bg-coral/10 px-3 py-2 text-sm text-coral">{fehler}</p>}

      {neuOffen && (
        <div className="grid gap-2 rounded-xl border border-teal/20 bg-teal/5 p-4">
          <input
            autoFocus
            placeholder="Was ist zu tun?"
            value={neuTitel}
            onChange={(e) => setNeuTitel(e.target.value)}
            className="rounded-lg border border-white/10 bg-shell/60 px-3 py-2 text-sm text-ink outline-none focus:border-teal/40"
          />
          <textarea
            rows={2}
            placeholder="Details (optional) — an wen, worauf bezogen, welcher Kanal"
            value={neuBeschreibung}
            onChange={(e) => setNeuBeschreibung(e.target.value)}
            className="rounded-lg border border-white/10 bg-shell/60 px-3 py-2 text-sm text-ink outline-none focus:border-teal/40"
          />
          <div className="flex flex-wrap items-center gap-2">
            <input type="date" value={neuFaellig}
              onChange={(e) => setNeuFaellig(e.target.value)}
              className="rounded-lg border border-white/10 bg-shell/60 px-2 py-1.5 text-sm text-ink" />
            <select value={neuBewerbung}
              onChange={(e) => setNeuBewerbung(e.target.value)}
              className="min-w-0 flex-1 truncate rounded-lg border border-white/10 bg-shell/60 px-2 py-1.5 text-sm text-ink">
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
          {/* #964 Befund 1: das Panel trug 'bg-panelstrong' — ein Token, das im
              Design-System nicht existiert. Tailwind erzeugt fuer eine
              unbekannte Farbe keine Regel und meldet auch keinen
              Fehler; das Overlay hatte deshalb GAR KEINEN Hintergrund,
              und die Liste dahinter schien durch den Aufgabentext.
              max-h/overflow ergaenzt, damit lange Beschreibungen im
              Panel bleiben statt herauszulaufen. */}
          <div className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-white/10 bg-panelstrong shadow-2xl"
            onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3 p-5 pb-0">
              <h3 className="text-base font-semibold text-ink">{detail.titel}</h3>
              <button onClick={() => { setDetail(null); setBearbeiten(null); }}
                className="rounded p-1 text-muted/50 hover:text-ink"><X size={16} /></button>
            </div>
            <div className="overflow-y-auto p-5 pt-2">
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
            {/* #964 Befund 2: die Kennung sichtbar und kopierbar, damit
                der Nutzer im Chat auf genau diese Aufgabe zeigen kann,
                statt sie zu umschreiben. */}
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(kennung(detail));
                  setKopiert(detail.id);
                  setTimeout(() => setKopiert(""), 2000);
                } catch { /* Zwischenablage nicht verfuegbar */ }
              }}
              title="Kennung kopieren"
              className="mt-3 flex items-center gap-1.5 font-mono text-[11px] text-muted/50 hover:text-teal">
              {kennung(detail)}
              {kopiert === detail.id
                ? <Check size={11} className="text-teal" />
                : <ClipboardCopy size={11} />}
            </button>

            {bearbeiten ? (
              <div className="mt-4 space-y-2 rounded-lg border border-white/10 bg-shell/40 p-3">
                {detail.herkunft === "nachfass" ? (
                  <p className="text-xs text-muted/60">
                    Bei einer Nachfassung ist der Titel aus Bewerbung und Firma
                    abgeleitet — änderbar ist der Text.
                  </p>
                ) : (
                  <input
                    value={bearbeiten.titel}
                    onChange={(ev) => setBearbeiten({ ...bearbeiten, titel: ev.target.value })}
                    placeholder="Titel"
                    className="w-full rounded-lg border border-white/10 bg-shell/60 px-3 py-2 text-sm text-ink outline-none focus:border-teal/40" />
                )}
                <textarea
                  value={bearbeiten.beschreibung}
                  onChange={(ev) => setBearbeiten({ ...bearbeiten, beschreibung: ev.target.value })}
                  rows={4}
                  placeholder="Was ist konkret zu tun? Ohne das ist die Aufgabe später nicht erledigbar."
                  className="w-full rounded-lg border border-white/10 bg-shell/60 px-3 py-2 text-sm text-ink outline-none focus:border-teal/40" />
                <div className="flex items-center gap-2">
                  <button
                    disabled={speichert || (detail.herkunft !== "nachfass"
                      && !bearbeiten.titel.trim())}
                    onClick={async () => {
                      setSpeichert(true);
                      try {
                        // Die drei Toepfe liegen in getrennten Tabellen
                        // und haben getrennte Endpunkte. Ein Nachfass
                        // an PATCH /api/tasks zu schicken ergaebe ein
                        // stilles 404 — der Nutzer haette gespeichert
                        // und nichts waere passiert.
                        if (detail.herkunft === "nachfass") {
                          await putJson(`/api/follow-ups/${detail.id}`, {
                            template: bearbeiten.beschreibung,
                          });
                        } else {
                          await patchJson(`/api/tasks/${detail.id}`, {
                            titel: bearbeiten.titel.trim(),
                            beschreibung: bearbeiten.beschreibung,
                          });
                        }
                        setDetail({ ...detail, ...bearbeiten });
                        setBearbeiten(null);
                        setFehler("");
                        await laden();
                      } catch {
                        setFehler("Änderung konnte nicht gespeichert werden.");
                      } finally {
                        setSpeichert(false);
                      }
                    }}
                    className="rounded-lg bg-teal/20 px-3 py-1.5 text-sm font-semibold text-teal hover:bg-teal/30 disabled:opacity-40">
                    {speichert ? "Speichert…" : "Speichern"}
                  </button>
                  <button onClick={() => setBearbeiten(null)}
                    className="rounded-lg px-3 py-1.5 text-sm text-muted/70 hover:text-ink">
                    Abbrechen
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {detail.herkunft !== "termin" && (
                  <button
                    onClick={() => setBearbeiten({
                      titel: detail.titel || "",
                      beschreibung: detail.beschreibung || "",
                    })}
                    className="rounded-lg bg-white/5 px-3 py-1.5 text-sm font-semibold text-ink/80 hover:bg-white/10">
                    Bearbeiten
                  </button>
                )}
                {detail.bewerbung_id && (
                  <button
                    onClick={() => { springeZurBewerbung(detail); setDetail(null); }}
                    className="rounded-lg bg-sky/15 px-3 py-1.5 text-sm font-semibold text-sky hover:bg-sky/25">
                    Zur Bewerbung
                  </button>
                )}
              </div>
            )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
