/**
 * Hinweiszone — G60 (#1087 B1, B5, A5).
 *
 * Befund aus dem UX-Review: bis zu fünf Banner vor dem ersten Inhalt
 * (Update-Stand, Bereitschaftsleiste, Quellen-Kasten, Suchbegriff-Abgleich,
 * Ollama-Angebot), drei davon auf jedem Tab — auf dem Aufgaben-Tab also
 * drei Blöcke, die mit Aufgaben nichts zu tun haben. Dazu drei Knöpfe für
 * dieselbe Jobsuche.
 *
 * Regel: höchstens EIN Banner, und nur auf dem Dashboard. Welcher, bestimmt
 * eine feste Reihenfolge — das Dringendste zuerst:
 *
 *   1. Verbindung zu Claude fehlt (nur mit Profil — ohne Profil erklärt
 *      der Einstieg die Verbindung selbst)
 *   2. kein Profil
 *   3. keine Quellen
 *   4. Suche empfohlen (neutral; dringlich erst nach 7 Tagen)
 *   5. Update bekannt (nur ein BEKANNTES Update; "Stand unbekannt" ist
 *      kein Banner, sondern steht in den Einstellungen)
 *   6. Ollama-Angebot (erst nach abgeschlossenem Einstieg)
 *
 * Framework-frei, damit der Node-Test die Reihenfolge prüfen kann.
 */

export const SUCHE_DRINGEND_NACH_TAGEN = 7;

/** Tage seit einem ISO-Zeitpunkt, oder null. */
export function tageSeit(iso, jetzt = new Date()) {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return Math.floor((jetzt.getTime() - t) / 86400000);
}

/**
 * @param {object} lage
 *   seite, verbunden (true/false/null=unbekannt), hatProfil,
 *   quellenAktiv, letzteSucheAm (ISO), updateBekannt ({version, url}),
 *   ollamaAngebot (bool), einstiegFertig (bool)
 * @returns {null | {id, ton, titel, text, aktion}}
 */
export function hinweisFuer(lage, jetzt = new Date()) {
  if (!lage || lage.seite !== "dashboard") return null;

  if (lage.hatProfil && lage.verbunden === false) {
    return {
      id: "verbindung",
      ton: "amber",
      titel: "Claude Desktop ist nicht verbunden",
      text: "Dashboard und Claude arbeiten zusammen. Beende Claude Desktop komplett (Rechtsklick auf das Symbol in der Taskleiste → „Beenden“) und starte es neu.",
      aktion: { art: "anleitung", label: "Anleitung" },
    };
  }
  if (!lage.hatProfil) {
    // Der Einstieg auf dem Dashboard erklärt das selbst — kein zweiter Hinweis.
    return null;
  }
  if (!lage.quellenAktiv) {
    return {
      id: "quellen",
      ton: "amber",
      titel: "Noch keine Jobbörsen ausgewählt",
      text: "Ohne ausgewählte Quellen kann keine Suche laufen. PBP schlägt passende Jobbörsen für dein Profil vor.",
      aktion: { art: "navigieren", ziel: "einstellungen", label: "Jobbörsen auswählen" },
    };
  }
  const tage = tageSeit(lage.letzteSucheAm, jetzt);
  // Eine Suche von gestern ist kein Anlass für ein Banner — erst nach
  // sieben Tagen (oder wenn nie gesucht wurde). Der Knopf auf dem
  // Dashboard bleibt ohnehin da, neutral.
  if (tage === null || tage >= SUCHE_DRINGEND_NACH_TAGEN) {
    return {
      id: "suche",
      ton: "amber",
      titel: tage === null ? "Noch keine Jobsuche gelaufen" : `Letzte Jobsuche vor ${tage} ${tage === 1 ? "Tag" : "Tagen"}`,
      text: "Eine neue Suche findet Stellen, die seitdem erschienen sind.",
      aktion: { art: "jobsuche", label: "Jobsuche starten" },
    };
  }
  if (lage.updateBekannt?.version) {
    return {
      id: "update",
      ton: "neutral",
      titel: `Neue Version verfügbar: v${lage.updateBekannt.version}`,
      text: "Einfach drüberinstallieren — deine Daten bleiben erhalten.",
      aktion: lage.updateBekannt.url ? { art: "link", url: lage.updateBekannt.url, label: "Update-Anleitung" } : null,
    };
  }
  if (lage.ollamaAngebot && lage.einstiegFertig) {
    return {
      id: "ollama",
      ton: "neutral",
      titel: "Lokale KI verfügbar (optional)",
      text: "Ollama ist installiert. Wenn du willst, sortiert PBP damit Stellen vor — ganz ohne Cloud.",
      aktion: { art: "navigieren", ziel: "einstellungen", tab: "ai", label: "Ansehen" },
    };
  }
  return null;
}
