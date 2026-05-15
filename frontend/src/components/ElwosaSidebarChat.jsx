/**
 * ElwosaSidebarChat — v1.7.0-beta.37 (#599)
 *
 * Live-Statusanzeige der lokalen AI als Chat-Stream in der linken Sidebar.
 * Charakter-Briefing: docs/elwosa-character.md
 *
 * Verhalten:
 * - 30s-Polling auf /api/elwosa/messages
 * - Crossfade-In bei neuer Nachricht
 * - Klickbare Code-Spans (Backticks) → Clipboard + Toast
 * - 👁-Toggle: Session-Hide via localStorage
 * - "..."-Menu: Pause / Aus / Verlauf loeschen
 * - Bei Sidebar collapsed: nur Avatar mit Pulse + Hover-Overlay
 * - Bei AI off: einzige Status-Nachricht, dann still
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronDown, Eye, EyeOff, MoreHorizontal, Pause, Settings, Trash2, X } from "lucide-react";

import { api, deleteRequest, postJson } from "@/api";

const HIDE_KEY = "pbp_elwosa_hidden_until";
const POLL_INTERVAL_MS = 30 * 1000;
const HEARTBEAT_INTERVAL_MS = 60 * 60 * 1000; // 1 Stunde
const HIDE_DURATION_MS = 30 * 60 * 1000; // 30 Minuten Session-Hide

function readHiddenUntil() {
  try {
    const raw = localStorage.getItem(HIDE_KEY);
    if (!raw) return 0;
    return Number(raw) || 0;
  } catch {
    return 0;
  }
}

function setHiddenUntil(ts) {
  try { localStorage.setItem(HIDE_KEY, String(ts)); } catch {}
}

/**
 * v1.7.0-beta.41 (#614): Markup-Renderer fuer Elwosa-Linien.
 *
 * Unterstuetzt drei Markup-Formen, die parallel im Text vorkommen koennen:
 * 1. `Backtick-Code` → klickbarer Code-Span, kopiert in Clipboard
 * 2. **Wort** → fett (max 1-2 mal pro Linie, dezent)
 * 3. [link:type:id|label] → klickbarer Link
 *    - type=pause + id=N → ruft elwosa_pause(N)
 *    - type=application + id=hash → navigiert zur Bewerbung
 *    - type=job + id=hash → navigiert zur Stelle
 *
 * Reihenfolge: erst Links extrahieren (greedy), dann Bold, dann Code.
 */
const LINK_RE = /\[link:([a-z_]+):([^|\]]+)\|([^\]]+)\]/g;
const BOLD_RE = /\*\*([^*]+)\*\*/g;
const CODE_RE = /`[^`]+`/g;

function renderWithMarkup(text, { onCopy, onPause, onNavigate }) {
  if (!text) return null;
  // Tokenize: erst Links rauspflicken, dann auf jeden Teil Bold + Code anwenden
  const tokens = [];
  let lastIdx = 0;
  let m;
  LINK_RE.lastIndex = 0;
  while ((m = LINK_RE.exec(text)) !== null) {
    if (m.index > lastIdx) {
      tokens.push({ type: "plain", text: text.slice(lastIdx, m.index) });
    }
    tokens.push({ type: "link", linkType: m[1], linkId: m[2], label: m[3] });
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) {
    tokens.push({ type: "plain", text: text.slice(lastIdx) });
  }

  return tokens.flatMap((tok, ti) => {
    if (tok.type === "link") {
      return [
        <button
          key={`l-${ti}`}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (tok.linkType === "pause") {
              onPause?.(parseInt(tok.linkId, 10) || 60);
            } else if (tok.linkType === "wiki") {
              // v1.7.0-beta.45 (#623): Wiki-Deep-Link in neuem Tab
              const url = `https://github.com/MadGapun/PBP/wiki/${encodeURIComponent(tok.linkId)}`;
              window.open(url, "_blank", "noopener,noreferrer");
            } else {
              onNavigate?.(tok.linkType, tok.linkId);
            }
          }}
          className="text-teal hover:text-teal/80 underline decoration-dotted decoration-teal/40 underline-offset-2 cursor-pointer"
          title={tok.linkType === "pause"
            ? `Elwosa fuer ${tok.linkId} Minuten pausieren`
            : `${tok.linkType}: ${tok.linkId}`}
        >
          {tok.label}
        </button>,
      ];
    }
    // Plain-Text: Bold + Code anwenden
    return renderBoldAndCode(tok.text, ti, onCopy);
  });
}

function renderBoldAndCode(text, baseKey, onCopy) {
  // Erst Bold extrahieren
  const parts = [];
  let lastIdx = 0;
  let m;
  BOLD_RE.lastIndex = 0;
  while ((m = BOLD_RE.exec(text)) !== null) {
    if (m.index > lastIdx) {
      parts.push({ type: "code-or-text", text: text.slice(lastIdx, m.index) });
    }
    parts.push({ type: "bold", text: m[1] });
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) {
    parts.push({ type: "code-or-text", text: text.slice(lastIdx) });
  }

  return parts.flatMap((p, pi) => {
    const key = `${baseKey}-${pi}`;
    if (p.type === "bold") {
      return [<strong key={key} className="font-semibold text-ink">{p.text}</strong>];
    }
    // Code-Spans im plain Text
    const segs = p.text.split(CODE_RE);
    const codes = p.text.match(CODE_RE) || [];
    const out = [];
    segs.forEach((seg, si) => {
      if (seg) out.push(<span key={`${key}-s${si}`}>{seg}</span>);
      if (si < codes.length) {
        const code = codes[si].slice(1, -1);
        out.push(
          <button
            key={`${key}-c${si}`}
            type="button"
            onClick={(e) => { e.stopPropagation(); onCopy?.(code); }}
            className="font-mono text-[11px] underline-offset-2 underline decoration-dotted decoration-teal/50 hover:text-teal cursor-pointer"
            title="Klicken um zu kopieren"
          >
            {code}
          </button>
        );
      }
    });
    return out;
  });
}

function relativeTime(iso) {
  if (!iso) return "";
  try {
    const ts = new Date(iso);
    const diff = Date.now() - ts.getTime();
    const min = Math.floor(diff / 60000);
    if (min < 1) return "gerade eben";
    if (min < 60) return `vor ${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `vor ${h}h`;
    return ts.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  } catch { return iso.slice(11, 16); }
}

function dayLabel(iso) {
  try {
    const ts = new Date(iso);
    const today = new Date();
    if (ts.toDateString() === today.toDateString()) return "Heute";
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (ts.toDateString() === yesterday.toDateString()) return "Gestern";
    return ts.toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "2-digit" });
  } catch { return ""; }
}

export default function ElwosaSidebarChat({ collapsed = false, onToast, onNavigateToSettings, onNavigate }) {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState(null);
  const [hidden, setHidden] = useState(() => readHiddenUntil() > Date.now());
  const [showMenu, setShowMenu] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const pollRef = useRef(null);
  // v1.7.0-beta.48 (#611): Sticky-Bottom-Auto-Scroll
  const scrollRef = useRef(null);
  const stickyRef = useRef(true);  // True = User ist am Ende
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);
  const [unreadBelow, setUnreadBelow] = useState(0);
  const lastMessageCountRef = useRef(0);

  // Polling + Heartbeat
  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      try {
        const [msgs, st] = await Promise.all([
          api("/api/elwosa/messages?limit=10"),
          api("/api/elwosa/status"),
        ]);
        if (cancelled) return;
        setMessages((msgs?.messages || []).slice().reverse()); // neueste unten
        setStatus(st);
      } catch {}
    }
    // v1.7.0-beta.40 (#609): Heartbeat fuer Welt-Trigger + Welcome
    async function heartbeat() {
      try {
        await postJson("/api/elwosa/heartbeat", {});
        // sofort danach Messages neu laden
        if (!cancelled) await fetchAll();
      } catch {}
    }
    fetchAll();
    heartbeat();  // einmal beim Mount
    pollRef.current = setInterval(fetchAll, POLL_INTERVAL_MS);
    const heartbeatInterval = setInterval(heartbeat, HEARTBEAT_INTERVAL_MS);
    // Beim Tab-Sichtbar-werden: Heartbeat ausloesen
    const onVis = () => {
      if (document.visibilityState === "visible") {
        heartbeat();
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
      clearInterval(heartbeatInterval);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  // Hide-Timer
  useEffect(() => {
    if (!hidden) return;
    const remaining = readHiddenUntil() - Date.now();
    if (remaining <= 0) { setHidden(false); return; }
    const t = setTimeout(() => setHidden(false), remaining);
    return () => clearTimeout(t);
  }, [hidden]);

  // v1.7.0-beta.48 (#611): Sticky-Bottom-Auto-Scroll.
  // - Wenn User am Ende ist (innerhalb 30px Toleranz): bei neuen
  //   Nachrichten automatisch nach unten scrollen.
  // - Wenn User aktiv nach oben gescrollt hat: nicht aufdraengen,
  //   stattdessen "X neue Nachrichten unten"-Indicator zeigen.
  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom < 30;
    stickyRef.current = atBottom;
    if (atBottom) {
      setShowJumpToBottom(false);
      setUnreadBelow(0);
    }
  }

  function jumpToBottom() {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    stickyRef.current = true;
    setShowJumpToBottom(false);
    setUnreadBelow(0);
  }

  // Auto-Scroll bei neuen Nachrichten — nur wenn sticky-bottom aktiv
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const newCount = messages.length;
    const wasMore = newCount > lastMessageCountRef.current;
    if (stickyRef.current) {
      // User ist am Ende → mitscrollen
      el.scrollTop = el.scrollHeight;
    } else if (wasMore) {
      // User ist oben → Counter hochzaehlen + Indicator zeigen
      const delta = newCount - lastMessageCountRef.current;
      setUnreadBelow((u) => u + delta);
      setShowJumpToBottom(true);
    }
    lastMessageCountRef.current = newCount;
  }, [messages]);

  // Wenn AI off + Settings disabled: kompletter Hide
  if (!status) return null;
  if (!status.is_active && status.ai_state === "off") {
    return null; // Elwosa schweigt komplett
  }

  // Wenn User per 👁 versteckt hat: in collapsed-Mode kompletter Hide,
  // sonst nur kleiner Wieder-einblenden-Button
  if (hidden && !collapsed) {
    return (
      <div className="px-3 py-2 text-[10px] text-muted/40">
        <button
          type="button"
          onClick={() => { setHiddenUntil(0); setHidden(false); }}
          className="flex items-center gap-1 hover:text-ink"
        >
          <Eye size={12} /> Elwosa wieder einblenden
        </button>
      </div>
    );
  }
  if (hidden && collapsed) return null;

  async function copyCode(code) {
    try {
      await navigator.clipboard.writeText(code);
      onToast?.(`„${code}" kopiert — paste in deinen Claude-Chat`, "success");
    } catch {
      onToast?.("Kopieren fehlgeschlagen", "danger");
    }
  }

  async function dismissMessage(id) {
    try {
      await deleteRequest(`/api/elwosa/messages/${id}`);
      setMessages((m) => m.filter((x) => x.id !== id));
    } catch {}
  }

  async function pauseElwosa(minuten) {
    try {
      await postJson("/api/elwosa/pause", { minuten });
      onToast?.(`Elwosa pausiert fuer ${minuten} Minuten`, "success");
      setShowMenu(false);
    } catch {}
  }

  async function clearHistory() {
    if (!confirm("Elwosa-Verlauf wirklich loeschen?")) return;
    try {
      // Alle Messages dismissen ist die User-freundliche Variante
      await Promise.all(
        messages.map((m) => deleteRequest(`/api/elwosa/messages/${m.id}`))
      );
      setMessages([]);
      onToast?.("Verlauf geloescht", "success");
      setShowMenu(false);
    } catch {}
  }

  function hideForSession() {
    setHiddenUntil(Date.now() + HIDE_DURATION_MS);
    setHidden(true);
  }

  // Avatar-Element
  const avatar = (
    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal/15 text-[11px] font-semibold text-teal">
      E
    </div>
  );

  // Collapsed Mode (60px Sidebar): nur Avatar mit Pulse
  if (collapsed) {
    const hasUnread = messages.some((m) => !m.read_at);
    return (
      <div
        className="relative flex justify-center py-2"
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        title={messages[messages.length - 1]?.content || "Elwosa"}
      >
        <div className="relative">
          {avatar}
          {hasUnread && (
            <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-teal animate-pulse" />
          )}
        </div>
        {isHovering && messages.length > 0 && (
          <div className="absolute left-12 bottom-0 z-50 w-72 rounded-lg border border-white/10 bg-bg/95 p-3 shadow-xl backdrop-blur-md">
            <div className="mb-2 flex items-center gap-2">
              {avatar}
              <span className="text-[11px] font-medium text-ink">Elwosa</span>
            </div>
            <div className="space-y-2">
              {messages.slice(-3).map((m) => (
                <p key={m.id} className="text-[11px] leading-relaxed text-muted/80">
                  {renderWithMarkup(m.content, { onCopy: copyCode, onPause: pauseElwosa, onNavigate })}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Expanded Mode
  const groupedByDay = [];
  let lastDay = null;
  messages.forEach((m) => {
    const d = dayLabel(m.created_at);
    if (d !== lastDay) {
      groupedByDay.push({ type: "day", label: d });
      lastDay = d;
    }
    groupedByDay.push({ type: "msg", msg: m });
  });

  return (
    <div className="border-t border-white/5 px-3 py-2">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {avatar}
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted/70">
            Elwosa
          </span>
        </div>
        <div className="flex items-center gap-1">
          {/* v1.7.0-beta.38 (#601): Zahnrad statt mood-Anzeige.
              Klick fuehrt zu Einstellungen -> Lokale KI -> Elwosa. */}
          <button
            type="button"
            onClick={() => onNavigateToSettings?.("ai")}
            className="text-muted/40 hover:text-ink"
            title="Elwosa-Einstellungen oeffnen"
          >
            <Settings size={12} />
          </button>
          <button
            type="button"
            onClick={hideForSession}
            className="text-muted/40 hover:text-ink"
            title="Fuer 30 Minuten ausblenden"
          >
            <EyeOff size={12} />
          </button>
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowMenu(!showMenu)}
              className="text-muted/40 hover:text-ink"
              title="Menue"
            >
              <MoreHorizontal size={12} />
            </button>
            {showMenu && (
              <div className="absolute right-0 top-5 z-50 w-44 rounded-lg border border-white/10 bg-bg/95 py-1 shadow-xl backdrop-blur-md">
                <button
                  type="button"
                  onClick={() => pauseElwosa(60)}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-[11px] text-muted hover:bg-white/5"
                >
                  <Pause size={11} /> 1 Stunde pausieren
                </button>
                <button
                  type="button"
                  onClick={() => pauseElwosa(240)}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-[11px] text-muted hover:bg-white/5"
                >
                  <Pause size={11} /> 4 Stunden pausieren
                </button>
                <button
                  type="button"
                  onClick={clearHistory}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-[11px] text-muted hover:bg-white/5"
                >
                  <Trash2 size={11} /> Verlauf loeschen
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* v1.7.0-beta.48 (#611): Adaptive Hoehe + Sticky-Bottom-Scroll.
          v1.7.0-beta.60 (#625): max-h auf 32vh reduziert + min-h auf 100px,
          damit das Hauptmenue oben Vorrang hat. Der umgebende Sidebar-Footer
          cappt zusaetzlich auf 42vh und scrollt wenn noetig. */}
      <div className="relative">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="space-y-2 min-h-[100px] max-h-[32vh] overflow-y-auto pr-1"
        >
          {messages.length === 0 && (
            <p className="text-[10px] text-muted/40 italic">
              {status.ai_state === "active"
                ? "Elwosa ist still. Wenn die AI arbeitet, redet sie."
                : `Elwosa: ${status.ai_state}`}
            </p>
          )}
          {groupedByDay.map((item, i) => {
            if (item.type === "day") {
              return (
                <div key={`day-${i}`} className="text-[9px] uppercase tracking-wider text-muted/30 pt-1">
                  ── {item.label} ──
                </div>
              );
            }
            const m = item.msg;
            return (
              <div
                key={m.id}
                className="group rounded-md bg-white/[0.02] p-2 hover:bg-white/[0.04] transition-colors"
              >
                <p className="text-[11px] leading-relaxed text-muted/85">
                  {renderWithMarkup(m.content, { onCopy: copyCode, onPause: pauseElwosa, onNavigate })}
                </p>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-[9px] text-muted/30">
                    {relativeTime(m.created_at)}
                  </span>
                  <button
                    type="button"
                    onClick={() => dismissMessage(m.id)}
                    className="text-muted/20 opacity-0 group-hover:opacity-100 hover:text-coral transition-opacity"
                    title="Diese Nachricht ausblenden"
                  >
                    <X size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        {/* Indicator: User hat hoch gescrollt + neue Nachricht kam */}
        {showJumpToBottom && (
          <button
            type="button"
            onClick={jumpToBottom}
            className="absolute bottom-1 left-1/2 -translate-x-1/2 flex items-center gap-1 rounded-full bg-teal/90 px-2.5 py-1 text-[10px] font-medium text-white shadow-lg hover:bg-teal transition-all"
            title="Zu den neuesten Nachrichten springen"
          >
            <ChevronDown size={11} />
            {unreadBelow > 0 ? `${unreadBelow} neu` : "neueste"}
          </button>
        )}
      </div>
    </div>
  );
}
