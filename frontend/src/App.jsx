import {
  AppWindow,
  BarChart3,
  BriefcaseBusiness,
  CalendarDays,
  ChevronDown,
  Copy,
  Coffee,
  ExternalLink,
  Heart,
  FolderOpen,
  HelpCircle,
  Link2,
  Link2Off,
  Plus,
  Send,
  Settings2,
  Trash2,
  UserRound,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, deleteRequest, optionalApi, postJson } from "@/api";
import { AppContext } from "@/app-context";
import GlobalDocumentDropZone from "@/components/GlobalDocumentDropZone";
import ProfileOnboarding from "@/components/ProfileOnboarding";
import { Button, Card, Field, Modal, TextInput, ToastViewport } from "@/components/ui";
import ApplicationsPage from "@/pages/ApplicationsPage";
import DashboardPage from "@/pages/DashboardPage";
import JobsPage from "@/pages/JobsPage";
import ProfilePage from "@/pages/ProfilePage";
import SettingsPage from "@/pages/SettingsPage";
import CalendarPage from "@/pages/CalendarPage";
import DocumentsPage from "@/pages/DocumentsPage";
import StatsPage from "@/pages/StatsPage";
import { cn, copyToClipboard, parsePageFromHash, resolveLegacyAction } from "@/utils";

const DEFAULT_WORKSPACE = {
  has_profile: false,
  profile_name: null,
  profile: { completeness: 0, complete: 0, total: 9, missing_areas: [], positionen: 0, skills: 0, dokumente: 0 },
  sources: { active: 0, total: 0 },
  search: { status: "nie" },
  jobs: { active: 0 },
  applications: { total: 0, follow_ups_total: 0, follow_ups_due: 0 },
  readiness: {
    label: "Startklar machen",
    tone: "blue",
    headline: "Lege dein Profil an oder importiere vorhandene Unterlagen.",
    description: "Ohne Profil kann PBP noch nicht für Jobsuche, Export oder Bewerbungen arbeiten.",
    action_type: "prompt",
    action_target: "/ersterfassung",
    action_label: "Profil starten",
  },
  navigation: {},
};

const TAB_CONFIG = [
  { id: "dashboard", title: "Dashboard", icon: AppWindow, defaultMeta: "Status und Übersicht" },
  { id: "profil", title: "Profil", icon: UserRound, defaultMeta: "Lebenslauf-Basis und Vollständigkeit" },
  { id: "stellen", title: "Stellen", icon: BriefcaseBusiness, defaultMeta: "Treffer, Filter und Fit" },
  { id: "bewerbungen", title: "Bewerbungen", icon: Send, defaultMeta: "TODOs, Follow-ups und Status" },
  { id: "dokumente", title: "Docs", icon: FolderOpen, defaultMeta: "Suche, Filter und Querverweis" },
  { id: "kalender", title: "Kalender", icon: CalendarDays, defaultMeta: "Termine und ICS-Export" },
  { id: "statistiken", title: "Statistiken", icon: BarChart3, defaultMeta: "Charts, Trends und Export" },
  { id: "einstellungen", title: "Einstellungen", icon: Settings2, defaultMeta: "Quellen, Suche und Verhalten" },
];

function preferenceFlag(value) {
  return value === true || value === "true" || value === 1 || value === "1";
}

function isTypingTargetActive() {
  if (typeof document === "undefined") return false;
  const element = document.activeElement;
  if (!element) return false;
  const tagName = (element.tagName || "").toUpperCase();
  if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return true;
  return Boolean(element.isContentEditable);
}

function displayProfileName(profile, duplicateNameCounts) {
  const name = (profile?.name || "").trim() || "Unbenanntes Profil";
  const key = name.toLocaleLowerCase("de-DE");
  if ((duplicateNameCounts.get(key) || 0) < 2) {
    return name;
  }
  return `${name} (ID ${profile.id})`;
}

function normalizeProfiles(profiles) {
  const dedupedById = new Map();
  for (const profile of profiles || []) {
    if (!profile?.id || dedupedById.has(profile.id)) continue;
    dedupedById.set(profile.id, profile);
  }

  const uniqueProfiles = [...dedupedById.values()];
  const duplicateNameCounts = new Map();
  for (const profile of uniqueProfiles) {
    const name = (profile?.name || "").trim() || "Unbenanntes Profil";
    const key = name.toLocaleLowerCase("de-DE");
    duplicateNameCounts.set(key, (duplicateNameCounts.get(key) || 0) + 1);
  }

  return uniqueProfiles.map((profile) => ({
    ...profile,
    display_name: displayProfileName(profile, duplicateNameCounts),
  }));
}

export default function App() {
  const TOAST_DEDUP_WINDOW_MS = 5000;
  const [page, setPage] = useState(parsePageFromHash());
  const [intent, setIntent] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [chrome, setChrome] = useState({
    loading: true,
    status: { has_profile: false },
    workspace: DEFAULT_WORKSPACE,
    profiles: [],
    profile: null,
    wizardCompleted: false,
    searchStatus: { status: "nie" },
    profileOnboarding: {
      profileId: "",
      started: false,
      completed: false,
      dismissed: false,
    },
  });
  const [toasts, setToasts] = useState([]);
  const [createProfileOpen, setCreateProfileOpen] = useState(false);
  const [createProfileForm, setCreateProfileForm] = useState({ name: "", email: "" });
  const [deleteState, setDeleteState] = useState({ open: false, profile: null, confirm: "" });
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef(null);
  const [wizardOpen, setWizardOpen] = useState(true);
  const [profileOnboardingOpen, setProfileOnboardingOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpTab, setHelpTab] = useState("hilfe");
  const [mcpHelpOpen, setMcpHelpOpen] = useState(false);
  const [updateInfo, setUpdateInfo] = useState(null);
  const recentToastsRef = useRef(new Map());
  const liveUpdateTokenRef = useRef("");
  const liveUpdateSeenRef = useRef(false);
  const liveRefreshPendingRef = useRef(false);
  const liveSyncInFlightRef = useRef(false);
  const ownSaveInFlightRef = useRef(false);

  useEffect(() => {
    if (!profileMenuOpen) return undefined;
    function handleClickOutside(e) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setProfileMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [profileMenuOpen]);

  function dismissToast(id) {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }

  function pushToast(message, tone = "sky", options = {}) {
    const normalizedMessage = String(message || "").trim();
    const dedupeEnabled = options?.dedupe !== false;
    const dedupeWindowMs = Number(options?.dedupeWindowMs || TOAST_DEDUP_WINDOW_MS);
    if (dedupeEnabled && normalizedMessage) {
      const key = `${tone}:${normalizedMessage}`;
      const now = Date.now();
      const lastShownAt = recentToastsRef.current.get(key) || 0;
      if (now - lastShownAt < dedupeWindowMs) {
        return;
      }
      recentToastsRef.current.set(key, now);
      if (recentToastsRef.current.size > 200) {
        for (const [existingKey, shownAt] of recentToastsRef.current.entries()) {
          if (now - shownAt > dedupeWindowMs * 2) {
            recentToastsRef.current.delete(existingKey);
          }
        }
      }
    }

    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`;
    setToasts((current) => [...current, { id, message: normalizedMessage || message, tone, action: options?.action }]);
    window.setTimeout(() => dismissToast(id), Number(options?.duration) || 4200);
  }

  async function copyPrompt(prompt) {
    try {
      const rawPrompt = String(prompt || "").trim();
      const normalizedPrompt = rawPrompt.toLocaleLowerCase("de-DE");
      let promptToCopy = rawPrompt;
      let copiedResolvedWorkflow = false;

      if (normalizedPrompt.startsWith("/")) {
        const workflowName = rawPrompt.slice(1).split(/\s+/)[0];
        if (workflowName) {
          try {
            const resolved = await api(`/api/workflow-prompt/${encodeURIComponent(workflowName)}`);
            if (resolved?.prompt) {
              promptToCopy = resolved.prompt;
              copiedResolvedWorkflow = true;
            }
          } catch (error) {
            pushToast("Anleitung konnte nicht geladen werden \u2014 der Originaltext wurde kopiert.", "amber");
          }
        }
      }

      await copyToClipboard(promptToCopy);

      // #275: Warnung wenn Claude nicht verbunden
      const connStatus = chrome.status?.mcp_connection?.status;
      if (connStatus && connStatus !== "connected") {
        pushToast(
          "Claude Desktop scheint nicht verbunden zu sein. Bitte pr\u00fcfen: 1) L\u00e4uft das PBP-Fenster noch? 2) Claude Desktop komplett beenden und neu starten 3) Unter Einstellungen > Entwickler den MCP-Status pr\u00fcfen.",
          "amber",
          { duration: 12000, dedupe: true }
        );
      }

      const isConversationPrompt =
        normalizedPrompt === "/ersterfassung" || normalizedPrompt.startsWith("/ersterfassung ");
      if (isConversationPrompt) {
        const activeProfileId =
          chrome.profile?.id || chrome.profiles?.find((item) => item.is_active)?.id || "";
        if (activeProfileId) {
          await Promise.all([
            postJson(`/api/user-preferences/profile_onboarding_started_${activeProfileId}`, { value: true }),
            postJson(`/api/user-preferences/profile_onboarding_completed_${activeProfileId}`, { value: false }),
            postJson(`/api/user-preferences/profile_onboarding_dismissed_${activeProfileId}`, { value: false }),
            postJson(`/api/user-preferences/profile_onboarding_conversation_${activeProfileId}`, { value: "active" }),
          ]);
          startTransition(() => {
            setChrome((current) => ({
              ...current,
              profileOnboarding: {
                ...current.profileOnboarding,
                profileId: activeProfileId,
                started: true,
                completed: false,
                dismissed: false,
              },
            }));
          });
        }
      }
      pushToast(
        "Anleitung kopiert! Wechsle jetzt zu Claude Desktop \u2014 Einfuegen mit Strg+V (Cmd+V auf Mac).",
        "success",
        { duration: 10000, action: { label: "Zu Claude wechseln", onClick: () => { window.open("claude://", "_self"); } } }
      );
    } catch (error) {
      pushToast(`Kopieren fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function refreshChrome(options = {}) {
    const quiet = Boolean(options?.quiet);
    if (quiet && !options?.forceReload) {
      ownSaveInFlightRef.current = true;
    }
    try {
      const [status, workspace, profilesData, profile, wizardPreference, searchStatus] =
        await Promise.all([
          api("/api/status"),
          api("/api/workspace-summary"),
          api("/api/profiles"),
          optionalApi("/api/profile"),
          api("/api/user-preferences/wizard_completed"),
          api("/api/search-status"),
        ]);
      const activeProfileId =
        profile?.id || profilesData?.profiles?.find((item) => item.is_active)?.id || "";
      const [onboardingStartedPreference, onboardingCompletedPreference, onboardingDismissedPreference] =
        activeProfileId
          ? await Promise.all([
              api(`/api/user-preferences/profile_onboarding_started_${activeProfileId}`),
              api(`/api/user-preferences/profile_onboarding_completed_${activeProfileId}`),
              api(`/api/user-preferences/profile_onboarding_dismissed_${activeProfileId}`),
            ])
          : [{ value: false }, { value: false }, { value: false }];
      const profileOnboarding = {
        profileId: activeProfileId,
        started: preferenceFlag(onboardingStartedPreference?.value),
        completed: preferenceFlag(onboardingCompletedPreference?.value),
        dismissed: preferenceFlag(onboardingDismissedPreference?.value),
      };

      // After a quiet refresh (autosave), sync the live-update token so the
      // polling loop does not treat our own save as an external change and
      // force-reload the page.
      if (quiet && !options?.forceReload) {
        try {
          const liveState = await optionalApi("/api/live-update-token");
          if (liveState?.token) {
            liveUpdateTokenRef.current = String(liveState.token);
            liveUpdateSeenRef.current = true;
            liveRefreshPendingRef.current = false;
          }
        } catch {
          // best-effort – don't block the refresh
        } finally {
          ownSaveInFlightRef.current = false;
        }
      }

      startTransition(() => {
        setChrome({
          loading: false,
          status,
          workspace: workspace || DEFAULT_WORKSPACE,
          profiles: profilesData?.profiles || [],
          profile,
          wizardCompleted: Boolean(wizardPreference?.value),
          searchStatus: searchStatus || { status: "nie" },
          profileOnboarding,
        });
        setProfileOnboardingOpen(
          profileOnboarding.started && !profileOnboarding.completed && !profileOnboarding.dismissed
        );
        if (!quiet || options?.forceReload) {
          setReloadKey((current) => current + 1);
        }
      });
    } catch (error) {
      if (!quiet) {
        pushToast(`Dashboard konnte nicht geladen werden: ${error.message}`, "danger");
      }
      startTransition(() => {
        setChrome((current) => ({ ...current, loading: false }));
      });
    }
  }

  const syncHash = useEffectEvent(() => {
    setPage(parsePageFromHash());
  });

  const syncLiveUpdates = useEffectEvent(async () => {
    if (liveSyncInFlightRef.current) return;
    liveSyncInFlightRef.current = true;
    try {
      const liveState = await optionalApi("/api/live-update-token");
      if (!liveState?.token) return;

      const nextToken = String(liveState.token);
      if (!liveUpdateSeenRef.current) {
        liveUpdateTokenRef.current = nextToken;
        liveUpdateSeenRef.current = true;
        liveRefreshPendingRef.current = false;
        return;
      }

      const changed = nextToken !== liveUpdateTokenRef.current;
      if (changed) {
        liveUpdateTokenRef.current = nextToken;
      }

      // If a quiet save from this client is in-flight, the token change is
      // our own — absorb it and don't schedule a reload.
      if (ownSaveInFlightRef.current) {
        liveRefreshPendingRef.current = false;
        return;
      }

      if (!changed && !liveRefreshPendingRef.current) {
        return;
      }

      if (isTypingTargetActive()) {
        liveRefreshPendingRef.current = true;
        return;
      }

      liveRefreshPendingRef.current = false;
      await refreshChrome({ quiet: true, forceReload: true });
    } catch {
      // kein Toast: Polling soll im Hintergrund robust bleiben
    } finally {
      liveSyncInFlightRef.current = false;
    }
  });

  useEffect(() => {
    refreshChrome();
    // Update-Check (#286)
    optionalApi("/api/update-check").then((data) => {
      if (data?.update_available) setUpdateInfo(data);
    });
  }, []);

  useEffect(() => {
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, [syncHash]);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      if (cancelled) return;
      await syncLiveUpdates();
      if (cancelled) return;
      timer = window.setTimeout(tick, 2000);
    };

    tick();
    return () => {
      cancelled = true;
      liveRefreshPendingRef.current = false;
      liveSyncInFlightRef.current = false;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [syncLiveUpdates]);

  // #359: Periodically poll connection status independently of DB changes.
  // Without this, the Lebensanzeige only updates when the live-update token
  // changes (i.e. on DB writes), leaving it stale at "disconnected".
  useEffect(() => {
    let cancelled = false;
    const pollConnection = async () => {
      if (cancelled) return;
      try {
        const status = await optionalApi("/api/status");
        if (status?.mcp_connection && !cancelled) {
          startTransition(() => {
            setChrome((prev) => {
              if (prev.status?.mcp_connection?.status === status.mcp_connection.status) return prev;
              return { ...prev, status: { ...prev.status, mcp_connection: status.mcp_connection } };
            });
          });
        }
      } catch {}
    };
    const id = window.setInterval(pollConnection, 30000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  function navigateTo(nextPage, nextIntent = null) {
    setIntent(nextIntent ? { page: nextPage, ...nextIntent, nonce: Date.now() } : null);
    setPage(nextPage);
    if (window.location.hash !== `#${nextPage}`) {
      window.location.hash = nextPage;
    }
  }

  async function executeAction(action) {
    if (!action) return;
    if (action.prompt) {
      await copyPrompt(action.prompt);
      return;
    }

    const resolved = resolveLegacyAction(action.action_target || action.actionTarget);
    if (resolved) {
      navigateTo(resolved.page, resolved);
      return;
    }

    if (action.action_type === "page" && action.action_target) {
      navigateTo(action.action_target);
      return;
    }

    if (action.action_type === "prompt" && action.action_target) {
      await copyPrompt(action.action_target);
    }
  }

  async function handleReadinessAction() {
    const readiness = chrome.workspace?.readiness;
    if (!readiness) return;
    if (readiness.action_type === "prompt") {
      await copyPrompt(readiness.action_target);
      return;
    }
    if (readiness.action_target) {
      navigateTo(readiness.action_target);
    }
  }

  async function handleProfileSwitch(profileId) {
    try {
      await postJson("/api/profiles/switch", { profile_id: profileId });
      await refreshChrome();
      pushToast("Aktives Profil gewechselt.", "success");
    } catch (error) {
      pushToast(`Profilwechsel fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function handleCreateProfile(event) {
    event.preventDefault();
    try {
      const response = await postJson("/api/profiles/new", createProfileForm);
      if (response?.id) {
        try {
          await Promise.all([
            postJson(`/api/user-preferences/profile_onboarding_started_${response.id}`, { value: true }),
            postJson(`/api/user-preferences/profile_onboarding_completed_${response.id}`, { value: false }),
            postJson(`/api/user-preferences/profile_onboarding_dismissed_${response.id}`, { value: false }),
            postJson(`/api/user-preferences/profile_onboarding_conversation_${response.id}`, {
              value: "idle",
            }),
          ]);
          setProfileOnboardingOpen(true);
        } catch (preferenceError) {
          pushToast(
            `Profil wurde erstellt, aber das Setup konnte nicht vorbereitet werden: ${preferenceError.message}`,
            "danger"
          );
        }
      }
      setCreateProfileOpen(false);
      setCreateProfileForm({ name: "", email: "" });
      await refreshChrome();
      navigateTo("dashboard");
      pushToast("Neues Profil erstellt.", "success");
    } catch (error) {
      pushToast(`Profil konnte nicht erstellt werden: ${error.message}`, "danger");
    }
  }

  async function handleDeleteProfile() {
    try {
      await deleteRequest(`/api/profiles/${deleteState.profile.id}`);
      setDeleteState({ open: false, profile: null, confirm: "" });
      await refreshChrome();
      pushToast("Profil gelöscht.", "success");
    } catch (error) {
      pushToast(`Löschen fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function closeWizard(completed = false) {
    setWizardOpen(false);
    if (completed) {
      try {
        await postJson("/api/user-preferences/wizard_completed", { value: true });
      } catch (error) {
        pushToast(`Wizard-Status konnte nicht gespeichert werden: ${error.message}`, "danger");
      }
    }
  }

  async function dismissProfileOnboarding() {
    const profileId = chrome.profileOnboarding?.profileId || chrome.profile?.id;
    setProfileOnboardingOpen(false);
    if (!profileId) return;
    try {
      await postJson(`/api/user-preferences/profile_onboarding_dismissed_${profileId}`, {
        value: true,
      });
      startTransition(() => {
        setChrome((current) => ({
          ...current,
          profileOnboarding: { ...current.profileOnboarding, dismissed: true },
        }));
      });
    } catch (error) {
      pushToast(`Onboarding konnte nicht geschlossen werden: ${error.message}`, "danger");
    }
  }

  async function reopenProfileOnboarding() {
    const profileId = chrome.profileOnboarding?.profileId || chrome.profile?.id;
    setProfileOnboardingOpen(true);
    if (!profileId) return;
    try {
      await postJson(`/api/user-preferences/profile_onboarding_dismissed_${profileId}`, {
        value: false,
      });
      startTransition(() => {
        setChrome((current) => ({
          ...current,
          profileOnboarding: { ...current.profileOnboarding, dismissed: false },
        }));
      });
    } catch (error) {
      pushToast(`Onboarding konnte nicht erneut geöffnet werden: ${error.message}`, "danger");
    }
  }

  async function completeProfileOnboarding() {
    const profileId = chrome.profileOnboarding?.profileId || chrome.profile?.id;
    setProfileOnboardingOpen(false);
    if (!profileId) return;
    try {
      await Promise.all([
        postJson(`/api/user-preferences/profile_onboarding_started_${profileId}`, { value: true }),
        postJson(`/api/user-preferences/profile_onboarding_completed_${profileId}`, { value: true }),
        postJson(`/api/user-preferences/profile_onboarding_dismissed_${profileId}`, { value: false }),
      ]);
      await refreshChrome();
      pushToast("Profil-Setup abgeschlossen.", "success");
    } catch (error) {
      pushToast(`Onboarding konnte nicht abgeschlossen werden: ${error.message}`, "danger");
    }
  }

  const readiness = chrome.workspace?.readiness || DEFAULT_WORKSPACE.readiness;
  const profileOptions = normalizeProfiles(chrome.profiles);
  const activeProfileId = chrome.profile?.id || profileOptions.find((item) => item.is_active)?.id || "";
  const profileOptionIds = new Set(profileOptions.map((item) => item.id));
  const selectedProfileId = profileOptionIds.has(activeProfileId)
    ? activeProfileId
    : profileOptions.find((item) => item.is_active)?.id || profileOptions[0]?.id || "";
  const currentProfile = profileOptions.find((p) => p.id === selectedProfileId);
  const currentProfileName = currentProfile?.display_name || "Kein Profil";
  const showWizard =
    !chrome.loading && !chrome.status?.has_profile && !chrome.wizardCompleted && wizardOpen;
  const showProfileOnboarding =
    !chrome.loading &&
    chrome.status?.has_profile &&
    chrome.profileOnboarding?.started &&
    !chrome.profileOnboarding?.completed &&
    profileOnboardingOpen;
  const showProfileOnboardingCta =
    !chrome.loading &&
    chrome.status?.has_profile &&
    chrome.profileOnboarding?.started &&
    !chrome.profileOnboarding?.completed &&
    !showProfileOnboarding;
  const profileIsComplete = (chrome.workspace?.profile?.completeness || 0) >= 100;
  const showWorkspaceStrip =
    !chrome.loading &&
    !profileIsComplete &&
    (chrome.workspace?.readiness?.stage || readiness.stage) !== "im_fluss";
  const showReadinessActionButton =
    (readiness.action_target || "").toString().toLowerCase() !== "dashboard" &&
    (readiness.action_label || "").toString().toLowerCase() !== "dashboard ansehen";

  const appContext = {
    page,
    intent,
    clearIntent: () => setIntent(null),
    chrome,
    reloadKey,
    refreshChrome,
    navigateTo,
    pushToast,
    copyPrompt,
    executeAction,
    openCreateProfileModal: () => setCreateProfileOpen(true),
    openProfileOnboarding: reopenProfileOnboarding,
  };

  return (
    <AppContext.Provider value={appContext}>
      <div className="app-shell">
        <ToastViewport toasts={toasts} onDismiss={dismissToast} />

        <header className="app-topbar glass-topbar sticky top-0 z-50">
          <div className="mx-auto flex w-full max-w-[92rem] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2.5 sm:px-8">
            <p className="brand-title shrink-0 text-[13px] font-medium text-ink/80">
              Persönliches Bewerbungs-Portal
            </p>

            <nav className="tabs flex min-w-0 flex-1 items-center gap-0.5">
              {TAB_CONFIG.map((tab) => {
                const Icon = tab.icon;
                const isActive = page === tab.id;
                const badge =
                  tab.id === "profil"
                    ? chrome.workspace?.navigation?.profile_badge
                    : tab.id === "stellen"
                      ? chrome.workspace?.navigation?.jobs_badge
                      : tab.id === "bewerbungen"
                        ? chrome.workspace?.navigation?.applications_badge
                        : tab.id === "einstellungen"
                          ? chrome.workspace?.navigation?.settings_badge
                          : null;
                const meta =
                  tab.id === "dashboard" ? readiness.label || tab.defaultMeta : tab.defaultMeta;

                return (
                  <button
                    key={tab.id}
                    type="button"
                    className={cn(
                      "tab relative flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors duration-150",
                      isActive
                        ? "bg-white/[0.08] text-ink"
                        : "text-muted hover:text-ink hover:bg-white/[0.04]"
                    )}
                    data-page={tab.id}
                    onClick={() => navigateTo(tab.id)}
                  >
                    <Icon size={15} className={isActive ? "text-sky" : ""} />
                    <span>{tab.title}</span>
                    <span id={`tab-meta-${tab.id}`} className="sr-only">{meta}</span>
                    {badge ? (
                      <span
                        id={`tab-badge-${tab.id}`}
                        className="tab-badge ml-1 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-amber/80 px-1 text-[10px] font-bold leading-none text-shell"
                      >
                        {badge}
                      </span>
                    ) : (
                      <span id={`tab-badge-${tab.id}`} className="hidden">{badge}</span>
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Help Button (#75) */}
            <button
              type="button"
              onClick={() => { setWizardOpen(false); setHelpOpen(true); }}
              className="shrink-0 rounded-lg p-1.5 text-muted/50 hover:text-ink hover:bg-white/[0.04] transition-colors"
              title="Hilfe & Support"
            >
              <HelpCircle size={18} />
            </button>

            <div
              id="profile-switcher"
              ref={profileMenuRef}
              className="relative flex shrink-0 items-center"
            >
              <button
                type="button"
                className="flex items-center gap-2.5 rounded-xl border border-white/8 bg-white/[0.04] px-3 py-1.5 text-[13px] font-medium text-ink transition-all duration-200 hover:border-white/12 hover:bg-white/[0.07]"
                onClick={() => setProfileMenuOpen((prev) => !prev)}
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal/15 text-[10px] font-bold uppercase text-teal">
                  {currentProfileName[0] || "?"}
                </span>
                <span className="max-w-[10rem] truncate">{currentProfileName}</span>
                <ChevronDown
                  size={14}
                  className={cn(
                    "text-muted/50 transition-transform duration-200",
                    profileMenuOpen && "rotate-180"
                  )}
                />
              </button>

              {profileMenuOpen && (
                <div className="absolute right-0 top-full z-50 mt-2 min-w-[13rem] overflow-hidden rounded-xl border border-white/10 shadow-2xl backdrop-blur-2xl animate-rise"
                  style={{ background: "rgba(30, 34, 52, 0.95)" }}
                >
                  <div className="p-1">
                    {profileOptions.length === 0 && (
                      <p className="px-3 py-2 text-[12px] text-muted/50">Kein Profil vorhanden</p>
                    )}
                    {profileOptions.map((profile) => (
                      <button
                        key={profile.id}
                        type="button"
                        className={cn(
                          "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors duration-150",
                          profile.id === selectedProfileId
                            ? "bg-teal/10 font-medium text-teal"
                            : "text-muted hover:bg-white/[0.06] hover:text-ink"
                        )}
                        onClick={() => {
                          handleProfileSwitch(profile.id);
                          setProfileMenuOpen(false);
                        }}
                      >
                        <span
                          className={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold uppercase",
                            profile.id === selectedProfileId
                              ? "bg-teal/20 text-teal"
                              : "bg-white/[0.06] text-muted/60"
                          )}
                        >
                          {profile.display_name?.[0] || "?"}
                        </span>
                        <span className="truncate">{profile.display_name}</span>
                      </button>
                    ))}
                  </div>
                  <div className="border-t border-white/6 p-1">
                    <button
                      type="button"
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-muted transition-colors duration-150 hover:bg-white/[0.06] hover:text-ink"
                      onClick={() => {
                        setCreateProfileOpen(true);
                        setProfileMenuOpen(false);
                      }}
                    >
                      <Plus size={14} />
                      <span>Neues Profil</span>
                    </button>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-coral/60 transition-colors duration-150 hover:bg-coral/5 hover:text-coral disabled:cursor-not-allowed disabled:opacity-40"
                      disabled={!chrome.profile}
                      onClick={() => {
                        setDeleteState({ open: true, profile: chrome.profile, confirm: "" });
                        setProfileMenuOpen(false);
                      }}
                    >
                      <Trash2 size={14} />
                      <span>Profil löschen</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Update-Banner (#286) */}
        {updateInfo?.update_available && (
          <div className="mx-auto w-full max-w-[92rem] px-5 sm:px-8 pt-2">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-amber/20 bg-amber/8 px-4 py-2.5 text-sm text-amber">
              <span>
                Neue Version verfuegbar: <strong>v{updateInfo.latest_version}</strong>
                {updateInfo.release_name ? ` — ${updateInfo.release_name}` : ""}
              </span>
              <div className="flex items-center gap-2">
                {updateInfo.release_url && (
                  <a
                    href={updateInfo.release_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg bg-amber/15 px-3 py-1 text-xs font-medium hover:bg-amber/25 transition-colors"
                  >
                    Update-Anleitung
                  </a>
                )}
                <button
                  type="button"
                  className="rounded-lg p-1 hover:bg-amber/15 transition-colors"
                  onClick={() => setUpdateInfo(null)}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M3.5 3.5l7 7M10.5 3.5l-7 7" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}

        {showWorkspaceStrip ? (
          <div
          id="workspace-strip"
          className={cn(
            "workspace-strip mx-auto w-full max-w-[92rem] px-5 pb-2 pt-4 sm:px-8",
            !chrome.loading && "active"
          )}
        >
          <Card className="workspace-grid flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl px-5 py-3">
            <div className="min-w-0 flex-1">
              <h2 className="workspace-headline truncate text-[13px] font-semibold text-ink">
                {readiness.headline}
              </h2>
              <p className="mt-0.5 truncate text-[12px] text-muted/50">
                {chrome.workspace?.profile_name || "Kein Profil"} — {readiness.description}
              </p>
            </div>

            <div className="flex items-center gap-5 text-center">
              <div className="workspace-card">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted/40">Profil</p>
                <p className="workspace-value text-base font-semibold text-ink">{chrome.workspace?.profile?.completeness || 0}%</p>
              </div>
              <div className="h-6 w-px bg-white/[0.06]" />
              <div className="workspace-card">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted/40">Quellen</p>
                <p className="workspace-value text-base font-semibold text-ink">{chrome.workspace?.sources?.active || 0}/{chrome.workspace?.sources?.total || 0}</p>
              </div>
              <div className="h-6 w-px bg-white/[0.06]" />
              <div className="workspace-card">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted/40">Stellen</p>
                <p className="workspace-value text-base font-semibold text-ink">{chrome.workspace?.jobs?.active || 0}</p>
              </div>
              <div className="h-6 w-px bg-white/[0.06]" />
              <div className="workspace-card">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted/40">Bewerbungen aktiv</p>
                <p className="workspace-value text-base font-semibold text-ink">{chrome.workspace?.applications?.active ?? chrome.workspace?.applications?.total ?? 0}</p>
              </div>
            </div>

            {showReadinessActionButton || showProfileOnboardingCta ? (
              <div className="workspace-actions flex shrink-0 gap-2">
                {showReadinessActionButton ? (
                  <Button size="sm" onClick={handleReadinessAction}>{readiness.action_label || "Öffnen"}</Button>
                ) : null}
                {showProfileOnboardingCta ? (
                  <Button size="sm" variant="ghost" onClick={reopenProfileOnboarding}>
                    Setup fortsetzen
                  </Button>
                ) : null}
              </div>
            ) : null}
          </Card>
          </div>
        ) : null}

        {!chrome.loading && chrome.status?.has_profile && chrome.workspace?.sources?.active === 0 ? (
          <div
            id="source-banner"
            className="mx-auto flex w-full max-w-[92rem] flex-wrap items-center gap-3 px-5 pb-2 sm:px-8"
          >
            <Card className="glass-banner glass-banner-amber flex w-full flex-wrap items-center justify-between gap-3 rounded-xl">
              <p className="text-[13px] font-medium text-amber">
                Keine Jobquellen aktiviert. Ohne Quellen kann keine Suche starten.
              </p>
              <Button size="sm" onClick={() => navigateTo("einstellungen")}>
                <Settings2 size={14} />
                Quellen aktivieren
              </Button>
            </Card>
          </div>
        ) : null}


        <div className="mx-auto flex w-full max-w-[92rem] px-5 pt-4 sm:px-8">
          {/* Global Sidebar (#363) */}
          <aside className="hidden lg:block w-48 shrink-0 pr-6">
            <div className="sticky top-16 space-y-3">
              <p className="text-[10px] font-mono text-muted/30 select-none">
                v{chrome.status?.version || "?"}
              </p>

              {/* MCP Connection Indicator (#273, #309, #363) */}
              {(() => {
                const conn = chrome.status?.mcp_connection;
                const st = conn?.status || "disconnected";
                const cfg = {
                  connected: { color: "text-teal", bg: "bg-teal/15 hover:bg-teal/25", dot: "bg-teal", label: "Verbunden", Icon: Link2 },
                  unknown: { color: "text-amber", bg: "bg-amber/15 hover:bg-amber/25", dot: "bg-amber", label: "Pr\u00fcfe\u2026", Icon: Link2 },
                  disconnected: { color: "text-coral", bg: "bg-coral/15 hover:bg-coral/25", dot: "bg-coral", label: "Nicht verbunden", Icon: Link2Off },
                }[st] || { color: "text-coral", bg: "bg-coral/15 hover:bg-coral/25", dot: "bg-coral", label: "Nicht verbunden", Icon: Link2Off };
                const handleClick = () => {
                  if (st === "connected") {
                    window.open("claude://", "_self");
                  } else {
                    setMcpHelpOpen(true);
                  }
                };
                return (
                  <button
                    type="button"
                    onClick={handleClick}
                    className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium cursor-pointer transition-colors ${cfg.bg} ${cfg.color}`}
                    title={st === "connected" ? "Claude Desktop \u00f6ffnen" : `MCP: ${cfg.label} \u2014 Klicke f\u00fcr Hilfe`}
                  >
                    <span className={`inline-block h-2 w-2 rounded-full ${cfg.dot}`} />
                    <span>{cfg.label}</span>
                  </button>
                );
              })()}

              {/* Page-specific sidebar navigation */}
              {page === "profil" && (
                <>
                  <div className="h-px bg-white/[0.06]" />
                  <nav className="space-y-1">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted/40">Navigation</p>
                    {[
                      ["profil-uebersicht", "\u00dcbersicht"],
                      ["profil-persoenlich", "Pers\u00f6nliche Daten"],
                      ["profil-suchkriterien", "Suchkriterien"],
                      ["profil-blacklist", "Blacklist"],
                      ["profil-erfahrung", "Berufserfahrung"],
                      ["profil-ausbildung", "Ausbildung"],
                      ["profil-skills", "Skills"],
                      ["profil-dokumente", "Dokumente"],
                    ].map(([id, label]) => (
                      <a
                        key={id}
                        href={`#${id}`}
                        className="block rounded-lg px-3 py-1.5 text-[13px] text-muted/60 transition-colors hover:bg-white/[0.06] hover:text-ink"
                        onClick={(e) => {
                          e.preventDefault();
                          document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }}
                      >
                        {label}
                      </a>
                    ))}
                  </nav>
                </>
              )}
            </div>
          </aside>

          <main className="min-w-0 flex-1 pb-12">
            {page === "dashboard" ? <DashboardPage /> : null}
            {page === "profil" ? <ProfilePage /> : null}
            {page === "stellen" ? <JobsPage /> : null}
            {page === "bewerbungen" ? <ApplicationsPage /> : null}
            {page === "dokumente" ? <DocumentsPage /> : null}
            {page === "kalender" ? <CalendarPage /> : null}
            {page === "statistiken" ? <StatsPage /> : null}
            {page === "einstellungen" ? <SettingsPage /> : null}
          </main>
        </div>

        <Modal
          open={createProfileOpen}
          title="Neues Profil anlegen"
          description="Lege ein weiteres Profil für einen anderen Karrierepfad oder Zielmarkt an."
          onClose={() => setCreateProfileOpen(false)}
          footer={
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setCreateProfileOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" form="create-profile-form">
                Profil anlegen
              </Button>
            </div>
          }
        >
          <form id="create-profile-form" className="grid gap-4" onSubmit={handleCreateProfile}>
            <Field label="Profilname">
              <TextInput
                autoFocus
                value={createProfileForm.name}
                onChange={(event) =>
                  setCreateProfileForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="z. B. IT Consulting"
                required
              />
            </Field>
            <Field label="E-Mail">
              <TextInput
                type="email"
                value={createProfileForm.email}
                onChange={(event) =>
                  setCreateProfileForm((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="optional"
              />
            </Field>
          </form>
        </Modal>

        <Modal
          open={deleteState.open}
          title="Profil unwiderruflich löschen"
          description="Tippe den Profilnamen exakt ein, damit das Profil inklusive Daten gelöscht werden kann."
          onClose={() => setDeleteState({ open: false, profile: null, confirm: "" })}
          footer={
            <div className="flex justify-end gap-3">
              <Button
                variant="ghost"
                onClick={() => setDeleteState({ open: false, profile: null, confirm: "" })}
              >
                Abbrechen
              </Button>
              <Button
                variant="danger"
                disabled={deleteState.confirm !== deleteState.profile?.name}
                onClick={handleDeleteProfile}
              >
                Endgültig löschen
              </Button>
            </div>
          }
        >
          <div className="grid gap-4">
            <Card className="glass-banner glass-banner-danger rounded-[24px] shadow-none">
              <p className="text-sm text-ink">
                Betroffen sind alle Positionen, Skills, Ausbildungsdaten, Dokumente, Jobs und
                Bewerbungen des Profils <strong>{deleteState.profile?.name}</strong> (ID{" "}
                {deleteState.profile?.id}).
              </p>
            </Card>
            <Field label="Profilname bestätigen">
              <TextInput
                value={deleteState.confirm}
                onChange={(event) =>
                  setDeleteState((current) => ({ ...current, confirm: event.target.value }))
                }
                placeholder={deleteState.profile?.name || ""}
              />
            </Field>
          </div>
        </Modal>

        <div
          id="wizard-overlay"
          className={cn(
            "glass-overlay fixed inset-x-0 bottom-0 top-[52px] z-[45] items-center justify-center px-4 py-6",
            showWizard ? "show flex" : "hidden"
          )}
        >
          <div className="glass-card-strong w-full max-w-2xl rounded-2xl p-6 animate-rise">
            <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-xl font-semibold text-ink">
                  Willkommen beim Bewerbungs-Assistenten
                </h2>
                <p className="mt-1 max-w-lg text-[13px] text-muted/60">
                  Am schnellsten startest du mit dem Kennlerngespräch — Claude fuehrt dich durch alles.
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => closeWizard(false)}>
                Später
              </Button>
            </div>

            {/* Primaerer Pfad */}
            <Card className="glass-card-soft rounded-xl border border-sky/20 mb-3">
              <div className="flex items-center gap-3">
                <div className="glass-icon h-10 w-10 shrink-0 bg-sky/15 text-sky rounded-xl flex items-center justify-center">
                  <Send size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-base font-semibold text-ink">Kennlerngespräch starten</h3>
                  <p className="text-[12px] text-muted/50">
                    Claude fragt dich alles Wichtige und baut dein Profil automatisch auf.
                  </p>
                </div>
                <Button size="sm" onClick={() => { closeWizard(true); copyPrompt("/ersterfassung"); }}>
                  <Copy size={14} />
                  Starten
                </Button>
              </div>
            </Card>

            {/* Alternative Pfade (kompakt) */}
            <p className="text-[11px] text-muted/40 mb-2 uppercase tracking-widest">Oder manuell:</p>
            <div className="grid gap-2 sm:grid-cols-3">
              <button
                type="button"
                className="glass-card-soft rounded-xl p-3 text-left hover:bg-white/[0.04] transition-colors"
                onClick={() => { closeWizard(true); navigateTo("profil"); }}
              >
                <UserRound size={14} className="text-muted/40 mb-1" />
                <p className="text-[13px] font-medium text-ink">Profil anlegen</p>
                <p className="text-[11px] text-muted/40">Manuell ausfuellen</p>
              </button>
              <button
                type="button"
                className="glass-card-soft rounded-xl p-3 text-left hover:bg-white/[0.04] transition-colors"
                onClick={() => { closeWizard(true); navigateTo("profil", { composer: "document" }); }}
              >
                <FolderOpen size={14} className="text-muted/40 mb-1" />
                <p className="text-[13px] font-medium text-ink">Unterlagen importieren</p>
                <p className="text-[11px] text-muted/40">PDF, DOCX hochladen</p>
              </button>
              <button
                type="button"
                className="glass-card-soft rounded-xl p-3 text-left hover:bg-white/[0.04] transition-colors"
                onClick={() => { closeWizard(true); navigateTo("einstellungen"); }}
              >
                <Settings2 size={14} className="text-muted/40 mb-1" />
                <p className="text-[13px] font-medium text-ink">Quellen aktivieren</p>
                <p className="text-[11px] text-muted/40">Jobportale einrichten</p>
              </button>
            </div>
          </div>
        </div>

        <ProfileOnboarding
          open={showProfileOnboarding}
          profile={chrome.profile}
          workspace={chrome.workspace}
          onDismiss={dismissProfileOnboarding}
          onComplete={completeProfileOnboarding}
        />

        {/* Help Modal (#75) */}
        {helpOpen && (
          <Modal open={helpOpen} title="Hilfe & Support" onClose={() => setHelpOpen(false)}>
            <div className="flex gap-1 mb-4 border-b border-white/8 pb-2 overflow-x-auto">
              {[
                { id: "hilfe", label: "Hilfe" },
                { id: "faq", label: "FAQ" },
                { id: "troubleshooting", label: "Probleme" },
                { id: "bug", label: "Bug melden" },
                { id: "feature", label: "Feature" },
                { id: "credits", label: "Credits" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setHelpTab(t.id)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    helpTab === t.id
                      ? "bg-sky/15 text-sky font-medium"
                      : "text-muted/50 hover:text-ink hover:bg-white/[0.04]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {helpTab === "hilfe" && (
              <div className="space-y-3 text-sm text-muted/60">
                {/* Context-sensitive help based on current page */}
                {page === "dashboard" && (
                  <>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Dashboard</h3>
                      <p>Das Dashboard zeigt dir eine Übersicht über dein Profil, aktuelle Stellen und Bewerbungen. Die Metriken aktualisieren sich automatisch.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Top-Stellen</h3>
                      <p>Zeigt die 3 besten Stellen nach Score, bei denen du dich noch nicht beworben hast. Klicke darauf, um zur Stellenansicht zu springen.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Follow-Ups</h3>
                      <p>Fällige Nachfass-Aktionen werden hier hervorgehoben. Klicke auf "Erledigt", um sie abzuhaken.</p>
                    </div>
                  </>
                )}
                {page === "profil" && (
                  <>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Profil aufbauen</h3>
                      <p>Dein Profil ist die Basis für alles: Lebenslauf-Export, Fit-Analysen und personalisierte Anschreiben. Je vollständiger, desto besser.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Positionen & Projekte</h3>
                      <p>Fülle Positionen mit dem STAR-Format aus (Situation, Task, Action, Result). Das ergibt starke Projektbeschreibungen für den Lebenslauf.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Dokumente</h3>
                      <p>Ziehe PDF- oder DOCX-Dateien per Drag & Drop ins Fenster. Der Dokumenttyp wird automatisch erkannt.</p>
                    </div>
                  </>
                )}
                {page === "stellen" && (
                  <>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Stellensuche</h3>
                      <p>Aktiviere Jobquellen unter "Einstellungen" und starte eine Suche über Claude mit "/jobsuche_workflow". Die Stellen werden automatisch bewertet.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Score</h3>
                      <p>Der Score (0–100) zeigt die Passgenauigkeit: Entfernung, Skills, Gehalt und Keywords fliessen ein. Klicke auf den Score um ihn manuell anzupassen.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Fit-Analyse</h3>
                      <p>Klicke auf "Fit-Analyse" für eine detaillierte Auswertung der MUSS-/PLUS-Treffer und Risiken.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Anpinnen & Blacklist</h3>
                      <p>Pinne interessante Stellen an, damit sie oben bleiben. Unpassende Firmen oder Keywords kannst du auf die Blacklist setzen.</p>
                    </div>
                  </>
                )}
                {page === "bewerbungen" && (
                  <>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Bewerbungen verwalten</h3>
                      <p>Hier trackst du alle laufenden Bewerbungen mit Status, Timeline und Notizen. Ändere den Status per Dropdown.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Timeline & Notizen</h3>
                      <p>Klicke auf eine Bewerbung für die vollständige Timeline. Dort kannst du Notizen hinzufügen und Follow-ups planen.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Follow-Ups</h3>
                      <p>Plane automatische Erinnerungen (z.B. "In 2 Wochen nachfragen"). Die werden auf dem Dashboard als TODO angezeigt.</p>
                    </div>
                  </>
                )}
                {page === "statistiken" && (
                  <>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Statistiken</h3>
                      <p>Visualisiert Bewerbungsverlauf, Erfolgsquoten, Antwortzeiten und Gehaltsverteilung. Exportiere Berichte als PDF.</p>
                    </div>
                  </>
                )}
                {page === "einstellungen" && (
                  <>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Jobquellen</h3>
                      <p>Aktiviere und deaktiviere einzelne Quellen (StepStone, Indeed, LinkedIn, etc.). LinkedIn und XING benötigen Login-Daten.</p>
                    </div>
                    <div className="glass-card p-3">
                      <h3 className="font-medium text-ink mb-1">Suchkriterien</h3>
                      <p>Definiere MUSS-Keywords (Pflicht), PLUS-Keywords (Bonus) und AUSSCHLUSS-Keywords. Diese steuern den Score der gefundenen Stellen.</p>
                    </div>
                  </>
                )}
                {/* General help always shown */}
                <div className="glass-card p-3">
                  <h3 className="font-medium text-ink mb-1">Wie starte ich?</h3>
                  <p>Öffne Claude Desktop und tippe "Ersterfassung starten". Claude führt dich durch den Aufbau deines Bewerbungsprofils.</p>
                </div>
                <div className="glass-card p-3">
                  <h3 className="font-medium text-ink mb-1">Support & Dokumentation</h3>
                  <p>Für Fragen und Probleme erstelle ein Issue auf GitHub. Du brauchst dafür einen kostenlosen GitHub-Account.</p>
                  <a
                    href="https://github.com/MadGapun/PBP#readme"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center gap-1.5 text-sky hover:underline text-[13px]"
                  >
                    <ExternalLink size={12} />
                    Vollständige Anleitung auf GitHub
                  </a>
                </div>
              </div>
            )}

            {helpTab === "faq" && (
              <div className="space-y-2 text-sm text-muted/60">
                {[
                  { q: "Was ist MCP?", a: "MCP (Model Context Protocol) ist die Schnittstelle, ueber die PBP mit Claude Desktop kommuniziert. PBP stellt Tools bereit, die Claude nutzen kann." },
                  { q: "Wo werden meine Daten gespeichert?", a: "Alle Daten liegen lokal auf deinem Geraet. Unter Windows in %LOCALAPPDATA%/bewerbungs-assistent, auf macOS in ~/.bewerbungs-assistent. Es werden keine Daten an Server gesendet." },
                  { q: "Muss Claude Desktop laufen?", a: "Fuer die KI-Funktionen ja. Das Dashboard funktioniert aber auch ohne Claude Desktop — du kannst Profil, Stellen und Bewerbungen jederzeit verwalten." },
                  { q: "Wie starte ich das Kennlerngespräch?", a: "Oeffne Claude Desktop und tippe /ersterfassung ein. Claude fuehrt dich dann Schritt fuer Schritt durch den Aufbau deines Profils." },
                  { q: "Kann ich mehrere Profile haben?", a: "Ja. Klicke oben auf deinen Profilnamen und waehle 'Neues Profil'. Du kannst zwischen Profilen wechseln." },
                  { q: "Wie funktioniert die Jobsuche?", a: "Aktiviere Quellen unter Einstellungen, dann kopiere /jobsuche_workflow in Claude Desktop. Claude durchsucht die aktivierten Portale und bewertet die Treffer." },
                  { q: "Welche Dokumentformate werden unterstuetzt?", a: "PDF, DOCX, DOC und TXT. Ziehe Dateien per Drag & Drop ins Dashboard-Fenster oder nutze den Upload-Button." },
                  { q: "Wie exportiere ich meinen Lebenslauf?", a: "Gehe zu Profil > Lebenslauf-Export. Es stehen verschiedene Formate zur Verfuegung (PDF, DOCX, TXT)." },
                  { q: "Kostet PBP etwas?", a: "Nein. PBP ist kostenlos und Open Source (MIT-Lizenz). Du brauchst aber einen Claude Desktop Account (kostenloser Tier reicht)." },
                  { q: "Wie aktualisiere ich PBP?", a: "Lade die neue Version von GitHub herunter und fuehre den Installer erneut aus. Deine Daten bleiben erhalten." },
                ].map(({ q, a }) => (
                  <details key={q} className="glass-card rounded-lg group">
                    <summary className="cursor-pointer px-3 py-2.5 font-medium text-ink text-[13px] hover:bg-white/[0.03] rounded-lg list-none flex items-center justify-between">
                      {q}
                      <ChevronDown size={14} className="text-muted/30 transition-transform group-open:rotate-180" />
                    </summary>
                    <p className="px-3 pb-2.5 text-[12.5px]">{a}</p>
                  </details>
                ))}
              </div>
            )}

            {helpTab === "troubleshooting" && (
              <div className="space-y-2 text-sm text-muted/60">
                {[
                  { q: "Claude antwortet nicht auf PBP-Befehle", a: "1. Pruefe ob das PBP-Terminal/Fenster noch laeuft\n2. Oeffne Claude Desktop Einstellungen > Entwickler — PBP muss dort als MCP-Server sichtbar sein\n3. Starte Claude Desktop neu (komplett beenden und neu oeffnen)\n4. Pruefe den MCP-Status im Dashboard-Header" },
                  { q: "Dashboard startet nicht", a: "1. Pruefe ob Port 8200 bereits belegt ist (anderes PBP-Fenster?)\n2. Starte das Dashboard ueber das Terminal: python start_dashboard.py\n3. Pruefe die Logs unter Einstellungen > Logs" },
                  { q: "Jobsuche findet keine Stellen", a: "1. Pruefe ob Quellen unter Einstellungen aktiviert sind\n2. Pruefe ob Suchkriterien (Keywords, Ort, Umkreis) gesetzt sind\n3. Manche Quellen brauchen einen Login (LinkedIn, XING)\n4. StepStone blockiert automatische Suche — nutze Claude-in-Chrome (siehe unten)" },
                  { q: "StepStone blockiert / Timeout bei Jobsuche", a: "StepStone erkennt automatische Browser und zeigt CAPTCHAs. Workaround:\n\n1. Deaktiviere StepStone als automatische Quelle\n2. Oeffne StepStone manuell im Chrome-Browser mit Claude-in-Chrome:\n   https://www.stepstone.de/jobs/plm?radius=100&location=Hamburg\n3. Bitte Claude die Stellen via stelle_manuell_anlegen zu uebernehmen\n4. Oder nutze den Prompt: 'Suche StepStone via Chrome nach PLM-Stellen'\n\nDas funktioniert zuverlaessig, weil der echte Browser nicht geblockt wird." },
                  { q: "Dokumente werden nicht erkannt", a: "1. Nur PDF, DOCX, DOC und TXT werden unterstuetzt\n2. Gescannte PDFs ohne Text-Layer koennen nicht analysiert werden\n3. Versuche 'Erneut analysieren' auf dem Dokument" },
                  { q: "MCP-Verbindung zeigt 'Nicht verbunden'", a: "Die Verbindung wird ueber einen Heartbeat geprueft. Claude Desktop muss PBP mindestens einmal aufgerufen haben. Tippe einen beliebigen PBP-Befehl in Claude Desktop ein." },
                ].map(({ q, a }) => (
                  <details key={q} className="glass-card rounded-lg group">
                    <summary className="cursor-pointer px-3 py-2.5 font-medium text-ink text-[13px] hover:bg-white/[0.03] rounded-lg list-none flex items-center justify-between">
                      {q}
                      <ChevronDown size={14} className="text-muted/30 transition-transform group-open:rotate-180" />
                    </summary>
                    <pre className="px-3 pb-2.5 text-[12px] whitespace-pre-wrap font-sans">{a}</pre>
                  </details>
                ))}
                <div className="glass-card p-3 mt-2">
                  <p className="text-[12px]">Problem nicht geloest? Erstelle ein <a href="https://github.com/MadGapun/PBP/issues/new?labels=bug" target="_blank" rel="noopener noreferrer" className="text-sky hover:underline">GitHub Issue</a> mit einer Beschreibung und den Logs aus Einstellungen.</p>
                </div>
              </div>
            )}

            {helpTab === "bug" && (
              <div className="space-y-3">
                <p className="text-sm text-muted/60">
                  Beschreibe den Fehler moeglichst genau. Ein GitHub-Account wird benoetigt.
                </p>
                <a
                  href="https://github.com/MadGapun/PBP/issues/new?labels=bug&title=%5BBug%5D+"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg bg-coral/15 px-4 py-2.5 text-sm font-medium text-coral hover:bg-coral/25 transition-colors"
                >
                  <ExternalLink size={16} />
                  Bug auf GitHub melden
                </a>
              </div>
            )}

            {helpTab === "feature" && (
              <div className="space-y-3">
                <p className="text-sm text-muted/60">
                  Hast du eine Idee für eine Verbesserung? Erstelle einen Feature-Vorschlag auf GitHub.
                </p>
                <a
                  href="https://github.com/MadGapun/PBP/issues/new?labels=enhancement&title=%5BFeature%5D+"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg bg-sky/15 px-4 py-2.5 text-sm font-medium text-sky hover:bg-sky/25 transition-colors"
                >
                  <ExternalLink size={16} />
                  Feature vorschlagen
                </a>
              </div>
            )}

            {helpTab === "credits" && (
              <div className="space-y-3 text-sm">
                <div className="glass-card p-3">
                  <h3 className="font-medium text-ink mb-2">PBP — Persönliches Bewerbungs-Portal</h3>
                  <p className="text-muted/60">Version: v{chrome.status?.version || "0.32.5"}</p>
                  <p className="text-muted/60">Lizenz: MIT</p>
                </div>
                <div className="glass-card p-3">
                  <h3 className="font-medium text-ink mb-2">Team</h3>
                  <p className="text-muted/60">Markus (MadGapun) — Konzept, Backend, Projektleitung</p>
                  <p className="text-muted/60">Toms (Koala280) — React-Frontend</p>
                  <p className="text-muted/60">Claude — KI-Assistent & Co-Developer</p>
                  <p className="text-muted/60">Codex (TANTE) — Frontend-Recovery & Co-Developer</p>
                </div>
                <div className="glass-card p-3 border border-sky/15">
                  <div className="flex items-center gap-2 mb-2">
                    <Coffee size={16} className="text-amber" />
                    <h3 className="font-medium text-ink">Kaffee spendieren</h3>
                  </div>
                  <p className="text-muted/60 mb-3">PBP ist kostenlos und bleibt es. Wenn dir das Tool bei deiner Jobsuche hilft, kannst du mir einen Kaffee spendieren.</p>
                  <a
                    href="https://paypal.me/birzite"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-sky/10 text-sky hover:bg-sky/20 transition-colors text-sm"
                  >
                    <Heart size={14} />
                    Unterstützen via PayPal
                  </a>
                </div>
                <div className="glass-card p-3 border border-amber/15">
                  <h3 className="font-medium text-ink mb-2">Rechtliche Hinweise</h3>
                  <div className="space-y-1.5 text-muted/60 text-[12px]">
                    <p><strong>Jobsuche / Scraping:</strong> Die Stellensuche greift auf öffentlich zugängliche Daten von Jobportalen zu (z.B. Bundesagentur für Arbeit, LinkedIn, XING, StepStone). Die Nutzung erfolgt auf eigene Verantwortung. Bitte beachte die jeweiligen Nutzungsbedingungen der Plattformen.</p>
                    <p><strong>Datenspeicherung:</strong> Alle Daten werden ausschließlich lokal auf deinem Gerät gespeichert. Es findet keine Übertragung an Dritte statt.</p>
                    <p><strong>Keine Gewähr:</strong> PBP übernimmt keine Gewähr für die Vollständigkeit, Richtigkeit oder Aktualität der gesammelten Stellenangebote.</p>
                    <p><strong>Verantwortung:</strong> Du bist selbst dafür verantwortlich, dass deine Nutzung der Jobsuche-Funktion im Einklang mit den Nutzungsbedingungen der jeweiligen Plattformen steht.</p>
                  </div>
                </div>
                <a
                  href="https://github.com/MadGapun/PBP"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sky hover:underline"
                >
                  <ExternalLink size={14} />
                  github.com/MadGapun/PBP
                </a>
              </div>
            )}
          </Modal>
        )}

        {/* MCP Verbindungshilfe-Dialog (#309) */}
        {mcpHelpOpen && (
          <Modal open={mcpHelpOpen} title="MCP-Verbindung" onClose={() => setMcpHelpOpen(false)}>
            {(() => {
              const conn = chrome.status?.mcp_connection;
              const st = conn?.status || "disconnected";
              return (
                <div className="space-y-4 text-sm">
                  {st === "unknown" && (
                    <>
                      <div className="glass-card p-3 border-amber/20 border">
                        <h3 className="font-medium text-amber mb-1">Verbindung wird gepr&uuml;ft</h3>
                        <p className="text-muted/60">
                          Der MCP-Server hat sich k&uuml;rzlich gemeldet, aber die Verbindung ist nicht best&auml;tigt.
                          Das kann passieren wenn Claude Desktop gerade neu gestartet wurde.
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <h3 className="font-medium text-ink mb-2">Verbindung testen</h3>
                        <p className="text-muted/60 mb-3">
                          &Ouml;ffne Claude Desktop und sende eine kurze Nachricht wie
                          <span className="mx-1 px-1.5 py-0.5 bg-white/[0.06] rounded text-ink font-mono text-xs">Zeige meinen Profil-Status</span>
                          um die Verbindung zu pr&uuml;fen.
                        </p>
                        <button
                          type="button"
                          onClick={() => { window.open("claude://", "_self"); setMcpHelpOpen(false); }}
                          className="w-full py-2 px-4 rounded-lg bg-amber/15 text-amber font-medium hover:bg-amber/25 transition-colors"
                        >
                          Claude Desktop &ouml;ffnen &amp; testen
                        </button>
                      </div>
                    </>
                  )}
                  {st === "disconnected" && (
                    <>
                      <div className="glass-card p-3 border-coral/20 border">
                        <h3 className="font-medium text-coral mb-1">Nicht verbunden</h3>
                        <p className="text-muted/60">
                          Der MCP-Server antwortet nicht. Das bedeutet, dass Claude Desktop
                          nicht l&auml;uft oder der Bewerbungs-Assistent nicht konfiguriert ist.
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <h3 className="font-medium text-ink mb-2">Fehlerbehebung</h3>
                        <ol className="space-y-2 text-muted/60 list-decimal list-inside">
                          <li>
                            <strong className="text-ink">Claude Desktop &ouml;ffnen</strong>
                            <span className="block ml-5 mt-0.5">Stelle sicher, dass Claude Desktop l&auml;uft (nicht nur der Browser).</span>
                          </li>
                          <li>
                            <strong className="text-ink">MCP-Server pr&uuml;fen</strong>
                            <span className="block ml-5 mt-0.5">
                              In Claude Desktop: Einstellungen &rarr; Developer &rarr; &bdquo;bewerbungs-assistent&ldquo; sollte als MCP-Server gelistet sein.
                            </span>
                          </li>
                          <li>
                            <strong className="text-ink">Server-Status testen</strong>
                            <span className="block ml-5 mt-0.5">
                              Pr&uuml;fe ob <a href="http://localhost:8200" target="_blank" rel="noreferrer" className="text-sky underline">localhost:8200</a> erreichbar ist.
                            </span>
                          </li>
                          <li>
                            <strong className="text-ink">Claude Desktop neu starten</strong>
                            <span className="block ml-5 mt-0.5">Beende Claude Desktop vollst&auml;ndig und starte es neu.</span>
                          </li>
                        </ol>
                      </div>
                      <button
                        type="button"
                        onClick={() => { window.open("claude://", "_self"); setMcpHelpOpen(false); }}
                        className="w-full py-2 px-4 rounded-lg bg-coral/15 text-coral font-medium hover:bg-coral/25 transition-colors"
                      >
                        Claude Desktop &ouml;ffnen
                      </button>
                    </>
                  )}
                </div>
              );
            })()}
          </Modal>
        )}

        <GlobalDocumentDropZone
          hasActiveProfile={Boolean(activeProfileId)}
          profileName={chrome.profile?.name}
          refreshChrome={refreshChrome}
          pushToast={pushToast}
        />
      </div>
    </AppContext.Provider>
  );
}

