// #1345 (G117): eine Stelle fuer alles, was die Diagramme der Statistik-Seite
// teilen: Farben je Farbschema, die Faltung der Status in Phasen, Zahlen in
// deutscher Schreibweise und die Rangliste (statt Kreisdiagramm).
//
// Die Farben sind gegen die Flaechen der beiden Farbschemata geprueft
// (Abstand fuer Farbfehlsichtige, Mindestabstand bei normalem Sehen). Im
// hellen Schema liegen drei Toene unter 3:1 gegen die Flaeche: dort ist eine
// sichtbare Beschriftung oder Legende Pflicht, Farbe allein traegt nichts.
// Wer einen Wert aendert, prueft die Reihe neu; ein Farbton wird nie
// "durchgezaehlt" (keine Farbe je Balken-Index).

export const FARBEN = {
  light: {
    flaeche: "#ffffff",
    text: "#647088",
    raster: "#e6e9f0",
    eine: "#2a78d6",
    paar: ["#2a78d6", "#1baf7a"],
    neutral: "#9aa1b0",
    phasen: {
      vorbereitung: "#e87ba4",
      beworben: "#2a78d6",
      gespraech: "#eda100",
      angebot: "#1baf7a",
      absage: "#eb6834",
      ohne_ergebnis: "#9aa1b0",
      sonstige: "#008300",
    },
  },
  dark: {
    flaeche: "#1c202e",
    text: "#8c98b2",
    raster: "#2b3042",
    eine: "#3987e5",
    paar: ["#3987e5", "#199e70"],
    neutral: "#7d8598",
    phasen: {
      vorbereitung: "#d55181",
      beworben: "#3987e5",
      gespraech: "#c98500",
      angebot: "#199e70",
      absage: "#d95926",
      ohne_ergebnis: "#7d8598",
      sonstige: "#008300",
    },
  },
};

export function farben(schema) {
  return FARBEN[schema === "light" ? "light" : "dark"];
}

// Reihenfolge = Stapelreihenfolge im Diagramm (unten nach oben) und in der
// Legende. Die Farbe haengt an der Phase, nie an ihrer Position.
export const PHASEN = [
  { key: "vorbereitung", label: "In Vorbereitung" },
  { key: "beworben", label: "Beworben" },
  { key: "gespraech", label: "Im Gespräch" },
  { key: "angebot", label: "Angebot" },
  { key: "absage", label: "Absage" },
  { key: "ohne_ergebnis", label: "Ohne Ergebnis" },
  { key: "sonstige", label: "Sonstige" },
];

const STATUS_PHASE = {
  in_vorbereitung: "vorbereitung",
  entwurf: "vorbereitung",
  beworben: "beworben",
  eingangsbestaetigung: "beworben",
  interview: "gespraech",
  zweitgespraech: "gespraech",
  interview_abgeschlossen: "gespraech",
  angebot: "angebot",
  angenommen: "angebot",
  abgelehnt: "absage",
  zurueckgezogen: "ohne_ergebnis",
  abgelaufen: "ohne_ergebnis",
  arbeitgeber_ausgefallen: "ohne_ergebnis",
};

// Ein unbekannter Status faellt nie still in eine bekannte Phase.
export function phaseVon(status) {
  return STATUS_PHASE[status] || "sonstige";
}

// {status: anzahl} -> {phase: anzahl}; nur Phasen mit Wert > 0.
export function phasenSumme(nachStatus) {
  const summe = {};
  for (const [status, anzahl] of Object.entries(nachStatus || {})) {
    const n = Number(anzahl) || 0;
    if (n <= 0) continue;
    const phase = phaseVon(status);
    summe[phase] = (summe[phase] || 0) + n;
  }
  return summe;
}

// Die Phasen, die in mindestens einem Zeitraum vorkommen, in fester Reihenfolge.
export function phasenImVerlauf(zeitraeume) {
  const da = new Set();
  for (const nachStatus of zeitraeume || []) {
    for (const key of Object.keys(phasenSumme(nachStatus))) da.add(key);
  }
  return PHASEN.filter((p) => da.has(p.key));
}

const GANZ = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const EINE_STELLE = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });

export function zahl(wert) {
  const n = Number(wert);
  if (wert == null || wert === "" || !Number.isFinite(n)) return "–";
  return (Number.isInteger(n) ? GANZ : EINE_STELLE).format(n);
}

// 12.5 -> "12,5 %" (geschuetztes Leerzeichen); fehlender Wert bleibt ein Strich.
export function prozent(wert) {
  const n = Number(wert);
  if (wert == null || wert === "" || !Number.isFinite(n)) return "–";
  return `${EINE_STELLE.format(n)} %`;
}

// Rangliste fuer Balken: absteigend, hoechstens `max` Zeilen; der Rest wird
// zu einer Zeile "Sonstige" (immer zuletzt, mit der Zahl der gefalteten
// Eintraege). `anteil` ist der Anteil an der Summe in Prozent, `breite` die
// Balkenlaenge relativ zum groessten Wert (0..100).
export function rangliste(eintraege, { max = 8 } = {}) {
  const sauber = (eintraege || [])
    .map((e) => ({ ...e, name: String(e.name ?? ""), wert: Number(e.wert) || 0 }))
    .filter((e) => e.wert > 0);
  // Stabil: gleiche Werte behalten die gelieferte Reihenfolge.
  const sortiert = sauber
    .map((e, i) => [e, i])
    .sort((a, b) => b[0].wert - a[0].wert || a[1] - b[1])
    .map(([e]) => e);
  const summe = sortiert.reduce((s, e) => s + e.wert, 0);
  let zeilen = sortiert;
  if (sortiert.length > max) {
    const kopf = sortiert.slice(0, max - 1);
    const rest = sortiert.slice(max - 1);
    zeilen = [
      ...kopf,
      {
        name: "Sonstige",
        wert: rest.reduce((s, e) => s + e.wert, 0),
        gefaltet: rest.length,
      },
    ];
  }
  const groesster = zeilen.reduce((m, e) => Math.max(m, e.wert), 0);
  return zeilen.map((e) => ({
    ...e,
    anteil: summe ? (e.wert / summe) * 100 : 0,
    breite: groesster ? (e.wert / groesster) * 100 : 0,
  }));
}
