/**
 * "Dashboard anpassen" — Bereiche an-/abschalten und sortieren (#985)
 *
 * Nutzerwunsch vom 07.09.2026, wortgleich zum Schnellzugriff-Muster aus
 * #979: *"dass man Infobereiche an- und abschalten kann, hier aber auch
 * sortieren, um sich sein eigenes Dashboard zusammenzubasteln."*
 *
 * Bewusst mit Pfeiltasten statt Ziehen und Ablegen: Drag-and-drop
 * braucht eine Bibliothek, funktioniert auf dem Touchpad schlecht und
 * ist mit der Tastatur gar nicht bedienbar. Zwei Pfeile koennen alles,
 * was hier gebraucht wird — die Liste ist acht Zeilen lang.
 */
import { ArrowDown, ArrowUp, RotateCcw, X } from "lucide-react";

import { Button, Card } from "@/components/ui";

export default function DashboardAnpassen({
  katalog, bereiche, onAendern, onZuruecksetzen, onSchliessen,
}) {
  const info = Object.fromEntries((katalog || []).map((k) => [k.id, k]));

  function verschieben(index, richtung) {
    const ziel = index + richtung;
    if (ziel < 0 || ziel >= bereiche.length) return;
    const neu = [...bereiche];
    [neu[index], neu[ziel]] = [neu[ziel], neu[index]];
    onAendern(neu);
  }

  function umschalten(index) {
    const neu = bereiche.map((b, i) =>
      i === index ? { ...b, sichtbar: !b.sichtbar } : b);
    onAendern(neu);
  }

  return (
    <Card className="mb-5 rounded-2xl border border-sky/20 bg-sky/[0.03]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink">Dashboard anpassen</h2>
          <p className="mt-0.5 text-[12px] text-muted/70">
            Reihenfolge und Sichtbarkeit. Was du abschaltest, ist nicht weg —
            es steht weiter in seinem eigenen Tab.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={onZuruecksetzen}>
            <RotateCcw size={13} />
            Voreinstellung
          </Button>
          <Button size="sm" variant="ghost" onClick={onSchliessen}>
            <X size={14} />
            Fertig
          </Button>
        </div>
      </div>

      <ul className="mt-3 grid gap-1">
        {bereiche.map((b, i) => {
          const meta = info[b.id] || {};
          const fest = Boolean(meta.fest);
          return (
            <li
              key={b.id}
              className="flex items-center gap-2 rounded-lg border border-white/[0.05] px-3 py-2"
            >
              <input
                type="checkbox"
                className="shrink-0"
                checked={b.sichtbar}
                disabled={fest}
                onChange={() => umschalten(i)}
                title={fest
                  ? "Dieser Bereich bleibt — einklappen geht trotzdem"
                  : "Bereich anzeigen"}
              />
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium text-ink/90">
                  {meta.titel || b.id}
                  {fest ? (
                    <span className="ml-2 text-[10px] uppercase tracking-[0.1em] text-muted/40">
                      bleibt
                    </span>
                  ) : null}
                </span>
                {meta.beschreibung ? (
                  <span className="block truncate text-[11px] text-muted/60">
                    {meta.beschreibung}
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                onClick={() => verschieben(i, -1)}
                disabled={i === 0}
                title="Nach oben"
                className="shrink-0 rounded p-1 text-muted/50 transition hover:text-sky disabled:opacity-20"
              >
                <ArrowUp size={13} />
              </button>
              <button
                type="button"
                onClick={() => verschieben(i, 1)}
                disabled={i === bereiche.length - 1}
                title="Nach unten"
                className="shrink-0 rounded p-1 text-muted/50 transition hover:text-sky disabled:opacity-20"
              >
                <ArrowDown size={13} />
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
