import { useEffect, useEffectEvent, useRef } from "react";

import { analyzeUploadedDocuments, createFileSignature, uploadDocumentFile } from "@/document-upload";
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

    let uploaded = 0;
    let failed = 0;
    for (const file of uniqueFiles) {
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

    if (uploaded > 0 && failed === 0) {
      pushToast(`${uploaded} Datei(en) für ${profileName || "das aktive Profil"} hochgeladen und analysiert.`, "success");
      return;
    }
    if (uploaded > 0 && failed > 0) {
      pushToast(`${uploaded} Datei(en) erfolgreich, ${failed} fehlgeschlagen.`, "amber");
      return;
    }
    pushToast("Keine Datei konnte verarbeitet werden.", "danger");
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

