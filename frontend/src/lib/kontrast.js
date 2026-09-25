// Kontrast nach WCAG 2.1 (G71, #1087 H4). Die Paletten in theme.js
// muessen fuer Lesetext 4,5:1 erreichen — der Node-Test prueft jede
// Voreinstellung in beiden Modi.

function kanal(v) {
  const c = v / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function leuchtdichte(rgb) {
  const [r, g, b] = String(rgb).trim().split(/[\s,]+/).map(Number);
  return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b);
}

export function kontrast(a, b) {
  const [h, d] = [leuchtdichte(a), leuchtdichte(b)].sort((x, y) => y - x);
  return (h + 0.05) / (d + 0.05);
}

export const MINDEST_KONTRAST = 4.5;
export const TEXT_TOKENS = ["ink", "muted", "teal", "amber", "coral", "sky"];
export const FLAECHEN = ["shell", "panel", "panel-strong"];
