/**
 * Ein einklappbarer Dashboard-Bereich — v1.7.35 (#985)
 *
 * Nutzerwunsch vom 07.09.2026:
 *
 *   "Ich haette gerne das ganze Kapitel einklappbar. [...] manche wollen
 *   es, andere nicht. manche zum anklicken, manche offen."
 *
 * Und dazu: an- und abschaltbar sowie sortierbar, damit sich jeder sein
 * eigenes Dashboard zusammenstellt.
 *
 * Der Zustand liegt beim Nutzer (`profile_settings`), nicht im Browser:
 * er soll den Rechner ueberleben, nicht nur die Sitzung. Deshalb meldet
 * die Komponente jede Aenderung nach oben, statt selbst zu speichern.
 */
import { ChevronDown, ChevronRight } from "lucide-react";

export default function DashboardBereich({
  titel, offen, onUmschalten, kopfZusatz, children,
}) {
  if (offen) {
    return (
      <section className="min-w-0">
        {/* Ausgeklappt traegt der Inhalt seine eigene Ueberschrift —
            ein zweiter Titel darueber waere die Wiederholung, gegen die
            das Dashboard gerade aufgeraeumt wurde (#976, #984). Der
            Griff zum Einklappen sitzt deshalb als schmale Leiste
            daneben. */}
        <div className="mb-1 flex items-center justify-end gap-2">
          {kopfZusatz}
          <button
            type="button"
            onClick={onUmschalten}
            title={`${titel} einklappen`}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted/40 transition hover:text-muted"
          >
            <ChevronDown size={12} />
            einklappen
          </button>
        </div>
        {children}
      </section>
    );
  }

  return (
    <section className="min-w-0">
      <button
        type="button"
        onClick={onUmschalten}
        className="glass-tab flex w-full items-center gap-2 rounded-xl px-4 py-2.5 text-left transition"
        title={`${titel} ausklappen`}
      >
        <ChevronRight size={14} className="shrink-0 text-muted/50" />
        <span className="text-[13px] font-semibold text-ink/80">{titel}</span>
        {kopfZusatz ? (
          <span className="ml-auto text-[11px] text-muted/50">{kopfZusatz}</span>
        ) : null}
      </button>
    </section>
  );
}
