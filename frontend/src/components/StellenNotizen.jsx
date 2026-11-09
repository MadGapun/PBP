/**
 * StellenNotizen — #1316
 *
 * Eigene Notizen an einer Stelle, getrennt vom Anzeigentext: je Eintrag
 * Zeitpunkt, Verfasser ("von dir" / "von Claude") und Freitext. Sie zaehlen
 * nie in die Punkte und gehen beim Anlegen einer Bewerbung mit.
 *
 * Steht in der Beschreibung noch ein alter Notizteil hinter "---", bietet
 * der Bereich an, ihn zu verschieben — nie von selbst, immer mit Vorschau.
 */
import { useCallback, useEffect, useState } from "react";
import { Pencil, StickyNote, Trash2 } from "lucide-react";

import { api, deleteRequest, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { Button, TextArea } from "@/components/ui";
import { bestaetigen } from "@/lib/bestaetigung";
import { formatDateTime } from "@/utils";

export default function StellenNotizen({ jobHash, onBeschreibungGeaendert }) {
  const { pushToast } = useApp();
  const [notizen, setNotizen] = useState([]);
  const [notizteil, setNotizteil] = useState(null);
  const [geladen, setGeladen] = useState(false);
  const [entwurf, setEntwurf] = useState("");
  // Das Eingabefeld erscheint erst auf Klick: ein offenes Feld bekaeme beim Oeffnen des Dialogs den Fokus (useDialogFokus),
  // der Dialog spraenge ans Ende, und solange ein Feld den Fokus hat, frischt die Seite nichts auf (isTypingTargetActive).
  const [schreiben, setSchreiben] = useState(false);
  const [bearbeiten, setBearbeiten] = useState({ id: null, text: "" });
  const [beschaeftigt, setBeschaeftigt] = useState(false);

  // Nicht an pushToast haengen: es aendert sich mit jeder Meldung (CLAUDE.md, MERKE UI).
  const laden = useCallback(async () => {
    if (!jobHash) return;
    try {
      const antwort = await api(`/api/jobs/${jobHash}/notizen`);
      setNotizen(antwort?.notizen || []);
      setNotizteil(antwort?.notizteil_in_beschreibung || null);
    } catch {
      setNotizen([]);
    } finally {
      setGeladen(true);
    }
  }, [jobHash]);

  useEffect(() => { laden(); }, [laden]);

  async function hinzufuegen() {
    const text = entwurf.trim();
    if (!text) return;
    setBeschaeftigt(true);
    try {
      await postJson(`/api/jobs/${jobHash}/notizen`, { text });
      setEntwurf("");
      setSchreiben(false);
      await laden();
      pushToast("Notiz gespeichert.", "success");
    } catch (error) {
      pushToast(`Notiz konnte nicht gespeichert werden: ${error.message}`, "danger");
    } finally {
      setBeschaeftigt(false);
    }
  }

  async function speichern() {
    const text = bearbeiten.text.trim();
    if (!text) return;
    try {
      await putJson(`/api/jobs/${jobHash}/notizen/${bearbeiten.id}`, { text });
      setBearbeiten({ id: null, text: "" });
      await laden();
      pushToast("Notiz geändert.", "success");
    } catch (error) {
      pushToast(`Notiz konnte nicht geändert werden: ${error.message}`, "danger");
    }
  }

  async function loeschen(notiz) {
    const ok = await bestaetigen({
      titel: "Notiz löschen?",
      text: `Die Notiz vom ${formatDateTime(notiz.erstellt_am)} (${notiz.von}) wird gelöscht. Das lässt sich nicht rückgängig machen.`,
      ja: "Löschen",
    });
    if (!ok) return;
    try {
      await deleteRequest(`/api/jobs/${jobHash}/notizen/${notiz.id}`);
      await laden();
      pushToast("Notiz gelöscht.", "success");
    } catch (error) {
      pushToast(`Notiz konnte nicht gelöscht werden: ${error.message}`, "danger");
    }
  }

  async function ausBeschreibung() {
    if (!notizteil) return;
    const vorschau = notizteil.notizen.length > 600 ? `${notizteil.notizen.slice(0, 600)} …` : notizteil.notizen;
    const ok = await bestaetigen({
      titel: "Notizteil verschieben?",
      text: `Dieser Text steht in der Beschreibung hinter „---“ und wird zu einer Notiz:\n\n${vorschau}\n\nDie Beschreibung behält nur den Teil davor. An den Punkten ändert sich nichts.`,
      ja: "Verschieben",
    });
    if (!ok) return;
    try {
      await postJson(`/api/jobs/${jobHash}/notizen/aus-beschreibung`, {});
      await laden();
      pushToast("Notizteil in die Notizen verschoben.", "success");
      if (onBeschreibungGeaendert) onBeschreibungGeaendert();
    } catch (error) {
      pushToast(`Verschieben fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  if (!jobHash) return null;

  return (
    <div className="glass-card p-4 rounded-xl" data-testid="stellen-notizen">
      <h3 className="text-sm font-semibold text-ink mb-1 flex items-center gap-1.5">
        <StickyNote size={14} /> Deine Notizen zur Stelle
      </h3>
      <p className="text-xs text-muted mb-3">
        Nur für dich und Claude — sie zählen nie in die Punkte und gehen mit, wenn du dich bewirbst.
      </p>
      {notizteil ? (
        <div className="mb-3 rounded-lg border border-amber/30 bg-amber/10 px-3 py-2" data-testid="notizteil-hinweis">
          <p className="text-xs text-ink">In der Beschreibung steht hinter „---“ noch ein Notizteil.</p>
          <Button size="sm" variant="secondary" className="mt-2" onClick={ausBeschreibung}>
            In die Notizen verschieben
          </Button>
        </div>
      ) : null}
      {geladen && notizen.length === 0 ? (
        <p className="text-sm text-muted mb-3">Noch keine Notiz. Halte hier fest, was du zu dieser Stelle überlegst.</p>
      ) : null}
      <ul className="space-y-2 mb-3">
        {notizen.map((n) => (
          <li key={n.id} className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2" data-testid="stellen-notiz">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted">
                {formatDateTime(n.erstellt_am)} · {n.von}{n.geaendert_am ? " · geändert" : ""}
              </span>
              <span className="flex gap-1">
                <button type="button" className="text-muted hover:text-sky" title="Notiz bearbeiten" aria-label="Notiz bearbeiten"
                  onClick={() => setBearbeiten({ id: n.id, text: n.text })}>
                  <Pencil size={13} />
                </button>
                <button type="button" className="text-muted hover:text-coral" title="Notiz löschen" aria-label="Notiz löschen"
                  onClick={() => loeschen(n)}>
                  <Trash2 size={13} />
                </button>
              </span>
            </div>
            {bearbeiten.id === n.id ? (
              <div className="mt-2 space-y-2">
                <TextArea rows={4} value={bearbeiten.text} aria-label="Notiz ändern"
                  onChange={(e) => setBearbeiten((b) => ({ ...b, text: e.target.value }))} />
                <div className="flex gap-2">
                  <Button size="sm" onClick={speichern} disabled={!bearbeiten.text.trim()}>Speichern</Button>
                  <Button size="sm" variant="ghost" onClick={() => setBearbeiten({ id: null, text: "" })}>Abbrechen</Button>
                </div>
              </div>
            ) : (
              <p className="mt-1 text-sm text-ink whitespace-pre-wrap">{n.text}</p>
            )}
          </li>
        ))}
      </ul>
      {schreiben ? (
        <div className="space-y-2">
          <TextArea rows={3} value={entwurf} placeholder="Neue Notiz, z. B. eine Rechnung oder offene Fragen …" autoFocus
            aria-label="Neue Notiz" onChange={(e) => setEntwurf(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" onClick={hinzufuegen} disabled={beschaeftigt || !entwurf.trim()}>Notiz speichern</Button>
            <Button size="sm" variant="ghost" onClick={() => { setSchreiben(false); setEntwurf(""); }}>Abbrechen</Button>
          </div>
        </div>
      ) : (
        <Button size="sm" variant="secondary" onClick={() => setSchreiben(true)}>Notiz hinzufügen</Button>
      )}
    </div>
  );
}
