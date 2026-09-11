/**
 * Gehaltskennzahlen — EINE Fassung fuer beide Tabs (#1015).
 *
 * `buildAnnualSalaryMetrics` lag wortgleich in `DashboardPage.jsx` und
 * `JobsPage.jsx`. Beide Kopien tragen denselben v1.6.2-Kommentar und
 * denselben beta.26-Plausibilitaetsfilter — sie sind also nicht
 * zufaellig aehnlich, sondern eine kopierte Fassung. Dieselbe Bauform,
 * die dieses Projekt sechzehnmal gekostet hat (#963 zuerst); die
 * Doppelung wurde hier VORGEFUNDEN, nicht angelegt, und beim Ergaenzen
 * der Schaetz-Zaehlung waere sie um eine dritte Abweichung gewachsen.
 *
 * Neu gegenueber den beiden Kopien: `estimatedBasisCount`. Das vierte
 * Akzeptanzkriterium von #1015 verlangt, dass die Durchschnittskennzahl
 * ausweist, wie viele der zugrunde liegenden Werte GESCHAETZT sind —
 * `allEstimated` beantwortete nur die Extremfrage "gar keine echte
 * Angabe" und schwieg zu jeder Mischung.
 *
 * Warum das zaehlt: gemeldet wurde eine Kennzahl von 92.375 EUR ueber
 * acht Stellen, in die zwei geschaetzte Praktikumsgehaelter von 80.000
 * bis 120.000 EUR eingeflossen sind. Seit v1.7.78 entstehen solche
 * Schaetzungen gar nicht mehr (`estimate_salary` schweigt bei Praktika
 * und studentischen Taetigkeiten), aber der Altbestand traegt sie
 * weiter — und eine Durchschnittszahl, die ihre Grundlage verschweigt,
 * ist genau der Fehler aus #989 in der Statistik.
 */

/** Tagessaetze, die faelschlich als Jahresgehalt gefuehrt werden, raus. */
export const ANNUAL_MIN_PLAUSIBLE = 20000;

export function positiveSalary(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return numeric;
}

export function buildAnnualSalaryMetrics(jobs = []) {
  // v1.6.2 Bugfix: vorher wurde bei "mindestens eine echte Angabe" der
  // gesamte geschaetzte Pool verworfen — bei 2 echten und 272
  // geschaetzten Stellen zeigte die Karte nur 2 Datenpunkte. Jetzt
  // werden alle kombiniert; `allEstimated` bleibt true nur, wenn KEINE
  // echte Angabe existiert.
  const realRows = [];
  const estimatedRows = [];
  for (const job of jobs) {
    let min = positiveSalary(job?.salary_min);
    let max = positiveSalary(job?.salary_max);
    if (min === null && max === null) continue;
    if (min === null) min = max;
    if (max === null) max = min;
    const entry = {
      min,
      max,
      salaryType: String(job?.salary_type || "").toLowerCase(),
      estimated: Boolean(job?.salary_estimated),
    };
    if (entry.estimated) {
      estimatedRows.push(entry);
    } else {
      realRows.push(entry);
    }
  }

  const rows = [...realRows, ...estimatedRows];
  const allEstimated = realRows.length === 0 && estimatedRows.length > 0;

  const annualRows = rows.filter(
    (row) => row.salaryType === "jaehrlich" && row.min >= ANNUAL_MIN_PLAUSIBLE
  );
  if (!annualRows.length) {
    return {
      jobsWithSalary: rows.length,
      annualBasisCount: 0,
      estimatedBasisCount: 0,
      averageMin: null,
      averageMax: null,
      bandMin: null,
      bandMax: null,
      allEstimated,
    };
  }

  const mins = annualRows.map((row) => row.min);
  const maxs = annualRows.map((row) => row.max);
  return {
    jobsWithSalary: rows.length,
    annualBasisCount: annualRows.length,
    // #1015 AK 4: nicht "alles geschaetzt ja/nein", sondern wie viele.
    estimatedBasisCount: annualRows.filter((row) => row.estimated).length,
    averageMin: Math.round(mins.reduce((sum, value) => sum + value, 0) / mins.length),
    averageMax: Math.round(maxs.reduce((sum, value) => sum + value, 0) / maxs.length),
    // v1.6.2: echte Min/Max-Spanne fuer die Bandbreite-Kachel.
    bandMin: Math.min(...mins),
    bandMax: Math.max(...maxs),
    allEstimated,
  };
}

/**
 * Die Fusszeile unter der Durchschnitts-Kachel.
 *
 * Sie nennt die Grundlage samt Schaetzanteil. "Auf Basis von 8 Stellen"
 * verschweigt, dass sieben davon geraten sind — und eine Zahl, deren
 * Grundlage man nicht sieht, kann man nicht einordnen.
 */
export function grundlagenText(metrics) {
  const gesamt = Number(metrics?.annualBasisCount || 0);
  if (!gesamt) return "Noch keine Gehaltsdaten";
  const geschaetzt = Number(metrics?.estimatedBasisCount || 0);
  const teile = [
    `Auf Basis von ${gesamt} ${gesamt === 1 ? "Stelle" : "Stellen"} mit Jahresgehalt`,
  ];
  if (geschaetzt === gesamt) {
    teile.push("alle geschätzt");
  } else if (geschaetzt > 0) {
    teile.push(`davon ${geschaetzt} geschätzt`);
  } else {
    teile.push("alle belegt");
  }
  if (gesamt < 3) teile.push("wenig Datenbasis");
  return teile.join(" — ");
}
