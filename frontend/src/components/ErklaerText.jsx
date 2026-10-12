// Ein Erklärtext, der sich einklappen lässt (#1170 U11): „Was ist das?“ mit gemerktem Zustand.
//
// Der Kopf trägt den Titel und ist der Schalter; darunter steht der Text. Ob er aufgeklappt steht, entscheidet die Wahl des Menschen
// für DIESEN Erklärtext, sonst der Schalter „Erklärtexte zeigen“ unter Einstellungen › Erscheinungsbild (Vorgabe: aufgeklappt, wie
// bisher). Die Logik steht in lib/erklaertexte.js; hier nur das Zeichnen.

import { ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";

import { aufgeklappt, EREIGNIS, leseAlle, leseEinzeln, schreibeEinzeln } from "@/lib/erklaertexte";
import { cn } from "@/utils";

export default function ErklaerText({ id, titel = "Was ist das?", children, className, titelKlasse, ...rest }) {
  const [alle, setAlle] = useState(leseAlle);
  const [einzeln, setEinzeln] = useState(() => leseEinzeln(id));

  useEffect(() => {
    const neuLesen = () => {
      setAlle(leseAlle());
      setEinzeln(leseEinzeln(id));
    };
    window.addEventListener(EREIGNIS, neuLesen);
    return () => window.removeEventListener(EREIGNIS, neuLesen);
  }, [id]);

  const offen = aufgeklappt(alle, einzeln);

  return (
    <div
      className={cn("rounded-xl border border-white/8 bg-white/[0.02] p-3 text-xs text-muted", className)}
      data-erklaertext={id}
      data-offen={offen ? "ja" : "nein"}
      {...rest}
    >
      <button
        type="button"
        aria-expanded={offen}
        onClick={() => {
          setEinzeln(!offen);
          schreibeEinzeln(id, !offen);
        }}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className={cn("font-medium", titelKlasse)}>{titel}</span>
        <ChevronDown
          size={14}
          aria-hidden="true"
          className={cn("shrink-0 text-muted transition-transform", offen && "rotate-180")}
        />
      </button>
      {offen ? <div className="mt-2" data-erklaertext-inhalt>{children}</div> : null}
    </div>
  );
}
