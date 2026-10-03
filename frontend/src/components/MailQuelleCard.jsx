/**
 * Einstellungen › Quellen im Detail › Mail-Ordner (Add-on) — die Zugangsschicht (#947, v1.8).
 *
 * Ein Mail-Ordner ist der weitreichendste Datenzugriff, den PBP je hätte. Deshalb: Vorgabe AUS, ein bewusster
 * Schalter mit Warnung, und eine Liste der Ordner, die gelesen werden dürfen — genau diese, kein Platzhalter, keine
 * Unterordner. Die Regel prüft PBP auf dem Server bei jeder Mail; diese Karte stellt sie nur ein und zeigt die Zahlen.
 *
 * Was hier steht, kommt aus GET /api/mail-quelle (dieselbe Antwort wie `mail_quelle_anzeigen` im Chat).
 */
import { BookOpen, FolderPlus, Mail, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, deleteRequest, postJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card, Field, LoadingPanel, SectionHeading, SelectInput, TextInput } from "@/components/ui";
import { bestaetigen } from "@/lib/bestaetigung";
import { ANBIETER_LISTE, anbieterLabel, darfFreigeben, freigabeSchritt, statusText, statusTon, zahlenText } from "@/lib/mailQuelle";
import { oeffneAdresse } from "@/lib/webAdresse";

const ANLEITUNG = "https://github.com/MadGapun/PBP/wiki/Mail-Ordner";

export default function MailQuelleCard() {
  const { pushToast } = useApp();
  const [u, setU] = useState(null);
  const [fehler, setFehler] = useState("");
  const [busy, setBusy] = useState(false);
  const [anbieter, setAnbieter] = useState("thunderbird");
  const [konto, setKonto] = useState("");
  const [ordner, setOrdner] = useState("");
  const [warnung, setWarnung] = useState("");        // Text der Posteingang-Warnung, solange sie offen ist

  const laden = useCallback(async () => {
    try {
      setU(await api("/api/mail-quelle"));
      setFehler("");
    } catch (error) {
      setFehler(error.message || "Der Stand der Mail-Ordner ließ sich nicht laden.");
    }
  }, []);

  useEffect(() => { laden(); }, [laden]);

  async function schalten(an) {
    setBusy(true);
    try {
      if (an) {
        // Den Wortlaut der Warnung liefert der Server (eine Quelle); erst nach der Bestätigung geht der Aufruf mit `bestaetigt` los.
        const ok = await bestaetigen({ text: u.einschalten_text || "Soll PBP einem Mail-Add-on erlauben, freigegebene Ordner zu lesen?" });
        if (!ok) return;
        const antwort = await postJson("/api/mail-quelle/scan", { an: true, bestaetigt: true });
        pushToast(antwort.text, "success");
      } else {
        const antwort = await postJson("/api/mail-quelle/scan", { an: false });
        pushToast(antwort.text, "success");
      }
      await laden();
    } catch (error) {
      pushToast(`Das hat nicht geklappt: ${error.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function freigeben(posteingangBestaetigt = false) {
    setBusy(true);
    try {
      const antwort = await postJson("/api/mail-quelle/freigaben", {
        anbieter, konto, ordner, posteingang_bestaetigt: posteingangBestaetigt,
      });
      const schritt = freigabeSchritt(antwort);
      if (schritt === "warnung") {
        setWarnung(antwort.text);
        return;
      }
      setWarnung("");
      if (schritt === "fertig") {
        setOrdner("");
        pushToast(antwort.text, "success");
      } else {
        pushToast(antwort.text || "Das hat nicht geklappt.", "warning");
      }
      await laden();
    } catch (error) {
      pushToast(error.message, "warning");
    } finally {
      setBusy(false);
    }
  }

  async function zuruecknehmen(f) {
    const ok = await bestaetigen({
      text: `Die Freigabe für „${f.ordner}“ zurücknehmen? Aus diesem Ordner nimmt PBP dann nichts mehr entgegen. Was schon importiert wurde, bleibt.`,
    });
    if (!ok) return;
    setBusy(true);
    try {
      const antwort = await deleteRequest(`/api/mail-quelle/freigaben/${encodeURIComponent(f.id)}`);
      pushToast(antwort.text, "success");
      await laden();
    } catch (error) {
      pushToast(error.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function zuruecksetzen() {
    const ok = await bestaetigen({
      text: "Den Ordner-Scan ausschalten und die ganze Liste der freigegebenen Ordner löschen? Bereits importierte Mails und Stellen bleiben in PBP.",
    });
    if (!ok) return;
    setBusy(true);
    try {
      const antwort = await postJson("/api/mail-quelle/zuruecksetzen", {});
      pushToast(antwort.text, "success");
      await laden();
    } catch (error) {
      pushToast(error.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  if (!u && !fehler) return <LoadingPanel label="Mail-Ordner werden geladen …" />;
  if (!u) {
    return (
      <Card className="rounded-2xl" data-mail-fehler>
        <SectionHeading title="Mail-Ordner (Add-on)" description="Jobmails aus freigegebenen Ordnern." />
        <p className="text-sm text-coral">{fehler}</p>
        <div className="mt-3"><Button size="sm" variant="secondary" onClick={laden}>Noch einmal versuchen</Button></div>
      </Card>
    );
  }

  return (
    <Card className="rounded-2xl" data-mail-quelle>
      <SectionHeading title="Mail-Ordner (Add-on)"
        description="Jobmails aus Ordnern in deinem Mail-Programm, die du ausdrücklich freigibst."
        action={(
          <Button size="sm" variant="ghost" onClick={() => oeffneAdresse(ANLEITUNG)} title="Die Schritt-für-Schritt-Anleitung im Wiki: einen Ordner und einen Filter in Thunderbird oder Outlook einrichten.">
            <BookOpen size={14} className="mr-1 inline" /> Anleitung
          </Button>
        )} />

      <div className="flex flex-wrap items-center gap-3">
        <Mail size={16} className="text-muted" aria-hidden="true" />
        <Badge tone={statusTon(u)}>Ordner-Scan: {statusText(u)}</Badge>
        {u.scan_aktiv && !u.neu_bestaetigen && !u.unlesbar ? (
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => schalten(false)} data-mail-schalter="aus"
            title="Schaltet den Ordner-Scan sofort aus. Bereits importierte Mails und Stellen bleiben.">Ausschalten</Button>
        ) : (
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => schalten(true)} data-mail-schalter="an"
            title="Erlaubt einem gekoppelten Mail-Add-on, die freigegebenen Ordner von sich aus zu lesen. Du wirst vorher gefragt.">
            {u.neu_bestaetigen ? "Erneut bestätigen und einschalten" : "Einschalten …"}
          </Button>
        )}
      </div>

      <p className="mt-3 text-sm text-muted">
        Standardmäßig ist der Ordner-Scan <strong className="text-ink">aus</strong>: kein Add-on liest dann einen Ordner von sich aus.
        PBP selbst öffnet nie ein Postfach; es nimmt nur Mails entgegen, die ein gekoppeltes Add-on schickt, und prüft vorher gegen diese Liste.
        Mails, die du selbst im Mail-Programm mit „An PBP senden“ schickst, brauchen diesen Schalter nicht.
      </p>

      {u.hinweise?.length ? (
        <div className="mt-3 grid gap-2" data-mail-hinweise>
          {u.hinweise.map((h) => (
            <p key={h} className="rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink">{h}</p>
          ))}
        </div>
      ) : null}

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-ink">Freigegebene Ordner</h3>
        {u.freigaben.length ? (
          <div className="mt-2 grid gap-2" data-mail-freigaben>
            {u.freigaben.map((f) => (
              <div key={f.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line/40 bg-shell/40 px-3 py-2" data-mail-freigabe={f.id}>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm text-ink">{f.ordner}</span>
                    <Badge tone="neutral">{anbieterLabel(f.anbieter)}</Badge>
                    {f.konto ? <span className="text-xs text-muted">Konto: {f.konto}</span> : null}
                    {f.posteingang ? <Badge tone="amber">ganzer Posteingang</Badge> : null}
                  </div>
                  <p className="mt-1 text-xs text-muted" data-mail-zahlen>{zahlenText(f)}</p>
                </div>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => zuruecknehmen(f)} title="Nimmt die Freigabe sofort zurück.">
                  <Trash2 size={14} className="mr-1 inline" /> Zurücknehmen
                </Button>
              </div>
            ))}
            <p className="text-xs text-muted">Zusammen {u.summe.mails} {u.summe.mails === 1 ? "Mail" : "Mails"} und {u.summe.stellen} {u.summe.stellen === 1 ? "Stelle" : "Stellen"} aus Ordnern.</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted" data-mail-leer>Noch kein Ordner freigegeben. Solange die Liste leer ist, wird nichts gelesen – auch wenn der Ordner-Scan an ist.</p>
        )}
      </div>

      <div className="mt-5 rounded-xl border border-line/40 bg-shell/40 p-4" data-mail-neu>
        <h3 className="text-sm font-semibold text-ink">Ordner freigeben</h3>
        <p className="mt-1 text-xs text-muted">
          Genau ein Ordner pro Eintrag, so geschrieben wie dein Mail-Programm ihn nennt (zum Beispiel „Jobs/Portale“). Unterordner sind nicht dabei und
          brauchen eine eigene Freigabe. Am besten legst du in deinem Mail-Programm einen eigenen Ordner nur für Jobmails an – die Anleitung zeigt wie.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Field label="Mail-Programm">
            <SelectInput value={anbieter} onChange={(e) => setAnbieter(e.target.value)} data-mail-anbieter>
              {ANBIETER_LISTE.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </SelectInput>
          </Field>
          <Field label="Konto (nur falls das Add-on eines mitsendet)">
            <TextInput value={konto} onChange={(e) => setKonto(e.target.value)} placeholder="leer lassen" data-mail-konto />
          </Field>
          <Field label="Ordner">
            <TextInput value={ordner} onChange={(e) => { setOrdner(e.target.value); setWarnung(""); }} placeholder="Jobs/Portale" data-mail-ordner />
          </Field>
        </div>
        {warnung ? (
          <div className="mt-3 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-mail-posteingang>
            <p>{warnung}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="danger" disabled={busy} onClick={() => freigeben(true)} data-mail-posteingang-ja>Ja, ganzen Posteingang freigeben</Button>
              <Button size="sm" variant="ghost" onClick={() => setWarnung("")}>Nein, abbrechen</Button>
            </div>
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="primary" disabled={busy || !darfFreigeben(anbieter, ordner)} onClick={() => freigeben(false)} data-mail-freigeben>
            <FolderPlus size={14} className="mr-1 inline" /> Freigeben
          </Button>
          {u.freigaben.length || u.scan_aktiv ? (
            <Button size="sm" variant="ghost" disabled={busy} onClick={zuruecksetzen} data-mail-zuruecksetzen
              title="Schaltet den Ordner-Scan aus und leert die Liste. Importierte Daten bleiben.">Alles zurücksetzen</Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
