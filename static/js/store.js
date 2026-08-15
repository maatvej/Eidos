// filename: static/js/store.js
/**
 * Advanced Reactive State Store using JavaScript Proxy pattern.
 * Supports fine-grained key subscriptions, toast notification system,
 * theme transition locking, and localStorage persistence.
 */

export class Store {
  /**
   * @param {Object} initialState - Initial application state object
   */
  constructor(initialState = {}) {
    this.rawState = { ...initialState };
    this.listeners = new Set();
    this.state = new Proxy(this.rawState, {
      get: (target, prop) => {
        return target[prop];
      },
      set: (target, key, value) => {
        const oldValue = target[key];
        target[key] = value;
        if (oldValue !== value) {
          this.notify(key, value, oldValue);
        }
        return true;
      },
    });
  }

  /**
   * Subscribes a callback function to state updates.
   * @param {Function} listener - Callback function receiving current state, modified key, and oldValue
   * @param {Array<string>|null} filterKeys - Optional list of keys to watch. If provided, listener only executes on matching key changes.
   * @returns {Function} Unsubscribe function
   */
  subscribe(listener, filterKeys = null) {
    const subscriber = { listener, filterKeys };
    this.listeners.add(subscriber);
    // Execute immediately on subscription for initial sync
    try {
      listener(this.state, null, null);
    } catch (err) {
      console.error("[Store] Subscription execution error:", err);
    }
    return () => this.listeners.delete(subscriber);
  }

  /**
   * Notifies active subscribers of state changes.
   * @param {string} changedKey
   * @param {*} newValue
   * @param {*} oldValue
   */
  notify(changedKey, newValue, oldValue) {
    this.listeners.forEach(({ listener, filterKeys }) => {
      if (filterKeys && !filterKeys.includes(changedKey)) {
        return;
      }
      try {
        listener(this.state, changedKey, oldValue);
      } catch (err) {
        console.error("[Store] Listener error:", err);
      }
    });
  }

  /**
   * Merges new state properties into existing state atomically.
   * All target properties are written before subscriber notifications are triggered.
   * @param {Object} newState - Partial state update
   */
  setState(newState) {
    if (!newState || typeof newState !== "object") return;
    const changed = [];
    for (const [key, value] of Object.entries(newState)) {
      const oldValue = this.rawState[key];
      if (oldValue !== value) {
        this.rawState[key] = value;
        changed.push({ key, value, oldValue });
      }
    }
    for (const { key, value, oldValue } of changed) {
      this.notify(key, value, oldValue);
    }
  }
}

// Initial theme determination with FOUC safety
const getInitialTheme = () => {
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

/**
 * Session & Local storage helpers for job state and view persistence
 */
export const StorageHelper = {
  ACTIVE_JOB_KEY: "eidos_active_job_id",
  JOB_STATE_KEY: "eidos_active_job_state",
  LAST_VIEW_KEY: "eidos_last_view",

  saveActiveJob(jobId) {
    if (!jobId) return;
    try {
      sessionStorage.setItem(this.ACTIVE_JOB_KEY, jobId);
      localStorage.setItem(this.ACTIVE_JOB_KEY, jobId);
    } catch (e) {
      console.warn("[Storage] Failed to save active job:", e);
    }
  },

  getActiveJob() {
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

  saveJobState(state) {
    if (!state) return;
    try {
      if (!state.jobId) {
        this.clearActiveJob();
        return;
      }
      const payload = {
        jobId: state.jobId,
        status: state.status || "IDLE",
        progress: typeof state.progress === "number" ? state.progress : 0,
        stepMessage: state.stepMessage || "",
        transcript: state.transcript || null,
        errorMessage: state.errorMessage || null,
        currentTime: typeof state.currentTime === "number" ? state.currentTime : 0,
        initialAudioTime: typeof state.initialAudioTime === "number" ? state.initialAudioTime : 0,
        initialSearchQuery: state.initialSearchQuery || "",
        savedAt: Date.now(),
      };
      const serialized = JSON.stringify(payload);
      sessionStorage.setItem(this.JOB_STATE_KEY, serialized);
      localStorage.setItem(this.JOB_STATE_KEY, serialized);
      this.saveActiveJob(state.jobId);
    } catch (e) {
      console.warn("[Storage] Failed to save job state snapshot:", e);
    }
  },

  getSavedJobState() {
    try {
      const raw =
        sessionStorage.getItem(this.JOB_STATE_KEY) ||
        localStorage.getItem(this.JOB_STATE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed && parsed.jobId) {
        return parsed;
      }
      return null;
    } catch (e) {
      console.warn("[Storage] Failed to parse saved job state:", e);
      return null;
    }
  },

  saveLastView(viewName) {
    try {
      sessionStorage.setItem(this.LAST_VIEW_KEY, viewName);
    } catch (e) {
      console.warn("[Storage] Failed to save last view:", e);
    }
  },

  getLastView() {
    try {
      return sessionStorage.getItem(this.LAST_VIEW_KEY) || "studio";
    } catch (e) {
      return "studio";
    }
  },
};

// Compute initial state from persistent storage if available
const getInitialJobState = () => {
  const saved = StorageHelper.getSavedJobState();
  if (saved && saved.jobId) {
    return {
      jobId: saved.jobId,
      status: saved.status || "IDLE",
      progress: typeof saved.progress === "number" ? saved.progress : 0,
      stepMessage: saved.stepMessage || "",
      transcript: saved.transcript || null,
      errorMessage: saved.errorMessage || null,
      currentTime: typeof saved.currentTime === "number" ? saved.currentTime : 0.0,
      initialAudioTime: typeof saved.initialAudioTime === "number" ? saved.initialAudioTime : 0.0,
      initialSearchQuery: saved.initialSearchQuery || "",
    };
  }

  const activeJobId = StorageHelper.getActiveJob();
  if (activeJobId) {
    return {
      jobId: activeJobId,
      status: "LOADING",
      progress: 10,
      stepMessage: "Восстановление состояния...",
      transcript: null,
      errorMessage: null,
      currentTime: 0.0,
      initialAudioTime: 0.0,
      initialSearchQuery: "",
    };
  }

  return {
    jobId: null,
    status: "IDLE",
    progress: 0,
    stepMessage: "",
    transcript: null,
    errorMessage: null,
    currentTime: 0.0,
    initialAudioTime: 0.0,
    initialSearchQuery: "",
  };
};

const initialJobState = getInitialJobState();

// Global Application Reactive Store Instance
export const globalStore = new Store({
  ...initialJobState,
  currentRoute: typeof window !== "undefined" ? window.location.pathname || "/" : "/",
  currentView: StorageHelper.getLastView(),
  theme: getInitialTheme(),
  user: null,
});

// Automatically synchronize state changes to persistent storage
globalStore.subscribe(
  (state) => {
    if (state.jobId) {
      StorageHelper.saveJobState(state);
    } else if (state.status === "IDLE") {
      StorageHelper.clearActiveJob();
    }
  },
  ["jobId", "status", "progress", "stepMessage", "transcript", "errorMessage", "currentTime"]
);

/**
 * Asynchronously hydrates job data from the backend into the global reactive store.
 * Supports fallback to account transcription records for persistent historical links.
 *
 * @param {string} jobId - Unique UUID of the job or transcription
 * @param {Object} [options] - Optional initial params (seekTime, searchQuery, forceReload)
 * @returns {Promise<boolean>} True if hydrated successfully, false otherwise
 */
export async function hydrateJob(jobId, options = {}) {
  if (!jobId) return false;

  const seekTime = options.seekTime !== undefined ? parseFloat(options.seekTime) || 0 : null;
  const searchQuery = options.searchQuery !== undefined ? options.searchQuery : null;
  const forceReload = options.forceReload === true;

  StorageHelper.saveActiveJob(jobId);

  const current = globalStore.state;
  const isSameJob = current.jobId === jobId;

  // If already loaded and SUCCESS with transcript, just update seek & search unless forceReload is set
  if (isSameJob && current.status === "SUCCESS" && current.transcript && !forceReload) {
    const updates = {};
    if (seekTime !== null) {
      updates.currentTime = seekTime;
      updates.initialAudioTime = seekTime;
    }
    if (searchQuery !== null) {
      updates.initialSearchQuery = searchQuery;
    }
    if (Object.keys(updates).length > 0) {
      globalStore.setState(updates);
    }
    return true;
  }

  // Non-destructive initial state setup
  const updatePayload = {
    jobId,
    errorMessage: null,
  };

  if (seekTime !== null) {
    updatePayload.currentTime = seekTime;
    updatePayload.initialAudioTime = seekTime;
  }
  if (searchQuery !== null) {
    updatePayload.initialSearchQuery = searchQuery;
  }

  if (isSameJob && current.transcript) {
    // Retain existing transcript while re-validating
    updatePayload.status = current.status || "LOADING";
    updatePayload.progress = typeof current.progress === "number" ? current.progress : 10;
    updatePayload.stepMessage = current.stepMessage || "Синхронизация с сервером...";
  } else {
    updatePayload.status = "LOADING";
    updatePayload.progress = isSameJob && typeof current.progress === "number" && current.progress > 0 ? current.progress : 10;
    updatePayload.stepMessage = isSameJob && current.stepMessage ? current.stepMessage : "Восстановление состояния и данных расшифровки...";
    if (!isSameJob) {
      updatePayload.transcript = null;
    }
  }

  globalStore.setState(updatePayload);

  try {
    // 1. First attempt: fetch from active transcription jobs endpoint
    const jobRes = await fetch(`/api/v1/transcription/jobs/${jobId}`);
    if (jobRes.ok) {
      const jobData = await jobRes.json();
      const statusLower = (jobData.status || "").toLowerCase();

      if (statusLower === "completed" && jobData.result) {
        globalStore.setState({
          jobId,
          status: "SUCCESS",
          progress: 100,
          stepMessage: "Стенограмма готова",
          transcript: jobData.result,
          errorMessage: null,
        });
        return true;
      }

      if (statusLower === "failed") {
        globalStore.setState({
          jobId,
          status: "ERROR",
          progress: 0,
          errorMessage: jobData.error_message || "Ошибка при выполнении расшифровки.",
        });
        return false;
      }

      if (statusLower === "cancelled") {
        globalStore.setState({
          jobId,
          status: "ERROR",
          progress: 0,
          errorMessage: "Обработка задачи была отменена.",
        });
        return false;
      }

      // Pending or Processing status
      globalStore.setState({
        jobId,
        status: "LOADING",
        progress: jobData.progress_percentage || 25,
        stepMessage: jobData.current_step || "ИИ-обработка аудиозаписи...",
      });
      return true;
    }

    // 2. Fallback attempt: fetch from account transcriptions history endpoint
    const historyRes = await fetch(`/api/v1/account/transcriptions/${jobId}`);
    if (historyRes.ok) {
      const historyData = await historyRes.json();
      const statusLower = (historyData.status || "").toLowerCase();

      if (statusLower === "completed" && historyData.result) {
        globalStore.setState({
          jobId,
          status: "SUCCESS",
          progress: 100,
          stepMessage: "Стенограмма готова",
          transcript: historyData.result,
          errorMessage: null,
        });
        return true;
      }

      // Reconstruct transcript object if only transcription_text & metadata are present
      if (statusLower === "completed" && historyData.transcription_text) {
        const synthesizedResult = {
          utterances: [
            {
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

        globalStore.setState({
          jobId,
          status: "SUCCESS",
          progress: 100,
          stepMessage: "Стенограмма готова",
          transcript: synthesizedResult,
          errorMessage: null,
        });
        return true;
      }

      if (statusLower === "failed") {
        globalStore.setState({
          jobId,
          status: "ERROR",
          progress: 0,
          errorMessage: historyData.error_message || "Ошибка при обработке записи.",
        });
        return false;
      }

      globalStore.setState({
        jobId,
        status: "LOADING",
        progress: 50,
        stepMessage: "Обработка аудиофайла...",
      });
      return true;
    }

    // If endpoints returned not found, but we already have valid restored transcript, keep it
    if (isSameJob && globalStore.state.transcript && globalStore.state.status === "SUCCESS") {
      return true;
    }

    // Not found
    globalStore.setState({
      jobId,
      status: "ERROR",
      errorMessage: "Указанная запись или задача транскрипции не найдена.",
    });
    return false;
  } catch (err) {
    console.error("[Hydration] Error hydrating job:", err);
    if (isSameJob && globalStore.state.transcript && globalStore.state.status === "SUCCESS") {
      return true;
    }
    globalStore.setState({
      jobId,
      status: "ERROR",
      errorMessage: "Сетевой сбой при восстановлении данных задачи.",
    });
    return false;
  }
}

/**
 * Robust Theme Switcher with Transition Locking
 * Prevents overlapping transitions, layout shifts, and visual flashes.
 */
let isThemeSwitching = false;

export function applyTheme(newTheme, withTransitionLock = true) {
  const root = document.documentElement;
  const oldTheme = root.getAttribute("data-theme") || "dark";

  if (withTransitionLock) {
    root.classList.add("theme-transitioning");
  }

  root.setAttribute("data-theme", newTheme);
  if (newTheme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }

  try {
    localStorage.setItem("eidos_theme", newTheme);
  } catch (e) {
    console.warn("[Theme] Unable to persist theme to localStorage:", e);
  }

  globalStore.setState({ theme: newTheme });

  if (withTransitionLock) {
    setTimeout(() => {
      root.classList.remove("theme-transitioning");
    }, 300);
  }
}

export function toggleTheme() {
  if (isThemeSwitching) return;
  isThemeSwitching = true;

  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const target = current === "dark" ? "light" : "dark";

  applyTheme(target, true);

  showToast(
    `Тема переключена на ${target === "dark" ? "тёмную" : "светлую"}`,
    "info",
    2000
  );

  setTimeout(() => {
    isThemeSwitching = false;
  }, 350);
}

/**
 * Toast Notification Utility
 * @param {string} message - Text message to display
 * @param {"success" | "error" | "info"} type - Notification type
 * @param {number} duration - Auto-dismiss timeout in ms
 */
export function showToast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", "alert");

  const messageSpan = document.createElement("span");
  messageSpan.textContent = message;

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.innerHTML = "&times;";
  closeBtn.setAttribute("aria-label", "Закрыть уведомление");
  closeBtn.style.cssText =
    "background:none; border:none; color:inherit; font-size:1.2rem; cursor:pointer; padding:0 4px; line-height:1; opacity:0.8; transition:opacity 0.2s;";
  closeBtn.addEventListener("mouseenter", () => (closeBtn.style.opacity = "1"));
  closeBtn.addEventListener("mouseleave", () => (closeBtn.style.opacity = "0.8"));

  const removeToast = () => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      toast.style.transition = "opacity 0.25s ease, transform 0.25s ease";
      setTimeout(() => toast.remove(), 250);
    }
  };

  closeBtn.addEventListener("click", removeToast);

  toast.appendChild(messageSpan);
  toast.appendChild(closeBtn);
  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}
