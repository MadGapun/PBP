// Die Hilfe zum Fragen (#1233, F51): eine Frage zur Bedienung, beantwortet aus Hilfe, Haeufigen Fragen, Wiki und Prompt-Katalog.
//
// Dieselbe Komponente sitzt im Hilfe-Dialog (Reiter "Frag mich", fuer alle) und in der Seitenleiste (kompakt, nur wenn die lokale KI
// laeuft). Die Karten kommen vom Server und nie aus einem Sprachmodell; die lokale KI kann hoechstens eine Kurzantwort darueberlegen,
// wenn der Mensch das eingeschaltet hat. Fragen werden nicht gespeichert: der Verlauf lebt nur hier im Arbeitsspeicher.
//
// Kopiert wird ueber `copyPrompt` (App-Kontext, G72), gesprungen ueber `onOeffnen` (navigateTo der App).
import { useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, Search } from "lucide-react";

import { api, postJson } from "@/api";
import MitClaude from "@/components/MitClaude";
import { SETTINGS_REITER } from "@/lib/einstellungenReiter";
import {
  BEISPIELFRAGEN, aktionen, bereinigeFrage, hatKarten, kannFragen, kiAnzeige, kiOffen, kopfzeile, satzFuerClaude, verlaufMit, vorigeFrage,
} from "@/lib/hilfeFrage";
import { sichereAdresse } from "@/lib/webAdresse";
import { PAGE_IDS } from "@/utils";

const REITER_IDS = SETTINGS_REITER.map((r) => r.id);
const POLL_MS = 1500;
const POLL_HOECHSTENS_MS = 150 * 1000;

function Karte({ karte, kompakt, onOeffnen, copyPrompt }) {
  const wege = aktionen(karte, PAGE_IDS, REITER_IDS);
  return (
    <div className={`glass-card rounded-lg ${kompakt ? "p-2" : "p-3"}`} data-hilfe-karte={karte.id}>
      <h4 className={`font-medium text-ink ${kompakt ? "text-xs" : "text-[13px]"}`}>{karte.titel}</h4>
      <p className={`mt-0.5 whitespace-pre-line text-muted ${kompakt ? "line-clamp-4 text-xs" : "text-[12.5px]"}`}>{karte.kurz}</p>
      <p className="mt-1 text-xs text-muted" data-hilfe-quelle>{karte.quelle}</p>
      {wege.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {wege.map((w) => {
            if (w.art === "oeffnen") {
              return (
                <button key="oeffnen" type="button" data-hilfe-aktion="oeffnen" onClick={() => onOeffnen?.(w.page, w.intent)}
                  className="rounded-lg bg-teal/15 px-2.5 py-1 text-[12px] text-teal transition-colors hover:bg-teal/25">
                  {w.label}
                </button>
              );
            }
            if (w.art === "wiki") {
              return (
                <a key="wiki" href={sichereAdresse(w.url)} target="_blank" rel="noopener noreferrer" data-hilfe-aktion="wiki"
                  className="inline-flex items-center gap-1 rounded-lg bg-white/[0.05] px-2.5 py-1 text-[12px] text-sky transition-colors hover:bg-white/[0.09]">
                  <ExternalLink size={11} aria-hidden="true" /> {w.label}
                </a>
              );
            }
            return (
              <button key="prompt" type="button" data-hilfe-aktion="prompt" onClick={() => copyPrompt?.(w.text)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-sky/10 px-2.5 py-1 text-[12px] text-sky transition-colors hover:bg-sky/20"
                aria-label={`Prompt „${w.label}“ kopieren`}>
                <MitClaude size={12}>{w.label}</MitClaude>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Antwort({ eintrag, kompakt, onOeffnen, copyPrompt }) {
  const { antwort } = eintrag;
  const [alle, setAlle] = useState(false);
  const ki = kiAnzeige(antwort.ki, eintrag.kiStand);
  const karten = antwort.karten || [];
  const sichtbar = kompakt && !alle ? karten.slice(0, 1) : karten;
  const satz = satzFuerClaude(antwort);
  return (
    <div className="space-y-1.5" data-hilfe-antwort={antwort.status}>
      <p className="text-xs text-ink/80" data-hilfe-frage-text>
        <span className="text-muted">Frage: </span>{eintrag.frage}
      </p>
      {kopfzeile(antwort) && <p className={`font-medium text-ink ${kompakt ? "text-xs" : "text-[13px]"}`}>{kopfzeile(antwort)}</p>}
      {ki.zeigen && (
        <div className="rounded-lg border border-teal/25 bg-teal/[0.06] p-2" data-hilfe-ki>
          {ki.wartet ? (
            <p className="flex items-center gap-1.5 text-[12px] text-muted">
              <Loader2 size={12} className="animate-spin" aria-hidden="true" /> Die lokale KI formuliert eine Kurzantwort aus den Abschnitten …
            </p>
          ) : (
            <>
              <p className={`text-ink ${kompakt ? "text-[12px]" : "text-[13px]"}`} data-hilfe-ki-text>{ki.text}</p>
              <p className="mt-1 text-xs text-muted">Von der lokalen KI aus den Abschnitten unten formuliert. Prüfe die Quelle.</p>
            </>
          )}
        </div>
      )}
      {hatKarten(antwort) && sichtbar.map((k) => <Karte key={k.id} karte={k} kompakt={kompakt} onOeffnen={onOeffnen} copyPrompt={copyPrompt} />)}
      {kompakt && !alle && karten.length > 1 && (
        <button type="button" onClick={() => setAlle(true)} className="text-xs text-teal underline decoration-dotted hover:text-teal">
          {karten.length - 1} weiter{karten.length - 1 === 1 ? "er" : "e"} Treffer zeigen
        </button>
      )}
      {satz && (
        <div className="pt-0.5">
          <p className="mb-1 text-xs text-muted">
            {hatKarten(antwort) && antwort.status === "gefunden" ? "Passt das nicht?" : "Dafür ist Claude da."}
          </p>
          <button type="button" data-hilfe-satz onClick={() => copyPrompt?.(satz)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky/10 px-2.5 py-1 text-[12px] text-sky transition-colors hover:bg-sky/20">
            <MitClaude size={12}>Frage kopieren</MitClaude>
          </button>
        </div>
      )}
    </div>
  );
}

export default function HilfeFrage({ variante = "voll", onOeffnen, copyPrompt, onToast }) {
  const kompakt = variante === "kompakt";
  const [eingabe, setEingabe] = useState("");
  const [verlauf, setVerlauf] = useState([]);
  const [laeuft, setLaeuft] = useState(false);
  const zaehler = useRef(0);
  const timer = useRef(new Map());
  const aktiv = useRef(true);

  useEffect(() => {
    aktiv.current = true;
    const laufende = timer.current;
    return () => {
      aktiv.current = false;
      laufende.forEach((t) => clearInterval(t));
      laufende.clear();
    };
  }, []);

  function kiPollen(id, job) {
    const start = Date.now();
    const t = setInterval(async () => {
      if (!aktiv.current || Date.now() - start > POLL_HOECHSTENS_MS) {
        clearInterval(t);
        timer.current.delete(id);
        return;
      }
      try {
        const stand = await api(`/api/hilfe/ki/${encodeURIComponent(job)}`);
        if (!aktiv.current) return;
        setVerlauf((v) => v.map((e) => (e.id === id ? { ...e, kiStand: stand } : e)));
        if (stand.status !== "laeuft") {
          clearInterval(t);
          timer.current.delete(id);
        }
      } catch {
        clearInterval(t);
        timer.current.delete(id);
        setVerlauf((v) => v.map((e) => (e.id === id ? { ...e, kiStand: { status: "fehler" } } : e)));
      }
    }, POLL_MS);
    timer.current.set(id, t);
  }

  // `text` ist eine angeklickte Beispielfrage; sonst gilt, was im Feld steht.
  async function fragen(event, text) {
    event?.preventDefault?.();
    const frage = bereinigeFrage(typeof text === "string" ? text : eingabe);
    if (!kannFragen(frage) || laeuft) return;
    setLaeuft(true);
    try {
      const antwort = await postJson("/api/hilfe/frage", { frage, vorherige: vorigeFrage(verlauf), mit_ki: true });   // ob eine Kurzantwort entsteht, entscheidet der Server (Schalter, lokale KI)
      zaehler.current += 1;
      const eintrag = { id: zaehler.current, frage: antwort.frage || frage, antwort, kiStand: null };
      setVerlauf((v) => verlaufMit(v, eintrag));
      setEingabe("");
      if (kiOffen(antwort.ki, null)) kiPollen(eintrag.id, antwort.ki.job);
    } catch (error) {
      onToast?.(error?.message || "Die Hilfe antwortet gerade nicht. Versuche es gleich noch einmal.", "danger");
    } finally {
      setLaeuft(false);
    }
  }

  const neueste = [...verlauf].reverse();
  return (
    <div className={kompakt ? "space-y-2" : "space-y-3"} data-hilfe-frage={variante}>
      {!kompakt && (
        <div className="text-sm text-muted">
          <p>
            Stell eine Frage zur Bedienung von PBP. Ich suche in der Hilfe, den häufigen Fragen, dem Wiki und den Prompts für Claude und
            zeige dir, wo es steht.
          </p>
          <p className="mt-1 text-[12px]">Deine Frage wird nicht gespeichert.</p>
        </div>
      )}
      <form onSubmit={fragen} className="flex items-center gap-1.5">
        <input
          type="text"
          value={eingabe}
          onChange={(e) => setEingabe(e.target.value)}
          maxLength={400}
          placeholder={kompakt ? "Frag zur Bedienung …" : "Zum Beispiel: Wo stelle ich ein, dass sich PBP selbst aktualisiert?"}
          aria-label="Frage zur Bedienung von PBP"
          data-hilfe-eingabe
          className={`glass-input min-w-0 flex-1 rounded-lg text-ink ${kompakt ? "px-2 py-1 text-xs" : "px-3 py-2 text-sm"}`}
        />
        <button type="submit" disabled={!kannFragen(eingabe) || laeuft} data-hilfe-abschicken aria-label="Frage abschicken"
          className={`inline-flex shrink-0 items-center gap-1 rounded-lg bg-teal/15 text-teal transition-colors hover:bg-teal/25 disabled:opacity-40 ${kompakt ? "px-2 py-1 text-xs" : "px-3 py-2 text-sm"}`}>
          {laeuft ? <Loader2 size={13} className="animate-spin" aria-hidden="true" /> : <Search size={13} aria-hidden="true" />}
          {!kompakt && "Fragen"}
        </button>
      </form>
      {!kompakt && verlauf.length === 0 && (
        <div className="space-y-1.5" data-hilfe-beispiele>
          <p className="text-[12px] text-muted">Nicht sicher, was du fragen sollst? Zum Beispiel:</p>
          <div className="flex flex-wrap gap-1.5">
            {BEISPIELFRAGEN.map((beispiel) => (
              <button
                key={beispiel}
                type="button"
                disabled={laeuft}
                onClick={() => fragen(null, beispiel)}
                data-hilfe-beispiel
                className="rounded-full border border-white/10 px-2.5 py-1 text-left text-[12px] text-muted transition-colors hover:border-teal/40 hover:text-ink disabled:opacity-40"
              >
                {beispiel}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className={kompakt ? "max-h-[38vh] space-y-3 overflow-y-auto pr-1" : "space-y-4"} aria-live="polite" data-hilfe-verlauf>
        {neueste.map((e) => (
          <Antwort key={e.id} eintrag={e} kompakt={kompakt} onOeffnen={onOeffnen} copyPrompt={copyPrompt} />
        ))}
      </div>
    </div>
  );
}
