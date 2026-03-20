import {
  Ban,
  BriefcaseBusiness,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Download,
  GraduationCap,
  Pencil,
  Plus,
  RefreshCcw,
  Sparkles,
  Trash2,
  Upload,
  Wrench,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, apiUrl, deleteRequest, optionalApi, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { analyzeUploadedDocuments, createFileSignature, uploadDocumentFile } from "@/document-upload";
import { extractDroppedFiles } from "@/file-drop";
import {
  Badge,
  Button,
  Card,
  CheckboxInput,
  EmptyState,
  Field,
  LoadingPanel,
  MetricCard,
  Modal,
  PageHeader,
  SectionHeading,
  SelectInput,
  TagInput,
  TextArea,
  TextInput,
} from "@/components/ui";
import { cn, docTypeLabel, formatDateTime, normalizeMonthDate } from "@/utils";

const EMPTY_PROFILE = {
  name: "",
  email: "",
  phone: "",
  address: "",
  city: "",
  plz: "",
  country: "Deutschland",
  birthday: "",
  nationality: "",
  summary: "",
  informal_notes: "",
  preferences: { stellentyp: "", min_gehalt: "", ziel_gehalt: "", min_tagessatz: "", min_stundensatz: "", max_entfernung_km: "" },
};

const EMPTY_POSITION = {
  id: "",
  company: "",
  title: "",
  location: "",
  start_date: "",
  end_date: "",
  is_current: false,
  employment_type: "festanstellung",
  industry: "",
  description: "",
  tasks: "",
  achievements: "",
  technologies: "",
};

const EMPTY_PROJECT = {
  name: "",
  role: "",
  duration: "",
  technologies: "",
  description: "",
  situation: "",
  task: "",
  action: "",
  result: "",
};

const EMPTY_EDUCATION = {
  id: "",
  institution: "",
  degree: "",
  field_of_study: "",
  start_date: "",
  end_date: "",
};

const EMPTY_SKILL = {
  id: "",
  name: "",
  category: "fachlich",
  level: 3,
  years_experience: "",
  since_year: "",
};

const SKILL_CATEGORY_LABELS = {
  fachlich: "Fachlich",
  tool: "Tools",
  methodisch: "Methodisch",
  soft_skill: "Soft Skills",
  sprache: "Sprachen",
};

const SKILL_CATEGORY_NORMALIZE = {
  fachlich: "fachlich",
  fachkenntnisse: "fachlich",
  technisch: "fachlich",
  "ki/ml": "fachlich",
  tool: "tool",
  tools: "tool",
  methodisch: "methodisch",
  soft_skill: "soft_skill",
  "soft skills": "soft_skill",
  "soft skill": "soft_skill",
  sprache: "sprache",
  sprachen: "sprache",
};

function normalizeSkillCategory(raw) {
  if (!raw) return "fachlich";
  const key = String(raw).trim().toLowerCase();
  return SKILL_CATEGORY_NORMALIZE[key] || "fachlich";
}

const EMPLOYMENT_TYPE_LABELS = {
  festanstellung: "Festanstellung",
  freelance: "Freelance",
  teilzeit: "Teilzeit",
  praktikum: "Praktikum",
};

function formatPositionPeriod(position) {
  const start = position?.start_date || "";
  const end = position?.is_current ? "heute" : position?.end_date || "";
  return [position?.location, start, end].filter(Boolean).join(" - ");
}

function toDraft(profile) {
  return profile
    ? { ...EMPTY_PROFILE, ...profile, preferences: { ...EMPTY_PROFILE.preferences, ...(profile.preferences || {}) } }
    : EMPTY_PROFILE;
}

function normalizeProfile(draft) {
  const preferences = { ...(draft.preferences || {}) };
  ["min_gehalt", "ziel_gehalt", "min_tagessatz", "min_stundensatz", "max_entfernung_km"].forEach((key) => {
    if (preferences[key] === "" || preferences[key] === null || typeof preferences[key] === "undefined") {
      preferences[key] = null;
      return;
    }
    const numeric = Number(preferences[key]);
    preferences[key] = Number.isFinite(numeric) ? numeric : null;
  });
  return { ...draft, preferences };
}

function criteriaToDraft(criteria) {
  return {
    keywords_muss: [...(criteria?.keywords_muss || [])],
    keywords_plus: [...(criteria?.keywords_plus || [])],
    keywords_ausschluss: [...(criteria?.keywords_ausschluss || [])],
    regionen: [...(criteria?.regionen || [])],
    min_gehalt: criteria?.min_gehalt ?? "",
    min_tagessatz: criteria?.min_tagessatz ?? "",
    min_stundensatz: criteria?.min_stundensatz ?? "",
    max_entfernung_km: criteria?.max_entfernung_km ?? "",
    stellentyp: criteria?.stellentyp || "",
    gewichtung_muss: criteria?.gewichtung?.muss ?? 2,
    gewichtung_plus: criteria?.gewichtung?.plus ?? 1,
    gewichtung_remote: criteria?.gewichtung?.remote ?? 2,
    gewichtung_naehe: criteria?.gewichtung?.naehe ?? 2,
    gewichtung_fern_malus: criteria?.gewichtung?.fern_malus ?? 3,
    gewichtung_gehalt: criteria?.gewichtung?.gehalt ?? 1,
  };
}

function criteriaDraftToPayload(criteriaDraft) {
  return {
    keywords_muss: criteriaDraft.keywords_muss,
    keywords_plus: criteriaDraft.keywords_plus,
    keywords_ausschluss: criteriaDraft.keywords_ausschluss,
    regionen: criteriaDraft.regionen,
    min_gehalt: criteriaDraft.min_gehalt === "" ? null : Number(criteriaDraft.min_gehalt),
    min_tagessatz: criteriaDraft.min_tagessatz === "" ? null : Number(criteriaDraft.min_tagessatz),
    min_stundensatz: criteriaDraft.min_stundensatz === "" ? null : Number(criteriaDraft.min_stundensatz),
    max_entfernung_km: criteriaDraft.max_entfernung_km === "" ? null : Number(criteriaDraft.max_entfernung_km),
    stellentyp: criteriaDraft.stellentyp,
    gewichtung: {
      muss: Number(criteriaDraft.gewichtung_muss),
      plus: Number(criteriaDraft.gewichtung_plus),
      remote: Number(criteriaDraft.gewichtung_remote),
      naehe: Number(criteriaDraft.gewichtung_naehe),
      fern_malus: Number(criteriaDraft.gewichtung_fern_malus),
      gehalt: Number(criteriaDraft.gewichtung_gehalt),
    },
  };
}

function parseOptionalInt(value) {
  if (value === "" || value === null || typeof value === "undefined") return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
}

function buildSkillDraft(skill) {
  const currentYear = new Date().getFullYear();
  const normalized = { ...EMPTY_SKILL, ...(skill || {}) };
  const yearsExperience = parseOptionalInt(normalized.years_experience);
  const existingSinceYear = parseOptionalInt(normalized.since_year);
  const derivedSinceYear =
    yearsExperience === null
      ? ""
      : Math.min(currentYear, Math.max(1900, currentYear - Math.max(0, yearsExperience)));
  return {
    ...normalized,
    category: normalizeSkillCategory(normalized.category),
    years_experience: yearsExperience === null ? "" : yearsExperience,
    since_year: existingSinceYear === null ? derivedSinceYear : existingSinceYear,
  };
}

function buildSkillPayload(skillDraft) {
  const currentYear = new Date().getFullYear();
  const level = parseOptionalInt(skillDraft.level);
  const manualYears = parseOptionalInt(skillDraft.years_experience);
  const sinceYear = parseOptionalInt(skillDraft.since_year);
  const boundedSinceYear =
    sinceYear === null ? null : Math.min(currentYear, Math.max(1900, sinceYear));
  const yearsExperience =
    boundedSinceYear === null ? manualYears : Math.max(0, currentYear - boundedSinceYear);
  return {
    name: (skillDraft.name || "").trim(),
    category: skillDraft.category || "fachlich",
    level: Math.min(5, Math.max(1, level ?? 3)),
    years_experience: yearsExperience,
  };
}

const EXTRACTION_STATUS_META = {
  ausstehend: { label: "Ausstehend", tone: "amber" },
  angewendet: { label: "Angewendet", tone: "success" },
  teilweise: { label: "Teilweise", tone: "sky" },
  verworfen: { label: "Verworfen", tone: "danger" },
  manuell_korrigiert: { label: "Manuell korrigiert", tone: "sky" },
};

const DOCUMENT_STATUS_META = {
  nicht_extrahiert: {
    label: "Nicht analysiert",
    tone: "amber",
    help: "Dokument wurde hochgeladen, aber noch nicht analysiert.",
  },
  basis_analysiert: {
    label: "Basis analysiert",
    tone: "sky",
    help: "Basisanalyse ist abgeschlossen. Eine erneute Analyse kann zusätzliche Profildaten übernehmen.",
  },
  angewendet: {
    label: "Angewendet",
    tone: "success",
    help: "Erkannte Inhalte wurden bereits in das Profil übernommen.",
  },
  teilweise: {
    label: "Teilweise",
    tone: "sky",
    help: "Nur ein Teil der extrahierten Inhalte wurde übernommen.",
  },
  verworfen: {
    label: "Verworfen",
    tone: "danger",
    help: "Das Analyseergebnis wurde verworfen und nicht übernommen.",
  },
  manuell_korrigiert: {
    label: "Manuell korrigiert",
    tone: "sky",
    help: "Analysewerte wurden manuell geprüft und korrigiert.",
  },
  analysiert_leer: {
    label: "Ohne Inhalt",
    tone: "neutral",
    help: "Kein verwertbarer Text erkannt (z. B. Bildscan ohne OCR-Text).",
  },
};

function getDocumentStatusMeta(status) {
  const normalized = String(status || "").trim().toLowerCase();
  if (!normalized) {
    return {
      label: "Ohne Status",
      tone: "neutral",
      help: "Für dieses Dokument liegt noch kein Analyse-Status vor.",
    };
  }
  const known = DOCUMENT_STATUS_META[normalized];
  if (known) return known;
  return {
    label: normalized.replaceAll("_", " "),
    tone: "neutral",
    help: "Status vom Backend geliefert. Details sind im Extraktions-Verlauf sichtbar.",
  };
}

function countExtractedFields(extractedFields) {
  if (!extractedFields || typeof extractedFields !== "object") return 0;
  return Object.values(extractedFields).filter((value) => {
    if (value === null || typeof value === "undefined") return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value).length > 0;
    if (typeof value === "string") return value.trim().length > 0;
    return true;
  }).length;
}

export default function ProfilePage() {
  const { chrome, intent, clearIntent, reloadKey, refreshChrome, pushToast, openCreateProfileModal } = useApp();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [draft, setDraft] = useState(EMPTY_PROFILE);
  const [criteriaDraft, setCriteriaDraft] = useState(criteriaToDraft({}));
  const [blacklist, setBlacklist] = useState([]);
  const [blacklistForm, setBlacklistForm] = useState({ type: "firma", value: "" });
  const [completeness, setCompleteness] = useState({ completeness: 0 });
  const [extractions, setExtractions] = useState([]);
  const [positionDialog, setPositionDialog] = useState({ open: false, draft: EMPTY_POSITION });
  const [projectDialog, setProjectDialog] = useState({ open: false, positionId: "", draft: EMPTY_PROJECT });
  const [educationDialog, setEducationDialog] = useState({ open: false, draft: EMPTY_EDUCATION });
  const [skillDialog, setSkillDialog] = useState({ open: false, draft: EMPTY_SKILL });
  const [expandedPositions, setExpandedPositions] = useState({});
  const [expandedExtractionId, setExpandedExtractionId] = useState("");
  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  const [uploadForm, setUploadForm] = useState({ doc_type: "sonstiges" });
  const [dragDocumentsActive, setDragDocumentsActive] = useState(false);
  const [extractionDialog, setExtractionDialog] = useState({
    open: false,
    loading: false,
    saving: false,
    document: null,
    extraction: null,
    draftText: "{}",
  });
  const importRef = useRef(null);
  const documentFileInputRef = useRef(null);
  const suppressProfileAutosaveRef = useRef(true);
  const lastSavedProfileSnapshotRef = useRef("");
  const suppressCriteriaAutosaveRef = useRef(true);
  const lastSavedCriteriaSnapshotRef = useRef("");
  const currentYear = new Date().getFullYear();
  const documentFolderInputRef = useRef(null);
  const profileElementCards = [
    { key: "experience", label: "Berufserfahrung", value: profile?.positions?.length || 0, note: "Positionen" },
    { key: "education", label: "Ausbildungen", value: profile?.education?.length || 0, note: "Ausbildungen erfasst" },
    { key: "skills", label: "Skills", value: profile?.skills?.length || 0, note: "Kompetenzen erfasst" },
    {
      key: "completeness",
      label: "Vollständigkeit des Profils",
      value: `${Math.round(Number(completeness?.completeness || 0))}%`,
      note: "Fortschritt",
    },
  ];

  const loadPage = useEffectEvent(async () => {
    try {
      const results = await Promise.allSettled([
        optionalApi("/api/profile"),
        api("/api/profile/completeness"),
        api("/api/extractions"),
        api("/api/search-criteria"),
        api("/api/blacklist"),
      ]);
      const profileData = results[0].status === "fulfilled" ? results[0].value : null;
      const completenessData = results[1].status === "fulfilled" ? results[1].value : null;
      const extractionData = results[2].status === "fulfilled" ? results[2].value : null;
      const searchCriteria = results[3].status === "fulfilled" ? results[3].value : {};
      const blacklistRows = results[4].status === "fulfilled" ? results[4].value : [];
      const nextDraft = toDraft(profileData);
      const nextCriteriaDraft = criteriaToDraft(searchCriteria || {});
      suppressProfileAutosaveRef.current = true;
      lastSavedProfileSnapshotRef.current = profileData
        ? JSON.stringify(normalizeProfile(nextDraft))
        : "";
      suppressCriteriaAutosaveRef.current = true;
      lastSavedCriteriaSnapshotRef.current = JSON.stringify(criteriaDraftToPayload(nextCriteriaDraft));
      startTransition(() => {
        setProfile(profileData);
        setDraft(nextDraft);
        setCriteriaDraft(nextCriteriaDraft);
        setBlacklist(blacklistRows || []);
        setCompleteness(completenessData || { completeness: 0 });
        setExtractions(extractionData?.extractions || []);
        setLoading(false);
      });
    } catch (error) {
      pushToast(`Profilseite konnte nicht geladen werden: ${error.message}`, "danger");
      startTransition(() => setLoading(false));
    }
  });

  useEffect(() => {
    setLoading(true);
    loadPage();
  }, [reloadKey]);

  useEffect(() => {
    if (loading || !profile) return undefined;
    if (suppressProfileAutosaveRef.current) {
      suppressProfileAutosaveRef.current = false;
      return undefined;
    }

    const payload = normalizeProfile(draft);
    const snapshot = JSON.stringify(payload);
    if (snapshot === lastSavedProfileSnapshotRef.current) return undefined;

    const handle = window.setTimeout(async () => {
      try {
        await postJson("/api/profile", payload);
        lastSavedProfileSnapshotRef.current = snapshot;
        startTransition(() => {
          setProfile((current) =>
            current ? { ...current, ...payload, preferences: { ...current.preferences, ...payload.preferences } } : current
          );
        });
        await refreshChrome({ quiet: true });
      } catch (error) {
        pushToast(`Profil konnte nicht gespeichert werden: ${error.message}`, "danger");
      }
    }, 700);

    return () => window.clearTimeout(handle);
  }, [draft, loading, profile, pushToast, refreshChrome]);

  useEffect(() => {
    if (loading) return undefined;
    if (suppressCriteriaAutosaveRef.current) {
      suppressCriteriaAutosaveRef.current = false;
      return undefined;
    }

    const payload = criteriaDraftToPayload(criteriaDraft);
    const snapshot = JSON.stringify(payload);
    if (snapshot === lastSavedCriteriaSnapshotRef.current) return undefined;

    const handle = window.setTimeout(async () => {
      try {
        await postJson("/api/search-criteria", payload);
        lastSavedCriteriaSnapshotRef.current = snapshot;
        await refreshChrome({ quiet: true });
      } catch (error) {
        pushToast(`Suchkriterien konnten nicht gespeichert werden: ${error.message}`, "danger");
      }
    }, 600);

    return () => window.clearTimeout(handle);
  }, [criteriaDraft, loading, pushToast, refreshChrome]);

  useEffect(() => {
    if (intent?.page !== "profil") return;
    if (intent.composer === "position") setPositionDialog({ open: true, draft: EMPTY_POSITION });
    if (intent.composer === "education") setEducationDialog({ open: true, draft: EMPTY_EDUCATION });
    if (intent.composer === "skill") setSkillDialog({ open: true, draft: buildSkillDraft(EMPTY_SKILL) });
    if (intent.composer === "document") {
      document.getElementById("section-documents")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    clearIntent();
  }, [intent]);

  async function saveItem(type, dialog) {
    const draftValue = dialog.draft;
    try {
      if (type === "position") {
        const { id, ...payload } = draftValue;
        let savedId = id;
        if (id) {
          await putJson(`/api/position/${id}`, payload);
        } else {
          const created = await postJson("/api/position", payload);
          savedId = created?.id || id;
        }
        const nextPosition = {
          ...payload,
          id: savedId,
          projects: Array.isArray(draftValue.projects) ? draftValue.projects : [],
        };
        startTransition(() => {
          setProfile((current) => {
            if (!current) return current;
            const existing = Array.isArray(current.positions) ? current.positions : [];
            const updated = id
              ? existing.map((item) => (item.id === id ? { ...item, ...nextPosition } : item))
              : [nextPosition, ...existing];
            return { ...current, positions: updated };
          });
        });
        setPositionDialog({ open: false, draft: EMPTY_POSITION });
      }
      if (type === "education") {
        const { id, ...payload } = draftValue;
        let savedId = id;
        if (id) {
          await putJson(`/api/education/${id}`, payload);
        } else {
          const created = await postJson("/api/education", payload);
          savedId = created?.id || id;
        }
        const nextEducation = { ...payload, id: savedId };
        startTransition(() => {
          setProfile((current) => {
            if (!current) return current;
            const existing = Array.isArray(current.education) ? current.education : [];
            const updated = id
              ? existing.map((item) => (item.id === id ? { ...item, ...nextEducation } : item))
              : [nextEducation, ...existing];
            return { ...current, education: updated };
          });
        });
        setEducationDialog({ open: false, draft: EMPTY_EDUCATION });
      }
      if (type === "skill") {
        const payload = buildSkillPayload(draftValue);
        let savedId = draftValue.id;
        if (draftValue.id) {
          await putJson(`/api/skill/${draftValue.id}`, payload);
        } else {
          const created = await postJson("/api/skill", payload);
          savedId = created?.id || draftValue.id;
        }
        const nextSkill = { ...payload, id: savedId };
        startTransition(() => {
          setProfile((current) => {
            if (!current) return current;
            const existing = Array.isArray(current.skills) ? current.skills : [];
            const updated = draftValue.id
              ? existing.map((item) => (item.id === draftValue.id ? { ...item, ...nextSkill } : item))
              : [nextSkill, ...existing];
            return { ...current, skills: updated };
          });
        });
        setSkillDialog({ open: false, draft: EMPTY_SKILL });
      }
      await refreshChrome({ quiet: true });
      pushToast("Eintrag gespeichert.", "success");
    } catch (error) {
      pushToast(`Eintrag konnte nicht gespeichert werden: ${error.message}`, "danger");
    }
  }

  function togglePosition(positionId) {
    setExpandedPositions((current) => ({ ...current, [positionId]: !current[positionId] }));
  }

  async function saveProject() {
    if (!projectDialog.positionId) return;
    if (!projectDialog.draft.name?.trim()) {
      pushToast("Projektname ist ein Pflichtfeld.", "danger");
      return;
    }
    try {
      const isEdit = Boolean(projectDialog.draft.id);
      if (isEdit) {
        const { id, ...payload } = projectDialog.draft;
        await putJson(`/api/project/${id}`, payload);
        startTransition(() => {
          setProfile((current) => {
            if (!current) return current;
            return {
              ...current,
              positions: (current.positions || []).map((position) => {
                if (position.id !== projectDialog.positionId) return position;
                return {
                  ...position,
                  projects: (position.projects || []).map((p) =>
                    p.id === id ? { ...p, ...payload } : p
                  ),
                };
              }),
            };
          });
        });
      } else {
        const created = await postJson("/api/project", {
          ...projectDialog.draft,
          position_id: projectDialog.positionId,
        });
        const nextProject = { ...projectDialog.draft, id: created?.id || "" };
        startTransition(() => {
          setProfile((current) => {
            if (!current) return current;
            return {
              ...current,
              positions: (current.positions || []).map((position) => {
                if (position.id !== projectDialog.positionId) return position;
                const existingProjects = Array.isArray(position.projects) ? position.projects : [];
                return { ...position, projects: [...existingProjects, nextProject] };
              }),
            };
          });
        });
      }
      setProjectDialog({ open: false, positionId: "", draft: EMPTY_PROJECT });
      await refreshChrome({ quiet: true });
      pushToast(isEdit ? "Projekt aktualisiert." : "Projekt gespeichert.", "success");
    } catch (error) {
      pushToast(`Projekt konnte nicht gespeichert werden: ${error.message}`, "danger");
    }
  }

  async function deleteProject(positionId, projectId) {
    if (!window.confirm("Projekt wirklich löschen?")) return;
    try {
      await deleteRequest(`/api/project/${projectId}`);
      startTransition(() => {
        setProfile((current) => {
          if (!current) return current;
          return {
            ...current,
            positions: (current.positions || []).map((position) => {
              if (position.id !== positionId) return position;
              return {
                ...position,
                projects: (position.projects || []).filter((p) => p.id !== projectId),
              };
            }),
          };
        });
      });
      await refreshChrome({ quiet: true });
      pushToast("Projekt gelöscht.", "success");
    } catch (error) {
      pushToast(`Projekt konnte nicht gelöscht werden: ${error.message}`, "danger");
    }
  }

  async function refreshProfileContent(options = {}) {
    const syncChrome = Boolean(options?.syncChrome);
    if (syncChrome) {
      await Promise.all([loadPage(), refreshChrome({ quiet: true })]);
      return;
    }
    await loadPage();
  }

  async function processDocumentFiles(filesLike) {
    const incoming = Array.from(filesLike || []).filter((file) => file && file.name);
    if (!incoming.length) return;

    const signatures = new Set();
    const files = [];
    for (const file of incoming) {
      const signature = createFileSignature(file);
      if (signatures.has(signature)) continue;
      signatures.add(signature);
      files.push(file);
    }

    if (!files.length) {
      pushToast("Diese Dateien sind bereits enthalten.", "neutral");
      return;
    }

    let uploaded = 0;
    let failed = 0;
    for (const file of files) {
      try {
        await uploadDocumentFile(file, uploadForm.doc_type || "sonstiges");
        uploaded += 1;
      } catch (error) {
        failed += 1;
        pushToast(`Upload fehlgeschlagen (${file.name}): ${error.message}`, "danger");
      }
    }

    if (uploaded > 0) {
      try {
        await analyzeUploadedDocuments();
      } catch (error) {
        pushToast(`Analyse nach Upload fehlgeschlagen: ${error.message}`, "danger");
      }
    }

    await refreshProfileContent({ syncChrome: true });

    if (uploaded > 0 && failed === 0) {
      pushToast(`${uploaded} Dokument(e) hochgeladen und analysiert.`, "success");
      return;
    }
    if (uploaded > 0 && failed > 0) {
      pushToast(`${uploaded} Dokument(e) hochgeladen, ${failed} fehlgeschlagen.`, "amber");
      return;
    }
    pushToast("Keine Datei konnte verarbeitet werden.", "danger");
  }

  async function importFolder() {
    if (!folderPath) {
      pushToast("Bitte einen Ordnerpfad eingeben.", "danger");
      return;
    }
    try {
      await postJson("/api/documents/import-folder", { folder_path: folderPath, import_documents: true, import_applications: true });
      setFolderDialogOpen(false);
      setFolderPath("");
      await refreshProfileContent({ syncChrome: true });
      pushToast("Ordnerimport abgeschlossen.", "success");
    } catch (error) {
      pushToast(`Ordnerimport fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function importProfile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const body = new FormData();
      body.append("file", file);
      await api("/api/profile/import", { method: "POST", body });
      await refreshProfileContent({ syncChrome: true });
      pushToast("Profil importiert.", "success");
    } catch (error) {
      pushToast(`Profilimport fehlgeschlagen: ${error.message}`, "danger");
    } finally {
      event.target.value = "";
    }
  }

  async function quickAction(fn, successText, options = {}) {
    try {
      await fn();
      if (typeof options.onSuccess === "function") {
        await options.onSuccess();
      }
      if (options.localRefresh) {
        await refreshProfileContent({ syncChrome: Boolean(options.syncChrome) });
      } else {
        await refreshChrome({ quiet: true });
      }
      pushToast(successText, "success");
    } catch (error) {
      pushToast(`${successText} fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function analyzeSingleDocument(docId) {
    try {
      await postJson(`/api/document/${docId}/reanalyze`, {});
      const result = await analyzeUploadedDocuments();
      await refreshProfileContent({ syncChrome: true });

      if (result?.status === "keine_dokumente" || result?.status === "keine_daten") {
        pushToast(result?.nachricht || "Keine neuen Daten zur Analyse gefunden.", "amber");
        return;
      }

      pushToast(result?.nachricht || "Dokument wurde analysiert.", "success");
    } catch (error) {
      pushToast(`Dokumentanalyse fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function addBlacklistEntry() {
    const value = String(blacklistForm.value || "").trim();
    if (!value) {
      pushToast("Bitte einen Wert für die Blacklist eingeben.", "danger");
      return;
    }
    try {
      await postJson("/api/blacklist", { ...blacklistForm, value });
      setBlacklistForm({ type: "firma", value: "" });
      const rows = await api("/api/blacklist");
      startTransition(() => setBlacklist(rows || []));
      await refreshChrome({ quiet: true });
      pushToast("Blacklist-Eintrag angelegt.", "success");
    } catch (error) {
      pushToast(`Blacklist-Eintrag fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function removeBlacklistEntry(entryId) {
    try {
      await deleteRequest(`/api/blacklist/${entryId}`);
      startTransition(() => setBlacklist((current) => current.filter((entry) => entry.id !== entryId)));
      await refreshChrome({ quiet: true });
      pushToast("Blacklist-Eintrag entfernt.", "success");
    } catch (error) {
      const message = String(error?.message || "");
      if (message.includes("Blacklist-Eintrag nicht gefunden")) {
        startTransition(() => setBlacklist((current) => current.filter((entry) => entry.id !== entryId)));
        pushToast("Blacklist-Eintrag war bereits entfernt.", "sky");
        return;
      }
      if (message.includes("HTTP 404")) {
        pushToast("Löschen-Endpunkt nicht gefunden. Bitte Dashboard-Server neu starten.", "danger");
        return;
      }
      pushToast(`Blacklist-Eintrag konnte nicht gelöscht werden: ${message}`, "danger");
    }
  }

  async function openExtractionDialog(document) {
    setExtractionDialog({
      open: true,
      loading: true,
      saving: false,
      document,
      extraction: null,
      draftText: "{}",
    });
    try {
      const response = await api(`/api/document/${document.id}/extraction`);
      const extraction = response?.extraction || null;
      setExtractionDialog({
        open: true,
        loading: false,
        saving: false,
        document,
        extraction,
        draftText: JSON.stringify(extraction?.extracted_fields || {}, null, 2),
      });
    } catch (error) {
      const message = String(error?.message || "");
      if (message.includes("404")) {
        pushToast(
          "Extraktion-Endpunkt nicht gefunden (404). Bitte API neu starten, wahrscheinlich läuft noch eine alte Instanz.",
          "danger"
        );
      } else {
        pushToast(`Extraktion konnte nicht geladen werden: ${error.message}`, "danger");
      }
      setExtractionDialog({
        open: true,
        loading: false,
        saving: false,
        document,
        extraction: null,
        draftText: "{}",
      });
    }
  }

  async function saveExtractionCorrections() {
    if (!extractionDialog.document?.id) return;

    let correctedFields = {};
    try {
      correctedFields = JSON.parse(extractionDialog.draftText || "{}");
    } catch {
      pushToast("JSON ist ungültig. Bitte Syntax prüfen.", "danger");
      return;
    }

    setExtractionDialog((current) => ({ ...current, saving: true }));
    try {
      const response = await putJson(`/api/document/${extractionDialog.document.id}/extraction`, {
        corrected_fields: correctedFields,
      });
      await refreshProfileContent({ syncChrome: true });
      const appliedKeys = Object.keys(response?.angewendet || {});
      pushToast(
        appliedKeys.length
          ? `Korrekturen übernommen: ${appliedKeys.join(", ")}`
          : "Korrekturen gespeichert.",
        "success"
      );
      setExtractionDialog({
        open: false,
        loading: false,
        saving: false,
        document: null,
        extraction: null,
        draftText: "{}",
      });
    } catch (error) {
      pushToast(`Korrekturen konnten nicht gespeichert werden: ${error.message}`, "danger");
      setExtractionDialog((current) => ({ ...current, saving: false }));
    }
  }

  if (loading) return <LoadingPanel label="Profil wird geladen..." />;

  if (!chrome.status?.has_profile || !profile) {
    return (
      <div id="page-profil" className="page active">
        <PageHeader title="Profil" description="Lege dein erstes Profil an oder importiere vorhandene Daten." eyebrow="Profil" />
        <EmptyState
          title="Noch kein aktives Profil"
          description="Ohne Profil bleiben Matching, Exporte und automatische Auswertungen leer."
          action={<Button onClick={openCreateProfileModal}>Profil anlegen</Button>}
        />
      </div>
    );
  }

  const documents = profile.documents || [];
  const latestDocument = documents.reduce(
    (latest, item) => {
      const timestamp = Date.parse(item?.created_at || "");
      if (Number.isNaN(timestamp)) return latest;
      if (timestamp > latest.timestamp) return { item, timestamp };
      return latest;
    },
    { item: null, timestamp: -Infinity }
  ).item;
  const latestDocumentLabel = latestDocument?.created_at
    ? formatDateTime(latestDocument.created_at)
    : "Noch keine Uploads";
  const processedDocumentCount = documents.filter((item) =>
    ["angewendet", "teilweise", "manuell_korrigiert", "verworfen"].includes(String(item?.extraction_status || ""))
  ).length;
  const pendingDocumentCount = Math.max(0, documents.length - processedDocumentCount);
  const documentTypeCounts = documents.reduce((acc, item) => {
    const key = docTypeLabel(item?.doc_type || "sonstiges");
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const topDocumentTypes = Object.entries(documentTypeCounts)
    .sort(([, leftCount], [, rightCount]) => Number(rightCount) - Number(leftCount))
    .slice(0, 4);
  const weightingCards = [
    { label: "MUSS", key: "gewichtung_muss", chip: "Pflicht", desc: "Harte Kriterien mit höchster Priorität.", color: "teal" },
    { label: "PLUS", key: "gewichtung_plus", chip: "Bonus", desc: "Zusatzpunkte für passende Bonuskriterien.", color: "sky" },
    { label: "Remote", key: "gewichtung_remote", chip: "Modus", desc: "Gewichtung für Homeoffice und Hybrid.", color: "sky" },
    { label: "Nähe", key: "gewichtung_naehe", chip: "Standort", desc: "Fokus auf Pendel- und Präsenztreffer.", color: "teal" },
    { label: "Fern-Malus", key: "gewichtung_fern_malus", chip: "Abzug", desc: "Höherer Wert = stärkerer Abzug bei Distanz.", color: "coral" },
    { label: "Gehalt", key: "gewichtung_gehalt", chip: "Vergütung", desc: "Gehaltsangaben stärker ins Ranking einbeziehen.", color: "amber" },
  ];

  const normalizeWeight = (value) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 0;
    return Math.max(0, Math.min(10, numeric));
  };

  const formatWeightValue = (value) => (Number.isInteger(value) ? String(value) : value.toFixed(1));

  const nudgeWeight = (key, delta) => {
    setCriteriaDraft((current) => ({
      ...current,
      [key]: String(normalizeWeight((Number(current[key]) || 0) + delta)),
    }));
  };

  const weightColorVars = {
    teal: { track: "bg-teal/20", fill: "bg-teal", thumb: "accent-teal", value: "text-teal", label: "text-ink/70" },
    sky: { track: "bg-sky/20", fill: "bg-sky", thumb: "accent-sky", value: "text-sky", label: "text-ink/70" },
    coral: { track: "bg-coral/20", fill: "bg-coral", thumb: "accent-coral", value: "text-coral", label: "text-ink/70" },
    amber: { track: "bg-amber/20", fill: "bg-amber", thumb: "accent-amber", value: "text-amber", label: "text-ink/70" },
  };

  const renderWeightRow = (card) => {
    const value = normalizeWeight(criteriaDraft[card.key]);
    const c = weightColorVars[card.color];

    return (
      <div key={card.key} className="group flex items-center gap-4 py-2">
        <div className="w-28 shrink-0">
          <p className={cn("text-[12px] font-semibold", c.label)}>{card.label}</p>
          <p className="text-[10px] text-muted/50">{card.chip}</p>
        </div>
        <div className="relative flex flex-1 items-center">
          <input
            type="range"
            min={0}
            max={10}
            step={0.5}
            value={value}
            onChange={(event) => setCriteriaDraft((current) => ({ ...current, [card.key]: event.target.value }))}
            className={cn("weight-slider h-1.5 w-full cursor-pointer appearance-none rounded-full", c.track, c.thumb)}
            style={{
              background: `linear-gradient(to right, var(--slider-fill) ${value * 10}%, transparent ${value * 10}%)`,
              "--slider-fill": `var(--color-${card.color})`,
            }}
          />
        </div>
        <span className={cn("w-8 text-right text-sm font-bold tabular-nums", c.value)}>
          {formatWeightValue(value)}
        </span>
      </div>
    );
  };

  return (
    <div id="page-profil" className="page active">
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Profil</h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => importRef.current?.click()}>
            <Upload size={15} /> Importieren
          </Button>
          <Button variant="ghost" onClick={async () => {
            const res = await api("/api/profile/export");
            const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = `profil_${draft.name || "backup"}.json`; a.click();
            URL.revokeObjectURL(url);
            pushToast("Profil exportiert", "success");
          }}>
            <Download size={15} /> Exportieren
          </Button>
          <Button variant="danger" onClick={async () => {
            if (!window.confirm("Profil wirklich löschen? Alle zugehörigen Daten (Positionen, Skills, Dokumente) werden ebenfalls gelöscht.")) return;
            try {
              await api(`/api/profiles/${profile.id}`, { method: "DELETE" });
              pushToast("Profil gelöscht", "success");
              refreshChrome();
            } catch (err) {
              pushToast("Fehler beim Löschen: " + (err.message || err), "error");
            }
          }}>
            <Trash2 size={15} /> Löschen
          </Button>
        </div>
      </div>

      <input ref={importRef} type="file" accept=".json" className="hidden" onChange={importProfile} />

      <div className="flex gap-6">
        {/* Sticky sidebar navigation (#122) */}
        <nav className="hidden lg:block w-48 shrink-0">
          <div className="sticky top-6 space-y-1">
            <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted/40">Navigation</p>
            {[
              ["profil-uebersicht", "Übersicht"],
              ["profil-persoenlich", "Persönliche Daten"],
              ["profil-suchkriterien", "Suchkriterien"],
              ["profil-blacklist", "Blacklist"],
              ["profil-erfahrung", "Berufserfahrung"],
              ["profil-ausbildung", "Ausbildung"],
              ["profil-skills", "Skills"],
              ["profil-dokumente", "Dokumente"],
            ].map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="block rounded-lg px-3 py-1.5 text-[13px] text-muted/60 transition-colors hover:bg-white/[0.06] hover:text-ink"
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                {label}
              </a>
            ))}
          </div>
        </nav>

        <div className="min-w-0 flex-1 grid gap-6">
        <div id="profil-uebersicht" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {profileElementCards.map((item) => (
            <MetricCard
              key={item.key}
              label={item.label}
              value={item.value}
              note={item.note}
              tone="neutral"
            />
          ))}
        </div>

        <Card id="profil-persoenlich" className="rounded-2xl">
          <SectionHeading title="Persönliche Daten" description="Diese Daten fließen in CV, Anschreiben und Matching ein." />
          <div className="grid gap-5">
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">Kontakt</p>
                <div className="grid gap-3">
                  <Field label="Name">
                    <TextInput value={draft.name || ""} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} />
                  </Field>
                  <Field label="E-Mail">
                    <TextInput value={draft.email || ""} onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))} />
                  </Field>
                  <Field label="Telefon">
                    <TextInput value={draft.phone || ""} onChange={(event) => setDraft((current) => ({ ...current, phone: event.target.value }))} />
                  </Field>
                </div>
              </div>

              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">Adresse</p>
                <div className="grid gap-3">
                  <Field label="Strasse">
                    <TextInput value={draft.address || ""} onChange={(event) => setDraft((current) => ({ ...current, address: event.target.value }))} />
                  </Field>
                  <div className="grid grid-cols-[6rem_minmax(0,8rem)_minmax(0,1fr)] gap-3">
                    <Field label="PLZ">
                      <TextInput value={draft.plz || ""} onChange={(event) => setDraft((current) => ({ ...current, plz: event.target.value }))} />
                    </Field>
                    <Field label="Ort">
                      <TextInput value={draft.city || ""} onChange={(event) => setDraft((current) => ({ ...current, city: event.target.value }))} />
                    </Field>
                    <Field label="Land">
                      <TextInput value={draft.country || ""} onChange={(event) => setDraft((current) => ({ ...current, country: event.target.value }))} />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Geburtsdatum">
                      <TextInput value={draft.birthday || ""} onChange={(event) => setDraft((current) => ({ ...current, birthday: event.target.value }))} />
                    </Field>
                    <Field label="Nationalität">
                      <TextInput value={draft.nationality || ""} onChange={(event) => setDraft((current) => ({ ...current, nationality: event.target.value }))} />
                    </Field>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-3">
              <Field label="Kurzprofil / Summary">
                <TextArea rows={4} value={draft.summary || ""} onChange={(event) => setDraft((current) => ({ ...current, summary: event.target.value }))} />
              </Field>
              <Field label="Informelle Notizen">
                <TextArea rows={3} value={draft.informal_notes || ""} onChange={(event) => setDraft((current) => ({ ...current, informal_notes: event.target.value }))} />
              </Field>
            </div>
          </div>
        </Card>

        <Card id="profil-suchkriterien" className="rounded-2xl">
          <SectionHeading title="Suchkriterien" description="Keywords und Gewichtungen für Matching und Scoring." />
          <div className="grid gap-4">
            {[
              ["MUSS-Keywords", "keywords_muss", "sky", "z.B. Data Scientist"],
              ["PLUS-Keywords", "keywords_plus", "success", "z.B. Python, Machine Learning"],
              ["Ausschluss-Keywords", "keywords_ausschluss", "danger", "z.B. Praktikum, Junior"],
              ["Regionen", "regionen", "amber", "z.B. Hamburg, Berlin"],
            ].map(([label, key, tone, placeholder]) => (
              <Field key={key} label={label}>
                <TagInput
                  tags={criteriaDraft[key] || []}
                  onChange={(newTags) => setCriteriaDraft((current) => ({ ...current, [key]: newTags }))}
                  tone={tone}
                  placeholder={placeholder}
                />
              </Field>
            ))}

            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Min. Gehalt">
                <TextInput
                  type="number"
                  value={criteriaDraft.min_gehalt}
                  onChange={(event) => setCriteriaDraft((current) => ({ ...current, min_gehalt: event.target.value }))}
                />
              </Field>
              <Field label="Min. Tagessatz">
                <TextInput
                  type="number"
                  value={criteriaDraft.min_tagessatz}
                  onChange={(event) => setCriteriaDraft((current) => ({ ...current, min_tagessatz: event.target.value }))}
                />
              </Field>
              <Field label="Min. Stundensatz">
                <TextInput
                  type="number"
                  value={criteriaDraft.min_stundensatz}
                  onChange={(event) => setCriteriaDraft((current) => ({ ...current, min_stundensatz: event.target.value }))}
                />
              </Field>
              <Field label="Max. Entfernung (km)">
                <TextInput
                  type="number"
                  value={criteriaDraft.max_entfernung_km}
                  onChange={(event) => setCriteriaDraft((current) => ({ ...current, max_entfernung_km: event.target.value }))}
                  placeholder="z.B. 50"
                />
              </Field>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Stellentyp">
                <SelectInput
                  value={criteriaDraft.stellentyp}
                  onChange={(event) => setCriteriaDraft((current) => ({ ...current, stellentyp: event.target.value }))}
                >
                  <option value="">Keine Auswahl</option>
                  <option value="festanstellung">Festanstellung</option>
                  <option value="freelance">Freelance</option>
                  <option value="teilzeit">Teilzeit</option>
                </SelectInput>
              </Field>
            </div>

            <div className="mt-2 divide-y divide-white/[0.06] rounded-xl border border-white/10 bg-white/[0.02] px-4">
              {weightingCards.map((card) => renderWeightRow(card))}
            </div>

            <div id="profil-blacklist" className="mt-2 border-t border-white/8 pt-5">
              <SectionHeading title="Blacklist" description="Ausschlüsse für Firmen oder Keywords." />
              <div className="grid gap-4 md:grid-cols-[12rem_minmax(0,1fr)_auto]">
                <Field label="Typ">
                  <SelectInput value={blacklistForm.type} onChange={(event) => setBlacklistForm((current) => ({ ...current, type: event.target.value }))}>
                    <option value="firma">Firma</option>
                    <option value="keyword">Keyword</option>
                    <option value="ort">Ort</option>
                  </SelectInput>
                </Field>
                <Field label="Wert">
                  <TextInput value={blacklistForm.value} onChange={(event) => setBlacklistForm((current) => ({ ...current, value: event.target.value }))} />
                </Field>
                <div className="flex items-end">
                  <Button onClick={addBlacklistEntry}>
                    <Ban size={15} />
                    Hinzufügen
                  </Button>
                </div>
              </div>
              <div className="mt-6 grid gap-3">
                {blacklist.length ? (
                  blacklist.map((entry) => (
                    <Card key={entry.id ?? `${entry.type}-${entry.value}`} className="glass-card-soft rounded-xl shadow-none">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex min-w-0 flex-wrap items-center gap-3">
                          <Badge tone="danger">{entry.type}</Badge>
                          <p className="text-sm font-semibold text-ink">{entry.value}</p>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removeBlacklistEntry(entry.id)}
                          disabled={!entry.id}
                          title="Eintrag löschen"
                          aria-label={`Blacklist-Eintrag ${entry.value} löschen`}
                        >
                          <Trash2 size={14} />
                          Entfernen
                        </Button>
                      </div>
                    </Card>
                  ))
                ) : (
                  <EmptyState title="Keine Blacklist-Einträge" description="Ausschlüsse erscheinen hier nach dem Speichern." />
                )}
              </div>
            </div>
          </div>
        </Card>

        <div className="grid gap-6">
          <Card id="profil-erfahrung" className="rounded-2xl">
            <SectionHeading title="Berufserfahrung" description="Positionen für CV und Matching." action={<Button onClick={() => setPositionDialog({ open: true, draft: EMPTY_POSITION })}><Plus size={15} />Position</Button>} />
            <div className="grid gap-4">
              {profile.positions?.length ? profile.positions.map((item) => {
                const isExpanded = Boolean(expandedPositions[item.id]);
                const projects = item.projects || [];
                const projectCount = projects.length;
                const projectCountLabel = `${projectCount} ${projectCount === 1 ? "Projekt" : "Projekte"}`;
                return (
                  <Card key={item.id} className="glass-card-soft rounded-xl shadow-none">
                    <div className="flex w-full items-center justify-between gap-3">
                      <div className="min-w-0 flex-1 cursor-pointer space-y-2" role="button" tabIndex={0} onClick={() => togglePosition(item.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") togglePosition(item.id); }}>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone="sky">{item.company || "Unbekannt"}</Badge>
                          <Badge tone={projectCount ? "success" : "neutral"}>{projectCountLabel}</Badge>
                        </div>
                        <h3 className="text-lg font-semibold text-ink">{item.title || "Ohne Titel"}</h3>
                        <p className="text-sm text-muted">{formatPositionPeriod(item)}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Button size="sm" variant="ghost" onClick={() => setPositionDialog({ open: true, draft: { ...item, start_date: normalizeMonthDate(item.start_date), end_date: normalizeMonthDate(item.end_date) } })}>Bearbeiten</Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            if (!window.confirm("Position wirklich löschen? Alle zugehörigen Projekte werden ebenfalls gelöscht.")) return;
                            quickAction(() => deleteRequest(`/api/position/${item.id}`), "Position gelöscht", {
                              onSuccess: () =>
                                startTransition(() => {
                                  setProfile((current) => {
                                    if (!current) return current;
                                    return {
                                      ...current,
                                      positions: (current.positions || []).filter((position) => position.id !== item.id),
                                    };
                                  });
                                }),
                            });
                          }}
                        >
                          <Trash2 size={15} />
                          Löschen
                        </Button>
                        <button type="button" onClick={() => togglePosition(item.id)} className="p-1">
                          <ChevronDown size={18} className={cn("text-muted transition-transform duration-200", isExpanded && "rotate-180")} />
                        </button>
                      </div>
                    </div>

                    {isExpanded ? (
                      <div className="mt-4 grid gap-3">
                        <div className="flex flex-wrap gap-2">
                          {item.employment_type ? (
                            <Badge tone="neutral">{EMPLOYMENT_TYPE_LABELS[item.employment_type] || item.employment_type}</Badge>
                          ) : null}
                          {item.industry ? <Badge tone="neutral">{item.industry}</Badge> : null}
                        </div>

                        {item.description ? <p className="text-sm text-muted/80">{item.description}</p> : null}
                        {item.tasks ? (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">Aufgaben</p>
                            <p className="mt-1 text-sm text-muted/80">{item.tasks}</p>
                          </div>
                        ) : null}
                        {item.achievements ? (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">Erfolge</p>
                            <p className="mt-1 text-sm text-teal/80">{item.achievements}</p>
                          </div>
                        ) : null}
                        {item.technologies ? (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">Technologien</p>
                            <p className="mt-1 text-sm text-muted/80">{item.technologies}</p>
                          </div>
                        ) : null}

                        <div className="rounded-xl border border-white/[0.04] bg-white/[0.01] p-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">
                              Projekte ({projects.length})
                            </p>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setProjectDialog({ open: true, positionId: item.id, draft: EMPTY_PROJECT })}
                            >
                              <Plus size={13} />
                              Projekt
                            </Button>
                          </div>

                          {projects.length ? (
                            <div className="mt-3 grid gap-2">
                              {projects.map((project, index) => (
                                <div key={project.id || `${item.id}-${index}`} className="rounded-lg border border-white/[0.04] bg-white/[0.015] p-3">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="text-sm font-semibold text-ink">{project.name || "Projekt"}</p>
                                    {project.role ? <Badge tone="sky">{project.role}</Badge> : null}
                                  </div>
                                  {project.duration ? <p className="mt-1 text-[12px] text-muted/50">{project.duration}</p> : null}
                                  {project.description ? <p className="mt-2 text-[12px] text-muted/70">{project.description}</p> : null}
                                  <div className="mt-2 grid gap-1 text-[12px]">
                                    {project.situation ? <p className="text-muted/70"><strong>S:</strong> {project.situation}</p> : null}
                                    {project.task ? <p className="text-muted/70"><strong>T:</strong> {project.task}</p> : null}
                                    {project.action ? <p className="text-muted/70"><strong>A:</strong> {project.action}</p> : null}
                                    {project.result ? <p className="text-teal/80"><strong>R:</strong> {project.result}</p> : null}
                                  </div>
                                  {project.technologies ? <p className="mt-2 text-[11px] text-muted/50">Tech: {project.technologies}</p> : null}
                                  <div className="mt-2 flex gap-3 border-t border-white/[0.04] pt-2">
                                    <button type="button" className="text-[12px] text-muted/50 hover:text-ink transition-colors" onClick={() => setProjectDialog({ open: true, positionId: item.id, draft: { ...project } })}>Bearbeiten</button>
                                    <button type="button" className="text-[12px] text-muted/50 hover:text-coral transition-colors" onClick={() => deleteProject(item.id, project.id)}>
                                      <span className="inline-flex items-center gap-1"><Trash2 size={11} /> Löschen</span>
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-2 text-[12px] text-muted/50">Noch keine Projekte erfasst.</p>
                          )}
                        </div>
                      </div>
                    ) : null}
                  </Card>
                );
              }) : <EmptyState title="Noch keine Positionen" description="Berufserfahrung ist ein Kernbaustein des Profils." action={<Button onClick={() => setPositionDialog({ open: true, draft: EMPTY_POSITION })}><BriefcaseBusiness size={15} />Position erfassen</Button>} />}
            </div>
          </Card>

          <Card id="profil-ausbildung" className="rounded-2xl">
            <SectionHeading title="Ausbildung" description="Studium und Ausbildung." action={<Button onClick={() => setEducationDialog({ open: true, draft: EMPTY_EDUCATION })}><Plus size={15} />Ausbildung</Button>} />
            <div className="grid gap-4">
              {profile.education?.length ? profile.education.map((item) => (
                <Card key={item.id} className="glass-card-soft rounded-xl shadow-none">
                  <h3 className="text-lg font-semibold text-ink">{item.institution}</h3>
                  <p className="mt-2 text-sm text-muted">{[item.degree, item.field_of_study].filter(Boolean).join(" - ")}</p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Button variant="ghost" onClick={() => setEducationDialog({ open: true, draft: { ...item, start_date: normalizeMonthDate(item.start_date), end_date: normalizeMonthDate(item.end_date) } })}>Bearbeiten</Button>
                    <Button
                      variant="ghost"
                      onClick={() =>
                        quickAction(() => deleteRequest(`/api/education/${item.id}`), "Ausbildung gelöscht", {
                          onSuccess: () =>
                            startTransition(() => {
                              setProfile((current) => {
                                if (!current) return current;
                                return {
                                  ...current,
                                  education: (current.education || []).filter((education) => education.id !== item.id),
                                };
                              });
                            }),
                        })
                      }
                    >
                      <Trash2 size={15} />
                      Löschen
                    </Button>
                  </div>
                </Card>
              )) : <EmptyState title="Noch keine Ausbildung" description="Füge Ausbildung oder Studium hinzu." action={<Button onClick={() => setEducationDialog({ open: true, draft: EMPTY_EDUCATION })}><GraduationCap size={15} />Ausbildung erfassen</Button>} />}
            </div>
          </Card>

          <Card id="profil-skills" className="rounded-2xl">
            <SectionHeading title="Skills" description="Kompetenzen für Matching und Fit-Analyse." action={<Button onClick={() => setSkillDialog({ open: true, draft: buildSkillDraft(EMPTY_SKILL) })}><Plus size={15} />Skill</Button>} />
            {profile.skills?.length ? (() => {
              const groups = {};
              for (const skill of profile.skills) {
                const cat = normalizeSkillCategory(skill.category);
                if (!groups[cat]) groups[cat] = [];
                groups[cat].push(skill);
              }
              return (
                <div className="grid gap-5">
                  {Object.entries(groups).map(([category, skills]) => (
                    <div key={category}>
                      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">
                        {SKILL_CATEGORY_LABELS[category] || category}
                      </p>
                      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                        {skills.map((item) => (
                          <Card key={item.id} className="glass-card-soft rounded-xl shadow-none">
                            <div className="flex items-center justify-between">
                              <Badge tone="sky">{SKILL_CATEGORY_LABELS[normalizeSkillCategory(item.category)]}</Badge>
                              <div className="flex items-center gap-1" title={`Level ${item.level ?? "?"}`}>
                                {[1, 2, 3, 4, 5].map((dot) => (
                                  <button
                                    key={dot}
                                    type="button"
                                    className={`h-2.5 w-2.5 rounded-full transition-colors ${
                                      dot <= (item.level ?? 0)
                                        ? (item.level ?? 0) <= 2 ? "bg-amber" : (item.level ?? 0) <= 3 ? "bg-sky" : "bg-teal"
                                        : "bg-white/[0.08] hover:bg-white/[0.2]"
                                    }`}
                                    onClick={async () => {
                                      const newLevel = dot === item.level ? dot - 1 : dot;
                                      try {
                                        await putJson(`/api/skill/${item.id}`, { ...item, level: newLevel });
                                        setProfile((prev) => ({
                                          ...prev,
                                          skills: prev.skills.map((s) => s.id === item.id ? { ...s, level: newLevel } : s),
                                        }));
                                        await refreshChrome({ quiet: true });
                                      } catch (error) {
                                        pushToast(`Level konnte nicht geändert werden: ${error.message}`, "danger");
                                      }
                                    }}
                                  />
                                ))}
                              </div>
                            </div>
                            <h3 className="mt-2 text-sm font-semibold text-ink">{item.name}</h3>
                            <p className="mt-1 text-[12px] text-muted/50">
                              {item.years_experience
                                ? `${item.years_experience} Jahre Erfahrung - seit ${Math.max(1900, currentYear - Math.max(0, Number(item.years_experience) || 0))}`
                                : "Ohne Erfahrungsjahre"}
                            </p>
                            <div className="mt-3 flex gap-2">
                              <Button size="sm" variant="ghost" onClick={() => setSkillDialog({ open: true, draft: buildSkillDraft(item) })}>Bearbeiten</Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  quickAction(() => deleteRequest(`/api/skill/${item.id}`), "Skill gelöscht", {
                                    onSuccess: () =>
                                      startTransition(() => {
                                        setProfile((current) => {
                                          if (!current) return current;
                                          return {
                                            ...current,
                                            skills: (current.skills || []).filter((skill) => skill.id !== item.id),
                                          };
                                        });
                                      }),
                                  })
                                }
                              >
                                <Trash2 size={13} />
                                Löschen
                              </Button>
                            </div>
                          </Card>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })() : <EmptyState title="Noch keine Skills" description="Lege Fach-, Tool- oder Soft-Skills an." action={<Button onClick={() => setSkillDialog({ open: true, draft: buildSkillDraft(EMPTY_SKILL) })}><Wrench size={15} />Skill erfassen</Button>} />}
          </Card>
        </div>

        <Card id="profil-dokumente" className="rounded-2xl">
          <SectionHeading
            title="Dokumente"
            description="Upload, Ordnerimport und Reanalyse bleiben über die vorhandenen Endpunkte erhalten."
          />
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
            <Card className="glass-card-soft rounded-xl shadow-none">
              <div className="grid gap-4">
                <Field label="Dokumenttyp">
                  <SelectInput value={uploadForm.doc_type} onChange={(event) => setUploadForm((current) => ({ ...current, doc_type: event.target.value }))}>
                    <option value="sonstiges">Automatisch / Sonstiges</option>
                    <option value="lebenslauf">Lebenslauf</option>
                    <option value="anschreiben">Anschreiben</option>
                    <option value="zeugnis">Zeugnis</option>
                    <option value="zertifikat">Zertifikat</option>
                  </SelectInput>
                </Field>
                <div
                  className={cn(
                    "rounded-xl border-2 border-dashed border-white/15 bg-white/[0.02] p-5 transition",
                    dragDocumentsActive && "border-sky/60 bg-sky/10 ring-2 ring-sky/35"
                  )}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setDragDocumentsActive(true);
                  }}
                  onDragEnter={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setDragDocumentsActive(true);
                  }}
                  onDragLeave={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (event.currentTarget.contains(event.relatedTarget)) return;
                    setDragDocumentsActive(false);
                  }}
                  onDrop={async (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setDragDocumentsActive(false);
                    const files = await extractDroppedFiles(event.dataTransfer);
                    await processDocumentFiles(files);
                  }}
                >
                  <p className="text-sm font-semibold text-ink">Dateien oder Ordner hier hineinziehen</p>
                  <p className="mt-1 text-xs text-muted">Mehrfach-Upload bleibt aktiv.</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button type="button" variant="secondary" onClick={() => documentFileInputRef.current?.click()}>
                      <Upload size={15} />
                      Dateien auswählen
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => documentFolderInputRef.current?.click()}
                    >
                      Ordner auswählen
                    </Button>
                  </div>
                  <input
                    ref={documentFileInputRef}
                    className="hidden"
                    type="file"
                    multiple
                    onChange={async (event) => {
                      await processDocumentFiles(event.target.files);
                      event.target.value = "";
                    }}
                  />
                  <input
                    ref={documentFolderInputRef}
                    className="hidden"
                    type="file"
                    multiple
                    webkitdirectory=""
                    directory=""
                    onChange={async (event) => {
                      await processDocumentFiles(event.target.files);
                      event.target.value = "";
                    }}
                  />
                </div>
              </div>
            </Card>

            <Card className="glass-card-soft rounded-xl shadow-none">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/50">Dokumentenstatus</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-muted/50">Gesamt</p>
                  <p className="mt-1 text-lg font-semibold text-ink">{documents.length}</p>
                </div>
                <div className="rounded-lg border border-teal/15 bg-teal/[0.06] px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-teal/70">Bearbeitet</p>
                  <p className="mt-1 text-lg font-semibold text-teal">{processedDocumentCount}</p>
                </div>
                <div className="rounded-lg border border-amber/15 bg-amber/[0.06] px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-amber/70">Offen</p>
                  <p className="mt-1 text-lg font-semibold text-amber">{pendingDocumentCount}</p>
                </div>
                <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-muted/50">Letzte Aktivität</p>
                  <p className="mt-1 text-[12px] font-medium text-ink/90">{latestDocumentLabel}</p>
                </div>
              </div>

              <div className="mt-4 rounded-lg border border-white/[0.05] bg-white/[0.02] p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted/50">Dokumenttypen</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {topDocumentTypes.length ? (
                    topDocumentTypes.map(([type, count]) => (
                      <Badge key={type} tone="neutral">{type} ({count})</Badge>
                    ))
                  ) : (
                    <span className="text-[12px] text-muted/60">Noch keine Dokumente vorhanden.</span>
                  )}
                </div>
              </div>

              <p className="mt-4 text-[12px] leading-relaxed text-muted/65">
                Tipp: Dokumente mit Status <span className="text-teal/80">angewendet</span> sind bereits in dein Profil eingeflossen.
                Über das Stift-Symbol kannst du extrahierte Inhalte prüfen und korrigieren.
              </p>
            </Card>
          </div>
          <div className="mt-5 grid gap-1.5">
            {documents.length ? documents.map((item) => (
              <div key={item.id} className="grid items-center gap-3 rounded-xl border border-white/[0.04] px-4 py-2.5 transition-colors hover:bg-white/[0.03]" style={{ gridTemplateColumns: "8rem 10.5rem minmax(0,1fr) 8.5rem auto" }}>
                <SelectInput
                  value={item.doc_type || "sonstiges"}
                  className="!min-h-0 !rounded-md !px-2 !py-1 text-[11px]"
                  onChange={async (event) => {
                    const newType = event.target.value;
                    const oldType = item.doc_type;
                    startTransition(() => setDocuments((cur) => cur.map((d) => d.id === item.id ? { ...d, doc_type: newType } : d)));
                    try {
                      await putJson(`/api/document/${item.id}/doc-type`, { doc_type: newType });
                      await refreshChrome({ quiet: true });
                      pushToast("Dokumenttyp aktualisiert.", "success");
                    } catch (err) {
                      startTransition(() => setDocuments((cur) => cur.map((d) => d.id === item.id ? { ...d, doc_type: oldType } : d)));
                      pushToast(`Fehler: ${err.message}`, "danger");
                    }
                  }}
                >
                  <option value="sonstiges">Sonstiges</option>
                  <option value="lebenslauf">Lebenslauf</option>
                  <option value="lebenslauf_vorlage">Lebenslauf (Vorlage)</option>
                  <option value="anschreiben">Anschreiben</option>
                  <option value="anschreiben_vorlage">Anschreiben (Vorlage)</option>
                  <option value="zeugnis">Zeugnis</option>
                  <option value="zertifikat">Zertifikat</option>
                </SelectInput>
                {(() => {
                  const statusMeta = getDocumentStatusMeta(item.extraction_status);
                  return (
                    <div className="group relative inline-flex">
                      <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
                      <div className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 w-64 -translate-x-1/2 translate-y-1 rounded-lg border border-white/12 bg-slate/95 px-2.5 py-2 text-[11px] leading-relaxed text-muted opacity-0 shadow-2xl transition-all duration-150 delay-0 group-hover:translate-y-0 group-hover:opacity-100 group-hover:delay-300">
                        {statusMeta.help}
                      </div>
                    </div>
                  );
                })()}
                <p className="truncate text-[13px] font-medium text-ink">
                  {item.filename}
                  {(item.doc_type || "").endsWith("_vorlage") && (
                    <span className="ml-1.5 inline-flex rounded bg-teal/15 px-1.5 py-px text-[10px] font-bold text-teal">VORLAGE</span>
                  )}
                </p>
                <span className="text-[11px] text-muted/40">{formatDateTime(item.created_at)}</span>
                <div className="flex justify-end gap-1.5">
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-white/15 bg-white/[0.05] px-2 text-[11px] font-medium text-ink/85 transition-colors hover:bg-white/[0.1] hover:text-ink"
                    title="Extrahierte Infos"
                    onClick={() => openExtractionDialog(item)}
                  >
                    <Pencil size={13} />
                    Details
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-teal/30 bg-teal/10 px-2 text-[11px] font-medium text-teal transition-colors hover:bg-teal/18"
                    title="Dokument analysieren"
                    onClick={() => analyzeSingleDocument(item.id)}
                  >
                    <Sparkles size={13} />
                    Analysieren
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-white/15 bg-white/[0.05] px-2 text-[11px] font-medium text-ink/85 transition-colors hover:bg-white/[0.1] hover:text-ink"
                    title="Reanalyse-Status zurücksetzen"
                    onClick={() =>
                      quickAction(() => postJson(`/api/document/${item.id}/reanalyze`, {}), "Dokument für Reanalyse markiert", {
                        localRefresh: true,
                        syncChrome: true,
                      })
                    }
                  >
                    <RefreshCcw size={13} />
                    Reset
                  </button>
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-coral/20 bg-coral/[0.08] px-2 text-[11px] font-medium text-coral/90 transition-colors hover:bg-coral/15 hover:text-coral"
                    title="Löschen"
                    onClick={() =>
                      quickAction(() => deleteRequest(`/api/document/${item.id}`), "Dokument gelöscht", {
                        localRefresh: true,
                        syncChrome: true,
                      })
                    }
                  >
                    <Trash2 size={13} />
                    Löschen
                  </button>
                </div>
              </div>
            )) : <EmptyState title="Noch keine Dokumente" description="Lade Lebenslauf, Zeugnisse oder Anschreiben hoch." />}
          </div>
        </Card>

        <Card className="rounded-2xl">
          <SectionHeading
            title={`Extraktions-Verlauf (${extractions.length})`}
            description="Typ, Status und erkannte Bereiche pro Lauf."
          />
          {extractions.length ? (
            <div className="overflow-hidden rounded-xl border border-white/[0.05]">
              {extractions.slice(0, 10).map((entry, index) => {
                const statusMeta = EXTRACTION_STATUS_META[entry.status] || {
                  label: entry.status || "Unbekannt",
                  tone: "neutral",
                };
                const isExpanded = expandedExtractionId === entry.id;
                const fieldCount = countExtractedFields(entry.extracted_fields);
                const conflictCount = Array.isArray(entry.conflicts) ? entry.conflicts.length : 0;
                const extractedFieldKeys = Object.keys(entry.extracted_fields || {});
                const appliedEntries = Object.entries(entry.applied_fields || {});
                const appliedSummary = appliedEntries.map(([key, value]) => {
                  if (Array.isArray(value)) return `${key}: ${value.length}`;
                  if (value && typeof value === "object") return `${key}: ${Object.keys(value).length}`;
                  return `${key}: ${value ?? 0}`;
                }).join(" | ");
                const summaryParts = [extractedFieldKeys.length ? extractedFieldKeys.join(", ") : `${fieldCount} Bereiche extrahiert`];
                if (appliedSummary) summaryParts.push(`→ ${appliedSummary}`);
                if (conflictCount) summaryParts.push(`${conflictCount} Konflikte`);
                return (
                  <div
                    key={entry.id}
                    className={cn(
                      "px-4 py-3 transition-colors",
                      isExpanded ? "bg-white/[0.03]" : "hover:bg-white/[0.02]",
                      index < Math.min(extractions.length, 10) - 1 && "border-b border-white/[0.05]"
                    )}
                  >
                    <div
                      role="button"
                      tabIndex={0}
                      className="cursor-pointer rounded-lg outline-none transition focus-visible:ring-2 focus-visible:ring-teal/35 focus-visible:ring-offset-2 focus-visible:ring-offset-shell"
                      onClick={() => setExpandedExtractionId((current) => (current === entry.id ? "" : entry.id))}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setExpandedExtractionId((current) => (current === entry.id ? "" : entry.id));
                        }
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-[15px] font-semibold text-ink">
                            {entry.extraction_type || entry.filename || "auto"}
                          </p>
                          <p className="mt-1 text-[12px] text-muted/50">{formatDateTime(entry.created_at)}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(event) => {
                              event.stopPropagation();
                              quickAction(
                                () => deleteRequest(`/api/extraction-history/${entry.id}`),
                                "Historieneintrag gelöscht",
                                { localRefresh: true, syncChrome: true }
                              );
                            }}
                          >
                            <Trash2 size={14} />
                            Löschen
                          </Button>
                        </div>
                        <ChevronDown
                          size={20}
                          className={cn("shrink-0 text-muted/60 transition-transform duration-200", isExpanded && "rotate-180")}
                        />
                      </div>
                      <p className="mt-2 text-[13px] text-muted/70">{summaryParts.join(", ")}</p>
                    </div>

                    <div
                      className={cn(
                        "grid transition-all duration-300 ease-out",
                        isExpanded ? "mt-3 grid-rows-[1fr] opacity-100" : "mt-0 grid-rows-[0fr] opacity-0"
                      )}
                    >
                      <div className="overflow-hidden">
                        <div className="space-y-3 rounded-xl border border-white/[0.05] bg-white/[0.02] p-3">
                          {extractedFieldKeys.map((fieldKey) => {
                            const fieldData = entry.extracted_fields[fieldKey];
                            const appliedCount = entry.applied_fields?.[fieldKey];
                            return (
                              <div key={fieldKey} className="rounded-lg border border-white/[0.04] bg-white/[0.02] p-2.5">
                                <div className="flex items-center gap-2">
                                  <p className="text-[11px] font-semibold text-teal/80">{fieldKey}</p>
                                  {appliedCount != null && <Badge tone="success">{typeof appliedCount === "number" ? `${appliedCount} übernommen` : "übernommen"}</Badge>}
                                </div>
                                <div className="mt-1.5 text-[12px] text-ink/80">
                                  {Array.isArray(fieldData) ? (
                                    <div className="flex flex-wrap gap-1.5">
                                      {fieldData.slice(0, 12).map((item, i) => (
                                        <span key={i} className="inline-block rounded-md border border-white/[0.06] bg-white/[0.04] px-2 py-0.5 text-[11px]">
                                          {typeof item === "string" ? item : item?.name || item?.title || item?.institution || JSON.stringify(item).slice(0, 40)}
                                        </span>
                                      ))}
                                      {fieldData.length > 12 && <span className="text-[11px] text-muted/50">+{fieldData.length - 12} weitere</span>}
                                    </div>
                                  ) : fieldData && typeof fieldData === "object" ? (
                                    <div className="grid gap-1 sm:grid-cols-2">
                                      {Object.entries(fieldData).map(([k, v]) => (
                                        <div key={k} className="flex gap-1.5">
                                          <span className="shrink-0 text-[11px] text-muted/50">{k}:</span>
                                          <span className="text-[11px] text-ink/80 truncate">{String(v ?? "–")}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    <p className="text-[11px] text-ink/70">{String(fieldData ?? "–")}</p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                          {conflictCount > 0 && (
                            <div className="rounded-lg border border-coral/15 bg-coral/[0.04] p-2.5">
                              <p className="text-[11px] font-semibold text-coral/80">Konflikte ({conflictCount})</p>
                              <p className="mt-1 text-[12px] text-ink/70">
                                {(entry.conflicts || []).slice(0, 5).map((item) => (typeof item === "string" ? item : item?.field || item?.key || "Konflikt")).join(", ")}
                              </p>
                            </div>
                          )}
                          <div className="flex items-center gap-3 text-[11px] text-muted/40">
                            <span>ID: {entry.id || "n/a"}</span>
                            <span>Dokument: {entry.document_id || "n/a"}</span>
                            <span>Abgeschlossen: {entry.completed_at ? formatDateTime(entry.completed_at) : "Noch offen"}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="Keine Extraktionshistorie"
              description="Sobald Dokumente analysiert werden, erscheinen die Einträge hier."
            />
          )}
        </Card>
      </div>
      </div>{/* end flex layout */}

      <Modal
        open={positionDialog.open}
        title={positionDialog.draft.id ? "Position bearbeiten" : "Neue Position"}
        onClose={() => setPositionDialog({ open: false, draft: EMPTY_POSITION })}
        footer={<div className="flex justify-end gap-3"><Button variant="ghost" onClick={() => setPositionDialog({ open: false, draft: EMPTY_POSITION })}>Abbrechen</Button><Button onClick={() => saveItem("position", positionDialog)}>Speichern</Button></div>}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Firma">
            <TextInput value={positionDialog.draft.company || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, company: event.target.value } }))} />
          </Field>
          <Field label="Titel">
            <TextInput value={positionDialog.draft.title || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, title: event.target.value } }))} />
          </Field>
          <Field label="Standort">
            <TextInput value={positionDialog.draft.location || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, location: event.target.value } }))} />
          </Field>
          <Field label="Branche">
            <TextInput value={positionDialog.draft.industry || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, industry: event.target.value } }))} />
          </Field>
          <Field label="Von">
            <TextInput type="month" value={positionDialog.draft.start_date || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, start_date: event.target.value } }))} />
          </Field>
          <Field label="Bis">
            <TextInput
              type="month"
              value={positionDialog.draft.end_date || ""}
              disabled={Boolean(positionDialog.draft.is_current)}
              onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, end_date: event.target.value } }))}
            />
          </Field>
          <Field label="Anstellungsart">
            <SelectInput value={positionDialog.draft.employment_type || "festanstellung"} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, employment_type: event.target.value } }))}>
              <option value="festanstellung">Festanstellung</option>
              <option value="freelance">Freelance</option>
              <option value="teilzeit">Teilzeit</option>
              <option value="praktikum">Praktikum</option>
            </SelectInput>
          </Field>
          <label className="mt-8 inline-flex items-center gap-2 text-sm text-ink">
            <CheckboxInput checked={Boolean(positionDialog.draft.is_current)} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, is_current: event.target.checked, end_date: event.target.checked ? "" : current.draft.end_date } }))} />
            Aktuelle Position
          </label>
        </div>
        <div className="mt-4 grid gap-4">
          <Field label="Beschreibung">
            <TextArea rows={2} value={positionDialog.draft.description || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, description: event.target.value } }))} />
          </Field>
          <Field label="Aufgaben">
            <TextArea rows={3} value={positionDialog.draft.tasks || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, tasks: event.target.value } }))} />
          </Field>
          <Field label="Erfolge / Achievements">
            <TextArea rows={2} value={positionDialog.draft.achievements || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, achievements: event.target.value } }))} />
          </Field>
          <Field label="Technologien">
            <TextInput value={positionDialog.draft.technologies || ""} onChange={(event) => setPositionDialog((current) => ({ ...current, draft: { ...current.draft, technologies: event.target.value } }))} />
          </Field>
        </div>
      </Modal>

      <Modal
        open={projectDialog.open}
        title={projectDialog.draft?.id ? "Projekt bearbeiten (STAR-Methode)" : "Projekt hinzufügen (STAR-Methode)"}
        onClose={() => setProjectDialog({ open: false, positionId: "", draft: EMPTY_PROJECT })}
        footer={<div className="flex justify-end gap-3"><Button variant="ghost" onClick={() => setProjectDialog({ open: false, positionId: "", draft: EMPTY_PROJECT })}>Abbrechen</Button><Button onClick={saveProject}>Speichern</Button></div>}
      >
        <div className="grid gap-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Projektname">
              <TextInput value={projectDialog.draft.name || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, name: event.target.value } }))} />
            </Field>
            <Field label="Rolle">
              <TextInput value={projectDialog.draft.role || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, role: event.target.value } }))} />
            </Field>
            <Field label="Dauer">
              <TextInput value={projectDialog.draft.duration || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, duration: event.target.value } }))} />
            </Field>
            <Field label="Technologien">
              <TextInput value={projectDialog.draft.technologies || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, technologies: event.target.value } }))} />
            </Field>
          </div>
          <Field label="Beschreibung">
            <TextArea rows={2} value={projectDialog.draft.description || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, description: event.target.value } }))} />
          </Field>
          <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-teal/70">STAR-Methode</p>
          <Field label="S - Situation">
            <TextArea rows={2} value={projectDialog.draft.situation || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, situation: event.target.value } }))} />
          </Field>
          <Field label="T - Task / Aufgabe">
            <TextArea rows={2} value={projectDialog.draft.task || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, task: event.target.value } }))} />
          </Field>
          <Field label="A - Action / Vorgehen">
            <TextArea rows={2} value={projectDialog.draft.action || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, action: event.target.value } }))} />
          </Field>
          <Field label="R - Result / Ergebnis">
            <TextArea rows={2} value={projectDialog.draft.result || ""} onChange={(event) => setProjectDialog((current) => ({ ...current, draft: { ...current.draft, result: event.target.value } }))} />
          </Field>
        </div>
      </Modal>

      <Modal
        open={educationDialog.open}
        title={educationDialog.draft.id ? "Ausbildung bearbeiten" : "Ausbildung hinzufügen"}
        onClose={() => setEducationDialog({ open: false, draft: EMPTY_EDUCATION })}
        footer={<div className="flex justify-end gap-3"><Button variant="ghost" onClick={() => setEducationDialog({ open: false, draft: EMPTY_EDUCATION })}>Abbrechen</Button><Button onClick={() => saveItem("education", educationDialog)}>Speichern</Button></div>}
      >
        <div className="grid gap-4 md:grid-cols-2">
          {[
            ["institution", "Institution"],
            ["degree", "Abschluss"],
            ["field_of_study", "Fachrichtung"],
            ["start_date", "Startdatum"],
            ["end_date", "Enddatum"],
          ].map(([key, label]) => (
            <Field key={key} label={label}>
              <TextInput value={educationDialog.draft[key] || ""} onChange={(event) => setEducationDialog((current) => ({ ...current, draft: { ...current.draft, [key]: event.target.value } }))} />
            </Field>
          ))}
        </div>
      </Modal>

      <Modal
        open={skillDialog.open}
        title={skillDialog.draft.id ? "Skill bearbeiten" : "Skill hinzufügen"}
        onClose={() => setSkillDialog({ open: false, draft: EMPTY_SKILL })}
        footer={(() => {
          const allSkills = profile?.skills || [];
          const curIdx = skillDialog.draft.id ? allSkills.findIndex((s) => s.id === skillDialog.draft.id) : -1;
          const hasPrev = curIdx > 0;
          const hasNext = curIdx >= 0 && curIdx < allSkills.length - 1;
          return (
            <div className="flex items-center justify-between gap-3">
              <div className="flex gap-1">
                {skillDialog.draft.id && allSkills.length > 1 ? (
                  <>
                    <Button variant="ghost" disabled={!hasPrev} onClick={() => setSkillDialog({ open: true, draft: buildSkillDraft(allSkills[curIdx - 1]) })}><ChevronLeft size={16} /></Button>
                    <span className="flex items-center text-xs text-muted/60 tabular-nums">{curIdx + 1}/{allSkills.length}</span>
                    <Button variant="ghost" disabled={!hasNext} onClick={() => setSkillDialog({ open: true, draft: buildSkillDraft(allSkills[curIdx + 1]) })}><ChevronRight size={16} /></Button>
                  </>
                ) : null}
              </div>
              <div className="flex gap-3">
                <Button variant="ghost" onClick={() => setSkillDialog({ open: false, draft: EMPTY_SKILL })}>Abbrechen</Button>
                <Button onClick={() => saveItem("skill", skillDialog)}>Speichern</Button>
              </div>
            </div>
          );
        })()}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Name">
            <TextInput value={skillDialog.draft.name} onChange={(event) => setSkillDialog((current) => ({ ...current, draft: { ...current.draft, name: event.target.value } }))} />
          </Field>
          <Field label="Kategorie">
            <SelectInput value={skillDialog.draft.category} onChange={(event) => setSkillDialog((current) => ({ ...current, draft: { ...current.draft, category: event.target.value } }))}>
              <option value="fachlich">Fachlich</option>
              <option value="tool">Tool</option>
              <option value="methodisch">Methodisch</option>
              <option value="soft_skill">Soft Skill</option>
              <option value="sprache">Sprache</option>
            </SelectInput>
          </Field>
          <Field label="Level (1–5)">
            <TextInput type="number" min="1" max="5" value={skillDialog.draft.level} onChange={(event) => {
              const raw = event.target.value;
              if (raw === "") { setSkillDialog((c) => ({ ...c, draft: { ...c.draft, level: "" } })); return; }
              const n = Number(raw);
              if (!Number.isFinite(n)) return;
              const clamped = Math.min(5, Math.max(1, Math.round(n)));
              setSkillDialog((c) => ({ ...c, draft: { ...c.draft, level: clamped } }));
            }} />
          </Field>
          <Field label="Jahre Erfahrung">
            <TextInput
              type="number"
              min="0"
              value={skillDialog.draft.years_experience}
              onChange={(event) => {
                const years = parseOptionalInt(event.target.value);
                const sinceYear = years === null ? "" : Math.min(currentYear, Math.max(1900, currentYear - Math.max(0, years)));
                setSkillDialog((current) => ({
                  ...current,
                  draft: {
                    ...current.draft,
                    years_experience: event.target.value,
                    since_year: sinceYear,
                  },
                }));
              }}
            />
          </Field>
          <Field label="Seit (Jahr)">
            <TextInput
              type="number"
              min="1900"
              max={String(currentYear)}
              value={skillDialog.draft.since_year}
              onChange={(event) => {
                const sinceYear = parseOptionalInt(event.target.value);
                const years = sinceYear === null ? "" : Math.max(0, currentYear - Math.min(currentYear, Math.max(1900, sinceYear)));
                setSkillDialog((current) => ({
                  ...current,
                  draft: {
                    ...current.draft,
                    since_year: event.target.value,
                    years_experience: years,
                  },
                }));
              }}
            />
          </Field>
        </div>
      </Modal>

      <Modal
        open={folderDialogOpen}
        title="Ordner importieren"
        description="Gib einen lokalen Ordnerpfad an, um bestehende Unterlagen zu importieren."
        onClose={() => setFolderDialogOpen(false)}
        footer={<div className="flex justify-end gap-3"><Button variant="ghost" onClick={() => setFolderDialogOpen(false)}>Abbrechen</Button><Button onClick={importFolder}>Import starten</Button></div>}
      >
        <Field label="Ordnerpfad">
          <TextInput value={folderPath} onChange={(event) => setFolderPath(event.target.value)} placeholder="C:\\Users\\...\\Bewerbungen" />
        </Field>
      </Modal>

      <Modal
        open={extractionDialog.open}
        title={`Extrahierte Infos${extractionDialog.document?.filename ? `: ${extractionDialog.document.filename}` : ""}`}
      description="Hier kannst du die aus dem Dokument erkannten Felder ansehen und nachträglich korrigieren."
        onClose={() =>
          setExtractionDialog({
            open: false,
            loading: false,
            saving: false,
            document: null,
            extraction: null,
            draftText: "{}",
          })
        }
        footer={
          <div className="flex justify-end gap-3">
            <Button
              variant="ghost"
              onClick={() =>
                setExtractionDialog({
                  open: false,
                  loading: false,
                  saving: false,
                  document: null,
                  extraction: null,
                  draftText: "{}",
                })
              }
            >
              Schließen
            </Button>
            <Button
              onClick={saveExtractionCorrections}
              disabled={extractionDialog.loading || extractionDialog.saving || !extractionDialog.extraction}
            >
              {extractionDialog.saving ? "Speichere..." : "Korrekturen speichern"}
            </Button>
          </div>
        }
      >
        {extractionDialog.loading ? (
          <p className="text-sm text-muted">Extraktion wird geladen...</p>
        ) : extractionDialog.extraction ? (
          <div className="grid gap-4">
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Status">
                <TextInput value={extractionDialog.extraction.status || ""} readOnly />
              </Field>
              <Field label="Typ">
                <TextInput value={extractionDialog.extraction.extraction_type || ""} readOnly />
              </Field>
              <Field label="Zeitpunkt">
                <TextInput value={formatDateTime(extractionDialog.extraction.created_at)} readOnly />
              </Field>
            </div>
            <Field label="Extrahierte Felder (JSON)">
              <TextArea
                rows={16}
                value={extractionDialog.draftText}
                onChange={(event) =>
                  setExtractionDialog((current) => ({ ...current, draftText: event.target.value }))
                }
              />
            </Field>
            <p className="text-xs text-muted">
              Unterstützte Korrekturen für direkte Übernahme: <code>persoenliche_daten</code> und <code>skills</code>.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted">
            Für dieses Dokument liegt noch keine Extraktion vor. Starte ggf. zuerst eine Analyse.
          </p>
        )}
      </Modal>
    </div>
  );
}

