import { useCallback, useEffect, useRef, useState } from "react";

import { api, deleteRequest, postJson, putJson } from "@/api";
import { Button } from "@/components/ui";
import { formatDateTime } from "@/utils";
import { alterText, groesseText, versuchText } from "@/lib/sicherung";

/**
 * Datensicherung (#1098): wann zuletzt, was behalten wird, jetzt sichern
 * und einen Stand zurückholen.
 *
 * Wiederherstellen geht bewusst "beim nächsten Start": im laufenden
 * Betrieb zeigen Verbindungen (auch die von Claude Desktop) auf die
 * Datei. Die Karte sagt deshalb genau, was danach zu tun ist.
 */
export default function SicherungKarte({ pushToast }) {
  const [stand, setStand] = useState(null);
  const [laeuft, setLaeuft] = useState(false);
  const [frage, setFrage] = useState("");
  const [ladefehler, setLadefehler] = useState(false);
  const aktiv = useRef(true);

  // v1.7.146 (#1142): ein Abruffehler ist KEINE leere Liste. Vorher stand bei
  // einem Fehler "Noch keine Sicherung vorhanden", obwohl welche da waren.
  const laden = useCallback(async () => {
    try {
      const neu = await api("/api/sicherungen");
      setStand(neu);
      setLadefehler(false);
      return neu;
    } catch {
      setLadefehler(true);
      setStand((alt) => alt || { sicherungen: [], letzte: null, alter_tage: null, unbekannt: true });
      return null;
    }
  }, []);

  useEffect(() => {
    aktiv.current = true;
    laden();
    return () => { aktiv.current = false; };
  }, [laden]);

  // Nach "Jetzt sichern" bis zum Ausgang nachfragen und ihn nennen (hoechstens
  // zwei Minuten); vorher hiess es nur "laeuft im Hintergrund".
  async function ergebnisAbwarten() {
    for (let i = 0; i < 60 && aktiv.current; i += 1) {
      await new Promise((r) => setTimeout(r, 2000));
      const neu = await laden();
      const v = neu?.letzter_versuch;
      if (!aktiv.current || !v || v.status === "laeuft") continue;
      const meldung = versuchText(v);
      if (meldung) pushToast(meldung.text, meldung.art === "fehler" ? "danger" : "amber", { duration: 15000 });
      else pushToast("Sicherung angelegt.", "success");
      return;
    }
  }

  async function jetztSichern() {
    setLaeuft(true);
    try {
      const erg = await postJson("/api/sicherungen", {});
      pushToast(erg.status === "laeuft_bereits"
        ? "Eine Sicherung läuft bereits."
        : "Sicherung läuft im Hintergrund — du kannst weiterarbeiten.", "success");
      if (erg.status !== "laeuft_bereits") ergebnisAbwarten();
    } catch (error) {
      pushToast(`Sicherung nicht gestartet: ${error.message}`, "danger");
    } finally {
      setLaeuft(false);
    }
  }

  // v1.7.146 (#1138): die taegliche Sicherung laeuft jetzt wirklich. Wer Platz
  // sparen will, nimmt die Dokumente heraus; die Datenbank bleibt immer drin.
  async function dokumenteUmstellen(an) {
    try {
      await putJson("/api/sicherungen/einstellung", { dokumente_taeglich: an });
      pushToast(an
        ? "Die tägliche Sicherung enthält wieder die Dokumente."
        : "Die tägliche Sicherung enthält nur noch die Datenbank. Eine Sicherung, die du selbst anlegst, enthält die Dokumente weiterhin.",
      "success");
      await laden();
    } catch (error) {
      pushToast(`Konnte die Einstellung nicht speichern: ${error.message}`, "danger");
    }
  }

  async function wiederherstellen(name) {
    setLaeuft(true);
    try {
      const erg = await postJson("/api/sicherungen/wiederherstellen",
        { name, confirm: "WIEDERHERSTELLEN" });
      setFrage("");
      pushToast(`Vorgemerkt. ${erg.naechster_schritt}`, "amber", { duration: 20000 });
      await laden();
    } catch (error) {
      pushToast(`Nicht vorgemerkt: ${error.message}`, "danger");
    } finally {
      setLaeuft(false);
    }
  }

  async function vormerkungAufheben() {
    try {
      await deleteRequest("/api/sicherungen/wiederherstellen");
      pushToast("Vormerkung aufgehoben — es wird nichts eingespielt.", "success");
      await laden();
    } catch (error) {
      pushToast(`Konnte die Vormerkung nicht aufheben: ${error.message}`, "danger");
    }
  }

  if (!stand) return null;
  const alter = alterText(stand.alter_tage);
  const liste = stand.sicherungen || [];
  const versuch = versuchText(stand.letzter_versuch);

  return (
    <div className="glass-card p-3 grid gap-3" data-testid="sicherung-karte">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className={`text-sm font-medium ${alter.alt ? "text-amber" : "text-ink"}`}>{alter.text}</p>
          <p className="text-xs text-muted">
            PBP sichert einmal am Tag von selbst, vor dem Leeren eines Bereichs und vor dem
            Zusammenführen zweier Stellen — samt deiner Dokumente. {stand.regel}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={jetztSichern} disabled={laeuft}>
          Jetzt sichern
        </Button>
      </div>

      {stand.dokumente_groesse > 0 ? (
        <label className="flex items-start gap-2 text-sm text-ink" data-testid="sicherung-dokumente-schalter">
          <input
            type="checkbox"
            className="mt-1"
            checked={stand.dokumente_taeglich !== false}
            onChange={(e) => dokumenteUmstellen(e.target.checked)}
          />
          <span>
            Dokumente in die tägliche Sicherung aufnehmen
            <span className="block text-xs text-muted">
              Dein Dokumentenordner ist {groesseText(stand.dokumente_groesse)} groß. Ohne Haken enthält die
              tägliche Sicherung nur die Datenbank. Sicherungen, die du selbst anlegst, enthalten die Dokumente immer.
            </span>
          </span>
        </label>
      ) : null}

      {ladefehler ? (
        <p className="text-sm text-amber" data-testid="sicherung-ladefehler">
          Die Sicherungen konnten gerade nicht abgefragt werden. Die Liste unten kann veraltet sein.
        </p>
      ) : null}

      {versuch ? (
        <p className={`rounded-xl border p-3 text-sm ${versuch.art === "fehler" ? "border-coral/40 text-coral" : "border-amber/40 text-amber"}`}
           data-testid="sicherung-versuch">
          {versuch.text}
        </p>
      ) : null}

      {stand.vorgemerkt ? (
        <div className="rounded-xl border border-amber/40 p-3 text-sm text-ink" data-testid="sicherung-vorgemerkt">
          <p>
            Beim nächsten Start wird die Sicherung <strong>{stand.vorgemerkt}</strong> eingespielt.
            Beende dafür PBP und Claude Desktop ganz (Claude Desktop: Rechtsklick auf das Symbol
            unten rechts in der Taskleiste → Beenden) und starte beides neu.
          </p>
          <Button variant="ghost" size="sm" onClick={vormerkungAufheben}>Vormerkung aufheben</Button>
        </div>
      ) : null}

      {liste.length ? (
        <details>
          <summary className="cursor-pointer text-sm text-ink">
            {liste.length} {liste.length === 1 ? "Sicherung" : "Sicherungen"} ({groesseText(stand.platz_belegt)})
          </summary>
          <ul className="mt-2 grid gap-2">
            {liste.map((s) => (
              <li key={s.name} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="text-ink">
                  {formatDateTime(s.zeit)} · {s.anlass_text} · {groesseText(s.groesse)}
                  {s.dokumente ? " · mit Dokumenten" : " · nur Datenbank"}
                </span>
                {frage === s.name ? (
                  <span className="flex flex-wrap items-center gap-2" data-testid="sicherung-frage">
                    <span className="text-xs text-muted">
                      Dein jetziger Stand wird vorher selbst gesichert.
                    </span>
                    <Button size="sm" onClick={() => wiederherstellen(s.name)} disabled={laeuft}>
                      Ja, beim nächsten Start einspielen
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setFrage("")}>Abbrechen</Button>
                  </span>
                ) : (
                  <Button variant="ghost" size="sm" onClick={() => setFrage(s.name)}>
                    Diesen Stand wiederherstellen
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
