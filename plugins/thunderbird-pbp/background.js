/* "An PBP senden" — Thunderbird-MailExtension (J2/#478, PBP v1.8).
 *
 * Rechtsklick auf eine oder MEHRERE markierte Nachrichten in der
 * Nachrichtenliste -> "An PBP senden". Jede Nachricht geht als .eml an
 * die lokale PBP-Ingest-API (127.0.0.1) und laeuft dort durch die volle
 * Pipeline (Duplikat-Erkennung, Bewerbungs-Zuordnung, Termine, Timeline).
 *
 * Thread senden: in Thunderbird den Thread markieren (Klick auf die
 * erste Nachricht, dann Strg/Cmd+Klick bzw. Umschalt+Klick auf die
 * weiteren — oder im Thread-Modus den zusammengefalteten Thread
 * anklicken und alle Nachrichten auswaehlen) und dann "An PBP senden".
 *
 * Architektur D1 (PBP-Wiki, Plan-Roadmap-v18): Das Add-on ist ein
 * EXTERNER Prozess und spricht nur ueber die REST-API — kein Zugriff
 * auf die PBP-Datenbank. Der API-Key stammt aus dem Pairing in den
 * PBP-Einstellungen (Erweiterungen -> Gekoppelte Plugins).
 */

const MENU_ID = "pbp-send";

browser.menus.create({
  id: MENU_ID,
  title: "An PBP senden",
  contexts: ["message_list"],
});

async function getSettings() {
  const stored = await browser.storage.local.get({
    pbpUrl: "http://127.0.0.1:8200",
    apiKey: "",
  });
  return {
    url: (stored.pbpUrl || "http://127.0.0.1:8200").replace(/\/+$/, ""),
    apiKey: (stored.apiKey || "").trim(),
  };
}

function notify(title, message) {
  browser.notifications.create({
    type: "basic",
    iconUrl: browser.runtime.getURL("icon-64.png"),
    title,
    message,
  });
}

function sanitizeFilename(subject) {
  const base = (subject || "nachricht")
    .replace(/[^\w\däöüÄÖÜß .-]+/g, "_")
    .slice(0, 60)
    .trim() || "nachricht";
  return base + ".eml";
}

async function getMessageFile(msg) {
  // TB 106+: getRaw kann direkt ein File liefern — byte-treu, kein Umweg.
  try {
    const file = await browser.messages.getRaw(msg.id, { data_format: "File" });
    if (file instanceof File) return file;
  } catch (e) {
    /* aeltere TB-Version -> Fallback unten */
  }
  const raw = await browser.messages.getRaw(msg.id);
  // Binary-String byte-treu in Bytes ueberfuehren (nie als UTF-8 deuten,
  // sonst korrumpieren Umlaute in Headern/Body).
  const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
  return new File([bytes], sanitizeFilename(msg.subject), {
    type: "message/rfc822",
  });
}

async function sendMessageToPbp(settings, msg) {
  const file = await getMessageFile(msg);
  const form = new FormData();
  form.append("file", file, sanitizeFilename(msg.subject));
  const resp = await fetch(settings.url + "/api/v1/ingest/email", {
    method: "POST",
    headers: { "X-PBP-API-Key": settings.apiKey },
    body: form,
  });
  if (!resp.ok) {
    let detail = "";
    try {
      const data = await resp.json();
      detail = data.error || JSON.stringify(data).slice(0, 120);
    } catch (e) {
      detail = "HTTP " + resp.status;
    }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  return resp.json();
}

browser.menus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== MENU_ID) return;

  const settings = await getSettings();
  if (!settings.apiKey) {
    notify(
      "PBP: Kopplung fehlt",
      "Erst in PBP koppeln (Einstellungen → Erweiterungen), dann den " +
        "API-Key in den Add-on-Einstellungen eintragen."
    );
    browser.runtime.openOptionsPage();
    return;
  }

  const messages = (info.selectedMessages && info.selectedMessages.messages) || [];
  if (messages.length === 0) {
    notify("PBP", "Keine Nachricht ausgewaehlt.");
    return;
  }

  let ok = 0;
  let duplikate = 0;
  let fehler = 0;
  for (const msg of messages) {
    try {
      const result = await sendMessageToPbp(settings, msg);
      if (result.status === "duplicate") duplikate += 1;
      else ok += 1;
    } catch (e) {
      fehler += 1;
      if (e.status === 401 || e.status === 403) {
        notify(
          "PBP: Key ungueltig",
          "Der API-Key wurde nicht akzeptiert (" + e.message + "). " +
            "In PBP neu koppeln und den Key in den Add-on-Einstellungen " +
            "aktualisieren."
        );
        return; // weitere Versuche sind sinnlos
      }
      console.error("PBP-Ingest fehlgeschlagen:", msg.subject, e);
    }
  }

  const teile = [];
  if (ok) teile.push(ok + " uebergeben");
  if (duplikate) teile.push(duplikate + " schon vorhanden (nur verknuepft)");
  if (fehler) teile.push(fehler + " fehlgeschlagen");
  notify(
    "PBP: " + (fehler && !ok ? "Uebergabe fehlgeschlagen" : "Fertig"),
    teile.join(", ") +
      (fehler && !ok
        ? " — laeuft das PBP-Dashboard? (" + settings.url + ")"
        : "")
  );
});
