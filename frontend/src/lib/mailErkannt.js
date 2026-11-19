// #1412 D5: was PBP in einer hochgeladenen Mail erkannt hat, steht in der
// Meldung — Termin und erkannter Status. Der Status wird nur ANGEBOTEN.

function zeitText(start) {
  const m = String(start || "").match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!m) return "";
  return `${m[3]}.${m[2]}.${m[4] ? `, ${m[4]}:${m[5]} Uhr` : ""}`;
}

/** Meldung nach dem Hochladen einer Datei in eine Bewerbung: { text, angebot }. */
export function uploadMeldung(dateiname, ergebnis) {
  if (ergebnis?.duplicate_of) {
    return { text: `'${dateiname}' verknüpft (war schon vorhanden).`, angebot: null };
  }
  const erkannt = ergebnis?.mail_erkannt;
  if (!erkannt) {
    return { text: `'${dateiname}' hochgeladen und verknüpft.`, angebot: null };
  }
  const teile = [`'${dateiname}' hochgeladen und verknüpft`];
  const termine = (ergebnis.meetings || []).map((m) => zeitText(m.start || m.meeting_date)).filter(Boolean);
  if (termine.length === 1) teile.push(`Termin ${termine[0]} angelegt`);
  else if (erkannt.termine > 1) teile.push(`${erkannt.termine} Termine angelegt`);
  if (erkannt.angebot) teile.push(`Status erkannt: ${erkannt.angebot.name}`);
  return { text: `${teile.join(" · ")}.`, angebot: erkannt.angebot || null };
}
