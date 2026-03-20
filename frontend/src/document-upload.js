import { api, postJson } from "@/api";

export function createFileSignature(file) {
  return `${file.name}::${file.size}::${file.lastModified}::${file.webkitRelativePath || ""}`;
}

const EMAIL_EXTENSIONS = new Set([".msg", ".eml"]);

export function isEmailFile(file) {
  const name = (file?.name || "").toLowerCase();
  return EMAIL_EXTENSIONS.has(name.slice(name.lastIndexOf(".")));
}

export async function uploadDocumentFile(file, docType = "sonstiges") {
  const body = new FormData();
  body.append("file", file);
  body.append("doc_type", docType);
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
