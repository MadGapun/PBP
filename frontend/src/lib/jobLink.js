/**
 * Link zur Original-Stellenanzeige (#765).
 *
 * Der Nutzer bewirbt sich auf der Original-Anzeige — der Weg dorthin muss
 * sichtbar sein. Drei Zustaende, die in der UI unterschieden werden muessen:
 *
 *   detail : echte Anzeige         -> normaler Link
 *   suche  : Suchergebnis-Seite    -> Link, aber ehrlich beschriftet
 *   keine  : gar keine URL         -> sichtbarer Hinweis statt leerem Feld
 *
 * Kein stiller toter Link, kein leeres Feld ohne Erklaerung. Die Erkennung
 * spiegelt `is_search_result_url` im Backend (job_scraper/__init__.py); das
 * Flag `is_search_url` aus der DB hat Vorrang, die Heuristik greift nur, wenn
 * es fehlt (Altbestand vor #763).
 */

const SEARCH_BARE_PATHS = [
  "/jobs", "/jobsuche", "/stellenangebote", "/stellenmarkt",
  "/suche", "/projekte", "/jobboerse",
];

const SEARCH_QUERY_KEYS = ["what", "where", "q", "keywords", "suchbegriff", "was", "wo"];

export function looksLikeSearchUrl(url) {
  if (!url) return false;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  const path = parsed.pathname.replace(/\/+$/, "") || "/";
  const host = parsed.hostname;

  // Detail-Marker im PFAD schlagen alles andere (z.B. /jobs/view/123)
  if (/\/(jobdetail|viewjob|job|jobs|stellenangebote)\/[^/]*\d{4,}/.test(path)) return false;
  if (/--\d/.test(path)) return false; // StepStone-Detailform

  if (SEARCH_BARE_PATHS.includes(path)) return true;
  if (path === "/jobsuche/suche") return true;

  // StepStone-SEO-Suchseiten: /jobs/<keyword>/in-<ort> ohne Detail-Marker
  if (host.includes("stepstone.") && !path.includes("--")) {
    if (path.startsWith("/jobs/") || path.startsWith("/stellenangebote/")) return true;
  }

  const params = parsed.searchParams;
  return SEARCH_QUERY_KEYS.some((k) => params.has(k));
}

/**
 * @returns {{art: 'detail'|'suche'|'keine', url: string, label: string, hinweis: string}}
 */
export function jobLinkInfo(job) {
  const url = (job?.url || "").trim();
  if (!url) {
    return {
      art: "keine",
      url: "",
      label: "",
      hinweis: "Kein Link zur Anzeige hinterlegt — die Stelle muss auf dem Portal gesucht werden.",
    };
  }
  const istSuche = job?.is_search_url ? true : looksLikeSearchUrl(url);
  if (istSuche) {
    return {
      art: "suche",
      url,
      label: "Suchergebnis-Seite öffnen",
      hinweis: "Das ist die Trefferliste des Portals, nicht die Anzeige selbst — die Stelle dort heraussuchen.",
    };
  }
  return { art: "detail", url, label: "Stellenanzeige öffnen", hinweis: "" };
}
