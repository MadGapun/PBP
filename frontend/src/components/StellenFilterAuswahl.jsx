// #1307/#1308: eigene Ansichten und die Sprache der Anzeige im Stellen-Tab.
//
// Gefiltert wird auf dem SERVER (`services/stellen_liste.py` ruft `stellen_filter.passt`, dieselbe Pruefung wie
// `stellen_bulk_bewerten` und die Regeln); hier stehen nur die beiden Auswahlfelder und das Abzeichen an der Stelle. Die
// Ansichten legt der Mensch mit Claude an („Speichere mir eine Ansicht …“); die Regeln stehen unter Einstellungen › Automatik.

import { useEffect, useState } from "react";

import { api } from "@/api";
import { Badge, SelectInput } from "@/components/ui";
import { SPRACH_AUSWAHL, spracheAbzeichen } from "@/lib/stellenFilter";
import { cn } from "@/utils";

const FELD = "!h-9 !min-h-0 !w-auto !rounded-xl !pl-3 !pr-3 !py-0 !text-[13px]";
const AKTIV = "!border-teal/20 !bg-teal/8 !text-teal";
const RUHIG = "!border-white/5 !bg-white/[0.03] !text-muted";

/** Die Auswahl „Sprache“ — der Wert geht unverändert an den Server (`sprache=de,gemischt`). */
export function SprachFilter({ wert, onChange }) {
  return (
    <SelectInput
      aria-label="Sprache der Anzeige"
      title="Die Sprache erkennt PBP aus dem Anzeigentext. Ohne oder mit zu kurzem Text ist sie unbekannt."
      className={cn(FELD, wert ? AKTIV : RUHIG)}
      value={wert || ""}
      onChange={(event) => onChange(event.target.value)}
    >
      {SPRACH_AUSWAHL.map((e) => (
        <option key={e.wert || "alle"} value={e.wert}>{e.text}</option>
      ))}
    </SelectInput>
  );
}

/**
 * Die gespeicherten Ansichten (und Regeln — wer sehen will, was eine Regel trifft, wählt sie hier). Ohne gespeicherten Filter
 * erscheint nichts: die Liste soll nicht mit einem leeren Feld anfangen.
 * Geladen wird einmal beim Öffnen (nicht an `pushToast` gebunden, siehe MERKE in CLAUDE.md).
 */
export function AnsichtAuswahl({ wert, onChange, onNamen }) {
  const [filter, setFilter] = useState([]);
  useEffect(() => {
    let aktiv = true;
    api("/api/stellen-filter")
      .then((d) => {
        if (!aktiv) return;
        const liste = [...(d?.ansichten || []), ...(d?.regeln || [])];
        setFilter(liste);
        if (onNamen) onNamen(Object.fromEntries(liste.map((f) => [String(f.id), f.name])));
      })
      .catch(() => aktiv && setFilter([]));
    return () => { aktiv = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const gewaehltFehlt = wert && !filter.some((f) => String(f.id) === String(wert));
  if (!filter.length && !wert) return null;
  return (
    <SelectInput
      aria-label="Gespeicherte Ansicht"
      title="Eigene Ansichten legst du mit Claude an; Regeln stehen unter Einstellungen › Automatik."
      className={cn(FELD, wert ? AKTIV : RUHIG)}
      value={wert || ""}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">Ansicht: keine</option>
      {gewaehltFehlt ? <option value={wert}>Ansicht nicht mehr vorhanden</option> : null}
      {filter.map((f) => (
        <option key={f.id} value={String(f.id)} title={f.beschreibung}>
          {f.art === "regel" ? `Regel: ${f.name}` : f.name}
        </option>
      ))}
    </SelectInput>
  );
}

/** Das dezente Merkmal an der Stellenkarte: nur bei Englisch, gemischt oder einer anderen Sprache. */
export function SpracheMarke({ job }) {
  const marke = spracheAbzeichen(job);
  if (!marke) return null;
  return (
    <span title={marke.titel} data-sprache={job.sprache}>
      <Badge tone="neutral">{marke.text}</Badge>
    </span>
  );
}
