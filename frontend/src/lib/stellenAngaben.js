// #1044: eine Stelle sieht auf der Karte und im Popup gleich aus.
//
// Das Popup "Stellendetails" war eigener Code und las die Rohwerte:
// "festanstellung" klein und grau statt "Festanstellung" in Blau, kein
// Umfang, keine Entfernung, "Unbekannt" statt "Unbekannte Firma" und ein
// Gehalt mit Bindestrich, "(jaehrlich)" und "(geschaetzt)". Die Daten waren
// dieselben — nur die Darstellung stand zweimal im Code. Hier steht sie
// einmal, und beide Ansichten lesen sie.
//
// Framework-frei, damit `node stellenAngaben.test.mjs` sie ohne Build prueft.

export const ANSTELLUNGSFORM_TEXT = {
  festanstellung: "Festanstellung",
  zeitarbeit: "Zeitarbeit",
  freelance: "Freelance",
  praktikum: "Praktikum",
  werkstudent: "Werkstudent",
  ausbildung: "Ausbildung",
};

// #1301: EINE Farbtabelle fuer die Anstellungsform. Abzeichen, Stellenkarte,
// Popup und Bewerbungskarte lesen sie; das MCP-Werkzeug `stellen_anzeigen`
// liest das Gegenstueck `ANSTELLUNGSFORM_FARBE` in services/stellenart.py,
// und tests/test_v183_anstellungsform_farben_1301.py haelt beide
// deckungsgleich. Vorgabe aus #111/#435: Freelance gruen, Festanstellung
// blau, unbekannt grau. Die uebrigen Formen haben je einen ruhigen eigenen
// Ton — nicht amber (das ist "Angepinnt") und nicht rot (das ist eine
// Warnung, Zeitarbeit ist keine).
export const ANSTELLUNGSFORM_TON = {
  festanstellung: "sky",
  freelance: "success",
  zeitarbeit: "violett",
  praktikum: "mandarine",
  werkstudent: "gelb",
  ausbildung: "braun",
};

/** Unbekannt ist ein eigener Zustand (Lehre 2) — grau, nie wie Festanstellung. */
export const ANSTELLUNGSFORM_TON_UNBEKANNT = "neutral";

// Der dezente Rand und Hauch der Karte je Ton. Die Klassen stehen hier
// ausgeschrieben, damit Tailwind sie findet.
export const KARTE_TON = {
  sky: "border-sky/25 bg-sky/[0.03]",
  success: "border-teal/25 bg-teal/[0.03]",
  violett: "border-violett/25 bg-violett/[0.03]",
  mandarine: "border-mandarine/25 bg-mandarine/[0.03]",
  gelb: "border-gelb/25 bg-gelb/[0.03]",
  braun: "border-braun/25 bg-braun/[0.03]",
  neutral: "",
};

export const UMFANG_TEXT = {
  vollzeit: "Vollzeit",
  teilzeit: "Teilzeit",
  // "Vollzeit / Teilzeit" ist eine ZUSAGE, keine Mehrdeutigkeit — ein
  // Etikett mit nur zwei Werten macht daraus eine Falschangabe.
  beides: "Voll- oder Teilzeit",
};

// #1299: die Auswahl im Bearbeiten-Dialog der Stelle. Die Werte sind die,
// die der Server annimmt (services/stelle_aendern.py), die Texte sichtbar.
export const REMOTE_STUFE_TEXT = {
  remote: "Remote",
  hybrid: "Hybrid",
  vor_ort: "Vor Ort",
  unbekannt: "Unbekannt",
};

export const UMFANG_AUSWAHL_TEXT = { ...UMFANG_TEXT, unbekannt: "Unbekannt" };

/** Die Merkmale, die der Dialog bearbeitet. */
export const MERKMAL_FELDER = ["employment_type", "arbeitsumfang", "remote_level"];

/**
 * Was der Bearbeiten-Dialog speichert (#1299): alle Textfelder, aber ein
 * Merkmal nur, wenn der Mensch es GEAENDERT hat. Ein unveraendert
 * mitgeschicktes Merkmal hiesse fuer den Server "von Hand bestaetigt" —
 * und danach ueberschriebe es kein Suchlauf mehr, obwohl niemand es
 * angefasst hat.
 */
export function stelleSpeichernNutzlast(job, form) {
  const nutzlast = {};
  for (const [feld, wert] of Object.entries(form || {})) {
    if (MERKMAL_FELDER.includes(feld)) {
      const bisher = String(job?.[feld] || (feld === "employment_type" ? "" : "unbekannt"));
      if (String(wert || "") && String(wert) !== bisher) nutzlast[feld] = wert;
    } else {
      nutzlast[feld] = wert;
    }
  }
  return nutzlast;
}

/** Der Arbeitgeber zur Anzeige; ohne Angabe ein benannter Platzhalter. */
export function firmaText(job) {
  const firma = String(job?.company || "").trim();
  return firma || "Unbekannte Firma";
}

/** Anstellungsform als {text, ton} — oder null, wenn keine vorliegt. */
export function anstellungsform(job) {
  const art = String(job?.employment_type || "").trim();
  if (!art) return null;
  return {
    text: ANSTELLUNGSFORM_TEXT[art] || art,
    ton: ANSTELLUNGSFORM_TON[art] || ANSTELLUNGSFORM_TON_UNBEKANNT,
  };
}

/**
 * #1301: das Abzeichen der Anstellungsform fuer JEDE Karte — auch ohne
 * Angabe. `art` ist der Rohwert (Stelle: `employment_type`, Bewerbung:
 * `job_employment_type`). Die Farbe steht nie allein: das Abzeichen
 * nennt die Form beim Namen, `titel` erklaert die Farbe am Kartenrand.
 */
export function anstellungsformMarke(art) {
  const wert = String(art || "").trim();
  const bekannt = Object.prototype.hasOwnProperty.call(ANSTELLUNGSFORM_TON, wert);
  const ton = bekannt ? ANSTELLUNGSFORM_TON[wert] : ANSTELLUNGSFORM_TON_UNBEKANNT;
  const text = wert ? (ANSTELLUNGSFORM_TEXT[wert] || wert) : "Form unbekannt";
  const titel = wert
    ? `Anstellungsform: ${text}. Die Farbe des Kartenrands steht für die Anstellungsform.`
    : "Die Anzeige nennt keine Anstellungsform. Grau heißt: unbekannt, nicht Festanstellung. Eintragen kannst du sie in den Details.";
  return { wert, text, ton, karte: KARTE_TON[ton] || "", titel };
}

// #1326: der Filter "Stellenart" auf der Bewerbungsseite. Er kannte nur
// Festanstellung und Freelance, und "Freelance" hiess "alles ausser
// Festanstellung" (Zeitarbeit, Praktikum ... landeten dort), "Festanstellung"
// schloss die Bewerbungen ohne Angabe ein. Jetzt dieselbe Liste wie die
// Kartenfarben; "Form unbekannt" ist ein eigener Eintrag (Lehre 2) und
// umfasst genau das, was die Karte grau zeigt: keine oder eine fremde Angabe.
export const STELLENART_FILTER_UNBEKANNT = "unbekannt";

export const STELLENART_FILTER_OPTIONEN = [
  ...Object.entries(ANSTELLUNGSFORM_TEXT).map(([wert, text]) => ({ wert, text })),
  { wert: STELLENART_FILTER_UNBEKANNT, text: "Form unbekannt" },
];

/** Passt die Anstellungsform `art` zum Filterwert? Leerer Filter = alle. */
export function passtZurStellenart(art, filter) {
  if (!filter) return true;
  const wert = String(art || "").trim();
  const bekannt = Object.prototype.hasOwnProperty.call(ANSTELLUNGSFORM_TEXT, wert);
  if (filter === STELLENART_FILTER_UNBEKANNT) return !bekannt;
  return bekannt && wert === filter;
}

/**
 * Der Arbeitsumfang als Text — oder null. `unbekannt` bekommt bewusst
 * kein Etikett (#1023): an den meisten Stellen fehlt die Angabe, und ein
 * "unbekannt" ueberall waere Rauschen.
 */
export function umfangText(job) {
  const umfang = String(job?.arbeitsumfang || "").trim();
  if (!umfang || umfang === "unbekannt") return null;
  return UMFANG_TEXT[umfang] || umfang;
}

/**
 * Das Gehalt als ein Satz — oder null ohne Untergrenze.
 * Den Waehrungsformatierer reicht der Aufrufer herein, damit dieses Modul
 * ohne Build und ohne Pfad-Alias pruefbar bleibt.
 */
export function gehaltText(job, formatiere) {
  if (!job?.salary_min) return null;
  const f = typeof formatiere === "function" ? formatiere : (wert) => String(wert);
  const bis = job.salary_max ? ` bis ${f(job.salary_max)}` : "";
  const geschaetzt = job.salary_estimated ? " (geschätzt)" : "";
  return `Gehalt: ${f(job.salary_min)}${bis}${geschaetzt}`;
}

/** Die Entfernung, wie der Server sie beschriftet — oder null. */
export function entfernungText(job) {
  return job?.entfernung?.entfernung_text || null;
}
