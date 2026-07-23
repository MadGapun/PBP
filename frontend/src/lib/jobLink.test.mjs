// #765: Kipp-Test fuer die Link-Klassifikation im Frontend. Framework-frei,
// laeuft mit dem blanken Node der CI-Runner:
//   node src/lib/jobLink.test.mjs
//
// Der Kern-Beweis: die Frontend-Heuristik darf nicht von der Backend-Logik
// (`is_search_result_url` in job_scraper/__init__.py, #763) wegdriften. Beide
// Listen sind bewusst dieselben Faelle — wer eine Seite aendert, sieht hier
// sofort, dass die andere nachzuziehen ist.
import { jobLinkInfo, looksLikeSearchUrl } from "./jobLink.js";

let failed = 0;
function check(name, actual, expected) {
  const ok = actual === expected;
  if (!ok) {
    failed++;
    console.error(`  FAIL  ${name}: erwartet ${JSON.stringify(expected)}, war ${JSON.stringify(actual)}`);
  } else {
    console.log(`  ok    ${name}`);
  }
}

console.log("jobLink-Klassifikation (#765)");

// --- Such-URLs (dieselben Faelle wie test_v179_url_heilung_763.py) ---
const SUCHE = [
  "https://www.stepstone.de/jobs/plm-manager/in-hamburg",
  "https://www.stepstone.de/stellenangebote/plm",
  "https://de.indeed.com/jobs",
  "https://www.arbeitsagentur.de/jobsuche/suche",
  "https://www.xing.com/jobs",
  "https://www.stepstone.de/jobs?what=plm",
];
for (const url of SUCHE) check(`suche: ${url}`, looksLikeSearchUrl(url), true);

// --- Detail-URLs: ein False-Positive hier waere eine Regression, weil er
//     dem Nutzer einen funktionierenden Link als "nur eine Trefferliste"
//     verkauft. ---
const DETAIL = [
  "https://www.xing.com/jobs/hamburg-plm-manager-123456",
  "https://www.arbeitsagentur.de/jobsuche/jobdetail/12345",
  "https://www.stepstone.de/stellenangebote--PLM-Hamburg--123456-inline.html",
  "https://www.linkedin.com/jobs/view/4012345678",
  "https://de.indeed.com/viewjob?jk=abc123",
  "https://careers.example.com/job/Norderstedt-IT-Partner/12345",
];
for (const url of DETAIL) check(`detail: ${url}`, looksLikeSearchUrl(url), false);

// --- jobLinkInfo: die drei Zustaende der UI ---
check("keine URL -> art", jobLinkInfo({ url: "" }).art, "keine");
check("keine URL -> Hinweis da", jobLinkInfo({ url: "" }).hinweis.length > 0, true);

const detail = jobLinkInfo({ url: "https://careers.example.com/job/4711" });
check("Detail -> art", detail.art, "detail");
check("Detail -> kein Warnhinweis", detail.hinweis, "");
check("Detail -> Label", detail.label, "Stellenanzeige öffnen");

const suche = jobLinkInfo({ url: "https://www.stepstone.de/jobs/plm/in-hamburg" });
check("Suche -> art", suche.art, "suche");
check("Suche -> eigenes Label", suche.label, "Suchergebnis-Seite öffnen");
check("Suche -> Hinweis da", suche.hinweis.length > 0, true);

// Das DB-Flag hat Vorrang: der Scraper wusste es besser als die Heuristik.
check(
  "is_search_url schlaegt Heuristik",
  jobLinkInfo({ url: "https://careers.example.com/job/4711", is_search_url: 1 }).art,
  "suche",
);

// Kaputte URL darf nicht werfen und nicht faelschlich "Suche" sagen.
check("Muell-URL wirft nicht", looksLikeSearchUrl("nicht-mal-eine-url"), false);

console.log(failed === 0 ? "\nAlle Faelle gruen." : `\n${failed} Fehler.`);
process.exit(failed === 0 ? 0 : 1);
