import { useCallback, useEffect, useState } from "react";

import { api, deleteRequest, postJson } from "@/api";
import { Button } from "@/components/ui";
import { formatDateTime } from "@/utils";
import { alterText, groesseText } from "@/lib/sicherung";

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

  const laden = useCallback(async () => {
    try {
      setStand(await api("/api/sicherungen"));
    } catch {
      setStand({ sicherungen: [], letzte: null, alter_tage: null });
    }
  }, []);

  useEffect(() => { laden(); }, [laden]);

  async function jetztSichern() {
    setLaeuft(true);
    try {
      const erg = await postJson("/api/sicherungen", {});
      pushToast(erg.status === "laeuft_bereits"
        ? "Eine Sicherung läuft bereits."
        : "Sicherung läuft im Hintergrund — du kannst weiterarbeiten.", "success");
      setTimeout(laden, 4000);
    } catch (error) {
      pushToast(`Sicherung nicht gestartet: ${error.message}`, "danger");
    } finally {
      setLaeuft(false);
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
