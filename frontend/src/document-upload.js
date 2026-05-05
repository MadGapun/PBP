import { api, postJson } from "@/api";

export function createFileSignature(file) {
  return `${file.name}::${file.size}::${file.lastModified}::${file.webkitRelativePath || ""}`;
}

const EMAIL_EXTENSIONS = new Set([".msg", ".eml"]);

export function isEmailFile(file) {
  const name = (file?.name || "").toLowerCase();
  return EMAIL_EXTENSIONS.has(name.slice(name.lastIndexOf(".")));
}

export async function uploadDocumentFile(file, docType = "sonstiges", options = {}) {
  // v1.6.9 (#570): optional applicationId fuer Direkt-Upload aus einer
  // Bewerbungs-Detailansicht — Backend verknuepft dann automatisch und
  // legt keine Duplikate an.
  const body = new FormData();
  body.append("file", file);
  body.append("doc_type", docType);
  if (options.applicationId) {
    body.append("link_application_id", String(options.applicationId));
  }
  if (options.positionId) {
    body.append("position_id", String(options.positionId));
  }
  return api("/api/documents/upload", { method: "POST", body });
}

export async function uploadEmailFile(file) {
  const body = new FormData();
  body.append("file", file);
  return api("/api/emails/upload", { method: "POST", body });
}

export async function analyzeUploadedDocuments() {
  return postJson("/api/dokumente-analysieren", {});
}
