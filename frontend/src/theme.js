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

// v1.7.0-beta.57 (#626): Vorbelegte Theme-Presets fuer User die nicht
// jeden Token einzeln einstellen wollen. Jeder Preset enthaelt komplette
// Paletten fuer light + dark; "default" entspricht der DEFAULT_PALETTE
// und dient als Reset-Anker. Custom-Overrides ueberschreiben Preset-Werte
// pro Token (Mischbetrieb erlaubt).
export const THEME_PRESETS = [
  {
    id: "default",
    label: "PBP Standard",
    description: "Original-Schema mit teal/amber/coral/sky-Akzenten.",
    palette: DEFAULT_PALETTE,
  },
  {
    id: "modern_blue",
    label: "Modern Blau",
    description: "Kuehler Blauton dominant, ruhiger fuer lange Sessions.",
    palette: {
      dark: {
        shell: "14 18 32",
        panel: "22 30 50",
        "panel-strong": "32 42 66",
        ink: "228 236 252",
        muted: "150 168 200",
        line: "60 78 116",
        teal: "94 220 230",
        amber: "245 196 90",
        coral: "246 130 155",
        sky: "108 152 255",
      },
      light: {
        shell: "240 245 252",
        panel: "255 255 255",
        "panel-strong": "228 236 248",
        ink: "20 32 56",
        muted: "92 110 142",
        line: "200 216 236",
        teal: "20 130 154",
        amber: "200 124 26",
        coral: "210 50 100",
        sky: "30 96 220",
      },
    },
  },
  {
    id: "warm_sand",
    label: "Warm Sand",
    description: "Warme Erdtoene, weicher als der Standard.",
    palette: {
      dark: {
        shell: "30 25 22",
        panel: "44 36 32",
        "panel-strong": "56 46 40",
        ink: "246 236 222",
        muted: "176 158 138",
        line: "94 76 60",
        teal: "120 200 168",
        amber: "248 188 92",
        coral: "246 138 110",
        sky: "186 168 218",
      },
      light: {
        shell: "250 244 234",
        panel: "255 250 242",
        "panel-strong": "242 232 218",
        ink: "52 38 28",
        muted: "128 102 78",
        line: "224 208 184",
        teal: "32 136 110",
        amber: "200 118 28",
        coral: "200 76 60",
        sky: "120 96 168",
      },
    },
  },
  {
    id: "high_contrast",
    label: "High Contrast",
    description: "Maximaler Kontrast — Barrierefreiheit, Sehschwache.",
    palette: {
      dark: {
        shell: "0 0 0",
        panel: "16 16 20",
        "panel-strong": "30 30 38",
        ink: "255 255 255",
        muted: "200 204 214",
        line: "120 124 140",
        teal: "0 255 200",
        amber: "255 220 60",
        coral: "255 100 110",
        sky: "120 180 255",
      },
      light: {
        shell: "255 255 255",
        panel: "255 255 255",
        "panel-strong": "240 240 244",
        ink: "0 0 0",
        muted: "60 64 76",
        line: "120 124 140",
        teal: "0 110 96",
        amber: "168 96 0",
        coral: "190 16 56",
        sky: "20 64 200",
      },
    },
  },
];

const STORAGE_MODE = "pbp-theme-mode";
const STORAGE_CUSTOM = "pbp-theme-custom";
const STORAGE_PRESET = "pbp-theme-preset";

export function loadPreset() {
  try {
    const raw = localStorage.getItem(STORAGE_PRESET);
    if (!raw) return "default";
    return THEME_PRESETS.some((p) => p.id === raw) ? raw : "default";
  } catch {
    return "default";
  }
}

export function savePreset(id) {
  try { localStorage.setItem(STORAGE_PRESET, id); } catch { /* ignore */ }
}

export function getPresetPalette(id) {
  const preset = THEME_PRESETS.find((p) => p.id === id);
  return preset ? preset.palette : DEFAULT_PALETTE;
}

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

export function applyTheme(mode, custom, presetId) {
  if (typeof document === "undefined") return;
  const active = resolveActiveMode(mode);
  const root = document.documentElement;
  root.setAttribute("data-theme", active);
  // v1.7.0-beta.57 (#626): Preset-Palette als Basis. Custom-Override
  // pro Token gewinnt. Wenn presetId nicht gegeben oder "default":
  // setzen wir keine CSS-Variablen aus Preset, damit die styles.css-
  // Defaults greifen (Backwards-Compat zur alten Logik).
  const preset = presetId && presetId !== "default"
    ? getPresetPalette(presetId)[active] || {}
    : null;
  const overrides = (custom && custom[active]) || {};
  // alle Token-Overrides setzen, unbenutzte entfernen
  THEME_TOKENS.forEach(({ key }) => {
    const varName = `--color-${key}`;
    if (overrides[key]) {
      root.style.setProperty(varName, overrides[key]);
    } else if (preset && preset[key]) {
      root.style.setProperty(varName, preset[key]);
    } else {
      root.style.removeProperty(varName);
    }
  });
}
