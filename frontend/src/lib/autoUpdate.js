/**
 * Auto-Update — was die Oberfläche aus /api/auto-update macht (#1093, v1.8).
 *
 * Framework-frei, damit der Node-Test die Regeln prüfen kann:
 *   - die vier Stufen und ihre Texte (Nutzerwort 02.10.2026),
 *   - welcher Hinweis auf dem Dashboard erscheint (`updateHinweis`),
 *   - Fortschritt, Größen, Zeiten.
 *
 * Grundsatz: PBP installiert nie etwas, ohne dass der Mensch die Stufe gewählt hat. Die Vorgabe ist „aus“.
 */

/** Die vier Stufen, in der Reihenfolge der Einstellung. */
export const STUFEN = [
  {
    id: "aus",
    kurz: "Nur Hinweis",
    text: "PBP sagt Bescheid, wenn es eine neue Version gibt. Du installierst sie selbst.",
  },
  {
    id: "hinweis",
    kurz: "Mit einem Klick",
    text: "Der Hinweis in PBP startet das Update mit einem Klick. Du musst nichts herunterladen.",
  },
  {
    id: "auto_meldung",
    kurz: "Automatisch, mit Meldung",
    text: "PBP lädt und installiert selbst, sobald nichts anderes läuft, und sagt danach Bescheid.",
  },
  {
    id: "auto_still",
    kurz: "Automatisch, still",
    text: "Wie zuvor, aber ohne Meldung. Die Version steht im Verlauf und in der Seitenleiste.",
  },
];

/** Die Antworten auf die Rückfrage beim ersten Update. */
export const ANTWORTEN = [
  { id: "automatisch", label: "Ja, automatisch", titel: "PBP installiert Updates selbst und sagt danach Bescheid." },
  { id: "klick", label: "Mit einem Klick", titel: "Du startest das Update im Hinweis mit einem Klick." },
  { id: "nein", label: "Nein, ich mache es selbst", titel: "PBP sagt nur Bescheid. Installiert wird von Hand." },
  { id: "spaeter", label: "Später", titel: "PBP fragt beim nächsten Update noch einmal." },
];

export const INSTALLER_AUFRAEUMEN = [
  { id: "fragen", label: "Fragen" },
  { id: "immer", label: "Immer löschen" },
  { id: "nie", label: "Nie löschen" },
];

export const AUTOMATISCHE_STUFEN = ["auto_meldung", "auto_still"];

export function stufeLabel(id) {
  return STUFEN.find((s) => s.id === id)?.kurz || "Nur Hinweis";
}

/** Fortschritt des laufenden Laufs in ganzen Prozent (0 bis 100). */
export function prozent(job) {
  const a = Number(job?.anteil);
  if (!Number.isFinite(a)) return 0;
  return Math.max(0, Math.min(100, Math.round(a * 100)));
}

/** Größe für Menschen: „2,4 MB“. */
export function groesseText(bytes) {
  const b = Number(bytes);
  if (!Number.isFinite(b) || b <= 0) return "0 MB";
  const mb = b / (1024 * 1024);
  if (mb < 0.1) return "< 0,1 MB";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1).replace(".", ",")} GB`;
  return `${mb.toFixed(mb < 10 ? 1 : 0).replace(".", ",")} MB`;
}

/** Ist gerade ein Lauf in Arbeit? Dann fragt die Oberfläche öfter nach dem Stand. */
export function laeuft(au) {
  return au?.job?.status === "laeuft";
}

/** Wann die Oberfläche das nächste Mal fragt (Millisekunden). */
export function naechsteFrageMs(au) {
  if (laeuft(au)) return 1500;
  if (au?.job?.status === "fehler" || au?.neustart_noetig) return 20000;
  return 60000;
}

const OPTIONEN = { art: "update-optionen", label: "Update-Optionen" };

/**
 * Mit welcher Fassung arbeitet Claude gerade? Nur wenn die Verbindung steht und die Fassung lesbar ist.
 * Ältere Programmstände schreiben keine Fassung in den Herzschlag; dann weiß PBP es nicht und sagt nichts.
 */
export function claudeFassung(mcp) {
  if (!mcp || mcp.status !== "connected") return "";
  return fassungsSchluessel(mcp.version) ? mcp.version : "";
}

/**
 * Arbeiten Claude und das Dashboard mit verschiedenen Fassungen? Dann `{ claude, dashboard, claudeAelter }`, sonst null.
 *
 * Das passiert nach jedem Update: das Dashboard startet neu, Claude Desktop hält seinen PBP-Server aber so lange am
 * Leben, bis es ganz beendet wird. Bis dahin sieht Claude die neuen Werkzeuge nicht.
 */
export function verbindungsAbweichung(au, mcp) {
  if (!au?.verfuegbar) return null;
  const claude = claudeFassung(mcp);
  const dashboard = au.laufend;
  if (!claude || !fassungsSchluessel(dashboard) || claude === dashboard) return null;
  return { claude, dashboard, claudeAelter: istNeuer(dashboard, claude) };
}

/**
 * Der Hinweis zum Auto-Update für die Hinweiszone — oder null.
 *
 * `dringend` hebt ihn über die Hinweise „Quellen“ und „Suche“: etwas, das gerade passiert ist (Rückfall,
 * Lauf, Fehler, Neustart nötig) oder gefragt werden muss, wartet nicht hinter einer Suchempfehlung.
 *
 * @param {object|null} au  Antwort von GET /api/auto-update
 * @param {object} [extra]  { releaseUrl } — die Seite der Veröffentlichung (aus /api/update-check);
 *                          { mcp } — die Verbindung zu Claude (`mcp_connection` aus dem Status);
 *                          { vorab } — eine neuere Vorabversion (`vorabNeu`), die PBP nennt, aber nie installiert (#1179)
 */
export function updateHinweis(au, extra = {}) {
  if (!au || !au.verfuegbar) return null;
  const neu = au.neu || null;
  const job = au.job || null;
  const anleitung = extra.releaseUrl
    ? { art: "link", url: extra.releaseUrl, label: "Update-Anleitung" }
    : { art: "link", url: "https://github.com/MadGapun/PBP/releases/latest", label: "Update-Anleitung" };

  if (au.rueckgang) {
    return {
      id: "update-rueckgang", ton: "amber", dringend: true,
      titel: `Version ${au.rueckgang.von} ließ sich nicht starten`,
      text: `PBP läuft wieder mit Version ${au.rueckgang.nach}. Du musst nichts tun; die neue Version wird nicht noch einmal automatisch installiert.`,
      aktionen: [{ art: "update-gesehen", label: "Verstanden" }, OPTIONEN],
    };
  }
  if (laeuft(au)) {
    return {
      id: "update-laeuft", ton: "neutral", dringend: true,
      titel: `Version ${job.version || ""} wird vorbereitet`.replace("  ", " "),
      text: job.text || "PBP lädt und prüft das Update im Hintergrund. Nichts wird beendet.",
      fortschritt: prozent(job),
      aktionen: [],
    };
  }
  if (job?.status === "fehler" && neu && neu.version === job.version) {
    return {
      id: "update-fehler", ton: "amber", dringend: true,
      titel: `Das Update auf Version ${job.version} hat nicht geklappt`,
      text: `${job.text || "Beim Update ist etwas schiefgegangen."} Die bisherige Version läuft unverändert weiter.`,
      aktionen: [{ art: "update-installieren", label: "Erneut versuchen", version: job.version }, anleitung, OPTIONEN],
    };
  }
  if (au.neustart_noetig && au.stufe !== "auto_still") {
    return {
      id: "update-neustart", ton: "neutral", dringend: true,
      titel: `Version ${au.aktuell} ist installiert`,
      text: `Sie gilt nach dem nächsten Neustart. ${neustartText()}`,
      aktionen: [OPTIONEN],
    };
  }
  const abweichung = au.stufe === "auto_still" ? null : verbindungsAbweichung(au, extra.mcp);
  if (abweichung) {
    return abweichung.claudeAelter
      ? {
        id: "update-verbindung", ton: "neutral", dringend: true,
        titel: `Claude arbeitet noch mit Version ${abweichung.claude}`,
        text: `PBP selbst läuft schon mit Version ${abweichung.dashboard}. Beende Claude Desktop komplett (Rechtsklick auf das Symbol in der Taskleiste → „Beenden“) und starte es neu, damit beides zusammenpasst.`,
        aktionen: [OPTIONEN],
      }
      : {
        id: "update-verbindung", ton: "neutral", dringend: true,
        titel: `Dieses Fenster läuft noch mit Version ${abweichung.dashboard}`,
        text: `Claude arbeitet schon mit Version ${abweichung.claude}. Beende PBP und starte es über die Verknüpfung „PBP Bewerbungs-Portal“ neu, damit beides zusammenpasst.`,
        aktionen: [OPTIONEN],
      };
  }
  // Keine fertige neue Version: eine neuere VORABVERSION wird genannt, mit dem Weg dorthin (#1179).
  if (!neu) return extra.vorab ? vorabHinweis(extra.vorab) : null;

  if (neu.status === "unvollstaendig") {
    return {
      id: "update", ton: "neutral", dringend: false,
      titel: `Version ${neu.version} ist erschienen`,
      text: neu.text || "Das automatische Update dafür ist noch nicht bereit. Du kannst sie von Hand installieren.",
      aktionen: [anleitung],
    };
  }
  const auszug = Array.isArray(neu.auszug) && neu.auszug.length ? `${neu.auszug[0]} ` : "";
  if (neu.frage_faellig) {
    return {
      id: "update-frage", ton: "neutral", dringend: true,
      titel: `Neue Version ${neu.version} – soll PBP Updates künftig selbst installieren?`,
      text: `${auszug}Ohne Antwort bleibt alles beim Alten. Du kannst das jederzeit unter Einstellungen › Updates ändern.`,
      beiVersion: neu.version,
      aktionen: ANTWORTEN.map((a) => ({ art: "update-antwort", antwort: a.id, label: a.label, titel: a.titel, version: neu.version })),
    };
  }
  if (au.blockiert && au.blockiert.dauerhaft) {
    return {
      id: "update", ton: "amber", dringend: false,
      titel: `Version ${neu.version} wurde nicht automatisch installiert`,
      text: `${au.blockiert.text || ""} Du kannst es erneut versuchen oder die Version von Hand installieren.`.trim(),
      aktionen: [{ art: "update-installieren", label: "Erneut versuchen", version: neu.version }, anleitung, OPTIONEN],
    };
  }
  if (neu.zurueckgenommen) {
    return {
      id: "update", ton: "neutral", dringend: false,
      titel: `Version ${neu.version} ist da, du bleibst bewusst bei der älteren`,
      text: "Du hast zu einer früheren Version zurückgeschaltet. PBP schaltet nicht von selbst wieder um.",
      aktionen: [{ art: "update-installieren", label: "Trotzdem installieren", version: neu.version }, OPTIONEN],
    };
  }
  if (au.stufe === "hinweis") {
    return {
      id: "update", ton: "neutral", dringend: false,
      titel: `Neue Version verfügbar: v${neu.version}`,
      text: `${auszug}Ein Klick installiert sie – du musst nichts herunterladen. Sie gilt nach dem nächsten Neustart.`,
      aktionen: [{ art: "update-installieren", label: "Jetzt aktualisieren", version: neu.version }, OPTIONEN],
    };
  }
  if (AUTOMATISCHE_STUFEN.includes(au.stufe)) {
    return {
      id: "update", ton: "neutral", dringend: false,
      titel: `Version ${neu.version} wird automatisch installiert`,
      text: "PBP lädt sie im Hintergrund, sobald nichts anderes läuft. Der Hinweis erscheint, wenn sie bereit ist.",
      aktionen: [{ art: "update-installieren", label: "Jetzt installieren", version: neu.version }, OPTIONEN],
    };
  }
  return {
    id: "update", ton: "neutral", dringend: false,
    titel: `Neue Version verfügbar: v${neu.version}`,
    text: `${auszug}Einfach drüberinstallieren – deine Daten bleiben erhalten. Oder PBP macht es selbst: siehe Update-Optionen.`,
    aktionen: [anleitung, OPTIONEN],
  };
}

/**
 * Wie der Neustart geht — an EINER Stelle, damit Hinweis, Einstellung und Seitenleiste dasselbe sagen (#1170 U4).
 *
 * Vorher stand überall „Beende PBP und Claude Desktop“. Was „PBP beenden“ heißt, wusste niemand: PBP läuft als
 * schwarzes Fenster „PBP Bewerbungs-Portal“ (Dashboard starten.bat), Claude Desktop hält seinen PBP-Server so
 * lange am Leben, bis es ganz beendet wird. Beides muss neu starten, damit die neue Version gilt.
 */
export const NEUSTART_SCHRITTE = [
  "Schließe das schwarze Fenster „PBP Bewerbungs-Portal“, falls es offen ist. Das ist das Dashboard.",
  "Beende Claude Desktop ganz: Rechtsklick auf das Claude-Symbol unten rechts in der Taskleiste → „Beenden“. Das Fenster zu schließen reicht nicht.",
  "Starte Claude Desktop und danach „PBP Bewerbungs-Portal“ vom Desktop neu.",
];

/** Die Schritte als ein Satz-Text, für Hinweise ohne Liste. */
export function neustartText() {
  return NEUSTART_SCHRITTE.map((s, i) => `${i + 1}. ${s}`).join(" ");
}

/** „Aktuell“ steht nur da, wenn nichts mehr aussteht: weder eine neuere Version noch ein Neustart (#1170 U4). */
export function zeigeAktuell(au) {
  return Boolean(au) && !au.neu && !au.neustart_noetig;
}

/** Die Zeile unter der Version in der Seitenleiste, solange eine installierte Version auf den Neustart wartet. */
export function seitenleisteText(au) {
  if (!au?.verfuegbar || !au.neustart_noetig) return "";
  return `Neustart nötig für v${au.aktuell}`;
}

/** Soll die Seitenleiste auf die Update-Einstellungen führen statt auf eine fremde Seite? */
export function seitenleisteFuehrtZuEinstellungen(au) {
  return Boolean(au?.verfuegbar);
}

const FASSUNG = /^(\d{1,3})\.(\d{1,3})\.(\d{1,4})(?:-(alpha|beta|rc)\.(\d{1,3}))?$/;
const RANG = { alpha: 1, beta: 2, rc: 3 };

/** Vergleichswert einer Fassung wie im Programm (`fassung.py`): Vorabversionen liegen vor der fertigen. */
export function fassungsSchluessel(fassung) {
  const m = FASSUNG.exec(typeof fassung === "string" ? fassung : "");
  if (!m) return null;
  return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] ? RANG[m[4]] : 9, m[5] ? Number(m[5]) : 0];
}

/** Ist `a` echt neuer als `b`? Bei einer ungültigen Seite: nein. */
export function istNeuer(a, b) {
  const x = fassungsSchluessel(a);
  const y = fassungsSchluessel(b);
  if (!x || !y) return false;
  for (let i = 0; i < x.length; i += 1) {
    if (x[i] !== y[i]) return x[i] > y[i];
  }
  return false;
}

/**
 * Ist diese Version schon installiert (und wartet nur auf den Neustart)? Dann ist sie kein „Update verfügbar“
 * mehr, auch wenn das laufende Programm noch die ältere ist.
 */
export function istSchonInstalliert(au, version) {
  return Boolean(au?.verfuegbar && au.aktuell && version && !istNeuer(version, au.aktuell));
}

// ── Vorabversionen (#1179) ─────────────────────────────────────────────────────────────
//
// Zwei Auskünfte zur selben Frage: Die allgemeine Prüfung (GET /api/update-check) nennt einer Beta-Installation auch
// neuere Betas; die feste Quelle des Auto-Updates (GET /api/auto-update) kennt nie eine Vorabversion — sie werden nie
// automatisch installiert, und an einer Beta hängt kein Update-Paket. Ohne diese Regeln sagte die Seitenleiste „Neue
// Version verfügbar“ und die Update-Seite „Aktuell“, ohne einen Knopf (Nutzerfrage 08.10.2026).

const ARCHIV_ADRESSE = "https://github.com/MadGapun/PBP/archive/refs/tags/";
const RELEASE_ADRESSE = "https://github.com/MadGapun/PBP/releases/tag/";

/** Warum PBP eine Vorabversion nicht von selbst installiert — überall dieser Satz. */
export const VORAB_ERKLAERUNG = "PBP installiert Vorabversionen nie von selbst, auch nicht mit der Stufe „Mit einem Klick“: "
  + "Sie sind zum Ausprobieren und können noch Fehler haben.";

/** Der Weg zu einer Vorabversion, in der Reihenfolge der Handgriffe. */
export const VORAB_SCHRITTE = [
  "Klicke „ZIP herunterladen“ und entpacke die Datei (Windows: Rechtsklick → „Alle extrahieren“).",
  "Starte im entpackten Ordner den Installer (Windows: Doppelklick auf INSTALLIEREN.bat, Mac: INSTALLIEREN.command). Einfach drüberinstallieren: Deine Daten bleiben erhalten, und vorher legt der Installer eine Sicherung an.",
  "Starte danach PBP und Claude Desktop neu, wie nach jedem Update.",
];

/** Ist das eine Vorabversion (Alpha, Beta, RC)? Eine ungültige Fassung: nein. */
export function istVorabversion(fassung) {
  const k = fassungsSchluessel(fassung);
  return Boolean(k) && k[3] !== 9;
}

/**
 * Eine neuere VORABVERSION, die PBP nennt, aber nie von selbst installiert — oder null.
 *
 * @param {object|null} au    Antwort von GET /api/auto-update
 * @param {object|null} info  Antwort von GET /api/update-check
 * @returns {{version: string, url: string, zip: string}|null}
 */
export function vorabNeu(au, info) {
  if (!info?.update_available) return null;
  const version = typeof info.latest_version === "string" ? info.latest_version : "";
  if (!istVorabversion(version)) return null;
  // Eine fertige neue Version geht vor und hat ihren eigenen Weg (Hinweis „Jetzt installieren“).
  if (au?.neu) return null;
  // Schon von Hand installiert und nur noch nicht neu gestartet: kein „Update verfügbar“ mehr.
  if (istSchonInstalliert(au, version)) return null;
  return {
    version,
    url: info.release_url || `${RELEASE_ADRESSE}v${version}`,
    zip: `${ARCHIV_ADRESSE}v${version}.zip`,
  };
}

/** Der Hinweis für die Hinweiszone des Dashboards: kurz, mit beiden Wegen (ZIP laden, Veröffentlichung lesen). */
export function vorabHinweis(vorab) {
  return {
    id: "update-vorab", ton: "neutral", dringend: false,
    titel: `Neue Vorabversion verfügbar: v${vorab.version}`,
    text: "PBP installiert Vorabversionen nie von selbst. Zum Ausprobieren: ZIP laden und den Installer darin starten "
      + "(Windows: INSTALLIEREN.bat) — einfach drüberinstallieren, deine Daten bleiben erhalten.",
    aktionen: [
      { art: "link", url: vorab.zip, label: "ZIP herunterladen" },
      { art: "link", url: vorab.url, label: "Veröffentlichung ansehen" },
    ],
  };
}
