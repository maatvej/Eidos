/**
 * Centralized Application Store using Zustand.
 * Manages active job state, audio playback synchronization, theme, user profile, and persistent cache.
 */

import { create } from "zustand";
import {
  AccountTab,
  AppTheme,
  AppView,
  TranscriptionJobEntity,
  TranscriptionResult,
  UIJobStatus,
  UserProfile,
} from "../types";
import { showToast } from "./toastStore";

interface SavedJobSnapshot {
  jobId: string;
  status: UIJobStatus;
  progress: number;
  stepMessage: string;
  transcript: TranscriptionResult | null;
  errorMessage: string | null;
  currentTime: number;
  initialAudioTime: number;
  initialSearchQuery: string;
  savedAt: number;
}

export const StorageHelper = {
  ACTIVE_JOB_KEY: "eidos_active_job_id",
  JOB_STATE_KEY: "eidos_active_job_state",
  LAST_VIEW_KEY: "eidos_last_view",

  saveActiveJob(jobId: string | null) {
    if (!jobId) return;
    try {
      sessionStorage.setItem(this.ACTIVE_JOB_KEY, jobId);
      localStorage.setItem(this.ACTIVE_JOB_KEY, jobId);
    } catch (e) {
      console.warn("[Storage] Failed to save active job:", e);
    }
  },

  getActiveJob(): string | null {
    try {
      return (
        sessionStorage.getItem(this.ACTIVE_JOB_KEY) ||
        localStorage.getItem(this.ACTIVE_JOB_KEY) ||
        null
      );
    } catch (e) {
      return null;
    }
  },

  clearActiveJob() {
    try {
      sessionStorage.removeItem(this.ACTIVE_JOB_KEY);
      localStorage.removeItem(this.ACTIVE_JOB_KEY);
      sessionStorage.removeItem(this.JOB_STATE_KEY);
      localStorage.removeItem(this.JOB_STATE_KEY);
    } catch (e) {
      console.warn("[Storage] Failed to clear active job:", e);
    }
  },

  saveJobState(snapshot: SavedJobSnapshot) {
    if (!snapshot || !snapshot.jobId) return;
    try {
      const serialized = JSON.stringify(snapshot);
      sessionStorage.setItem(this.JOB_STATE_KEY, serialized);
      localStorage.setItem(this.JOB_STATE_KEY, serialized);
      sessionStorage.setItem(`${this.JOB_STATE_KEY}_${snapshot.jobId}`, serialized);
      localStorage.setItem(`${this.JOB_STATE_KEY}_${snapshot.jobId}`, serialized);
      this.saveActiveJob(snapshot.jobId);
    } catch (e) {
      console.warn("[Storage] Failed to save job state snapshot:", e);
    }
  },

  getSavedJobState(targetJobId: string | null = null): SavedJobSnapshot | null {
    try {
      if (targetJobId) {
        const specificRaw =
          sessionStorage.getItem(`${this.JOB_STATE_KEY}_${targetJobId}`) ||
          localStorage.getItem(`${this.JOB_STATE_KEY}_${targetJobId}`);
        if (specificRaw) {
          const parsed = JSON.parse(specificRaw);
          if (parsed && parsed.jobId === targetJobId) {
            return parsed;
          }
        }
      }
      const raw =
        sessionStorage.getItem(this.JOB_STATE_KEY) ||
        localStorage.getItem(this.JOB_STATE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed && parsed.jobId) {
        if (targetJobId && parsed.jobId !== targetJobId) {
          return null;
        }
        return parsed;
      }
      return null;
    } catch (e) {
      console.warn("[Storage] Failed to parse saved job state:", e);
      return null;
    }
  },

  saveLastView(viewName: AppView) {
    try {
      sessionStorage.setItem(this.LAST_VIEW_KEY, viewName);
    } catch (e) {
      console.warn("[Storage] Failed to save last view:", e);
    }
  },

  getLastView(): AppView {
    try {
      const v = sessionStorage.getItem(this.LAST_VIEW_KEY);
      return v === "account" ? "account" : "studio";
    } catch (e) {
      return "studio";
    }
  },
};

const getInitialTheme = (): AppTheme => {
  try {
    const saved = localStorage.getItem("eidos_theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  } catch (e) {
    return "dark";
  }
};

const getInitialJobSnapshot = () => {
  if (typeof window !== "undefined") {
    const pathname = window.location.pathname || "";
    const jobMatch = pathname.match(/^\/(?:jobs|transcriptions|job|transcription)\/([^/?#]+)/);
    if (jobMatch && jobMatch[1]) {
      const urlJobId = decodeURIComponent(jobMatch[1]);
      const saved = StorageHelper.getSavedJobState(urlJobId);
      if (saved && saved.jobId === urlJobId) {
        return saved;
      }
      return {
        jobId: urlJobId,
        status: "LOADING" as UIJobStatus,
        progress: 10,
        stepMessage: "Восстановление состояния и данных расшифровки...",
        transcript: null,
        errorMessage: null,
        currentTime: 0.0,
        initialAudioTime: 0.0,
        initialSearchQuery: "",
        savedAt: Date.now(),
      };
    }
  }

  return {
    jobId: null,
    status: "IDLE" as UIJobStatus,
    progress: 0,
    stepMessage: "",
    transcript: null,
    errorMessage: null,
    currentTime: 0.0,
    initialAudioTime: 0.0,
    initialSearchQuery: "",
    savedAt: Date.now(),
  };
};

const getInitialAccountTab = (): AccountTab => {
  if (typeof window !== "undefined") {
    const pathname = window.location.pathname || "";
    if (pathname.includes("/profile")) return "profile";
    if (pathname.includes("/security")) return "security";
  }
  return "history";
};

export interface NavigateOptions {
  replace?: boolean;
  seekTime?: number;
  searchQuery?: string;
  forceReload?: boolean;
  resetState?: boolean;
}

interface AppState {
  theme: AppTheme;
  user: UserProfile | null;
  currentView: AppView;
  currentRoute: string;
  accountTab: AccountTab;

  // Job & Transcription state
  jobId: string | null;
  status: UIJobStatus;
  progress: number;
  stepMessage: string;
  transcript: TranscriptionResult | null;
  errorMessage: string | null;
  currentTime: number;
  initialAudioTime: number;
  initialSearchQuery: string;

  // Actions
  setTheme: (theme: AppTheme) => void;
  toggleTheme: () => void;
  setUser: (user: UserProfile | null) => void;
  setView: (view: AppView, updateUrl?: boolean) => void;
  setAccountTab: (tab: AccountTab, updateUrl?: boolean) => void;
  setCurrentRoute: (route: string) => void;
  setJobState: (partial: Partial<AppState>) => void;
  setCurrentTime: (time: number) => void;
  resetJobState: () => void;
  hydrateJob: (jobId: string, options?: { seekTime?: number; searchQuery?: string; forceReload?: boolean }) => Promise<boolean>;
  navigate: (path: string, options?: NavigateOptions) => Promise<void>;
  resolveCurrentRoute: (
    pathname: string,
    search?: string,
    options?: { seekTime?: number; searchQuery?: string; forceReload?: boolean }
  ) => Promise<void>;
  renameSpeakerInState: (oldName: string, newName: string) => void;
}

const initialSnapshot = getInitialJobSnapshot();

export const useAppStore = create<AppState>((set, get) => ({
  theme: getInitialTheme(),
  user: null,
  currentView:
    typeof window !== "undefined" && window.location.pathname.startsWith("/account")
      ? "account"
      : StorageHelper.getLastView(),
  currentRoute: typeof window !== "undefined" ? window.location.pathname || "/" : "/",
  accountTab: getInitialAccountTab(),

  jobId: initialSnapshot.jobId,
  status: initialSnapshot.status,
  progress: initialSnapshot.progress,
  stepMessage: initialSnapshot.stepMessage,
  transcript: initialSnapshot.transcript,
  errorMessage: initialSnapshot.errorMessage,
  currentTime: initialSnapshot.currentTime,
  initialAudioTime: initialSnapshot.initialAudioTime,
  initialSearchQuery: initialSnapshot.initialSearchQuery,

  setTheme: (newTheme: AppTheme) => {
    const root = document.documentElement;
    root.classList.add("theme-transitioning");
    root.setAttribute("data-theme", newTheme);
    if (newTheme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    try {
      localStorage.setItem("eidos_theme", newTheme);
    } catch (e) {}

    set({ theme: newTheme });

    setTimeout(() => {
      root.classList.remove("theme-transitioning");
    }, 300);
  },

  toggleTheme: () => {
    const current = get().theme;
    const target: AppTheme = current === "dark" ? "light" : "dark";
    get().setTheme(target);
    showToast(`Тема переключена на ${target === "dark" ? "тёмную" : "светлую"}`, "info", 2000);
  },

  setUser: (user) => set({ user }),

  setView: (view, updateUrl = true) => {
    StorageHelper.saveLastView(view);
    set({ currentView: view });
    if (updateUrl && typeof window !== "undefined") {
      const targetPath =
        view === "account" ? `/account/${get().accountTab || "history"}` : "/";
      window.history.pushState({}, "", targetPath);
      set({ currentRoute: targetPath });
    }
  },

  setAccountTab: (tab, updateUrl = true) => {
    set({ accountTab: tab, currentView: "account" });
    StorageHelper.saveLastView("account");
    if (updateUrl && typeof window !== "undefined") {
      const targetPath = `/account/${tab}`;
      window.history.pushState({}, "", targetPath);
      set({ currentRoute: targetPath });
    }
  },

  setCurrentRoute: (currentRoute) => set({ currentRoute }),

  setJobState: (partial) => {
    set((state) => {
      const updated = { ...state, ...partial };
      if (updated.jobId && updated.status !== "IDLE") {
        StorageHelper.saveJobState({
          jobId: updated.jobId,
          status: updated.status,
          progress: updated.progress,
          stepMessage: updated.stepMessage,
          transcript: updated.transcript,
          errorMessage: updated.errorMessage,
          currentTime: updated.currentTime,
          initialAudioTime: updated.initialAudioTime,
          initialSearchQuery: updated.initialSearchQuery,
          savedAt: Date.now(),
        });
      }
      return partial;
    });
  },

  setCurrentTime: (currentTime) => set({ currentTime }),

  resetJobState: () => {
    StorageHelper.clearActiveJob();
    set({
      jobId: null,
      status: "IDLE",
      progress: 0,
      stepMessage: "",
      transcript: null,
      errorMessage: null,
      currentTime: 0,
      initialAudioTime: 0,
      initialSearchQuery: "",
    });
  },

  navigate: async (path: string, options: NavigateOptions = {}) => {
    const { replace = false, resetState = false, ...resolveOpts } = options;

    if (typeof window !== "undefined") {
      if (replace) {
        window.history.replaceState({}, "", path);
      } else {
        window.history.pushState({}, "", path);
      }
    }

    if (resetState) {
      get().resetJobState();
    }

    const [pathname, searchStr] = path.split("?");
    const search = searchStr ? `?${searchStr}` : "";
    await get().resolveCurrentRoute(pathname, search, resolveOpts);
  },

  resolveCurrentRoute: async (
    pathname: string,
    search: string = "",
    options: { seekTime?: number; searchQuery?: string; forceReload?: boolean } = {}
  ) => {
    const fullPath = pathname + (search ? (search.startsWith("?") ? search : `?${search}`) : "");
    set({ currentRoute: fullPath });
    const searchParams = new URLSearchParams(search);

    // 1. Account Routes (/account, /account/history, /account/profile, /account/security)
    if (pathname.startsWith("/account")) {
      let tab: AccountTab = "history";
      if (pathname.includes("/profile")) {
        tab = "profile";
      } else if (pathname.includes("/security")) {
        tab = "security";
      }
      StorageHelper.saveLastView("account");
      set({ currentView: "account", accountTab: tab });
      return;
    }

    // 2. Job / Transcription Studio Routes (/jobs/:id, /job/:id, /transcriptions/:id, /transcription/:id)
    const jobMatch = pathname.match(/^\/(?:jobs|transcriptions|job|transcription)\/([^/?#]+)/);
    if (jobMatch && jobMatch[1]) {
      const targetJobId = decodeURIComponent(jobMatch[1]);
      StorageHelper.saveLastView("studio");
      set({ currentView: "studio" });
      const seekTime =
        options.seekTime !== undefined
          ? options.seekTime
          : searchParams.get("t")
          ? parseFloat(searchParams.get("t")!)
          : undefined;
      const searchQuery =
        options.searchQuery !== undefined
          ? options.searchQuery
          : searchParams.get("q") || undefined;
      await get().hydrateJob(targetJobId, {
        seekTime,
        searchQuery,
        forceReload: options.forceReload,
      });
      return;
    }

    // 3. Root / Studio Routes (/ or /studio or /dashboard)
    StorageHelper.saveLastView("studio");
    set({ currentView: "studio" });
    if (pathname === "/" || pathname === "/studio" || pathname === "/dashboard") {
      get().resetJobState();
    }
  },

  hydrateJob: async (jobId, options = {}) => {
    if (!jobId) return false;
    const { seekTime, searchQuery, forceReload = false } = options;

    StorageHelper.saveActiveJob(jobId);
    const current = get();
    const isSameJob = current.jobId === jobId;

    if (isSameJob && current.status === "SUCCESS" && current.transcript && !forceReload) {
      const updates: Partial<AppState> = {};
      if (seekTime !== undefined) {
        updates.currentTime = seekTime;
        updates.initialAudioTime = seekTime;
      }
      if (searchQuery !== undefined) {
        updates.initialSearchQuery = searchQuery;
      }
      if (Object.keys(updates).length > 0) {
        get().setJobState(updates);
      }
      return true;
    }

    const updatePayload: Partial<AppState> = {
      jobId,
      errorMessage: null,
    };

    if (seekTime !== undefined) {
      updatePayload.currentTime = seekTime;
      updatePayload.initialAudioTime = seekTime;
    }
    if (searchQuery !== undefined) {
      updatePayload.initialSearchQuery = searchQuery;
    }

    if (isSameJob && current.transcript) {
      updatePayload.status = current.status || "LOADING";
      updatePayload.progress = typeof current.progress === "number" ? current.progress : 10;
      updatePayload.stepMessage = current.stepMessage || "Синхронизация с сервером...";
    } else {
      const saved = StorageHelper.getSavedJobState(jobId);
      if (saved && saved.jobId === jobId && saved.transcript) {
        updatePayload.status = saved.status || "SUCCESS";
        updatePayload.progress = typeof saved.progress === "number" ? saved.progress : 100;
        updatePayload.stepMessage = saved.stepMessage || "Стенограмма готова";
        updatePayload.transcript = saved.transcript;
      } else {
        updatePayload.status = "LOADING";
        updatePayload.progress = isSameJob && current.progress > 0 ? current.progress : 10;
        updatePayload.stepMessage = isSameJob && current.stepMessage ? current.stepMessage : "Восстановление состояния и данных расшифровки...";
        if (!isSameJob) {
          updatePayload.transcript = null;
        }
      }
    }

    get().setJobState(updatePayload);

    try {
      // 1. Check transcription jobs endpoint
      const jobRes = await fetch(`/api/v1/transcription/jobs/${jobId}`);
      if (jobRes.ok) {
        const jobData: TranscriptionJobEntity = await jobRes.json();
        const statusUpper = (jobData.status || "").toUpperCase();

        if (statusUpper === "COMPLETED" && jobData.result) {
          get().setJobState({
            jobId,
            status: "SUCCESS",
            progress: 100,
            stepMessage: "Стенограмма готова",
            transcript: jobData.result,
            errorMessage: null,
          });
          return true;
        }

        if (statusUpper === "FAILED") {
          get().setJobState({
            jobId,
            status: "ERROR",
            progress: 0,
            errorMessage: jobData.error_message || "Ошибка при выполнении расшифровки.",
          });
          return false;
        }

        if (statusUpper === "CANCELLED") {
          get().setJobState({
            jobId,
            status: "ERROR",
            progress: 0,
            errorMessage: "Обработка задачи была отменена.",
          });
          return false;
        }

        get().setJobState({
          jobId,
          status: "LOADING",
          progress: jobData.progress_percentage || 25,
          stepMessage: jobData.current_step || "ИИ-обработка аудиозаписи...",
        });
        return true;
      }

      // 2. Check account transcriptions endpoint
      const historyRes = await fetch(`/api/v1/account/transcriptions/${jobId}`);
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        const statusUpper = (historyData.status || "").toUpperCase();

        if (statusUpper === "COMPLETED" && historyData.result) {
          get().setJobState({
            jobId,
            status: "SUCCESS",
            progress: 100,
            stepMessage: "Стенограмма готова",
            transcript: historyData.result,
            errorMessage: null,
          });
          return true;
        }

        if (statusUpper === "COMPLETED" && historyData.transcription_text) {
          const rawBlocks = historyData.transcription_text.split(/\n\n+/);
          const parsedUtterances = rawBlocks
            .map((block: string, idx: number) => {
              const colonIdx = block.indexOf(":");
              if (colonIdx > 0 && colonIdx < 50) {
                const speaker = block.substring(0, colonIdx).trim();
                const text = block.substring(colonIdx + 1).trim();
                return {
                  id: `synth_${idx}`,
                  speaker: speaker || "Спикер",
                  text: text || block.trim(),
                  start: 0.0,
                  end: historyData.duration_seconds || 0.0,
                  words: [],
                };
              }
              return {
                id: `synth_${idx}`,
                speaker: "Спикер",
                text: block.trim(),
                start: 0.0,
                end: historyData.duration_seconds || 0.0,
                words: [],
              };
            })
            .filter((u: { text: string }) => u.text.length > 0);

          const synthesizedResult: TranscriptionResult = {
            utterances: parsedUtterances.length > 0 ? parsedUtterances : [
              {
                id: "synth_0",
                speaker: "Спикер",
                text: historyData.transcription_text,
                start: 0.0,
                end: historyData.duration_seconds || 0.0,
                words: [],
              },
            ],
            analysis: {
              title: historyData.title || "Стенограмма аудиозаписи",
              timestamp: new Date().toLocaleDateString("ru-RU"),
              executive_summary: historyData.transcription_text.substring(0, 300) + "...",
              overall_sentiment: "NEUTRAL",
              key_decisions: [],
              action_items: [],
            },
            duration_seconds: historyData.duration_seconds || 0.0,
            detected_language: historyData.language || "ru",
          };

          get().setJobState({
            jobId,
            status: "SUCCESS",
            progress: 100,
            stepMessage: "Стенограмма готова",
            transcript: synthesizedResult,
            errorMessage: null,
          });
          return true;
        }

        if (statusUpper === "FAILED") {
          get().setJobState({
            jobId,
            status: "ERROR",
            progress: 0,
            errorMessage: historyData.error_message || "Ошибка при обработке записи.",
          });
          return false;
        }

        get().setJobState({
          jobId,
          status: "LOADING",
          progress: 50,
          stepMessage: "Обработка аудиофайла...",
        });
        return true;
      }

      const fallbackSaved = StorageHelper.getSavedJobState(jobId);
      if (fallbackSaved && fallbackSaved.jobId === jobId && fallbackSaved.transcript) {
        get().setJobState({
          jobId,
          status: fallbackSaved.status || "SUCCESS",
          progress: typeof fallbackSaved.progress === "number" ? fallbackSaved.progress : 100,
          stepMessage: fallbackSaved.stepMessage || "Стенограмма готова",
          transcript: fallbackSaved.transcript,
          errorMessage: null,
        });
        return true;
      }

      get().setJobState({
        jobId,
        status: "ERROR",
        errorMessage: "Указанная запись или задача транскрипции не найдена.",
      });
      return false;
    } catch (err) {
      console.error("[Hydration] Error hydrating job:", err);
      const fallbackSaved = StorageHelper.getSavedJobState(jobId);
      if (fallbackSaved && fallbackSaved.jobId === jobId && fallbackSaved.transcript) {
        get().setJobState({
          jobId,
          status: fallbackSaved.status || "SUCCESS",
          progress: typeof fallbackSaved.progress === "number" ? fallbackSaved.progress : 100,
          stepMessage: fallbackSaved.stepMessage || "Стенограмма готова",
          transcript: fallbackSaved.transcript,
          errorMessage: null,
        });
        return true;
      }
      get().setJobState({
        jobId,
        status: "ERROR",
        errorMessage: "Сетевой сбой при восстановлении данных задачи.",
      });
      return false;
    }
  },

  renameSpeakerInState: (oldName: string, newName: string) => {
    const current = get().transcript;
    if (!current || !current.utterances) return;
    const updated = {
      ...current,
      utterances: current.utterances.map((u) => {
        if (u.speaker === oldName) {
          return {
            ...u,
            speaker: newName,
            words: u.words?.map((w) => (w.speaker === oldName ? { ...w, speaker: newName } : w)),
          };
        }
        return u;
      }),
    };
    get().setJobState({ transcript: updated });
  },
}));
