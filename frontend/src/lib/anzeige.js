/**
 * Anzeigenamen statt Rohwerte — G65 (#1087 D2).
 *
 * Gespeichert wird ein Schluessel, gezeigt ein Wort. Das Gegenstueck auf
 * dem Server ist `services/anzeigenamen.py`; ein Test haelt beide
 * Tabellen gleich. Status laufen ueber `statusLabel()` in utils.js.
 */

export const GRUND_TEXT = {
  zu_weit_entfernt: "Zu weit entfernt",
  gehalt_zu_niedrig: "Gehalt zu niedrig",
  falsches_fachgebiet: "Falsches Fachgebiet",
  falsche_branche: "Falsche Branche",
  falsches_system: "Falsches System",
  zu_junior: "Zu junior",
  zu_senior: "Zu senior",
  unpassendes_arbeitsmodell: "Unpassendes Arbeitsmodell",
  firma_uninteressant: "Firma uninteressant",
  zeitarbeit: "Zeitarbeit",
  befristet: "Befristet",
  bereits_beworben: "Bereits beworben",
  duplikat: "Duplikat",
  kein_hochschulabschluss: "Kein Hochschulabschluss",
  sonstiges: "Sonstiges",
};

export const BEWERBUNGSART_TEXT = {
  mit_dokumenten: "mit Unterlagen",
  elektronisch: "per E-Mail",
  ueber_portal: "über ein Portal",
};

function schluessel(wert) {
  return String(wert ?? "").trim().toLowerCase().replace(/[\s_]+/g, "_");
}

/**
 * Ein Ablehnungsgrund als Wort. `katalog` sind die Beschriftungen aus den
 * Einstellungen — ein eigener Grund steht dort so, wie der Mensch ihn
 * geschrieben hat, gespeichert ist er klein.
 */
export function grundText(wert, katalog = []) {
  const roh = String(wert ?? "").trim();
  const key = schluessel(roh);
  if (GRUND_TEXT[key]) return GRUND_TEXT[key];
  for (const eintrag of katalog || []) {
    const label = typeof eintrag === "string" ? eintrag : eintrag?.label;
    if (label && schluessel(label) === key && label !== label.toLowerCase()) return label;
  }
  const text = roh.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function bewerbungsartText(wert) {
  const roh = String(wert ?? "").trim();
  return BEWERBUNGSART_TEXT[schluessel(roh)] || roh.replace(/_/g, " ");
}

// Die Namen der Quellen, wie die Registry (`job_scraper.SOURCE_REGISTRY`)
// sie fuehrt. Ein Test haelt beide gleich — eine neue Quelle ohne Eintrag
// hier faellt dort auf.
export const QUELLE_TEXT = {
  bundesagentur: "Bundesagentur für Arbeit",
  hays: "Hays",
  freelance_de: "freelance.de",
  ingenieur_de: "ingenieur.de (VDI)",
  heise_jobs: "Heise Jobs",
  gulp: "GULP",
  solcom: "SOLCOM",
  stellenanzeigen_de: "Stellenanzeigen.de",
  adzuna: "Adzuna",
  jobware: "Jobware",
  ferchau: "FERCHAU",
  kimeta: "Kimeta",
  jobspy_linkedin: "LinkedIn (via JobSpy)",
  jobspy_indeed: "Indeed.de (via JobSpy)",
  jobspy_glassdoor: "Glassdoor (via JobSpy)",
  arbeitnow: "Arbeitnow",
  personio: "Personio (DACH-Mittelstand)",
  workable: "Workable (Public Postings)",
  meinestadt: "meinestadt.de (Regional)",
  himalayas: "Himalayas (Remote)",
  remotive: "Remotive (Remote)",
  remoteok: "RemoteOK",
  praktikum_de: "Praktikum.de",
  studentjob: "StudentJob.de",
  berufsstart: "Berufsstart.de",
  workday_dax: "Workday-DAX-Cluster",
  greenhouse: "Greenhouse Boards",
  jobspy_google: "Google Jobs (via JobSpy)",
  stepstone: "StepStone",
  freelancermap: "Freelancermap",
  indeed: "Indeed",
  linkedin: "LinkedIn",
  xing: "XING",
  google_jobs: "Google Jobs (im Browser)",
  manuell: "Von Hand",
  manual: "Von Hand",
  import: "Import",
};

/** Eine Quelle als Name: Server-Label, Registry-Name, sonst lesbar. */
export function quelleText(eintrag) {
  if (eintrag && typeof eintrag === "object") {
    return eintrag.label || quelleText(eintrag.name);
  }
  const roh = String(eintrag ?? "").trim();
  if (QUELLE_TEXT[roh]) return QUELLE_TEXT[roh];
  if (roh.startsWith("plugin:")) return `Plugin ${roh.slice(7)}`;
  if (roh.startsWith("newsletter:")) return `Newsletter ${roh.slice(11)}`;
  return roh.replace(/_/g, " ") || "unbekannt";
}

// Kleine Aufzaehlungen ohne eigene Tabelle (Kostenart, Aufgabenstand,
// Verbindungszustand): der Schluessel lesbar, bekannte Werte als Wort.
const KLARTEXT = {
  offen: "offen",
  erledigt: "erledigt",
  hinfaellig: "hinfällig",
  connected: "verbunden",
  disconnected: "nicht verbunden",
  unknown: "unbekannt",
  remote: "Remote",
  hybrid: "Hybrid",
  vor_ort: "Vor Ort",
};

export function klartext(wert) {
  const roh = String(wert ?? "").trim();
  return KLARTEXT[roh] || roh.replace(/_/g, " ");
}

/** ISO-Datum als TT.MM.JJJJ, alles andere unveraendert. */
export function datumText(wert) {
  const m = String(wert ?? "").slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(wert ?? "");
}

// G66 (#1087 E2): Kontaktrollen deutsch. Gespeichert bleibt der
// Schluessel (`hiring_manager`, `interviewer`, `hr`) — er ist der Alias,
// die Beschriftung ist neu. Kontakte- und Bewerbungen-Tab lesen diese
// eine Liste; vorher hatte jeder seine eigene.
export const KONTAKTROLLEN = [
  { value: "recruiter", label: "Recruiter" },
  { value: "headhunter", label: "Headhunter" },
  { value: "hiring_manager", label: "Fachvorgesetzte/r" },
  { value: "interviewer", label: "Gesprächspartner/in" },
  { value: "hr", label: "Personalabteilung" },
  { value: "kollege", label: "Kollege/Kollegin" },
  { value: "mentor", label: "Mentor/in" },
  { value: "sonstiges", label: "Sonstiges" },
];

export function kontaktrolleText(wert) {
  const roh = String(wert ?? "").trim();
  return KONTAKTROLLEN.find((r) => r.value === roh)?.label || roh.replace(/_/g, " ");
}
