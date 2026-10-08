function withJsonHeaders(options = {}) {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  return { ...options, headers };
}

function getErrorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data === "string") return data;
  // #1096: manche Endpunkte antworten mit `nachricht` (sonst stand nur "HTTP 400" da)
  return data.error || data.fehler || data.message || data.nachricht || fallback;
}

function normalizeBaseUrl(baseUrl = "") {
  return String(baseUrl).trim().replace(/\/+$/, "");
}

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

export function apiUrl(path) {
  if (!path) {
    return API_BASE_URL || "/";
  }

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  if (!API_BASE_URL) {
    return path;
  }

  return path.startsWith("/") ? `${API_BASE_URL}${path}` : `${API_BASE_URL}/${path}`;
}

export async function api(path, options = {}) {
  const response = await fetch(apiUrl(path), withJsonHeaders(options));
  const contentType = response.headers.get("content-type") || "";

  if (!response.ok) {
    let payload = null;
    try {
      payload = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
    } catch (error) {
      payload = null;
    }
    // #1094: Status und Antwort mitgeben — ein 409 (z.B. vermutete
    // Dublette) braucht die Angaben aus der Antwort, nicht nur den Text.
    const fehler = new Error(getErrorMessage(payload, `HTTP ${response.status}`));
    fehler.status = response.status;
    fehler.payload = payload;
    throw fehler;
  }

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response;
}

export async function optionalApi(path, options = {}) {
  let response;
  try {
    response = await fetch(apiUrl(path), withJsonHeaders(options));
  } catch {
    // Network error (server unreachable, CORS, etc.) — return null
    // instead of throwing so polling loops stay silent (#123).
    return null;
  }
  if (response.status === 404) {
    return null;
  }
  const contentType = response.headers.get("content-type") || "";

  if (!response.ok) {
    let payload = null;
    try {
      payload = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
    } catch (error) {
      payload = null;
    }
    throw new Error(getErrorMessage(payload, `HTTP ${response.status}`));
  }

  return contentType.includes("application/json") ? response.json() : response;
}

export async function postJson(path, body) {
  return api(path, { method: "POST", body: JSON.stringify(body) });
}

export async function putJson(path, body) {
  return api(path, { method: "PUT", body: JSON.stringify(body) });
}

export async function patchJson(path, body) {
  return api(path, { method: "PATCH", body: JSON.stringify(body) });
}

export async function deleteRequest(path, body) {
  const options = { method: "DELETE" };
  if (body !== undefined) options.body = JSON.stringify(body);
  return api(path, options);
}
