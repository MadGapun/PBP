// #1307/#1308: eigene Regeln unter Einstellungen › Automatik — ansehen, an- und ausschalten, testen, auf den Bestand
// anwenden, löschen, und eine Sprach-Regel ohne Claude anlegen.
//
// Alle Antworten kommen aus `services/gespeicherte_filter.verwalten` (derselbe Weg wie das Claude-Werkzeug
// `stellen_filter_verwalten`); hier wird nur angezeigt. Eine Regel sortiert NEUE Treffer nach jeder Suche aus; beim Anlegen
// ändert sie nichts am Bestand — das tut erst „Auf vorhandene Stellen anwenden“ nach einer Vorschau.

import { useEffect, useState } from "react";
import { Filter, Trash2 } from "lucide-react";

import { api, deleteRequest, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card, SelectInput } from "@/components/ui";
import { bestaetigen } from "@/lib/bestaetigung";
import { grundText } from "@/lib/anzeige";

const SPRACH_REGELN = [
  { wert: "en", text: "Rein englische Anzeigen" },
  { wert: "andere", text: "Anzeigen in einer anderen Sprache (weder Deutsch noch Englisch)" },
];

export default function StellenRegeln() {
  // pushToast nur in Handlern - Laden haengt nicht daran (sonst laedt jede Meldung neu).
  const { pushToast } = useApp();
  const [daten, setDaten] = useState(null);
  const [beschaeftigt, setBeschaeftigt] = useState("");
  const [neueSprache, setNeueSprache] = useState("en");
  const [neuerGrund, setNeuerGrund] = useState("");

  async function laden() {
    try {
      setDaten(await api("/api/stellen-filter"));
    } catch {
      setDaten({ regeln: [], ansichten: [], verfuegbare_gruende: [] });
    }
  }
  useEffect(() => { laden(); }, []);

  async function mit(kennung, arbeit) {
    setBeschaeftigt(kennung);
    try {
      await arbeit();
      await laden();
    } catch (err) {
      pushToast(err.message, "danger", { duration: 7000 });
    } finally {
      setBeschaeftigt("");
    }
  }

  function umschalten(regel) {
    return mit(`aktiv-${regel.id}`, async () => {
      await putJson(`/api/stellen-filter/${regel.id}/aktiv`, { aktiv: !regel.aktiv });
      pushToast(regel.aktiv ? `„${regel.name}“ ruht: neue Treffer bleiben stehen.` : `„${regel.name}“ wirkt wieder auf neue Treffer.`, "success");
    });
  }

  function anwenden(regel) {
    return mit(`anwenden-${regel.id}`, async () => {
      const vorschau = await postJson(`/api/stellen-filter/${regel.id}/anwenden`, { dry_run: true });
      const n = Number(vorschau?.wuerde_aussortieren || 0);
      if (!n) {
        pushToast(`„${regel.name}“ trifft im Moment keine vorhandene Stelle.`, "info");
        return;
      }
      const zusatz = [
        vorschau.geschuetzt ? `${vorschau.geschuetzt} geschützte Stelle(n) (zurückgeholt oder mit Urteil) bleiben.` : "",
        vorschau.sprache_unbekannt ? `${vorschau.sprache_unbekannt} Stelle(n) ohne erkennbare Sprache bleiben.` : "",
      ].filter(Boolean).join(" ");
      const ok = await bestaetigen({
        titel: `${n} Stelle(n) aussortieren?`,
        text: `Die Regel „${regel.name}“ sortiert ${n} vorhandene Stelle(n) aus. ${zusatz}\n\nDu findest sie danach unter Stellen › Aussortiert und kannst sie dort zurückholen.`,
        ja: "Aussortieren",
      });
      if (!ok) return;
      const erg = await postJson(`/api/stellen-filter/${regel.id}/anwenden`, { dry_run: false });
      pushToast(`${erg.aussortiert} Stelle(n) aussortiert — zurückholen unter Stellen › Aussortiert.`, "success", { duration: 6000 });
    });
  }

  function loeschen(regel) {
    return mit(`loeschen-${regel.id}`, async () => {
      const ok = await bestaetigen({
        titel: "Regel löschen?",
        text: `„${regel.name}“ wird gelöscht. Was sie schon aussortiert hat, bleibt aussortiert und lässt sich unter Stellen › Aussortiert zurückholen.`,
        ja: "Löschen",
      });
      if (!ok) return;
      await deleteRequest(`/api/stellen-filter/${regel.id}`);
      pushToast(`„${regel.name}“ ist gelöscht.`, "success");
    });
  }

  function anlegen() {
    const auswahl = SPRACH_REGELN.find((r) => r.wert === neueSprache);
    return mit("anlegen", async () => {
      const erg = await postJson("/api/stellen-filter", {
        name: auswahl.text,
        art: "regel",
        bedingungen: { sprache: [neueSprache] },
        gruende: [neuerGrund],
      });
      const n = Number(erg?.wuerde_aussortieren || 0);
      pushToast(
        `Regel angelegt. Sie sortiert ab jetzt neue Treffer aus${n ? ` — ${n} vorhandene Stelle(n) würde sie treffen; „Auf vorhandene Stellen anwenden“ nimmt sie mit` : ""}.`,
        "success",
        { duration: 7000 },
      );
    });
  }

  if (!daten) return null;
  const regeln = daten.regeln || [];
  const gruende = daten.verfuegbare_gruende || [];

  return (
    <Card className="rounded-2xl" data-testid="stellen-regeln-card">
      <div className="mb-3 flex items-center gap-2">
        <Filter size={16} className="text-muted" />
        <h3 className="text-sm font-semibold text-ink">Eigene Regeln für neue Treffer</h3>
      </div>
      <p className="mb-4 text-xs text-muted">
        Eine Regel sortiert passende neue Stellen nach jeder Suche von selbst aus — mit dem Grund, den du wählst.
        Stellen, die du zurückgeholt hast, Stellen mit gelesenem Urteil und Stellen mit Bewerbung bleiben immer stehen.
        Weitere Regeln und Ansichten (Titel, Anzeigentext, Quelle, Punkte) legst du mit Claude an:
        „Speichere mir eine Regel, die …“.
      </p>

      {regeln.length ? (
        <ul className="mb-4 space-y-2">
          {regeln.map((r) => (
            <li key={r.id} className="rounded-xl border border-white/5 bg-white/[0.02] p-3" data-regel={r.name}>
              <div className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={Boolean(r.aktiv)}
                    disabled={Boolean(beschaeftigt)}
                    onChange={() => umschalten(r)}
                    aria-label={`Regel ${r.name} an oder aus`}
                  />
                  <strong>{r.name}</strong>
                </label>
                {!r.aktiv ? <Badge tone="neutral">ruht</Badge> : null}
                <span className="ml-auto inline-flex gap-2">
                  <Button variant="secondary" size="sm" disabled={Boolean(beschaeftigt)} onClick={() => anwenden(r)}>
                    Auf vorhandene Stellen anwenden
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`Regel ${r.name} löschen`} disabled={Boolean(beschaeftigt)} onClick={() => loeschen(r)}>
                    <Trash2 size={14} />
                  </Button>
                </span>
              </div>
              <p className="mt-1 text-xs text-muted">
                {r.beschreibung} · Grund: {(r.gruende || []).map((g) => grundText(g)).join(", ")}
                {r.treffer_gesamt ? ` · bisher ${r.treffer_gesamt} aussortiert` : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-4 text-xs text-muted">Noch keine eigene Regel.</p>
      )}

      <div className="flex flex-wrap items-end gap-2 border-t border-white/5 pt-3">
        <span className="w-full text-xs font-medium text-ink">Neue Regel nach der Sprache der Anzeige</span>
        <SelectInput aria-label="Welche Anzeigen" className="!w-auto" value={neueSprache} onChange={(e) => setNeueSprache(e.target.value)}>
          {SPRACH_REGELN.map((r) => <option key={r.wert} value={r.wert}>{r.text}</option>)}
        </SelectInput>
        <SelectInput aria-label="Grund" className="!w-auto" value={neuerGrund} onChange={(e) => setNeuerGrund(e.target.value)}>
          <option value="">Grund wählen …</option>
          {gruende.map((g) => <option key={g} value={g}>{grundText(g)}</option>)}
        </SelectInput>
        <Button size="sm" disabled={!neuerGrund || Boolean(beschaeftigt)} onClick={anlegen}>Regel anlegen</Button>
        <span className="w-full text-[11px] text-muted">
          Passt kein Grund, lege unter Einstellungen › Ablehnungsgründe einen eigenen an (z. B. „englischsprachig“).
          Stellen ohne oder mit zu kurzem Anzeigentext haben keine erkennbare Sprache — eine Sprach-Regel lässt sie stehen.
        </span>
      </div>
    </Card>
  );
}
