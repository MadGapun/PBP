/**
 * "E-Mail importieren" — v1.7.35 (#985), zugezogen vom Dashboard.
 */
import { useRef, useState } from "react";
import { Mail } from "lucide-react";

import { api } from "@/api";
import { Button } from "@/components/ui";

export default function EmailUploadButton({ pushToast }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/emails/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        pushToast(data.error || "E-Mail-Upload fehlgeschlagen", "danger");
        return;
      }
      const matchInfo = data.match?.application
        ? ` → ${data.match.application.company} (${Math.round(data.match.confidence * 100)}%)`
        : " (nicht zugeordnet)";
      const statusInfo = data.detected_status?.status
        ? ` | Status: ${data.detected_status.status}`
        : "";
      const meetingInfo = data.meetings?.length
        ? ` | ${data.meetings.length} Termin(e)`
        : "";
      const docInfo = data.imported_documents
        ? ` | ${data.imported_documents} Dokument(e)`
        : "";
      pushToast(`E-Mail importiert${matchInfo}${statusInfo}${meetingInfo}${docInfo}`, "success");
    } catch (err) {
      pushToast(`Upload fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept=".msg,.eml"
        className="hidden"
        onChange={handleUpload}
      />
      <Button
        size="sm"
        variant="ghost"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
      >
        <Mail size={14} className="mr-1" />
        {uploading ? "Importiere..." : "E-Mail importieren"}
      </Button>
    </>
  );
}
