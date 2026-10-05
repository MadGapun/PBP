/**
 * Einstellungen › Updates — Auto-Update (#1093, v1.8).
 *
 * Eine Frage, vier Antworten: wie sollen neue Versionen auf den Rechner kommen? Die Vorgabe ist „Nur Hinweis“
 * (so war es immer). Alles andere schaltet der Mensch hier bewusst ein, und jederzeit wieder aus.
 *
 * Was hier steht, kommt aus GET /api/auto-update (dieselbe Antwort wie `update_status` im Chat). Die Regeln
 * für Texte und Stufen stehen in lib/autoUpdate.js (Node-Test).
 */
import { oeffneAdresse } from "@/lib/webAdresse";
import { bestaetigen } from "@/lib/bestaetigung";
import { Download, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { postJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card, Field, LoadingPanel, SectionHeading, SelectInput, TextInput } from "@/components/ui";
import { INSTALLER_AUFRAEUMEN, NEUSTART_SCHRITTE, STUFEN, claudeFassung, groesseText, laeuft, prozent, verbindungsAbweichung, zeigeAktuell } from "@/lib/autoUpdate";

const RELEASES = "https://github.com/MadGapun/PBP/releases/latest";

function zeitText(iso) {
  const t = Date.parse(iso || "");
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const ERGEBNIS = {
  installiert: { label: "Installiert", tone: "success" },
  fehler: { label: "Nicht geklappt", tone: "danger" },
  zurueckgeschaltet: { label: "Zurückgeschaltet", tone: "amber" },
};

export default function UpdatesTab() {
  const { autoUpdate: au, refreshAutoUpdate, autoUpdateAktion, pushToast, chrome } = useApp();
  const [busy, setBusy] = useState("");
  const [vorgaenger, setVorgaenger] = useState(null);

  if (!au) return <LoadingPanel label="Update-Stand wird geladen..." />;

  async function senden(pfad, daten, erfolg) {
    setBusy(pfad);
    try {
      await postJson(pfad, daten);
      if (erfolg) pushToast(erfolg, "success");
      await refreshAutoUpdate();
    } catch (error) {
      pushToast(`Das hat nicht geklappt: ${error.message}`, "danger");
    } finally {
      setBusy("");
    }
  }

  async function stufeWaehlen(id) {
    if (id === au.stufe) return;
    await senden("/api/auto-update/einstellungen", { stufe: id }, `Gemerkt: ${STUFEN.find((s) => s.id === id)?.kurz}.`);
  }

  async function vorgaengerSpeichern() {
    const n = Number(vorgaenger ?? au.vorgaenger_behalten);
    await senden("/api/auto-update/einstellungen", { vorgaenger_behalten: n }, "Gemerkt. Überzählige Versionen räumt PBP beim nächsten Start auf.");
    setVorgaenger(null);
  }

  async function zurueckschalten(v) {
    const ok = await bestaetigen({
      text: `Beim nächsten Start läuft wieder Version ${v}. Die neueren Versionen bleiben gespeichert, PBP schaltet aber nicht von selbst wieder um. Du musst danach PBP und Claude Desktop neu starten. Fortfahren?`,
    });
    if (!ok) return;
    await senden("/api/auto-update/zurueck", { version: v }, `Beim nächsten Start läuft Version ${v}.`);
  }

  if (!au.verfuegbar) {
    return (
      <Card className="rounded-2xl" data-updates-nicht-verfuegbar>
        <SectionHeading title="Updates" description="Neue Versionen von PBP." />
        <p className="text-sm text-muted">{au.grund}</p>
        <div className="mt-3">
          <Button size="sm" variant="secondary" onClick={() => oeffneAdresse(RELEASES)}>
            <Download size={14} className="mr-1 inline" /> Neueste Version von Hand holen
          </Button>
        </div>
      </Card>
    );
  }

  const neu = au.neu;
  const lauf = laeuft(au);
  const dauerhaft = au.blockiert?.dauerhaft ? au.blockiert : null;
  const pruefung = au.pruefung;
  const fassungen = au.fassungen || [];
  const gesamt = fassungen.reduce((s, f) => s + (f.bytes || 0), 0);
  const anzahl = vorgaenger ?? au.vorgaenger_behalten;
  const mcp = chrome?.status?.mcp_connection;
  const claude = claudeFassung(mcp);
  const abweichung = verbindungsAbweichung(au, mcp);

  return (
    <div className="grid gap-6" data-updates-tab>
      {/* ── Stand ── */}
      <Card className="rounded-2xl">
        <SectionHeading title="Updates" description="Welche Version läuft, und ob es eine neuere gibt." />
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="sky">Läuft: v{au.laufend}</Badge>
          {au.neustart_noetig ? <Badge tone="amber">Ab dem nächsten Neustart: v{au.aktuell}</Badge> : null}
          {claude ? (
            <span title="Die Version von PBP, mit der Claude gerade arbeitet.">
              <Badge tone={abweichung ? "amber" : "neutral"}>Claude: v{claude}</Badge>
            </span>
          ) : null}
          {neu ? <Badge tone="success">Neu: v{neu.version}</Badge> : zeigeAktuell(au) ? <Badge tone="neutral">Aktuell</Badge> : null}
          <Button size="sm" variant="ghost" disabled={busy !== "" || lauf} onClick={() => senden("/api/auto-update/pruefen", {})}
            title="Fragt die offiziellen GitHub-Veröffentlichungen, ob es eine neuere Version gibt.">
            <RefreshCw size={14} className="mr-1 inline" /> {busy === "/api/auto-update/pruefen" ? "Prüfe …" : "Jetzt prüfen"}
          </Button>
        </div>
        {pruefung?.zeit ? (
          <p className="mt-2 text-xs text-muted">
            Zuletzt geprüft: {zeitText(pruefung.zeit)}{pruefung.status === "keine_antwort" ? ` – ${pruefung.text}` : ""}
          </p>
        ) : null}
        {au.neustart_noetig ? (
          <div className="mt-3 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-updates-neustart>
            <p>Version {au.aktuell} ist installiert und gilt nach dem nächsten Neustart:</p>
            <ol className="mt-1 list-decimal space-y-0.5 pl-5">
              {NEUSTART_SCHRITTE.map((schritt) => <li key={schritt}>{schritt}</li>)}
            </ol>
          </div>
        ) : null}
        {abweichung ? (
          <p className="mt-3 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-updates-verbindung>
            {abweichung.claudeAelter
              ? `Claude arbeitet noch mit Version ${abweichung.claude}, PBP selbst läuft schon mit Version ${abweichung.dashboard}. Beende Claude Desktop komplett (Rechtsklick auf das Symbol in der Taskleiste → „Beenden“) und starte es neu.`
              : `Claude arbeitet schon mit Version ${abweichung.claude}, dieses Fenster läuft noch mit Version ${abweichung.dashboard}. Beende PBP und starte es über die Verknüpfung „PBP Bewerbungs-Portal“ neu.`}
          </p>
        ) : null}
        {neu ? (
          <div className="mt-4 rounded-xl border border-line/40 bg-shell/40 p-4" data-updates-neu>
            <p className="font-semibold text-ink">Version {neu.version}{neu.groesse ? ` · ${groesseText(neu.groesse)}` : ""}</p>
            {Array.isArray(neu.auszug) && neu.auszug.length ? (
              <ul className="mt-2 list-disc pl-5 text-sm text-muted">
                {neu.auszug.map((z) => <li key={z}>{z}</li>)}
              </ul>
            ) : null}
            {neu.status === "unvollstaendig" ? (
              <p className="mt-2 text-sm text-muted">{neu.text}</p>
            ) : null}
            {dauerhaft ? (
              <p className="mt-2 text-sm text-amber">{dauerhaft.text} Die Version wird nicht noch einmal von selbst versucht.</p>
            ) : null}
            {lauf ? (
              <div className="mt-3" data-updates-lauf>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-sky transition-all" style={{ width: `${prozent(au.job)}%` }} />
                </div>
                <p className="mt-1 text-xs text-muted">{au.job.text}</p>
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {neu.status === "neu" && !lauf ? (
                <Button size="sm" disabled={busy !== ""} onClick={() => autoUpdateAktion({ art: "update-installieren", version: neu.version })}
                  title="Lädt die Version von den offiziellen GitHub-Veröffentlichungen, prüft sie und legt sie neben die bisherige. Nichts wird beendet.">
                  <Download size={14} className="mr-1 inline" /> {neu.zurueckgenommen ? "Trotzdem installieren" : "Jetzt installieren"}
                </Button>
              ) : null}
              <Button size="sm" variant="ghost" onClick={() => oeffneAdresse(RELEASES)}>Veröffentlichung ansehen</Button>
            </div>
          </div>
        ) : null}
        {au.rueckgang ? (
          <p className="mt-3 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-updates-rueckgang>
            Version {au.rueckgang.von} ließ sich nicht starten. PBP läuft wieder mit Version {au.rueckgang.nach}.{" "}
            <button type="button" className="text-sky underline" onClick={() => autoUpdateAktion({ art: "update-gesehen" })}>Verstanden</button>
          </p>
        ) : null}
      </Card>

      {/* ── Die vier Stufen ── */}
      <Card className="rounded-2xl">
        <SectionHeading title="Wie sollen Updates installiert werden?" description="Du entscheidest. Ohne deine Wahl bleibt es bei „Nur Hinweis“." />
        <div className="grid gap-2" role="radiogroup" aria-label="Wie sollen Updates installiert werden?" data-updates-stufen>
          {STUFEN.map((s) => {
            const aktiv = au.stufe === s.id;
            return (
              <label key={s.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${
                aktiv ? "border-sky/40 bg-sky/10" : "border-line/40 bg-shell/40 hover:border-sky/30"}`}>
                <input type="radio" name="update-stufe" value={s.id} checked={aktiv} disabled={busy !== ""}
                  onChange={() => stufeWaehlen(s.id)} className="mt-1" data-stufe={s.id} />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-ink">{s.kurz}{s.id === "aus" ? " (Vorgabe)" : ""}</span>
                  <span className="block text-[13px] text-muted">{s.text}</span>
                </span>
              </label>
            );
          })}
        </div>
        <p className="mt-3 flex items-start gap-2 text-xs text-muted">
          <ShieldCheck size={14} className="mt-0.5 shrink-0 text-teal" aria-hidden="true" />
          <span>
            PBP lädt nur von den offiziellen GitHub-Veröffentlichungen dieses Projekts und installiert nie eine Vorabversion
            und nie über die Versionslinie hinaus. Jede Datei wird auf ihre Prüfsumme geprüft
            {au.signatur?.erforderlich ? " und auf die Signatur des Entwicklers" : ""}. Wird nichts erkannt, wird nichts installiert.
            Nichts startet von selbst neu; die neue Version gilt nach dem nächsten Neustart.
          </span>
        </p>
      </Card>

      {/* ── Platz ── */}
      <Card className="rounded-2xl">
        <SectionHeading title="Frühere Versionen" description="Sie liegen im Programmordner (nicht bei deinen Daten) und erlauben es, zurückzuschalten, falls eine Version Probleme macht." />
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-48">
            <Field label="Wie viele behalten?" hint="1 bis 10, Vorgabe 3">
              <TextInput type="number" min={1} max={10} value={anzahl}
                onChange={(e) => setVorgaenger(e.target.value)} data-updates-vorgaenger />
            </Field>
          </div>
          <Button size="sm" variant="secondary" disabled={busy !== "" || vorgaenger === null} onClick={vorgaengerSpeichern}>Übernehmen</Button>
        </div>
        {fassungen.length ? (
          <div className="mt-4 grid gap-2" data-updates-fassungen>
            {fassungen.map((f) => (
              <div key={f.version} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line/40 bg-shell/40 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm text-ink">v{f.version}</span>
                  {f.laeuft ? <Badge tone="sky">läuft</Badge> : null}
                  {f.aktuell && !f.laeuft ? <Badge tone="amber">ab dem nächsten Start</Badge> : null}
                  {f.vorherige && !f.aktuell ? <Badge tone="neutral">Rückweg</Badge> : null}
                  <span className="text-xs text-muted">{groesseText(f.bytes)}</span>
                </div>
                {!f.aktuell ? (
                  <Button size="sm" variant="ghost" disabled={busy !== ""} onClick={() => zurueckschalten(f.version)}
                    title="Beim nächsten Start läuft diese Version.">
                    <RotateCcw size={14} className="mr-1 inline" /> Beim nächsten Start nutzen
                  </Button>
                ) : null}
              </div>
            ))}
            <p className="text-xs text-muted">Zusammen {groesseText(gesamt)}.</p>
          </div>
        ) : null}
      </Card>

      {/* ── Installer ── */}
      <Card className="rounded-2xl">
        <SectionHeading title="Nach einer Installation von Hand" description="Wer das ZIP lädt und INSTALLIEREN.bat startet, hinterlässt das ZIP und den entpackten Ordner. Der Installer kann beides am Ende löschen." />
        <div className="w-64">
          <Field label="Aufräumen">
            <SelectInput value={au.installer_aufraeumen}
              onChange={(e) => senden("/api/auto-update/einstellungen", { installer_aufraeumen: e.target.value }, "Gemerkt.")}>
              {INSTALLER_AUFRAEUMEN.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </SelectInput>
          </Field>
        </div>
        <p className="mt-2 text-xs text-muted">
          „Fragen“ ist die Vorgabe. Gelöscht wird nie ungefragt, außer du wählst „Immer löschen“, und nur, was als entpackter Installer erkannt wird.
        </p>
      </Card>

      {/* ── Verlauf ── */}
      <Card className="rounded-2xl">
        <SectionHeading title="Verlauf" description="Jede Installation mit Version, Ergebnis und Prüfsumme." />
        {au.verlauf?.length ? (
          <div className="grid gap-2" data-updates-verlauf>
            {au.verlauf.map((e, i) => {
              const erg = ERGEBNIS[e.ergebnis] || { label: e.ergebnis || "–", tone: "neutral" };
              return (
                <div key={`${e.zeit}-${i}`} className="rounded-xl border border-line/40 bg-shell/40 px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-ink">v{e.version}</span>
                    <Badge tone={erg.tone}>{erg.label}</Badge>
                    <span className="text-xs text-muted">{zeitText(e.zeit)}{e.ausloeser ? ` · ${e.ausloeser}` : ""}</span>
                  </div>
                  {e.grund && e.ergebnis !== "installiert" ? <p className="mt-1 text-xs text-muted">{e.grund}</p> : null}
                  {e.sha256 ? (
                    <p className="mt-1 break-all font-mono text-xs text-muted">
                      sha256 {e.sha256}{e.signiert ? ` · signiert (${e.schluessel})` : ""}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-muted">Noch keine Installation.</p>
        )}
      </Card>
    </div>
  );
}
