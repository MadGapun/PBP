/**
 * Einstellungen › Lokale KI › Eigene Anthropic-API (optional) — der API-Weg der KI (#1236, v1.8).
 *
 * Wer ein API-Guthaben bei Anthropic hat, kann gleichartige Massenaufgaben, die sonst die lokale KI erledigt, über die API
 * laufen lassen. Vorgabe ist AUS, jede Aufgabe wird einzeln freigegeben, und was dabei den Rechner verlässt, steht VOR der
 * Freigabe da (die Feldliste je Aufgabe). Die Karte erscheint nur, wenn es etwas zu zeigen gibt: ein Schlüssel in der
 * Umgebung, eine Freigabe oder schon Verbrauch. Ohne beides sieht diese Seite aus wie vorher.
 *
 * Was hier steht, kommt aus GET /api/api-weg (dieselbe Antwort wie `api_weg_anzeigen` im Chat). Den Schlüssel zeigt keine
 * Antwort und kein Feld: er steht nur in der Umgebungsvariable, PBP speichert ihn nirgends.
 */
import { KeyRound, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card, CheckboxInput, Field, SectionHeading, SelectInput, TextInput } from "@/components/ui";
import { bestaetigen } from "@/lib/bestaetigung";
import {
  aufgabeStatus, aufgabeTon, budgetEingabe, budgetZeile, datumText, kannPruefen, letzterAufrufText, neueAuswahl,
  pruefungText, pruefungTon, sichtbar, verbrauchProzent, verbrauchZeile,
} from "@/lib/apiWeg";

export default function ApiWegKarte() {
  const { pushToast } = useApp();
  const [u, setU] = useState(null);
  const [busy, setBusy] = useState(false);
  const [budget, setBudget] = useState("");
  const [budgetGeaendert, setBudgetGeaendert] = useState(false);

  const laden = useCallback(async () => {
    try {
      setU(await api("/api/api-weg"));
    } catch {
      // Ohne Antwort zeigt die Karte nichts: die Seite sieht aus wie vorher.
      setU(null);
    }
  }, []);

  useEffect(() => { laden(); }, [laden]);

  useEffect(() => {
    if (u && !budgetGeaendert) {
      setBudget(u.budget?.usd != null ? String(u.budget.usd).replace(".", ",") : "");
    }
  }, [u, budgetGeaendert]);

  async function speichern(koerper, { bestaetigung = null } = {}) {
    setBusy(true);
    try {
      try {
        await putJson("/api/api-weg", koerper);
      } catch (fehler) {
        // Freigeben fragt erst: der Server liefert die Feldliste als Text (eine Quelle), der Mensch bestätigt, dann geht es los.
        if (fehler.payload?.status !== "bestaetigung_noetig") throw fehler;
        const ok = await bestaetigen({
          titel: bestaetigung?.titel || "Daten an die Anthropic-API senden?",
          text: fehler.payload.text,
          ja: "Ja, freigeben",
          nein: "Abbrechen",
          gefahr: false,
        });
        if (!ok) return false;
        await putJson("/api/api-weg", { ...koerper, bestaetigt: true });
      }
      await laden();
      return true;
    } catch (fehler) {
      pushToast(fehler.message || "Das hat nicht geklappt.", "danger");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function umschalten(a, an) {
    const ok = await speichern({ aufgaben: neueAuswahl(u, a.id, an) });
    if (ok) pushToast(an ? `„${a.titel}“ läuft jetzt über die API (im Rahmen des Budgets).` : `„${a.titel}“ ist wieder aus.`, "success");
  }

  async function modellWaehlen(a, modell) {
    await speichern({ modelle: { [a.id]: modell || null } });
  }

  async function budgetSpeichern() {
    const zahl = budgetEingabe(budget);
    if (zahl === null) {
      pushToast("Das Budget braucht einen Betrag in US-Dollar, zum Beispiel 5 oder 5,50.", "warning");
      return;
    }
    if (await speichern({ budget_usd: zahl })) {
      setBudgetGeaendert(false);
      pushToast(zahl > 0 ? "Budget gespeichert." : "Budget auf null gesetzt: PBP gibt nichts aus.", "success");
    }
  }

  async function pruefen() {
    const ok = await bestaetigen({
      titel: "Schlüssel prüfen?",
      text: "PBP schickt eine einzige kleine Anfrage an Anthropic (das Wort „ok“, nichts aus deinem Profil). Das kostet einen Bruchteil eines Cents.",
      ja: "Ja, prüfen",
      nein: "Abbrechen",
      gefahr: false,
    });
    if (!ok) return;
    setBusy(true);
    try {
      const antwort = await postJson("/api/api-weg/pruefen", { bestaetigt: true });
      pushToast(antwort.ergebnis === "gueltig" ? "Die API hat die Probeanfrage angenommen." : (antwort.text || "Die Probe hat nicht geklappt."),
        antwort.ergebnis === "gueltig" ? "success" : "warning");
      await laden();
    } catch (fehler) {
      pushToast(fehler.message || "Die Probe hat nicht geklappt.", "danger");
    } finally {
      setBusy(false);
    }
  }

  if (!sichtbar(u)) return null;

  const prozent = verbrauchProzent(u);

  return (
    <Card className="rounded-2xl" data-api-weg>
      <SectionHeading title="Eigene Anthropic-API (optional)"
        description="Für Fortgeschrittene: Mit einem eigenen API-Schlüssel erledigt die Anthropic-API gleichartige Massenaufgaben statt der lokalen KI." />

      <div className="flex flex-wrap items-center gap-3" data-api-schluessel>
        <KeyRound size={16} className="text-muted" aria-hidden="true" />
        <Badge tone={u.schluessel_gesetzt ? "success" : "amber"}>{u.schluessel_gesetzt ? "Schlüssel gefunden" : "Kein Schlüssel gefunden"}</Badge>
        <Badge tone={pruefungTon(u.pruefung)} className="normal-case" >{pruefungText(u.pruefung)}</Badge>
        <Button size="sm" variant="secondary" disabled={busy || !kannPruefen(u)} onClick={pruefen} data-api-pruefen
          title="Schickt eine einzige kleine Anfrage an Anthropic und sagt danach, ob die API den Schlüssel angenommen hat.">
          Schlüssel prüfen …
        </Button>
      </div>

      {!u.schluessel_gesetzt ? (
        <p className="mt-3 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-api-ohne-schluessel>
          PBP findet keinen Schlüssel. Der Schlüssel steht nur in der Umgebungsvariable <code className="font-mono">{u.variable}</code>;
          PBP speichert ihn nirgends. Trage ihn dort ein und starte PBP neu. Solange er fehlt, läuft alles wie ohne diese Karte.
        </p>
      ) : null}

      <div className="mt-4 flex items-start gap-2 rounded-xl border border-sky/20 bg-sky/5 p-3 text-sm text-muted" data-api-datenschutz>
        <ShieldCheck size={16} className="mt-0.5 shrink-0 text-sky" aria-hidden="true" />
        <p>
          <strong className="text-ink">Das ist eine Ausnahme von „läuft komplett lokal“.</strong> Gibst du unten eine Aufgabe frei, schickt PBP
          selbst die dort genannten Angaben an Anthropic (die Firma hinter Claude). Ohne Freigabe geschieht nichts. Der Hauptschalter unter
          Claude (Cloud) sperrt auch diesen Weg.
        </p>
      </div>

      {u.hinweise?.length ? (
        <div className="mt-3 grid gap-2" data-api-hinweise>
          {u.hinweise.map((h) => (
            <p key={h} className="rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink">{h}</p>
          ))}
        </div>
      ) : null}

      <div className="mt-5 grid gap-3" data-api-aufgaben>
        <h3 className="text-sm font-semibold text-ink">Aufgaben</h3>
        {u.aufgaben.map((a) => (
          <div key={a.id} className="rounded-xl border border-line/40 bg-shell/40 p-4" data-api-aufgabe={a.id}>
            <div className="flex flex-wrap items-center gap-3">
              <CheckboxInput checked={a.freigegeben} disabled={busy || (!a.freigegeben && !u.schluessel_gesetzt)}
                onChange={(e) => umschalten(a, e.target.checked)} aria-label={`${a.titel} über die API laufen lassen`} data-api-schalter={a.id} />
              <span className="text-sm font-medium text-ink">{a.titel}</span>
              <span data-api-status={a.id}><Badge tone={aufgabeTon(a)} className="normal-case">{aufgabeStatus(a)}</Badge></span>
            </div>
            <p className="mt-2 text-sm text-muted">{a.beschreibung}</p>
            <details className="mt-2" open={!a.freigegeben} data-api-felder>
              <summary className="cursor-pointer text-sm text-ink">Was geht an die API – und was nicht?</summary>
              <ul className="mt-2 list-disc pl-5 text-sm text-muted">
                {a.gesendet.map((t) => <li key={t}>{t}</li>)}
                <li>{a.immer || "das heutige Datum und die Uhrzeit"}</li>
              </ul>
              <p className="mt-2 text-sm text-muted"><strong className="text-ink">Nicht gesendet:</strong> {a.nicht_gesendet.join("; ")}.</p>
            </details>
            {a.freigegeben ? (
              <div className="mt-3 max-w-md">
                <Field label="Modell" hint="Vorgabe ist das günstigste. Ein teureres Modell lohnt sich nur, wenn die Messprobe zeigt, dass das günstige zu oft danebenliegt.">
                  <SelectInput value={a.modell || ""} disabled={busy} onChange={(e) => modellWaehlen(a, e.target.value)} data-api-modell={a.id}>
                    {u.modelle.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}{m.vorgabe ? " (günstigstes)" : ""} – {m.preis}</option>
                    ))}
                  </SelectInput>
                </Field>
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="mt-5 rounded-xl border border-line/40 bg-shell/40 p-4" data-api-budget>
        <h3 className="text-sm font-semibold text-ink">Budget</h3>
        <p className="mt-1 text-xs text-muted">
          Die Obergrenze in US-Dollar. PBP rechnet vor jedem Aufruf den ungünstigsten Fall und sendet nicht mehr, wenn er die Grenze überschreiten würde.
          Ohne Budget ruft PBP die API nicht auf.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="w-40">
            <Field label="Budget (US-Dollar)">
              <TextInput value={budget} inputMode="decimal" placeholder="zum Beispiel 5" data-api-budget-eingabe
                onChange={(e) => { setBudget(e.target.value); setBudgetGeaendert(true); }} />
            </Field>
          </div>
          <Button size="sm" variant="primary" disabled={busy || !budgetGeaendert} onClick={budgetSpeichern} data-api-budget-speichern>Speichern</Button>
        </div>
        <p className="mt-3 text-sm text-ink" data-api-budget-zeile>{budgetZeile(u)}</p>
        {prozent !== null ? (
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10" role="img" aria-label={`${prozent} Prozent des Budgets verbraucht`}>
            <div className={`h-full ${prozent >= 90 ? "bg-coral" : "bg-teal"}`} style={{ width: `${prozent}%` }} />
          </div>
        ) : null}
        <p className="mt-2 text-xs text-muted" data-api-verbrauch>{verbrauchZeile(u)}</p>
        <p className="mt-1 text-xs text-muted">{u.grenze}</p>
        {u.letzter_aufruf ? <p className="mt-1 text-xs text-muted" data-api-letzter>{letzterAufrufText(u.letzter_aufruf)}</p> : null}
        <p className="mt-1 text-xs text-muted" data-api-preise>
          Preise nach der Preisseite von Anthropic, Stand {datumText(u.preise_stand) || "unbekannt"}. Maßgeblich ist immer die Abrechnung bei Anthropic.
        </p>
      </div>
    </Card>
  );
}
