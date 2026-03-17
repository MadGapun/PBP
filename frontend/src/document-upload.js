import { api, postJson } from "@/api";

export function createFileSignature(file) {
  return `${file.name}::${file.size}::${file.lastModified}::${file.webkitRelativePath || ""}`;
}

export async function uploadDocumentFile(file, docType = "sonstiges") {
  const body = new FormData();
  body.append("file", file);
  body.append("doc_type", docType);
  return api("/api/documents/upload", { method: "POST", body });
}

export async function analyzeUploadedDocuments() {
  return postJson("/api/dokumente-analysieren", {});
}
