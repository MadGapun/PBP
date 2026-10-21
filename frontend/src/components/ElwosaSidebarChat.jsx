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
import { sichereAdresse } from "@/lib/webAdresse";
import { bestaetigen } from "@/lib/bestaetigung";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronDown, Eye, EyeOff, MoreHorizontal, Pause, Settings, Trash2, X } from "lucide-react";

import { api, deleteRequest, postJson } from "@/api";
import { HilfeAntwort, HilfeEingabe, useHilfeFrage } from "@/components/HilfeFrage";
import { neueNachrichten } from "@/lib/elwosaStrom";
import { ansageText, seitenleisteFragt, stromMit } from "@/lib/hilfeFrage";

const HIDE_KEY = "pbp_elwosa_hidden_until";
const POLL_INTERVAL_MS = 30 * 1000;
const HEARTBEAT_INTERVAL_MS = 60 * 60 * 1000; // 1 Stunde
const HIDE_DURATION_MS = 30 * 60 * 1000; // 30 Minuten Session-Hide
const AM_ENDE_TOLERANZ = 30; // px: so nah am Ende gilt der Mensch noch als "am Ende"

/** #1256 (F58): Steht der Bereich am Ende? Gerechnet mit der Geometrie von JETZT, nicht mit dem, was ein Scroll-Ereignis vor einer Weile meldete. */
function stehtAmEnde(el) {
  return Boolean(el) && el.scrollHeight - el.scrollTop - el.clientHeight < AM_ENDE_TOLERANZ;
}

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
            } else if (tok.linkType === "prompt") {
              // F24 (#713): fertigen Claude-Prompt in die Zwischenablage
              onCopy?.(tok.linkId);
            } else {
              onNavigate?.(tok.linkType, tok.linkId);
            }
          }}
          className="text-teal hover:text-teal underline decoration-dotted decoration-teal/40 underline-offset-2 cursor-pointer"
          title={tok.linkType === "pause"
            ? `Elwosa für ${tok.linkId} Minuten pausieren`
            : tok.linkType === "prompt"
              ? "Kopiert den fertigen Prompt — danach in Claude einfügen"
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
            className="font-mono text-xs underline-offset-2 underline decoration-dotted decoration-teal/50 hover:text-teal cursor-pointer"
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

export default function ElwosaSidebarChat({ collapsed = false, onToast, onCopyPrompt, onOeffnen, onNavigateToSettings, onNavigate, className = "" }) {
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
  // #1256 (F58): die groesste Kennung, die der Mensch schon gesehen hat (null: noch nichts geladen). Neu ist, was eine groessere traegt - die ZAHL der
  // Nachrichten taugt nicht: der Verlauf holt nur zehn, bei voller Liste bleibt sie gleich, und nach dem Ausblenden steigt sie ohne neue Nachricht.
  const letzteKennung = useRef(null);
  // #1256 (F58): so hoch war der Bereich, als wir ihn zuletzt ausgerichtet haben (der Groessenbeobachter vergleicht damit)
  const sichtHoehe = useRef(0);
  const groessenBeobachter = useRef(null);
  // #1256 (F58): stand der Mensch am Ende, BEVOR die neue Liste ins Bild kam? Gemessen beim Eintreffen der Daten (null: kein Eintreffen, etwa beim Ausblenden).
  const warAmEnde = useRef(null);
  // #1254 (F57): der Zustand der Fragen zur Bedienung liegt hier und nicht im Feld darunter: die Antworten stehen im Bereich der Nachrichten
  // (EIN Bereich zum Scrollen), nur das Feld bleibt unten.
  const hilfe = useHilfeFrage({ onToast });
  const neuesterHilfeEintrag = hilfe.verlauf.length ? hilfe.verlauf[hilfe.verlauf.length - 1].id : 0;
  const gesehenerHilfeEintrag = useRef(0);

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
        // #1256 (F58): ob der Mensch am Ende steht, wird JETZT an der Geometrie gemessen, bevor die neue Liste im Bild steht. Das Scroll-Ereignis zu
        // einem Sprung ans Ende kann noch ausstehen (es laeuft erst im naechsten Bild): stickyRef waere dann veraltet, die Meldung bliebe verdeckt.
        warAmEnde.current = stehtAmEnde(scrollRef.current);
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

  // v1.7.12 (#822): read_at setzen, sobald der Stream tatsaechlich
  // sichtbar ist. Der Endpoint existierte seit je — er wurde nur nie
  // aufgerufen, deshalb war read_at bei allen Nachrichten null und das
  // naheliegendste Frequenz-Signal fehlte (durchgehend ungelesene
  // Ambiente-Linien daempfen serverseitig das Kontingent).
  useEffect(() => {
    if (collapsed || hidden) return;
    if (!messages.some((m) => !m.read_at)) return;
    postJson("/api/elwosa/messages/mark-read", {})
      .then(() => {
        setMessages((prev) => prev.map((m) =>
          m.read_at ? m : { ...m, read_at: new Date().toISOString() }));
      })
      .catch(() => {});
  }, [messages, collapsed, hidden]);

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
    const atBottom = distanceFromBottom < AM_ENDE_TOLERANZ;
    stickyRef.current = atBottom;
    if (atBottom) {
      setShowJumpToBottom(false);
      setUnreadBelow(0);
    }
  }

  // #1256 (F58): Der Bereich meldet, wenn sich seine HOEHE aendert, ohne dass jemand scrollt (der Kopf der Seitenleiste waechst um eine Zeile, die
  // Fenstergroesse aendert sich). Wer am Ende stand, bleibt am Ende: sonst rutscht die letzte Meldung aus dem Bild, und das verspaetete Scroll-Ereignis
  // zu einem Sprung rechnet schon mit der neuen Hoehe und haelt den Menschen faelschlich fuer "nicht am Ende" - die naechste Meldung bliebe verdeckt.
  // Als Ref-Funktion, weil es den Bereich erst gibt, wenn der Status da ist, und nicht mehr, solange Elwosa ausgeblendet ist.
  const listeRef = useCallback((el) => {
    groessenBeobachter.current?.disconnect();
    groessenBeobachter.current = null;
    scrollRef.current = el;
    if (!el) return;
    // ein neuer Bereich beginnt unten wie ein Chat (nach dem Wiedereinblenden stand er sonst oben, bei den aeltesten Nachrichten)
    stickyRef.current = true;
    el.scrollTop = el.scrollHeight;
    sichtHoehe.current = el.clientHeight;
    if (typeof ResizeObserver === "undefined") return;
    groessenBeobachter.current = new ResizeObserver(() => {
      const liste = scrollRef.current;
      if (!liste) return;
      // Abstand zum Ende zweimal gerechnet: mit der Hoehe von VORHER (stand der Mensch am Ende, bevor sich etwas aenderte? das Scroll-Ereignis eines
      // Sprungs kann schon mit der neuen Hoehe gerechnet haben) und mit der von JETZT (reicht der Bereich nach dem Wachsen bis ans Ende?).
      const abstandVorher = liste.scrollHeight - liste.scrollTop - sichtHoehe.current;
      const abstandJetzt = liste.scrollHeight - liste.scrollTop - liste.clientHeight;
      sichtHoehe.current = liste.clientHeight;
      if (Math.min(abstandVorher, abstandJetzt) >= AM_ENDE_TOLERANZ) return; // wer oben liest, bleibt stehen
      liste.scrollTop = liste.scrollHeight;
      stickyRef.current = true;
      setShowJumpToBottom(false);
      setUnreadBelow(0);
    });
    groessenBeobachter.current.observe(el);
  }, []);

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
    // #1256 (F58): neu ist, was eine groessere Kennung traegt als die zuletzt gesehene - nicht, was die Liste laenger macht (sie holt nur zehn)
    const { anzahl: neue, hoechste } = neueNachrichten(letzteKennung.current, messages);
    letzteKennung.current = hoechste;
    // #1256 (F58): folgt der Mensch dem Ende? Entweder hat er es zuletzt getan (stickyRef) ODER er stand beim Eintreffen der Daten am Ende (die Geometrie
    // von damals): das Scroll-Ereignis zu seinem Sprung kann noch ausstehen, dann steht in stickyRef noch der Zustand davor.
    const folgt = stickyRef.current || warAmEnde.current === true;
    warAmEnde.current = null;
    if (folgt) {
      // User ist am Ende → mitscrollen
      el.scrollTop = el.scrollHeight;
    } else if (neue > 0) {
      // User ist oben → Counter hochzaehlen + Indicator zeigen
      setUnreadBelow((u) => u + neue);
      setShowJumpToBottom(true);
    }
  }, [messages]);

  // #1254 (F57): nach einer Frage scrollt der Bereich an den ANFANG der neuen Antwort, nicht ans Ende: die Frage und der erste Treffer sind zu
  // sehen, der Rest liegt darunter. Am Ende stuende sonst nur das Unterste einer langen Antwort im Bild.
  useLayoutEffect(() => {
    if (neuesterHilfeEintrag === gesehenerHilfeEintrag.current) return;
    gesehenerHilfeEintrag.current = neuesterHilfeEintrag;
    const liste = scrollRef.current;
    const eintrag = liste?.querySelector(`[data-hilfe-eintrag="${neuesterHilfeEintrag}"]`);
    if (!liste || !eintrag) return;
    liste.scrollTop += eintrag.getBoundingClientRect().top - liste.getBoundingClientRect().top - 4;
  }, [neuesterHilfeEintrag]);

  // Wenn AI off + Settings disabled: kompletter Hide
  if (!status) return null;
  if (!status.is_active && status.ai_state === "off") {
    return null; // Elwosa schweigt komplett
  }

  // Wenn User per 👁 versteckt hat: in collapsed-Mode kompletter Hide,
  // sonst nur kleiner Wieder-einblenden-Button
  if (hidden && !collapsed) {
    return (
      <div className="px-3 py-2 text-xs text-muted">
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

  // G72 (#1087 E4): derselbe Kopierweg wie ueberall — ein "/name" wird
  // zur Anleitung aufgeloest, ein Fehlschlag zeigt den Text zum
  // Selbstkopieren.
  async function copyCode(code) {
    await onCopyPrompt?.(code, { erfolg: `„${code}“ kopiert — in deinen Claude-Chat einfügen.` });
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
      onToast?.(`Elwosa pausiert für ${minuten} Minuten`, "success");
      setShowMenu(false);
    } catch {}
  }

  async function clearHistory() {
    if (!(await bestaetigen({ text: "Elwosa-Verlauf wirklich löschen?" }))) return;
    try {
      // Alle Messages dismissen ist die User-freundliche Variante
      await Promise.all(
        messages.map((m) => deleteRequest(`/api/elwosa/messages/${m.id}`))
      );
      setMessages([]);
      onToast?.("Verlauf gelöscht", "success");
      setShowMenu(false);
    } catch {}
  }

  function hideForSession() {
    setHiddenUntil(Date.now() + HIDE_DURATION_MS);
    setHidden(true);
  }

  // Avatar-Element
  const avatar = (
    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal/15 text-xs font-semibold text-teal">
      E
    </div>
  );

  // Collapsed Mode (60px Sidebar): nur Avatar mit Pulse
  if (collapsed) {
    const hasUnread = messages.some((m) => !m.read_at);
    return (
      <div
        className="relative flex justify-center py-2"
        onMouseEnter={() => {
          setIsHovering(true);
          // #822: Hover-Popup zeigt die letzten Linien — das zaehlt als
          // gelesen, sonst bleibt die Daempfung im collapsed-Modus aktiv.
          if (hasUnread) {
            postJson("/api/elwosa/messages/mark-read", {})
              .then(() => {
                setMessages((prev) => prev.map((m) =>
                  m.read_at ? m : { ...m, read_at: new Date().toISOString() }));
              })
              .catch(() => {});
          }
        }}
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
          <div className="absolute left-12 bottom-0 z-50 w-72 rounded-lg border border-white/10 bg-shell/95 p-3 shadow-xl backdrop-blur-md">
            <div className="mb-2 flex items-center gap-2">
              {avatar}
              <span className="text-xs font-medium text-ink">Elwosa</span>
            </div>
            <div className="space-y-2">
              {messages.slice(-3).map((m) => (
                <p key={m.id} className="text-xs leading-relaxed text-muted">
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
  const fragenAktiv = seitenleisteFragt(status);
  // #1254 (F57): Elwosas Nachrichten und die Antworten der Hilfe stehen nach der Zeit in EINEM Strom, die neueste unten wie in einem Chat (eine
  // Nachricht nach einer Antwort kommt UNTER die Antwort); vor jeder Reihe von Antworten steht die Zeile "Fragen zur Bedienung": die Hilfe ist nicht Elwosa.
  const strom = stromMit(messages, fragenAktiv ? hilfe.verlauf : []);
  const groupedByDay = [];
  let lastDay = null;
  let letzteArt = null;
  strom.forEach((x) => {
    const d = dayLabel(x.art === "hilfe" ? new Date(x.t).toISOString() : x.nachricht.created_at);
    if (d !== lastDay) {
      groupedByDay.push({ type: "day", label: d });
      lastDay = d;
    }
    if (x.art === "hilfe") {
      if (letzteArt !== "hilfe") groupedByDay.push({ type: "hilfe-kopf" });
      groupedByDay.push({ type: "hilfe", eintrag: x.eintrag });
    } else {
      groupedByDay.push({ type: "msg", msg: x.nachricht });
    }
    letzteArt = x.art;
  });
  const ansage = fragenAktiv && hilfe.verlauf.length > 0 ? ansageText(hilfe.verlauf[hilfe.verlauf.length - 1]) : "";

  return (
    /* v1.7.17 (#907): Flex-Column mit durchgereichter Hoehe — Header
       bleibt stehen (shrink-0), NUR die Nachrichtenliste scrollt.
       Vorher: maxHeight:100% gegen ein height:auto-Elternteil ist in
       CSS unaufloesbar (= none) — der innere Scroller scrollte nie,
       stattdessen schob die Liste den ganzen Footer zum Scrollen. */
    <div className={`border-t border-white/5 px-3 py-2 flex min-h-0 flex-col ${className}`} data-elwosa-chat>
      <div className="mb-2 flex shrink-0 items-center justify-between">
        <div className="flex items-center gap-2">
          {avatar}
          <span className="text-xs font-semibold uppercase tracking-wider text-muted">
            Elwosa
          </span>
        </div>
        <div className="flex items-center gap-1">
          {/* v1.7.0-beta.38 (#601): Zahnrad statt mood-Anzeige.
              Klick fuehrt zu Einstellungen -> Lokale KI -> Elwosa. */}
          <button aria-label="Elwosa-Einstellungen öffnen"
            type="button"
            onClick={() => onNavigateToSettings?.("ai")}
            className="text-muted hover:text-ink"
            title="Elwosa-Einstellungen öffnen"
          >
            <Settings size={12} />
          </button>
          <button aria-label="Für 30 Minuten ausblenden"
            type="button"
            onClick={hideForSession}
            className="text-muted hover:text-ink"
            title="Für 30 Minuten ausblenden"
          >
            <EyeOff size={12} />
          </button>
          <div className="relative">
            <button aria-label="Menü"
              type="button"
              onClick={() => setShowMenu(!showMenu)}
              className="text-muted hover:text-ink"
              title="Menü"
            >
              <MoreHorizontal size={12} />
            </button>
            {showMenu && (
              <div className="absolute right-0 top-5 z-50 w-44 rounded-lg border border-white/10 bg-shell/95 py-1 shadow-xl backdrop-blur-md">
                <button
                  type="button"
                  onClick={() => pauseElwosa(60)}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-muted hover:bg-white/5"
                >
                  <Pause size={11} /> 1 Stunde pausieren
                </button>
                <button
                  type="button"
                  onClick={() => pauseElwosa(240)}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-muted hover:bg-white/5"
                >
                  <Pause size={11} /> 4 Stunden pausieren
                </button>
                <button
                  type="button"
                  onClick={clearHistory}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-muted hover:bg-white/5"
                >
                  <Trash2 size={11} /> Verlauf löschen
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* v1.7.0-beta.48 (#611): Adaptive Hoehe + Sticky-Bottom-Scroll.
          v1.7.0-beta.61 (#625 Folge-Fix): Keine festen vh-Werte mehr.
          Container darueber gibt via flex:1 + min-h:0 vor wieviel Platz
          zur Verfuegung steht — Elwosa fuellt das aus und scrollt intern.
          Auf grossen Screens wird Elwosa entsprechend gross. */}
      <div className="relative flex-1 min-h-0">
        <div
          ref={listeRef}
          onScroll={handleScroll} data-elwosa-liste
          className="h-full space-y-2 overflow-y-auto pr-1"
        >
          {messages.length === 0 && (
            <p className="text-xs text-muted italic">
              {status.ai_state === "active"
                ? "Elwosa ist still. Wenn die AI arbeitet, redet sie."
                : `Elwosa: ${status.ai_state}`}
            </p>
          )}
          {groupedByDay.map((item, i) => {
            if (item.type === "day") {
              return (
                <div key={`day-${i}`} className="text-xs uppercase tracking-wider text-muted pt-1">
                  ── {item.label} ──
                </div>
              );
            }
            if (item.type === "hilfe-kopf") {
              return (
                <div key={`hilfe-kopf-${i}`} className="text-xs uppercase tracking-wider text-muted pt-1" data-hilfe-trennzeile>
                  <span aria-hidden="true">── </span>Fragen zur Bedienung<span aria-hidden="true"> ──</span>
                </div>
              );
            }
            if (item.type === "hilfe") {
              return <HilfeAntwort key={`hilfe-${item.eintrag.id}`} eintrag={item.eintrag} kompakt onOeffnen={onOeffnen} copyPrompt={onCopyPrompt} />;
            }
            const m = item.msg;
            return (
              <div
                key={m.id} data-elwosa-nachricht
                className="group rounded-md bg-white/[0.02] p-2 hover:bg-white/[0.04] transition-colors"
              >
                <p className="text-xs leading-relaxed text-muted">
                  {renderWithMarkup(m.content, { onCopy: copyCode, onPause: pauseElwosa, onNavigate })}
                </p>
                {/* #823 (F37): dezenter Verweis unter der Linie — extern
                    in neuem Tab, pbp://-Deeplinks per Tab-Navigation. */}
                {m.link_url && (
                  m.link_url.startsWith("pbp://") ? (
                    <button
                      type="button"
                      onClick={() => {
                        const teil = m.link_url.replace("pbp://", "").split("/");
                        onNavigate?.(teil[0] === "tab" ? teil[1] : teil[0]);
                      }}
                      className="mt-0.5 text-xs text-teal underline decoration-dotted hover:text-teal">
                      {m.link_label || "Ansehen"}
                    </button>
                  ) : (
                    <a href={sichereAdresse(m.link_url)} target="_blank" rel="noopener noreferrer"
                      className="mt-0.5 inline-block text-xs text-teal underline decoration-dotted hover:text-teal">
                      {m.link_label || "Mehr dazu"}
                    </a>
                  )
                )}
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-xs text-muted">
                    {relativeTime(m.created_at)}
                  </span>
                  <button aria-label="Diese Nachricht ausblenden"
                    type="button"
                    onClick={() => dismissMessage(m.id)}
                    className="text-muted hover:text-coral transition-colors"
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
            className="absolute bottom-1 left-1/2 -translate-x-1/2 flex items-center gap-1 rounded-full bg-teal/90 px-2.5 py-1 text-xs font-medium text-shell shadow-lg hover:bg-teal transition-all"
            title="Zu den neuesten Nachrichten springen"
          >
            <ChevronDown size={11} />
            {unreadBelow > 0 ? `${unreadBelow} neu` : "neueste"}
          </button>
        )}
      </div>
      {/* #1233 (F51): Fragen zur Bedienung - nur, wenn die lokale KI laeuft (Nutzerwunsch 16.10.2026). Die Antworten sind Karten aus
          Hilfe, FAQ, Wiki und Prompt-Katalog; Fragen werden nicht gespeichert. #1254: hier steht nur das Feld (fest unter dem Verlauf, wie bei
          einem Chat); die Antworten stehen im Strom oben, im Bereich zum Scrollen. */}
      {fragenAktiv && (
        <div className="mt-2 shrink-0 border-t border-white/5 pt-2" data-sidebar-hilfe data-hilfe-frage="kompakt">
          <HilfeEingabe hilfe={hilfe} kompakt />
        </div>
      )}
      {/* Vorleseprogramme: eine neue Antwort der Hilfe wird gemeldet, auch wenn sie mitten im Strom steht (der Rahmen ist schon da, bevor etwas darin steht). */}
      {fragenAktiv && <div className="sr-only" aria-live="polite" data-hilfe-ansage>{ansage}</div>}
    </div>
  );
}
