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
  subNavigation = null,
  badges = {},
  meta = {},
  brand = {},
  collapsed = false,
  onToggle,
}) {
  return (
    <aside
      className={cn(
        "app-sidebar shrink-0 bg-shell/80 backdrop-blur-md border-r border-white/8",
        "flex flex-col h-screen sticky top-0 z-40 transition-all duration-200",
        collapsed ? "w-[60px]" : "w-[240px]"
      )}
      aria-label="Hauptnavigation"
    >
      {/* Brand-Block — Versionsnummer + 3-stufiger MCP-Status (beta.24) */}
      <div className="px-4 py-4 border-b border-white/8">
        {!collapsed ? (
          <>
            <p className="brand-title text-[13px] font-semibold text-ink leading-tight">
              Persönliches<br/>Bewerbungs-Portal
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px]">
              {brand.version ? (
                <span className="font-mono text-muted/40">v{brand.version}</span>
              ) : null}
              {brand.connectionStatus ? (() => {
                const cfg = CONN_CONFIG[brand.connectionStatus] || CONN_CONFIG.disconnected;
                return (
                  <button
                    type="button"
                    onClick={brand.onConnectionClick}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors",
                      "hover:bg-white/[0.06]",
                      cfg.color
                    )}
                    title={brand.connectionStatus === "connected"
                      ? "Claude Desktop oeffnen"
                      : `MCP: ${cfg.label} — Klicke fuer Hilfe`}
                  >
                    <span className={cn("h-1.5 w-1.5 rounded-full", cfg.dot)} />
                    <span className="font-medium">{cfg.label}</span>
                  </button>
                );
              })() : null}
            </div>
          </>
        ) : (
          <span className="text-[13px] font-semibold text-ink" title="Persönliches Bewerbungs-Portal">
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
                    collapsed && "justify-center"
                  )}
                  data-page={tab.id}
                  onClick={() => onSelectPage?.(tab.id)}
                  title={collapsed ? tab.title : undefined}
                >
                  <Icon size={16} className={isActive ? "text-sky shrink-0" : "shrink-0"} />
                  {!collapsed && (
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
                {!collapsed && subItems ? (
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

      {/* Toggle-Button am Boden */}
      {onToggle ? (
        <button
          type="button"
          onClick={onToggle}
          className="border-t border-white/8 px-4 py-2.5 text-[11px] text-muted/60 hover:text-ink hover:bg-white/[0.03] transition-colors flex items-center justify-center gap-1.5"
          title={collapsed ? "Sidebar ausklappen" : "Sidebar einklappen"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} className="rotate-90" />}
          {!collapsed && <span>Einklappen</span>}
        </button>
      ) : null}
    </aside>
  );
}
