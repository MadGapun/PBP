import { useEffect, useEffectEvent, useRef } from "react";

import { analyzeUploadedDocuments, createFileSignature, isEmailFile, uploadDocumentFile, uploadEmailFile } from "@/document-upload";
import {
  extractDroppedFiles,
  GLOBAL_FILE_DRAG_STATE_EVENT,
  GLOBAL_FILE_DROP_EVENT,
  isFileDragEvent,
} from "@/file-drop";

export default function GlobalDocumentDropZone({ hasActiveProfile, profileName, refreshChrome, pushToast }) {
  const dragDepthRef = useRef(0);
  const busyRef = useRef(false);
  const dragActiveRef = useRef(false);

  const setDragState = useEffectEvent((nextActive) => {
    const active = Boolean(nextActive);
    if (dragActiveRef.current === active) return;
    dragActiveRef.current = active;
    window.dispatchEvent(new CustomEvent(GLOBAL_FILE_DRAG_STATE_EVENT, { detail: { active } }));
  });

  const hideOverlay = useEffectEvent(() => {
    dragDepthRef.current = 0;
    setDragState(false);
  });

  const processFiles = useEffectEvent(async (files) => {
    if (busyRef.current) {
      pushToast("Es wird bereits ein Upload verarbeitet. Bitte kurz warten.", "neutral");
      return;
    }

    const uniqueFiles = [];
    const signatures = new Set();
    for (const file of files || []) {
      if (!file || !file.name) continue;
      const signature = createFileSignature(file);
      if (signatures.has(signature)) continue;
      signatures.add(signature);
      uniqueFiles.push(file);
    }
    if (!uniqueFiles.length) return;

    const delegated = new CustomEvent(GLOBAL_FILE_DROP_EVENT, {
      cancelable: true,
      detail: { files: uniqueFiles },
    });
    window.dispatchEvent(delegated);
    if (delegated.defaultPrevented) return;

    if (!hasActiveProfile) {
      pushToast("Bitte zuerst ein Profil aktivieren, bevor Dokumente hochgeladen werden.", "danger");
      return;
    }

    busyRef.current = true;

    // Separate email files from document files (#136)
    const emailFiles = uniqueFiles.filter((f) => isEmailFile(f));
    const docFiles = uniqueFiles.filter((f) => !isEmailFile(f));

    let uploaded = 0;
    let failed = 0;
    let emailsImported = 0;

    // Process email files via /api/emails/upload
    for (const file of emailFiles) {
      try {
        const result = await uploadEmailFile(file);
        emailsImported += 1;
        const matchInfo = result.match?.application
          ? ` → ${result.match.application.company}`
          : "";
        const meetingInfo = result.meetings?.length
          ? ` | ${result.meetings.length} Termin(e)`
          : "";
        pushToast(`E-Mail importiert: ${result.parsed?.subject || file.name}${matchInfo}${meetingInfo}`, "success");
      } catch (err) {
        failed += 1;
        pushToast(`E-Mail-Import fehlgeschlagen (${file.name}): ${err.message}`, "danger");
      }
    }

    // Process document files normally
    for (const file of docFiles) {
      try {
        await uploadDocumentFile(file);
        uploaded += 1;
        try {
          await analyzeUploadedDocuments();
        } catch (analysisError) {
          failed += 1;
          pushToast(`Analyse fehlgeschlagen (${file.name}): ${analysisError.message}`, "danger");
        }
      } catch (uploadError) {
        failed += 1;
        pushToast(`Upload fehlgeschlagen (${file.name}): ${uploadError.message}`, "danger");
      }
    }

    busyRef.current = false;
    await refreshChrome();

    const totalOk = uploaded + emailsImported;
    if (totalOk > 0 && failed === 0) {
      if (docFiles.length > 0) {
        pushToast(`${uploaded} Datei(en) für ${profileName || "das aktive Profil"} hochgeladen und analysiert.`, "success");
      }
      return;
    }
    if (totalOk > 0 && failed > 0) {
      pushToast(`${totalOk} Datei(en) erfolgreich, ${failed} fehlgeschlagen.`, "amber");
      return;
    }
    if (totalOk === 0 && failed > 0) {
      pushToast("Keine Datei konnte verarbeitet werden.", "danger");
    }
  });

  useEffect(() => {
    function onWindowDragEnter(event) {
      if (!isFileDragEvent(event)) return;
      event.preventDefault();
      dragDepthRef.current += 1;
      setDragState(true);
    }

    function onWindowDragOver(event) {
      if (!isFileDragEvent(event)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      setDragState(true);
    }

    function onWindowDragLeave(event) {
      if (!isFileDragEvent(event)) return;
      event.preventDefault();
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) {
        setDragState(false);
      }
    }

    async function onWindowDrop(event) {
      if (!isFileDragEvent(event)) return;
      event.preventDefault();
      hideOverlay();
      const files = await extractDroppedFiles(event.dataTransfer);
      await processFiles(files);
    }

    window.addEventListener("dragenter", onWindowDragEnter);
    window.addEventListener("dragover", onWindowDragOver);
    window.addEventListener("dragleave", onWindowDragLeave);
    window.addEventListener("drop", onWindowDrop);
    return () => {
      window.removeEventListener("dragenter", onWindowDragEnter);
      window.removeEventListener("dragover", onWindowDragOver);
      window.removeEventListener("dragleave", onWindowDragLeave);
      window.removeEventListener("drop", onWindowDrop);
      setDragState(false);
    };
  }, [hideOverlay, processFiles, setDragState]);

  return null;
}

