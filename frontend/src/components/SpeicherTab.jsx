/**
 * Einstellungen › Speicher & Downloads — wohin PBP schreibt und lädt, wie viel dort liegt (#1131, v1.8).
 *
 * Eine Liste nach Orten. Je Ort: Klartextname, Pfad mit „Ordner öffnen“, ein Satz, was dort liegt, Größe, und wer es
 * angelegt hat. Bereinigen geschieht in zwei Schritten (wie das Löschen in der Gefahrenzone): erst die Auswahl oder
 * Vorschau mit Zahlen, dann die Bestätigung. Was anderen Programmen gehört (Playwright-Browser, Ollama-Modelle), wird
 * gezeigt und erklärt, aber nie angeboten zu löschen.
 *
 * Was hier steht, kommt aus GET /api/speicher (dieselbe Antwort wie `speicher_anzeigen` im Chat). Die Regeln für
 * Texte und Schritte stehen in lib/speicher.js (Node-Test).
 */
import { FolderOpen, HardDrive, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, postJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card, LoadingPanel, SectionHeading } from "@/components/ui";
import { groesseText } from "@/lib/autoUpdate";
import {
  URHEBER_TON, auswahlSumme, bereinigbar, darfLoeschen, loeschSatz, ortGroesse, schrittAus, zusammenfassung,
} from "@/lib/speicher";

export default function SpeicherTab() {
  const { pushToast } = useApp();
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [offen, setOffen] = useState({});            // welcher Ort zeigt seine Einzelheiten
  const [dialog, setDialog] = useState(null);        // { ort, aktion, schritt, antwort, gewaehlt }
  const [busy, setBusy] = useState("");

  const laden = useCallback(async () => {
    setLaedt(true);
    setFehler("");
    try {
      setDaten(await api("/api/speicher"));
    } catch (error) {
      setFehler(error.message || "Die Übersicht ließ sich nicht laden.");
    } finally {
      setLaedt(false);
    }
  }, []);

  useEffect(() => { laden(); }, [laden]);

  async function ordnerOeffnen(ort) {
    try {
      const antwort = await postJson("/api/speicher/ordner-oeffnen", { ort: ort.id });
      if (antwort.status !== "ok") pushToast(antwort.text || "Der Ordner ließ sich nicht öffnen.", "warning");
    } catch (error) {
      pushToast(error.message, "danger");
    }
  }

  async function starten(ort, aktion) {
    setBusy(aktion);
    try {
      const antwort = await postJson("/api/speicher/bereinigen", { aktion });
      setDialog({ ort: ort.id, aktion, schritt: schrittAus(antwort), antwort, gewaehlt: new Set() });
    } catch (error) {
      pushToast(error.message, "warning");      // z. B. „Gerade läuft eine Jobsuche …“
    } finally {
      setBusy("");
    }
  }

  async function weiter() {
    setBusy(dialog.aktion);
    try {
      const antwort = await postJson("/api/speicher/bereinigen", { aktion: dialog.aktion, auswahl: [...dialog.gewaehlt] });
      setDialog({ ...dialog, schritt: schrittAus(antwort), antwort });
    } catch (error) {
      pushToast(error.message, "warning");
    } finally {
      setBusy("");
    }
  }

  async function loeschen() {
    setBusy(dialog.aktion);
    try {
      const auswahl = dialog.antwort.braucht_auswahl ? [...dialog.gewaehlt] : undefined;
      const antwort = await postJson("/api/speicher/bereinigen", { aktion: dialog.aktion, auswahl, bestaetigt: true });
      setDialog({ ...dialog, schritt: schrittAus(antwort), antwort });
      await laden();
    } catch (error) {
      pushToast(error.message, "warning");
    } finally {
      setBusy("");
    }
  }

  function umschalten(id) {
    const gewaehlt = new Set(dialog.gewaehlt);
    if (gewaehlt.has(id)) gewaehlt.delete(id); else gewaehlt.add(id);
    setDialog({ ...dialog, gewaehlt });
  }

  if (!daten && !fehler) return <LoadingPanel label="Speicher wird gemessen …" />;
  if (!daten) {
    return (
      <Card className="rounded-2xl" data-speicher-fehler>
        <SectionHeading title="Speicher & Downloads" description="Wohin PBP schreibt und lädt." />
        <p className="text-sm text-coral">{fehler}</p>
        <div className="mt-3"><Button size="sm" variant="secondary" onClick={laden}>Noch einmal versuchen</Button></div>
      </Card>
    );
  }

  const aktionen = daten.aktionen || {};

  return (
    <div className="grid gap-6" data-speicher-tab>
      <Card className="rounded-2xl">
        <SectionHeading title="Speicher & Downloads" description="Wohin PBP auf deinem Rechner schreibt und lädt, wie viel dort liegt und wer es angelegt hat."
          action={(
            <Button size="sm" variant="ghost" disabled={laedt} onClick={laden} title="Misst alle Orte noch einmal nach.">
              <RefreshCw size={14} className={`mr-1 inline ${laedt ? "animate-spin" : ""}`} /> {laedt ? "Messe …" : "Neu messen"}
            </Button>
          )} />
        <p className="text-sm text-ink" data-speicher-summe>{zusammenfassung(daten)}</p>
        {daten.laufende_arbeit?.length ? (
          <p className="mt-2 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-speicher-arbeit>
            Gerade läuft {daten.laufende_arbeit_text}. Aufräumen geht erst danach, damit nichts mitten im Schreiben gelöscht wird.
          </p>
        ) : null}
        <p className="mt-2 text-xs text-muted">
          Gelöscht wird nie ohne deine Bestätigung. Erst siehst du Zahlen und Dateien, dann entscheidest du. Was anderen Programmen gehört,
          zeigt PBP nur und löscht es nie.
        </p>
      </Card>

      {daten.orte.map((ort) => {
        const ids = bereinigbar(ort, aktionen);
        const geoeffnet = Boolean(offen[ort.id]);
        const hier = dialog && dialog.ort === ort.id ? dialog : null;
        return (
          <Card key={ort.id} className="rounded-2xl" data-speicher-ort={ort.id}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <HardDrive size={16} className="text-muted" aria-hidden="true" />
                  <h3 className="text-base font-semibold text-ink">{ort.name}</h3>
                  <span title="Wer diesen Ort angelegt hat.">
                    <Badge tone={URHEBER_TON[ort.urheber] || "neutral"}>{ort.urheber_text}</Badge>
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">{ort.was}</p>
                {ort.hinweis ? <p className="mt-1 text-xs text-muted">{ort.hinweis}</p> : null}
                {ort.pfad ? <p className="mt-1 break-all font-mono text-xs text-muted" data-speicher-pfad>{ort.pfad}</p> : null}
              </div>
              <div className="shrink-0 sm:text-right">
                <p className="text-lg font-semibold text-ink" data-speicher-groesse>{ortGroesse(ort)}</p>
                {ort.oeffnen ? (
                  <Button size="sm" variant="ghost" onClick={() => ordnerOeffnen(ort)} title="Öffnet diesen Ordner im Datei-Explorer.">
                    <FolderOpen size={14} className="mr-1 inline" /> Ordner öffnen
                  </Button>
                ) : null}
              </div>
            </div>

            {ort.eintraege?.length ? (
              <div className="mt-3">
                <button type="button" className="text-xs text-sky underline-offset-2 hover:underline" aria-expanded={geoeffnet}
                  onClick={() => setOffen({ ...offen, [ort.id]: !geoeffnet })}>
                  {geoeffnet ? "Einzelheiten ausblenden" : `Einzelheiten (${ort.eintraege.length})`}
                </button>
                {geoeffnet ? (
                  <div className="mt-2 grid gap-1" data-speicher-eintraege>
                    {ort.eintraege.map((e, i) => (
                      <div key={`${e.name}-${i}`} className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-line/30 bg-shell/40 px-3 py-1.5 text-sm">
                        <span className="min-w-0"><span className="text-ink">{e.name}</span> <span className="text-xs text-muted">{e.was}</span></span>
                        <span className="text-xs text-muted">{groesseText(e.bytes)}{e.vollstaendig === false ? " oder mehr" : ""}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {ids.length ? (
              <div className="mt-4 flex flex-wrap gap-2" data-speicher-aktionen>
                {ids.map((id) => (
                  <Button key={id} size="sm" variant="secondary" disabled={busy !== "" || Boolean(daten.laufende_arbeit?.length)}
                    data-speicher-aktion={id} title={aktionen[id].erklaerung} onClick={() => starten(ort, id)}>
                    <Trash2 size={14} className="mr-1 inline" /> {aktionen[id].titel}
                  </Button>
                ))}
              </div>
            ) : null}

            {hier ? (
              <div className="mt-4 rounded-xl border border-line/40 bg-shell/40 p-4" data-speicher-dialog={hier.schritt}>
                <p className="font-semibold text-ink">{hier.antwort?.titel}</p>
                {hier.antwort?.hinweis ? <p className="mt-1 text-xs text-muted">{hier.antwort.hinweis}</p> : null}

                {hier.schritt === "auswahl" || hier.schritt === "vorschau" ? (
                  <div className="mt-3 grid gap-1">
                    {hier.antwort.kandidaten.map((k) => (
                      <label key={k.id} className="flex items-start gap-2 rounded-lg px-2 py-1 text-sm hover:bg-white/[0.04]">
                        {hier.schritt === "auswahl" ? (
                          <input type="checkbox" className="mt-1" checked={hier.gewaehlt.has(k.id)} onChange={() => umschalten(k.id)} data-speicher-wahl={k.id} />
                        ) : <span className="mt-1 w-3" aria-hidden="true">•</span>}
                        <span className="min-w-0 flex-1"><span className="text-ink">{k.name}</span> <span className="text-xs text-muted">{k.was}</span></span>
                        <span className="text-xs text-muted">{groesseText(k.bytes)}</span>
                      </label>
                    ))}
                    {hier.antwort.weitere ? <p className="px-2 text-xs text-muted">… und {hier.antwort.weitere} weitere.</p> : null}
                  </div>
                ) : null}

                {hier.schritt === "auswahl" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="secondary" disabled={busy !== "" || hier.gewaehlt.size === 0} onClick={weiter}>
                      Weiter ({hier.gewaehlt.size} gewählt, {groesseText(auswahlSumme(hier.antwort.kandidaten, hier.gewaehlt))})
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setDialog(null)}>Abbrechen</Button>
                  </div>
                ) : null}

                {hier.schritt === "vorschau" ? (
                  <div className="mt-3">
                    <p className="text-sm text-ink" data-speicher-satz>{loeschSatz(hier.antwort, hier.antwort.braucht_auswahl ? hier.gewaehlt : null)}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Button size="sm" variant="danger" disabled={busy !== "" || !darfLoeschen(hier.antwort, hier.gewaehlt)} onClick={loeschen} data-speicher-bestaetigen>
                        <Trash2 size={14} className="mr-1 inline" /> Jetzt löschen
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setDialog(null)}>Abbrechen</Button>
                    </div>
                  </div>
                ) : null}

                {hier.schritt === "ergebnis" ? (
                  <div className="mt-3" data-speicher-ergebnis>
                    <p className="text-sm text-ink">{hier.antwort.text}</p>
                    <div className="mt-2"><Button size="sm" variant="ghost" onClick={() => setDialog(null)}>Schließen</Button></div>
                  </div>
                ) : null}

                {hier.schritt === "leer" || hier.schritt === "fehler" ? (
                  <div className="mt-3">
                    <p className="text-sm text-ink">{hier.antwort?.text || "Das hat nicht geklappt."}</p>
                    <div className="mt-2"><Button size="sm" variant="ghost" onClick={() => setDialog(null)}>Schließen</Button></div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </Card>
        );
      })}
    </div>
  );
}
