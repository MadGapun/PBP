/**
 * Mail-Ordner als Quelle — was die Oberfläche aus /api/mail-quelle macht (#947, v1.8).
 *
 * Framework-frei, damit der Node-Test die Regeln prüfen kann: die Zeile über dem Schalter, die Zahlen je Ordner und
 * die Warnstufen. Die Entscheidungen selbst (was gelesen werden darf) trifft PBP auf dem Server, nie diese Datei.
 */

/** Die Mail-Programme, wie der Server sie kennt (`ANBIETER` in services/mail_quelle.py). */
export const ANBIETER_LISTE = [
  { id: "thunderbird", label: "Thunderbird" },
  { id: "outlook", label: "Outlook" },
  { id: "sonstige", label: "Anderes Mail-Programm" },
];

export function anbieterLabel(id) {
  return ANBIETER_LISTE.find((a) => a.id === id)?.label || id || "";
}

/** Die eine Zeile über dem Schalter: ehrlich darüber, ob gerade wirklich etwas gelesen werden darf. */
export function statusText(u) {
  if (!u) return "";
  if (u.unlesbar) return "Aus (die gespeicherte Einstellung ließ sich nicht sicher lesen)";
  if (u.neu_bestaetigen) return "Aus (in einer Beta eingeschaltet, bitte erneut bestätigen)";
  if (!u.scan_aktiv) return "Aus";
  const n = Array.isArray(u.freigaben) ? u.freigaben.length : 0;
  if (n === 0) return "An, aber kein Ordner freigegeben – es wird nichts gelesen";
  return `An – ${n} Ordner freigegeben`;
}

/** Ton des Abzeichens: nur „wirksam“ ist auffällig, alles andere ruhig. */
export function statusTon(u) {
  if (u?.wirksam) return "amber";
  return "neutral";
}

export function zeitText(iso) {
  const t = Date.parse(iso || "");
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Die Zahlen je Ordner: letzter Lauf, verarbeitete Mails, daraus entstandene Stellen. */
export function zahlenText(f) {
  if (!f || !f.letzter_lauf) return "noch nichts gelesen";
  const mails = Number(f.mails) || 0;
  const stellen = Number(f.stellen) || 0;
  return `${mails} ${mails === 1 ? "Mail" : "Mails"}, ${stellen} ${stellen === 1 ? "Stelle" : "Stellen"}, zuletzt ${zeitText(f.letzter_lauf)}`;
}

/** Kann der Mensch freigeben? Der Ordnername muss etwas enthalten; alles Weitere prüft der Server. */
export function darfFreigeben(anbieter, ordner) {
  return Boolean(ANBIETER_LISTE.some((a) => a.id === anbieter) && String(ordner || "").replace(/[\\/\s]/g, "") !== "");
}

/** Was nach dem Antwort-Status der Freigabe passiert. */
export function freigabeSchritt(antwort) {
  switch (antwort?.status) {
    case "freigegeben": return "fertig";
    case "posteingang_warnung": return "warnung";
    case "schon_da": return "schon_da";
    default: return "fehler";
  }
}
