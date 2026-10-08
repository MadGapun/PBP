// Firmen-Ansicht (#1080, v1.8): die Regeln, die nichts zeichnen. Die Ansicht liest GET /api/firmen/ansicht — dieselbe Antwort
// wie `firma_kontext` im Chat, nur für Menschen ausgelegt (services/firmen_ansicht.py).

import { zuBewerbung, zuDokument, zuKontakt, zuStelle } from "./wege.js";

/** Reihenfolge der Filter über der Zeitleiste. */
export const ART_REIHENFOLGE = ["bewerbung", "stelle", "kontakt", "lebenslauf", "korrespondenz", "recherche", "blacklist", "erwaehnt"];

/** Wie eine Art im Filter und in der Kopfzeile heißt (Einzahl, Mehrzahl). */
export const ART_NAMEN = {
  bewerbung: ["Bewerbung", "Bewerbungen"],
  stelle: ["Stelle", "Stellen"],
  kontakt: ["Kontakt", "Kontakte"],
  lebenslauf: ["Station im Lebenslauf", "Stationen im Lebenslauf"],
  korrespondenz: ["Dokument", "Dokumente"],
  recherche: ["Recherche", "Recherchen"],
  blacklist: ["Blacklist-Eintrag", "Blacklist-Einträge"],
  erwaehnt: ["Erwähnung in Notizen", "Erwähnungen in Notizen"],
};

export function artName(art, anzahl) {
  const namen = ART_NAMEN[art] || [art, art];
  return anzahl === 1 ? namen[0] : namen[1];
}

/** Datum für Menschen: 2026-09-10 → 10.09.2026, 2021-03 → 03.2021, 2021 → 2021, leer → „ohne Datum“. */
export function datumText(datum) {
  const s = String(datum || "").trim();
  if (!s) return "ohne Datum";
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(s);
  if (!m) return s;
  const [, jahr, monat, tag] = m;
  if (tag) return `${tag}.${monat}.${jahr}`;
  if (monat) return `${monat}.${jahr}`;
  return jahr;
}

/** Nur die Einträge einer Art; ohne Art alle. */
export function filterZeitleiste(zeitleiste, art) {
  const liste = Array.isArray(zeitleiste) ? zeitleiste : [];
  return art ? liste.filter((e) => e.art === art) : liste;
}

/** Die Arten, zu denen es etwas gibt, in fester Reihenfolge, mit Anzahl — die Filter-Knöpfe über der Zeitleiste. */
export function filterKnoepfe(zaehlung) {
  const z = zaehlung || {};
  return ART_REIHENFOLGE.filter((art) => (z[art] || 0) > 0).map((art) => ({ art, anzahl: z[art], label: artName(art, z[art]) }));
}

/** Eine Zeile über der Zeitleiste: „2 Bewerbungen · 1 Stelle · 1 Kontakt“. Leer, wenn es nichts gibt. */
export function zaehlungsZeile(zaehlung, aussortiert) {
  const teile = filterKnoepfe(zaehlung).map((k) => `${k.anzahl} ${k.label}`);
  const n = Number(aussortiert?.anzahl || 0);
  if (n > 0) teile.push(`${n} aussortierte ${n === 1 ? "Stelle" : "Stellen"}`);
  return teile.join(" · ");
}

/**
 * Wohin ein Eintrag führt: { seite, intent } für `navigateTo(seite, intent)` der App.
 * Ohne Ziel (oder mit unbekannter Seite) → null; dann zeigt die Ansicht keinen „Öffnen“-Knopf.
 */
export function sprung(ziel) {
  if (!ziel || !ziel.seite) return null;
  // #1171 (G85): ein Eintrag oeffnet SEIN Objekt (Stelle, Person, Dokument), nicht nur die Seite dazu.
  // Was ein Sprung meint, steht in lib/wege.js; hier nur die Zuordnung der Felder des Servers.
  switch (ziel.seite) {
    case "bewerbungen": {
      const z = zuBewerbung(ziel.bewerbung_id);
      return { seite: "bewerbungen", intent: z ? z.intent : null };
    }
    case "stellen": {
      const z = zuStelle(ziel.job_hash);
      return { seite: "stellen", intent: z ? z.intent : null };
    }
    case "kontakte": {
      const z = zuKontakt(ziel.kontakt_id);
      return { seite: "kontakte", intent: z ? z.intent : { ansicht: "kontakte", suche: ziel.suche || "" } };
    }
    case "dokumente": {
      const z = zuDokument(ziel.dokument_id);
      return { seite: "dokumente", intent: z ? z.intent : null };
    }
    case "profil":
    case "suche":
      return { seite: ziel.seite, intent: null };
    default:
      return null;
  }
}

/** Wohin der Knopf „Öffnen“ führt, als Wort: „Bewerbung öffnen“, „Im Profil ansehen“ … */
export function sprungText(ziel) {
  switch (ziel?.seite) {
    case "bewerbungen": return "Bewerbung öffnen";
    case "stellen": return "Stelle öffnen";
    case "kontakte": return "Kontakt öffnen";
    case "profil": return "Im Profil ansehen";
    case "dokumente": return "Bei den Dokumenten ansehen";
    case "suche": return "Blacklist ansehen";
    default: return "";
  }
}

/**
 * Ein Hash hinter #kontakte/ → die Firmen-Ansicht: „fi_…“ ist die Kennung eines Firmen-Eintrags, „firma:Name“ ein Name.
 * Alles andere ist keine Firma (null). `kennung` kommt aus utils.parseHashZiel (schon dekodiert).
 */
export function ansichtAusKennung(kennung) {
  const k = String(kennung || "").trim();
  if (!k) return null;
  if (k.startsWith("fi_")) return { ansicht: "firmen", firmaId: k };
  if (k.startsWith("firma:") && k.length > 6) return { ansicht: "firmen", firmaName: k.slice(6) };
  return null;
}

/** Der Hash, der zu einer Firma führt — das Gegenstück zu `ansichtAusKennung`. Mit Kennung (fi_…) oder Name. */
export function hashFuerFirma(idOderName) {
  const s = String(idOderName || "").trim();
  if (!s) return "#kontakte";
  return "#kontakte/" + encodeURIComponent(s.startsWith("fi_") ? s : `firma:${s}`);
}

/** Welche Badge-Farbe zu einem Bewerbungsstatus passt (nur zur Orientierung, nie als Aussage). */
export function statusTon(status) {
  switch (status) {
    case "angebot": case "angenommen": return "success";
    case "interview": case "zweitgespraech": case "interview_abgeschlossen": return "sky";
    case "abgelehnt": case "arbeitgeber_ausgefallen": return "danger";
    case "zurueckgezogen": case "abgelaufen": return "neutral";
    default: return "neutral";
  }
}

/** Der Text auf dem Badge: der Status in Worten (siehe STATUS_OPTIONS in utils.js); unbekannte Werte bleiben, wie sie sind. */
export function statusText(status, optionen) {
  const treffer = (optionen || []).find((o) => o.value === status);
  return treffer ? treffer.label : status || "";
}

/** Die Schreibweisen einer Firma für die Kopfzeile: Name zuerst, dann die bestätigten, ohne Doppelte. */
export function schreibweisen(stamm) {
  if (!stamm) return [];
  const gesehen = new Set();
  const aus = [];
  for (const a of stamm.aliase || []) {
    const k = String(a.alias || "").trim().toLowerCase();
    if (k && !gesehen.has(k)) {
      gesehen.add(k);
      aus.push({ id: a.id, alias: a.alias, art: a.art, art_text: a.art_text });
    }
  }
  return aus;
}

/** Als Mutterfirma kommen alle anderen Firmen in Frage — nie die Firma selbst und nie eine ihrer Töchter (das ergäbe einen Kreis). */
export function mutterOptionen(firmen, firma) {
  if (!firma) return [];
  const kinder = new Set((firma.tochterfirmen || []).map((t) => t.id));
  return (firmen || []).filter((f) => f.id !== firma.id && !kinder.has(f.id));
}

/** Die Firma, mit der sich `firma` zusammenführen ließe: alle anderen. */
export function zusammenfuehrenOptionen(firmen, firma) {
  return (firmen || []).filter((f) => f.id !== firma?.id);
}

/** Ein Satz zu einem Vorschlag der Bestandsprüfung. */
export function vorschlagText(v) {
  if (!v) return "";
  const anzahl = (v.schreibweisen || []).length;
  const wie = v.art === "ergaenzung"
    ? `ergänzt „${v.ergaenzt_firma?.name || "?"}“ um ${(v.neue_schreibweisen || []).length} Schreibweise${(v.neue_schreibweisen || []).length === 1 ? "" : "n"}`
    : `${anzahl} Schreibweisen, ${v.vorkommen} Vorkommen`;
  return `${v.name}: ${wie}`;
}

/** Wie sicher ein Vorschlag ist, in Worten. */
export function sicherheitText(sicherheit) {
  return sicherheit === "hoch" ? "Sehr wahrscheinlich dieselbe Firma" : "Vermutlich dieselbe Firma — bitte prüfen";
}

/** Die Fehlermeldung einer Antwort: die Antwort nennt `error` oder `text`. */
export function fehlerText(antwort, vorgabe = "Das hat nicht geklappt.") {
  return antwort?.error || antwort?.text || vorgabe;
}

/** Darf der Knopf „Als Firma anlegen“ erscheinen? Nur, wenn es etwas zu ordnen gibt und noch kein Eintrag besteht. */
export function kannAnlegen(ansicht) {
  return Boolean(ansicht && ansicht.status === "ok" && !ansicht.stammsatz && !(ansicht.mehrdeutig || []).length && ansicht.name);
}
