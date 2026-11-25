// #1436 (Nutzerwunsch 24.11.2026): Suchbegriffe je Quelle ohne Claude pflegen.
//
// Bis hierher gab es die Suchprofile je Jobboerse (#564) nur ueber die
// Werkzeuge suchprofil_lesen und suchprofil_aktualisieren. Liste und Auftrag
// kommen vom Server (`services/browser_handoff.py`): gezeigt werden nur
// Quellen, deren Begriffe PBP auch liest (Auftrag an Claude, interner Lauf)
// oder die schon ein Profil haben - eine Einstellung ohne Leser waere eine
// ohne Wirkung (L11). Gespeichert wird ueber denselben Weg wie das Werkzeug;
// Filter und Notizen bestehender Eintraege bleiben erhalten.

import { useEffect, useRef, useState } from "react";

import { optionalApi, putJson } from "@/api";
import { useApp } from "@/app-context";
import MitClaude from "@/components/MitClaude";
import { Badge, Button, Card, Field, SectionHeading, TagInput } from "@/components/ui";

const FELDER = [
  ["primaere_suchen", "Zuerst suchen", "Die treffsichersten Begriffe für diese Jobbörse.", "sky"],
  ["sekundaere_suchen", "Danach suchen", "Allgemeinere Begriffe, wenn die ersten wenig bringen.", "neutral"],
  ["nicht_verwenden", "Nicht verwenden", "Begriffe, die hier nur Unpassendes liefern.", "danger"],
];

function QuelleBearbeiten({ quelle, hervorheben, onGespeichert }) {
  const { pushToast } = useApp();
  const [werte, setWerte] = useState(() => Object.fromEntries(FELDER.map(([f]) => [f, quelle[f] || []])));
  const [speichert, setSpeichert] = useState(false);
  const ref = useRef(null);
  const geaendert = FELDER.some(([f]) => JSON.stringify(werte[f]) !== JSON.stringify(quelle[f] || []));

  useEffect(() => {
    if (hervorheben) ref.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [hervorheben]);

  async function speichern() {
    setSpeichert(true);
    try {
      const antwort = await putJson(`/api/suchprofile/${encodeURIComponent(quelle.key)}`, werte);
      pushToast?.(`Suchbegriffe für ${quelle.name} gespeichert.`, "success");
      onGespeichert?.(antwort?.quelle);
    } catch (fehler) {
      pushToast?.(`Nicht gespeichert: ${fehler?.message || "unbekannter Fehler"}`, "danger");
    } finally {
      setSpeichert(false);
    }
  }

  const eigene = (quelle.primaere_suchen?.length || 0) + (quelle.sekundaere_suchen?.length || 0);
  return (
    <details
      ref={ref}
      open={hervorheben || undefined}
      // scroll-mt: der feste Kopf der Seite verdeckte beim Sprung sonst Ueberschrift und Erklaerung.
      className={`scroll-mt-28 rounded-xl border px-4 py-3 ${hervorheben ? "border-sky/40" : "border-white/5"}`}
      data-testid={`suchbegriffe-${quelle.key}`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-ink">{quelle.name}</span>
        {eigene ? (
          <Badge tone="sky">{eigene === 1 ? "1 eigener Begriff" : `${eigene} eigene Begriffe`}</Badge>
        ) : quelle.ersatz_suchkriterien ? (
          <Badge>sucht mit {quelle.ersatz_suchkriterien} Begriffen aus deinen Suchkriterien</Badge>
        ) : (
          <Badge tone="amber">keine Suchbegriffe, Claude fragt nach</Badge>
        )}
        <span className="text-xs text-muted">genutzt von: {quelle.wirkung}</span>
      </summary>
      <div className="mt-3 grid gap-3">
        {FELDER.map(([feld, titel, hinweis, ton]) => (
          <Field key={feld} label={titel} hint={hinweis}>
            <TagInput
              tags={werte[feld]}
              tone={ton}
              placeholder="Begriff eingeben, Enter"
              onChange={(neu) => setWerte((alt) => ({ ...alt, [feld]: neu }))}
            />
          </Field>
        ))}
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={speichern} disabled={!geaendert || speichert}>
            {speichert ? "Speichert …" : "Speichern"}
          </Button>
          {!geaendert ? <span className="text-xs text-muted">Nichts geändert.</span> : null}
        </div>
      </div>
    </details>
  );
}

export default function SuchbegriffeJeQuelle({ quelle: zielQuelle = "" }) {
  const { copyPrompt } = useApp();
  const [daten, setDaten] = useState(null);

  function laden() {
    optionalApi("/api/suchprofile").then((antwort) => setDaten(antwort || { quellen: [] }))
      .catch(() => setDaten({ quellen: [] }));
  }

  useEffect(() => { laden(); }, []);

  const quellen = Array.isArray(daten?.quellen) ? daten.quellen : [];
  return (
    <Card className="rounded-2xl" id="suchbegriffe-je-quelle" data-testid="suchbegriffe-je-quelle">
      <SectionHeading
        title="Suchbegriffe je Quelle"
        description="Manche Jobbörsen finden mit anderen Begriffen mehr als mit deinen Suchkriterien. Ohne eigene Begriffe gelten die Suchkriterien oder Claude fragt dich."
        action={daten?.pflege_prompt ? (
          <Button size="sm" variant="ghost" data-mit-claude-seite onClick={() => copyPrompt(daten.pflege_prompt)}>
            <MitClaude>Suche pflegen</MitClaude>
          </Button>
        ) : null}
      />
      {daten === null ? (
        <p className="text-sm text-muted">Lädt …</p>
      ) : quellen.length ? (
        <div className="grid gap-2">
          {quellen.map((q) => (
            <QuelleBearbeiten
              key={`${q.key}:${JSON.stringify([q.primaere_suchen, q.sekundaere_suchen, q.nicht_verwenden])}`}
              quelle={q}
              hervorheben={zielQuelle === q.key}
              onGespeichert={laden}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted">
          Keine deiner gewählten Quellen nutzt eigene Suchbegriffe. Wählst du eine Browser-Quelle wie LinkedIn oder
          StepStone, kannst du ihre Begriffe hier pflegen.
        </p>
      )}
    </Card>
  );
}
