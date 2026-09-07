/**
 * Schnellzugriff „Mit Claude" — v1.7.33 (#979, G29)
 *
 * Die Karten kamen bis v1.7.32 aus einer festen Liste IM Frontend:
 * Prompt, Label, Beschreibung und Icon standen hier, und dieselben
 * Titel noch einmal im META-Dict von `dashboard.py`. Eine Umbenennung
 * musste zweimal passieren; „Inbound erfassen" hiess deshalb jahrelang
 * anders als das, was der Prompt tut.
 *
 * Jetzt rendert diese Komponente aus `/api/prompts`, also aus
 * `services/prompt_katalog.py`. Sie traegt keinen einzigen Prompt-Text
 * mehr — nur noch die Zuordnung Icon-Kennung zu Symbol, weil ein
 * Python-Modul keine lucide-Komponente halten kann.
 *
 * Der Nutzer waehlt selbst, was hier steht (Zahnrad). Die Auswahl liegt
 * in `profile_settings` und ueberlebt Update und Neustart; ohne Auswahl
 * gilt der Katalog-Standard, damit sich fuer Bestandsnutzer nichts
 * aendert.
 */
import { useCallback, useEffect, useState } from "react";
import {
  BarChart3, BookOpen, Briefcase, Bug, CheckSquare, FileText, HandCoins,
  HelpCircle, Inbox, Info, List, Mail, MailPlus, Mic, Network, PenLine,
  PlayCircle, PlusCircle, RefreshCw, Search, Send, Settings2, Sparkles,
  TrendingDown, UserCheck,
} from "lucide-react";

import { Button, Card } from "@/components/ui";

// Die einzige Stelle, an der das Frontend noch etwas ueber einen Prompt
// weiss: welches Symbol dazu passt. Alles andere kommt aus dem Katalog.
const SYMBOLE = {
  play: PlayCircle, book: BookOpen, plus: PlusCircle, refresh: RefreshCw,
  list: List, search: Search, send: Send, file: FileText, pen: PenLine,
  mail: MailPlus, check: CheckSquare, inbox: Inbox, briefcase: Briefcase,
  mic: Mic, coins: HandCoins, chart: BarChart3, usercheck: UserCheck,
  trending: TrendingDown, network: Network, sparkles: Sparkles, bug: Bug,
  help: HelpCircle, envelope: Mail,
};

function symbol(kennung) {
  return SYMBOLE[kennung] || Sparkles;
}

function slash(eintrag) {
  return `/${eintrag.prompt || eintrag.id}`;
}

export default function SchnellzugriffKarten({ copyPrompt, openHelp, pushToast }) {
  const [katalog, setKatalog] = useState(null);
  const [gewaehlt, setGewaehlt] = useState([]);
  const [kategorien, setKategorien] = useState([]);
  const [auswahlOffen, setAuswahlOffen] = useState(false);
  const [hilfeOffen, setHilfeOffen] = useState(() => {
    try {
      const gespeichert = localStorage.getItem("pbp_dashboard_quickhelp_open");
      return gespeichert === null ? true : gespeichert === "1";
    } catch {
      return true;
    }
  });

  const laden = useCallback(() => {
    fetch("/api/prompts")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setKatalog(d.prompts || []);
        setGewaehlt(d.schnellzugriff || []);
        setKategorien(d.kategorien || []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  async function speichern(ids) {
    setGewaehlt(ids);
    try {
      await fetch("/api/prompts/schnellzugriff", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompts: ids }),
      });
    } catch {
      pushToast?.("Auswahl konnte nicht gespeichert werden.", "danger");
      laden();
    }
  }

  function umschalten(id) {
    speichern(gewaehlt.includes(id)
      ? gewaehlt.filter((x) => x !== id)
      : [...gewaehlt, id]);
  }

  if (!katalog) return null;

  const sichtbar = katalog.filter((e) => gewaehlt.includes(e.id));
  const gruppen = (kategorien.length ? kategorien : [...new Set(katalog.map((e) => e.kategorie))])
    .map((k) => [k, sichtbar.filter((e) => e.kategorie === k)])
    .filter(([, items]) => items.length);

  return (
    <Card className="rounded-2xl">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <h2 className="text-sm font-semibold text-ink">Schnellzugriff</h2>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setAuswahlOffen((v) => !v)}
          title="Auswählen, welche Karten hier stehen"
        >
          <Settings2 size={14} />
          {auswahlOffen ? "Fertig" : "Auswählen"}
        </Button>
      </div>

      <details
        className="mt-1.5 rounded-lg border border-sky/15 bg-sky/[0.05] px-3 py-2 group"
        open={hilfeOffen}
        onToggle={(e) => {
          const offen = e.currentTarget.open;
          setHilfeOffen(offen);
          try { localStorage.setItem("pbp_dashboard_quickhelp_open", offen ? "1" : "0"); } catch { /* private Sitzung */ }
        }}
      >
        <summary className="cursor-pointer list-none flex items-center gap-2 text-[12px] text-muted/80">
          <Info size={13} className="shrink-0 text-sky/70" />
          <span className="flex-1"><strong className="text-ink/90">Was ist der Schnellzugriff?</strong></span>
          <span className="text-muted/50 text-[10px] group-open:rotate-90 transition-transform shrink-0">▶</span>
        </summary>
        <p className="mt-2 pl-[21px] text-[12px] text-muted/80 leading-relaxed">
          Beispiel-Prompts für Claude Desktop. <strong className="text-ink/90">Klick auf eine Karte
          kopiert den Prompt in die Zwischenablage</strong> — danach in Claude einfügen und absenden.
          Du kannst auch frei mit Claude reden; das hier sind nur Vorschläge für häufige Workflows.
          {/* #979 Befund 4: hier stand ein Satz, der auf die Hilfe VERWIES,
              ohne sie öffnen zu können — der Öffner lag als State in App.jsx
              und wurde nirgends durchgereicht. */}
          {" "}
          <button
            type="button"
            className="text-sky hover:underline"
            onClick={() => openHelp?.("prompts")}
          >
            Alle {katalog.length} Prompts ansehen
          </button>
        </p>
      </details>

      {auswahlOffen ? (
        <div className="mt-3 rounded-xl border border-white/[0.06] p-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <p className="text-[12px] text-muted/70">
              Hier auswählen, was auf dem Dashboard steht. Abgewählte Prompts bleiben in der Hilfe erreichbar.
            </p>
            <Button size="sm" variant="ghost" onClick={() => speichern([])}>
              Voreinstellung
            </Button>
          </div>
          {(kategorien.length ? kategorien : []).map((k) => {
            const items = katalog.filter((e) => e.kategorie === k);
            if (!items.length) return null;
            return (
              <div key={k} className="mt-3">
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-teal/60">{k}</p>
                <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {items.map((e) => (
                    <label key={e.id} className="flex items-start gap-2 rounded-lg px-2 py-1.5 text-[12px] hover:bg-white/[0.03]">
                      <input
                        type="checkbox"
                        className="mt-0.5 shrink-0"
                        checked={gewaehlt.includes(e.id)}
                        onChange={() => umschalten(e.id)}
                      />
                      <span className="min-w-0">
                        <span className="block font-medium text-ink/90">{e.titel}</span>
                        <span className="block text-muted/60">{e.beschreibung}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : gruppen.length === 0 ? (
        <p className="mt-3 text-[12px] text-muted/70">
          Keine Karten ausgewählt.{" "}
          <button type="button" className="text-sky hover:underline" onClick={() => setAuswahlOffen(true)}>
            Auswählen
          </button>
        </p>
      ) : (
        gruppen.map(([kategorie, items]) => (
          <div key={kategorie} className="mt-3">
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-teal/60">{kategorie}</p>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
              {items.map((e) => {
                const Symbol = symbol(e.icon);
                return (
                  <button
                    key={e.id}
                    type="button"
                    className="glass-tab flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-left transition"
                    onClick={() => copyPrompt(slash(e))}
                    title={e.beschreibung}
                  >
                    <Symbol size={16} className="shrink-0 text-teal/50" />
                    <div className="min-w-0">
                      <span className="block text-[13px] font-semibold text-ink/90">{e.titel}</span>
                      <span className="block truncate text-[11px] text-muted/60">{e.beschreibung}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))
      )}
    </Card>
  );
}
