/**
 * Kontakte › Firmen — alles, was PBP zu einer Firma weiß, als eine Zeitleiste (#1080, v1.8).
 *
 * Lesen ist der Normalfall: erst die Historie (Bewerbungen auch als Vermittler und als Endkunde, Stellen, Kontakte, früherer
 * Arbeitgeber im Lebenslauf, Dokumente, Recherchen, Blacklist), jeder Eintrag mit dem Sprung dorthin, wo er steht. Das Ändern
 * (Schreibweisen, Mutterfirma, Kontakte mit Zeitraum, Zusammenführen, Löschen) steht hinter „Bearbeiten“. Bewerbungen, Stellen
 * und Kontakte behalten ihren Firmennamen als Text; der Firmen-Eintrag fasst nur bestätigte Schreibweisen zusammen.
 *
 * Alles hier geht über dieselben Dienste wie die Werkzeuge im Chat (firmen_stamm_anzeigen / firmen_stamm_bearbeiten): was du hier
 * klickst, kann Claude ebenso — und umgekehrt. Die Regeln ohne Zeichnung stehen in lib/firmen.js (Node-Test).
 */
import {
  ArrowLeft, Ban, BookOpen, Building2, ExternalLink, FileText, Mail, Pencil, Plus, Search, Send, StickyNote, Trash2, UserRound, X,
  BriefcaseBusiness,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, deleteRequest, patchJson, postJson } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card, EmptyState, Field, LoadingPanel, SectionHeading, TextArea, TextInput } from "@/components/ui";
import { bestaetigen } from "@/lib/bestaetigung";
import {
  datumText, fehlerText, filterKnoepfe, filterZeitleiste, hashFuerFirma, kannAnlegen, mutterOptionen, schreibweisen,
  sicherheitText, sprung, sprungText, statusText, statusTon, vorschlagText, zaehlungsZeile, zusammenfuehrenOptionen,
} from "@/lib/firmen";
import { STATUS_OPTIONS } from "@/utils";

const ART_ICON = {
  bewerbung: Send, stelle: BriefcaseBusiness, kontakt: UserRound, lebenslauf: Building2, korrespondenz: Mail,
  recherche: BookOpen, blacklist: Ban, erwaehnt: StickyNote,
};

const ALIAS_ARTEN = [
  ["schreibweise", "Andere Schreibweise"], ["frueherer_name", "Früherer Name"], ["kurzform", "Kurzform"], ["bereich", "Geschäftsbereich"],
];

const SELECT_KLASSE = "w-full rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-sm text-ink";

export default function FirmenAnsicht({ ziel }) {
  const { pushToast, reloadKey, navigateTo } = useApp();
  const [liste, setListe] = useState(null);
  const [auswahl, setAuswahl] = useState(null);          // { id } | { name } | null
  const [ansicht, setAnsicht] = useState(null);
  const [laedt, setLaedt] = useState(false);
  const [filter, setFilter] = useState("");
  const [suche, setSuche] = useState("");
  const [bearbeiten, setBearbeiten] = useState(false);
  const [vorschlaege, setVorschlaege] = useState(null);  // null = zu | { anzahl, vorschlaege, gewaehlt:Set }
  const [busy, setBusy] = useState(false);
  const letztesZiel = useRef(0);
  // `pushToast` ändert sich mit jeder Meldung; die Ladefunktionen dürfen sich deshalb nicht daran hängen — sonst lädt jede Meldung
  // die Ansicht neu, und nach dem Löschen fragte sie noch einmal nach der Firma, die es nicht mehr gibt.
  const melden = useRef(pushToast);
  melden.current = pushToast;

  const listeLaden = useCallback(async () => {
    try {
      setListe(await api("/api/firmen"));
    } catch (error) {
      melden.current(`Die Firmen ließen sich nicht laden: ${error.message}`, "danger");
    }
  }, []);

  const ansichtLaden = useCallback(async (wahl) => {
    if (!wahl) { setAnsicht(null); return; }
    setLaedt(true);
    try {
      const q = wahl.id ? `id=${encodeURIComponent(wahl.id)}` : `name=${encodeURIComponent(wahl.name)}`;
      setAnsicht(await api(`/api/firmen/ansicht?${q}`));
    } catch (error) {
      melden.current(error.message, "danger");
      setAnsicht(null);
    } finally {
      setLaedt(false);
    }
  }, []);

  useEffect(() => { listeLaden(); }, [listeLaden, reloadKey]);
  useEffect(() => { ansichtLaden(auswahl); }, [auswahl, ansichtLaden, reloadKey]);

  // Ein Sprung von außen (Stelle, Bewerbung, Kontakt, Link aus dem Chat) öffnet die Firma.
  useEffect(() => {
    if (!ziel || ziel.nonce === letztesZiel.current) return;
    letztesZiel.current = ziel.nonce;
    if (ziel.zurueck) zurueck();
    else if (ziel.firmaId) oeffnen({ id: ziel.firmaId });
    else if (ziel.firmaName) oeffnen({ name: ziel.firmaName });
  }, [ziel]);

  function oeffnen(wahl) {
    setFilter("");
    setBearbeiten(false);
    setAuswahl(wahl);
    try { window.history.replaceState(null, "", hashFuerFirma(wahl.id || wahl.name)); } catch { /* ohne Adresszeile geht es auch */ }
  }

  function zurueck() {
    setAuswahl(null);
    setAnsicht(null);
    setBearbeiten(false);
    setSuche("");                                   // „Alle Firmen“ zeigt alle, nicht die zuletzt gesuchte
    try { window.history.replaceState(null, "", "#kontakte"); } catch { /* s. o. */ }
  }

  async function neuLaden(neueWahl) {
    await listeLaden();
    if (neueWahl) setAuswahl(neueWahl);
    else await ansichtLaden(auswahl);
  }

  /** Führt eine Änderung aus, meldet das Ergebnis und lädt neu. Gibt die Antwort zurück (oder null bei einem Fehler). */
  async function ausfuehren(aufruf, erfolg, neueWahl) {
    setBusy(true);
    try {
      const antwort = await aufruf();
      if (erfolg) pushToast(typeof erfolg === "function" ? erfolg(antwort) : erfolg, "success");
      await neuLaden(typeof neueWahl === "function" ? neueWahl(antwort) : neueWahl);
      return antwort;
    } catch (error) {
      pushToast(fehlerText(error.payload, error.message), "danger");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function vorschlaegeOeffnen() {
    try {
      const daten = await api("/api/firmen/vorschlaege");
      setVorschlaege({ ...daten, gewaehlt: new Set(daten.vorschlaege.filter((v) => v.sicherheit === "hoch").map((v) => v.vorschlag_id)) });
    } catch (error) {
      pushToast(error.message, "danger");
    }
  }

  async function vorschlaegeAnwenden() {
    const auswahlIds = [...vorschlaege.gewaehlt];
    setBusy(true);
    try {
      const vorschau = await postJson("/api/firmen/vorschlaege/anwenden", { auswahl: auswahlIds });
      if (!(await bestaetigen({ titel: "Diese Firmen anlegen?", text: `${vorschau.text}\n\nBewerbungen, Stellen und Kontakte behalten ihren Text.`, ja: "Anlegen", gefahr: false }))) return;
      const antwort = await postJson("/api/firmen/vorschlaege/anwenden", { auswahl: auswahlIds, bestaetigt: true });
      pushToast(antwort.text, antwort.probleme?.length ? "warning" : "success");
      setVorschlaege(null);
      await neuLaden();
    } catch (error) {
      pushToast(fehlerText(error.payload, error.message), "danger");
    } finally {
      setBusy(false);
    }
  }

  const gefiltert = (liste?.firmen || []).filter((f) => {
    const s = suche.trim().toLowerCase();
    return !s || [f.name, ...(f.aliase || [])].some((n) => n.toLowerCase().includes(s));
  });

  // ── Die Ansicht einer Firma ─────────────────────────────────────────────────────────────────────────────
  if (auswahl) {
    return (
      <div data-firmen-ansicht>
        <div className="mb-4">
          <Button size="sm" variant="ghost" onClick={zurueck} title="Zurück zur Liste aller Firmen.">
            <ArrowLeft size={14} className="mr-1 inline" /> Alle Firmen
          </Button>
        </div>
        {laedt && !ansicht ? <LoadingPanel label="Die Firma wird geladen …" /> : null}
        {ansicht && ansicht.status === "ok" ? (
          <Detail
            ansicht={ansicht} liste={liste} filter={filter} setFilter={setFilter} bearbeiten={bearbeiten} setBearbeiten={setBearbeiten}
            busy={busy} ausfuehren={ausfuehren} oeffnen={oeffnen} navigateTo={navigateTo} pushToast={pushToast}
            geloescht={() => { zurueck(); listeLaden(); }}
          />
        ) : null}
        {ansicht && ansicht.status !== "ok" ? (
          <EmptyState title="Diese Firma gibt es nicht (mehr)" description={ansicht.text || ""}
            action={<Button size="sm" variant="secondary" onClick={zurueck}>Zur Liste</Button>} />
        ) : null}
      </div>
    );
  }

  // ── Die Liste ───────────────────────────────────────────────────────────────────────────────────────────
  return (
    <div data-firmen-liste>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input
            type="search" value={suche} onChange={(e) => setSuche(e.target.value)} aria-label="Firma suchen oder öffnen"
            onKeyDown={(e) => { if (e.key === "Enter" && suche.trim()) oeffnen({ name: suche.trim() }); }}
            placeholder="Firma suchen — Enter öffnet, was PBP zu diesem Namen weiß …"
            className="w-full rounded-lg border border-white/8 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-ink placeholder-muted focus:border-sky/40 focus:outline-none"
          />
        </div>
        <Button size="sm" variant="secondary" disabled={!suche.trim()} onClick={() => oeffnen({ name: suche.trim() })}
          title="Zeigt alles, was PBP zu diesem Namen weiß — auch wenn es noch keinen Firmen-Eintrag gibt.">
          Öffnen
        </Button>
      </div>

      {liste?.offene_vorschlaege ? (
        <Card className="mb-4 rounded-2xl border-sky/30" data-firmen-vorschlaege-hinweis>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink">
              PBP hat {liste.offene_vorschlaege === 1 ? "einen Vorschlag" : "Vorschläge"}: Namen aus deinen Bewerbungen, Kontakten und dem
              Lebenslauf, die vermutlich dieselbe Firma sind. Nichts davon wird ohne dein Ja angelegt.
            </p>
            <Button size="sm" variant="secondary" onClick={vorschlaegeOeffnen} disabled={busy}>Vorschläge ansehen</Button>
          </div>
        </Card>
      ) : null}

      {vorschlaege ? (
        <Card className="mb-4 rounded-2xl" data-firmen-vorschlaege>
          <SectionHeading title="Vorschläge" description="Was PBP für dieselbe Firma hält. Du entscheidest, was angelegt wird."
            action={<Button size="sm" variant="ghost" onClick={() => setVorschlaege(null)} title="Schließt die Vorschläge."><X size={14} /></Button>} />
          <div className="grid gap-1">
            {vorschlaege.vorschlaege.map((v) => (
              <label key={v.vorschlag_id} className="flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-white/[0.04]">
                <input
                  type="checkbox" className="mt-1" checked={vorschlaege.gewaehlt.has(v.vorschlag_id)} data-firmen-vorschlag={v.vorschlag_id}
                  onChange={() => {
                    const g = new Set(vorschlaege.gewaehlt);
                    if (g.has(v.vorschlag_id)) g.delete(v.vorschlag_id); else g.add(v.vorschlag_id);
                    setVorschlaege({ ...vorschlaege, gewaehlt: g });
                  }}
                />
                <span className="min-w-0 flex-1">
                  <span className="text-ink">{vorschlagText(v)}</span>
                  <span className="block text-xs text-muted">{(v.schreibweisen || []).join(" · ")}</span>
                </span>
                <span title={sicherheitText(v.sicherheit)}><Badge tone={v.sicherheit === "hoch" ? "success" : "amber"}>{v.sicherheit === "hoch" ? "sicher" : "prüfen"}</Badge></span>
              </label>
            ))}
            {!vorschlaege.vorschlaege.length ? <p className="text-sm text-muted">Im Moment gibt es nichts vorzuschlagen.</p> : null}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy || vorschlaege.gewaehlt.size === 0} onClick={vorschlaegeAnwenden}>
              Ausgewählte anlegen ({vorschlaege.gewaehlt.size})
            </Button>
            <p className="text-xs text-muted">Danach fragt PBP noch einmal nach. Frühere Namen und Geschäftsbereiche kennt nur du — die trägst du in der Firma ein.</p>
          </div>
        </Card>
      ) : null}

      {!liste ? <LoadingPanel label="Firmen werden geladen …" /> : null}
      {liste && !liste.firmen.length ? (
        <EmptyState
          title="Noch keine Firmen angelegt"
          description="Ein Firmen-Eintrag fasst die Schreibweisen einer Firma zusammen („Alt AG“ heißt heute „Neu GmbH“) und kennt ihre Mutterfirma. Suche oben einen Namen und öffne ihn: PBP zeigt alles, was es dazu weiß — und du kannst ihn dort als Firma anlegen."
        />
      ) : null}
      {liste && liste.firmen.length ? (
        <div className="grid gap-2 sm:grid-cols-2" data-firmen-karten>
          {gefiltert.map((f) => (
            <button key={f.id} type="button" onClick={() => oeffnen({ id: f.id })} data-firma-karte={f.id}
              className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 text-left transition-colors hover:bg-white/[0.06]"
              title={`Öffnet alles, was PBP zu ${f.name} weiß.`}>
              <span className="flex items-center gap-2">
                <Building2 size={16} className="text-muted" aria-hidden="true" />
                <span className="font-semibold text-ink">{f.name}</span>
              </span>
              <span className="mt-1 block text-xs text-muted">
                {[f.aliase?.length ? `auch: ${f.aliase.slice(0, 3).join(", ")}${f.aliase.length > 3 ? " …" : ""}` : "",
                  f.mutterfirma ? `Mutterfirma: ${f.mutterfirma}` : "", f.tochterfirmen ? `${f.tochterfirmen} Tochterfirma${f.tochterfirmen === 1 ? "" : "en"}` : "",
                  f.branche].filter(Boolean).join(" · ") || "Noch keine Schreibweisen eingetragen."}
              </span>
            </button>
          ))}
          {!gefiltert.length ? <p className="text-sm text-muted">Keine Firma mit diesem Namen im Firmen-Eintrag. Mit Enter öffnest du trotzdem, was PBP dazu weiß.</p> : null}
        </div>
      ) : null}
    </div>
  );
}

// ── Detail ────────────────────────────────────────────────────────────────────────────────────────────────

function Detail({ ansicht, liste, filter, setFilter, bearbeiten, setBearbeiten, busy, ausfuehren, oeffnen, navigateTo, pushToast, geloescht }) {
  const stamm = ansicht.stammsatz;
  const eintraege = filterZeitleiste(ansicht.zeitleiste, filter);
  const knoepfe = filterKnoepfe(ansicht.zaehlung);

  async function alsFirmaAnlegen() {
    await ausfuehren(() => postJson("/api/firmen", { name: ansicht.name }), "Die Firma ist angelegt.", (antwort) => ({ id: antwort.firma.id }));
  }

  function gehe(ziel) {
    const s = sprung(ziel);
    if (s) navigateTo(s.seite, s.intent);
  }

  return (
    <div className="grid gap-4" data-firmen-detail={stamm?.id || "ohne-eintrag"}>
      <Card className="rounded-2xl">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Building2 size={18} className="text-muted" aria-hidden="true" />
              <h2 className="text-lg font-semibold text-ink" data-firma-name>{ansicht.name}</h2>
              {stamm ? <Badge tone="success">Firmen-Eintrag</Badge> : <span title="PBP kennt den Namen aus deinen Daten, hat aber noch keinen Firmen-Eintrag dazu."><Badge>ohne Eintrag</Badge></span>}
            </div>
            {stamm ? (
              <p className="mt-1 text-sm text-muted">
                {[stamm.branche, stamm.standorte].filter(Boolean).join(" · ")}
              </p>
            ) : null}
            <p className="mt-1 text-sm text-ink">{zaehlungsZeile(ansicht.zaehlung, ansicht.aussortiert) || "Dazu hat PBP noch nichts gespeichert."}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {kannAnlegen(ansicht) ? (
              <Button size="sm" disabled={busy} onClick={alsFirmaAnlegen} title="Legt einen Firmen-Eintrag an, damit Schreibweisen, Mutterfirma und Kontakte dort gepflegt werden können.">
                <Plus size={14} className="mr-1 inline" /> Als Firma anlegen
              </Button>
            ) : null}
            {stamm ? (
              <Button size="sm" variant={bearbeiten ? "primary" : "secondary"} onClick={() => setBearbeiten(!bearbeiten)} aria-pressed={bearbeiten}
                title="Schreibweisen, Mutterfirma, Kontakte und mehr ändern.">
                <Pencil size={14} className="mr-1 inline" /> {bearbeiten ? "Fertig" : "Bearbeiten"}
              </Button>
            ) : null}
          </div>
        </div>

        {stamm ? (
          <div className="mt-3 grid gap-2 text-sm" data-firma-stamm>
            {schreibweisen(stamm).length ? (
              <p className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted">Zählt auch als:</span>
                {schreibweisen(stamm).map((a) => (
                  <span key={a.id} title={a.art_text}><Badge tone="sky">{a.alias}</Badge></span>
                ))}
              </p>
            ) : null}
            {stamm.mutterfirma || stamm.tochterfirmen?.length ? (
              <p className="flex flex-wrap items-center gap-1.5">
                {stamm.mutterfirma ? (<>
                  <span className="text-xs text-muted">Mutterfirma:</span>
                  <button type="button" className="text-sky underline-offset-2 hover:underline" onClick={() => oeffnen({ id: stamm.mutterfirma.id })}>{stamm.mutterfirma.name}</button>
                </>) : null}
                {stamm.tochterfirmen?.length ? (<>
                  <span className="ml-2 text-xs text-muted">Tochterfirmen:</span>
                  {stamm.tochterfirmen.map((t) => (
                    <button key={t.id} type="button" className="text-sky underline-offset-2 hover:underline" onClick={() => oeffnen({ id: t.id })}>{t.name}</button>
                  ))}
                </>) : null}
                <span className="text-xs text-muted">· Konzern wird mitgesucht, aber nie als dieselbe Firma behandelt.</span>
              </p>
            ) : null}
            {stamm.notizen ? <p className="whitespace-pre-line text-sm text-muted">{stamm.notizen}</p> : null}
          </div>
        ) : null}
        {ansicht.mehrdeutig?.length ? (
          <p className="mt-3 rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink" data-firma-mehrdeutig>
            Der Name passt zu mehreren Firmen: {ansicht.mehrdeutig.join(", ")}. PBP rät nicht — öffne die gemeinte Firma über die Liste.
          </p>
        ) : null}
      </Card>

      {ansicht.warnungen?.length ? (
        <Card className="rounded-2xl border-amber/40" data-firma-warnungen>
          <SectionHeading title="Bitte zuerst lesen" description="Hier läuft schon etwas — vor jedem weiteren Schritt klären." />
          <ul className="grid gap-2">
            {ansicht.warnungen.map((w, i) => <li key={i} className="rounded-xl border border-amber/30 bg-amber/10 p-3 text-sm text-ink">{w}</li>)}
          </ul>
        </Card>
      ) : null}

      {bearbeiten && stamm ? (
        <Bearbeiten stamm={stamm} liste={liste} busy={busy} ausfuehren={ausfuehren} oeffnen={oeffnen} pushToast={pushToast} geloescht={geloescht} />
      ) : null}

      <Card className="rounded-2xl">
        <SectionHeading title="Historie" description="Alles, was PBP zu dieser Firma weiß — das Neueste zuerst. Jeder Eintrag führt dorthin, wo er steht." />
        {knoepfe.length > 1 ? (
          <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label="Historie filtern" data-firma-filter>
            {[{ art: "", label: "Alles", anzahl: ansicht.zeitleiste.length }, ...knoepfe].map((k) => (
              <button key={k.art || "alles"} type="button" aria-pressed={filter === k.art} onClick={() => setFilter(k.art)}
                className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${filter === k.art ? "bg-sky/15 text-sky" : "text-muted hover:bg-white/5"}`}>
                {k.label} ({k.anzahl})
              </button>
            ))}
          </div>
        ) : null}

        {!ansicht.zeitleiste.length ? (
          <p className="text-sm text-muted" data-firma-leer>
            {ansicht.gefunden ? "Zu dieser Firma gibt es nur aussortierte Stellen (unten)." : "Zu diesem Namen hat PBP nichts gespeichert — weder Bewerbungen, Stellen, Lebenslauf, Kontakte, Dokumente noch Recherchen."}
            {ansicht.aehnliche?.length ? ` Namen, die so beginnen: ${ansicht.aehnliche.join(", ")}.` : ""}
          </p>
        ) : (
          <ol className="grid gap-2" data-firma-zeitleiste>
            {eintraege.map((e, i) => (
              <Eintrag key={`${e.art}-${i}-${e.titel}`} e={e} bearbeiten={bearbeiten} busy={busy} ausfuehren={ausfuehren} gehe={gehe} />
            ))}
          </ol>
        )}

        {ansicht.aussortiert?.anzahl ? (
          <div className="mt-4 rounded-xl border border-line/30 bg-shell/40 p-3 text-sm" data-firma-aussortiert>
            <p className="text-ink">{ansicht.aussortiert.anzahl} aussortierte {ansicht.aussortiert.anzahl === 1 ? "Stelle" : "Stellen"}</p>
            <p className="mt-1 text-xs text-muted">
              Gründe gelten je Stelle, nicht für die Firma: dieselbe Firma schreibt passende und unpassende Rollen aus.
              {" "}{Object.entries(ansicht.aussortiert.gruende || {}).map(([g, n]) => `${g.replaceAll("_", " ")} (${n})`).join(" · ")}
            </p>
            {ansicht.aussortiert.beispiele?.length ? (
              <ul className="mt-2 grid gap-0.5 text-xs text-muted">
                {ansicht.aussortiert.beispiele.map((b, i) => <li key={i}>{b.titel}{b.grund ? ` — ${String(b.grund).replaceAll("_", " ")}` : ""}</li>)}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}

function Eintrag({ e, bearbeiten, busy, ausfuehren, gehe }) {
  const Icon = ART_ICON[e.art] || FileText;
  const [aendern, setAendern] = useState(false);
  const zuordnung = e.ref?.zuordnung_id;
  const s = sprung(e.ziel);
  return (
    <li className="rounded-xl border border-line/30 bg-shell/40 px-3 py-2.5" data-firma-eintrag={e.art}>
      <div className="flex flex-wrap items-start gap-3">
        <Icon size={16} className="mt-0.5 shrink-0 text-muted" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-ink">{e.titel || e.rolle_text}</span>
            <Badge tone={e.art === "kontakt" && e.aktuell === false ? "neutral" : "sky"}>{e.rolle_text}</Badge>
            {e.status ? <Badge tone={statusTon(e.status)}>{statusText(e.status, STATUS_OPTIONS)}</Badge> : null}
            {e.art === "kontakt" && e.aktuell === false ? <Badge>früher</Badge> : null}
            {e.via_text ? <span title={e.gefunden_als ? `Gefunden als „${e.gefunden_als}“.` : ""}><Badge tone="amber">{e.via_text}{e.gefunden_als ? `: ${e.gefunden_als}` : ""}</Badge></span> : null}
          </div>
          {e.text ? <p className="mt-0.5 text-sm text-muted">{e.text}</p> : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className="text-xs text-muted">{datumText(e.datum)}</span>
          {s ? (
            <button type="button" className="inline-flex items-center gap-1 text-xs text-sky underline-offset-2 hover:underline" onClick={() => gehe(e.ziel)} title={sprungText(e.ziel)}>
              {sprungText(e.ziel)} <ExternalLink size={12} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      </div>
      {bearbeiten && zuordnung ? (
        <div className="mt-2 border-t border-line/20 pt-2">
          {aendern ? (
            <ZuordnungFormular start={e.ref} busy={busy} abbrechen={() => setAendern(false)}
              speichern={async (felder) => {
                const antwort = await ausfuehren(() => patchJson(`/api/firmen/zuordnungen/${zuordnung}`, felder), "Gespeichert.");
                if (antwort) setAendern(false);
              }} />
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="ghost" onClick={() => setAendern(true)} title="Rolle und Zeitraum dieses Kontakts bei dieser Firma ändern.">Zeitraum ändern</Button>
              <Button size="sm" variant="ghost" disabled={busy} title="Nimmt den Kontakt aus dieser Firma. Der Kontakt selbst bleibt."
                onClick={async () => {
                  if (!(await bestaetigen({ titel: "Aus der Firma nehmen?", text: `${e.titel} gehört dann nicht mehr zu dieser Firma. Der Kontakt bleibt unverändert.`, ja: "Herausnehmen" }))) return;
                  await ausfuehren(() => deleteRequest(`/api/firmen/zuordnungen/${zuordnung}`), "Der Kontakt gehört nicht mehr zu dieser Firma.");
                }}>
                <X size={14} className="mr-1 inline" /> Herausnehmen
              </Button>
            </div>
          )}
        </div>
      ) : null}
    </li>
  );
}

/** Rolle und Zeitraum eines Kontakts bei einer Firma. `aktuell` ergibt sich aus dem Ende, wenn nichts gewählt ist. */
function ZuordnungFormular({ start, busy, speichern, abbrechen }) {
  const [rolle, setRolle] = useState(start?.rolle || "");
  const [von, setVon] = useState(start?.von || "");
  const [bis, setBis] = useState(start?.bis || "");
  const [aktuell, setAktuell] = useState(!start?.bis);
  return (
    <form className="grid gap-2 sm:grid-cols-2" onSubmit={(ev) => { ev.preventDefault(); speichern({ rolle, von, bis, aktuell: bis ? false : aktuell }); }} data-firma-zuordnung-formular>
      <Field label="Rolle dort" hint="zum Beispiel Recruiter, Kollege, Mentor"><TextInput value={rolle} onChange={(e) => setRolle(e.target.value)} /></Field>
      <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink">
        <input type="checkbox" checked={bis ? false : aktuell} disabled={Boolean(bis)} onChange={(e) => setAktuell(e.target.checked)} /> arbeitet dort noch
      </label>
      <Field label="Von" hint="2021, 2021-03 oder 03.2021 — leer = unbekannt"><TextInput value={von} onChange={(e) => setVon(e.target.value)} placeholder="2021" /></Field>
      <Field label="Bis" hint="leer = bis heute"><TextInput value={bis} onChange={(e) => setBis(e.target.value)} placeholder="2023" /></Field>
      <div className="flex gap-2 sm:col-span-2">
        <Button size="sm" type="submit" disabled={busy}>Speichern</Button>
        <Button size="sm" variant="ghost" type="button" onClick={abbrechen}>Abbrechen</Button>
      </div>
    </form>
  );
}

// ── Bearbeiten ────────────────────────────────────────────────────────────────────────────────────────────

function Bearbeiten({ stamm, liste, busy, ausfuehren, oeffnen, pushToast, geloescht }) {
  const [name, setName] = useState(stamm.name);
  const [branche, setBranche] = useState(stamm.branche || "");
  const [standorte, setStandorte] = useState(stamm.standorte || "");
  const [notizen, setNotizen] = useState(stamm.notizen || "");
  const [alias, setAlias] = useState("");
  const [art, setArt] = useState("schreibweise");
  const [mutter, setMutter] = useState(stamm.mutterfirma?.id || "");
  const [zusammen, setZusammen] = useState("");
  const [kontakte, setKontakte] = useState(null);
  const [kontakt, setKontakt] = useState({ id: "", rolle: "", von: "", bis: "" });

  useEffect(() => {
    setName(stamm.name); setBranche(stamm.branche || ""); setStandorte(stamm.standorte || ""); setNotizen(stamm.notizen || "");
    setMutter(stamm.mutterfirma?.id || "");
  }, [stamm.id, stamm.name, stamm.branche, stamm.standorte, stamm.notizen, stamm.mutterfirma?.id]);

  useEffect(() => {
    let abgebrochen = false;
    api("/api/contacts").then((d) => { if (!abgebrochen) setKontakte(d?.contacts || []); }).catch(() => { if (!abgebrochen) setKontakte([]); });
    return () => { abgebrochen = true; };
  }, []);

  const andere = zusammenfuehrenOptionen(liste?.firmen, stamm);
  const muetter = mutterOptionen(liste?.firmen, stamm);

  async function stammdatenSpeichern() {
    const felder = { branche, standorte, notizen };
    if (name.trim() && name.trim() !== stamm.name) felder.name = name.trim();
    await ausfuehren(() => patchJson(`/api/firmen/${stamm.id}`, felder), "Gespeichert.");
  }

  async function zusammenfuehren() {
    const quelle = andere.find((f) => f.id === zusammen);
    if (!quelle) return;
    if (!(await bestaetigen({
      titel: "Diese Firmen zusammenführen?",
      text: `„${quelle.name}“ geht in „${stamm.name}“ auf: ihr Name und ihre Schreibweisen wandern hierher, ihr Eintrag verschwindet. Bewerbungen und Stellen bleiben unverändert.`,
      ja: "Zusammenführen",
    }))) return;
    await ausfuehren(() => postJson(`/api/firmen/${stamm.id}/zusammenfuehren`, { quelle_id: quelle.id, bestaetigt: true }), "Die Firmen sind zusammengeführt.");
    setZusammen("");
  }

  async function loeschen() {
    if (!(await bestaetigen({
      titel: "Den Firmen-Eintrag löschen?",
      text: `Der Eintrag „${stamm.name}“ mit seinen ${stamm.aliase.length} Schreibweisen wird gelöscht. Bewerbungen, Stellen, Kontakte und Lebenslauf bleiben unverändert.`,
      ja: "Löschen",
    }))) return;
    try {
      await deleteRequest(`/api/firmen/${stamm.id}?bestaetigt=true`);
      pushToast("Der Firmen-Eintrag ist gelöscht.", "success");
      geloescht();
    } catch (error) {
      pushToast(fehlerText(error.payload, error.message), "danger");
    }
  }

  return (
    <Card className="rounded-2xl border-sky/30" data-firma-bearbeiten>
      <SectionHeading title="Bearbeiten" description="Hier änderst du nur den Firmen-Eintrag. Bewerbungen, Stellen, Kontakte und Lebenslauf behalten ihren Text." />
      <div className="grid gap-5">
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={(ev) => { ev.preventDefault(); stammdatenSpeichern(); }}>
          <Field label="Name"><TextInput value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Branche"><TextInput value={branche} onChange={(e) => setBranche(e.target.value)} /></Field>
          <Field label="Standorte"><TextInput value={standorte} onChange={(e) => setStandorte(e.target.value)} /></Field>
          <Field label="Notizen" className="sm:col-span-2"><TextArea rows={3} value={notizen} onChange={(e) => setNotizen(e.target.value)} /></Field>
          <div className="sm:col-span-2"><Button size="sm" type="submit" disabled={busy}>Speichern</Button></div>
        </form>

        <div data-firma-aliase>
          <h3 className="text-sm font-semibold text-ink">Schreibweisen</h3>
          <p className="mb-2 text-xs text-muted">Namen, unter denen diese Firma bei dir vorkommt: früherer Name, Kurzform, Geschäftsbereich.</p>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {stamm.aliase.map((a) => (
              <span key={a.id} className="inline-flex items-center gap-1 rounded-lg border border-sky/15 bg-sky/8 px-2.5 py-1 text-sm text-sky" title={a.art_text}>
                {a.alias}
                <button type="button" className="text-sky/70 hover:text-sky" aria-label={`${a.alias} entfernen`} title="Entfernt diese Schreibweise. Bewerbungen und Stellen bleiben unverändert."
                  onClick={() => ausfuehren(() => deleteRequest(`/api/firmen/${stamm.id}/aliase/${a.id}`), "Entfernt.")}><X size={12} /></button>
              </span>
            ))}
            {!stamm.aliase.length ? <span className="text-sm text-muted">Noch keine.</span> : null}
          </div>
          <form className="flex flex-wrap items-end gap-2" onSubmit={async (ev) => {
            ev.preventDefault();
            if (!alias.trim()) return;
            const antwort = await ausfuehren(() => postJson(`/api/firmen/${stamm.id}/aliase`, { alias: alias.trim(), art }), "Hinzugefügt.");
            if (antwort) setAlias("");
          }}>
            <Field label="Neue Schreibweise" className="min-w-[200px] flex-1"><TextInput value={alias} onChange={(e) => setAlias(e.target.value)} placeholder="zum Beispiel Alt AG" /></Field>
            <label className="grid gap-1.5 text-sm"><span className="text-[13px] font-medium text-ink/80">Art</span>
              <select className={SELECT_KLASSE} value={art} onChange={(e) => setArt(e.target.value)} aria-label="Art der Schreibweise">
                {ALIAS_ARTEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
              </select>
            </label>
            <Button size="sm" type="submit" disabled={busy || !alias.trim()}>Hinzufügen</Button>
          </form>
        </div>

        <div data-firma-mutter>
          <h3 className="text-sm font-semibold text-ink">Mutterfirma</h3>
          <p className="mb-2 text-xs text-muted">Konzern und Tochter werden zusammen gefunden, aber nie als dieselbe Firma behandelt.</p>
          <div className="flex flex-wrap items-center gap-2">
            <select className={`${SELECT_KLASSE} max-w-xs`} value={mutter} onChange={(e) => setMutter(e.target.value)} aria-label="Mutterfirma">
              <option value="">keine</option>
              {muetter.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
            <Button size="sm" variant="secondary" disabled={busy || mutter === (stamm.mutterfirma?.id || "")}
              onClick={() => ausfuehren(() => patchJson(`/api/firmen/${stamm.id}`, { mutterfirma_id: mutter }), mutter ? "Mutterfirma gesetzt." : "Mutterfirma gelöst.")}>
              Übernehmen
            </Button>
          </div>
        </div>

        <div data-firma-kontakt-zuordnen>
          <h3 className="text-sm font-semibold text-ink">Kontakt dieser Firma zuordnen</h3>
          <p className="mb-2 text-xs text-muted">Dieselbe Person kann mehreren Firmen angehören, aktuell oder früher. Der Text „Firma“ am Kontakt bleibt, wie er ist.</p>
          <form className="grid gap-2 sm:grid-cols-4" onSubmit={async (ev) => {
            ev.preventDefault();
            if (!kontakt.id) return;
            const antwort = await ausfuehren(() => postJson(`/api/firmen/${stamm.id}/kontakte`, { kontakt_id: kontakt.id, rolle: kontakt.rolle, von: kontakt.von, bis: kontakt.bis }), "Zugeordnet.");
            if (antwort) setKontakt({ id: "", rolle: "", von: "", bis: "" });
          }}>
            <label className="grid gap-1.5 text-sm sm:col-span-2"><span className="text-[13px] font-medium text-ink/80">Kontakt</span>
              <select className={SELECT_KLASSE} value={kontakt.id} onChange={(e) => setKontakt({ ...kontakt, id: e.target.value })} aria-label="Kontakt">
                <option value="">{kontakte === null ? "Kontakte werden geladen …" : "Bitte wählen"}</option>
                {(kontakte || []).map((k) => <option key={k.id} value={k.id}>{k.full_name}{k.company ? ` (${k.company})` : ""}</option>)}
              </select>
            </label>
            <Field label="Rolle dort"><TextInput value={kontakt.rolle} onChange={(e) => setKontakt({ ...kontakt, rolle: e.target.value })} placeholder="Recruiter" /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Von"><TextInput value={kontakt.von} onChange={(e) => setKontakt({ ...kontakt, von: e.target.value })} placeholder="2021" /></Field>
              <Field label="Bis"><TextInput value={kontakt.bis} onChange={(e) => setKontakt({ ...kontakt, bis: e.target.value })} placeholder="heute" /></Field>
            </div>
            <div className="sm:col-span-4"><Button size="sm" type="submit" disabled={busy || !kontakt.id}>Zuordnen</Button></div>
          </form>
        </div>

        {andere.length ? (
          <div data-firma-zusammenfuehren>
            <h3 className="text-sm font-semibold text-ink">Mit einer anderen Firma zusammenführen</h3>
            <p className="mb-2 text-xs text-muted">Wenn zwei Einträge dieselbe Firma sind. Der gewählte Eintrag geht in diesem auf.</p>
            <div className="flex flex-wrap items-center gap-2">
              <select className={`${SELECT_KLASSE} max-w-xs`} value={zusammen} onChange={(e) => setZusammen(e.target.value)} aria-label="Firma, die in diese aufgeht">
                <option value="">Bitte wählen</option>
                {andere.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
              <Button size="sm" variant="secondary" disabled={busy || !zusammen} onClick={zusammenfuehren}>Zusammenführen …</Button>
            </div>
          </div>
        ) : null}

        <div className="border-t border-line/20 pt-3" data-firma-loeschen>
          <Button size="sm" variant="ghost" disabled={busy} onClick={loeschen} title="Löscht nur den Firmen-Eintrag. Bewerbungen, Stellen, Kontakte und Lebenslauf bleiben.">
            <Trash2 size={14} className="mr-1 inline" /> Firmen-Eintrag löschen …
          </Button>
        </div>
      </div>
    </Card>
  );
}
