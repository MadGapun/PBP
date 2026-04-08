import { ChevronLeft, ChevronRight, Download, FileText, Link2, Search, X } from "lucide-react";
import { useEffect, useEffectEvent, useState } from "react";

import { api, apiUrl } from "@/api";
import { useApp } from "@/app-context";
import {
  Badge,
  Card,
  EmptyState,
  LoadingPanel,
  PageHeader,
  SelectInput,
} from "@/components/ui";
import { formatDate } from "@/utils";

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

export default function DocumentsPage() {
  const { reloadKey, pushToast, navigateTo } = useApp();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ documents: [], total: 0, page: 1, pages: 1, doc_types: [] });
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [docType, setDocType] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");

  const loadData = useEffectEvent(async () => {
    try {
      const params = new URLSearchParams({ page: String(page), per_page: "25", sort, order });
      if (activeQuery) params.set("q", activeQuery);
      if (docType) params.set("doc_type", docType);
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
  }, [reloadKey, page, sort, order, activeQuery, docType]);

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

  if (loading && data.documents.length === 0) return <LoadingPanel />;

  return (
    <div id="page-dokumente" className="page active">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <PageHeader title="Dokumente" subtitle={`${data.total} Dokumente`} />
      </div>

      {/* Search + Filters */}
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
          description={activeQuery || docType
            ? "Keine Dokumente fuer diese Suche/Filter gefunden."
            : "Noch keine Dokumente vorhanden. Dokumente werden beim Upload und E-Mail-Import automatisch erfasst."
          }
        />
      ) : (
        <>
          <div className="grid gap-2">
            {data.documents.map((doc) => (
              <Card key={doc.id} className="rounded-xl">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-sky/10 shrink-0">
                    <FileText size={18} className="text-sky" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-medium text-ink truncate">{doc.filename}</h3>
                      <Badge tone="neutral">{docTypeLabel(doc.doc_type)}</Badge>
                    </div>
                    {/* Application cross-reference (#360) */}
                    {(doc.app_company || doc.app_title) && (
                      <button
                        type="button"
                        onClick={() => navigateTo("bewerbungen")}
                        className="mt-0.5 flex items-center gap-1 text-sm text-sky/70 hover:text-sky transition-colors"
                      >
                        <Link2 size={11} />
                        <span className="truncate">
                          {doc.app_company}{doc.app_title ? ` \u2014 ${doc.app_title}` : ""}
                        </span>
                        {doc.app_status && (
                          <Badge tone={doc.app_status === "abgelehnt" ? "danger" : doc.app_status === "interview" ? "amber" : "sky"} className="ml-1">
                            {doc.app_status}
                          </Badge>
                        )}
                      </button>
                    )}
                    {/* Text preview */}
                    {doc.extracted_text && (
                      <p className="mt-1 text-xs text-muted/40 line-clamp-1">
                        {doc.extracted_text.slice(0, 150)}
                      </p>
                    )}
                    <div className="mt-1 text-[11px] text-muted/30">
                      {doc.created_at && formatDate(doc.created_at)}
                    </div>
                  </div>
                  <a
                    href={apiUrl(`/api/documents/${doc.id}/download`)}
                    className="shrink-0 rounded-lg p-1.5 text-muted/30 hover:text-teal transition-colors"
                    title="Herunterladen"
                  >
                    <Download size={14} />
                  </a>
                </div>
              </Card>
            ))}
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
                Seite {data.page} von {data.pages}
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
    </div>
  );
}
