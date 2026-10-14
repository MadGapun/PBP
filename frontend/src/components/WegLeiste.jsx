/**
 * WegLeiste — #1171 (G85, Baustein 3)
 *
 * Die feste Leiste oben in der Ansicht eines Falls (Stelle, Bewerbung, Kontakt): links der Rückweg, in der Mitte die anderen
 * Ansichten desselben Falls, rechts der nächste Schritt. Sie liegt über dem scrollenden Inhalt des Dialogs und bleibt deshalb
 * beim Scrollen stehen — wer weiterwill, muss nie nach unten scrollen.
 *
 * Was in die Leiste kommt, rechnet `lib/wegleiste.js` (rein, mit Test); hier wird gezeichnet und der Klick weitergereicht:
 *   * Rückweg: dorthin, woher man kam (`von`), sonst schließt er den Dialog (die Liste steht darunter, samt Filter).
 *   * Fälle: mit einem Objekt öffnet der Klick es, mit mehreren erscheint eine kurze Auswahl.
 *   * Hauptknopf und „weitere Wege“: `onAktion(<kennung>)` — was die Kennung tut, weiß die Seite.
 *
 * Jede Navigation aus der Leiste nimmt `selbst` als `von` mit; die Zielseite zeigt damit ihren Rückweg.
 */
import { ChevronDown, ChevronLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useApp } from "@/app-context";
import MitClaude from "@/components/MitClaude";
import { cn } from "@/utils";

function Schritt({ schritt, onAktion, haupt = false }) {
  const inhalt = schritt.mitClaude ? <MitClaude size={14}>{schritt.label}</MitClaude> : schritt.label;
  return (
    <button
      type="button"
      data-weg-aktion={schritt.aktion}
      data-weg-haupt={haupt ? "ja" : undefined}
      onClick={() => onAktion?.(schritt.aktion)}
      className={cn(
        "inline-flex h-9 items-center gap-2 whitespace-nowrap rounded-xl px-3.5 text-[13px] font-medium transition-colors",
        haupt
          ? "bg-teal/85 font-semibold text-shell hover:bg-teal/95"
          : "text-ink hover:bg-white/[0.06]"
      )}
    >
      {inhalt}
    </button>
  );
}

export default function WegLeiste({ leiste, selbst = null, von = null, onVerlassen, onZurueck, onAktion, className }) {
  const { navigateTo } = useApp();
  const [offen, setOffen] = useState("");        // Kennung des geöffneten Fall-Menüs oder "weitere"
  const wurzelRef = useRef(null);

  useEffect(() => {
    if (!offen) return undefined;
    const aussen = (event) => {
      if (wurzelRef.current && !wurzelRef.current.contains(event.target)) setOffen("");
    };
    // #1213: Escape schliesst zuerst das Menue, nicht den ganzen Dialog. Der Dialog hoert auf `document` (Blasen-Phase); dieser
    // Listener sitzt in der Fang-Phase davor und haelt das Ereignis an. Der Fokus kehrt zum Ausloeser zurueck.
    const taste = (event) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      event.preventDefault();
      wurzelRef.current?.querySelector('[aria-expanded="true"]')?.focus?.();
      setOffen("");
    };
    document.addEventListener("mousedown", aussen);
    document.addEventListener("keydown", taste, true);
    return () => {
      document.removeEventListener("mousedown", aussen);
      document.removeEventListener("keydown", taste, true);
    };
  }, [offen]);

  if (!leiste) return null;

  const oeffnen = (ziel) => {
    if (!ziel) return;
    setOffen("");
    onVerlassen?.();
    navigateTo(ziel.seite, { ...(ziel.intent || {}), von: selbst || undefined });
  };

  const zurueck = () => {
    setOffen("");
    onVerlassen?.();
    if (von?.seite) {
      navigateTo(von.seite, { ...(von.intent || {}), zurueckVon: true });
    } else {
      onZurueck?.();
    }
  };

  const rueckLabel = von?.label ? `Zurück zu ${von.label}` : leiste.zurueck?.label || "Zurück";

  return (
    <nav
      ref={wurzelRef}
      aria-label="Weg-Leiste"
      data-weg-leiste={leiste.art}
      className={cn(
        "flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1 border-b border-white/6 bg-white/[0.02] px-4 py-2",
        className
      )}
    >
      <button
        type="button"
        data-weg-zurueck
        onClick={zurueck}
        title={rueckLabel}
        className="inline-flex h-9 max-w-[16rem] items-center gap-1 rounded-xl px-2.5 text-[13px] font-medium text-muted transition-colors hover:bg-white/[0.06] hover:text-ink"
      >
        <ChevronLeft size={15} aria-hidden="true" className="shrink-0" />
        <span className="truncate">{rueckLabel}</span>
      </button>

      <span className="hidden h-5 w-px bg-white/10 sm:block" aria-hidden="true" />

      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1" data-weg-faelle>
        {leiste.faelle.map((f) => {
          const einzeln = f.anzahl === 1;
          const istOffen = offen === f.id;
          return (
            <div key={f.id} className="relative" data-weg-fall={f.id}>
              <button
                type="button"
                aria-haspopup={einzeln ? undefined : "menu"}
                aria-expanded={einzeln ? undefined : istOffen}
                title={einzeln ? `${f.label} öffnen` : `${f.anzahl} ${f.label} — Auswahl`}
                onClick={() => (einzeln ? oeffnen(f.eintraege[0].ziel) : setOffen(istOffen ? "" : f.id))}
                className="inline-flex h-9 items-center gap-1 whitespace-nowrap rounded-xl px-3 text-[13px] text-ink transition-colors hover:bg-white/[0.06]"
              >
                {f.label}
                {f.anzahl > 1 ? <span className="text-xs text-muted">{f.anzahl}</span> : null}
                {einzeln ? null : <ChevronDown size={13} aria-hidden="true" className="text-muted" />}
              </button>
              {!einzeln && istOffen ? (
                <ul
                  role="menu"
                  data-weg-menue={f.id}
                  className="absolute left-0 top-full z-50 mt-1 max-h-64 min-w-[14rem] max-w-[22rem] overflow-y-auto rounded-xl border border-white/10 bg-shell p-1 shadow-2xl shadow-black/40"
                >
                  {f.eintraege.map((e, i) => (
                    <li key={`${f.id}-${i}`} role="none">
                      <button
                        type="button"
                        role="menuitem"
                        data-weg-eintrag
                        onClick={() => oeffnen(e.ziel)}
                        className="block w-full truncate rounded-lg px-3 py-1.5 text-left text-[13px] text-ink hover:bg-white/[0.06]"
                      >
                        {e.label}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>

      {leiste.haupt ? (
        <div className="relative ml-auto flex items-center gap-1" data-weg-schritt>
          <Schritt schritt={leiste.haupt} onAktion={(a) => { setOffen(""); onAktion?.(a); }} haupt />
          {leiste.weitere.length ? (
            <>
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={offen === "weitere"}
                aria-label="Weitere Wege"
                title="Weitere Wege"
                data-weg-weitere
                onClick={() => setOffen(offen === "weitere" ? "" : "weitere")}
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-muted transition-colors hover:bg-white/[0.06] hover:text-ink"
              >
                <ChevronDown size={15} aria-hidden="true" />
              </button>
              {offen === "weitere" ? (
                <ul
                  role="menu"
                  className="absolute right-0 top-full z-50 mt-1 min-w-[14rem] rounded-xl border border-white/10 bg-shell p-1 shadow-2xl shadow-black/40"
                >
                  {leiste.weitere.map((w) => (
                    <li key={w.aktion} role="none">
                      <button
                        type="button"
                        role="menuitem"
                        data-weg-aktion={w.aktion}
                        onClick={() => { setOffen(""); onAktion?.(w.aktion); }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-[13px] text-ink hover:bg-white/[0.06]"
                      >
                        {w.mitClaude ? <MitClaude size={13}>{w.label}</MitClaude> : w.label}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </nav>
  );
}
