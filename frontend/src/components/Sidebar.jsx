/**
 * Sidebar-Navigation (#508 / v1.6.0-beta.23)
 *
 * Loest die horizontale Top-Tab-Reihe ab, die ab ca. 1400px Breite mit dem
 * Theme-Toggle und Profile-Switcher kollidiert (#507) und auf Laptop-
 * Bildschirmen unbedienbar wurde.
 *
 * Architektur (Variante B aus #508):
 *   - Persistente linke Sidebar mit Branding, Hauptbereichen und Versions-/
 *     Connection-Status.
 *   - Sub-Navigation pro Hauptbereich nur unter dem aktiven Bereich
 *     eingerueckt sichtbar (kaskadierend).
 *   - Auf schmalen Viewports einklappbar (Hamburger in der Top-Bar).
 *   - Vertikales Scrollen, falls die Liste mehr als die Hoehe braucht.
 *
 * Sub-Navigation wird per Prop reingegeben — die einzelnen Pages bleiben
 * fuer ihre interne Sub-Tab-Logik selbst zustaendig (uns interessiert hier
 * nur die Anzeige in der Sidebar).
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, Link2, Link2Off } from "lucide-react";

import { cn } from "@/utils";

// MCP-Connection-Status-Konfig (3-stufig, gleiche Logik wie das alte
// Sidebar-Badge in App.jsx — beta.24 / User-Feedback nach beta.23)
const CONN_CONFIG = {
  connected:    { color: "text-teal",  dot: "bg-teal",     label: "Verbunden",      Icon: Link2 },
  unknown:      { color: "text-amber", dot: "bg-amber",    label: "Pruefe…",   Icon: Link2 },
  disconnected: { color: "text-coral", dot: "bg-coral",    label: "Nicht verbunden", Icon: Link2Off },
};

export default function Sidebar({
  tabs,
  activePage,
  onSelectPage,
  // subNavigation: { items: [{id, label, active?}], onSelect: (id) => void }
  // wird nur unter dem aktiven Hauptbereich eingerueckt angezeigt.
  subNavigation = null,
  badges = {},
  meta = {},
  brand = {},
  collapsed = false,
  onToggle,
  // beta.30: Slot fuer zusaetzliche Inhalte am unteren Rand der Sidebar
  // — typisch fuer Live-Status-Badges (z.B. JobsucheStatusBadge).
  footerSlot = null,
}) {
  // beta.30 / User-Feedback: Wenn Sidebar collapsed, soll sie bei Hover
  // automatisch ausklappen (Overlay), beim Verlassen wieder einklappen.
  // Layout-Breite bleibt 60px, damit der Inhalt rechts nicht springt;
  // das innere Panel floatet dann als Overlay.
  const [hoverExpanded, setHoverExpanded] = useState(false);
  const visualCollapsed = collapsed && !hoverExpanded;
  const isFloatingOverlay = collapsed && hoverExpanded;

  return (
    <aside
      className={cn(
        "app-sidebar shrink-0 relative transition-[width] duration-200",
        collapsed ? "w-[60px]" : "w-[240px]"
      )}
      aria-label="Hauptnavigation"
      onMouseEnter={() => collapsed && setHoverExpanded(true)}
      onMouseLeave={() => setHoverExpanded(false)}
    >
      {/* Innerer Container — sticky-positioniert, breitet sich beim
          Hover ueber den Layout-Wrapper aus (Overlay), ohne den
          Layout-Flow zu beeinflussen. */}
      <div
        className={cn(
          "sticky top-0 h-screen flex flex-col bg-shell/80 backdrop-blur-md border-r border-white/8",
          "transition-[width,box-shadow] duration-200",
          visualCollapsed ? "w-[60px]" : "w-[240px]",
          isFloatingOverlay && "absolute top-0 left-0 z-50 shadow-2xl shadow-black/40",
          !isFloatingOverlay && "z-40"
        )}
      >
      {/* Status-Block (beta.35 / User-Feedback): App-Branding wandert in
          die Top-Bar; Sidebar zeigt nur die laufenden Status-Indikatoren
          untereinander — Version, MCP-Heartbeat, Suchstatus. */}
      <div className="px-4 py-3 border-b border-white/8">
        {!visualCollapsed ? (
          <div className="flex flex-col gap-1.5">
            {/* brand-title bleibt als verstecktes Element fuer Tests-Selektoren */}
            <span className="brand-title sr-only">Persönliches Bewerbungs-Portal</span>
            {brand.version ? (
              <span className="font-mono text-[10px] text-muted/40 select-none whitespace-nowrap">
                v{brand.version}
              </span>
            ) : null}
            {brand.connectionStatus ? (() => {
              const cfg = CONN_CONFIG[brand.connectionStatus] || CONN_CONFIG.disconnected;
              return (
                <button
                  type="button"
                  onClick={brand.onConnectionClick}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium transition-colors w-fit",
                    "hover:bg-white/[0.06]",
                    cfg.color
                  )}
                  title={brand.connectionStatus === "connected"
                    ? "Claude Desktop oeffnen"
                    : `MCP: ${cfg.label} — Klicke fuer Hilfe`}
                >
                  <span className={cn("h-1.5 w-1.5 rounded-full", cfg.dot)} />
                  <span>{cfg.label}</span>
                </button>
              );
            })() : null}
            {/* Suchstatus erscheint hier ueber den Footer-Slot */}
          </div>
        ) : (
          <span className="text-[13px] font-semibold text-ink block text-center" title="Persönliches Bewerbungs-Portal">
            PBP
          </span>
        )}
      </div>

      {/* Hauptbereiche */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-0.5">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activePage === tab.id;
            const badge = badges[tab.id];
            const subItems = isActive && subNavigation ? subNavigation : null;

            return (
              <li key={tab.id}>
                <button
                  type="button"
                  className={cn(
                    "tab w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors",
                    isActive
                      ? "bg-white/[0.08] text-ink"
                      : "text-muted hover:text-ink hover:bg-white/[0.04]",
                    visualCollapsed && "justify-center"
                  )}
                  data-page={tab.id}
                  onClick={() => onSelectPage?.(tab.id)}
                  title={visualCollapsed ? tab.title : undefined}
                >
                  <Icon size={16} className={isActive ? "text-sky shrink-0" : "shrink-0"} />
                  {!visualCollapsed && (
                    <>
                      <span className="flex-1 text-left">{tab.title}</span>
                      {badge ? (
                        <span
                          id={`tab-badge-${tab.id}`}
                          className="tab-badge inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-amber/80 px-1 text-[10px] font-bold leading-none text-shell"
                        >
                          {badge}
                        </span>
                      ) : (
                        <span id={`tab-badge-${tab.id}`} className="hidden">{badge}</span>
                      )}
                    </>
                  )}
                </button>
                {/* Sub-Navigation (kaskadierend, nur unter aktivem Bereich) */}
                {!visualCollapsed && subItems ? (
                  <ul className="ml-6 mt-0.5 mb-1 space-y-0.5 border-l border-white/8 pl-2">
                    {subItems.items.map((sub) => (
                      <li key={sub.id}>
                        <button
                          type="button"
                          className={cn(
                            "w-full text-left rounded-md px-2 py-1.5 text-[12px] transition-colors",
                            sub.active
                              ? "bg-sky/10 text-sky"
                              : "text-muted/80 hover:text-ink hover:bg-white/[0.03]"
                          )}
                          onClick={() => subItems.onSelect?.(sub.id)}
                        >
                          {sub.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {/* Tooltip-Meta (nur Screenreader) */}
                <span id={`tab-meta-${tab.id}`} className="sr-only">{meta[tab.id] || tab.defaultMeta}</span>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer-Slot — z.B. JobsucheStatusBadge (beta.30) */}
      {!visualCollapsed && footerSlot ? (
        <div className="border-t border-white/8 px-3 py-2">
          {footerSlot}
        </div>
      ) : null}

      {/* Toggle-Button am Boden */}
      {onToggle ? (
        <button
          type="button"
          onClick={onToggle}
          className="border-t border-white/8 px-4 py-2.5 text-[11px] text-muted/60 hover:text-ink hover:bg-white/[0.03] transition-colors flex items-center justify-center gap-1.5"
          title={visualCollapsed ? "Sidebar ausklappen" : "Sidebar einklappen"}
        >
          {visualCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} className="rotate-90" />}
          {!visualCollapsed && <span>Einklappen</span>}
        </button>
      ) : null}
      </div>
    </aside>
  );
}
