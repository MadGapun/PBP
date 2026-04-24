// Theme-System (Beta.7 — #475)
// Single source of truth fuer Dark/Light-Paletten.
// CSS-Defaults in styles.css muessen mit DEFAULT_PALETTE.dark synchron bleiben.

export const THEME_TOKENS = [
  { key: "shell", label: "App-Hintergrund", hint: "Grundflaeche hinter allen Cards" },
  { key: "panel", label: "Card-Flaeche", hint: "Haupt-Cards (Bewerbungen, Jobs, Profil)" },
  { key: "panel-strong", label: "Hover/Toolbar", hint: "Aktive Tabs, Hover-Panels" },
  { key: "ink", label: "Haupttext", hint: "Ueberschriften, Werte" },
  { key: "muted", label: "Sekundaertext", hint: "Labels, Meta-Infos" },
  { key: "line", label: "Borders/Linien", hint: "Trennlinien, Card-Rahmen" },
  { key: "teal", label: "Akzent Teal", hint: "Primaere Aktionen, Highlights" },
  { key: "amber", label: "Akzent Amber", hint: "Warnungen, Badges" },
  { key: "coral", label: "Akzent Coral", hint: "Fehler, Zombie-Status" },
  { key: "sky", label: "Akzent Sky", hint: "Info, Links, Interviews" },
];

export const DEFAULT_PALETTE = {
  dark: {
    shell: "18 20 30",
    panel: "28 32 46",
    "panel-strong": "36 40 56",
    ink: "230 236 250",
    muted: "140 152 178",
    line: "68 76 100",
    teal: "94 234 212",
    amber: "251 191 36",
    coral: "251 113 133",
    sky: "129 161 255",
  },
  light: {
    shell: "248 249 252",
    panel: "255 255 255",
    "panel-strong": "242 244 248",
    ink: "24 28 42",
    muted: "100 112 136",
    line: "220 225 235",
    teal: "13 148 136",
    amber: "217 119 6",
    coral: "225 29 72",
    sky: "37 99 235",
  },
};

const STORAGE_MODE = "pbp-theme-mode";
const STORAGE_CUSTOM = "pbp-theme-custom";

export function rgbToHex(rgbString) {
  if (!rgbString) return "#000000";
  const parts = rgbString.trim().split(/\s+/).map((n) => Math.max(0, Math.min(255, parseInt(n, 10) || 0)));
  if (parts.length !== 3) return "#000000";
  return "#" + parts.map((n) => n.toString(16).padStart(2, "0")).join("");
}

export function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

export function loadMode() {
  try {
    const raw = localStorage.getItem(STORAGE_MODE);
    return raw === "light" || raw === "dark" || raw === "system" ? raw : "system";
  } catch {
    return "system";
  }
}

export function saveMode(mode) {
  try { localStorage.setItem(STORAGE_MODE, mode); } catch { /* ignore */ }
}

export function loadCustom() {
  try {
    const raw = localStorage.getItem(STORAGE_CUSTOM);
    if (!raw) return { light: {}, dark: {} };
    const parsed = JSON.parse(raw);
    return {
      light: parsed?.light && typeof parsed.light === "object" ? parsed.light : {},
      dark: parsed?.dark && typeof parsed.dark === "object" ? parsed.dark : {},
    };
  } catch {
    return { light: {}, dark: {} };
  }
}

export function saveCustom(custom) {
  try { localStorage.setItem(STORAGE_CUSTOM, JSON.stringify(custom)); } catch { /* ignore */ }
}

export function resolveActiveMode(mode) {
  if (mode === "light" || mode === "dark") return mode;
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return "dark";
}

export function applyTheme(mode, custom) {
  if (typeof document === "undefined") return;
  const active = resolveActiveMode(mode);
  const root = document.documentElement;
  root.setAttribute("data-theme", active);
  const overrides = (custom && custom[active]) || {};
  // alle Token-Overrides setzen, unbenutzte entfernen
  THEME_TOKENS.forEach(({ key }) => {
    const varName = `--color-${key}`;
    if (overrides[key]) {
      root.style.setProperty(varName, overrides[key]);
    } else {
      root.style.removeProperty(varName);
    }
  });
}
