import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api, optionalApi } from "@/api";
import { useApp } from "@/app-context";
import { Button, Card, DatumFeld, SelectInput, TextInput } from "@/components/ui";
import { isoZuDe } from "@/lib/datumDe";
import { heuteIso } from "@/lib/bewerbungFormular";

// #1422: ein Ort im Dashboard fuer ALLE Kosten des Profils, auch die ohne
// Bewerbung (Tool-Abo, Pruefungsgebuehr). Der Bericht zaehlt sie mit.
export const KOSTEN_ART = {
  tool: "Tool/Abo",
  pruefung: "Prüfung",
  reise: "Reise",
  fortbildung: "Fortbildung",
  sonstiges: "Sonstiges",
};

export function euro(wert) {
  return `${Number(wert || 0).toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} €`;
}

const LEER = { kind: "tool", amount: "", description: "", incurred_at: "" };

export default function KostenBlock() {
  const { reloadKey, pushToast } = useApp();
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState({ ...LEER, incurred_at: heuteIso() });
  const [loeschen, setLoeschen] = useState("");

  async function laden() {
    const antwort = await optionalApi("/api/costs");
    if (antwort) setDaten(antwort);
  }

  useEffect(() => {
    laden();
  }, [reloadKey]);

  async function speichern() {
    const betrag = parseFloat(String(form.amount).replace(",", "."));
    if (!betrag || betrag <= 0) {
      pushToast("Bitte einen Betrag über 0 € eintragen.", "danger");
      return;
    }
    try {
      await api("/api/costs", {
        method: "POST",
        body: JSON.stringify({
          kind: form.kind,
          amount: betrag,
          description: form.description,
          incurred_at: form.incurred_at,
        }),
      });
      pushToast(`${euro(betrag)} erfasst`, "success");
      setForm({ ...LEER, incurred_at: heuteIso() });
      await laden();
    } catch (fehler) {
      pushToast(`Erfassen fehlgeschlagen: ${fehler.message}`, "danger");
    }
  }

  async function entfernen(id) {
    try {
      await api(`/api/costs/${id}`, { method: "DELETE" });
      setLoeschen("");
      await laden();
    } catch (fehler) {
      pushToast(`Löschen fehlgeschlagen: ${fehler.message}`, "danger");
    }
  }

  if (!daten) return null;
  const posten = daten.costs || [];

  return (
    <Card id="kosten" className="mb-6 rounded-2xl" data-kosten-block>
      <h2 className="text-sm font-semibold text-ink">Kosten für den Bericht</h2>
      <p className="mt-1 text-xs text-muted">
        Alles, was die Bewerbungen gekostet haben: Abos, Prüfungsgebühren, Reisen. Der Bericht
        zeigt jeden Posten mit Datum und Betrag. Posten ohne Datum zählen in keinem Zeitraum.
      </p>

      {posten.length === 0 ? (
        <p className="mt-3 text-sm text-muted">Noch keine Kosten erfasst.</p>
      ) : (
        <ul className="mt-3 divide-y divide-white/5 text-sm" aria-label="Erfasste Kosten">
          {posten.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2" data-kostenposten>
              <span className="w-24 text-muted">
                {p.incurred_at ? isoZuDe(p.incurred_at) : "ohne Datum"}
              </span>
              <span className="w-24 font-mono text-ink">{euro(p.amount)}</span>
              <span className="w-24 text-muted">{KOSTEN_ART[p.kind] || p.kind}</span>
              <span className="min-w-[10rem] flex-1 text-ink">
                {p.description || ""}
                {!p.application_id ? "" : <span className="ml-2 text-xs text-muted">(bei einer Bewerbung erfasst)</span>}
                {!p.incurred_at && (
                  <span className="ml-2 text-xs text-amber">
                    ohne Datum, zählt in keinem Zeitraum
                  </span>
                )}
              </span>
              {loeschen === p.id ? (
                <span className="flex items-center gap-2 text-xs">
                  <span className="text-muted">Wirklich löschen?</span>
                  <Button size="sm" variant="ghost" onClick={() => entfernen(p.id)}>
                    Ja, löschen
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setLoeschen("")}>
                    Abbrechen
                  </Button>
                </span>
              ) : (
                <button
                  type="button"
                  aria-label={`Posten vom ${p.incurred_at ? isoZuDe(p.incurred_at) : "ohne Datum"} löschen`}
                  onClick={() => setLoeschen(p.id)}
                  className="text-muted hover:text-coral"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-sm text-ink" data-kosten-summe>
        Summe: <span className="font-mono">{euro(daten.summe_eur)}</span>
        {daten.ohne_datum > 0 && (
          <span className="ml-2 text-xs text-muted">
            ({daten.ohne_datum} Posten ohne Datum)
          </span>
        )}
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-white/5 pt-3">
        <SelectInput
          aria-label="Art der Kosten"
          className="!h-9 !min-h-0 !w-auto"
          value={form.kind}
          onChange={(e) => setForm({ ...form, kind: e.target.value })}
        >
          {Object.entries(KOSTEN_ART).map(([wert, text]) => (
            <option key={wert} value={wert}>{text}</option>
          ))}
        </SelectInput>
        <DatumFeld
          aria-label="Datum der Kosten"
          className="!h-9 !min-h-0 !w-32"
          value={form.incurred_at}
          onChange={(iso) => setForm({ ...form, incurred_at: iso })}
        />
        <TextInput
          type="text"
          inputMode="decimal"
          aria-label="Betrag in Euro"
          placeholder="Betrag in €"
          className="!h-9 !min-h-0 !w-28"
          value={form.amount}
          onChange={(e) => setForm({ ...form, amount: e.target.value })}
        />
        <TextInput
          type="text"
          aria-label="Beschreibung der Kosten"
          placeholder="z. B. Abo für eine Stellenbörse, 1 Monat"
          className="!h-9 !min-h-0 min-w-[12rem] flex-1"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <Button size="sm" onClick={speichern}>Speichern</Button>
      </div>
    </Card>
  );
}
