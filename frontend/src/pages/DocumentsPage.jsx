import { ChevronDown, ChevronLeft, ChevronRight, Copy, Download, FileText, Link2, LinkIcon, RotateCcw, Search, Sparkles, Trash2, Unlink, Upload, X } from "lucide-react";
import { useEffect, useEffectEvent, useRef, useState } from "react";

import { api, apiUrl, deleteRequest, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import { analyzeUploadedDocuments, createFileSignature, uploadDocumentFile } from "@/document-upload";
import { extractDroppedFiles } from "@/file-drop";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  LoadingPanel,
  Modal,
  PageHeader,
  SelectInput,
} from "@/components/ui";
import { cn, copyToClipboard, formatDate, formatDateTime } from "@/utils";

const DOC_TYPE_LABELS = {
  lebenslauf: "Lebenslauf",
  anschreiben: "Anschreiben",
  zeugnis: "Zeugnis",
  zertifikat: "Zertifikat",
  bescheinigung: "Bescheinigung",
  mail_eingang: "E-Mail (Eingang)",
  mail_ausgang: "E-Mail (Ausgang)",
  sonstiges: "Sonstiges",
};

function docTypeLabel(type) {
  return DOC_TYPE_LABELS[type] || type || "Sonstiges";
}

const EXTRACTION_STATUS = {
  nicht_extrahiert: { label: "Nicht analysiert", tone: "danger" },
  basis_analysiert: { label: "Basis", tone: "amber" },
  analysiert: { label: "Analysiert", tone: "sky" },
  analysiert_leer: { label: "Leer", tone: "neutral" },
  angewendet: { label: "Angewendet", tone: "success" },
  duplikat: { label: "Duplikat", tone: "neutral" },
};

function extractionBadge(status) {
  const s = EXTRACTION_STATUS[status] || EXTRACTION_STATUS.nicht_extrahiert;
  return s;
}

export default function DocumentsPage() {
  const { reloadKey, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ documents: [], total: 0, page: 1, pages: 1, doc_types: [], applications: [], unlinked_count: 0, unanalyzed_count: 0 });
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [docType, setDocType] = useState("");
  const [appFilter, setAppFilter] = useState("");
  const [unlinkedFilter, setUnlinkedFilter] = useState(false);
  const [extractionFilter, setExtractionFilter] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const [expandedText, setExpandedText] = useState(null);
  const [linkModal, setLinkModal] = useState({ open: false, doc: null, value: "", search: "" });
  const [deleteConfirm, setDeleteConfirm] = useState(null); // doc.id to confirm
  const [expandedDoc, setExpandedDoc] = useState(null); // #390: expanded detail view
  const [templateChoice, setTemplateChoice] = useState({}); // #496: per-doc template override (docId -> templateKey)
  const [availableTemplates, setAvailableTemplates] = useState([]); // #496: loaded once on mount
  const [uploadType, setUploadType] = useState("sonstiges");
  const [appSearch, setAppSearch] = useState("");
  const [appDropdownOpen, setAppDropdownOpen] = useState(false);
  const appDropdownRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const uploadedSignaturesRef = useRef(new Set());

  const loadData = useEffectEvent(async () => {
    try {
      const params = new URLSearchParams({ page: String(page), per_page: "25", sort, order });
      if (activeQuery) params.set("q", activeQuery);
      if (docType) params.set("doc_type", docType);
      if (appFilter) params.set("application_id", appFilter);
      if (unlinkedFilter) params.set("unlinked", "1");
      if (extractionFilter) params.set("extraction_status", extractionFilter);
      const result = await api(`/api/documents?${params}`);
      setData(result);
    } catch (error) {
      pushToast(`Dokumente konnten nicht geladen werden: ${error.message}`, "danger");
    } finally {
      setLoading(false);
    }
  });

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [reloadKey, page, sort, order, activeQuery, docType, appFilter, unlinkedFilter, extractionFilter]);

  // #496: Load analysis templates once for the template dropdown
  useEffect(() => {
    api("/api/analysis-templates")
      .then((r) => setAvailableTemplates(r.templates || []))
      .catch(() => {});
  }, []);

  function handleSearch(e) {
    e.preventDefault();
    setPage(1);
    setActiveQuery(query);
  }

  function clearSearch() {
    setQuery("");
    setActiveQuery("");
    setPage(1);
  }

  function toggleSort(col) {
    if (sort === col) {
      setOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setSort(col);
      setOrder("desc");
    }
    setPage(1);
  }

  async function saveLink() {
    if (!linkModal.doc) return;
    try {
      await putJson(`/api/document/${linkModal.doc.id}/link`, {
        application_id: linkModal.value || null,
      });
      pushToast("Verknuepfung aktualisiert", "success");
      setLinkModal({ open: false, doc: null, value: "" });
      loadData();
    } catch (error) {
      pushToast(`Fehler: ${error.message}`, "danger");
    }
  }

  async function deleteDocument(docId) {
    try {
      await deleteRequest(`/api/document/${docId}`);
      pushToast("Dokument geloescht", "success");
      setDeleteConfirm(null);
      loadData();
    } catch (error) {
      pushToast(`Loeschen fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  // #496: Prompt-Templates pro Dokumenttyp. Prompt wird serverseitig
  // gebaut (src/bewerbungs_assistent/document_analysis_prompts.py).
  async function reanalyzeDocument(docId, templateKey = null) {
    const chosen = templateKey || templateChoice[docId] || null;
    try {
      await postJson(`/api/document/${docId}/reanalyze`, {});
      try {
        const qs = chosen ? `?template=${encodeURIComponent(chosen)}` : "";
        const response = await api(`/api/document/${docId}/analysis-prompt${qs}`);
        if (response.available_templates && !availableTemplates.length) {
          setAvailableTemplates(response.available_templates);
        }
        await copyToClipboard(response.prompt);
        pushToast(
          `Analyse-Prompt (${response.template_label}) kopiert \u2014 in Claude einfuegen`,
          "success"
        );
      } catch {
        pushToast("Dokument vorgemerkt (Clipboard/API blockiert)", "success");
      }
      loadData();
    } catch (error) {
      pushToast(`Fehler: ${error.message}`, "danger");
    }
  }

  async function processFiles(files) {
    if (!files?.length) return;
    setUploading(true);
    let count = 0;
    try {
      for (const file of files) {
        const sig = await createFileSignature(file);
        if (uploadedSignaturesRef.current.has(sig)) continue;
        uploadedSignaturesRef.current.add(sig);
        await uploadDocumentFile(file, uploadType);
        count++;
      }
      if (count > 0) {
        pushToast(`${count} Dokument${count > 1 ? "e" : ""} hochgeladen`, "success");
        loadData();
      }
    } catch (error) {
      pushToast(`Upload-Fehler: ${error.message}`, "danger");
    } finally {
      setUploading(false);
    }
  }

  if (loading && data.documents.length === 0) return <LoadingPanel />;

  return (
    <div id="page-dokumente" className="page active">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <PageHeader title="Dokumente" subtitle={`${data.total} Dokumente`} />
      </div>

      {/* Upload area */}
      <Card className="mb-4 rounded-xl">
        <div className="flex flex-wrap items-center gap-4">
          <div
            className={cn(
              "flex-1 min-w-[200px] rounded-xl border-2 border-dashed border-white/15 bg-white/[0.02] px-4 py-3 transition",
              dragActive && "border-sky/60 bg-sky/10 ring-2 ring-sky/35"
            )}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={(e) => { e.preventDefault(); if (e.currentTarget.contains(e.relatedTarget)) return; setDragActive(false); }}
            onDrop={async (e) => { e.preventDefault(); setDragActive(false); const files = await extractDroppedFiles(e.dataTransfer); await processFiles(files); }}
          >
            <div className="flex items-center gap-3">
              <Upload size={16} className="text-muted/40 shrink-0" />
              <span className="text-sm text-muted/60">Dateien oder Ordner hier ablegen</span>
              <div className="flex items-center gap-2 ml-auto">
                <SelectInput
                  className="!h-8 !min-h-0 !w-auto !rounded-lg !border-white/5 !bg-white/[0.03] !pl-2 !pr-2 !py-0 !text-[12px] !text-muted/60"
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                >
                  <option value="sonstiges">Auto / Sonstiges</option>
                  <option value="lebenslauf">Lebenslauf</option>
                  <option value="anschreiben">Anschreiben</option>
                  <option value="zeugnis">Zeugnis</option>
                  <option value="zertifikat">Zertifikat</option>
                </SelectInput>
                <Button type="button" size="sm" variant="secondary" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
                  {uploading ? "Lade..." : "Dateien"}
                </Button>
                <Button type="button" size="sm" variant="ghost" disabled={uploading} onClick={() => folderInputRef.current?.click()}>
                  Ordner
                </Button>
              </div>
            </div>
          </div>
          <input ref={fileInputRef} className="hidden" type="file" multiple accept=".pdf,.doc,.docx,.txt,.md,.csv,.json,.xml,.rtf,.msg,.eml" onChange={async (e) => { await processFiles(e.target.files); e.target.value = ""; }} />
          <input ref={folderInputRef} className="hidden" type="file" multiple accept=".pdf,.doc,.docx,.txt,.md,.csv,.json,.xml,.rtf,.msg,.eml" webkitdirectory="" directory="" onChange={async (e) => { await processFiles(e.target.files); e.target.value = ""; }} />
        </div>
      </Card>

      {/* Search + Filters (#366) */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="flex flex-1 items-center gap-2 min-w-[200px] max-w-md">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/40" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Dateiname oder Inhalt suchen..."
              className="w-full rounded-xl border border-white/8 bg-white/[0.03] py-2 pl-9 pr-8 text-sm text-ink placeholder:text-muted/30 focus:border-sky/30 focus:outline-none"
            />
            {activeQuery && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted/40 hover:text-ink"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="rounded-xl bg-sky/15 px-3 py-2 text-xs font-medium text-sky hover:bg-sky/25 transition-colors"
          >
            Suchen
          </button>
        </form>

        <SelectInput
          className="!h-9 !min-h-0 !w-auto !rounded-xl !border-white/5 !bg-white/[0.03] !pl-3 !pr-3 !py-0 !text-[13px] !text-muted/60"
          value={docType}
          onChange={(e) => { setDocType(e.target.value); setPage(1); }}
        >
          <option value="">Alle Typen</option>
          {data.doc_types.map((t) => (
            <option key={t} value={t}>{docTypeLabel(t)}</option>
          ))}
        </SelectInput>

        {/* Application filter — searchable (#366) */}
        {data.applications?.length > 0 && (
          <div className="relative" ref={appDropdownRef}>
            <input
              type="text"
              value={appSearch}
              onChange={(e) => { setAppSearch(e.target.value); setAppDropdownOpen(true); }}
              onFocus={() => setAppDropdownOpen(true)}
              onBlur={() => setTimeout(() => setAppDropdownOpen(false), 200)}
              placeholder={appFilter ? (data.applications.find((a) => a.id === appFilter)?.company || "Bewerbung") : "Bewerbung filtern..."}
              className="h-9 w-[14rem] rounded-xl border border-white/5 bg-white/[0.03] px-3 text-[13px] text-muted/60 placeholder:text-muted/30 focus:border-sky/30 focus:outline-none"
            />
            {appFilter && (
              <button type="button" onClick={() => { setAppFilter(""); setAppSearch(""); setPage(1); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted/40 hover:text-ink">
                <X size={12} />
              </button>
            )}
            {appDropdownOpen && (() => {
              const q = appSearch.toLowerCase();
              const filtered = data.applications.filter((a) =>
                !q || (a.company || "").toLowerCase().includes(q) || (a.title || "").toLowerCase().includes(q)
              );
              if (filtered.length === 0) return null;
              return (
                <div className="absolute left-0 top-full z-50 mt-1 max-h-48 w-[18rem] overflow-y-auto rounded-xl border border-white/10 bg-[rgba(30,34,52,0.95)] shadow-2xl backdrop-blur-2xl">
                  <button type="button" className="flex w-full px-3 py-1.5 text-[12px] text-muted/50 hover:bg-white/[0.06]" onMouseDown={() => { setAppFilter(""); setAppSearch(""); setPage(1); setAppDropdownOpen(false); }}>
                    Alle Bewerbungen
                  </button>
                  {filtered.map((a) => (
                    <button key={a.id} type="button" className={cn("flex w-full px-3 py-1.5 text-[12px] text-left transition-colors hover:bg-white/[0.06]", appFilter === a.id ? "text-sky" : "text-muted/60")} onMouseDown={() => { setAppFilter(a.id); setAppSearch(""); setUnlinkedFilter(false); setPage(1); setAppDropdownOpen(false); }}>
                      {a.company}{a.title ? ` \u2014 ${a.title}` : ""}
                    </button>
                  ))}
                </div>
              );
            })()}
          </div>
        )}

        {/* Unlinked quick filter (#366) */}
        {data.unlinked_count > 0 && (
          <button
            type="button"
            onClick={() => { setUnlinkedFilter(!unlinkedFilter); setAppFilter(""); setPage(1); }}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
              unlinkedFilter
                ? "bg-amber/15 text-amber"
                : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
            }`}
          >
            <Unlink size={12} />
            Nicht verknuepft ({data.unlinked_count})
          </button>
        )}

        {/* Unanalyzed quick filter (#369) */}
        {data.unanalyzed_count > 0 && (
          <button
            type="button"
            onClick={() => {
              const next = extractionFilter ? "" : "nicht_extrahiert";
              setExtractionFilter(next);
              setPage(1);
            }}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
              extractionFilter
                ? "bg-violet-500/15 text-violet-400"
                : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
            }`}
          >
            <Sparkles size={12} />
            Nicht analysiert ({data.unanalyzed_count})
          </button>
        )}

        {/* Sort toggles */}
        <div className="flex items-center gap-1">
          {[
            { col: "created_at", label: "Datum" },
            { col: "filename", label: "Name" },
            { col: "doc_type", label: "Typ" },
          ].map((s) => (
            <button
              key={s.col}
              type="button"
              onClick={() => toggleSort(s.col)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                sort === s.col
                  ? "bg-sky/15 text-sky"
                  : "text-muted/40 hover:text-ink hover:bg-white/[0.04]"
              }`}
            >
              {s.label}
              {sort === s.col && (order === "desc" ? " \u2193" : " \u2191")}
            </button>
          ))}
        </div>
      </div>

      {data.documents.length === 0 ? (
        <EmptyState
          title="Keine Dokumente"
          description={activeQuery || docType || appFilter || unlinkedFilter || extractionFilter
            ? "Keine Dokumente fuer diese Suche/Filter gefunden."
            : "Noch keine Dokumente vorhanden. Dokumente werden beim Upload und E-Mail-Import automatisch erfasst."
          }
        />
      ) : (
        <>
          <div className="grid gap-2">
            {data.documents.map((doc) => {
              const isTextExpanded = expandedText === doc.id;
              const isExpanded = expandedDoc === doc.id;
              return (
                <Card
                  key={doc.id}
                  className={cn("rounded-xl cursor-pointer transition-colors", isExpanded ? "ring-1 ring-sky/20" : "hover:bg-white/[0.02]")}
                  onClick={() => setExpandedDoc(isExpanded ? null : doc.id)}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-sky/10 shrink-0">
                      <FileText size={18} className="text-sky" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-medium text-ink truncate">{doc.filename}</h3>
                        <Badge tone="neutral">{docTypeLabel(doc.doc_type)}</Badge>
                        {(() => {
                          const eb = extractionBadge(doc.extraction_status);
                          return <Badge tone={eb.tone}>{eb.label}</Badge>;
                        })()}
                      </div>
                      {/* Application cross-reference — clickable (#366) */}
                      {(doc.app_company || doc.app_title) ? (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); navigateTo("bewerbungen", { highlight: doc.linked_application_id }); }}
                          className="mt-0.5 flex items-center gap-1 text-sm text-sky/70 hover:text-sky transition-colors"
                        >
                          <Link2 size={11} />
                          <span className="truncate">
                            {doc.app_company}{doc.app_title ? ` \u2014 ${doc.app_title}` : ""}
                          </span>
                          {doc.app_status && (
                            <Badge tone={doc.app_status === "abgelehnt" ? "danger" : doc.app_status === "interview" ? "amber" : "neutral"} className="ml-1">
                              {doc.app_status}
                            </Badge>
                          )}
                        </button>
                      ) : (
                        <p className="mt-0.5 text-[11px] text-muted/30">Nicht verknuepft</p>
                      )}
                      {/* Expandable text preview (#366) */}
                      {doc.extracted_text && (
                        <button
                          type="button"
                          className="mt-1 text-left text-xs text-muted/40 hover:text-muted/60 transition-colors w-full"
                          onClick={() => setExpandedText(isTextExpanded ? null : doc.id)}
                        >
                          {isTextExpanded
                            ? doc.extracted_text.slice(0, 500)
                            : doc.extracted_text.slice(0, 150)}
                          {doc.extracted_text.length > (isTextExpanded ? 500 : 150) && "\u2026"}
                          {doc.extracted_text.length > 150 && (
                            <span className="ml-1 text-sky/50">{isTextExpanded ? "weniger" : "mehr"}</span>
                          )}
                        </button>
                      )}
                      <div className="mt-1 text-[11px] text-muted/30">
                        {doc.created_at && formatDate(doc.created_at)}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      {/* Reanalyze button (#369) — for already-analyzed docs: reset to re-analyze */}
                      {/* #391: Also show for basis_analysiert with Sparkles icon to indicate full analysis needed */}
                      {doc.extraction_status === "basis_analysiert" ? (
                        <button
                          type="button"
                          onClick={() => reanalyzeDocument(doc.id)}
                          className="rounded-lg p-1.5 text-amber/50 hover:text-amber transition-colors"
                          title="Vollanalyse starten (bisher nur Basis)"
                        >
                          <Sparkles size={14} />
                        </button>
                      ) : doc.extraction_status && !["nicht_extrahiert", ""].includes(doc.extraction_status) ? (
                        <button
                          type="button"
                          onClick={() => reanalyzeDocument(doc.id)}
                          className="rounded-lg p-1.5 text-muted/30 hover:text-violet-400 transition-colors"
                          title="Erneut analysieren"
                        >
                          <RotateCcw size={14} />
                        </button>
                      ) : null}
                      {/* Link/Unlink button (#366) */}
                      <button
                        type="button"
                        onClick={() => setLinkModal({
                          open: true,
                          doc,
                          value: doc.linked_application_id || "",
                        })}
                        className="rounded-lg p-1.5 text-muted/30 hover:text-sky transition-colors"
                        title="Verknuepfung aendern"
                      >
                        <LinkIcon size={14} />
                      </button>
                      {/* #403: Copy communication ID */}
                      <button
                        type="button"
                        onClick={() => {
                          const shortId = doc.id.slice(0, 8);
                          navigator.clipboard.writeText(shortId);
                          pushToast(`ID ${shortId} kopiert`, "success");
                        }}
                        className="rounded-lg p-1.5 text-muted/30 hover:text-amber transition-colors"
                        title={`Kommunikations-ID kopieren (${doc.id.slice(0, 8)})`}
                      >
                        <Copy size={14} />
                      </button>
                      <a
                        href={apiUrl(`/api/documents/${doc.id}/download`)}
                        className="shrink-0 rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors"
                        title="Herunterladen"
                      >
                        <Download size={14} />
                      </a>
                      {deleteConfirm === doc.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => deleteDocument(doc.id)}
                            className="rounded-lg px-2 py-1 text-xs font-medium bg-red-500/15 text-red-400 hover:bg-red-500/25 transition-colors"
                          >
                            Ja
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteConfirm(null)}
                            className="rounded-lg px-2 py-1 text-xs text-muted/50 hover:text-ink transition-colors"
                          >
                            Nein
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDeleteConfirm(doc.id)}
                          className="shrink-0 rounded-lg p-1.5 text-muted/30 hover:text-red-400 transition-colors"
                          title="Loeschen"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                  {/* #390: Expanded document detail view */}
                  {isExpanded && (
                    <div className="mt-3 border-t border-white/[0.06] pt-3" onClick={(e) => e.stopPropagation()}>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="text-xs text-muted/50 space-y-1">
                          <p><span className="text-muted/30">ID:</span> {doc.id.slice(0, 8)}</p>
                          <p><span className="text-muted/30">Typ:</span> {docTypeLabel(doc.doc_type)}</p>
                          <p><span className="text-muted/30">Erstellt:</span> {doc.created_at ? formatDateTime(doc.created_at) : "k.A."}</p>
                          <p><span className="text-muted/30">Status:</span> {extractionBadge(doc.extraction_status).label}</p>
                          {doc.app_company && <p><span className="text-muted/30">Bewerbung:</span> {doc.app_company}{doc.app_title ? ` — ${doc.app_title}` : ""}</p>}
                        </div>
                        <div className="flex flex-col gap-2 items-start sm:items-end">
                          {availableTemplates.length > 0 && (
                            <SelectInput
                              className="!h-8 !min-h-0 !w-auto !rounded-lg !border-white/10 !bg-white/[0.03] !pl-2 !pr-2 !py-0 !text-[11px] !text-muted/60"
                              value={templateChoice[doc.id] || ""}
                              onChange={(e) => setTemplateChoice((prev) => ({ ...prev, [doc.id]: e.target.value }))}
                              title="Analyse-Template"
                            >
                              <option value="">Auto (nach Dokumenttyp)</option>
                              {availableTemplates.map((t) => (
                                <option key={t.key} value={t.key}>{t.label}</option>
                              ))}
                            </SelectInput>
                          )}
                          <Button
                            size="sm"
                            onClick={() => reanalyzeDocument(doc.id)}
                          >
                            <Sparkles size={13} />
                            {doc.extraction_status === "basis_analysiert"
                              ? "Vollanalyse starten"
                              : doc.extraction_status && !["nicht_extrahiert", ""].includes(doc.extraction_status)
                                ? "Erneut analysieren"
                                : "Analysieren"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => window.open(apiUrl(`/api/documents/${doc.id}/download`), "_blank")}
                          >
                            <Download size={13} />
                            Herunterladen
                          </Button>
                        </div>
                      </div>
                      {doc.extracted_text && (
                        <div className="mt-3 rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 max-h-48 overflow-y-auto">
                          <p className="text-xs text-muted/40 whitespace-pre-wrap">{doc.extracted_text.slice(0, 2000)}</p>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                type="button"
                disabled={data.page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg p-1.5 text-muted/40 hover:text-ink disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-xs text-muted/50">
                Seite {data.page} von {data.pages} ({data.total} Dokumente)
              </span>
              <button
                type="button"
                disabled={data.page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg p-1.5 text-muted/40 hover:text-ink disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </>
      )}

      {/* Link-Document Modal (#366) */}
      <Modal
        open={linkModal.open}
        title="Dokument verknuepfen"
        description={linkModal.doc ? `${linkModal.doc.filename}` : ""}
        onClose={() => setLinkModal({ open: false, doc: null, value: "", search: "" })}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setLinkModal({ open: false, doc: null, value: "", search: "" })}>
              Abbrechen
            </Button>
            <Button onClick={saveLink}>
              Speichern
            </Button>
          </div>
        }
      >
        <div className="space-y-2">
          <input
            type="text"
            value={linkModal.search}
            onChange={(e) => setLinkModal((cur) => ({ ...cur, search: e.target.value }))}
            placeholder="Bewerbung suchen..."
            className="w-full rounded-xl border border-white/8 bg-white/[0.03] py-2 px-3 text-sm text-ink placeholder:text-muted/30 focus:border-sky/30 focus:outline-none"
          />
          <div className="max-h-48 overflow-y-auto rounded-xl border border-white/[0.05]">
            <button
              type="button"
              className={cn("flex w-full px-3 py-2 text-sm transition-colors hover:bg-white/[0.06]", !linkModal.value ? "text-sky font-medium" : "text-muted/60")}
              onClick={() => setLinkModal((cur) => ({ ...cur, value: "" }))}
            >
              Nicht verknuepft
            </button>
            {(data.applications || [])
              .filter((a) => {
                const q = (linkModal.search || "").toLowerCase();
                return !q || (a.company || "").toLowerCase().includes(q) || (a.title || "").toLowerCase().includes(q);
              })
              .map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className={cn("flex w-full px-3 py-2 text-sm text-left transition-colors hover:bg-white/[0.06]", linkModal.value === a.id ? "text-sky font-medium" : "text-muted/60")}
                  onClick={() => setLinkModal((cur) => ({ ...cur, value: a.id }))}
                >
                  {a.company}{a.title ? ` \u2014 ${a.title}` : ""}
                </button>
              ))
            }
          </div>
        </div>
      </Modal>
    </div>
  );
}
