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
 * Der Hinweis zum Auto-Update für die Hinweiszone — oder null.
 *
 * `dringend` hebt ihn über die Hinweise „Quellen“ und „Suche“: etwas, das gerade passiert ist (Rückfall,
 * Lauf, Fehler, Neustart nötig) oder gefragt werden muss, wartet nicht hinter einer Suchempfehlung.
 *
 * @param {object|null} au  Antwort von GET /api/auto-update
 * @param {object} [extra]  { releaseUrl } — die Seite der Veröffentlichung (aus /api/update-check)
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
      text: "Sie gilt nach dem nächsten Neustart. Beende PBP und Claude Desktop komplett (Rechtsklick auf das Symbol in der Taskleiste → „Beenden“) und starte beides neu.",
      aktionen: [OPTIONEN],
    };
  }
  if (!neu) return null;

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

/** Die Zeile unter der Version in der Seitenleiste, wenn läuft und installiert auseinanderfallen. */
export function seitenleisteText(au) {
  if (!au?.verfuegbar || !au.neustart_noetig) return "";
  return `läuft v${au.laufend} · installiert v${au.aktuell}`;
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
