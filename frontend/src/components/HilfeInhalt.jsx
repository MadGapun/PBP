// Inhalt des Hilfe-Dialogs (G68, #1087 D9). Die Texte stehen in
// lib/hilfe.js; Titel und Beschreibung der Prompts kommen aus
// /api/prompts, also aus demselben Katalog wie der Schnellzugriff.
import { useEffect, useState } from "react";
import { ChevronDown, Copy, ExternalLink, Mail } from "lucide-react";
import { FAQ, HILFE, MELDE_PROMPT, MELDEWEGE, PROBLEME, START_HILFE } from "@/lib/hilfe";

function useKatalog() {
  const [eintraege, setEintraege] = useState(null);
  useEffect(() => {
    let alive = true;
    fetch("/api/prompts")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { if (alive) setEintraege(d?.prompts || []); })
      .catch(() => { if (alive) setEintraege([]); });
    return () => { alive = false; };
  }, []);
  return eintraege;
}

function kennung(p) {
  return p.prompt || p.name || p.id;
}

function PromptKarte({ eintrag, copyPrompt }) {
  return (
    <div className="glass-card flex items-start justify-between gap-3 rounded-lg px-3 py-2.5" data-hilfe-prompt={eintrag.id}>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-ink">{eintrag.titel}</p>
        {eintrag.beschreibung && <p className="mt-0.5 text-[12px] text-muted">{eintrag.beschreibung}</p>}
      </div>
      <button
        type="button"
        onClick={() => copyPrompt(`/${kennung(eintrag)}`)}
        className="flex shrink-0 items-center gap-1.5 rounded-lg bg-sky/10 px-2.5 py-1.5 text-[12px] text-sky transition-colors hover:bg-sky/20"
        aria-label={`Prompt „${eintrag.titel}“ kopieren`}
      >
        <Copy size={13} /> Kopieren
      </button>
    </div>
  );
}

export function HilfeTab({ page, pageTitel, copyPrompt }) {
  const katalog = useKatalog();
  const hilfe = HILFE[page] || HILFE.dashboard;
  const prompts = (katalog || []).filter((p) => hilfe.prompts.includes(p.id));
  return (
    <div className="space-y-3 text-sm text-muted" data-hilfe-tab={page}>
      {pageTitel && <h3 className="text-[12px] font-bold uppercase tracking-[0.15em] text-teal">{pageTitel}</h3>}
      {hilfe.abschnitte.map((a) => (
        <div key={a.titel} className="glass-card p-3">
          <h4 className="mb-1 font-medium text-ink">{a.titel}</h4>
          <p>{a.text}</p>
        </div>
      ))}
      {prompts.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[12px] font-medium text-ink">Mit Claude weiter</p>
          {prompts.map((p) => <PromptKarte key={p.id} eintrag={p} copyPrompt={copyPrompt} />)}
        </div>
      )}
      <div className="glass-card p-3">
        <h4 className="mb-1 font-medium text-ink">{START_HILFE.titel}</h4>
        <p>{START_HILFE.text}</p>
      </div>
    </div>
  );
}

function Aufklapper({ eintraege, vor = false }) {
  return eintraege.map(({ q, a }) => (
    <details key={q} className="glass-card group rounded-lg">
      <summary className="flex cursor-pointer list-none items-center justify-between rounded-lg px-3 py-2.5 text-[13px] font-medium text-ink hover:bg-white/[0.03]">
        {q}
        <ChevronDown size={14} className="text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      {vor
        ? <pre className="whitespace-pre-wrap px-3 pb-2.5 font-sans text-[12.5px]">{a}</pre>
        : <p className="px-3 pb-2.5 text-[12.5px]">{a}</p>}
    </details>
  ));
}

export function FragenTab() {
  return (
    <div className="space-y-2 text-sm text-muted">
      <Aufklapper eintraege={FAQ} />
      <p className="glass-card mt-2 p-3 text-[12px]">
        Ausführlicher im <a href="https://github.com/MadGapun/PBP/wiki/FAQ" target="_blank" rel="noopener noreferrer" className="text-sky hover:underline">PBP-Wiki</a>.
      </p>
    </div>
  );
}

export function ProblemeTab() {
  return (
    <div className="space-y-2 text-sm text-muted">
      <Aufklapper eintraege={PROBLEME} vor />
      <p className="glass-card mt-2 p-3 text-[12px]">
        Nicht gelöst? Unter „Melden“ stehen beide Wege, mit und ohne GitHub-Konto.
      </p>
    </div>
  );
}

export function MeldenTab({ copyPrompt }) {
  return (
    <div className="space-y-3 text-sm text-muted" data-hilfe-melden>
      <div className="glass-card p-3">
        <h4 className="mb-1 font-medium text-ink">Erst mit Claude</h4>
        <p className="mb-2">Claude sucht zuerst eine Lösung und schreibt dann einen Bericht ohne Namen und Kontaktdaten, den du so weitergeben kannst.</p>
        <button
          type="button"
          onClick={() => copyPrompt(`/${MELDE_PROMPT}`)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-sky/10 px-3 py-1.5 text-[13px] text-sky transition-colors hover:bg-sky/20"
        >
          <Copy size={13} /> „Problem melden“ kopieren
        </button>
      </div>
      {MELDEWEGE.map((w) => (
        <div key={w.art} className="glass-card p-3" data-meldeweg={w.art}>
          <h4 className="mb-1 font-medium text-ink">{w.titel}</h4>
          <p className="mb-2">{w.text}</p>
          <div className="flex flex-wrap gap-2">
            <a href={w.fehler} target={w.art === "github" ? "_blank" : undefined} rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-coral/15 px-3 py-1.5 text-[13px] text-coral hover:bg-coral/25">
              {w.art === "mail" ? <Mail size={13} /> : <ExternalLink size={13} />} Fehler melden
            </a>
            <a href={w.wunsch} target={w.art === "github" ? "_blank" : undefined} rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-sky/15 px-3 py-1.5 text-[13px] text-sky hover:bg-sky/25">
              {w.art === "mail" ? <Mail size={13} /> : <ExternalLink size={13} />} Idee vorschlagen
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}
