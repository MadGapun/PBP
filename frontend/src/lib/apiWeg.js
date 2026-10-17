/**
 * Optionaler API-Weg der KI (#1236, v1.8) — was die Oberfläche aus GET /api/api-weg macht.
 *
 * Framework-frei, damit der Node-Test die Regeln prüfen kann: wann die Karte überhaupt erscheint, die Zeilen über den
 * Schaltern, das Budget und der Verbrauch. Die Entscheidungen selbst (darf diese Aufgabe jetzt über die API laufen?
 * stimmt der Betrag? ist der Schlüssel gültig?) trifft PBP auf dem Server, nie diese Datei.
 */

/** Die Karte erscheint nur, wenn es etwas zu zeigen gibt: ein Schlüssel, eine Freigabe oder schon Verbrauch. */
export function sichtbar(u) {
  return Boolean(u && u.sichtbar);
}

/** „2026-10-16“ -> „16.10.2026“ (ein reines Datum, ohne Zeitzone: es ist in jeder Zeitzone derselbe Tag). */
export function datumText(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
}

export function zeitText(iso) {
  const t = Date.parse(iso || "");
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Die Zeile zur Prüfung des Schlüssels. „Gültig“ steht nur nach einer echten Probe, nie wegen des bloßen Vorhandenseins. */
export function pruefungText(p) {
  switch (p?.ergebnis) {
    case "gueltig": return `Gültig – die API hat die Probeanfrage angenommen${p.zeit ? ` (${zeitText(p.zeit)})` : ""}`;
    case "ungueltig": return "Die API hat den Schlüssel abgelehnt";
    case "unklar": return `Die Probe hat kein klares Ergebnis gebracht${p.code ? " (siehe letzter Aufruf)" : ""}`;
    default: return "Noch nicht geprüft";
  }
}

export function pruefungTon(p) {
  if (p?.ergebnis === "gueltig") return "success";
  if (p?.ergebnis === "ungueltig") return "danger";
  return "neutral";
}

/** Eine Aufgabe in einem Satz: aus, bereit oder freigegeben, aber gerade ruhend (mit Grund vom Server). */
export function aufgabeStatus(a) {
  if (!a) return "";
  if (!a.freigegeben) return "Aus";
  if (a.bereit) return "Freigegeben und bereit";
  return `Freigegeben, aber gerade nicht genutzt: ${a.grund_text || "unbekannter Grund"}`;
}

export function aufgabeTon(a) {
  if (!a?.freigegeben) return "neutral";
  return a.bereit ? "success" : "amber";
}

/** Die neue Liste der freigegebenen Aufgaben, wenn der Mensch eine ein- oder ausschaltet. */
export function neueAuswahl(u, aufgabeId, an) {
  const aktuell = (u?.aufgaben || []).filter((a) => a.freigegeben).map((a) => a.id);
  const ohne = aktuell.filter((id) => id !== aufgabeId);
  return an ? [...ohne, aufgabeId] : ohne;
}

/** „5“, „5,50“, „5.5“ -> Zahl; alles andere -> null. Der Server prüft noch einmal (Obergrenze, Rundung auf Cent). */
export function budgetEingabe(text) {
  const t = String(text ?? "").trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  const n = Number(t);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/** Wie viel vom Budget ist verbraucht (0–100)? null, wenn es kein Budget gibt. */
export function verbrauchProzent(u) {
  const budget = u?.budget?.usd;
  if (!budget || budget <= 0) return null;
  const verbraucht = Number(u?.verbrauch?.usd) || 0;
  return Math.max(0, Math.min(100, Math.round((verbraucht / budget) * 100)));
}

export function budgetZeile(u) {
  if (!u?.budget?.gesetzt) return "Kein Budget gesetzt – ohne Obergrenze ruft PBP die API nicht auf.";
  return `Verbraucht ${u.verbrauch?.text || "0,00 US-Dollar"} von ${u.budget.text}`;
}

export function verbrauchZeile(u) {
  const v = u?.verbrauch;
  if (!v || !v.aufrufe) return "Bisher kein Aufruf über PBP.";
  const n = (x) => Number(x || 0).toLocaleString("de-DE");
  const aufrufe = `${n(v.aufrufe)} ${v.aufrufe === 1 ? "Aufruf" : "Aufrufe"}`;
  const seit = v.seit ? `, seit ${zeitText(v.seit).slice(0, 10)}` : "";
  return `${aufrufe} (${n(v.eingabe_tokens)} Tokens ein, ${n(v.ausgabe_tokens)} aus), ${v.text}${seit}`;
}

/** Der letzte Aufruf, mit Grund, falls er scheiterte. */
export function letzterAufrufText(l) {
  if (!l) return "";
  const wann = l.zeit ? ` (${zeitText(l.zeit)})` : "";
  return l.ok ? `Letzter Aufruf: gelungen${wann}` : `Letzter Aufruf: gescheitert${wann} – ${l.text || l.code || "unbekannter Grund"}`;
}

/** Kann der Mensch die Probe anstoßen? Ohne Schlüssel gibt es nichts zu prüfen. */
export function kannPruefen(u) {
  return Boolean(u?.schluessel_gesetzt);
}

/** Die Zeile für die Datenschutz-Anzeige: nur wenn der Server die vierte Zeile liefert. */
export function datenflussApi(dataFlow) {
  return Array.isArray(dataFlow?.sent_to_api) && dataFlow.sent_to_api.length ? dataFlow.sent_to_api : null;
}
