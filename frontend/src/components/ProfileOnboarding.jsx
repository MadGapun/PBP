import { Check, Copy, Upload, X } from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { api, deleteRequest, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import SourceSelectionList from "@/components/SourceSelectionList";
import { analyzeUploadedDocuments, createFileSignature, uploadDocumentFile } from "@/document-upload";
import { extractDroppedFiles, GLOBAL_FILE_DRAG_STATE_EVENT, GLOBAL_FILE_DROP_EVENT } from "@/file-drop";
import { Badge, Button, Card, CheckboxInput } from "@/components/ui";
import { cn, copyToClipboard, docTypeLabel, firstIncompleteStepIndex, getKnownProfileFacts, sanitizeSkillName } from "@/utils";

const STEP_IDS = ["documents", "conversation", "sources", "jobs"];
const CONVERSATION_COMMAND = "/ersterfassung";
const JOB_WORKFLOW_COMMAND = "/jobsuche_workflow";
const CONVERSATION_STATE = { IDLE: "idle", ACTIVE: "active", COMPLETE: "complete" };

function normalizeConversationState(value) {
  return Object.values(CONVERSATION_STATE).includes(value) ? value : CONVERSATION_STATE.IDLE;
}

function buildJobSnapshot(rows) {
  if (!Array.isArray(rows) || !rows.length) return "";
  return rows
    .map((job, index) => {
      const fallbackIdentity = [job?.title || "", job?.company || "", job?.url || "", index].join("::");
      const identity = job?.hash || job?.id || job?.url || fallbackIdentity;
      return [
        identity,
        job?.is_active ? "1" : "0",
        job?.score ?? "",
        job?.updated_at || "",
        job?.found_at || "",
      ].join("|");
    })
    .sort()
    .join("||");
}

function normalizeSkillInput(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function uploadStatusMeta(status) {
  if (status === "uploading") return { tone: "sky", label: "Upload läuft" };
  if (status === "analyzing") return { tone: "sky", label: "Analyse läuft" };
  if (status === "done") return { tone: "success", label: "Analysiert" };
  if (status === "error") return { tone: "danger", label: "Fehler" };
  return { tone: "neutral", label: "Wartet" };
}

function docStatusMeta(status) {
  if (!status || status === "nicht_extrahiert") return { tone: "neutral", label: "Offen" };
  if (status === "analysiert_leer") return { tone: "neutral", label: "Analysiert (leer)" };
  return { tone: "success", label: "Analysiert" };
}

function createUploadEntry(file) {
  const name = file.webkitRelativePath || file.name;
  const basename = name.split("/").pop() || name;
  return {
    id: `upload_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`,
    signature: createFileSignature(file),
    name,
    basename,
    file,
    documentId: null,
    storedFilename: "",
    status: "queued",
    message: "Wartet auf Upload...",
  };
}

export default function ProfileOnboarding({ open, profile, workspace, onDismiss, onComplete }) {
  const { chrome, refreshChrome, pushToast } = useApp();

  const [sources, setSources] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loadingSupplemental, setLoadingSupplemental] = useState(false);
  const [activeStep, setActiveStep] = useState("documents");
  const [conversationState, setConversationState] = useState(CONVERSATION_STATE.IDLE);
  const [sourcesVisited, setSourcesVisited] = useState(false);
  const [jobWorkflowStarted, setJobWorkflowStarted] = useState(false);
  const [loginJobs, setLoginJobs] = useState({});
  const [uploadItems, setUploadItems] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [globalDragActive, setGlobalDragActive] = useState(false);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState([]);
  const [deletingDocuments, setDeletingDocuments] = useState(false);
  const [removingSkills, setRemovingSkills] = useState({});
  const [savingSkills, setSavingSkills] = useState({});
  const [editingSkillId, setEditingSkillId] = useState("");
  const [editingSkillName, setEditingSkillName] = useState("");
  const [newSkillName, setNewSkillName] = useState("");
  const [addingSkill, setAddingSkill] = useState(false);

  const loginPollersRef = useRef(new Map());
  const analysisQueueRef = useRef(Promise.resolve());
  const uploadItemsRef = useRef([]);
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const conversationSyncInFlightRef = useRef(false);
  const jobSyncInFlightRef = useRef(false);
  const jobSnapshotRef = useRef("");
  const lastAnalysisRefreshAtRef = useRef(0);
  const conversationStartedToastShownRef = useRef(false);
  const skillAutosaveTimerRef = useRef(null);

  const knownFacts = useMemo(() => getKnownProfileFacts(profile), [profile]);
  const conversationPreferenceKey = profile?.id ? `profile_onboarding_conversation_${profile.id}` : "";

  const documentCount = profile?.documents?.length || 0;
  const applicationCount = workspace?.applications?.total || 0;
  const activeSources = sources.filter((source) => source.active).length || workspace?.sources?.active || 0;
  const jobCount = jobs.length || workspace?.jobs?.active || 0;
  const missingAreas = workspace?.profile?.missing_areas || [];
  const profileSkills = (profile?.skills || [])
    .map((skill) => {
      const name = sanitizeSkillName(skill?.name);
      if (!name) return null;
      return {
        id: skill?.id,
        name,
        category: skill?.category || "fachlich",
        level: skill?.level ?? 3,
        years_experience: skill?.years_experience,
        last_used_year: skill?.last_used_year,
      };
    })
    .filter(Boolean);

  const stepState = {
    documentsDone: documentCount > 0 || applicationCount > 0 || uploadItems.length > 0,
    conversationDone: conversationState === CONVERSATION_STATE.COMPLETE,
    sourcesDone: sourcesVisited && activeSources > 0,
    jobsDone: jobCount > 0 || jobWorkflowStarted,
  };

  const steps = useMemo(
    () =>
      STEP_IDS.map((id, index) => ({
        id,
        number: index + 1,
        title:
          id === "documents"
            ? "Unterlagen"
            : id === "conversation"
              ? "Kennlerngespräch"
              : id === "sources"
                ? "Quellen"
                : "Jobsuche",
        done:
          id === "documents"
            ? stepState.documentsDone
            : id === "conversation"
              ? stepState.conversationDone
              : id === "sources"
                ? stepState.sourcesDone
                : stepState.jobsDone,
      })),
    [stepState.documentsDone, stepState.conversationDone, stepState.sourcesDone, stepState.jobsDone]
  );

  const initialStepIndex = firstIncompleteStepIndex(steps);
  const activeStepIndex = steps.findIndex((step) => step.id === activeStep);
  const completedSteps = steps.filter((step) => step.done).length;
  const canComplete = steps.every((step) => step.done);

  const loadSupplemental = useEffectEvent(async () => {
    if (!profile?.id) {
      jobSnapshotRef.current = "";
      startTransition(() => {
        setSources([]);
        setJobs([]);
        setLoadingSupplemental(false);
      });
      return;
    }
    try {
      const [sourceRows, activeJobs, conversationPreference] = await Promise.all([
        api("/api/sources"),
        api("/api/jobs?active=true"),
        api(`/api/user-preferences/${conversationPreferenceKey}`),
      ]);
      const normalizedJobs = Array.isArray(activeJobs) ? activeJobs : [];
      const normalizedConversationState = normalizeConversationState(conversationPreference?.value);
      conversationStartedToastShownRef.current =
        normalizedConversationState === CONVERSATION_STATE.ACTIVE ||
        normalizedConversationState === CONVERSATION_STATE.COMPLETE;
      jobSnapshotRef.current = buildJobSnapshot(normalizedJobs);
      startTransition(() => {
        setSources(sourceRows || []);
        setJobs(normalizedJobs);
        setConversationState(normalizedConversationState);
        setLoadingSupplemental(false);
      });
    } catch (error) {
      pushToast(`Onboarding-Daten konnten nicht geladen werden: ${error.message}`, "danger");
      startTransition(() => setLoadingSupplemental(false));
    }
  });

  useEffect(() => {
    if (!open) return;
    setLoadingSupplemental(true);
    loadSupplemental();
  }, [open, profile?.id]);

  useEffect(() => {
    if (!open) return;
    setActiveStep((current) => {
      if (!current || !steps.some((step) => step.id === current)) {
        return steps[initialStepIndex]?.id || "documents";
      }
      return current;
    });
  }, [open, initialStepIndex, steps]);

  useEffect(() => {
    if (!open) return;
    conversationStartedToastShownRef.current = false;
    jobSnapshotRef.current = "";
    if (skillAutosaveTimerRef.current) {
      window.clearTimeout(skillAutosaveTimerRef.current);
      skillAutosaveTimerRef.current = null;
    }
    startTransition(() => {
      setSourcesVisited(false);
      setJobWorkflowStarted(false);
      setUploadItems([]);
      setDragActive(false);
      setGlobalDragActive(false);
      setSelectedDocumentIds([]);
      setDeletingDocuments(false);
    });
    uploadItemsRef.current = [];
    setEditingSkillId("");
    setEditingSkillName("");
    setNewSkillName("");
    setAddingSkill(false);
    setSavingSkills({});
    setRemovingSkills({});
  }, [open, profile?.id]);

  useEffect(() => {
    uploadItemsRef.current = uploadItems;
  }, [uploadItems]);

  useEffect(() => {
    if (!open) return undefined;
    function consumeGlobalDragState(event) {
      setGlobalDragActive(Boolean(event?.detail?.active));
    }

    function consumeGlobalDrop(event) {
      const files = event?.detail?.files;
      if (!files?.length) return;
      event.preventDefault();
      setActiveStep("documents");
      addFiles(files);
    }
    window.addEventListener(GLOBAL_FILE_DRAG_STATE_EVENT, consumeGlobalDragState);
    window.addEventListener(GLOBAL_FILE_DROP_EVENT, consumeGlobalDrop);
    return () => {
      window.removeEventListener(GLOBAL_FILE_DRAG_STATE_EVENT, consumeGlobalDragState);
      window.removeEventListener(GLOBAL_FILE_DROP_EVENT, consumeGlobalDrop);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (activeStep === "sources") setSourcesVisited(true);
  }, [open, activeStep]);

  useEffect(() => {
    if (!open) return undefined;
    document.body.classList.add("overflow-hidden");
    return () => document.body.classList.remove("overflow-hidden");
  }, [open]);

  useEffect(() => {
    return () => {
      loginPollersRef.current.forEach((handle) => window.clearInterval(handle));
      loginPollersRef.current.clear();
      if (skillAutosaveTimerRef.current) {
        window.clearTimeout(skillAutosaveTimerRef.current);
      }
    };
  }, []);

  const pollConversationState = useEffectEvent(async () => {
    if (!conversationPreferenceKey) return;
    try {
      const response = await api(`/api/user-preferences/${conversationPreferenceKey}`);
      const nextState = normalizeConversationState(response?.value);
      if (nextState === conversationState) return;
      startTransition(() => setConversationState(nextState));
      if (nextState === CONVERSATION_STATE.ACTIVE && !conversationStartedToastShownRef.current) {
        conversationStartedToastShownRef.current = true;
        pushToast("Kennlerngespräch gestartet.", "sky");
      }
      if (nextState === CONVERSATION_STATE.COMPLETE) {
        conversationStartedToastShownRef.current = true;
        if (activeStep === "conversation") {
          setActiveStep("sources");
        }
        await refreshChrome();
        pushToast("Kennlerngespräch abgeschlossen. Weiter zu Quellen.", "success");
      }
    } catch {
      // bewusst still
    }
  });

  const syncProfileDuringConversation = useEffectEvent(async () => {
    if (conversationSyncInFlightRef.current) return;
    conversationSyncInFlightRef.current = true;
    try {
      await refreshChrome({ quiet: true });
    } catch {
      // bewusst still
    } finally {
      conversationSyncInFlightRef.current = false;
    }
  });

  const syncJobsDuringWorkflow = useEffectEvent(async () => {
    if (jobSyncInFlightRef.current) return;
    jobSyncInFlightRef.current = true;
    try {
      const nextJobs = await api("/api/jobs?active=true");
      const normalized = Array.isArray(nextJobs) ? nextJobs : [];
      const nextSnapshot = buildJobSnapshot(normalized);
      const changed = nextSnapshot !== jobSnapshotRef.current;

      if (changed) {
        jobSnapshotRef.current = nextSnapshot;
        startTransition(() => setJobs(normalized));
      }
      if (normalized.length > 0 && !jobWorkflowStarted) {
        startTransition(() => setJobWorkflowStarted(true));
      }
    } catch {
      // bewusst still
    } finally {
      jobSyncInFlightRef.current = false;
    }
  });

  useEffect(() => {
    if (!open || !conversationPreferenceKey || conversationState === CONVERSATION_STATE.COMPLETE) {
      return undefined;
    }
    pollConversationState();
    const handle = window.setInterval(() => {
      pollConversationState();
    }, 2000);
    return () => window.clearInterval(handle);
  }, [open, conversationState, conversationPreferenceKey, pollConversationState]);

  useEffect(() => {
    if (!open || conversationState !== CONVERSATION_STATE.ACTIVE || !conversationPreferenceKey) {
      return undefined;
    }
    syncProfileDuringConversation();
    const handle = window.setInterval(() => {
      syncProfileDuringConversation();
    }, 2000);
    return () => {
      window.clearInterval(handle);
      conversationSyncInFlightRef.current = false;
    };
  }, [open, conversationState, conversationPreferenceKey, syncProfileDuringConversation]);

  useEffect(() => {
    if (!open || !profile?.id) {
      return undefined;
    }
    syncJobsDuringWorkflow();
    const handle = window.setInterval(() => {
      syncJobsDuringWorkflow();
    }, 2000);
    return () => {
      window.clearInterval(handle);
      jobSyncInFlightRef.current = false;
    };
  }, [open, profile?.id, syncJobsDuringWorkflow]);

  const profileDocumentIds = useMemo(
    () => new Set((profile?.documents || []).map((doc) => doc.id).filter(Boolean)),
    [profile?.documents]
  );
  const profileDocumentFilenames = useMemo(
    () => new Set((profile?.documents || []).map((doc) => doc.filename).filter(Boolean)),
    [profile?.documents]
  );
  const visibleUploadItems = useMemo(
    () =>
      uploadItems.filter((item) => {
        if (item.status !== "done") return true;
        const hasIdMatch = item.documentId && profileDocumentIds.has(item.documentId);
        const hasFilenameMatch = item.storedFilename && profileDocumentFilenames.has(item.storedFilename);
        return !(hasIdMatch || hasFilenameMatch);
      }),
    [uploadItems, profileDocumentIds, profileDocumentFilenames]
  );
  const docsFromProfile = useMemo(() => profile?.documents || [], [profile?.documents]);
  const visibleDocs = useMemo(() => docsFromProfile, [docsFromProfile]);
  const selectedDocCount = docsFromProfile.filter((doc) => selectedDocumentIds.includes(doc.id)).length;
  const allDocsSelected =
    docsFromProfile.length > 0 && docsFromProfile.every((doc) => selectedDocumentIds.includes(doc.id));
  const showDocRows = visibleUploadItems.length > 0 || docsFromProfile.length > 0;

  useEffect(() => {
    const availableIds = new Set(docsFromProfile.map((doc) => doc.id));
    setSelectedDocumentIds((current) => {
      const next = current.filter((docId) => availableIds.has(docId));
      if (next.length === current.length && next.every((value, index) => value === current[index])) {
        return current;
      }
      return next;
    });
  }, [docsFromProfile]);

  if (!open || !profile) return null;

  function updateUploadItem(uploadId, patch) {
    startTransition(() => {
      setUploadItems((current) => {
        const next = current.map((item) => (item.id === uploadId ? { ...item, ...patch } : item));
        uploadItemsRef.current = next;
        return next;
      });
    });
  }

  async function refreshAfterAnalysis(options = {}) {
    const force = Boolean(options?.force);
    const now = Date.now();
    const minIntervalMs = 1800;
    if (!force && now - lastAnalysisRefreshAtRef.current < minIntervalMs) {
      return;
    }
    lastAnalysisRefreshAtRef.current = now;
    try {
      await refreshChrome({ quiet: true });
    } catch {
      // bewusst still: Analyse-Ergebnis bleibt gültig, auch wenn UI-Refresh kurz fehlschlaegt.
    }
  }

  function queueAnalysis(uploadId) {
    analysisQueueRef.current = analysisQueueRef.current
      .then(async () => {
        updateUploadItem(uploadId, { status: "analyzing", message: "Analyse läuft..." });
        const result = await analyzeUploadedDocuments();
        if (result?.status === "keine_daten") {
          updateUploadItem(uploadId, {
            status: "done",
            message: result?.nachricht || "Analyse abgeschlossen (keine neuen Profildaten erkannt).",
          });
        } else {
          updateUploadItem(uploadId, {
            status: "done",
            message: result?.nachricht || "Analyse abgeschlossen.",
          });
        }
        const hasPendingUploads = uploadItemsRef.current.some((item) =>
          item.status === "queued" || item.status === "uploading" || item.status === "analyzing"
        );
        await refreshAfterAnalysis({ force: !hasPendingUploads });
      })
      .catch((error) => {
        updateUploadItem(uploadId, { status: "error", message: `Analyse fehlgeschlagen: ${error.message}` });
      });
  }

  async function processUpload(entry) {
    try {
      updateUploadItem(entry.id, { status: "uploading", message: "Upload läuft..." });
      const uploadResponse = await uploadDocumentFile(entry.file);
      updateUploadItem(entry.id, {
        status: "queued",
        message: "Hochgeladen. Warte auf Analyse...",
        documentId: uploadResponse?.id || null,
        storedFilename: uploadResponse?.filename || entry.basename || entry.name,
      });
      queueAnalysis(entry.id);
    } catch (error) {
      updateUploadItem(entry.id, { status: "error", message: `Upload fehlgeschlagen: ${error.message}` });
      pushToast(`Upload fehlgeschlagen (${entry.name}): ${error.message}`, "danger");
    }
  }

  function addFiles(filesLike) {
    const files = Array.from(filesLike || []).filter((file) => file && file.name);
    if (!files.length) return;
    const signatures = new Set(uploadItemsRef.current.map((item) => item.signature));
    const accepted = [];
    for (const file of files) {
      const next = createUploadEntry(file);
      if (signatures.has(next.signature)) continue;
      signatures.add(next.signature);
      accepted.push(next);
    }
    if (!accepted.length) {
      pushToast("Diese Dateien sind bereits enthalten.", "neutral");
      return;
    }
    uploadItemsRef.current = [...uploadItemsRef.current, ...accepted];
    setUploadItems((current) => [...current, ...accepted]);
    accepted.forEach((entry) => {
      void processUpload(entry);
    });
  }

  function toggleDocumentSelection(docId, checked) {
    if (!docId) return;
    setSelectedDocumentIds((current) => {
      const hasId = current.includes(docId);
      if (checked && !hasId) return [...current, docId];
      if (!checked && hasId) return current.filter((id) => id !== docId);
      return current;
    });
  }

  function toggleSelectAllDocuments() {
    const allDocIds = docsFromProfile.map((doc) => doc.id);
    setSelectedDocumentIds((current) => {
      if (allDocsSelected) {
        return current.filter((id) => !allDocIds.includes(id));
      }
      const next = new Set(current);
      allDocIds.forEach((id) => next.add(id));
      return [...next];
    });
  }

  async function removeSelectedDocuments() {
    const selectedDocs = docsFromProfile.filter((doc) => selectedDocumentIds.includes(doc.id));
    if (!selectedDocs.length) return;

    const count = selectedDocs.length;
    const confirmed = window.confirm(
      `${count} Datei(en) wirklich entfernen?\n\n` +
        "Die zugehörigen Extraktions-/Analyse-Einträge dieser Datei(en) werden ebenfalls gelöscht."
    );
    if (!confirmed) return;

    setDeletingDocuments(true);
    try {
      const results = await Promise.allSettled(
        selectedDocs.map((doc) => deleteRequest(`/api/document/${doc.id}`))
      );
      const failed = results.filter((result) => result.status === "rejected");

      const deletedIds = new Set(selectedDocs.map((doc) => doc.id));
      const deletedNames = new Set(selectedDocs.map((doc) => doc.filename));
      setUploadItems((current) =>
        current.filter((item) => {
          if (item.documentId && deletedIds.has(item.documentId)) return false;
          const itemName = item.storedFilename || item.basename || item.name.split("/").pop() || item.name;
          return !deletedNames.has(itemName);
        })
      );
      setSelectedDocumentIds([]);
      await refreshChrome();

      if (failed.length) {
        pushToast(
          `${count - failed.length} Datei(en) entfernt, ${failed.length} Datei(en) konnten nicht gelöscht werden.`,
          "danger"
        );
        return;
      }
      pushToast(`${count} Datei(en) inklusive Analyse-Einträgen entfernt.`, "success");
    } catch (error) {
      pushToast(`Dateien konnten nicht entfernt werden: ${error.message}`, "danger");
    } finally {
      setDeletingDocuments(false);
    }
  }

  async function copyConversationCommand() {
    try {
      await copyToClipboard(CONVERSATION_COMMAND);
      if (profile?.id) {
        startTransition(() => setConversationState(CONVERSATION_STATE.ACTIVE));
        await Promise.all([
          postJson(`/api/user-preferences/profile_onboarding_started_${profile.id}`, { value: true }),
          postJson(`/api/user-preferences/profile_onboarding_completed_${profile.id}`, { value: false }),
          postJson(`/api/user-preferences/profile_onboarding_dismissed_${profile.id}`, { value: false }),
          postJson(`/api/user-preferences/profile_onboarding_conversation_${profile.id}`, { value: CONVERSATION_STATE.ACTIVE }),
        ]);
      }
      pushToast("Befehl kopiert — füge ihn mit Strg+V in Claude ein.", "success", { duration: 7200 });
    } catch (error) {
      pushToast(`Befehl konnte nicht kopiert werden: ${error.message}`, "danger");
    }
  }

  function trackLoginJob(sourceKey, jobId) {
    const previous = loginPollersRef.current.get(sourceKey);
    if (previous) window.clearInterval(previous);
    const handle = window.setInterval(async () => {
      try {
        const job = await api(`/api/background-jobs/${jobId}`);
        startTransition(() => {
          setLoginJobs((current) => ({
            ...current,
            [sourceKey]: { status: job.status, message: job.message || "", jobId },
          }));
        });
        if (job.status !== "running") {
          window.clearInterval(handle);
          loginPollersRef.current.delete(sourceKey);
          pushToast(job.message || "Login abgeschlossen.", job.status === "fehler" ? "danger" : "success");
        }
      } catch (error) {
        window.clearInterval(handle);
        loginPollersRef.current.delete(sourceKey);
        pushToast(`Login-Status konnte nicht geladen werden: ${error.message}`, "danger");
      }
    }, 1500);
    loginPollersRef.current.set(sourceKey, handle);
  }

  async function startSourceLogin(source, options = {}) {
    if (!options.force && loginJobs[source.key]?.status === "running") {
      return;
    }
    try {
      const response = await postJson(`/api/sources/${source.key}/login`, {});
      startTransition(() => {
        setLoginJobs((current) => ({
          ...current,
          [source.key]: { status: "running", message: response.nachricht || "", jobId: response.job_id },
        }));
      });
      trackLoginJob(source.key, response.job_id);
      pushToast(response.nachricht || `${source.name}: Login gestartet.`, "sky");
    } catch (error) {
      pushToast(`Login konnte nicht gestartet werden: ${error.message}`, "danger");
    }
  }

  async function toggleSource(source, checked, options = {}) {
    const previous = sources;
    const next = sources.map((item) => (item.key === source.key ? { ...item, active: checked } : item));
    startTransition(() => setSources(next));
    try {
      await postJson("/api/sources", {
        active_sources: next.filter((item) => item.active).map((item) => item.key),
      });
      const shouldStartLogin = Boolean(
        options.autoStartLogin ?? (checked && source.login_erforderlich)
      );
      if (shouldStartLogin) {
        await startSourceLogin(source);
      }
    } catch (error) {
      startTransition(() => setSources(previous));
      pushToast(`Quelle konnte nicht aktualisiert werden: ${error.message}`, "danger");
    }
  }

  async function copyJobWorkflow() {
    try {
      await copyToClipboard(JOB_WORKFLOW_COMMAND);
      setJobWorkflowStarted(true);
      void syncJobsDuringWorkflow();
      pushToast("Befehl kopiert — füge ihn mit Strg+V in Claude ein.", "success", { duration: 7200 });
    } catch (error) {
      pushToast(`Befehl konnte nicht kopiert werden: ${error.message}`, "danger");
    }
  }

  async function removeSkill(skill) {
    if (!skill?.id) return;
    startTransition(() => {
      setRemovingSkills((current) => ({ ...current, [skill.id]: true }));
    });
    try {
      await deleteRequest(`/api/skill/${skill.id}`);
      await refreshChrome();
      if (editingSkillId === skill.id) {
        setEditingSkillId("");
        setEditingSkillName("");
      }
      pushToast(`Skill entfernt: ${skill.name}`, "success");
    } catch (error) {
      pushToast(`Skill konnte nicht entfernt werden: ${error.message}`, "danger");
    } finally {
      startTransition(() => {
        setRemovingSkills((current) => ({ ...current, [skill.id]: false }));
      });
    }
  }

  function beginSkillEdit(skill) {
    if (!skill?.id) return;
    setEditingSkillId(skill.id);
    setEditingSkillName(skill.name || "");
  }

  function cancelSkillEdit() {
    if (skillAutosaveTimerRef.current) {
      window.clearTimeout(skillAutosaveTimerRef.current);
      skillAutosaveTimerRef.current = null;
    }
    setEditingSkillId("");
    setEditingSkillName("");
  }

  async function saveSkillEdit(skill, options = {}) {
    if (!skill?.id) return;
    const closeEditor = options.closeEditor !== false;
    const silent = Boolean(options.silent);
    const notifySuccess = options.notifySuccess ?? !silent;
    const nextValue = options.value ?? editingSkillName;
    const cleaned = normalizeSkillInput(sanitizeSkillName(nextValue));
    if (!cleaned) {
      if (!silent) {
        pushToast("Skill-Name darf nicht leer sein.", "danger");
      }
      return;
    }

    const alreadyExists = profileSkills.some(
      (item) => item.id !== skill.id && item.name.toLocaleLowerCase("de-DE") === cleaned.toLocaleLowerCase("de-DE")
    );
    if (alreadyExists) {
      if (!silent) {
        pushToast("Skill ist bereits vorhanden.", "neutral");
      }
      return;
    }

    const currentName = normalizeSkillInput(sanitizeSkillName(skill.name));
    if (currentName.toLocaleLowerCase("de-DE") === cleaned.toLocaleLowerCase("de-DE")) {
      if (closeEditor) {
        setEditingSkillId("");
        setEditingSkillName("");
      }
      return;
    }

    startTransition(() => {
      setSavingSkills((current) => ({ ...current, [skill.id]: true }));
    });
    try {
      await putJson(`/api/skill/${skill.id}`, {
        name: cleaned,
        category: skill.category || "fachlich",
        level: skill.level ?? 3,
        years_experience: skill.years_experience,
        last_used_year: skill.last_used_year,
      });
      await refreshChrome({ quiet: true });
      if (closeEditor) {
        setEditingSkillId("");
        setEditingSkillName("");
      }
      if (notifySuccess) {
        pushToast(`Skill aktualisiert: ${cleaned}`, "success");
      }
    } catch (error) {
      if (!silent) {
        pushToast(`Skill konnte nicht aktualisiert werden: ${error.message}`, "danger");
      }
    } finally {
      startTransition(() => {
        setSavingSkills((current) => ({ ...current, [skill.id]: false }));
      });
    }
  }

  function scheduleSkillAutosave(skill, nextValue) {
    if (!skill?.id) return;
    if (skillAutosaveTimerRef.current) {
      window.clearTimeout(skillAutosaveTimerRef.current);
    }
    skillAutosaveTimerRef.current = window.setTimeout(() => {
      void saveSkillEdit(skill, {
        value: nextValue,
        closeEditor: false,
        silent: true,
        notifySuccess: false,
      });
    }, 550);
  }

  async function finishSkillEdit(skill) {
    if (skillAutosaveTimerRef.current) {
      window.clearTimeout(skillAutosaveTimerRef.current);
      skillAutosaveTimerRef.current = null;
    }
    await saveSkillEdit(skill, { closeEditor: true, notifySuccess: false });
  }

  async function addSkillManually() {
    const cleaned = normalizeSkillInput(sanitizeSkillName(newSkillName));
    if (!cleaned) {
      pushToast("Bitte einen gültigen Skill-Namen eingeben.", "danger");
      return;
    }
    const alreadyExists = profileSkills.some(
      (item) => item.name.toLocaleLowerCase("de-DE") === cleaned.toLocaleLowerCase("de-DE")
    );
    if (alreadyExists) {
      pushToast("Skill ist bereits vorhanden.", "neutral");
      setNewSkillName("");
      return;
    }

    setAddingSkill(true);
    try {
      await postJson("/api/skill", { name: cleaned, category: "fachlich", level: 3 });
      await refreshChrome({ quiet: true });
      setNewSkillName("");
      pushToast(`Skill hinzugefügt: ${cleaned}`, "success");
    } catch (error) {
      pushToast(`Skill konnte nicht hinzugefügt werden: ${error.message}`, "danger");
    } finally {
      setAddingSkill(false);
    }
  }

  function skipStep() {
    if (!window.confirm("Das komplette Setup wirklich überspringen?")) return;
    onDismiss();
  }

  function goNext() {
    const next = steps[activeStepIndex + 1];
    if (next) setActiveStep(next.id);
  }

  const documentsPanel = (
    <Card className="glass-card-soft rounded-xl p-6 shadow-none sm:p-8">
      <p className="text-sm text-muted">
        Lade Lebensläufe, Anschreiben, Zeugnisse oder bestehende Unterlagen hoch, damit direkt eine erste Analyse startet.
      </p>
      <div className="mt-5 rounded-xl border-2 border-dashed border-white/12 bg-white/[0.04] p-4 sm:p-6">
        <div
          className={cn(
            "rounded-xl border border-white/10 bg-sky/10 px-4 py-8 text-center transition",
            (dragActive || globalDragActive) && "border-sky/60 bg-sky/12 ring-2 ring-sky/35"
          )}
          data-global-drop-target="profile-documents"
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            if (event.currentTarget.contains(event.relatedTarget)) return;
            setDragActive(false);
          }}
          onDrop={async (event) => {
            event.preventDefault();
            event.stopPropagation();
            setDragActive(false);
            const files = await extractDroppedFiles(event.dataTransfer);
            addFiles(files);
          }}
        >
          <p className="text-sm font-semibold text-ink">Dateien oder Ordner hier hineinziehen</p>
          <p className="mt-2 text-xs text-muted">Mehrfach-Upload und späteres Nachladen bleibt aktiv.</p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <Button type="button" variant="secondary" onClick={() => fileInputRef.current?.click()}>
              <Upload size={15} />
              Dateien auswählen
            </Button>
            <Button size="sm" variant="ghost" type="button" onClick={() => folderInputRef.current?.click()}>
              Ordner auswählen
            </Button>
          </div>
          <input
            ref={fileInputRef}
            className="hidden"
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt,.md,.csv,.json,.xml,.rtf,.msg,.eml"
            onChange={(event) => {
              addFiles(event.target.files);
              event.target.value = "";
            }}
          />
          <input
            ref={folderInputRef}
            className="hidden"
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt,.md,.csv,.json,.xml,.rtf,.msg,.eml"
            webkitdirectory=""
            directory=""
            onChange={(event) => {
              addFiles(event.target.files);
              event.target.value = "";
            }}
          />
        </div>
        {showDocRows ? (
          <div className="mt-4 grid gap-2">
            {visibleDocs.length ? (
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2">
                <p className="text-xs text-muted">
                  {selectedDocCount}/{visibleDocs.length} markiert
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="ghost" onClick={toggleSelectAllDocuments}>
                    {allDocsSelected ? "Auswahl aufheben" : "Alle markieren"}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={!selectedDocCount || deletingDocuments}
                    onClick={removeSelectedDocuments}
                  >
                    {deletingDocuments ? "Lösche..." : "Ausgewählte entfernen"}
                  </Button>
                </div>
              </div>
            ) : null}
            {visibleUploadItems.map((item) => {
              const status = uploadStatusMeta(item.status);
              return (
                <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{item.name}</p>
                    <p className="mt-1 text-xs text-muted">{item.message}</p>
                  </div>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </div>
              );
            })}
            {visibleDocs.map((doc) => {
              const status = docStatusMeta(doc.extraction_status);
              const checked = selectedDocumentIds.includes(doc.id);
              return (
                <div key={doc.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/4 px-4 py-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <CheckboxInput
                      checked={checked}
                      onChange={(event) => toggleDocumentSelection(doc.id, event.target.checked)}
                      disabled={deletingDocuments}
                      aria-label={`${doc.filename} markieren`}
                      className="shrink-0 self-center"
                    />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{doc.filename}</p>
                      <p className="mt-1 text-xs text-muted">{docTypeLabel(doc.doc_type)}</p>
                    </div>
                  </div>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </Card>
  );

  const mcpConnection = chrome?.status?.mcp_connection;
  const mcpConnected = mcpConnection?.status === "connected";

  const conversationPanel = (
    <Card className="glass-card-soft rounded-xl p-6 shadow-none sm:p-8">
      <p className="text-sm text-muted">
        Um offene Punkte zu klären, führst du jetzt in Claude ein kurzes Kennlerngespräch.
      </p>

      {/* #274: Verbindungs-Verifikation */}
      {mcpConnection && !mcpConnected && (
        <div className="mt-4 rounded-xl border border-amber/30 bg-amber/5 p-4">
          <p className="text-sm font-semibold text-amber">Claude Verbindung pr&uuml;fen</p>
          <p className="mt-1 text-xs text-muted">
            &Ouml;ffne Claude Desktop und schau unten links: Siehst du ein Hammer-Symbol mit einer Zahl?
          </p>
          <div className="mt-2 space-y-1 text-xs text-muted">
            <p>Falls nicht:</p>
            <p>1. Ist das PBP-Konsolenfenster noch offen? (Nicht schlie&szlig;en!)</p>
            <p>2. Claude Desktop beenden: Rechtsklick auf Symbol in Taskleiste &rarr; Beenden</p>
            <p>3. Claude Desktop neu starten</p>
            <p>4. Hammer-Symbol unten links pr&uuml;fen</p>
          </div>
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button variant="secondary" onClick={copyConversationCommand}>
          <Copy size={15} />
          /ersterfassung kopieren
        </Button>
        <Badge tone={conversationState === CONVERSATION_STATE.COMPLETE ? "success" : conversationState === CONVERSATION_STATE.ACTIVE ? "sky" : "neutral"}>
          {conversationState === CONVERSATION_STATE.COMPLETE ? "Abgeschlossen" : conversationState === CONVERSATION_STATE.ACTIVE ? "Läuft" : "Noch offen"}
        </Badge>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-white/4 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Bekannt</p>
          <div className="mt-2 grid gap-2">
            {knownFacts.length
              ? knownFacts.map((fact) => (
                  <p key={fact} className="text-sm text-ink">
                    {fact}
                  </p>
                ))
              : <p className="text-sm text-muted">Noch keine belastbaren Angaben vorhanden.</p>}
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Offen</p>
          <div className="mt-2 grid gap-2">
            {missingAreas.length
              ? missingAreas.map((area) => (
                  <p key={area} className="text-sm text-ink">
                    {area}
                  </p>
                ))
              : <p className="text-sm text-muted">Aktuell sind keine großen Lücken offen.</p>}
          </div>
        </div>
      </div>
      <div className="mt-3 rounded-xl border border-white/10 bg-white/4 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Skills</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={newSkillName}
            onChange={(event) => setNewSkillName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              if (!addingSkill) void addSkillManually();
            }}
            placeholder="Neuen Skill hinzufügen"
            className="h-8 min-w-[15rem] rounded-lg border border-white/15 bg-white/[0.04] px-3 text-xs text-ink placeholder:text-muted focus:border-sky/45 focus:outline-none"
          />
          <Button size="sm" type="button" variant="secondary" onClick={addSkillManually} disabled={addingSkill}>
            {addingSkill ? "Füge hinzu..." : "Skill hinzufügen"}
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {profileSkills.length
            ? profileSkills.map((skill) => (
                <span
                  key={skill.id || skill.name}
                  className="inline-flex items-center gap-2 rounded-full border border-sky/20 bg-sky/10 px-2 py-1 text-xs font-semibold text-sky"
                >
                  {editingSkillId === skill.id ? (
                    <>
                      <input
                        type="text"
                        value={editingSkillName}
                        onChange={(event) => {
                          const next = event.target.value;
                          setEditingSkillName(next);
                          scheduleSkillAutosave(skill, next);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void finishSkillEdit(skill);
                          }
                          if (event.key === "Escape") {
                            event.preventDefault();
                            cancelSkillEdit();
                          }
                        }}
                        className="h-7 w-44 rounded-md border border-white/20 bg-white/[0.08] px-2 text-xs text-ink focus:border-sky/45 focus:outline-none"
                        aria-label={`Skill bearbeiten: ${skill.name}`}
                      />
                      <Button
                        size="sm"
                        variant="ghost"
                        type="button"
                        onClick={() => finishSkillEdit(skill)}
                        disabled={Boolean(savingSkills[skill.id])}
                      >
                        {savingSkills[skill.id] ? "..." : "Fertig"}
                      </Button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="rounded px-1 text-left text-xs font-semibold text-sky transition hover:bg-white/10"
                        onClick={() => beginSkillEdit(skill)}
                        title={`Skill bearbeiten: ${skill.name}`}
                        aria-label={`Skill bearbeiten: ${skill.name}`}
                      >
                        {skill.name}
                      </button>
                      <button
                        type="button"
                        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-sky/85 transition hover:bg-white/10 hover:text-sky"
                        onClick={(event) => {
                          event.stopPropagation();
                          void removeSkill(skill);
                        }}
                        disabled={!skill.id || Boolean(removingSkills[skill.id])}
                        title={skill.id ? `Skill entfernen: ${skill.name}` : "Skill kann nicht entfernt werden"}
                        aria-label={`Skill entfernen: ${skill.name}`}
                      >
                        <X size={10} />
                      </button>
                    </>
                  )}
                </span>
              ))
            : <p className="text-sm text-muted">Noch keine Skills im Profil vorhanden.</p>}
        </div>
      </div>
    </Card>
  );

  const hasActiveSources = sources.some((s) => s.active);
  const sourcesPanel = (
    <Card className="glass-card-soft rounded-xl p-6 shadow-none sm:p-8">
      {!hasActiveSources ? (
        <p className="text-sm text-muted">
          Wähle mindestens eine Quelle aus, die durchsucht werden soll.
        </p>
      ) : null}
      <div className="mt-5">
        <SourceSelectionList sources={sources} loginJobs={loginJobs} onToggle={toggleSource} onStartLogin={startSourceLogin} />
      </div>
    </Card>
  );

  const jobsPanel = (
    <Card className="glass-card-soft rounded-xl p-6 shadow-none sm:p-8">
      <p className="text-sm text-muted">
        Starte jetzt den Jobsuche-Workflow in Claude.
      </p>
      <div className="mt-5 grid gap-3 sm:max-w-lg">
        <Button variant="secondary" onClick={copyJobWorkflow}>
          <Copy size={15} />
          /jobsuche_workflow kopieren
        </Button>
      </div>
      <p className="mt-4 text-xs text-muted">Aktuell erkannte Jobs: {jobCount}</p>
    </Card>
  );

  const panel = activeStep === "documents"
    ? documentsPanel
    : activeStep === "conversation"
      ? conversationPanel
      : activeStep === "sources"
        ? sourcesPanel
        : jobsPanel;

  const footerWarning = activeStep === "conversation" && conversationState === CONVERSATION_STATE.ACTIVE
    ? "Kennlerngespräch läuft gerade. Weiter nur, wenn du bewusst unterbrechen willst."
    : null;

  return createPortal(
    <div
      id="profile-onboarding-overlay"
      className="glass-overlay fixed inset-0 z-[980] flex items-start justify-center overflow-y-auto px-4 py-6 sm:px-6"
    >
      <div className="glass-card-strong w-full max-w-6xl rounded-2xl p-6 sm:p-8">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-3xl font-semibold text-ink sm:text-4xl">
              Willkommen {profile.name || "ohne Namen"}
            </h2>
            <p className="mt-2 text-sm text-muted">Richte dein Profil in vier kurzen Schritten ein.</p>
          </div>
          <Badge tone={canComplete ? "success" : "sky"}>
            {completedSteps}/{steps.length} Schritte
          </Badge>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          {steps.map((step) => (
            <button
              key={step.id}
              type="button"
              className={cn(
                "glass-tab flex min-h-[4.25rem] items-center justify-between rounded-xl px-4 py-3 text-left transition",
                activeStep === step.id && "glass-tab-active"
              )}
              onClick={() => setActiveStep(step.id)}
            >
              <span className="text-sm font-semibold text-ink/90">
                {step.number}. {step.title}
              </span>
              {step.done ? (
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-teal/20 text-teal">
                  <Check size={13} />
                </span>
              ) : null}
            </button>
          ))}
        </div>

        <div className="mt-6">
          {loadingSupplemental ? (
            <Card className="glass-card-soft rounded-xl shadow-none">
              <div className="flex min-h-40 items-center justify-center gap-3 text-sm text-muted">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/12 border-t-teal" />
                Onboarding wird vorbereitet...
              </div>
            </Card>
          ) : (
            panel
          )}
        </div>

        <div
          className={cn(
            "mt-6 flex flex-wrap items-center gap-3 border-t border-white/10 pt-5",
            footerWarning ? "justify-between" : "justify-end"
          )}
        >
          {footerWarning ? <p className="text-sm text-muted">{footerWarning}</p> : null}
          <div className="flex flex-wrap gap-3">
            {activeStepIndex < steps.length - 1 ? (
              <>
                <Button variant="secondary" onClick={skipStep}>
                  Überspringen
                </Button>
                <Button onClick={goNext}>
                  {activeStep === "conversation" && conversationState === CONVERSATION_STATE.ACTIVE
                    ? "Vorzeitig weiter"
                    : "Weiter"}
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" onClick={onDismiss}>
                  Schließen
                </Button>
                <Button onClick={onComplete} disabled={!canComplete}>
                  <Check size={15} />
                  Onboarding abschliessen
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

