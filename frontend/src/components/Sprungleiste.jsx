/**
 * Sprungleiste — #1171 (G85, Baustein 2)
 *
 * Eine lange Ansicht (der Dialog „Timeline“ ist rund 2.300 bis 2.600 Pixel hoch bei 650 Pixeln Sicht) bekommt oben eine
 * Leiste mit ihren Abschnitten. Ein Klick bringt den Abschnitt an den oberen Rand — ohne Scrollen, ohne zu suchen.
 * Die Leiste bleibt beim Scrollen stehen und zeigt, in welchem Abschnitt man gerade ist.
 *
 * Gelesen wird, was im Dokument steht: jeder Block mit `data-abschnitt="<Kennung>"` ist ein Ziel. Die Reihenfolge und
 * die Namen legt `lib/wege.js` fest (`TIMELINE_ABSCHNITTE`), ein Abschnitt, den es gerade nicht gibt, fehlt in der Leiste.
 */
import { useEffect, useRef, useState } from "react";

import { cn } from "@/utils";
import { sprungleiste } from "@/lib/wege";

function koerperVon(element) {
  return element?.closest?.("[data-modal-koerper]") || null;
}

export default function Sprungleiste({ wurzelRef, etikett = "Abschnitte", anfang = null }) {
  const leisteRef = useRef(null);
  const [vorhanden, setVorhanden] = useState([]);
  const [aktiv, setAktiv] = useState("");
  const anfangErledigtRef = useRef(0);

  // Welche Abschnitte gibt es gerade? Sie kommen und gehen (Termine erst, wenn es welche gibt). Bewusst `useEffect`:
  // der Bezug (`wurzelRef`) haengt am Elternknoten und ist in einem `useLayoutEffect` des Kindes noch leer.
  useEffect(() => {
    const wurzel = wurzelRef?.current;
    if (!wurzel) return undefined;
    const lesen = () => {
      const liste = [...wurzel.querySelectorAll("[data-abschnitt]")].map((e) => e.getAttribute("data-abschnitt"));
      setVorhanden((vorher) => (vorher.join("|") === liste.join("|") ? vorher : liste));
    };
    lesen();
    const beobachter = new MutationObserver(lesen);
    beobachter.observe(wurzel, { childList: true, subtree: true });
    return () => beobachter.disconnect();
  }, [wurzelRef]);

  // In welchem Abschnitt stehe ich? Der letzte, dessen Oberkante die Leiste erreicht hat.
  useEffect(() => {
    const wurzel = wurzelRef?.current;
    const koerper = koerperVon(wurzel);
    if (!koerper) return undefined;
    let rahmen = 0;
    const pruefen = () => {
      rahmen = 0;
      const grenze = koerper.getBoundingClientRect().top + (leisteRef.current?.offsetHeight || 40) + 24;
      let aktuell = "";
      const alle = [...wurzel.querySelectorAll("[data-abschnitt]")];
      for (const abschnitt of alle) {
        if (abschnitt.getBoundingClientRect().top <= grenze) aktuell = abschnitt.getAttribute("data-abschnitt");
      }
      // Am Ende des Inhalts kann der letzte Abschnitt nicht mehr bis nach oben scrollen — er gilt dann trotzdem
      // als der, in dem man steht (sonst bliebe nach einem Klick auf ihn der vorige Eintrag markiert).
      if (alle.length && koerper.scrollTop + koerper.clientHeight >= koerper.scrollHeight - 2) {
        aktuell = alle[alle.length - 1].getAttribute("data-abschnitt");
      }
      setAktiv(aktuell);
    };
    const beiScroll = () => { if (!rahmen) rahmen = requestAnimationFrame(pruefen); };
    pruefen();
    koerper.addEventListener("scroll", beiScroll, { passive: true });
    return () => {
      koerper.removeEventListener("scroll", beiScroll);
      if (rahmen) cancelAnimationFrame(rahmen);
    };
  }, [wurzelRef, vorhanden]);

  // #1177 (G88): wer einen Treffer der Suche oeffnet, soll im Abschnitt landen, nicht oben — `anfang` ist
  // `{ kennung, nr }`; `nr` ist je Oeffnen neu, damit derselbe Abschnitt beim naechsten Oeffnen wieder gilt. Gesprungen wird,
  // sobald der Abschnitt im Dialog steht (die Termine kommen mit den Daten).
  useEffect(() => {
    if (!anfang?.kennung || anfangErledigtRef.current === anfang.nr) return;
    if (!vorhanden.includes(anfang.kennung)) return;
    anfangErledigtRef.current = anfang.nr;
    springe(anfang.kennung, true);
  }, [anfang, vorhanden]);

  function springe(kennung, sofort = false) {
    const wurzel = wurzelRef?.current;
    const ziel = wurzel?.querySelector(`[data-abschnitt="${kennung}"]`);
    const koerper = koerperVon(wurzel);
    if (!ziel || !koerper) return;
    const leiste = leisteRef.current?.offsetHeight || 40;
    const oben = ziel.getBoundingClientRect().top - koerper.getBoundingClientRect().top + koerper.scrollTop - leiste - 8;
    const ruhig = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    koerper.scrollTo({ top: Math.max(0, oben), behavior: ruhig || sofort ? "auto" : "smooth" });
    setAktiv(kennung);
  }

  const eintraege = sprungleiste(vorhanden);
  if (eintraege.length < 2) return null;

  return (
    <nav
      ref={leisteRef}
      aria-label={etikett}
      data-sprungleiste
      className="sticky -top-5 z-20 -mx-6 -mt-5 flex flex-wrap items-center gap-1.5 border-b border-white/8 bg-shell/95 px-6 py-2 backdrop-blur"
    >
      <span className="mr-1 text-xs text-muted">Springe zu:</span>
      {eintraege.map((e) => (
        <button
          key={e.kennung}
          type="button"
          data-sprung-abschnitt={e.kennung}
          aria-current={aktiv === e.kennung ? "true" : undefined}
          onClick={() => springe(e.kennung)}
          className={cn(
            "rounded-full px-3 py-1 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/30",
            aktiv === e.kennung ? "bg-sky/15 text-sky" : "text-muted hover:bg-white/[0.06] hover:text-ink"
          )}
        >
          {e.label}
        </button>
      ))}
    </nav>
  );
}
