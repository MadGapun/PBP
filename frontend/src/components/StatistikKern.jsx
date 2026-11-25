import { useEffect, useState } from "react";

import { optionalApi } from "@/api";
import { useApp } from "@/app-context";
import { Card } from "@/components/ui";

// #798: die Auswertung am Bildschirm. Liest denselben Datenkern wie das PDF
// (/api/bericht/kennzahlen) und rechnet selbst nichts: jede Zahl kommt fertig
// mit Text, Bezug und Zustand.

function Abschnitt({ titel, children }) {
  return (
    <section className="mb-6" aria-label={titel}>
      <h2 className="mb-3 text-base font-semibold text-ink">{titel}</h2>
      {children}
    </section>
  );
}

function Balken({ name, wert, hoechste, text, dunkel }) {
  const breite = hoechste ? (wert / hoechste) * 100 : 0;
  const innen = hoechste && dunkel != null ? (dunkel / hoechste) * 100 : null;
  return (
    // #1345: der Balken behaelt mindestens 4rem, sonst blieb ihm bei 390 px kaum Platz.
    <div className="grid grid-cols-[minmax(5rem,11rem)_minmax(4rem,1fr)_auto] items-center gap-3 py-1 text-sm">
      <span className="text-ink">{name}</span>
      <span className="relative h-2.5 rounded-sm bg-white/[0.05]" aria-hidden="true">
        <span
          className={`absolute inset-y-0 left-0 rounded-sm ${innen == null ? "bg-sky/70" : "bg-sky/25"}`}
          style={{ width: `${breite}%` }}
        />
        {innen != null ? (
          <span className="absolute inset-y-0 left-0 rounded-sm bg-sky/80" style={{ width: `${innen}%` }} />
        ) : null}
      </span>
      <span className="whitespace-nowrap text-right font-medium text-ink">{text}</span>
    </div>
  );
}

function Saeulen({ achse }) {
  const abschnitte = achse?.abschnitte || [];
  if (!abschnitte.length) return <p className="text-sm text-muted">Noch keine Bewerbung erfasst.</p>;
  const hoechste = Math.max(...abschnitte.map((a) => a.bewerbungen), 1);
  return (
    <div>
      <div className="flex items-end gap-1 overflow-x-auto" role="list" aria-label="Bewerbungen im Zeitverlauf">
        {abschnitte.map((a) => (
          <div
            key={a.schluessel}
            role="listitem"
            className="flex min-w-[3.75rem] flex-1 flex-col items-center text-xs"
            title={`${a.text}: ${a.bewerbungen} Bewerbungen, davon ${a.gespraeche} mit Gespräch`}
          >
            <span className="mb-0.5 font-medium text-ink">{a.bewerbungen || ""}</span>
            <span className="relative block h-20 w-full max-w-8">
              <span
                className="absolute inset-x-0 bottom-0 rounded-t-sm bg-sky/25"
                style={{ height: `${(a.bewerbungen / hoechste) * 100}%` }}
              />
              <span
                className="absolute inset-x-0 bottom-0 rounded-t-sm bg-sky/80"
                style={{ height: `${(a.gespraeche / hoechste) * 100}%` }}
              />
            </span>
            <span className="mt-1 whitespace-nowrap text-xs text-muted">{a.text}</span>
            <span className="text-xs text-muted">{a.gespraeche}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">Hell: Bewerbungen. Dunkel und untere Zahl: davon mit Gespräch.</p>
    </div>
  );
}

function Weitere({ text }) {
  return text ? <p className="mt-1 text-xs text-muted">{text}</p> : null;
}

export default function StatistikKern({ von, bis }) {
  const { reloadKey } = useApp();
  const [daten, setDaten] = useState(null);

  useEffect(() => {
    let aktuell = true;
    const abfrage = new URLSearchParams();
    if (von) abfrage.set("from", von);
    if (bis) abfrage.set("to", bis);
    const zusatz = abfrage.toString();
    optionalApi(`/api/bericht/kennzahlen${zusatz ? `?${zusatz}` : ""}`).then((antwort) => {
      if (aktuell && antwort) setDaten(antwort);
    });
    return () => {
      aktuell = false;
    };
  }, [von, bis, reloadKey]);

  if (!daten) return null;
  const basis = daten.kennzahlen.bewerbungen.wert;
  const stufen = daten.trichter.stufen;
  const wegeMax = Math.max(...daten.wege.zeilen.map((z) => z.bewerbungen), 1);
  const endenMax = Math.max(...daten.ausgang.zeilen.map((z) => z.anteil.anzahl), 1);
  const suche = daten.meine_suche;
  if (!daten.zeitraum.aktiv && basis === 0 && !suche.gesichtet) return null;

  return (
    <div data-statistik-kern>
      <p className="mb-4 text-sm text-muted">
        Diese Übersicht gilt für <strong className="text-ink">{daten.zeitraum.text}</strong>. Nachweis,
        Auswertung und Rohdaten nutzen denselben Zeitraum.
      </p>

      <Abschnitt titel="Wie steht es?">
        <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {daten.kacheln.map((k) => (
            <Card key={k.name} className="!p-3" data-kachel={k.name}>
              <p className="text-xl font-semibold text-ink">{k.wert}</p>
              <p className="text-xs font-medium text-ink">{k.name}</p>
              <p className="text-xs text-muted">{k.hinweis}</p>
            </Card>
          ))}
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-ink">Wie weit kamen die {basis} Bewerbungen?</h3>
            {stufen.map((s) => (
              <Balken key={s.stufe} name={s.stufe} wert={s.wert.anzahl} hoechste={basis} text={s.wert.anzahl} />
            ))}
            <p className="mt-2 text-xs text-muted">
              Ohne belastbare Zahl und deshalb nicht gezeigt: {daten.trichter.entfallen.map((e) => e.stufe).join(", ")}.
            </p>
          </Card>
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-ink">Bewerbungen im Zeitverlauf</h3>
            <Saeulen achse={daten.zeitachse} />
          </Card>
        </div>
      </Abschnitt>

      <Abschnitt titel="Was steht an?">
        <Card>
          {daten.ansteht.zeilen.length === 0 ? (
            <p className="text-sm text-muted">Gerade ist kein Nachfassen geplant.</p>
          ) : (
            <ul className="divide-y divide-white/5 text-sm">
              {daten.ansteht.zeilen.map((z, i) => (
                <li key={`${z.datum}-${i}`} className="flex flex-wrap gap-x-3 py-1.5">
                  <span className={`w-28 ${z.ueberfaellig ? "font-medium text-amber" : "text-muted"}`}>
                    {z.datum}{z.ueberfaellig ? " (fällig)" : ""}
                  </span>
                  <span className="min-w-[12rem] flex-1 text-ink">{[z.firma, z.stelle].filter(Boolean).join(", ")}</span>
                  <span className="text-muted">{z.was}</span>
                </li>
              ))}
            </ul>
          )}
          <Weitere text={daten.ansteht.weitere_text} />
        </Card>
      </Abschnitt>

      <Abschnitt titel="Was funktioniert?">
        <div className="grid gap-3 lg:grid-cols-2">
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-ink">Welcher Weg führt zu Gesprächen?</h3>
            {daten.wege.zeilen.length === 0 ? <p className="text-sm text-muted">{"Noch keine Angabe."}</p> : null}
            {daten.wege.zeilen.map((z) => (
              <Balken
                key={z.weg}
                name={z.weg}
                wert={z.bewerbungen}
                hoechste={wegeMax}
                dunkel={z.gespraeche.anzahl}
                text={`${z.gespraeche.anzahl} von ${z.bewerbungen}`}
              />
            ))}
            <p className="mt-2 text-xs text-muted">
              Hell: Bewerbungen. Dunkel: davon mit Gespräch. {daten.wege.luecke_satz}
            </p>
          </Card>
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-ink">
              Wie endeten die {daten.ausgang.abgeschlossen.wert} abgeschlossenen Verfahren?
            </h3>
            {daten.ausgang.zeilen.map((z) => (
              <Balken key={z.status} name={z.text} wert={z.anteil.anzahl} hoechste={endenMax} text={z.anteil.anzahl} />
            ))}
            {daten.satz_absagen ? <p className="mt-2 text-sm font-medium text-ink">{daten.satz_absagen}</p> : null}
          </Card>
          <Card className="lg:col-span-2">
            <h3 className="mb-2 text-sm font-semibold text-ink">Wie lange dauert es?</h3>
            <dl className="grid gap-1 text-sm sm:grid-cols-[14rem_1fr]">
              <dt className="text-muted">Bis zur ersten Antwort</dt>
              <dd className="text-ink">{daten.dauer.bis_antwort.text}</dd>
              <dt className="text-muted">Bis zum ersten Gespräch</dt>
              <dd className="text-ink">{daten.dauer.bis_gespraech.text}</dd>
            </dl>
            <Weitere text={daten.dauer.nachgetragen_satz} />
          </Card>
        </div>
      </Abschnitt>

      <Abschnitt titel="Meine Suche">
        <Card>
          {!suche.verfuegbar ? (
            <p className="text-sm text-muted">{suche.hinweis}</p>
          ) : (
            <>
              <p className="text-sm text-ink">
                {suche.gesichtet} Stellen gesichtet, {suche.in_der_liste} noch in der Liste,{" "}
                {suche.aussortiert} von dir aussortiert.
              </p>
              {suche.gruende.zeilen.map((z) => (
                <Balken
                  key={z.grund}
                  name={z.grund}
                  wert={z.anzahl}
                  hoechste={Math.max(...suche.gruende.zeilen.map((g) => g.anzahl), 1)}
                  text={z.anzahl}
                />
              ))}
              <Weitere text={suche.gruende.weitere_text} />
            </>
          )}
          <p className="mt-2 text-xs text-muted">
            Dieser Teil beschreibt die Suche, nicht deine Bewerbungen. Er erscheint nicht im Nachweis fürs Amt.
          </p>
        </Card>
      </Abschnitt>

    </div>
  );
}
