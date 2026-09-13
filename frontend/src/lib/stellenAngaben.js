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

export const ANSTELLUNGSFORM_TON = {
  festanstellung: "sky",
  freelance: "success",
  praktikum: "amber",
  werkstudent: "amber",
  ausbildung: "amber",
  zeitarbeit: "danger",
};

export const UMFANG_TEXT = {
  vollzeit: "Vollzeit",
  teilzeit: "Teilzeit",
  // "Vollzeit / Teilzeit" ist eine ZUSAGE, keine Mehrdeutigkeit — ein
  // Etikett mit nur zwei Werten macht daraus eine Falschangabe.
  beides: "Voll- oder Teilzeit",
};

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
    ton: ANSTELLUNGSFORM_TON[art] || "neutral",
  };
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
