export const PAGE_IDS = [
  "dashboard",
  "profil",
  "stellen",
  "bewerbungen",
  "kalender",
  "statistiken",
  "einstellungen",
];

export const STATUS_OPTIONS = [
  { value: "in_vorbereitung", label: "In Vorbereitung" },
  { value: "entwurf", label: "Entwurf" },
  { value: "beworben", label: "Beworben" },
  { value: "eingangsbestaetigung", label: "Eingangsbestätigung" },
  { value: "interview", label: "Interview" },
  { value: "zweitgespraech", label: "Zweitgespräch" },
  { value: "interview_abgeschlossen", label: "Interview abgeschlossen" },
  { value: "warte_auf_rueckmeldung", label: "Warte auf Rückmeldung" },
  { value: "angebot", label: "Angebot" },
  { value: "angenommen", label: "Angenommen" },
  { value: "abgelehnt", label: "Abgelehnt" },
  { value: "zurueckgezogen", label: "Zurückgezogen" },
  { value: "abgelaufen", label: "Abgelaufen" },
];

export function cn(...parts) {
  return parts.filter(Boolean).join(" ");
}

export function parsePageFromHash() {
  const raw = window.location.hash.replace(/^#/, "").trim();
  const page = raw || "dashboard";
  return PAGE_IDS.includes(page) ? page : "dashboard";
}

export function formatDate(value) {
  if (!value) return "Keine Angabe";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) return "Keine Angabe";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatCurrency(value, suffix = "EUR") {
  if (value === null || value === undefined || value === "") return "Keine Angabe";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return new Intl.NumberFormat("de-DE", {
    maximumFractionDigits: 0,
  }).format(number) + ` ${suffix}`;
}

export function splitKeywords(rawText) {
  return (rawText || "")
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function joinKeywords(items) {
  return (items || []).join("\n");
}

export function statusTone(status) {
  switch (status) {
    case "in_vorbereitung":
      return "violet";
    case "angebot":
    case "angenommen":
      return "success";
    case "zweitgespraech":
      return "success";
    case "interview_abgeschlossen":
      return "teal";
    case "interview":
    case "eingangsbestaetigung":
      return "sky";
    case "warte_auf_rueckmeldung":
      return "amber";
    case "abgelehnt":
    case "zurueckgezogen":
      return "danger";
    case "abgelaufen":
      return "neutral";
    case "beworben":
      return "amber";
    case "bearbeitet":
      return "neutral";
    default:
      return "neutral";
  }
}

export function priorityTone(priority) {
  switch (priority) {
    case "hoch":
      return "danger";
    case "mittel":
      return "amber";
    default:
      return "sky";
  }
}

export function readinessTone(tone) {
  switch (tone) {
    case "green":
      return "success";
    case "yellow":
      return "amber";
    case "red":
      return "danger";
    default:
      return "sky";
  }
}

export function docTypeLabel(docType) {
  const labels = {
    lebenslauf: "Lebenslauf",
    lebenslauf_vorlage: "Lebenslauf (Vorlage)",
    anschreiben: "Anschreiben",
    anschreiben_vorlage: "Anschreiben (Vorlage)",
    zeugnis: "Zeugnis",
    zertifikat: "Zertifikat",
    sonstiges: "Sonstiges",
  };
  return labels[docType] || docType || "Unbekannt";
}

export function isTemplateDoc(doc) {
  const type = doc?.doc_type || "";
  return type.endsWith("_vorlage");
}

export function statusLabel(status) {
  const found = STATUS_OPTIONS.find((opt) => opt.value === status);
  if (found) return found.label;
  // Also handle eingangsbestaetigung which is not in STATUS_OPTIONS
  const extra = {
    eingangsbestaetigung: "Eingangsbestätigung",
    notiz: "Notiz",
    bearbeitet: "Bearbeitet",
  };
  return extra[status] || status || "Unbekannt";
}

export function normalizeMonthDate(value) {
  if (!value) return "";
  const str = String(value).trim();
  // Already YYYY-MM format
  if (/^\d{4}-\d{2}$/.test(str)) return str;
  // YYYY-MM-DD → YYYY-MM
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) return str.slice(0, 7);
  // MM/YYYY → YYYY-MM
  const slashMatch = str.match(/^(\d{1,2})\/(\d{4})$/);
  if (slashMatch) return `${slashMatch[2]}-${slashMatch[1].padStart(2, "0")}`;
  // DD.MM.YYYY → YYYY-MM
  const dotMatch = str.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (dotMatch) return `${dotMatch[3]}-${dotMatch[2].padStart(2, "0")}`;
  // Just a year like "2016"
  if (/^\d{4}$/.test(str)) return `${str}-01`;
  return str;
}

export function employmentTypeLabel(type) {
  const labels = {
    festanstellung: "Festanstellung",
    freelance: "Freelance",
    teilzeit: "Teilzeit",
    vollzeit: "Vollzeit",
    praktikant: "Praktikum",
  };
  return labels[type] || type || "Keine Angabe";
}

export async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text);
}

export function resolveLegacyAction(actionTarget = "") {
  if (!actionTarget) return null;
  if (actionTarget.includes("showPage('profil')")) {
    if (actionTarget.includes("showPositionForm")) return { page: "profil", composer: "position" };
    if (actionTarget.includes("showSkillForm")) return { page: "profil", composer: "skill" };
    if (actionTarget.includes("showEducationForm")) return { page: "profil", composer: "education" };
    return { page: "profil" };
  }
  if (actionTarget.includes("showPage('bewerbungen')")) return { page: "bewerbungen" };
  if (actionTarget.includes("showPage('stellen')")) return { page: "stellen" };
  if (actionTarget.includes("showPage('einstellungen')")) return { page: "einstellungen" };
  if (actionTarget.includes("wizardDocUpload")) return { page: "profil", composer: "document" };
  return null;
}

export function dueState(isoDate) {
  if (!isoDate) return false;
  return isoDate <= new Date().toISOString().slice(0, 10);
}

export function textExcerpt(value, max = 180) {
  const clean = (value || "").replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max).trim()}...`;
}

function canonicalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[.,;:!?]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const SKILL_HEADER_PHRASES = new Set([
  "kompetenzen",
  "und kompetenzen",
  "kenntnisse und kompetenzen",
  "fahigkeiten und kompetenzen",
  "personliche fahigkeiten und kompetenzen",
  "skills",
]);

export function sanitizeSkillName(value) {
  const cleaned = String(value || "").replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  if (SKILL_HEADER_PHRASES.has(canonicalizeText(cleaned))) return "";
  return cleaned;
}

export function getKnownProfileFacts(profile) {
  if (!profile) return [];

  const facts = [];
  const positions = profile.positions || [];
  const education = profile.education || [];
  const documents = profile.documents || [];
  const activePosition = positions.find((item) => item.is_current) || positions[0];
  const location = [profile.city, profile.country].filter(Boolean).join(", ");
  const analyzedDocumentCount = documents.filter(
    (item) => item.extraction_status && item.extraction_status !== "nicht_extrahiert"
  ).length;

  if (profile.name) facts.push(`Name: ${profile.name}`);
  if (profile.email) facts.push(`E-Mail: ${profile.email}`);
  if (profile.phone) facts.push(`Telefon: ${profile.phone}`);
  if (location) facts.push(`Standort: ${location}`);
  if (profile.summary) facts.push("Ein Kurzprofil ist bereits vorhanden.");
  if (activePosition?.title || activePosition?.company) {
    facts.push(
      `Beruflicher Fokus: ${activePosition.title || "Rolle"}${activePosition.company ? ` bei ${activePosition.company}` : ""}.`
    );
  }
  if (positions.length) facts.push(`${positions.length} berufliche Station(en) sind bereits hinterlegt.`);
  if (education.length) facts.push(`${education.length} Ausbildungsstation(en) sind vorhanden.`);
  if (documents.length) facts.push(`${documents.length} Dokument(e) liegen bereits im Profil.`);
  if (analyzedDocumentCount > 0) {
    facts.push(
      analyzedDocumentCount === 1
        ? "1 Dokument wurde bereits automatisiert ausgewertet."
        : `${analyzedDocumentCount} Dokument(e) wurden bereits automatisiert ausgewertet.`
    );
  }
  if (profile.suggested_job_titles?.length) {
    facts.push(
      `Vorgeschlagene Jobtitel: ${profile.suggested_job_titles.slice(0, 3).map((item) => item.title).join(", ")}.`
    );
  }

  return facts;
}

export function firstIncompleteStepIndex(steps) {
  const index = (steps || []).findIndex((step) => !step.done);
  return index === -1 ? Math.max((steps || []).length - 1, 0) : index;
}

