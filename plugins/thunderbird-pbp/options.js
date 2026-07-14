/* Options-Seite: PBP-URL + API-Key speichern, Verbindung testen. */

const urlInput = document.getElementById("pbpUrl");
const keyInput = document.getElementById("apiKey");
const statusEl = document.getElementById("status");

async function load() {
  const stored = await browser.storage.local.get({
    pbpUrl: "http://127.0.0.1:8200",
    apiKey: "",
  });
  urlInput.value = stored.pbpUrl;
  keyInput.value = stored.apiKey;
}

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok ? "ok" : "fehler";
}

document.getElementById("save").addEventListener("click", async () => {
  await browser.storage.local.set({
    pbpUrl: urlInput.value.trim() || "http://127.0.0.1:8200",
    apiKey: keyInput.value.trim(),
  });
  setStatus("Gespeichert.", true);
});

document.getElementById("test").addEventListener("click", async () => {
  const url = (urlInput.value.trim() || "http://127.0.0.1:8200").replace(/\/+$/, "");
  const key = keyInput.value.trim();
  if (!key) {
    setStatus("Erst den API-Key eintragen (Pairing in PBP).", false);
    return;
  }
  setStatus("Teste...", true);
  try {
    const resp = await fetch(url + "/api/v1/ingest/ping", {
      headers: { "X-PBP-API-Key": key },
    });
    if (resp.ok) {
      const data = await resp.json();
      setStatus(
        "Verbunden mit PBP " + (data.pbp_version || "?") +
          " als Plugin „" + (data.plugin || "?") + "“.",
        true
      );
    } else if (resp.status === 401) {
      setStatus("Key unbekannt oder widerrufen — in PBP neu koppeln.", false);
    } else {
      setStatus("PBP antwortet mit HTTP " + resp.status + ".", false);
    }
  } catch (e) {
    setStatus("PBP nicht erreichbar — laeuft das Dashboard? (" + url + ")", false);
  }
});

load();
